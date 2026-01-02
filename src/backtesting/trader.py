from __future__ import annotations

from .portfolio import Portfolio
from .types import ActionLiteral, Action


class TradeExecutor:
    """Executes trades against a Portfolio with Backtester-identical semantics."""

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
            return portfolio.apply_short_open(ticker, int(quantity), float(current_price))
        if action_enum == Action.COVER:
            return portfolio.apply_short_cover(ticker, int(quantity), float(current_price))

        # hold or unknown action
        return 0


