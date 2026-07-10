"""No-op broker — logs intended trades without submitting anything."""

from __future__ import annotations

import logging

from integrations.broker.models import (
    AccountSnapshot,
    MarketClock,
    OrderResult,
    OrderStatus,
    Position,
    TradeOrder,
)

logger = logging.getLogger(__name__)


class NoOpBroker:
    """Safe default broker for development and dry runs."""

    def __init__(
        self,
        *,
        cash: float = 100_000.0,
        positions: list[Position] | None = None,
    ) -> None:
        self._cash = cash
        self._positions = positions or []

    @property
    def name(self) -> str:
        return "noop"

    def get_account(self) -> AccountSnapshot:
        position_value = sum(p.market_value for p in self._positions)
        portfolio_value = self._cash + position_value
        return AccountSnapshot(
            cash=self._cash,
            equity=portfolio_value,
            buying_power=self._cash,
            portfolio_value=portfolio_value,
        )

    def get_positions(self) -> list[Position]:
        return list(self._positions)

    def get_open_orders(self) -> list[OrderStatus]:
        return []

    def is_market_open(self) -> bool:
        return True

    def submit_order(self, order: TradeOrder) -> OrderResult:
        if order.action == "hold" or order.quantity <= 0:
            return OrderResult(
                submitted=False,
                dry_run=True,
                order=order,
                message="No order needed (hold or zero quantity).",
            )

        logger.info(
            "[DRY RUN] Would submit: %s %d %s — %s",
            order.action.upper(),
            order.quantity,
            order.ticker,
            order.reason,
        )
        return OrderResult(
            submitted=False,
            dry_run=True,
            order=order,
            message=f"Dry run: {order.action} {order.quantity} {order.ticker}",
        )

    def cancel_all_orders(self) -> None:
        logger.info("[DRY RUN] Would cancel all open orders.")
