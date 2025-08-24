import json
from typing import Any, List

from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel
from typing_extensions import Literal

from src.graph.state import AgentState, show_agent_reasoning
from src.tools.api import get_financial_metrics, get_market_cap, search_line_items
from src.utils.api_key import get_api_key_from_state
from src.utils.llm import call_llm
from src.utils.progress import progress


# ---------------------------------
# Public signal schema
# ---------------------------------
class ElonMuskSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: float
    reasoning: str


# ---------------------------------
# Main agent function
# ---------------------------------
def elon_musk_agent(state: AgentState, agent_id: str = "elon_musk_agent"):
    """
    Analyze stocks using Elon Musk-style principles:
    - First-principles reasoning
    - Innovation speed over static moats
    - Factory/production excellence
    - Vertical integration & data flywheels
    - Risk & optionality toward planetary-scale markets
    - Scenario-based valuation with power-law outcomes
    """
    data = state["data"]
    end_date = data["end_date"]
    tickers = data["tickers"]
    api_key = get_api_key_from_state(state, "FINANCIAL_DATASETS_API_KEY")

    analysis_data: dict[str, Any] = {}
    musk_analysis: dict[str, Any] = {}

    for ticker in tickers:
        progress.update_status(agent_id, ticker, "Fetching financial metrics")
        metrics = get_financial_metrics(
            ticker, end_date, period="ttm", limit=10, api_key=api_key
        )

        progress.update_status(agent_id, ticker, "Gathering financial line items")
        financial_line_items = search_line_items(
            ticker,
            [
                "capital_expenditure",
                "depreciation_and_amortization",
                "net_income",
                "outstanding_shares",
                "total_assets",
                "total_liabilities",
                "shareholders_equity",
                "dividends_and_other_cash_distributions",
                "issuance_or_purchase_of_equity_shares",
                "gross_profit",
                "revenue",
                "free_cash_flow",
            ],
            end_date,
            period="ttm",
            limit=10,
            api_key=api_key,
        )

        progress.update_status(agent_id, ticker, "Getting market cap")
        market_cap = get_market_cap(ticker, end_date, api_key=api_key)

        # Musk-style analysis blocks
        progress.update_status(agent_id, ticker, "Analyzing growth and adoption")
        growth_analysis = analyze_growth_and_adoption(financial_line_items)

        progress.update_status(agent_id, ticker, "Analyzing innovation velocity")
        innovation_analysis = analyze_innovation_velocity(financial_line_items, metrics)

        progress.update_status(agent_id, ticker, "Analyzing engineering moat")
        engineering_moat = analyze_engineering_moat(metrics, financial_line_items)

        progress.update_status(agent_id, ticker, "Analyzing vertical integration")
        vertical_integration = analyze_vertical_integration_and_capex(financial_line_items, metrics)

        progress.update_status(agent_id, ticker, "Analyzing execution and risk")
        execution_risk = analyze_execution_and_risk(metrics, financial_line_items)

        progress.update_status(agent_id, ticker, "Performing scenario valuation")
        valuation = scenario_based_valuation(financial_line_items)

        # Aggregate scoring
        total_score = (
            growth_analysis["score"]
            + innovation_analysis["score"]
            + engineering_moat["score"]
            + vertical_integration["score"]
            + execution_risk["score"]
        )
        max_possible_score = (
            growth_analysis["max_score"]
            + innovation_analysis["max_score"]
            + engineering_moat["max_score"]
            + vertical_integration["max_score"]
            + execution_risk["max_score"]
        )

        margin_of_safety = None
        intrinsic_value = valuation.get("intrinsic_value")
        if intrinsic_value and market_cap:
            try:
                margin_of_safety = (intrinsic_value - market_cap) / market_cap
            except ZeroDivisionError:
                margin_of_safety = None

        analysis_data[ticker] = {
            "ticker": ticker,
            "score": total_score,
            "max_score": max_possible_score,
            "growth_analysis": growth_analysis,
            "innovation_analysis": innovation_analysis,
            "engineering_moat": engineering_moat,
            "vertical_integration": vertical_integration,
            "execution_risk": execution_risk,
            "valuation": valuation,
            "market_cap": market_cap,
            "margin_of_safety_vs_ev": margin_of_safety,
        }

        progress.update_status(agent_id, ticker, "Generating Elon Musk decision")
        musk_output = generate_musk_output(
            ticker=ticker,
            analysis_data=analysis_data,
            state=state,
            agent_id=agent_id,
        )

        musk_analysis[ticker] = {
            "signal": musk_output.signal,
            "confidence": musk_output.confidence,
            "reasoning": musk_output.reasoning,
        }

        progress.update_status(agent_id, ticker, "Done", analysis=musk_output.reasoning)

    message = HumanMessage(content=json.dumps(musk_analysis), name=agent_id)

    if state["metadata"].get("show_reasoning"):
        show_agent_reasoning(musk_analysis, agent_id)

    state["data"]["analyst_signals"][agent_id] = musk_analysis
    progress.update_status(agent_id, None, "Done")
    return {"messages": [message], "data": state["data"]}


# ---------------------------------
# Helper functions
# ---------------------------------
def _safe_series(items: list, attr: str) -> List[float]:
    vals: List[float] = []
    for it in items:
        v = getattr(it, attr, None)
        if isinstance(v, (int, float)):
            vals.append(float(v))
    return vals


def analyze_growth_and_adoption(financial_line_items: list) -> dict[str, Any]:
    # Measures revenue CAGR, acceleration, and gross margin improvements
    if not financial_line_items or len(financial_line_items) < 3:
        return {"score": 0, "max_score": 10, "details": "Insufficient history"}

    details = []
    score = 0
    max_score = 10

    rev = _safe_series(financial_line_items, "revenue")
    gp = _safe_series(financial_line_items, "gross_profit")

    # Revenue CAGR
    if len(rev) >= 3 and rev[-1] > 0:
        cagr_years = len(rev) - 1
        try:
            cagr = (rev[0] / rev[-1]) ** (1 / cagr_years) - 1
        except ZeroDivisionError:
            cagr = 0.0
        details.append(f"Revenue CAGR ~ {cagr:.1%} over {cagr_years} periods")
        if cagr > 0.30:
            score += 5
        elif cagr > 0.15:
            score += 4
        elif cagr > 0.08:
            score += 3
        elif cagr > 0.0:
            score += 2

    # Gross margin improvement
    if len(rev) >= 3 and len(gp) >= 3:
        margins = [gp[i] / rev[i] for i in range(len(rev)) if rev[i] > 0]
        if len(margins) >= 3:
            if (sum(margins[:2]) / 2) > (sum(margins[-2:]) / 2) + 0.02:
                score += 2
                details.append("Gross margin improving (scale effect)")

    return {"score": min(score, max_score), "max_score": max_score, "details": "; ".join(details)}


def analyze_innovation_velocity(financial_line_items: list, metrics: list) -> dict[str, Any]:
    # Looks at growth acceleration and operating margin trend
    max_score = 10
    score = 0
    details = []

    rev = _safe_series(financial_line_items, "revenue")
    gp = _safe_series(financial_line_items, "gross_profit")

    if len(rev) >= 4 and rev[-1] > 0:
        try:
            growth_now = (rev[0] - rev[1]) / rev[1]
            growth_prev = (rev[1] - rev[2]) / rev[2]
            if growth_now > 0.15:
                score += 3
            if growth_now - growth_prev > 0.05:
                score += 2
                details.append("Revenue growth accelerating")
        except ZeroDivisionError:
            pass

    if metrics and getattr(metrics[0], "operating_margin", None) is not None:
        om = metrics[0].operating_margin
        if om > 0.15:
            score += 2
            details.append("Healthy operating margin")

    return {"score": min(score, max_score), "max_score": max_score, "details": "; ".join(details)}


def analyze_engineering_moat(metrics: list, financial_line_items: list) -> dict[str, Any]:
    # Engineering/production moat: ROE consistency + margin stability
    max_score = 8
    score = 0
    details = []

    if metrics and len(metrics) >= 3:
        roes = [m.return_on_equity for m in metrics if getattr(m, "return_on_equity", None) is not None]
        if len(roes) >= 3 and sum(1 for r in roes if r > 0.15) / len(roes) >= 0.6:
            score += 3
            details.append("Consistently strong ROE")

    rev = _safe_series(financial_line_items, "revenue")
    gp = _safe_series(financial_line_items, "gross_profit")
    if len(rev) >= 5 and len(gp) >= 5:
        gm = [gp[i] / rev[i] for i in range(len(rev)) if rev[i] > 0]
        avg = sum(gm) / len(gm)
        var = sum((x - avg) ** 2 for x in gm) / len(gm)
        stability = 1 - (var ** 0.5) / avg if avg > 0 else 0
        if stability > 0.6:
            score += 2
            details.append("Stable gross margins (manufacturing discipline)")

    return {"score": min(score, max_score), "max_score": max_score, "details": "; ".join(details)}


def analyze_vertical_integration_and_capex(financial_line_items: list, metrics: list) -> dict[str, Any]:
    # Vertical integration: Capex intensity vs. growth, FCF margin trend
    max_score = 6
    score = 0
    details = []

    rev = _safe_series(financial_line_items, "revenue")
    capex = _safe_series(financial_line_items, "capital_expenditure")
    fcf = _safe_series(financial_line_items, "free_cash_flow")

    if rev and capex and rev[0] > 0:
        capex_intensity = abs(capex[0]) / rev[0]
        details.append(f"Capex intensity {capex_intensity:.1%}")
        if len(capex) >= 3 and len(rev) >= 3 and rev[2] > 0:
            old_intensity = abs(capex[2]) / rev[2]
            if capex_intensity < old_intensity:
                score += 2
                details.append("Capex/revenue improving with scale")

    if fcf and rev and rev[0] > 0:
        fcf_margin = fcf[0] / rev[0]
        if fcf_margin > 0.05:
            score += 2
            details.append("Positive FCF margin achieved")

    return {"score": min(score, max_score), "max_score": max_score, "details": "; ".join(details)}


def analyze_execution_and_risk(metrics: list, financial_line_items: list) -> dict[str, Any]:
    # Execution quality and risk tolerance
    max_score = 6
    score = 0
    details = []

    if metrics and getattr(metrics[0], "debt_to_equity", None) is not None:
        d2e = metrics[0].debt_to_equity
        if d2e < 0.8:
            score += 2
            details.append("Reasonable leverage")

    ni = _safe_series(financial_line_items, "net_income")
    if len(ni) >= 4:
        avg = sum(ni) / len(ni)
        var = sum((x - avg) ** 2 for x in ni) / len(ni)
        volatility = (var ** 0.5) / (abs(avg) + 1e-9)
        if volatility < 1.0:
            score += 2
            details.append("Earnings volatility acceptable")

    return {"score": min(score, max_score), "max_score": max_score, "details": "; ".join(details)}


def scenario_based_valuation(financial_line_items: list) -> dict[str, Any]:
    # Scenario-based expected value (bear/base/bull)
    if not financial_line_items or len(financial_line_items) < 3:
        return {"intrinsic_value": None, "details": ["Insufficient data"]}

    rev = _safe_series(financial_line_items, "revenue")
    fcf = _safe_series(financial_line_items, "free_cash_flow")

    if not rev or rev[0] <= 0:
        return {"intrinsic_value": None, "details": ["Missing revenue"]}

    r0 = rev[0]
    if len(rev) >= 3 and rev[-1] > 0:
        years = len(rev) - 1
        try:
            hist_g = (rev[0] / rev[-1]) ** (1 / years) - 1
        except ZeroDivisionError:
            hist_g = 0.10
    else:
        hist_g = 0.10

    scenarios = [
        {"p": 0.25, "g0": max(hist_g * 0.5, -0.05), "fcf_target": 0.05, "dr": 0.18},
        {"p": 0.50, "g0": min(hist_g, 0.25),        "fcf_target": 0.12, "dr": 0.14},
        {"p": 0.25, "g0": min(hist_g * 1.5, 0.40),  "fcf_target": 0.20, "dr": 0.12},
    ]

    horizon = 10
    terminal_g = 0.025
    exp_value = 0.0
    details = []

    for sc in scenarios:
        g = sc["g0"]
        dr = sc["dr"]
        fcf_target = sc["fcf_target"]

        growth_path = [g + (0.03 - g) * (t / horizon) for t in range(1, horizon + 1)]
        current_fcf_m = (fcf[0] / r0) if (fcf and r0 > 0) else 0.0
        fcf_path = [current_fcf_m + (fcf_target - current_fcf_m) * (t / horizon) for t in range(1, horizon + 1)]

        rev_t = r0
        pv = 0.0
        for t in range(1, horizon + 1):
            rev_t *= (1 + growth_path[t - 1])
            fcf_t = rev_t * fcf_path[t - 1]
            pv += fcf_t / ((1 + dr) ** t)

        tv = (rev_t * fcf_path[-1] * (1 + terminal_g)) / (dr - terminal_g)
        pv += tv / ((1 + dr) ** horizon)

        exp_value += sc["p"] * pv
        details.append(f"Scenario p={sc['p']}, g0={sc['g0']:.1%}, PV≈${pv:,.0f}")

    return {
        "intrinsic_value": exp_value,
        "assumptions": {"terminal_growth": terminal_g, "horizon_years": horizon},
        "details": details,
    }


# ---------------------------------
# LLM Output Generation
# ---------------------------------
def generate_musk_output(
    ticker: str,
    analysis_data: dict[str, Any],
    state: AgentState,
    agent_id: str = "elon_musk_agent",
) -> ElonMuskSignal:
    """Generate Elon Musk-style investment decision."""
    template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are Elon Musk. Analyze investments with first-principles engineering, rapid innovation cycles, and planetary-scale ambition.
PRINCIPLES:
1. First principles reasoning — reduce to physics, cost curves, scalability limits.
2. Innovation speed > static moats.
3. Factory as product — focus on production efficiency and scaling.
4. Vertical integration & data network effects.
5. Accept calculated risk for asymmetric upside.
6. Target markets with massive TAM and impact.
""",
            ),
            (
                "human",
                """Analyze {ticker} with the provided computed data:
{analysis_data}

Return EXACT JSON:
{{
  "signal": "bullish" | "bearish" | "neutral",
  "confidence": float (0-100),
  "reasoning": "Short, high-signal Elon Musk-style analysis with specific numeric references."
}}""",
            ),
        ]
    )

    prompt = template.invoke({"analysis_data": json.dumps(analysis_data, indent=2), "ticker": ticker})

    def default_signal():
        return ElonMuskSignal(signal="neutral", confidence=0.0, reasoning="Parsing error fallback")

    return call_llm(
        prompt=prompt,
        pydantic_model=ElonMuskSignal,
        agent_name=agent_id,
        state=state,
        default_factory=default_signal,
    )
