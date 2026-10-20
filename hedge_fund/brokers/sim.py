"""SimBroker — deterministic simulated broker for backtests.

Fills every order completely: at the order's reference price, moved against the
order by any declared slippage, with any declared commission taken out of cash.
Both default to zero, and at zero the book is exactly the reference prices — that
determinism is the point: given the same orders, a backtest replays to the same
book. Costs live here, inside place_order, so they change fills without touching
the pipeline.

Margin is not modeled: cash may go negative and stays visible. With an
unlevered mandate (gross_target <= 1), sells-before-buys ordering, and
floor-toward-zero sizing, a long book won't get there — but nothing here
pretends to enforce it.
"""

from __future__ import annotations

from math import isfinite

from hedge_fund.brokers.models import Fill, Order, Position


class SimBroker:
    """In-memory broker: signed positions plus a cash balance."""

    def __init__(
        self,
        cash: float,
        commission_bps: float = 0.0,
        slippage_bps: float = 0.0,
    ) -> None:
        """Costs are charged on every fill and quoted in basis points; both are
        zero by default, and at zero the book is the reference prices exactly.

        Slippage moves the fill against the order and lands in `Fill.price`;
        commission is a fee on notional that leaves cash but never touches the
        price, so a fill stays comparable across a backtest.
        """
        for name, value in (("commission_bps", commission_bps), ("slippage_bps", slippage_bps)):
            if not isfinite(value) or value < 0:
                raise ValueError(f"{name} must be a finite, non-negative number")
        if slippage_bps >= 10_000:
            # A sell at >= 100% slippage would fill at a zero or negative price;
            # the book would take it, because only the reference price is checked.
            raise ValueError("slippage_bps must stay under 10000 — no fill prices at or below zero")
        self._cash = cash
        self._commission_bps = commission_bps
        self._slippage_bps = slippage_bps
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

        if order.side == "buy":
            fill_price = order.price * (1 + self._slippage_bps / 10_000)
        else:
            fill_price = order.price * (1 - self._slippage_bps / 10_000)
        notional = order.quantity * fill_price
        fee = notional * self._commission_bps / 10_000

        if order.side == "buy":
            self._shares[order.ticker] = self._shares.get(order.ticker, 0) + order.quantity
            self._cash -= notional + fee
        else:
            self._shares[order.ticker] = self._shares.get(order.ticker, 0) - order.quantity
            self._cash += notional - fee

        if self._shares[order.ticker] == 0:
            del self._shares[order.ticker]

        return Fill(
            ticker=order.ticker,
            side=order.side,
            quantity=order.quantity,
            price=fill_price,
        )
