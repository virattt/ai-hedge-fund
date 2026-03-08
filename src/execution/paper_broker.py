"""Paper broker: simulates fills at last known price, persists state to JSON."""

import json
import uuid
from pathlib import Path

from src.execution.broker import BaseBroker
from src.execution.models import (
    AccountInfo,
    AssetClass,
    Order,
    OrderResult,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
)


class PaperBroker(BaseBroker):
    """
    Simulates execution at last known price. Tracks cash and positions in memory
    and persists to a JSON file. Call set_last_price(ticker, price) before
    submitting orders so fills use realistic prices.
    """

    def __init__(
        self,
        initial_cash: float = 100_000.0,
        state_path: str | Path = ".paper_broker_state.json",
    ):
        self._initial_cash = initial_cash
        self._state_path = Path(state_path)
        self._cash = initial_cash
        self._positions: dict[str, dict] = {}  # ticker -> {quantity, avg_price, ...}
        self._orders: dict[str, dict] = {}  # order_id -> {order, status, filled_qty, fill_price}
        self._last_prices: dict[str, float] = {}
        self._load()

    def set_last_price(self, ticker: str, price: float) -> None:
        """Set last known price for a ticker (used for simulated fill price)."""
        self._last_prices[ticker] = price

    def get_fill_price(self, order: Order) -> float:
        """Resolve fill price: limit price if set, else last known price, else 0."""
        if order.order_type == OrderType.LIMIT and order.limit_price is not None:
            return order.limit_price
        return self._last_prices.get(order.ticker, 0.0)

    def _load(self) -> None:
        if not self._state_path.exists():
            return
        try:
            with open(self._state_path) as f:
                data = json.load(f)
            self._cash = data.get("cash", self._initial_cash)
            self._positions = data.get("positions", {})
            # Do not restore orders; only state
        except Exception:
            pass

    def _save(self) -> None:
        try:
            with open(self._state_path, "w") as f:
                json.dump(
                    {
                        "cash": self._cash,
                        "positions": self._positions,
                    },
                    f,
                    indent=2,
                )
        except Exception:
            pass

    async def connect(self) -> None:
        pass

    async def disconnect(self) -> None:
        self._save()

    async def get_account(self) -> AccountInfo:
        positions = await self.get_positions()
        position_value = sum(
            abs(p.quantity) * p.avg_price for p in positions
        )
        return AccountInfo(
            cash=self._cash,
            equity=self._cash + position_value,
            buying_power=self._cash,
            margin_used=0.0,
            positions=positions,
        )

    async def get_positions(self) -> list[Position]:
        out = []
        for ticker, data in self._positions.items():
            qty = data.get("quantity", 0.0)
            if qty == 0:
                continue
            out.append(
                Position(
                    ticker=ticker,
                    quantity=qty,
                    avg_price=data.get("avg_price", 0.0),
                    unrealized_pnl=None,
                    asset_class=AssetClass.EQUITY,
                )
            )
        return out

    async def submit_order(self, order: Order) -> OrderResult:
        fill_price = self.get_fill_price(order)
        if fill_price <= 0:
            return OrderResult(
                order_id="",
                status=OrderStatus.REJECTED,
                message="No price available for paper fill",
            )
        order_id = str(uuid.uuid4())
        pos = self._positions.setdefault(
            order.ticker,
            {"quantity": 0.0, "avg_price": 0.0},
        )
        prev_qty = pos["quantity"]
        prev_avg = pos["avg_price"]
        if order.side == OrderSide.BUY:
            cost = order.quantity * fill_price
            if cost > self._cash:
                return OrderResult(
                    order_id=order_id,
                    status=OrderStatus.REJECTED,
                    message="Insufficient cash for paper fill",
                )
            self._cash -= cost
            new_qty = prev_qty + order.quantity
            if new_qty != 0:
                pos["avg_price"] = (
                    prev_avg * prev_qty + fill_price * order.quantity
                ) / new_qty
            else:
                pos["avg_price"] = 0.0
            pos["quantity"] = new_qty
        else:
            if prev_qty < order.quantity:
                return OrderResult(
                    order_id=order_id,
                    status=OrderStatus.REJECTED,
                    message="Insufficient position for paper sell",
                )
            self._cash += order.quantity * fill_price
            new_qty = prev_qty - order.quantity
            pos["quantity"] = new_qty
            if new_qty == 0:
                pos["avg_price"] = 0.0
        self._orders[order_id] = {
            "order": order,
            "status": OrderStatus.FILLED,
            "filled_quantity": order.quantity,
            "fill_price": fill_price,
        }
        self._save()
        return OrderResult(
            order_id=order_id,
            status=OrderStatus.FILLED,
            filled_quantity=order.quantity,
            average_fill_price=fill_price,
        )

    async def cancel_order(self, order_id: str) -> bool:
        if order_id not in self._orders:
            return False
        rec = self._orders[order_id]
        if rec["status"] in (OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED):
            return False
        rec["status"] = OrderStatus.CANCELLED
        return True

    async def get_order_status(self, order_id: str) -> OrderStatus:
        if order_id not in self._orders:
            return OrderStatus.REJECTED
        return self._orders[order_id]["status"]
