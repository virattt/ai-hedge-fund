"""Backtest replay — evaluates current alert rule thresholds against the
historical discovery_snapshots table to validate whether the system actually
picks winners.

Replay modes:
  - score_threshold:    triggers when composite score ≥ N
  - high_confluence:    triggers when distinct_sources ≥ N AND score ≥ M
                        (mimics the current high_confluence alert rule)
  - source_threshold:   triggers when any signal from a chosen source
                        contributed ≥ X to the composite score

Each ticker triggers at most once per backtest run — the EARLIEST snapshot in
the lookback window that passes the rule. We then compute the ticker's return
and SPY-relative alpha over the hold period via the existing pricing_service.

When discovery_snapshots is sparse (e.g. <30 days of history), results will be
correspondingly thin. The endpoint still returns; the UI surfaces the empty
state.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from statistics import median

from sqlalchemy import asc
from sqlalchemy.orm import Session

from app.backend.database import SessionLocal
from app.backend.database.models import DiscoverySnapshot

logger = logging.getLogger(__name__)

MODE_SCORE_THRESHOLD = "score_threshold"
MODE_HIGH_CONFLUENCE = "high_confluence"
MODE_SOURCE_THRESHOLD = "source_threshold"
_VALID_MODES = {MODE_SCORE_THRESHOLD, MODE_HIGH_CONFLUENCE, MODE_SOURCE_THRESHOLD}


@dataclass
class BacktestParams:
    """Threshold inputs for one backtest run."""
    score_threshold: float = 60.0
    min_sources: int = 4
    source_filter: str | None = None
    source_score_threshold: float = 20.0


@dataclass
class BacktestTrigger:
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


@dataclass
class BacktestResult:
    mode: str
    lookback_days: int
    hold_days: int
    params: BacktestParams
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
    triggers: list[BacktestTrigger] = field(default_factory=list)


def _signal_sources(signals_json: object) -> list[str]:
    if not signals_json or not isinstance(signals_json, list):
        return []
    out: list[str] = []
    for s in signals_json:
        if isinstance(s, dict):
            src = s.get("source")
            if isinstance(src, str):
                out.append(src)
    return out


def _source_max_score(signals_json: object, source: str) -> float:
    """Highest score contribution from a specific source within one snapshot."""
    if not signals_json or not isinstance(signals_json, list):
        return 0.0
    best = 0.0
    for s in signals_json:
        if isinstance(s, dict) and s.get("source") == source:
            score = s.get("score") or 0
            try:
                score_f = float(score)
            except (TypeError, ValueError):
                continue
            if score_f > best:
                best = score_f
    return best


def _evaluate(row: DiscoverySnapshot, mode: str, params: BacktestParams) -> bool:
    if mode == MODE_SCORE_THRESHOLD:
        return row.score is not None and row.score >= params.score_threshold
    if mode == MODE_HIGH_CONFLUENCE:
        if row.score is None or row.score < params.score_threshold:
            return False
        return (row.distinct_sources or 0) >= params.min_sources
    if mode == MODE_SOURCE_THRESHOLD:
        if not params.source_filter:
            return False
        return _source_max_score(row.signals, params.source_filter) >= params.source_score_threshold
    return False


def _coerce_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


async def _compute_trigger_return(trigger: BacktestTrigger) -> None:
    """Populate entry/exit/return/alpha on a trigger by fetching prices."""
    from app.backend.services.pricing_service import get_period_return

    trigger_d = date.fromisoformat(trigger.trigger_date)
    exit_target = trigger_d + timedelta(days=trigger.holding_period_days)
    if exit_target > date.today():
        result = await get_period_return(trigger.ticker, trigger_d)
        if result is not None:
            trigger.entry_price = result.start_price
        return

    ticker_data, spy_data = await asyncio.gather(
        get_period_return(trigger.ticker, trigger_d),
        get_period_return("SPY", trigger_d),
    )
    if ticker_data is None:
        return
    trigger.entry_price = ticker_data.start_price

    # v1 approximation: pricing_service returns end_close = latest available.
    # For triggers whose exit_target ≥ today we end up using "held-to-now"
    # rather than "held for exactly hold_days", which is the right thing to
    # do for the most recent triggers. Future enhancement: per-trigger
    # intermediate-date price lookup.
    trigger.exit_price = ticker_data.end_price
    if ticker_data.start_price > 0:
        trigger.return_pct = (ticker_data.end_price / ticker_data.start_price - 1.0) * 100.0
    if spy_data is not None and spy_data.start_price > 0:
        trigger.spy_return_pct = (spy_data.end_price / spy_data.start_price - 1.0) * 100.0
        if trigger.return_pct is not None:
            trigger.alpha_pct = trigger.return_pct - trigger.spy_return_pct


def _load_snapshots(db: Session, lookback_days: int) -> list[DiscoverySnapshot]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    rows = (
        db.query(DiscoverySnapshot)
        .filter(DiscoverySnapshot.snapshot_at >= cutoff)
        .filter(DiscoverySnapshot.is_ticker == True)  # noqa: E712 - SQLAlchemy comparison
        .order_by(asc(DiscoverySnapshot.snapshot_at))
        .all()
    )
    return rows


async def run_backtest(
    mode: str,
    score_threshold: float = 60.0,
    min_sources: int = 4,
    source_filter: str | None = None,
    source_score_threshold: float = 20.0,
    lookback_days: int = 90,
    hold_days: int = 30,
) -> BacktestResult:
    if mode not in _VALID_MODES:
        raise ValueError(f"Unknown mode {mode!r}; expected one of {sorted(_VALID_MODES)}")
    if mode == MODE_SOURCE_THRESHOLD and not source_filter:
        raise ValueError("source_threshold mode requires source_filter parameter")

    params = BacktestParams(
        score_threshold=score_threshold,
        min_sources=min_sources,
        source_filter=source_filter,
        source_score_threshold=source_score_threshold,
    )

    db = SessionLocal()
    try:
        rows = _load_snapshots(db, lookback_days)
    finally:
        db.close()

    snapshot_count = len(rows)
    distinct_tickers = len({r.ticker for r in rows})

    first_trigger_per_ticker: dict[str, BacktestTrigger] = {}
    for row in rows:
        ticker = (row.ticker or "").upper()
        if not ticker or ticker in first_trigger_per_ticker:
            continue
        if not _evaluate(row, mode, params):
            continue
        trigger_at = _coerce_aware(row.snapshot_at) if row.snapshot_at else None
        if trigger_at is None:
            continue
        first_trigger_per_ticker[ticker] = BacktestTrigger(
            ticker=ticker,
            trigger_date=trigger_at.date().isoformat(),
            snapshot_score=float(row.score or 0),
            distinct_sources_at_trigger=int(row.distinct_sources or 0),
            signal_sources=_signal_sources(row.signals),
            holding_period_days=hold_days,
        )

    triggers = list(first_trigger_per_ticker.values())
    if triggers:
        await asyncio.gather(*(_compute_trigger_return(t) for t in triggers), return_exceptions=True)

    realised = [t for t in triggers if t.return_pct is not None]
    win_rate: float | None = None
    avg_return: float | None = None
    median_return: float | None = None
    avg_alpha: float | None = None
    best_return: float | None = None
    worst_return: float | None = None
    if realised:
        returns = [t.return_pct for t in realised if t.return_pct is not None]
        alphas = [t.alpha_pct for t in realised if t.alpha_pct is not None]
        win_rate = sum(1 for r in returns if r > 0) / len(returns) * 100.0
        avg_return = sum(returns) / len(returns)
        median_return = median(returns)
        if alphas:
            avg_alpha = sum(alphas) / len(alphas)
        best_return = max(returns)
        worst_return = min(returns)

    triggers_sorted = sorted(
        triggers,
        key=lambda t: t.return_pct if t.return_pct is not None else float("-inf"),
        reverse=True,
    )

    return BacktestResult(
        mode=mode,
        lookback_days=lookback_days,
        hold_days=hold_days,
        params=params,
        total_triggers=len(triggers),
        triggers_with_returns=len(realised),
        win_rate_pct=win_rate,
        avg_return_pct=avg_return,
        median_return_pct=median_return,
        avg_alpha_pct=avg_alpha,
        best_return_pct=best_return,
        worst_return_pct=worst_return,
        snapshot_count_in_window=snapshot_count,
        distinct_tickers_in_window=distinct_tickers,
        triggers=triggers_sorted,
    )
