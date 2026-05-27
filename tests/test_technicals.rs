// Source: tests/test_technicals.rs
//! Verifies mathematical correctness of standard indicators calculated in Rust.

use ai_hedge_fund::agents::technicals::{calculate_ema, calculate_rsi, calculate_sma};

#[test]
fn test_sma_calculation() {
    let data = vec![10.0, 20.0, 30.0, 40.0, 50.0];
    let sma = calculate_sma(&data, 3);
    // Last element is the rolling average of [30, 40, 50] = 40.0
    assert!((sma[4] - 40.0).abs() < 1e-5);
}

#[test]
fn test_ema_calculation() {
    let data = vec![10.0, 20.0, 30.0];
    let ema = calculate_ema(&data, 3);
    assert!(ema.len() == 3);
    assert!(ema[2] > 0.0);
}

#[test]
fn test_rsi_calculation() {
    let data = vec![50.0; 20];
    let rsi = calculate_rsi(&data, 14);
    // Flat price should remain at 50 RSI
    assert!((rsi[19] - 50.0).abs() < 1e-5);
}
