"""Tests for 13F-HR async cache entry points in insider_service/__init__.py.

Covers get_thirteenf_filings(), get_compare_holdings(), and get_holding_history()
including cache hit/miss behavior, date-aware listing cache key, and ValueError
propagation for detail endpoints.
"""
from collections.abc import Generator
from datetime import date
from unittest.mock import patch

import pytest

import app.backend.services.insider_service as insider_service
from app.backend.models.insider_schemas import (
    CompareHoldingsResponse,
    HoldingHistoryResponse,
    ThirteenFListResponse,
)


# ---------------------------------------------------------------------------
# Helpers to build minimal response objects
# ---------------------------------------------------------------------------


def _make_list_response() -> ThirteenFListResponse:
    return ThirteenFListResponse(filings=[], total=0, has_more=False, skipped_count=0)


def _make_compare_response() -> CompareHoldingsResponse:
    return CompareHoldingsResponse(
        accession_no="0001234567-26-000001",
        current_period="2025-12-31",
        previous_period="2025-09-30",
        manager_name="ACME CORP",
        records=[],
        total=0,
    )


def _make_history_response() -> HoldingHistoryResponse:
    return HoldingHistoryResponse(
        accession_no="0001234567-26-000001",
        manager_name="ACME CORP",
        periods=[],
        records=[],
        total=0,
    )


# ---------------------------------------------------------------------------
# Fixture: clear cache before each test
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clear_cache() -> Generator[None, None, None]:
    """Clear the insider cache before each test to ensure isolation."""
    insider_service._insider_cache.clear()
    yield
    insider_service._insider_cache.clear()


# ---------------------------------------------------------------------------
# get_thirteenf_filings tests
# ---------------------------------------------------------------------------


class TestGetThirteenFFilings:
    """Tests for get_thirteenf_filings() cache entry point."""

    @pytest.mark.asyncio
    async def test_cache_miss_calls_worker(self) -> None:
        """Cache miss calls _fetch_thirteenf_filings via asyncio.to_thread."""
        expected = _make_list_response()
        with patch.object(
            insider_service,
            "_fetch_thirteenf_filings",
            return_value=expected,
        ) as mock_worker:
            result = await insider_service.get_thirteenf_filings(20, 0, None, None)

        assert result == expected
        mock_worker.assert_called_once_with(20, 0, None, None, None)

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached(self) -> None:
        """Second call returns cached value without calling worker again."""
        expected = _make_list_response()
        with patch.object(
            insider_service,
            "_fetch_thirteenf_filings",
            return_value=expected,
        ) as mock_worker:
            await insider_service.get_thirteenf_filings(20, 0, None, None)
            result = await insider_service.get_thirteenf_filings(20, 0, None, None)

        assert result == expected
        assert mock_worker.call_count == 1

    @pytest.mark.asyncio
    async def test_cache_key_includes_date(self) -> None:
        """Listing cache key includes today's date to ensure daily expiry."""
        expected = _make_list_response()
        today = date.today().isoformat()

        with patch.object(
            insider_service,
            "_fetch_thirteenf_filings",
            return_value=expected,
        ):
            await insider_service.get_thirteenf_filings(20, 0, 2026, 1)

        matching_keys = [k for k in insider_service._insider_cache if today in k]
        assert len(matching_keys) == 1
        assert "thirteenf:filings:" in matching_keys[0]
        assert "2026" in matching_keys[0]
        assert "1" in matching_keys[0]

    @pytest.mark.asyncio
    async def test_cache_key_includes_limit_and_offset(self) -> None:
        """Different limit/offset values produce different cache keys."""
        expected = _make_list_response()
        with patch.object(
            insider_service,
            "_fetch_thirteenf_filings",
            return_value=expected,
        ) as mock_worker:
            await insider_service.get_thirteenf_filings(20, 0, None, None)
            await insider_service.get_thirteenf_filings(20, 20, None, None)

        assert mock_worker.call_count == 2

    @pytest.mark.asyncio
    async def test_passes_year_and_quarter_to_worker(self) -> None:
        """Year and quarter are forwarded to the worker function."""
        expected = _make_list_response()
        with patch.object(
            insider_service,
            "_fetch_thirteenf_filings",
            return_value=expected,
        ) as mock_worker:
            await insider_service.get_thirteenf_filings(10, 0, 2025, 4)

        mock_worker.assert_called_once_with(10, 0, 2025, 4, None)

    @pytest.mark.asyncio
    async def test_cache_key_includes_company_name(self) -> None:
        """company_name is included in cache key, producing distinct entries."""
        expected = _make_list_response()
        with patch.object(
            insider_service,
            "_fetch_thirteenf_filings",
            return_value=expected,
        ) as mock_worker:
            # First call with company_name populates a keyed entry.
            await insider_service.get_thirteenf_filings(20, 0, None, None, company_name="Berkshire")
            # Second call with same params hits the cache — worker not called again.
            await insider_service.get_thirteenf_filings(20, 0, None, None, company_name="Berkshire")

        assert mock_worker.call_count == 1

        matching_keys = [k for k in insider_service._insider_cache if "Berkshire" in k]
        assert len(matching_keys) == 1

    @pytest.mark.asyncio
    async def test_different_company_names_produce_different_cache_keys(self) -> None:
        """Different company_name values result in separate cache entries (cache misses)."""
        expected = _make_list_response()
        with patch.object(
            insider_service,
            "_fetch_thirteenf_filings",
            return_value=expected,
        ) as mock_worker:
            await insider_service.get_thirteenf_filings(20, 0, None, None, company_name="Berkshire")
            await insider_service.get_thirteenf_filings(20, 0, None, None, company_name="BlackRock")

        assert mock_worker.call_count == 2

    @pytest.mark.asyncio
    async def test_empty_company_name_normalized_to_none(self) -> None:
        """Empty string company_name is normalized to None before cache key construction."""
        expected = _make_list_response()
        with patch.object(
            insider_service,
            "_fetch_thirteenf_filings",
            return_value=expected,
        ) as mock_worker:
            await insider_service.get_thirteenf_filings(20, 0, None, None, company_name="")
            # Should hit the same cache entry as company_name=None.
            await insider_service.get_thirteenf_filings(20, 0, None, None, company_name=None)

        assert mock_worker.call_count == 1

    @pytest.mark.asyncio
    async def test_whitespace_company_name_normalized_to_none(self) -> None:
        """Whitespace-only company_name is normalized to None before cache key construction."""
        expected = _make_list_response()
        with patch.object(
            insider_service,
            "_fetch_thirteenf_filings",
            return_value=expected,
        ) as mock_worker:
            await insider_service.get_thirteenf_filings(20, 0, None, None, company_name="   ")
            # Should hit the same cache entry as company_name=None.
            await insider_service.get_thirteenf_filings(20, 0, None, None, company_name=None)

        assert mock_worker.call_count == 1

    @pytest.mark.asyncio
    async def test_company_name_passed_through_to_worker(self) -> None:
        """Normalized company_name is forwarded to _fetch_thirteenf_filings."""
        expected = _make_list_response()
        with patch.object(
            insider_service,
            "_fetch_thirteenf_filings",
            return_value=expected,
        ) as mock_worker:
            await insider_service.get_thirteenf_filings(20, 0, None, None, company_name="Berkshire")

        mock_worker.assert_called_once_with(20, 0, None, None, "Berkshire")


# ---------------------------------------------------------------------------
# get_compare_holdings tests
# ---------------------------------------------------------------------------


class TestGetCompareHoldings:
    """Tests for get_compare_holdings() cache entry point."""

    @pytest.mark.asyncio
    async def test_cache_miss_calls_worker(self) -> None:
        """Cache miss calls _fetch_compare_holdings via asyncio.to_thread."""
        acc = "0001234567-26-000001"
        expected = _make_compare_response()
        with patch.object(
            insider_service,
            "_fetch_compare_holdings",
            return_value=expected,
        ) as mock_worker:
            result = await insider_service.get_compare_holdings(acc)

        assert result == expected
        mock_worker.assert_called_once_with(acc)

    @pytest.mark.asyncio
    async def test_cache_hit_skips_fetch(self) -> None:
        """Second call returns cached value without calling worker again."""
        acc = "0001234567-26-000001"
        expected = _make_compare_response()
        with patch.object(
            insider_service,
            "_fetch_compare_holdings",
            return_value=expected,
        ) as mock_worker:
            await insider_service.get_compare_holdings(acc)
            result = await insider_service.get_compare_holdings(acc)

        assert result == expected
        assert mock_worker.call_count == 1

    @pytest.mark.asyncio
    async def test_propagates_value_error(self) -> None:
        """ValueError from worker propagates without being caught."""
        acc = "0001234567-26-000001"
        with patch.object(
            insider_service,
            "_fetch_compare_holdings",
            side_effect=ValueError("No comparison data"),
        ):
            with pytest.raises(ValueError, match="No comparison data"):
                await insider_service.get_compare_holdings(acc)

    @pytest.mark.asyncio
    async def test_cache_key_contains_accession_no(self) -> None:
        """Cache key for compare uses the accession number."""
        acc = "0001234567-26-000001"
        expected = _make_compare_response()
        with patch.object(
            insider_service,
            "_fetch_compare_holdings",
            return_value=expected,
        ):
            await insider_service.get_compare_holdings(acc)

        matching_keys = [k for k in insider_service._insider_cache if acc in k and "compare" in k]
        assert len(matching_keys) == 1


# ---------------------------------------------------------------------------
# get_holding_history tests
# ---------------------------------------------------------------------------


class TestGetHoldingHistory:
    """Tests for get_holding_history() cache entry point."""

    @pytest.mark.asyncio
    async def test_cache_miss_calls_worker(self) -> None:
        """Cache miss calls _fetch_holding_history via asyncio.to_thread."""
        acc = "0001234567-26-000001"
        expected = _make_history_response()
        with patch.object(
            insider_service,
            "_fetch_holding_history",
            return_value=expected,
        ) as mock_worker:
            result = await insider_service.get_holding_history(acc, 4)

        assert result == expected
        mock_worker.assert_called_once_with(acc, 4)

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached(self) -> None:
        """Second call with same args returns cached value."""
        acc = "0001234567-26-000001"
        expected = _make_history_response()
        with patch.object(
            insider_service,
            "_fetch_holding_history",
            return_value=expected,
        ) as mock_worker:
            await insider_service.get_holding_history(acc, 4)
            result = await insider_service.get_holding_history(acc, 4)

        assert result == expected
        assert mock_worker.call_count == 1

    @pytest.mark.asyncio
    async def test_different_periods_produces_different_cache_keys(self) -> None:
        """Different periods values produce separate cache entries."""
        acc = "0001234567-26-000001"
        expected = _make_history_response()
        with patch.object(
            insider_service,
            "_fetch_holding_history",
            return_value=expected,
        ) as mock_worker:
            await insider_service.get_holding_history(acc, 4)
            await insider_service.get_holding_history(acc, 8)

        assert mock_worker.call_count == 2

    @pytest.mark.asyncio
    async def test_propagates_value_error(self) -> None:
        """ValueError from worker propagates without being caught."""
        acc = "0001234567-26-000001"
        with patch.object(
            insider_service,
            "_fetch_holding_history",
            side_effect=ValueError("No holding history"),
        ):
            with pytest.raises(ValueError, match="No holding history"):
                await insider_service.get_holding_history(acc, 4)

    @pytest.mark.asyncio
    async def test_cache_key_contains_accession_no_and_periods(self) -> None:
        """Cache key for history contains both accession number and periods."""
        acc = "0001234567-26-000001"
        expected = _make_history_response()
        with patch.object(
            insider_service,
            "_fetch_holding_history",
            return_value=expected,
        ):
            await insider_service.get_holding_history(acc, 4)

        matching_keys = [k for k in insider_service._insider_cache if acc in k and "history" in k and "4" in k]
        assert len(matching_keys) == 1
