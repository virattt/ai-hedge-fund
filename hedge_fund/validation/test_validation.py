"""Offline tests for the CPCV / PBO validation-gate scaffold.

Synthetic returns only — no live APIs, no market data.
"""

from __future__ import annotations

import json
from math import comb
from pathlib import Path

import numpy as np
import pytest

from hedge_fund.validation import (
    EDUCATIONAL_DISCLAIMER,
    cpcv_splits,
    estimate_pbo,
    run_validation_gate,
)
from hedge_fund.validation.__main__ import main as validation_main
from hedge_fund.validation.cpcv import assign_groups
from hedge_fund.validation.gate import equity_to_returns, returns_from_payload
from hedge_fund.validation.models import ValidationReport

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "ledger" / "backtest_result.json"


def _iid_returns(n: int = 120, seed: int = 0, mean: float = 0.001, vol: float = 0.01) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.normal(mean, vol, n)


# ---------------------------------------------------------------------------
# CPCV splits
# ---------------------------------------------------------------------------


class TestCPCVSplits:
    def test_fold_count_is_combinations(self):
        n_groups, n_test = 6, 2
        splits = cpcv_splits(120, n_groups=n_groups, n_test_groups=n_test, purge=1, embargo=1)
        assert len(splits) == comb(n_groups, n_test)
        assert {s.fold_id for s in splits} == set(range(len(splits)))

    def test_groups_cover_every_index(self):
        groups = assign_groups(100, 8)
        assert groups.shape == (100,)
        assert set(groups.tolist()) == set(range(8))
        # Contiguous: group ids never go backwards.
        assert all(groups[i] <= groups[i + 1] for i in range(len(groups) - 1))

    def test_train_and_test_never_overlap(self):
        splits = cpcv_splits(90, n_groups=6, n_test_groups=2, purge=2, embargo=2)
        for split in splits:
            train = set(split.train_indices.tolist())
            test = set(split.test_indices.tolist())
            purged = set(split.purged_indices.tolist())
            embargoed = set(split.embargoed_indices.tolist())
            assert train.isdisjoint(test)
            assert train.isdisjoint(purged)
            assert train.isdisjoint(embargoed)
            assert test.isdisjoint(purged)
            assert test.isdisjoint(embargoed)
            assert purged.isdisjoint(embargoed)

    def test_purge_and_embargo_leave_a_gap(self):
        purge, embargo = 3, 2
        splits = cpcv_splits(60, n_groups=6, n_test_groups=1, purge=purge, embargo=embargo)
        # One test group per fold — a single contiguous block.
        for split in splits:
            test = split.test_indices
            lo, hi = int(test.min()), int(test.max()) + 1
            train = set(split.train_indices.tolist())
            for i in range(max(0, lo - purge), lo):
                assert i not in train
            for i in range(hi, min(60, hi + embargo)):
                assert i not in train
            assert int(split.purged_indices.size) == (0 if lo == 0 else min(purge, lo))
            assert int(split.embargoed_indices.size) == (0 if hi == 60 else min(embargo, 60 - hi))

    def test_adjacent_test_groups_share_one_purge_window(self):
        # Groups 0 and 1 are adjacent; purge should not fire between them.
        splits = cpcv_splits(60, n_groups=6, n_test_groups=2, purge=2, embargo=2)
        adjacent = next(s for s in splits if s.test_groups == (0, 1))
        # First two groups are the test block; no interior purge.
        test = set(adjacent.test_indices.tolist())
        assert adjacent.purged_indices.size == 0  # block starts at 0
        assert test.isdisjoint(set(adjacent.train_indices.tolist()))

    def test_rejects_bad_parameters(self):
        with pytest.raises(ValueError, match="n_groups"):
            cpcv_splits(10, n_groups=1)
        with pytest.raises(ValueError, match="n_test_groups"):
            cpcv_splits(10, n_groups=4, n_test_groups=4)
        with pytest.raises(ValueError, match="purge"):
            cpcv_splits(10, n_groups=4, n_test_groups=1, purge=-1)


# ---------------------------------------------------------------------------
# PBO hook
# ---------------------------------------------------------------------------


class TestPBO:
    def test_single_trial_is_documented_heuristic(self):
        result = estimate_pbo(_iid_returns(80, seed=1), n_groups=8)
        assert result.n_trials == 1
        assert result.method == "heuristic_is_oos_sharpe_decay"
        assert result.n_combinations == comb(8, 4)
        assert result.probability is None or 0.0 <= result.probability <= 1.0
        assert "not Bailey" in result.limitations
        assert "green-light" in result.limitations.lower()

    def test_multi_trial_rank_pbo_range(self):
        rng = np.random.default_rng(2)
        # Two independent trials — rank PBO is defined and in [0, 1].
        trials = rng.normal(0.0, 0.01, size=(80, 3))
        result = estimate_pbo(trials, n_groups=8)
        assert result.n_trials == 3
        assert result.method == "cscv_rank"
        assert result.probability is not None
        assert 0.0 <= result.probability <= 1.0
        assert "green-light" in result.limitations.lower()

    def test_overfit_winner_scores_high(self):
        rng = np.random.default_rng(3)
        n = 80
        noise = rng.normal(0.0, 0.01, size=(n, 2))
        # Trial 0 looks great in the first half, dies in the second.
        # Trial 1 is flat noise. IS-half combinations that overweight the
        # first half will pick trial 0, which then ranks poorly OOS.
        trials = noise.copy()
        trials[:40, 0] += 0.05
        trials[40:, 0] -= 0.05
        result = estimate_pbo(trials, n_groups=8)
        assert result.method == "cscv_rank"
        assert result.probability is not None
        assert result.probability > 0.0


# ---------------------------------------------------------------------------
# Gate
# ---------------------------------------------------------------------------


class TestValidationGate:
    def test_report_structure_and_disclaimer(self):
        returns = _iid_returns(120)
        report = run_validation_gate(returns, n_groups=6, n_test_groups=2, purge=1, embargo=1)
        assert isinstance(report, ValidationReport)
        assert report.disclaimer == EDUCATIONAL_DISCLAIMER
        assert "not a trading green-light" in report.disclaimer
        assert "not investment advice" in report.disclaimer
        assert report.educational_only is True
        assert report.is_trading_green_light is False
        assert report.source == "returns"
        assert report.n_returns == 120
        assert report.cpcv.n_folds == comb(6, 2)
        assert len(report.cpcv.folds) == report.cpcv.n_folds
        assert report.pbo.n_trials == 1
        assert any("not a trading green-light" in n for n in report.notes)

    def test_equity_curve_kind(self):
        equity = np.cumprod(1.0 + _iid_returns(61, seed=4))
        equity = np.concatenate([[1.0], equity])
        report = run_validation_gate(equity, kind="equity", n_groups=6, pbo_groups=8)
        assert report.source == "equity_curve"
        assert report.n_returns == 61
        assert report.is_trading_green_light is False

    def test_fund_nav_payload(self):
        nav = np.linspace(100_000.0, 110_000.0, 40).tolist()
        payload = {
            "fund": "alpha-one",
            "nav": nav,
            "metrics": {"sharpe_ratio": 1.0},
        }
        report = run_validation_gate(payload, n_groups=4, n_test_groups=1, pbo_groups=4)
        assert report.source == "fund_nav"
        assert report.n_returns == 39

    def test_per_model_equity_curve_payload(self):
        payload = {"equity_curve": [100.0, 101.0, 100.5, 102.0] + [102.0 + i * 0.1 for i in range(20)]}
        report = run_validation_gate(payload, n_groups=4, n_test_groups=1, pbo_groups=4)
        assert report.source == "equity_curve"

    def test_returns_from_payload_order(self):
        data = {"returns": [0.01, -0.01], "nav": [100.0, 110.0], "equity_curve": [1.0, 2.0]}
        arr, label = returns_from_payload(data)
        assert label == "returns"
        np.testing.assert_allclose(arr, [0.01, -0.01])

    def test_equity_to_returns(self):
        np.testing.assert_allclose(equity_to_returns([100.0, 110.0, 99.0]), [0.1, -0.1])

    def test_saved_json_path(self, tmp_path: Path):
        path = tmp_path / "bt.json"
        path.write_text(json.dumps({"returns": _iid_returns(48, seed=5).tolist()}))
        report = run_validation_gate(path, n_groups=6, n_test_groups=2, pbo_groups=6)
        assert report.source == "returns"
        assert report.n_returns == 48

    def test_one_point_nav_fixture_fails_loud(self):
        with pytest.raises(ValueError, match="at least 2"):
            run_validation_gate(FIXTURE)

    def test_short_series_fails_loud(self):
        with pytest.raises(ValueError):
            run_validation_gate([0.01], kind="returns")

    def test_public_entry_points_document_disclaimer(self):
        for fn in (run_validation_gate, cpcv_splits, estimate_pbo, equity_to_returns):
            assert fn.__doc__ is not None
            assert "Educational use only" in fn.__doc__
            assert "not a trading green-light" in fn.__doc__


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class TestCLI:
    def test_cli_writes_report_json(self, tmp_path: Path, capsys):
        path = tmp_path / "curve.json"
        path.write_text(json.dumps({"nav": np.linspace(100.0, 120.0, 50).tolist()}))
        code = validation_main([str(path), "--n-groups", "5", "--n-test-groups", "1", "--pbo-groups", "4"])
        assert code == 0
        captured = capsys.readouterr()
        assert EDUCATIONAL_DISCLAIMER in captured.err
        report = ValidationReport.model_validate_json(captured.out)
        assert report.is_trading_green_light is False
        assert report.source == "fund_nav"
        assert report.cpcv.n_folds == 5

    def test_cli_missing_file(self, tmp_path: Path, capsys):
        code = validation_main([str(tmp_path / "missing.json")])
        assert code == 2
        assert "not a file" in capsys.readouterr().err
