from __future__ import annotations

from .portfolio import Portfolio
from .types import ActionLiteral, Action


class TradeExecutor:
    """Executes trades against a Portfolio with Backtester-identical semantics."""

    def __init__(self, long_only: bool = False) -> None:
        """Initialize TradeExecutor.

        Args:
            long_only: If True, disable short selling and covering operations.
        """
        self._long_only = long_only

    def execute_trade(
        self,
        ticker: str,
        action: ActionLiteral,
        quantity: float,
        current_price: float,
        portfolio: Portfolio,
    ) -> int:
        if quantity is None or quantity <= 0:
            return 0

        # Coerce to enum if strings provided
        try:
            action_enum = Action(action) if not isinstance(action, Action) else action
        except Exception:
            action_enum = Action.HOLD

        if action_enum == Action.BUY:
            return portfolio.apply_long_buy(ticker, int(quantity), float(current_price))
        if action_enum == Action.SELL:
            return portfolio.apply_long_sell(ticker, int(quantity), float(current_price))
        if action_enum == Action.SHORT:
            if self._long_only:
                # Block short selling in long-only mode
                return 0
            return portfolio.apply_short_open(ticker, int(quantity), float(current_price))
        if action_enum == Action.COVER:
            if self._long_only:
                # Block covering in long-only mode
                return 0
            return portfolio.apply_short_cover(ticker, int(quantity), float(current_price))

        # hold or unknown action
        return 0


