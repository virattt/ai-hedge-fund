"""
autoresearch/params.py — The single mutable file.

The AI agent modifies ONLY this file. Every tunable knob lives here.
After each modification, `evaluate.py` is run to measure the effect.
If Sharpe improves → git commit (keep). Otherwise → git checkout (revert).

RULES (for the AI agent):
  - Change ONE section per experiment for clean attribution.
  - Never delete a parameter — set it to a neutral value instead.
  - Weights that form an ensemble must stay non-negative.
  - Keep this file importable Python at all times.
"""

# ─────────────────────────────────────────────────────────────
# 1. TECHNICAL ANALYST — Strategy Ensemble Weights
# ─────────────────────────────────────────────────────────────
STRATEGY_WEIGHTS = {
    "trend": 0.30,
    "mean_reversion": 0.20,
    "momentum": 0.35,
    "volatility": 0.15,
    "stat_arb": 0.00,
}

# ─────────────────────────────────────────────────────────────
# 2. TECHNICAL ANALYST — Indicator Parameters
# ─────────────────────────────────────────────────────────────

# Trend
EMA_SHORT = 5
EMA_MEDIUM = 13
EMA_LONG = 34
ADX_PERIOD = 21

# Mean Reversion
MA_WINDOW = 50
BOLLINGER_WINDOW = 20
BOLLINGER_STD = 5.0
RSI_SHORT = 14
RSI_LONG = 28
ZSCORE_BULLISH = -2.0
ZSCORE_BEARISH = 2.0
BB_BULLISH = 0.2
BB_BEARISH = 0.8

# Momentum
MOM_1M_WEIGHT = 1.0
MOM_3M_WEIGHT = 0.0
MOM_6M_WEIGHT = 0.0
MOM_BULLISH = 0.001
MOM_BEARISH = -0.001
MOM_CONFIDENCE_SCALE = 15.0

# Volatility
VOL_HIST_WINDOW = 21
VOL_MA_WINDOW = 63
VOL_LOW_REGIME = 0.95
VOL_HIGH_REGIME = 1.2
VOL_Z_BULLISH = -0.5
VOL_Z_BEARISH = 2.0

# Statistical Arbitrage
STAT_ARB_ROLLING = 63
HURST_MAX_LAG = 20
HURST_THRESHOLD = 0.4
SKEW_THRESHOLD = 1.0

# Final signal classification
SIGNAL_BULLISH_THRESHOLD = 0.2
SIGNAL_BEARISH_THRESHOLD = -0.2

# ─────────────────────────────────────────────────────────────
# 3. RISK MANAGEMENT — Position Sizing
# ─────────────────────────────────────────────────────────────
RISK_BASE_LIMIT = 0.30

# Volatility band thresholds and multipliers
RISK_VOL_BANDS = [
    # (max_annualized_vol, multiplier)
    (0.15, 1.25),   # Low vol → modest boost
    (0.40, 1.00),   # Medium vol → no penalty
    (0.70, 1.00),   # High vol → no penalty (test: is vol risk helping?)
]
RISK_EXTREME_VOL_MULT = 0.50
RISK_MED_VOL_DECAY = 0.5
RISK_HIGH_VOL_DECAY = 0.5
RISK_MIN_MULT = 0.25
RISK_MAX_MULT = 1.25

# Correlation multipliers
CORR_BANDS = [
    # (min_correlation, multiplier)
    (0.80, 0.70),
    (0.60, 0.85),
    (0.40, 1.00),
    (0.20, 1.05),
]
CORR_DEFAULT_MULT = 1.10

VOLATILITY_LOOKBACK_DAYS = 60

# ─────────────────────────────────────────────────────────────
# 4. ANALYST SIGNAL AGGREGATION — Who to trust
# ─────────────────────────────────────────────────────────────
ANALYST_WEIGHTS = {
    "aswath_damodaran_agent": 1.0,
    "ben_graham_agent": 1.0,
    "bill_ackman_agent": 1.0,
    "cathie_wood_agent": 1.0,
    "charlie_munger_agent": 1.0,
    "michael_burry_agent": 1.0,
    "mohnish_pabrai_agent": 1.0,
    "peter_lynch_agent": 1.0,
    "phil_fisher_agent": 1.0,
    "rakesh_jhunjhunwala_agent": 1.0,
    "stanley_druckenmiller_agent": 1.0,
    "warren_buffett_agent": 1.0,
    "technical_analyst_agent": 1.0,
    "fundamentals_analyst_agent": 1.0,
    "growth_analyst_agent": 1.0,
    "news_sentiment_agent": 1.0,
    "sentiment_analyst_agent": 1.0,
    "valuation_analyst_agent": 1.0,
}

# ─────────────────────────────────────────────────────────────
# 5. PORTFOLIO DECISION — Deterministic Trading Rules
# ─────────────────────────────────────────────────────────────
BUY_THRESHOLD = 0.05
SELL_THRESHOLD = -0.05
# Mode 1 (technical only, 1 agent): scores range ±0.2–1.0 → -0.90 works
# Mode 2 (full signals, 18 agents): scores range ±0.05–0.65 → use -0.15 to allow shorting
SHORT_THRESHOLD = -0.90
CONFIDENCE_POWER = 1.0        # exponent on confidence (>1 amplifies high-conf signals)
POSITION_SIZE_FRACTION = 1.00  # fraction of max_shares to trade
MIN_CONFIDENCE_TO_ACT = 20    # ignore signals below this confidence (0-100)

# ─────────────────────────────────────────────────────────────
# 6. BACKTEST CONFIG — Fixed per experiment session
# ─────────────────────────────────────────────────────────────
BACKTEST_TICKERS = ["AAPL", "NVDA", "MSFT", "GOOGL", "TSLA"]
BACKTEST_START = "2025-01-02"
BACKTEST_END = "2026-03-07"
BACKTEST_INITIAL_CASH = 100_000
BACKTEST_MARGIN_REQ = 0.5
