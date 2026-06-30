import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional
from src.tools.api import get_prices, prices_to_df
from app.backend.portfolio.ticker_normalizer import normalize_ticker

logger = logging.getLogger(__name__)


def _fetch_yfinance_prices(ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Fallback: fetch price data from Yahoo Finance via yfinance."""
    try:
        import yfinance as yf
        data = yf.download(ticker, start=start_date, end=end_date, progress=False, auto_adjust=True)
        if data.empty:
            return pd.DataFrame()
        df = data.reset_index()
        df.columns = [c[0].lower() if isinstance(c, tuple) else c.lower() for c in df.columns]
        df = df.rename(columns={"date": "Date"})
        df["Date"] = pd.to_datetime(df["Date"])
        df.set_index("Date", inplace=True)
        numeric_cols = ["open", "close", "high", "low", "volume"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        df.sort_index(inplace=True)
        return df
    except Exception as e:
        logger.warning("yfinance fallback failed for %s: %s", ticker, e)
        return pd.DataFrame()


def _is_gbp_pence_ticker(analysis_ticker: str) -> bool:
    """Yahoo Finance returns LSE-listed prices in GBp (pence). Detect these."""
    return analysis_ticker.upper().endswith(".L")


def compute_indicators(ticker: str, api_key: Optional[str] = None) -> dict:
    """
    Compute current price, RSI-14, SMA-20, SMA-50, and trend for a ticker.
    Returns a dict with keys: current_price, rsi_14, sma_20, sma_50, trend.
    """
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=120)).strftime("%Y-%m-%d")

    analysis_ticker, supported = normalize_ticker(ticker)

    df = pd.DataFrame()
    used_yfinance = False

    if supported:
        prices = get_prices(ticker=analysis_ticker, start_date=start_date, end_date=end_date, api_key=api_key)
        if prices:
            df = prices_to_df(prices)

    # Fallback to yfinance if primary source returned nothing
    if df.empty or len(df) < 14:
        yf_ticker = analysis_ticker
        df = _fetch_yfinance_prices(yf_ticker, start_date, end_date)
        if not df.empty:
            used_yfinance = True

    if df.empty or len(df) < 14:
        return {}

    # Yahoo Finance returns LSE prices in GBp (pence) — convert to GBP
    if used_yfinance and _is_gbp_pence_ticker(analysis_ticker):
        for col in ["open", "close", "high", "low"]:
            if col in df.columns:
                df[col] = df[col] / 100.0

    # Defensive: if prices from src.tools.api still look like pence for .L tickers
    # (e.g. ISF.L showing 800+ instead of ~8), apply conversion
    if not used_yfinance and _is_gbp_pence_ticker(analysis_ticker):
        sample_price = float(df["close"].iloc[-1])
        if sample_price > 100:
            for col in ["open", "close", "high", "low"]:
                if col in df.columns:
                    df[col] = df[col] / 100.0

    close = df["close"]
    current_price = float(close.iloc[-1])
    rsi_14 = _calculate_rsi(close, 14)
    sma_20 = float(close.rolling(20).mean().iloc[-1]) if len(close) >= 20 else None
    sma_50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else None
    trend = _determine_trend(close, sma_20, sma_50)

    return {
        "current_price": round(current_price, 4),
        "rsi_14": round(rsi_14, 2) if rsi_14 is not None else None,
        "sma_20": round(sma_20, 4) if sma_20 is not None else None,
        "sma_50": round(sma_50, 4) if sma_50 is not None else None,
        "trend": trend,
    }


def determine_action_label(rsi: Optional[float], trend: Optional[str]) -> str:
    """
    Map indicators to educational action labels.
    NOT financial advice — purely educational.
    """
    if rsi is None or trend is None:
        return "WATCH"

    if trend == "up" and rsi < 70:
        return "HOLD"
    elif trend == "up" and rsi >= 70:
        return "REVIEW"
    elif trend == "down" and rsi > 30:
        return "REVIEW"
    elif trend == "down" and rsi <= 30:
        return "ADD CAUTIOUSLY"
    else:
        return "WATCH"


def compute_risk_score(rsi: Optional[float], trend: Optional[str],
                       profit_loss_pct: Optional[float]) -> Optional[int]:
    """
    Compute a risk score from 1 (low risk) to 10 (high risk).
    Based on RSI extremes, trend direction, and drawdown from cost basis.
    Educational only.
    """
    if rsi is None and trend is None:
        return None

    score = 5  # neutral baseline

    # RSI contribution: extremes add risk
    if rsi is not None:
        if rsi > 80:
            score += 3
        elif rsi > 70:
            score += 2
        elif rsi < 20:
            score += 2
        elif rsi < 30:
            score += 1
        elif 40 <= rsi <= 60:
            score -= 1

    # Trend contribution
    if trend == "down":
        score += 2
    elif trend == "sideways":
        score += 1
    elif trend == "up":
        score -= 1

    # Loss magnitude contribution
    if profit_loss_pct is not None:
        if profit_loss_pct < -30:
            score += 2
        elif profit_loss_pct < -15:
            score += 1
        elif profit_loss_pct > 50:
            score += 1  # concentration risk from large gains

    return max(1, min(10, score))


def _calculate_rsi(close: pd.Series, period: int = 14) -> Optional[float]:
    if len(close) < period + 1:
        return None
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta.where(delta < 0, 0.0))
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    val = rsi.iloc[-1]
    if pd.isna(val):
        return None
    return float(val)


def _determine_trend(close: pd.Series, sma_20: Optional[float], sma_50: Optional[float]) -> str:
    current = float(close.iloc[-1])
    if sma_20 is not None and sma_50 is not None:
        if current > sma_20 > sma_50:
            return "up"
        elif current < sma_20 < sma_50:
            return "down"
    elif sma_20 is not None:
        if current > sma_20:
            return "up"
        elif current < sma_20:
            return "down"
    return "sideways"
