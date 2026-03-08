"""File-based cache with TTL. Survives restarts. Uses .cache/ directory."""

import hashlib
import json
import os
import time
from pathlib import Path

# TTL seconds per data type
TTL_PRICES = 86400  # 1 day
TTL_FINANCIAL_METRICS = 604800  # 1 week
TTL_NEWS = 14400  # 4 hours
TTL_INSIDER_TRADES = 86400  # 1 day
TTL_LINE_ITEMS = 604800  # 1 week


def _safe_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()[:32]


class FileCache:
    """Persistent cache with TTL. Same interface as Cache for drop-in use."""

    def __init__(self, cache_dir: str | Path = ".cache"):
        self._root = Path(cache_dir)
        self._root.mkdir(parents=True, exist_ok=True)
        self._prices_dir = self._root / "prices"
        self._financial_metrics_dir = self._root / "financial_metrics"
        self._line_items_dir = self._root / "line_items"
        self._insider_trades_dir = self._root / "insider_trades"
        self._company_news_dir = self._root / "company_news"
        for d in (
            self._prices_dir,
            self._financial_metrics_dir,
            self._line_items_dir,
            self._insider_trades_dir,
            self._company_news_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)

    def _read(self, path: Path, ttl: int) -> list[dict] | None:
        if not path.exists():
            return None
        try:
            with open(path) as f:
                obj = json.load(f)
            expires = obj.get("expires", 0)
            if time.time() > expires:
                return None
            return obj.get("data")
        except Exception:
            return None

    def _write(self, path: Path, data: list[dict], ttl: int) -> None:
        try:
            with open(path, "w") as f:
                json.dump({"data": data, "expires": time.time() + ttl}, f)
        except Exception:
            pass

    def _merge_data(
        self,
        existing: list[dict] | None,
        new_data: list[dict],
        key_field: str,
    ) -> list[dict]:
        if not existing:
            return new_data
        existing_keys = {item.get(key_field) for item in existing}
        merged = existing.copy()
        merged.extend([i for i in new_data if i.get(key_field) not in existing_keys])
        return merged

    def get_prices(self, key: str) -> list[dict] | None:
        path = self._prices_dir / f"{_safe_key(key)}.json"
        return self._read(path, TTL_PRICES)

    def set_prices(self, key: str, data: list[dict]) -> None:
        path = self._prices_dir / f"{_safe_key(key)}.json"
        existing = self._read(path, TTL_PRICES)
        merged = self._merge_data(existing, data, "time")
        self._write(path, merged, TTL_PRICES)

    def get_financial_metrics(self, key: str) -> list[dict] | None:
        path = self._financial_metrics_dir / f"{_safe_key(key)}.json"
        return self._read(path, TTL_FINANCIAL_METRICS)

    def set_financial_metrics(self, key: str, data: list[dict]) -> None:
        path = self._financial_metrics_dir / f"{_safe_key(key)}.json"
        existing = self._read(path, TTL_FINANCIAL_METRICS)
        merged = self._merge_data(existing, data, "report_period")
        self._write(path, merged, TTL_FINANCIAL_METRICS)

    def get_line_items(self, key: str) -> list[dict] | None:
        path = self._line_items_dir / f"{_safe_key(key)}.json"
        return self._read(path, TTL_LINE_ITEMS)

    def set_line_items(self, key: str, data: list[dict]) -> None:
        path = self._line_items_dir / f"{_safe_key(key)}.json"
        existing = self._read(path, TTL_LINE_ITEMS)
        merged = self._merge_data(existing, data, "report_period")
        self._write(path, merged, TTL_LINE_ITEMS)

    def get_insider_trades(self, key: str) -> list[dict] | None:
        path = self._insider_trades_dir / f"{_safe_key(key)}.json"
        return self._read(path, TTL_INSIDER_TRADES)

    def set_insider_trades(self, key: str, data: list[dict]) -> None:
        path = self._insider_trades_dir / f"{_safe_key(key)}.json"
        existing = self._read(path, TTL_INSIDER_TRADES)
        merged = self._merge_data(existing, data, "filing_date")
        self._write(path, merged, TTL_INSIDER_TRADES)

    def get_company_news(self, key: str) -> list[dict] | None:
        path = self._company_news_dir / f"{_safe_key(key)}.json"
        return self._read(path, TTL_NEWS)

    def set_company_news(self, key: str, data: list[dict]) -> None:
        path = self._company_news_dir / f"{_safe_key(key)}.json"
        existing = self._read(path, TTL_NEWS)
        merged = self._merge_data(existing, data, "date")
        self._write(path, merged, TTL_NEWS)
