"""Broker data models — positions, orders, fills.

Two order verbs, not four: positions are signed share counts, so "short" is
just selling past zero and "cover" is buying back toward it. Long/short
labeling is a display concern, not an execution one.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Commission(BaseModel):
    """What a fill costs to execute: a per-ticket charge plus a per-share rate,
    the two shapes real schedules actually combine.

    Both default to zero, so a broker nobody configured prices exactly as it
    did before commissions existed — an existing backtest replays to the same
    book, to the cent, rather than quietly drifting.
    """

    per_trade: float = 0.0
    per_share: float = 0.0

    def charge(self, quantity: int) -> float:
        return self.per_trade + self.per_share * quantity


class Position(BaseModel):
    """Signed share count in one ticker. Negative = short.

    `cost_basis` is the weighted-average entry price and stays positive on
    both sides: the sign already lives in `shares`, and carrying it twice
    would only create a way for the two to disagree. It defaults to zero so a
    caller that builds a Position from shares alone still works.
    """

    ticker: str
    shares: int
    cost_basis: float = 0.0


class Order(BaseModel):
    """An instruction to trade. `price` is the reference price the caller
    computed (the as-of close): SimBroker fills exactly there, a live broker
    fills at its own quote — the Fill always carries the truth."""

    ticker: str
    side: Literal["buy", "sell"]
    quantity: int = Field(gt=0)
    price: float


class Fill(BaseModel):
    """An executed order at its actual fill price.

    `commission` and `realized_pnl` ride along because the Fill is what the
    caller keeps. Re-deriving either afterwards would mean reconstructing the
    basis the broker already held at fill time — and after a crossing order
    that basis is gone.
    """

    ticker: str
    side: Literal["buy", "sell"]
    quantity: int
    price: float
    commission: float = 0.0
    realized_pnl: float = 0.0
