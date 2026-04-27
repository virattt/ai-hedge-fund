"""Ticker pass-through endpoints — F4a.

Wraps ``src.tools.api`` functions via ``asyncio.to_thread`` to provide
REST endpoints for ticker data.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Query
from pydantic import BaseModel

from ..schemas import FinancialMetricsResponse, InsiderTradesResponse

# Ensure ``src/`` is importable.
_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from tools.api import get_company_news as _get_company_news  # noqa: E402
from tools.api import get_financial_metrics as _get_financial_metrics  # noqa: E402
from tools.api import get_insider_trades as _get_insider_trades  # noqa: E402
from tools.api import get_prices as _get_prices  # noqa: E402

router = APIRouter()


class PricesResponse(BaseModel):
    prices: list[dict] = []


class NewsResponse(BaseModel):
    news: list[dict] = []


@router.get("/tickers/{symbol}/prices", response_model=PricesResponse)
async def get_prices(
    symbol: str,
    start_date: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    end_date: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
) -> PricesResponse:
    end = end_date or datetime.now(UTC).strftime("%Y-%m-%d")
    start = start_date or (datetime.strptime(end, "%Y-%m-%d") - timedelta(days=90)).strftime("%Y-%m-%d")
    ticker = symbol.upper()
    try:
        prices = await asyncio.to_thread(_get_prices, ticker, start, end)
        return PricesResponse(prices=[p.model_dump() for p in prices])
    except Exception:  # noqa: BLE001
        return PricesResponse()


@router.get("/tickers/{symbol}/news", response_model=NewsResponse)
async def get_news(
    symbol: str,
    start_date: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    end_date: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    limit: int = Query(50, ge=1, le=1000),
) -> NewsResponse:
    end = end_date or datetime.now(UTC).strftime("%Y-%m-%d")
    start = start_date or (datetime.strptime(end, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")
    ticker = symbol.upper()
    try:
        news = await asyncio.to_thread(_get_company_news, ticker, end, start, limit)
        return NewsResponse(news=[n.model_dump() for n in news])
    except Exception:  # noqa: BLE001
        return NewsResponse()


@router.get("/tickers/{symbol}/financial-metrics", response_model=FinancialMetricsResponse)
async def get_financial_metrics(
    symbol: str,
    end_date: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    period: str = Query("ttm"),
    limit: int = Query(10, ge=1, le=100),
) -> FinancialMetricsResponse:
    end = end_date or datetime.now(UTC).strftime("%Y-%m-%d")
    ticker = symbol.upper()
    try:
        metrics = await asyncio.to_thread(_get_financial_metrics, ticker, end, period, limit)
        return FinancialMetricsResponse(financial_metrics=[m.model_dump() for m in metrics])
    except Exception:  # noqa: BLE001
        return FinancialMetricsResponse(financial_metrics=[])


@router.get("/tickers/{symbol}/insider-trades", response_model=InsiderTradesResponse)
async def get_insider_trades(
    symbol: str,
    end_date: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    start_date: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    limit: int = Query(100, ge=1, le=1000),
) -> InsiderTradesResponse:
    end = end_date or datetime.now(UTC).strftime("%Y-%m-%d")
    ticker = symbol.upper()
    try:
        trades = await asyncio.to_thread(_get_insider_trades, ticker, end, start_date, limit)
        return InsiderTradesResponse(insider_trades=[t.model_dump() for t in trades])
    except Exception:  # noqa: BLE001
        return InsiderTradesResponse(insider_trades=[])
