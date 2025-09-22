"""Repository abstraction for persisting hedge fund artefacts in Azure Cosmos DB."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

try:  # pragma: no cover - azure client is optional in unit tests
    from azure.cosmos import CosmosClient
    from azure.cosmos.exceptions import CosmosHttpResponseError
except ImportError:  # pragma: no cover
    CosmosClient = None  # type: ignore
    CosmosHttpResponseError = Exception  # type: ignore

logger = logging.getLogger(__name__)


class CosmosRepository:
    """Small repository wrapper around Cosmos DB containers."""

    def __init__(
        self,
        *,
        endpoint: Optional[str] = None,
        key: Optional[str] = None,
        database_name: str = "",
        snapshot_container: str = "",
        result_container: str = "",
        status_container: str = "",
        client: Optional[CosmosClient] = None,
        use_stub: bool = False,
        stub_snapshot: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._use_stub = use_stub or CosmosClient is None or not (endpoint and key and database_name)
        self._stub_snapshot = stub_snapshot
        self._stub_results: list[Dict[str, Any]] = []
        self._stub_statuses: list[Dict[str, Any]] = []

        self._result_partition_field = os.getenv("COSMOS_RESULT_PARTITION_KEY", "messageId")
        self._status_partition_field = os.getenv("COSMOS_STATUS_PARTITION_KEY", "messageId")

        if self._use_stub:
            if stub_snapshot is None:
                stub_env_value = os.getenv("COSMOS_STUB_SNAPSHOT")
                if stub_env_value:
                    try:
                        self._stub_snapshot = json.loads(stub_env_value)
                    except json.JSONDecodeError:
                        logger.warning("Failed to parse COSMOS_STUB_SNAPSHOT. Falling back to empty portfolio.")
                if self._stub_snapshot is None:
                    self._stub_snapshot = {
                        "id": "stub-portfolio",
                        "portfolio": {
                            "positions": {},
                            "total_cash": 0.0,
                        },
                    }
            self._client = None
            self._database = None
            self._snapshot_container = None
            self._result_container = None
            self._status_container = None
            logger.info("Using in-memory CosmosRepository stub. Set COSMOS_ENDPOINT and COSMOS_KEY for live mode.")
            return

        if client is not None:
            self._client = client
        else:
            assert endpoint and key  # for mypy
            self._client = CosmosClient(endpoint, credential=key)

        self._database = self._client.get_database_client(database_name)
        self._snapshot_container = self._database.get_container_client(snapshot_container)
        self._result_container = self._database.get_container_client(result_container)
        self._status_container = self._database.get_container_client(status_container)

    @classmethod
    def from_environment(cls) -> "CosmosRepository":
        endpoint = os.getenv("COSMOS_ENDPOINT") or os.getenv("COSMOS_ACCOUNT_URI")
        key = os.getenv("COSMOS_KEY") or os.getenv("COSMOS_PRIMARY_KEY")
        database_name = os.getenv("COSMOS_DATABASE", "ai-hedge-fund")
        snapshot_container = os.getenv("COSMOS_SNAPSHOT_CONTAINER", "portfolioSnapshots")
        result_container = os.getenv("COSMOS_RESULTS_CONTAINER", "hedgeFundResults")
        status_container = os.getenv("COSMOS_STATUS_CONTAINER", "hedgeFundStatus")

        use_stub = not (endpoint and key)
        return cls(
            endpoint=endpoint,
            key=key,
            database_name=database_name,
            snapshot_container=snapshot_container,
            result_container=result_container,
            status_container=status_container,
            use_stub=use_stub,
        )

    # Portfolio snapshots -------------------------------------------------
    def get_latest_portfolio_snapshot(self) -> Dict[str, Any]:
        """Return the most recent portfolio snapshot stored in Cosmos."""

        if self._use_stub:
            assert self._stub_snapshot is not None
            return self._stub_snapshot

        query = "SELECT TOP 1 * FROM c ORDER BY c._ts DESC"
        try:
            items = list(
                self._snapshot_container.query_items(
                    query=query,
                    enable_cross_partition_query=True,
                )
            )
        except CosmosHttpResponseError as exc:  # pragma: no cover - network interaction
            logger.error("Failed to query Cosmos for portfolio snapshot: %s", exc)
            raise

        if not items:
            raise RuntimeError("No portfolio snapshots found in Cosmos DB")
        return items[0]

    # Run results ---------------------------------------------------------
    def save_run_result(self, message_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Persist the hedge fund output for the processed message."""

        record = dict(payload)
        record.setdefault("id", message_id)
        record.setdefault("messageId", message_id)
        record.setdefault("processedAt", datetime.now(timezone.utc).isoformat())

        if self._use_stub:
            self._stub_results.append(record)
            return record

        if self._result_partition_field not in record:
            record[self._result_partition_field] = record["messageId"]

        try:  # pragma: no cover - requires Cosmos DB
            self._result_container.upsert_item(record)
        except CosmosHttpResponseError as exc:
            logger.error("Failed to upsert hedge fund result: %s", exc)
            raise
        return record

    # Status --------------------------------------------------------------
    def publish_status(self, message_id: str, status_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Publish a concise completion status for downstream automation."""

        record = dict(status_payload)
        record.setdefault("id", message_id)
        record.setdefault("messageId", message_id)
        record.setdefault("processedAt", datetime.now(timezone.utc).isoformat())
        record.setdefault("status", "completed")

        if self._use_stub:
            self._stub_statuses.append(record)
            return record

        if self._status_partition_field not in record:
            record[self._status_partition_field] = record["messageId"]

        try:  # pragma: no cover
            self._status_container.upsert_item(record)
        except CosmosHttpResponseError as exc:
            logger.error("Failed to upsert status payload: %s", exc)
            raise
        return record


__all__ = ["CosmosRepository"]
