// Source: src/backtesting/output.py
//! Sibling to src/backtesting/output.py
//! Handles generation and persistence of backtest metrics output files (CSV, JSON, graphs).

use crate::backtesting::portfolio::Portfolio;
use crate::backtesting::types::PerformanceMetrics;
use crate::utils::display::{print_backtest_results, BacktestRow};
use crate::workflow::HedgeFundResult;
use std::collections::HashMap;

pub struct OutputBuilder {
    pub initial_capital: Option<f64>,
}

pub struct DayRowInput<'a> {
    pub date_str: &'a str,
    pub tickers: &'a [String],
    pub agent_output: &'a HedgeFundResult,
    pub executed_trades: &'a HashMap<String, u32>,
    pub current_prices: &'a HashMap<String, f64>,
    pub portfolio: &'a Portfolio,
    pub performance_metrics: &'a PerformanceMetrics,
    pub total_value: f64,
    pub benchmark_return_pct: Option<f64>,
}

impl OutputBuilder {
    pub fn new(initial_capital: Option<f64>) -> Self {
        Self { initial_capital }
    }

    pub fn build_day_rows(&self, input: DayRowInput<'_>) -> Vec<BacktestRow> {
        let mut day_rows = Vec::new();

        // Retrieve decisions
        let decisions_json = input.agent_output.decisions.as_ref();
        let decisions_obj = decisions_json.and_then(|v| v.as_object());

        for ticker in input.tickers {
            let price = input.current_prices.get(ticker).copied().unwrap_or(0.0);
            let pos = input
                .portfolio
                .positions
                .get(ticker)
                .cloned()
                .unwrap_or_default();

            let long_val = pos.long as f64 * price;
            let short_val = pos.short as f64 * price;
            let net_position_value = long_val - short_val;

            let ticker_decision = decisions_obj.and_then(|obj| obj.get(ticker));
            let action = ticker_decision
                .and_then(|d| d.get("action"))
                .and_then(|a| a.as_str())
                .unwrap_or("hold");

            let quantity = input.executed_trades.get(ticker).copied().unwrap_or(0) as f64;

            day_rows.push(BacktestRow::Trade {
                date: input.date_str.to_string(),
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
        let initial_val = self.initial_capital.unwrap_or(input.total_value);
        let return_pct = if initial_val > 0.0 {
            ((input.total_value / initial_val) - 1.0) * 100.0
        } else {
            0.0
        };

        day_rows.push(BacktestRow::Summary {
            date: input.date_str.to_string(),
            label: "PORTFOLIO SUMMARY".to_string(),
            total_position_value: input.total_value - input.portfolio.cash,
            cash_balance: input.portfolio.cash,
            short_sale_proceeds: input.portfolio.short_sale_proceeds(),
            margin_used: input.portfolio.margin_used,
            available_cash: input.portfolio.available_cash(),
            total_value: input.total_value,
            return_pct,
            sharpe_ratio: if input.performance_metrics.risk_metrics_available {
                Some(input.performance_metrics.sharpe_ratio)
            } else {
                None
            },
            sortino_ratio: if input.performance_metrics.risk_metrics_available {
                input.performance_metrics.sortino_ratio
            } else {
                None
            },
            max_drawdown: input.performance_metrics.max_drawdown,
            benchmark_return_pct: input.benchmark_return_pct,
        });

        day_rows
    }

    pub fn print_rows(&self, rows: &[BacktestRow]) {
        print_backtest_results(rows);
    }
}
