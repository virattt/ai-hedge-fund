"""Trading costs — what a fill costs beyond the price on the tape.

A real shop splits the cost of a trade into three parts: the commission
per share, half the bid-ask spread paid on every side, and market impact
that grows with order size against the name's daily volume. This model
carries the first two. Impact needs average daily volume at every session
and is a later addition.

Defaults are a liquid US large/mid cap traded by a small fund: 5 bps of
half-spread per side and $0.005 a share (Interactive Brokers' fixed
rate). There is no minimum per order. Zero on both means free fills.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TradingCosts(BaseModel):
    """The cost model a mandate names in its `costs:` block."""

    model_config = ConfigDict(extra="forbid")

    spread_bps: float = Field(
        default=5.0, ge=0, description="half the bid-ask spread, in basis points, paid on every side"
    )
    commission_per_share: float = Field(
        default=0.005, ge=0, description="broker commission per share, in dollars"
    )

    def fill_price(self, side: Literal["buy", "sell"], mark: float) -> float:
        """A buy pays the half-spread above *mark*; a sell receives it below.
        A short is a sell and a cover is a buy, so the same two lines hold."""
        spread = mark * self.spread_bps / 10_000
        return mark + spread if side == "buy" else mark - spread

    def commission(self, quantity: int) -> float:
        return quantity * self.commission_per_share
