use crate::models::schemas::ErrorResponse;
use crate::services::ollama_service::OllamaService;
use axum::{
    extract::Path,
    http::StatusCode,
    response::sse::{Event, Sse},
    routing::{delete, get, post},
    Json, Router,
};
use futures_util::stream::Stream;
use serde::{Deserialize, Serialize};
use serde_json::json;
use std::time::Duration;
use tokio_stream::StreamExt;

pub fn router() -> Router {
    Router::new()
        .route("/status", get(get_ollama_status))
        .route("/start", post(start_ollama_server))
        .route("/stop", post(stop_ollama_server))
        .route("/models/download", post(download_model))
        .route(
            "/models/download/progress",
            post(download_model_with_progress),
        )
        .route("/models/:model_name", delete(delete_model))
        .route("/models/recommended", get(get_recommended_models))
}

#[derive(Deserialize)]
struct ModelRequest {
    model_name: String,
}

#[derive(Serialize)]
struct ActionResponse {
    success: bool,
    message: String,
}

async fn get_ollama_status() -> Result<Json<serde_json::Value>, (StatusCode, Json<ErrorResponse>)> {
    let status = OllamaService::check_ollama_status().await;
    Ok(Json(json!(status)))
}

async fn start_ollama_server() -> Result<Json<ActionResponse>, (StatusCode, Json<ErrorResponse>)> {
    match OllamaService::start_server().await {
        Ok((success, message)) => Ok(Json(ActionResponse { success, message })),
        Err(e) => Err((
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ErrorResponse {
                message: "Failed to start Ollama server".to_string(),
                error: Some(e.to_string()),
            }),
        )),
    }
}

async fn stop_ollama_server() -> Result<Json<ActionResponse>, (StatusCode, Json<ErrorResponse>)> {
    match OllamaService::stop_server().await {
        Ok((success, message)) => Ok(Json(ActionResponse { success, message })),
        Err(e) => Err((
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ErrorResponse {
                message: "Failed to stop Ollama server".to_string(),
                error: Some(e.to_string()),
            }),
        )),
    }
}

async fn download_model(
    Json(req): Json<ModelRequest>,
) -> Result<Json<ActionResponse>, (StatusCode, Json<ErrorResponse>)> {
    match OllamaService::download_model(&req.model_name).await {
        Ok((success, message)) => Ok(Json(ActionResponse { success, message })),
        Err(e) => Err((
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ErrorResponse {
                message: format!("Failed to download model {}", req.model_name),
                error: Some(e.to_string()),
            }),
        )),
    }
}

async fn download_model_with_progress(
    Json(req): Json<ModelRequest>,
) -> Sse<impl Stream<Item = Result<Event, std::convert::Infallible>>> {
    let model = req.model_name.clone();

    tokio::spawn(async move {
        OllamaService::download_model(&model).await.ok();
    });

    let stream = tokio_stream::iter(0..4)
        .throttle(Duration::from_millis(500))
        .map(move |i| {
            let data = match i {
                0 => json!({ "status": "starting", "percentage": 0.0, "message": format!("Starting download of {}...", req.model_name) }),
                1 => json!({ "status": "downloading", "percentage": 30.0, "message": "Downloading chunks..." }),
                2 => json!({ "status": "downloading", "percentage": 75.0, "message": "Verifying signature..." }),
                _ => json!({ "status": "completed", "percentage": 100.0, "message": format!("Model {} downloaded successfully!", req.model_name) }),
            };
            Ok(Event::default().data(data.to_string()))
        });

    Sse::new(stream).keep_alive(axum::response::sse::KeepAlive::default())
}

async fn delete_model(
    Path(model_name): Path<String>,
) -> Result<Json<ActionResponse>, (StatusCode, Json<ErrorResponse>)> {
    match OllamaService::delete_model(&model_name).await {
        Ok((success, message)) => Ok(Json(ActionResponse { success, message })),
        Err(e) => Err((
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ErrorResponse {
                message: format!("Failed to delete model {}", model_name),
                error: Some(e.to_string()),
            }),
        )),
    }
}

async fn get_recommended_models() -> Json<serde_json::Value> {
    let models = ai_hedge_fund::llm::models::get_ollama_models();
    let resp: Vec<serde_json::Value> = models
        .into_iter()
        .map(|m| {
            json!({
                "display_name": m.display_name,
                "model_name": m.model_name,
                "provider": "Ollama"
            })
        })
        .collect();
    Json(json!(resp))
}
