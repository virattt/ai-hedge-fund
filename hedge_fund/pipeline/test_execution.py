"""build_orders tests — pure diffing math."""

import pytest

from hedge_fund.brokers.models import Liquidity, Position
from hedge_fund.pipeline.execution import build_orders


def _positions(**shares):
    return {t: Position(ticker=t, shares=s) for t, s in shares.items()}


def test_floor_sizing_never_overshoots():
    orders = build_orders({"AAPL": 0.25}, {}, {"AAPL": 300.0}, equity=10_000.0)
    assert len(orders) == 1
    assert orders[0].side == "buy"
    assert orders[0].quantity == 8  # 2500 / 300 = 8.33 -> 8


def test_delta_against_existing_position():
    orders = build_orders(
        {"AAPL": 0.25}, _positions(AAPL=5), {"AAPL": 250.0}, equity=10_000.0,
    )
    assert len(orders) == 1
    assert orders[0].side == "buy"
    assert orders[0].quantity == 5  # target 10, held 5


def test_held_name_missing_from_targets_is_closed():
    orders = build_orders({}, _positions(AAPL=7), {"AAPL": 100.0}, equity=10_000.0)
    assert len(orders) == 1
    assert orders[0].side == "sell"
    assert orders[0].quantity == 7


def test_subshare_delta_emits_nothing():
    orders = build_orders({"AAPL": 0.005}, {}, {"AAPL": 100.0}, equity=10_000.0)
    assert orders == []  # 50 dollars / 100 = 0.5 shares -> floor 0


def test_sells_before_buys_alphabetical():
    orders = build_orders(
        {"AAPL": 0.2, "MSFT": 0.0, "NVDA": 0.2, "AMZN": 0.0},
        _positions(MSFT=10, NVDA=1, AMZN=5),
        {"AAPL": 100.0, "MSFT": 100.0, "NVDA": 100.0, "AMZN": 100.0},
        equity=10_000.0,
    )
    assert [(o.ticker, o.side) for o in orders] == [
        ("AMZN", "sell"), ("MSFT", "sell"),
        ("AAPL", "buy"), ("NVDA", "buy"),
    ]


def test_short_target_sells_past_zero():
    orders = build_orders({"AAPL": -0.2}, {}, {"AAPL": 100.0}, equity=10_000.0)
    assert len(orders) == 1
    assert orders[0].side == "sell"
    assert orders[0].quantity == 20


def test_max_shares_caps_buys_and_sells_and_drops_subshare_caps():
    orders = build_orders(
        {"AAPL": 0.5, "MSFT": 0.0, "NVDA": 0.5},
        _positions(MSFT=40),
        {"AAPL": 100.0, "MSFT": 100.0, "NVDA": 100.0},
        equity=10_000.0,
        max_shares={"AAPL": 12, "MSFT": 15, "NVDA": 0},
    )
    assert [(o.ticker, o.side, o.quantity) for o in orders] == [("MSFT", "sell", 15), ("AAPL", "buy", 12)]
    uncapped = build_orders({"AAPL": 0.5}, {}, {"AAPL": 100.0}, equity=10_000.0, max_shares={"MSFT": 1})
    assert uncapped[0].quantity == 50   # a cap on another name changes nothing


def test_no_trade_band_holds_small_adds_but_never_a_trim_close_or_flip():
    # Equity 10,000, every mark 100, band $300. AAPL's +2 add ($200) waits
    # and so does XOM's short add of 1 ($100); MSFT's 2-share close, NVDA's
    # 1-share trim and TSLA's flip from 1 long to 1 short all trade though
    # each is under the band; AMZN's 5-share add ($500) clears it.
    orders = build_orders(
        {"AAPL": 0.52, "AMZN": 0.05, "NVDA": 0.09, "TSLA": -0.01, "XOM": -0.03},
        _positions(AAPL=50, MSFT=2, NVDA=10, TSLA=1, XOM=-2),
        {t: 100.0 for t in ("AAPL", "AMZN", "MSFT", "NVDA", "TSLA", "XOM")},
        equity=10_000.0,
        min_notional=300.0,
    )
    assert [(o.ticker, o.side, o.quantity) for o in orders] == [
        ("MSFT", "sell", 2), ("NVDA", "sell", 1), ("TSLA", "sell", 2), ("AMZN", "buy", 5),
    ]
    unbanded = build_orders({"AAPL": 0.52}, _positions(AAPL=50), {"AAPL": 100.0}, equity=10_000.0)
    assert [(o.ticker, o.side, o.quantity) for o in unbanded] == [("AAPL", "buy", 2)]


def test_band_applies_before_the_volume_cap():
    # A $5,000 move clears a $300 band, then the cap slices it to 10 shares:
    # the band judges the move wanted, not the slice that fills today.
    orders = build_orders(
        {"AAPL": 0.5}, {}, {"AAPL": 100.0}, equity=10_000.0,
        max_shares={"AAPL": 10}, min_notional=300.0,
    )
    assert [(o.ticker, o.quantity) for o in orders] == [("AAPL", 10)]


def test_liquidity_rides_on_the_order():
    orders = build_orders(
        {"AAPL": 0.5, "MSFT": 0.5}, {}, {"AAPL": 100.0, "MSFT": 100.0}, equity=10_000.0,
        liquidity={"AAPL": Liquidity(adv=1_000.0, volatility=0.02)},
    )
    by_ticker = {o.ticker: o for o in orders}
    assert (by_ticker["AAPL"].adv, by_ticker["AAPL"].volatility) == (1_000.0, 0.02)
    assert by_ticker["AAPL"].participation == pytest.approx(0.05)
    assert (by_ticker["MSFT"].adv, by_ticker["MSFT"].volatility) == (None, None)
    assert by_ticker["MSFT"].participation == 0.0
