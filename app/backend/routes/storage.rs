use axum::{routing::post, Router, Json, http::StatusCode};
use serde::Deserialize;
use crate::models::schemas::ErrorResponse;

pub fn router() -> Router {
    Router::new().route("/save-json", post(save_json_file))
}

#[derive(Deserialize)]
struct SaveJsonRequest {
    filename: String,
    data: serde_json::Value,
}

async fn save_json_file(
    Json(req): Json<SaveJsonRequest>,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<ErrorResponse>)> {
    let outputs_dir = std::path::Path::new("outputs");
    if let Err(e) = std::fs::create_dir_all(outputs_dir) {
        return Err((
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ErrorResponse {
                message: "Failed to create outputs directory".to_string(),
                error: Some(e.to_string()),
            }),
        ));
    }

    let file_path = outputs_dir.join(&req.filename);
    let json_str = match serde_json::to_string_pretty(&req.data) {
        Ok(s) => s,
        Err(e) => return Err((
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ErrorResponse {
                message: "Failed to serialize JSON data".to_string(),
                error: Some(e.to_string()),
            }),
        )),
    };

    if let Err(e) = std::fs::write(&file_path, json_str) {
        return Err((
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ErrorResponse {
                message: format!("Failed to write to file: {:?}", file_path),
                error: Some(e.to_string()),
            }),
        ));
    }

    Ok(Json(serde_json::json!({
        "success": true,
        "message": format!("File saved successfully to {:?}", file_path),
        "filename": req.filename
    })))
}
