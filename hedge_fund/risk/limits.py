"""Risk limits — hard caps the analysts cannot override.

"Conviction requests, risk disposes": portfolio construction proposes target
weights, and this stage clamps them against the fund's limits. Everything
here is deterministic arithmetic — the LLM's influence over the book ends at
the Signal, and no clamp is ever negotiable.

Exposure removed by a clamp is NOT redistributed to other names; it stays in
cash. Redistributing would let the risk stage *increase* positions, which
inverts its job.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RiskLimits(BaseModel):
    """The fund's hard limits, set in its FundSpec."""

    model_config = ConfigDict(extra="forbid")

    max_position_pct: float = Field(
        gt=0, le=1.0, description="max |weight| per ticker, as a fraction of equity"
    )
    max_gross_exposure: float = Field(
        gt=0, description="max sum of |weights| across the book (1.0 = unlevered)"
    )
    min_cash_reserve_pct: float = Field(
        default=0.0,
        ge=0.0,
        lt=1.0,
        description="min fraction of equity left in cash; caps NET exposure at "
        "1 - this. Defaults to 0.0 — a mandate that does not ask for a reserve "
        "prices exactly as it did before this limit existed.",
    )


class ClampEvent(BaseModel):
    """One limit firing — recorded so every clamp is explainable."""

    limit: Literal["max_position_pct", "max_gross_exposure", "min_cash_reserve_pct"]
    ticker: str | None = None  # None for the portfolio-level gross clamp
    before: float
    after: float


class RiskResult(BaseModel):
    """Clamped weights plus the audit trail of every limit that fired."""

    weights: dict[str, float]
    clamps: list[ClampEvent]


def apply_limits(weights: dict[str, float], limits: RiskLimits) -> RiskResult:
    """Clamp target weights against the fund's hard limits.

    Order matters and makes the pair idempotent:
    1. Per-ticker cap: any |weight| above max_position_pct is clamped to the
       cap, preserving sign. One ClampEvent per clamped ticker.
    2. Gross cap: if the summed |weights| still exceed max_gross_exposure,
       every weight is scaled down proportionally. Scaling only shrinks, so
       it can never re-violate the per-ticker cap.
    3. Cash floor: cash here is equity * (1 - NET exposure) — a short credits
       its proceeds and margin is not modeled — so reserving cash is a cap on
       the SIGNED sum, not the absolute one. A market-neutral book already
       sits near 100% cash and is left alone; only a net-long book above the
       ceiling is scaled. Scaling shrinks shorts toward zero alongside longs,
       so gross falls too and neither earlier cap can be re-violated.
    """
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

    gross = sum(abs(w) for w in clamped.values())
    if gross > limits.max_gross_exposure:
        scale = limits.max_gross_exposure / gross
        clamped = {t: w * scale for t, w in clamped.items()}
        clamps.append(ClampEvent(
            limit="max_gross_exposure", before=gross, after=limits.max_gross_exposure,
        ))

    # Guarded rather than folded into the comparison: at the default of 0.0 the
    # ceiling is 1.0 and an unlevered book sits exactly on it, so skipping the
    # branch outright is what keeps a fund without a reserve arithmetically
    # identical to one from before this limit existed.
    if limits.min_cash_reserve_pct > 0:
        ceiling = 1.0 - limits.min_cash_reserve_pct
        net = sum(clamped.values())
        # Tolerance, not sloppiness: scaling to the ceiling lands a float dust
        # mote above it, and a bare `>` would clamp an already-clamped book a
        # second time and record a 0.9000000000000001 -> 0.9 event. This
        # function promises idempotence, and every ClampEvent is supposed to
        # be explainable to someone reading the receipt.
        if net > ceiling + 1e-12:
            clamped = {t: w * (ceiling / net) for t, w in clamped.items()}
            clamps.append(ClampEvent(
                limit="min_cash_reserve_pct", before=net, after=ceiling,
            ))

    return RiskResult(weights=clamped, clamps=clamps)
