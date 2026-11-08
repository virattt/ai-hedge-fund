"""Pipeline records — the serialized truth of every decision and execution.

A DecisionRecord is an assessment: what the analysts saw, what they said,
and how views became validated target weights. A CycleRecord is that
decision executed: what risk clamped, what was ordered and filled, and what
the book looks like after. `hedge_fund.pipeline.session.SessionRecord` wraps
both into the per-session unit the ledger persists.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_serializer

from hedge_fund.brokers.models import Fill, Order
from hedge_fund.fund.spec import FundSpec
from hedge_fund.models import Signal
from hedge_fund.portfolio.construction import FlatReason
from hedge_fund.risk.exposures import Exposures
from hedge_fund.risk.limits import ClampEvent


class TickerSkip(BaseModel):
    """A requested name that could not be traded this cycle, and why."""

    ticker: str
    reason: str


class StrategyRecord(BaseModel):
    """One strategy's slice of a cycle: its analysts' views and its sleeve."""

    name: str
    slice: float                        # normalized capital slice of the fund
    signals: list[Signal]               # this strategy's analysts x tradeable tickers
    convictions: dict[str, float]       # blended views, pre-scaling
    weights: dict[str, float]           # the sleeve, before netting across strategies
    eligible_scores: dict[str, float] = Field(default_factory=dict)
    flat_reason: FlatReason | None = None
    final_contribution: dict[str, float] = Field(default_factory=dict)  # fraction of fund equity


class Allocated(BaseModel):
    """One weight the allocator set: the mandate's number, the evidence it
    was judged on, and the weight the decision used."""

    mandate: float
    t_stat: float | None                # None when nothing was graded
    n: int                              # graded dates (analyst) or periods (strategy)
    weight: float                       # mandate x multiplier


class AllocationRecord(BaseModel):
    """What the scorecard made of the mandate's weights at one session:
    every strategy's capital slice and, inside it, every model's blend
    weight. The decision carries the one it was made with."""

    as_of: str
    strategies: dict[str, Allocated]
    models: dict[str, dict[str, Allocated]]   # strategy -> model -> weight


class DecisionRecord(BaseModel):
    """An auditable assessment, without orders or broker accounting."""

    schema_version: Literal[2] = 2
    fund: str
    as_of: str
    spec: FundSpec
    universe: list[str]
    marks: dict[str, float]
    skipped: list[TickerSkip]
    strategies: list[StrategyRecord]
    target_weights: dict[str, float]
    clamps: list[ClampEvent]
    final_weights: dict[str, float]
    risk_scale_factor: float | None = None
    allocation: AllocationRecord | None = None
    drawdown: float | None = None       # fall from the NAV peak, when the mandate has a halving tier
    exposures: Exposures | None = None  # the factor model the clamps were measured with

    @model_serializer(mode="wrap")
    def _serialize(self, handler):
        """A decision made without an allocator, a halving tier, or a factor
        limit serializes exactly as every decision did before they existed:
        it sits inside a hashed record."""
        data = handler(self)
        for name in ("allocation", "drawdown", "exposures"):
            if getattr(self, name) is None:
                data.pop(name, None)
        return data

    @property
    def is_stopped_out(self) -> bool:
        """A drawdown stop-out: every target is zero and no analyst was asked."""
        return any(c.limit == "max_drawdown_pct" for c in self.clamps)

    @property
    def is_halved(self) -> bool:
        """The halving tier fired: the book runs at half size until it recovers."""
        return any(c.limit == "halve_drawdown_pct" for c in self.clamps)


class CycleRecord(BaseModel):
    """One tick of the fund, fully serialized — every stage's inputs and
    outputs. `model_dump_json()` round-trips; nothing about a decision
    lives anywhere else."""

    schema_version: Literal[2] = 2
    fund: str
    as_of: str
    spec: FundSpec                      # self-contained audit copy
    universe: list[str]                 # the tickers this cycle was asked to trade
    marks: dict[str, float]             # ticker -> close used for sizing and NAV
    skipped: list[TickerSkip]
    strategies: list[StrategyRecord]    # every sleeve, incl. each thesis
    target_weights: dict[str, float]    # the NETTED book, pre-risk
    clamps: list[ClampEvent]
    final_weights: dict[str, float]     # post-risk
    equity_before: float
    cash_before: float
    orders: list[Order]
    fills: list[Fill]
    positions: dict[str, int]           # signed shares after fills
    cash: float
    nav: float                          # cash + sum(shares * mark)
    risk_scale_factor: float | None = None
    original_assessment: DecisionRecord | None = None
    refreshed_assessment: DecisionRecord | None = None
    execution_as_of: str | None = None
    execution_policy: Literal["next_close", "next_bar"] | None = None
    allocation: AllocationRecord | None = None
    drawdown: float | None = None
    exposures: Exposures | None = None

    @model_serializer(mode="wrap")
    def _serialize(self, handler):
        data = handler(self)
        for name in ("allocation", "drawdown", "exposures"):
            if getattr(self, name) is None:
                data.pop(name, None)
        return data

    @property
    def traded_notional(self) -> float:
        """Dollars that changed hands at the fill prices, both sides added."""
        return sum(f.quantity * f.price for f in self.fills)

    @property
    def slippage(self) -> float:
        """What the fills cost against the reference marks: a buy filled above
        its mark and a sell filled below both count as a positive cost."""
        return sum(
            (fill.price - order.price) * fill.quantity * (1 if fill.side == "buy" else -1)
            for order, fill in zip(self.orders, self.fills)
        )

    @property
    def spread_cost(self) -> float:
        """The half-spread the mandate's cost model charges on these orders,
        at their marks: the part of the slippage the spread explains."""
        return sum(o.quantity * o.price * self.spec.costs.spread_bps / 10_000 for o in self.orders)

    @property
    def impact(self) -> float:
        """The slippage beyond the modelled spread: market impact on a
        simulated fill; on a live broker, whatever the venue did beyond it."""
        return self.slippage - self.spread_cost

    @property
    def commission(self) -> float:
        """The cash the fills do not explain. Derived from the book, not from
        the mandate's cost model, so a record filled free reports zero and a
        live broker's real fees land here without a schema change."""
        signed_notional = sum(
            f.quantity * f.price * (1 if f.side == "buy" else -1) for f in self.fills
        )
        return self.cash_before - self.cash - signed_notional

    @property
    def trading_cost(self) -> float:
        return self.slippage + self.commission
