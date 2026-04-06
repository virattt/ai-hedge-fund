"""Tests for 13F-HR route handlers (Phase 3.1).

Covers:
- GET /insider/thirteenf: 200 with filings, year/quarter param passthrough, default params
- GET /insider/thirteenf/compare: 200 success, 404 on ValueError, 422 for malformed accession_no, 500 on unexpected error
- GET /insider/thirteenf/history: 200 success, 404 on ValueError, 422 for malformed accession_no
"""
import pytest
import pytest_asyncio
import httpx
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch
from fastapi import FastAPI

from app.backend.models.insider_schemas import (
    CompareHoldingsRecord,
    CompareHoldingsResponse,
    HoldingHistoryRecord,
    HoldingHistoryResponse,
    ThirteenFFilingListItem,
    ThirteenFListResponse,
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

_VALID_ACCESSION_NO = "0001234567-26-000001"
_MALFORMED_ACCESSION_NO = "bad-accession"


def _make_list_response() -> ThirteenFListResponse:
    item = ThirteenFFilingListItem(
        filing_date="2026-03-15",
        accession_no=_VALID_ACCESSION_NO,
        company="BERKSHIRE HATHAWAY INC",
        cik=1067983,
        form="13F-HR",
    )
    return ThirteenFListResponse(
        filings=[item],
        total=5000,
        has_more=True,
        skipped_count=0,
    )


def _make_compare_response() -> CompareHoldingsResponse:
    record = CompareHoldingsRecord(
        cusip="023135106",
        ticker="AMZN",
        issuer="AMAZON COM INC",
        shares=10000000,
        prev_shares=8000000,
        value=1500000,
        prev_value=1200000,
        share_change=2000000,
        share_change_pct=25.0,
        value_change=300000,
        value_change_pct=25.0,
        status="INCREASED",
    )
    return CompareHoldingsResponse(
        accession_no=_VALID_ACCESSION_NO,
        current_period="2025-12-31",
        previous_period="2025-09-30",
        manager_name="BERKSHIRE HATHAWAY INC",
        records=[record],
        total=1,
    )


def _make_history_response() -> HoldingHistoryResponse:
    record = HoldingHistoryRecord(
        cusip="023135106",
        ticker="AMZN",
        issuer="AMAZON COM INC",
        periods_data={
            "2025-03-31": 7000000,
            "2025-06-30": 8000000,
            "2025-09-30": 9000000,
            "2025-12-31": 10000000,
        },
    )
    return HoldingHistoryResponse(
        accession_no=_VALID_ACCESSION_NO,
        manager_name="BERKSHIRE HATHAWAY INC",
        periods=["2025-03-31", "2025-06-30", "2025-09-30", "2025-12-31"],
        records=[record],
        total=1,
    )


# ---------------------------------------------------------------------------
# GET /insider/thirteenf – listing endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_thirteenf_listing_returns_200_with_filings(client: httpx.AsyncClient) -> None:
    """Valid request returns 200 with ThirteenFListResponse JSON."""
    mock_response = _make_list_response()
    with patch(
        "app.backend.routes.insider.get_thirteenf_filings",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        response = await client.get("/insider/thirteenf?limit=20&offset=0")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5000
    assert data["has_more"] is True
    assert data["skipped_count"] == 0
    assert len(data["filings"]) == 1
    assert data["filings"][0]["accession_no"] == _VALID_ACCESSION_NO
    assert data["filings"][0]["company"] == "BERKSHIRE HATHAWAY INC"


@pytest.mark.asyncio
async def test_thirteenf_listing_passes_year_quarter_params(client: httpx.AsyncClient) -> None:
    """year and quarter query params are forwarded to get_thirteenf_filings."""
    mock_response = _make_list_response()
    with patch(
        "app.backend.routes.insider.get_thirteenf_filings",
        new_callable=AsyncMock,
        return_value=mock_response,
    ) as mock_svc:
        await client.get("/insider/thirteenf?limit=20&offset=0&year=2026&quarter=1")

    mock_svc.assert_called_once_with(limit=20, offset=0, year=2026, quarter=1)


@pytest.mark.asyncio
async def test_thirteenf_listing_defaults_no_year_quarter(client: httpx.AsyncClient) -> None:
    """year and quarter default to None when not provided."""
    mock_response = _make_list_response()
    with patch(
        "app.backend.routes.insider.get_thirteenf_filings",
        new_callable=AsyncMock,
        return_value=mock_response,
    ) as mock_svc:
        await client.get("/insider/thirteenf")

    _, kwargs = mock_svc.call_args
    assert kwargs["year"] is None
    assert kwargs["quarter"] is None


@pytest.mark.asyncio
async def test_thirteenf_listing_service_error_returns_500(client: httpx.AsyncClient) -> None:
    """Unhandled service exception is converted to HTTP 500."""
    with patch(
        "app.backend.routes.insider.get_thirteenf_filings",
        new_callable=AsyncMock,
        side_effect=RuntimeError("SEC API failure"),
    ):
        response = await client.get("/insider/thirteenf")

    assert response.status_code == 500


# ---------------------------------------------------------------------------
# GET /insider/thirteenf/compare – compare holdings endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_thirteenf_compare_returns_200_with_records(client: httpx.AsyncClient) -> None:
    """Valid accession_no returns 200 with CompareHoldingsResponse JSON."""
    mock_response = _make_compare_response()
    with patch(
        "app.backend.routes.insider.get_compare_holdings",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        response = await client.get(f"/insider/thirteenf/compare?accession_no={_VALID_ACCESSION_NO}")

    assert response.status_code == 200
    data = response.json()
    assert data["accession_no"] == _VALID_ACCESSION_NO
    assert data["current_period"] == "2025-12-31"
    assert data["previous_period"] == "2025-09-30"
    assert data["manager_name"] == "BERKSHIRE HATHAWAY INC"
    assert data["total"] == 1
    assert len(data["records"]) == 1
    assert data["records"][0]["status"] == "INCREASED"


@pytest.mark.asyncio
async def test_thirteenf_compare_returns_404_when_no_data(client: httpx.AsyncClient) -> None:
    """ValueError from service (no comparison data) results in HTTP 404."""
    with patch(
        "app.backend.routes.insider.get_compare_holdings",
        new_callable=AsyncMock,
        side_effect=ValueError("No comparison data available for this filing (no previous quarter found)"),
    ):
        response = await client.get(f"/insider/thirteenf/compare?accession_no={_VALID_ACCESSION_NO}")

    assert response.status_code == 404
    assert "No comparison data" in response.json()["detail"]


@pytest.mark.asyncio
async def test_thirteenf_compare_returns_422_for_malformed_accession_no(client: httpx.AsyncClient) -> None:
    """Malformed accession_no that fails pattern=^\\d{10}-\\d{2}-\\d{6}$ returns HTTP 422."""
    response = await client.get(f"/insider/thirteenf/compare?accession_no={_MALFORMED_ACCESSION_NO}")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_thirteenf_compare_returns_500_on_unexpected_error(client: httpx.AsyncClient) -> None:
    """Unexpected RuntimeError from service is converted to HTTP 500."""
    with patch(
        "app.backend.routes.insider.get_compare_holdings",
        new_callable=AsyncMock,
        side_effect=RuntimeError("Unexpected SEC API error"),
    ):
        response = await client.get(f"/insider/thirteenf/compare?accession_no={_VALID_ACCESSION_NO}")

    assert response.status_code == 500


@pytest.mark.asyncio
async def test_thirteenf_compare_missing_accession_no_returns_422(client: httpx.AsyncClient) -> None:
    """Missing required accession_no param returns HTTP 422."""
    response = await client.get("/insider/thirteenf/compare")
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /insider/thirteenf/history – holding history endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_thirteenf_history_returns_200_with_periods(client: httpx.AsyncClient) -> None:
    """Valid accession_no and periods returns 200 with HoldingHistoryResponse JSON."""
    mock_response = _make_history_response()
    with patch(
        "app.backend.routes.insider.get_holding_history",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        response = await client.get(f"/insider/thirteenf/history?accession_no={_VALID_ACCESSION_NO}&periods=4")

    assert response.status_code == 200
    data = response.json()
    assert data["accession_no"] == _VALID_ACCESSION_NO
    assert data["manager_name"] == "BERKSHIRE HATHAWAY INC"
    assert len(data["periods"]) == 4
    assert data["total"] == 1
    assert len(data["records"]) == 1
    assert data["records"][0]["periods_data"]["2025-12-31"] == 10000000


@pytest.mark.asyncio
async def test_thirteenf_history_returns_404_when_no_data(client: httpx.AsyncClient) -> None:
    """ValueError from service (no history data) results in HTTP 404."""
    with patch(
        "app.backend.routes.insider.get_holding_history",
        new_callable=AsyncMock,
        side_effect=ValueError("No holding history available for this filing"),
    ):
        response = await client.get(f"/insider/thirteenf/history?accession_no={_VALID_ACCESSION_NO}")

    assert response.status_code == 404
    assert "No holding history" in response.json()["detail"]


@pytest.mark.asyncio
async def test_thirteenf_history_returns_422_for_malformed_accession_no(client: httpx.AsyncClient) -> None:
    """Malformed accession_no that fails pattern=^\\d{10}-\\d{2}-\\d{6}$ returns HTTP 422."""
    response = await client.get(f"/insider/thirteenf/history?accession_no={_MALFORMED_ACCESSION_NO}")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_thirteenf_history_passes_periods_param(client: httpx.AsyncClient) -> None:
    """periods query param is forwarded to get_holding_history."""
    mock_response = _make_history_response()
    with patch(
        "app.backend.routes.insider.get_holding_history",
        new_callable=AsyncMock,
        return_value=mock_response,
    ) as mock_svc:
        await client.get(f"/insider/thirteenf/history?accession_no={_VALID_ACCESSION_NO}&periods=6")

    mock_svc.assert_called_once_with(accession_no=_VALID_ACCESSION_NO, periods=6)


@pytest.mark.asyncio
async def test_thirteenf_history_default_periods_is_4(client: httpx.AsyncClient) -> None:
    """periods defaults to 4 when not provided."""
    mock_response = _make_history_response()
    with patch(
        "app.backend.routes.insider.get_holding_history",
        new_callable=AsyncMock,
        return_value=mock_response,
    ) as mock_svc:
        await client.get(f"/insider/thirteenf/history?accession_no={_VALID_ACCESSION_NO}")

    _, kwargs = mock_svc.call_args
    assert kwargs["periods"] == 4


@pytest.mark.asyncio
async def test_thirteenf_history_service_error_returns_500(client: httpx.AsyncClient) -> None:
    """Unexpected RuntimeError from service is converted to HTTP 500."""
    with patch(
        "app.backend.routes.insider.get_holding_history",
        new_callable=AsyncMock,
        side_effect=RuntimeError("Unexpected SEC API error"),
    ):
        response = await client.get(f"/insider/thirteenf/history?accession_no={_VALID_ACCESSION_NO}")

    assert response.status_code == 500
