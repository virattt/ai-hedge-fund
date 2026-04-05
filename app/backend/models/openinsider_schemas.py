"""Pydantic schemas for OpenInsider scraping data.

Defines request/response models for the OpenInsider screener endpoint,
representing data scraped from openinsider.com tables.
"""
from pydantic import BaseModel


class OpenInsiderRecord(BaseModel):
    """Single row from an openinsider.com screener results table.

    All string fields are returned as-is from the HTML table. Numeric fields
    use None when the cell is empty or unparseable.
    """

    filing_date: str
    trade_date: str
    ticker: str
    company_name: str
    insider_name: str
    title: str
    trade_type: str
    price: float | None = None
    qty: int | None = None
    owned: int | None = None
    delta_own: str | None = None
    value: float | None = None


class OpenInsiderResponse(BaseModel):
    """Top-level response envelope for the OpenInsider screener endpoint.

    preset identifies which screener configuration produced the results.
    cached is True when the response was served from the in-memory LRU+TTL cache.
    """

    preset: str
    records: list[OpenInsiderRecord]
    total: int
    cached: bool = False
