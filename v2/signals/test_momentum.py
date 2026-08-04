"""Tests for the point-in-time momentum alpha model."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from v2.data.models import Price
from v2.signals import MomentumModel


class PriceClient:
    def __init__(self, prices):
        self.prices = prices
        self.calls = []

    def get_prices(self, ticker, start_date, end_date, **kwargs):
        self.calls.append((ticker, start_date, end_date))
        return self.prices


def _prices(closes, *, start="2025-01-01"):
    first = date.fromisoformat(start)
    return [Price(open=close, close=close, high=close, low=close, volume=100, time=(first + timedelta(days=i)).isoformat()) for i, close in enumerate(closes)]


def test_rising_prices_produce_positive_signal():
    client = PriceClient(_prices(range(100, 141)))
    signal = MomentumModel(horizons=(10, 20), skip_days=2).predict("TEST", "2025-02-10", client)

    assert signal.value > 0
    assert signal.components["return_10d"] > 0
    assert signal.metadata["skip_days"] == 2


def test_falling_prices_produce_negative_signal():
    client = PriceClient(_prices(range(140, 99, -1)))
    signal = MomentumModel(horizons=(10, 20), skip_days=2).predict("TEST", "2025-02-10", client)

    assert signal.value < 0
    assert signal.components["return_20d"] < 0


def test_flat_prices_are_neutral():
    signal = MomentumModel(horizons=(10,), skip_days=0).predict("TEST", "2025-01-20", PriceClient(_prices([100.0] * 20)))

    assert signal.value == 0.0
    assert signal.components["return_10d"] == 0.0


def test_insufficient_history_abstains():
    signal = MomentumModel(horizons=(20,), skip_days=5).predict("TEST", "2025-01-10", PriceClient(_prices([100.0] * 10)))

    assert signal.value == 0.0
    assert signal.components == {}
    assert signal.metadata["required_observations"] == 26


def test_future_prices_are_ignored_even_if_provider_returns_them():
    past = _prices([100.0] * 11, start="2025-01-01")
    future = _prices([1000.0], start="2025-02-01")
    signal = MomentumModel(horizons=(10,), skip_days=0).predict("TEST", "2025-01-11", PriceClient(past + future))

    assert signal.value == 0.0
    assert signal.metadata["observations"] == 11


def test_missing_dates_use_available_observations():
    bars = _prices(range(100, 112))
    del bars[5]
    signal = MomentumModel(horizons=(10,), skip_days=0).predict("TEST", "2025-01-12", PriceClient(bars))

    assert signal.value > 0
    assert signal.metadata["observations"] == 11


def test_conviction_is_bounded_for_extreme_move():
    signal = MomentumModel(horizons=(2,), skip_days=0, signal_scale=100).predict("TEST", "2025-01-03", PriceClient(_prices([1.0, 10.0, 100.0])))

    assert -1.0 <= signal.value <= 1.0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"horizons": ()},
        {"horizons": (0,)},
        {"horizons": (10, 10)},
        {"horizons": (10,), "weights": (1.0, 2.0)},
        {"horizons": (10,), "weights": (0.0,)},
        {"horizons": (10,), "skip_days": -1},
        {"horizons": (10,), "signal_scale": 0},
    ],
)
def test_invalid_configuration_fails_loud(kwargs):
    with pytest.raises(ValueError):
        MomentumModel(**kwargs)
