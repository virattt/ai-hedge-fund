// Source: tests/backtesting/test_valuation.rs
//! Mathematical verification of portfolio valuation, exposure metrics, and summaries.

use ai_hedge_fund::backtesting::portfolio::Portfolio;
use ai_hedge_fund::backtesting::valuation::{
    calculate_portfolio_value, compute_exposures, compute_portfolio_summary,
};
use std::collections::HashMap;

#[test]
fn test_calculate_portfolio_value() {
    let mut portfolio = Portfolio::new(vec!["AAPL".to_string(), "MSFT".to_string()], 100000.0, 0.5);
    portfolio.apply_long_buy("AAPL", 10, 100.0);
    portfolio.apply_short_open("MSFT", 5, 200.0);

    let mut current_prices = HashMap::new();
    current_prices.insert("AAPL".to_string(), 100.0);
    current_prices.insert("MSFT".to_string(), 200.0);

    let value = calculate_portfolio_value(&portfolio, &current_prices);
    // cash after trades
    let expected = portfolio.cash + 10.0 * 100.0 - 5.0 * 200.0;
    assert_eq!(value, expected);
    assert_eq!(value, 100000.0);
}

#[test]
fn test_compute_exposures() {
    let mut portfolio = Portfolio::new(vec!["AAPL".to_string(), "MSFT".to_string()], 100000.0, 0.5);
    portfolio.apply_long_buy("AAPL", 10, 100.0);
    portfolio.apply_short_open("MSFT", 5, 200.0);

    let mut current_prices = HashMap::new();
    current_prices.insert("AAPL".to_string(), 100.0);
    current_prices.insert("MSFT".to_string(), 200.0);

    let exp = compute_exposures(&portfolio, &current_prices);
    assert_eq!(exp.long_exposure, 1000.0);
    assert_eq!(exp.short_exposure, 1000.0);
    assert_eq!(exp.gross_exposure, 2000.0);
    assert_eq!(exp.net_exposure, 0.0);
    assert_eq!(exp.long_short_ratio, 1.0);
}

#[test]
fn test_compute_exposures_with_no_shorts_ratio_inf() {
    let mut portfolio = Portfolio::new(vec!["AAPL".to_string()], 100000.0, 0.5);
    portfolio.apply_long_buy("AAPL", 1, 100.0);

    let mut current_prices = HashMap::new();
    current_prices.insert("AAPL".to_string(), 100.0);

    let exp = compute_exposures(&portfolio, &current_prices);
    assert_eq!(exp.short_exposure, 0.0);
    assert!(exp.long_short_ratio.is_infinite());
}

#[test]
fn test_compute_portfolio_summary() {
    let mut portfolio = Portfolio::new(vec!["AAPL".to_string()], 100000.0, 0.5);
    portfolio.apply_long_buy("AAPL", 10, 100.0);

    let mut current_prices = HashMap::new();
    current_prices.insert("AAPL".to_string(), 100.0);

    let total_value = calculate_portfolio_value(&portfolio, &current_prices);

    let mut metrics = HashMap::new();
    metrics.insert("sharpe_ratio".to_string(), Some(1.0));
    metrics.insert("sortino_ratio".to_string(), Some(2.0));
    metrics.insert("max_drawdown".to_string(), Some(-5.0));

    let summary = compute_portfolio_summary(&portfolio, total_value, Some(100000.0), &metrics);

    assert_eq!(summary.cash_balance, 99000.0);
    assert_eq!(summary.total_position_value, 1000.0);
    assert_eq!(summary.total_value, total_value);
    assert_eq!(summary.return_pct, 0.0);
    assert_eq!(summary.sharpe_ratio, Some(1.0));
}
