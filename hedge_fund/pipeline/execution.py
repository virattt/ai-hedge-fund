"""Execution — turn target weights into delta orders.

Targets are the complete statement of the desired book: any held name absent
from the targets has an implicit target of zero, so close orders fall out of
the same arithmetic as everything else. Pure function; the broker does the
filling.

Later: Almgren-Chriss optimal execution, fill probability.
"""

from __future__ import annotations

from hedge_fund.brokers.models import Liquidity, Order, Position


def build_orders(
    target_weights: dict[str, float],
    positions: dict[str, Position],
    marks: dict[str, float],
    equity: float,
    max_shares: dict[str, int] | None = None,
    min_notional: float = 0.0,
    liquidity: dict[str, Liquidity] | None = None,
) -> list[Order]:
    """Diff the target book against the broker's current book.

    Sizing: target_shares = int(weight * equity / mark) — floor toward zero,
    never overshoot the target; sub-share dust stays in cash and is
    re-evaluated next cycle. Orders below one share are not emitted.

    *min_notional* is the no-trade band: an add worth less than it is not
    worth the spread, so it waits and is re-targeted next cycle. A trim, a
    close or a flip always goes through, however small: it only moves the
    book toward a decision that already passed every limit, and a hard
    limit may be waiting on it. *max_shares* then caps an order's
    size per ticker (the volume cap); the rest of the move is re-targeted
    next cycle, the way a desk slices a large order over days. A cap below
    one share emits no order for that name. *liquidity* rides on each order
    so the broker can price its impact.

    Ordering: all sells first, then buys, alphabetical within each group —
    deterministic, and sells free the cash that buys consume within the
    same cycle.

    A KeyError on marks here means a pipeline bug upstream (execute_decision
    prices every tradeable and held name before calling this) — let it raise.
    """
    sells: list[Order] = []
    buys: list[Order] = []

    for ticker in sorted(set(target_weights) | set(positions)):
        mark = marks[ticker]
        target_shares = int(target_weights.get(ticker, 0.0) * equity / mark)
        current_shares = positions[ticker].shares if ticker in positions else 0
        delta = target_shares - current_shares
        adds = target_shares * current_shares >= 0 and abs(target_shares) > abs(current_shares)
        if adds and abs(delta) * mark < min_notional:
            continue
        if max_shares is not None and ticker in max_shares:
            delta = max(-max_shares[ticker], min(max_shares[ticker], delta))
        if delta == 0:
            continue
        name = liquidity.get(ticker) if liquidity is not None else None
        order = Order(
            ticker=ticker,
            side="buy" if delta > 0 else "sell",
            quantity=abs(delta),
            price=mark,
            adv=name.adv if name is not None else None,
            volatility=name.volatility if name is not None else None,
        )
        (buys if delta > 0 else sells).append(order)

    return sells + buys
