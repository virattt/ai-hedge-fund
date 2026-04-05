"""Tests for _fetch_grants() and get_insider_grants() (Phase 6.2).

Verifies:
- Derivative trades DataFrame rows are parsed into GrantRecord objects
- _classify_transaction_type applied to each row's Code and AcquiredDisposed columns
- Optional columns (ExercisePrice, ExpirationDate, Shares, UnderlyingSecurity) safely coerced
- skipped_count increments on per-filing parse failure without aborting
- limit/offset pagination works correctly
- get_insider_grants() cache hit returns cached response without re-fetching
- get_insider_grants() cache miss triggers fetch and stores result
"""
import asyncio
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from tests.backend.insider.conftest import make_filing, make_transaction_summary


_COMPANY_PATCH = "edgar.Company"


# ---------------------------------------------------------------------------
# Helpers for building fake derivative_trades DataFrames
# ---------------------------------------------------------------------------


def _make_derivative_df(rows: list[dict] | None = None) -> pd.DataFrame:
    """Build a fake derivative_trades DataFrame matching edgartools columns."""
    defaults = {
        "Security": "Common Stock Option",
        "Date": "2024-03-15",
        "Code": "M",
        "Shares": 50000.0,
        "Price": None,
        "ExercisePrice": 0.01,
        "ExpirationDate": "2030-01-01",
        "UnderlyingSecurity": "Common Stock",
        "AcquiredDisposed": "A",
    }
    if rows is None:
        rows = [defaults]
    # Fill missing keys with defaults
    normalized = []
    for row in rows:
        r = dict(defaults)
        r.update(row)
        normalized.append(r)
    return pd.DataFrame(normalized)


def _make_form4_with_trades(derivative_rows: list[dict] | None = None, raise_on_obj: Exception | None = None) -> MagicMock:
    """Build a mock filing whose form4.derivative_trades returns a DataFrame."""
    filing = MagicMock()
    filing.accession_no = "0000320193-24-000081"
    filing.filing_date = "2024-03-15"

    if raise_on_obj is not None:
        filing.obj.side_effect = raise_on_obj
    else:
        form4 = MagicMock()
        form4.derivative_trades = _make_derivative_df(derivative_rows)
        filing.obj.return_value = form4

    return filing


# ---------------------------------------------------------------------------
# _fetch_grants
# ---------------------------------------------------------------------------


class TestFetchGrants:
    """Tests for the synchronous _fetch_grants() worker."""

    def test_single_derivative_row_produces_one_record(self) -> None:
        """One derivative_trades row → one GrantRecord in the response."""
        filing = _make_form4_with_trades()

        with patch("app.backend.services.insider_service._ensure_identity"):
            with patch(_COMPANY_PATCH) as MockCompany:
                MockCompany.return_value.get_filings.return_value = [filing]
                from app.backend.services.insider_service._grants import _fetch_grants
                response = _fetch_grants("AAPL", form_type="4", limit=10, offset=0)

        assert len(response.records) == 1
        record = response.records[0]
        assert record.security_title == "Common Stock Option"
        assert record.code == "M"
        assert record.acquired_disposed == "A"
        assert record.transaction_type == "Exercise"

    def test_transaction_type_derived_from_classify_helper(self) -> None:
        """transaction_type uses _classify_transaction_type(code, acquired_disposed)."""
        filing = _make_form4_with_trades([{"Code": "A", "AcquiredDisposed": "A"}])

        with patch("app.backend.services.insider_service._ensure_identity"):
            with patch(_COMPANY_PATCH) as MockCompany:
                MockCompany.return_value.get_filings.return_value = [filing]
                from app.backend.services.insider_service._grants import _fetch_grants
                response = _fetch_grants("AAPL", form_type="4", limit=10, offset=0)

        assert response.records[0].transaction_type == "Grant"

    def test_sale_transaction_type(self) -> None:
        """Code with AcquiredDisposed='D' maps to 'Sale'."""
        filing = _make_form4_with_trades([{"Code": "M", "AcquiredDisposed": "D"}])

        with patch("app.backend.services.insider_service._ensure_identity"):
            with patch(_COMPANY_PATCH) as MockCompany:
                MockCompany.return_value.get_filings.return_value = [filing]
                from app.backend.services.insider_service._grants import _fetch_grants
                response = _fetch_grants("AAPL", form_type="4", limit=10, offset=0)

        assert response.records[0].transaction_type == "Sale"

    def test_exercise_price_coerced_to_float(self) -> None:
        """ExercisePrice column value is coerced to float."""
        filing = _make_form4_with_trades([{"ExercisePrice": "12.50"}])

        with patch("app.backend.services.insider_service._ensure_identity"):
            with patch(_COMPANY_PATCH) as MockCompany:
                MockCompany.return_value.get_filings.return_value = [filing]
                from app.backend.services.insider_service._grants import _fetch_grants
                response = _fetch_grants("AAPL", form_type="4", limit=10, offset=0)

        assert response.records[0].exercise_price == pytest.approx(12.50)

    def test_exercise_price_none_when_missing(self) -> None:
        """None ExercisePrice results in None on the record."""
        filing = _make_form4_with_trades([{"ExercisePrice": None}])

        with patch("app.backend.services.insider_service._ensure_identity"):
            with patch(_COMPANY_PATCH) as MockCompany:
                MockCompany.return_value.get_filings.return_value = [filing]
                from app.backend.services.insider_service._grants import _fetch_grants
                response = _fetch_grants("AAPL", form_type="4", limit=10, offset=0)

        assert response.records[0].exercise_price is None

    def test_shares_coerced_to_int(self) -> None:
        """Shares column value is coerced to int."""
        filing = _make_form4_with_trades([{"Shares": "25000.0"}])

        with patch("app.backend.services.insider_service._ensure_identity"):
            with patch(_COMPANY_PATCH) as MockCompany:
                MockCompany.return_value.get_filings.return_value = [filing]
                from app.backend.services.insider_service._grants import _fetch_grants
                response = _fetch_grants("AAPL", form_type="4", limit=10, offset=0)

        assert response.records[0].shares == 25000

    def test_shares_none_when_missing(self) -> None:
        """None Shares results in None on the record."""
        filing = _make_form4_with_trades([{"Shares": None}])

        with patch("app.backend.services.insider_service._ensure_identity"):
            with patch(_COMPANY_PATCH) as MockCompany:
                MockCompany.return_value.get_filings.return_value = [filing]
                from app.backend.services.insider_service._grants import _fetch_grants
                response = _fetch_grants("AAPL", form_type="4", limit=10, offset=0)

        assert response.records[0].shares is None

    def test_multiple_rows_from_single_filing(self) -> None:
        """Multiple derivative_trades rows in one filing produce multiple records."""
        filing = _make_form4_with_trades([
            {"Code": "A", "AcquiredDisposed": "A", "Security": "RSU"},
            {"Code": "M", "AcquiredDisposed": "A", "Security": "Stock Option"},
        ])

        with patch("app.backend.services.insider_service._ensure_identity"):
            with patch(_COMPANY_PATCH) as MockCompany:
                MockCompany.return_value.get_filings.return_value = [filing]
                from app.backend.services.insider_service._grants import _fetch_grants
                response = _fetch_grants("AAPL", form_type="4", limit=10, offset=0)

        assert len(response.records) == 2

    def test_skipped_count_increments_on_filing_parse_failure(self) -> None:
        """Filing that raises on obj() increments skipped_count and is excluded."""
        bad_filing = _make_form4_with_trades(raise_on_obj=RuntimeError("parse error"))
        good_filing = _make_form4_with_trades()

        with patch("app.backend.services.insider_service._ensure_identity"):
            with patch(_COMPANY_PATCH) as MockCompany:
                MockCompany.return_value.get_filings.return_value = [bad_filing, good_filing]
                from app.backend.services.insider_service._grants import _fetch_grants
                response = _fetch_grants("AAPL", form_type="4", limit=10, offset=0)

        assert response.skipped_count == 1
        assert len(response.records) == 1

    def test_empty_derivative_trades_df_skips_filing(self) -> None:
        """A filing with an empty derivative_trades DataFrame contributes 0 records."""
        filing = MagicMock()
        filing.accession_no = "0000320193-24-EMPTY"
        filing.filing_date = "2024-03-15"
        form4 = MagicMock()
        form4.derivative_trades = pd.DataFrame()
        filing.obj.return_value = form4

        with patch("app.backend.services.insider_service._ensure_identity"):
            with patch(_COMPANY_PATCH) as MockCompany:
                MockCompany.return_value.get_filings.return_value = [filing]
                from app.backend.services.insider_service._grants import _fetch_grants
                response = _fetch_grants("AAPL", form_type="4", limit=10, offset=0)

        assert len(response.records) == 0
        assert response.skipped_count == 0

    def test_limit_caps_filings_processed(self) -> None:
        """limit parameter caps the number of filings processed."""
        filings = [_make_form4_with_trades() for _ in range(10)]
        # Make each filing have unique accession_no
        for i, f in enumerate(filings):
            f.accession_no = f"ACC{i}"

        with patch("app.backend.services.insider_service._ensure_identity"):
            with patch(_COMPANY_PATCH) as MockCompany:
                MockCompany.return_value.get_filings.return_value = filings
                from app.backend.services.insider_service._grants import _fetch_grants
                response = _fetch_grants("AAPL", form_type="4", limit=3, offset=0)

        assert len(response.records) == 3

    def test_offset_skips_first_n_filings(self) -> None:
        """offset parameter skips the first N filings."""
        filings = []
        for i in range(5):
            f = _make_form4_with_trades()
            f.accession_no = f"ACC{i}"
            filings.append(f)

        with patch("app.backend.services.insider_service._ensure_identity"):
            with patch(_COMPANY_PATCH) as MockCompany:
                MockCompany.return_value.get_filings.return_value = filings
                from app.backend.services.insider_service._grants import _fetch_grants
                response = _fetch_grants("AAPL", form_type="4", limit=10, offset=2)

        assert len(response.records) == 3

    def test_total_reflects_record_count(self) -> None:
        """total equals the number of successfully parsed records."""
        filings = [_make_form4_with_trades() for _ in range(3)]
        for i, f in enumerate(filings):
            f.accession_no = f"ACC{i}"

        with patch("app.backend.services.insider_service._ensure_identity"):
            with patch(_COMPANY_PATCH) as MockCompany:
                MockCompany.return_value.get_filings.return_value = filings
                from app.backend.services.insider_service._grants import _fetch_grants
                response = _fetch_grants("AAPL", form_type="4", limit=10, offset=0)

        assert response.total == 3

    def test_ticker_uppercased_in_response(self) -> None:
        """ticker field in the response is uppercased."""
        filing = _make_form4_with_trades()

        with patch("app.backend.services.insider_service._ensure_identity"):
            with patch(_COMPANY_PATCH) as MockCompany:
                MockCompany.return_value.get_filings.return_value = [filing]
                from app.backend.services.insider_service._grants import _fetch_grants
                response = _fetch_grants("aapl", form_type="4", limit=10, offset=0)

        assert response.ticker == "AAPL"

    def test_insider_name_from_ownership_summary(self) -> None:
        """insider_name and position come from get_ownership_summary() on the filing."""
        filing = MagicMock()
        filing.accession_no = "ACC1"
        filing.filing_date = "2024-05-01"
        form4 = MagicMock()
        form4.derivative_trades = _make_derivative_df()

        summary = make_transaction_summary(
            insider_name="Luca Maestri",
            position="CFO",
            primary_activity="Exercise",
            net_change=50000,
            net_value=None,
            remaining_shares=None,
            has_10b5_1_plan=None,
            transaction_count=1,
        )
        form4.get_ownership_summary.return_value = summary
        filing.obj.return_value = form4

        with patch("app.backend.services.insider_service._ensure_identity"):
            with patch(_COMPANY_PATCH) as MockCompany:
                MockCompany.return_value.get_filings.return_value = [filing]
                from app.backend.services.insider_service._grants import _fetch_grants
                response = _fetch_grants("AAPL", form_type="4", limit=10, offset=0)

        assert response.records[0].insider_name == "Luca Maestri"
        assert response.records[0].position == "CFO"


# ---------------------------------------------------------------------------
# get_insider_grants (async entry point + cache behavior)
# ---------------------------------------------------------------------------


class TestGetInsiderGrants:
    """Tests for the async get_insider_grants() cache behavior."""

    def _make_grants_response(self, ticker: str = "AAPL"):
        from app.backend.models.insider_schemas import GrantRecord, GrantsResponse
        record = GrantRecord(
            filing_date="2024-03-15",
            accession_no="0000320193-24-000081",
            insider_name="Tim Cook",
            position="CEO",
            transaction_type="Exercise",
            security_title="Common Stock Option",
            acquired_disposed="A",
            code="M",
            shares=50000,
            exercise_price=0.01,
        )
        return GrantsResponse(ticker=ticker, records=[record], total=1, skipped_count=0)

    @pytest.mark.asyncio
    async def test_cache_miss_calls_fetch_and_stores_result(self) -> None:
        """On cache miss, _fetch_grants is called and result is cached."""
        import app.backend.services.insider_service as svc
        cache_key = "grants:TSLA:4:50:0"
        svc._insider_cache.pop(cache_key, None)

        expected = self._make_grants_response("TSLA")

        with patch("app.backend.services.insider_service._grants._fetch_grants", return_value=expected):
            from app.backend.services.insider_service import get_insider_grants
            result = await get_insider_grants("TSLA", form_type="4", limit=50, offset=0)

        assert result.ticker == "TSLA"
        assert cache_key in svc._insider_cache

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached_without_fetching(self) -> None:
        """On cache hit, _fetch_grants is NOT called."""
        import app.backend.services.insider_service as svc
        cache_key = "grants:MSFT:4:50:0"
        cached_response = self._make_grants_response("MSFT")
        svc._cache_put(cache_key, cached_response)

        with patch("app.backend.services.insider_service._grants._fetch_grants") as mock_fetch:
            from app.backend.services.insider_service import get_insider_grants
            result = await get_insider_grants("MSFT", form_type="4", limit=50, offset=0)

        mock_fetch.assert_not_called()
        assert result.ticker == "MSFT"

        svc._insider_cache.pop(cache_key, None)
