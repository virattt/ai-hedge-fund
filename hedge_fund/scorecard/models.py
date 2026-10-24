"""What the scorecard says: one row per analyst, one per strategy, and the
fund's P&L those rows are measured against."""

from __future__ import annotations

from pydantic import BaseModel, computed_field


class AnalystScore(BaseModel):
    """How one alpha model's views held up over the fund's own horizon.

    Every rate carries its count so a hit rate from twelve calls reads as
    the noise it is. `None` means there was nothing to measure."""

    name: str
    n_views: int                      # non-abstained views with a forward return
    n_directional: int                # views with a nonzero conviction
    n_abstained: int
    hit_rate: float | None            # directional views whose sign matched the excess return
    slugging: float | None            # mean gain on hits / mean loss on misses
    ic_mean: float | None             # mean of the per-date rank correlations
    ic_std: float | None
    ic_t_stat: float | None           # ic_mean / ic_std * sqrt(n_dates)
    n_dates: int                      # dates that produced an IC


class StrategyScore(BaseModel):
    """What one strategy's sleeve earned, period by period, between executions."""

    name: str
    n_periods: int
    pnl: float                        # dollars attributed
    return_pct: float                 # compounded period returns
    win_rate: float | None            # periods with a positive return; flat is not a win
    share_of_pnl: float | None        # pnl / fund_pnl; None when the fund made nothing
    max_drawdown_pct: float           # peak-to-trough of the sleeve's compounded curve


class Scorecard(BaseModel):
    fund: str
    first_session: str
    last_session: str
    horizon: str | None               # the fund's cadence: the period every view is judged over
    analysts: list[AnalystScore]
    strategies: list[StrategyScore]
    fund_pnl: float                   # pre-fill equity, last execution minus first
    trading_cost: float               # spread and commission paid inside that window

    @computed_field
    @property
    def unattributed(self) -> float:
        """Fund P&L no sleeve explains: whole-share rounding, cash, and (once
        a cost model exists) trading costs. Reported, never hidden."""
        return self.fund_pnl - sum(s.pnl for s in self.strategies)
