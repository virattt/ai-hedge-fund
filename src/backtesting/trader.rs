// Source: src/backtesting/trader.py
//! Sibling to src/backtesting/trader.py
//! Simulates exchange trade execution for buying, selling, shorting, and covering positions.

use crate::backtesting::portfolio::Portfolio;

#[derive(Debug, Default)]
pub struct TradeExecutor;

impl TradeExecutor {
    pub fn new() -> Self {
        Self
    }

    /// Executes trade and returns the executed quantity.
    pub fn execute_trade(
        &self,
        ticker: &str,
        action: &str,
        quantity: u32,
        price: f64,
        portfolio: &mut Portfolio,
    ) -> u32 {
        match action {
            "buy" => portfolio.apply_long_buy(ticker, quantity, price),
            "sell" => portfolio.apply_long_sell(ticker, quantity, price),
            "short" => portfolio.apply_short_open(ticker, quantity, price),
            "cover" => portfolio.apply_short_cover(ticker, quantity, price),
            _ => 0,
        }
    }
}
