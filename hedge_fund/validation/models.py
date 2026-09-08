"""Pydantic models for the CPCV / PBO validation report.

    ValidationSplit  \u2014 one train/test combination out of CPCV: which groups
                       were held out, what was purged/embargoed, which
                       candidate won in-sample, and how it did out-of-sample.
    ValidationReport \u2014 top-level container returned by validate_candidates().
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ValidationSplit(BaseModel):
    """One combinatorial train/test split.

    `test_group_indices` names which of the `n_groups` chronological blocks
    were held out as the test set for this split; the rest (minus anything
    purged or embargoed) formed the training set. `selected_candidate` is
    whichever candidate scored best on `in_sample_performance` \u2014 the model
    selection a real backtest-picking process would have made seeing only
    the training data. `out_sample_performance` is what *every* candidate
    actually did on the held-out data, so `selected_out_sample_rank` shows
    where the in-sample winner really landed.
    """

    model_config = ConfigDict(extra="forbid")

    split_index: int = Field(description="0-based index into the enumerated combinations")
    test_group_indices: list[int] = Field(description="which of the n_groups blocks were held out")
    train_dates: list[str] = Field(description="dates used for in-sample selection, sorted")
    test_dates: list[str] = Field(description="held-out dates scored out-of-sample, sorted")
    purged_dates: list[str] = Field(
        default_factory=list,
        description="training dates dropped because they fell within purge_periods of a test block",
    )
    embargoed_dates: list[str] = Field(
        default_factory=list,
        description="training dates dropped because they fell within embargo_periods after a test block",
    )
    in_sample_performance: dict[str, float] = Field(
        description="each candidate's Sharpe ratio computed on train_dates only"
    )
    out_sample_performance: dict[str, float] = Field(
        description="each candidate's Sharpe ratio computed on test_dates only"
    )
    selected_candidate: str = Field(description="the in-sample winner for this split")
    selected_out_sample_performance: float = Field(
        description="the in-sample winner's Sharpe ratio on test_dates"
    )
    selected_out_sample_rank: float = Field(
        description="rank (1=worst .. n_candidates=best) of the winner's out-of-sample "
        "performance among all candidates; ties share the average rank"
    )
    relative_rank: float = Field(description="selected_out_sample_rank / (n_candidates + 1)")
    logit: float = Field(description="ln(relative_rank / (1 - relative_rank))")


class ValidationReport(BaseModel):
    """Full CPCV / PBO report \u2014 serializable, `model_dump_json()` round-trips.

    `pbo` is the fraction of splits where the in-sample winner landed at or
    below the out-of-sample median (logit <= 0) \u2014 the empirical estimate of
    the Probability of Backtest Overfitting from Bailey, Borwein, Lopez de
    Prado & Zhu (2014). 0.0 means the in-sample winner was never a median-
    or-worse out-of-sample performer; 1.0 means it always was.
    """

    model_config = ConfigDict(extra="forbid")

    candidates: list[str] = Field(description="candidate names, sorted")
    n_periods: int
    n_groups: int
    n_test_groups: int
    purge_periods: int
    embargo_periods: int
    metric: str = Field(default="sharpe_ratio", description="performance metric used for selection and ranking")
    splits: list[ValidationSplit] = Field(default_factory=list)
    selection_counts: dict[str, int] = Field(
        default_factory=dict,
        description="how many splits picked each candidate as the in-sample winner",
    )
    pbo: float = Field(description="Probability of Backtest Overfitting, in [0, 1]")
