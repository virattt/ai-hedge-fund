"""Analyst scorecard — grade every alpha model on what happened next.

A view is judged over the fund's own horizon: from the decision it was part
of to the next decision. That is the period the fund acted on it. Two
measures, from two kinds of shop:

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

A minute fund's assessment is marked at the day's close, so a bar never
prices a view from its decision marks (`SessionRecord.price_at`). A view at
a bar is scored only when the name has an exact print at both bars: held or
targeted. Never-targeted names and the first bar drop out.
"""

from __future__ import annotations

from math import sqrt

import numpy as np

from hedge_fund.pipeline.session import SessionRecord
from hedge_fund.scorecard.models import AnalystScore

# A date's IC needs this many ranked names to mean anything at all.
_MIN_VIEWS_PER_DATE = 3


def score_analysts(records: list[SessionRecord]) -> list[AnalystScore]:
    """One score per analyst that gave a view in a decision followed by
    another decision, sorted by name. A persona staffed into two strategies
    is asked twice per decision and counted once."""
    decided = [r for r in records if r.decision is not None]
    # analyst -> (session, conviction, forward return, excess return)
    views: dict[str, list[tuple[str, float, float, float]]] = {}
    abstained: dict[str, int] = {}
    for current, following in zip(decided, decided[1:]):
        benchmark_return = following.benchmark_close / current.benchmark_close - 1
        seen: set[tuple[str, str]] = set()
        for strategy in current.decision.strategies:
            for signal in strategy.signals:
                key = (signal.model_name, signal.ticker)
                if key in seen:
                    continue
                seen.add(key)
                if signal.metadata.get("abstained") is True:
                    abstained[signal.model_name] = abstained.get(signal.model_name, 0) + 1
                    continue
                price_now = current.price_at(signal.ticker)
                price_next = following.price_at(signal.ticker)
                if price_now is None or price_next is None:
                    continue
                forward = price_next / price_now - 1
                views.setdefault(signal.model_name, []).append(
                    (current.session, signal.value, forward, forward - benchmark_return)
                )
    names = sorted(set(views) | set(abstained))
    return [_score(name, views.get(name, []), abstained.get(name, 0)) for name in names]


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _score(name: str, views: list[tuple[str, float, float, float]], n_abstained: int) -> AnalystScore:
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
        name=name, n_views=len(views), n_directional=len(directional), n_abstained=n_abstained,
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
