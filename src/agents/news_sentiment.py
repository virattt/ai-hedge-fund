

from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field
from src.data.models import CompanyNews, SocialMediaPost
import pandas as pd
import numpy as np
import json

from src.graph.state import AgentState, show_agent_reasoning
from src.tools.api import get_company_news, get_reddit_posts, get_twitter_posts
from src.utils.api_key import get_api_key_from_state
from src.utils.llm import call_llm
from src.utils.progress import progress
from typing_extensions import Literal


class Sentiment(BaseModel):
    """Represents the sentiment of a news article or social media post."""

    sentiment: Literal["positive", "negative", "neutral"]
    confidence: int = Field(description="Confidence 0-100")


def news_sentiment_agent(state: AgentState, agent_id: str = "news_sentiment_agent"):
    """
    Analyzes sentiment for a list of tickers across news, Reddit, and Twitter
    and generates trading signals.

    For each ticker the agent fetches:
      - Company news from the Financial Datasets API
      - Recent Reddit posts via the public Reddit JSON API
      - Recent tweets via the Twitter API v2 (when TWITTER_BEARER_TOKEN is set)

    Items without a pre-classified sentiment are scored by an LLM. Signals from
    all sources are aggregated to produce an overall bullish/bearish/neutral
    signal and confidence score per ticker.
    """
    data = state.get("data", {})
    end_date = data.get("end_date")
    tickers = data.get("tickers")
    api_key = get_api_key_from_state(state, "FINANCIAL_DATASETS_API_KEY")
    reddit_user_agent = get_api_key_from_state(state, "REDDIT_USER_AGENT")
    twitter_bearer_token = get_api_key_from_state(state, "TWITTER_BEARER_TOKEN")
    sentiment_analysis = {}

    for ticker in tickers:
        # --- 1. Fetch company news ---
        progress.update_status(agent_id, ticker, "Fetching company news")
        company_news = get_company_news(
            ticker=ticker,
            end_date=end_date,
            limit=100,
            api_key=api_key,
        ) or []

        # --- 2. Fetch Reddit posts ---
        progress.update_status(agent_id, ticker, "Fetching Reddit posts")
        reddit_posts = get_reddit_posts(
            ticker=ticker,
            end_date=end_date,
            limit=25,
            user_agent=reddit_user_agent,
        ) or []

        # --- 3. Fetch Twitter posts ---
        progress.update_status(agent_id, ticker, "Fetching Twitter posts")
        twitter_posts = get_twitter_posts(
            ticker=ticker,
            end_date=end_date,
            limit=25,
            bearer_token=twitter_bearer_token,
        ) or []

        sentiment_confidences: dict[int, int] = {}
        llm_classified_counts = {"news": 0, "reddit": 0, "twitter": 0}

        # --- 4. Classify the most recent items per source via LLM ---
        if company_news:
            recent_news = company_news[:10]
            news_to_classify = [n for n in recent_news if n.sentiment is None][:5]
            if news_to_classify:
                progress.update_status(
                    agent_id,
                    ticker,
                    f"Analyzing sentiment for {len(news_to_classify)} news articles",
                )
                _classify_items(
                    items=news_to_classify,
                    ticker=ticker,
                    source_label="news article",
                    text_fn=lambda n: n.title,
                    state=state,
                    agent_id=agent_id,
                    sentiment_confidences=sentiment_confidences,
                )
                llm_classified_counts["news"] = len(news_to_classify)

        if reddit_posts:
            reddit_to_classify = reddit_posts[:5]
            progress.update_status(
                agent_id,
                ticker,
                f"Analyzing sentiment for {len(reddit_to_classify)} Reddit posts",
            )
            _classify_items(
                items=reddit_to_classify,
                ticker=ticker,
                source_label="Reddit post",
                text_fn=lambda p: p.text or p.title or "",
                state=state,
                agent_id=agent_id,
                sentiment_confidences=sentiment_confidences,
            )
            llm_classified_counts["reddit"] = len(reddit_to_classify)

        if twitter_posts:
            twitter_to_classify = twitter_posts[:5]
            progress.update_status(
                agent_id,
                ticker,
                f"Analyzing sentiment for {len(twitter_to_classify)} tweets",
            )
            _classify_items(
                items=twitter_to_classify,
                ticker=ticker,
                source_label="tweet",
                text_fn=lambda p: p.text,
                state=state,
                agent_id=agent_id,
                sentiment_confidences=sentiment_confidences,
            )
            llm_classified_counts["twitter"] = len(twitter_to_classify)

        # --- 5. Aggregate signals across all sources ---
        progress.update_status(agent_id, ticker, "Aggregating signals")

        all_items = list(company_news) + list(reddit_posts) + list(twitter_posts)
        sentiment_series = pd.Series(
            [item.sentiment for item in all_items]
        ).dropna()
        all_signals = np.where(
            sentiment_series == "negative",
            "bearish",
            np.where(sentiment_series == "positive", "bullish", "neutral"),
        ).tolist()

        bullish_signals = all_signals.count("bullish")
        bearish_signals = all_signals.count("bearish")
        neutral_signals = all_signals.count("neutral")
        total_signals = len(all_signals)

        if bullish_signals > bearish_signals:
            overall_signal = "bullish"
        elif bearish_signals > bullish_signals:
            overall_signal = "bearish"
        else:
            overall_signal = "neutral"

        confidence = _calculate_confidence_score(
            sentiment_confidences=sentiment_confidences,
            items=all_items,
            overall_signal=overall_signal,
            bullish_signals=bullish_signals,
            bearish_signals=bearish_signals,
            total_signals=total_signals,
        )

        # Per-source breakdown for the reasoning report
        def _source_metrics(items: list) -> dict:
            sigs = [
                "bullish" if i.sentiment == "positive"
                else "bearish" if i.sentiment == "negative"
                else "neutral"
                for i in items
                if i.sentiment is not None
            ]
            return {
                "total": len(items),
                "bullish": sigs.count("bullish"),
                "bearish": sigs.count("bearish"),
                "neutral": sigs.count("neutral"),
            }

        reasoning = {
            "news_sentiment": {
                "signal": overall_signal,
                "confidence": confidence,
                "metrics": {
                    "total_items": total_signals,
                    "bullish_items": bullish_signals,
                    "bearish_items": bearish_signals,
                    "neutral_items": neutral_signals,
                    "items_classified_by_llm": sum(llm_classified_counts.values()),
                    "by_source": {
                        "news": _source_metrics(company_news),
                        "reddit": _source_metrics(reddit_posts),
                        "twitter": _source_metrics(twitter_posts),
                    },
                    "llm_classified_by_source": llm_classified_counts,
                },
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
        show_agent_reasoning(sentiment_analysis, "News Sentiment Analysis Agent")

    if "analyst_signals" not in state["data"]:
        state["data"]["analyst_signals"] = {}
    state["data"]["analyst_signals"][agent_id] = sentiment_analysis

    progress.update_status(agent_id, None, "Done")

    return {
        "messages": [message],
        "data": state["data"],
    }


def _classify_items(
    items: list,
    ticker: str,
    source_label: str,
    text_fn,
    state: AgentState,
    agent_id: str,
    sentiment_confidences: dict,
) -> None:
    """Classify a list of items in-place using the LLM, recording confidences."""
    for idx, item in enumerate(items):
        progress.update_status(
            agent_id,
            ticker,
            f"Analyzing sentiment for {source_label} {idx + 1} of {len(items)}",
        )
        text = (text_fn(item) or "").strip()
        if not text:
            item.sentiment = "neutral"
            sentiment_confidences[id(item)] = 0
            continue

        prompt = (
            f"Please analyze the sentiment of the following {source_label} "
            f"with the following context: "
            f"The stock is {ticker}. "
            f"Determine if sentiment is 'positive', 'negative', or 'neutral' "
            f"for the stock {ticker} only. "
            f"Also provide a confidence score for your prediction from 0 to 100. "
            f"Respond in JSON format.\n\n"
            f"Content: {text}"
        )
        response = call_llm(prompt, Sentiment, agent_name=agent_id, state=state)
        if response:
            item.sentiment = response.sentiment.lower()
            sentiment_confidences[id(item)] = response.confidence
        else:
            item.sentiment = "neutral"
            sentiment_confidences[id(item)] = 0


def _calculate_confidence_score(
    sentiment_confidences: dict,
    items: list,
    overall_signal: str,
    bullish_signals: int,
    bearish_signals: int,
    total_signals: int,
) -> float:
    """
    Calculate confidence score for a sentiment signal.

    Uses a weighted approach combining LLM confidence scores (70%) with
    signal proportion (30%) when LLM classifications are available.
    """
    if total_signals == 0:
        return 0.0

    if sentiment_confidences:
        matching_items = [
            item for item in items
            if item.sentiment and (
                (overall_signal == "bullish" and item.sentiment == "positive") or
                (overall_signal == "bearish" and item.sentiment == "negative") or
                (overall_signal == "neutral" and item.sentiment == "neutral")
            )
        ]

        llm_confidences = [
            sentiment_confidences[id(item)]
            for item in matching_items
            if id(item) in sentiment_confidences
        ]

        if llm_confidences:
            avg_llm_confidence = sum(llm_confidences) / len(llm_confidences)
            signal_proportion = (max(bullish_signals, bearish_signals) / total_signals) * 100
            return round(0.7 * avg_llm_confidence + 0.3 * signal_proportion, 2)

    return round((max(bullish_signals, bearish_signals) / total_signals) * 100, 2)
