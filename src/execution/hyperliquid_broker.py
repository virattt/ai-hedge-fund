"""Hyperliquid broker adapter: perpetual futures. Requires hyperliquid-python-sdk."""

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
    import eth_account
    from hyperliquid.exchange import Exchange
    from hyperliquid.info import Info
    from hyperliquid.utils.constants import MAINNET_API_URL, TESTNET_API_URL
    _HAS_HYPER = True
except ImportError:
    _HAS_HYPER = False
    Exchange = None  # type: ignore
    Info = None
    MAINNET_API_URL = ""
    TESTNET_API_URL = ""


class HyperliquidBroker(BaseBroker):
    """
    Implements BaseBroker for Hyperliquid perpetuals. Wallet from private key in .env;
    perp orders with leverage; funding rate data for arbitrage signals.
    """

    def __init__(
        self,
        private_key: str | None = None,
        account_address: str | None = None,
        testnet: bool = True,
    ):
        if not _HAS_HYPER:
            raise RuntimeError(
                "hyperliquid-python-sdk is required: pip install hyperliquid-python-sdk"
            )
        self._private_key = private_key or os.environ.get("HYPERLIQUID_PRIVATE_KEY", "")
        self._account_address = account_address or os.environ.get("HYPERLIQUID_ACCOUNT_ADDRESS", "")
        self._testnet = testnet
        self._wallet: Any = None
        self._exchange: Any = None
        self._info: Any = None

    def _get_exchange(self) -> Any:
        if self._exchange is not None:
            return self._exchange
        if not self._private_key:
            raise ValueError("HYPERLIQUID_PRIVATE_KEY or private_key required")
        self._wallet = eth_account.Account.from_key(self._private_key)
        url = TESTNET_API_URL if self._testnet else MAINNET_API_URL
        self._exchange = Exchange(
            self._wallet,
            url,
            account_address=self._account_address or self._wallet.address,
        )
        self._info = Info(url)
        return self._exchange

    async def connect(self) -> None:
        self._get_exchange()

    async def disconnect(self) -> None:
        self._exchange = None
        self._info = None
        self._wallet = None

    async def get_account(self) -> AccountInfo:
        ex = self._get_exchange()
        try:
            # User state: equity, margin summary
            meta = self._info.meta()
            user_state = self._info.user_state(
                self._account_address or self._wallet.address
            )
            margin_summary = user_state.get("marginSummary", {}) or user_state
            equity = float(margin_summary.get("accountValue", 0) or margin_summary.get("accountValue", 0))
            positions = await self.get_positions()
            return AccountInfo(
                cash=0.0,
                equity=equity,
                buying_power=equity,
                margin_used=float(margin_summary.get("totalMarginUsed", 0) or 0),
                positions=positions,
            )
        except Exception:
            return AccountInfo(cash=0.0, equity=0.0, buying_power=0.0)

    async def get_positions(self) -> list[Position]:
        try:
            ex = self._get_exchange()
            addr = self._account_address or self._wallet.address
            user_state = self._info.user_state(addr)
            asset_positions = user_state.get("assetPositions", []) or []
            out: list[Position] = []
            for ap in asset_positions:
                pos = ap.get("position", {}) or ap
                coin = pos.get("coin", "")
                szi = float(pos.get("szi", 0) or 0)
                entry_px = float(pos.get("entryPx", 0) or pos.get("entryPx", 0))
                if szi == 0:
                    continue
                out.append(
                    Position(
                        ticker=coin,
                        quantity=szi,
                        avg_price=entry_px,
                        unrealized_pnl=None,
                        asset_class=AssetClass.PERP,
                    )
                )
            return out
        except Exception:
            return []

    def get_funding_rates(self) -> dict[str, float]:
        """Return coin -> current funding rate for arbitrage signals."""
        try:
            self._get_exchange()
            funding = self._info.funding_history()
            out: dict[str, float] = {}
            for row in (funding or [])[:50]:
                coin = row.get("coin", "")
                rate = float(row.get("fundingRate", 0) or 0)
                if coin:
                    out[coin] = rate
            return out
        except Exception:
            return {}

    async def submit_order(self, order: Order) -> OrderResult:
        if order.asset_class != AssetClass.PERP:
            return OrderResult(
                order_id="",
                status=OrderStatus.REJECTED,
                message="HyperliquidBroker only supports PERP",
            )
        ex = self._get_exchange()
        try:
            coin = order.ticker.upper()
            is_buy = order.side.value == "BUY"
            size = order.quantity
            limit_price = order.limit_price
            if order.order_type == OrderType.MARKET:
                market_fn = getattr(ex, "market_open", None)
                if market_fn:
                    result = market_fn(coin, is_buy, size, None, 0.01)
                else:
                    result = ex.order(
                        coin=coin,
                        is_buy=is_buy,
                        size=size,
                        limit_price=str(limit_price or 0),
                        order_type={"limit": {"tif": "Ioc"}},
                    )
            else:
                result = ex.order(
                    coin=coin,
                    is_buy=is_buy,
                    size=size,
                    limit_price=str(limit_price or 0),
                    order_type={"limit": {"tif": "Gtc"}},
                )
            if result.get("status") == "ok":
                data = result.get("response", {}).get("data", {})
                statuses = data.get("statuses", [])
                oid = None
                for st in statuses:
                    if "resting" in st:
                        oid = st["resting"].get("oid")
                        break
                return OrderResult(
                    order_id=str(oid) if oid else "",
                    status=OrderStatus.SUBMITTED,
                    message=None,
                )
            return OrderResult(
                order_id="",
                status=OrderStatus.REJECTED,
                message=result.get("response", {}).get("message", str(result)),
            )
        except Exception as e:
            return OrderResult(
                order_id="",
                status=OrderStatus.REJECTED,
                message=str(e),
            )

    async def cancel_order(self, order_id: str) -> bool:
        try:
            ex = self._get_exchange()
            ex.cancel(order_id)
            return True
        except Exception:
            return False

    async def get_order_status(self, order_id: str) -> OrderStatus:
        try:
            addr = self._account_address or self._wallet.address
            order = self._info.query_order_by_oid(addr, int(order_id))
            if not order:
                return OrderStatus.REJECTED
            status = (order.get("status") or order.get("order", {}).get("status") or "").lower()
            if "filled" in status:
                return OrderStatus.FILLED
            if "cancel" in status:
                return OrderStatus.CANCELLED
            return OrderStatus.SUBMITTED
        except Exception:
            return OrderStatus.REJECTED
