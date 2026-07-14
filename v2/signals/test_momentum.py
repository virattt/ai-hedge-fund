"""Tests for the Momentum alpha model (12-1 time-series momentum)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from v2.data.models import Price
from v2.models import Signal
from v2.signals import MomentumModel
from v2.signals.base import AlphaModel, QuantModel


class MockPriceClient:
    """Returns canned daily bars, filtered point-in-time by [start, end]."""

    def __init__(self, prices: list[Price]) -> None:
        self._prices = prices
        self.last_end_date: str | None = None

    def get_prices(self, ticker, start_date, end_date, **kwargs) -> list[Price]:
        self.last_end_date = end_date
        return [p for p in self._prices if start_date <= p.time[:10] <= end_date]


def _series(end_date: str, closes: list[float]) -> list[Price]:
    """Build one daily bar per calendar day, oldest first, ending at end_date."""
    end = datetime.strptime(end_date, "%Y-%m-%d").date()
    n = len(closes)
    return [
        Price(
            open=c,
            high=c,
            low=c,
            close=c,
            volume=0,
            time=(end - timedelta(days=(n - 1 - i))).isoformat(),
        )
        for i, c in enumerate(closes)
    ]


# ---------------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------------


class TestInterface:
    def test_is_quant_model(self):
        assert issubclass(MomentumModel, QuantModel)
        assert issubclass(MomentumModel, AlphaModel)

    def test_name(self):
        assert MomentumModel().name == "momentum"

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"lookback_months": 0},
            {"skip_months": -1},
            {"lookback_months": 3, "skip_months": 3},
            {"lookback_months": 3, "skip_months": 5},
        ],
    )
    def test_invalid_params_rejected(self, kwargs):
        with pytest.raises(ValueError):
            MomentumModel(**kwargs)


# ---------------------------------------------------------------------------
# predict
# ---------------------------------------------------------------------------


class TestMomentumPredict:
    def test_uptrend_is_long(self):
        # 300 rising daily closes -> positive 12-1 return -> bullish conviction.
        closes = [100.0 * (1.001**i) for i in range(300)]
        client = MockPriceClient(_series("2025-06-30", closes))
        sig = client_predict(client, "2025-06-30")
        assert isinstance(sig, Signal)
        assert sig.model_name == "momentum"
        assert sig.value > 0.0
        assert sig.components["trailing_return"] > 0.0

    def test_downtrend_is_short(self):
        closes = [100.0 * (0.999**i) for i in range(300)]
        client = MockPriceClient(_series("2025-06-30", closes))
        sig = client_predict(client, "2025-06-30")
        assert sig.value < 0.0
        assert sig.components["trailing_return"] < 0.0

    def test_insufficient_history_is_neutral(self):
        # Fewer bars than the lookback window -> no view.
        closes = [100.0 + i for i in range(100)]
        client = MockPriceClient(_series("2025-06-30", closes))
        sig = client_predict(client, "2025-06-30")
        assert sig.value == 0.0

    def test_last_month_is_skipped(self):
        # Rise for the first 279 bars, then crash hard over the final ~month.
        # The 12-1 window ends one month before `date`, so it must ignore the
        # crash and still read the up-move -> bullish.
        closes = [100.0 * (1.002**i) for i in range(279)]
        closes += [closes[-1] * (0.90**k) for k in range(1, 22)]  # -10%/day for 21 days
        client = MockPriceClient(_series("2025-06-30", closes))
        sig = client_predict(client, "2025-06-30")
        assert sig.value > 0.0, "signal should reflect the 12-1 window, not the skipped last month"

    def test_point_in_time_ignores_future_bars(self):
        # Rising history up to `date`, then a crash on later dates. A
        # point-in-time model must not see the post-date bars.
        closes = [100.0 * (1.001**i) for i in range(300)]
        history = _series("2025-06-30", closes)
        future = _series("2025-08-15", [50.0 * (0.9**k) for k in range(46)])  # after date
        client = MockPriceClient(history + future)

        sig = client_predict(client, "2025-06-30")
        assert client.last_end_date == "2025-06-30"
        assert sig.value > 0.0  # unaffected by the future crash


def client_predict(client: MockPriceClient, date: str) -> Signal:
    return MomentumModel().predict("TEST", date, client)
