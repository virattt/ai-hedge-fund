from __future__ import annotations

import json
from typing_extensions import Literal
from pydantic import BaseModel

from src.graph.state import AgentState, show_agent_reasoning
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage

from src.tools.api import (
    get_financial_metrics,
    get_market_cap,
    search_line_items,
)
from src.utils.llm import call_llm
from src.utils.progress import progress


class AswathDamodaranSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: float          # 0‒100
    reasoning: str


def aswath_damodaran_agent(state: AgentState):
    """
    Analyze US equities through Aswath Damodaran's intrinsic-value lens:
      • Cost of Equity via CAPM (risk-free + β·ERP)
      • 5-yr revenue / FCFF growth trends & reinvestment efficiency
      • FCFF-to-Firm DCF → equity value → per-share intrinsic value
      • Cross-check with relative valuation (PE vs. Fwd PE sector median proxy)
    Produces a trading signal and explanation in Damodaran's analytical voice.
    """
    data      = state["data"]
    end_date  = data["end_date"]
    tickers   = data["tickers"]

    analysis_data: dict[str, dict] = {}
    damodaran_signals: dict[str, dict] = {}

    for ticker in tickers:
        # ─── Fetch core data ────────────────────────────────────────────────────
        progress.update_status("aswath_damodaran_agent", ticker, "Fetching financial metrics")
        metrics = get_financial_metrics(ticker, end_date, period="ttm", limit=5)

        progress.update_status("aswath_damodaran_agent", ticker, "Fetching financial line items")
        line_items = search_line_items(
            ticker,
            [
                "free_cash_flow",
                "ebit",
                "interest_expense",
                "capital_expenditure",
                "depreciation_and_amortization",
                "outstanding_shares",
                "net_income",
                "total_debt",
            ],
            end_date,
        )

        progress.update_status("aswath_damodaran_agent", ticker, "Getting market cap")
        market_cap = get_market_cap(ticker, end_date)

        # ─── Analyses ───────────────────────────────────────────────────────────
        progress.update_status("aswath_damodaran_agent", ticker, "Analyzing growth and reinvestment")
        growth_analysis = analyze_growth_and_reinvestment(metrics, line_items)

        progress.update_status("aswath_damodaran_agent", ticker, "Analyzing risk profile")
        risk_analysis = analyze_risk_profile(metrics, line_items)

        progress.update_status("aswath_damodaran_agent", ticker, "Calculating intrinsic value (DCF)")
        intrinsic_val_analysis = calculate_intrinsic_value_dcf(metrics, line_items, risk_analysis)

        progress.update_status("aswath_damodaran_agent", ticker, "Assessing relative valuation")
        relative_val_analysis = analyze_relative_valuation(metrics)

        # ─── Score & margin of safety ──────────────────────────────────────────
        total_score = (
            growth_analysis["score"]
            + risk_analysis["score"]
            + relative_val_analysis["score"]
        )
        max_score = growth_analysis["max_score"] + risk_analysis["max_score"] + relative_val_analysis["max_score"]

        intrinsic_value = intrinsic_val_analysis["intrinsic_value"]
        margin_of_safety = (
            (intrinsic_value - market_cap) / market_cap if intrinsic_value and market_cap else None
        )

        # Decision rules (Damodaran tends to act with ~20-25 % MOS)
        if margin_of_safety is not None and margin_of_safety >= 0.25:
            signal = "bullish"
        elif margin_of_safety is not None and margin_of_safety <= -0.25:
            signal = "bearish"
        else:
            signal = "neutral"

        confidence = min(max(abs(margin_of_safety or 0) * 200, 10), 100)  # simple proxy 10-100

        analysis_data[ticker] = {
            "signal": signal,
            "score": total_score,
            "max_score": max_score,
            "margin_of_safety": margin_of_safety,
            "growth_analysis": growth_analysis,
            "risk_analysis": risk_analysis,
            "relative_val_analysis": relative_val_analysis,
            "intrinsic_val_analysis": intrinsic_val_analysis,
            "market_cap": market_cap,
        }

        # ─── LLM: craft Damodaran-style narrative ──────────────────────────────
        progress.update_status("aswath_damodaran_agent", ticker, "Generating Damodaran analysis")
        damodaran_output = generate_damodaran_output(
            ticker=ticker,
            analysis_data=analysis_data,
            state=state,
        )

        damodaran_signals[ticker] = damodaran_output.model_dump()

        progress.update_status("aswath_damodaran_agent", ticker, "Done", analysis=damodaran_output.reasoning)

    # ─── Push message back to graph state ──────────────────────────────────────
    message = HumanMessage(content=json.dumps(damodaran_signals), name="aswath_damodaran_agent")

    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(damodaran_signals, "Aswath Damodaran Agent")

    state["data"]["analyst_signals"]["aswath_damodaran_agent"] = damodaran_signals
    progress.update_status("aswath_damodaran_agent", None, "Done")

    return {"messages": [message], "data": state["data"]}


# ────────────────────────────────────────────────────────────────────────────────
# Helper analyses
# ────────────────────────────────────────────────────────────────────────────────
def analyze_growth_and_reinvestment(metrics: list, line_items: list) -> dict[str, any]:
    """
    Growth score (0-4):
      +2  5-yr CAGR of revenue > 8 %
      +1  5-yr CAGR of revenue > 3 %
      +1  Positive FCFF growth over 5 yr
    Reinvestment efficiency (ROIC > WACC) adds +1
    """
    max_score = 4
    if len(metrics) < 2:
        return {"score": 0, "max_score": max_score, "details": "Insufficient history"}

    # Revenue CAGR (oldest to latest)
    revs = [m.revenue for m in reversed(metrics) if hasattr(m, "revenue") and m.revenue]
    if len(revs) >= 2 and revs[0] > 0:
        cagr = (revs[-1] / revs[0]) ** (1 / (len(revs) - 1)) - 1
    else:
        cagr = None

    score, details = 0, []

    if cagr is not None:
        if cagr > 0.08:
            score += 2
            details.append(f"Revenue CAGR {cagr:.1%} (> 8 %)")
        elif cagr > 0.03:
            score += 1
            details.append(f"Revenue CAGR {cagr:.1%} (> 3 %)")
        else:
            details.append(f"Sluggish revenue CAGR {cagr:.1%}")
    else:
        details.append("Revenue data incomplete")

    # FCFF growth (proxy: free_cash_flow trend)
    fcfs = [li.free_cash_flow for li in reversed(line_items) if li.free_cash_flow]
    if len(fcfs) >= 2 and fcfs[-1] > fcfs[0]:
        score += 1
        details.append("Positive FCFF growth")
    else:
        details.append("Flat or declining FCFF")

    # Reinvestment efficiency (ROIC vs. 10 % hurdle)
    latest = metrics[0]
    if latest.return_on_invested_capital and latest.return_on_invested_capital > 0.10:
        score += 1
        details.append(f"ROIC {latest.return_on_invested_capital:.1%} (> 10 %)")

    return {"score": score, "max_score": max_score, "details": "; ".join(details), "metrics": latest.model_dump()}


def analyze_risk_profile(metrics: list, line_items: list) -> dict[str, any]:
    """
    Risk score (0-3):
      +1  Beta < 1.3
      +1  Debt/Equity < 1
      +1  Interest Coverage > 3×
    """
    max_score = 3
    if not metrics:
        return {"score": 0, "max_score": max_score, "details": "No metrics"}

    latest = metrics[0]
    score, details = 0, []

    # Beta
    beta = getattr(latest, "beta", None)
    if beta is not None:
        if beta < 1.3:
            score += 1
            details.append(f"Beta {beta:.2f}")
        else:
            details.append(f"High beta {beta:.2f}")
    else:
        details.append("Beta NA")

    # Debt / Equity
    dte = getattr(latest, "debt_to_equity", None)
    if dte is not None:
        if dte < 1:
            score += 1
            details.append(f"D/E {dte:.1f}")
        else:
            details.append(f"High D/E {dte:.1f}")
    else:
        details.append("D/E NA")

    # Interest coverage
    ebit = getattr(latest, "ebit", None)
    interest = getattr(latest, "interest_expense", None)
    if ebit and interest and interest != 0:
        coverage = ebit / abs(interest)
        if coverage > 3:
            score += 1
            details.append(f"Interest coverage × {coverage:.1f}")
        else:
            details.append(f"Weak coverage × {coverage:.1f}")
    else:
        details.append("Interest coverage NA")

    # Compute cost of equity for later use
    cost_of_equity = estimate_cost_of_equity(beta)

    return {
        "score": score,
        "max_score": max_score,
        "details": "; ".join(details),
        "beta": beta,
        "cost_of_equity": cost_of_equity,
    }


def analyze_relative_valuation(metrics: list) -> dict[str, any]:
    """
    Simple PE check vs. historical median (proxy since sector comps unavailable):
      +1 if TTM P/E < 70 % of 5-yr median
      +0 if between 70 %-130 %
      ‑1 if >130 %
    """
    max_score = 1
    if not metrics or len(metrics) < 5:
        return {"score": 0, "max_score": max_score, "details": "Insufficient P/E history"}

    pes = [m.price_to_earnings_ratio for m in metrics if m.price_to_earnings_ratio]
    if len(pes) < 5:
        return {"score": 0, "max_score": max_score, "details": "P/E data sparse"}

    ttm_pe = pes[0]
    median_pe = sorted(pes)[len(pes) // 2]

    if ttm_pe < 0.7 * median_pe:
        score, desc = 1, f"P/E {ttm_pe:.1f} vs. median {median_pe:.1f} (cheap)"
    elif ttm_pe > 1.3 * median_pe:
        score, desc = -1, f"P/E {ttm_pe:.1f} vs. median {median_pe:.1f} (expensive)"
    else:
        score, desc = 0, f"P/E inline with history"

    return {"score": score, "max_score": max_score, "details": desc}


# ────────────────────────────────────────────────────────────────────────────────
# Intrinsic value via FCFF DCF (Damodaran style)
# ────────────────────────────────────────────────────────────────────────────────
def calculate_intrinsic_value_dcf(metrics: list, line_items: list, risk_analysis: dict) -> dict[str, any]:
    """
    FCFF DCF with:
      • Base FCFF = latest free cash flow
      • Growth = 5-yr revenue CAGR (capped 12 %)
      • Fade linearly to terminal growth 2.5 % by year 10
      • Discount @ cost of equity (no debt split given data limitations)
    """
    if not metrics or len(metrics) < 2 or not line_items:
        return {"intrinsic_value": None, "details": ["Insufficient data"]}

    latest_m = metrics[0]
    fcff0 = getattr(latest_m, "free_cash_flow", None)
    shares = getattr(line_items[0], "outstanding_shares", None)
    if not fcff0 or not shares:
        return {"intrinsic_value": None, "details": ["Missing FCFF or share count"]}

    # Growth assumptions
    revs = [m.revenue for m in reversed(metrics) if m.revenue]
    if len(revs) >= 2 and revs[0] > 0:
        base_growth = min((revs[-1] / revs[0]) ** (1 / (len(revs) - 1)) - 1, 0.12)
    else:
        base_growth = 0.04  # fallback

    terminal_growth = 0.025
    years = 10

    # Discount rate
    discount = risk_analysis.get("cost_of_equity") or 0.09

    # Project FCFF and discount
    pv_sum = 0.0
    g = base_growth
    g_step = (terminal_growth - base_growth) / (years - 1)
    for yr in range(1, years + 1):
        fcff_t = fcff0 * (1 + g)
        pv = fcff_t / (1 + discount) ** yr
        pv_sum += pv
        g += g_step

    # Terminal value (perpetuity with terminal growth)
    tv = (
        fcff0
        * (1 + terminal_growth)
        / (discount - terminal_growth)
        / (1 + discount) ** years
    )

    equity_value = pv_sum + tv
    intrinsic_per_share = equity_value / shares

    return {
        "intrinsic_value": equity_value,
        "intrinsic_per_share": intrinsic_per_share,
        "assumptions": {
            "base_fcff": fcff0,
            "base_growth": base_growth,
            "terminal_growth": terminal_growth,
            "discount_rate": discount,
            "projection_years": years,
        },
        "details": ["FCFF DCF completed"],
    }


def estimate_cost_of_equity(beta: float | None) -> float:
    """CAPM: r_e = r_f + β × ERP (use Damodaran's long-term averages)."""
    risk_free = 0.04          # 10-yr US Treasury proxy
    erp = 0.05                # long-run US equity risk premium
    beta = beta if beta is not None else 1.0
    return risk_free + beta * erp


# ────────────────────────────────────────────────────────────────────────────────
# LLM generation
# ────────────────────────────────────────────────────────────────────────────────
def generate_damodaran_output(
    ticker: str,
    analysis_data: dict[str, any],
    state: AgentState,
) -> AswathDamodaranSignal:
    """
    Ask the LLM to channel Prof. Damodaran's analytical style:
      • Story → Numbers → Value narrative
      • Emphasize risk, growth, and cash-flow assumptions
      • Cite cost of capital, implied MOS, and valuation cross-checks
    """
    template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are Aswath Damodaran, Professor of Finance at NYU Stern.
                Use your valuation framework to issue trading signals on US equities.

                Speak with your usual clear, data-driven tone:
                  ◦ Start with the company "story" (qualitatively)
                  ◦ Connect that story to key numerical drivers: revenue growth, margins, reinvestment, risk
                  ◦ Conclude with value: your FCFF DCF estimate, margin of safety, and relative valuation sanity checks
                  ◦ Highlight major uncertainties and how they affect value
                Return ONLY the JSON specified below.""",
            ),
            (
                "human",
                """Ticker: {ticker}

                Analysis data:
                {analysis_data}

                Respond EXACTLY in this JSON schema:
                {{
                  "signal": "bullish" | "bearish" | "neutral",
                  "confidence": float (0-100),
                  "reasoning": "string"
                }}""",
            ),
        ]
    )

    prompt = template.invoke({"analysis_data": json.dumps(analysis_data, indent=2), "ticker": ticker})

    def default_signal():
        return AswathDamodaranSignal(
            signal="neutral",
            confidence=0.0,
            reasoning="Parsing error; defaulting to neutral",
        )

    return call_llm(
        prompt=prompt,
        pydantic_model=AswathDamodaranSignal,
        agent_name="aswath_damodaran_agent",
        state=state,
        default_factory=default_signal,
    )
