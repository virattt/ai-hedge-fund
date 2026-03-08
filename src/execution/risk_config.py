"""Configuration for the pre-trade risk engine."""

from dataclasses import dataclass


@dataclass
class RiskConfig:
    """Pre-trade risk limits. Reject orders that violate these before they reach the broker."""

    max_position_pct: float = 0.15  # 15% max per ticker
    max_daily_loss_pct: float = 0.03  # 3% daily drawdown limit
    max_single_order_usd: float = 10_000.0  # $10k max per order
    max_leverage: float = 2.0  # 2x max leverage (for Hyperliquid)
    max_sector_pct: float = 0.40  # 40% max per sector
    circuit_breaker_failures: int = 3  # pause after N consecutive failures
    circuit_breaker_cooldown_s: int = 300  # 5 minute cooldown
