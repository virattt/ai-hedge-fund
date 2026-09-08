"""Tests for CPCV / PBO validation \u2014 stats, engine, and models."""

from __future__ import annotations

import itertools
import json

import numpy as np
import pytest

from hedge_fund.backtesting.fund import FundBacktestMetrics, FundBacktestResult
from hedge_fund.validation import (
    ValidationReport,
    generate_cpcv_splits,
    load_backtest_result,
    load_candidates,
    periodic_returns,
    probability_of_backtest_overfitting,
    relative_rank_and_logit,
    select_best,
    sharpe_ratio,
    validate_candidates,
)
from hedge_fund.validation.stats import chronological_groups


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

CAPITAL = 100_000.0


def _dates(n: int) -> list[str]:
    dates = []
    for i in range(n):
        month = i // 4 + 1
        day = (i % 4) * 7 + 1
        dates.append(f"2024-{month:02d}-{day:02d}")
    return dates


def _nav_from_returns(returns: list[float]) -> list[float]:
    nav = []
    equity = CAPITAL
    for r in returns:
        equity = equity * (1 + r)
        nav.append(equity)
    return nav


def _result(name: str, n: int = 12, returns: list[float] | None = None,
            capital: float = CAPITAL, rebalance: str = "weekly",
            dates: list[str] | None = None) -> FundBacktestResult:
    dates = dates if dates is not None else _dates(n)
    if returns is None:
        returns = [0.01] * n
    nav = _nav_from_returns(returns)
    metrics = FundBacktestMetrics(
        total_return_pct=nav[-1] / capital - 1,
        annualized_return_pct=0.0,
        sharpe_ratio=0.0,
        max_drawdown_pct=0.0,
        benchmark_return_pct=0.0,
        excess_return_pct=0.0,
        n_cycles=len(dates),
        n_orders=0,
    )
    return FundBacktestResult(
        fund=name, start=dates[0], end=dates[-1], rebalance=rebalance,
        benchmark="SPY", universe=["AAPL"], capital=capital,
        dates=dates, nav=nav, benchmark_nav=nav,
        metrics=metrics, records=[],
    )


def _rng_returns(n: int, mu: float, sigma: float, seed: int) -> list[float]:
    return list(np.random.default_rng(seed).normal(mu, sigma, n))


# ---------------------------------------------------------------------------
# stats.py \u2014 pure functions
# ---------------------------------------------------------------------------

class TestPeriodicReturns:
    def test_matches_fund_metrics_convention(self):
        nav = [110_000.0, 99_000.0, 108_900.0]
        returns = periodic_returns(100_000.0, nav)
        np.testing.assert_allclose(returns, [0.10, -0.10, 0.10])

    def test_length_matches_nav(self):
        nav = [101.0, 102.0, 103.0, 104.0]
        assert len(periodic_returns(100.0, nav)) == len(nav)


class TestSharpeRatio:
    def test_zero_for_single_observation(self):
        assert sharpe_ratio(np.array([0.05]), 52) == 0.0

    def test_zero_for_zero_variance(self):
        assert sharpe_ratio(np.array([0.01, 0.01, 0.01]), 52) == 0.0

    def test_zero_for_empty(self):
        assert sharpe_ratio(np.array([]), 52) == 0.0

    def test_positive_for_positive_drift(self):
        returns = np.array([0.02, 0.01, 0.03, 0.015, 0.025])
        assert sharpe_ratio(returns, 52) > 0

    def test_negative_for_negative_drift(self):
        returns = np.array([-0.02, -0.01, -0.03, -0.015, -0.025])
        assert sharpe_ratio(returns, 52) < 0


class TestChronologicalGroups:
    def test_even_split(self):
        groups = chronological_groups(12, 6)
        assert [len(g) for g in groups] == [2] * 6
        assert np.concatenate(groups).tolist() == list(range(12))

    def test_uneven_split_front_loads_extra(self):
        groups = chronological_groups(14, 6)
        assert [len(g) for g in groups] == [3, 3, 2, 2, 2, 2]

    def test_rejects_too_few_groups(self):
        with pytest.raises(ValueError):
            chronological_groups(10, 1)

    def test_rejects_more_groups_than_periods(self):
        with pytest.raises(ValueError):
            chronological_groups(3, 6)


class TestGenerateCPCVSplits:
    def test_number_of_combinations(self):
        splits = generate_cpcv_splits(60, 6, 2, purge_periods=0, embargo_periods=0)
        assert len(splits) == 15  # C(6, 2)

    def test_train_test_partition_no_overlap(self):
        for split in generate_cpcv_splits(60, 6, 2, purge_periods=1, embargo_periods=1):
            assert set(split.train_idx.tolist()) & set(split.test_idx.tolist()) == set()
            assert set(split.train_idx.tolist()) & set(split.purged_idx.tolist()) == set()
            assert set(split.train_idx.tolist()) & set(split.embargoed_idx.tolist()) == set()

    def test_purge_and_embargo_shrink_training_set(self):
        no_purge = generate_cpcv_splits(60, 6, 1, purge_periods=0, embargo_periods=0)[0]
        purged = generate_cpcv_splits(60, 6, 1, purge_periods=2, embargo_periods=3)[0]
        assert len(purged.train_idx) < len(no_purge.train_idx)
        assert len(purged.purged_idx) > 0
        assert len(purged.embargoed_idx) > 0

    def test_zero_purge_and_embargo_is_a_pure_complement(self):
        splits = generate_cpcv_splits(30, 5, 1, purge_periods=0, embargo_periods=0)
        for split in splits:
            assert len(split.train_idx) + len(split.test_idx) == 30
            assert len(split.purged_idx) == 0
            assert len(split.embargoed_idx) == 0

    def test_embargo_only_follows_test_block_forward(self):
        # 6 groups of 10, test group index 2 -> periods [20, 29].
        splits = generate_cpcv_splits(60, 6, 1, purge_periods=0, embargo_periods=5)
        split = next(s for s in splits if s.test_group_indices == (2,))
        assert split.embargoed_idx.tolist() == [30, 31, 32, 33, 34]
        assert 19 in split.train_idx  # nothing purged before the block (purge=0)

    def test_non_adjacent_test_groups_purge_independently(self):
        # groups 0 and 3 of 6x10 are not adjacent -> two separate purge zones.
        splits = generate_cpcv_splits(60, 6, 2, purge_periods=2, embargo_periods=0)
        split = next(s for s in splits if s.test_group_indices == (0, 3))
        # block 1: [0, 9], block 2: [30, 39]
        assert 10 in split.purged_idx and 11 in split.purged_idx
        assert 8 not in split.purged_idx  # inside the test block itself, not purged
        assert 28 in split.purged_idx and 29 in split.purged_idx
        assert 40 in split.purged_idx and 41 in split.purged_idx

    def test_rejects_n_test_groups_out_of_range(self):
        with pytest.raises(ValueError):
            generate_cpcv_splits(60, 6, 0, purge_periods=0, embargo_periods=0)
        with pytest.raises(ValueError):
            generate_cpcv_splits(60, 6, 6, purge_periods=0, embargo_periods=0)

    def test_rejects_negative_purge_or_embargo(self):
        with pytest.raises(ValueError):
            generate_cpcv_splits(60, 6, 2, purge_periods=-1, embargo_periods=0)
        with pytest.raises(ValueError):
            generate_cpcv_splits(60, 6, 2, purge_periods=0, embargo_periods=-1)

    def test_deterministic_ordering(self):
        a = generate_cpcv_splits(60, 6, 2, 1, 1)
        b = generate_cpcv_splits(60, 6, 2, 1, 1)
        assert [s.test_group_indices for s in a] == [s.test_group_indices for s in b]
        assert [s.test_group_indices for s in a] == sorted(
            itertools.combinations(range(6), 2)
        )


class TestSelectBest:
    def test_picks_highest(self):
        assert select_best({"a": 0.1, "b": 0.5, "c": -0.2}) == "b"

    def test_tie_breaks_alphabetically(self):
        assert select_best({"zeta": 1.0, "alpha": 1.0, "mid": 1.0}) == "alpha"

    def test_single_candidate(self):
        assert select_best({"solo": 0.3}) == "solo"


class TestRelativeRankAndLogit:
    def test_best_gets_positive_logit(self):
        perf = {"a": 1.0, "b": 2.0, "c": 3.0}
        rank, rel, logit = relative_rank_and_logit(perf, "c", ["a", "b", "c"])
        assert rank == 3.0
        assert rel == pytest.approx(0.75)
        assert logit > 0

    def test_worst_gets_negative_logit(self):
        perf = {"a": 1.0, "b": 2.0, "c": 3.0}
        rank, rel, logit = relative_rank_and_logit(perf, "a", ["a", "b", "c"])
        assert rank == 1.0
        assert logit < 0

    def test_ties_share_average_rank(self):
        perf = {"a": 1.0, "b": 1.0, "c": 3.0}
        rank_a, _, _ = relative_rank_and_logit(perf, "a", ["a", "b", "c"])
        rank_b, _, _ = relative_rank_and_logit(perf, "b", ["a", "b", "c"])
        assert rank_a == rank_b == 1.5


class TestProbabilityOfBacktestOverfitting:
    def test_all_below_median(self):
        assert probability_of_backtest_overfitting([-1.0, -0.5, 0.0]) == 1.0

    def test_all_above_median(self):
        assert probability_of_backtest_overfitting([0.1, 0.2, 0.3]) == 0.0

    def test_mixed(self):
        assert probability_of_backtest_overfitting([-1.0, 1.0]) == pytest.approx(0.5)

    def test_empty_is_zero(self):
        assert probability_of_backtest_overfitting([]) == 0.0


# ---------------------------------------------------------------------------
# engine.py \u2014 validate_candidates
# ---------------------------------------------------------------------------

class TestValidateCandidatesCompatibility:
    def test_rejects_single_candidate(self):
        with pytest.raises(ValueError, match="at least 2"):
            validate_candidates({"only": _result("only")})

    def test_rejects_mismatched_dates(self):
        a = _result("a", dates=_dates(12))
        b = _result("b", dates=_dates(11) + ["2025-01-01"])
        with pytest.raises(ValueError, match="incompatible dates"):
            validate_candidates({"a": a, "b": b})

    def test_rejects_mismatched_rebalance(self):
        a = _result("a", rebalance="weekly")
        b = _result("b", rebalance="daily")
        with pytest.raises(ValueError, match="rebalance"):
            validate_candidates({"a": a, "b": b})

    def test_rejects_mismatched_capital(self):
        a = _result("a", capital=100_000.0)
        b = _result("b", capital=50_000.0)
        with pytest.raises(ValueError, match="capital"):
            validate_candidates({"a": a, "b": b})

    def test_rejects_nan_nav(self):
        a = _result("a")
        b = _result("b")
        b.nav[3] = float("nan")
        with pytest.raises(ValueError, match="non-finite"):
            validate_candidates({"a": a, "b": b})

    def test_rejects_infinite_nav(self):
        a = _result("a")
        b = _result("b")
        b.nav[3] = float("inf")
        with pytest.raises(ValueError, match="non-finite"):
            validate_candidates({"a": a, "b": b})

    def test_rejects_non_positive_nav(self):
        a = _result("a")
        b = _result("b")
        b.nav[0] = 0.0
        with pytest.raises(ValueError, match="positive"):
            validate_candidates({"a": a, "b": b})

    def test_rejects_non_positive_capital(self):
        a = _result("a", capital=100_000.0)
        b = _result("b", capital=100_000.0)
        b.capital = -1.0
        with pytest.raises(ValueError, match="capital"):
            validate_candidates({"a": a, "b": b})

    def test_rejects_too_few_periods_for_groups(self):
        a = _result("a", n=3)
        b = _result("b", n=3)
        with pytest.raises(ValueError):
            validate_candidates({"a": a, "b": b}, n_groups=6)

    def test_rejects_bad_n_test_groups(self):
        a = _result("a", n=12)
        b = _result("b", n=12)
        with pytest.raises(ValueError):
            validate_candidates({"a": a, "b": b}, n_groups=6, n_test_groups=6)


class TestValidateCandidatesBehavior:
    def test_report_shape(self):
        candidates = {
            "a": _result("a", n=24, returns=_rng_returns(24, 0.01, 0.02, 1)),
            "b": _result("b", n=24, returns=_rng_returns(24, 0.0, 0.02, 2)),
        }
        report = validate_candidates(
            candidates, n_groups=6, n_test_groups=2,
            purge_periods=1, embargo_periods=1,
        )
        assert isinstance(report, ValidationReport)
        assert report.candidates == ["a", "b"]
        assert report.n_periods == 24
        assert len(report.splits) == 15  # C(6, 2)
        assert 0.0 <= report.pbo <= 1.0
        assert set(report.selection_counts) == {"a", "b"}
        assert sum(report.selection_counts.values()) == len(report.splits)
        for split in report.splits:
            assert split.selected_candidate in ("a", "b")
            assert split.selected_out_sample_performance == pytest.approx(
                split.out_sample_performance[split.selected_candidate]
            )
            # every date accounted for exactly once across train/test/purge/embargo
            all_dates = (split.train_dates + split.test_dates
                         + split.purged_dates + split.embargoed_dates)
            assert len(all_dates) == 24
            assert len(set(all_dates)) == 24

    def test_dominant_strategy_has_low_pbo(self):
        # "good" clearly and consistently beats the others in every regime.
        n = 60
        candidates = {
            "good": _result("good", n=n, returns=_rng_returns(n, 0.01, 0.01, 1)),
            "bad": _result("bad", n=n, returns=_rng_returns(n, -0.01, 0.01, 2)),
            "worse": _result("worse", n=n, returns=_rng_returns(n, -0.02, 0.01, 3)),
        }
        report = validate_candidates(candidates)
        assert report.pbo < 0.3
        assert report.selection_counts["good"] == len(report.splits)

    def test_indistinguishable_noise_strategies_are_overfit_prone(self):
        # Same distribution, no real edge -> in-sample winner is coin-flip
        # out-of-sample, so PBO should be substantial (near the ~0.5 chance level).
        n = 120
        candidates = {
            f"noise_{i}": _result(f"noise_{i}", n=n, returns=_rng_returns(n, 0.0, 0.02, i))
            for i in range(5)
        }
        report = validate_candidates(candidates, n_groups=6, n_test_groups=2)
        assert report.pbo > 0.2

    def test_deterministic_across_runs(self):
        candidates = {
            "a": _result("a", n=30, returns=_rng_returns(30, 0.01, 0.02, 7)),
            "b": _result("b", n=30, returns=_rng_returns(30, 0.0, 0.02, 8)),
            "c": _result("c", n=30, returns=_rng_returns(30, -0.01, 0.02, 9)),
        }
        r1 = validate_candidates(candidates)
        r2 = validate_candidates(candidates)
        assert r1 == r2

    def test_ties_pick_alphabetically_first_and_stay_deterministic(self):
        # Identical return streams -> every split is an exact in-sample tie.
        n = 24
        returns = [0.01, -0.005, 0.02, 0.0] * (n // 4)
        candidates = {
            "zzz": _result("zzz", n=n, returns=returns),
            "aaa": _result("aaa", n=n, returns=returns),
            "mmm": _result("mmm", n=n, returns=returns),
        }
        report = validate_candidates(candidates, n_groups=6, n_test_groups=2)
        assert all(s.selected_candidate == "aaa" for s in report.splits)
        # a 3-way exact tie out-of-sample too -> logit is always 0 -> PBO == 1.
        assert report.pbo == 1.0
        for split in report.splits:
            assert split.relative_rank == pytest.approx(0.5)
            assert split.logit == pytest.approx(0.0)

    def test_purge_and_embargo_reduce_available_training_dates(self):
        candidates = {
            "a": _result("a", n=24, returns=_rng_returns(24, 0.01, 0.02, 1)),
            "b": _result("b", n=24, returns=_rng_returns(24, 0.0, 0.02, 2)),
        }
        tight = validate_candidates(candidates, n_groups=6, n_test_groups=1,
                                    purge_periods=0, embargo_periods=0)
        loose = validate_candidates(candidates, n_groups=6, n_test_groups=1,
                                    purge_periods=2, embargo_periods=2)
        assert len(loose.splits[0].train_dates) < len(tight.splits[0].train_dates)
        assert loose.splits[0].purged_dates or loose.splits[0].embargoed_dates

    def test_boundary_n_test_groups_equals_n_groups_minus_one(self):
        candidates = {
            "a": _result("a", n=12, returns=_rng_returns(12, 0.01, 0.02, 1)),
            "b": _result("b", n=12, returns=_rng_returns(12, 0.0, 0.02, 2)),
        }
        report = validate_candidates(candidates, n_groups=4, n_test_groups=3,
                                     purge_periods=0, embargo_periods=0)
        assert len(report.splits) == 4  # C(4, 3)
        for split in report.splits:
            assert len(split.train_dates) > 0

    def test_raises_when_purge_embargo_consume_all_training_data(self):
        candidates = {
            "a": _result("a", n=12, returns=_rng_returns(12, 0.01, 0.02, 1)),
            "b": _result("b", n=12, returns=_rng_returns(12, 0.0, 0.02, 2)),
        }
        with pytest.raises(ValueError, match="no training periods"):
            validate_candidates(candidates, n_groups=4, n_test_groups=1,
                                purge_periods=3, embargo_periods=3)

    def test_report_round_trips_through_json(self):
        candidates = {
            "a": _result("a", n=24, returns=_rng_returns(24, 0.01, 0.02, 1)),
            "b": _result("b", n=24, returns=_rng_returns(24, 0.0, 0.02, 2)),
        }
        report = validate_candidates(candidates)
        payload = report.model_dump_json()
        restored = ValidationReport.model_validate_json(payload)
        assert restored == report
        assert json.loads(payload)["pbo"] == pytest.approx(report.pbo)


# ---------------------------------------------------------------------------
# io.py \u2014 file handling, kept separate from the math
# ---------------------------------------------------------------------------

class TestIO:
    def test_load_backtest_result_round_trips(self, tmp_path):
        result = _result("a", n=6)
        path = tmp_path / "a.json"
        path.write_text(result.model_dump_json())
        loaded = load_backtest_result(path)
        assert loaded == result

    def test_load_candidates_reads_multiple_files(self, tmp_path):
        a = _result("a", n=6)
        b = _result("b", n=6)
        (tmp_path / "a.json").write_text(a.model_dump_json())
        (tmp_path / "b.json").write_text(b.model_dump_json())
        candidates = load_candidates({
            "a": tmp_path / "a.json",
            "b": tmp_path / "b.json",
        })
        assert candidates["a"] == a
        assert candidates["b"] == b

    def test_load_missing_file_fails_loud(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_backtest_result(tmp_path / "missing.json")

    def test_load_invalid_json_fails_loud(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("{not valid json")
        with pytest.raises(Exception):
            load_backtest_result(path)

    def test_end_to_end_from_disk(self, tmp_path):
        a = _result("a", n=24, returns=_rng_returns(24, 0.01, 0.02, 1))
        b = _result("b", n=24, returns=_rng_returns(24, 0.0, 0.02, 2))
        (tmp_path / "a.json").write_text(a.model_dump_json())
        (tmp_path / "b.json").write_text(b.model_dump_json())
        candidates = load_candidates({"a": tmp_path / "a.json", "b": tmp_path / "b.json"})
        report = validate_candidates(candidates)
        assert report.candidates == ["a", "b"]
