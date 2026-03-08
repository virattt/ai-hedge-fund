"""Execution layer: broker abstraction, order management, and risk controls."""

from src.execution.broker import BaseBroker
from src.execution.models import (
    AccountInfo,
    Order,
    OrderResult,
    OrderStatus,
    Position,
)
from src.execution.order_manager import OrderManager
from src.execution.paper_broker import PaperBroker
from src.execution.risk_config import RiskConfig
from src.execution.risk_engine import PreTradeRiskEngine

try:
    from src.execution.tastytrade_broker import TastytradeBroker
except (RuntimeError, ImportError):
    TastytradeBroker = None  # type: ignore

try:
    from src.execution.hyperliquid_broker import HyperliquidBroker
except (RuntimeError, ImportError):
    HyperliquidBroker = None  # type: ignore

__all__ = [
    "AccountInfo",
    "BaseBroker",
    "Order",
    "OrderManager",
    "OrderResult",
    "OrderStatus",
    "PaperBroker",
    "Position",
    "PreTradeRiskEngine",
    "RiskConfig",
    "TastytradeBroker",
    "HyperliquidBroker",
]
