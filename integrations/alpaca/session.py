"""Persist per-trading-day scheduler state for idempotency and triggers."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from integrations.alpaca.market_hours import now_et, trading_date


@dataclass
class TradingSessionState:
    trading_day: str
    heavy_open_completed: bool = False
    last_heavy_at: str | None = None
    last_light_at: str | None = None
    last_trigger_at: str | None = None
    open_reference_prices: dict[str, float] = field(default_factory=dict)
    last_news_check_at: str | None = None
    seen_news_keys: list[str] = field(default_factory=list)
    spy_open_price: float | None = None
    last_watch_at: str | None = None
    last_watch_prices: dict[str, float] = field(default_factory=dict)
    watch_price_history: dict[str, list[float]] = field(default_factory=dict)
    # Rotating-batch analysis of speculative (non-held) tickers.
    batch_cursor: int = 0
    news_cursor: int = 0
    # Set when a heavy-open cycle is *attempted*, so a crash mid-cycle
    # (e.g. provider 429) doesn't retry in a hot loop.
    last_heavy_attempt_at: str | None = None
    # End-of-day performance reports generated for this trading day.
    eod_report_done: bool = False

    @classmethod
    def for_today(cls) -> TradingSessionState:
        return cls(trading_day=trading_date().isoformat())

    def mark_heavy(self, *, prices: dict[str, float], spy_price: float | None = None) -> None:
        self.heavy_open_completed = True
        self.last_heavy_at = now_et().isoformat()
        for key, value in prices.items():
            self.open_reference_prices[key.upper()] = float(value)
        if spy_price is not None:
            self.spy_open_price = float(spy_price)

    def mark_heavy_attempt(self) -> None:
        self.last_heavy_attempt_at = now_et().isoformat()

    def seed_open_references(self, prices: dict[str, float]) -> None:
        """First-seen watch prices become open references for tickers the
        heavy-open cycle didn't analyze (lazy universe rotation)."""
        for sym, price in prices.items():
            self.open_reference_prices.setdefault(sym.upper(), float(price))

    def mark_light(self) -> None:
        self.last_light_at = now_et().isoformat()

    def mark_trigger(self) -> None:
        self.last_trigger_at = now_et().isoformat()
        self.last_heavy_at = now_et().isoformat()

    def mark_news_check(self, keys: list[str]) -> None:
        self.last_news_check_at = now_et().isoformat()
        merged = set(self.seen_news_keys)
        merged.update(keys)
        self.seen_news_keys = sorted(merged)[-500:]

    def mark_watch(self, prices: dict[str, float], *, max_history: int = 30) -> None:
        self.last_watch_at = now_et().isoformat()
        self.last_watch_prices = {k.upper(): float(v) for k, v in prices.items()}
        history = dict(self.watch_price_history)
        for sym, price in self.last_watch_prices.items():
            ring = list(history.get(sym, []))
            ring.append(price)
            history[sym] = ring[-max_history:]
        self.watch_price_history = history


class SessionStore:
    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    def path_for(self, day: date) -> Path:
        return self._root / f"{day.isoformat()}.json"

    def load(self, day: date | None = None) -> TradingSessionState:
        day = day or trading_date()
        path = self.path_for(day)
        if not path.exists():
            return TradingSessionState(trading_day=day.isoformat())
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return TradingSessionState(**data)

    def save(self, state: TradingSessionState) -> Path:
        path = self.path_for(date.fromisoformat(state.trading_day))
        path.write_text(json.dumps(asdict(state), indent=2), encoding="utf-8")
        return path
