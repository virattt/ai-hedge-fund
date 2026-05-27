// Source: src/backtesting/types.py
//! Sibling to src/backtesting/types.py
//! Common types for backtesting.

/// Performance metrics calculated at the end of a backtest run.
#[derive(Debug, serde::Serialize, serde::Deserialize, Clone)]
pub struct PerformanceMetrics {
    pub sharpe_ratio: f64,
    pub total_return: f64,
}
