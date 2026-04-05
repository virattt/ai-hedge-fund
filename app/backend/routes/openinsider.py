"""FastAPI route handler for the OpenInsider screener endpoint.

Exposes a single endpoint:
- GET /insider/openinsider/screener  -- scrape openinsider.com with preset or custom filters

Input validation enforces:
- preset via Literal enum (required)
- ticker via regex ``^[A-Z]{1,5}$`` (optional, custom mode only)
- integer params via ge/le bounds (optional, custom mode only)
- officer_filter and transaction_type via Literal enums (optional, custom mode only)

Custom parameters are silently ignored when ``preset`` is not ``"custom"``.
Only keys in ``ALLOWED_CUSTOM_KEYS`` are forwarded to the service layer.
"""
import logging
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from app.backend.models.openinsider_schemas import OpenInsiderResponse
from app.backend.services.openinsider_service import OpenInsiderFetchError, get_openinsider_screener

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/insider/openinsider", tags=["openinsider"])

# Allowlist of custom parameter keys accepted by the screener endpoint.
# Keys not in this set are silently discarded to prevent parameter injection.
ALLOWED_CUSTOM_KEYS: frozenset[str] = frozenset(
    {
        "ticker",
        "min_value",
        "filing_days",
        "min_delta_own",
        "min_insiders",
        "officer_filter",
        "transaction_type",
    }
)


@router.get(
    "/screener",
    response_model=OpenInsiderResponse,
    responses={
        422: {"description": "Invalid query parameters (preset, ticker regex, out-of-range values, or unknown enum value)"},
        502: {"description": "Failed to fetch data from openinsider.com after retry"},
        500: {"description": "Internal server error"},
    },
)
async def openinsider_screener(
    preset: Literal["ceo_cfo_conviction", "cluster_buy", "significant_increase", "custom"] = Query(
        ..., description="Screener preset or 'custom' for manual filter configuration"
    ),
    ticker: str | None = Query(
        None,
        pattern=r"^[A-Z]{1,5}$",
        description="Filter by ticker symbol (1-5 uppercase letters, custom mode only)",
    ),
    min_value: int | None = Query(
        None,
        ge=0,
        le=100_000_000,
        description="Minimum transaction value in USD (custom mode only)",
    ),
    filing_days: int | None = Query(
        None,
        ge=1,
        le=365,
        description="Filing date lookback in days (custom mode only)",
    ),
    min_delta_own: int | None = Query(
        None,
        ge=0,
        le=100,
        description="Minimum percentage change in holdings (custom mode only)",
    ),
    min_insiders: int | None = Query(
        None,
        ge=1,
        le=20,
        description="Minimum distinct insiders buying the same ticker (custom mode only)",
    ),
    officer_filter: Literal["any", "ceo_cfo", "officer"] | None = Query(
        None,
        description="Officer title filter (custom mode only)",
    ),
    transaction_type: Literal["purchase", "sale", "all"] | None = Query(
        None,
        description="Transaction type filter (custom mode only)",
    ),
) -> OpenInsiderResponse:
    """Return insider trading records from openinsider.com screener.

    For named presets (``ceo_cfo_conviction``, ``cluster_buy``,
    ``significant_increase``), uses preset-specific URL parameters and ignores
    any custom filter arguments. For ``preset=custom``, builds a custom query
    from the non-None filter arguments.

    Responses are served from an in-memory LRU+TTL cache (1-hour TTL) when
    available; ``cached=True`` in the response indicates a cache hit.
    """
    if preset == "custom":
        raw_params: dict[str, str | None] = {
            "ticker": ticker,
            "min_value": str(min_value) if min_value is not None else None,
            "filing_days": str(filing_days) if filing_days is not None else None,
            "min_delta_own": str(min_delta_own) if min_delta_own is not None else None,
            "min_insiders": str(min_insiders) if min_insiders is not None else None,
            "officer_filter": officer_filter,
            "transaction_type": transaction_type,
        }
        custom_params: dict[str, str] | None = {
            k: v
            for k, v in raw_params.items()
            if v is not None and k in ALLOWED_CUSTOM_KEYS
        } or None
    else:
        custom_params = None

    try:
        return await get_openinsider_screener(preset=preset, custom_params=custom_params)
    except OpenInsiderFetchError as exc:
        logger.warning("OpenInsider fetch failed for preset=%s: %s", preset, exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected error for openinsider screener preset=%s", preset)
        raise HTTPException(status_code=500, detail=f"Internal server error: {exc}") from exc
