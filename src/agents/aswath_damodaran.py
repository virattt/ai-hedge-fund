from __future__ import annotations

import json
import logging
from typing_extensions import Literal
from pydantic import BaseModel

logger = logging.getLogger(__name__)

from src.graph.state import AgentState, show_agent_reasoning
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage

from src.tools.api import (
    get_financial_metrics,
    get_market_cap,
    get_prices,
    search_line_items,
)
from src.utils.api_key import get_api_key_from_state
from src.utils.llm import call_llm
from src.utils.progress import progress


class AswathDamodaranSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: float          # 0‒100
    reasoning: str


def aswath_damodaran_agent(state: AgentState, agent_id: str = "aswath_damodaran_agent"):
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
    api_key  = get_api_key_from_state(state, "FINANCIAL_DATASETS_API_KEY")

    analysis_data: dict[str, dict] = {}
    damodaran_signals: dict[str, dict] = {}

    for ticker in tickers:
        # ─── Fetch core data ────────────────────────────────────────────────────
        progress.update_status(agent_id, ticker, "Fetching financial metrics")
        metrics = get_financial_metrics(ticker, end_date, period="ttm", limit=5, api_key=api_key)

        progress.update_status(agent_id, ticker, "Fetching financial line items")
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
                "total_shareholder_equity",
                "revenue",
            ],
            end_date,
            api_key=api_key,
        )

        logger.info("[Damodaran/%s] metrics=%d line_items=%d", ticker, len(metrics), len(line_items))
        if line_items:
            li0 = line_items[0]
            logger.info(
                "[Damodaran/%s] li[0]: period=%s fcf=%s net_income=%s revenue=%s shares=%s",
                ticker,
                getattr(li0, "report_period", None),
                getattr(li0, "free_cash_flow", None),
                getattr(li0, "net_income", None),
                getattr(li0, "revenue", None),
                getattr(li0, "outstanding_shares", None),
            )

        progress.update_status(agent_id, ticker, "Getting market cap")
        market_cap = get_market_cap(ticker, end_date, api_key=api_key)
        logger.info("[Damodaran/%s] market_cap from API: %s", ticker, market_cap)

        # Fallback: price × shares_outstanding (works when OVERVIEW discovery fails)
        if not market_cap and line_items:
            shares = getattr(line_items[0], "outstanding_shares", None)
            if shares:
                from datetime import date as _date, timedelta as _td
                _start = (_date.fromisoformat(end_date) - _td(days=7)).isoformat()
                recent_prices = get_prices(ticker, _start, end_date, api_key=api_key)
                if recent_prices:
                    market_cap = recent_prices[-1].close * shares
                    logger.info("[Damodaran/%s] market_cap from price×shares: %s × %s = %s", ticker, recent_prices[-1].close, shares, market_cap)
                else:
                    logger.warning("[Damodaran/%s] price fallback returned no prices for %s to %s", ticker, _start, end_date)
            else:
                logger.warning("[Damodaran/%s] outstanding_shares is None, cannot compute market_cap fallback", ticker)

        # ─── Analyses ───────────────────────────────────────────────────────────
        progress.update_status(agent_id, ticker, "Analyzing growth and reinvestment")
        growth_analysis = analyze_growth_and_reinvestment(metrics, line_items)

        progress.update_status(agent_id, ticker, "Analyzing risk profile")
        risk_analysis = analyze_risk_profile(metrics, line_items)

        progress.update_status(agent_id, ticker, "Calculating intrinsic value (DCF)")
        intrinsic_val_analysis = calculate_intrinsic_value_dcf(metrics, line_items, risk_analysis)

        progress.update_status(agent_id, ticker, "Assessing relative valuation")
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

        logger.info(
            "[Damodaran/%s] intrinsic_value=%s market_cap=%s MoS=%s → signal=%s",
            ticker,
            intrinsic_value,
            market_cap,
            f"{margin_of_safety:.1%}" if margin_of_safety is not None else "None",
            signal,
        )
        logger.info("[Damodaran/%s] DCF details: %s", ticker, intrinsic_val_analysis.get("details"))

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
        progress.update_status(agent_id, ticker, "Generating Damodaran analysis")
        damodaran_output = generate_damodaran_output(
            ticker=ticker,
            analysis_data=analysis_data,
            state=state,
            agent_id=agent_id,
            signal=signal,
        )

        # Override the LLM signal with the pre-computed quantitative signal so
        # the narrative prose cannot contradict the DCF/MoS calculation.
        final = damodaran_output.model_dump()
        final["signal"] = signal
        damodaran_signals[ticker] = final

        progress.update_status(agent_id, ticker, "Done", analysis=damodaran_output.reasoning)

    # ─── Push message back to graph state ──────────────────────────────────────
    message = HumanMessage(content=json.dumps(damodaran_signals), name=agent_id)

    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(damodaran_signals, "Aswath Damodaran Agent")

    state["data"]["analyst_signals"][agent_id] = damodaran_signals
    progress.update_status(agent_id, None, "Done")

    return {"messages": [message], "data": state["data"]}


# ────────────────────────────────────────────────────────────────────────────────
# Helper analyses
# ────────────────────────────────────────────────────────────────────────────────
def analyze_growth_and_reinvestment(metrics: list, line_items: list) -> dict[str, any]:
    """
    Growth score (0-4):
      +2  Revenue CAGR > 8 %
      +1  Revenue CAGR > 3 %
      +1  Positive FCFF growth over available history
    Reinvestment efficiency (ROIC > WACC) adds +1

    Revenue and FCF trends are sourced from line_items (historical annual data);
    metrics[0] provides current-period ratios.
    """
    max_score = 4
    if not metrics and not line_items:
        return {"score": 0, "max_score": max_score, "details": "Insufficient history"}

    # Revenue CAGR — use line_items (oldest to latest order, already sorted desc so reverse)
    revs = [li.revenue for li in reversed(line_items) if getattr(li, "revenue", None)]
    if len(revs) >= 2 and revs[0] > 0:
        cagr = (revs[-1] / revs[0]) ** (1 / (len(revs) - 1)) - 1
    else:
        # Fallback to FinancialMetrics revenue_growth if available
        cagr = metrics[0].revenue_growth if metrics and metrics[0].revenue_growth else None

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

    # FCFF growth (proxy: free_cash_flow trend from line_items)
    fcfs = [li.free_cash_flow for li in reversed(line_items) if getattr(li, "free_cash_flow", None)]
    if len(fcfs) >= 2 and fcfs[-1] > fcfs[0]:
        score += 1
        details.append("Positive FCFF growth")
    else:
        details.append("Flat or declining FCFF")

    # Reinvestment efficiency (ROIC vs. 10 % hurdle) — from metrics snapshot
    if metrics:
        latest = metrics[0]
        if latest.return_on_invested_capital and latest.return_on_invested_capital > 0.10:
            score += 1
            details.append(f"ROIC {latest.return_on_invested_capital:.1%} (> 10 %)")
        metrics_dump = latest.model_dump()
    else:
        metrics_dump = {}

    return {"score": score, "max_score": max_score, "details": "; ".join(details), "metrics": metrics_dump}


def analyze_risk_profile(metrics: list, line_items: list) -> dict[str, any]:
    """
    Risk score (0-3):
      +1  Beta < 1.3
      +1  Debt/Equity < 1
      +1  Interest Coverage > 3×

    Beta and D/E are sourced from metrics[0] when available; D/E and interest
    coverage fall back to line_items[0] when not present in metrics.
    """
    max_score = 3
    score, details = 0, []

    latest = metrics[0] if metrics else None
    latest_li = line_items[0] if line_items else None

    # Beta (metrics only — not in line items)
    beta = getattr(latest, "beta", None) if latest else None
    if beta is not None:
        if beta < 1.3:
            score += 1
            details.append(f"Beta {beta:.2f}")
        else:
            details.append(f"High beta {beta:.2f}")
    else:
        details.append("Beta NA")

    # Debt / Equity — metrics first, then compute from line_items
    dte = getattr(latest, "debt_to_equity", None) if latest else None
    if dte is None and latest_li:
        total_debt = getattr(latest_li, "total_debt", None)
        total_equity = getattr(latest_li, "total_shareholder_equity", None) or getattr(latest_li, "total_equity", None)
        if total_debt is not None and total_equity and total_equity != 0:
            dte = total_debt / abs(total_equity)
    if dte is not None:
        if dte < 1:
            score += 1
            details.append(f"D/E {dte:.2f}")
        else:
            details.append(f"High D/E {dte:.2f}")
    else:
        details.append("D/E NA")

    # Interest coverage — line_items carry ebit and interest_expense
    ebit = getattr(latest_li, "ebit", None) if latest_li else None
    interest = getattr(latest_li, "interest_expense", None) if latest_li else None
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
      • Base FCFF = latest free cash flow (from line_items)
      • Growth = revenue CAGR from line_items history (capped 12 %)
      • Fade linearly to terminal growth 2.5 % by year 10
      • Discount @ cost of equity (no debt split given data limitations)
    """
    if not line_items:
        return {"intrinsic_value": None, "details": ["Insufficient data"]}

    # Base FCFF from latest line item; shares from same period (optional — only needed for per-share display)
    fcff0 = getattr(line_items[0], "free_cash_flow", None)
    shares = getattr(line_items[0], "outstanding_shares", None)
    fcff_source = "free_cash_flow"

    # Fallback: use net_income as a FCFF proxy (reasonable for asset-light / fintech companies)
    if not fcff0:
        fcff0 = getattr(line_items[0], "net_income", None)
        fcff_source = "net_income (proxy)"

    if not fcff0:
        return {"intrinsic_value": None, "details": [f"Missing FCFF (fcff={fcff0})"]}

    # Growth assumptions — use revenue trend from line_items
    revs = [li.revenue for li in reversed(line_items) if getattr(li, "revenue", None)]
    if len(revs) >= 2 and revs[0] > 0:
        base_growth = min((revs[-1] / revs[0]) ** (1 / (len(revs) - 1)) - 1, 0.12)
    elif metrics and metrics[0].revenue_growth:
        base_growth = min(metrics[0].revenue_growth, 0.12)
    else:
        base_growth = 0.04  # fallback

    terminal_growth = 0.025
    years = 10

    # Discount rate
    discount = risk_analysis.get("cost_of_equity") or 0.09

    # Project FCFF and discount — compound each year from the prior year's FCF
    pv_sum = 0.0
    fcff_t = fcff0
    g = base_growth
    g_step = (terminal_growth - base_growth) / (years - 1)
    for yr in range(1, years + 1):
        fcff_t = fcff_t * (1 + g)          # compound from prior year, not from base
        pv = fcff_t / (1 + discount) ** yr
        pv_sum += pv
        if yr < years:
            g += g_step

    # Terminal value uses the FCF projected at end of Year 10 (not the base)
    tv = (
        fcff_t
        * (1 + terminal_growth)
        / (discount - terminal_growth)
        / (1 + discount) ** years
    )

    equity_value = pv_sum + tv
    intrinsic_per_share = equity_value / shares if shares else None

    return {
        "intrinsic_value": equity_value,
        "intrinsic_per_share": intrinsic_per_share,
        "assumptions": {
            "base_fcff": fcff0,
            "fcff_source": fcff_source,
            "base_growth": base_growth,
            "terminal_growth": terminal_growth,
            "discount_rate": discount,
            "projection_years": years,
        },
        "details": [f"FCFF DCF completed (source: {fcff_source})"],
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
    agent_id: str,
    signal: str = "neutral",
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
                A quantitative DCF model has already been run. Your sole task is to write the
                narrative reasoning that explains the pre-computed results — do NOT re-evaluate
                the signal or claim data is insufficient.

                Write in Damodaran's voice: story → numerical drivers → value conclusion.
                Reference the specific numbers provided (revenue CAGR, FCFF, margin of safety,
                intrinsic value). If a metric is missing, note it in one phrase and move on.
                Return ONLY the JSON specified below.""",
            ),
            (
                "human",
                """Ticker: {ticker}

                Pre-computed quantitative analysis:
                {analysis_data}

                The trading signal has already been determined from the DCF margin of safety.
                Your job is only to explain WHY in Damodaran's analytical voice.

                Respond EXACTLY in this JSON schema:
                {{
                  "signal": "{signal}",
                  "confidence": <float 0-100 reflecting your conviction in the narrative>,
                  "reasoning": "<3-5 sentence Damodaran-style explanation citing the numbers above>"
                }}""",
            ),
        ]
    )

    prompt = template.invoke({"analysis_data": json.dumps(analysis_data, indent=2), "ticker": ticker, "signal": signal})

    def default_signal():
        return AswathDamodaranSignal(
            signal="neutral",
            confidence=0.0,
            reasoning="Parsing error; defaulting to neutral",
        )

    return call_llm(
        prompt=prompt,
        pydantic_model=AswathDamodaranSignal,
        agent_name=agent_id,
        state=state,
        default_factory=default_signal,
    )
