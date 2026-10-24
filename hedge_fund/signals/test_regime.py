"""Tests for RegimeModel (HMM market regime)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from hedge_fund.data.models import Price
from hedge_fund.signals import ALPHA_MODEL_REGISTRY, RegimeModel, get_investment_approach
from hedge_fund.signals import regime

pytest.importorskip("hmmlearn")


def _bars(n=1400, seed=0, shock_from=None):
    """Calm uptrend, then a high-vol selloff. Optionally wreck every bar from `shock_from` on."""
    rng = np.random.default_rng(seed)
    r = np.concatenate([rng.normal(0.0008, 0.008, n // 2), rng.normal(-0.001, 0.025, n - n // 2)])
    close = 100 * np.exp(np.cumsum(r))
    vol = rng.integers(1_000_000, 2_000_000, n).astype(float)
    if shock_from is not None:
        close[shock_from:] *= 3.0
        vol[shock_from:] *= 10
    idx = pd.bdate_range("2015-01-01", periods=n)
    return [Price(open=c, close=c, high=c * (1 + abs(x)), low=c * (1 - abs(x)),
                  volume=int(v), time=d.strftime("%Y-%m-%d"))
            for c, x, v, d in zip(close, r, vol, idx)]


class MockClient:
    def __init__(self, bars):
        self._bars = bars
        self.calls = 0

    def get_prices(self, ticker, start_date, end_date, **kwargs):
        self.calls += 1
        return [b for b in self._bars if start_date <= b.time <= end_date]


def _frame(bars):
    df = pd.DataFrame([b.model_dump() for b in bars])
    df.index = pd.to_datetime(df["time"])
    return df[["open", "high", "low", "close", "volume"]].astype(float)


def _fast():
    return RegimeModel(n_states=(2, 3), n_restarts=1)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def test_registered_long_only():
    assert ALPHA_MODEL_REGISTRY["regime"] is RegimeModel
    assert get_investment_approach("regime") == "long_only"
    assert RegimeModel().name == "regime"


# ---------------------------------------------------------------------------
# No lookahead
# ---------------------------------------------------------------------------

def test_features_ignore_future_bars():
    bars, shocked = _bars(), _bars(shock_from=900)
    day = pd.Timestamp(bars[899].time)
    f1 = regime.build_features(_frame(bars))
    f2 = regime.build_features(_frame(shocked))
    pd.testing.assert_frame_equal(f1.loc[:day], f2.loc[:day])


def test_forward_filter_ignores_future_bars():
    bars, shocked = _bars(), _bars(shock_from=900)
    f1 = regime.build_features(_frame(bars))
    f2 = regime.build_features(_frame(shocked))
    model = regime.fit_hmm(f1[regime.FEATURES].values[:600], (2, 3), 1)
    k = f1.index.get_loc(pd.Timestamp(bars[899].time)) + 1
    p1 = regime.forward_filter(model, f1[regime.FEATURES].values)
    p2 = regime.forward_filter(model, f2[regime.FEATURES].values)
    np.testing.assert_allclose(p1[:k], p2[:k])
    np.testing.assert_allclose(p1.sum(axis=1), 1, atol=1e-9)


def test_predict_ignores_future_bars():
    """Same as-of date, different future: identical signal."""
    date = _bars()[1100].time
    a = _fast().predict("AAPL", date, MockClient(_bars()))
    b = _fast().predict("AAPL", date, MockClient(_bars(shock_from=1101)))
    assert a.value == b.value
    assert a.components == b.components


def test_going_back_in_time_refits():
    """A model fit on later data must not be reused for an earlier date."""
    bars = _bars()
    m, client = _fast(), MockClient(bars)
    m.predict("X", bars[1300].time, client)
    m.predict("X", bars[1100].time, client)
    assert m._fit_date <= pd.Timestamp(bars[1100].time)


# ---------------------------------------------------------------------------
# predict
# ---------------------------------------------------------------------------

def test_abstains_without_enough_history():
    bars = _bars()
    sig = _fast().predict("X", bars[500].time, MockClient(bars))
    assert sig.value == 0.0
    assert sig.metadata["abstained"] is True


def test_signal_shape_and_range():
    bars = _bars()
    sig = _fast().predict("MSFT", bars[1300].time, MockClient(bars))
    assert sig.ticker == "MSFT"
    assert 0.0 <= sig.value <= 1.0
    assert set(sig.components) == set(regime.LABELS)
    assert abs(sum(sig.components.values()) - 1.0) < 1e-3
    assert "abstained" not in sig.metadata


def test_same_date_reuses_assessment_across_tickers():
    bars = _bars()
    m, client = _fast(), MockClient(bars)
    a = m.predict("A", bars[1300].time, client)
    b = m.predict("B", bars[1300].time, client)
    assert (a.ticker, b.ticker) == ("A", "B")
    assert a.value == b.value
    assert client.calls == 1


def test_stale_data_goes_flat():
    bars = _bars()[:1300]
    last = pd.Timestamp(bars[-1].time)
    sig = _fast().predict("X", (last + pd.Timedelta(days=10)).strftime("%Y-%m-%d"), MockClient(bars))
    assert sig.value == 0.0
    assert "stale" in sig.reasoning


# ---------------------------------------------------------------------------
# Switching rules
# ---------------------------------------------------------------------------

def _lp(**kw):
    row = np.zeros(len(regime.LABELS))
    for k, v in kw.items():
        row[regime.LABELS.index(k)] = v
    return row


def test_switch_needs_three_days_above_threshold():
    seq = [_lp(CALM_UP=0.9, CHOP=0.1)] * 2 + [_lp(CALM_UP=0.6, CHOP=0.4)] + [_lp(CALM_UP=0.9, CHOP=0.1)] * 3
    d = regime.apply_switching_rules(np.array(seq), np.zeros(len(seq)))
    assert [x.state for x in d] == [None, None, None, None, None, "CALM_UP"]


def test_cooldown_blocks_fast_flip():
    seq = [_lp(CALM_UP=0.9, CHOP=0.1)] * 3 + [_lp(CRASH=0.9, CALM_UP=0.1)] * 3
    d = regime.apply_switching_rules(np.array(seq), np.zeros(len(seq)))
    assert d[2].state == "CALM_UP"
    assert d[5].state == "CALM_UP"


def test_uncertain_means_zero_size():
    seq = [_lp(CALM_UP=0.9, CHOP=0.1)] * 3 + [_lp(CALM_UP=0.5, CHOP=0.4)]
    d = regime.apply_switching_rules(np.array(seq), np.zeros(len(seq)))
    assert d[2].size == 1.0
    assert d[3].size == 0.0


def test_danger_halves_size():
    seq = [_lp(CALM_UP=0.9, CHOP=0.1)] * 3
    d = regime.apply_switching_rules(np.array(seq), np.array([0, 0, 0.3]))
    assert d[2].size == 0.5
