// Source: src/main.py
//! Main entry point for the AI Hedge Fund trading simulator.
//! Consolidates analyst recommendations, performs risk management, and outputs final portfolio decisions.

use anyhow::Result;
use ai_hedge_fund::workflow::run_hedge_fund;

#[tokio::main]
async fn main() -> Result<()> {
    dotenvy::dotenv().ok();
    println!("Welcome to the AI Hedge Fund (Rust Port)!");

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
        "gpt-4",
        "OpenAI",
    ).await?;

    println!("Workflow result: {:?}", result);
    Ok(())
}
