

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
    """Rappresenta il sentiment di un articolo di news o di un post social."""

    sentiment: Literal["positive", "negative", "neutral"]
    confidence: int = Field(description="Confidenza da 0 a 100")


def news_sentiment_agent(state: AgentState, agent_id: str = "news_sentiment_agent"):
    """
    Analizza il sentiment per una lista di ticker su news, Reddit e Twitter
    e genera segnali di trading.

    Per ogni ticker l'agente recupera:
      - Le news societarie dall'API Financial Datasets
      - I post Reddit recenti tramite l'API JSON pubblica di Reddit
      - I tweet recenti tramite Twitter API v2 (quando TWITTER_BEARER_TOKEN è impostato)

    Gli elementi senza sentiment pre-classificato vengono valutati da un LLM.
    I segnali provenienti da tutte le fonti vengono aggregati per produrre un
    segnale complessivo bullish/bearish/neutral e un punteggio di confidenza
    per ciascun ticker.
    """
    data = state.get("data", {})
    end_date = data.get("end_date")
    tickers = data.get("tickers")
    api_key = get_api_key_from_state(state, "FINANCIAL_DATASETS_API_KEY")
    reddit_user_agent = get_api_key_from_state(state, "REDDIT_USER_AGENT")
    twitter_bearer_token = get_api_key_from_state(state, "TWITTER_BEARER_TOKEN")
    sentiment_analysis = {}

    for ticker in tickers:
        # --- 1. Recupera le news societarie ---
        progress.update_status(agent_id, ticker, "Recupero delle news societarie")
        company_news = get_company_news(
            ticker=ticker,
            end_date=end_date,
            limit=100,
            api_key=api_key,
        ) or []

        # --- 2. Recupera i post da Reddit ---
        progress.update_status(agent_id, ticker, "Recupero dei post da Reddit")
        reddit_posts = get_reddit_posts(
            ticker=ticker,
            end_date=end_date,
            limit=25,
            user_agent=reddit_user_agent,
        ) or []

        # --- 3. Recupera i post da Twitter ---
        progress.update_status(agent_id, ticker, "Recupero dei post da Twitter")
        twitter_posts = get_twitter_posts(
            ticker=ticker,
            end_date=end_date,
            limit=25,
            bearer_token=twitter_bearer_token,
        ) or []

        sentiment_confidences: dict[int, int] = {}
        llm_classified_counts = {"news": 0, "reddit": 0, "twitter": 0}

        # --- 4. Classifica con l'LLM gli elementi più recenti per ogni fonte ---
        if company_news:
            recent_news = company_news[:10]
            news_to_classify = [n for n in recent_news if n.sentiment is None][:5]
            if news_to_classify:
                progress.update_status(
                    agent_id,
                    ticker,
                    f"Analisi del sentiment per {len(news_to_classify)} articoli di news",
                )
                _classify_items(
                    items=news_to_classify,
                    ticker=ticker,
                    source_label="articolo di news",
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
                f"Analisi del sentiment per {len(reddit_to_classify)} post Reddit",
            )
            _classify_items(
                items=reddit_to_classify,
                ticker=ticker,
                source_label="post Reddit",
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
                f"Analisi del sentiment per {len(twitter_to_classify)} tweet",
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

        # --- 5. Aggrega i segnali da tutte le fonti ---
        progress.update_status(agent_id, ticker, "Aggregazione dei segnali")

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

        # Dettaglio per fonte da inserire nel report di reasoning
        def _source_metrics(items: list) -> dict:
            sigs = [
                "bullish" if i.sentiment == "positive"
                else "bearish" if i.sentiment == "negative"
                else "neutral"
                for i in items
                if i.sentiment is not None
            ]
            return {
                "totale": len(items),
                "bullish": sigs.count("bullish"),
                "bearish": sigs.count("bearish"),
                "neutral": sigs.count("neutral"),
            }

        reasoning = {
            "news_sentiment": {
                "segnale": overall_signal,
                "confidenza": confidence,
                "metriche": {
                    "elementi_totali": total_signals,
                    "elementi_bullish": bullish_signals,
                    "elementi_bearish": bearish_signals,
                    "elementi_neutral": neutral_signals,
                    "classificati_dall_llm": sum(llm_classified_counts.values()),
                    "per_fonte": {
                        "news": _source_metrics(company_news),
                        "reddit": _source_metrics(reddit_posts),
                        "twitter": _source_metrics(twitter_posts),
                    },
                    "classificati_dall_llm_per_fonte": llm_classified_counts,
                },
            }
        }

        sentiment_analysis[ticker] = {
            "signal": overall_signal,
            "confidence": confidence,
            "reasoning": reasoning,
        }

        progress.update_status(
            agent_id, ticker, "Completato", analysis=json.dumps(reasoning, indent=4)
        )

    message = HumanMessage(
        content=json.dumps(sentiment_analysis),
        name=agent_id,
    )

    if state.get("metadata", {}).get("show_reasoning"):
        show_agent_reasoning(sentiment_analysis, "Agente di Analisi del Sentiment delle News")

    if "analyst_signals" not in state["data"]:
        state["data"]["analyst_signals"] = {}
    state["data"]["analyst_signals"][agent_id] = sentiment_analysis

    progress.update_status(agent_id, None, "Completato")

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
    """Classifica in place una lista di elementi usando l'LLM, registrando le confidenze."""
    for idx, item in enumerate(items):
        progress.update_status(
            agent_id,
            ticker,
            f"Analisi del sentiment per {source_label} {idx + 1} di {len(items)}",
        )
        text = (text_fn(item) or "").strip()
        if not text:
            item.sentiment = "neutral"
            sentiment_confidences[id(item)] = 0
            continue

        prompt = (
            f"Analizza il sentiment del seguente {source_label} "
            f"considerando il seguente contesto: "
            f"l'azione di riferimento è {ticker}. "
            f"Determina se il sentiment è 'positive', 'negative' o 'neutral' "
            f"esclusivamente rispetto all'azione {ticker}. "
            f"Indica inoltre un punteggio di confidenza compreso tra 0 e 100. "
            f"Rispondi in formato JSON.\n\n"
            f"Contenuto: {text}"
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
    Calcola il punteggio di confidenza per un segnale di sentiment.

    Quando sono disponibili classificazioni dell'LLM, utilizza un approccio
    pesato che combina i punteggi di confidenza dell'LLM (70%) con la
    proporzione di segnali concordi (30%).
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
