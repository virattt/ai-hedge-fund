"""Offline tests for momentum and mean-reversion AlphaModels.

Synthetic price series only — no live Financial Datasets client.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from hedge_fund.data.client import FDClientError
from hedge_fund.data.models import Price
from hedge_fund.fund.spec import Fund, FundSpec
from hedge_fund.models import Signal
from hedge_fund.signals import ALPHA_MODEL_REGISTRY, MeanReversionModel, MomentumModel


class FakePriceClient:
    """Canned prices; optional infra error. Filters by the requested window
    unless ``leak_future`` is set, so point-in-time filtering is the model's job.
    """

    def __init__(self, prices=None, error=None, *, leak_future=False):
        self._prices = list(prices or [])
        self._error = error
        self._leak_future = leak_future
        self.calls = []

    def get_prices(self, ticker, start_date, end_date, **kwargs):
        if self._error is not None:
            raise self._error
        self.calls.append((ticker, start_date, end_date))
        if self._leak_future:
            return list(self._prices)
        return [
            p for p in self._prices
            if start_date <= p.time[:10] <= end_date
        ]


def _bars(closes, start="2024-01-01") -> list[Price]:
    """Sequential calendar-day bars from *start* with the given closes."""
    day = date.fromisoformat(start)
    out = []
    for close in closes:
        out.append(Price(
            open=close, close=close, high=close, low=close,
            volume=1000, time=day.isoformat(),
        ))
        day += timedelta(days=1)
    return out


def _as_of(prices: list[Price]) -> str:
    return prices[-1].time[:10]


def _in_unit_interval(value: float) -> None:
    assert -1.0 <= value <= 1.0


# ---------------------------------------------------------------------------
# Registry + constructor
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_registry_keys(self):
        assert ALPHA_MODEL_REGISTRY["momentum"] is MomentumModel
        assert ALPHA_MODEL_REGISTRY["mean_reversion"] is MeanReversionModel

    def test_fund_staffs_sleeves_with_params(self):
        spec = FundSpec(
            name="quant-sleeves",
            strategies=[
                {
                    "name": "mom",
                    "models": [{"name": "momentum", "params": {"lookback": 10, "skip": 2}}],
                },
                {
                    "name": "mr",
                    "models": [{"name": "mean_reversion", "params": {"window": 5, "z_scale": 1.5}}],
                },
            ],
            risk={"max_position_pct": 0.25, "max_gross_exposure": 1.0},
        )
        fund = Fund(spec)
        mom = fund.strategies[0][1][0]
        mr = fund.strategies[1][1][0]
        assert isinstance(mom, MomentumModel)
        assert mom.name == "momentum"
        assert mom._lookback == 10
        assert mom._skip == 2
        assert isinstance(mr, MeanReversionModel)
        assert mr.name == "mean_reversion"
        assert mr._window == 5
        assert mr._z_scale == 1.5

    def test_momentum_rejects_bad_params(self):
        with pytest.raises(ValueError, match="lookback"):
            MomentumModel(lookback=0)
        with pytest.raises(ValueError, match="skip"):
            MomentumModel(skip=-1)

    def test_mean_reversion_rejects_bad_params(self):
        with pytest.raises(ValueError, match="window"):
            MeanReversionModel(window=1)
        with pytest.raises(ValueError, match="z_scale"):
            MeanReversionModel(z_scale=0.0)


# ---------------------------------------------------------------------------
# Momentum
# ---------------------------------------------------------------------------

class TestMomentum:
    def test_uptrend_is_bullish_with_thesis(self):
        prices = _bars([100 + i for i in range(12)])
        sig = MomentumModel(lookback=8, skip=2).predict("TEST", _as_of(prices), FakePriceClient(prices))
        assert isinstance(sig, Signal)
        assert sig.model_name == "momentum"
        assert sig.ticker == "TEST"
        assert sig.value > 0.0
        _in_unit_interval(sig.value)
        assert sig.reasoning
        assert "momentum" in sig.reasoning
        assert sig.metadata["abstained"] is False

    def test_downtrend_is_bearish(self):
        prices = _bars([200 - i for i in range(12)])
        sig = MomentumModel(lookback=8, skip=2).predict("TEST", _as_of(prices), FakePriceClient(prices))
        assert sig.value < 0.0
        _in_unit_interval(sig.value)
        assert sig.reasoning

    def test_skip_ignores_recent_reversal(self):
        # Rise for 6 bars, then crash in the last 2. skip=2 keeps the rise;
        # skip=0 sees the crash.
        closes = [100, 110, 120, 130, 140, 150, 50, 40]
        prices = _bars(closes)
        client = FakePriceClient(prices)
        as_of = _as_of(prices)
        skipped = MomentumModel(lookback=5, skip=2).predict("TEST", as_of, client)
        raw = MomentumModel(lookback=5, skip=0).predict("TEST", as_of, client)
        assert skipped.value > 0.0
        assert raw.value < 0.0

    def test_short_history_abstains(self):
        prices = _bars([100, 101, 102])
        sig = MomentumModel(lookback=20, skip=5).predict("TEST", _as_of(prices), FakePriceClient(prices))
        assert sig.value == 0.0
        assert sig.metadata["abstained"] is True
        assert sig.metadata["reason"] == "short_history"
        assert sig.reasoning
        assert "short history" in sig.reasoning

    def test_empty_prices_abstain(self):
        sig = MomentumModel(lookback=5, skip=1).predict("TEST", "2024-02-01", FakePriceClient([]))
        assert sig.value == 0.0
        assert sig.metadata["abstained"] is True
        assert sig.reasoning

    def test_infra_error_raises(self):
        client = FakePriceClient(error=FDClientError("down", status_code=500, path="/prices/"))
        with pytest.raises(FDClientError) as exc_info:
            MomentumModel(lookback=5, skip=1).predict("TEST", "2024-02-01", client)
        assert exc_info.value.status_code == 500

    def test_point_in_time_drops_future_bars(self):
        # 8 rising bars through 2024-01-08, then a crash on 2024-01-09.
        # Query as-of 2024-01-08 must not see the crash.
        prices = _bars([100, 110, 120, 130, 140, 150, 160, 170, 10])
        client = FakePriceClient(prices, leak_future=True)
        sig = MomentumModel(lookback=6, skip=1).predict("TEST", "2024-01-08", client)
        assert sig.value > 0.0
        assert sig.metadata["abstained"] is False

    def test_extreme_return_stays_in_unit_interval(self):
        prices = _bars([1.0] + [1.0] * 5 + [10_000.0] + [10_000.0])
        sig = MomentumModel(lookback=6, skip=1).predict("TEST", _as_of(prices), FakePriceClient(prices))
        _in_unit_interval(sig.value)
        assert sig.value > 0.9


# ---------------------------------------------------------------------------
# Mean reversion
# ---------------------------------------------------------------------------

class TestMeanReversion:
    def test_spike_is_bearish_with_thesis(self):
        prices = _bars([100.0] * 19 + [130.0])
        sig = MeanReversionModel(window=20).predict("TEST", _as_of(prices), FakePriceClient(prices))
        assert isinstance(sig, Signal)
        assert sig.model_name == "mean_reversion"
        assert sig.value < 0.0
        _in_unit_interval(sig.value)
        assert sig.reasoning
        assert "z-score" in sig.reasoning
        assert sig.metadata["abstained"] is False
        assert sig.metadata["z_score"] > 0.0

    def test_dip_is_bullish(self):
        prices = _bars([100.0] * 19 + [70.0])
        sig = MeanReversionModel(window=20).predict("TEST", _as_of(prices), FakePriceClient(prices))
        assert sig.value > 0.0
        _in_unit_interval(sig.value)
        assert sig.reasoning
        assert sig.metadata["z_score"] < 0.0

    def test_flat_window_abstains(self):
        prices = _bars([100.0] * 20)
        sig = MeanReversionModel(window=20).predict("TEST", _as_of(prices), FakePriceClient(prices))
        assert sig.value == 0.0
        assert sig.metadata["abstained"] is True
        assert sig.metadata["reason"] == "zero_vol"
        assert sig.reasoning

    def test_short_history_abstains(self):
        prices = _bars([100.0, 101.0, 99.0])
        sig = MeanReversionModel(window=20).predict("TEST", _as_of(prices), FakePriceClient(prices))
        assert sig.value == 0.0
        assert sig.metadata["abstained"] is True
        assert sig.metadata["reason"] == "short_history"
        assert "short history" in sig.reasoning

    def test_empty_prices_abstain(self):
        sig = MeanReversionModel(window=5).predict("TEST", "2024-02-01", FakePriceClient([]))
        assert sig.value == 0.0
        assert sig.metadata["abstained"] is True
        assert sig.reasoning

    def test_infra_error_raises(self):
        client = FakePriceClient(error=FDClientError("down", status_code=429, path="/prices/"))
        with pytest.raises(FDClientError) as exc_info:
            MeanReversionModel(window=5).predict("TEST", "2024-02-01", client)
        assert exc_info.value.status_code == 429

    def test_point_in_time_drops_future_spike(self):
        # Flat through 2024-01-20; spike on 2024-01-21 must not fire as-of the 20th.
        prices = _bars([100.0] * 20 + [160.0])
        client = FakePriceClient(prices, leak_future=True)
        sig = MeanReversionModel(window=20).predict("TEST", "2024-01-20", client)
        assert sig.value == 0.0
        assert sig.metadata["reason"] == "zero_vol"

    def test_extreme_z_stays_in_unit_interval(self):
        prices = _bars([100.0] * 19 + [1_000.0])
        sig = MeanReversionModel(window=20, z_scale=0.5).predict(
            "TEST", _as_of(prices), FakePriceClient(prices),
        )
        _in_unit_interval(sig.value)
        assert sig.value < -0.9
