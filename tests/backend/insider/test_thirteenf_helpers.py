"""Tests for _sanitize_dataframe_records() in _helpers.py (Phase 1.1).

Verifies:
- NaN values are replaced with None in the output dicts
- Non-NaN values are preserved unchanged
- Empty DataFrame returns an empty list
"""
import math

import pandas as pd
import pytest


class TestSanitizeDataframeRecords:
    """Tests for the _sanitize_dataframe_records() helper."""

    def test_sanitize_replaces_nan_with_none(self) -> None:
        """NaN float values in DataFrame cells become None in the output dicts."""
        from app.backend.services.insider_service._helpers import _sanitize_dataframe_records

        df = pd.DataFrame([{"a": 1.0, "b": float("nan")}])
        records = _sanitize_dataframe_records(df)

        assert records[0]["a"] == 1.0
        assert records[0]["b"] is None

    def test_sanitize_preserves_non_nan_values(self) -> None:
        """String, int, and float values that are not NaN pass through unchanged."""
        from app.backend.services.insider_service._helpers import _sanitize_dataframe_records

        df = pd.DataFrame([{"name": "AAPL", "shares": 1000, "price": 175.5}])
        records = _sanitize_dataframe_records(df)

        assert records[0]["name"] == "AAPL"
        assert records[0]["shares"] == 1000
        assert records[0]["price"] == pytest.approx(175.5)

    def test_sanitize_handles_empty_dataframe(self) -> None:
        """Empty DataFrame returns an empty list without raising."""
        from app.backend.services.insider_service._helpers import _sanitize_dataframe_records

        records = _sanitize_dataframe_records(pd.DataFrame())

        assert records == []

    def test_sanitize_all_nan_columns_become_none(self) -> None:
        """A column that is entirely NaN results in all None values."""
        from app.backend.services.insider_service._helpers import _sanitize_dataframe_records

        df = pd.DataFrame([
            {"ticker": "AAPL", "value": float("nan")},
            {"ticker": "MSFT", "value": float("nan")},
        ])
        records = _sanitize_dataframe_records(df)

        assert records[0]["value"] is None
        assert records[1]["value"] is None

    def test_sanitize_mixed_rows_preserves_present_and_nulls_absent(self) -> None:
        """Rows with mixed NaN and non-NaN in the same column are each handled correctly."""
        from app.backend.services.insider_service._helpers import _sanitize_dataframe_records

        df = pd.DataFrame([
            {"ticker": "AAPL", "change_pct": 5.0},
            {"ticker": "MSFT", "change_pct": float("nan")},
        ])
        records = _sanitize_dataframe_records(df)

        assert records[0]["change_pct"] == pytest.approx(5.0)
        assert records[1]["change_pct"] is None

    def test_sanitize_returns_list_of_dicts(self) -> None:
        """Return type is a list of plain dicts (JSON-serializable structure)."""
        from app.backend.services.insider_service._helpers import _sanitize_dataframe_records

        df = pd.DataFrame([{"a": 1}])
        records = _sanitize_dataframe_records(df)

        assert isinstance(records, list)
        assert isinstance(records[0], dict)
