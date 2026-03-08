"""Order, position, and account models for the execution layer."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class AssetClass(str, Enum):
    EQUITY = "EQUITY"
    OPTION = "OPTION"
    PERP = "PERP"


class OptionDetails(BaseModel):
    """Option-specific order details."""

    strike: float
    expiry: str  # YYYY-MM-DD
    option_type: str  # "call" | "put"
    strategy_type: str | None = None  # e.g. "covered_call", "cash_secured_put"


class Order(BaseModel):
    """Unified order representation across brokers."""

    ticker: str
    side: OrderSide
    quantity: float
    order_type: OrderType = OrderType.MARKET
    asset_class: AssetClass = AssetClass.EQUITY
    option_details: OptionDetails | None = None
    limit_price: float | None = None
    stop_price: float | None = None
    client_order_id: str | None = None


class OrderResult(BaseModel):
    """Result of order submission."""

    order_id: str
    status: OrderStatus
    filled_quantity: float = 0.0
    average_fill_price: float | None = None
    message: str | None = None


class Position(BaseModel):
    """Single position (long or short)."""

    ticker: str
    quantity: float  # positive = long, negative = short
    avg_price: float
    unrealized_pnl: float | None = None
    asset_class: AssetClass = AssetClass.EQUITY


class AccountInfo(BaseModel):
    """Broker account summary."""

    cash: float
    equity: float
    buying_power: float
    margin_used: float = 0.0
    positions: list[Position] = Field(default_factory=list)
