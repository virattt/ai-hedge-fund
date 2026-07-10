"""Trading schedule strategy — heavy LLM at open, light rule-based refresh, triggers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

from dotenv import load_dotenv

load_dotenv()

CycleKind = Literal["heavy", "light", "triggered_heavy"]

# Rule-based analysts — no LLM calls (see src/utils/analysts.py).
LIGHT_ANALYSTS: tuple[str, ...] = (
    "technical_analyst",
    "fundamentals_analyst",
    "valuation_analyst",
    "growth_analyst",
    "sentiment_analyst",
)

# Default heavy panel — LLM personas + key rule-based anchors.
DEFAULT_HEAVY_ANALYSTS: tuple[str, ...] = (
    "warren_buffett",
    "charlie_munger",
    "aswath_damodaran",
    "michael_burry",
    "valuation_analyst",
    "fundamentals_analyst",
    "technical_analyst",
)


def _parse_csv(value: str | None, default: tuple[str, ...]) -> tuple[str, ...]:
    if not value or not value.strip():
        return default
    return tuple(item.strip() for item in value.split(",") if item.strip())


@dataclass(frozen=True)
class SchedulerConfig:
    """Daemon configuration loaded from environment."""

    heavy_model_name: str
    heavy_model_provider: str
    heavy_analysts: tuple[str, ...]
    light_analysts: tuple[str, ...]
    light_interval_minutes: int
    open_delay_minutes: int
    price_swing_pct: float
    spy_move_pct: float
    trigger_cooldown_minutes: int
    news_lookback_hours: int
    session_dir: str

    @property
    def open_time_et(self) -> tuple[int, int]:
        """Market open 9:30 ET plus configured delay."""
        base_minutes = 9 * 60 + 30 + self.open_delay_minutes
        return base_minutes // 60, base_minutes % 60


def load_scheduler_config() -> SchedulerConfig:
    return SchedulerConfig(
        heavy_model_name=os.getenv("SCHEDULER_HEAVY_MODEL", "gpt-4.1"),
        heavy_model_provider=os.getenv("SCHEDULER_HEAVY_PROVIDER", "OpenAI"),
        heavy_analysts=_parse_csv(os.getenv("SCHEDULER_HEAVY_ANALYSTS"), DEFAULT_HEAVY_ANALYSTS),
        light_analysts=_parse_csv(os.getenv("SCHEDULER_LIGHT_ANALYSTS"), LIGHT_ANALYSTS),
        light_interval_minutes=int(os.getenv("SCHEDULER_LIGHT_INTERVAL_MIN", "5")),
        open_delay_minutes=int(os.getenv("SCHEDULER_OPEN_DELAY_MIN", "5")),
        price_swing_pct=float(os.getenv("SCHEDULER_PRICE_SWING_PCT", "2.0")),
        spy_move_pct=float(os.getenv("SCHEDULER_SPY_MOVE_PCT", "1.0")),
        trigger_cooldown_minutes=int(os.getenv("SCHEDULER_TRIGGER_COOLDOWN_MIN", "30")),
        news_lookback_hours=int(os.getenv("SCHEDULER_NEWS_LOOKBACK_HOURS", "24")),
        session_dir=os.getenv("SCHEDULER_SESSION_DIR", "data/scheduler"),
    )
