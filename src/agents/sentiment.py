import json
from typing import Dict, Any, List
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
import numpy as np
from langchain_core.messages import HumanMessage
from langchain_openai.chat_models import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from graph.state import AgentState, show_agent_reasoning
from utils.progress import progress
from tools.api import get_news_data, get_insider_trades
from data.models import NewsArticle

def sentiment_agent(state: AgentState):
    """Analyzes market sentiment and generates trading signals for multiple tickers."""
    data = state.get("data", {})
    end_date = data.get("end_date")
    tickers = data.get("tickers")
    llm = ChatOpenAI(model="gpt-4o")

    sentiment_analysis = {}

    for ticker in tickers:
        sentiment_analysis[ticker] = _analyze_ticker_sentiment(ticker, end_date, llm)
        progress.update_status("sentiment_agent", ticker, "Done")

    message = HumanMessage(
        content=json.dumps(sentiment_analysis),
        name="sentiment_agent",
    )

    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(sentiment_analysis, "Sentiment Analysis Agent")

    state["data"]["analyst_signals"]["sentiment_agent"] = sentiment_analysis

    return {
        "messages": [message],
        "data": data,
    }

def _analyze_ticker_sentiment(ticker: str, end_date: str, llm: ChatOpenAI) -> Dict[str, Any]:
    """Analyze sentiment for a single ticker."""
    progress.update_status("sentiment_agent", ticker, "Fetching insider trades")
    insider_trades = get_insider_trades(
        ticker=ticker,
        end_date=end_date,
        limit=1000,
    )

    if not insider_trades:
        progress.update_status("sentiment_agent", ticker, "Failed: No insider trades found")
        return {
            "signal": "neutral",
            "confidence": 0,
            "reasoning": "No insider trades found"
        }

    progress.update_status("sentiment_agent", ticker, "Analyzing sentiment")
    
    with ThreadPoolExecutor() as executor:
        # Start news API call
        news_future = executor.submit(
            get_news_data,
            ticker=ticker,
            start_date=(datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'),
            end_date=end_date,
            sort_by="relevancy"
        )
        
        # Process insider trades while waiting for news
        insider_result = _process_insider_trades(insider_trades)
        
        # Get news results
        news_data = news_future.result()
        news_result = _process_news_sentiment(news_data, llm)

    # Combine sentiments (60% insider, 40% news)
    weighted_insider = insider_result["confidence"] * 0.6
    weighted_news = news_result["confidence"] * 0.4

    if news_result["signal"] == insider_result["signal"]:
        overall_sentiment = news_result["signal"]
        overall_confidence = weighted_insider + weighted_news
    else:
        if weighted_insider > weighted_news:
            overall_sentiment = insider_result["signal"]
            overall_confidence = weighted_insider
        else:
            overall_sentiment = news_result["signal"]
            overall_confidence = weighted_news

    return {
        "signal": overall_sentiment,
        "confidence": round(overall_confidence * 100, 2),
        "reasoning": {
            "insider_sentiment": {
                "signal": insider_result["signal"],
                "confidence": round(insider_result["confidence"] * 100, 2),
                "bullish_trades": insider_result["bullish_trades"],
                "bearish_trades": insider_result["bearish_trades"]
            },
            "news_sentiment": {
                "signal": news_result["signal"],
                "confidence": round(news_result["confidence"] * 100, 2),
                "articles_analyzed": news_result["articles_analyzed"],
                "key_points": news_result["key_points"]
            }
        }
    }

def _analyze_article_sentiment(article: NewsArticle, llm: ChatOpenAI) -> Dict[str, Any]:
    """Analyze sentiment of a single article using GPT."""
    template = ChatPromptTemplate.from_messages([
        (
            "system",
            """You are a financial sentiment analyzer. Analyze the following news article about a company.
            Consider only factors that directly impact stock value:
            1. Revenue/profit implications
            2. Market competition impact
            3. Regulatory/legal effects
            4. Innovation/product developments
            
            Return ONLY a JSON object with exactly these fields:
            {{
                "sentiment": "bullish" | "bearish" | "neutral",
                "confidence": <float between 0 and 1>,
                "key_points": [<max 2 most important points>]
            }}
            
            Be concise and focus only on stock price impact."""
        ),
        (
            "human",
            "Title: {title}\nDescription: {description}"
        ),
    ])

    prompt = template.invoke({
        "title": article.title,
        "description": article.description or ""
    })

    try:
        result = llm.invoke(prompt)
        return json.loads(result.content)
    except (json.JSONDecodeError, Exception):
        return {
            "sentiment": "neutral",
            "confidence": 0.0,
            "key_points": []
        }

def _process_insider_trades(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Process insider trading sentiment using pandas."""
    transaction_shares = pd.Series([t.transaction_shares for t in trades]).dropna()
    bearish_condition = transaction_shares < 0
    signals = np.where(bearish_condition, "bearish", "bullish").tolist()
    
    bullish_signals = signals.count("bullish")
    bearish_signals = signals.count("bearish")
    total_signals = len(signals)
    
    if total_signals > 0:
        sentiment = "bullish" if bullish_signals > bearish_signals else "bearish" if bearish_signals > bullish_signals else "neutral"
        confidence = max(bullish_signals, bearish_signals) / total_signals
    else:
        sentiment = "neutral"
        confidence = 0.0

    return {
        "signal": sentiment,
        "confidence": confidence,
        "bullish_trades": bullish_signals,
        "bearish_trades": bearish_signals
    }

def _process_news_sentiment(news_data: List[NewsArticle], llm: ChatOpenAI) -> Dict[str, Any]:
    """Process news sentiment from articles."""
    SENTIMENT_VALUES = {
        "bullish": 1,
        "bearish": -1,
        "neutral": 0
    }
    
    article_analyses = []
    for article in news_data[:5]:
        analysis = _analyze_article_sentiment(article, llm)
        if analysis["confidence"] > 0:
            article_analyses.append({
                "title": article.title,
                "source": article.source.name, 
                "published": article.publishedAt,
                "analysis": analysis
            })

    if not article_analyses:
        return {
            "signal": "neutral",
            "confidence": 0.0,
            "articles_analyzed": 0,
            "key_points": []
        }

    sentiment_scores = []
    total_confidence = 0
    all_key_points = []
    
    for analysis in article_analyses:
        sentiment_value = SENTIMENT_VALUES[analysis["analysis"]["sentiment"]]
        
        confidence = analysis["analysis"]["confidence"]
        sentiment_scores.append(sentiment_value * confidence)
        total_confidence += confidence
        all_key_points.extend(analysis["analysis"]["key_points"])

    avg_sentiment = sum(sentiment_scores) / len(sentiment_scores)
    confidence = total_confidence / len(article_analyses)
    
    sentiment = (
        "bullish" if avg_sentiment > 0.2
        else "bearish" if avg_sentiment < -0.2
        else "neutral"
    )

    return {
        "signal": sentiment,
        "confidence": confidence,
        "articles_analyzed": len(article_analyses),
        "key_points": list(set(all_key_points))
    }