from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field
import json
from typing_extensions import Literal

from src.graph.state import AgentState, show_agent_reasoning
from src.tools.exa_search import search_exa
from src.utils.api_key import get_api_key_from_state
from src.utils.llm import call_llm
from src.utils.progress import progress


class WebSentiment(BaseModel):
    """Represents the aggregated sentiment from web search results."""

    sentiment: Literal["positive", "negative", "neutral"]
    confidence: int = Field(description="Confidence 0-100")
    reasoning: str = Field(description="Brief explanation of the sentiment assessment")


def exa_news_agent(state: AgentState, agent_id: str = "exa_news_agent"):
    """Analyzes web sentiment for a list of tickers using Exa AI-powered search.

    This agent uses Exa to search for recent news, analysis, and commentary
    about each ticker. It retrieves article highlights and uses an LLM to
    assess overall market sentiment, producing a trading signal.

    Args:
        state: The current state of the agent graph.
        agent_id: The ID of the agent.

    Returns:
        A dictionary containing the updated state with the agent's analysis.
    """
    data = state.get("data", {})
    end_date = data.get("end_date")
    tickers = data.get("tickers")
    exa_api_key = get_api_key_from_state(state, "EXA_API_KEY")
    sentiment_analysis = {}

    for ticker in tickers:
        progress.update_status(agent_id, ticker, "Searching web for news and analysis")

        # Search for recent news about this ticker
        results = search_exa(
            query=f"{ticker} stock latest news analysis",
            num_results=10,
            search_type="auto",
            category="news",
            end_published_date=f"{end_date}T23:59:59.000Z" if end_date else None,
            api_key=exa_api_key,
        )

        if not results:
            # Fallback: try broader search without category filter
            progress.update_status(agent_id, ticker, "Retrying with broader search")
            results = search_exa(
                query=f"{ticker} stock market sentiment outlook",
                num_results=10,
                search_type="auto",
                end_published_date=f"{end_date}T23:59:59.000Z" if end_date else None,
                api_key=exa_api_key,
            )

        if not results:
            sentiment_analysis[ticker] = {
                "signal": "neutral",
                "confidence": 0,
                "reasoning": {
                    "web_sentiment": {
                        "signal": "neutral",
                        "confidence": 0,
                        "metrics": {
                            "articles_found": 0,
                            "articles_analyzed": 0,
                        },
                        "details": "No web search results available.",
                    }
                },
            }
            progress.update_status(agent_id, ticker, "Done (no results)")
            continue

        progress.update_status(agent_id, ticker, f"Analyzing {len(results)} articles")

        # Build article summaries for the LLM
        article_summaries = []
        for i, result in enumerate(results[:10], 1):
            article = f"Article {i}: {result.title}"
            if result.published_date:
                article += f" (Published: {result.published_date})"
            if result.snippet:
                article += f"\nContent: {result.snippet[:1000]}"
            article_summaries.append(article)

        articles_text = "\n\n".join(article_summaries)

        # Use LLM to analyze sentiment from the articles
        prompt = (
            f"Analyze the following web articles about the stock {ticker} and determine "
            f"the overall market sentiment.\n\n"
            f"Consider:\n"
            f"- Are the articles generally positive, negative, or neutral about the stock?\n"
            f"- What is the prevailing market outlook?\n"
            f"- Are there any significant risks or catalysts mentioned?\n\n"
            f"Articles:\n{articles_text}\n\n"
            f"Provide your assessment as JSON with 'sentiment' (positive/negative/neutral), "
            f"'confidence' (0-100), and 'reasoning' (brief explanation)."
        )

        llm_result = call_llm(prompt, WebSentiment, agent_name=agent_id, state=state)

        if llm_result:
            sentiment_label = llm_result.sentiment.lower()
            confidence = llm_result.confidence
            llm_reasoning = llm_result.reasoning
        else:
            sentiment_label = "neutral"
            confidence = 0
            llm_reasoning = "LLM analysis failed, defaulting to neutral."

        # Map sentiment to trading signal
        if sentiment_label == "positive":
            overall_signal = "bullish"
        elif sentiment_label == "negative":
            overall_signal = "bearish"
        else:
            overall_signal = "neutral"

        reasoning = {
            "web_sentiment": {
                "signal": overall_signal,
                "confidence": confidence,
                "metrics": {
                    "articles_found": len(results),
                    "articles_analyzed": min(len(results), 10),
                },
                "details": llm_reasoning,
                "sources": [
                    {"title": r.title, "url": r.url, "date": r.published_date}
                    for r in results[:5]
                ],
            }
        }

        sentiment_analysis[ticker] = {
            "signal": overall_signal,
            "confidence": confidence,
            "reasoning": reasoning,
        }

        progress.update_status(
            agent_id, ticker, "Done", analysis=json.dumps(reasoning, indent=4)
        )

    message = HumanMessage(
        content=json.dumps(sentiment_analysis),
        name=agent_id,
    )

    if state.get("metadata", {}).get("show_reasoning"):
        show_agent_reasoning(sentiment_analysis, "Exa Web Search Analyst")

    if "analyst_signals" not in state["data"]:
        state["data"]["analyst_signals"] = {}
    state["data"]["analyst_signals"][agent_id] = sentiment_analysis

    progress.update_status(agent_id, None, "Done")

    return {
        "messages": [message],
        "data": state["data"],
    }
