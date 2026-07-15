"""Alpaca broker adapter using alpaca-py TradingClient."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from integrations.alpaca.config import AlpacaConfig
from integrations.broker.models import (
    AccountSnapshot,
    MarketClock,
    OrderResult,
    OrderStatus,
    Position,
    TradeOrder,
)

if TYPE_CHECKING:
    from alpaca.trading.client import TradingClient

logger = logging.getLogger(__name__)

_ACTION_TO_SIDE = {
    "buy": "buy",
    "cover": "buy",
    "sell": "sell",
    "short": "sell",
}


class AlpacaBroker:
    """Read Alpaca account state; submit orders only when execution is enabled."""

    def __init__(self, config: AlpacaConfig) -> None:
        self._config = config
        self._client = self._create_client(config)

    @staticmethod
    def _create_client(config: AlpacaConfig) -> TradingClient:
        try:
            from alpaca.trading.client import TradingClient
        except ImportError as exc:
            raise ImportError(
                "alpaca-py is required for Alpaca integration. "
                "Install with: poetry install --with alpaca"
            ) from exc

        return TradingClient(
            api_key=config.api_key,
            secret_key=config.secret_key,
            paper=config.paper,
        )

    @property
    def name(self) -> str:
        return f"alpaca-{self._config.mode_label.lower()}"

    @property
    def config(self) -> AlpacaConfig:
        return self._config

    def get_account(self) -> AccountSnapshot:
        account = self._client.get_account()
        return AccountSnapshot(
            cash=float(account.cash),
            equity=float(account.equity),
            buying_power=float(account.buying_power),
            portfolio_value=float(account.portfolio_value),
            currency=str(account.currency),
        )

    def _raw_account(self):
        return self._client.get_account()

    def shorting_enabled(self) -> bool:
        account = self._raw_account()
        return bool(getattr(account, "shorting_enabled", False))

    def trading_blocked(self) -> bool:
        account = self._raw_account()
        return bool(getattr(account, "account_blocked", False) or getattr(account, "trading_blocked", False))

    def get_positions(self) -> list[Position]:
        positions: list[Position] = []
        for pos in self._client.get_all_positions():
            qty = int(float(pos.qty))
            side = "long" if qty >= 0 else "short"
            positions.append(
                Position(
                    ticker=str(pos.symbol).upper(),
                    quantity=qty,
                    avg_entry_price=float(pos.avg_entry_price),
                    current_price=float(pos.current_price),
                    market_value=float(pos.market_value),
                    side=side,
                )
            )
        return positions

    def get_open_orders(self) -> list[OrderStatus]:
        from alpaca.trading.requests import GetOrdersRequest
        from alpaca.trading.enums import QueryOrderStatus

        orders = self._client.get_orders(
            GetOrdersRequest(status=QueryOrderStatus.OPEN, limit=100)
        )
        return [
            OrderStatus(
                order_id=str(order.id),
                ticker=str(order.symbol),
                side=str(order.side),
                quantity=float(order.qty),
                status=str(order.status),
                filled_qty=float(order.filled_qty or 0),
                filled_avg_price=float(order.filled_avg_price) if order.filled_avg_price else None,
            )
            for order in orders
        ]

    def is_market_open(self) -> bool:
        clock = self._client.get_clock()
        return bool(clock.is_open)

    def submit_order(self, order: TradeOrder) -> OrderResult:
        if order.action == "hold" or order.quantity <= 0:
            return OrderResult(
                submitted=False,
                dry_run=True,
                order=order,
                message="No order needed (hold or zero quantity).",
            )

        if not self._config.execution_enabled:
            logger.info(
                "[READ-ONLY] Would submit: %s %d %s — %s",
                order.action.upper(),
                order.quantity,
                order.ticker,
                order.reason,
            )
            return OrderResult(
                submitted=False,
                dry_run=True,
                order=order,
                message=(
                    f"Execution disabled ({self._config.mode_label}). "
                    f"Use --execute or set LIVE_TRADING_ENABLED=true."
                ),
            )

        if self.trading_blocked():
            return OrderResult(
                submitted=False,
                dry_run=False,
                order=order,
                message="Account trading is blocked.",
            )

        if order.action in ("short", "sell"):
            position_qty = self._position_qty(order.ticker)
            if order.action == "short" or (order.action == "sell" and position_qty <= 0):
                if not self.shorting_enabled():
                    return OrderResult(
                        submitted=False,
                        dry_run=False,
                        order=order,
                        message="Short selling is not enabled on this Alpaca account.",
                    )

        if not self.is_market_open():
            return OrderResult(
                submitted=False,
                dry_run=False,
                order=order,
                message="Market is closed — order not submitted.",
            )

        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import MarketOrderRequest

        side_str = _ACTION_TO_SIDE[order.action]
        side = OrderSide.BUY if side_str == "buy" else OrderSide.SELL

        request = MarketOrderRequest(
            symbol=order.ticker.upper(),
            qty=order.quantity,
            side=side,
            time_in_force=TimeInForce.DAY,
        )
        result = self._client.submit_order(request)
        logger.info(
            "Submitted order %s: %s %d %s",
            result.id,
            order.action.upper(),
            order.quantity,
            order.ticker,
        )
        return OrderResult(
            submitted=True,
            dry_run=False,
            order=order,
            broker_order_id=str(result.id),
            message=f"Order submitted: {result.status}",
        )

    def cancel_all_orders(self) -> None:
        if not self._config.execution_enabled:
            logger.info("[READ-ONLY] Would cancel all open orders.")
            return
        self._client.cancel_orders()

    def get_market_clock(self) -> MarketClock:
        clock = self._client.get_clock()
        return MarketClock(
            is_open=bool(clock.is_open),
            next_open=clock.next_open.isoformat() if clock.next_open else None,
            next_close=clock.next_close.isoformat() if clock.next_close else None,
        )

    def _position_qty(self, ticker: str) -> int:
        try:
            pos = self._client.get_open_position(ticker.upper())
            return int(float(pos.qty))
        except Exception:
            return 0
