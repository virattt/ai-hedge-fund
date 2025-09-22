"""Adapters for interacting with Alpaca's paper trading REST API."""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pydantic import ValidationError

try:
    from alpaca_trade_api import REST  # type: ignore
    from alpaca_trade_api.rest import APIError  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    REST = None  # type: ignore

    class APIError(Exception):  # type: ignore
        """Fallback error so caller code can catch API failures uniformly."""

        pass

from src.agents.portfolio_manager import PortfolioDecision

_LOGGER = logging.getLogger(__name__)


def _env(*names: str) -> Optional[str]:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


def _isoformat(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, str):
        return value
    return str(value)


def _serialize_response(response: Any) -> Dict[str, Any]:
    if response is None:
        return {}
    raw = getattr(response, "_raw", None)
    if isinstance(raw, dict):
        return raw
    if hasattr(response, "_raw") and hasattr(response._raw, "_raw"):
        inner = getattr(response._raw, "_raw")
        if isinstance(inner, dict):
            return inner
    if hasattr(response, "_raw") and hasattr(response._raw, "__dict__"):
        return dict(response._raw.__dict__)
    if hasattr(response, "__dict__"):
        return {
            key: value
            for key, value in response.__dict__.items()
            if not key.startswith("_")
        }
    return {"value": str(response)}


@dataclass
class BrokerOrder:
    ticker: str
    action: str
    quantity: int
    side: str
    order_id: Optional[str] = None
    status: str = "skipped"
    submitted_at: Optional[str] = None
    filled_at: Optional[str] = None
    error: Optional[str] = None
    dry_run: bool = False
    raw: Dict[str, Any] = field(default_factory=dict)

    def as_record(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "action": self.action,
            "side": self.side,
            "quantity": self.quantity,
            "order_id": self.order_id,
            "status": self.status,
            "submitted_at": self.submitted_at,
            "filled_at": self.filled_at,
            "error": self.error,
            "dry_run": self.dry_run,
            "raw": self.raw,
        }


class PaperBroker:
    """Wrapper around Alpaca's REST API tuned for paper trading."""

    ACTION_TO_SIDE = {
        "buy": "buy",
        "sell": "sell",
        "short": "sell",
        "cover": "buy",
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        base_url: Optional[str] = None,
        *,
        confidence_threshold: int = 60,
        dry_run: bool = False,
    ) -> None:
        self._logger = _LOGGER
        self.dry_run = dry_run
        self.confidence_threshold = confidence_threshold

        self.api_key = api_key or _env("ALPACA_API_KEY_ID", "APCA_API_KEY_ID")
        self.api_secret = api_secret or _env(
            "ALPACA_API_SECRET_KEY", "APCA_API_SECRET_KEY"
        )
        self.base_url = base_url or _env(
            "ALPACA_API_BASE_URL", "APCA_API_BASE_URL"
        )
        if not self.base_url:
            self.base_url = "https://paper-api.alpaca.markets"

        confidence_override = os.getenv("ALPACA_CONFIDENCE_THRESHOLD")
        if confidence_override:
            try:
                self.confidence_threshold = int(confidence_override)
            except ValueError:
                self._logger.warning(
                    "Invalid ALPACA_CONFIDENCE_THRESHOLD=%s", confidence_override
                )

        self._client: Optional[REST] = None
        if REST is None:
            self._logger.warning(
                "alpaca-trade-api is not installed; paper trading will run in dry-run mode"
            )
        elif not self.dry_run:
            if not self.api_key or not self.api_secret:
                self._logger.warning(
                    "Missing Alpaca credentials. Falling back to dry-run mode."
                )
                self.dry_run = True
            else:
                try:
                    self._client = REST(
                        key_id=self.api_key,
                        secret_key=self.api_secret,
                        base_url=self.base_url,
                        api_version="v2",
                    )
                except Exception as exc:  # pragma: no cover - network
                    self._logger.error("Failed to initialize Alpaca REST client: %s", exc)
                    self._client = None
                    self.dry_run = True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def submit_order(
        self,
        ticker: str,
        decision: PortfolioDecision | Dict[str, Any],
        *,
        time_in_force: str = "day",
    ) -> BrokerOrder:
        """Submit an equity order to Alpaca (market DAY order by default)."""

        parsed = self._coerce_decision(decision)
        if parsed is None:
            return BrokerOrder(
                ticker=ticker,
                action=str(getattr(decision, "action", "unknown")),
                quantity=0,
                side="unknown",
                status="invalid_decision",
                error="Unable to parse decision",
            )

        action = parsed.action.lower()
        quantity = int(parsed.quantity)
        side = self.ACTION_TO_SIDE.get(action)

        if side is None:
            return BrokerOrder(
                ticker=ticker,
                action=parsed.action,
                quantity=quantity,
                side="unknown",
                status="skipped",
                error=f"Unsupported action: {parsed.action}",
            )

        if quantity <= 0:
            return BrokerOrder(
                ticker=ticker,
                action=parsed.action,
                quantity=quantity,
                side=side,
                status="skipped",
                error="Non-positive quantity",
            )

        if parsed.confidence is not None and parsed.confidence < self.confidence_threshold:
            return BrokerOrder(
                ticker=ticker,
                action=parsed.action,
                quantity=quantity,
                side=side,
                status="skipped_confidence",
                error="Decision confidence below threshold",
            )

        if self.dry_run or self._client is None:
            now = datetime.now(timezone.utc).isoformat()
            return BrokerOrder(
                ticker=ticker,
                action=parsed.action,
                quantity=quantity,
                side=side,
                order_id=f"dry-{ticker}-{int(time.time() * 1000)}",
                status="accepted_dry_run",
                submitted_at=now,
                dry_run=True,
            )

        try:
            response = self._client.submit_order(
                symbol=ticker,
                qty=quantity,
                side=side,
                type="market",
                time_in_force=time_in_force,
            )
            return self._to_broker_order(
                ticker=ticker,
                action=parsed.action,
                quantity=quantity,
                side=side,
                response=response,
            )
        except APIError as exc:  # pragma: no cover - API error path
            self._logger.error("Alpaca API error submitting order: %s", exc)
            return BrokerOrder(
                ticker=ticker,
                action=parsed.action,
                quantity=quantity,
                side=side,
                status="error",
                error=str(exc),
            )
        except Exception as exc:  # pragma: no cover - API error path
            self._logger.exception("Unexpected error submitting Alpaca order")
            return BrokerOrder(
                ticker=ticker,
                action=parsed.action,
                quantity=quantity,
                side=side,
                status="error",
                error=str(exc),
            )

    def replace_order(
        self,
        order_id: str,
        ticker: str,
        decision: PortfolioDecision | Dict[str, Any],
        *,
        time_in_force: str = "day",
    ) -> BrokerOrder:
        parsed = self._coerce_decision(decision)
        if parsed is None:
            return BrokerOrder(
                ticker=ticker,
                action=str(getattr(decision, "action", "unknown")),
                quantity=0,
                side="unknown",
                status="invalid_decision",
                error="Unable to parse decision",
            )

        side = self.ACTION_TO_SIDE.get(parsed.action.lower(), "unknown")
        quantity = int(parsed.quantity)
        if self.dry_run or self._client is None:
            return BrokerOrder(
                ticker=ticker,
                action=parsed.action,
                quantity=quantity,
                side=side,
                order_id=order_id,
                status="accepted_dry_run",
                submitted_at=datetime.now(timezone.utc).isoformat(),
                dry_run=True,
            )

        try:
            response = self._client.replace_order(
                order_id,
                qty=quantity if quantity > 0 else None,
                time_in_force=time_in_force,
            )
            return self._to_broker_order(
                ticker=ticker,
                action=parsed.action,
                quantity=quantity,
                side=side,
                response=response,
            )
        except APIError as exc:  # pragma: no cover - API error path
            self._logger.error("Alpaca API error replacing order %s: %s", order_id, exc)
            return BrokerOrder(
                ticker=ticker,
                action=parsed.action,
                quantity=quantity,
                side=side,
                order_id=order_id,
                status="error",
                error=str(exc),
            )
        except Exception as exc:  # pragma: no cover - API error path
            self._logger.exception("Unexpected error replacing Alpaca order")
            return BrokerOrder(
                ticker=ticker,
                action=parsed.action,
                quantity=quantity,
                side=side,
                order_id=order_id,
                status="error",
                error=str(exc),
            )

    def cancel_order(self, order_id: str, ticker: str, action: str) -> BrokerOrder:
        side = self.ACTION_TO_SIDE.get(action.lower(), "unknown")
        if self.dry_run or self._client is None:
            return BrokerOrder(
                ticker=ticker,
                action=action,
                quantity=0,
                side=side,
                order_id=order_id,
                status="cancelled_dry_run",
                submitted_at=datetime.now(timezone.utc).isoformat(),
                dry_run=True,
            )

        try:
            self._client.cancel_order(order_id)
            return BrokerOrder(
                ticker=ticker,
                action=action,
                quantity=0,
                side=side,
                order_id=order_id,
                status="cancelled",
            )
        except APIError as exc:  # pragma: no cover - API error path
            self._logger.error("Alpaca API error cancelling order %s: %s", order_id, exc)
            return BrokerOrder(
                ticker=ticker,
                action=action,
                quantity=0,
                side=side,
                order_id=order_id,
                status="error",
                error=str(exc),
            )
        except Exception as exc:  # pragma: no cover - API error path
            self._logger.exception("Unexpected error cancelling Alpaca order")
            return BrokerOrder(
                ticker=ticker,
                action=action,
                quantity=0,
                side=side,
                order_id=order_id,
                status="error",
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _coerce_decision(
        self, decision: PortfolioDecision | Dict[str, Any]
    ) -> Optional[PortfolioDecision]:
        if isinstance(decision, PortfolioDecision):
            return decision
        try:
            return PortfolioDecision.model_validate(decision)
        except ValidationError as exc:
            self._logger.error("Invalid PortfolioDecision payload: %s", exc)
            return None

    def _to_broker_order(
        self,
        *,
        ticker: str,
        action: str,
        quantity: int,
        side: str,
        response: Any,
    ) -> BrokerOrder:
        order_id = getattr(response, "id", None) or getattr(response, "order_id", None)
        status = getattr(response, "status", "submitted")
        submitted_at = _isoformat(getattr(response, "submitted_at", None))
        filled_at = _isoformat(getattr(response, "filled_at", None))
        raw = _serialize_response(response)

        return BrokerOrder(
            ticker=ticker,
            action=action,
            quantity=quantity,
            side=side,
            order_id=order_id,
            status=status,
            submitted_at=submitted_at,
            filled_at=filled_at,
            raw=raw,
        )


__all__ = ["PaperBroker", "BrokerOrder"]
