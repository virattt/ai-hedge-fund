use anyhow::{Result, Context};
use crate::models::schemas::{GraphNode, GraphEdge};
use ai_hedge_fund::workflow::{run_hedge_fund, HedgeFundResult};
use ai_hedge_fund::cli::input::resolve_data_provider;
use ai_hedge_fund::data::provider::configure_provider;

pub fn extract_base_agent_key(unique_id: &str) -> String {
    // Unique ID format: "agent_name_suffix" or similar. Extract prefix before suffix.
    let parts: Vec<&str> = unique_id.split('_').collect();
    if parts.len() >= 2 {
        let last_part = parts[parts.len() - 1];
        if last_part.len() == 6 && last_part.chars().all(|c| c.is_ascii_alphanumeric()) {
            return parts[..parts.len() - 1].join("_");
        }
    }
    unique_id.to_string()
}

pub async fn run_graph_async(
    graph_nodes: &[GraphNode],
    _graph_edges: &[GraphEdge],
    portfolio: serde_json::Value,
    tickers: &[String],
    start_date: &str,
    end_date: &str,
    model_name: &str,
    model_provider: &str,
) -> Result<HedgeFundResult> {
    // Resolve selected analysts from graph_nodes
    let mut selected_analysts = Vec::new();
    for node in graph_nodes {
        let base_key = extract_base_agent_key(&node.id);
        if base_key != "portfolio_manager" && base_key != "risk_manager" && base_key != "start_node" {
            // Keep analyst name matching the standard config
            let standard_key = match base_key.as_str() {
                "growth_agent" => "growth_analyst".to_string(),
                "sentiment" => "sentiment_analyst".to_string(),
                "fundamentals" => "fundamentals_analyst".to_string(),
                "news_sentiment" => "news_sentiment_agent".to_string(),
                "valuation" => "valuation_analyst".to_string(),
                "technicals" => "technical_analyst".to_string(),
                other => other.to_string(),
            };
            selected_analysts.push(standard_key);
        }
    }

    // Call the core Rust hedge fund workflow driver
    let show_reasoning = false;
    let data_provider = resolve_data_provider(None);
    configure_provider(Some(data_provider));
    run_hedge_fund(
        tickers.to_vec(),
        start_date,
        end_date,
        portfolio,
        show_reasoning,
        selected_analysts,
        model_name,
        model_provider,
        Some(data_provider),
    )
    .await
    .context("Failed to run Rust hedge fund graph workflow")
}
