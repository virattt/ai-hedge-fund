"""Queue-based job runner for the AI hedge fund."""

from __future__ import annotations

import json
import logging
import os
import random
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional

from dotenv import load_dotenv

try:  # pragma: no cover - imported lazily for environments without Azure SDK
    from azure.core.exceptions import AzureError, ResourceExistsError, ServiceRequestError, ServiceResponseError
    from azure.storage.queue import QueueClient, TextBase64DecodePolicy, TextBase64EncodePolicy
    from azure.storage.queue._models import QueueMessage
    try:
        from azure.cosmos.exceptions import CosmosHttpResponseError
    except ImportError:  # pragma: no cover
        CosmosHttpResponseError = AzureError  # type: ignore[misc,assignment]
except ImportError as exc:  # pragma: no cover
    raise RuntimeError(
        "The Azure Storage Queue SDK is required to run the queue worker."
        " Install the project with the 'azure-storage-queue' extra."
    ) from exc

import httpx

from src.data.cosmos_repository import CosmosRepository
from src.main import run_hedge_fund

logger = logging.getLogger(__name__)


class PoisonMessageError(Exception):
    """Raised when a queue message cannot be processed and should be dead-lettered."""


@dataclass(slots=True)
class QueueConfig:
    """Configuration required to connect to Azure Storage Queues."""

    account: str
    queue_name: str
    sas_token: str
    dead_letter_queue_name: str
    visibility_timeout: int = 300
    max_attempts: int = 5
    base_backoff_seconds: float = 2.0
    max_backoff_seconds: float = 30.0

    @classmethod
    def from_environment(cls) -> "QueueConfig":
        """Load queue configuration from environment variables."""

        account = os.getenv("QUEUE_ACCOUNT")
        queue_name = os.getenv("QUEUE_NAME")
        sas_token = os.getenv("QUEUE_SAS")

        if not all([account, queue_name, sas_token]):
            missing = [
                name
                for name, value in [
                    ("QUEUE_ACCOUNT", account),
                    ("QUEUE_NAME", queue_name),
                    ("QUEUE_SAS", sas_token),
                ]
                if not value
            ]
            raise RuntimeError(
                "Missing Azure Storage Queue configuration."
                f" Ensure the following variables are set: {', '.join(missing)}"
            )

        dead_letter_queue = os.getenv("QUEUE_DEAD_LETTER_NAME", f"{queue_name}-deadletter")
        visibility_timeout = int(os.getenv("QUEUE_VISIBILITY_TIMEOUT", "300"))
        max_attempts = int(os.getenv("QUEUE_MAX_ATTEMPTS", "5"))
        base_backoff = float(os.getenv("QUEUE_BACKOFF_SECONDS", "2"))
        max_backoff = float(os.getenv("QUEUE_BACKOFF_MAX_SECONDS", "30"))

        return cls(
            account=account,
            queue_name=queue_name,
            sas_token=sas_token.lstrip("?"),
            dead_letter_queue_name=dead_letter_queue,
            visibility_timeout=visibility_timeout,
            max_attempts=max_attempts,
            base_backoff_seconds=base_backoff,
            max_backoff_seconds=max_backoff,
        )


class QueueWorker:
    """Dequeues hedge-fund jobs, orchestrates processing, and reports completion."""

    RETRYABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
        ServiceRequestError,
        ServiceResponseError,
        AzureError,
        CosmosHttpResponseError,  # type: ignore[arg-type]
        httpx.HTTPError,
        TimeoutError,
    )

    def __init__(
        self,
        queue_client: QueueClient,
        repository: CosmosRepository,
        *,
        dead_letter_client: Optional[QueueClient] = None,
        config: Optional[QueueConfig] = None,
    ) -> None:
        self.queue_client = queue_client
        self.repository = repository
        self.dead_letter_client = dead_letter_client
        self.config = config or QueueConfig.from_environment()

    @classmethod
    def from_environment(cls) -> "QueueWorker":
        """Create a worker using environment variables."""

        config = QueueConfig.from_environment()
        account_url = f"https://{config.account}.queue.core.windows.net"

        encode_policy = TextBase64EncodePolicy()
        decode_policy = TextBase64DecodePolicy()

        queue_client = QueueClient(
            account_url=account_url,
            queue_name=config.queue_name,
            credential=config.sas_token,
            message_encode_policy=encode_policy,
            message_decode_policy=decode_policy,
        )

        dead_letter_client: Optional[QueueClient] = None
        try:
            dead_letter_client = QueueClient(
                account_url=account_url,
                queue_name=config.dead_letter_queue_name,
                credential=config.sas_token,
                message_encode_policy=encode_policy,
                message_decode_policy=decode_policy,
            )
            dead_letter_client.create_queue()
        except ResourceExistsError:
            pass
        except AzureError as exc:
            logger.warning("Unable to create or connect to dead-letter queue: %s", exc, exc_info=True)
            dead_letter_client = None

        repository = CosmosRepository.from_environment()
        return cls(
            queue_client=queue_client,
            repository=repository,
            dead_letter_client=dead_letter_client,
            config=config,
        )

    def run(self) -> None:
        """Receive and process a single queue message."""

        message = self._receive_message()
        if message is None:
            logger.info("No messages available on queue '%s'", self.config.queue_name)
            return

        logger.info("Processing message %s", message.id)
        try:
            payload = self._parse_message(message)
        except PoisonMessageError as exc:
            logger.error("Poison message detected: %s", exc)
            self._dead_letter(message, reason=str(exc))
            self._delete_message(message)
            return

        try:
            self._process_with_retries(message, payload)
        except PoisonMessageError as exc:
            logger.error("Poison message after validation: %s", exc)
            self._dead_letter(message, reason=str(exc))
            self._delete_message(message)
            return
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("Failed to process message %s: %s", message.id, exc)
            self._dead_letter(message, reason=f"processing_error: {exc}")
            self._delete_message(message)
            return

        self._delete_message(message)
        logger.info("Message %s processed successfully", message.id)

    def _receive_message(self) -> Optional[QueueMessage]:
        return self._execute_with_backoff(
            lambda: self.queue_client.receive_message(visibility_timeout=self.config.visibility_timeout),
            operation_name="receive_message",
        )

    def _delete_message(self, message: QueueMessage) -> None:
        if not message:
            return
        self._execute_with_backoff(
            lambda: self.queue_client.delete_message(message.id, message.pop_receipt),
            operation_name="delete_message",
            suppress_errors=True,
        )

    def _dead_letter(self, message: QueueMessage, *, reason: str) -> None:
        if not self.dead_letter_client:
            logger.warning(
                "Dead-letter queue not configured. Message %s will be dropped. Reason: %s",
                getattr(message, "id", "<unknown>"),
                reason,
            )
            return

        payload = {
            "originalMessageId": getattr(message, "id", None),
            "reason": reason,
            "content": getattr(message, "content", None),
            "deadLetteredAt": datetime.now(timezone.utc).isoformat(),
        }

        def _send() -> None:
            self.dead_letter_client.send_message(json.dumps(payload))

        try:
            self._execute_with_backoff(_send, operation_name="send_dead_letter")
            logger.info(
                "Message %s moved to dead-letter queue '%s'",
                getattr(message, "id", "<unknown>"),
                self.config.dead_letter_queue_name,
            )
        except AzureError:
            logger.exception(
                "Failed to send message %s to dead-letter queue '%s'",
                getattr(message, "id", "<unknown>"),
                self.config.dead_letter_queue_name,
            )

    def _parse_message(self, message: QueueMessage) -> Dict[str, Any]:
        try:
            payload = json.loads(message.content)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive programming
            raise PoisonMessageError("Message content is not valid JSON") from exc

        if not isinstance(payload, dict):
            raise PoisonMessageError("Queue message payload must be a JSON object")

        tickers = payload.get("tickers")
        if not tickers or not isinstance(tickers, Iterable) or isinstance(tickers, (str, bytes)):
            raise PoisonMessageError("Queue message is missing a list of 'tickers'")
        tickers = [ticker.strip() for ticker in tickers if str(ticker).strip()]
        if not tickers:
            raise PoisonMessageError("Queue message included an empty ticker list")

        analysis_window = payload.get("analysis_window") or {}
        if not isinstance(analysis_window, dict):
            raise PoisonMessageError("'analysis_window' must be a JSON object with start/end dates")

        start_date = analysis_window.get("start") or analysis_window.get("start_date")
        end_date = analysis_window.get("end") or analysis_window.get("end_date")
        if not (start_date and end_date):
            raise PoisonMessageError("'analysis_window' must contain 'start'/'end' or 'start_date'/'end_date'")

        overrides = payload.get("overrides") or {}
        if overrides and not isinstance(overrides, dict):
            raise PoisonMessageError("'overrides' must be a JSON object when provided")

        return {
            "tickers": tickers,
            "start_date": start_date,
            "end_date": end_date,
            "overrides": overrides,
            "raw": payload,
        }

    def _process_with_retries(self, message: QueueMessage, payload: Dict[str, Any]) -> None:
        attempt = 0
        while True:
            attempt += 1
            try:
                self._process_message(message, payload)
                return
            except PoisonMessageError:
                raise
            except self.RETRYABLE_EXCEPTIONS as exc:
                if attempt >= self.config.max_attempts:
                    logger.error(
                        "Exceeded retry limit (%s) for message %s due to transient error: %s",
                        self.config.max_attempts,
                        message.id,
                        exc,
                    )
                    raise
                delay = self._compute_backoff(attempt)
                logger.warning(
                    "Transient error processing message %s (attempt %s/%s): %s. Retrying in %.2fs",
                    message.id,
                    attempt,
                    self.config.max_attempts,
                    exc,
                    delay,
                )
                time.sleep(delay)
            except Exception:
                raise

    def _process_message(self, message: QueueMessage, payload: Dict[str, Any]) -> None:
        portfolio_snapshot = self.repository.get_latest_portfolio_snapshot()
        if not portfolio_snapshot:
            raise RuntimeError("No portfolio snapshot available in Cosmos DB")

        portfolio_data = portfolio_snapshot.get("portfolio") if isinstance(portfolio_snapshot, dict) else None
        if portfolio_data is None:
            raise RuntimeError("Portfolio snapshot payload is missing the 'portfolio' field")

        overrides = payload.get("overrides", {})
        run_kwargs = {
            "tickers": payload["tickers"],
            "start_date": payload["start_date"],
            "end_date": payload["end_date"],
            "portfolio": portfolio_data,
            "show_reasoning": bool(overrides.get("show_reasoning", False)),
            "selected_analysts": overrides.get("selected_analysts", []) or [],
            "model_name": overrides.get("model_name", "gpt-4.1"),
            "model_provider": overrides.get("model_provider", "OpenAI"),
        }

        hedge_result = run_hedge_fund(**run_kwargs)
        processed_at = datetime.now(timezone.utc).isoformat()

        result_record = {
            "id": message.id,
            "messageId": message.id,
            "tickers": payload["tickers"],
            "analysisWindow": {
                "start": payload["start_date"],
                "end": payload["end_date"],
            },
            "portfolioSnapshotId": portfolio_snapshot.get("id"),
            "decisions": hedge_result.get("decisions"),
            "analystSignals": hedge_result.get("analyst_signals"),
            "processedAt": processed_at,
            "metadata": {
                "rawMessage": payload["raw"],
            },
        }
        self.repository.save_run_result(message.id, result_record)

        summary = self._summarise_decisions(hedge_result.get("decisions"))
        status_payload = {
            "id": message.id,
            "messageId": message.id,
            "status": "completed",
            "summary": summary,
            "tickers": payload["tickers"],
            "processedAt": processed_at,
        }
        self.repository.publish_status(message.id, status_payload)

    def _compute_backoff(self, attempt: int) -> float:
        capped_attempt = max(0, attempt - 1)
        delay = self.config.base_backoff_seconds * (2**capped_attempt)
        delay = min(delay, self.config.max_backoff_seconds)
        jitter = random.uniform(0, self.config.base_backoff_seconds)
        return delay + jitter

    def _summarise_decisions(self, decisions: Optional[Dict[str, Any]]) -> str:
        if not decisions or not isinstance(decisions, dict):
            return "Decisions recorded for tickers." if decisions else "No decisions produced."

        summaries: list[str] = []
        for ticker, decision in decisions.items():
            if isinstance(decision, dict):
                action = decision.get("action") or decision.get("recommendation") or "decision"
                summaries.append(f"{ticker}:{action}")
            else:
                summaries.append(f"{ticker}:{decision}")
        return ", ".join(summaries) if summaries else "Decisions recorded for tickers."

    def _execute_with_backoff(
        self,
        func,
        *,
        operation_name: str,
        suppress_errors: bool = False,
    ):
        attempt = 0
        while True:
            attempt += 1
            try:
                return func()
            except self.RETRYABLE_EXCEPTIONS as exc:
                if attempt >= self.config.max_attempts:
                    if suppress_errors:
                        logger.warning(
                            "Operation %s failed after %s attempts: %s",
                            operation_name,
                            attempt,
                            exc,
                        )
                        return None
                    raise
                delay = self._compute_backoff(attempt)
                logger.debug(
                    "Retryable error during %s (attempt %s/%s): %s. Sleeping %.2fs",
                    operation_name,
                    attempt,
                    self.config.max_attempts,
                    exc,
                    delay,
                )
                time.sleep(delay)
            except Exception:
                if suppress_errors:
                    logger.exception("Non-retryable error during %s", operation_name)
                    return None
                raise


def main() -> None:
    """Entry point for running the queue worker as a module."""

    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        stream=sys.stdout,
    )

    worker = QueueWorker.from_environment()
    worker.run()


if __name__ == "__main__":
    main()
