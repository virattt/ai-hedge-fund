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
    let cli = ai_hedge_fund::cli::input::parse_cli_inputs();
    
    // Resolve dates
    let (start_date, end_date) = ai_hedge_fund::cli::input::resolve_dates(cli.start_date, cli.end_date, Some(1));
    
    // Fallback to default tickers if empty
    let tickers = if cli.tickers.is_empty() {
        vec!["AAPL".to_string(), "MSFT".to_string()]
    } else {
        cli.tickers
    };

    // Determine model name and provider
    let model_name = cli.model.unwrap_or_else(|| "gpt-4".to_string());
    let model_provider = if cli.ollama {
        "Ollama".to_string()
    } else {
        "OpenAI".to_string()
    };

    let selected_analysts = cli.analysts.unwrap_or_default();

    // Create the backtester engine instance
    let mut backtester = BacktestEngine {
        tickers,
        start_date,
        end_date,
        initial_capital: cli.initial_cash,
        model_name,
        model_provider,
        selected_analysts,
        initial_margin_requirement: cli.margin_requirement,
    };

    let _metrics = run_backtest(&mut backtester).await?;

    Ok(())
}
