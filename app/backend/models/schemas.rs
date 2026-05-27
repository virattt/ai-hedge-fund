use ai_hedge_fund::llm::models::ModelProvider;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum FlowRunStatus {
    Idle,
    InProgress,
    Complete,
    Error,
}

impl FlowRunStatus {
    pub fn as_str(&self) -> &'static str {
        match self {
            FlowRunStatus::Idle => "IDLE",
            FlowRunStatus::InProgress => "IN_PROGRESS",
            FlowRunStatus::Complete => "COMPLETE",
            FlowRunStatus::Error => "ERROR",
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentModelConfig {
    pub agent_id: String,
    pub model_name: Option<String>,
    pub model_provider: Option<ModelProvider>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PortfolioPosition {
    pub ticker: String,
    pub quantity: f64,
    pub trade_price: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GraphNode {
    pub id: String,
    pub r#type: Option<String>,
    pub data: Option<serde_json::Value>,
    pub position: Option<serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GraphEdge {
    pub id: String,
    pub source: String,
    pub target: String,
    pub r#type: Option<String>,
    pub data: Option<serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HedgeFundResponse {
    pub decisions: serde_json::Value,
    pub analyst_signals: serde_json::Value,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ErrorResponse {
    pub message: String,
    pub error: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BaseHedgeFundRequest {
    pub tickers: Vec<String>,
    pub graph_nodes: Vec<GraphNode>,
    pub graph_edges: Vec<GraphEdge>,
    pub agent_models: Option<Vec<AgentModelConfig>>,
    pub model_name: Option<String>,
    pub model_provider: Option<ModelProvider>,
    pub margin_requirement: f64,
    pub portfolio_positions: Option<Vec<PortfolioPosition>>,
    pub api_keys: Option<HashMap<String, String>>,
}

impl BaseHedgeFundRequest {
    pub fn get_agent_ids(&self) -> Vec<String> {
        self.graph_nodes.iter().map(|n| n.id.clone()).collect()
    }

    pub fn get_agent_model_config(&self, agent_id: &str) -> (String, ModelProvider) {
        if let Some(ref configs) = self.agent_models {
            let base_agent_key = extract_base_agent_key(agent_id);
            for config in configs {
                let config_base_key = extract_base_agent_key(&config.agent_id);
                if config.agent_id == agent_id || config_base_key == base_agent_key {
                    return (
                        config.model_name.clone().unwrap_or_else(|| {
                            self.model_name
                                .clone()
                                .unwrap_or_else(|| "gpt-4.1".to_string())
                        }),
                        config.model_provider.clone().unwrap_or_else(|| {
                            self.model_provider.clone().unwrap_or(ModelProvider::OpenAI)
                        }),
                    );
                }
            }
        }
        (
            self.model_name
                .clone()
                .unwrap_or_else(|| "gpt-4.1".to_string()),
            self.model_provider.clone().unwrap_or(ModelProvider::OpenAI),
        )
    }
}

fn extract_base_agent_key(agent_id: &str) -> String {
    agent_id.split('-').next().unwrap_or(agent_id).to_string()
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BacktestRequest {
    #[serde(flatten)]
    pub base: BaseHedgeFundRequest,
    pub start_date: String,
    pub end_date: String,
    pub initial_capital: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BacktestDayResult {
    pub date: String,
    pub portfolio_value: f64,
    pub cash: f64,
    pub decisions: HashMap<String, serde_json::Value>,
    pub executed_trades: HashMap<String, i32>,
    pub analyst_signals: HashMap<String, serde_json::Value>,
    pub current_prices: HashMap<String, f64>,
    pub long_exposure: f64,
    pub short_exposure: f64,
    pub gross_exposure: f64,
    pub net_exposure: f64,
    pub long_short_ratio: Option<f64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BacktestPerformanceMetrics {
    pub sharpe_ratio: Option<f64>,
    pub sortino_ratio: Option<f64>,
    pub max_drawdown: Option<f64>,
    pub max_drawdown_date: Option<String>,
    pub long_short_ratio: Option<f64>,
    pub gross_exposure: Option<f64>,
    pub net_exposure: Option<f64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BacktestResponse {
    pub results: Vec<BacktestDayResult>,
    pub performance_metrics: BacktestPerformanceMetrics,
    pub final_portfolio: serde_json::Value,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HedgeFundRequest {
    #[serde(flatten)]
    pub base: BaseHedgeFundRequest,
    pub end_date: Option<String>,
    pub start_date: Option<String>,
    pub initial_cash: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FlowCreateRequest {
    pub name: String,
    pub description: Option<String>,
    pub nodes: Vec<serde_json::Value>,
    pub edges: Vec<serde_json::Value>,
    pub viewport: Option<serde_json::Value>,
    pub data: Option<serde_json::Value>,
    pub is_template: bool,
    pub tags: Option<Vec<String>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FlowUpdateRequest {
    pub name: Option<String>,
    pub description: Option<String>,
    pub nodes: Option<Vec<serde_json::Value>>,
    pub edges: Option<Vec<serde_json::Value>>,
    pub viewport: Option<serde_json::Value>,
    pub data: Option<serde_json::Value>,
    pub is_template: Option<bool>,
    pub tags: Option<Vec<String>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FlowResponse {
    pub id: i32,
    pub name: String,
    pub description: Option<String>,
    pub nodes: Vec<serde_json::Value>,
    pub edges: Vec<serde_json::Value>,
    pub viewport: Option<serde_json::Value>,
    pub data: Option<serde_json::Value>,
    pub is_template: bool,
    pub tags: Option<serde_json::Value>,
    pub created_at: String,
    pub updated_at: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FlowSummaryResponse {
    pub id: i32,
    pub name: String,
    pub description: Option<String>,
    pub is_template: bool,
    pub tags: Option<serde_json::Value>,
    pub created_at: String,
    pub updated_at: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FlowRunCreateRequest {
    pub request_data: Option<serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FlowRunUpdateRequest {
    pub status: Option<FlowRunStatus>,
    pub results: Option<serde_json::Value>,
    pub error_message: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FlowRunResponse {
    pub id: i32,
    pub flow_id: i32,
    pub status: String,
    pub run_number: i32,
    pub created_at: String,
    pub updated_at: Option<String>,
    pub started_at: Option<String>,
    pub completed_at: Option<String>,
    pub request_data: Option<serde_json::Value>,
    pub results: Option<serde_json::Value>,
    pub error_message: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FlowRunSummaryResponse {
    pub id: i32,
    pub flow_id: i32,
    pub status: String,
    pub run_number: i32,
    pub created_at: String,
    pub started_at: Option<String>,
    pub completed_at: Option<String>,
    pub error_message: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApiKeyCreateRequest {
    pub provider: String,
    pub key_value: String,
    pub description: Option<String>,
    pub is_active: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApiKeyUpdateRequest {
    pub key_value: Option<String>,
    pub description: Option<String>,
    pub is_active: Option<bool>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApiKeyResponse {
    pub id: i32,
    pub provider: String,
    pub key_value: String,
    pub is_active: bool,
    pub description: Option<String>,
    pub created_at: String,
    pub updated_at: Option<String>,
    pub last_used: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApiKeySummaryResponse {
    pub id: i32,
    pub provider: String,
    pub is_active: bool,
    pub description: Option<String>,
    pub created_at: String,
    pub updated_at: Option<String>,
    pub last_used: Option<String>,
    pub has_key: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApiKeyBulkUpdateRequest {
    pub api_keys: Vec<ApiKeyCreateRequest>,
}
