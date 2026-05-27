// Source: src/backtesting/engine.py
//! Sibling to src/backtesting/engine.py
//! Main backtesting engine driver coordinating simulation loops, portfolio changes, and performance updates.

use anyhow::{Result, Context};
use chrono::{NaiveDate, Datelike};
use std::collections::HashMap;

use crate::backtesting::portfolio::Portfolio;
use crate::backtesting::trader::TradeExecutor;
use crate::backtesting::metrics::PerformanceMetricsCalculator;
use crate::backtesting::types::{PerformanceMetrics, PortfolioValuePoint};
use crate::backtesting::benchmarks::BenchmarkCalculator;
use crate::backtesting::controller::AgentController;
use crate::backtesting::output::OutputBuilder;
use crate::utils::display::BacktestRow;
use crate::agents::portfolio_manager::PortfolioDecision;
use crate::tools::api::get_prices;
use crate::data::provider::{configure_provider, active_provider, DataProvider};

/// Driver engine for executing historical backtests.
#[derive(Debug)]
pub struct BacktestEngine {
    pub tickers: Vec<String>,
    pub start_date: String,
    pub end_date: String,
    pub initial_capital: f64,
    pub model_name: String,
    pub model_provider: String,
    pub selected_analysts: Vec<String>,
    pub initial_margin_requirement: f64,
    pub data_provider: Option<DataProvider>,
}

impl BacktestEngine {
    /// Runs the historical simulation daily loop.
    pub async fn run_backtest(&mut self) -> Result<PerformanceMetrics> {
        println!("BacktestEngine: prefetching historical datasets...");

        configure_provider(self.data_provider);
        let provider = active_provider();
        let api_key = std::env::var("FINANCIAL_DATASETS_API_KEY").ok();

        match provider {
            DataProvider::YahooFinance => {
                println!("Using Yahoo Finance as the data provider (free tier).");
            }
            DataProvider::FinancialDatasets => {
                if api_key.is_none()
                    || api_key.as_deref() == Some("your-financial-datasets-api-key")
                    || api_key.as_deref().unwrap_or("").is_empty()
                {
                    println!("--------------------------------------------------------------------------------");
                    println!("WARNING: FINANCIAL_DATASETS_API_KEY is not set or is set to a placeholder.");
                    println!("Historical API queries will fail or be unauthorized. Please configure the key");
                    println!("in your environment or in a .env file, or use --data-provider yahoo-finance.");
                    println!("--------------------------------------------------------------------------------");
                }
            }
        }

        // 1. Parse start and end dates
        let start_dt = NaiveDate::parse_from_str(&self.start_date, "%Y-%m-%d")
            .context("Failed to parse start_date")?;
        let end_dt = NaiveDate::parse_from_str(&self.end_date, "%Y-%m-%d")
            .context("Failed to parse end_date")?;

        // 2. Instantiate portfolio, executor, and metrics calculator, and output builder, and benchmark calculator
        let mut portfolio = Portfolio::new(self.tickers.clone(), self.initial_capital, self.initial_margin_requirement);
        let executor = TradeExecutor::new();
        let calculator = PerformanceMetricsCalculator::new();
        let output_builder = OutputBuilder::new(Some(self.initial_capital));
        let benchmark = BenchmarkCalculator::new();
        let controller = AgentController::new();

        let mut portfolio_values: Vec<PortfolioValuePoint> = Vec::new();
        let mut table_rows: Vec<BacktestRow> = Vec::new();
        let mut performance_metrics = PerformanceMetrics::default();

        let mut current_dt = start_dt;

        println!("Starting daily simulation from {} to {}...", self.start_date, self.end_date);

        // Daily Loop
        while current_dt <= end_dt {
            // Check if weekday (business day)
            let weekday = current_dt.weekday().number_from_monday();
            if weekday > 5 {
                current_dt = current_dt.succ_opt().context("Date overflow")?;
                continue;
            }

            let current_date_str = current_dt.format("%Y-%m-%d").to_string();
            let previous_dt = current_dt - chrono::Duration::days(1);
            let previous_date_str = previous_dt.format("%Y-%m-%d").to_string();
            let lookback_start = (current_dt - chrono::Duration::days(30)).format("%Y-%m-%d").to_string();

            // Fetch daily closing prices
            let mut daily_prices = HashMap::new();
            let mut missing_price = false;

            for ticker in &self.tickers {
                match get_prices(ticker, &previous_date_str, &current_date_str, api_key.as_deref()).await {
                    Ok(prices) => {
                        if let Some(p) = prices.last() {
                            daily_prices.insert(ticker.clone(), p.close);
                        } else {
                            println!("Note: No price found for {} on {} (likely trading holiday), skipping day.", ticker, current_date_str);
                            missing_price = true;
                        }
                    }
                    Err(e) => {
                        println!("Warning: API call failed for {} on {}: {}, skipping day.", ticker, current_date_str, e);
                        missing_price = true;
                    }
                }
            }

            if missing_price {
                // If closing price is missing (e.g. trading holiday), skip this day
                current_dt = current_dt.succ_opt().context("Date overflow")?;
                continue;
            }

            // Invoke standard agents sequentially via the controller
            let agent_output = controller.run_agent(
                self.tickers.clone(),
                &lookback_start,
                &current_date_str,
                &portfolio,
                &self.model_name,
                &self.model_provider,
                self.selected_analysts.clone(),
                self.data_provider,
            ).await?;

            let decisions_json = agent_output.decisions.as_ref()
                .context("Missing decisions in agent state")?;
            let decisions: HashMap<String, PortfolioDecision> = serde_json::from_value(decisions_json.clone())?;

            // Execute Trades
            let mut executed_trades = HashMap::new();
            for ticker in &self.tickers {
                let mut executed_qty = 0;
                if let Some(dec) = decisions.get(ticker) {
                    if dec.action != "hold" && dec.quantity > 0 {
                        let price = *daily_prices.get(ticker).unwrap();
                        executed_qty = executor.execute_trade(ticker, &dec.action, dec.quantity, price, &mut portfolio);
                    }
                }
                executed_trades.insert(ticker.clone(), executed_qty);
            }

            // Calculate Portfolio Value (NVI) and Exposures
            let total_value = crate::backtesting::valuation::calculate_portfolio_value(&portfolio, &daily_prices);
            let exposures = crate::backtesting::valuation::compute_exposures(&portfolio, &daily_prices);

            let point = PortfolioValuePoint {
                date: current_dt,
                portfolio_value: total_value,
                long_exposure: exposures.long_exposure,
                short_exposure: exposures.short_exposure,
                gross_exposure: exposures.gross_exposure,
                net_exposure: exposures.net_exposure,
                long_short_ratio: exposures.long_short_ratio,
            };
            portfolio_values.push(point);

            // Update performance metrics before rendering this day's summary so
            // drawdown and return statistics include the latest portfolio value.
            if let Some(computed) = calculator.compute_metrics(&portfolio_values) {
                performance_metrics = computed;
            }

            // Fetch S&P 500 comparison return
            let benchmark_return = benchmark.get_return_pct("SPY", &self.start_date, &current_date_str).await;

            // Build daily rows and prepend
            let rows = output_builder.build_day_rows(
                &current_date_str,
                &self.tickers,
                &agent_output,
                &executed_trades,
                &daily_prices,
                &portfolio,
                &performance_metrics,
                total_value,
                benchmark_return,
            );

            let mut new_table_rows = rows;
            new_table_rows.extend(table_rows);
            table_rows = new_table_rows;

            // Print full history
            output_builder.print_rows(&table_rows);

            current_dt = current_dt.succ_opt().context("Date overflow")?;
        }

        Ok(performance_metrics)
    }
}
