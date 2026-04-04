"""Tests for insider trading FastAPI route handlers.

Uses httpx.AsyncClient with ASGITransport (compatible with httpx >= 0.24) instead of
starlette TestClient, which has an incompatibility with httpx 0.28 in this environment.

Covers:
- GET /insider/summary: valid request, invalid ticker validation (422), offset passthrough
- GET /insider/detail: valid request, unknown accession_no (404), invalid ticker (422), service error (500)
"""
import pytest
import pytest_asyncio
import httpx
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch
from fastapi import FastAPI

from app.backend.models.insider_schemas import (
    InsiderAggregates,
    InsiderDetailResponse,
    InsiderFilingSummary,
    InsiderSummaryResponse,
    InsiderTransactionDetail,
)
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
# Helpers: sample response objects
# ---------------------------------------------------------------------------


def _make_summary_response(ticker: str = "AAPL", form_type: str = "4") -> InsiderSummaryResponse:
    filing = InsiderFilingSummary(
        filing_date="2024-03-15",
        accession_no="0000320193-24-000081",
        insider_name="Tim Cook",
        position="CEO",
        primary_activity="Sale",
        net_change=-50000,
        net_value=8750000.0,
        remaining_shares=3280000,
        has_10b5_1_plan=True,
        transaction_types=["Sale"],
        transaction_count=2,
        form_type=form_type,
    )
    agg = InsiderAggregates(
        total_filings=1,
        total_purchases=0,
        total_sales=1,
        total_other=0,
        net_sentiment=-1,
        largest_transaction_value=8750000.0,
        largest_transaction_insider="Tim Cook",
        plan_10b5_1_count=1,
        plan_10b5_1_ratio=1.0,
        activity_by_date=[],
    )
    return InsiderSummaryResponse(
        ticker=ticker,
        form_type=form_type,
        filings=[filing],
        aggregates=agg,
        total=1,
        skipped_count=0,
    )


def _make_detail_response(ticker: str = "AAPL") -> InsiderDetailResponse:
    tx = InsiderTransactionDetail(
        transaction_type="Sale",
        code="S",
        description="Open market or private sale",
        shares=25000.0,
        price_per_share=175.0,
        value=4375000.0,
        security_type="non-derivative",
        security_title="Common Stock",
        is_10b5_1_plan=True,
        is_derivative=False,
    )
    return InsiderDetailResponse(
        ticker=ticker,
        filing_date="2024-03-15",
        accession_no="0000320193-24-000081",
        insider_name="Tim Cook",
        position="CEO",
        form_type="4",
        transactions=[tx],
        market_trades_count=1,
        derivative_trades_count=0,
    )


# ---------------------------------------------------------------------------
# Summary endpoint – happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_summary_returns_200_with_valid_ticker(client: httpx.AsyncClient) -> None:
    """Valid uppercase ticker returns 200 with InsiderSummaryResponse JSON."""
    mock_response = _make_summary_response()
    with patch(
        "app.backend.routes.insider.get_insider_summary",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        response = await client.get("/insider/summary?ticker=AAPL&form_type=4&limit=50&offset=0")

    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "AAPL"
    assert data["form_type"] == "4"
    assert data["total"] == 1
    assert data["skipped_count"] == 0
    assert len(data["filings"]) == 1
    assert data["filings"][0]["accession_no"] == "0000320193-24-000081"


@pytest.mark.asyncio
async def test_summary_passes_offset_to_service(client: httpx.AsyncClient) -> None:
    """offset query param is forwarded correctly to get_insider_summary."""
    mock_response = _make_summary_response()
    with patch(
        "app.backend.routes.insider.get_insider_summary",
        new_callable=AsyncMock,
        return_value=mock_response,
    ) as mock_svc:
        response = await client.get("/insider/summary?ticker=AAPL&form_type=4&limit=25&offset=50")

    assert response.status_code == 200
    mock_svc.assert_called_once_with(ticker="AAPL", form_type="4", limit=25, offset=50)


@pytest.mark.asyncio
async def test_summary_uses_default_form_type_4(client: httpx.AsyncClient) -> None:
    """form_type defaults to '4' when not specified."""
    mock_response = _make_summary_response()
    with patch(
        "app.backend.routes.insider.get_insider_summary",
        new_callable=AsyncMock,
        return_value=mock_response,
    ) as mock_svc:
        response = await client.get("/insider/summary?ticker=AAPL")

    assert response.status_code == 200
    _, kwargs = mock_svc.call_args
    assert kwargs["form_type"] == "4"


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
async def test_summary_rejects_invalid_ticker_with_422(client: httpx.AsyncClient, bad_ticker: str) -> None:
    """Tickers that don't match ^[A-Z]{1,5}$ return HTTP 422."""
    response = await client.get(f"/insider/summary?ticker={bad_ticker}&form_type=4")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_summary_missing_ticker_returns_422(client: httpx.AsyncClient) -> None:
    """Missing required ticker param returns HTTP 422."""
    response = await client.get("/insider/summary?form_type=4")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_summary_service_error_returns_500(client: httpx.AsyncClient) -> None:
    """Unhandled service exception is converted to HTTP 500."""
    with patch(
        "app.backend.routes.insider.get_insider_summary",
        new_callable=AsyncMock,
        side_effect=RuntimeError("edgartools failure"),
    ):
        response = await client.get("/insider/summary?ticker=AAPL")

    assert response.status_code == 500


# ---------------------------------------------------------------------------
# Detail endpoint – happy path and error cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_detail_returns_200_with_valid_params(client: httpx.AsyncClient) -> None:
    """Valid ticker and accession_no returns 200 with InsiderDetailResponse JSON."""
    mock_response = _make_detail_response()
    with patch(
        "app.backend.routes.insider.get_insider_detail",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        response = await client.get(
            "/insider/detail?ticker=AAPL&form_type=4&accession_no=0000320193-24-000081"
        )

    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "AAPL"
    assert data["accession_no"] == "0000320193-24-000081"
    assert len(data["transactions"]) == 1


@pytest.mark.asyncio
async def test_detail_passes_accession_no_to_service(client: httpx.AsyncClient) -> None:
    """accession_no query param is forwarded correctly to get_insider_detail."""
    mock_response = _make_detail_response()
    with patch(
        "app.backend.routes.insider.get_insider_detail",
        new_callable=AsyncMock,
        return_value=mock_response,
    ) as mock_svc:
        await client.get(
            "/insider/detail?ticker=MSFT&form_type=4&accession_no=0000789019-24-000050"
        )

    mock_svc.assert_called_once_with(
        ticker="MSFT", form_type="4", accession_no="0000789019-24-000050"
    )


@pytest.mark.asyncio
async def test_detail_returns_404_for_unknown_accession_no(client: httpx.AsyncClient) -> None:
    """ValueError from service (filing not found) results in HTTP 404."""
    with patch(
        "app.backend.routes.insider.get_insider_detail",
        new_callable=AsyncMock,
        side_effect=ValueError("Filing not found: 0000000000-00-000000"),
    ):
        response = await client.get(
            "/insider/detail?ticker=AAPL&form_type=4&accession_no=0000000000-00-000000"
        )

    assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_ticker",
    [
        "aapl",
        "TOOLONG",
        "A1",
    ],
)
async def test_detail_rejects_invalid_ticker_with_422(client: httpx.AsyncClient, bad_ticker: str) -> None:
    """Tickers that don't match ^[A-Z]{1,5}$ return HTTP 422."""
    response = await client.get(
        f"/insider/detail?ticker={bad_ticker}&form_type=4&accession_no=0000320193-24-000081"
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_detail_service_error_returns_500(client: httpx.AsyncClient) -> None:
    """Unhandled service exception is converted to HTTP 500."""
    with patch(
        "app.backend.routes.insider.get_insider_detail",
        new_callable=AsyncMock,
        side_effect=RuntimeError("edgartools connection error"),
    ):
        response = await client.get(
            "/insider/detail?ticker=AAPL&form_type=4&accession_no=0000320193-24-000081"
        )

    assert response.status_code == 500


@pytest.mark.asyncio
async def test_detail_missing_accession_no_returns_422(client: httpx.AsyncClient) -> None:
    """Missing required accession_no query param returns HTTP 422."""
    response = await client.get("/insider/detail?ticker=AAPL&form_type=4")
    assert response.status_code == 422
