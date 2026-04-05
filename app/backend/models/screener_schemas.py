"""Pydantic schemas for the stock screener."""
from pydantic import BaseModel


class ScreenerRequest(BaseModel):
    filters: dict[str, str] = {}
    signal: str = ""
    ticker: str = ""
    order: str = "Ticker"
    ascend: bool = True
    limit: int = 200
    view: str = "overview"


class ScreenerFiltersResponse(BaseModel):
    filters: dict[str, list[str]]
    signals: list[str]
    orders: list[str]


class ScreenerResponse(BaseModel):
    columns: list[str]
    rows: list[dict]
    total: int
