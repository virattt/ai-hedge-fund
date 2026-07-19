"""Portfolio construction — blend analyst views into target weights.

This is the fund's portfolio manager: it takes every analyst's Signal and
produces one target weight per ticker. Pure arithmetic, no I/O — given the
same signals it always produces the same book.

v0 policy: conviction-weighted. Capital flows to tickers in proportion to
their blended conviction, scaled so the whole book deploys `gross_target`.
Known wart, accepted deliberately: the cross-sectional normalization ignores
*absolute* conviction — a lone weak view would receive the full gross target,
which the risk stage then clamps ("conviction requests, risk disposes"). A
min-conviction floor is the obvious knob once `evaluate()` can measure it.
"""

from __future__ import annotations

from pydantic import BaseModel

from v2.models import Signal


class BlendResult(BaseModel):
    """Per-ticker blended convictions and the target weights they imply."""

    convictions: dict[str, float]  # blended view per ticker, pre-scaling
    weights: dict[str, float]      # target weight per ticker; sum(|w|) <= gross_target


def blend_signals(
    signals: list[Signal],
    model_weights: dict[str, float],
    gross_target: float,
    market_neutral: bool = False,
) -> BlendResult:
    """Blend model signals into target weights.

    Per ticker, the conviction is a weighted mean over *voting* models:

        conviction_t = sum(w_m * value_mt) / sum(w_m)

    An abstained signal (metadata.abstained is True — LLM failure or
    insufficient data) is excluded from numerator AND denominator: "no
    opinion" must not masquerade as "opinion: neutral". A non-abstained 0.0
    (e.g. PEAD outside its window) is a real neutral vote and dilutes.

    With market_neutral, convictions are demeaned cross-sectionally before
    scaling — what a pod does with analyst rankings: long the names the desk
    likes most *relative to the others*, short the least liked, sleeve sums
    to zero dollars. Uniform convictions demean to a flat book.

    Cross-sectionally, weights are (demeaned) convictions normalized to the
    gross target: weight_t = conviction_t / sum(|convictions|) * gross_target.
    All-zero convictions produce an all-zero (flat) book.

    Args:
        signals:        Every model's Signal for every ticker this cycle.
        model_weights:  model_name -> blend weight from the StrategySpec.
        gross_target:   Desired sum of |weights| when views exist.
        market_neutral: Demean convictions before scaling (dollar-neutral).
    """
    weighted_sum: dict[str, float] = {}
    weight_total: dict[str, float] = {}
    for signal in signals:
        if signal.metadata.get("abstained") is True:
            continue
        w = model_weights[signal.model_name]
        weighted_sum[signal.ticker] = weighted_sum.get(signal.ticker, 0.0) + w * signal.value
        weight_total[signal.ticker] = weight_total.get(signal.ticker, 0.0) + w

    tickers = sorted({s.ticker for s in signals})
    convictions = {
        t: (weighted_sum[t] / weight_total[t]) if weight_total.get(t) else 0.0
        for t in tickers
    }

    scaled = convictions
    if market_neutral and tickers:
        mean = sum(convictions.values()) / len(convictions)
        scaled = {t: c - mean for t, c in convictions.items()}

    # Threshold, not == 0: demeaning identical convictions leaves ~1e-16
    # residue, and dividing by it would normalize noise into a full book.
    gross = sum(abs(c) for c in scaled.values())
    if gross < 1e-9:
        weights = {t: 0.0 for t in tickers}
    else:
        weights = {t: c / gross * gross_target for t, c in scaled.items()}

    return BlendResult(convictions=convictions, weights=weights)
