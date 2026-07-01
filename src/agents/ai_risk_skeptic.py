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


class AIRiskSkepticSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: int = Field(description="Confidence 0-100")
    reasoning: str = Field(description="Reasoning for the decision")


def ai_risk_skeptic_agent(state: AgentState, agent_id: str = "ai_risk_skeptic_agent"):
    """
    Analyzes stocks through the lens of AI sector structural risks:
    1. Regulatory exposure: EU AI Act, US export controls, AI safety legislation.
    2. Hyperscaler concentration: >60% revenue from 1-2 customers = fragile.
    3. Model commoditisation: when frontier AI is free, what survives in the stack?
    4. Valuation fragility: multiples pricing AI adoption faster than any historical tech cycle.
    Bullish on: proprietary data moats, vertical AI with regulatory shields, hardware without software substitute.
    Bearish on: pure-play AI SaaS with no proprietary data, single-hyperscaler dependency, hype-driven multiples.
    """
    data = state["data"]
    end_date = data["end_date"]
    tickers = data["tickers"]
    api_key = get_api_key_from_state(state, "FINANCIAL_DATASETS_API_KEY")

    start_date = (datetime.fromisoformat(end_date) - timedelta(days=365)).date().isoformat()

    analysis_data = {}
    skeptic_analysis = {}

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
                "total_debt",
                "cash_and_equivalents",
                "operating_expense",
                "deferred_revenue",
                "net_income",
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

        progress.update_status(agent_id, ticker, "Stress-testing valuation under commoditization")
        valuation_stress = analyze_valuation_stress(line_items, market_cap)

        progress.update_status(agent_id, ticker, "Assessing moat quality under AI commoditization")
        moat_analysis = analyze_moat_quality(metrics, line_items)

        progress.update_status(agent_id, ticker, "Analyzing revenue diversification")
        diversification_analysis = analyze_revenue_diversification(line_items)

        progress.update_status(agent_id, ticker, "Scanning for regulatory exposure")
        regulatory_analysis = analyze_regulatory_exposure(news)

        progress.update_status(agent_id, ticker, "Analyzing balance sheet fragility")
        fragility_analysis = analyze_leverage_fragility(metrics, line_items)

        total_score = (
            valuation_stress["score"]
            + moat_analysis["score"]
            + diversification_analysis["score"]
            + regulatory_analysis["score"]
            + fragility_analysis["score"]
        )
        max_possible_score = (
            valuation_stress["max_score"]
            + moat_analysis["max_score"]
            + diversification_analysis["max_score"]
            + regulatory_analysis["max_score"]
            + fragility_analysis["max_score"]
        )

        analysis_data[ticker] = {
            "ticker": ticker,
            "score": total_score,
            "max_score": max_possible_score,
            "valuation_stress": valuation_stress,
            "moat_analysis": moat_analysis,
            "diversification_analysis": diversification_analysis,
            "regulatory_analysis": regulatory_analysis,
            "fragility_analysis": fragility_analysis,
            "market_cap": market_cap,
        }

        progress.update_status(agent_id, ticker, "Generating AI Risk Skeptic analysis")
        skeptic_output = generate_ai_risk_skeptic_output(
            ticker=ticker,
            analysis_data=analysis_data[ticker],
            state=state,
            agent_id=agent_id,
        )

        skeptic_analysis[ticker] = {
            "signal": skeptic_output.signal,
            "confidence": skeptic_output.confidence,
            "reasoning": skeptic_output.reasoning,
        }

        progress.update_status(agent_id, ticker, "Done", analysis=skeptic_output.reasoning)

    message = HumanMessage(content=json.dumps(skeptic_analysis), name=agent_id)

    if state["metadata"].get("show_reasoning"):
        show_agent_reasoning(skeptic_analysis, agent_id)

    state["data"]["analyst_signals"][agent_id] = skeptic_analysis

    progress.update_status(agent_id, None, "Done")

    return {"messages": [message], "data": state["data"]}


###############################################################################
# Sub-analysis functions
###############################################################################


def analyze_valuation_stress(line_items: list, market_cap: float) -> dict:
    """
    Core skeptic question: if AI commoditises in 3 years and growth falls to 5%,
    what is this company worth? High score = company survives the stress test.
    max_score = 10 (stress downside:4 + P/S vs growth:3 + gross margin resilience:3)
    """
    score = 0
    details = []

    if not line_items or market_cap is None or market_cap <= 0:
        return {"score": 0, "max_score": 10, "details": "Insufficient data for valuation stress test"}

    revenues = [item.revenue for item in line_items if item.revenue]
    if not revenues:
        return {"score": 0, "max_score": 10, "details": "No revenue data for stress test"}

    current_revenue = revenues[0]
    current_ps = market_cap / current_revenue

    current_growth = 0.0
    if len(revenues) >= 2 and revenues[1]:
        current_growth = (revenues[0] - revenues[1]) / abs(revenues[1])

    # Stress scenario: AI commoditises → growth falls to 5%, valued at mature 3x P/S
    stress_revenue = current_revenue * (1 + 0.05) ** 3
    stress_valuation = stress_revenue * 3.0
    stress_downside = (stress_valuation - market_cap) / market_cap

    # 1. Commoditization stress downside (max 4)
    if stress_downside > -0.20:
        score += 4
        details.append(
            f"Passes commoditization stress test (implied downside {stress_downside:.0%}) — "
            f"not priced for hypergrowth only"
        )
    elif stress_downside > -0.50:
        score += 2
        details.append(
            f"Moderate downside in stress scenario ({stress_downside:.0%}) — "
            f"some growth premium but survivable"
        )
    else:
        details.append(
            f"Severe downside in commoditization scenario ({stress_downside:.0%}) — "
            f"market pricing in perpetual hypergrowth"
        )

    # 2. Current valuation vs growth rate — is the multiple justified? (max 3)
    if current_ps < 5 and current_growth > 0.10:
        score += 3
        details.append(
            f"Cheap relative to growth (P/S {current_ps:.1f}x at {current_growth:.1%} growth) — "
            f"value even in stress scenario"
        )
    elif current_ps < 15 and current_growth > 0.20:
        score += 2
        details.append(
            f"Reasonable multiple for growth (P/S {current_ps:.1f}x at {current_growth:.1%} growth)"
        )
    elif current_ps > 30 and current_growth < 0.25:
        details.append(
            f"Expensive relative to growth (P/S {current_ps:.1f}x at {current_growth:.1%} growth) — "
            f"priced for perfection"
        )
    else:
        score += 1
        details.append(f"Mixed valuation signal (P/S {current_ps:.1f}x at {current_growth:.1%} growth)")

    # 3. Gross margin structure — what survives commoditization? (max 3)
    gross_margins = [
        item.gross_margin for item in line_items
        if hasattr(item, "gross_margin") and item.gross_margin is not None
    ]
    if gross_margins:
        gm = gross_margins[0]
        if gm > 0.75:
            details.append(
                f"Very high gross margins ({gm:.1%}) — pure SaaS AI at highest commoditization risk; "
                f"margins could compress 20-30% if foundation models become free"
            )
        elif gm > 0.50:
            score += 2
            details.append(
                f"Mixed gross margins ({gm:.1%}) — hardware/services component adds resilience "
                f"against pure AI commoditization"
            )
        elif gm > 0.30:
            score += 3
            details.append(
                f"Infrastructure-grade margins ({gm:.1%}) — hardware moat is hardest to commoditize; "
                f"physical compute remains scarce even when models are free"
            )
        else:
            score += 1
            details.append(
                f"Thin gross margins ({gm:.1%}) — already price-competitive; "
                f"limited additional margin risk from commoditization"
            )
    else:
        details.append("Gross margin data not available")

    return {"score": score, "max_score": 10, "details": "; ".join(details)}


def analyze_moat_quality(metrics: list, line_items: list) -> dict:
    """
    Assess whether the company has structural moats that survive AI commoditization:
    proprietary data (R&D intensity), hardware barriers (capex intensity),
    capital-intensive barriers (asset intensity), and pricing power stability.
    max_score = 10 (R&D moat:3 + capex moat:3 + asset intensity:2 + margin stability:2)
    """
    score = 0
    details = []

    if not line_items:
        return {"score": 0, "max_score": 10, "details": "Insufficient data for moat quality analysis"}

    revenues = [item.revenue for item in line_items if item.revenue]
    latest = line_items[0]

    # 1. R&D intensity — proxy for proprietary technology/data moat (max 3)
    rd_expenses = [
        item.research_and_development for item in line_items
        if hasattr(item, "research_and_development") and item.research_and_development is not None
    ]
    if rd_expenses and revenues:
        rd_intensity = abs(rd_expenses[0]) / revenues[0] if revenues[0] else 0
        if rd_intensity > 0.20:
            score += 3
            details.append(
                f"Deep proprietary tech investment ({rd_intensity:.1%} R&D intensity) — "
                f"building moat that survives commoditization"
            )
        elif rd_intensity > 0.12:
            score += 2
            details.append(f"Meaningful R&D moat ({rd_intensity:.1%} R&D intensity)")
        elif rd_intensity > 0.05:
            score += 1
            details.append(f"Some R&D investment ({rd_intensity:.1%}) — modest proprietary differentiation")
        else:
            details.append(
                f"Low R&D ({rd_intensity:.1%}) — no proprietary data or tech moat; "
                f"high commoditization risk"
            )
    else:
        details.append("R&D data not available")

    # 2. Capex intensity — hardware moat, physically impossible to replicate quickly (max 3)
    capex = [
        item.capital_expenditure for item in line_items
        if hasattr(item, "capital_expenditure") and item.capital_expenditure is not None
    ]
    if capex and revenues:
        capex_intensity = abs(capex[0]) / revenues[0] if revenues[0] else 0
        if capex_intensity > 0.15:
            score += 3
            details.append(
                f"Heavy physical infrastructure investment ({capex_intensity:.1%} capex intensity) — "
                f"hardware moat cannot be replicated by software commoditization"
            )
        elif capex_intensity > 0.08:
            score += 2
            details.append(f"Meaningful capex moat ({capex_intensity:.1%} capex intensity)")
        elif capex_intensity > 0.03:
            score += 1
            details.append(f"Some physical asset base ({capex_intensity:.1%} capex intensity)")
        else:
            details.append(
                f"Asset-light model ({capex_intensity:.1%} capex intensity) — "
                f"pure software: most vulnerable to model commoditization"
            )
    else:
        details.append("Capex data not available")

    # 3. Asset intensity — capital-intensive businesses have structural entry barriers (max 2)
    total_assets = getattr(latest, "total_assets", None)
    if total_assets is not None and revenues:
        asset_intensity = total_assets / revenues[0] if revenues[0] else 0
        if asset_intensity > 1.5:
            score += 2
            details.append(
                f"High asset intensity ({asset_intensity:.1f}x revenue) — "
                f"capital barriers protect against new AI-only entrants"
            )
        elif asset_intensity > 0.8:
            score += 1
            details.append(f"Moderate asset intensity ({asset_intensity:.1f}x revenue)")
        else:
            details.append(
                f"Low asset intensity ({asset_intensity:.1f}x revenue) — "
                f"low barriers; easy for AI-native competitors to replicate"
            )
    else:
        details.append("Asset data not available")

    # 4. Operating margin stability — pricing power survives disruption cycles (max 2)
    op_margins = [
        m.operating_margin for m in metrics if m.operating_margin is not None
    ] if metrics else []
    if len(op_margins) >= 3:
        mean_m = sum(op_margins) / len(op_margins)
        variance = sum((m - mean_m) ** 2 for m in op_margins) / len(op_margins)
        std_m = variance ** 0.5
        cv = std_m / abs(mean_m) if mean_m != 0 else float("inf")
        if cv < 0.20 and mean_m > 0.10:
            score += 2
            details.append(
                f"Stable operating margins (avg {mean_m:.1%}, CV {cv:.2f}) — "
                f"pricing power survives disruption"
            )
        elif cv < 0.40:
            score += 1
            details.append(f"Moderate margin stability (CV {cv:.2f})")
        else:
            details.append(
                f"Volatile operating margins (CV {cv:.2f}) — fragile pricing power in commoditization"
            )
    else:
        details.append("Insufficient margin history for stability analysis")

    return {"score": score, "max_score": 10, "details": "; ".join(details)}


def analyze_revenue_diversification(line_items: list) -> dict:
    """
    Assess customer/revenue concentration risk.
    High variance growth = concentrated customer base (hyperscaler dependency).
    Deferred revenue growth = contracted, sticky revenue = not single-customer dependent.
    max_score = 6 (revenue consistency:3 + deferred revenue:3)
    """
    score = 0
    details = []

    if not line_items:
        return {"score": 0, "max_score": 6, "details": "Insufficient data for diversification analysis"}

    revenues = [item.revenue for item in line_items if item.revenue]

    # 1. Revenue growth consistency — low variance = diversified customer base (max 3)
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
            if cv < 0.25 and mean_g > 0:
                score += 3
                details.append(
                    f"Low revenue volatility (CV {cv:.2f}) — diversified customer base, "
                    f"not exposed to single hyperscaler concentration"
                )
            elif cv < 0.50:
                score += 2
                details.append(f"Moderate revenue consistency (CV {cv:.2f})")
            elif cv < 1.0:
                score += 1
                details.append(
                    f"High revenue volatility (CV {cv:.2f}) — possible customer concentration risk"
                )
            else:
                details.append(
                    f"Extreme revenue volatility (CV {cv:.2f}) — likely hyperscaler concentration; "
                    f"single-contract dependency"
                )
        else:
            details.append("Insufficient growth history")
    else:
        details.append("Insufficient revenue history for consistency analysis")

    # 2. Deferred revenue — contracted, sticky revenue signals multi-customer base (max 3)
    deferred = [getattr(item, "deferred_revenue", None) for item in line_items]
    deferred = [v for v in deferred if v is not None and v > 0]
    if len(deferred) >= 2 and revenues:
        def_growth = (deferred[0] - deferred[-1]) / abs(deferred[-1]) if deferred[-1] else 0
        def_to_rev = deferred[0] / revenues[0] if revenues[0] else 0
        if def_growth > 0.20 and def_to_rev > 0.10:
            score += 3
            details.append(
                f"Growing contracted revenue ({def_growth:.1%} deferred growth, "
                f"{def_to_rev:.1%} of revenue) — multi-customer sticky contracts, not hyperscaler dependent"
            )
        elif def_growth > 0.10 or def_to_rev > 0.05:
            score += 2
            details.append(f"Some contracted revenue visibility (deferred +{def_growth:.1%})")
        elif def_growth > 0:
            score += 1
            details.append(f"Modest deferred revenue growth ({def_growth:.1%})")
        else:
            details.append("No deferred revenue growth — transactional model with concentration risk")
    else:
        details.append("Deferred revenue data not available")

    return {"score": score, "max_score": 6, "details": "; ".join(details)}


def analyze_regulatory_exposure(news: list) -> dict:
    """
    High negative news sentiment = elevated regulatory/reputational risk.
    High score = clean news environment (passes regulatory smell test).
    max_score = 4
    """
    score = 0
    details = []

    if not news:
        return {"score": 2, "max_score": 4, "details": "No recent news — neutral regulatory assumption"}

    total = len(news)
    negative_count = sum(
        1 for n in news if n.sentiment and n.sentiment.lower() in ["negative", "bearish"]
    )
    negative_ratio = negative_count / total

    if negative_ratio > 0.60:
        details.append(
            f"Heavy negative news ({negative_ratio:.0%}) — elevated regulatory/reputational risk; "
            f"EU AI Act, export controls, or safety concerns likely in headlines"
        )
    elif negative_ratio > 0.40:
        score += 1
        details.append(
            f"Significant negative news ({negative_ratio:.0%}) — regulatory headwinds visible"
        )
    elif negative_ratio > 0.25:
        score += 2
        details.append(f"Moderate negative news ({negative_ratio:.0%}) — some regulatory noise")
    elif negative_ratio > 0.10:
        score += 3
        details.append(f"Low negative news ({negative_ratio:.0%}) — limited visible regulatory risk")
    else:
        score += 4
        details.append(
            f"Clean news environment ({negative_ratio:.0%} negative) — no visible regulatory exposure"
        )

    return {"score": score, "max_score": 4, "details": "; ".join(details)}


def analyze_leverage_fragility(metrics: list, line_items: list) -> dict:
    """
    A leveraged AI company cannot survive a regulatory shock or capex cycle downturn.
    High score = low debt + positive FCF = survives without capital markets.
    max_score = 6 (debt:3 + FCF:3)
    """
    score = 0
    details = []

    if not metrics and not line_items:
        return {"score": 0, "max_score": 6, "details": "Insufficient data for fragility analysis"}

    # 1. Leverage — high debt is catastrophic when AI narrative reverses (max 3)
    latest_metrics = metrics[0] if metrics else None
    debt_to_equity = getattr(latest_metrics, "debt_to_equity", None) if latest_metrics else None
    if debt_to_equity is not None:
        if debt_to_equity < 0.3:
            score += 3
            details.append(
                f"Low leverage (D/E {debt_to_equity:.2f}) — survives regulatory shock or AI narrative reversal"
            )
        elif debt_to_equity < 0.8:
            score += 2
            details.append(f"Manageable leverage (D/E {debt_to_equity:.2f})")
        elif debt_to_equity < 2.0:
            score += 1
            details.append(
                f"Elevated leverage (D/E {debt_to_equity:.2f}) — vulnerable to rate rises or credit tightening"
            )
        else:
            details.append(
                f"Dangerous leverage (D/E {debt_to_equity:.2f}) — one regulatory shock away from distress"
            )
    else:
        details.append("Debt-to-equity data not available")

    # 2. FCF — positive FCF means no forced dilution when AI sentiment turns (max 3)
    fcf_values = [getattr(item, "free_cash_flow", None) for item in line_items] if line_items else []
    fcf = [v for v in fcf_values if v is not None]
    if fcf:
        positive_count = sum(1 for v in fcf if v > 0)
        if positive_count == len(fcf) and len(fcf) >= 3:
            score += 3
            details.append(
                f"Consistently FCF positive ({positive_count}/{len(fcf)} periods) — "
                f"no forced equity issuance risk when AI sentiment turns"
            )
        elif positive_count >= len(fcf) * 0.75:
            score += 2
            details.append(f"Mostly FCF positive ({positive_count}/{len(fcf)} periods)")
        elif positive_count > 0:
            score += 1
            details.append(f"Inconsistent FCF ({positive_count}/{len(fcf)} periods positive)")
        else:
            details.append(
                "Persistently FCF negative — dependent on capital markets; "
                "regulatory shock could be existential"
            )
    else:
        details.append("FCF data not available")

    return {"score": score, "max_score": 6, "details": "; ".join(details)}


###############################################################################
# LLM generation
###############################################################################


def generate_ai_risk_skeptic_output(
    ticker: str,
    analysis_data: dict,
    state: AgentState,
    agent_id: str = "ai_risk_skeptic_agent",
) -> AIRiskSkepticSignal:
    """Generate investment signal using AI Risk Skeptic thesis."""

    facts = {
        "score": analysis_data.get("score"),
        "max_score": analysis_data.get("max_score"),
        "valuation_stress": analysis_data.get("valuation_stress", {}).get("details"),
        "moat_quality": analysis_data.get("moat_analysis", {}).get("details"),
        "revenue_diversification": analysis_data.get("diversification_analysis", {}).get("details"),
        "regulatory_exposure": analysis_data.get("regulatory_analysis", {}).get("details"),
        "leverage_fragility": analysis_data.get("fragility_analysis", {}).get("details"),
        "market_cap": analysis_data.get("market_cap"),
    }

    template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are an AI Risk Skeptic. Your core question for every stock: "
                "'If AI commoditises in 3 years, what is this company worth?'\n"
                "\n"
                "Decision framework:\n"
                "- Bullish: company passes the commoditization stress test — has proprietary data moat, "
                "hardware infrastructure that cannot be replicated by software, or vertical AI with "
                "regulatory shields. Low leverage. Valuation already prices in a slow-growth scenario.\n"
                "- Bearish: pure-play AI SaaS with no proprietary data or hardware moat, "
                "single-hyperscaler revenue dependency (>60%), valuation pricing perpetual hypergrowth, "
                "high leverage that cannot survive a narrative reversal, or heavy regulatory exposure "
                "(EU AI Act, US export controls, AI safety legislation).\n"
                "- Neutral: mixed moat signals, moderate regulatory risk, valuation somewhere between "
                "stress-test fair value and hype pricing.\n"
                "\n"
                "Confidence scale:\n"
                "- 90-100: Company survives all stress scenarios; antifragile to AI commoditization\n"
                "- 70-89: Passes most stress tests; some exposure but manageable\n"
                "- 50-69: Mixed — survives commoditization but not without pain\n"
                "- 30-49: Meaningful fragility; multiple AI risk factors present\n"
                "- 10-29: Fails the commoditization stress test; avoid\n"
                "\n"
                "Use vocabulary: commoditization scenario, hyperscaler dependency, regulatory tail risk, "
                "proprietary data moat, hardware moat, model wrapper, stress-test valuation, "
                "AI hype premium, export controls.\n"
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
        return AIRiskSkepticSignal(signal="neutral", confidence=50, reasoning="Insufficient data")

    return call_llm(
        prompt=prompt,
        pydantic_model=AIRiskSkepticSignal,
        agent_name=agent_id,
        state=state,
        default_factory=create_default_signal,
    )
