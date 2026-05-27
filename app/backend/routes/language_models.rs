use crate::services::ollama_service::OllamaService;
use ai_hedge_fund::llm::models::get_models_list;
use ai_hedge_fund::utils::llm::chatgpt_subscription_status_sync;
use axum::{routing::get, Json, Router};
use serde_json::json;

pub fn router() -> Router {
    Router::new()
        .route("/", get(get_language_models))
        .route("/providers", get(get_language_model_providers))
        .route(
            "/chatgpt-subscription/status",
            get(get_chatgpt_subscription_status),
        )
}

async fn get_language_models() -> Json<serde_json::Value> {
    let mut models = get_models_list();

    // Add available Ollama models
    let ollama_status = OllamaService::check_ollama_status().await;
    if ollama_status.server_running {
        let local_models = ai_hedge_fund::llm::models::get_ollama_models();
        for m in local_models {
            if ollama_status.available_models.contains(&m.model_name) {
                models.push(json!({
                    "display_name": m.display_name,
                    "model_name": m.model_name,
                    "provider": "Ollama"
                }));
            }
        }
    }

    Json(json!({ "models": models }))
}

async fn get_language_model_providers() -> Json<serde_json::Value> {
    let models = get_models_list();

    let mut providers: std::collections::HashMap<String, serde_json::Value> =
        std::collections::HashMap::new();
    for model in models {
        if let Some(provider_name) = model.get("provider").and_then(|v| v.as_str()) {
            let entry = providers
                .entry(provider_name.to_string())
                .or_insert_with(|| {
                    json!({
                        "name": provider_name,
                        "models": []
                    })
                });

            if let Some(models_arr) = entry.get_mut("models").and_then(|v| v.as_array_mut()) {
                models_arr.push(json!({
                    "display_name": model.get("display_name"),
                    "model_name": model.get("model_name")
                }));
            }
        }
    }

    let providers_list: Vec<serde_json::Value> = providers.into_values().collect();
    Json(json!({ "providers": providers_list }))
}

async fn get_chatgpt_subscription_status() -> Json<serde_json::Value> {
    let status = chatgpt_subscription_status_sync();
    Json(json!({
        "authenticated": status.authenticated,
        "email": status.email,
    }))
}
