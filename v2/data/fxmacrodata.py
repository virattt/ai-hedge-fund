"""FXMacroData client for macro, FX, and event data."""

from __future__ import annotations

import os
from typing import Any

import httpx

FXMACRODATA_BASE_URL = "https://fxmacrodata.com/api/v1"
FXMACRODATA_API_KEY_ENV_VARS = ("FXMACRODATA_API_KEY", "FXMD_API_KEY")
FXMACRODATA_ENDPOINTS = {
    "data_catalogue": (
        "data_catalogue/{currency}",
        {"include_capabilities", "include_coverage", "indicator"},
    ),
    "announcements": (
        "announcements/{currency}/{indicator}",
        {
            "start_date",
            "end_date",
            "series_mode",
            "limit",
            "offset",
            "page",
            "seasonality",
            "frequency",
            "revisions",
            "basis",
            "official_only",
        },
    ),
    "latest_announcements": ("announcements/{currency}/latest", set()),
    "announcement_changes": (
        "announcements/changes",
        {"currencies", "indicators", "since", "limit", "payload"},
    ),
    "predictions": (
        "predictions/{currency}/{indicator}",
        {
            "prediction_type",
            "prediction_source",
            "start_date",
            "end_date",
            "limit",
            "offset",
            "page",
        },
    ),
    "calendar": (
        "calendar/{currency}",
        {"indicator", "start_date", "end_date", "timezone"},
    ),
    "forex": (
        "forex/{base}/{quote}",
        {"start_date", "end_date", "limit", "offset", "page", "indicators"},
    ),
    "cot": ("cot/{currency}", {"start_date", "end_date", "limit", "offset", "page"}),
    "commodity": (
        "commodities/{indicator}",
        {"start_date", "end_date", "limit", "offset", "page"},
    ),
    "commodities_latest": ("commodities/latest", set()),
    "curves": ("curves/{currency}", {"curve_family", "metric", "date"}),
    "curve_proxies": ("curve_proxies/{currency}", {"curve_family", "date"}),
    "forward_curves": ("forward_curves/{currency}", {"curve_family", "method", "date"}),
    "rate_differentials": (
        "rate_differentials/{base}/{quote}",
        {"measure", "start_date", "end_date", "limit", "offset"},
    ),
    "forward_differentials": (
        "forward_differentials/{base}/{quote}",
        {
            "curve_family",
            "start_tenor_years",
            "end_tenor_years",
            "start_date",
            "end_date",
            "limit",
            "offset",
        },
    ),
    "market_sessions": ("market_sessions", {"at"}),
    "risk_sentiment": ("risk_sentiment", {"start_date", "end_date", "limit", "offset"}),
    "news": ("news/{currency}", {"limit", "offset"}),
    "press_releases": ("press-releases/{currency}", {"limit", "offset"}),
}
ALIASES = {
    "catalogue": "data_catalogue",
    "macro": "announcements",
    "macro_indicators": "announcements",
    "release_calendar": "calendar",
    "fx": "forex",
    "fx_spot": "forex",
    "commodities": "commodity",
    "press-releases": "press_releases",
    "latest": "latest_announcements",
    "changes": "announcement_changes",
}


class FXMacroDataClientError(Exception):
    """An FXMacroData request failed."""

    def __init__(
        self, message: str, *, status_code: int | None = None, path: str | None = None
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.path = path


def _env_api_key() -> str:
    for name in FXMACRODATA_API_KEY_ENV_VARS:
        value = os.environ.get(name)
        if value:
            return value
    return ""


def _dataset_name(dataset: str) -> str:
    normalized = dataset.lower().replace("-", "_")
    return ALIASES.get(normalized, normalized)


def _clean(params: dict[str, Any] | None) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in (params or {}).items():
        if value is None:
            continue
        if isinstance(value, (list, tuple, set)):
            value = ",".join(str(item) for item in value)
        cleaned[key] = value
    return cleaned


def _format_path(path_template: str, kwargs: dict[str, Any]) -> str:
    values = {
        key: str(kwargs[key]).lower()
        for key in ("currency", "base", "quote")
        if key in kwargs
    }
    if "indicator" in kwargs:
        values["indicator"] = str(kwargs["indicator"])
    try:
        return path_template.format(**values)
    except KeyError as exc:
        raise ValueError(
            f"missing required FXMacroData parameter: {exc.args[0]}"
        ) from exc


def _rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        rows: list[dict[str, Any]] = []
        for key, value in sorted(data.items()):
            rows.append(
                {"indicator": key, **value}
                if isinstance(value, dict)
                else {"indicator": key, "value": value}
            )
        return rows
    return [payload]


class FXMacroDataClient:
    """Client for FXMacroData's public read/data endpoints."""

    def __init__(
        self,
        api_key: str | None = None,
        timeout: float = 30.0,
        base_url: str | None = None,
    ) -> None:
        self._api_key = api_key or _env_api_key()
        self._client = httpx.Client(timeout=timeout)
        self._base_url = (base_url or FXMACRODATA_BASE_URL).rstrip("/")

    def __enter__(self) -> "FXMacroDataClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def fetch_dataset(self, dataset: str, **kwargs: Any) -> dict[str, Any]:
        dataset = _dataset_name(dataset)
        if dataset not in FXMACRODATA_ENDPOINTS:
            raise ValueError(
                f"dataset must be one of {', '.join(sorted(FXMACRODATA_ENDPOINTS))}"
            )
        path_template, query_keys = FXMACRODATA_ENDPOINTS[dataset]
        query = _clean({key: kwargs.get(key) for key in query_keys})
        if self._api_key and "api_key" not in query:
            query["api_key"] = self._api_key
        path = _format_path(path_template, kwargs)
        try:
            response = self._client.get(
                f"{self._base_url}/{path.lstrip('/')}", params=query
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise FXMacroDataClientError(
                f"GET {path} failed: HTTP {exc.response.status_code}",
                status_code=exc.response.status_code,
                path=path,
            ) from exc
        except httpx.HTTPError as exc:
            raise FXMacroDataClientError(
                f"GET {path} failed: {exc}", path=path
            ) from exc
        return response.json()

    def rows(self, payload: Any) -> list[dict[str, Any]]:
        return _rows(payload)

    def graphql(
        self, query: str, variables: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        try:
            response = self._client.post(
                f"{self._base_url}/graphql",
                json={"query": query, "variables": variables or {}},
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise FXMacroDataClientError(
                f"POST graphql failed: HTTP {exc.response.status_code}",
                status_code=exc.response.status_code,
                path="graphql",
            ) from exc
        except httpx.HTTPError as exc:
            raise FXMacroDataClientError(
                f"POST graphql failed: {exc}", path="graphql"
            ) from exc
        return response.json()

    def data_catalogue(self, currency: str = "usd", **kwargs: Any) -> dict[str, Any]:
        return self.fetch_dataset("data_catalogue", currency=currency, **kwargs)

    def announcements(
        self, currency: str, indicator: str, **kwargs: Any
    ) -> dict[str, Any]:
        return self.fetch_dataset(
            "announcements", currency=currency, indicator=indicator, **kwargs
        )

    macro_indicators = announcements

    def latest_announcements(self, currency: str = "usd") -> dict[str, Any]:
        return self.fetch_dataset("latest_announcements", currency=currency)

    def announcement_changes(self, **kwargs: Any) -> dict[str, Any]:
        return self.fetch_dataset("announcement_changes", **kwargs)

    def predictions(
        self, currency: str, indicator: str, **kwargs: Any
    ) -> dict[str, Any]:
        return self.fetch_dataset(
            "predictions", currency=currency, indicator=indicator, **kwargs
        )

    def release_calendar(self, currency: str = "usd", **kwargs: Any) -> dict[str, Any]:
        return self.fetch_dataset("calendar", currency=currency, **kwargs)

    def release_calendar_rows(
        self,
        currency: str = "usd",
        limit: int = 20,
        min_tier: int | None = None,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        rows = self.rows(self.release_calendar(currency=currency, **kwargs))
        if min_tier is not None:
            rows = [
                row
                for row in rows
                if int(row.get("market_tier") or 99) <= int(min_tier)
            ]
        return rows[: max(1, int(limit))]

    def forex(self, base: str, quote: str, **kwargs: Any) -> dict[str, Any]:
        return self.fetch_dataset("forex", base=base, quote=quote, **kwargs)

    def cot(self, currency: str, **kwargs: Any) -> dict[str, Any]:
        return self.fetch_dataset("cot", currency=currency, **kwargs)

    def commodity(self, indicator: str, **kwargs: Any) -> dict[str, Any]:
        return self.fetch_dataset("commodity", indicator=indicator, **kwargs)

    commodities = commodity

    def commodities_latest(self) -> dict[str, Any]:
        return self.fetch_dataset("commodities_latest")

    def curves(self, currency: str, **kwargs: Any) -> dict[str, Any]:
        return self.fetch_dataset("curves", currency=currency, **kwargs)

    def curve_proxies(self, currency: str, **kwargs: Any) -> dict[str, Any]:
        return self.fetch_dataset("curve_proxies", currency=currency, **kwargs)

    def forward_curves(self, currency: str, **kwargs: Any) -> dict[str, Any]:
        return self.fetch_dataset("forward_curves", currency=currency, **kwargs)

    def rate_differentials(
        self, base: str, quote: str, **kwargs: Any
    ) -> dict[str, Any]:
        return self.fetch_dataset(
            "rate_differentials", base=base, quote=quote, **kwargs
        )

    def forward_differentials(
        self, base: str, quote: str, **kwargs: Any
    ) -> dict[str, Any]:
        return self.fetch_dataset(
            "forward_differentials", base=base, quote=quote, **kwargs
        )

    def market_sessions(self, **kwargs: Any) -> dict[str, Any]:
        return self.fetch_dataset("market_sessions", **kwargs)

    def risk_sentiment(self, **kwargs: Any) -> dict[str, Any]:
        return self.fetch_dataset("risk_sentiment", **kwargs)

    def news(self, currency: str, **kwargs: Any) -> dict[str, Any]:
        return self.fetch_dataset("news", currency=currency, **kwargs)

    def press_releases(self, currency: str, **kwargs: Any) -> dict[str, Any]:
        return self.fetch_dataset("press_releases", currency=currency, **kwargs)


def get_fxmacrodata_dataset(dataset: str, **kwargs: Any) -> dict[str, Any]:
    api_key = kwargs.pop("api_key", None)
    base_url = kwargs.pop("base_url", None)
    timeout = kwargs.pop("timeout", 30.0)
    with FXMacroDataClient(
        api_key=api_key, base_url=base_url, timeout=timeout
    ) as client:
        return client.fetch_dataset(dataset, **kwargs)


def get_release_calendar(
    currency: str = "usd",
    *,
    limit: int = 100,
    min_tier: int | None = None,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    with FXMacroDataClient(
        **{
            key: kwargs.pop(key)
            for key in list(kwargs)
            if key in {"api_key", "timeout", "base_url"}
        }
    ) as client:
        return client.release_calendar_rows(
            currency=currency, limit=limit, min_tier=min_tier, **kwargs
        )
