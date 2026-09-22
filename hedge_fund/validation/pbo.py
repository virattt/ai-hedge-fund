"""Probability of backtest overfitting — tiny CSCV hook.

Educational use only. This validation gate is a research scaffold
(CPCV / PBO hooks), not a trading green-light and not investment advice.
A report here does not authorize live capital, auto-promotion, or real trading.

Bailey, Borwein, López de Prado, and Zhu define PBO from combinatorial
symmetric cross-validation (CSCV) across *many* strategy trials: for each
split of time groups into an in-sample and out-of-sample half, rank the
trials in-sample, then ask whether the in-sample winner is below-median
out-of-sample. That number is a diagnostic, not a trading green-light.

This module implements a small version of that rank estimator when two or
more trial columns are supplied. A single backtest equity curve cannot
rank competing trials, so ``estimate_pbo`` then falls back to a documented
heuristic (share of CSCV splits where out-of-sample Sharpe is worse than
in-sample Sharpe). That heuristic is **not** textbook PBO.
"""

from __future__ import annotations

from itertools import combinations
from math import comb

import numpy as np

from hedge_fund.validation.cpcv import assign_groups, period_sharpe
from hedge_fund.validation.models import PBOResult

_SINGLE_TRIAL_LIMITATIONS = (
    "Single-trial heuristic: share of CSCV splits where OOS Sharpe is "
    "strictly worse than IS Sharpe. This is not Bailey et al. PBO, which "
    "needs multiple competing trials so an in-sample winner can be ranked "
    "out of sample. Treat the number as a hook, not a trading green-light."
)

_MULTI_TRIAL_LIMITATIONS = (
    "Tiny CSCV rank PBO: fraction of combinations where the in-sample "
    "Sharpe winner is worse than the median out-of-sample rank. Scaffold "
    "only — not a research-grade replica, not a trading green-light, and "
    "not investment advice."
)


def _as_trial_matrix(trial_returns: np.ndarray) -> np.ndarray:
    arr = np.asarray(trial_returns, dtype=float)
    if arr.ndim == 1:
        arr = arr.reshape(-1, 1)
    if arr.ndim != 2:
        raise ValueError(f"trial_returns must be 1D or 2D, got shape {arr.shape}")
    if arr.shape[0] < 2:
        raise ValueError("need at least 2 observations to estimate PBO")
    if arr.shape[1] < 1:
        raise ValueError("need at least 1 trial column")
    return arr


def estimate_pbo(
    trial_returns: np.ndarray,
    n_groups: int = 8,
) -> PBOResult:
    """Estimate a PBO-style diagnostic from one or more return trials.

    Educational use only. This validation gate is a research scaffold
    (CPCV / PBO hooks), not a trading green-light and not investment advice.

    Parameters
    ----------
    trial_returns
        Shape ``(n_periods,)`` or ``(n_periods, n_trials)``. Columns are
        competing backtest trials (same length, aligned in time).
    n_groups
        Even number of contiguous time groups (>= 2). Each CSCV split
        takes ``n_groups // 2`` groups as the in-sample half.
    """
    matrix = _as_trial_matrix(trial_returns)
    n_obs, n_trials = matrix.shape
    if n_groups < 2 or n_groups % 2:
        raise ValueError(f"n_groups must be even and >= 2, got {n_groups}")
    if n_obs < n_groups:
        raise ValueError(f"need at least n_groups={n_groups} observations, got {n_obs}")

    groups = assign_groups(n_obs, n_groups)
    half = n_groups // 2
    n_combinations = comb(n_groups, half)

    if n_trials == 1:
        return _heuristic_is_oos_decay(matrix[:, 0], groups, n_groups, half, n_combinations)
    return _cscv_rank_pbo(matrix, groups, n_groups, half, n_combinations)


def _heuristic_is_oos_decay(
    returns: np.ndarray,
    groups: np.ndarray,
    n_groups: int,
    half: int,
    n_combinations: int,
) -> PBOResult:
    worse = 0
    scored = 0
    for is_groups in combinations(range(n_groups), half):
        is_mask = np.isin(groups, is_groups)
        is_s = period_sharpe(returns[is_mask])
        oos_s = period_sharpe(returns[~is_mask])
        if is_s is None or oos_s is None:
            continue
        scored += 1
        if oos_s < is_s:
            worse += 1
    probability = (worse / scored) if scored else None
    skipped = n_combinations - scored
    notes = (
        f"Scored {scored}/{n_combinations} CSCV splits "
        f"({skipped} skipped: undefined Sharpe)."
    )
    return PBOResult(
        probability=probability,
        method="heuristic_is_oos_sharpe_decay",
        n_trials=1,
        n_combinations=n_combinations,
        limitations=_SINGLE_TRIAL_LIMITATIONS,
        notes=notes,
    )


def _cscv_rank_pbo(
    matrix: np.ndarray,
    groups: np.ndarray,
    n_groups: int,
    half: int,
    n_combinations: int,
) -> PBOResult:
    n_trials = matrix.shape[1]
    overfit = 0
    scored = 0
    for is_groups in combinations(range(n_groups), half):
        is_mask = np.isin(groups, is_groups)
        is_sharpes: list[float | None] = []
        oos_sharpes: list[float | None] = []
        for j in range(n_trials):
            is_sharpes.append(period_sharpe(matrix[is_mask, j]))
            oos_sharpes.append(period_sharpe(matrix[~is_mask, j]))
        if any(s is None for s in is_sharpes + oos_sharpes):
            continue
        is_arr = np.array(is_sharpes, dtype=float)
        oos_arr = np.array(oos_sharpes, dtype=float)
        winner = int(np.argmax(is_arr))
        # Higher Sharpe = better. Rank 1 is best; mid-rank is (n_trials + 1) / 2.
        oos_order = np.argsort(-oos_arr, kind="stable")
        oos_rank = int(np.flatnonzero(oos_order == winner)[0]) + 1
        scored += 1
        if oos_rank > n_trials / 2.0:
            overfit += 1
    probability = (overfit / scored) if scored else None
    skipped = n_combinations - scored
    notes = (
        f"Scored {scored}/{n_combinations} CSCV splits "
        f"({skipped} skipped: undefined Sharpe)."
    )
    return PBOResult(
        probability=probability,
        method="cscv_rank",
        n_trials=n_trials,
        n_combinations=n_combinations,
        limitations=_MULTI_TRIAL_LIMITATIONS,
        notes=notes,
    )
