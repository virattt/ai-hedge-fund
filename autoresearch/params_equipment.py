"""
autoresearch/params_equipment.py — Sector-specific params for semiconductor equipment.

Universe: AMAT, ASML, LRCX, KLAC, TEL
Regime: Long capex cycle, order-book driven, quarterly earnings cadence.

Baseline (tech params applied to equipment):
  Full-window: Sharpe 1.63, return +76.92%, max DD -16.7%
  OOS (H2 2025): Sharpe 2.05, return +57.72%, max DD -16.63%

Note: Equipment generalizes better than energy to the tech-tuned params
(Sharpe 1.63 vs energy 0.03), suggesting momentum/trend still works but
risk limits need tightening (higher vol = bigger drawdown at same RISK_BASE_LIMIT).

RULES (for the AI agent):
  - Change ONE section per experiment for clean attribution.
  - Never delete a parameter — set it to a neutral value instead.
  - Weights that form an ensemble must stay non-negative.
  - Keep this file importable Python at all times.
  - Run experiments with:
      poetry run python -m autoresearch.evaluate \
        --tickers AMAT,ASML,LRCX,KLAC,TEL \
        --prices-path prices_equipment.json
  - OOS check:
      poetry run python -m autoresearch.evaluate \
        --tickers AMAT,ASML,LRCX,KLAC,TEL \
        --prices-path prices_equipment.json \
        --start 2025-08-01 --end 2026-03-07
"""

# ─────────────────────────────────────────────────────────────
# 1. TECHNICAL ANALYST — Strategy Ensemble Weights
# ─────────────────────────────────────────────────────────────
# Equipment is capex-cycle driven — trend dominates over short-term momentum.
# Starting from tech-tuned weights; autoresearch will adjust from here.
STRATEGY_WEIGHTS = {
    "trend": 0.32,
    "mean_reversion": 0.16,
    "momentum": 0.37,
    "volatility": 0.15,
    "stat_arb": 0.00,
}

# ─────────────────────────────────────────────────────────────
# 2. TECHNICAL ANALYST — Indicator Parameters
# ─────────────────────────────────────────────────────────────

# Trend — equipment cycles are quarterly, not weekly
EMA_SHORT = 5
EMA_MEDIUM = 21
EMA_LONG = 50
ADX_PERIOD = 40

# Mean Reversion
MA_WINDOW = 63
BOLLINGER_WINDOW = 30
BOLLINGER_STD = 5.0
RSI_SHORT = 14
RSI_LONG = 28
RSI_OVERSOLD = 0
RSI_OVERBOUGHT = 100
ZSCORE_BULLISH = -2.0
ZSCORE_BEARISH = 2.0
BB_BULLISH = 0.2
BB_BEARISH = 0.8

# Momentum
MOM_1M_WEIGHT = 0.9
MOM_3M_WEIGHT = 0.1
MOM_6M_WEIGHT = 0.0
MOM_BULLISH = 0.001
MOM_BEARISH = -0.001
MOM_CONFIDENCE_SCALE = 18.0

# Volatility
VOL_HIST_WINDOW = 21
VOL_MA_WINDOW = 63
VOL_LOW_REGIME = 0.90
VOL_HIGH_REGIME = 1.25
VOL_Z_BULLISH = -0.5
VOL_Z_BEARISH = 1.5

# Statistical Arbitrage
STAT_ARB_ROLLING = 63
HURST_MAX_LAG = 20
HURST_THRESHOLD = 0.4
SKEW_THRESHOLD = 1.0

# Final signal classification
SIGNAL_BULLISH_THRESHOLD = 0.28
SIGNAL_BEARISH_THRESHOLD = -0.15

# ─────────────────────────────────────────────────────────────
# 3. RISK MANAGEMENT — Position Sizing
# ─────────────────────────────────────────────────────────────
# Equipment is higher vol than tech (max DD -16.7% vs -8.2% at same RISK_BASE_LIMIT).
# First experiment: reduce RISK_BASE_LIMIT to tighten drawdown.
RISK_BASE_LIMIT = 0.30

RISK_VOL_BANDS = [
    (0.15, 1.25),
    (0.40, 1.00),
    (0.70, 1.00),
]
RISK_EXTREME_VOL_MULT = 0.60
RISK_MED_VOL_DECAY = 0.5
RISK_HIGH_VOL_DECAY = 0.5
RISK_MIN_MULT = 0.25
RISK_MAX_MULT = 1.15

CORR_BANDS = [
    (0.80, 0.70),
    (0.60, 0.85),
    (0.40, 1.00),
    (0.20, 1.05),
]
CORR_DEFAULT_MULT = 1.10

VOLATILITY_LOOKBACK_DAYS = 45

# ─────────────────────────────────────────────────────────────
# 4. ANALYST SIGNAL AGGREGATION — Who to trust
# ─────────────────────────────────────────────────────────────
ANALYST_WEIGHTS = {
    "aswath_damodaran_agent": 0.0,
    "ben_graham_agent": 0.0,
    "bill_ackman_agent": 0.0,
    "cathie_wood_agent": 0.0,
    "charlie_munger_agent": 0.0,
    "michael_burry_agent": 0.0,
    "mohnish_pabrai_agent": 0.0,
    "peter_lynch_agent": 0.0,
    "phil_fisher_agent": 0.0,
    "rakesh_jhunjhunwala_agent": 0.0,
    "stanley_druckenmiller_agent": 0.0,
    "warren_buffett_agent": 0.0,
    "technical_analyst_agent": 1.0,
    "fundamentals_analyst_agent": 0.0,
    "growth_analyst_agent": 0.0,
    "news_sentiment_agent": 0.0,
    "sentiment_analyst_agent": 0.0,
    "valuation_analyst_agent": 0.0,
}

# ─────────────────────────────────────────────────────────────
# 5. PORTFOLIO DECISION — Deterministic Trading Rules
# ─────────────────────────────────────────────────────────────
BUY_THRESHOLD = 0.05
SELL_THRESHOLD = -0.05
SHORT_THRESHOLD = -0.90
CONFIDENCE_POWER = 1.0
POSITION_SIZE_FRACTION = 1.00
MIN_CONFIDENCE_TO_ACT = 20

# ─────────────────────────────────────────────────────────────
# 6. BACKTEST CONFIG
# ─────────────────────────────────────────────────────────────
BACKTEST_TICKERS = ["AMAT", "ASML", "LRCX", "KLAC", "TEL"]
BACKTEST_START = "2025-01-02"
BACKTEST_END = "2026-03-07"
BACKTEST_INITIAL_CASH = 100_000
BACKTEST_MARGIN_REQ = 0.5

# Sector-specific cache path — evaluate.py reads this automatically when --params is used
PRICES_PATH = "prices_equipment.json"
