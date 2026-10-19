"""The intraday session grid — pure New York clock arithmetic.

A minute fund's session is a bar boundary: a New York wall-clock instant
inside the fund's trading window, written `YYYY-MM-DDTHH:MM:SS` with no
offset. The grid for one day is anchored at the window's start, steps by the
interval, and always ends with a bar at the window's end, so there is a mark
at the close whether or not the interval divides the window. Everything here
is deterministic from (day, interval, window); the data layer is not asked.

Why no UTC offset in the key: the allowed windows (04:00–20:00) never cross
a daylight-saving switch (02:00), so a NY-local timestamp is unambiguous and
sorts correctly as text, after any date-only daily session key.
"""

from __future__ import annotations

from datetime import date as _date
from datetime import datetime, time, timedelta
from typing import TYPE_CHECKING

from hedge_fund.data.sessions import NEW_YORK

if TYPE_CHECKING:  # the window is only read here; importing it would pull in the fund package
    from hedge_fund.fund.spec import TradingWindow

_FORMAT = "%Y-%m-%dT%H:%M:%S"


def is_intraday(session: str) -> bool:
    """A bar key carries a time; a daily key is a bare date."""
    return len(session) > 10


def session_date(session: str) -> str:
    """The New York date a session (daily or bar) belongs to."""
    return session[:10]


def bar_grid(day: str, interval_seconds: int, window: TradingWindow) -> list[str]:
    """Every bar in *day*'s window, in order. The last bar is the window's end."""
    return [_key(day, s) for s in _grid_seconds(interval_seconds, window)]


def current_bar(now: datetime, interval_seconds: int, window: TradingWindow) -> str | None:
    """The most recent bar boundary at or before *now* on *now*'s New York
    day, or None before the day's first bar. After the window closes, the
    day's last bar. Weekends and holidays are the caller's to skip."""
    local = now.astimezone(NEW_YORK)
    day = local.date().isoformat()
    elapsed = local.hour * 3600 + local.minute * 60 + local.second
    start, end = window.start_seconds, window.end_seconds
    if elapsed < start:
        return None
    if elapsed >= end:
        return _key(day, end)
    return _key(day, start + ((elapsed - start) // interval_seconds) * interval_seconds)


def next_bar(now: datetime, interval_seconds: int, window: TradingWindow) -> datetime:
    """The first bar boundary strictly after *now*, as an aware New York
    datetime: today's next boundary, else the window's start on the next
    weekday. Holidays are not consulted; the runner notices those from the
    market itself."""
    local = now.astimezone(NEW_YORK)
    day = local.date()
    elapsed = local.hour * 3600 + local.minute * 60 + local.second
    for second in _grid_seconds(interval_seconds, window):
        if second > elapsed:
            return _at(day, second)
    day += timedelta(days=1)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return _at(day, window.start_seconds)


def previous_bar(session: str, interval_seconds: int, window: TradingWindow) -> str:
    """The bar before *session* on the grid; the prior weekday's last bar
    when *session* opens its day."""
    day, elapsed = _split(session)
    seconds = _grid_seconds(interval_seconds, window)
    earlier = [s for s in seconds if s < elapsed]
    if earlier:
        return _key(day.isoformat(), earlier[-1])
    day -= timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return _key(day.isoformat(), seconds[-1])


def bars_per_day(interval_seconds: int, window: TradingWindow) -> int:
    return len(_grid_seconds(interval_seconds, window))


def bars_between(after: str, before: str, interval_seconds: int, window: TradingWindow) -> int:
    """How many grid bars on weekdays fall strictly between two sessions.
    Zero when *before* is the bar right after *after*; the size of a gap
    otherwise. *after* may be a daily key (a fund that changed cadence)."""
    seconds = _grid_seconds(interval_seconds, window)
    start_day = _date.fromisoformat(after[:10])
    end_day, end_elapsed = _split(before)
    start_elapsed = _split(after)[1] if is_intraday(after) else window.end_seconds
    count = 0
    day = start_day
    while day <= end_day:
        if day.weekday() < 5:
            for second in seconds:
                if (day > start_day or second > start_elapsed) and (day < end_day or second < end_elapsed):
                    count += 1
        day += timedelta(days=1)
    return count


def to_key(moment: datetime) -> str:
    """An aware datetime as a bar key, in New York."""
    return moment.astimezone(NEW_YORK).strftime(_FORMAT)


def is_last_bar(session: str, window: TradingWindow) -> bool:
    """Whether *session* is its day's closing bar (the window's end)."""
    return _split(session)[1] == window.end_seconds


def bar_time(session: str) -> datetime:
    """A bar key as an aware New York datetime."""
    return datetime.strptime(session, _FORMAT).replace(tzinfo=NEW_YORK)


def _grid_seconds(interval_seconds: int, window: TradingWindow) -> list[int]:
    if interval_seconds <= 0:
        raise ValueError(f"interval must be positive, got {interval_seconds}")
    start, end = window.start_seconds, window.end_seconds
    seconds = list(range(start, end, interval_seconds))
    if seconds[-1] != end:
        seconds.append(end)
    return seconds


def _key(day: str, seconds: int) -> str:
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{day}T{hours:02d}:{minutes:02d}:{secs:02d}"


def _split(session: str) -> tuple[_date, int]:
    moment = datetime.strptime(session, _FORMAT)
    return moment.date(), moment.hour * 3600 + moment.minute * 60 + moment.second


def _at(day: _date, seconds: int) -> datetime:
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return datetime.combine(day, time(hours, minutes, secs), tzinfo=NEW_YORK)
