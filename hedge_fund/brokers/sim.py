"""SimBroker — deterministic simulated broker for backtests.

Fills every order completely. With a cost model, the fill price sits half a
spread away from the order's reference price and the commission comes out
of cash; without one, the fill is exactly at the reference price. Either
way the fill is deterministic: given the same orders, a backtest replays to
the same book.

Margin is not modeled: cash may go negative and stays visible. With an
unlevered mandate (gross_target <= 1), sells-before-buys ordering, and
floor-toward-zero sizing, a long book rarely gets there — the spread and
commission can take it a few dollars below zero when the share-rounding
dust is small — but nothing here pretends to enforce it.
"""

from __future__ import annotations

from math import isfinite

from hedge_fund.brokers.costs import TradingCosts
from hedge_fund.brokers.models import Fill, Order, Position


class SimBroker:
    """In-memory broker: signed positions plus a cash balance. *costs* is
    the mandate's cost model; None fills free, at the reference price."""

    def __init__(self, cash: float, costs: TradingCosts | None = None) -> None:
        self._cash = cash
        self._costs = costs
        self._shares: dict[str, int] = {}

    def positions(self) -> dict[str, Position]:
        return {
            t: Position(ticker=t, shares=s)
            for t, s in self._shares.items()
            if s != 0
        }

    def cash(self) -> float:
        return self._cash

    def place_order(self, order: Order) -> Fill:
        if not isfinite(order.price) or order.price <= 0:
            raise ValueError(
                f"cannot fill {order.ticker} at price {order.price} — "
                "the caller must price every order"
            )

        price = order.price if self._costs is None else self._costs.fill_price(order.side, order.price)
        commission = 0.0 if self._costs is None else self._costs.commission(order.quantity)

        if order.side == "buy":
            self._shares[order.ticker] = self._shares.get(order.ticker, 0) + order.quantity
            self._cash -= order.quantity * price + commission
        else:
            self._shares[order.ticker] = self._shares.get(order.ticker, 0) - order.quantity
            self._cash += order.quantity * price - commission

        if self._shares[order.ticker] == 0:
            del self._shares[order.ticker]

        return Fill(
            ticker=order.ticker,
            side=order.side,
            quantity=order.quantity,
            price=price,
        )
