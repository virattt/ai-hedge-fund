// Source: src/backtesting/engine.py
//! Sibling to src/backtesting/engine.py
//! Main backtesting engine driver coordinating simulation loops, portfolio changes, and performance updates.

use anyhow::{Result, Context};
use chrono::{NaiveDate, Datelike};
use std::collections::HashMap;

use crate::backtesting::portfolio::Portfolio;
use crate::backtesting::trader::TradeExecutor;
use crate::backtesting::metrics::PerformanceMetricsCalculator;
use crate::backtesting::types::PerformanceMetrics;
use crate::graph::state::AgentState;

use crate::tools::api::get_prices;
use crate::agents::fundamentals::fundamentals_analyst_agent;
use crate::agents::technicals::technical_analyst_agent;
use crate::agents::risk_manager::risk_management_agent;
use crate::agents::portfolio_manager::{portfolio_management_agent, PortfolioDecision};

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
}

impl BacktestEngine {
    /// Runs the historical simulation daily loop.
    pub async fn run_backtest(&mut self) -> Result<PerformanceMetrics> {
        println!("BacktestEngine: prefetching historical datasets...");
        
        let api_key = std::env::var("FINANCIAL_DATASETS_API_KEY").ok();
        if api_key.is_none() || api_key.as_deref() == Some("your-financial-datasets-api-key") || api_key.as_deref().unwrap_or("").is_empty() {
            println!("--------------------------------------------------------------------------------");
            println!("WARNING: FINANCIAL_DATASETS_API_KEY is not set or is set to a placeholder.");
            println!("Historical API queries will fail or be unauthorized. Please configure the key");
            println!("in your environment or in a .env file.");
            println!("--------------------------------------------------------------------------------");
        }

        // 1. Parse start and end dates
        let start_dt = NaiveDate::parse_from_str(&self.start_date, "%Y-%m-%d")
            .context("Failed to parse start_date")?;
        let end_dt = NaiveDate::parse_from_str(&self.end_date, "%Y-%m-%d")
            .context("Failed to parse end_date")?;

        // 2. Instantiate portfolio, executor, and metrics calculator
        let mut portfolio = Portfolio::new(self.tickers.clone(), self.initial_capital, self.initial_margin_requirement);
        let executor = TradeExecutor::new();
        let calculator = PerformanceMetricsCalculator::new();

        let mut daily_values = Vec::new();
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

            // Build AgentState
            let mut state = AgentState {
                messages: Vec::new(),
                data: HashMap::new(),
                metadata: HashMap::new(),
            };

            state.data.insert("tickers".to_string(), serde_json::to_value(self.tickers.clone())?);
            state.data.insert("start_date".to_string(), serde_json::json!(lookback_start));
            state.data.insert("end_date".to_string(), serde_json::json!(current_date_str));
            state.data.insert("portfolio".to_string(), serde_json::to_value(portfolio.clone())?);

            if let Some(key) = &api_key {
                state.metadata.insert("FINANCIAL_DATASETS_API_KEY".to_string(), serde_json::json!(key));
            }

            // Invoke standard agents sequentially
            fundamentals_analyst_agent(&mut state, "fundamentals_analyst_agent").await?;
            technical_analyst_agent(&mut state, "technical_analyst_agent").await?;
            risk_management_agent(&mut state, "risk_management_agent").await?;
            portfolio_management_agent(&mut state, "portfolio_manager").await?;

            // Retrieve decisions
            let decisions_json = state.data.get("decisions")
                .context("Missing decisions in agent state")?;
            let decisions: HashMap<String, PortfolioDecision> = serde_json::from_value(decisions_json.clone())?;

            // Execute Trades
            for ticker in &self.tickers {
                if let Some(dec) = decisions.get(ticker) {
                    if dec.action != "hold" && dec.quantity > 0 {
                        let price = *daily_prices.get(ticker).unwrap();
                        let executed_qty = executor.execute_trade(ticker, &dec.action, dec.quantity, price, &mut portfolio);
                        if executed_qty > 0 {
                            println!(
                                "Trade: [{}] {} {} shares @ ${:.2}",
                                current_date_str, dec.action.to_uppercase(), executed_qty, price
                            );
                        }
                    }
                }
            }

            // Calculate Portfolio Value (NVI)
            let mut total_value = portfolio.cash;
            for (ticker, pos) in &portfolio.positions {
                if let Some(&price) = daily_prices.get(ticker) {
                    total_value += pos.long as f64 * price;
                    total_value -= pos.short as f64 * price;
                }
            }

            daily_values.push(total_value);
            println!("Daily Value [{}]: ${:.2}", current_date_str, total_value);

            current_dt = current_dt.succ_opt().context("Date overflow")?;
        }

        // Calculate performance metrics at the end of the simulation
        let metrics = calculator.compute_metrics(&daily_values)
            .unwrap_or(PerformanceMetrics {
                sharpe_ratio: 0.0,
                total_return: 0.0,
            });

        Ok(metrics)
    }
}
