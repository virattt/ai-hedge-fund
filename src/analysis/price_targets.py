"""Multi-horizon price target model.

For each horizon (3M / 6M / 12M / 24M) we produce three independent estimates
through different lenses:

1. **Technical**: project current 6-month annualized momentum forward, with
   confidence decay over time.
2. **Fundamental**: project forward EPS at the (clamped) analyst growth rate,
   multiply by the appropriate target P/E.
3. **Analyst**: scale the analyst mean 12M target to the horizon (linear for
   <12M, compound at the same implied growth rate for >12M).

These are combined via horizon-specific weights: shorter horizons lean
technical, longer horizons lean fundamental + analyst. We attach a bear /
bull range derived from realized annualized volatility (1σ band at
sqrt(t) scaling), giving an honest "where could this end up" envelope
that widens with time.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd


@dataclass
class HorizonTarget:
    label: str                                 # "3M" / "6M" / "12M" / "24M"
    months: int
    technical_target: Optional[float] = None
    fundamental_target: Optional[float] = None
    analyst_target: Optional[float] = None
    combined_target: Optional[float] = None
    bear_case: Optional[float] = None
    bull_case: Optional[float] = None
    upside_pct: Optional[float] = None         # combined vs current (decimal)
    downside_pct: Optional[float] = None       # bear vs current (decimal)
    confidence: float = 50.0                   # 0-100
    components_used: int = 0                   # how many lenses fired
    notes: str = ""


@dataclass
class PriceTargetSet:
    current_price: float
    targets: list[HorizonTarget] = field(default_factory=list)
    annualized_volatility: Optional[float] = None  # σ on daily log returns × √252


# Weights per horizon: (technical, fundamental, analyst). Shorter horizons
# lean technical; longer horizons lean on fundamentals + analyst consensus.
_WEIGHTS = {
    3:  (0.55, 0.25, 0.20),
    6:  (0.40, 0.30, 0.30),
    12: (0.20, 0.35, 0.45),
    24: (0.10, 0.55, 0.35),
}


def _technical_target(close: pd.Series, current_price: float, months: int) -> Optional[float]:
    if len(close) < 126:
        return None
    six_mo_ret = current_price / float(close.iloc[-126]) - 1.0
    annualized = six_mo_ret * 2.0
    # Confidence decay — momentum effects shrink as horizon extends
    decay = 0.65 if months <= 6 else (0.45 if months <= 12 else 0.30)
    annual_growth = annualized * decay
    annual_growth = max(-0.40, min(0.50, annual_growth))
    return current_price * (1 + annual_growth) ** (months / 12)


def _fundamental_target(info: dict, current_price: float, months: int) -> Optional[float]:
    if not info:
        return None
    fpe = info.get("forwardPE")
    pe = info.get("trailingPE")
    eps = info.get("trailingEps") or info.get("forwardEps")
    growth = info.get("earningsGrowth")
    if growth is None:
        growth = info.get("revenueGrowth")
    if growth is None:
        growth = 0.10  # neutral default

    target_multiple = fpe or pe
    if not target_multiple or not eps or eps <= 0:
        return None

    growth = max(-0.30, min(0.60, float(growth)))
    projected_eps = float(eps) * (1 + growth) ** (months / 12)
    target = projected_eps * float(target_multiple)
    # Sanity clamp: ±60% of current per year
    cap = current_price * (1.6 ** (months / 12))
    floor = current_price * (0.5 ** (months / 12))
    return max(floor, min(cap, target))


def _analyst_target(analyst, current_price: float, months: int) -> Optional[float]:
    if not analyst:
        return None
    target_12m = analyst.mean_target
    if not target_12m or target_12m <= 0:
        return None
    if months == 12:
        return float(target_12m)
    if months < 12:
        # Linear interpolation from current to 12M target
        return current_price + (target_12m - current_price) * (months / 12)
    # >12M: extrapolate at the same compounded growth rate
    if current_price <= 0:
        return None
    growth = target_12m / current_price - 1.0
    growth = max(-0.30, min(0.60, growth))
    return current_price * (1 + growth) ** (months / 12)


def _annualized_volatility(close: pd.Series) -> Optional[float]:
    if len(close) < 60:
        return None
    try:
        import numpy as np
        log_ret = (close / close.shift(1)).apply(lambda x: math.log(x) if x and x > 0 else 0).dropna()
        if log_ret.std() == 0:
            return None
        return float(log_ret.std()) * math.sqrt(252)
    except Exception:
        return None


def compute_targets(
    close: pd.Series, info: dict, analyst, current_price: float
) -> PriceTargetSet:
    """Build a PriceTargetSet across the four standard horizons."""
    if current_price is None or current_price <= 0:
        return PriceTargetSet(current_price=current_price or 0.0)

    vol = _annualized_volatility(close)
    pts = PriceTargetSet(current_price=current_price, annualized_volatility=vol)

    for months in (3, 6, 12, 24):
        tech = _technical_target(close, current_price, months)
        fund = _fundamental_target(info, current_price, months)
        ana = _analyst_target(analyst, current_price, months)

        w_tech, w_fund, w_ana = _WEIGHTS[months]
        components: list[tuple[float, float, str]] = []
        if tech is not None:
            components.append((tech, w_tech, f"Technical ${tech:,.2f}"))
        if fund is not None:
            components.append((fund, w_fund, f"Fundamental ${fund:,.2f}"))
        if ana is not None:
            components.append((ana, w_ana, f"Analyst ${ana:,.2f}"))

        if not components:
            pts.targets.append(HorizonTarget(label=f"{months}M", months=months))
            continue

        total_w = sum(w for _, w, _ in components)
        combined = sum(t * w for t, w, _ in components) / total_w

        # Bear/bull from realized vol — 1σ band scaled by sqrt(time)
        if vol is not None and vol > 0:
            sigma_t = vol * math.sqrt(months / 12)
            bear = combined * math.exp(-sigma_t)
            bull = combined * math.exp(sigma_t)
        else:
            spread = 0.15 * math.sqrt(months / 12)
            bear = combined * (1 - spread)
            bull = combined * (1 + spread)

        upside = combined / current_price - 1.0
        downside = bear / current_price - 1.0

        # Confidence: tight clustering of components → high; wide spread → low
        if len(components) >= 2:
            vals = [t for t, _, _ in components]
            spread = (max(vals) - min(vals)) / combined if combined > 0 else 0
            confidence = max(40.0, min(90.0, 90 - spread * 100))
        else:
            confidence = 55.0

        pts.targets.append(
            HorizonTarget(
                label=f"{months}M",
                months=months,
                technical_target=tech,
                fundamental_target=fund,
                analyst_target=ana,
                combined_target=combined,
                bear_case=bear,
                bull_case=bull,
                upside_pct=upside,
                downside_pct=downside,
                confidence=confidence,
                components_used=len(components),
                notes=" · ".join(n for _, _, n in components),
            )
        )

    return pts
