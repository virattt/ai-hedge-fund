// Source: src/backtesting/metrics.py
//! Sibling to src/backtesting/metrics.py
//! Computes cumulative returns, Sharpe Ratio, Sortino Ratio, and Maximum Drawdowns from simulated portfolio value curves.

use crate::backtesting::types::{PerformanceMetrics, PortfolioValuePoint};

#[derive(Debug, Clone)]
pub struct PerformanceMetricsCalculator {
    pub annual_trading_days: f64,
    pub annual_rf_rate: f64,
}

impl PerformanceMetricsCalculator {
    const MIN_RISK_RETURN_OBSERVATIONS: usize = 20;

    pub fn new() -> Self {
        Self {
            annual_trading_days: 252.0,
            annual_rf_rate: 0.0434,
        }
    }

    /// Computes performance metrics from a daily portfolio value curve.
    pub fn compute_metrics(&self, values: &[PortfolioValuePoint]) -> Option<PerformanceMetrics> {
        if values.is_empty() {
            return None;
        }

        let initial_value = values[0].portfolio_value;
        let final_value = values[values.len() - 1].portfolio_value;
        let total_return = if initial_value > 0.0 {
            (final_value - initial_value) / initial_value * 100.0
        } else {
            0.0
        };

        // Calculate daily returns
        let mut daily_returns = Vec::new();
        for i in 1..values.len() {
            let prev = values[i - 1].portfolio_value;
            let ret = if prev > 0.0 {
                (values[i].portfolio_value - prev) / prev
            } else {
                0.0
            };
            daily_returns.push(ret);
        }

        let risk_metrics_available = daily_returns.len() >= Self::MIN_RISK_RETURN_OBSERVATIONS;
        let (sharpe_ratio, sortino_ratio) = if risk_metrics_available {
            let n = daily_returns.len() as f64;
            let daily_rf = self.annual_rf_rate / self.annual_trading_days;

            // Excess returns
            let excess: Vec<f64> = daily_returns.iter().map(|&r| r - daily_rf).collect();
            let mean_excess = excess.iter().sum::<f64>() / n;

            // Variance and Std Dev (ddof = 1 to match Pandas)
            let variance = excess
                .iter()
                .map(|&x| (x - mean_excess).powi(2))
                .sum::<f64>()
                / (n - 1.0);
            let std_dev = variance.sqrt();

            let sharpe_ratio = if std_dev > 1e-12 {
                (mean_excess / std_dev) * self.annual_trading_days.sqrt()
            } else {
                0.0
            };

            // Downside deviation
            let downside_sum_sq: f64 = excess
                .iter()
                .map(|&x| if x < 0.0 { x.powi(2) } else { 0.0 })
                .sum();
            let downside_dev = (downside_sum_sq / n).sqrt();

            let sortino_ratio = if downside_dev > 1e-12 {
                (mean_excess / downside_dev) * self.annual_trading_days.sqrt()
            } else if mean_excess > 0.0 {
                f64::INFINITY
            } else {
                0.0
            };

            (sharpe_ratio, Some(sortino_ratio))
        } else {
            (0.0, None)
        };

        // Maximum Drawdown Calculation
        let mut max_drawdown = 0.0;
        let mut max_drawdown_date = None;
        let mut peak = values[0].portfolio_value;

        for point in values {
            let val = point.portfolio_value;
            if val > peak {
                peak = val;
            }
            let dd = if peak > 0.0 { (peak - val) / peak } else { 0.0 };
            if dd > max_drawdown {
                max_drawdown = dd;
                max_drawdown_date = Some(point.date.format("%Y-%m-%d").to_string());
            }
        }

        // Convert to percentage (as in Python, max_drawdown is percentage, e.g. -15.4%)
        let max_drawdown_pct = -max_drawdown * 100.0;

        // Exposures (from the last point)
        let last_point = &values[values.len() - 1];
        let long_short_ratio = if last_point.short_exposure.abs() > 1e-9 {
            Some(last_point.long_exposure / last_point.short_exposure)
        } else {
            Some(f64::INFINITY)
        };

        Some(PerformanceMetrics {
            sharpe_ratio,
            risk_metrics_available,
            total_return,
            sortino_ratio,
            max_drawdown: Some(max_drawdown_pct),
            max_drawdown_date,
            long_short_ratio,
            gross_exposure: Some(last_point.gross_exposure),
            net_exposure: Some(last_point.net_exposure),
        })
    }
}

impl Default for PerformanceMetricsCalculator {
    fn default() -> Self {
        Self::new()
    }
}
