"""Risk limits — hard caps the analysts cannot override.

"Conviction requests, risk disposes": portfolio construction proposes target
weights, and this stage clamps them against the fund's limits. Everything
here is deterministic arithmetic — the LLM's influence over the book ends at
the Signal, and no clamp is ever negotiable.

Exposure removed by a clamp is NOT redistributed to other names; it stays in
cash. Redistributing would let the risk stage *increase* positions, which
inverts its job.

Three stages, each of which only shrinks: the per-name cap, the net cap (the
heavier side is scaled down until longs minus shorts sit at the band), then
the gross cap. The drawdown stop-out and the volume cap are limits on the
same model but act elsewhere: the stop-out in `advance`, where NAV is known,
and the volume cap in `execute_decision`, where orders are sized.
"""

from __future__ import annotations

from math import isfinite
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_serializer


class RiskLimits(BaseModel):
    """The fund's hard limits, set in its FundSpec."""

    model_config = ConfigDict(extra="forbid")

    max_position_pct: float = Field(
        gt=0, le=1.0, description="max |weight| per ticker, as a fraction of equity"
    )
    max_gross_exposure: float = Field(
        gt=0, description="max sum of |weights| across the book (1.0 = unlevered)"
    )
    max_net_exposure: float | None = Field(
        default=None, gt=0, description="max |longs minus shorts|; unset means no net band"
    )
    max_drawdown_pct: float | None = Field(
        default=None, gt=0, lt=1,
        description="NAV fall from its peak at which the fund is stopped out: sold to cash and kept there",
    )
    max_adv_pct: float | None = Field(
        default=None, gt=0, le=1,
        description="max order size as a share of the name's 20-day average daily volume",
    )

    @model_serializer(mode="wrap")
    def _serialize(self, handler):
        """A limit that is not set serializes as it did before the limit
        existed: every ledger record carries these inside its hash."""
        data = handler(self)
        for name in ("max_net_exposure", "max_drawdown_pct", "max_adv_pct"):
            if data.get(name) is None:
                data.pop(name, None)
        return data


class ClampEvent(BaseModel):
    """One limit firing — recorded so every clamp is explainable."""

    limit: Literal["max_position_pct", "max_gross_exposure", "max_net_exposure", "max_drawdown_pct", "max_adv_pct"]
    ticker: str | None = None  # None for a whole-book clamp
    before: float
    after: float


class RiskResult(BaseModel):
    """Clamped weights plus the audit trail of every limit that fired."""

    weights: dict[str, float]
    clamps: list[ClampEvent]
    scale_factor: float | None = None  # common multiplier when preserving proportions


def apply_limits(
    weights: dict[str, float], limits: RiskLimits, *, preserve_proportions: bool = False,
) -> RiskResult:
    """Clamp target weights against the fund's hard limits.

    With preserve_proportions, reduce every weight by a common factor instead
    of clipping individual names. This preserves strategy neutrality when the
    same factor is applied to each strategy's contribution.

    Without preserve_proportions, apply the three-stage reduction:
    1. Per-ticker cap: any |weight| above max_position_pct is clamped to the
       cap, preserving sign. One ClampEvent per clamped ticker.
    2. Net cap, when set: if |longs minus shorts| exceeds max_net_exposure,
       the heavier side is scaled down until the net sits at the band. One
       ClampEvent for the whole book.
    3. Gross cap: if the summed |weights| still exceed max_gross_exposure,
       every weight is scaled down proportionally. Scaling only shrinks, so
       it can never re-violate the caps before it.
    """
    if not isfinite(limits.max_position_pct) or not isfinite(limits.max_gross_exposure):
        raise ValueError("risk limits must be finite")
    if not 0 < limits.max_position_pct <= 1 or limits.max_gross_exposure <= 0:
        raise ValueError("risk limits must be positive, with max_position_pct at most 1")
    for ticker, weight in weights.items():
        if not isfinite(weight):
            raise ValueError(f"{ticker}: target weight must be finite")
    if not isfinite(sum(abs(w) for w in weights.values())):
        raise ValueError("fund gross exposure must be finite")
    if preserve_proportions:
        return _scale_proportionally(weights, limits)

    clamped: dict[str, float] = {}
    clamps: list[ClampEvent] = []

    for ticker in sorted(weights):
        w = weights[ticker]
        cap = limits.max_position_pct
        if abs(w) > cap:
            new_w = cap if w > 0 else -cap
            clamps.append(ClampEvent(
                limit="max_position_pct", ticker=ticker, before=w, after=new_w,
            ))
            clamped[ticker] = new_w
        else:
            clamped[ticker] = w

    longs = sum(w for w in clamped.values() if w > 0)
    shorts = -sum(w for w in clamped.values() if w < 0)
    net = longs - shorts
    if limits.max_net_exposure is not None and abs(net) > limits.max_net_exposure:
        band = limits.max_net_exposure
        if net > 0:
            scale = (band + shorts) / longs
            clamped = {t: w * scale if w > 0 else w for t, w in clamped.items()}
        else:
            scale = (band + longs) / shorts
            clamped = {t: w * scale if w < 0 else w for t, w in clamped.items()}
        clamps.append(ClampEvent(
            limit="max_net_exposure", before=net, after=band if net > 0 else -band,
        ))

    gross = sum(abs(w) for w in clamped.values())
    if gross > limits.max_gross_exposure:
        scale = limits.max_gross_exposure / gross
        clamped = {t: w * scale for t, w in clamped.items()}
        clamps.append(ClampEvent(
            limit="max_gross_exposure", before=gross, after=limits.max_gross_exposure,
        ))

    return RiskResult(weights=clamped, clamps=clamps)


def _scale_proportionally(weights: dict[str, float], limits: RiskLimits) -> RiskResult:
    largest = max((abs(w) for w in weights.values()), default=0.0)
    factor = min(1.0, limits.max_position_pct / largest) if largest else 1.0
    clamped = {t: weights[t] * factor for t in sorted(weights)}
    clamps = [
        ClampEvent(limit="max_position_pct", ticker=t, before=weights[t], after=clamped[t])
        for t in sorted(weights) if abs(weights[t]) > limits.max_position_pct
    ]
    net = sum(clamped.values())
    if limits.max_net_exposure is not None and abs(net) > limits.max_net_exposure:
        # Every weight shrinks by the same factor, so neutrality is kept.
        net_factor = limits.max_net_exposure / abs(net)
        clamped = {t: w * net_factor for t, w in clamped.items()}
        factor *= net_factor
        clamps.append(ClampEvent(
            limit="max_net_exposure", before=net,
            after=limits.max_net_exposure if net > 0 else -limits.max_net_exposure,
        ))
    gross = sum(abs(w) for w in clamped.values())
    if gross > limits.max_gross_exposure:
        gross_factor = limits.max_gross_exposure / gross
        clamped = {t: w * gross_factor for t, w in clamped.items()}
        factor *= gross_factor
        clamps.append(ClampEvent(limit="max_gross_exposure", before=gross, after=limits.max_gross_exposure))
    return RiskResult(weights=clamped, clamps=clamps, scale_factor=factor)
