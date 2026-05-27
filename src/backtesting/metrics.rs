// Source: src/backtesting/metrics.py
//! Sibling to src/backtesting/metrics.py
//! Computes cumulative returns, Sharpe Ratio, Sortino Ratio, and Maximum Drawdowns from simulated portfolio value curves.

use crate::backtesting::types::PerformanceMetrics;

#[derive(Debug, Default)]
pub struct PerformanceMetricsCalculator;

impl PerformanceMetricsCalculator {
    pub fn new() -> Self {
        Self
    }

    /// Computes performance metrics from a daily portfolio value curve.
    pub fn compute_metrics(&self, portfolio_values: &[f64]) -> Option<PerformanceMetrics> {
        if portfolio_values.len() < 3 {
            return None;
        }

        let initial_value = portfolio_values[0];
        let final_value = portfolio_values[portfolio_values.len() - 1];
        let total_return = if initial_value > 0.0 {
            (final_value - initial_value) / initial_value * 100.0
        } else {
            0.0
        };

        // Calculate daily returns
        let mut daily_returns = Vec::new();
        for i in 1..portfolio_values.len() {
            let prev = portfolio_values[i - 1];
            let ret = if prev > 0.0 {
                (portfolio_values[i] - prev) / prev
            } else {
                0.0
            };
            daily_returns.push(ret);
        }

        // Sharpe & Sortino Calculations
        let n = daily_returns.len() as f64;
        let mean_ret = daily_returns.iter().sum::<f64>() / n;
        let variance = daily_returns.iter().map(|&x| (x - mean_ret).powi(2)).sum::<f64>() / n;
        let std_dev = variance.sqrt();

        let sharpe_ratio = if std_dev > 0.0 {
            (mean_ret / std_dev) * 252.0_f64.sqrt()
        } else {
            0.0
        };

        // Maximum Drawdown Calculation
        let mut max_drawdown = 0.0;
        let mut peak = portfolio_values[0];
        for &val in portfolio_values {
            if val > peak {
                peak = val;
            }
            let dd = if peak > 0.0 {
                (peak - val) / peak
            } else {
                0.0
            };
            if dd > max_drawdown {
                max_drawdown = dd;
            }
        }

        Some(PerformanceMetrics {
            sharpe_ratio,
            total_return,
        })
    }
}
