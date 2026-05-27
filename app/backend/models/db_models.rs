use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize, sqlx::FromRow)]
pub struct HedgeFundFlow {
    pub id: i32,
    pub created_at: Option<DateTime<Utc>>,
    pub updated_at: Option<DateTime<Utc>>,
    pub name: String,
    pub description: Option<String>,
    pub nodes: serde_json::Value,
    pub edges: serde_json::Value,
    pub viewport: Option<serde_json::Value>,
    pub data: Option<serde_json::Value>,
    pub is_template: bool,
    pub tags: Option<serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize, sqlx::FromRow)]
pub struct HedgeFundFlowRun {
    pub id: i32,
    pub flow_id: i32,
    pub created_at: Option<DateTime<Utc>>,
    pub updated_at: Option<DateTime<Utc>>,
    pub status: String,
    pub started_at: Option<DateTime<Utc>>,
    pub completed_at: Option<DateTime<Utc>>,
    pub trading_mode: String,
    pub schedule: Option<String>,
    pub duration: Option<String>,
    pub request_data: Option<serde_json::Value>,
    pub initial_portfolio: Option<serde_json::Value>,
    pub final_portfolio: Option<serde_json::Value>,
    pub results: Option<serde_json::Value>,
    pub error_message: Option<String>,
    pub run_number: i32,
}

#[derive(Debug, Clone, Serialize, Deserialize, sqlx::FromRow)]
pub struct HedgeFundFlowRunCycle {
    pub id: i32,
    pub flow_run_id: i32,
    pub cycle_number: i32,
    pub created_at: Option<DateTime<Utc>>,
    pub started_at: DateTime<Utc>,
    pub completed_at: Option<DateTime<Utc>>,
    pub analyst_signals: Option<serde_json::Value>,
    pub trading_decisions: Option<serde_json::Value>,
    pub executed_trades: Option<serde_json::Value>,
    pub portfolio_snapshot: Option<serde_json::Value>,
    pub performance_metrics: Option<serde_json::Value>,
    pub status: String,
    pub error_message: Option<String>,
    pub llm_calls_count: Option<i32>,
    pub api_calls_count: Option<i32>,
    pub estimated_cost: Option<String>,
    pub trigger_reason: Option<String>,
    pub market_conditions: Option<serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize, sqlx::FromRow)]
pub struct ApiKey {
    pub id: i32,
    pub created_at: Option<DateTime<Utc>>,
    pub updated_at: Option<DateTime<Utc>>,
    pub provider: String,
    pub key_value: String,
    pub is_active: bool,
    pub description: Option<String>,
    pub last_used: Option<DateTime<Utc>>,
}
