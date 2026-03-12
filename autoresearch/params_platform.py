"""
autoresearch/params_platform.py — Sector-specific params for platform/enterprise AI (MSFT, AMZN, GOOGL, META, ORCL, PLTR).

Universe: Hyperscalers + enterprise AI. ikigaistudio Platform 45%.

Run: poetry run python -m autoresearch.evaluate --params autoresearch.params_platform
"""

STRATEGY_WEIGHTS = {"trend": 0.30, "mean_reversion": 0.18, "momentum": 0.37, "volatility": 0.15, "stat_arb": 0.00}
EMA_SHORT, EMA_MEDIUM, EMA_LONG = 5, 13, 34
ADX_PERIOD, MA_WINDOW, BOLLINGER_WINDOW, BOLLINGER_STD = 26, 50, 20, 5.0
RSI_SHORT, RSI_LONG, RSI_OVERSOLD, RSI_OVERBOUGHT = 14, 28, 0, 100
ZSCORE_BULLISH, ZSCORE_BEARISH, BB_BULLISH, BB_BEARISH = -2.0, 2.0, 0.2, 0.8
MOM_1M_WEIGHT, MOM_3M_WEIGHT, MOM_6M_WEIGHT = 1.0, 0.0, 0.0
MOM_BULLISH, MOM_BEARISH, MOM_CONFIDENCE_SCALE = 0.001, -0.001, 15.0
VOL_HIST_WINDOW, VOL_MA_WINDOW, VOL_LOW_REGIME, VOL_HIGH_REGIME = 21, 63, 0.95, 1.2
VOL_Z_BULLISH, VOL_Z_BEARISH = -0.5, 2.0
STAT_ARB_ROLLING, HURST_MAX_LAG, HURST_THRESHOLD, SKEW_THRESHOLD = 63, 20, 0.4, 1.0
SIGNAL_BULLISH_THRESHOLD, SIGNAL_BEARISH_THRESHOLD = 0.36, -0.2
RISK_BASE_LIMIT = 0.38
RISK_VOL_BANDS = [(0.15, 1.25), (0.40, 1.00), (0.70, 1.00)]
RISK_EXTREME_VOL_MULT, RISK_MED_VOL_DECAY, RISK_HIGH_VOL_DECAY = 0.50, 0.5, 0.5
RISK_MIN_MULT, RISK_MAX_MULT = 0.25, 1.15
CORR_BANDS = [(0.80, 0.70), (0.60, 0.85), (0.40, 1.00), (0.20, 1.05)]
CORR_DEFAULT_MULT, VOLATILITY_LOOKBACK_DAYS = 1.10, 45
ANALYST_WEIGHTS = {k: 0.0 for k in ["aswath_damodaran_agent","ben_graham_agent","bill_ackman_agent","cathie_wood_agent","charlie_munger_agent","michael_burry_agent","mohnish_pabrai_agent","peter_lynch_agent","phil_fisher_agent","rakesh_jhunjhunwala_agent","stanley_druckenmiller_agent","warren_buffett_agent","fundamentals_analyst_agent","growth_analyst_agent","news_sentiment_agent","sentiment_analyst_agent","valuation_analyst_agent"]}
ANALYST_WEIGHTS["technical_analyst_agent"] = 1.0
BUY_THRESHOLD, SELL_THRESHOLD, SHORT_THRESHOLD = 0.05, -0.05, -0.90
CONFIDENCE_POWER, POSITION_SIZE_FRACTION, MIN_CONFIDENCE_TO_ACT = 1.0, 1.00, 20
BACKTEST_TICKERS = ["MSFT", "AMZN", "GOOGL", "META", "ORCL", "PLTR"]
BACKTEST_START, BACKTEST_END = "2025-01-02", "2026-03-07"
BACKTEST_INITIAL_CASH, BACKTEST_MARGIN_REQ = 100_000, 0.5
PRICES_PATH = "prices_platform.json"
