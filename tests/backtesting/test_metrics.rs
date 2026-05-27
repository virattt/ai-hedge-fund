// Source: tests/backtesting/test_metrics.rs
//! Mathematical verification of daily portfolio metrics calculations.

use ai_hedge_fund::backtesting::metrics::PerformanceMetricsCalculator;

#[test]
fn test_metrics_insufficient_data_no_update() {
    let calc = PerformanceMetricsCalculator::new();
    let metrics = calc.compute_metrics(&[100000.0]);
    assert!(metrics.is_none());
}

#[test]
fn test_metrics_basic_sharpe_and_return() {
    let calc = PerformanceMetricsCalculator::new();
    let values = vec![100.0, 110.0, 105.0];
    let metrics = calc.compute_metrics(&values);
    assert!(metrics.is_some());
    let m = metrics.unwrap();
    assert!(m.sharpe_ratio != 0.0);
    assert!((m.total_return - 5.0).abs() < 1e-5);
}

#[test]
fn test_metrics_zero_volatility_sharpe_zero() {
    let calc = PerformanceMetricsCalculator::new();
    let values = vec![100.0, 100.0, 100.0, 100.0];
    let metrics = calc.compute_metrics(&values);
    assert!(metrics.is_some());
    let m = metrics.unwrap();
    assert_eq!(m.sharpe_ratio, 0.0);
    assert_eq!(m.total_return, 0.0);
}
