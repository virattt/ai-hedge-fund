"""
SentimentAnalyzer – LLM-powered news sentiment scoring via OpenRouter.

This module bridges the gap left by FMP's news endpoint, which does not
provide sentiment scores.  It takes CompanyNews objects (title + metadata)
and returns a normalised sentiment label ("positive" / "negative" / "neutral")
together with a confidence score (0-100).

The module is designed to be called from:
  • news_sentiment_agent  – classifies articles without pre-existing sentiment
  • sentiment_analyst_agent – enriches news before aggregation
  • michael_burry agent   – contrarian sentiment analysis
  • charlie_munger agent  – qualitative news review

Usage
-----
    from src.tools.sentiment_analyzer import enrich_news_sentiment

    # Mutates each CompanyNews.sentiment in-place and returns confidence map
    confidences = enrich_news_sentiment(news_list, ticker="AAPL", max_articles=5)
"""

from __future__ import annotations

import json
import os
import time
from typing import TYPE_CHECKING

import requests

if TYPE_CHECKING:
    from src.data.models import CompanyNews


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Preferred models in order of priority
_OPENROUTER_MODELS = [
    "google/gemini-2.0-flash-001",
    "anthropic/claude-3.5-sonnet",
]

_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"


def _get_openrouter_key() -> str:
    """Resolve the OpenRouter API key from the environment."""
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        print("[SentimentAnalyzer] WARNING: OPENROUTER_API_KEY not set.")
    return key


# ---------------------------------------------------------------------------
# Core LLM call
# ---------------------------------------------------------------------------

def _call_openrouter(
    prompt: str,
    model: str | None = None,
    max_retries: int = 2,
) -> dict | None:
    """
    Call OpenRouter chat-completions and return parsed JSON.

    Returns a dict like {"sentiment": "positive", "confidence": 82}
    or None on failure.
    """
    api_key = _get_openrouter_key()
    if not api_key:
        return None

    model = model or _OPENROUTER_MODELS[0]

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/ShutongSun/ai-hedge-fund",
        "X-Title": "AI Hedge Fund – Sentiment Analyzer",
    }

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a financial sentiment classifier. "
                    "Given a news headline about a stock, determine the sentiment "
                    "as 'positive', 'negative', or 'neutral' for the stock only. "
                    "Also provide a confidence score from 0 to 100. "
                    "Respond ONLY with valid JSON: "
                    '{"sentiment": "<positive|negative|neutral>", "confidence": <0-100>}'
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.0,
        "max_tokens": 80,
    }

    for attempt in range(max_retries + 1):
        try:
            resp = requests.post(
                _OPENROUTER_BASE_URL,
                headers=headers,
                json=payload,
                timeout=30,
            )

            if resp.status_code == 429 and attempt < max_retries:
                time.sleep(2 + attempt * 2)
                continue

            if resp.status_code != 200:
                print(f"[SentimentAnalyzer] OpenRouter error {resp.status_code}: {resp.text[:200]}")
                # Try fallback model on first failure
                if attempt == 0 and model == _OPENROUTER_MODELS[0] and len(_OPENROUTER_MODELS) > 1:
                    model = _OPENROUTER_MODELS[1]
                    payload["model"] = model
                    continue
                return None

            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

            # Parse JSON from response – handle markdown-wrapped JSON
            content = content.strip()
            if content.startswith("```"):
                # Strip markdown code fences
                lines = content.split("\n")
                content = "\n".join(
                    l for l in lines if not l.strip().startswith("```")
                ).strip()

            result = json.loads(content)

            # Validate
            sentiment = result.get("sentiment", "neutral").lower()
            if sentiment not in ("positive", "negative", "neutral"):
                sentiment = "neutral"
            confidence = int(result.get("confidence", 50))
            confidence = max(0, min(100, confidence))

            return {"sentiment": sentiment, "confidence": confidence}

        except json.JSONDecodeError:
            # Try to extract sentiment from free-text response
            if content:
                lower = content.lower()
                if "positive" in lower:
                    return {"sentiment": "positive", "confidence": 50}
                elif "negative" in lower:
                    return {"sentiment": "negative", "confidence": 50}
            return {"sentiment": "neutral", "confidence": 30}
        except Exception as e:
            print(f"[SentimentAnalyzer] Error: {e}")
            if attempt < max_retries:
                time.sleep(1)
                continue
            return None

    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_sentiment(title: str, ticker: str) -> dict:
    """
    Analyze the sentiment of a single news headline.

    Parameters
    ----------
    title : str
        The news headline text.
    ticker : str
        The stock ticker symbol for context.

    Returns
    -------
    dict
        {"sentiment": "positive"|"negative"|"neutral", "confidence": 0-100}
    """
    prompt = (
        f"The stock is {ticker}. "
        f"Analyze the sentiment of this headline for {ticker}:\n\n"
        f'"{title}"'
    )
    result = _call_openrouter(prompt)
    if result is None:
        return {"sentiment": "neutral", "confidence": 0}
    return result


def enrich_news_sentiment(
    news_items: list["CompanyNews"],
    ticker: str,
    max_articles: int = 5,
) -> dict[int, int]:
    """
    Enrich a list of CompanyNews objects with sentiment labels in-place.

    Only articles whose ``sentiment`` field is ``None`` are analyzed.
    At most ``max_articles`` will be sent to the LLM to control costs.

    Parameters
    ----------
    news_items : list[CompanyNews]
        Mutable list – each item's ``.sentiment`` will be set.
    ticker : str
        Stock ticker for context.
    max_articles : int
        Maximum number of articles to classify via LLM.

    Returns
    -------
    dict[int, int]
        Mapping of ``id(news_item)`` → confidence score (0-100) for each
        article that was classified by the LLM.
    """
    confidences: dict[int, int] = {}
    articles_to_analyze = [n for n in news_items if n.sentiment is None][:max_articles]

    for news in articles_to_analyze:
        result = analyze_sentiment(news.title, ticker)
        news.sentiment = result["sentiment"]
        confidences[id(news)] = result["confidence"]

    return confidences
