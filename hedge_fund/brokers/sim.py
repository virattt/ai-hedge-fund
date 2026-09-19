"""SimBroker — deterministic simulated broker for backtests.

Fills every order completely, exactly at the order's reference price. That
determinism is the point: given the same orders, a backtest replays to the
same book. Commissions are charged inside place_order, where they change
fills without touching the pipeline; slippage stays a future addition in the
same place.

Margin is not modeled: cash may go negative and stays visible. With an
unlevered mandate (gross_target <= 1), sells-before-buys ordering, and
floor-toward-zero sizing, a long book won't get there — but nothing here
pretends to enforce it.
"""

from __future__ import annotations

from hedge_fund.brokers.models import Commission, Fill, Order, Position


class SimBroker:
    """In-memory broker: signed positions carrying a weighted-average cost
    basis, plus a cash balance."""

    def __init__(self, cash: float, commission: Commission | None = None) -> None:
        self._cash = cash
        self._shares: dict[str, int] = {}
        self._basis: dict[str, float] = {}
        self._realized = 0.0
        self._commission = commission or Commission()

    def positions(self) -> dict[str, Position]:
        return {
            t: Position(ticker=t, shares=s, cost_basis=self._basis.get(t, 0.0))
            for t, s in self._shares.items()
            if s != 0
        }

    def cash(self) -> float:
        return self._cash

    def realized_pnl(self) -> float:
        """Cumulative realized P&L, gross of commission.

        Commission is booked as a cash expense rather than folded into basis
        or netted out here, so "what the position earned" and "what trading it
        cost" stay separable instead of arriving pre-mixed.
        """
        return self._realized

    def place_order(self, order: Order) -> Fill:
        if order.price <= 0:
            raise ValueError(
                f"cannot fill {order.ticker} at price {order.price} — "
                "the caller must price every order"
            )

        signed = order.quantity if order.side == "buy" else -order.quantity
        old = self._shares.get(order.ticker, 0)
        basis = self._basis.get(order.ticker, 0.0)
        new = old + signed

        realized = 0.0
        if old == 0 or (old > 0) == (signed > 0):
            # Opening, or adding in the direction already held: blend this fill
            # into the average. Nothing closes, so nothing realizes.
            basis = (abs(old) * basis + order.quantity * order.price) / abs(new)
        elif order.quantity <= abs(old):
            # Reducing, or closing exactly. The shares that left realize against
            # the basis; whatever remains keeps it, because an exit says nothing
            # about what the rest was bought for.
            realized = self._close(old, order.quantity, basis, order.price)
        else:
            # Crossing zero: one order closes the whole position and opens the
            # opposite one. Only the closed shares realize, and the new position
            # starts from this fill's price — carrying the old basis across would
            # price a short off shares the book no longer holds.
            realized = self._close(old, abs(old), basis, order.price)
            basis = order.price

        commission = self._commission.charge(order.quantity)
        self._cash += -signed * order.price - commission
        self._realized += realized

        if new == 0:
            self._shares.pop(order.ticker, None)
            self._basis.pop(order.ticker, None)
        else:
            self._shares[order.ticker] = new
            self._basis[order.ticker] = basis

        return Fill(
            ticker=order.ticker,
            side=order.side,
            quantity=order.quantity,
            price=order.price,
            commission=commission,
            realized_pnl=realized,
        )

    @staticmethod
    def _close(old: int, quantity: int, basis: float, price: float) -> float:
        """P&L on `quantity` shares leaving a position of signed size `old`.

        A long earns the rise above its basis, a short the fall below it — the
        only place in this class where the sign of the position changes the
        arithmetic rather than just the bookkeeping.
        """
        return quantity * (price - basis) if old > 0 else quantity * (basis - price)
