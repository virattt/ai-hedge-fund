// Source: src/backtester.py
//! Sibling to src/backtester.py
//! CLI entry point for executing historical backtests on agent strategies.

use ai_hedge_fund::backtesting::engine::BacktestEngine;
use ai_hedge_fund::backtesting::types::PerformanceMetrics;
use ai_hedge_fund::cli::input::resolve_data_provider;
use ai_hedge_fund::data::provider::configure_provider;
use ai_hedge_fund::utils::llm::{log_resolved_llm_config, resolve_llm_config};
use anyhow::Result;

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

    if let Some(result) = ai_hedge_fund::cli::chatgpt::try_run_from_env().await {
        return result;
    }

    println!("Starting Backtesting Engine (Rust Port)...");

    // Parse inputs using clap
    let cli = ai_hedge_fund::cli::input::parse_cli_inputs();

    let data_provider = resolve_data_provider(cli.data_provider.as_deref());
    configure_provider(Some(data_provider));

    // Resolve dates
    let (start_date, end_date) =
        ai_hedge_fund::cli::input::resolve_dates(cli.start_date, cli.end_date, Some(1));

    // Fallback to default tickers if empty
    let tickers = if cli.tickers.is_empty() {
        vec!["AAPL".to_string(), "MSFT".to_string()]
    } else {
        cli.tickers
    };

    // Determine model name and provider from CLI + environment
    let llm = resolve_llm_config(cli.model.as_deref(), cli.ollama, None);
    log_resolved_llm_config(&llm);
    let model_name = llm.model_name;
    let model_provider = llm.model_provider.value().to_string();

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
        data_provider: Some(data_provider),
    };

    let _metrics = run_backtest(&mut backtester).await?;

    Ok(())
}
