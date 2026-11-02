"""Risk limits — hard caps the analysts cannot override.

"Conviction requests, risk disposes": portfolio construction proposes target
weights, and this stage clamps them against the fund's limits. Everything
here is deterministic arithmetic — the LLM's influence over the book ends at
the Signal, and no clamp is ever negotiable.

Exposure removed by a clamp is NOT redistributed to other names; it stays in
cash. Redistributing would let the risk stage *increase* positions, which
inverts its job.

Seven stages, each of which only shrinks. Two act on names or sides: the
per-name cap, then the net cap (the heavier side is scaled down until longs
minus shorts sit at the band). Five scale the whole book by one factor, so
none can re-violate a stage before it: the sector cap, the beta cap, the
volatility cap, the drawdown halving, then the gross cap. A sector over its
cap therefore shrinks the innocent sectors too; a shop with an optimizer
would move only the offender, and this stage says so on the record instead.
The drawdown stop-out and the volume cap are limits on the same model but
act elsewhere: the stop-out in `advance`, where NAV is known, and the volume
cap in `execute_decision`, where orders are sized.
"""

from __future__ import annotations

from math import isfinite
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator

from hedge_fund.risk.exposures import Exposures

# A halved book runs at this share of its size.
_HALF = 0.5


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
    halve_drawdown_pct: float | None = Field(
        default=None, gt=0, lt=1,
        description="NAV fall from its peak at which the book runs at half size, until it recovers",
    )
    max_adv_pct: float | None = Field(
        default=None, gt=0, le=1,
        description="max order size as a share of the name's 20-day average daily volume",
    )
    max_beta: float | None = Field(
        default=None, gt=0, description="max |book beta| to the benchmark"
    )
    max_sector_pct: float | None = Field(
        default=None, gt=0, le=1, description="max |net weight| in any one sector"
    )
    max_volatility: float | None = Field(
        default=None, gt=0, description="max modelled annualized volatility of the book"
    )

    @model_validator(mode="after")
    def _halve_before_stop(self):
        if (self.halve_drawdown_pct is not None and self.max_drawdown_pct is not None
                and self.halve_drawdown_pct >= self.max_drawdown_pct):
            raise ValueError("halve_drawdown_pct must be below max_drawdown_pct")
        return self

    @property
    def has_factor_limits(self) -> bool:
        """Whether a limit needs the book's exposures to be measured."""
        return any(limit is not None for limit in (self.max_beta, self.max_sector_pct, self.max_volatility))

    @model_serializer(mode="wrap")
    def _serialize(self, handler):
        """A limit that is not set serializes as it did before the limit
        existed: every ledger record carries these inside its hash."""
        data = handler(self)
        for name in ("max_net_exposure", "max_drawdown_pct", "halve_drawdown_pct", "max_adv_pct",
                     "max_beta", "max_sector_pct", "max_volatility"):
            if data.get(name) is None:
                data.pop(name, None)
        return data


class ClampEvent(BaseModel):
    """One limit firing — recorded so every clamp is explainable."""

    limit: Literal[
        "max_position_pct", "max_gross_exposure", "max_net_exposure", "max_drawdown_pct",
        "halve_drawdown_pct", "max_adv_pct", "max_beta", "max_sector_pct", "max_volatility",
    ]
    ticker: str | None = None  # None for a whole-book clamp
    sector: str | None = None  # the sector a sector clamp measured
    before: float
    after: float

    @model_serializer(mode="wrap")
    def _serialize(self, handler):
        """A clamp with no sector serializes as every clamp did before
        sectors existed: it sits inside a hashed record."""
        data = handler(self)
        if self.sector is None:
            data.pop("sector", None)
        return data


class RiskResult(BaseModel):
    """Clamped weights plus the audit trail of every limit that fired."""

    weights: dict[str, float]
    clamps: list[ClampEvent]
    scale_factor: float | None = None  # common multiplier when preserving proportions


def apply_limits(
    weights: dict[str, float], limits: RiskLimits, *, preserve_proportions: bool = False,
    drawdown: float = 0.0, exposures: Exposures | None = None,
) -> RiskResult:
    """Clamp target weights against the fund's hard limits.

    *drawdown* is the fund's fall from its NAV peak, for the halving tier;
    *exposures* the book's factor model, required when a factor cap is set.

    With preserve_proportions, reduce every weight by a common factor instead
    of clipping individual names. This preserves strategy neutrality when the
    same factor is applied to each strategy's contribution.

    Without preserve_proportions:
    1. Per-ticker cap: any |weight| above max_position_pct is clamped to the
       cap, preserving sign. One ClampEvent per clamped ticker.
    2. Net cap, when set: if |longs minus shorts| exceeds max_net_exposure,
       the heavier side is scaled down until the net sits at the band. One
       ClampEvent for the whole book.
    3. The whole-book scalers, in order: sector, beta, volatility, the
       drawdown halving, then the gross cap. Each shrinks every weight by
       one factor, so none can re-violate a stage before it.
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
    if not isfinite(drawdown) or drawdown < 0:
        raise ValueError("drawdown must be a finite, non-negative fraction")
    if limits.has_factor_limits and exposures is None:
        raise ValueError("a beta, sector, or volatility limit needs the book's exposures")
    if exposures is not None:
        missing = sorted(set(weights) - set(exposures.names))
        if missing:
            raise ValueError(f"no exposure for {', '.join(missing)}")
    if preserve_proportions:
        return _scale_proportionally(weights, limits, drawdown, exposures)

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

    clamped, book_clamps, _ = _scale_book(clamped, limits, drawdown, exposures)
    return RiskResult(weights=clamped, clamps=[*clamps, *book_clamps])


def _scale_proportionally(
    weights: dict[str, float], limits: RiskLimits, drawdown: float, exposures: Exposures | None,
) -> RiskResult:
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
    clamped, book_clamps, book_factor = _scale_book(clamped, limits, drawdown, exposures)
    return RiskResult(weights=clamped, clamps=[*clamps, *book_clamps], scale_factor=factor * book_factor)


def _scale_book(
    weights: dict[str, float], limits: RiskLimits, drawdown: float, exposures: Exposures | None,
) -> tuple[dict[str, float], list[ClampEvent], float]:
    """The whole-book scalers: sector, beta, volatility, the drawdown
    halving, then gross. Returns the scaled weights, the clamps that fired,
    and the product of their factors."""
    clamps: list[ClampEvent] = []
    factor = 1.0

    if limits.max_sector_pct is not None:
        nets = exposures.sector_nets(weights)
        over = {sector: net for sector, net in nets.items() if abs(net) > limits.max_sector_pct}
        if over:
            scale = limits.max_sector_pct / max(abs(net) for net in over.values())
            weights = {t: w * scale for t, w in weights.items()}
            factor *= scale
            clamps.extend(
                ClampEvent(limit="max_sector_pct", sector=sector, before=net, after=net * scale)
                for sector, net in sorted(over.items())
            )

    if limits.max_beta is not None:
        beta = exposures.book_beta(weights)
        if abs(beta) > limits.max_beta:
            scale = limits.max_beta / abs(beta)
            weights = {t: w * scale for t, w in weights.items()}
            factor *= scale
            clamps.append(ClampEvent(
                limit="max_beta", before=beta, after=limits.max_beta if beta > 0 else -limits.max_beta,
            ))

    if limits.max_volatility is not None:
        volatility = exposures.book_volatility(weights)
        if volatility > limits.max_volatility:
            scale = limits.max_volatility / volatility
            weights = {t: w * scale for t, w in weights.items()}
            factor *= scale
            clamps.append(ClampEvent(limit="max_volatility", before=volatility, after=limits.max_volatility))

    if limits.halve_drawdown_pct is not None and drawdown >= limits.halve_drawdown_pct:
        weights = {t: w * _HALF for t, w in weights.items()}
        factor *= _HALF
        clamps.append(ClampEvent(limit="halve_drawdown_pct", before=drawdown, after=_HALF))

    gross = sum(abs(w) for w in weights.values())
    if gross > limits.max_gross_exposure:
        scale = limits.max_gross_exposure / gross
        weights = {t: w * scale for t, w in weights.items()}
        factor *= scale
        clamps.append(ClampEvent(limit="max_gross_exposure", before=gross, after=limits.max_gross_exposure))

    return weights, clamps, factor
