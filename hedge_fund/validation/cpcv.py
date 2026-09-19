"""Combinatorial purged cross-validation splits on a 1D return series.

Educational use only. This validation gate is a research scaffold
(CPCV / PBO hooks), not a trading green-light and not investment advice.
A report here does not authorize live capital, auto-promotion, or real trading.

This is a structural helper, not a research-grade clone of any single paper.
Each observation is treated as a one-period return (no overlapping labels
unless you set ``purge`` / ``embargo`` yourself).

Purge
    Drop this many observations from the *train* set immediately *before*
    each contiguous test block. Use this when a label at t depends on
    information that would overlap the test window (a holding period, a
    trailing lookback, etc.).

Embargo
    Drop this many observations from the *train* set immediately *after*
    each contiguous test block. Use this to keep residual serial
    correlation from leaking test-block information into later training
    samples.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from math import comb

import numpy as np

@dataclass(frozen=True)
class CPCVSplit:
    """One CPCV fold: integer index arrays into the original series."""

    fold_id: int
    test_groups: tuple[int, ...]
    train_indices: np.ndarray
    test_indices: np.ndarray
    purged_indices: np.ndarray
    embargoed_indices: np.ndarray


def assign_groups(n_obs: int, n_groups: int) -> np.ndarray:
    """Contiguous group id for each observation (groups as equal as possible).

    Educational use only. This validation gate is a research scaffold
    (CPCV / PBO hooks), not a trading green-light and not investment advice.
    """
    if n_groups < 2:
        raise ValueError(f"n_groups must be >= 2, got {n_groups}")
    if n_obs < n_groups:
        raise ValueError(
            f"need at least n_groups={n_groups} observations, got {n_obs}"
        )
    base, extra = divmod(n_obs, n_groups)
    groups = np.empty(n_obs, dtype=int)
    start = 0
    for g in range(n_groups):
        size = base + (1 if g < extra else 0)
        groups[start : start + size] = g
        start += size
    return groups


def _contiguous_blocks(mask: np.ndarray) -> list[tuple[int, int]]:
    """Inclusive-exclusive [lo, hi) runs where ``mask`` is True."""
    padded = np.concatenate(([False], mask, [False]))
    edges = np.diff(padded.astype(int))
    starts = np.flatnonzero(edges == 1)
    ends = np.flatnonzero(edges == -1)
    return list(zip(starts.tolist(), ends.tolist()))


def cpcv_splits(
    n_obs: int,
    n_groups: int = 6,
    n_test_groups: int = 2,
    purge: int = 0,
    embargo: int = 0,
) -> list[CPCVSplit]:
    """Combinatorial purged / embargoed train-test splits on a length-``n_obs`` series.

    Educational use only. This validation gate is a research scaffold
    (CPCV / PBO hooks), not a trading green-light and not investment advice.

    Fold count is ``C(n_groups, n_test_groups)``. Each combination of
    ``n_test_groups`` groups is the test set; the rest start as train,
    then lose ``purge`` bars before each test block and ``embargo`` bars
    after it.

    Parameters
    ----------
    n_obs
        Length of the return series.
    n_groups
        How many contiguous time groups to cut the series into (>= 2).
    n_test_groups
        How many of those groups form the test set on each fold
        (1 <= n_test_groups < n_groups).
    purge
        Train bars dropped immediately before each test block. Must be >= 0.
    embargo
        Train bars dropped immediately after each test block. Must be >= 0.
    """
    if n_test_groups < 1 or n_test_groups >= n_groups:
        raise ValueError(
            f"n_test_groups must be in [1, n_groups), got n_test_groups={n_test_groups}, "
            f"n_groups={n_groups}"
        )
    if purge < 0 or embargo < 0:
        raise ValueError(f"purge and embargo must be >= 0, got purge={purge}, embargo={embargo}")

    groups = assign_groups(n_obs, n_groups)
    folds: list[CPCVSplit] = []
    for fold_id, test_groups in enumerate(combinations(range(n_groups), n_test_groups)):
        test_mask = np.isin(groups, test_groups)
        train_mask = ~test_mask
        purged = np.zeros(n_obs, dtype=bool)
        embargoed = np.zeros(n_obs, dtype=bool)

        for lo, hi in _contiguous_blocks(test_mask):
            if purge:
                purged[max(0, lo - purge) : lo] = True
            if embargo:
                embargoed[hi : min(n_obs, hi + embargo)] = True

        # Only train-side bars count as purged / embargoed.
        purged &= train_mask
        embargoed &= train_mask & ~purged
        train_mask = train_mask & ~purged & ~embargoed

        folds.append(
            CPCVSplit(
                fold_id=fold_id,
                test_groups=tuple(test_groups),
                train_indices=np.flatnonzero(train_mask),
                test_indices=np.flatnonzero(test_mask),
                purged_indices=np.flatnonzero(purged),
                embargoed_indices=np.flatnonzero(embargoed),
            )
        )

    expected = comb(n_groups, n_test_groups)
    if len(folds) != expected:  # pragma: no cover - combinations is deterministic
        raise RuntimeError(f"expected {expected} folds, built {len(folds)}")
    return folds


def period_sharpe(returns: np.ndarray, periods_per_year: int = 252) -> float | None:
    """Annualized Sharpe of a return slice. None when undefined (too short / zero vol).

    Educational use only. This validation gate is a research scaffold
    (CPCV / PBO hooks), not a trading green-light and not investment advice.
    """
    r = np.asarray(returns, dtype=float)
    if r.size < 2:
        return None
    std = float(r.std(ddof=1))
    if std == 0.0 or not np.isfinite(std):
        return None
    mean = float(r.mean())
    if not np.isfinite(mean):
        return None
    return float(np.sqrt(periods_per_year) * mean / std)


def fold_test_stats(returns: np.ndarray, split: CPCVSplit) -> tuple[float | None, float | None]:
    """Mean return and Sharpe on a fold's test indices."""
    r = np.asarray(returns, dtype=float)[split.test_indices]
    if r.size == 0:
        return None, None
    mean = float(r.mean()) if np.isfinite(r).all() else None
    return mean, period_sharpe(r)
