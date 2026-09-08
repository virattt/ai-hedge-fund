"""CPCV / PBO validation engine \u2014 the public API's orchestration layer.

Compares multiple FundBacktestResult candidates over their (shared) periodic
returns using Combinatorial Purged Cross-Validation, and reports the
Probability of Backtest Overfitting (PBO): how often would picking the
best-looking candidate in-sample have actually picked a below-median
performer out-of-sample?

This module owns compatibility checks (the "can these two backtests even be
compared" question) and assembling the serializable ValidationReport; all
the actual math \u2014 splitting, purging, Sharpe, ranking, PBO \u2014 lives in
stats.py as pure functions.
"""

from __future__ import annotations

import math

from hedge_fund.backtesting.fund import FundBacktestResult
from hedge_fund.validation.models import ValidationReport, ValidationSplit
from hedge_fund.validation.stats import (
    PERIODS_PER_YEAR,
    generate_cpcv_splits,
    periodic_returns,
    relative_rank_and_logit,
    select_best,
    sharpe_ratio,
)


def validate_candidates(
    candidates: dict[str, FundBacktestResult],
    *,
    n_groups: int = 6,
    n_test_groups: int = 2,
    purge_periods: int = 1,
    embargo_periods: int = 1,
) -> ValidationReport:
    """Run CPCV over *candidates* and report the Probability of Backtest Overfitting.

    *candidates* maps a name (e.g. a strategy or parameterization label) to
    its full-sample FundBacktestResult. All candidates must share the same
    trading-day grid, rebalance cadence, and starting capital \u2014 otherwise
    their periodic returns aren't comparable and this raises ValueError.

    The shared date grid is split into `n_groups` chronological blocks.
    Every combination of `n_test_groups` blocks is, in turn, held out as a
    test set (`purge_periods` around its boundaries and `embargo_periods`
    after it are dropped from training so information can't leak across the
    split). For each split, the candidate with the best in-sample Sharpe
    ratio is "selected" \u2014 exactly what picking the best backtest does in
    practice \u2014 and its out-of-sample Sharpe ratio (and rank among all
    candidates) is recorded. PBO is the fraction of splits where that
    selection did no better than the out-of-sample median.
    """
    names = _validate_compatible(candidates)
    reference = candidates[names[0]]
    dates = reference.dates
    n_periods = len(dates)
    periods_per_year = PERIODS_PER_YEAR[reference.rebalance]

    returns = {
        name: periodic_returns(candidates[name].capital, candidates[name].nav)
        for name in names
    }

    cpcv_splits = generate_cpcv_splits(
        n_periods, n_groups, n_test_groups, purge_periods, embargo_periods
    )

    splits: list[ValidationSplit] = []
    selection_counts: dict[str, int] = {name: 0 for name in names}
    logits: list[float] = []

    for split in cpcv_splits:
        if len(split.train_idx) == 0:
            raise ValueError(
                f"split {split.split_index}: no training periods remain after "
                "purging/embargo \u2014 reduce n_groups, purge_periods, or embargo_periods"
            )
        if len(split.test_idx) == 0:
            raise ValueError(f"split {split.split_index}: test set is empty")

        in_sample = {
            name: sharpe_ratio(returns[name][split.train_idx], periods_per_year)
            for name in names
        }
        out_sample = {
            name: sharpe_ratio(returns[name][split.test_idx], periods_per_year)
            for name in names
        }
        selected = select_best(in_sample)
        selection_counts[selected] += 1
        rank, relative_rank, logit = relative_rank_and_logit(out_sample, selected, names)
        logits.append(logit)

        splits.append(ValidationSplit(
            split_index=split.split_index,
            test_group_indices=list(split.test_group_indices),
            train_dates=[dates[i] for i in split.train_idx],
            test_dates=[dates[i] for i in split.test_idx],
            purged_dates=[dates[i] for i in split.purged_idx],
            embargoed_dates=[dates[i] for i in split.embargoed_idx],
            in_sample_performance=in_sample,
            out_sample_performance=out_sample,
            selected_candidate=selected,
            selected_out_sample_performance=out_sample[selected],
            selected_out_sample_rank=rank,
            relative_rank=relative_rank,
            logit=logit,
        ))

    pbo = float(sum(1.0 for lam in logits if lam <= 0) / len(logits)) if logits else 0.0

    return ValidationReport(
        candidates=names,
        n_periods=n_periods,
        n_groups=n_groups,
        n_test_groups=n_test_groups,
        purge_periods=purge_periods,
        embargo_periods=embargo_periods,
        splits=splits,
        selection_counts=selection_counts,
        pbo=pbo,
    )


# ---------------------------------------------------------------------------
# Compatibility checks
# ---------------------------------------------------------------------------

def _validate_compatible(candidates: dict[str, FundBacktestResult]) -> list[str]:
    """Fail loud on anything that would make comparing candidates meaningless.

    Returns the sorted candidate names on success so callers get a stable
    iteration order for free.
    """
    if len(candidates) < 2:
        raise ValueError(
            f"validate_candidates needs at least 2 candidates to compare, got {len(candidates)}"
        )

    names = sorted(candidates)
    reference_name = names[0]
    reference = candidates[reference_name]

    if not reference.dates:
        raise ValueError(f"{reference_name!r}: backtest has no dates")

    for name in names:
        result = candidates[name]

        if result.dates != reference.dates:
            raise ValueError(
                f"{name!r} has incompatible dates with {reference_name!r} \u2014 "
                "all candidates must share the same trading-day grid"
            )
        if result.rebalance != reference.rebalance:
            raise ValueError(
                f"{name!r} rebalance cadence {result.rebalance!r} != "
                f"{reference.rebalance!r} for {reference_name!r} \u2014 "
                "candidates must share a rebalance frequency"
            )
        if result.capital != reference.capital:
            raise ValueError(
                f"{name!r} capital {result.capital!r} != {reference.capital!r} "
                f"for {reference_name!r} \u2014 candidates must share a starting capital"
            )
        if result.rebalance not in PERIODS_PER_YEAR:
            raise ValueError(
                f"{name!r}: unknown rebalance cadence {result.rebalance!r}"
            )
        if not math.isfinite(result.capital) or result.capital <= 0:
            raise ValueError(f"{name!r}: capital must be a positive finite number, got {result.capital!r}")
        if len(result.nav) != len(result.dates):
            raise ValueError(
                f"{name!r}: {len(result.nav)} nav points for {len(result.dates)} dates"
            )
        for value in result.nav:
            if not math.isfinite(value):
                raise ValueError(f"{name!r}: nav contains a non-finite value ({value!r})")
            if value <= 0:
                raise ValueError(f"{name!r}: nav must be positive, got {value!r}")

    return names
