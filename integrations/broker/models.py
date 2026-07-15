"""Broker data models — shared across all broker implementations."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Position(BaseModel):
    ticker: str
    quantity: int = Field(description="Positive = long, negative = short")
    avg_entry_price: float = 0.0
    current_price: float = 0.0
    market_value: float = 0.0
    side: Literal["long", "short"] = "long"


class AccountSnapshot(BaseModel):
    cash: float
    equity: float
    buying_power: float
    portfolio_value: float
    currency: str = "USD"


class MarketClock(BaseModel):
    is_open: bool
    next_open: str | None = None
    next_close: str | None = None


class TradeOrder(BaseModel):
    ticker: str
    action: Literal["buy", "sell", "short", "cover", "hold"]
    quantity: int = 0
    reason: str = ""


class OrderStatus(BaseModel):
    order_id: str
    ticker: str
    side: str
    quantity: float
    status: str
    filled_qty: float = 0.0
    filled_avg_price: float | None = None


class OrderResult(BaseModel):
    submitted: bool
    dry_run: bool
    order: TradeOrder
    broker_order_id: str | None = None
    message: str = ""
