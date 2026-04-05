"""Tests for the OpenInsider FastAPI route handler.

Uses httpx.AsyncClient with ASGITransport (compatible with httpx >= 0.24) instead of
starlette TestClient, which has an incompatibility with httpx 0.28 in this environment.

Covers:
- GET /insider/openinsider/screener: valid preset (200), invalid preset (422), fetch error (502)
- Ticker regex validation (422 on bad ticker)
- Numeric range validation (422 on out-of-range values)
- Literal enum validation for officer_filter (422 on unknown value)
- Custom params forwarded to service when preset=custom
- Custom params ignored when preset is a named preset
"""
import pytest
import pytest_asyncio
import httpx
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch
from fastapi import FastAPI

from app.backend.models.openinsider_schemas import OpenInsiderRecord, OpenInsiderResponse
from app.backend.routes.openinsider import router
from app.backend.services.openinsider_service import OpenInsiderFetchError

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


def _make_openinsider_response(preset: str = "ceo_cfo_conviction") -> OpenInsiderResponse:
    record = OpenInsiderRecord(
        filing_date="2026-04-01",
        trade_date="2026-03-28",
        ticker="AAPL",
        company_name="Apple Inc.",
        insider_name="Tim Cook",
        title="CEO",
        trade_type="P - Purchase",
        price=175.50,
        qty=10000,
        owned=3280000,
        delta_own="+0.3%",
        value=1755000.0,
    )
    return OpenInsiderResponse(
        preset=preset,
        records=[record],
        total=1,
        cached=False,
    )


# ---------------------------------------------------------------------------
# Happy path: valid preset returns 200
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_screener_returns_200_with_valid_preset(client: httpx.AsyncClient) -> None:
    """Valid preset returns 200 with OpenInsiderResponse JSON shape."""
    mock_response = _make_openinsider_response()
    with patch(
        "app.backend.routes.openinsider.get_openinsider_screener",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        response = await client.get("/insider/openinsider/screener?preset=ceo_cfo_conviction")

    assert response.status_code == 200
    data = response.json()
    assert data["preset"] == "ceo_cfo_conviction"
    assert data["total"] == 1
    assert data["cached"] is False
    assert len(data["records"]) == 1
    assert data["records"][0]["ticker"] == "AAPL"


# ---------------------------------------------------------------------------
# Preset validation: invalid preset returns 422
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_screener_rejects_invalid_preset_with_422(client: httpx.AsyncClient) -> None:
    """Unknown preset value returns HTTP 422 (FastAPI Literal validation)."""
    response = await client.get("/insider/openinsider/screener?preset=invalid")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_screener_missing_preset_returns_422(client: httpx.AsyncClient) -> None:
    """Missing required preset param returns HTTP 422."""
    response = await client.get("/insider/openinsider/screener")
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Error handling: service fetch error returns 502
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_screener_service_error_returns_502(client: httpx.AsyncClient) -> None:
    """OpenInsiderFetchError from service is converted to HTTP 502."""
    with patch(
        "app.backend.routes.openinsider.get_openinsider_screener",
        new_callable=AsyncMock,
        side_effect=OpenInsiderFetchError("failed to fetch"),
    ):
        response = await client.get("/insider/openinsider/screener?preset=ceo_cfo_conviction")

    assert response.status_code == 502


@pytest.mark.asyncio
async def test_screener_value_error_returns_400(client: httpx.AsyncClient) -> None:
    """ValueError from service is converted to HTTP 400."""
    with patch(
        "app.backend.routes.openinsider.get_openinsider_screener",
        new_callable=AsyncMock,
        side_effect=ValueError("invalid parameter combination"),
    ):
        response = await client.get("/insider/openinsider/screener?preset=ceo_cfo_conviction")

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_screener_generic_exception_returns_500(client: httpx.AsyncClient) -> None:
    """Unhandled exception from service is converted to HTTP 500."""
    with patch(
        "app.backend.routes.openinsider.get_openinsider_screener",
        new_callable=AsyncMock,
        side_effect=RuntimeError("unexpected error"),
    ):
        response = await client.get("/insider/openinsider/screener?preset=ceo_cfo_conviction")

    assert response.status_code == 500


# ---------------------------------------------------------------------------
# Custom params forwarded to service
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_screener_passes_custom_params_to_service(client: httpx.AsyncClient) -> None:
    """Custom preset with additional params forwards them to the service."""
    mock_response = _make_openinsider_response(preset="custom")
    with patch(
        "app.backend.routes.openinsider.get_openinsider_screener",
        new_callable=AsyncMock,
        return_value=mock_response,
    ) as mock_svc:
        response = await client.get(
            "/insider/openinsider/screener?preset=custom&min_value=50000&filing_days=60"
        )

    assert response.status_code == 200
    _, kwargs = mock_svc.call_args
    assert kwargs["preset"] == "custom"
    custom_params = kwargs["custom_params"]
    assert custom_params is not None
    assert "min_value" in custom_params
    assert "filing_days" in custom_params


# ---------------------------------------------------------------------------
# Ticker regex validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_ticker",
    [
        "aapl",           # lowercase
        "TOOLONG1",       # too long with digit
        "APL1",           # contains digit
        "A!",             # special char
        "invalid123",     # alphanumeric mixed
    ],
)
async def test_screener_rejects_invalid_ticker_with_422(client: httpx.AsyncClient, bad_ticker: str) -> None:
    """Tickers that don't match ^[A-Z]{1,5}$ return HTTP 422."""
    response = await client.get(
        f"/insider/openinsider/screener?preset=custom&ticker={bad_ticker}"
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Numeric range validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_screener_rejects_negative_min_value_with_422(client: httpx.AsyncClient) -> None:
    """min_value=-1 (below ge=0) returns HTTP 422."""
    response = await client.get(
        "/insider/openinsider/screener?preset=custom&min_value=-1"
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_screener_rejects_out_of_range_filing_days_with_422(client: httpx.AsyncClient) -> None:
    """filing_days=0 (below ge=1) returns HTTP 422."""
    response = await client.get(
        "/insider/openinsider/screener?preset=custom&filing_days=0"
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_screener_rejects_filing_days_above_max_with_422(client: httpx.AsyncClient) -> None:
    """filing_days=366 (above le=365) returns HTTP 422."""
    response = await client.get(
        "/insider/openinsider/screener?preset=custom&filing_days=366"
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_screener_rejects_min_delta_own_above_100_with_422(client: httpx.AsyncClient) -> None:
    """min_delta_own=101 (above le=100) returns HTTP 422."""
    response = await client.get(
        "/insider/openinsider/screener?preset=custom&min_delta_own=101"
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Literal enum validation for officer_filter and transaction_type
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_screener_rejects_invalid_officer_filter_with_422(client: httpx.AsyncClient) -> None:
    """officer_filter with unknown value returns HTTP 422."""
    response = await client.get(
        "/insider/openinsider/screener?preset=custom&officer_filter=admin"
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_screener_rejects_invalid_transaction_type_with_422(client: httpx.AsyncClient) -> None:
    """transaction_type with unknown value returns HTTP 422."""
    response = await client.get(
        "/insider/openinsider/screener?preset=custom&transaction_type=short"
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Custom params ignored for named presets
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_screener_ignores_custom_params_for_preset_mode(client: httpx.AsyncClient) -> None:
    """Named preset mode ignores custom params and calls service with custom_params=None."""
    mock_response = _make_openinsider_response(preset="ceo_cfo_conviction")
    with patch(
        "app.backend.routes.openinsider.get_openinsider_screener",
        new_callable=AsyncMock,
        return_value=mock_response,
    ) as mock_svc:
        response = await client.get(
            "/insider/openinsider/screener"
            "?preset=ceo_cfo_conviction&min_value=999999&ticker=ZZZZ&filing_days=180"
        )

    assert response.status_code == 200
    _, kwargs = mock_svc.call_args
    assert kwargs["preset"] == "ceo_cfo_conviction"
    assert kwargs["custom_params"] is None
