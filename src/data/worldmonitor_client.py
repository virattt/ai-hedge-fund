"""
World Monitor API client (Phase 0 scaffold).

This module is intentionally standalone and non-invasive:
- It does not alter any trading or backtesting flows by itself.
- It provides a thin, retry-aware client wrapper for future integration.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

import requests


@dataclass(frozen=True)
class WorldMonitorConfig:
    base_url: str = os.getenv("WORLDMONITOR_API_BASE_URL", "https://api.worldmonitor.app")
    api_key: str | None = os.getenv("WORLDMONITOR_API_KEY")
    timeout_seconds: int = int(os.getenv("WORLDMONITOR_TIMEOUT_SECONDS", "12"))
    max_retries: int = int(os.getenv("WORLDMONITOR_MAX_RETRIES", "2"))
    backoff_seconds: float = float(os.getenv("WORLDMONITOR_BACKOFF_SECONDS", "0.75"))


class WorldMonitorClient:
    def __init__(self, config: WorldMonitorConfig | None = None):
        self.config = config or WorldMonitorConfig()

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers

    def get_json(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Execute a GET request and parse JSON with basic retries.

        Raises:
            requests.HTTPError: non-success status after retries
            requests.RequestException: transport errors after retries
            ValueError: non-JSON body on success
        """
        if not path.startswith("/"):
            path = f"/{path}"
        url = f"{self.config.base_url}{path}"

        last_exc: Exception | None = None
        attempts = max(1, self.config.max_retries + 1)

        for attempt in range(1, attempts + 1):
            try:
                resp = requests.get(
                    url,
                    params=params,
                    headers=self._headers(),
                    timeout=self.config.timeout_seconds,
                )
                if resp.status_code >= 500 and attempt < attempts:
                    time.sleep(self.config.backoff_seconds * attempt)
                    continue
                resp.raise_for_status()
                return resp.json()
            except (requests.RequestException, ValueError) as exc:
                last_exc = exc
                if attempt >= attempts:
                    break
                time.sleep(self.config.backoff_seconds * attempt)

        if last_exc:
            raise last_exc
        raise RuntimeError("WorldMonitorClient failed without explicit exception.")

