"""Pydantic models for backtesting results."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TradeSignal(BaseModel):
    """A strategy's instruction to enter a position.

    The strategy decides ticker, direction, timing, and holding period.
    The engine handles position sizing, price lookup, and P&L.
    """

    ticker: str
    direction: str                    # "long" or "short"
    entry_date: str                   # YYYY-MM-DD — desired entry, engine snaps to next trading day
    holding_days: int                 # trading days to hold
    metadata: dict[str, Any] = Field(default_factory=dict)  # strategy-specific context


class Trade(BaseModel):
    """A single completed trade — one entry and one exit."""

    ticker: str
    direction: str                    # "long" or "short"
    entry_date: str                   # YYYY-MM-DD
    exit_date: str                    # YYYY-MM-DD
    entry_price: float
    exit_price: float
    shares: float
    pnl: float                        # dollar profit/loss
    return_pct: float                 # percentage return (signed)
    holding_days: int                 # trading days held
    metadata: dict[str, Any] = Field(default_factory=dict)  # strategy-specific context


class PerformanceMetrics(BaseModel):
    """Summary stats for a set of trades."""

    total_return_pct: float
    annualized_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    win_rate: float                   # fraction of trades with positive return
    n_trades: int
    n_long: int
    n_short: int
    avg_return_pct: float
    avg_holding_days: float


class BacktestResult(BaseModel):
    """Top-level result returned by the backtester."""

    trades: list[Trade] = Field(default_factory=list)
    metrics: PerformanceMetrics | None = None
    equity_curve: list[float] = Field(default_factory=list)
