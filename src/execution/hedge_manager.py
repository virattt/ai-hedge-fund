"""Hedge manager: equity portfolio hedge via BTC/ETH short perps; funding rate monitor."""

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class HedgeConfig:
    """Config for when and how much to hedge."""

    capitulation_signal_threshold: float = 0.8  # regime score above this -> hedge
    max_hedge_pct_of_equity: float = 0.10  # max 10% of equity in short perp notional
    funding_rate_alert_threshold: float = 0.0001  # alert when |rate| > this
    hedge_coins: list[str] = None  # default BTC, ETH

    def __post_init__(self) -> None:
        if self.hedge_coins is None:
            self.hedge_coins = ["BTC", "ETH"]


class HedgeManager:
    """
    Monitors equity portfolio exposure. When regime detector signals capitulation,
    can open BTC/ETH short perps as a portfolio hedge. Also monitors funding
    rates and alerts when above threshold (arb opportunity).
    """

    def __init__(
        self,
        hyperliquid_broker: Any,
        config: HedgeConfig | None = None,
        alert_callback: Callable[[str, dict], None] | None = None,
    ):
        """hyperliquid_broker: must implement get_funding_rates() and order submission."""
        self._broker = hyperliquid_broker
        self._config = config or HedgeConfig()
        self._alert = alert_callback

    def _alert_fn(self, title: str, payload: dict[str, Any]) -> None:
        if self._alert:
            self._alert(title, payload)

    def get_funding_rates(self) -> dict[str, float]:
        """Current funding rates from Hyperliquid."""
        return self._broker.get_funding_rates()

    def check_funding_rates(self) -> None:
        """If any |funding rate| > threshold, fire alert."""
        rates = self.get_funding_rates()
        thresh = self._config.funding_rate_alert_threshold
        for coin, rate in rates.items():
            if abs(rate) >= thresh:
                self._alert_fn(
                    "funding_rate_alert",
                    {"coin": coin, "funding_rate": rate, "threshold": thresh},
                )

    def should_hedge(self, regime_capitulation_score: float) -> bool:
        """True if regime signals capitulation above threshold."""
        return regime_capitulation_score >= self._config.capitulation_signal_threshold

    def suggested_hedge_notional(
        self, equity_value: float, regime_capitulation_score: float
    ) -> float:
        """Suggested short notional (USD) for hedge, 0 if no hedge."""
        if not self.should_hedge(regime_capitulation_score):
            return 0.0
        return min(
            equity_value * self._config.max_hedge_pct_of_equity,
            equity_value * 0.10,
        )
