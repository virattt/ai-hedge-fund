"""Run the validation-gate scaffold on returns, an equity curve, or a saved backtest.

Educational use only. This validation gate is a research scaffold
(CPCV / PBO hooks), not a trading green-light and not investment advice.
A report here does not authorize live capital, auto-promotion, or real trading.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from hedge_fund.validation.cpcv import cpcv_splits, fold_test_stats
from hedge_fund.validation.models import (
    EDUCATIONAL_DISCLAIMER,
    CPCVFold,
    CPCVResult,
    ValidationReport,
)
from hedge_fund.validation.pbo import estimate_pbo

_DEFAULT_NOTES = (
    "Scaffold only: CPCV folds and a PBO hook for a later research lab / "
    "auto-promotion path. This report is not a trading green-light and not "
    "investment advice."
)


def equity_to_returns(equity: np.ndarray | list[float]) -> np.ndarray:
    """Simple period returns from a level series (NAV or equity curve).

    Educational use only. This validation gate is a research scaffold
    (CPCV / PBO hooks), not a trading green-light and not investment advice.
    """
    levels = np.asarray(equity, dtype=float)
    if levels.size < 2:
        raise ValueError("equity/NAV series needs at least 2 points to form returns")
    if np.any(levels[:-1] == 0) or not np.isfinite(levels).all():
        raise ValueError("equity/NAV series must be finite with non-zero lagged levels")
    return np.diff(levels) / levels[:-1]


def returns_from_payload(data: dict[str, Any]) -> tuple[np.ndarray, str]:
    """Pull a 1D return series out of a backtest JSON object.

    Educational use only. This validation gate is a research scaffold
    (CPCV / PBO hooks), not a trading green-light and not investment advice.

    Accepts, in order: ``returns``, per-model ``equity_curve``, fund-level
    ``nav``. Extra keys (trades, records, metrics) are ignored.
    """
    if not isinstance(data, dict):
        raise ValueError("backtest payload must be a JSON object")
    if data.get("returns"):
        arr = np.asarray(data["returns"], dtype=float)
        if arr.ndim != 1:
            raise ValueError("returns must be a 1D array")
        return arr, "returns"
    if data.get("equity_curve"):
        return equity_to_returns(data["equity_curve"]), "equity_curve"
    if data.get("nav"):
        return equity_to_returns(data["nav"]), "fund_nav"
    raise ValueError(
        "payload needs one of: returns, equity_curve, nav "
        "(FundBacktestResult or BacktestResult JSON)"
    )


def load_backtest_returns(path: str | Path) -> tuple[np.ndarray, str]:
    """Load returns from a saved backtest JSON path.

    Educational use only. This validation gate is a research scaffold
    (CPCV / PBO hooks), not a trading green-light and not investment advice.
    """
    raw = Path(path).expanduser().read_text()
    payload = json.loads(raw)
    return returns_from_payload(payload)


def run_validation_gate(
    source: np.ndarray | list[float] | str | Path | dict[str, Any],
    *,
    kind: str | None = None,
    n_groups: int = 6,
    n_test_groups: int = 2,
    purge: int = 1,
    embargo: int = 1,
    pbo_groups: int = 8,
) -> ValidationReport:
    """Score a backtest series with CPCV folds and a PBO hook.

    Educational use only. This validation gate is a research scaffold
    (CPCV / PBO hooks), not a trading green-light and not investment advice.
    A report here does not authorize live capital, auto-promotion, or real trading.

    Parameters
    ----------
    source
        Period returns, an equity/NAV level series, a mapping with
        ``returns`` / ``equity_curve`` / ``nav``, or a path to a saved
        backtest JSON (``FundBacktestResult`` or ``BacktestResult``).
    kind
        When ``source`` is a numeric sequence: ``"returns"`` (default) or
        ``"equity"``. Ignored for paths and mappings.
    n_groups, n_test_groups, purge, embargo
        CPCV split parameters. See ``cpcv_splits``.
    pbo_groups
        Even group count for the PBO CSCV hook.
    """
    returns, source_label = _coerce_returns(source, kind)
    if returns.size < 2:
        raise ValueError("need at least 2 returns to run the validation gate")

    splits = cpcv_splits(
        returns.size,
        n_groups=n_groups,
        n_test_groups=n_test_groups,
        purge=purge,
        embargo=embargo,
    )
    folds: list[CPCVFold] = []
    oos_sharpes: list[float] = []
    empty_train = 0
    for split in splits:
        if split.train_indices.size == 0:
            empty_train += 1
        mean_r, sharpe = fold_test_stats(returns, split)
        if sharpe is not None:
            oos_sharpes.append(sharpe)
        folds.append(
            CPCVFold(
                fold_id=split.fold_id,
                test_groups=list(split.test_groups),
                n_train=int(split.train_indices.size),
                n_test=int(split.test_indices.size),
                n_purged=int(split.purged_indices.size),
                n_embargoed=int(split.embargoed_indices.size),
                test_mean_return=mean_r,
                test_sharpe=sharpe,
            )
        )

    mean_oos = float(np.mean(oos_sharpes)) if oos_sharpes else None
    cpcv = CPCVResult(
        n_groups=n_groups,
        n_test_groups=n_test_groups,
        n_folds=len(folds),
        purge=purge,
        embargo=embargo,
        folds=folds,
        mean_oos_sharpe=mean_oos,
        n_empty_train_folds=empty_train,
    )
    pbo = estimate_pbo(returns, n_groups=pbo_groups)

    return ValidationReport(
        disclaimer=EDUCATIONAL_DISCLAIMER,
        educational_only=True,
        is_trading_green_light=False,
        n_returns=int(returns.size),
        source=source_label,
        cpcv=cpcv,
        pbo=pbo,
        notes=[_DEFAULT_NOTES],
    )


def _coerce_returns(
    source: np.ndarray | list[float] | str | Path | dict[str, Any],
    kind: str | None,
) -> tuple[np.ndarray, str]:
    if isinstance(source, (str, Path)):
        return load_backtest_returns(source)
    if isinstance(source, dict):
        return returns_from_payload(source)
    arr = np.asarray(source, dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"numeric source must be 1D, got shape {arr.shape}")
    label = kind or "returns"
    if label == "equity":
        return equity_to_returns(arr), "equity_curve"
    if label != "returns":
        raise ValueError(f"kind must be 'returns' or 'equity', got {kind!r}")
    return arr, "returns"
