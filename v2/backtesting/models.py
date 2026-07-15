"""Pydantic models for backtesting results."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Trade(BaseModel):
    """A single completed trade — one entry and one exit."""

    ticker: str
    direction: Literal["long", "short"]
    entry_date: str                   # YYYY-MM-DD
    exit_date: str                    # YYYY-MM-DD
    entry_price: float
    exit_price: float
    shares: float
    pnl: float                        # dollar profit/loss
    return_pct: float                 # percentage return (signed)
    holding_days: int                 # trading days held
    reasoning: str | None = None      # why the alpha model opened this (from the Signal)
    metadata: dict[str, Any] = Field(default_factory=dict)  # alpha-model context


class PositionSnapshot(BaseModel):
    """End-of-day mark for one open position."""

    direction: Literal["long", "short"]
    shares: float
    entry_price: float
    market_price: float
    market_value: float               # gross exposure at the current close
    equity_value: float               # capital attributed to the position
    unrealized_pnl: float
    exit_date: str


class PortfolioLedgerEntry(BaseModel):
    """One end-of-day portfolio snapshot used to derive NAV-based metrics."""

    date: str
    cash: float
    positions: dict[str, PositionSnapshot] = Field(default_factory=dict)
    long_market_value: float = 0.0
    short_market_value: float = 0.0
    margin_used: float = 0.0
    gross_exposure: float = 0.0
    net_exposure: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    nav: float


class PerformanceMetrics(BaseModel):
    """Portfolio NAV risk metrics plus completed-trade statistics."""

    total_return_pct: float
    annualized_return_pct: float
    annualized_volatility: float
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
    ledger: list[PortfolioLedgerEntry] = Field(default_factory=list)
