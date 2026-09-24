"""Validate complete strategy contributions before order submission."""

from __future__ import annotations

from math import isfinite
from typing import TYPE_CHECKING

from hedge_fund.portfolio.construction import blend_signals, WEIGHT_TOLERANCE
from hedge_fund.signals import get_investment_approach

if TYPE_CHECKING:
    from hedge_fund.fund.spec import FundSpec
    from hedge_fund.pipeline.models import StrategyRecord


def validate_targets(spec: FundSpec, strategies: list[StrategyRecord], final_weights: dict[str, float]) -> None:
    """Raise ValueError if the proposed book violates its recorded mandate.

    Short evidence is recomputed from the signals and declared profiles rather
    than trusting the sizing output. All checks run before any orders are sent.
    Contributions are fractions of fund equity, not of strategy capital.
    """
    by_name = {s.name: s for s in spec.strategies}
    if len(strategies) != len(by_name) or {s.name for s in strategies} != set(by_name):
        raise ValueError(f"{spec.name}: strategy contributions do not match the mandate")
    total_slice = sum(s.weight for s in spec.strategies)
    if not isfinite(total_slice) or total_slice <= 0:
        raise ValueError(f"{spec.name}: strategy allocations must have a finite, positive total")
    combined: dict[str, float] = {}
    for record in strategies:
        strategy = by_name[record.name]
        scope = f"strategy {strategy.name!r}"
        expected_slice = strategy.weight / total_slice
        if not isfinite(record.slice) or record.slice <= 0 or abs(record.slice - expected_slice) > WEIGHT_TOLERANCE:
            raise ValueError(f"{scope}: capital slice does not match the mandate")
        evidence = blend_signals(
            record.signals,
            strategy.model_weights,
            strategy.blend.gross_target,
            mode=strategy.blend.mode,
            investment_approaches={m.name: get_investment_approach(m.name) for m in strategy.models},
        )
        if record.eligible_scores.keys() != evidence.eligible_scores.keys():
            raise ValueError(f"{scope}: eligible score tickers do not match analyst signals")
        for ticker, score in record.eligible_scores.items():
            if not isfinite(score) or abs(score - evidence.eligible_scores[ticker]) > WEIGHT_TOLERANCE:
                raise ValueError(f"{scope}, {ticker}: eligible score does not match analyst evidence")
        for label, weights, gross_limit in (
            ("target", record.weights, strategy.blend.gross_target),
            ("final contribution", record.final_contribution, strategy.blend.gross_target * expected_slice),
        ):
            for ticker, weight in weights.items():
                if not isfinite(weight):
                    raise ValueError(f"{scope}, {ticker}: {label} must be finite")
                if strategy.blend.mode == "long_only" and weight < -WEIGHT_TOLERANCE:
                    raise ValueError(f"{scope}, {ticker}: long-only {label} cannot be negative")
                if weight < -WEIGHT_TOLERANCE and evidence.eligible_scores.get(ticker, 0.0) >= 0:
                    raise ValueError(f"{scope}, {ticker}: negative {label} has no eligible short evidence")
                if evidence.flat_reason is not None and abs(weight) > WEIGHT_TOLERANCE:
                    raise ValueError(f"{scope}, {ticker}: {evidence.flat_reason} requires zero {label}")
            gross = sum(abs(w) for w in weights.values())
            if not isfinite(gross) or gross > gross_limit + WEIGHT_TOLERANCE:
                raise ValueError(f"{scope}: {label} exceeds strategy gross target")
            if strategy.blend.mode == "dollar_neutral" and abs(sum(weights.values())) > WEIGHT_TOLERANCE:
                raise ValueError(f"{scope}: {label} is not dollar-neutral")
        for ticker, weight in record.final_contribution.items():
            combined[ticker] = combined.get(ticker, 0.0) + weight

    for ticker in sorted(set(combined) | set(final_weights)):
        weight = final_weights.get(ticker, 0.0)
        contribution = combined.get(ticker, 0.0)
        if not isfinite(weight) or not isfinite(contribution):
            raise ValueError(f"{spec.name}, {ticker}: final weight and contributions must be finite")
        if abs(weight - contribution) > WEIGHT_TOLERANCE:
            raise ValueError(f"{spec.name}, {ticker}: strategy contributions do not sum to final weight")
        if abs(weight) > spec.risk.max_position_pct + WEIGHT_TOLERANCE:
            raise ValueError(f"{spec.name}, {ticker}: final weight exceeds max_position_pct")
    gross = sum(abs(w) for w in final_weights.values())
    if not isfinite(gross) or gross > spec.risk.max_gross_exposure + WEIGHT_TOLERANCE:
        raise ValueError(f"{spec.name}: final weights exceed max_gross_exposure")
