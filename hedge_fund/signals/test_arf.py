"""Tests for ARFModel (AI Relevance Factor alpha model)."""

from __future__ import annotations

import pandas as pd
import pytest

from hedge_fund.signals import ALPHA_MODEL_REGISTRY, ARFModel, QuantModel, get_investment_approach
from hedge_fund.signals.base import AlphaModel


class MockDataClient:
    """Mock DataClient for testing without external services."""
    pass


@pytest.fixture
def sample_snapshots_df() -> pd.DataFrame:
    """Fixture containing sample ARF snapshots across multiple dates."""
    return pd.DataFrame([
        # NVDA on 2026-06-01: High exposure, low valuation stretch, high ROE
        {
            "ticker": "NVDA",
            "as_of_date": "2026-06-01",
            "leg": "US",
            "arf": 55.0,
            "decile": 5,
            "froth_flag": False,
            "e_score": 98.0,
            "v_score": 20.0,
            "implied_growth_gap": -0.85,
            "roe": 1.15,
            "ps_ratio": 18.0,
        },
        # NVDA on 2026-07-01 (later snapshot)
        {
            "ticker": "NVDA",
            "as_of_date": "2026-07-01",
            "leg": "US",
            "arf": 58.0,
            "decile": 5,
            "froth_flag": False,
            "e_score": 97.0,
            "v_score": 22.0,
            "implied_growth_gap": -0.88,
            "roe": 1.17,
            "ps_ratio": 17.5,
        },
        # LITE on 2026-06-01: Froth Flag triggered
        {
            "ticker": "LITE",
            "as_of_date": "2026-06-01",
            "leg": "US",
            "arf": 100.0,
            "decile": 1,
            "froth_flag": True,
            "e_score": 87.0,
            "v_score": 100.0,
            "implied_growth_gap": None,
            "roe": -2.40,
            "ps_ratio": 28.0,
        },
        # INTC on 2026-06-01: Low exposure, high stretch
        {
            "ticker": "INTC",
            "as_of_date": "2026-06-01",
            "leg": "US",
            "arf": 75.0,
            "decile": 3,
            "froth_flag": False,
            "e_score": 25.0,
            "v_score": 95.0,
            "implied_growth_gap": None,
            "roe": -0.05,
            "ps_ratio": 2.5,
        },
    ])


class TestARFInterface:
    def test_registered_and_subclass(self):
        assert issubclass(ARFModel, QuantModel)
        assert issubclass(ARFModel, AlphaModel)
        assert "arf" in ALPHA_MODEL_REGISTRY
        assert ALPHA_MODEL_REGISTRY["arf"] is ARFModel

    def test_name(self, sample_snapshots_df):
        model = ARFModel(snapshots_df=sample_snapshots_df)
        assert model.name == "arf"

    def test_investment_approach(self):
        assert get_investment_approach("arf") == "long_short"


class TestARFPredict:
    def test_froth_flag_triggers_strong_short(self, sample_snapshots_df):
        model = ARFModel(snapshots_df=sample_snapshots_df)
        sig = model.predict("LITE", "2026-06-15", MockDataClient())
        assert sig.value == -1.0
        assert sig.model_name == "arf"
        assert "Froth Warning" in sig.reasoning
        assert sig.components["froth_flag"] == 1.0

    def test_quality_compounder_triggers_strong_long(self, sample_snapshots_df):
        model = ARFModel(snapshots_df=sample_snapshots_df)
        sig = model.predict("NVDA", "2026-06-15", MockDataClient())
        # (98 - 20) / 100 = 0.78 + 0.15 quality bonus = 0.93
        assert sig.value > 0.8
        assert sig.model_name == "arf"
        assert "Bullish" in sig.reasoning
        assert sig.components["e_score"] == 98.0
        assert sig.components["v_score"] == 20.0

    def test_point_in_time_selection(self, sample_snapshots_df):
        model = ARFModel(snapshots_df=sample_snapshots_df)
        # As of 2026-06-15, only the 2026-06-01 snapshot is visible
        sig_june = model.predict("NVDA", "2026-06-15", MockDataClient())
        assert sig_june.metadata["snapshot_date"] == "2026-06-01"

        # As of 2026-07-05, the 2026-07-01 snapshot is visible
        sig_july = model.predict("NVDA", "2026-07-05", MockDataClient())
        assert sig_july.metadata["snapshot_date"] == "2026-07-01"

    def test_speculative_multiple_stretch_short(self, sample_snapshots_df):
        model = ARFModel(snapshots_df=sample_snapshots_df)
        sig = model.predict("INTC", "2026-06-15", MockDataClient())
        # (25 - 95)/100 - 0.2 penalty = -0.90
        assert sig.value < -0.6
        assert "Bearish" in sig.reasoning

    def test_unknown_ticker_abstains(self, sample_snapshots_df):
        model = ARFModel(snapshots_df=sample_snapshots_df)
        sig = model.predict("UNKNOWN_XYZ", "2026-06-15", MockDataClient())
        assert sig.value == 0.0
        assert sig.metadata.get("abstained") is True


class TestARFRealDatabase:
    def test_loads_from_real_arf_db(self):
        """Test against real arf.db if it exists on disk."""
        db_path = "/Users/sheng/Developer/ARF/data/arf.db"
        model = ARFModel(db_path=db_path)
        if model._df.empty:
            pytest.skip("ARF database not found at expected path")

        sig = model.predict("NVDA", "2026-09-15", MockDataClient())
        assert sig.model_name == "arf"
        assert sig.ticker == "NVDA"
        assert sig.value > 0.0
        assert sig.components["e_score"] > 90.0
