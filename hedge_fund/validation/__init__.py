"""CPCV / PBO validation framework.

Fund backtests report full-sample performance, which says nothing about
whether picking the best-looking strategy overfit the backtest period. This
package answers that with:

    Combinatorial Purged Cross-Validation (CPCV) \u2014 chronological folds with
    purging and embargo so training data can never leak into an evaluation
    period, enumerated combinatorially (every way to hold out n_test_groups
    of n_groups blocks) rather than a single train/test split.

    Probability of Backtest Overfitting (PBO) \u2014 across every CPCV split, how
    often would the in-sample winner have been a below-median performer
    out-of-sample? (Bailey, Borwein, Lopez de Prado & Zhu, 2014.)

    from hedge_fund.validation import validate_candidates, load_candidates

    candidates = load_candidates({"a": "a-backtest.json", "b": "b-backtest.json"})
    report = validate_candidates(candidates)
    print(report.pbo)
"""

from hedge_fund.validation.engine import validate_candidates
from hedge_fund.validation.io import load_backtest_result, load_candidates
from hedge_fund.validation.models import ValidationReport, ValidationSplit
from hedge_fund.validation.stats import (
    CPCVSplit,
    chronological_groups,
    generate_cpcv_splits,
    periodic_returns,
    probability_of_backtest_overfitting,
    relative_rank_and_logit,
    select_best,
    sharpe_ratio,
)

__all__ = [
    "validate_candidates",
    "load_backtest_result",
    "load_candidates",
    "ValidationReport",
    "ValidationSplit",
    "CPCVSplit",
    "chronological_groups",
    "generate_cpcv_splits",
    "periodic_returns",
    "probability_of_backtest_overfitting",
    "relative_rank_and_logit",
    "select_best",
    "sharpe_ratio",
]
