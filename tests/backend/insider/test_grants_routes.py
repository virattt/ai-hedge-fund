"""Tests for GET /insider/grants route handler (Phase 6.3).

Verifies:
- 200 response with valid ticker and GrantsResponse JSON
- 422 for invalid tickers (lowercase, too long, digits, special chars)
- 422 for missing ticker
- 500 for service errors
- limit, form_type, offset parameters forwarded to service
- default parameters (form_type='4', limit=50, offset=0)
"""
import pytest
import pytest_asyncio
import httpx
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch
from fastapi import FastAPI

from app.backend.models.insider_schemas import GrantRecord, GrantsResponse
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


def _make_grants_response(ticker: str = "AAPL") -> GrantsResponse:
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


# ---------------------------------------------------------------------------
# Grants endpoint – happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_grants_returns_200_with_valid_ticker(client: httpx.AsyncClient) -> None:
    """Valid uppercase ticker returns 200 with GrantsResponse JSON."""
    mock_response = _make_grants_response()
    with patch(
        "app.backend.routes.insider.get_insider_grants",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        response = await client.get("/insider/grants?ticker=AAPL&form_type=4&limit=50&offset=0")

    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "AAPL"
    assert data["total"] == 1
    assert data["skipped_count"] == 0
    assert len(data["records"]) == 1
    assert data["records"][0]["accession_no"] == "0000320193-24-000081"
    assert data["records"][0]["transaction_type"] == "Exercise"


@pytest.mark.asyncio
async def test_grants_passes_params_to_service(client: httpx.AsyncClient) -> None:
    """limit, form_type, and offset query params are forwarded to get_insider_grants."""
    mock_response = _make_grants_response()
    with patch(
        "app.backend.routes.insider.get_insider_grants",
        new_callable=AsyncMock,
        return_value=mock_response,
    ) as mock_svc:
        await client.get("/insider/grants?ticker=AAPL&form_type=4&limit=25&offset=10")

    mock_svc.assert_called_once_with(ticker="AAPL", form_type="4", limit=25, offset=10)


@pytest.mark.asyncio
async def test_grants_default_params(client: httpx.AsyncClient) -> None:
    """form_type defaults to '4', limit to 50, offset to 0 when not specified."""
    mock_response = _make_grants_response()
    with patch(
        "app.backend.routes.insider.get_insider_grants",
        new_callable=AsyncMock,
        return_value=mock_response,
    ) as mock_svc:
        await client.get("/insider/grants?ticker=AAPL")

    _, kwargs = mock_svc.call_args
    assert kwargs["form_type"] == "4"
    assert kwargs["limit"] == 50
    assert kwargs["offset"] == 0


# ---------------------------------------------------------------------------
# Grants endpoint – validation errors
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
async def test_grants_rejects_invalid_ticker_with_422(client: httpx.AsyncClient, bad_ticker: str) -> None:
    """Tickers that don't match ^[A-Z]{1,5}$ return HTTP 422."""
    response = await client.get(f"/insider/grants?ticker={bad_ticker}&form_type=4")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_grants_missing_ticker_returns_422(client: httpx.AsyncClient) -> None:
    """Missing required ticker param returns HTTP 422."""
    response = await client.get("/insider/grants?form_type=4")
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Grants endpoint – error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_grants_service_error_returns_500(client: httpx.AsyncClient) -> None:
    """Unhandled service exception is converted to HTTP 500."""
    with patch(
        "app.backend.routes.insider.get_insider_grants",
        new_callable=AsyncMock,
        side_effect=RuntimeError("edgartools failure"),
    ):
        response = await client.get("/insider/grants?ticker=AAPL")

    assert response.status_code == 500
