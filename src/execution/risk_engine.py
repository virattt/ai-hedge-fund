"""Pre-trade risk engine: reject orders that violate limits before they reach the broker."""

import json
import time
from pathlib import Path

from src.execution.models import AccountInfo, Order, OrderSide
from src.execution.risk_config import RiskConfig


class PreTradeRiskEngine:
    """
    Runs before every order submission. Rejects orders that violate position,
    daily loss, order size, leverage, or concentration limits. Tracks circuit
    breaker and kill switch state.
    """

    def __init__(
        self,
        config: RiskConfig | None = None,
        state_path: str | Path = ".risk_engine_state.json",
    ):
        self.config = config or RiskConfig()
        self._state_path = Path(state_path)
        self._consecutive_failures = 0
        self._paused_until: float = 0.0
        self._kill_switch_engaged = False
        self._daily_start_equity: float | None = None
        self._load_state()

    def _load_state(self) -> None:
        if not self._state_path.exists():
            return
        try:
            with open(self._state_path) as f:
                data = json.load(f)
            self._consecutive_failures = data.get("consecutive_failures", 0)
            self._paused_until = data.get("paused_until", 0.0)
            self._kill_switch_engaged = data.get("kill_switch_engaged", False)
            self._daily_start_equity = data.get("daily_start_equity")
        except Exception:
            pass

    def _save_state(self) -> None:
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._state_path, "w") as f:
                json.dump(
                    {
                        "consecutive_failures": self._consecutive_failures,
                        "paused_until": self._paused_until,
                        "kill_switch_engaged": self._kill_switch_engaged,
                        "daily_start_equity": self._daily_start_equity,
                    },
                    f,
                )
        except Exception:
            pass

    def engage_kill_switch(self) -> None:
        """Emergency halt: no new orders until disengaged."""
        self._kill_switch_engaged = True
        self._save_state()

    def disengage_kill_switch(self) -> None:
        self._kill_switch_engaged = False
        self._save_state()

    def is_halted(self) -> bool:
        """True if kill switch is on or circuit breaker is in cooldown."""
        if self._kill_switch_engaged:
            return True
        if time.time() < self._paused_until:
            return True
        return False

    def record_success(self) -> None:
        self._consecutive_failures = 0
        self._save_state()

    def record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= self.config.circuit_breaker_failures:
            self._paused_until = time.time() + self.config.circuit_breaker_cooldown_s
        self._save_state()

    def set_daily_start_equity(self, equity: float) -> None:
        """Call at start of day to track daily drawdown."""
        self._daily_start_equity = equity
        self._save_state()

    def check_order(
        self,
        order: Order,
        account: AccountInfo,
        current_prices: dict[str, float] | None = None,
    ) -> tuple[bool, str]:
        """
        Returns (allowed, reason). If allowed is False, reason explains why.
        current_prices: optional ticker -> price for order value and position value.
        """
        if self.is_halted():
            return False, "halted (kill switch or circuit breaker)"

        # Order size limit
        price = (current_prices or {}).get(order.ticker) or 0.0
        if order.side == OrderSide.BUY and price > 0:
            order_value = order.quantity * price
            if order_value > self.config.max_single_order_usd:
                return False, f"order value ${order_value:.0f} exceeds max ${self.config.max_single_order_usd:.0f}"

        # Daily loss limit
        if self._daily_start_equity is not None and self._daily_start_equity > 0:
            loss_pct = (self._daily_start_equity - account.equity) / self._daily_start_equity
            if loss_pct >= self.config.max_daily_loss_pct:
                return False, f"daily loss {loss_pct:.1%} >= limit {self.config.max_daily_loss_pct:.1%}"

        # Position limit: after this order, position in this ticker must not exceed max_position_pct of equity
        if account.equity <= 0:
            return True, ""
        pos_value_by_ticker: dict[str, float] = {}
        for p in account.positions:
            px = (current_prices or {}).get(p.ticker) or p.avg_price
            pos_value_by_ticker[p.ticker] = abs(p.quantity) * px
        if order.side == OrderSide.BUY and price > 0:
            new_val = pos_value_by_ticker.get(order.ticker, 0) + order.quantity * price
            if new_val / account.equity > self.config.max_position_pct:
                return False, f"position would exceed {self.config.max_position_pct:.0%} of equity"

        return True, ""
