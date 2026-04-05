"""Tests for form_type=^[345]$ validation on all four insider route handlers (Remediation.2).

Verifies that each route returns HTTP 422 for invalid form_type values and
HTTP 200 for each valid value ('3', '4', '5').
"""
import pytest
import pytest_asyncio
import httpx
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch
from fastapi import FastAPI

from app.backend.models.insider_schemas import (
    GrantRecord,
    GrantsResponse,
    InsiderAggregates,
    InsiderDetailResponse,
    InsiderFilingSummary,
    InsiderSummaryResponse,
    OwnershipChangeRecord,
    OwnershipChangesResponse,
)
from app.backend.routes.insider import router

# ---------------------------------------------------------------------------
# Shared test app + async client fixture
# ---------------------------------------------------------------------------

_test_app = FastAPI()
_test_app.include_router(router)


@pytest_asyncio.fixture()
async def client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Async httpx client backed by the test FastAPI app."""
    transport = httpx.ASGITransport(app=_test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


# ---------------------------------------------------------------------------
# Minimal response factories
# ---------------------------------------------------------------------------


def _summary_response() -> InsiderSummaryResponse:
    agg = InsiderAggregates(
        total_filings=0, total_purchases=0, total_sales=0, total_other=0,
        net_sentiment=0, activity_by_date=[],
    )
    return InsiderSummaryResponse(ticker="AAPL", form_type="4", filings=[], aggregates=agg, total=0, skipped_count=0)


def _detail_response() -> InsiderDetailResponse:
    return InsiderDetailResponse(
        ticker="AAPL", filing_date="2024-03-15", accession_no="0000320193-24-000081",
        insider_name="Tim Cook", position="CEO", form_type="4",
        transactions=[], market_trades_count=0, derivative_trades_count=0,
    )


def _ownership_response() -> OwnershipChangesResponse:
    return OwnershipChangesResponse(ticker="AAPL", records=[], insiders=[], total=0, skipped_count=0)


def _grants_response() -> GrantsResponse:
    return GrantsResponse(ticker="AAPL", records=[], total=0, skipped_count=0)


# ---------------------------------------------------------------------------
# /insider/summary — form_type validation
# ---------------------------------------------------------------------------


_INVALID_FORM_TYPES = ["0", "6", "99", "A", "form4", ""]

_VALID_FORM_TYPES = ["3", "4", "5"]


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_form_type", _INVALID_FORM_TYPES)
async def test_summary_invalid_form_type_returns_422(client: httpx.AsyncClient, bad_form_type: str) -> None:
    """form_type values outside ^[345]$ return HTTP 422 for /insider/summary."""
    response = await client.get(f"/insider/summary?ticker=AAPL&form_type={bad_form_type}")
    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize("valid_form_type", _VALID_FORM_TYPES)
async def test_summary_valid_form_type_returns_200(client: httpx.AsyncClient, valid_form_type: str) -> None:
    """form_type values '3', '4', '5' all return HTTP 200 for /insider/summary."""
    with patch(
        "app.backend.routes.insider.get_insider_summary",
        new_callable=AsyncMock,
        return_value=_summary_response(),
    ):
        response = await client.get(f"/insider/summary?ticker=AAPL&form_type={valid_form_type}")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# /insider/detail — form_type validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_form_type", _INVALID_FORM_TYPES)
async def test_detail_invalid_form_type_returns_422(client: httpx.AsyncClient, bad_form_type: str) -> None:
    """form_type values outside ^[345]$ return HTTP 422 for /insider/detail."""
    response = await client.get(
        f"/insider/detail?ticker=AAPL&form_type={bad_form_type}&accession_no=0000320193-24-000081"
    )
    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize("valid_form_type", _VALID_FORM_TYPES)
async def test_detail_valid_form_type_returns_200(client: httpx.AsyncClient, valid_form_type: str) -> None:
    """form_type values '3', '4', '5' all return HTTP 200 for /insider/detail."""
    with patch(
        "app.backend.routes.insider.get_insider_detail",
        new_callable=AsyncMock,
        return_value=_detail_response(),
    ):
        response = await client.get(
            f"/insider/detail?ticker=AAPL&form_type={valid_form_type}&accession_no=0000320193-24-000081"
        )
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# /insider/ownership — form_type validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_form_type", _INVALID_FORM_TYPES)
async def test_ownership_invalid_form_type_returns_422(client: httpx.AsyncClient, bad_form_type: str) -> None:
    """form_type values outside ^[345]$ return HTTP 422 for /insider/ownership."""
    response = await client.get(f"/insider/ownership?ticker=AAPL&form_type={bad_form_type}")
    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize("valid_form_type", _VALID_FORM_TYPES)
async def test_ownership_valid_form_type_returns_200(client: httpx.AsyncClient, valid_form_type: str) -> None:
    """form_type values '3', '4', '5' all return HTTP 200 for /insider/ownership."""
    with patch(
        "app.backend.routes.insider.get_ownership_changes",
        new_callable=AsyncMock,
        return_value=_ownership_response(),
    ):
        response = await client.get(f"/insider/ownership?ticker=AAPL&form_type={valid_form_type}")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# /insider/grants — form_type validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_form_type", _INVALID_FORM_TYPES)
async def test_grants_invalid_form_type_returns_422(client: httpx.AsyncClient, bad_form_type: str) -> None:
    """form_type values outside ^[345]$ return HTTP 422 for /insider/grants."""
    response = await client.get(f"/insider/grants?ticker=AAPL&form_type={bad_form_type}")
    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize("valid_form_type", _VALID_FORM_TYPES)
async def test_grants_valid_form_type_returns_200(client: httpx.AsyncClient, valid_form_type: str) -> None:
    """form_type values '3', '4', '5' all return HTTP 200 for /insider/grants."""
    with patch(
        "app.backend.routes.insider.get_insider_grants",
        new_callable=AsyncMock,
        return_value=_grants_response(),
    ):
        response = await client.get(f"/insider/grants?ticker=AAPL&form_type={valid_form_type}")
    assert response.status_code == 200
