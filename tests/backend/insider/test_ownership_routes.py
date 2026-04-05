"""Tests for GET /insider/ownership route handler (Phase 5.3).

Verifies:
- 200 response with valid ticker and OwnershipChangesResponse JSON
- 422 for invalid tickers (lowercase, too long, digits, special chars)
- 422 for missing ticker
- 500 for service errors
- limit parameter is passed through to service
- form_type parameter is forwarded to service
"""
import pytest
import pytest_asyncio
import httpx
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch
from fastapi import FastAPI

from app.backend.models.insider_schemas import OwnershipChangeRecord, OwnershipChangesResponse
from app.backend.routes.insider import router

# ---------------------------------------------------------------------------
# Shared test app
# ---------------------------------------------------------------------------

_test_app = FastAPI()
_test_app.include_router(router)


# ---------------------------------------------------------------------------
# Async client fixture
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture()
async def client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Async httpx client backed by the test FastAPI app via ASGITransport."""
    transport = httpx.ASGITransport(app=_test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ownership_response(ticker: str = "AAPL") -> OwnershipChangesResponse:
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


# ---------------------------------------------------------------------------
# Ownership endpoint – happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ownership_returns_200_with_valid_ticker(client: httpx.AsyncClient) -> None:
    """Valid uppercase ticker returns 200 with OwnershipChangesResponse JSON."""
    mock_response = _make_ownership_response()
    with patch(
        "app.backend.routes.insider.get_ownership_changes",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        response = await client.get("/insider/ownership?ticker=AAPL&form_type=4&limit=50&offset=0")

    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "AAPL"
    assert data["total"] == 1
    assert data["skipped_count"] == 0
    assert len(data["records"]) == 1
    assert data["records"][0]["accession_no"] == "0000320193-24-000081"
    assert data["insiders"] == ["Tim Cook"]


@pytest.mark.asyncio
async def test_ownership_passes_params_to_service(client: httpx.AsyncClient) -> None:
    """limit, form_type, and offset query params are forwarded to get_ownership_changes."""
    mock_response = _make_ownership_response()
    with patch(
        "app.backend.routes.insider.get_ownership_changes",
        new_callable=AsyncMock,
        return_value=mock_response,
    ) as mock_svc:
        await client.get("/insider/ownership?ticker=AAPL&form_type=4&limit=25&offset=10")

    mock_svc.assert_called_once_with(ticker="AAPL", form_type="4", limit=25, offset=10)


@pytest.mark.asyncio
async def test_ownership_default_params(client: httpx.AsyncClient) -> None:
    """form_type defaults to '4', limit to 50, offset to 0 when not specified."""
    mock_response = _make_ownership_response()
    with patch(
        "app.backend.routes.insider.get_ownership_changes",
        new_callable=AsyncMock,
        return_value=mock_response,
    ) as mock_svc:
        await client.get("/insider/ownership?ticker=AAPL")

    _, kwargs = mock_svc.call_args
    assert kwargs["form_type"] == "4"
    assert kwargs["limit"] == 50
    assert kwargs["offset"] == 0


# ---------------------------------------------------------------------------
# Ownership endpoint – validation errors
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_ticker",
    [
        "aapl",      # lowercase
        "TOOLONG",   # 7 chars
        "APL1",      # digit
        "A!",        # special char
    ],
)
async def test_ownership_rejects_invalid_ticker_with_422(client: httpx.AsyncClient, bad_ticker: str) -> None:
    """Tickers that don't match ^[A-Z]{1,5}$ return HTTP 422."""
    response = await client.get(f"/insider/ownership?ticker={bad_ticker}&form_type=4")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_ownership_missing_ticker_returns_422(client: httpx.AsyncClient) -> None:
    """Missing required ticker param returns HTTP 422."""
    response = await client.get("/insider/ownership?form_type=4")
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Ownership endpoint – error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ownership_service_error_returns_500(client: httpx.AsyncClient) -> None:
    """Unhandled service exception is converted to HTTP 500."""
    with patch(
        "app.backend.routes.insider.get_ownership_changes",
        new_callable=AsyncMock,
        side_effect=RuntimeError("edgartools failure"),
    ):
        response = await client.get("/insider/ownership?ticker=AAPL")

    assert response.status_code == 500
