"""Tastytrade broker adapter: equities and options. Requires tastytrade package.

OAuth (recommended, aligned with Dexter): TASTYTRADE_CLIENT_ID, TASTYTRADE_CLIENT_SECRET,
TASTYTRADE_REFRESH_TOKEN. Get refresh token via: https://my.tastytrade.com/app.html#/manage/api-access/oauth-applications
"""

import os
from typing import Any

from src.execution.broker import BaseBroker
from src.execution.models import (
    AccountInfo,
    AssetClass,
    Order,
    OrderResult,
    OrderStatus,
    OrderType,
    Position,
)

try:
    from tastytrade import OAuthSession
    from tastytrade.dx import DXLink
    _HAS_TASTY = True
except ImportError:
    _HAS_TASTY = False
    OAuthSession = None  # type: ignore
    DXLink = None


class TastytradeBroker(BaseBroker):
    """
    Implements BaseBroker for Tastytrade (equities + options). Uses OAuth (client_id,
    client_secret, refresh_token) aligned with Dexter. Requires: poetry install --extras tastytrade
    """

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        refresh_token: str | None = None,
        session: Any = None,
        is_test: bool = False,
    ):
        if not _HAS_TASTY:
            raise RuntimeError(
                "tastytrade package is required: poetry install --extras tastytrade"
            )
        self._client_id = client_id or os.environ.get("TASTYTRADE_CLIENT_ID", "")
        self._client_secret = client_secret or os.environ.get("TASTYTRADE_CLIENT_SECRET", "")
        self._refresh_token = refresh_token or os.environ.get("TASTYTRADE_REFRESH_TOKEN", "")
        self._session = session
        self._dx: Any = None
        self._is_test = is_test

    async def connect(self) -> None:
        if self._session is not None:
            return
        if not all([self._client_secret, self._refresh_token]):
            raise ValueError(
                "TASTYTRADE_CLIENT_SECRET and TASTYTRADE_REFRESH_TOKEN required. "
                "Create OAuth app at https://my.tastytrade.com/app.html#/manage/api-access/oauth-applications"
            )
        self._session = OAuthSession(
            self._client_secret,
            self._refresh_token,
        )
        try:
            self._dx = DXLink(self._session)
        except Exception:
            self._dx = None

    async def disconnect(self) -> None:
        if self._dx:
            try:
                await self._dx.close()
            except Exception:
                pass
        self._session = None
        self._dx = None

    async def get_account(self) -> AccountInfo:
        await self.connect()
        try:
            from tastytrade.account import get_accounts
            accounts = get_accounts(self._session)
            acc = accounts[0] if accounts else None
            if not acc:
                return AccountInfo(cash=0.0, equity=0.0, buying_power=0.0)
            cash = float(getattr(acc, "cash_balance", 0) or getattr(acc, "cashBalance", 0))
            equity = float(getattr(acc, "equity", 0) or cash)
            bp = float(getattr(acc, "buying_power", 0) or getattr(acc, "buyingPower", cash))
            positions: list[Position] = await self.get_positions()
            return AccountInfo(
                cash=cash,
                equity=equity,
                buying_power=bp,
                margin_used=0.0,
                positions=positions,
            )
        except Exception:
            return AccountInfo(cash=0.0, equity=0.0, buying_power=0.0)

    async def get_positions(self) -> list[Position]:
        await self.connect()
        try:
            from tastytrade.account import get_positions
            positions = get_positions(self._session)
            out: list[Position] = []
            for p in positions or []:
                sym = getattr(p, "symbol", "") or getattr(p, "underlying_symbol", "")
                qty = float(getattr(p, "quantity", 0) or 0)
                if qty == 0:
                    continue
                avg = float(getattr(p, "average_open_price", 0) or getattr(p, "averageOpenPrice", 0))
                out.append(
                    Position(
                        ticker=sym,
                        quantity=qty,
                        avg_price=avg,
                        unrealized_pnl=None,
                        asset_class=AssetClass.EQUITY,
                    )
                )
            return out
        except Exception:
            return []

    def _build_option_symbol(self, order: Order) -> str:
        if not order.option_details:
            return order.ticker
        d = order.option_details
        # OCC symbol: underlying 6 chars + expiry 6 (YYMMDD) + C/P + strike 8
        ul = order.ticker[:6].ljust(6)
        exp = d.expiry.replace("-", "")[2:]  # YYMMDD
        cp = "C" if (d.option_type or "call").lower() == "call" else "P"
        strike_str = f"{int(d.strike * 1000):08d}"
        return f"{ul}{exp}{cp}{strike_str}"

    async def submit_order(self, order: Order) -> OrderResult:
        await self.connect()
        if order.asset_class == AssetClass.OPTION and not order.option_details:
            return OrderResult(
                order_id="",
                status=OrderStatus.REJECTED,
                message="Option order requires option_details",
            )
        symbol = (
            self._build_option_symbol(order)
            if order.asset_class == AssetClass.OPTION
            else order.ticker
        )
        try:
            # Tastytrade SDK: create and place order (API may vary by SDK version)
            from tastytrade.order import OrderAction, OrderType as TastyOrderType
            action = OrderAction.BUY if order.side.value == "BUY" else OrderAction.SELL
            tasty_type = (
                TastyOrderType.MARKET
                if order.order_type == OrderType.MARKET
                else TastyOrderType.LIMIT
            )
            price = order.limit_price if order.order_type == OrderType.LIMIT else None
            place_fn = getattr(self._session, "place_order", None) or getattr(
                self._session, "create_order", None
            )
            if not place_fn:
                return OrderResult(
                    order_id="",
                    status=OrderStatus.REJECTED,
                    message="Tastytrade session has no place_order/create_order",
                )
            placed = place_fn(
                symbol=symbol,
                action=action,
                quantity=int(order.quantity),
                order_type=tasty_type,
                limit_price=price,
            )
            order_id = getattr(placed, "id", None) or getattr(placed, "order_id", "") or ""
            return OrderResult(
                order_id=str(order_id),
                status=OrderStatus.SUBMITTED,
                message=None,
            )
        except Exception as e:
            return OrderResult(
                order_id="",
                status=OrderStatus.REJECTED,
                message=str(e),
            )

    async def cancel_order(self, order_id: str) -> bool:
        await self.connect()
        cancel_fn = getattr(self._session, "cancel_order", None) or getattr(
            self._session, "delete_order", None
        )
        if not cancel_fn:
            return False
        try:
            cancel_fn(order_id)
            return True
        except Exception:
            return False

    async def get_order_status(self, order_id: str) -> OrderStatus:
        await self.connect()
        get_fn = getattr(self._session, "get_order", None) or getattr(
            self._session, "order", None
        )
        if not get_fn:
            return OrderStatus.REJECTED
        try:
            order = get_fn(order_id)
            status = getattr(order, "status", "") or getattr(order, "state", "")
            s = str(status).upper()
            if "FILLED" in s:
                return OrderStatus.FILLED
            if "CANCELLED" in s or "CANCELED" in s:
                return OrderStatus.CANCELLED
            if "REJECTED" in s:
                return OrderStatus.REJECTED
            if "PARTIAL" in s:
                return OrderStatus.PARTIALLY_FILLED
            return OrderStatus.SUBMITTED
        except Exception:
            return OrderStatus.REJECTED
