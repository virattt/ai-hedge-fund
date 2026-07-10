"""Algorithmic market signals for the watch loop — no LLM, no Finnhub."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Literal

from integrations.alpaca.market_hours import now_et
from integrations.alpaca.price_feed import PriceSnapshot
from integrations.alpaca.session import TradingSessionState
from integrations.alpaca.strategy import SchedulerConfig

logger = logging.getLogger(__name__)

PromoteLevel = Literal["none", "light", "heavy"]


@dataclass
class WatchEvaluation:
    """Result of one watch-tick algorithmic scan."""

    promote: PromoteLevel = "none"
    alerts: list[str] = field(default_factory=list)
    heavy_alerts: list[str] = field(default_factory=list)
    # Symbols that fired, tracked per escalation level. A triggered heavy
    # cycle analyzes only heavy_symbols (plus holdings) — light-level tick
    # moves must NOT drag dozens of names into an expensive LLM cycle.
    heavy_symbols: list[str] = field(default_factory=list)
    light_symbols: list[str] = field(default_factory=list)
    snapshots: dict[str, PriceSnapshot] = field(default_factory=dict)
    metrics: dict[str, dict[str, float]] = field(default_factory=dict)

    def add_alert(self, message: str, *, level: PromoteLevel = "none", symbol: str | None = None) -> None:
        self.alerts.append(message)
        if level == "heavy":
            self.heavy_alerts.append(message)
        if symbol:
            self.add_symbol(symbol, level=level)
        if level == "heavy":
            self.promote = "heavy"
        elif level == "light" and self.promote != "heavy":
            self.promote = "light"

    def add_symbol(self, symbol: str, *, level: PromoteLevel) -> None:
        target = self.heavy_symbols if level == "heavy" else self.light_symbols
        sym = symbol.upper()
        if level != "none" and sym not in target:
            target.append(sym)


class MarketSignalEngine:
    """
    Pure price/math signals that decide when to escalate to light or heavy cycles.

    Watch loop (cheap): batch Alpaca snapshots only.
    Light cycle (medium): rule-based analysts + Finnhub.
    Heavy cycle (expensive): LLM panel.
    """

    def __init__(self, config: SchedulerConfig) -> None:
        self._config = config

    def evaluate(
        self,
        tickers: list[str],
        session: TradingSessionState,
        snapshots: dict[str, PriceSnapshot],
    ) -> WatchEvaluation:
        result = WatchEvaluation(snapshots=dict(snapshots))

        if not session.heavy_open_completed:
            return result

        spy = snapshots.get("SPY")
        if spy and session.spy_open_price and session.spy_open_price > 0:
            spy_move = abs(spy.price - session.spy_open_price) / session.spy_open_price * 100
            result.metrics["SPY"] = {
                "price": spy.price,
                "vs_open_pct": spy_move,
            }
            if spy_move >= self._config.spy_move_pct:
                result.add_alert(
                    f"SPY {spy_move:+.2f}% vs session open (${session.spy_open_price:.2f} → ${spy.price:.2f})",
                    level="heavy",
                )

        last_watch = session.last_watch_prices or {}

        for ticker in tickers:
            sym = ticker.upper()
            snap = snapshots.get(sym)
            if snap is None:
                continue

            metrics: dict[str, float] = {"price": snap.price}
            ref = session.open_reference_prices.get(sym)
            if ref and ref > 0:
                vs_open = (snap.price - ref) / ref * 100
                metrics["vs_open_pct"] = vs_open
                if abs(vs_open) >= self._config.price_swing_pct:
                    result.add_alert(
                        f"{sym} {vs_open:+.2f}% vs open (${ref:.2f} → ${snap.price:.2f})",
                        level="heavy",
                        symbol=sym,
                    )

            prev = last_watch.get(sym)
            if prev and prev > 0:
                vs_tick = (snap.price - prev) / prev * 100
                metrics["vs_last_watch_pct"] = vs_tick
                if abs(vs_tick) >= self._config.watch_tick_move_pct:
                    result.add_alert(
                        f"{sym} {vs_tick:+.2f}% since last watch (${prev:.2f} → ${snap.price:.2f})",
                        level="light",
                        symbol=sym,
                    )

            momentum = self._momentum(session, sym, snap.price)
            if momentum is not None:
                metrics["momentum_pct"] = momentum
                if abs(momentum) >= self._config.watch_momentum_pct:
                    result.add_alert(
                        f"{sym} momentum {momentum:+.2f}% over last {self._config.watch_momentum_ticks} ticks",
                        level="light",
                        symbol=sym,
                    )

            result.metrics[sym] = metrics

        if result.promote == "heavy" and self._heavy_cooldown_active(session):
            result.promote = "light" if result.alerts else "none"
            for sym in result.heavy_symbols:
                if sym not in result.light_symbols:
                    result.light_symbols.append(sym)
            result.heavy_symbols.clear()
            result.heavy_alerts.clear()
            result.alerts.append("(heavy cooldown — downgraded to light/none)")

        return result

    def _momentum(self, session: TradingSessionState, ticker: str, price: float) -> float | None:
        history = session.watch_price_history.get(ticker, [])
        if len(history) < 2:
            return None
        lookback = history[-self._config.watch_momentum_ticks :]
        if not lookback or lookback[0] <= 0:
            return None
        return (price - lookback[0]) / lookback[0] * 100

    def _heavy_cooldown_active(self, session: TradingSessionState) -> bool:
        last = session.last_trigger_at or session.last_heavy_at
        if not last:
            return False
        try:
            last_dt = datetime.fromisoformat(last)
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=now_et().tzinfo)
            elapsed = now_et() - last_dt.astimezone(now_et().tzinfo)
            return elapsed < timedelta(minutes=self._config.trigger_cooldown_minutes)
        except (TypeError, ValueError):
            return False

    def should_check_news(self, session: TradingSessionState) -> bool:
        if not session.last_news_check_at:
            return True
        try:
            last = datetime.fromisoformat(session.last_news_check_at)
            if last.tzinfo is None:
                last = last.replace(tzinfo=now_et().tzinfo)
            elapsed = now_et() - last.astimezone(now_et().tzinfo)
            return elapsed >= timedelta(minutes=self._config.news_check_interval_minutes)
        except (TypeError, ValueError):
            return True
