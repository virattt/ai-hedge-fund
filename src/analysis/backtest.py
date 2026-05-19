"""Multi-horizon backtest of the technical recommendation engine.

For each historical date (1M / 3M / 6M / 1Y ago), we ask: if we had run the
same technical signal logic on data available only up to that date, what
verdict would we have produced? And, knowing what happened next, was the
verdict directionally correct?

This is deliberately TECHNICAL-only — yfinance's `.info` only gives current
fundamental ratios, so backtesting fundamental verdicts would be unreliable.
The technical indicators (RSI, MACD, SMAs, Bollinger, volume) are exactly
reproducible at any historical date from the price/volume series we
already hold.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from src.analysis import indicators as ind
from src.analysis.verdicts import (
    IndicatorRow,
    Verdict,
    aggregate_verdict,
    signal_bollinger,
    signal_macd,
    signal_rsi,
    signal_volume,
    signal_vs_sma,
)


@dataclass
class BacktestPoint:
    label: str                       # "1M ago", "3M ago", "6M ago", "1Y ago"
    as_of_date: str                  # YYYY-MM-DD
    price_then: float
    price_now: float
    realized_return: float           # decimal, e.g. 0.082 = +8.2%
    spx_return: Optional[float]
    alpha: Optional[float]           # ticker_return - spx_return
    technical_verdict: Verdict       # the verdict we would have produced then
    technical_confidence: float      # 0-1
    indicator_signals: list[IndicatorRow] = field(default_factory=list)
    correct: Optional[bool] = None   # did the verdict direction match actual return?


@dataclass
class BacktestSummary:
    points: list[BacktestPoint] = field(default_factory=list)
    hit_count: int = 0
    miss_count: int = 0
    na_count: int = 0
    avg_alpha: Optional[float] = None  # mean alpha when verdict was BUY

    @property
    def hit_rate(self) -> Optional[float]:
        total = self.hit_count + self.miss_count
        return self.hit_count / total if total > 0 else None


def _signals_at(
    close: pd.Series, volume: pd.Series, idx: int
) -> tuple[Verdict, float, list[IndicatorRow]]:
    """Compute the 6 technical signals using price/volume data up to (and
    including) the given DataFrame index position. Returns (aggregate
    verdict, confidence, list of indicator rows)."""
    close_slice = close.iloc[: idx + 1]
    vol_slice = volume.iloc[: idx + 1]
    if len(close_slice) < 200:
        return "N/A", 0.0, []

    price = float(close_slice.iloc[-1])

    rsi_val = float(ind.rsi(close_slice, 14).iloc[-1])
    macd_line, sig_line, hist = ind.macd(close_slice)
    macd_v = float(macd_line.iloc[-1])
    sig_v = float(sig_line.iloc[-1])
    hist_v = float(hist.iloc[-1])

    sma50_series = ind.sma(close_slice, 50)
    sma200_series = ind.sma(close_slice, 200)
    sma50 = float(sma50_series.iloc[-1])
    sma200 = float(sma200_series.iloc[-1])
    sma200_slope = None
    if len(sma200_series.dropna()) >= 21:
        sma200_slope = float(sma200_series.iloc[-1] - sma200_series.iloc[-21])

    bb_low, _bb_mid, bb_up = ind.bollinger(close_slice, 20, 2.0)
    bb_low_v = float(bb_low.iloc[-1])
    bb_up_v = float(bb_up.iloc[-1])

    pct_today = (
        float(close_slice.iloc[-1] / close_slice.iloc[-2] - 1)
        if len(close_slice) >= 2
        else 0.0
    )
    rel_vol = ind.relative_volume(vol_slice, 50)

    rows: list[IndicatorRow] = []

    def _ind(name: str, state: str, sig_result: tuple[Verdict, str]) -> None:
        rows.append(IndicatorRow(name=name, state=state, signal=sig_result[0], rationale=sig_result[1]))

    _ind("RSI (14)", f"{rsi_val:.1f}", signal_rsi(rsi_val))
    _ind(
        "MACD",
        f"MACD {macd_v:.3f} / Signal {sig_v:.3f} / Hist {hist_v:+.3f}",
        signal_macd(macd_v, sig_v, hist_v),
    )
    _ind(
        "Price vs SMA 50",
        f"${price:.2f} vs ${sma50:.2f}",
        signal_vs_sma(price, sma50, None),
    )
    _ind(
        "Price vs SMA 200",
        f"${price:.2f} vs ${sma200:.2f}"
        + (f" (slope {sma200_slope:+.2f})" if sma200_slope is not None else ""),
        signal_vs_sma(price, sma200, sma200_slope),
    )
    _ind(
        "Bollinger Bands",
        f"low ${bb_low_v:.2f} / up ${bb_up_v:.2f}",
        signal_bollinger(price, bb_low_v, bb_up_v),
    )
    _ind(
        "Volume vs 50d avg",
        f"{rel_vol:.2f}x",
        signal_volume(rel_vol, pct_today),
    )

    v, conf = aggregate_verdict(rows, key="signal")
    return v, conf, rows


def run_backtest(
    close: pd.Series, volume: pd.Series, spx_close: Optional[pd.Series] = None
) -> BacktestSummary:
    """Backtest the technical verdict at 1M / 3M / 6M / 1Y ago and compare
    to actual realized return.

    Args:
        close:  Adjusted close series, oldest -> newest.
        volume: Volume series, same index.
        spx_close: Optional S&P 500 close series for alpha computation.
    """
    summary = BacktestSummary()
    if len(close) < 252 + 200:
        return summary

    horizons = [
        ("1M ago", 21),
        ("3M ago", 63),
        ("6M ago", 126),
        ("1Y ago", 252),
    ]

    alphas_for_buys: list[float] = []

    for label, days_back in horizons:
        if len(close) <= days_back + 200:
            continue
        idx = len(close) - 1 - days_back
        as_of = close.index[idx]
        as_of_str = as_of.strftime("%Y-%m-%d") if hasattr(as_of, "strftime") else str(as_of)
        price_then = float(close.iloc[idx])
        price_now = float(close.iloc[-1])
        realized = price_now / price_then - 1.0

        spx_ret: Optional[float] = None
        alpha: Optional[float] = None
        if spx_close is not None and len(spx_close) > days_back:
            try:
                spx_then = float(spx_close.iloc[-1 - days_back])
                spx_now = float(spx_close.iloc[-1])
                spx_ret = spx_now / spx_then - 1.0
                alpha = realized - spx_ret
            except Exception:
                spx_ret = None
                alpha = None

        verdict, conf, rows = _signals_at(close, volume, idx)

        correct: Optional[bool] = None
        if verdict in ("BUY", "STRONG BUY"):
            correct = realized > 0
            if correct:
                summary.hit_count += 1
            else:
                summary.miss_count += 1
            if alpha is not None:
                alphas_for_buys.append(alpha)
        elif verdict in ("SELL", "REDUCE"):
            correct = realized < 0
            if correct:
                summary.hit_count += 1
            else:
                summary.miss_count += 1
        elif verdict == "HOLD":
            correct = abs(realized) < 0.15  # ±15% counts as a successful HOLD
            if correct:
                summary.hit_count += 1
            else:
                summary.miss_count += 1
        else:
            summary.na_count += 1

        summary.points.append(
            BacktestPoint(
                label=label,
                as_of_date=as_of_str,
                price_then=price_then,
                price_now=price_now,
                realized_return=realized,
                spx_return=spx_ret,
                alpha=alpha,
                technical_verdict=verdict,
                technical_confidence=conf,
                indicator_signals=rows,
                correct=correct,
            )
        )

    if alphas_for_buys:
        summary.avg_alpha = sum(alphas_for_buys) / len(alphas_for_buys)

    return summary
