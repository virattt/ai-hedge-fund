"""FYI Market Context Agent — broad market/sector backdrop, informational only."""
import json

import pandas as pd
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from src.graph.state import AgentState
from src.tools.api import get_company_news, get_financial_metrics, get_prices, prices_to_df
from src.utils.api_key import get_api_key_from_state
from src.utils.llm import call_llm
from src.utils.progress import progress


class MarketContextOutput(BaseModel):
    signal: str = Field(description="bullish, bearish, or neutral")
    confidence: int = Field(description="0-100")
    reasoning: str = Field(description="3 sentences: macro backdrop, sector position, catalyst watch")
    sector_outlook: str = Field(description="1 sentence on sector outlook")
    macro_theme: str = Field(description="1 sentence on dominant macro theme affecting this stock")


def fyi_market_context_agent(state: AgentState, agent_id: str = "fyi_market_context_agent"):
    """
    FYI-only agent. Analyzes broader market environment for each ticker.
    Does NOT influence trading decisions (filtered by portfolio manager).
    """
    data = state["data"]
    start_date = data["start_date"]
    end_date = data["end_date"]
    tickers = data["tickers"]
    api_key = get_api_key_from_state(state, "FINANCIAL_DATASETS_API_KEY")

    market_context = {}

    for ticker in tickers:
        progress.update_status(agent_id, ticker, "Fetching market context data")

        prices = get_prices(ticker, start_date, end_date, api_key=api_key)
        prices_df = prices_to_df(prices) if prices else pd.DataFrame()

        metrics_list = get_financial_metrics(ticker, end_date, period="ttm", limit=4, api_key=api_key)
        news_list = get_company_news(ticker, end_date, start_date, limit=20, api_key=api_key)

        # Price performance context
        price_ctx = {}
        if not prices_df.empty and len(prices_df) >= 5:
            cur = float(prices_df["close"].iloc[-1])
            p1m = float(prices_df["close"].iloc[-21]) if len(prices_df) > 21 else float(prices_df["close"].iloc[0])
            p3m = float(prices_df["close"].iloc[-63]) if len(prices_df) > 63 else float(prices_df["close"].iloc[0])
            p6m = float(prices_df["close"].iloc[-126]) if len(prices_df) > 126 else float(prices_df["close"].iloc[0])
            price_ctx = {
                "current_price": round(cur, 2),
                "1m_return_pct": round((cur / p1m - 1) * 100, 2),
                "3m_return_pct": round((cur / p3m - 1) * 100, 2),
                "6m_return_pct": round((cur / p6m - 1) * 100, 2),
            }

        # Financial metrics snapshot
        metrics_ctx = {}
        if metrics_list:
            m = metrics_list[0]
            metrics_ctx = {
                "pe_ratio": getattr(m, "price_to_earnings_ratio", None),
                "revenue_growth_yoy": getattr(m, "revenue_growth", None),
                "operating_margin": getattr(m, "operating_margin", None),
                "debt_to_equity": getattr(m, "debt_to_equity", None),
                "return_on_equity": getattr(m, "return_on_equity", None),
                "market_cap": getattr(m, "market_cap", None),
            }

        # News headlines
        headlines = [
            getattr(a, "title", "") for a in (news_list or [])[:12] if getattr(a, "title", "")
        ]

        progress.update_status(agent_id, ticker, "Analyzing market context")

        template = ChatPromptTemplate.from_messages([
            ("system",
             "You are a seasoned macro-market strategist. Given live data for a stock, assess the broader "
             "market context: macro regime (rates/inflation/growth cycle), sector momentum, institutional flow "
             "patterns, and near-term catalysts. Give a clear, opinionated directional view. "
             "reasoning = exactly 3 sentences. sector_outlook = 1 sentence. macro_theme = 1 sentence."),
            ("human",
             "Ticker: {ticker}\n\n"
             "Price Performance:\n{price_ctx}\n\n"
             "Financial Snapshot:\n{metrics_ctx}\n\n"
             "Recent Headlines:\n{headlines}\n\n"
             "Respond with: signal (bullish/bearish/neutral), confidence (0-100), reasoning, "
             "sector_outlook, macro_theme."),
        ])

        prompt = template.invoke({
            "ticker": ticker,
            "price_ctx": json.dumps(price_ctx, indent=2),
            "metrics_ctx": json.dumps({k: v for k, v in metrics_ctx.items() if v is not None}, indent=2),
            "headlines": "\n".join(f"• {h}" for h in headlines) if headlines else "No recent news available",
        })

        out = call_llm(prompt=prompt, pydantic_model=MarketContextOutput, agent_name=agent_id, state=state)

        market_context[ticker] = {
            "signal": (out.signal.lower() if out else "neutral"),
            "confidence": (out.confidence if out else 50),
            "reasoning": (out.reasoning if out else "Market context unavailable."),
            "sector_outlook": (out.sector_outlook if out else ""),
            "macro_theme": (out.macro_theme if out else ""),
        }
        progress.update_status(agent_id, ticker, "Done")

    message = HumanMessage(content=json.dumps(market_context), name=agent_id)
    state["data"]["analyst_signals"][agent_id] = market_context
    progress.update_status(agent_id, None, "Done")
    return {"messages": state["messages"] + [message], "data": data}
