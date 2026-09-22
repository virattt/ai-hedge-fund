"""PaperBroker — paper venue for live-clock runs.

Accepts orders, fills them at the caller's mark (or later, at a delayed
mark), and keeps the same cash / signed-share book SimBroker does. It is
not a backtest clock and not a live exchange: there is no historical
replay here, and nothing is sent to a real venue.

place_order is the Broker-protocol path used by run_cycle: open and fill
at mark in one step so the pipeline stays unchanged. Delayed fills use
open_order, then fill (optionally at a new mark) or cancel.
"""

from __future__ import annotations

from hedge_fund.brokers.models import Fill, Order, Position


class PaperBroker:
    """In-memory paper book: signed positions, cash, and open tickets.

    A live-clock run may seed *positions* from a prior CycleRecord so the
    book carries between process invocations. Fills never hit a live venue.
    """

    venue = "paper"

    def __init__(
        self,
        cash: float,
        positions: dict[str, int] | None = None,
    ) -> None:
        self._cash = cash
        self._shares: dict[str, int] = {
            ticker: shares
            for ticker, shares in (positions or {}).items()
            if shares != 0
        }
        self._open: dict[str, Order] = {}
        self._filled: set[str] = set()
        self._cancelled: set[str] = set()
        self._next_id = 1

    def positions(self) -> dict[str, Position]:
        return {
            t: Position(ticker=t, shares=s)
            for t, s in self._shares.items()
            if s != 0
        }

    def cash(self) -> float:
        return self._cash

    def open_orders(self) -> dict[str, Order]:
        """Currently open tickets. A copy; mutations do not touch the book."""
        return {oid: order.model_copy() for oid, order in self._open.items()}

    def open_order(self, order: Order) -> str:
        """Accept *order* without filling. Returns the ticket id.

        The order is copied onto the book. A non-positive mark is rejected
        here — the caller must price every ticket, same as place_order.
        """
        self._require_price(order)
        oid = str(self._next_id)
        self._next_id += 1
        self._open[oid] = order.model_copy()
        return oid

    def fill(self, order_id: str, price: float | None = None) -> Fill:
        """Fill an open ticket at its mark, or at *price* if given.

        A delayed fill passes the later mark as *price*. The ticket must
        still be open — filled or cancelled ids raise.
        """
        order = self._take_open(order_id, action="fill")
        fill_price = order.price if price is None else price
        if fill_price <= 0:
            # Put the ticket back so a bad delayed mark does not drop it.
            self._open[order_id] = order
            self._filled.discard(order_id)
            raise ValueError(
                f"cannot fill {order.ticker} at price {fill_price} — "
                "the caller must price every order"
            )
        return self._apply(order.ticker, order.side, order.quantity, fill_price)

    def cancel(self, order_id: str) -> None:
        """Drop an open ticket. Cash and positions are unchanged."""
        self._take_open(order_id, action="cancel")
        self._cancelled.add(order_id)

    def place_order(self, order: Order) -> Fill:
        """Broker protocol: open and fill at the order's mark immediately."""
        oid = self.open_order(order)
        return self.fill(oid)

    def _take_open(self, order_id: str, *, action: str) -> Order:
        order = self._open.pop(order_id, None)
        if order is not None:
            if action == "fill":
                self._filled.add(order_id)
            return order
        if order_id in self._filled:
            raise ValueError(f"cannot {action} {order_id}: already filled")
        if order_id in self._cancelled:
            raise ValueError(f"cannot {action} {order_id}: already cancelled")
        raise ValueError(f"cannot {action} {order_id}: unknown order")

    def _require_price(self, order: Order) -> None:
        if order.price <= 0:
            raise ValueError(
                f"cannot fill {order.ticker} at price {order.price} — "
                "the caller must price every order"
            )

    def _apply(self, ticker: str, side: str, quantity: int, price: float) -> Fill:
        if side == "buy":
            self._shares[ticker] = self._shares.get(ticker, 0) + quantity
            self._cash -= quantity * price
        else:
            self._shares[ticker] = self._shares.get(ticker, 0) - quantity
            self._cash += quantity * price

        if self._shares[ticker] == 0:
            del self._shares[ticker]

        return Fill(ticker=ticker, side=side, quantity=quantity, price=price)
