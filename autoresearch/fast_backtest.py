"""
autoresearch/fast_backtest.py — Deterministic backtester using cached data.

No LLM calls. No API calls. Pure math. Runs in seconds.
Reads params from autoresearch/params.py and cached data from autoresearch/cache/.

Two modes:
  1. Technical-only (no signal cache needed): Recomputes technical indicators
     from cached price data with current params. Free and instant.
  2. Full-signal (needs signal cache): Uses cached LLM agent signals + recomputed
     technical signals, aggregated with configurable weights.
"""

import json
import math
import sys
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

CACHE_DIR = Path(__file__).resolve().parent / "cache"


def load_prices_cache() -> dict[str, pd.DataFrame]:
    """Load cached price data into DataFrames keyed by ticker."""
    prices_path = CACHE_DIR / "prices.json"
    if not prices_path.exists():
        raise FileNotFoundError(
            f"No price cache at {prices_path}. Run: poetry run python -m autoresearch.cache_signals --prices-only"
        )
    with open(prices_path) as f:
        raw = json.load(f)

    frames = {}
    for ticker, records in raw.items():
        if not records:
            continue
        df = pd.DataFrame(records)
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()
        frames[ticker] = df
    return frames


def load_signals_cache() -> Optional[dict]:
    """Load cached agent signals. Returns None if cache doesn't exist."""
    signals_path = CACHE_DIR / "signals.json"
    if not signals_path.exists():
        return None
    with open(signals_path) as f:
        return json.load(f)


# ── Technical indicator computations (parameterized) ────────

def compute_ema(series: pd.Series, window: int) -> pd.Series:
    return series.ewm(span=window, adjust=False).mean()


def compute_rsi(series: pd.Series, period: int) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def compute_bollinger(series: pd.Series, window: int, num_std: float):
    sma = series.rolling(window).mean()
    std = series.rolling(window).std()
    return sma + num_std * std, sma - num_std * std


def compute_adx(df: pd.DataFrame, period: int) -> pd.Series:
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    up = df["high"] - df["high"].shift()
    down = df["low"].shift() - df["low"]
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    plus_dm_s = pd.Series(plus_dm, index=df.index).ewm(span=period).mean()
    minus_dm_s = pd.Series(minus_dm, index=df.index).ewm(span=period).mean()
    tr_s = tr.ewm(span=period).mean()
    plus_di = 100 * plus_dm_s / tr_s.replace(0, np.nan)
    minus_di = 100 * minus_dm_s / tr_s.replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(span=period).mean()


def compute_hurst(series: pd.Series, max_lag: int) -> float:
    arr = np.asarray(series.dropna().values, dtype=float)
    if len(arr) < max_lag + 2:
        return 0.5
    lags_used, tau = [], []
    for lag in range(2, max_lag):
        diff = arr[lag:] - arr[:-lag]
        if len(diff) < 2:
            continue
        s = np.var(diff, ddof=0)
        lags_used.append(lag)
        tau.append(max(1e-8, np.sqrt(s)))
    if len(tau) < 2:
        return 0.5
    try:
        reg = np.polyfit(np.log(lags_used), np.log(tau), 1)
        return float(reg[0])
    except Exception:
        return 0.5


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def _safe(val, default=0.0):
    try:
        if pd.isna(val) or np.isnan(val):
            return default
    except (TypeError, ValueError):
        pass
    return float(val) if val is not None else default


# ── Technical signal computation using params ────────────────

def compute_technical_signals(df: pd.DataFrame, params) -> dict:
    """Compute all 5 technical sub-signals using current params. Returns {signal, confidence}."""

    if len(df) < 10:
        return {"signal": "neutral", "confidence": 50}

    close = df["close"]

    # 1. Trend
    ema_s = compute_ema(close, params.EMA_SHORT)
    ema_m = compute_ema(close, params.EMA_MEDIUM)
    ema_l = compute_ema(close, params.EMA_LONG)
    adx = compute_adx(df, params.ADX_PERIOD)
    trend_strength = _safe(adx.iloc[-1], 50) / 100.0
    short_trend = ema_s.iloc[-1] > ema_m.iloc[-1]
    medium_trend = ema_m.iloc[-1] > ema_l.iloc[-1]
    if short_trend and medium_trend:
        trend_sig, trend_conf = "bullish", trend_strength
    elif not short_trend and not medium_trend:
        trend_sig, trend_conf = "bearish", trend_strength
    else:
        trend_sig, trend_conf = "neutral", 0.5

    # 2. Mean Reversion (Z-score + Bollinger + RSI — RSI now live, unlocks mr when Bollinger neutralized)
    ma = close.rolling(params.MA_WINDOW).mean()
    std = close.rolling(params.MA_WINDOW).std()
    z = (close - ma) / std.replace(0, np.nan)
    bb_up, bb_lo = compute_bollinger(close, params.BOLLINGER_WINDOW, params.BOLLINGER_STD)
    bb_range = (bb_up - bb_lo).replace(0, np.nan)
    bb_pos = (close - bb_lo) / bb_range
    rsi = compute_rsi(close, params.RSI_SHORT)
    z_val = _safe(z.iloc[-1])
    bb_val = _safe(bb_pos.iloc[-1], 0.5)
    rsi_val = _safe(rsi.iloc[-1], 50.0)
    zbb_bull = z_val < params.ZSCORE_BULLISH and bb_val < params.BB_BULLISH
    zbb_bear = z_val > params.ZSCORE_BEARISH and bb_val > params.BB_BEARISH
    rsi_bull = rsi_val < params.RSI_OVERSOLD
    rsi_bear = rsi_val > params.RSI_OVERBOUGHT
    if zbb_bull or rsi_bull:
        conf_zbb = min(abs(z_val) / 4, 1.0) if zbb_bull else 0.0
        conf_rsi = min((params.RSI_OVERSOLD - rsi_val) / 30, 1.0) if rsi_bull else 0.0
        mr_sig, mr_conf = "bullish", max(conf_zbb, conf_rsi) or 0.5
    elif zbb_bear or rsi_bear:
        conf_zbb = min(abs(z_val) / 4, 1.0) if zbb_bear else 0.0
        conf_rsi = min((rsi_val - params.RSI_OVERBOUGHT) / 30, 1.0) if rsi_bear else 0.0
        mr_sig, mr_conf = "bearish", max(conf_zbb, conf_rsi) or 0.5
    else:
        mr_sig, mr_conf = "neutral", 0.5

    # 3. Momentum
    returns = close.pct_change()
    m1 = returns.rolling(21).sum()
    m3 = returns.rolling(63).sum()
    m6 = returns.rolling(126).sum()
    vol_ma = df["volume"].rolling(21).mean()
    vol_mom = df["volume"] / vol_ma.replace(0, np.nan)
    score = (params.MOM_1M_WEIGHT * m1 + params.MOM_3M_WEIGHT * m3 + params.MOM_6M_WEIGHT * m6)
    mom_score = _safe(score.iloc[-1])
    vol_confirm = _safe(vol_mom.iloc[-1], 0) > 1.0
    if mom_score > params.MOM_BULLISH and vol_confirm:
        mom_sig, mom_conf = "bullish", min(abs(mom_score) * params.MOM_CONFIDENCE_SCALE, 1.0)
    elif mom_score < params.MOM_BEARISH and vol_confirm:
        mom_sig, mom_conf = "bearish", min(abs(mom_score) * params.MOM_CONFIDENCE_SCALE, 1.0)
    else:
        mom_sig, mom_conf = "neutral", 0.5

    # 4. Volatility
    hist_vol = returns.rolling(params.VOL_HIST_WINDOW).std() * math.sqrt(252)
    vol_sma = hist_vol.rolling(params.VOL_MA_WINDOW).mean()
    vol_regime = hist_vol / vol_sma.replace(0, np.nan)
    vol_z = (hist_vol - vol_sma) / hist_vol.rolling(params.VOL_MA_WINDOW).std().replace(0, np.nan)
    vr = _safe(vol_regime.iloc[-1], 1.0)
    vz = _safe(vol_z.iloc[-1])
    if vr < params.VOL_LOW_REGIME and vz < params.VOL_Z_BULLISH:
        vol_sig, vol_conf = "bullish", min(abs(vz) / 3, 1.0)
    elif vr > params.VOL_HIGH_REGIME and vz > params.VOL_Z_BEARISH:
        vol_sig, vol_conf = "bearish", min(abs(vz) / 3, 1.0)
    else:
        vol_sig, vol_conf = "neutral", 0.5

    # 5. Stat Arb
    skew = returns.rolling(params.STAT_ARB_ROLLING).skew()
    hurst = compute_hurst(close, params.HURST_MAX_LAG)
    sk = _safe(skew.iloc[-1])
    if hurst < params.HURST_THRESHOLD and sk > params.SKEW_THRESHOLD:
        sa_sig, sa_conf = "bullish", (0.5 - hurst) * 2
    elif hurst < params.HURST_THRESHOLD and sk < -params.SKEW_THRESHOLD:
        sa_sig, sa_conf = "bearish", (0.5 - hurst) * 2
    else:
        sa_sig, sa_conf = "neutral", 0.5

    # Weighted ensemble
    sig_map = {"bullish": 1, "neutral": 0, "bearish": -1}
    components = {
        "trend": (trend_sig, trend_conf),
        "mean_reversion": (mr_sig, mr_conf),
        "momentum": (mom_sig, mom_conf),
        "volatility": (vol_sig, vol_conf),
        "stat_arb": (sa_sig, sa_conf),
    }
    w_sum = 0.0
    w_total = 0.0
    for key, (sig, conf) in components.items():
        w = params.STRATEGY_WEIGHTS.get(key, 0.0)
        w_sum += sig_map[sig] * w * conf
        w_total += w * conf

    final_score = w_sum / w_total if w_total > 0 else 0.0
    if final_score > params.SIGNAL_BULLISH_THRESHOLD:
        signal = "bullish"
    elif final_score < params.SIGNAL_BEARISH_THRESHOLD:
        signal = "bearish"
    else:
        signal = "neutral"

    return {"signal": signal, "confidence": round(abs(final_score) * 100)}


# ── Risk management (parameterized) ─────────────────────────

def compute_vol_adjusted_limit(annualized_vol: float, params) -> float:
    base = params.RISK_BASE_LIMIT
    mult = params.RISK_EXTREME_VOL_MULT
    for max_vol, band_mult in params.RISK_VOL_BANDS:
        if annualized_vol < max_vol:
            mult = band_mult
            break
    mult = max(params.RISK_MIN_MULT, min(params.RISK_MAX_MULT, mult))
    return base * mult


def compute_corr_multiplier(avg_corr: float, params) -> float:
    for min_corr, mult in params.CORR_BANDS:
        if avg_corr >= min_corr:
            return mult
    return params.CORR_DEFAULT_MULT


# ── Deterministic portfolio decision ─────────────────────────

def deterministic_portfolio_decision(
    ticker: str,
    weighted_score: float,
    confidence: float,
    max_shares: int,
    current_long: int,
    current_short: int,
    params,
) -> dict:
    """Pure-math replacement for the LLM portfolio manager."""
    if confidence < params.MIN_CONFIDENCE_TO_ACT:
        return {"action": "hold", "quantity": 0}

    frac = params.POSITION_SIZE_FRACTION * min(confidence / 100.0, 1.0)

    if weighted_score > params.BUY_THRESHOLD:
        qty = max(1, int(max_shares * frac))
        return {"action": "buy", "quantity": qty}

    if weighted_score < params.SHORT_THRESHOLD and current_long == 0:
        qty = max(1, int(max_shares * frac))
        return {"action": "short", "quantity": qty}

    if weighted_score < params.SELL_THRESHOLD and current_long > 0:
        qty = max(1, int(current_long * frac))
        return {"action": "sell", "quantity": qty}

    if weighted_score > params.BUY_THRESHOLD and current_short > 0:
        qty = min(current_short, max(1, int(current_short * frac)))
        return {"action": "cover", "quantity": qty}

    return {"action": "hold", "quantity": 0}


# ── Main fast backtest engine ────────────────────────────────

class FastBacktestEngine:
    def __init__(self, params_module):
        self.p = params_module
        self.prices = load_prices_cache()
        self.signals_cache = load_signals_cache()
        self.tickers = self.p.BACKTEST_TICKERS
        self.portfolio_values = []

    def _get_price_slice(self, ticker: str, end_date: str, lookback_days: int = 200) -> pd.DataFrame:
        df = self.prices.get(ticker)
        if df is None or df.empty:
            return pd.DataFrame()
        end_dt = pd.Timestamp(end_date)
        mask = df.index <= end_dt
        return df[mask].tail(lookback_days)

    def _get_close_price(self, ticker: str, date_str: str) -> Optional[float]:
        df = self.prices.get(ticker)
        if df is None or df.empty:
            return None
        end_dt = pd.Timestamp(date_str)
        before = df[df.index <= end_dt]
        if before.empty:
            return None
        return float(before["close"].iloc[-1])

    def run(self) -> dict:
        """Run the fast backtest. Returns performance metrics."""
        dates = pd.date_range(self.p.BACKTEST_START, self.p.BACKTEST_END, freq="B")
        cash = float(self.p.BACKTEST_INITIAL_CASH)
        positions = {t: {"long": 0, "short": 0, "long_cost_basis": 0.0, "short_cost_basis": 0.0} for t in self.tickers}
        margin_req = self.p.BACKTEST_MARGIN_REQ

        if len(dates) > 0:
            self.portfolio_values = [{"date": dates[0], "value": cash}]
        else:
            self.portfolio_values = []

        for current_date in dates:
            date_str = current_date.strftime("%Y-%m-%d")

            # Get current prices
            current_prices = {}
            skip = False
            for t in self.tickers:
                p = self._get_close_price(t, date_str)
                if p is None or p <= 0:
                    skip = True
                    break
                current_prices[t] = p
            if skip:
                continue

            # Compute total portfolio value
            total_value = cash
            for t in self.tickers:
                total_value += positions[t]["long"] * current_prices[t]
                total_value -= positions[t]["short"] * current_prices[t]

            # Gather signals for each ticker
            for t in self.tickers:
                # Recompute technical signals with current params
                price_df = self._get_price_slice(t, date_str)
                if price_df.empty:
                    continue
                tech_signal = compute_technical_signals(price_df, self.p)

                # Collect all signals: technical (recomputed) + cached LLM agents
                all_signals = {"technical_analyst_agent": tech_signal}
                if self.signals_cache and date_str in self.signals_cache:
                    for agent_id, agent_signals in self.signals_cache[date_str].items():
                        if agent_id == "technical_analyst_agent":
                            continue  # we recomputed this
                        if t in agent_signals:
                            all_signals[agent_id] = agent_signals[t]

                # Weighted aggregation: score = sum(signal * weight * confidence) / sum(weight)
                # Confidence DAMPENS the score (low-confidence signals contribute less)
                sig_map = {"bullish": 1, "neutral": 0, "bearish": -1}
                w_sum = 0.0
                w_total = 0.0
                avg_conf = 0.0
                n_signals = 0
                for agent_id, sig_data in all_signals.items():
                    sig_val = sig_map.get(sig_data.get("signal", "neutral"), 0)
                    conf = sig_data.get("confidence", 50)
                    if isinstance(conf, (int, float)) and conf > 1:
                        conf = conf / 100.0  # normalize 0-100 to 0-1
                    conf = max(0.0, min(1.0, conf))
                    agent_weight = self.p.ANALYST_WEIGHTS.get(agent_id, 1.0)
                    conf_adjusted = conf ** self.p.CONFIDENCE_POWER
                    w_sum += sig_val * agent_weight * conf_adjusted
                    w_total += agent_weight
                    avg_conf += conf
                    n_signals += 1

                weighted_score = w_sum / w_total if w_total > 0 else 0.0
                confidence = (avg_conf / n_signals * 100) if n_signals > 0 else 0.0

                # Risk management: compute position limits
                ann_vol = self._estimate_volatility(t, date_str)
                vol_limit = compute_vol_adjusted_limit(ann_vol, self.p)
                position_limit = total_value * vol_limit
                current_pos_value = abs(positions[t]["long"] - positions[t]["short"]) * current_prices[t]
                remaining_limit = max(0, position_limit - current_pos_value)
                max_shares = int(min(remaining_limit, cash) / current_prices[t]) if current_prices[t] > 0 else 0

                # Deterministic portfolio decision
                decision = deterministic_portfolio_decision(
                    ticker=t,
                    weighted_score=weighted_score,
                    confidence=confidence,
                    max_shares=max_shares,
                    current_long=positions[t]["long"],
                    current_short=positions[t]["short"],
                    params=self.p,
                )

                # Execute trade
                action = decision["action"]
                qty = decision["quantity"]
                cash, positions = self._execute(t, action, qty, current_prices[t], cash, positions, margin_req)

            # Record portfolio value
            total_value = cash
            for t in self.tickers:
                total_value += positions[t]["long"] * current_prices[t]
                total_value -= positions[t]["short"] * current_prices[t]
            self.portfolio_values.append({"date": current_date, "value": total_value})

        return self._compute_metrics()

    def _estimate_volatility(self, ticker: str, date_str: str) -> float:
        df = self._get_price_slice(ticker, date_str, lookback_days=self.p.VOLATILITY_LOOKBACK_DAYS + 10)
        if df.empty or len(df) < 5:
            return 0.25
        returns = df["close"].pct_change().dropna()
        if len(returns) < 2:
            return 0.25
        daily_vol = returns.tail(self.p.VOLATILITY_LOOKBACK_DAYS).std()
        return float(daily_vol * np.sqrt(252)) if not np.isnan(daily_vol) else 0.25

    def _execute(self, ticker, action, qty, price, cash, positions, margin_req) -> tuple:
        if qty <= 0:
            return cash, positions
        pos = positions[ticker]
        if action == "buy":
            cost = qty * price
            if cost <= cash:
                old = pos["long"]
                old_cb = pos["long_cost_basis"]
                new_total = old + qty
                if new_total > 0:
                    pos["long_cost_basis"] = (old_cb * old + cost) / new_total
                pos["long"] = new_total
                cash -= cost
            else:
                max_q = int(cash / price) if price > 0 else 0
                if max_q > 0:
                    cost = max_q * price
                    old = pos["long"]
                    old_cb = pos["long_cost_basis"]
                    new_total = old + max_q
                    if new_total > 0:
                        pos["long_cost_basis"] = (old_cb * old + cost) / new_total
                    pos["long"] = new_total
                    cash -= cost
        elif action == "sell":
            qty = min(qty, pos["long"])
            if qty > 0:
                cash += qty * price
                pos["long"] -= qty
                if pos["long"] == 0:
                    pos["long_cost_basis"] = 0.0
        elif action == "short":
            proceeds = qty * price
            margin_needed = proceeds * margin_req
            if margin_needed <= cash:
                pos["short"] += qty
                cash += proceeds - margin_needed
        elif action == "cover":
            qty = min(qty, pos["short"])
            if qty > 0:
                cost = qty * price
                cash -= cost
                pos["short"] -= qty
        return cash, positions

    def _compute_metrics(self) -> dict:
        if len(self.portfolio_values) < 3:
            return {"sharpe_ratio": 0.0, "sortino_ratio": 0.0, "max_drawdown": 0.0, "total_return_pct": 0.0}

        values = [p["value"] for p in self.portfolio_values]
        returns = pd.Series(values).pct_change().dropna()
        if len(returns) < 2:
            return {"sharpe_ratio": 0.0, "sortino_ratio": 0.0, "max_drawdown": 0.0, "total_return_pct": 0.0}

        daily_rf = 0.0434 / 252
        excess = returns - daily_rf
        mean_ex = excess.mean()
        std_ex = excess.std()

        sharpe = float(np.sqrt(252) * mean_ex / std_ex) if std_ex > 1e-12 else 0.0
        downside = np.minimum(excess, 0)
        dd_std = float(np.sqrt(np.mean(downside ** 2)))
        sortino = float(np.sqrt(252) * mean_ex / dd_std) if dd_std > 1e-12 else 0.0

        cummax = pd.Series(values).cummax()
        drawdown = (pd.Series(values) - cummax) / cummax
        max_dd = float(drawdown.min() * 100)

        total_ret = (values[-1] / values[0] - 1) * 100 if values[0] > 0 else 0.0

        return {
            "sharpe_ratio": round(sharpe, 4),
            "sortino_ratio": round(sortino, 4),
            "max_drawdown": round(max_dd, 2),
            "total_return_pct": round(total_ret, 2),
        }
