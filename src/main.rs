// Source: src/main.py
//! Main entry point for the AI Hedge Fund trading simulator.
//! Consolidates analyst recommendations, performs risk management, and outputs final portfolio decisions.

use anyhow::Result;
use ai_hedge_fund::cli::input::resolve_data_provider;
use ai_hedge_fund::data::provider::configure_provider;
use ai_hedge_fund::utils::llm::{log_resolved_llm_config, resolve_llm_config};
use ai_hedge_fund::workflow::run_hedge_fund;

#[tokio::main]
async fn main() -> Result<()> {
    dotenvy::dotenv().ok();

    if let Some(result) = ai_hedge_fund::cli::chatgpt::try_run_from_env().await {
        return result;
    }

    println!("Welcome to the AI Hedge Fund (Rust Port)!");

    let data_provider = resolve_data_provider(None);
    configure_provider(Some(data_provider));

    let llm = resolve_llm_config(None, false, None);
    log_resolved_llm_config(&llm);

    let tickers = vec!["AAPL".to_string(), "MSFT".to_string()];
    let start_date = "2026-01-01";
    let end_date = "2026-01-05";
    
    let portfolio = serde_json::json!({
        "cash": 100000.0,
        "positions": {}
    });

    let result = run_hedge_fund(
        tickers,
        start_date,
        end_date,
        portfolio,
        true,
        vec!["warren_buffett".to_string(), "ben_graham".to_string()],
        &llm.model_name,
        llm.model_provider.value(),
        Some(data_provider),
    ).await?;

    println!("Workflow result: {:?}", result);
    Ok(())
}
