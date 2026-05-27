// Source: src/backtesting/output.py
//! Sibling to src/backtesting/output.py
//! Handles generation and persistence of backtest metrics output files (CSV, JSON, graphs).

use crate::backtesting::portfolio::Portfolio;
use crate::backtesting::types::PerformanceMetrics;
use crate::utils::display::{BacktestRow, print_backtest_results};
use crate::workflow::HedgeFundResult;
use std::collections::HashMap;

pub struct OutputBuilder {
    pub initial_capital: Option<f64>,
}

impl OutputBuilder {
    pub fn new(initial_capital: Option<f64>) -> Self {
        Self { initial_capital }
    }

    pub fn build_day_rows(
        &self,
        date_str: &str,
        tickers: &[String],
        agent_output: &HedgeFundResult,
        executed_trades: &HashMap<String, u32>,
        current_prices: &HashMap<String, f64>,
        portfolio: &Portfolio,
        performance_metrics: &PerformanceMetrics,
        total_value: f64,
        benchmark_return_pct: Option<f64>,
    ) -> Vec<BacktestRow> {
        let mut day_rows = Vec::new();

        // Retrieve decisions
        let decisions_json = agent_output.decisions.as_ref();
        let decisions_obj = decisions_json.and_then(|v| v.as_object());

        for ticker in tickers {
            let price = current_prices.get(ticker).copied().unwrap_or(0.0);
            let pos = portfolio.positions.get(ticker).cloned().unwrap_or_default();
            
            let long_val = pos.long as f64 * price;
            let short_val = pos.short as f64 * price;
            let net_position_value = long_val - short_val;

            let ticker_decision = decisions_obj.and_then(|obj| obj.get(ticker));
            let action = ticker_decision.and_then(|d| d.get("action")).and_then(|a| a.as_str()).unwrap_or("hold");
            
            let quantity = executed_trades.get(ticker).copied().unwrap_or(0) as f64;

            day_rows.push(BacktestRow::Trade {
                date: date_str.to_string(),
                ticker: ticker.clone(),
                action: action.to_string(),
                quantity,
                price,
                long_shares: pos.long as f64,
                short_shares: pos.short as f64,
                position_value: net_position_value,
            });
        }

        // Summary row
        let initial_val = self.initial_capital.unwrap_or(total_value);
        let return_pct = if initial_val > 0.0 {
            ((total_value / initial_val) - 1.0) * 100.0
        } else {
            0.0
        };

        day_rows.push(BacktestRow::Summary {
            date: date_str.to_string(),
            label: "PORTFOLIO SUMMARY".to_string(),
            total_position_value: total_value - portfolio.cash,
            cash_balance: portfolio.cash,
            short_sale_proceeds: portfolio.short_sale_proceeds(),
            margin_used: portfolio.margin_used,
            available_cash: portfolio.available_cash(),
            total_value,
            return_pct,
            sharpe_ratio: if performance_metrics.risk_metrics_available {
                Some(performance_metrics.sharpe_ratio)
            } else {
                None
            },
            sortino_ratio: if performance_metrics.risk_metrics_available {
                performance_metrics.sortino_ratio
            } else {
                None
            },
            max_drawdown: performance_metrics.max_drawdown,
            benchmark_return_pct,
        });

        day_rows
    }

    pub fn print_rows(&self, rows: &[BacktestRow]) {
        print_backtest_results(rows);
    }
}
