"""Pipeline records — the serialized truth of every cycle.

A CycleRecord captures one tick of the fund end to end: what the analysts
saw, what they said, how views became weights, what risk clamped, what was
ordered and filled, and what the book looks like after. The ledger persists
these; `fund why AAPL` will answer from them alone.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from hedge_fund.brokers.models import Fill, Order
from hedge_fund.fund.spec import FundSpec
from hedge_fund.models import Signal
from hedge_fund.portfolio.construction import FlatReason
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


class PendingRunResult(BaseModel):
    """A saved proposal awaiting an explicit run with completed session data."""

    schema_version: Literal[2] = 2
    status: Literal["pending"] = "pending"
    execution_policy: Literal["next_close"] = "next_close"
    fund: str
    as_of: str
    proposal: DecisionRecord
    reason: str
    scheduled_execution_date: str | None = None


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
    execution_policy: Literal["next_close"] | None = None
