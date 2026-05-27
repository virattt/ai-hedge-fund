use axum::Router;
use sqlx::SqlitePool;

pub mod api_keys;
pub mod flow_runs;
pub mod flows;
pub mod health;
pub mod hedge_fund;
pub mod language_models;
pub mod ollama;
pub mod storage;

pub fn api_router() -> Router<SqlitePool> {
    Router::new()
        .merge(health::router().with_state(()))
        .nest("/hedge-fund", hedge_fund::router())
        .nest("/storage", storage::router().with_state(()))
        .nest("/flows", flows::router())
        .nest("/flows/:flow_id/runs", flow_runs::router())
        .nest("/ollama", ollama::router().with_state(()))
        .nest("/language-models", language_models::router().with_state(()))
        .nest("/api-keys", api_keys::router())
}
