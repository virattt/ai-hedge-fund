"""Scheduler daemon — always-on paper/sim ticks on the market calendar.

The pipeline is one `run_cycle`. This module is the outer loop the cycle
docstring leaves to the caller: poll on an interval, decide whether this
mandate's session is due, and either run the cycle or no-op.

A tick is identified by an idempotency key `{mandate}:{session_date}`.
Session date is the last trading day on or before the clock, taken from
the mandate's benchmark bars — the same grid the backtester uses, so
weekends and holidays fall out of the bars instead of a holiday table.
The mandate's `rebalance` cadence then decides whether that session is
due (daily / last trading day of the ISO week / last trading day of the
month). A period is not closed until the clock has reached Friday (week)
or the last calendar day of the month, so a Thursday poll of a weekly
fund does not fire early.

Double-fire is a no-op: the key store and the newest CycleRecord for
this mandate both count as "already ran this session." A kill-switch
file or `HEDGE_FUND_KILL_SWITCH` env stops new ticks. Venue is paper
or sim only — there is no live exchange on this path.

The loop sleeps through an injected `sleep` so tests never wait on the
wall clock. `evaluate_tick` is the unit the tests (and `--once`) call.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date as _date
from datetime import timedelta
from pathlib import Path
from typing import Callable, Literal, Mapping

from hedge_fund.backtesting.fund import rebalance_grid
from hedge_fund.brokers.paper import PaperBroker
from hedge_fund.brokers.sim import SimBroker
from hedge_fund.data.protocol import DataClient
from hedge_fund.fund.spec import Fund, normalize_universe
from hedge_fund.ledger import (
    broker_for_run,
    latest_run_receipt,
    load_cycle_record,
    save_cycle_record,
)
from hedge_fund.paths import KILL_SWITCH_PATH, TICKS_DIR
from hedge_fund.pipeline.models import CycleRecord
from hedge_fund.pipeline.run_cycle import run_cycle

VENUES = ("paper", "sim")
KILL_SWITCH_ENV = "HEDGE_FUND_KILL_SWITCH"
DEFAULT_INTERVAL_SECONDS = 60.0
DEFAULT_LOOKBACK_DAYS = 40

TickStatus = Literal["ran", "skipped", "halted", "not_due"]
VenueName = Literal["paper", "sim"]


@dataclass(frozen=True)
class TickResult:
    """Outcome of one scheduled evaluation. `record` is set only on `ran`."""

    status: TickStatus
    reason: str
    key: str | None = None
    session_date: str | None = None
    venue: str | None = None
    record: CycleRecord | None = None


@dataclass(frozen=True)
class ScheduleConfig:
    """How often to poll, which venue, and where the kill-switch lives."""

    interval_seconds: float = DEFAULT_INTERVAL_SECONDS
    venue: VenueName = "paper"
    lookback_days: int = DEFAULT_LOOKBACK_DAYS
    kill_switch_path: Path = KILL_SWITCH_PATH
    ticks_dir: Path = TICKS_DIR

    def __post_init__(self) -> None:
        if self.interval_seconds < 0:
            raise ValueError(
                f"interval_seconds must be >= 0, got {self.interval_seconds}"
            )
        if self.venue not in VENUES:
            raise ValueError(
                f"daemon venue must be paper or sim, not {self.venue!r} — "
                "this milestone has no live venue"
            )
        if self.lookback_days < 1:
            raise ValueError(
                f"lookback_days must be >= 1, got {self.lookback_days}"
            )


def tick_key(fund_name: str, session_date: str) -> str:
    """Idempotency key: one completed cycle per mandate + session date."""
    return f"{fund_name}:{session_date}"


def session_date(trading_days: list[str], as_of: str) -> str | None:
    """Last trading day on or before *as_of*, or None if the window is empty."""
    prior = [day for day in trading_days if day <= as_of]
    return prior[-1] if prior else None


def period_closed(session: str, as_of: str, cadence: str) -> bool:
    """True once the clock has reached the end of *session*'s rebalance period.

    Daily sessions are due as soon as they exist. Weekly waits until Friday
    of that ISO week (so a Thursday poll cannot claim the week). Monthly
    waits until the last calendar day of the month.
    """
    if cadence == "daily":
        return True
    start = _date.fromisoformat(session)
    clock = _date.fromisoformat(as_of)
    if cadence == "weekly":
        iso = start.isocalendar()
        friday = _date.fromisocalendar(iso.year, iso.week, 5)
        return clock >= friday
    if cadence == "monthly":
        if start.month == 12:
            last = _date(start.year, 12, 31)
        else:
            last = _date(start.year, start.month + 1, 1) - timedelta(days=1)
        return clock >= last
    raise ValueError(f"unknown rebalance cadence {cadence!r}")


def rebalance_due(trading_days: list[str], session: str, cadence: str) -> bool:
    """True if *session* is a rebalance date on *cadence* given *trading_days*."""
    grid = rebalance_grid(sorted(set(trading_days)), cadence)
    return session in grid


def fetch_trading_days(
    data_client: DataClient,
    benchmark: str,
    as_of: str,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> list[str]:
    """Sorted session dates from *benchmark* bars in the lookback window."""
    start = (_date.fromisoformat(as_of) - timedelta(days=lookback_days)).isoformat()
    bars = data_client.get_prices(benchmark, start, as_of)
    days = sorted({bar.time[:10] for bar in bars if start <= bar.time[:10] <= as_of})
    if not days:
        raise ValueError(
            f"no {benchmark} bars in [{start}, {as_of}] — "
            "cannot build the trading calendar"
        )
    return days


class FileTickStore:
    """Durable idempotency keys: one file per `{mandate}_{session}.tick`."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def seen(self, key: str) -> bool:
        return self._path(key).exists()

    def remember(self, key: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(key + "\n")
        tmp.replace(path)

    def _path(self, key: str) -> Path:
        safe = key.replace("/", "_").replace(":", "_")
        return self.directory / f"{safe}.tick"


class KillSwitch:
    """Halt new ticks when the env is on or the kill file exists.

    Re-reads both on every `active()` call so a `touch` mid-loop is seen
    on the next evaluation without restarting the process.
    """

    def __init__(
        self,
        path: Path | None = KILL_SWITCH_PATH,
        environ: Mapping[str, str] | None = None,
    ) -> None:
        self.path = path
        self.environ = environ if environ is not None else os.environ

    def active(self) -> bool:
        if _env_is_on(self.environ.get(KILL_SWITCH_ENV, "")):
            return True
        return self.path is not None and self.path.exists()


def _env_is_on(raw: str) -> bool:
    value = raw.strip().lower()
    return value not in {"", "0", "false", "no", "off"}


def broker_for_venue(
    venue: str,
    fund_name: str,
    capital: float,
    directory: Path,
) -> tuple[PaperBroker | SimBroker, CycleRecord | None]:
    """Open a paper or sim book, seeded from the newest receipt when one exists."""
    if venue not in VENUES:
        raise ValueError(
            f"daemon venue must be paper or sim, not {venue!r} — "
            "this milestone has no live venue"
        )
    if venue == "paper":
        return broker_for_run(fund_name, capital, directory)
    path = latest_run_receipt(fund_name, directory)
    if path is None:
        return SimBroker(cash=capital), None
    record = load_cycle_record(path, expected_fund=fund_name)
    return SimBroker(cash=record.cash, positions=record.positions), record


def already_completed(
    fund_name: str,
    session: str,
    receipts: Path,
    store: FileTickStore,
) -> bool:
    """True if this mandate already has a tick for *session*.

    The key store is the explicit record. The newest CycleRecord also
    counts — a one-shot CLI paper run for the same session is the same
    tick, so the daemon must not fire again.
    """
    key = tick_key(fund_name, session)
    if store.seen(key):
        return True
    path = latest_run_receipt(fund_name, receipts)
    if path is None:
        return False
    record = load_cycle_record(path, expected_fund=fund_name)
    if record.as_of >= session:
        store.remember(key)
        return True
    return False


def evaluate_tick(
    fund: Fund,
    universe: list[str],
    *,
    as_of: str,
    data_client: DataClient,
    receipts: Path,
    store: FileTickStore,
    kill_switch: KillSwitch,
    venue: str = "paper",
    trading_days: list[str] | None = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> TickResult:
    """One scheduled evaluation. No sleep. Safe to call twice.

    Order: kill-switch, then calendar/cadence, then the idempotency key,
    then `run_cycle`. A halt or a duplicate never touches the broker.
    """
    if venue not in VENUES:
        raise ValueError(
            f"daemon venue must be paper or sim, not {venue!r} — "
            "this milestone has no live venue"
        )
    universe = normalize_universe(universe)
    spec = fund.spec

    if kill_switch.active():
        return TickResult(status="halted", reason="kill-switch is on", venue=venue)

    days = (
        list(trading_days)
        if trading_days is not None
        else fetch_trading_days(
            data_client, spec.benchmark, as_of, lookback_days=lookback_days,
        )
    )
    session = session_date(days, as_of)
    if session is None:
        return TickResult(
            status="not_due",
            reason=f"no trading session on or before {as_of}",
            venue=venue,
        )
    key = tick_key(spec.name, session)
    if not rebalance_due(days, session, spec.rebalance):
        return TickResult(
            status="not_due",
            reason=f"{session} is not a {spec.rebalance} rebalance session",
            key=key,
            session_date=session,
            venue=venue,
        )
    if not period_closed(session, as_of, spec.rebalance):
        return TickResult(
            status="not_due",
            reason=f"{spec.rebalance} period that includes {session} is still open",
            key=key,
            session_date=session,
            venue=venue,
        )
    if already_completed(spec.name, session, receipts, store):
        return TickResult(
            status="skipped",
            reason="duplicate tick",
            key=key,
            session_date=session,
            venue=venue,
        )

    broker, _prior = broker_for_venue(venue, spec.name, spec.capital, receipts)
    record = run_cycle(fund, session, broker, data_client, universe)
    save_cycle_record(record, receipts)
    store.remember(key)
    return TickResult(
        status="ran",
        reason="cycle completed",
        key=key,
        session_date=session,
        venue=venue,
        record=record,
    )


def run_loop(
    tick_fn: Callable[[], TickResult],
    *,
    interval_seconds: float,
    sleep: Callable[[float], None],
    once: bool = False,
    should_continue: Callable[[], bool] | None = None,
) -> list[TickResult]:
    """Poll *tick_fn* until halt, `--once`, or *should_continue* is false.

    *sleep* is required so a test can pass a recorder (or a no-op) and
    never wait on the wall clock. A halted tick breaks before sleeping.
    """
    if interval_seconds < 0:
        raise ValueError(f"interval_seconds must be >= 0, got {interval_seconds}")
    results: list[TickResult] = []
    while True:
        result = tick_fn()
        results.append(result)
        if result.status == "halted" or once:
            break
        if should_continue is not None and not should_continue():
            break
        sleep(interval_seconds)
    return results


__all__ = [
    "DEFAULT_INTERVAL_SECONDS",
    "DEFAULT_LOOKBACK_DAYS",
    "KILL_SWITCH_ENV",
    "VENUES",
    "FileTickStore",
    "KillSwitch",
    "ScheduleConfig",
    "TickResult",
    "already_completed",
    "broker_for_venue",
    "evaluate_tick",
    "fetch_trading_days",
    "period_closed",
    "rebalance_due",
    "run_loop",
    "session_date",
    "tick_key",
]
