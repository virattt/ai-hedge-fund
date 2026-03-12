"""
autoresearch/params_energy.py — Sector-specific params for energy (XOM, CVX, OXY, SLB, EOG).

Universe: XOM, CVX, OXY, SLB, EOG
Regime: Commodity-driven, rate-sensitive. Tech params: full-window Sharpe 0.03, OOS 1.47.
→ OOS is strong; tune to lift full-window while preserving OOS.

Run: poetry run python -m autoresearch.evaluate --params autoresearch.params_energy
"""

STRATEGY_WEIGHTS = {
    "trend": 0.30,
    "mean_reversion": 0.18,
    "momentum": 0.37,
    "volatility": 0.15,
    "stat_arb": 0.00,
}

EMA_SHORT = 5
EMA_MEDIUM = 13
EMA_LONG = 34
ADX_PERIOD = 26

MA_WINDOW = 50
BOLLINGER_WINDOW = 20
BOLLINGER_STD = 5.0
RSI_SHORT = 14
RSI_LONG = 28
RSI_OVERSOLD = 0
RSI_OVERBOUGHT = 100
ZSCORE_BULLISH = -2.0
ZSCORE_BEARISH = 2.0
BB_BULLISH = 0.2
BB_BEARISH = 0.8

MOM_1M_WEIGHT = 1.0
MOM_3M_WEIGHT = 0.0
MOM_6M_WEIGHT = 0.0
MOM_BULLISH = 0.001
MOM_BEARISH = -0.001
MOM_CONFIDENCE_SCALE = 15.0

VOL_HIST_WINDOW = 21
VOL_MA_WINDOW = 63
VOL_LOW_REGIME = 0.95
VOL_HIGH_REGIME = 1.2
VOL_Z_BULLISH = -0.5
VOL_Z_BEARISH = 2.0

STAT_ARB_ROLLING = 63
HURST_MAX_LAG = 20
HURST_THRESHOLD = 0.4
SKEW_THRESHOLD = 1.0

SIGNAL_BULLISH_THRESHOLD = 0.28
SIGNAL_BEARISH_THRESHOLD = -0.2

RISK_BASE_LIMIT = 0.30
RISK_VOL_BANDS = [(0.15, 1.25), (0.40, 1.00), (0.70, 1.00)]
RISK_EXTREME_VOL_MULT = 0.50
RISK_MED_VOL_DECAY = 0.5
RISK_HIGH_VOL_DECAY = 0.5
RISK_MIN_MULT = 0.25
RISK_MAX_MULT = 1.15

CORR_BANDS = [(0.80, 0.70), (0.60, 0.85), (0.40, 1.00), (0.20, 1.05)]
CORR_DEFAULT_MULT = 1.10
VOLATILITY_LOOKBACK_DAYS = 45

ANALYST_WEIGHTS = {k: 0.0 for k in [
    "aswath_damodaran_agent", "ben_graham_agent", "bill_ackman_agent", "cathie_wood_agent",
    "charlie_munger_agent", "michael_burry_agent", "mohnish_pabrai_agent", "peter_lynch_agent",
    "phil_fisher_agent", "rakesh_jhunjhunwala_agent", "stanley_druckenmiller_agent", "warren_buffett_agent",
    "fundamentals_analyst_agent", "growth_analyst_agent", "news_sentiment_agent", "sentiment_analyst_agent", "valuation_analyst_agent",
]}
ANALYST_WEIGHTS["technical_analyst_agent"] = 1.0

BUY_THRESHOLD = 0.05
SELL_THRESHOLD = -0.05
SHORT_THRESHOLD = -0.90
CONFIDENCE_POWER = 1.0
POSITION_SIZE_FRACTION = 1.00
MIN_CONFIDENCE_TO_ACT = 20

BACKTEST_TICKERS = ["XOM", "CVX", "OXY", "SLB", "EOG"]
BACKTEST_START = "2025-01-02"
BACKTEST_END = "2026-03-07"
BACKTEST_INITIAL_CASH = 100_000
BACKTEST_MARGIN_REQ = 0.5
PRICES_PATH = "prices_energy.json"
