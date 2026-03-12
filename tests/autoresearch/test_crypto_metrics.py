"""Tests for autoresearch.crypto_metrics."""

import numpy as np
import pandas as pd
import pytest

from autoresearch.crypto_metrics import (
    compute_all_crypto_metrics,
    compute_calmar_tuw,
    compute_capture_ratios,
    compute_regime_hit_rate,
    compute_rolling_stability,
    compute_skew_kurtosis,
    compute_turnover_adjusted_alpha,
    compute_ulcer_metrics,
    compute_var_cvar,
)


def test_compute_calmar_tuw_empty():
    r = pd.Series(dtype=float)
    out = compute_calmar_tuw(r)
    assert out["calmar"] == 0.0
    assert out["tuw_pct"] == 0.0


def test_compute_calmar_tuw_positive_returns():
    r = pd.Series([0.01] * 252, index=pd.date_range("2024-01-01", periods=252, freq="B"))
    out = compute_calmar_tuw(r)
    # No drawdown -> calmar is 0 (division by zero guarded)
    assert out["calmar"] >= 0
    assert out["tuw_pct"] == 0.0  # no drawdown


def test_compute_calmar_tuw_with_drawdown():
    # Up then down then up -> has drawdown, positive calmar
    r = pd.Series([0.02] * 50 + [-0.01] * 50 + [0.02] * 152, index=pd.date_range("2024-01-01", periods=252, freq="B"))
    out = compute_calmar_tuw(r)
    assert out["calmar"] > 0
    assert out["tuw_pct"] > 0


def test_compute_ulcer_metrics():
    r = pd.Series([0.01, -0.02, -0.01, 0.02], index=pd.date_range("2024-01-01", periods=4, freq="B"))
    out = compute_ulcer_metrics(r)
    assert "ulcer_index" in out
    assert "ulcer_perf_index" in out
    assert out["ulcer_index"] >= 0


def test_compute_var_cvar():
    np.random.seed(42)
    r = pd.Series(np.random.randn(500) * 0.02, index=pd.date_range("2024-01-01", periods=500, freq="B"))
    out = compute_var_cvar(r)
    assert out["var95_pct"] < 0
    assert out["var99_pct"] < 0
    assert out["cvar95_pct"] < 0
    assert out["cvar99_pct"] < 0


def test_compute_skew_kurtosis():
    r = pd.Series([0.01] * 100 + [-0.05], index=pd.date_range("2024-01-01", periods=101, freq="B"))
    out = compute_skew_kurtosis(r)
    assert "skew" in out
    assert "kurtosis" in out


def test_compute_regime_hit_rate():
    dates = pd.date_range("2024-01-01", periods=50, freq="B")
    direction = pd.Series(["bull", "bear"] * 25, index=dates)
    fwd5 = pd.Series(np.random.randn(50) * 0.01, index=dates)
    fwd10 = pd.Series(np.random.randn(50) * 0.01, index=dates)
    out = compute_regime_hit_rate(direction, fwd5, fwd10)
    assert 0 <= out["hit_rate_5d"] <= 100
    assert 0 <= out["hit_rate_10d"] <= 100


def test_compute_turnover_adjusted_alpha():
    assert compute_turnover_adjusted_alpha(10, 2, 1) == 8.0
    assert compute_turnover_adjusted_alpha(0, 0, 0) == 0.0


def test_compute_capture_ratios():
    dates = pd.date_range("2024-01-01", periods=100, freq="B")
    port = pd.Series(np.random.randn(100) * 0.02, index=dates)
    bench = pd.Series(np.random.randn(100) * 0.015, index=dates)
    out = compute_capture_ratios(port, bench)
    assert "up_capture" in out
    assert "down_capture" in out


def test_compute_rolling_stability():
    r = pd.Series(np.random.randn(200) * 0.01, index=pd.date_range("2024-01-01", periods=200, freq="B"))
    out = compute_rolling_stability(r, windows=(60, 90))
    assert "roll60_sharpe_mean" in out
    assert "roll90_sharpe_mean" in out


def test_compute_all_crypto_metrics():
    r = pd.Series(np.random.randn(300) * 0.01, index=pd.date_range("2024-01-01", periods=300, freq="B"))
    out = compute_all_crypto_metrics(r)
    assert "calmar" in out
    assert "ulcer_index" in out
    assert "var95_pct" in out
    assert "skew" in out
    assert "roll60_sharpe_mean" in out


def test_compute_all_crypto_metrics_with_benchmark():
    r = pd.Series(np.random.randn(300) * 0.01, index=pd.date_range("2024-01-01", periods=300, freq="B"))
    bench = pd.Series(np.random.randn(300) * 0.01, index=r.index)
    out = compute_all_crypto_metrics(r, benchmark_returns=bench)
    assert "up_capture" in out
    assert "down_capture" in out
