"""Pydantic schemas for Earnings Sentiment analysis (FMP + EDGAR + LLM)."""

from pydantic import BaseModel


class TranscriptAnalysis(BaseModel):
    """LLM-structured output for a single earnings call transcript."""
    overall_sentiment: str = "neutral"
    confidence: float = 50.0
    management_tone: str = "neutral"
    key_themes: list[str] = []
    forward_guidance: str = ""
    notable_quotes: list[str] = []


class TranscriptSentiment(BaseModel):
    """Full sentiment record for one earnings call."""
    ticker: str
    quarter: str
    year: int
    date: str
    analysis: TranscriptAnalysis
    source: str


class SentimentDelta(BaseModel):
    """Comparison between two consecutive transcripts."""
    current: TranscriptSentiment
    previous: TranscriptSentiment | None = None
    delta_direction: str = "stable"
    delta_magnitude: float = 0.0
    key_changes: list[str] = []


class EarningsAnalysisResponse(BaseModel):
    ticker: str
    transcripts: list[TranscriptSentiment]
    delta: SentimentDelta | None = None
    cached: bool


class ConvictionSignal(BaseModel):
    ticker: str
    sentiment_delta: str = "stable"
    management_tone: str = "neutral"
    key_themes: list[str] = []
    insider_activity: str = "neutral"
    insider_buy_count: int = 0
    insider_buy_value: float = 0.0
    ceo_cfo_buying: bool = False
    conviction_score: float = 50.0
    reasoning: str = ""


class ConvictionResponse(BaseModel):
    signals: list[ConvictionSignal]
    total: int
    cached: bool


class EarningsAnalysisRequest(BaseModel):
    ticker: str
    model_name: str
    model_provider: str


class ConvictionRequest(BaseModel):
    tickers: list[str]
    model_name: str
    model_provider: str
