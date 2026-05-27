// Source: src/backtesting/benchmarks.py
//! Sibling to src/backtesting/benchmarks.py
//! Computes and compares strategy performance against default benchmarks such as Buy & Hold AAPL/SPY.

use crate::tools::api::get_prices;

pub struct BenchmarkCalculator;

impl BenchmarkCalculator {
    pub fn new() -> Self {
        Self
    }

    /// Compute simple buy-and-hold return % for ticker from start_date to end_date.
    /// Return is (last_close / first_close - 1) * 100, or None if unavailable.
    pub async fn get_return_pct(
        &self,
        ticker: &str,
        start_date: &str,
        end_date: &str,
    ) -> Option<f64> {
        let api_key = std::env::var("FINANCIAL_DATASETS_API_KEY").ok();
        match get_prices(ticker, start_date, end_date, api_key.as_deref()).await {
            Ok(prices) => {
                if prices.is_empty() {
                    return None;
                }
                let first_close = prices.first()?.close;
                let last_close = prices.last()?.close;

                if first_close == 0.0 {
                    return None;
                }

                Some(((last_close / first_close) - 1.0) * 100.0)
            }
            Err(_) => None,
        }
    }
}

impl Default for BenchmarkCalculator {
    fn default() -> Self {
        Self::new()
    }
}
