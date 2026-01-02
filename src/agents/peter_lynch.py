from src.graph.state import AgentState, show_agent_reasoning
from src.tools.api import (
    get_market_cap,
    search_line_items,
    get_insider_trades,
    get_company_news,
)
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage
from pydantic import BaseModel
import json
from typing_extensions import Literal
from src.utils.progress import progress
from src.utils.llm import call_llm
from src.utils.api_key import get_api_key_from_state


class PeterLynchSignal(BaseModel):
    """
    Container for the Peter Lynch-style output signal.
    """
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: float
    reasoning: str


def peter_lynch_agent(state: AgentState, agent_id: str = "peter_lynch_agent"):
    """
    Analyzes stocks using Peter Lynch's investing principles:
      - Invest in what you know (clear, understandable businesses).
      - Growth at a Reasonable Price (GARP), emphasizing the PEG ratio.
      - Look for consistent revenue & EPS increases and manageable debt.
      - Be alert for potential "ten-baggers" (high-growth opportunities).
      - Avoid overly complex or highly leveraged businesses.
      - Use news sentiment and insider trades for secondary inputs.
      - If fundamentals strongly align with GARP, be more aggressive.

    The result is a bullish/bearish/neutral signal, along with a
    confidence (0–100) and a textual reasoning explanation.
    """

    data = state["data"]
    end_date = data["end_date"]
    tickers = data["tickers"]
    api_key = get_api_key_from_state(state, "FINANCIAL_DATASETS_API_KEY")
    analysis_data = {}
    lynch_analysis = {}

    for ticker in tickers:
        progress.update_status(agent_id, ticker, "Gathering financial line items")
        # Relevant line items for Peter Lynch's approach
        financial_line_items = search_line_items(
            ticker,
            [
                "revenue",
                "earnings_per_share",
                "net_income",
                "operating_income",
                "gross_margin",
                "operating_margin",
                "free_cash_flow",
                "capital_expenditure",
                "cash_and_equivalents",
                "total_debt",
                "shareholders_equity",
                "outstanding_shares",
            ],
            end_date,
            period="annual",
            limit=5,
            api_key=api_key,
        )

        progress.update_status(agent_id, ticker, "Getting market cap")
        market_cap = get_market_cap(ticker, end_date, api_key=api_key)

        progress.update_status(agent_id, ticker, "Fetching insider trades")
        insider_trades = get_insider_trades(ticker, end_date, limit=50, api_key=api_key)

        progress.update_status(agent_id, ticker, "Fetching company news")
        company_news = get_company_news(ticker, end_date, limit=50, api_key=api_key)

        # Perform sub-analyses:
        progress.update_status(agent_id, ticker, "Analyzing growth")
        growth_analysis = analyze_lynch_growth(financial_line_items)

        progress.update_status(agent_id, ticker, "Analyzing fundamentals")
        fundamentals_analysis = analyze_lynch_fundamentals(financial_line_items)

        progress.update_status(agent_id, ticker, "Analyzing valuation (focus on PEG)")
        valuation_analysis = analyze_lynch_valuation(financial_line_items, market_cap)

        progress.update_status(agent_id, ticker, "Analyzing sentiment")
        sentiment_analysis = analyze_sentiment(company_news)

        progress.update_status(agent_id, ticker, "Analyzing insider activity")
        insider_activity = analyze_insider_activity(insider_trades)

        # Combine partial scores with weights typical for Peter Lynch:
        #   30% Growth, 25% Valuation, 20% Fundamentals,
        #   15% Sentiment, 10% Insider Activity = 100%
        total_score = (
            growth_analysis["score"] * 0.30
            + valuation_analysis["score"] * 0.25
            + fundamentals_analysis["score"] * 0.20
            + sentiment_analysis["score"] * 0.15
            + insider_activity["score"] * 0.10
        )

        max_possible_score = 10.0

        # Map final score to signal
        if total_score >= 7.5:
            signal = "bullish"
        elif total_score <= 4.5:
            signal = "bearish"
        else:
            signal = "neutral"

        analysis_data[ticker] = {
            "signal": signal,
            "score": total_score,
            "max_score": max_possible_score,
            "growth_analysis": growth_analysis,
            "valuation_analysis": valuation_analysis,
            "fundamentals_analysis": fundamentals_analysis,
            "sentiment_analysis": sentiment_analysis,
            "insider_activity": insider_activity,
        }

        progress.update_status(agent_id, ticker, "Generating Peter Lynch analysis")
        lynch_output = generate_lynch_output(
            ticker=ticker,
            analysis_data=analysis_data[ticker],
            state=state,
            agent_id=agent_id,
        )

        lynch_analysis[ticker] = {
            "signal": lynch_output.signal,
            "confidence": lynch_output.confidence,
            "reasoning": lynch_output.reasoning,
        }

        progress.update_status(agent_id, ticker, "Done", analysis=lynch_output.reasoning)

    # Wrap up results
    message = HumanMessage(content=json.dumps(lynch_analysis), name=agent_id)

    if state["metadata"].get("show_reasoning"):
        show_agent_reasoning(lynch_analysis, "Peter Lynch Agent")

    # Save signals to state
    state["data"]["analyst_signals"][agent_id] = lynch_analysis

    progress.update_status(agent_id, None, "Done")

    return {"messages": [message], "data": state["data"]}


def analyze_lynch_growth(financial_line_items: list) -> dict:
    """
    Evaluate growth based on revenue and EPS trends:
      - Consistent revenue growth
      - Consistent EPS growth
    Peter Lynch liked companies with steady, understandable growth,
    often searching for potential 'ten-baggers' with a long runway.
    """
    if not financial_line_items or len(financial_line_items) < 2:
        return {"score": 0, "details": "Insufficient financial data for growth analysis"}

    details = []
    raw_score = 0  # We'll sum up points, then scale to 0–10 eventually

    # 1) Revenue Growth
    revenues = [fi.revenue for fi in financial_line_items if fi.revenue is not None]
    if len(revenues) >= 2:
        latest_rev = revenues[0]
        older_rev = revenues[-1]
        if older_rev > 0:
            rev_growth = (latest_rev - older_rev) / abs(older_rev)
            if rev_growth > 0.25:
                raw_score += 3
                details.append(f"Strong revenue growth: {rev_growth:.1%}")
            elif rev_growth > 0.10:
                raw_score += 2
                details.append(f"Moderate revenue growth: {rev_growth:.1%}")
            elif rev_growth > 0.02:
                raw_score += 1
                details.append(f"Slight revenue growth: {rev_growth:.1%}")
            else:
                details.append(f"Flat or negative revenue growth: {rev_growth:.1%}")
        else:
            details.append("Older revenue is zero/negative; can't compute revenue growth.")
    else:
        details.append("Not enough revenue data to assess growth.")

    # 2) EPS Growth
    eps_values = [fi.earnings_per_share for fi in financial_line_items if fi.earnings_per_share is not None]
    if len(eps_values) >= 2:
        latest_eps = eps_values[0]
        older_eps = eps_values[-1]
        if abs(older_eps) > 1e-9:
            eps_growth = (latest_eps - older_eps) / abs(older_eps)
            if eps_growth > 0.25:
                raw_score += 3
                details.append(f"Strong EPS growth: {eps_growth:.1%}")
            elif eps_growth > 0.10:
                raw_score += 2
                details.append(f"Moderate EPS growth: {eps_growth:.1%}")
            elif eps_growth > 0.02:
                raw_score += 1
                details.append(f"Slight EPS growth: {eps_growth:.1%}")
            else:
                details.append(f"Minimal or negative EPS growth: {eps_growth:.1%}")
        else:
            details.append("Older EPS is near zero; skipping EPS growth calculation.")
    else:
        details.append("Not enough EPS data for growth calculation.")

    # raw_score can be up to 6 => scale to 0–10
    final_score = min(10, (raw_score / 6) * 10)
    return {"score": final_score, "details": "; ".join(details)}


def analyze_lynch_fundamentals(financial_line_items: list) -> dict:
    """
    Evaluate basic fundamentals:
      - Debt/Equity
      - Operating margin (or gross margin)
      - Positive Free Cash Flow
    Lynch avoided heavily indebted or complicated businesses.
    """
    if not financial_line_items:
        return {"score": 0, "details": "Insufficient fundamentals data"}

    details = []
    raw_score = 0  # We'll accumulate up to 6 points, then scale to 0–10

    # 1) Debt-to-Equity
    debt_values = [fi.total_debt for fi in financial_line_items if fi.total_debt is not None]
    eq_values = [fi.shareholders_equity for fi in financial_line_items if fi.shareholders_equity is not None]
    if debt_values and eq_values and len(debt_values) == len(eq_values) and len(debt_values) > 0:
        recent_debt = debt_values[0]
        recent_equity = eq_values[0] if eq_values[0] else 1e-9
        de_ratio = recent_debt / recent_equity
        if de_ratio < 0.5:
            raw_score += 2
            details.append(f"Low debt-to-equity: {de_ratio:.2f}")
        elif de_ratio < 1.0:
            raw_score += 1
            details.append(f"Moderate debt-to-equity: {de_ratio:.2f}")
        else:
            details.append(f"High debt-to-equity: {de_ratio:.2f}")
    else:
        details.append("No consistent debt/equity data available.")

    # 2) Operating Margin
    om_values = [fi.operating_margin for fi in financial_line_items if fi.operating_margin is not None]
    if om_values:
        om_recent = om_values[0]
        if om_recent > 0.20:
            raw_score += 2
            details.append(f"Strong operating margin: {om_recent:.1%}")
        elif om_recent > 0.10:
            raw_score += 1
            details.append(f"Moderate operating margin: {om_recent:.1%}")
        else:
            details.append(f"Low operating margin: {om_recent:.1%}")
    else:
        details.append("No operating margin data available.")

    # 3) Positive Free Cash Flow
    fcf_values = [fi.free_cash_flow for fi in financial_line_items if fi.free_cash_flow is not None]
    if fcf_values and fcf_values[0] is not None:
        if fcf_values[0] > 0:
            raw_score += 2
            details.append(f"Positive free cash flow: {fcf_values[0]:,.0f}")
        else:
            details.append(f"Recent FCF is negative: {fcf_values[0]:,.0f}")
    else:
        details.append("No free cash flow data available.")

    # raw_score up to 6 => scale to 0–10
    final_score = min(10, (raw_score / 6) * 10)
    return {"score": final_score, "details": "; ".join(details)}


def analyze_lynch_valuation(financial_line_items: list, market_cap: float | None) -> dict:
    """
    Peter Lynch's approach to 'Growth at a Reasonable Price' (GARP):
      - Emphasize the PEG ratio: (P/E) / Growth Rate
      - Also consider a basic P/E if PEG is unavailable
    A PEG < 1 is very attractive; 1-2 is fair; >2 is expensive.
    """
    if not financial_line_items or market_cap is None:
        return {"score": 0, "details": "Insufficient data for valuation"}

    details = []
    raw_score = 0

    # Gather data for P/E
    net_incomes = [fi.net_income for fi in financial_line_items if fi.net_income is not None]
    eps_values = [fi.earnings_per_share for fi in financial_line_items if fi.earnings_per_share is not None]

    # Approximate P/E via (market cap / net income) if net income is positive
    pe_ratio = None
    if net_incomes and net_incomes[0] and net_incomes[0] > 0:
        pe_ratio = market_cap / net_incomes[0]
        details.append(f"Estimated P/E: {pe_ratio:.2f}")
    else:
        details.append("No positive net income => can't compute approximate P/E")

    # If we have at least 2 EPS data points, let's estimate growth
    eps_growth_rate = None
    if len(eps_values) >= 2:
        latest_eps = eps_values[0]
        older_eps = eps_values[-1]
        if older_eps > 0:
            # Calculate annualized growth rate (CAGR) for PEG ratio
            num_years = len(eps_values) - 1
            if latest_eps > 0:
                # CAGR formula: (ending_value/beginning_value)^(1/years) - 1
                eps_growth_rate = (latest_eps / older_eps) ** (1 / num_years) - 1
            else:
                # If latest EPS is negative, use simple average growth
                eps_growth_rate = (latest_eps - older_eps) / (older_eps * num_years)
            details.append(f"Annualized EPS growth rate: {eps_growth_rate:.1%}")
        else:
            details.append("Cannot compute EPS growth rate (older EPS <= 0)")
    else:
        details.append("Not enough EPS data to compute growth rate")

    # Compute PEG if possible
    peg_ratio = None
    if pe_ratio and eps_growth_rate and eps_growth_rate > 0:
        # PEG ratio formula: P/E divided by growth rate (as percentage)
        # Since eps_growth_rate is stored as decimal (0.25 for 25%),
        # we multiply by 100 to convert to percentage for the PEG calculation
        # Example: P/E=20, growth=0.25 (25%) => PEG = 20/25 = 0.8
        peg_ratio = pe_ratio / (eps_growth_rate * 100)
        details.append(f"PEG ratio: {peg_ratio:.2f}")

    # Scoring logic:
    #   - P/E < 15 => +2, < 25 => +1
    #   - PEG < 1 => +3, < 2 => +2, < 3 => +1
    if pe_ratio is not None:
        if pe_ratio < 15:
            raw_score += 2
        elif pe_ratio < 25:
            raw_score += 1

    if peg_ratio is not None:
        if peg_ratio < 1:
            raw_score += 3
        elif peg_ratio < 2:
            raw_score += 2
        elif peg_ratio < 3:
            raw_score += 1

    final_score = min(10, (raw_score / 5) * 10)
    return {"score": final_score, "details": "; ".join(details)}


def analyze_sentiment(news_items: list) -> dict:
    """
    Basic news sentiment check. Negative headlines weigh on the final score.
    """
    if not news_items:
        return {"score": 5, "details": "No news data; default to neutral sentiment"}

    negative_keywords = ["lawsuit", "fraud", "negative", "downturn", "decline", "investigation", "recall"]
    negative_count = 0
    for news in news_items:
        title_lower = (news.title or "").lower()
        if any(word in title_lower for word in negative_keywords):
            negative_count += 1

    details = []
    if negative_count > len(news_items) * 0.3:
        # More than 30% negative => somewhat bearish => 3/10
        score = 3
        details.append(f"High proportion of negative headlines: {negative_count}/{len(news_items)}")
    elif negative_count > 0:
        # Some negativity => 6/10
        score = 6
        details.append(f"Some negative headlines: {negative_count}/{len(news_items)}")
    else:
        # Mostly positive => 8/10
        score = 8
        details.append("Mostly positive or neutral headlines")

    return {"score": score, "details": "; ".join(details)}


def analyze_insider_activity(insider_trades: list) -> dict:
    """
    Simple insider-trade analysis:
      - If there's heavy insider buying, it's a positive sign.
      - If there's mostly selling, it's a negative sign.
      - Otherwise, neutral.
    """
    # Default 5 (neutral)
    score = 5
    details = []

    if not insider_trades:
        details.append("No insider trades data; defaulting to neutral")
        return {"score": score, "details": "; ".join(details)}

    buys, sells = 0, 0
    for trade in insider_trades:
        if trade.transaction_shares is not None:
            if trade.transaction_shares > 0:
                buys += 1
            elif trade.transaction_shares < 0:
                sells += 1

    total = buys + sells
    if total == 0:
        details.append("No significant buy/sell transactions found; neutral stance")
        return {"score": score, "details": "; ".join(details)}

    buy_ratio = buys / total
    if buy_ratio > 0.7:
        # Heavy buying => +3 => total 8
        score = 8
        details.append(f"Heavy insider buying: {buys} buys vs. {sells} sells")
    elif buy_ratio > 0.4:
        # Some buying => +1 => total 6
        score = 6
        details.append(f"Moderate insider buying: {buys} buys vs. {sells} sells")
    else:
        # Mostly selling => -1 => total 4
        score = 4
        details.append(f"Mostly insider selling: {buys} buys vs. {sells} sells")

    return {"score": score, "details": "; ".join(details)}


def generate_lynch_output(
    ticker: str,
    analysis_data: dict[str, any],
    state: AgentState,
    agent_id: str,
) -> PeterLynchSignal:
    """
    Generates a final JSON signal in Peter Lynch's voice & style.
    """
    template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are a Peter Lynch AI agent. You make investment decisions based on Peter Lynch's well-known principles:
                
                1. Invest in What You Know: Emphasize understandable businesses, possibly discovered in everyday life.
                2. Growth at a Reasonable Price (GARP): Rely on the PEG ratio as a prime metric.
                3. Look for 'Ten-Baggers': Companies capable of growing earnings and share price substantially.
                4. Steady Growth: Prefer consistent revenue/earnings expansion, less concern about short-term noise.
                5. Avoid High Debt: Watch for dangerous leverage.
                6. Management & Story: A good 'story' behind the stock, but not overhyped or too complex.
                
                When you provide your reasoning, do it in Peter Lynch's voice:
                - Cite the PEG ratio
                - Mention 'ten-bagger' potential if applicable
                - Refer to personal or anecdotal observations (e.g., "If my kids love the product...")
                - Use practical, folksy language
                - Provide key positives and negatives
                - Conclude with a clear stance (bullish, bearish, or neutral)
                
                Return your final output strictly in JSON with the fields:
                {{
                  "signal": "bullish" | "bearish" | "neutral",
                  "confidence": 0 to 100,
                  "reasoning": "string"
                }}
                """,
            ),
            (
                "human",
                """Based on the following analysis data for {ticker}, produce your Peter Lynch–style investment signal.

                Analysis Data:
                {analysis_data}

                Return only valid JSON with "signal", "confidence", and "reasoning".
                """,
            ),
        ]
    )

    prompt = template.invoke({"analysis_data": json.dumps(analysis_data, indent=2), "ticker": ticker})

    def create_default_signal():
        return PeterLynchSignal(
            signal="neutral",
            confidence=0.0,
            reasoning="Error in analysis; defaulting to neutral"
        )

    return call_llm(
        prompt=prompt,
        pydantic_model=PeterLynchSignal,
        agent_name=agent_id,
        state=state,
        default_factory=create_default_signal,
    )
