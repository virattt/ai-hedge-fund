"""Backtest endpoints — stub level for F3.

Returns empty collections so the frontend can render without crashing.
Real backtester integration is a separate task.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class BacktestListResponse(BaseModel):
    items: list = []


@router.get("/backtests", response_model=BacktestListResponse)
def list_backtests() -> BacktestListResponse:
    return BacktestListResponse()
