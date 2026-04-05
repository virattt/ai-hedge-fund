"""Tests for _parse_trade_rows() in _detail.py (Remediation.2).

Covers:
- Empty DataFrame, None input, non-DataFrame input
- Single market trade row: security_type, is_derivative, code, security_title
- Derivative flag=True vs False
- None price/shares handling → value=None
- value computation: round(shares * price, 2)
- Multiple rows → multiple records
- transaction_type from _classify_transaction_type
"""
from unittest.mock import patch

import pandas as pd
import pytest

from app.backend.models.insider_schemas import InsiderTransactionDetail


# ---------------------------------------------------------------------------
# DataFrame helpers (shared with test_detail_fetch.py via direct import)
# ---------------------------------------------------------------------------


def _make_market_df(rows: list[dict] | None = None) -> pd.DataFrame:
    """Build a fake market_trades DataFrame matching edgartools columns."""
    defaults = {
        "Security": "Common Stock",
        "Date": "2024-03-15",
        "Code": "S",
        "Shares": 25000.0,
        "Price": 175.0,
        "AcquiredDisposed": "D",
    }
    if rows is None:
        rows = [defaults]
    normalized = [dict(defaults, **row) for row in rows]
    return pd.DataFrame(normalized)


def _make_derivative_df(rows: list[dict] | None = None) -> pd.DataFrame:
    """Build a fake derivative_trades DataFrame matching edgartools columns."""
    defaults = {
        "Security": "Stock Option",
        "Date": "2024-03-15",
        "Code": "M",
        "Shares": 50000.0,
        "Price": None,
        "AcquiredDisposed": "A",
    }
    if rows is None:
        rows = [defaults]
    normalized = [dict(defaults, **row) for row in rows]
    return pd.DataFrame(normalized)


# ---------------------------------------------------------------------------
# _parse_trade_rows
# ---------------------------------------------------------------------------


class TestParseTradeRows:
    """Tests for the _parse_trade_rows() function."""

    def test_empty_dataframe_returns_empty_list(self) -> None:
        """An empty DataFrame returns an empty list without raising."""
        from app.backend.services.insider_service._detail import _parse_trade_rows

        assert _parse_trade_rows(pd.DataFrame(), is_derivative=False) == []

    def test_none_input_returns_empty_list(self) -> None:
        """None input (not a DataFrame) returns an empty list."""
        from app.backend.services.insider_service._detail import _parse_trade_rows

        assert _parse_trade_rows(None, is_derivative=False) == []

    def test_non_dataframe_input_returns_empty_list(self) -> None:
        """Non-DataFrame input (e.g. a string) returns an empty list."""
        from app.backend.services.insider_service._detail import _parse_trade_rows

        assert _parse_trade_rows("not a dataframe", is_derivative=False) == []

    def test_single_market_trade_row_parsed(self) -> None:
        """Single market_trades row produces one InsiderTransactionDetail."""
        from app.backend.services.insider_service._detail import _parse_trade_rows

        result = _parse_trade_rows(_make_market_df(), is_derivative=False)

        assert len(result) == 1
        record = result[0]
        assert isinstance(record, InsiderTransactionDetail)
        assert record.security_type == "non-derivative"
        assert record.is_derivative is False
        assert record.security_title == "Common Stock"
        assert record.code == "S"

    def test_derivative_flag_true_sets_type_and_field(self) -> None:
        """is_derivative=True sets security_type='derivative' and is_derivative=True."""
        from app.backend.services.insider_service._detail import _parse_trade_rows

        result = _parse_trade_rows(_make_derivative_df(), is_derivative=True)

        assert result[0].security_type == "derivative"
        assert result[0].is_derivative is True

    def test_derivative_flag_false_sets_type_and_field(self) -> None:
        """is_derivative=False sets security_type='non-derivative' and is_derivative=False."""
        from app.backend.services.insider_service._detail import _parse_trade_rows

        result = _parse_trade_rows(_make_market_df(), is_derivative=False)

        assert result[0].security_type == "non-derivative"
        assert result[0].is_derivative is False

    def test_value_computed_shares_times_price_rounded(self) -> None:
        """value = round(shares * price, 2) when both are provided."""
        from app.backend.services.insider_service._detail import _parse_trade_rows

        df = _make_market_df([{"Shares": 123.456, "Price": 10.0, "AcquiredDisposed": "D", "Code": "S", "Security": "CS"}])
        result = _parse_trade_rows(df, is_derivative=False)

        assert result[0].value == pytest.approx(round(123.456 * 10.0, 2))

    def test_value_none_when_price_none(self) -> None:
        """value is None when Price is missing/None."""
        from app.backend.services.insider_service._detail import _parse_trade_rows

        df = _make_market_df([{"Shares": 1000.0, "Price": None, "AcquiredDisposed": "D", "Code": "S", "Security": "CS"}])
        result = _parse_trade_rows(df, is_derivative=False)

        assert result[0].value is None

    def test_value_none_when_shares_none(self) -> None:
        """value is None when Shares is missing/None."""
        from app.backend.services.insider_service._detail import _parse_trade_rows

        df = _make_market_df([{"Shares": None, "Price": 100.0, "AcquiredDisposed": "D", "Code": "S", "Security": "CS"}])
        result = _parse_trade_rows(df, is_derivative=False)

        assert result[0].value is None

    def test_price_per_share_stored(self) -> None:
        """price_per_share is populated from the Price column."""
        from app.backend.services.insider_service._detail import _parse_trade_rows

        df = _make_market_df([{"Price": 200.0, "Shares": 500.0, "AcquiredDisposed": "D", "Code": "S", "Security": "CS"}])
        assert _parse_trade_rows(df, is_derivative=False)[0].price_per_share == pytest.approx(200.0)

    def test_shares_stored(self) -> None:
        """shares is populated from the Shares column."""
        from app.backend.services.insider_service._detail import _parse_trade_rows

        df = _make_market_df([{"Shares": 999.0, "Price": 1.0, "AcquiredDisposed": "D", "Code": "S", "Security": "CS"}])
        assert _parse_trade_rows(df, is_derivative=False)[0].shares == pytest.approx(999.0)

    def test_multiple_rows_produce_multiple_records(self) -> None:
        """Multiple DataFrame rows produce multiple InsiderTransactionDetail records."""
        from app.backend.services.insider_service._detail import _parse_trade_rows

        df = _make_market_df([
            {"Code": "S", "AcquiredDisposed": "D", "Shares": 100.0, "Price": 10.0, "Security": "CS"},
            {"Code": "P", "AcquiredDisposed": "A", "Shares": 200.0, "Price": 20.0, "Security": "CS2"},
        ])
        assert len(_parse_trade_rows(df, is_derivative=False)) == 2

    def test_transaction_type_from_classify_helper(self) -> None:
        """transaction_type uses _classify_transaction_type(code, acquired_disposed)."""
        from app.backend.services.insider_service._detail import _parse_trade_rows

        df = _make_market_df([{"Code": "P", "AcquiredDisposed": "A", "Shares": 100.0, "Price": 10.0, "Security": "CS"}])
        assert _parse_trade_rows(df, is_derivative=False)[0].transaction_type == "Purchase"
