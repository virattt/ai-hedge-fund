"""Hard execution guardrails applied to every order before submission.

Motivated by the first trading days' reports: the system churned 4-15x
equity per day in whipsaw round trips. The governor enforces portfolio-level
limits that individual cycles cannot see:

- daily turnover cap (notional submitted / equity)
- daily fill-count cap
- per-symbol cooldown between risk-increasing trades
- max open-position count
- intraday drawdown breaker (drawdown => risk-reducing orders only)
- minimum conviction for triggered-heavy entries

Risk-reducing orders (closing/trimming an existing position) are never
vetoed — the governor must not trap the book in a losing state.

State persists per trading day in the scheduler session dir, so restarts
and multiple entry points (daemon, CLI runs) share the same budgets.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from integrations.broker.models import OrderResult, TradeOrder

logger = logging.getLogger(__name__)

_RISK_INCREASING = {"buy", "short"}


@dataclass(frozen=True)
class RiskGovernorConfig:
    enabled: bool = True
    max_turnover_x: float = 1.0
    max_fills_per_day: int = 40
    symbol_cooldown_minutes: int = 60
    max_open_positions: int = 15
    max_intraday_drawdown_pct: float = 0.5
    min_triggered_heavy_confidence: float = 70.0
    state_dir: str = "data/scheduler"


def load_risk_config() -> RiskGovernorConfig:
    return RiskGovernorConfig(
        enabled=os.getenv("RISK_GOVERNOR_ENABLED", "true").strip().lower() in ("1", "true", "yes"),
        max_turnover_x=float(os.getenv("RISK_MAX_TURNOVER_X", "1.0")),
        max_fills_per_day=int(os.getenv("RISK_MAX_FILLS_PER_DAY", "40")),
        symbol_cooldown_minutes=int(os.getenv("RISK_SYMBOL_COOLDOWN_MIN", "60")),
        max_open_positions=int(os.getenv("RISK_MAX_OPEN_POSITIONS", "15")),
        max_intraday_drawdown_pct=float(os.getenv("RISK_MAX_INTRADAY_DRAWDOWN_PCT", "0.5")),
        min_triggered_heavy_confidence=float(os.getenv("RISK_MIN_TRIGGERED_CONFIDENCE", "70")),
        state_dir=os.getenv("SCHEDULER_SESSION_DIR", "data/scheduler"),
    )


@dataclass
class RiskDayState:
    trading_day: str
    day_open_equity: float | None = None
    notional_submitted: float = 0.0
    fills_submitted: int = 0
    last_trade_at: dict[str, str] = field(default_factory=dict)


class RiskGovernor:
    """Stateful order filter shared by all cycles within a trading day."""

    def __init__(self, config: RiskGovernorConfig | None = None) -> None:
        from integrations.alpaca.market_hours import trading_date

        self._config = config or load_risk_config()
        self._day = trading_date().isoformat()
        self._path = Path(self._config.state_dir) / f"risk-{self._day}.json"
        self._state = self._load_state()

    def _load_state(self) -> RiskDayState:
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
                if data.get("trading_day") == self._day:
                    return RiskDayState(**data)
            except (OSError, json.JSONDecodeError, TypeError):
                logger.warning("Corrupt risk state at %s — starting fresh", self._path)
        return RiskDayState(trading_day=self._day)

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(asdict(self._state), indent=2), encoding="utf-8")

    # -- classification ----------------------------------------------------

    @staticmethod
    def _is_risk_reducing(order: TradeOrder, positions: dict[str, Any]) -> bool:
        """Sell against an existing long / cover against an existing short."""
        pos = positions.get(order.ticker.upper(), {})
        if order.action == "sell":
            return float(pos.get("long", 0)) > 0
        if order.action == "cover":
            return float(pos.get("short", 0)) > 0
        return False

    @staticmethod
    def _open_position_count(positions: dict[str, Any]) -> int:
        return sum(
            1
            for pos in positions.values()
            if float(pos.get("long", 0)) > 0 or float(pos.get("short", 0)) > 0
        )

    @staticmethod
    def _is_new_position(order: TradeOrder, positions: dict[str, Any]) -> bool:
        pos = positions.get(order.ticker.upper(), {})
        return float(pos.get("long", 0)) == 0 and float(pos.get("short", 0)) == 0

    def _in_cooldown(self, ticker: str, now: datetime) -> bool:
        last = self._state.last_trade_at.get(ticker.upper())
        if not last:
            return False
        try:
            last_dt = datetime.fromisoformat(last)
        except ValueError:
            return False
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=now.tzinfo)
        return (now - last_dt) < timedelta(minutes=self._config.symbol_cooldown_minutes)

    # -- filtering ---------------------------------------------------------

    def filter_orders(
        self,
        orders: list[TradeOrder],
        *,
        positions: dict[str, Any],
        equity: float | None,
        prices: dict[str, float],
        cycle_kind: str,
        decisions: dict[str, Any] | None = None,
    ) -> tuple[list[TradeOrder], list[OrderResult]]:
        """Split proposed orders into (allowed, vetoed-with-reasons)."""
        if not self._config.enabled:
            return orders, []

        from integrations.alpaca.market_hours import now_et

        now = now_et()
        cfg = self._config
        state = self._state
        if equity and state.day_open_equity is None:
            state.day_open_equity = float(equity)

        drawdown_active = False
        if equity and state.day_open_equity:
            dd_pct = (state.day_open_equity - equity) / state.day_open_equity * 100
            drawdown_active = dd_pct >= cfg.max_intraday_drawdown_pct

        open_count = self._open_position_count(positions)
        # Budget consumed by orders accepted earlier in this same cycle.
        pending_notional = 0.0
        pending_fills = 0
        pending_new_positions = 0

        allowed: list[TradeOrder] = []
        vetoed: list[OrderResult] = []

        def veto(order: TradeOrder, why: str) -> None:
            logger.info("Risk governor veto: %s %s %d — %s", order.action, order.ticker, order.quantity, why)
            vetoed.append(
                OrderResult(submitted=False, dry_run=True, order=order, message=f"Risk governor: {why}")
            )

        for order in orders:
            if order.action == "hold" or order.quantity <= 0:
                allowed.append(order)
                continue

            price = prices.get(order.ticker.upper(), 0.0)
            notional = order.quantity * price

            if self._is_risk_reducing(order, positions):
                # Exits/trims always pass; they still consume turnover budget.
                pending_notional += notional
                pending_fills += 1
                allowed.append(order)
                continue

            # Everything past here is risk-increasing (buy/short, or a
            # sell/cover with no position behind it).
            if drawdown_active:
                veto(
                    order,
                    f"intraday drawdown breaker active "
                    f"(≥{cfg.max_intraday_drawdown_pct}% below day-open equity) — reductions only",
                )
                continue

            if state.fills_submitted + pending_fills >= cfg.max_fills_per_day:
                veto(order, f"daily fill cap reached ({cfg.max_fills_per_day})")
                continue

            if equity and equity > 0:
                budget = cfg.max_turnover_x * equity
                if state.notional_submitted + pending_notional + notional > budget:
                    veto(
                        order,
                        f"daily turnover cap {cfg.max_turnover_x:.1f}x equity "
                        f"(${budget:,.0f}) would be exceeded",
                    )
                    continue

            if self._in_cooldown(order.ticker, now):
                veto(order, f"symbol cooldown ({cfg.symbol_cooldown_minutes}m since last trade)")
                continue

            if self._is_new_position(order, positions):
                if open_count + pending_new_positions >= cfg.max_open_positions:
                    veto(order, f"max open positions reached ({cfg.max_open_positions})")
                    continue

            if cycle_kind == "triggered_heavy":
                confidence = None
                if decisions and order.ticker in decisions:
                    confidence = decisions[order.ticker].get("confidence")
                elif decisions and order.ticker.upper() in decisions:
                    confidence = decisions[order.ticker.upper()].get("confidence")
                if confidence is not None and float(confidence) < cfg.min_triggered_heavy_confidence:
                    veto(
                        order,
                        f"triggered-heavy conviction {float(confidence):.0f} below "
                        f"minimum {cfg.min_triggered_heavy_confidence:.0f}",
                    )
                    continue

            pending_notional += notional
            pending_fills += 1
            if self._is_new_position(order, positions):
                pending_new_positions += 1
            allowed.append(order)

        return allowed, vetoed

    def record_submissions(self, results: list[OrderResult], prices: dict[str, float]) -> None:
        """Charge submitted orders against the day's budgets and persist."""
        from integrations.alpaca.market_hours import now_et

        now = now_et().isoformat()
        for result in results:
            if not result.submitted:
                continue
            order = result.order
            price = prices.get(order.ticker.upper(), 0.0)
            self._state.notional_submitted += order.quantity * price
            self._state.fills_submitted += 1
            self._state.last_trade_at[order.ticker.upper()] = now
        self.save()
