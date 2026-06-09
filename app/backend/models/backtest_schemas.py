"""Pydantic schemas for the backtest replay endpoint."""

from pydantic import BaseModel


class BacktestParamsResponse(BaseModel):
    score_threshold: float
    min_sources: int
    source_filter: str | None
    source_score_threshold: float


class BacktestTriggerResponse(BaseModel):
    ticker: str
    trigger_date: str
    snapshot_score: float
    distinct_sources_at_trigger: int
    signal_sources: list[str]
    holding_period_days: int
    entry_price: float | None = None
    exit_price: float | None = None
    return_pct: float | None = None
    spy_return_pct: float | None = None
    alpha_pct: float | None = None


class BacktestResultResponse(BaseModel):
    mode: str
    lookback_days: int
    hold_days: int
    params: BacktestParamsResponse
    total_triggers: int
    triggers_with_returns: int
    win_rate_pct: float | None
    avg_return_pct: float | None
    median_return_pct: float | None
    avg_alpha_pct: float | None
    best_return_pct: float | None
    worst_return_pct: float | None
    snapshot_count_in_window: int
    distinct_tickers_in_window: int
    triggers: list[BacktestTriggerResponse]
