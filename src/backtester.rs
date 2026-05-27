// Source: src/backtester.py
//! Sibling to src/backtester.py
//! CLI entry point for executing historical backtests on agent strategies.

use anyhow::Result;
use ai_hedge_fund::backtesting::engine::BacktestEngine;
use ai_hedge_fund::backtesting::types::PerformanceMetrics;

/// Runs the backtest, handling potential runtime errors or interruptions.
pub async fn run_backtest(backtester: &mut BacktestEngine) -> Result<Option<PerformanceMetrics>> {
    println!("Running historical backtest simulation...");
    
    match backtester.run_backtest().await {
        Ok(metrics) => {
            println!("Backtest completed successfully!");
            Ok(Some(metrics))
        }
        Err(e) => {
            eprintln!("Backtest failed: {}", e);
            Err(e)
        }
    }
}

#[tokio::main]
async fn main() -> Result<()> {
    // Load environment variables (.env)
    dotenvy::dotenv().ok();

    println!("Starting Backtesting Engine (Rust Port)...");
    
    // Parse inputs using clap
    let tickers = vec!["AAPL".to_string(), "MSFT".to_string()];
    let start_date = "2026-01-01".to_string();
    let end_date = "2026-02-01".to_string();
    let initial_cash = 100000.0;
    
    // Create the backtester engine instance
    let mut backtester = BacktestEngine {
        tickers,
        start_date,
        end_date,
        initial_capital: initial_cash,
        model_name: "gpt-4".to_string(),
        model_provider: "OpenAI".to_string(),
        selected_analysts: vec![],
        initial_margin_requirement: 0.5,
    };

    let _metrics = run_backtest(&mut backtester).await?;

    Ok(())
}
