"""Statistical functions for event study: OLS, t-test, bootstrap.

All functions are pure (no side effects, no state). They operate on numpy
arrays and return either model objects or raw values. The engine.py module
calls these to do the actual math.
"""

from __future__ import annotations

import numpy as np
from scipy import stats as sp_stats

from v2.event_study.models import BootstrapCI, MarketModelFit


def fit_market_model(
    stock_returns: np.ndarray,
    market_returns: np.ndarray,
) -> MarketModelFit:
    """Fit the market model via OLS: R_stock = alpha + beta * R_market.

    Uses the normal equations (np.linalg.lstsq) with a design matrix
    [1, R_market] to solve for alpha (intercept) and beta (slope).

    R-squared measures how much of the stock's variance is explained
    by market moves. Higher R² = more of the stock's movement is
    "expected" market drift, so abnormal returns are more meaningful.
    """
    n = len(stock_returns)

    # Design matrix: column of 1s (intercept) + market returns (slope)
    X = np.column_stack([np.ones(n), market_returns])

    # Solve the least-squares problem: min ||X·coeffs - stock_returns||²
    coeffs, _, _, _ = np.linalg.lstsq(X, stock_returns, rcond=None)
    alpha, beta = coeffs[0], coeffs[1]

    # R² = 1 - (sum of squared residuals) / (total sum of squares)
    predicted = alpha + beta * market_returns
    ss_res = np.sum((stock_returns - predicted) ** 2)
    ss_tot = np.sum((stock_returns - stock_returns.mean()) ** 2)
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

    return MarketModelFit(alpha=alpha, beta=beta, r_squared=r_squared, n_obs=n)


def compute_abnormal_returns(
    stock_returns: np.ndarray,
    market_returns: np.ndarray,
    alpha: float,
    beta: float,
) -> np.ndarray:
    """Compute abnormal returns: AR_t = R_stock,t - (alpha + beta * R_market,t).

    The "expected" return on day t is what the market model predicts:
    alpha + beta * R_market. Anything above or below that is "abnormal" —
    i.e., not explained by general market movement. On earnings days,
    this abnormal return captures the event's impact.
    """
    return stock_returns - (alpha + beta * market_returns)


def sum_car(daily_ar: np.ndarray, start: int, end: int) -> float:
    """Cumulative Abnormal Return = sum of daily ARs over [start, end].

    For window [0, +1]: sum of AR on day 0 and day 1 (2 trading days).
    For window [0, +5]: sum of AR on days 0 through 5 (6 trading days).
    """
    return float(np.sum(daily_ar[start : end + 1]))


def ttest_cars(cars: np.ndarray) -> tuple[float, float]:
    """One-sample t-test: is the mean CAR significantly different from 0?

    H0: mean CAR = 0 (earnings announcements don't move prices).
    H1: mean CAR ≠ 0 (they do).

    Returns (t_stat, p_value). A small p-value (< 0.05) means we can
    reject H0 — the event type systematically moves prices.
    """
    if len(cars) < 2:
        return 0.0, 1.0
    t_stat, p_value = sp_stats.ttest_1samp(cars, popmean=0.0)
    return float(t_stat), float(p_value)


def bootstrap_ci(
    cars: np.ndarray,
    n_bootstrap: int = 10_000,
    confidence: float = 0.95,
    rng_seed: int | None = None,
) -> BootstrapCI:
    """Percentile bootstrap confidence interval for mean CAR.

    How it works:
    1. Resample the observed CARs with replacement (same size as original).
    2. Compute the mean of each resample.
    3. Repeat 10,000 times → distribution of possible means.
    4. Take the 2.5th and 97.5th percentiles → 95% CI.

    If the CI doesn't include 0, the mean CAR is statistically significant
    (non-parametric analog of the t-test — doesn't assume normality).

    rng_seed makes results reproducible for testing.
    """
    rng = np.random.default_rng(rng_seed)
    n = len(cars)
    boot_means = np.array([
        rng.choice(cars, size=n, replace=True).mean() for _ in range(n_bootstrap)
    ])
    lower_pct = (1 - confidence) / 2 * 100   # 2.5 for 95% CI
    upper_pct = (1 + confidence) / 2 * 100   # 97.5 for 95% CI
    lower, upper = np.percentile(boot_means, [lower_pct, upper_pct])
    return BootstrapCI(
        lower=float(lower),
        upper=float(upper),
        confidence=confidence,
        n_bootstrap=n_bootstrap,
    )
