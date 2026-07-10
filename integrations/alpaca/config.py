"""Alpaca configuration and safety gates."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class AlpacaConfig:
    api_key: str
    secret_key: str
    paper: bool
    live_trading_enabled: bool
    kill_switch: bool
    max_order_notional: float
    allowed_tickers: frozenset[str] | None
    margin_requirement: float

    @property
    def execution_enabled(self) -> bool:
        return self.live_trading_enabled and not self.kill_switch

    @property
    def mode_label(self) -> str:
        if self.kill_switch:
            return "KILL SWITCH"
        if not self.live_trading_enabled:
            return "read-only"
        return "paper" if self.paper else "LIVE"


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_allowed_tickers(value: str | None) -> frozenset[str] | None:
    if not value or not value.strip():
        return None
    return frozenset(t.strip().upper() for t in value.split(",") if t.strip())


def load_alpaca_config(*, execute: bool = False) -> AlpacaConfig:
    api_key = os.getenv("ALPACA_API_KEY", "").strip()
    secret_key = os.getenv("ALPACA_SECRET_KEY", "").strip()

    if not api_key or not secret_key:
        raise ValueError(
            "ALPACA_API_KEY and ALPACA_SECRET_KEY must be set in your .env file. "
            "Get paper keys from https://app.alpaca.markets/"
        )

    env_execution = _parse_bool(os.getenv("LIVE_TRADING_ENABLED"), default=False)
    return AlpacaConfig(
        api_key=api_key,
        secret_key=secret_key,
        paper=_parse_bool(os.getenv("ALPACA_PAPER"), default=True),
        live_trading_enabled=env_execution or execute,
        kill_switch=_parse_bool(os.getenv("TRADING_KILL_SWITCH"), default=False),
        max_order_notional=float(os.getenv("MAX_ORDER_NOTIONAL", "5000")),
        allowed_tickers=_parse_allowed_tickers(os.getenv("ALLOWED_TICKERS")),
        margin_requirement=float(os.getenv("MARGIN_REQUIREMENT", "0.5")),
    )
