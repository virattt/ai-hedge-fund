"""Azure Cosmos DB persistence helpers."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from threading import Lock
from typing import Any, Dict, Optional

try:  # pragma: no cover - dependency provided at runtime
    from azure.cosmos import CosmosClient, exceptions
except ImportError:  # pragma: no cover - gracefully handle missing dependency
    CosmosClient = None  # type: ignore
    exceptions = None  # type: ignore

from src.config import CosmosSettings, get_cosmos_settings


LOGGER = logging.getLogger(__name__)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_partition_key(user_id: Optional[str], strategy_id: Optional[str]) -> str:
    user_component = user_id or "default"
    if strategy_id:
        return f"{user_component}::{strategy_id}"
    return user_component


class CosmosContainerManager:
    """Lazy manager that provides Cosmos container clients on demand."""

    def __init__(self, settings: CosmosSettings) -> None:
        self._settings = settings
        self._client: Optional[CosmosClient] = None
        self._database = None
        self._containers: Dict[str, Any] = {}
        self._lock = Lock()

    @property
    def is_configured(self) -> bool:
        return self._settings.is_configured and CosmosClient is not None

    def _get_client(self) -> Optional[CosmosClient]:
        if not self.is_configured:
            return None

        if self._client is None:
            try:
                self._client = CosmosClient(self._settings.endpoint, credential=self._settings.key)
            except Exception as exc:  # pragma: no cover - network errors
                LOGGER.warning("Failed to initialize Cosmos client: %s", exc)
                return None
        return self._client

    def _get_database(self):
        if self._database is not None:
            return self._database

        client = self._get_client()
        if client is None:
            return None

        try:
            self._database = client.get_database_client(self._settings.database)
        except Exception as exc:  # pragma: no cover - network errors
            LOGGER.warning("Failed to connect to Cosmos database '%s': %s", self._settings.database, exc)
            return None

        return self._database

    def get_container(self, container_name: Optional[str]):
        if not container_name or not self.is_configured:
            return None

        with self._lock:
            if container_name in self._containers:
                return self._containers[container_name]

            database = self._get_database()
            if database is None:
                return None

            try:
                container = database.get_container_client(container_name)
            except Exception as exc:  # pragma: no cover - network errors
                LOGGER.warning("Failed to obtain Cosmos container '%s': %s", container_name, exc)
                return None

            self._containers[container_name] = container
            return container


@dataclass(slots=True)
class CosmosPortfolioRepository:
    """Repository for managing user portfolios in Cosmos DB."""

    manager: CosmosContainerManager
    container_name: Optional[str]

    def _get_container(self):
        return self.manager.get_container(self.container_name)

    def load_portfolio(self, user_id: Optional[str], strategy_id: Optional[str] = None) -> Optional[dict]:
        container = self._get_container()
        if container is None:
            return None

        partition = _build_partition_key(user_id, strategy_id)
        document_id = partition
        try:
            item = container.read_item(item=document_id, partition_key=partition)
        except Exception as exc:
            if exceptions and isinstance(exc, exceptions.CosmosResourceNotFoundError):
                return None
            LOGGER.warning("Failed to load portfolio for %s: %s", partition, exc)
            return None

        return deepcopy(item.get("portfolio")) if item else None

    def save_portfolio(self, user_id: Optional[str], portfolio: dict, strategy_id: Optional[str] = None) -> bool:
        container = self._get_container()
        if container is None:
            return False

        partition = _build_partition_key(user_id, strategy_id)
        document = {
            "id": partition,
            "partition_key": partition,
            "user_id": user_id,
            "strategy_id": strategy_id,
            "portfolio": deepcopy(portfolio),
            "updated_at": _utcnow_iso(),
        }

        try:
            container.upsert_item(body=document)
            return True
        except Exception as exc:  # pragma: no cover - network errors
            LOGGER.warning("Failed to save portfolio for %s: %s", partition, exc)
            return False


@dataclass(slots=True)
class CosmosRunDocumentRepository:
    """Repository for persisting run artefacts like analyst signals or decisions."""

    manager: CosmosContainerManager
    container_name: Optional[str]
    document_type: str

    def _get_container(self):
        return self.manager.get_container(self.container_name)

    def upsert_document(
        self,
        run_id: str,
        user_id: Optional[str],
        payload: Dict[str, Any],
        *,
        strategy_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None,
    ) -> bool:
        container = self._get_container()
        if container is None:
            return False

        if not run_id:
            LOGGER.debug("Skipping Cosmos upsert because run_id is empty")
            return False

        partition = _build_partition_key(user_id, strategy_id)
        document = {
            "id": str(run_id),
            "partition_key": partition,
            "user_id": user_id,
            "strategy_id": strategy_id,
            "run_id": str(run_id),
            "document_type": self.document_type,
            "timestamp": timestamp or _utcnow_iso(),
            "data": deepcopy(payload),
            "metadata": metadata or {},
        }

        try:
            container.upsert_item(body=document)
            return True
        except Exception as exc:  # pragma: no cover - network errors
            LOGGER.warning(
                "Failed to upsert %s document for run %s (partition %s): %s",
                self.document_type,
                run_id,
                partition,
                exc,
            )
            return False


class CosmosPersistence:
    """Facade exposing Cosmos repositories used by the application."""

    def __init__(self, settings: Optional[CosmosSettings] = None) -> None:
        self.settings = settings or get_cosmos_settings()
        self._manager = CosmosContainerManager(self.settings)
        self.portfolios = CosmosPortfolioRepository(self._manager, self.settings.portfolio_container)
        self.analyst_documents = CosmosRunDocumentRepository(
            self._manager,
            self.settings.analyst_signals_container,
            "analyst_signals",
        )
        self.decision_documents = CosmosRunDocumentRepository(
            self._manager,
            self.settings.decisions_container,
            "decisions",
        )

    @property
    def is_configured(self) -> bool:
        return self._manager.is_configured


_PERSISTENCE_SINGLETON: Optional[CosmosPersistence] = None
_PERSISTENCE_LOCK = Lock()


def get_cosmos_persistence() -> CosmosPersistence:
    """Return a lazily-instantiated Cosmos persistence facade."""

    global _PERSISTENCE_SINGLETON
    if _PERSISTENCE_SINGLETON is not None:
        return _PERSISTENCE_SINGLETON

    with _PERSISTENCE_LOCK:
        if _PERSISTENCE_SINGLETON is None:
            _PERSISTENCE_SINGLETON = CosmosPersistence()

    return _PERSISTENCE_SINGLETON


__all__ = [
    "CosmosPersistence",
    "CosmosPortfolioRepository",
    "CosmosRunDocumentRepository",
    "get_cosmos_persistence",
]

