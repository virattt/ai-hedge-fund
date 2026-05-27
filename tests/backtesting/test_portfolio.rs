// Source: tests/backtesting/test_portfolio.rs
//! Mathematical and logic verification of the Portfolio ledger state.

use ai_hedge_fund::backtesting::portfolio::Portfolio;

#[test]
fn test_apply_long_buy_basic() {
    let mut portfolio = Portfolio::new(vec!["AAPL".to_string()], 100000.0, 0.5);
    let executed = portfolio.apply_long_buy("AAPL", 100, 50.0);
    assert_eq!(executed, 100);
    assert_eq!(portfolio.positions["AAPL"].long, 100);
    assert!((portfolio.positions["AAPL"].long_cost_basis - 50.0).abs() < 1e-5);
    assert!((portfolio.cash - 95000.0).abs() < 1e-5);
}

#[test]
fn test_apply_long_buy_partial_fill_when_insufficient_cash() {
    let mut p = Portfolio::new(vec!["AAPL".to_string()], 120.0, 0.5);
    let executed = p.apply_long_buy("AAPL", 10, 20.0);
    assert_eq!(executed, 6);
    assert_eq!(p.positions["AAPL"].long, 6);
    assert!((p.cash - 0.0).abs() < 1e-5);
}

#[test]
fn test_apply_long_sell_realized_gain_and_cost_basis_reset() {
    let mut portfolio = Portfolio::new(vec!["AAPL".to_string()], 100000.0, 0.5);
    portfolio.apply_long_buy("AAPL", 100, 50.0);
    let executed = portfolio.apply_long_sell("AAPL", 100, 60.0);
    assert_eq!(executed, 100);
    assert_eq!(portfolio.positions["AAPL"].long, 0);
    assert!((portfolio.positions["AAPL"].long_cost_basis - 0.0).abs() < 1e-5);
    assert!((portfolio.realized_gains["AAPL"].long - 1000.0).abs() < 1e-5);
    assert!((portfolio.cash - 101000.0).abs() < 1e-5);
}

#[test]
fn test_apply_long_sell_clamps_to_owned() {
    let mut p = Portfolio::new(vec!["AAPL".to_string()], 10000.0, 0.5);
    p.apply_long_buy("AAPL", 10, 100.0);
    let executed = p.apply_long_sell("AAPL", 20, 100.0);
    assert_eq!(executed, 10);
    assert_eq!(p.positions["AAPL"].long, 0);
}

#[test]
fn test_apply_short_open_basic() {
    let mut portfolio = Portfolio::new(vec!["MSFT".to_string()], 100000.0, 0.5);
    let executed = portfolio.apply_short_open("MSFT", 100, 30.0);
    assert_eq!(executed, 100);
    let pos = &portfolio.positions["MSFT"];
    assert_eq!(pos.short, 100);
    assert!((pos.short_cost_basis - 30.0).abs() < 1e-5);
    assert!((pos.short_margin_used - 1500.0).abs() < 1e-5);
    assert!((portfolio.margin_used - 1500.0).abs() < 1e-5);
    assert!((portfolio.cash - 101500.0).abs() < 1e-5);
}

#[test]
fn test_apply_short_open_partial_when_insufficient_margin_cash() {
    let mut p = Portfolio::new(vec!["AAPL".to_string()], 200.0, 0.5);
    let executed = p.apply_short_open("AAPL", 10, 100.0);
    assert_eq!(executed, 4);
    let pos = &p.positions["AAPL"];
    assert_eq!(pos.short, 4);
    assert!((pos.short_margin_used - 200.0).abs() < 1e-5);
    assert!((p.cash - 400.0).abs() < 1e-5);
}

#[test]
fn test_apply_short_open_uses_available_cash_not_total_cash() {
    let mut p = Portfolio::new(vec!["AAPL".to_string()], 1000.0, 0.5);
    let first = p.apply_short_open("AAPL", 10, 100.0);
    assert_eq!(first, 10);
    let second = p.apply_short_open("AAPL", 30, 100.0);
    assert_eq!(second, 20);
    assert_eq!(p.positions["AAPL"].short, 30);
    assert!((p.margin_used - 1500.0).abs() < 1e-5);
}

#[test]
fn test_apply_short_cover_realized_gain_and_margin_release() {
    let mut portfolio = Portfolio::new(vec!["AAPL".to_string()], 100000.0, 0.5);
    portfolio.apply_short_open("AAPL", 100, 50.0);
    let pre_cash = portfolio.cash;
    let pre_margin_used = portfolio.positions["AAPL"].short_margin_used;
    let executed = portfolio.apply_short_cover("AAPL", 40, 40.0);
    assert_eq!(executed, 40);
    let pos = &portfolio.positions["AAPL"];
    assert!((portfolio.realized_gains["AAPL"].short - 400.0).abs() < 1e-5);
    let released = 0.4 * pre_margin_used;
    assert!((pos.short_margin_used - (pre_margin_used - released)).abs() < 1e-5);
    let expected_cash = pre_cash + released - 1600.0;
    assert!((portfolio.cash - expected_cash).abs() < 1e-5);
}

#[test]
fn test_apply_short_cover_clamps_to_existing_short() {
    let mut p = Portfolio::new(vec!["AAPL".to_string()], 10000.0, 0.5);
    p.apply_short_open("AAPL", 5, 100.0);
    let executed = p.apply_short_cover("AAPL", 10, 100.0);
    assert_eq!(executed, 5);
    assert_eq!(p.positions["AAPL"].short, 0);
}
