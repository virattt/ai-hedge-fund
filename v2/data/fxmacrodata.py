"""FXMacroData client for macro release-calendar context."""

from __future__ import annotations

import os
from typing import Any

import httpx


class FXMacroDataClientError(Exception):
    """An FXMacroData request failed."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        path: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.path = path


class FXMacroDataClient:
    """Client for FXMacroData macroeconomic and central-bank release events."""

    BASE_URL = "https://fxmacrodata.com/api/v1"

    def __init__(
        self,
        api_key: str | None = None,
        timeout: float = 30.0,
        base_url: str | None = None,
    ) -> None:
        self._api_key = api_key or os.environ.get("FXMACRODATA_API_KEY", "")
        self._timeout = timeout
        self._client = httpx.Client(timeout=timeout)
        self._base_url = (base_url or self.BASE_URL).rstrip("/")

    def __enter__(self) -> FXMacroDataClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def get_release_calendar(
        self,
        currency: str = "usd",
        *,
        limit: int = 100,
        min_tier: int | None = None,
    ) -> list[dict[str, Any]]:
        """Return release-calendar rows for one currency."""
        rows = self._get(
            f"/calendar/{currency.lower()}",
            params={"limit": max(1, int(limit))},
        ).get("data", [])
        if min_tier is not None:
            rows = [
                row
                for row in rows
                if int(row.get("market_tier") or 99) <= int(min_tier)
            ]
        return rows[: max(1, int(limit))]

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        if self._api_key:
            params = {**params, "api_key": self._api_key}
        try:
            response = self._client.get(f"{self._base_url}{path}", params=params)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise FXMacroDataClientError(
                f"GET {path} failed: HTTP {exc.response.status_code}",
                status_code=exc.response.status_code,
                path=path,
            ) from exc
        except httpx.HTTPError as exc:
            raise FXMacroDataClientError(f"GET {path} failed: {exc}", path=path) from exc
        return response.json()
