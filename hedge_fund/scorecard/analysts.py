"""Analyst scorecard — grade every alpha model on what happened next.

A view is judged at the analyst's own horizon: the number of trading days
the model declared its view plays out over (`AlphaModel.horizon_days`,
stamped on every `Signal`). A value investor's call is graded a year on; an
earnings-drift model's at the weeks before the next print. A view whose
horizon the ledger has not reached yet is pending: counted, not graded.
Two measures, from two kinds of shop:

- Hit rate and slugging, the discretionary desk's pair, on the return in
  excess of the benchmark: a long-only analyst in a bull market must not
  score for free.
- IC, the quant desk's number: on each date, the Spearman rank correlation
  between the analyst's convictions and the raw forward returns across the
  names it viewed. Ranking within a date cancels the market by itself. The
  per-date ICs form a series; its mean, spread and t-stat say whether the
  skill is real or noise.

Only the decisions on session records count. The refreshed assessment
`execute_decision` makes across a calendar gap re-asks the same analysts
with no new close, its `as_of` is not a session, and the sleeves already
rest on it through `final_contribution` — scoring it would double-weight
every Friday view of a daily fund.

The ledger records every session, so N trading days on is N session dates
on. A minute fund's sessions are bars; its day is the date part, and a
view is graded at the last bar of the target day. The assessment marks a
minute fund at the day's close, so a bar never prices a view from its
decision marks (`SessionRecord.price_at`): a view at a bar is graded only
when the name has an exact print at both bars, held or targeted.

A view recorded before horizons existed carries none; it is graded at the
horizon its model declares today.
"""

from __future__ import annotations

from math import sqrt

import numpy as np

from hedge_fund.pipeline.session import SessionRecord
from hedge_fund.scorecard.models import AnalystScore
from hedge_fund.signals import get_horizon_days

# A date's IC needs this many ranked names to mean anything at all.
_MIN_VIEWS_PER_DATE = 3


def score_analysts(records: list[SessionRecord]) -> list[AnalystScore]:
    """One score per analyst that gave a view in any decision, sorted by
    name. A persona staffed into two strategies is asked twice per decision
    and counted once."""
    dates = sorted({r.session[:10] for r in records})
    day_index = {day: i for i, day in enumerate(dates)}
    last_record_of: dict[str, SessionRecord] = {}
    for record in records:
        last_record_of[record.session[:10]] = record
    # analyst -> (session, conviction, forward return, excess return)
    views: dict[str, list[tuple[str, float, float, float]]] = {}
    abstained: dict[str, int] = {}
    pending: dict[str, int] = {}
    horizons: dict[str, int] = {}
    for current in records:
        if current.decision is None:
            continue
        seen: set[tuple[str, str]] = set()
        for strategy in current.decision.strategies:
            for signal in strategy.signals:
                key = (signal.model_name, signal.ticker)
                if key in seen:
                    continue
                seen.add(key)
                name = signal.model_name
                horizon = signal.horizon_days if signal.horizon_days is not None else get_horizon_days(name)
                horizons.setdefault(name, horizon)
                if signal.metadata.get("abstained") is True:
                    abstained[name] = abstained.get(name, 0) + 1
                    continue
                target_index = day_index[current.session[:10]] + horizon
                if target_index >= len(dates):
                    pending[name] = pending.get(name, 0) + 1
                    continue
                target = last_record_of[dates[target_index]]
                price_now = current.price_at(signal.ticker)
                price_next = target.price_at(signal.ticker)
                if price_now is None or price_next is None:
                    continue
                forward = price_next / price_now - 1
                benchmark_return = target.benchmark_close / current.benchmark_close - 1
                views.setdefault(name, []).append(
                    (current.session, signal.value, forward, forward - benchmark_return)
                )
    return [
        _score(name, horizons[name], views.get(name, []), abstained.get(name, 0), pending.get(name, 0))
        for name in sorted(horizons)
    ]


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _score(
    name: str, horizon_days: int, views: list[tuple[str, float, float, float]],
    n_abstained: int, n_pending: int,
) -> AnalystScore:
    directional = [(value, excess) for _, value, _, excess in views if value != 0]
    hits = [abs(excess) for value, excess in directional if excess != 0 and (value > 0) == (excess > 0)]
    misses = [abs(excess) for value, excess in directional if excess == 0 or (value > 0) != (excess > 0)]
    hit_rate = len(hits) / len(directional) if directional else None
    slugging = None
    if hits and misses and sum(misses) > 0:
        slugging = (sum(hits) / len(hits)) / (sum(misses) / len(misses))

    by_date: dict[str, list[tuple[float, float]]] = {}
    for session, value, forward, _ in views:
        by_date.setdefault(session, []).append((value, forward))
    ics: list[float] = []
    for pairs in by_date.values():
        if len(pairs) < _MIN_VIEWS_PER_DATE:
            continue
        ic = _spearman(np.array([v for v, _ in pairs]), np.array([f for _, f in pairs]))
        if ic is not None:
            ics.append(ic)
    ic_mean = float(np.mean(ics)) if ics else None
    ic_std = float(np.std(ics, ddof=1)) if len(ics) >= 2 else None
    ic_t_stat = ic_mean / ic_std * sqrt(len(ics)) if ic_std else None

    return AnalystScore(
        name=name, horizon_days=horizon_days,
        n_views=len(views), n_directional=len(directional), n_abstained=n_abstained, n_pending=n_pending,
        hit_rate=hit_rate, slugging=slugging,
        ic_mean=ic_mean, ic_std=ic_std, ic_t_stat=ic_t_stat, n_dates=len(ics),
    )


def _spearman(x: np.ndarray, y: np.ndarray) -> float | None:
    """Pearson correlation of the average ranks. None with fewer than three
    points or when either side has no variance to rank."""
    if len(x) < _MIN_VIEWS_PER_DATE:
        return None
    rx = _average_ranks(x)
    ry = _average_ranks(y)
    dx = rx - rx.mean()
    dy = ry - ry.mean()
    denominator = sqrt(float((dx * dx).sum()) * float((dy * dy).sum()))
    if denominator == 0:
        return None
    return float((dx * dy).sum() / denominator)


def _average_ranks(values: np.ndarray) -> np.ndarray:
    """1-based ranks; a tie group shares the mean of the positions it spans."""
    _, inverse, counts = np.unique(values, return_inverse=True, return_counts=True)
    last_position = np.cumsum(counts)
    return (last_position - (counts - 1) / 2)[inverse]
