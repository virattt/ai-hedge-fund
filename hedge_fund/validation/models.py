"""Report types for the validation-gate scaffold.

Educational use only. This validation gate is a research scaffold
(CPCV / PBO hooks), not a trading green-light and not investment advice.
A report here does not authorize live capital, auto-promotion, or real trading.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

EDUCATIONAL_DISCLAIMER = (
    "Educational use only. This validation gate is a research scaffold "
    "(CPCV / PBO hooks), not a trading green-light and not investment advice. "
    "A report here does not authorize live capital, auto-promotion, or real trading."
)


class CPCVFold(BaseModel):
    """One combinatorial purged CV fold — split summary plus test-set stats.

    Train/test index lists stay off the report (they can be large). The
    split helper returns the actual indices for callers that need them.
    """

    fold_id: int
    test_groups: list[int]
    n_train: int
    n_test: int
    n_purged: int
    n_embargoed: int
    test_mean_return: float | None = None
    test_sharpe: float | None = None


class CPCVResult(BaseModel):
    """Combinatorial purged cross-validation over a 1D return series.

    ``n_folds`` is C(n_groups, n_test_groups). This is a structural
    scaffold — not a research-grade clone of any single paper.
    """

    n_groups: int
    n_test_groups: int
    n_folds: int
    purge: int
    embargo: int
    folds: list[CPCVFold] = Field(default_factory=list)
    mean_oos_sharpe: float | None = None
    n_empty_train_folds: int = 0


class PBOResult(BaseModel):
    """Probability of backtest overfitting hook.

    With two or more trial columns this is a tiny CSCV rank estimator
    (Bailey / López de Prado style). A single backtest series cannot
    rank competing trials, so the gate fills a documented heuristic
    instead — not the textbook PBO number.
    """

    probability: float | None = None
    method: str
    n_trials: int
    n_combinations: int = 0
    limitations: str
    notes: str = ""


class ValidationReport(BaseModel):
    """Structured output of ``run_validation_gate``.

    ``is_trading_green_light`` is always False. Passing CPCV folds or a
    PBO number here is not a license to trade, promote a strategy, or
    treat the backtest as out-of-sample truth.
    """

    disclaimer: str = EDUCATIONAL_DISCLAIMER
    educational_only: bool = True
    is_trading_green_light: bool = False
    n_returns: int
    source: str
    cpcv: CPCVResult
    pbo: PBOResult
    notes: list[str] = Field(default_factory=list)
