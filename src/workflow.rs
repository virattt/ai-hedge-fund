// Source: src/workflow.rs
//! Core workflow orchestrator for the AI Hedge Fund trading simulator.

use anyhow::{Result, Context};
use std::collections::HashMap;

use crate::graph::state::AgentState;
use crate::agents::fundamentals::fundamentals_analyst_agent;
use crate::agents::technicals::technical_analyst_agent;
use crate::agents::warren_buffett::warren_buffett_agent;
use crate::agents::ben_graham::ben_graham_agent;
use crate::agents::charlie_munger::charlie_munger_agent;
use crate::agents::michael_burry::michael_burry_agent;
use crate::agents::cathie_wood::cathie_wood_agent;
use crate::agents::bill_ackman::bill_ackman_agent;
use crate::agents::aswath_damodaran::aswath_damodaran_agent;
use crate::agents::growth_agent::growth_analyst_agent;
use crate::agents::mohnish_pabrai::mohnish_pabrai_agent;
use crate::agents::nassim_taleb::nassim_taleb_agent;
use crate::agents::news_sentiment::news_sentiment_agent;
use crate::agents::peter_lynch::peter_lynch_agent;
use crate::agents::phil_fisher::phil_fisher_agent;
use crate::agents::rakesh_jhunjhunwala::rakesh_jhunjhunwala_agent;
use crate::agents::sentiment::sentiment_analyst_agent;
use crate::agents::stanley_druckenmiller::stanley_druckenmiller_agent;
use crate::agents::valuation::valuation_analyst_agent;
use crate::agents::risk_manager::risk_management_agent;
use crate::agents::portfolio_manager::portfolio_management_agent;

/// Result structure returned by running the hedge fund flow.
#[derive(Debug, serde::Serialize, serde::Deserialize, Clone)]
pub struct HedgeFundResult {
    pub decisions: Option<serde_json::Value>,
    pub analyst_signals: HashMap<String, serde_json::Value>,
}

/// Parses the JSON string from the portfolio manager's agent response.
pub fn parse_hedge_fund_response(response: &str) -> Option<serde_json::Value> {
    serde_json::from_str(response).ok()
}

/// Runs the AI Hedge Fund agent workflow for a set of tickers over a date range.
pub async fn run_hedge_fund(
    tickers: Vec<String>,
    _start_date: &str,
    end_date: &str,
    portfolio: serde_json::Value,
    show_reasoning: bool,
    selected_analysts: Vec<String>,
    model_name: &str,
    model_provider: &str,
) -> Result<HedgeFundResult> {
    println!("Starting parallel hedge fund execution workflow...");
    
    // Resolve lookback start (30 days lookback)
    let end_dt = chrono::NaiveDate::parse_from_str(end_date, "%Y-%m-%d")
        .context("Failed to parse end_date in run_hedge_fund")?;
    let lookback_start = (end_dt - chrono::Duration::days(30)).format("%Y-%m-%d").to_string();

    let api_key = std::env::var("FINANCIAL_DATASETS_API_KEY").ok();

    // 1. Initialize input state
    let mut state = AgentState {
        messages: Vec::new(),
        data: HashMap::new(),
        metadata: HashMap::new(),
    };

    state.data.insert("tickers".to_string(), serde_json::to_value(tickers.clone())?);
    state.data.insert("start_date".to_string(), serde_json::json!(lookback_start));
    state.data.insert("end_date".to_string(), serde_json::json!(end_date));
    state.data.insert("portfolio".to_string(), portfolio);
    state.data.insert("analyst_signals".to_string(), serde_json::json!({}));

    state.metadata.insert("show_reasoning".to_string(), serde_json::json!(show_reasoning));
    state.metadata.insert("model_name".to_string(), serde_json::json!(model_name));
    state.metadata.insert("model_provider".to_string(), serde_json::json!(model_provider));
    
    if let Some(key) = api_key {
        state.metadata.insert("FINANCIAL_DATASETS_API_KEY".to_string(), serde_json::json!(key));
    }

    // 2. Resolve selected analysts (default to all registered if empty)
    let mut selected = selected_analysts;
    if selected.is_empty() {
        selected = vec![
            "warren_buffett".to_string(),
            "ben_graham".to_string(),
            "charlie_munger".to_string(),
            "michael_burry".to_string(),
            "cathie_wood".to_string(),
            "bill_ackman".to_string(),
            "aswath_damodaran".to_string(),
            "growth_analyst".to_string(),
            "mohnish_pabrai".to_string(),
            "nassim_taleb".to_string(),
            "peter_lynch".to_string(),
            "phil_fisher".to_string(),
            "rakesh_jhunjhunwala".to_string(),
            "stanley_druckenmiller".to_string(),
            "technical_analyst".to_string(),
            "fundamentals_analyst".to_string(),
            "news_sentiment_analyst".to_string(),
            "sentiment_analyst".to_string(),
            "valuation_analyst".to_string(),
        ];
    }

    // 3. Execute selected analysts in parallel
    let mut tasks: Vec<tokio::task::JoinHandle<anyhow::Result<AgentState>>> = Vec::new();
    for analyst in &selected {
        let mut state_clone = state.clone();
        let analyst_clone = analyst.clone();
        tasks.push(tokio::spawn(async move {
            match analyst_clone.as_str() {
                "warren_buffett" => warren_buffett_agent(&mut state_clone, "warren_buffett_agent").await,
                "ben_graham" => ben_graham_agent(&mut state_clone, "ben_graham_agent").await,
                "charlie_munger" => charlie_munger_agent(&mut state_clone, "charlie_munger_agent").await,
                "michael_burry" => michael_burry_agent(&mut state_clone, "michael_burry_agent").await,
                "cathie_wood" => cathie_wood_agent(&mut state_clone, "cathie_wood_agent").await,
                "bill_ackman" => bill_ackman_agent(&mut state_clone, "bill_ackman_agent").await,
                "aswath_damodaran" => aswath_damodaran_agent(&mut state_clone, "aswath_damodaran_agent").await,
                "growth_analyst" => growth_analyst_agent(&mut state_clone, "growth_analyst_agent").await,
                "mohnish_pabrai" => mohnish_pabrai_agent(&mut state_clone, "mohnish_pabrai_agent").await,
                "nassim_taleb" => nassim_taleb_agent(&mut state_clone, "nassim_taleb_agent").await,
                "peter_lynch" => peter_lynch_agent(&mut state_clone, "peter_lynch_agent").await,
                "phil_fisher" => phil_fisher_agent(&mut state_clone, "phil_fisher_agent").await,
                "rakesh_jhunjhunwala" => rakesh_jhunjhunwala_agent(&mut state_clone, "rakesh_jhunjhunwala_agent").await,
                "stanley_druckenmiller" => stanley_druckenmiller_agent(&mut state_clone, "stanley_druckenmiller_agent").await,
                "technical_analyst" => technical_analyst_agent(&mut state_clone, "technical_analyst_agent").await,
                "fundamentals_analyst" => fundamentals_analyst_agent(&mut state_clone, "fundamentals_analyst_agent").await,
                "news_sentiment_analyst" => news_sentiment_agent(&mut state_clone, "news_sentiment_agent").await,
                "sentiment_analyst" => sentiment_analyst_agent(&mut state_clone, "sentiment_analyst_agent").await,
                "valuation_analyst" => valuation_analyst_agent(&mut state_clone, "valuation_analyst_agent").await,
                _ => Ok(()),
            }?;
            Ok(state_clone)
        }));
    }

    let results = futures::future::join_all(tasks).await;

    // 4. Merge all concurrent results back into the main state
    for res in results {
        if let Ok(Ok(completed_state)) = res {
            if let Some(completed_signals) = completed_state.data.get("analyst_signals").and_then(|v| v.as_object()) {
                for (k, v) in completed_signals {
                    if let Some(main_signals) = state.data.get_mut("analyst_signals").and_then(|v| v.as_object_mut()) {
                        main_signals.insert(k.clone(), v.clone());
                    }
                }
            }
        }
    }

    // 5. Sequentially run sizing and consensus agents
    risk_management_agent(&mut state, "risk_management_agent").await?;
    portfolio_management_agent(&mut state, "portfolio_manager").await?;

    // 6. Retrieve and return final outputs
    let decisions = state.data.get("decisions").cloned();
    let analyst_signals = state.data.get("analyst_signals")
        .and_then(|v| serde_json::from_value::<HashMap<String, serde_json::Value>>(v.clone()).ok())
        .unwrap_or_default();

    Ok(HedgeFundResult {
        decisions,
        analyst_signals,
    })
}
