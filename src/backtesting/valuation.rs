// Source: src/backtesting/valuation.py
//! Sibling to src/backtesting/valuation.py
//! Performs valuation checks during backtest simulation steps to determine portfolio asset values.

use std::collections::HashMap;
use crate::backtesting::portfolio::Portfolio;

/// Compute total portfolio value.
/// total_value = cash + market value of longs - market value of shorts
pub fn calculate_portfolio_value(portfolio: &Portfolio, current_prices: &HashMap<String, f64>) -> f64 {
    let mut total_value = portfolio.cash;
    for (ticker, pos) in &portfolio.positions {
        if let Some(&price) = current_prices.get(ticker) {
            total_value += pos.long as f64 * price;
            total_value -= pos.short as f64 * price;
        }
    }
    total_value
}

/// Exposure analysis for long/short positioning.
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct Exposures {
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

/// Compute long/short/gross/net exposures and long/short ratio.
pub fn compute_exposures(portfolio: &Portfolio, current_prices: &HashMap<String, f64>) -> Exposures {
    let mut long_exposure = 0.0;
    let mut short_exposure = 0.0;
    for (ticker, pos) in &portfolio.positions {
        if let Some(&price) = current_prices.get(ticker) {
            long_exposure += pos.long as f64 * price;
            short_exposure += pos.short as f64 * price;
        }
    }
    let gross_exposure = long_exposure + short_exposure;
    let net_exposure = long_exposure - short_exposure;
    let long_short_ratio = if short_exposure > 1e-9 {
        long_exposure / short_exposure
    } else {
        f64::INFINITY
    };

    Exposures {
        long_exposure,
        short_exposure,
        gross_exposure,
        net_exposure,
        long_short_ratio,
    }
}

/// Backtest summary record.
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct PortfolioSummary {
    pub total_value: f64,
    pub return_pct: f64,
    pub cash_balance: f64,
    pub total_position_value: f64,
    pub sharpe_ratio: Option<f64>,
    pub sortino_ratio: Option<f64>,
    pub max_drawdown: Option<f64>,
}

/// Compute portfolio summary fields in a pure, testable function.
pub fn compute_portfolio_summary(
    portfolio: &Portfolio,
    total_value: f64,
    initial_value: Option<f64>,
    performance_metrics: &HashMap<String, Option<f64>>,
) -> PortfolioSummary {
    let cash_balance = portfolio.cash;
    let total_position_value = total_value - cash_balance;
    let return_pct = if let Some(init) = initial_value {
        if init != 0.0 {
            (total_value / init - 1.0) * 100.0
        } else {
            0.0
        }
    } else {
        0.0
    };

    PortfolioSummary {
        total_value,
        return_pct,
        cash_balance,
        total_position_value,
        sharpe_ratio: performance_metrics.get("sharpe_ratio").copied().flatten(),
        sortino_ratio: performance_metrics.get("sortino_ratio").copied().flatten(),
        max_drawdown: performance_metrics.get("max_drawdown").copied().flatten(),
    }
}
