"""Utilities for recording executions in Azure Cosmos DB."""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from src.brokers.alpaca import BrokerOrder

_LOGGER = logging.getLogger(__name__)

try:  # pragma: no cover - optional dependency
    from azure.cosmos import CosmosClient, PartitionKey  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    CosmosClient = None  # type: ignore
    PartitionKey = None  # type: ignore


class CosmosOrderStore:
    """Persist executed broker orders for reconciliation."""

    def __init__(
        self,
        *,
        endpoint: Optional[str] = None,
        key: Optional[str] = None,
        database: Optional[str] = None,
        container: Optional[str] = None,
        dry_run: bool = False,
    ) -> None:
        self._logger = _LOGGER
        self.enabled = not dry_run

        self.endpoint = endpoint or os.getenv("COSMOS_ENDPOINT") or os.getenv(
            "AZURE_COSMOS_ENDPOINT"
        )
        self.key = key or os.getenv("COSMOS_KEY") or os.getenv("AZURE_COSMOS_KEY")
        self.database_name = database or os.getenv("COSMOS_DATABASE", "hedge-fund")
        self.container_name = container or os.getenv(
            "COSMOS_CONTAINER", "broker-orders"
        )

        self._client = None
        self._container = None

        if not self.enabled:
            self._logger.debug("Cosmos order store disabled due to dry-run mode")
            return

        if CosmosClient is None:
            self._logger.warning(
                "azure-cosmos is not installed; order persistence disabled"
            )
            self.enabled = False
            return

        if not self.endpoint or not self.key:
            self._logger.warning(
                "Missing Cosmos credentials; order persistence disabled"
            )
            self.enabled = False
            return

        try:
            self._client = CosmosClient(self.endpoint, credential=self.key)  # type: ignore[arg-type]
            database_client = self._client.create_database_if_not_exists(  # type: ignore[assignment]
                id=self.database_name
            )
            partition_key = PartitionKey(path="/ticker") if PartitionKey else None
            self._container = database_client.create_container_if_not_exists(  # type: ignore[assignment]
                id=self.container_name,
                partition_key=partition_key,
            )
        except Exception as exc:  # pragma: no cover - requires Cosmos env
            self._logger.error("Failed to initialise Cosmos persistence: %s", exc)
            self.enabled = False
            self._client = None
            self._container = None

    def record_order(
        self,
        order: BrokerOrder | Dict[str, Any],
        *,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Upsert a broker order record into Cosmos DB."""

        if not self.enabled or self._container is None:
            return None

        record = self._normalise_order(order)
        if record is None:
            return None

        now = datetime.now(timezone.utc).isoformat()
        record.setdefault("created_at", now)
        record["updated_at"] = now
        if metadata:
            record.setdefault("metadata", {}).update(metadata)

        try:
            result = self._container.upsert_item(record)  # type: ignore[union-attr]
            return result.get("id") if isinstance(result, dict) else record.get("id")
        except Exception as exc:  # pragma: no cover - requires Cosmos env
            self._logger.error("Failed to persist order %s: %s", record.get("id"), exc)
            return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _normalise_order(
        self, order: BrokerOrder | Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        if isinstance(order, BrokerOrder):
            base = order.as_record()
        elif isinstance(order, dict):
            base = dict(order)
        else:
            self._logger.error("Unsupported order payload type: %s", type(order))
            return None

        ticker = base.get("ticker")
        if not ticker:
            self._logger.error("Broker order missing ticker: %s", base)
            return None

        order_id = base.get("order_id") or str(uuid.uuid4())
        base.setdefault("id", order_id)
        base.setdefault("broker", "alpaca")
        base.setdefault("status", "unknown")

        raw = base.get("raw")
        if isinstance(raw, (list, tuple, set)):
            base["raw"] = list(raw)
        elif isinstance(raw, bytes):
            base["raw"] = raw.decode("utf-8", errors="ignore")
        elif raw and not isinstance(raw, (dict, str)):
            try:
                base["raw"] = json.loads(json.dumps(raw, default=str))
            except Exception:
                base["raw"] = str(raw)

        return base


__all__ = ["CosmosOrderStore"]
