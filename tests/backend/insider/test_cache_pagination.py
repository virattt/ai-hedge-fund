"""Tests verifying cache keys include limit/offset pagination parameters (Remediation.2).

Verifies that:
- Different limit/offset values produce different cache keys (no stale data across pages)
- get_insider_summary, get_ownership_changes, get_insider_grants each use
  pagination-aware cache keys: f"{prefix}:{ticker}:{form_type}:{limit}:{offset}"
"""
import pytest
from unittest.mock import patch

from app.backend.models.insider_schemas import (
    GrantRecord,
    GrantsResponse,
    InsiderAggregates,
    InsiderFilingSummary,
    InsiderSummaryResponse,
    OwnershipChangeRecord,
    OwnershipChangesResponse,
)


# ---------------------------------------------------------------------------
# Helpers: minimal valid response objects
# ---------------------------------------------------------------------------


def _make_summary_response(ticker: str = "AAPL") -> InsiderSummaryResponse:
    agg = InsiderAggregates(
        total_filings=1, total_purchases=0, total_sales=1, total_other=0,
        net_sentiment=-1, activity_by_date=[],
    )
    filing = InsiderFilingSummary(
        filing_date="2024-03-15", accession_no="ACC1",
        insider_name="Tim Cook", position="CEO",
        primary_activity="Sale", net_change=-1000, form_type="4",
    )
    return InsiderSummaryResponse(ticker=ticker, form_type="4", filings=[filing], aggregates=agg, total=1, skipped_count=0)


def _make_ownership_response(ticker: str = "AAPL") -> OwnershipChangesResponse:
    record = OwnershipChangeRecord(
        filing_date="2024-03-15", accession_no="ACC1",
        insider_name="Tim Cook", position="CEO",
        net_change=-1000, form_type="4",
    )
    return OwnershipChangesResponse(ticker=ticker, records=[record], insiders=["Tim Cook"], total=1, skipped_count=0)


def _make_grants_response(ticker: str = "AAPL") -> GrantsResponse:
    record = GrantRecord(
        filing_date="2024-03-15", accession_no="ACC1",
        insider_name="Tim Cook", position="CEO",
        transaction_type="Exercise", security_title="Stock Option",
        acquired_disposed="A", code="M",
    )
    return GrantsResponse(ticker=ticker, records=[record], total=1, skipped_count=0)


# ---------------------------------------------------------------------------
# Cache key tests for get_insider_summary
# ---------------------------------------------------------------------------


class TestSummaryCacheKeyIncludesPagination:
    """get_insider_summary uses limit+offset in the cache key."""

    def setup_method(self) -> None:
        import app.backend.services.insider_service as svc
        svc._insider_cache.clear()

    @pytest.mark.asyncio
    async def test_different_offsets_produce_different_cache_entries(self) -> None:
        """Requests with different offset values are cached under different keys."""
        import app.backend.services.insider_service as svc

        response_page1 = _make_summary_response()
        response_page2 = _make_summary_response()

        with patch("app.backend.services.insider_service._summary._fetch_summaries", return_value=response_page1):
            from app.backend.services.insider_service import get_insider_summary
            await get_insider_summary("AAPL", form_type="4", limit=50, offset=0)

        with patch("app.backend.services.insider_service._summary._fetch_summaries", return_value=response_page2):
            await get_insider_summary("AAPL", form_type="4", limit=50, offset=50)

        assert "summary:AAPL:4:50:0" in svc._insider_cache
        assert "summary:AAPL:4:50:50" in svc._insider_cache

    @pytest.mark.asyncio
    async def test_different_limits_produce_different_cache_entries(self) -> None:
        """Requests with different limit values are cached under different keys."""
        import app.backend.services.insider_service as svc

        with patch("app.backend.services.insider_service._summary._fetch_summaries", return_value=_make_summary_response()):
            from app.backend.services.insider_service import get_insider_summary
            await get_insider_summary("AAPL", form_type="4", limit=10, offset=0)

        with patch("app.backend.services.insider_service._summary._fetch_summaries", return_value=_make_summary_response()):
            await get_insider_summary("AAPL", form_type="4", limit=100, offset=0)

        assert "summary:AAPL:4:10:0" in svc._insider_cache
        assert "summary:AAPL:4:100:0" in svc._insider_cache

    @pytest.mark.asyncio
    async def test_cached_page1_does_not_serve_page2_request(self) -> None:
        """A cache hit for page 1 does not bleed into a page 2 request."""
        import app.backend.services.insider_service as svc

        page1 = _make_summary_response("AAPL")
        page2 = _make_summary_response("AAPL")
        page2.filings[0].accession_no = "ACC-PAGE2"

        svc._cache_put("summary:AAPL:4:50:0", page1)

        with patch("app.backend.services.insider_service._summary._fetch_summaries", return_value=page2) as mock_fetch:
            from app.backend.services.insider_service import get_insider_summary
            result = await get_insider_summary("AAPL", form_type="4", limit=50, offset=50)

        mock_fetch.assert_called_once()
        assert result.filings[0].accession_no == "ACC-PAGE2"


# ---------------------------------------------------------------------------
# Cache key tests for get_ownership_changes
# ---------------------------------------------------------------------------


class TestOwnershipCacheKeyIncludesPagination:
    """get_ownership_changes uses limit+offset in the cache key."""

    def setup_method(self) -> None:
        import app.backend.services.insider_service as svc
        svc._insider_cache.clear()

    @pytest.mark.asyncio
    async def test_different_offsets_produce_different_cache_entries(self) -> None:
        """Different offset values are cached under different ownership keys."""
        import app.backend.services.insider_service as svc

        with patch("app.backend.services.insider_service._fetch_ownership_changes", return_value=_make_ownership_response()):
            from app.backend.services.insider_service import get_ownership_changes
            await get_ownership_changes("AAPL", form_type="4", limit=50, offset=0)

        with patch("app.backend.services.insider_service._fetch_ownership_changes", return_value=_make_ownership_response()):
            await get_ownership_changes("AAPL", form_type="4", limit=50, offset=50)

        assert "ownership:AAPL:4:50:0" in svc._insider_cache
        assert "ownership:AAPL:4:50:50" in svc._insider_cache

    @pytest.mark.asyncio
    async def test_cached_page1_does_not_serve_page2_request(self) -> None:
        """A cache hit for ownership page 1 does not bleed into page 2."""
        import app.backend.services.insider_service as svc

        page1 = _make_ownership_response()
        page2 = _make_ownership_response()
        page2.records[0].accession_no = "OWNERSHIP-PAGE2"

        svc._cache_put("ownership:AAPL:4:50:0", page1)

        with patch("app.backend.services.insider_service._fetch_ownership_changes", return_value=page2) as mock_fetch:
            from app.backend.services.insider_service import get_ownership_changes
            result = await get_ownership_changes("AAPL", form_type="4", limit=50, offset=50)

        mock_fetch.assert_called_once()
        assert result.records[0].accession_no == "OWNERSHIP-PAGE2"


# ---------------------------------------------------------------------------
# Cache key tests for get_insider_grants
# ---------------------------------------------------------------------------


class TestGrantsCacheKeyIncludesPagination:
    """get_insider_grants uses limit+offset in the cache key."""

    def setup_method(self) -> None:
        import app.backend.services.insider_service as svc
        svc._insider_cache.clear()

    @pytest.mark.asyncio
    async def test_different_offsets_produce_different_cache_entries(self) -> None:
        """Different offset values are cached under different grants keys."""
        import app.backend.services.insider_service as svc

        with patch("app.backend.services.insider_service._grants._fetch_grants", return_value=_make_grants_response()):
            from app.backend.services.insider_service import get_insider_grants
            await get_insider_grants("AAPL", form_type="4", limit=50, offset=0)

        with patch("app.backend.services.insider_service._grants._fetch_grants", return_value=_make_grants_response()):
            await get_insider_grants("AAPL", form_type="4", limit=50, offset=50)

        assert "grants:AAPL:4:50:0" in svc._insider_cache
        assert "grants:AAPL:4:50:50" in svc._insider_cache

    @pytest.mark.asyncio
    async def test_cached_page1_does_not_serve_page2_request(self) -> None:
        """A cache hit for grants page 1 does not bleed into page 2."""
        import app.backend.services.insider_service as svc

        page1 = _make_grants_response()
        page2 = _make_grants_response()
        page2.records[0].accession_no = "GRANTS-PAGE2"

        svc._cache_put("grants:AAPL:4:50:0", page1)

        with patch("app.backend.services.insider_service._grants._fetch_grants", return_value=page2) as mock_fetch:
            from app.backend.services.insider_service import get_insider_grants
            result = await get_insider_grants("AAPL", form_type="4", limit=50, offset=50)

        mock_fetch.assert_called_once()
        assert result.records[0].accession_no == "GRANTS-PAGE2"
