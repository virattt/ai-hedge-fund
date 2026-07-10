"""Shared scheduler config for tests."""

from __future__ import annotations

from integrations.alpaca.strategy import SchedulerConfig


def sample_scheduler_config(**overrides) -> SchedulerConfig:
    base = dict(
        heavy_model_name="gpt-5.5",
        heavy_model_provider="OpenAI",
        heavy_analysts=("warren_buffett",),
        light_analysts=("technical_analyst",),
        light_interval_minutes=5,
        open_delay_minutes=5,
        price_swing_pct=2.0,
        spy_move_pct=1.0,
        trigger_cooldown_minutes=30,
        news_lookback_hours=24,
        session_dir="data/scheduler",
        watch_interval_seconds=60,
        watch_tick_move_pct=0.75,
        watch_momentum_pct=1.5,
        watch_momentum_ticks=5,
        news_check_interval_minutes=5,
        light_promote_cooldown_minutes=3,
        alpaca_data_calls_per_minute=100,
        news_calls_per_minute=30,
    )
    base.update(overrides)
    return SchedulerConfig(**base)
