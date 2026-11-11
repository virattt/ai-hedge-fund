"""Headline dates render on Windows as well as POSIX."""

from datetime import datetime

import pytest

from hedge_fund.data.sessions import NEW_YORK
from hedge_fund.features.intraday import Headline, IntradayContext


@pytest.mark.parametrize("day", [3, 13, 30])
def test_previous_day_headline_has_an_unpadded_day(day):
    context = IntradayContext(
        ticker="TEST", as_of="2024-07-01T09:30:00", move_pct=None,
        market_pct=None, earnings=None,
        headlines=[Headline(datetime(2024, 6, day, 17, 0, tzinfo=NEW_YORK), "Wire", "Earlier news")],
    )
    assert f"    Jun {day} 17:00 ET  Wire: Earlier news" in context.render()


def test_same_day_headline_keeps_its_time_only():
    context = IntradayContext(
        ticker="TEST", as_of="2024-06-04T09:30:00", move_pct=None,
        market_pct=None, earnings=None,
        headlines=[Headline(datetime(2024, 6, 4, 9, 0, tzinfo=NEW_YORK), "Wire", "Today's news")],
    )
    assert "    09:00 ET  Wire: Today's news" in context.render()
    assert "Jun" not in context.render()
