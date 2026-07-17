"""Pipeline records — the serialized truth of every cycle.

A CycleRecord captures one tick of the fund end to end: what the analysts
saw, what they said, how views became weights, what risk clamped, what was
ordered and filled, and what the book looks like after. The ledger persists
these; `fund why AAPL` will answer from them alone.
"""

from __future__ import annotations

from pydantic import BaseModel

from v2.brokers.models import Fill, Order
from v2.fund.spec import FundSpec
from v2.models import Signal
from v2.risk.limits import ClampEvent


class TickerSkip(BaseModel):
    """A universe name that could not be traded this cycle, and why."""

    ticker: str
    reason: str


class CycleRecord(BaseModel):
    """One tick of the fund, fully serialized — every stage's inputs and
    outputs. `model_dump_json()` round-trips; nothing about a decision
    lives anywhere else."""

    fund: str
    as_of: str
    spec: FundSpec                      # self-contained audit copy
    marks: dict[str, float]             # ticker -> close used for sizing and NAV
    skipped: list[TickerSkip]
    signals: list[Signal]               # every analyst x tradeable ticker, incl. reasoning
    convictions: dict[str, float]       # blended views, pre-scaling
    target_weights: dict[str, float]    # post-blend, pre-risk
    clamps: list[ClampEvent]
    final_weights: dict[str, float]     # post-risk
    equity_before: float
    cash_before: float
    orders: list[Order]
    fills: list[Fill]
    positions: dict[str, int]           # signed shares after fills
    cash: float
    nav: float                          # cash + sum(shares * mark)
