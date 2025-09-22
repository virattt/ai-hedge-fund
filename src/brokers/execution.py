"""Trading execution helpers built on top of broker adapters."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from pydantic import ValidationError

from src.agents.portfolio_manager import PortfolioDecision
from src.persistence import CosmosOrderStore

from .alpaca import BrokerOrder, PaperBroker

logger = logging.getLogger(__name__)


def extract_risk_limits(analyst_signals: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    limits: Dict[str, Dict[str, Any]] = {}
    for agent_id, payload in analyst_signals.items():
        if not isinstance(payload, dict):
            continue
        if not str(agent_id).startswith("risk_management_agent"):
            continue
        for ticker, details in payload.items():
            if isinstance(details, dict):
                limits[ticker] = details
    return limits


def dispatch_paper_orders(
    *,
    decisions: Dict[str, Any],
    analyst_signals: Dict[str, Any],
    state_data: Dict[str, Any],
    confidence_threshold: Optional[int],
    dry_run: bool,
) -> list[dict[str, Any]]:
    orders: list[dict[str, Any]] = []
    risk_limits = extract_risk_limits(analyst_signals)
    current_prices = state_data.get("current_prices", {}) or {}

    broker = PaperBroker(
        confidence_threshold=confidence_threshold or 60,
        dry_run=dry_run,
    )
    order_store = CosmosOrderStore(dry_run=dry_run)

    for ticker, raw_decision in decisions.items():
        try:
            decision = PortfolioDecision.model_validate(raw_decision)
        except ValidationError as exc:
            logger.error("Invalid decision for %s: %s", ticker, exc)
            continue

        action = decision.action.lower()
        if action == "hold":
            continue

        requested_quantity = int(decision.quantity)
        if requested_quantity <= 0:
            logger.info("Skipping %s order for %s due to non-positive quantity", action, ticker)
            continue

        risk_context = risk_limits.get(ticker, {})
        remaining_limit = float(risk_context.get("remaining_position_limit", 0) or 0)
        price = float(current_prices.get(ticker, 0) or 0)
        allowed_quantity = requested_quantity

        if remaining_limit <= 0 and risk_context:
            logger.info("Skipping %s for %s: no remaining risk limit", action, ticker)
            continue

        if price > 0 and remaining_limit > 0:
            max_qty = int(remaining_limit // price)
            if max_qty <= 0:
                logger.info("Skipping %s for %s: risk limit allows zero shares", action, ticker)
                continue
            allowed_quantity = min(requested_quantity, max_qty)

        if allowed_quantity <= 0:
            logger.info("Skipping %s for %s after risk adjustment", action, ticker)
            continue

        decision_to_submit = decision.model_copy(update={"quantity": allowed_quantity})

        try:
            broker_order = broker.submit_order(ticker, decision_to_submit)
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.exception("Failed to submit Alpaca order for %s", ticker)
            broker_order = BrokerOrder(
                ticker=ticker,
                action=decision.action,
                quantity=allowed_quantity,
                side=PaperBroker.ACTION_TO_SIDE.get(action, "unknown"),
                status="error",
                error=str(exc),
            )

        metadata = {
            "requested_quantity": requested_quantity,
            "risk_remaining_limit": remaining_limit if remaining_limit else None,
            "decision_confidence": decision.confidence,
            "current_price": price if price else None,
        }

        order_record = broker_order.as_record()
        order_record["metadata"] = metadata
        orders.append(order_record)
        order_store.record_order(broker_order, metadata=metadata)

    return orders


__all__ = ["dispatch_paper_orders", "extract_risk_limits"]
