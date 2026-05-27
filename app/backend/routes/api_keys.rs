use axum::{
    routing::{get, post, put, delete, patch},
    Router,
    Json,
    extract::{Path, State},
    http::StatusCode,
};
use sqlx::SqlitePool;
use crate::repositories::api_key_repository::ApiKeyRepository;
use crate::models::schemas::{
    ApiKeyCreateRequest,
    ApiKeyUpdateRequest,
    ApiKeyResponse,
    ApiKeySummaryResponse,
    ApiKeyBulkUpdateRequest,
    ErrorResponse,
};

pub fn router() -> Router<SqlitePool> {
    Router::new()
        .route("/", post(create_or_update_api_key).get(get_api_keys))
        .route("/bulk", post(bulk_update_api_keys))
        .route("/:provider", get(get_api_key).put(update_api_key).delete(delete_api_key))
        .route("/:provider/deactivate", patch(deactivate_api_key))
        .route("/:provider/last-used", patch(update_last_used))
}

fn map_key_to_response(k: crate::database::models::ApiKey) -> ApiKeyResponse {
    ApiKeyResponse {
        id: k.id,
        provider: k.provider,
        key_value: k.key_value,
        is_active: k.is_active,
        description: k.description,
        created_at: k.created_at.map(|t| t.to_rfc3339()).unwrap_or_default(),
        updated_at: k.updated_at.map(|t| t.to_rfc3339()),
        last_used: k.last_used.map(|t| t.to_rfc3339()),
    }
}

fn map_key_to_summary(k: crate::database::models::ApiKey) -> ApiKeySummaryResponse {
    ApiKeySummaryResponse {
        id: k.id,
        provider: k.provider,
        is_active: k.is_active,
        description: k.description,
        created_at: k.created_at.map(|t| t.to_rfc3339()).unwrap_or_default(),
        updated_at: k.updated_at.map(|t| t.to_rfc3339()),
        last_used: k.last_used.map(|t| t.to_rfc3339()),
        has_key: !k.key_value.is_empty(),
    }
}

async fn create_or_update_api_key(
    State(db): State<SqlitePool>,
    Json(req): Json<ApiKeyCreateRequest>,
) -> Result<Json<ApiKeyResponse>, (StatusCode, Json<ErrorResponse>)> {
    let repo = ApiKeyRepository::new(&db);
    match repo.create_or_update_api_key(&req.provider, &req.key_value, req.description.as_deref(), req.is_active).await {
        Ok(key) => Ok(Json(map_key_to_response(key))),
        Err(e) => Err((
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ErrorResponse {
                message: "Failed to create or update API key".to_string(),
                error: Some(e.to_string()),
            }),
        )),
    }
}

async fn get_api_keys(
    State(db): State<SqlitePool>,
) -> Result<Json<Vec<ApiKeySummaryResponse>>, (StatusCode, Json<ErrorResponse>)> {
    let repo = ApiKeyRepository::new(&db);
    match repo.get_all_api_keys(true).await {
        Ok(keys) => Ok(Json(keys.into_iter().map(map_key_to_summary).collect())),
        Err(e) => Err((
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ErrorResponse {
                message: "Failed to retrieve API keys".to_string(),
                error: Some(e.to_string()),
            }),
        )),
    }
}

async fn get_api_key(
    State(db): State<SqlitePool>,
    Path(provider): Path<String>,
) -> Result<Json<ApiKeyResponse>, (StatusCode, Json<ErrorResponse>)> {
    let repo = ApiKeyRepository::new(&db);
    match repo.get_api_key_by_provider(&provider).await {
        Ok(Some(key)) => Ok(Json(map_key_to_response(key))),
        Ok(None) => Err((
            StatusCode::NOT_FOUND,
            Json(ErrorResponse {
                message: format!("API key not found for provider: {}", provider),
                error: None,
            }),
        )),
        Err(e) => Err((
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ErrorResponse {
                message: "Failed to retrieve API key".to_string(),
                error: Some(e.to_string()),
            }),
        )),
    }
}

async fn update_api_key(
    State(db): State<SqlitePool>,
    Path(provider): Path<String>,
    Json(req): Json<ApiKeyUpdateRequest>,
) -> Result<Json<ApiKeyResponse>, (StatusCode, Json<ErrorResponse>)> {
    let repo = ApiKeyRepository::new(&db);
    match repo.update_api_key(&provider, req.key_value.as_deref(), req.description.as_deref(), req.is_active).await {
        Ok(Some(key)) => Ok(Json(map_key_to_response(key))),
        Ok(None) => Err((
            StatusCode::NOT_FOUND,
            Json(ErrorResponse {
                message: format!("API key not found for provider: {}", provider),
                error: None,
            }),
        )),
        Err(e) => Err((
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ErrorResponse {
                message: "Failed to update API key".to_string(),
                error: Some(e.to_string()),
            }),
        )),
    }
}

async fn delete_api_key(
    State(db): State<SqlitePool>,
    Path(provider): Path<String>,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<ErrorResponse>)> {
    let repo = ApiKeyRepository::new(&db);
    match repo.delete_api_key(&provider).await {
        Ok(true) => Ok(Json(serde_json::json!({ "message": "API key deleted successfully" }))),
        Ok(false) => Err((
            StatusCode::NOT_FOUND,
            Json(ErrorResponse {
                message: format!("API key not found for provider: {}", provider),
                error: None,
            }),
        )),
        Err(e) => Err((
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ErrorResponse {
                message: "Failed to delete API key".to_string(),
                error: Some(e.to_string()),
            }),
        )),
    }
}

async fn deactivate_api_key(
    State(db): State<SqlitePool>,
    Path(provider): Path<String>,
) -> Result<Json<ApiKeySummaryResponse>, (StatusCode, Json<ErrorResponse>)> {
    let repo = ApiKeyRepository::new(&db);
    match repo.deactivate_api_key(&provider).await {
        Ok(true) => {
            if let Ok(Some(key)) = repo.get_api_key_by_provider(&provider).await {
                Ok(Json(map_key_to_summary(key)))
            } else {
                Err((
                    StatusCode::INTERNAL_SERVER_ERROR,
                    Json(ErrorResponse {
                        message: "Failed to reload key after deactivation".to_string(),
                        error: None,
                    }),
                ))
            }
        }
        Ok(false) => Err((
            StatusCode::NOT_FOUND,
            Json(ErrorResponse {
                message: format!("API key not found for provider: {}", provider),
                error: None,
            }),
        )),
        Err(e) => Err((
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ErrorResponse {
                message: "Failed to deactivate API key".to_string(),
                error: Some(e.to_string()),
            }),
        )),
    }
}

async fn update_last_used(
    State(db): State<SqlitePool>,
    Path(provider): Path<String>,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<ErrorResponse>)> {
    let repo = ApiKeyRepository::new(&db);
    match repo.update_last_used(&provider).await {
        Ok(true) => Ok(Json(serde_json::json!({ "message": "Last used timestamp updated" }))),
        Ok(false) => Err((
            StatusCode::NOT_FOUND,
            Json(ErrorResponse {
                message: format!("API key not found or inactive for provider: {}", provider),
                error: None,
            }),
        )),
        Err(e) => Err((
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ErrorResponse {
                message: "Failed to update last used timestamp".to_string(),
                error: Some(e.to_string()),
            }),
        )),
    }
}

async fn bulk_update_api_keys(
    State(db): State<SqlitePool>,
    Json(req): Json<ApiKeyBulkUpdateRequest>,
) -> Result<Json<Vec<ApiKeyResponse>>, (StatusCode, Json<ErrorResponse>)> {
    let repo = ApiKeyRepository::new(&db);
    let mut updated_keys = Vec::new();
    for key_req in req.api_keys {
        match repo.create_or_update_api_key(&key_req.provider, &key_req.key_value, key_req.description.as_deref(), key_req.is_active).await {
            Ok(k) => updated_keys.push(map_key_to_response(k)),
            Err(e) => return Err((
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(ErrorResponse {
                    message: "Failed to bulk update API keys".to_string(),
                    error: Some(e.to_string()),
                }),
            )),
        }
    }
    Ok(Json(updated_keys))
}
