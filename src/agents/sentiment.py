import json
from typing import Dict, Any, List
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from langchain_core.messages import HumanMessage
from langchain_openai.chat_models import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from agents.state import AgentState, show_agent_reasoning
from tools.api import get_news_data

def analyze_article_sentiment(article: Dict[str, Any], llm: ChatOpenAI) -> Dict[str, Any]:
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
        "title": article.get("title", ""),
        "description": article.get("description", ""),
        "content": article.get("content", "")
    })

    try:
        result = llm.invoke(prompt)
        return json.loads(result.content)
    except (json.JSONDecodeError, Exception) as e:
        return {
            "sentiment": "neutral",
            "confidence": 0.0,
            "key_points": []
        }

def process_insider_trades(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Process insider trading sentiment."""
    insider_signals = []
    for trade in trades:
        transaction_shares = trade["transaction_shares"]
        if not transaction_shares:
            continue
        if transaction_shares < 0:
            insider_signals.append("bearish")
        else:
            insider_signals.append("bullish")

    bullish_insider = insider_signals.count("bullish")
    bearish_insider = insider_signals.count("bearish")
    total_insider = len(insider_signals)
    
    if total_insider > 0:
        sentiment = "bullish" if bullish_insider > bearish_insider else "bearish" if bearish_insider > bullish_insider else "neutral"
        confidence = max(bullish_insider, bearish_insider) / total_insider
    else:
        sentiment = "neutral"
        confidence = 0.0

    return {
        "signal": sentiment,
        "confidence": confidence,
        "bullish_trades": bullish_insider,
        "bearish_trades": bearish_insider
    }

def process_news_sentiment(news_data: List[Dict[str, Any]], llm: ChatOpenAI) -> Dict[str, Any]:
    """Process news sentiment from articles."""
    # Analyze top 5 most relevant articles
    article_analyses = []
    for article in news_data[:5]:
        analysis = analyze_article_sentiment(article, llm)
        if analysis["confidence"] > 0:
            article_analyses.append({
                "title": article.get("title", ""),
                "source": article.get("source", {}).get("name", ""),
                "published": article.get("publishedAt", ""),
                "analysis": analysis
            })

    if not article_analyses:
        return {
            "signal": "neutral",
            "confidence": 0.0,
            "articles_analyzed": 0,
            "key_points": []
        }

    # Calculate sentiment
    sentiment_scores = []
    total_confidence = 0
    all_key_points = []
    
    for analysis in article_analyses:
        sentiment_value = {
            "bullish": 1,
            "bearish": -1,
            "neutral": 0
        }[analysis["analysis"]["sentiment"]]
        
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

def sentiment_agent(state: AgentState):
    """Analyzes market sentiment from news and insider trading."""
    show_reasoning = state["metadata"]["show_reasoning"]
    data = state["data"]
    llm = ChatOpenAI(model="gpt-4o")
    
    # Fetch news data with relevancy sorting for the past week
    news_future = None
    with ThreadPoolExecutor() as executor:
        # Start news API call
        news_future = executor.submit(
            get_news_data,
            ticker=data["ticker"],
            start_date=data["start_date"],
            end_date=data["end_date"],
            sort_by="relevancy"
        )
        
        # Process insider trades while waiting for news
        insider_result = process_insider_trades(data["insider_trades"])
        
        # Get news results
        news_data = news_future.result()
        news_result = process_news_sentiment(news_data, llm)

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

    message_content = {
        "signal": overall_sentiment,
        "confidence": f"{round(overall_confidence * 100)}%",
        "reasoning": {
            "insider_sentiment": {
                "signal": insider_result["signal"],
                "confidence": f"{round(insider_result['confidence'] * 100)}%",
                "bullish_trades": insider_result["bullish_trades"],
                "bearish_trades": insider_result["bearish_trades"]
            },
            "news_sentiment": {
                "signal": news_result["signal"],
                "confidence": f"{round(news_result['confidence'] * 100)}%",
                "articles_analyzed": news_result["articles_analyzed"],
                "key_points": news_result["key_points"]
            }
        }
    }

    if show_reasoning:
        show_agent_reasoning(message_content, "Sentiment Analysis Agent")

    message = HumanMessage(
        content=json.dumps(message_content),
        name="sentiment_agent",
    )

    return {
        "messages": [message],
        "data": data,
    }