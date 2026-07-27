from src.graph.state import AgentState, show_agent_reasoning
from src.tools.api import get_company_news, get_financial_metrics, get_market_cap, search_line_items
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field
from typing_extensions import Literal
import json
from datetime import datetime, timedelta
from src.utils.progress import progress
from src.utils.llm import call_llm
from src.utils.api_key import get_api_key_from_state


class AIInfraBullSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: int = Field(description="Confidence 0-100")
    reasoning: str = Field(description="Reasoning for the decision")


def ai_infra_bull_agent(state: AgentState, agent_id: str = "ai_infra_bull_agent"):
    """
    Analyzes stocks using an AI Infrastructure Bull thesis:
    1. Picks-and-shovels mindset: values chip equipment, power/cooling, networking alongside pure AI plays.
    2. Tracks R&D intensity and capex trajectory as leading indicators of AI infrastructure demand.
    3. Bullish on locked-in compute contracts, sovereign AI deals, multi-year backlogs.
    4. Key metrics: R&D intensity, capex buildout, gross margin expansion, contract visibility.
    5. Accepts high multiples when AI revenue mix is accelerating and switching costs are high.
    """
    data = state["data"]
    end_date = data["end_date"]
    tickers = data["tickers"]
    api_key = get_api_key_from_state(state, "FINANCIAL_DATASETS_API_KEY")

    start_date = (datetime.fromisoformat(end_date) - timedelta(days=365)).date().isoformat()

    analysis_data = {}
    infra_analysis = {}

    for ticker in tickers:
        progress.update_status(agent_id, ticker, "Fetching financial metrics")
        metrics = get_financial_metrics(ticker, end_date, period="annual", limit=5, api_key=api_key)

        progress.update_status(agent_id, ticker, "Gathering financial line items")
        line_items = search_line_items(
            ticker,
            [
                "revenue",
                "gross_margin",
                "operating_margin",
                "research_and_development",
                "capital_expenditure",
                "free_cash_flow",
                "total_assets",
                "total_liabilities",
                "operating_expense",
                "deferred_revenue",
                "outstanding_shares",
            ],
            end_date,
            period="annual",
            limit=5,
            api_key=api_key,
        )

        progress.update_status(agent_id, ticker, "Getting market cap")
        market_cap = get_market_cap(ticker, end_date, api_key=api_key)

        progress.update_status(agent_id, ticker, "Fetching company news")
        news = get_company_news(ticker, end_date=end_date, start_date=start_date, limit=50)

        progress.update_status(agent_id, ticker, "Analyzing AI revenue mix and investment")
        revenue_mix_analysis = analyze_ai_revenue_mix(metrics, line_items)

        progress.update_status(agent_id, ticker, "Analyzing infrastructure moat")
        moat_analysis = analyze_infrastructure_moat(metrics, line_items)

        progress.update_status(agent_id, ticker, "Analyzing backlog and contract signals")
        backlog_analysis = analyze_backlog_and_contracts(line_items)

        progress.update_status(agent_id, ticker, "Analyzing AI infrastructure valuation")
        valuation_analysis = analyze_ai_infra_valuation(line_items, market_cap)

        progress.update_status(agent_id, ticker, "Analyzing news for AI infrastructure signals")
        news_analysis = analyze_ai_news_signals(news)

        total_score = (
            revenue_mix_analysis["score"]
            + moat_analysis["score"]
            + backlog_analysis["score"]
            + valuation_analysis["score"]
            + news_analysis["score"]
        )
        max_possible_score = (
            revenue_mix_analysis["max_score"]
            + moat_analysis["max_score"]
            + backlog_analysis["max_score"]
            + valuation_analysis["max_score"]
            + news_analysis["max_score"]
        )

        analysis_data[ticker] = {
            "ticker": ticker,
            "score": total_score,
            "max_score": max_possible_score,
            "revenue_mix_analysis": revenue_mix_analysis,
            "moat_analysis": moat_analysis,
            "backlog_analysis": backlog_analysis,
            "valuation_analysis": valuation_analysis,
            "news_analysis": news_analysis,
            "market_cap": market_cap,
        }

        progress.update_status(agent_id, ticker, "Generating AI Infrastructure Bull analysis")
        infra_output = generate_ai_infra_bull_output(
            ticker=ticker,
            analysis_data=analysis_data[ticker],
            state=state,
            agent_id=agent_id,
        )

        infra_analysis[ticker] = {
            "signal": infra_output.signal,
            "confidence": infra_output.confidence,
            "reasoning": infra_output.reasoning,
        }

        progress.update_status(agent_id, ticker, "Done", analysis=infra_output.reasoning)

    message = HumanMessage(content=json.dumps(infra_analysis), name=agent_id)

    if state["metadata"].get("show_reasoning"):
        show_agent_reasoning(infra_analysis, agent_id)

    state["data"]["analyst_signals"][agent_id] = infra_analysis

    progress.update_status(agent_id, None, "Done")

    return {"messages": [message], "data": state["data"]}


###############################################################################
# Sub-analysis functions
###############################################################################


def analyze_ai_revenue_mix(metrics: list, line_items: list) -> dict:
    """
    Assess AI/infrastructure revenue exposure and investment intensity.
    R&D intensity and capex trajectory serve as proxies for AI infrastructure positioning.
    max_score = 10 (R&D:3 + revenue growth:3 + capex:2 + gross margin:2)
    """
    score = 0
    details = []

    # FIX: metrics is not used in this function — guard only on line_items
    if not line_items:
        return {"score": 0, "max_score": 10, "details": "Insufficient data for AI revenue mix analysis"}

    revenues = [item.revenue for item in line_items if item.revenue]

    # 1. R&D intensity — proxy for AI investment commitment (max 3)
    rd_expenses = [
        item.research_and_development for item in line_items
        if hasattr(item, "research_and_development") and item.research_and_development is not None
    ]
    if rd_expenses and revenues:
        rd_intensity = abs(rd_expenses[0]) / revenues[0] if revenues[0] else 0
        if rd_intensity > 0.20:
            score += 3
            details.append(f"Very high R&D intensity ({rd_intensity:.1%}) — deep AI investment commitment")
        elif rd_intensity > 0.12:
            score += 2
            details.append(f"High R&D intensity ({rd_intensity:.1%}) — meaningful AI investment")
        elif rd_intensity > 0.06:
            score += 1
            details.append(f"Moderate R&D intensity ({rd_intensity:.1%})")
        else:
            details.append(f"Low R&D intensity ({rd_intensity:.1%}) — limited innovation signal")
    else:
        details.append("R&D data not available")

    # 2. Revenue growth — AI demand pull-through (max 3)
    if len(revenues) >= 2 and revenues[1]:
        latest_growth = (revenues[0] - revenues[1]) / abs(revenues[1])
        if latest_growth > 0.30:
            score += 3
            details.append(f"Exceptional revenue growth ({latest_growth:.1%}) — strong AI demand pull-through")
        elif latest_growth > 0.15:
            score += 2
            details.append(f"Strong revenue growth ({latest_growth:.1%})")
        elif latest_growth > 0.05:
            score += 1
            details.append(f"Moderate revenue growth ({latest_growth:.1%})")
        else:
            details.append(f"Weak revenue growth ({latest_growth:.1%})")
        if len(revenues) >= 3 and revenues[2]:
            prior_growth = (revenues[1] - revenues[2]) / abs(revenues[2])
            if latest_growth > prior_growth:
                details.append("Growth accelerating — AI adoption ramp visible")
            else:
                details.append("Growth decelerating — check AI pipeline momentum")
    else:
        details.append("Insufficient revenue data for growth analysis")

    # 3. Capex intensity — picks-and-shovels infrastructure buildout signal (max 2)
    capex = [
        item.capital_expenditure for item in line_items
        if hasattr(item, "capital_expenditure") and item.capital_expenditure is not None
    ]
    if capex and revenues and len(capex) >= 2:
        capex_intensity = abs(capex[0]) / revenues[0] if revenues[0] else 0
        capex_growth = (abs(capex[0]) - abs(capex[-1])) / abs(capex[-1]) if capex[-1] else 0
        if capex_intensity > 0.15 and capex_growth > 0.20:
            score += 2
            details.append(
                f"Heavy infrastructure buildout (capex {capex_intensity:.1%} of revenue, "
                f"+{capex_growth:.1%} growth) — data center scale-up"
            )
        elif capex_intensity > 0.08 or capex_growth > 0.30:
            score += 1
            details.append(f"Growing infrastructure investment (capex {capex_intensity:.1%} of revenue)")
        else:
            details.append(f"Limited capex growth signal (capex {capex_intensity:.1%} of revenue)")
    else:
        details.append("Insufficient capex data")

    # 4. Gross margin level — software/platform margins signal high switching costs (max 2)
    gross_margins = [
        item.gross_margin for item in line_items
        if hasattr(item, "gross_margin") and item.gross_margin is not None
    ]
    if gross_margins:
        gm = gross_margins[0]
        if gm > 0.65:
            score += 2
            details.append(f"Software-like gross margins ({gm:.1%}) — high switching-cost AI platform")
        elif gm > 0.45:
            score += 1
            details.append(f"Healthy gross margins ({gm:.1%}) — hardware/software mix")
        else:
            details.append(f"Hardware-grade margins ({gm:.1%}) — picks-and-shovels infrastructure play")
    else:
        details.append("Gross margin data not available")

    return {"score": score, "max_score": 10, "details": "; ".join(details)}


def analyze_infrastructure_moat(metrics: list, line_items: list) -> dict:
    """
    Evaluate durability of AI infrastructure competitive position.
    High score = expanding margins + operating leverage + FCF consistency + fortress balance sheet.
    max_score = 10 (GM expansion:3 + op leverage:2 + FCF consistency:3 + balance sheet:2)
    """
    score = 0
    details = []

    if not metrics or not line_items:
        return {"score": 0, "max_score": 10, "details": "Insufficient data for infrastructure moat analysis"}

    # 1. Gross margin expansion — pricing power and mix shift toward higher-value AI products (max 3)
    gross_margins = [
        item.gross_margin for item in line_items
        if hasattr(item, "gross_margin") and item.gross_margin is not None
    ]
    if len(gross_margins) >= 2:
        expansion = gross_margins[0] - gross_margins[-1]
        if expansion > 0.05:
            score += 3
            details.append(f"Strong gross margin expansion (+{expansion:.1%}) — mix shift to high-value AI products")
        elif expansion > 0.02:
            score += 2
            details.append(f"Moderate gross margin expansion (+{expansion:.1%})")
        elif expansion > 0:
            score += 1
            details.append(f"Slight gross margin improvement (+{expansion:.1%})")
        else:
            details.append(f"Gross margins flat or contracting ({expansion:.1%})")
    else:
        details.append("Insufficient gross margin history")

    # 2. Operating leverage — revenue growing faster than opex (max 2)
    revenues = [item.revenue for item in line_items if item.revenue]
    opex = [
        item.operating_expense for item in line_items
        if hasattr(item, "operating_expense") and item.operating_expense is not None
    ]
    if len(revenues) >= 2 and len(opex) >= 2 and revenues[-1] and opex[-1]:
        rev_growth = (revenues[0] - revenues[-1]) / abs(revenues[-1])
        opex_growth = (abs(opex[0]) - abs(opex[-1])) / abs(opex[-1])
        if rev_growth > opex_growth and rev_growth > 0.10:
            score += 2
            details.append(
                f"Strong operating leverage (revenue +{rev_growth:.1%} vs opex +{opex_growth:.1%})"
            )
        elif rev_growth > opex_growth:
            score += 1
            details.append(
                f"Modest operating leverage (revenue +{rev_growth:.1%} vs opex +{opex_growth:.1%})"
            )
        else:
            details.append("No operating leverage — opex growing faster than revenue")
    else:
        details.append("Insufficient data for operating leverage analysis")

    # 3. FCF consistency — self-funding infrastructure without dilution (max 3)
    fcf_values = [getattr(item, "free_cash_flow", None) for item in line_items]
    fcf = [v for v in fcf_values if v is not None]
    if fcf:
        positive_count = sum(1 for v in fcf if v > 0)
        if positive_count == len(fcf) and len(fcf) >= 3:
            score += 3
            details.append(
                f"Consistent FCF generation ({positive_count}/{len(fcf)} periods) — "
                f"self-funding infrastructure moat"
            )
        elif positive_count >= len(fcf) * 0.75:
            score += 2
            details.append(f"Mostly positive FCF ({positive_count}/{len(fcf)} periods)")
        elif positive_count > 0:
            score += 1
            details.append(f"Inconsistent FCF ({positive_count}/{len(fcf)} periods positive)")
        else:
            details.append("No positive FCF periods — reliant on capital markets")
    else:
        details.append("FCF data not available")

    # 4. Balance sheet strength — fortress balance sheet for multi-year capex cycle (max 2)
    latest_metrics = metrics[0]  # safe: guard above ensures metrics is non-empty
    debt_to_equity = getattr(latest_metrics, "debt_to_equity", None)
    if debt_to_equity is not None:
        if debt_to_equity < 0.3:
            score += 2
            details.append(
                f"Fortress balance sheet (D/E {debt_to_equity:.2f}) — can sustain multi-year capex cycle"
            )
        elif debt_to_equity < 0.8:
            score += 1
            details.append(f"Manageable leverage (D/E {debt_to_equity:.2f})")
        else:
            details.append(f"High leverage (D/E {debt_to_equity:.2f}) — risk if AI capex cycle turns")
    else:
        details.append("Debt-to-equity data not available")

    return {"score": score, "max_score": 10, "details": "; ".join(details)}


def analyze_backlog_and_contracts(line_items: list) -> dict:
    """
    Assess contracted revenue visibility — proxy for sovereign AI deals and multi-year compute contracts.
    Uses deferred revenue growth and revenue predictability as RPO proxies.
    max_score = 6 (deferred revenue:3 + revenue consistency:3)
    """
    score = 0
    details = []

    if not line_items:
        return {"score": 0, "max_score": 6, "details": "Insufficient data for backlog analysis"}

    revenues = [item.revenue for item in line_items if item.revenue]

    # 1. Deferred revenue growth — proxy for RPO/backlog (prepaid multi-year contracts) (max 3)
    deferred = [getattr(item, "deferred_revenue", None) for item in line_items]
    deferred = [v for v in deferred if v is not None and v > 0]
    if len(deferred) >= 2 and revenues:
        def_growth = (deferred[0] - deferred[-1]) / abs(deferred[-1]) if deferred[-1] else 0
        def_to_rev = deferred[0] / revenues[0] if revenues[0] else 0
        if def_growth > 0.30 and def_to_rev > 0.10:
            score += 3
            details.append(
                f"Strong contract backlog build ({def_growth:.1%} deferred revenue growth, "
                f"{def_to_rev:.1%} of revenue) — sovereign AI deal signal"
            )
        elif def_growth > 0.15 or def_to_rev > 0.05:
            score += 2
            details.append(f"Growing contract visibility (deferred revenue +{def_growth:.1%})")
        elif def_growth > 0:
            score += 1
            details.append(f"Modest deferred revenue growth ({def_growth:.1%})")
        else:
            details.append("Deferred revenue flat or shrinking — limited contract backlog signal")
    else:
        details.append("Deferred revenue data not available — using revenue consistency as proxy")

    # 2. Revenue consistency — low variance growth = sticky compute contracts (max 3)
    if len(revenues) >= 3:
        growth_rates = []
        for i in range(len(revenues) - 1):
            if revenues[i] and revenues[i + 1]:
                growth_rates.append((revenues[i] - revenues[i + 1]) / abs(revenues[i + 1]))
        if growth_rates:
            mean_g = sum(growth_rates) / len(growth_rates)
            variance = sum((g - mean_g) ** 2 for g in growth_rates) / len(growth_rates)
            std_g = variance ** 0.5
            cv = std_g / abs(mean_g) if mean_g != 0 else float("inf")
            if mean_g > 0.10 and cv < 0.30:
                score += 3
                details.append(
                    f"Highly predictable revenue growth (avg {mean_g:.1%}, CV {cv:.2f}) — "
                    f"locked-in compute demand"
                )
            elif mean_g > 0.05 and cv < 0.50:
                score += 2
                details.append(f"Reasonably consistent growth (avg {mean_g:.1%}, CV {cv:.2f})")
            elif mean_g > 0:
                score += 1
                details.append(f"Positive but variable growth (avg {mean_g:.1%}, CV {cv:.2f})")
            else:
                details.append(f"Declining or volatile revenue (avg {mean_g:.1%})")
        else:
            details.append("Insufficient growth history")
    else:
        details.append("Insufficient revenue history for consistency analysis")

    return {"score": score, "max_score": 6, "details": "; ".join(details)}


def analyze_ai_infra_valuation(line_items: list, market_cap: float) -> dict:
    """
    Growth-adjusted valuation — AI Infrastructure Bull accepts high multiples
    when growth is exceptional and switching costs are high (CUDA ecosystem, proprietary silicon).
    max_score = 8 (P/S vs growth rate:4 + FCF yield:4)
    """
    score = 0
    details = []

    if not line_items or market_cap is None or market_cap <= 0:
        return {"score": 0, "max_score": 8, "details": "Insufficient data for AI infrastructure valuation"}

    revenues = [item.revenue for item in line_items if item.revenue]
    if not revenues:
        return {"score": 0, "max_score": 8, "details": "No revenue data for valuation analysis"}

    latest = line_items[0]
    current_revenue = revenues[0]

    # 1. Price/Sales vs growth rate — high P/S is acceptable when growth is exceptional (max 4)
    ps_ratio = market_cap / current_revenue
    growth_rate = 0.0
    if len(revenues) >= 2 and revenues[1]:
        growth_rate = (revenues[0] - revenues[1]) / abs(revenues[1])

    if growth_rate > 0.40 and ps_ratio < 20:
        score += 4
        details.append(
            f"Attractive growth-adjusted valuation (P/S {ps_ratio:.1f}x at {growth_rate:.1%} growth) — "
            f"explosive AI growth not yet fully priced"
        )
    elif growth_rate > 0.25 and ps_ratio < 30:
        score += 3
        details.append(f"Reasonable growth-adjusted valuation (P/S {ps_ratio:.1f}x at {growth_rate:.1%} growth)")
    elif growth_rate > 0.15 and ps_ratio < 15:
        score += 2
        details.append(f"Fair valuation for growth rate (P/S {ps_ratio:.1f}x at {growth_rate:.1%} growth)")
    elif ps_ratio > 50 and growth_rate < 0.15:
        details.append(
            f"Expensive for growth rate (P/S {ps_ratio:.1f}x at only {growth_rate:.1%} growth) — "
            f"stretched multiple"
        )
    else:
        score += 1
        details.append(f"Mixed valuation signal (P/S {ps_ratio:.1f}x at {growth_rate:.1%} growth)")

    # 2. FCF yield — margin of safety even at high multiples (max 4)
    fcf = getattr(latest, "free_cash_flow", None)
    if fcf is not None and market_cap > 0:
        fcf_yield = fcf / market_cap
        if fcf_yield > 0.05:
            score += 4
            details.append(
                f"High FCF yield ({fcf_yield:.1%}) — strong cash generation supports high multiple"
            )
        elif fcf_yield > 0.02:
            score += 3
            details.append(f"Decent FCF yield ({fcf_yield:.1%})")
        elif fcf_yield > 0:
            score += 1
            details.append(
                f"Positive but thin FCF yield ({fcf_yield:.1%}) — "
                f"multiple expansion reliant on growth delivery"
            )
        else:
            details.append(f"Negative FCF yield ({fcf_yield:.1%}) — priced for perfection")
    else:
        details.append("FCF data not available for yield analysis")

    return {"score": score, "max_score": 8, "details": "; ".join(details)}


def analyze_ai_news_signals(news: list) -> dict:
    """
    Scan recent news for positive AI infrastructure signals.
    Uses sentiment as a proxy for contract wins, data center expansions, and compute partnerships.
    max_score = 6 (sentiment quality:4 + news volume:2)
    """
    score = 0
    details = []

    if not news:
        return {"score": 1, "max_score": 6, "details": "No recent news — neutral assumption"}

    total = len(news)
    positive_count = sum(
        1 for n in news if n.sentiment and n.sentiment.lower() in ["positive", "bullish"]
    )
    negative_count = sum(
        1 for n in news if n.sentiment and n.sentiment.lower() in ["negative", "bearish"]
    )
    positive_ratio = positive_count / total
    negative_ratio = negative_count / total

    # Sentiment signal (max 4)
    if positive_ratio > 0.60:
        score += 4
        details.append(
            f"Strong positive news momentum ({positive_ratio:.0%} bullish) — AI infrastructure narrative intact"
        )
    elif positive_ratio > 0.40:
        score += 3
        details.append(f"Positive news bias ({positive_ratio:.0%} bullish)")
    elif positive_ratio > 0.25:
        score += 2
        details.append(f"Mixed news ({positive_ratio:.0%} bullish, {negative_ratio:.0%} bearish)")
    elif negative_ratio > 0.50:
        details.append(
            f"Negative news dominates ({negative_ratio:.0%} bearish) — AI thesis under pressure"
        )
    else:
        score += 1
        details.append(
            f"Neutral news environment ({positive_ratio:.0%} bullish, {negative_ratio:.0%} bearish)"
        )

    # News volume — high coverage signals sector attention (max 2)
    if total >= 30:
        score += 2
        details.append(f"High news volume ({total} articles) — strong AI sector coverage")
    elif total >= 15:
        score += 1
        details.append(f"Moderate news coverage ({total} articles)")
    else:
        details.append(f"Low news volume ({total} articles)")

    return {"score": score, "max_score": 6, "details": "; ".join(details)}


###############################################################################
# LLM generation
###############################################################################


def generate_ai_infra_bull_output(
    ticker: str,
    analysis_data: dict,
    state: AgentState,
    agent_id: str = "ai_infra_bull_agent",
) -> AIInfraBullSignal:
    """Generate investment signal using AI Infrastructure Bull thesis."""

    facts = {
        "score": analysis_data.get("score"),
        "max_score": analysis_data.get("max_score"),
        "revenue_mix": analysis_data.get("revenue_mix_analysis", {}).get("details"),
        "infrastructure_moat": analysis_data.get("moat_analysis", {}).get("details"),
        "backlog_contracts": analysis_data.get("backlog_analysis", {}).get("details"),
        "valuation": analysis_data.get("valuation_analysis", {}).get("details"),
        "news_signals": analysis_data.get("news_analysis", {}).get("details"),
        "market_cap": analysis_data.get("market_cap"),
    }

    template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are an AI Infrastructure Bull analyst. Your thesis: the AI infrastructure buildout "
                "(compute, data centers, networking, power) is a decade-long capex supercycle. You apply a "
                "picks-and-shovels mindset and value companies that enable AI at scale.\n"
                "\n"
                "Decision framework:\n"
                "- Bullish: strong R&D intensity, accelerating revenue growth, expanding gross margins, "
                "locked-in contracts/backlog, high capex growth signaling data center scale-up, "
                "high-switching-cost platforms (CUDA ecosystem, proprietary silicon).\n"
                "- Bearish: low R&D investment, decelerating growth, shrinking margins, no contract "
                "visibility, expensive valuation with insufficient growth, commodity hardware with no "
                "software layer.\n"
                "- Neutral: mixed signals or insufficient data.\n"
                "\n"
                "Confidence scale:\n"
                "- 90-100: Clear infrastructure winner with locked-in demand, expanding margins, fortress balance sheet\n"
                "- 70-89: Strong AI infrastructure positioning with most metrics supportive\n"
                "- 50-69: Mixed — some AI infrastructure exposure but not a pure-play conviction bet\n"
                "- 30-49: Weak infrastructure signals, limited AI revenue mix\n"
                "- 10-29: No discernible AI infrastructure moat\n"
                "\n"
                "Use vocabulary: picks-and-shovels, capex supercycle, AI compute moat, sovereign AI, "
                "CUDA ecosystem, hyperscaler, RPO/backlog, switching costs, infrastructure layer.\n"
                "Keep reasoning under 150 characters. Do not invent data. Return JSON only.",
            ),
            (
                "human",
                "Ticker: {ticker}\n"
                "Facts:\n{facts}\n\n"
                "Return exactly:\n"
                "{{\n"
                '  "signal": "bullish" | "bearish" | "neutral",\n'
                '  "confidence": int,\n'
                '  "reasoning": "short justification"\n'
                "}}",
            ),
        ]
    )

    prompt = template.invoke({
        "facts": json.dumps(facts, separators=(",", ":"), ensure_ascii=False),
        "ticker": ticker,
    })

    def create_default_signal():
        return AIInfraBullSignal(signal="neutral", confidence=50, reasoning="Insufficient data")

    return call_llm(
        prompt=prompt,
        pydantic_model=AIInfraBullSignal,
        agent_name=agent_id,
        state=state,
        default_factory=create_default_signal,
    )
