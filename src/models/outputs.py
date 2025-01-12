from typing import Literal

from pydantic import BaseModel

Signal_Type = Literal["neutral", "bullish", "bearish"]
Analysts = Literal[
    "fundamentals_agent",
    "sentiment_agent",
    "technical_analyst_agent",
    "valuation_agent",
]


class Signal(BaseModel):
    confidence: float
    signal: Signal_Type


class DetailsSignal(BaseModel):
    details: str
    signal: Signal_Type


class ReasoningAgent(BaseModel):
    financial_health_signal: DetailsSignal | None = None
    growth_signal: DetailsSignal | None = None
    price_ratios_signal: DetailsSignal | None = None
    profitability_signal: DetailsSignal | None = None


class MeanReversionMetrics(BaseModel):
    price_vs_bb: float
    rsi_14: float
    rsi_28: float
    z_score: float


class MeanReversionTechnicalSignal(Signal):
    metrics: MeanReversionMetrics


class MomentumMetrics(BaseModel):
    momentum_1m: float
    momentum_3m: float
    momentum_6m: float
    volume_momentum: float


class MomentumTechnicalSignal(Signal):
    metrics: MomentumMetrics


class StatisticalArbitrageMetrics(BaseModel):
    hurst_exponent: float
    kurtosis: float
    skewness: float


class StatisticalArbitrageTechnicalSignal(Signal):
    metrics: StatisticalArbitrageMetrics


class TrendFollowingMetrics(BaseModel):
    adx: float
    trend_strength: float


class TrendFollowingTechnicalSignal(Signal):
    metrics: TrendFollowingMetrics


class VolatilityMetrics(BaseModel):
    atr_ratio: float
    historical_volatility: float
    volatility_regime: float
    volatility_z_score: float


class VolatilityTechnicalSignal(Signal):
    metrics: VolatilityMetrics


class ReasoningTechnical(BaseModel):
    mean_reversion: MeanReversionTechnicalSignal | None = None
    momentum: MomentumTechnicalSignal | None = None
    statistical_arbitrage: StatisticalArbitrageTechnicalSignal | None = None
    trend_following: TrendFollowingTechnicalSignal | None = None
    volatility: VolatilityTechnicalSignal | None = None


class ValuationDetails(BaseModel):
    details: str
    signal: Signal_Type


class ReasoningValuation(BaseModel):
    dcf_analysis: ValuationDetails | None = None
    owner_earnings_analysis: ValuationDetails | None = None


class FundamentalsAgent(Signal):
    reasoning: ReasoningAgent  # Specialized reasoning for fundamentals

    def __str__(self):
        return "Fundamentals"


class RiskManagementAgent(BaseModel):
    max_position_size: float
    reasoning: str

    def __str__(self):
        return "Risk Management"


class SentimentAgent(Signal):
    pass

    def __str__(self):
        return "Sentiment"


class TechnicalAnalystAgent(Signal):
    reasoning: ReasoningTechnical

    def __str__(self):
        return "Technical Analyst"


class ValuationAgent(Signal):
    reasoning: ReasoningValuation

    def __str__(self):
        return "Valuation"


class AnalystSignals(BaseModel):
    fundamentals_agent: FundamentalsAgent | None = None
    risk_management_agent: RiskManagementAgent
    sentiment_agent: SentimentAgent | None = None
    technical_analyst_agent: TechnicalAnalystAgent | None = None
    valuation_agent: ValuationAgent | None = None

    @property
    def signals(self) -> list[Signal]:
        return [
            agent
            for agent in [
                self.fundamentals_agent,
                self.sentiment_agent,
                self.technical_analyst_agent,
                self.valuation_agent,
            ]
            if agent
        ]


class Decision(BaseModel):
    action: str
    confidence: float | None
    quantity: int
    reasoning: str


class RootResultModel(BaseModel):
    analyst_signals: AnalystSignals
    decision: Decision | None
