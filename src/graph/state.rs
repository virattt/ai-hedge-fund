// Source: src/graph/state.py
//! Sibling to src/graph/state.py
//! Defines the shared state object passed between different analyst, risk management, and portfolio manager agents.

use std::collections::HashMap;

/// AgentState is a structured representation of the LangGraph state.
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct AgentState {
    pub messages: Vec<serde_json::Value>,
    pub data: HashMap<String, serde_json::Value>,
    pub metadata: HashMap<String, serde_json::Value>,
}

/// Utility function to display the reasoning of a given agent.
pub fn show_agent_reasoning(output: &serde_json::Value, agent_name: &str) {
    println!("\n========== {} ==========", agent_name);
    if let Ok(pretty) = serde_json::to_string_pretty(output) {
        println!("{}", pretty);
    } else {
        println!("{:?}", output);
    }
    println!("================================================");
}
