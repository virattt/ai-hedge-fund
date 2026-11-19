"""Tests for alpha models (AlphaModel/QuantModel + PEADModel)."""

from __future__ import annotations

from hedge_fund.data.models import EarningsData, EarningsRecord
from hedge_fund.signals import PEADModel, QuantModel
from hedge_fund.signals.base import AlphaModel
from hedge_fund.models import Signal


class MockFDClient:
    """Returns canned earnings history for testing without API calls."""

    def __init__(self, earnings=None):
        self._earnings = earnings or []

    def get_earnings_history(self, ticker, limit=12):
        return self._earnings


def _rec(report_period, filing_date, surprise, source_type="8-K"):
    return EarningsRecord(
        ticker="TEST", report_period=report_period, source_type=source_type,
        filing_date=filing_date,
        quarterly=EarningsData(eps_surprise=surprise) if surprise else None,
    )


# ---------------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------------

class TestInterface:
    def test_quant_model_is_alpha_model(self):
        assert issubclass(QuantModel, AlphaModel)
        assert issubclass(PEADModel, QuantModel)

    def test_name(self):
        assert PEADModel().name == "pead"

    def test_helpers(self):
        assert QuantModel._safe_float(None) == 0.0
        assert QuantModel._safe_float("3.5") == 3.5
        assert QuantModel._normalize_to_signal(2.0) == 1.0
        assert QuantModel._normalize_to_signal(-2.0) == -1.0


# ---------------------------------------------------------------------------
# PEADModel.predict
# ---------------------------------------------------------------------------

class TestPEADPredict:
    def test_beat_fires_long(self):
        fd = MockFDClient([_rec("2025-06-30", "2025-08-01", "BEAT")])
        sig = PEADModel().predict("TEST", "2025-08-01", fd)
        assert sig.value == 1.0
        assert sig.model_name == "pead"
        assert "BEAT" in sig.reasoning

    def test_miss_fires_short(self):
        fd = MockFDClient([_rec("2025-06-30", "2025-08-01", "MISS")])
        sig = PEADModel().predict("TEST", "2025-08-01", fd)
        assert sig.value == -1.0

    def test_meet_is_neutral(self):
        fd = MockFDClient([_rec("2025-06-30", "2025-08-01", "MEET")])
        sig = PEADModel().predict("TEST", "2025-08-01", fd)
        assert sig.value == 0.0

    def test_no_earnings_is_neutral(self):
        fd = MockFDClient([])
        sig = PEADModel().predict("TEST", "2025-08-01", fd)
        assert sig.value == 0.0

    def test_stale_event_is_neutral(self):
        # Event filed 30 days before the query date — outside the freshness window
        fd = MockFDClient([_rec("2025-06-30", "2025-08-01", "BEAT")])
        sig = PEADModel().predict("TEST", "2025-08-31", fd)
        assert sig.value == 0.0

    def test_point_in_time_ignores_future_filings(self):
        # A filing dated after the query date must not be visible (no lookahead)
        fd = MockFDClient([_rec("2025-06-30", "2025-08-01", "BEAT")])
        sig = PEADModel().predict("TEST", "2025-07-15", fd)
        assert sig.value == 0.0

    def test_freshness_window_bridges_weekend(self):
        # Filed Saturday 2025-08-02; queried Monday 2025-08-04 (2 days) → still fresh
        fd = MockFDClient([_rec("2025-06-30", "2025-08-02", "BEAT")])
        sig = PEADModel().predict("TEST", "2025-08-04", fd)
        assert sig.value == 1.0

    def test_45_day_retrospective_filter(self):
        # Filing is 100+ days after the report period → retrospective, excluded
        fd = MockFDClient([_rec("2025-12-31", "2026-04-13", "BEAT")])
        sig = PEADModel().predict("TEST", "2026-04-13", fd)
        assert sig.value == 0.0

    def test_dedup_prefers_8k(self):
        # Same report period via 8-K and 10-Q; 8-K should be the chosen source
        fd = MockFDClient([
            _rec("2025-06-30", "2025-08-01", "BEAT", source_type="8-K"),
            _rec("2025-06-30", "2025-08-02", "BEAT", source_type="10-Q"),
        ])
        sig = PEADModel().predict("TEST", "2025-08-01", fd)
        assert sig.value == 1.0
        assert sig.metadata["source_type"] == "8-K"

    def test_10q_only_period_is_neutral(self):
        # No 8-K for the period — 10-Q filing date is not the announcement
        fd = MockFDClient([_rec("2025-06-30", "2025-08-01", "BEAT", source_type="10-Q")])
        sig = PEADModel().predict("TEST", "2025-08-01", fd)
        assert sig.value == 0.0

    def test_10q_fallback_when_announcement_only_false(self):
        fd = MockFDClient([_rec("2025-06-30", "2025-08-01", "BEAT", source_type="10-Q")])
        sig = PEADModel(announcement_only=False).predict("TEST", "2025-08-01", fd)
        assert sig.value == 1.0
        assert sig.metadata["source_type"] == "10-Q"

    def test_dedup_earliest_8k_wins(self):
        # Two 8-Ks for the same period; keep the earlier filing date
        fd = MockFDClient([
            _rec("2025-06-30", "2025-08-15", "BEAT", source_type="8-K"),
            _rec("2025-06-30", "2025-08-01", "BEAT", source_type="8-K"),
        ])
        sig = PEADModel().predict("TEST", "2025-08-01", fd)
        assert sig.value == 1.0
        assert sig.metadata["filing_date"] == "2025-08-01"

    def test_returns_signal_type(self):
        fd = MockFDClient([_rec("2025-06-30", "2025-08-01", "BEAT")])
        sig = PEADModel().predict("TEST", "2025-08-01", fd)
        assert isinstance(sig, Signal)


# ---------------------------------------------------------------------------
# QuantModel._compute_rsi
# ---------------------------------------------------------------------------

# 60 closes: a rally, a sell-off, then a range.
_RSI_PRICES = [
    101.2, 100.8, 101.7, 102.0, 101.3, 102.5, 102.1, 103.0, 103.3, 102.6,
    103.8, 103.4, 104.3, 104.6, 103.9, 105.1, 104.7, 105.6, 105.9, 105.2,
    106.4, 106.0, 106.9, 107.2, 106.5, 105.4, 105.9, 105.1, 104.8, 105.4,
    104.3, 104.8, 104.0, 103.7, 104.3, 103.2, 103.7, 102.9, 102.6, 103.2,
    102.1, 102.6, 101.8, 101.5, 102.1, 102.5, 101.9, 102.6, 102.4, 102.5,
    102.9, 102.3, 103.0, 102.8, 102.9, 103.3, 102.7, 103.4, 103.2, 103.3,
]


class TestComputeRSI:
    def test_matches_talib(self):
        import pandas as pd

        # talib.RSI(np.array(_RSI_PRICES), 14)[-1] (TA-Lib 0.6) = 52.22076120167022.
        # The old rolling-mean version returned 57.142857 here.
        assert abs(QuantModel._compute_rsi(pd.Series(_RSI_PRICES)) - 52.22076120167022) < 1e-9

    def test_prefix_matches_talib(self):
        import pandas as pd

        # talib.RSI(...)[24] = 65.09848759625741 (latest value after the rally).
        assert abs(QuantModel._compute_rsi(pd.Series(_RSI_PRICES[:25])) - 65.09848759625741) < 1e-9

    def test_neutral_when_not_enough_data_or_flat(self):
        import pandas as pd

        assert QuantModel._compute_rsi(pd.Series(_RSI_PRICES[:14])) == 50.0
        assert QuantModel._compute_rsi(pd.Series([100.0] * 30)) == 50.0
        assert QuantModel._compute_rsi(pd.Series([], dtype=float)) == 50.0

    def test_ignores_missing_prices(self):
        import pandas as pd

        with_gap = pd.Series(_RSI_PRICES[:30] + [float("nan")] + _RSI_PRICES[30:])
        assert QuantModel._compute_rsi(with_gap) == QuantModel._compute_rsi(pd.Series(_RSI_PRICES))
