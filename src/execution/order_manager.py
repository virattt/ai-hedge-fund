"""Order Management System: decision-to-order translation, routing, idempotency, audit."""

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from src.execution.audit import log_audit_event
from src.execution.broker import BaseBroker
from src.execution.models import (
    AssetClass,
    Order,
    OrderSide,
    OrderType,
)
from src.execution.risk_engine import PreTradeRiskEngine


def _idempotency_key(ticker: str, d: date) -> str:
    return f"{ticker}:{d.isoformat()}"


class OrderManager:
    """
    Translates portfolio manager decisions into orders, routes to the appropriate
    broker, enforces idempotency per ticker per day, and writes an append-only audit log.
    """

    def __init__(
        self,
        broker: BaseBroker,
        audit_log_path: str | Path = "src/execution/audit.log.jsonl",
        idempotency_store_path: str | Path = ".order_manager_idempotency.json",
        risk_engine: PreTradeRiskEngine | None = None,
    ):
        self._broker = broker
        self._audit_log_path = Path(audit_log_path)
        self._idempotency_path = Path(idempotency_store_path)
        self._risk_engine = risk_engine
        self._sent_today: dict[str, date] = {}
        self._load_idempotency()

    def _load_idempotency(self) -> None:
        if not self._idempotency_path.exists():
            return
        try:
            with open(self._idempotency_path) as f:
                data = json.load(f)
            for k, v in data.items():
                self._sent_today[k] = date.fromisoformat(v)
        except Exception:
            pass

    def _save_idempotency(self) -> None:
        try:
            self._idempotency_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._idempotency_path, "w") as f:
                json.dump(
                    {k: d.isoformat() for k, d in self._sent_today.items()},
                    f,
                )
        except Exception:
            pass

    def _already_sent(self, ticker: str) -> bool:
        today = date.today()
        key = _idempotency_key(ticker, today)
        return key in self._sent_today

    def _mark_sent(self, ticker: str) -> None:
        today = date.today()
        key = _idempotency_key(ticker, today)
        self._sent_today[key] = today
        self._save_idempotency()

    @staticmethod
    def _decision_to_order(ticker: str, decision: dict[str, Any]) -> Order | None:
        action = (decision.get("action") or "hold").lower()
        if action not in ("buy", "sell"):
            return None
        quantity = int(decision.get("quantity", 0))
        if quantity <= 0:
            return None
        return Order(
            ticker=ticker,
            side=OrderSide.BUY if action == "buy" else OrderSide.SELL,
            quantity=float(quantity),
            order_type=OrderType.MARKET,
            asset_class=AssetClass.EQUITY,
        )

    def _get_broker_for_asset_class(self, asset_class: AssetClass) -> BaseBroker:
        return self._broker

    async def process_decisions(
        self,
        decisions: dict[str, Any],
        *,
        skip_idempotency: bool = False,
        current_prices: dict[str, float] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Convert a dict of ticker -> {action, quantity, confidence, reasoning} into
        orders, run idempotency and pre-trade risk checks, submit to broker, audit log.
        Returns list of results: [{ticker, order_id, status, message}, ...].
        """
        results = []
        account = await self._broker.get_account() if self._risk_engine else None
        for ticker, decision in decisions.items():
            if not skip_idempotency and self._already_sent(ticker):
                results.append({
                    "ticker": ticker,
                    "order_id": None,
                    "status": "skipped_idempotency",
                    "message": "Already sent an order for this ticker today",
                })
                log_audit_event(
                    "order_skipped_idempotency",
                    {"ticker": ticker, "decision": decision},
                    self._audit_log_path,
                )
                continue
            order = self._decision_to_order(ticker, decision)
            if order is None:
                results.append({
                    "ticker": ticker,
                    "order_id": None,
                    "status": "skipped",
                    "message": "hold or zero quantity",
                })
                continue
            if self._risk_engine and account is not None:
                allowed, reason = self._risk_engine.check_order(
                    order, account, current_prices
                )
                if not allowed:
                    results.append({
                        "ticker": ticker,
                        "order_id": None,
                        "status": "rejected_risk",
                        "message": reason,
                    })
                    log_audit_event(
                        "risk_check_fail",
                        {"ticker": ticker, "reason": reason, "order": order.model_dump()},
                        self._audit_log_path,
                    )
                    continue
            broker = self._get_broker_for_asset_class(order.asset_class)
            log_audit_event(
                "order_submitted",
                {"ticker": ticker, "side": order.side.value, "quantity": order.quantity},
                self._audit_log_path,
            )
            result = await broker.submit_order(order)
            if self._risk_engine:
                if result.status.value in ("FILLED", "PARTIALLY_FILLED"):
                    self._risk_engine.record_success()
                elif result.status.value == "REJECTED":
                    self._risk_engine.record_failure()
            if result.status.value == "FILLED":
                self._mark_sent(ticker)
            log_audit_event(
                "order_result",
                {
                    "ticker": ticker,
                    "order_id": result.order_id,
                    "status": result.status.value,
                    "filled_quantity": result.filled_quantity,
                    "average_fill_price": result.average_fill_price,
                    "message": result.message,
                },
                self._audit_log_path,
            )
            results.append({
                "ticker": ticker,
                "order_id": result.order_id,
                "status": result.status.value,
                "filled_quantity": result.filled_quantity,
                "average_fill_price": result.average_fill_price,
                "message": result.message,
            })
        return results
