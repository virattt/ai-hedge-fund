// Source: tests/backtesting/test_metrics.rs
//! Mathematical verification of daily portfolio metrics calculations.

use ai_hedge_fund::backtesting::metrics::PerformanceMetricsCalculator;
use ai_hedge_fund::backtesting::types::PortfolioValuePoint;
use chrono::NaiveDate;

fn val_point(val: f64, days_offset: i64) -> PortfolioValuePoint {
    PortfolioValuePoint {
        date: NaiveDate::from_ymd_opt(2024, 1, 1).unwrap() + chrono::Duration::days(days_offset),
        portfolio_value: val,
        long_exposure: 0.0,
        short_exposure: 0.0,
        gross_exposure: 0.0,
        net_exposure: 0.0,
        long_short_ratio: 0.0,
    }
}

#[test]
fn test_metrics_insufficient_data_no_update() {
    let calc = PerformanceMetricsCalculator::new();
    let metrics = calc.compute_metrics(&[val_point(100000.0, 0)]);
    assert!(metrics.is_some());
    let m = metrics.unwrap();
    assert!(!m.risk_metrics_available);
    assert_eq!(m.total_return, 0.0);
    assert_eq!(m.max_drawdown, Some(-0.0));
}

#[test]
fn test_metrics_basic_return_and_drawdown_before_risk_sample() {
    let calc = PerformanceMetricsCalculator::new();
    let values = vec![
        val_point(100.0, 0),
        val_point(110.0, 1),
        val_point(105.0, 2),
    ];
    let metrics = calc.compute_metrics(&values);
    assert!(metrics.is_some());
    let m = metrics.unwrap();
    assert!(!m.risk_metrics_available);
    assert_eq!(m.total_return, 5.0);
    assert_eq!(m.max_drawdown, Some(-4.545454545454546));
    assert_eq!(m.sortino_ratio, None);
}

#[test]
fn test_metrics_zero_volatility_sharpe_zero_after_minimum_sample() {
    let calc = PerformanceMetricsCalculator::new();
    let values = (0..=20)
        .map(|day| val_point(100.0, day))
        .collect::<Vec<_>>();
    let metrics = calc.compute_metrics(&values);
    assert!(metrics.is_some());
    let m = metrics.unwrap();
    assert!(m.risk_metrics_available);
    assert_eq!(m.sharpe_ratio, 0.0);
    assert_eq!(m.total_return, 0.0);
}
