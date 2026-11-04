"""Broker data models — positions, orders, fills.

Two order verbs, not four: positions are signed share counts, so "short" is
just selling past zero and "cover" is buying back toward it. Long/short
labeling is a display concern, not an execution one.
"""

from __future__ import annotations

from typing import Literal, NamedTuple

from pydantic import BaseModel, Field, model_serializer


class Position(BaseModel):
    """Signed share count in one ticker. Negative = short."""

    ticker: str
    shares: int


class Liquidity(NamedTuple):
    """A name's liquidity as the engine saw it: 20-day average daily volume
    in shares, and the daily sigma of its log returns over the same bars."""

    adv: float
    volatility: float


class Order(BaseModel):
    """An instruction to trade. `price` is the reference price the caller
    computed (the as-of close): SimBroker fills around it, a live broker
    fills at its own quote — the Fill always carries the truth.

    `adv` and `volatility` are the name's liquidity as the engine saw it:
    20-day average daily volume in shares, and the daily sigma over the
    same bars. The cost model prices impact from them. Either is None when
    the engine had no bars for the name; then the order pays no impact."""

    ticker: str
    side: Literal["buy", "sell"]
    quantity: int = Field(gt=0)
    price: float
    adv: float | None = None
    volatility: float | None = None

    @property
    def participation(self) -> float:
        """The order's share of the name's average daily volume."""
        if not self.adv:
            return 0.0
        return self.quantity / self.adv

    @model_serializer(mode="wrap")
    def _serialize(self, handler):
        """An order without liquidity serializes exactly as every order did
        before the fields existed: each one sits inside a hash-chained
        ledger record."""
        data = handler(self)
        for field in ("adv", "volatility"):
            if getattr(self, field) is None:
                data.pop(field, None)
        return data


class Fill(BaseModel):
    """An executed order at its actual fill price."""

    ticker: str
    side: Literal["buy", "sell"]
    quantity: int
    price: float
