"""Statistical functions for CPCV / PBO validation.

All functions are pure (no side effects, no file or model I/O) \u2014 they take
plain arrays, dicts and ints and return plain values or small internal
dataclasses. engine.py is the only module that knows about FundBacktestResult
or ValidationReport; this module only knows numbers.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field

import numpy as np
from scipy.stats import rankdata

# Trading periods per year implied by a fund's rebalance cadence \u2014 mirrors
# hedge_fund.backtesting.fund._PERIODS_PER_YEAR (same convention, kept local
# so this module has no dependency on the backtester).
PERIODS_PER_YEAR = {"daily": 252, "weekly": 52, "monthly": 12}


def periodic_returns(capital: float, nav: list[float]) -> np.ndarray:
    """Per-period simple returns from starting *capital* and a *nav* curve.

    returns[0] is the first period's move off capital; returns[i] for i>0
    is nav[i] / nav[i-1] - 1. Mirrors backtesting.fund._metrics exactly, so
    a fund's full-sample Sharpe and a CPCV split computed over all periods
    agree.
    """
    curve = np.asarray([capital, *nav], dtype=float)
    return curve[1:] / curve[:-1] - 1


def sharpe_ratio(returns: np.ndarray, periods_per_year: int) -> float:
    """Annualized Sharpe ratio of a *returns* array; 0.0 if undefined.

    Undefined when there are fewer than two observations, or the sample has
    zero variance (a flat or single-period slice can't say anything about
    risk-adjusted skill).
    """
    if len(returns) < 2:
        return 0.0
    std = float(returns.std(ddof=1))
    if std == 0.0:
        return 0.0
    return float(returns.mean() / std) * np.sqrt(periods_per_year)


# ---------------------------------------------------------------------------
# Combinatorial Purged Cross-Validation
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CPCVSplit:
    """Index-level description of one train/test combination."""

    split_index: int
    test_group_indices: tuple[int, ...]
    train_idx: np.ndarray
    test_idx: np.ndarray
    purged_idx: np.ndarray = field(default_factory=lambda: np.array([], dtype=int))
    embargoed_idx: np.ndarray = field(default_factory=lambda: np.array([], dtype=int))


def chronological_groups(n_periods: int, n_groups: int) -> list[np.ndarray]:
    """Split `range(n_periods)` into `n_groups` contiguous, chronological blocks.

    Blocks are as equal in size as possible (numpy's array_split rule: the
    first `n_periods % n_groups` blocks get one extra element). Every block
    must be non-empty, so `n_groups` cannot exceed `n_periods`.
    """
    if n_groups < 2:
        raise ValueError(f"n_groups must be >= 2, got {n_groups}")
    if n_periods < n_groups:
        raise ValueError(
            f"n_periods ({n_periods}) must be >= n_groups ({n_groups}) \u2014 "
            "every chronological group needs at least one period"
        )
    return [np.asarray(block) for block in np.array_split(np.arange(n_periods), n_groups)]


def _merge_to_blocks(indices: np.ndarray) -> list[tuple[int, int]]:
    """Collapse a sorted array of indices into contiguous (start, end) runs."""
    if len(indices) == 0:
        return []
    blocks: list[tuple[int, int]] = []
    start = prev = int(indices[0])
    for idx in indices[1:]:
        idx = int(idx)
        if idx == prev + 1:
            prev = idx
            continue
        blocks.append((start, prev))
        start = prev = idx
    blocks.append((start, prev))
    return blocks


def generate_cpcv_splits(
    n_periods: int,
    n_groups: int,
    n_test_groups: int,
    purge_periods: int,
    embargo_periods: int,
) -> list[CPCVSplit]:
    """Enumerate every C(n_groups, n_test_groups) combinatorial train/test split.

    For each combination of `n_test_groups` chronological blocks chosen as
    the test set: the held-out periods are merged into contiguous test
    blocks, `purge_periods` training periods on either side of each block
    are dropped (they may straddle information that leaks across the
    train/test boundary), and a further `embargo_periods` training periods
    immediately *after* each block are dropped (serial correlation can
    otherwise let the test set's influence bleed forward into training).
    Everything else is training data.
    """
    if n_test_groups < 1 or n_test_groups >= n_groups:
        raise ValueError(
            f"n_test_groups must be in [1, n_groups - 1], got "
            f"n_test_groups={n_test_groups}, n_groups={n_groups}"
        )
    if purge_periods < 0:
        raise ValueError(f"purge_periods must be >= 0, got {purge_periods}")
    if embargo_periods < 0:
        raise ValueError(f"embargo_periods must be >= 0, got {embargo_periods}")

    groups = chronological_groups(n_periods, n_groups)
    splits: list[CPCVSplit] = []

    for split_index, combo in enumerate(itertools.combinations(range(n_groups), n_test_groups)):
        test_idx = np.sort(np.concatenate([groups[g] for g in combo]))
        blocks = _merge_to_blocks(test_idx)

        purge_mask = np.zeros(n_periods, dtype=bool)
        embargo_mask = np.zeros(n_periods, dtype=bool)
        for start, end in blocks:
            purge_lo, purge_hi = max(0, start - purge_periods), min(n_periods - 1, end + purge_periods)
            purge_mask[purge_lo:purge_hi + 1] = True
            embargo_lo = end + purge_periods + 1
            embargo_hi = min(n_periods - 1, end + purge_periods + embargo_periods)
            if embargo_lo <= embargo_hi:
                embargo_mask[embargo_lo:embargo_hi + 1] = True
        purge_mask[test_idx] = False  # the test set itself isn't "purged", it's held out

        test_mask = np.zeros(n_periods, dtype=bool)
        test_mask[test_idx] = True

        embargo_mask &= ~test_mask
        purged_idx = np.where(purge_mask & ~test_mask)[0]
        embargoed_idx = np.where(embargo_mask)[0]

        train_mask = ~(test_mask | purge_mask | embargo_mask)
        train_idx = np.where(train_mask)[0]

        splits.append(CPCVSplit(
            split_index=split_index,
            test_group_indices=combo,
            train_idx=train_idx,
            test_idx=test_idx,
            purged_idx=purged_idx,
            embargoed_idx=embargoed_idx,
        ))

    return splits


# ---------------------------------------------------------------------------
# Probability of Backtest Overfitting
# ---------------------------------------------------------------------------

def select_best(in_sample_performance: dict[str, float]) -> str:
    """Pick the in-sample winner, breaking ties deterministically by name.

    Highest performance wins; among equal performances, the alphabetically
    first candidate name wins, so results are reproducible regardless of
    dict ordering.
    """
    return min(in_sample_performance, key=lambda name: (-in_sample_performance[name], name))


def relative_rank_and_logit(
    out_sample_performance: dict[str, float],
    selected: str,
    order: list[str],
) -> tuple[float, float, float]:
    """Rank `selected`'s out-of-sample performance among all candidates.

    Ranks run 1 (worst) .. n (best); ties share the average rank (so a
    perfect tie between the top two candidates gives both rank n - 0.5).
    `relative_rank` is Bailey et al.'s omega_c = rank / (n + 1); `logit` is
    their lambda_c = ln(omega_c / (1 - omega_c)). lambda_c <= 0 means the
    in-sample winner performed at or below the out-of-sample median.

    Returns (rank, relative_rank, logit).
    """
    values = np.array([out_sample_performance[name] for name in order], dtype=float)
    ranks = rankdata(values, method="average")
    n = len(order)
    selected_rank = float(ranks[order.index(selected)])
    relative_rank = selected_rank / (n + 1)
    logit = float(np.log(relative_rank / (1 - relative_rank)))
    return selected_rank, relative_rank, logit


def probability_of_backtest_overfitting(logits: list[float]) -> float:
    """PBO = fraction of splits whose logit is <= 0 (winner underperformed
    the out-of-sample median)."""
    if not logits:
        return 0.0
    return float(np.mean([1.0 if lam <= 0 else 0.0 for lam in logits]))
