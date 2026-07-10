"""Convert agent decisions into broker orders with safety checks."""

from __future__ import annotations

import logging
from typing import Any

from integrations.alpaca.config import AlpacaConfig
from integrations.broker.models import OrderResult, TradeOrder
from integrations.broker.protocol import BrokerClient

logger = logging.getLogger(__name__)


def decisions_to_orders(decisions: dict[str, Any] | None) -> list[TradeOrder]:
    """Map portfolio-manager JSON output to TradeOrder objects."""
    if not decisions:
        return []

    orders: list[TradeOrder] = []
    for ticker, decision in decisions.items():
        action = str(decision.get("action", "hold")).lower()
        quantity = int(decision.get("quantity", 0) or 0)
        reasoning = str(decision.get("reasoning", ""))
        orders.append(
            TradeOrder(
                ticker=ticker.upper(),
                action=action,  # type: ignore[arg-type]
                quantity=max(quantity, 0),
                reason=reasoning,
            )
        )
    return orders


def validate_order(order: TradeOrder, config: AlpacaConfig | None, reference_price: float = 0.0) -> str | None:
    """Return an error message if the order fails safety checks, else None."""
    if order.action == "hold" or order.quantity <= 0:
        return None

    if config is None:
        return None

    if config.kill_switch:
        return "Kill switch is active."

    if config.allowed_tickers and order.ticker.upper() not in config.allowed_tickers:
        return f"Ticker {order.ticker} is not in ALLOWED_TICKERS."

    if reference_price > 0 and config.max_order_notional > 0:
        notional = order.quantity * reference_price
        if notional > config.max_order_notional:
            return (
                f"Order notional ${notional:,.2f} exceeds "
                f"MAX_ORDER_NOTIONAL ${config.max_order_notional:,.2f}."
            )

    return None


def execute_orders(
    broker: BrokerClient,
    orders: list[TradeOrder],
    *,
    config: AlpacaConfig | None = None,
    reference_prices: dict[str, float] | None = None,
) -> list[OrderResult]:
    """Submit orders through the broker after safety validation."""
    results: list[OrderResult] = []
    prices = reference_prices or {}

    for order in orders:
        if order.action == "hold" or order.quantity <= 0:
            continue

        error = validate_order(order, config, prices.get(order.ticker, 0.0))
        if error:
            logger.warning("Skipping %s %s: %s", order.action, order.ticker, error)
            results.append(
                OrderResult(
                    submitted=False,
                    dry_run=True,
                    order=order,
                    message=error,
                )
            )
            continue

        results.append(broker.submit_order(order))

    return results
