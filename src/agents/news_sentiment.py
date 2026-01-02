

from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field
from src.data.models import CompanyNews
import pandas as pd
import numpy as np
import json

from src.graph.state import AgentState, show_agent_reasoning
from src.tools.api import get_company_news
from src.utils.api_key import get_api_key_from_state
from src.utils.llm import call_llm
from src.utils.progress import progress
from typing_extensions import Literal


class Sentiment(BaseModel):
    """Represents the sentiment of a news article."""

    sentiment: Literal["positive", "negative", "neutral"]
    confidence: int = Field(description="Confidence 0-100")


def news_sentiment_agent(state: AgentState, agent_id: str = "news_sentiment_agent"):
    """
    Analyzes news sentiment for a list of tickers and generates trading signals.

    This agent fetches company news, uses an LLM to classify the sentiment of articles
    with missing sentiment data, and then aggregates the sentiments to produce an
    overall signal (bullish, bearish, or neutral) and a confidence score for each ticker.

    Args:
        state: The current state of the agent graph.
        agent_id: The ID of the agent.

    Returns:
        A dictionary containing the updated state with the agent's analysis.
    """
    data = state.get("data", {})
    end_date = data.get("end_date")
    tickers = data.get("tickers")
    api_key = get_api_key_from_state(state, "FINANCIAL_DATASETS_API_KEY")
    sentiment_analysis = {}

    for ticker in tickers:
        progress.update_status(agent_id, ticker, "Fetching company news")
        company_news = get_company_news(
            ticker=ticker,
            end_date=end_date,
            limit=100,
            api_key=api_key,
        )

        news_signals = []
        sentiment_confidences = {}  # Store confidence scores for each article
        
        if company_news:
            # Check the 10 most recent articles
            recent_articles = company_news[:10]
            articles_without_sentiment = [news for news in recent_articles if news.sentiment is None]
            
            # Analyze only the 5 most recent articles without sentiment to reduce LLM calls
            sentiments_classified_by_llm = 0
            if articles_without_sentiment:
              # We only take the first 5 articles, but this is configurable
              num_articles_to_analyze = 5
              articles_to_analyze = articles_without_sentiment[:num_articles_to_analyze]
              progress.update_status(agent_id, ticker, f"Analyzing sentiment for {len(articles_to_analyze)} articles")
              
              for idx, news in enumerate(articles_to_analyze):
                # We analyze based on title, but can also pass in the entire article text,
                # but this is more expensive and requires extracting the text from the article.
                # Note: this is an opportunity for improvement!
                progress.update_status(agent_id, ticker, f"Analyzing sentiment for article {idx + 1} of {len(articles_to_analyze)}")
                prompt = (
                    f"Please analyze the sentiment of the following news headline "
                    f"with the following context: "
                    f"The stock is {ticker}. "
                    f"Determine if sentiment is 'positive', 'negative', or 'neutral' for the stock {ticker} only. "
                    f"Also provide a confidence score for your prediction from 0 to 100. "
                    f"Respond in JSON format.\n\n"
                    f"Headline: {news.title}"
                )
                response = call_llm(prompt, Sentiment, agent_name=agent_id, state=state)
                if response:
                    news.sentiment = response.sentiment.lower()
                    sentiment_confidences[id(news)] = response.confidence
                else:
                    news.sentiment = "neutral"
                    sentiment_confidences[id(news)] = 0
                sentiments_classified_by_llm += 1

            # Aggregate sentiment across all articles
            sentiment = pd.Series([n.sentiment for n in company_news]).dropna()
            news_signals = np.where(sentiment == "negative","bearish", np.where(sentiment == "positive", "bullish", "neutral")).tolist()

        progress.update_status(agent_id, ticker, "Aggregating signals")

        # Calculate the sentiment signals
        bullish_signals = news_signals.count("bullish")
        bearish_signals = news_signals.count("bearish")
        neutral_signals = news_signals.count("neutral")

        if bullish_signals > bearish_signals:
            overall_signal = "bullish"
        elif bearish_signals > bullish_signals:
            overall_signal = "bearish"
        else:
            overall_signal = "neutral"

        total_signals = len(news_signals)
        confidence = _calculate_confidence_score(
            sentiment_confidences=sentiment_confidences,
            company_news=company_news,
            overall_signal=overall_signal,
            bullish_signals=bullish_signals,
            bearish_signals=bearish_signals,
            total_signals=total_signals
        )

        # Create reasoning for the news sentiment
        reasoning = {
            "news_sentiment": {
                "signal": overall_signal,
                "confidence": confidence,
                "metrics": {
                    "total_articles": total_signals,
                    "bullish_articles": bullish_signals,
                    "bearish_articles": bearish_signals,
                    "neutral_articles": neutral_signals,
                    "articles_classified_by_llm": sentiments_classified_by_llm,
                },
            }
        }

        # Create the sentiment analysis
        sentiment_analysis[ticker] = {
            "signal": overall_signal,
            "confidence": confidence,
            "reasoning": reasoning,
        }

        progress.update_status(agent_id, ticker, "Done", analysis=json.dumps(reasoning, indent=4))

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


def _calculate_confidence_score(
    sentiment_confidences: dict,
    company_news: list,
    overall_signal: str,
    bullish_signals: int,
    bearish_signals: int,
    total_signals: int
) -> float:
    """
    Calculate confidence score for a sentiment signal.
    
    Uses a weighted approach combining LLM confidence scores (70%) with 
    signal proportion (30%) when LLM classifications are available.
    
    Args:
        sentiment_confidences: Dictionary mapping news article IDs to confidence scores.
        company_news: List of CompanyNews objects.
        overall_signal: The overall sentiment signal ("bullish", "bearish", or "neutral").
        bullish_signals: Count of bullish signals.
        bearish_signals: Count of bearish signals.
        total_signals: Total number of signals.
        
    Returns:
        Confidence score as a float between 0 and 100.
    """
    if total_signals == 0:
        return 0.0
    
    # Calculate weighted confidence using LLM confidence scores when available
    if sentiment_confidences:
        # Get articles that match the overall signal
        matching_articles = [
            news for news in company_news 
            if news.sentiment and (
                (overall_signal == "bullish" and news.sentiment == "positive") or
                (overall_signal == "bearish" and news.sentiment == "negative") or
                (overall_signal == "neutral" and news.sentiment == "neutral")
            )
        ]
        
        # Calculate average confidence from LLM-classified articles that match the signal
        llm_confidences = [
            sentiment_confidences[id(news)] 
            for news in matching_articles 
            if id(news) in sentiment_confidences
        ]
        
        if llm_confidences:
            # Weight: 70% from LLM confidence scores, 30% from signal proportion
            avg_llm_confidence = sum(llm_confidences) / len(llm_confidences)
            signal_proportion = (max(bullish_signals, bearish_signals) / total_signals) * 100
            return round(0.7 * avg_llm_confidence + 0.3 * signal_proportion, 2)
    
    # Fallback to proportion-based confidence
    return round((max(bullish_signals, bearish_signals) / total_signals) * 100, 2)
