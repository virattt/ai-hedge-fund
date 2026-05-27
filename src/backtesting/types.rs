// Source: src/backtesting/types.py
//! Sibling to src/backtesting/types.py
//! Common types for backtesting.

/// Performance metrics calculated at the end of a backtest run.
#[derive(Debug, serde::Serialize, serde::Deserialize, Clone, Default)]
pub struct PerformanceMetrics {
    pub sharpe_ratio: f64,
    pub risk_metrics_available: bool,
    pub total_return: f64,
    pub sortino_ratio: Option<f64>,
    pub max_drawdown: Option<f64>,
    pub max_drawdown_date: Option<String>,
    pub long_short_ratio: Option<f64>,
    pub gross_exposure: Option<f64>,
    pub net_exposure: Option<f64>,
}

/// Represents a single daily data point of the portfolio valuation and exposures.
#[derive(Debug, serde::Serialize, serde::Deserialize, Clone)]
pub struct PortfolioValuePoint {
    #[serde(rename = "Date")]
    pub date: chrono::NaiveDate,
    #[serde(rename = "Portfolio Value")]
    pub portfolio_value: f64,
    #[serde(rename = "Long Exposure")]
    pub long_exposure: f64,
    #[serde(rename = "Short Exposure")]
    pub short_exposure: f64,
    #[serde(rename = "Gross Exposure")]
    pub gross_exposure: f64,
    #[serde(rename = "Net Exposure")]
    pub net_exposure: f64,
    #[serde(rename = "Long/Short Ratio")]
    pub long_short_ratio: f64,
}
