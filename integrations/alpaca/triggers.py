"""Event triggers that promote a light session to a heavy LLM re-analysis."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from integrations.alpaca.market_hours import now_et
from integrations.alpaca.session import TradingSessionState
from integrations.alpaca.strategy import SchedulerConfig
from src.tools.api import get_company_news, get_prices

logger = logging.getLogger(__name__)


@dataclass
class TriggerEvaluation:
    fired: bool = False
    reasons: list[str] = field(default_factory=list)

    def add(self, reason: str) -> None:
        self.fired = True
        self.reasons.append(reason)


class TriggerMonitor:
    """Detect price swings, benchmark moves, and fresh news."""

    def __init__(self, config: SchedulerConfig) -> None:
        self._config = config

    def evaluate(self, tickers: list[str], session: TradingSessionState) -> TriggerEvaluation:
        result = TriggerEvaluation()
        if not session.open_reference_prices:
            return result

        if self._in_cooldown(session):
            return result

        self._check_price_swings(tickers, session, result)
        self._check_spy_move(session, result)
        self._check_news(tickers, session, result)
        return result

    def _in_cooldown(self, session: TradingSessionState) -> bool:
        if not session.last_trigger_at and not session.last_heavy_at:
            return False
        last = session.last_trigger_at or session.last_heavy_at
        try:
            last_dt = datetime.fromisoformat(last)
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=now_et().tzinfo)
            elapsed = now_et() - last_dt.astimezone(now_et().tzinfo)
            return elapsed < timedelta(minutes=self._config.trigger_cooldown_minutes)
        except (TypeError, ValueError):
            return False

    def _check_price_swings(
        self,
        tickers: list[str],
        session: TradingSessionState,
        result: TriggerEvaluation,
    ) -> None:
        threshold = self._config.price_swing_pct / 100.0
        end = now_et().date().isoformat()
        start = (now_et().date() - timedelta(days=5)).isoformat()

        for ticker in tickers:
            ref = session.open_reference_prices.get(ticker.upper())
            if not ref or ref <= 0:
                continue
            prices = get_prices(ticker, start, end)
            if not prices:
                continue
            current = float(prices[-1].close)
            move = abs(current - ref) / ref
            if move >= threshold:
                result.add(
                    f"{ticker.upper()} moved {move * 100:.1f}% vs open reference "
                    f"(${ref:.2f} → ${current:.2f})"
                )

    def _check_spy_move(self, session: TradingSessionState, result: TriggerEvaluation) -> None:
        if session.spy_open_price is None or session.spy_open_price <= 0:
            return
        threshold = self._config.spy_move_pct / 100.0
        end = now_et().date().isoformat()
        start = (now_et().date() - timedelta(days=5)).isoformat()
        prices = get_prices("SPY", start, end)
        if not prices:
            return
        current = float(prices[-1].close)
        move = abs(current - session.spy_open_price) / session.spy_open_price
        if move >= threshold:
            result.add(
                f"SPY moved {move * 100:.1f}% vs session open "
                f"(${session.spy_open_price:.2f} → ${current:.2f})"
            )

    def _check_news(
        self,
        tickers: list[str],
        session: TradingSessionState,
        result: TriggerEvaluation,
    ) -> None:
        end = now_et().date().isoformat()
        start = (now_et() - timedelta(hours=self._config.news_lookback_hours)).date().isoformat()
        seen = set(session.seen_news_keys)
        new_keys: list[str] = []

        for ticker in tickers:
            try:
                articles = get_company_news(ticker, end, start_date=start, limit=20) or []
            except Exception as exc:
                logger.debug("News fetch failed for %s: %s", ticker, exc)
                continue
            for article in articles:
                key = f"{ticker.upper()}|{article.date}|{article.title}"
                if key not in seen:
                    new_keys.append(key)
                    result.add(f"New headline for {ticker.upper()}: {article.title[:80]}")

        if new_keys:
            session.mark_news_check(new_keys)
