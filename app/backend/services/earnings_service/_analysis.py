"""LLM-powered transcript analysis, sentiment delta, and conviction scoring."""

import asyncio
import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from app.backend.models.earnings_schemas import (
    ConvictionResponse,
    ConvictionSignal,
    EarningsAnalysisResponse,
    SentimentDelta,
    TranscriptAnalysis,
    TranscriptSentiment,
)
from src.llm.models import ModelProvider, get_model, get_model_info

from ._fetch import EarningsFetchError, fetch_transcripts

logger = logging.getLogger(__name__)

_MAX_TRANSCRIPT_CHARS: int = 50_000


class EarningsLLMError(Exception):
    pass


_ANALYSIS_PROMPT = """You are a senior equity analyst. Analyze this earnings call transcript for {ticker} ({quarter} {year}).

Provide a structured analysis:
1. overall_sentiment: exactly one of "bullish", "bearish", or "neutral"
2. confidence: 0-100 score for how confident you are in the sentiment assessment
3. management_tone: 2-4 word description of the CEO/CFO tone (e.g. "unusually confident", "cautiously optimistic", "defensive and evasive")
4. key_themes: up to 5 main topics/themes discussed (e.g. "margin expansion", "AI investment", "supply chain improvement")
5. forward_guidance: 1-2 sentence summary of management's forward-looking statements and guidance
6. notable_quotes: up to 3 significant direct quotes from the transcript

Focus on what matters for investment decisions: revenue trajectory, margin trends, competitive positioning, capital allocation, and management credibility.

Respond ONLY with valid JSON matching the schema. No markdown, no extra text."""


def _parse_json_text(text: str) -> TranscriptAnalysis | None:
    try:
        return TranscriptAnalysis(**json.loads(text))
    except Exception:
        pass
    for marker in ("```json", "```"):
        start = text.find(marker)
        if start != -1:
            json_text = text[start + len(marker):]
            end = json_text.find("```")
            if end != -1:
                json_text = json_text[:end].strip()
                try:
                    return TranscriptAnalysis(**json.loads(json_text))
                except Exception:
                    pass
    return None


def analyze_transcript_sync(content: str, ticker: str, quarter: str, year: int, source: str, model_name: str, model_provider: str, api_keys: dict) -> TranscriptSentiment:
    provider = ModelProvider(model_provider)
    llm = get_model(model_name, provider, api_keys)

    truncated = content[:_MAX_TRANSCRIPT_CHARS]

    model_info = get_model_info(model_name, provider.value)
    is_ollama = model_info and model_info.is_ollama()
    has_json = model_info and model_info.has_json_mode()

    messages = [
        SystemMessage(content=_ANALYSIS_PROMPT.format(ticker=ticker, quarter=quarter, year=year)),
        HumanMessage(content=f"Transcript:\n\n{truncated}"),
    ]

    if is_ollama:
        json_llm = llm.bind(format="json")
        result = json_llm.invoke(messages)
        analysis = _parse_json_text(result.content)
        if analysis is None:
            logger.warning("Failed to parse Ollama transcript analysis, using defaults")
            analysis = TranscriptAnalysis()
    elif has_json:
        structured_llm = llm.with_structured_output(TranscriptAnalysis, method="json_mode")
        analysis = structured_llm.invoke(messages)
    else:
        result = llm.invoke(messages)
        analysis = _parse_json_text(result.content)
        if analysis is None:
            logger.warning("Failed to parse LLM transcript analysis, using defaults")
            analysis = TranscriptAnalysis()

    return TranscriptSentiment(
        ticker=ticker.upper(),
        quarter=quarter,
        year=year,
        date=str(year) if not quarter else f"{year}-{quarter}",
        analysis=analysis,
        source=source,
    )


_SENTIMENT_VALUES = {"bullish": 1, "neutral": 0, "bearish": -1}


def compute_delta(current: TranscriptSentiment, previous: TranscriptSentiment | None) -> SentimentDelta:
    if previous is None:
        return SentimentDelta(current=current, previous=None, delta_direction="stable", delta_magnitude=0.0, key_changes=["No previous transcript for comparison"])

    cur_val = _SENTIMENT_VALUES.get(current.analysis.overall_sentiment, 0)
    prev_val = _SENTIMENT_VALUES.get(previous.analysis.overall_sentiment, 0)
    sentiment_shift = cur_val - prev_val

    if sentiment_shift > 0:
        direction = "improving"
    elif sentiment_shift < 0:
        direction = "deteriorating"
    else:
        direction = "stable"

    conf_diff = abs(current.analysis.confidence - previous.analysis.confidence)
    magnitude = min(100.0, abs(sentiment_shift) * 30 + conf_diff)

    changes = []
    if current.analysis.overall_sentiment != previous.analysis.overall_sentiment:
        changes.append(f"Sentiment shifted from {previous.analysis.overall_sentiment} to {current.analysis.overall_sentiment}")
    if current.analysis.management_tone != previous.analysis.management_tone:
        changes.append(f"Tone changed from '{previous.analysis.management_tone}' to '{current.analysis.management_tone}'")

    cur_themes = set(current.analysis.key_themes)
    prev_themes = set(previous.analysis.key_themes)
    new_themes = cur_themes - prev_themes
    dropped_themes = prev_themes - cur_themes
    if new_themes:
        changes.append(f"New themes: {', '.join(new_themes)}")
    if dropped_themes:
        changes.append(f"Dropped themes: {', '.join(dropped_themes)}")
    if not changes:
        changes.append("Sentiment broadly consistent quarter-over-quarter")

    return SentimentDelta(current=current, previous=previous, delta_direction=direction, delta_magnitude=round(magnitude, 1), key_changes=changes)


_POSITIVE_TONE_KEYWORDS = {"confident", "optimistic", "strong", "excited", "bullish", "positive", "encouraged"}
_NEGATIVE_TONE_KEYWORDS = {"cautious", "defensive", "uncertain", "concerned", "challenging", "difficult", "evasive"}
_POSITIVE_THEME_KEYWORDS = {"margin expansion", "revenue growth", "market share", "cost reduction", "innovation", "profitability"}
_C_LEVEL_TITLES = {"ceo", "cfo", "coo", "chief executive", "chief financial", "chief operating", "president"}


def build_conviction_for_ticker(ticker: str, analysis: EarningsAnalysisResponse, insider_records: list) -> ConvictionSignal:
    delta = analysis.delta
    if not delta:
        return ConvictionSignal(ticker=ticker, reasoning="No sentiment data available")

    score = 50.0
    reasons = []

    if delta.delta_direction == "improving":
        score += 30
        reasons.append(f"Sentiment improving ({delta.delta_magnitude:.0f}% shift)")
    elif delta.delta_direction == "deteriorating":
        score -= 20
        reasons.append(f"Sentiment deteriorating ({delta.delta_magnitude:.0f}% shift)")
    else:
        reasons.append("Sentiment stable quarter-over-quarter")

    tone = delta.current.analysis.management_tone.lower()
    if any(kw in tone for kw in _POSITIVE_TONE_KEYWORDS):
        score += 15
        reasons.append(f"Management tone: '{delta.current.analysis.management_tone}'")
    elif any(kw in tone for kw in _NEGATIVE_TONE_KEYWORDS):
        score -= 10
        reasons.append(f"Cautious management tone: '{delta.current.analysis.management_tone}'")

    cur_themes_lower = [t.lower() for t in delta.current.analysis.key_themes]
    positive_theme_hits = [t for t in cur_themes_lower if any(kw in t for kw in _POSITIVE_THEME_KEYWORDS)]
    if positive_theme_hits:
        score += 10
        reasons.append(f"Positive themes: {', '.join(positive_theme_hits[:3])}")

    ticker_upper = ticker.upper()
    earnings_date = delta.current.date
    buy_records = [r for r in insider_records if r.ticker.upper() == ticker_upper and r.trade_type.lower() in ("p - purchase", "purchase", "p")]
    post_earnings_buys = buy_records
    if earnings_date and len(earnings_date) >= 10:
        post_earnings_buys = [r for r in buy_records if r.trade_date >= earnings_date]
    buy_count = len(post_earnings_buys)
    buy_value = sum(r.value or 0 for r in post_earnings_buys)

    if buy_count > 0:
        insider_factor = min(25, buy_count * 8)
        score += insider_factor
        reasons.append(f"{buy_count} insider buy(s) worth ${buy_value:,.0f}")
        activity = "net_buying"
    else:
        sell_records = [r for r in insider_records if r.ticker.upper() == ticker_upper and r.trade_type.lower() in ("s - sale", "sale", "s")]
        if sell_records:
            activity = "net_selling"
            reasons.append("Insider selling detected")
        else:
            activity = "neutral"
            reasons.append("No recent insider activity")

    ceo_cfo_buying = False
    for r in post_earnings_buys:
        title_lower = r.title.lower()
        if any(t in title_lower for t in _C_LEVEL_TITLES):
            ceo_cfo_buying = True
            score += 20
            reasons.append(f"C-level insider buying: {r.insider_name} ({r.title})")
            break

    score = max(0, min(99, score))

    return ConvictionSignal(
        ticker=ticker_upper,
        sentiment_delta=delta.delta_direction,
        management_tone=delta.current.analysis.management_tone,
        key_themes=delta.current.analysis.key_themes,
        insider_activity=activity,
        insider_buy_count=buy_count,
        insider_buy_value=buy_value,
        ceo_cfo_buying=ceo_cfo_buying,
        conviction_score=round(score, 1),
        reasoning=". ".join(reasons),
    )


def build_earnings_analysis(ticker: str, model_name: str, model_provider: str, api_keys: dict) -> EarningsAnalysisResponse:
    fetch_result = fetch_transcripts(ticker, limit=2)

    sentiments: list[TranscriptSentiment] = []
    for t in fetch_result.transcripts:
        s = analyze_transcript_sync(t["content"], ticker, t["quarter"], t["year"], fetch_result.source, model_name, model_provider, api_keys)
        s.date = t.get("date", s.date)
        sentiments.append(s)

    delta = None
    if len(sentiments) >= 2:
        delta = compute_delta(sentiments[0], sentiments[1])
    elif len(sentiments) == 1:
        delta = compute_delta(sentiments[0], None)

    return EarningsAnalysisResponse(ticker=ticker.upper(), transcripts=sentiments, delta=delta, cached=False)


def build_conviction_signals(tickers: list[str], model_name: str, model_provider: str, api_keys: dict) -> ConvictionResponse:
    from app.backend.services.openinsider_service import get_openinsider_screener, OpenInsiderFetchError

    insider_records = []
    try:
        loop = asyncio.new_event_loop()
        try:
            oi_resp = loop.run_until_complete(get_openinsider_screener("latest_cluster_buys", None))
            insider_records = oi_resp.records
        finally:
            loop.close()
    except (OpenInsiderFetchError, Exception) as exc:
        logger.warning("Could not fetch OpenInsider data for conviction: %s", exc)

    signals = []
    for ticker in tickers:
        try:
            analysis = build_earnings_analysis(ticker, model_name, model_provider, api_keys)
            signal = build_conviction_for_ticker(ticker, analysis, insider_records)
            signals.append(signal)
        except (EarningsFetchError, EarningsLLMError) as exc:
            logger.warning("Conviction analysis failed for %s: %s", ticker, exc)
            signals.append(ConvictionSignal(ticker=ticker.upper(), reasoning=f"Analysis failed: {exc}"))

    signals.sort(key=lambda s: s.conviction_score, reverse=True)
    return ConvictionResponse(signals=signals, total=len(signals), cached=False)
