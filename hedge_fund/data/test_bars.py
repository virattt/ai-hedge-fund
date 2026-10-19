"""Bar grid tests — pure clock arithmetic, no data client."""

from datetime import datetime, timezone

import pytest

from hedge_fund.data.bars import (
    bar_grid,
    bar_time,
    bars_between,
    bars_per_day,
    current_bar,
    is_intraday,
    is_last_bar,
    next_bar,
    previous_bar,
    session_date,
    to_key,
)
from hedge_fund.data.sessions import NEW_YORK
from hedge_fund.fund import TradingWindow

REGULAR = TradingWindow()


def test_keys_tell_bars_from_days_and_sort_after_them():
    assert is_intraday("2026-10-05T09:30:00") and not is_intraday("2026-10-05")
    assert session_date("2026-10-05T09:30:00") == "2026-10-05"
    assert "2026-10-05" < "2026-10-05T09:30:00" < "2026-10-05T16:00:00" < "2026-10-06"


def test_grid_is_anchored_at_the_open_and_always_closes_at_the_end():
    grid = bar_grid("2026-10-05", 60, REGULAR)
    assert grid[0] == "2026-10-05T09:30:00" and grid[-1] == "2026-10-05T16:00:00"
    assert len(grid) == 391 == bars_per_day(60, REGULAR)
    # 7 minutes does not divide 390: the last full bar is 15:55, then a short one at the close.
    grid = bar_grid("2026-10-05", 7 * 60, REGULAR)
    assert grid[-2:] == ["2026-10-05T15:55:00", "2026-10-05T16:00:00"]
    # Sub-minute keeps seconds; a window of any length works.
    grid = bar_grid("2026-10-05", 30, TradingWindow(start="07:00", end="07:01"))
    assert grid == ["2026-10-05T07:00:00", "2026-10-05T07:00:30", "2026-10-05T07:01:00"]
    with pytest.raises(ValueError, match="positive"):
        bar_grid("2026-10-05", 0, REGULAR)


def test_current_bar_floors_to_the_grid_and_is_none_before_the_open():
    at = lambda h, m, s=0: datetime(2026, 10, 5, h, m, s, tzinfo=NEW_YORK)
    assert current_bar(at(9, 29, 59), 300, REGULAR) is None
    assert current_bar(at(9, 30), 300, REGULAR) == "2026-10-05T09:30:00"
    assert current_bar(at(10, 7, 12), 300, REGULAR) == "2026-10-05T10:05:00"
    assert current_bar(at(15, 59, 59), 300, REGULAR) == "2026-10-05T15:55:00"
    assert current_bar(at(16, 0), 300, REGULAR) == "2026-10-05T16:00:00"
    assert current_bar(at(19, 0), 300, REGULAR) == "2026-10-05T16:00:00"
    # Any zone in: the bar is a New York instant. 14:07 UTC is 10:07 ET in October.
    assert current_bar(datetime(2026, 10, 5, 14, 7, tzinfo=timezone.utc), 300, REGULAR) == "2026-10-05T10:05:00"


def test_next_bar_rolls_over_the_close_and_the_weekend():
    at = lambda h, m, s=0: datetime(2026, 10, 2, h, m, s, tzinfo=NEW_YORK)  # a Friday
    assert next_bar(at(10, 5), 300, REGULAR) == at(10, 10)
    assert next_bar(at(10, 5, 1), 300, REGULAR) == at(10, 10)
    assert next_bar(at(15, 58), 300, REGULAR) == at(16, 0)  # the short closing bar
    assert next_bar(at(16, 0), 300, REGULAR) == datetime(2026, 10, 5, 9, 30, tzinfo=NEW_YORK)  # Monday
    assert next_bar(at(5, 0), 300, REGULAR) == at(9, 30)


def test_previous_bar_crosses_to_the_prior_weekday_close():
    assert previous_bar("2026-10-05T10:05:00", 300, REGULAR) == "2026-10-05T10:00:00"
    assert previous_bar("2026-10-05T16:00:00", 7 * 60, REGULAR) == "2026-10-05T15:55:00"
    assert previous_bar("2026-10-05T09:30:00", 300, REGULAR) == "2026-10-02T16:00:00"  # Monday -> Friday


def test_bars_between_counts_the_gap_on_weekdays_only():
    assert bars_between("2026-10-05T10:00:00", "2026-10-05T10:05:00", 300, REGULAR) == 0
    assert bars_between("2026-10-05T10:00:00", "2026-10-05T10:15:00", 300, REGULAR) == 2
    # Friday 15:55 -> Monday 09:35: Friday's close, Monday's open.
    assert bars_between("2026-10-02T15:55:00", "2026-10-05T09:35:00", 300, REGULAR) == 2
    # From a daily key: everything on the grid after that day's close.
    assert bars_between("2026-10-02", "2026-10-05T09:35:00", 300, REGULAR) == 1
    assert to_key(datetime(2026, 10, 5, 14, 5, tzinfo=timezone.utc)) == "2026-10-05T10:05:00"


def test_dst_switch_day_is_an_ordinary_grid():
    """Clocks fall back at 02:00 on 2026-11-01, outside any allowed window: the
    grid that day is the same wall-clock list, and bar_time keeps the zone."""
    times = lambda day: [key[10:] for key in bar_grid(day, 3600, REGULAR)]
    assert times("2026-11-02") == times("2026-10-30")
    monday = bar_time("2026-11-02T09:30:00")
    friday = bar_time("2026-10-30T09:30:00")
    assert monday.utcoffset().total_seconds() == -5 * 3600 and friday.utcoffset().total_seconds() == -4 * 3600
    assert is_last_bar("2026-11-02T16:00:00", REGULAR) and not is_last_bar("2026-11-02T15:00:00", REGULAR)
