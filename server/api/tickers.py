"""Ticker pass-through endpoints — stub level for F4.

Returns empty collections so the frontend can render without crashing.
Real data integration (financial datasets API) is a separate task.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class PricesResponse(BaseModel):
    prices: list = []


class NewsResponse(BaseModel):
    news: list = []


@router.get("/tickers/{symbol}/prices", response_model=PricesResponse)
def get_prices(symbol: str) -> PricesResponse:  # noqa: ARG001
    return PricesResponse()


@router.get("/tickers/{symbol}/news", response_model=NewsResponse)
def get_news(symbol: str) -> NewsResponse:  # noqa: ARG001
    return NewsResponse()
