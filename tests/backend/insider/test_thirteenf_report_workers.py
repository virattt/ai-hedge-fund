"""Tests for 13F-HR report worker functions in _thirteenf.py.

Covers _load_thirteenf_report(), _fetch_compare_holdings(), and
_fetch_holding_history() including LRU cache behavior, ValueError
propagation for missing comparison/history data, and RuntimeError
wrapping on SEC API errors.
"""
from unittest.mock import MagicMock, patch
import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Helpers to build minimal mock DataFrames
# ---------------------------------------------------------------------------

def _make_compare_df() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "Cusip": "023135106",
            "Ticker": "AMZN",
            "Issuer": "AMAZON COM INC",
            "Shares": 10000000,
            "PrevShares": 8000000,
            "Value": 1500000,
            "PrevValue": 1200000,
            "ShareChange": 2000000,
            "ShareChangePct": 25.0,
            "ValueChange": 300000,
            "ValueChangePct": 25.0,
            "Status": "INCREASED",
        }
    ])


def _make_history_df() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "Cusip": "023135106",
            "Ticker": "AMZN",
            "Issuer": "AMAZON COM INC",
            "2025-03-31": 7000000,
            "2025-06-30": 8000000,
            "2025-09-30": 9000000,
            "2025-12-31": 10000000,
        }
    ])


# ---------------------------------------------------------------------------
# _load_thirteenf_report tests
# ---------------------------------------------------------------------------

class TestLoadThirteenFReport:

    def setup_method(self) -> None:
        """Clear LRU cache before each test to avoid cross-test pollution."""
        from app.backend.services.insider_service import _thirteenf
        _thirteenf._load_thirteenf_report.cache_clear()

    def test_load_thirteenf_report_calls_ensure_identity(self) -> None:
        """_ensure_identity() is called inside _load_thirteenf_report."""
        from app.backend.services.insider_service import _thirteenf

        mock_filing = MagicMock()
        mock_filing.obj.return_value = MagicMock()

        with patch.object(_thirteenf, "_ensure_identity") as mock_ei, \
             patch.object(_thirteenf, "_find_filing", return_value=mock_filing):
            _thirteenf._load_thirteenf_report("0001234567-26-000001")

        mock_ei.assert_called_once()

    def test_load_thirteenf_report_raises_value_error_when_not_found(self) -> None:
        """Raises ValueError when find() returns None (filing not in EDGAR)."""
        from app.backend.services.insider_service import _thirteenf

        with patch.object(_thirteenf, "_ensure_identity"), \
             patch.object(_thirteenf, "_find_filing", return_value=None):
            with pytest.raises(ValueError, match="not found"):
                _thirteenf._load_thirteenf_report("0001234567-26-000001")

    def test_load_thirteenf_report_raises_on_sec_error(self) -> None:
        """SEC API errors during find() are re-raised as RuntimeError."""
        from app.backend.services.insider_service import _thirteenf

        with patch.object(_thirteenf, "_ensure_identity"), \
             patch.object(_thirteenf, "_find_filing", side_effect=Exception("SEC timeout")):
            with pytest.raises(RuntimeError, match="SEC API error"):
                _thirteenf._load_thirteenf_report("0001234567-26-000001")

    def test_load_thirteenf_report_caches_repeated_calls(self) -> None:
        """The same accession_no hits the LRU cache on the second call."""
        from app.backend.services.insider_service import _thirteenf

        mock_filing = MagicMock()
        mock_report = MagicMock()
        mock_filing.obj.return_value = mock_report

        with patch.object(_thirteenf, "_ensure_identity"), \
             patch.object(_thirteenf, "_find_filing", return_value=mock_filing) as mock_find:
            _thirteenf._load_thirteenf_report("0001234567-26-000001")
            _thirteenf._load_thirteenf_report("0001234567-26-000001")

        # find() should only be called once due to LRU cache
        assert mock_find.call_count == 1


# ---------------------------------------------------------------------------
# _fetch_compare_holdings tests
# ---------------------------------------------------------------------------

class TestFetchCompareHoldings:

    def setup_method(self) -> None:
        """Clear LRU cache before each test."""
        from app.backend.services.insider_service import _thirteenf
        _thirteenf._load_thirteenf_report.cache_clear()

    def test_fetch_compare_holdings_returns_records(self) -> None:
        """Returns CompareHoldingsResponse when compare_holdings() returns a DataFrame."""
        from app.backend.services.insider_service import _thirteenf
        from app.backend.models.insider_schemas import CompareHoldingsResponse

        mock_report = MagicMock()
        mock_compare = MagicMock()
        mock_compare.data = _make_compare_df()
        mock_compare.current_period = "2025-12-31"
        mock_compare.previous_period = "2025-09-30"
        mock_compare.manager_name = "BERKSHIRE HATHAWAY INC"
        mock_report.compare_holdings.return_value = mock_compare

        with patch.object(_thirteenf, "_load_thirteenf_report", return_value=mock_report):
            result = _thirteenf._fetch_compare_holdings("0001234567-26-000001")

        assert isinstance(result, CompareHoldingsResponse)
        assert result.accession_no == "0001234567-26-000001"
        assert result.total == 1
        assert len(result.records) == 1

    def test_fetch_compare_holdings_raises_when_none(self) -> None:
        """Raises ValueError when compare_holdings() returns None."""
        from app.backend.services.insider_service import _thirteenf

        mock_report = MagicMock()
        mock_report.compare_holdings.return_value = None

        with patch.object(_thirteenf, "_load_thirteenf_report", return_value=mock_report):
            with pytest.raises(ValueError, match="No comparison data"):
                _thirteenf._fetch_compare_holdings("0001234567-26-000001")

    def test_fetch_compare_holdings_raises_when_filing_not_found(self) -> None:
        """Raises ValueError when _load_thirteenf_report raises ValueError."""
        from app.backend.services.insider_service import _thirteenf

        with patch.object(_thirteenf, "_load_thirteenf_report", side_effect=ValueError("not found")):
            with pytest.raises(ValueError):
                _thirteenf._fetch_compare_holdings("0001234567-26-000001")


# ---------------------------------------------------------------------------
# _fetch_holding_history tests
# ---------------------------------------------------------------------------

class TestFetchHoldingHistory:

    def setup_method(self) -> None:
        """Clear LRU cache before each test."""
        from app.backend.services.insider_service import _thirteenf
        _thirteenf._load_thirteenf_report.cache_clear()

    def test_fetch_holding_history_returns_records_with_periods_data(self) -> None:
        """Returns HoldingHistoryResponse with nested periods_data per record."""
        from app.backend.services.insider_service import _thirteenf
        from app.backend.models.insider_schemas import HoldingHistoryResponse

        mock_report = MagicMock()
        mock_history = MagicMock()
        mock_history.data = _make_history_df()
        mock_history.manager_name = "BERKSHIRE HATHAWAY INC"
        mock_report.holding_history.return_value = mock_history

        with patch.object(_thirteenf, "_load_thirteenf_report", return_value=mock_report):
            result = _thirteenf._fetch_holding_history("0001234567-26-000001", periods=4)

        assert isinstance(result, HoldingHistoryResponse)
        assert result.accession_no == "0001234567-26-000001"
        assert result.total == 1
        # periods list should contain the 4 period column headers
        assert len(result.periods) == 4
        # Each record has periods_data nested dict
        record = result.records[0]
        assert isinstance(record.periods_data, dict)
        assert len(record.periods_data) == 4
        assert record.cusip == "023135106"
        assert record.ticker == "AMZN"

    def test_fetch_holding_history_passes_periods_to_call(self) -> None:
        """holding_history() is called with the given periods argument."""
        from app.backend.services.insider_service import _thirteenf

        mock_report = MagicMock()
        mock_history = MagicMock()
        mock_history.data = _make_history_df()
        mock_history.manager_name = "TEST MANAGER"
        mock_report.holding_history.return_value = mock_history

        with patch.object(_thirteenf, "_load_thirteenf_report", return_value=mock_report):
            _thirteenf._fetch_holding_history("0001234567-26-000001", periods=6)

        mock_report.holding_history.assert_called_once_with(periods=6)

    def test_fetch_holding_history_raises_when_none(self) -> None:
        """Raises ValueError when holding_history() returns None."""
        from app.backend.services.insider_service import _thirteenf

        mock_report = MagicMock()
        mock_report.holding_history.return_value = None

        with patch.object(_thirteenf, "_load_thirteenf_report", return_value=mock_report):
            with pytest.raises(ValueError, match="No holding history"):
                _thirteenf._fetch_holding_history("0001234567-26-000001", periods=4)

    def test_fetch_holding_history_raises_when_filing_not_found(self) -> None:
        """Raises ValueError when _load_thirteenf_report raises ValueError."""
        from app.backend.services.insider_service import _thirteenf

        with patch.object(_thirteenf, "_load_thirteenf_report", side_effect=ValueError("not found")):
            with pytest.raises(ValueError):
                _thirteenf._fetch_holding_history("0001234567-26-000001", periods=4)
