"""Tests for _fetch_ownership_changes() and get_ownership_changes() (Phase 5.2).

Verifies:
- shares_before computed as remaining_shares - net_change
- shares_before is None when remaining_shares is None
- records returned in ascending filing_date order
- insiders list sorted by activity count (most active first), top 10
- skipped_count increments on filing parse failure
- get_ownership_changes() cache hit returns cached response without re-fetching
- get_ownership_changes() cache miss triggers fetch and stores result
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.backend.insider.conftest import make_filing, make_transaction_summary

_COMPANY_PATCH = "edgar.Company"


# ---------------------------------------------------------------------------
# _fetch_ownership_changes
# ---------------------------------------------------------------------------


class TestFetchOwnershipChanges:
    """Tests for the synchronous _fetch_ownership_changes() worker."""

    def test_shares_before_computed_from_remaining_minus_net_change(self) -> None:
        """shares_before = remaining_shares - net_change for sale transactions."""
        # remaining=3280000, net_change=-50000 → shares_before = 3280000 - (-50000) = 3330000
        ts = make_transaction_summary(remaining_shares=3280000, net_change=-50000, insider_name="Tim Cook")
        filing = make_filing(summary_result=ts)

        with patch("app.backend.services.insider_service._ensure_identity"):
            with patch(_COMPANY_PATCH) as MockCompany:
                MockCompany.return_value.get_filings.return_value = [filing]
                from app.backend.services.insider_service import _fetch_ownership_changes
                response = _fetch_ownership_changes("AAPL", form_type="4", limit=10, offset=0)

        assert len(response.records) == 1
        record = response.records[0]
        assert record.shares_before == 3330000
        assert record.shares_after == 3280000
        assert record.net_change == -50000

    def test_shares_before_is_none_when_remaining_shares_is_none(self) -> None:
        """shares_before is None when remaining_shares is not available."""
        ts = make_transaction_summary(remaining_shares=None, net_change=-10000)
        filing = make_filing(summary_result=ts)

        with patch("app.backend.services.insider_service._ensure_identity"):
            with patch(_COMPANY_PATCH) as MockCompany:
                MockCompany.return_value.get_filings.return_value = [filing]
                from app.backend.services.insider_service import _fetch_ownership_changes
                response = _fetch_ownership_changes("AAPL", form_type="4", limit=10, offset=0)

        assert response.records[0].shares_before is None
        assert response.records[0].shares_after is None

    def test_records_are_ordered_ascending_by_filing_date(self) -> None:
        """Results are returned in ascending filing_date order (oldest first for chart rendering)."""
        ts = make_transaction_summary()
        filings = [
            make_filing(accession_no="NEW", filing_date="2024-06-01", summary_result=ts),
            make_filing(accession_no="OLD", filing_date="2024-01-01", summary_result=ts),
            make_filing(accession_no="MID", filing_date="2024-03-15", summary_result=ts),
        ]

        with patch("app.backend.services.insider_service._ensure_identity"):
            with patch(_COMPANY_PATCH) as MockCompany:
                MockCompany.return_value.get_filings.return_value = filings
                from app.backend.services.insider_service import _fetch_ownership_changes
                response = _fetch_ownership_changes("AAPL", form_type="4", limit=10, offset=0)

        dates = [r.filing_date for r in response.records]
        assert dates == sorted(dates)
        assert response.records[0].accession_no == "OLD"

    def test_insiders_sorted_by_activity_count_descending(self) -> None:
        """insiders list is sorted by activity count, most active first."""
        # Tim Cook: 3 filings, Luca Maestri: 1 filing
        ts_tim = make_transaction_summary(insider_name="Tim Cook")
        ts_luca = make_transaction_summary(insider_name="Luca Maestri")
        filings = [
            make_filing(accession_no="A1", filing_date="2024-01-01", summary_result=ts_tim),
            make_filing(accession_no="A2", filing_date="2024-02-01", summary_result=ts_luca),
            make_filing(accession_no="A3", filing_date="2024-03-01", summary_result=ts_tim),
            make_filing(accession_no="A4", filing_date="2024-04-01", summary_result=ts_tim),
        ]

        with patch("app.backend.services.insider_service._ensure_identity"):
            with patch(_COMPANY_PATCH) as MockCompany:
                MockCompany.return_value.get_filings.return_value = filings
                from app.backend.services.insider_service import _fetch_ownership_changes
                response = _fetch_ownership_changes("AAPL", form_type="4", limit=10, offset=0)

        assert response.insiders[0] == "Tim Cook"
        assert response.insiders[1] == "Luca Maestri"

    def test_insiders_limited_to_top_10(self) -> None:
        """insiders list contains at most 10 entries."""
        filings = [
            make_filing(
                accession_no=f"A{i}",
                filing_date=f"2024-{i:02d}-01" if i > 0 else "2024-01-01",
                summary_result=make_transaction_summary(insider_name=f"Insider {i}"),
            )
            for i in range(1, 16)
        ]

        with patch("app.backend.services.insider_service._ensure_identity"):
            with patch(_COMPANY_PATCH) as MockCompany:
                MockCompany.return_value.get_filings.return_value = filings
                from app.backend.services.insider_service import _fetch_ownership_changes
                response = _fetch_ownership_changes("AAPL", form_type="4", limit=20, offset=0)

        assert len(response.insiders) <= 10

    def test_skipped_count_increments_on_parse_failure(self) -> None:
        """Filing that raises on obj() increments skipped_count and is excluded from records."""
        good_filing = make_filing(summary_result=make_transaction_summary())
        bad_filing = make_filing(raise_on_obj=RuntimeError("parse error"))

        with patch("app.backend.services.insider_service._ensure_identity"):
            with patch(_COMPANY_PATCH) as MockCompany:
                MockCompany.return_value.get_filings.return_value = [bad_filing, good_filing]
                from app.backend.services.insider_service import _fetch_ownership_changes
                response = _fetch_ownership_changes("AAPL", form_type="4", limit=10, offset=0)

        assert response.skipped_count == 1
        assert len(response.records) == 1

    def test_total_reflects_successful_record_count(self) -> None:
        """total field equals the number of successfully parsed records."""
        ts = make_transaction_summary()
        filings = [make_filing(accession_no=f"A{i}", filing_date="2024-01-01", summary_result=ts) for i in range(3)]

        with patch("app.backend.services.insider_service._ensure_identity"):
            with patch(_COMPANY_PATCH) as MockCompany:
                MockCompany.return_value.get_filings.return_value = filings
                from app.backend.services.insider_service import _fetch_ownership_changes
                response = _fetch_ownership_changes("AAPL", form_type="4", limit=10, offset=0)

        assert response.total == 3

    def test_limit_caps_records(self) -> None:
        """limit parameter caps the number of processed filings."""
        ts = make_transaction_summary()
        filings = [make_filing(accession_no=f"A{i}", filing_date="2024-01-01", summary_result=ts) for i in range(10)]

        with patch("app.backend.services.insider_service._ensure_identity"):
            with patch(_COMPANY_PATCH) as MockCompany:
                MockCompany.return_value.get_filings.return_value = filings
                from app.backend.services.insider_service import _fetch_ownership_changes
                response = _fetch_ownership_changes("AAPL", form_type="4", limit=3, offset=0)

        assert len(response.records) == 3

    def test_offset_skips_first_n_filings(self) -> None:
        """offset parameter skips the first N filings."""
        ts = make_transaction_summary()
        filings = [
            make_filing(accession_no=f"A{i}", filing_date=f"2024-0{i+1}-01", summary_result=ts)
            for i in range(5)
        ]

        with patch("app.backend.services.insider_service._ensure_identity"):
            with patch(_COMPANY_PATCH) as MockCompany:
                MockCompany.return_value.get_filings.return_value = filings
                from app.backend.services.insider_service import _fetch_ownership_changes
                response = _fetch_ownership_changes("AAPL", form_type="4", limit=10, offset=2)

        assert len(response.records) == 3

    def test_shares_before_computed_correctly_for_purchase(self) -> None:
        """For a purchase (positive net_change): shares_before = remaining - net_change."""
        # remaining=5000, net_change=1000 → shares_before = 5000 - 1000 = 4000
        ts = make_transaction_summary(remaining_shares=5000, net_change=1000)
        filing = make_filing(summary_result=ts)

        with patch("app.backend.services.insider_service._ensure_identity"):
            with patch(_COMPANY_PATCH) as MockCompany:
                MockCompany.return_value.get_filings.return_value = [filing]
                from app.backend.services.insider_service import _fetch_ownership_changes
                response = _fetch_ownership_changes("AAPL", form_type="4", limit=10, offset=0)

        assert response.records[0].shares_before == 4000
        assert response.records[0].shares_after == 5000


# ---------------------------------------------------------------------------
# get_ownership_changes (async entry point + cache behavior)
# ---------------------------------------------------------------------------


class TestGetOwnershipChanges:
    """Tests for the async get_ownership_changes() cache behavior."""

    def _make_ownership_response(self, ticker: str = "AAPL"):
        from app.backend.models.insider_schemas import OwnershipChangeRecord, OwnershipChangesResponse
        record = OwnershipChangeRecord(
            filing_date="2024-03-15",
            accession_no="0000320193-24-000081",
            insider_name="Tim Cook",
            position="CEO",
            shares_before=3330000,
            shares_after=3280000,
            net_change=-50000,
            form_type="4",
        )
        return OwnershipChangesResponse(
            ticker=ticker,
            records=[record],
            insiders=["Tim Cook"],
            total=1,
            skipped_count=0,
        )

    @pytest.mark.asyncio
    async def test_cache_miss_calls_fetch_and_stores_result(self) -> None:
        """On cache miss, _fetch_ownership_changes is called and result is cached."""
        from app.backend.services.insider_service import _insider_cache, get_ownership_changes

        cache_key = "ownership:TSLA:4:50:0"
        _insider_cache.pop(cache_key, None)

        expected = self._make_ownership_response("TSLA")

        with patch("app.backend.services.insider_service._fetch_ownership_changes", return_value=expected) as mock_fetch:
            with patch("app.backend.services.insider_service._ensure_identity"):
                result = await get_ownership_changes("TSLA", form_type="4", limit=50, offset=0)

        mock_fetch.assert_called_once()
        assert result.ticker == "TSLA"
        assert cache_key in _insider_cache

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached_without_fetching(self) -> None:
        """On cache hit, _fetch_ownership_changes is NOT called."""
        from app.backend.services.insider_service import _cache_put, _insider_cache, get_ownership_changes

        cache_key = "ownership:MSFT:4:50:0"
        cached_response = self._make_ownership_response("MSFT")
        _cache_put(cache_key, cached_response)

        with patch("app.backend.services.insider_service._fetch_ownership_changes") as mock_fetch:
            result = await get_ownership_changes("MSFT", form_type="4", limit=50, offset=0)

        mock_fetch.assert_not_called()
        assert result.ticker == "MSFT"

        _insider_cache.pop(cache_key, None)
