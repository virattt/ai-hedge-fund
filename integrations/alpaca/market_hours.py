"""US equity session helpers (America/New_York)."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

# Regular US cash session (no holiday calendar — use Alpaca clock when available).
SESSION_OPEN = time(9, 30)
SESSION_CLOSE = time(16, 0)


def now_et() -> datetime:
    return datetime.now(tz=ET)


def is_weekday(d: date) -> bool:
    return d.weekday() < 5


def is_regular_session(dt: datetime | None = None) -> bool:
    """True during Mon–Fri 9:30–16:00 ET (holidays not excluded)."""
    dt = dt or now_et()
    local = dt.astimezone(ET)
    if not is_weekday(local.date()):
        return False
    t = local.time()
    return SESSION_OPEN <= t < SESSION_CLOSE


def session_open_datetime(trading_day: date, *, delay_minutes: int = 0) -> datetime:
    open_minutes = SESSION_OPEN.hour * 60 + SESSION_OPEN.minute + delay_minutes
    return datetime(
        trading_day.year,
        trading_day.month,
        trading_day.day,
        open_minutes // 60,
        open_minutes % 60,
        tzinfo=ET,
    )


def next_light_tick(after: datetime, interval_minutes: int) -> datetime:
    """Next 5-minute boundary after `after` within the session, or next session open."""
    local = after.astimezone(ET)
    if not is_regular_session(local):
        return _next_session_start(local, delay_minutes=0)

    minute = local.minute - (local.minute % interval_minutes) + interval_minutes
    candidate = local.replace(second=0, microsecond=0)
    if minute >= 60:
        candidate = candidate.replace(hour=local.hour + 1, minute=minute - 60)
    else:
        candidate = candidate.replace(minute=minute)

    close_dt = datetime.combine(local.date(), SESSION_CLOSE, tzinfo=ET)
    if candidate >= close_dt:
        return _next_session_start(local, delay_minutes=0)
    return candidate


def _next_session_start(local: datetime, *, delay_minutes: int) -> datetime:
    day = local.date()
    if is_weekday(day) and local.time() < SESSION_OPEN:
        return session_open_datetime(day, delay_minutes=delay_minutes)
    day += timedelta(days=1)
    while not is_weekday(day):
        day += timedelta(days=1)
    return session_open_datetime(day, delay_minutes=delay_minutes)


def trading_date(dt: datetime | None = None) -> date:
    return (dt or now_et()).astimezone(ET).date()
