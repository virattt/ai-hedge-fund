"""Tests for 13F-HR worker functions in _thirteenf.py.

Covers _fetch_thirteenf_filings(), _load_thirteenf_report(),
_fetch_compare_holdings(), and _fetch_holding_history() including
pagination, has_more flag, _ensure_identity() call order, year/quarter
passthrough, SEC error wrapping, LRU cache behavior, and ValueError
propagation for missing comparison/history data.
"""
from unittest.mock import MagicMock, patch
import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Helpers to build minimal mock objects
# ---------------------------------------------------------------------------

def _make_filing(
    company: str = "BERKSHIRE HATHAWAY INC",
    cik: int = 1067983,
    filing_date: str = "2026-03-15",
    accession_no: str = "0001234567-26-000001",
    form: str = "13F-HR",
) -> MagicMock:
    f = MagicMock()
    f.company = company
    f.cik = cik
    f.filing_date = filing_date
    f.accession_no = accession_no
    f.form = form
    return f


def _make_filings_collection(filing_list: list) -> MagicMock:
    """Return a mock Filings object whose len() and slicing match filing_list."""
    filings = MagicMock()
    filings.__len__ = MagicMock(return_value=len(filing_list))
    filings.__iter__ = MagicMock(return_value=iter(filing_list))
    filings.__getitem__ = MagicMock(side_effect=lambda s: filing_list[s])
    return filings


def _make_compare_df() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "Cusip": "023135106",
            "Ticker": "AMZN",
            "Issuer": "AMAZON COM INC",
            "Shares": 10000000,
            "Prev_Shares": 8000000,
            "Value": 1500000,
            "Prev_Value": 1200000,
            "Share_Change": 2000000,
            "Share_Change_Pct": 25.0,
            "Value_Change": 300000,
            "Value_Change_Pct": 25.0,
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
# _fetch_thirteenf_filings tests
# ---------------------------------------------------------------------------

class TestFetchThirteenFFilings:

    def test_fetch_filings_calls_ensure_identity_first(self) -> None:
        """_ensure_identity() must be called before edgar.get_filings()."""
        from app.backend.services.insider_service import _thirteenf

        call_order: list[str] = []

        filing = _make_filing()
        filings = _make_filings_collection([filing])

        def fake_ensure_identity() -> None:
            call_order.append("ensure_identity")

        def fake_get_filings(**kwargs: object) -> MagicMock:
            call_order.append("get_filings")
            return filings

        with patch.object(_thirteenf, "_ensure_identity", side_effect=fake_ensure_identity), \
             patch.object(_thirteenf, "_get_filings", side_effect=fake_get_filings):
            _thirteenf._fetch_thirteenf_filings(limit=10, offset=0, year=None, quarter=None)

        assert call_order == ["ensure_identity", "get_filings"]

    def test_fetch_filings_returns_paginated_list(self) -> None:
        """Returns ThirteenFListResponse with correct filings slice."""
        from app.backend.services.insider_service import _thirteenf
        from app.backend.models.insider_schemas import ThirteenFListResponse

        filings_data = [
            _make_filing(company=f"CO{i}", cik=i, accession_no=f"000000000{i}-26-000001")
            for i in range(5)
        ]
        filings = _make_filings_collection(filings_data)

        with patch.object(_thirteenf, "_ensure_identity"), \
             patch.object(_thirteenf, "_get_filings", return_value=filings):
            result = _thirteenf._fetch_thirteenf_filings(limit=3, offset=0, year=None, quarter=None)

        assert isinstance(result, ThirteenFListResponse)
        assert len(result.filings) == 3
        assert result.total == 5

    def test_fetch_filings_has_more_true_when_more_filings_exist(self) -> None:
        """has_more is True when offset + limit < total."""
        from app.backend.services.insider_service import _thirteenf

        filings_data = [_make_filing(company=f"CO{i}") for i in range(5)]
        filings = _make_filings_collection(filings_data)

        with patch.object(_thirteenf, "_ensure_identity"), \
             patch.object(_thirteenf, "_get_filings", return_value=filings):
            result = _thirteenf._fetch_thirteenf_filings(limit=3, offset=0, year=None, quarter=None)

        assert result.has_more is True

    def test_fetch_filings_has_more_false_at_end(self) -> None:
        """has_more is False when offset + limit >= total."""
        from app.backend.services.insider_service import _thirteenf

        filings_data = [_make_filing(company=f"CO{i}") for i in range(3)]
        filings = _make_filings_collection(filings_data)

        with patch.object(_thirteenf, "_ensure_identity"), \
             patch.object(_thirteenf, "_get_filings", return_value=filings):
            result = _thirteenf._fetch_thirteenf_filings(limit=3, offset=0, year=None, quarter=None)

        assert result.has_more is False

    def test_fetch_filings_passes_year_quarter_to_get_filings(self) -> None:
        """year and quarter are forwarded to edgar.get_filings() when not None."""
        from app.backend.services.insider_service import _thirteenf

        filings = _make_filings_collection([])

        with patch.object(_thirteenf, "_ensure_identity"), \
             patch.object(_thirteenf, "_get_filings", return_value=filings) as mock_gf:
            _thirteenf._fetch_thirteenf_filings(limit=20, offset=0, year=2026, quarter=1)

        mock_gf.assert_called_once()
        call_kwargs = mock_gf.call_args.kwargs
        assert call_kwargs.get("year") == 2026
        assert call_kwargs.get("quarter") == 1

    def test_fetch_filings_omits_year_quarter_when_none(self) -> None:
        """year and quarter keys are NOT forwarded when they are None."""
        from app.backend.services.insider_service import _thirteenf

        filings = _make_filings_collection([])

        with patch.object(_thirteenf, "_ensure_identity"), \
             patch.object(_thirteenf, "_get_filings", return_value=filings) as mock_gf:
            _thirteenf._fetch_thirteenf_filings(limit=20, offset=0, year=None, quarter=None)

        call_kwargs = mock_gf.call_args.kwargs
        assert "year" not in call_kwargs
        assert "quarter" not in call_kwargs

    def test_fetch_filings_raises_runtime_error_on_sec_failure(self) -> None:
        """SEC API errors are caught and re-raised as RuntimeError."""
        from app.backend.services.insider_service import _thirteenf

        with patch.object(_thirteenf, "_ensure_identity"), \
             patch.object(_thirteenf, "_get_filings", side_effect=Exception("network timeout")):
            with pytest.raises(RuntimeError, match="SEC API error"):
                _thirteenf._fetch_thirteenf_filings(limit=10, offset=0, year=None, quarter=None)

    def test_fetch_filings_maps_filing_attributes(self) -> None:
        """Filing attributes are correctly mapped to ThirteenFFilingListItem fields."""
        from app.backend.services.insider_service import _thirteenf

        filing = _make_filing(
            company="BERKSHIRE HATHAWAY INC",
            cik=1067983,
            filing_date="2026-03-15",
            accession_no="0001234567-26-000001",
            form="13F-HR",
        )
        filings = _make_filings_collection([filing])

        with patch.object(_thirteenf, "_ensure_identity"), \
             patch.object(_thirteenf, "_get_filings", return_value=filings):
            result = _thirteenf._fetch_thirteenf_filings(limit=10, offset=0, year=None, quarter=None)

        assert len(result.filings) == 1
        item = result.filings[0]
        assert item.company == "BERKSHIRE HATHAWAY INC"
        assert item.cik == 1067983
        assert item.accession_no == "0001234567-26-000001"
        assert item.form == "13F-HR"


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
        mock_compare.df = _make_compare_df()
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
        mock_history.df = _make_history_df()
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
        mock_history.df = _make_history_df()
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
