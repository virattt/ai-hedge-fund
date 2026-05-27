use crate::database::models::HedgeFundFlowRun;
use crate::models::schemas::{
    ErrorResponse, FlowRunCreateRequest, FlowRunResponse, FlowRunSummaryResponse,
    FlowRunUpdateRequest,
};
use crate::repositories::flow_repository::FlowRepository;
use crate::repositories::flow_run_repository::FlowRunRepository;
use axum::{
    extract::{Path, Query, State},
    http::StatusCode,
    routing::{get, post},
    Json, Router,
};
use serde::Deserialize;
use sqlx::SqlitePool;

pub fn router() -> Router<SqlitePool> {
    Router::new()
        .route(
            "/",
            post(create_flow_run)
                .get(get_flow_runs)
                .delete(delete_all_flow_runs),
        )
        .route("/active", get(get_active_flow_run))
        .route("/latest", get(get_latest_flow_run))
        .route("/count", get(get_flow_run_count))
        .route(
            "/:run_id",
            get(get_flow_run)
                .put(update_flow_run)
                .delete(delete_flow_run),
        )
}

fn map_run_to_response(r: HedgeFundFlowRun) -> FlowRunResponse {
    FlowRunResponse {
        id: r.id,
        flow_id: r.flow_id,
        status: r.status,
        run_number: r.run_number,
        created_at: r.created_at.map(|t| t.to_rfc3339()).unwrap_or_default(),
        updated_at: r.updated_at.map(|t| t.to_rfc3339()),
        started_at: r.started_at.map(|t| t.to_rfc3339()),
        completed_at: r.completed_at.map(|t| t.to_rfc3339()),
        request_data: r.request_data,
        results: r.results,
        error_message: r.error_message,
    }
}

fn map_run_to_summary(r: HedgeFundFlowRun) -> FlowRunSummaryResponse {
    FlowRunSummaryResponse {
        id: r.id,
        flow_id: r.flow_id,
        status: r.status,
        run_number: r.run_number,
        created_at: r.created_at.map(|t| t.to_rfc3339()).unwrap_or_default(),
        started_at: r.started_at.map(|t| t.to_rfc3339()),
        completed_at: r.completed_at.map(|t| t.to_rfc3339()),
        error_message: r.error_message,
    }
}

async fn verify_flow_exists(
    db: &SqlitePool,
    flow_id: i32,
) -> Result<(), (StatusCode, Json<ErrorResponse>)> {
    let flow_repo = FlowRepository::new(db);
    match flow_repo.get_flow_by_id(flow_id).await {
        Ok(Some(_)) => Ok(()),
        Ok(None) => Err((
            StatusCode::NOT_FOUND,
            Json(ErrorResponse {
                message: format!("Flow not found with ID: {}", flow_id),
                error: None,
            }),
        )),
        Err(e) => Err((
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ErrorResponse {
                message: "Database error verifying flow existence".to_string(),
                error: Some(e.to_string()),
            }),
        )),
    }
}

async fn create_flow_run(
    State(db): State<SqlitePool>,
    Path(flow_id): Path<i32>,
    Json(req): Json<FlowRunCreateRequest>,
) -> Result<Json<FlowRunResponse>, (StatusCode, Json<ErrorResponse>)> {
    verify_flow_exists(&db, flow_id).await?;

    let run_repo = FlowRunRepository::new(&db);
    match run_repo
        .create_flow_run(flow_id, req.request_data.as_ref())
        .await
    {
        Ok(run) => Ok(Json(map_run_to_response(run))),
        Err(e) => Err((
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ErrorResponse {
                message: "Failed to create flow run".to_string(),
                error: Some(e.to_string()),
            }),
        )),
    }
}

#[derive(Debug, Deserialize)]
struct GetFlowRunsQuery {
    #[serde(default = "default_limit")]
    limit: i32,
    #[serde(default = "default_offset")]
    offset: i32,
}

fn default_limit() -> i32 {
    50
}
fn default_offset() -> i32 {
    0
}

async fn get_flow_runs(
    State(db): State<SqlitePool>,
    Path(flow_id): Path<i32>,
    Query(query): Query<GetFlowRunsQuery>,
) -> Result<Json<Vec<FlowRunSummaryResponse>>, (StatusCode, Json<ErrorResponse>)> {
    verify_flow_exists(&db, flow_id).await?;

    let run_repo = FlowRunRepository::new(&db);
    match run_repo
        .get_flow_runs_by_flow_id(flow_id, query.limit, query.offset)
        .await
    {
        Ok(runs) => Ok(Json(runs.into_iter().map(map_run_to_summary).collect())),
        Err(e) => Err((
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ErrorResponse {
                message: "Failed to retrieve flow runs".to_string(),
                error: Some(e.to_string()),
            }),
        )),
    }
}

async fn get_active_flow_run(
    State(db): State<SqlitePool>,
    Path(flow_id): Path<i32>,
) -> Result<Json<Option<FlowRunResponse>>, (StatusCode, Json<ErrorResponse>)> {
    verify_flow_exists(&db, flow_id).await?;

    let run_repo = FlowRunRepository::new(&db);
    match run_repo.get_active_flow_run(flow_id).await {
        Ok(Some(run)) => Ok(Json(Some(map_run_to_response(run)))),
        Ok(None) => Ok(Json(None)),
        Err(e) => Err((
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ErrorResponse {
                message: "Failed to retrieve active flow run".to_string(),
                error: Some(e.to_string()),
            }),
        )),
    }
}

async fn get_latest_flow_run(
    State(db): State<SqlitePool>,
    Path(flow_id): Path<i32>,
) -> Result<Json<Option<FlowRunResponse>>, (StatusCode, Json<ErrorResponse>)> {
    verify_flow_exists(&db, flow_id).await?;

    let run_repo = FlowRunRepository::new(&db);
    match run_repo.get_latest_flow_run(flow_id).await {
        Ok(Some(run)) => Ok(Json(Some(map_run_to_response(run)))),
        Ok(None) => Ok(Json(None)),
        Err(e) => Err((
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ErrorResponse {
                message: "Failed to retrieve latest flow run".to_string(),
                error: Some(e.to_string()),
            }),
        )),
    }
}

async fn get_flow_run(
    State(db): State<SqlitePool>,
    Path((flow_id, run_id)): Path<(i32, i32)>,
) -> Result<Json<FlowRunResponse>, (StatusCode, Json<ErrorResponse>)> {
    verify_flow_exists(&db, flow_id).await?;

    let run_repo = FlowRunRepository::new(&db);
    match run_repo.get_flow_run_by_id(run_id).await {
        Ok(Some(run)) => {
            if run.flow_id != flow_id {
                return Err((
                    StatusCode::NOT_FOUND,
                    Json(ErrorResponse {
                        message: format!(
                            "Flow run with ID {} does not belong to Flow {}",
                            run_id, flow_id
                        ),
                        error: None,
                    }),
                ));
            }
            Ok(Json(map_run_to_response(run)))
        }
        Ok(None) => Err((
            StatusCode::NOT_FOUND,
            Json(ErrorResponse {
                message: format!("Flow run not found with ID: {}", run_id),
                error: None,
            }),
        )),
        Err(e) => Err((
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ErrorResponse {
                message: "Failed to retrieve flow run".to_string(),
                error: Some(e.to_string()),
            }),
        )),
    }
}

async fn update_flow_run(
    State(db): State<SqlitePool>,
    Path((flow_id, run_id)): Path<(i32, i32)>,
    Json(req): Json<FlowRunUpdateRequest>,
) -> Result<Json<FlowRunResponse>, (StatusCode, Json<ErrorResponse>)> {
    verify_flow_exists(&db, flow_id).await?;

    let run_repo = FlowRunRepository::new(&db);
    match run_repo.get_flow_run_by_id(run_id).await {
        Ok(Some(run)) => {
            if run.flow_id != flow_id {
                return Err((
                    StatusCode::NOT_FOUND,
                    Json(ErrorResponse {
                        message: format!(
                            "Flow run with ID {} does not belong to Flow {}",
                            run_id, flow_id
                        ),
                        error: None,
                    }),
                ));
            }
        }
        Ok(None) => {
            return Err((
                StatusCode::NOT_FOUND,
                Json(ErrorResponse {
                    message: format!("Flow run not found with ID: {}", run_id),
                    error: None,
                }),
            ))
        }
        Err(e) => {
            return Err((
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(ErrorResponse {
                    message: "Database error validating flow run".to_string(),
                    error: Some(e.to_string()),
                }),
            ))
        }
    }

    let status_str = req.status.as_ref().map(|s| s.as_str());
    match run_repo
        .update_flow_run(
            run_id,
            status_str,
            req.results.as_ref(),
            req.error_message.as_deref(),
        )
        .await
    {
        Ok(Some(updated)) => Ok(Json(map_run_to_response(updated))),
        Ok(None) => Err((
            StatusCode::NOT_FOUND,
            Json(ErrorResponse {
                message: format!("Flow run not found with ID: {}", run_id),
                error: None,
            }),
        )),
        Err(e) => Err((
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ErrorResponse {
                message: "Failed to update flow run".to_string(),
                error: Some(e.to_string()),
            }),
        )),
    }
}

async fn delete_flow_run(
    State(db): State<SqlitePool>,
    Path((flow_id, run_id)): Path<(i32, i32)>,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<ErrorResponse>)> {
    verify_flow_exists(&db, flow_id).await?;

    let run_repo = FlowRunRepository::new(&db);
    match run_repo.get_flow_run_by_id(run_id).await {
        Ok(Some(run)) => {
            if run.flow_id != flow_id {
                return Err((
                    StatusCode::NOT_FOUND,
                    Json(ErrorResponse {
                        message: format!(
                            "Flow run with ID {} does not belong to Flow {}",
                            run_id, flow_id
                        ),
                        error: None,
                    }),
                ));
            }
        }
        Ok(None) => {
            return Err((
                StatusCode::NOT_FOUND,
                Json(ErrorResponse {
                    message: format!("Flow run not found with ID: {}", run_id),
                    error: None,
                }),
            ))
        }
        Err(e) => {
            return Err((
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(ErrorResponse {
                    message: "Database error validating flow run".to_string(),
                    error: Some(e.to_string()),
                }),
            ))
        }
    }

    match run_repo.delete_flow_run(run_id).await {
        Ok(true) => Ok(Json(
            serde_json::json!({ "message": "Flow run deleted successfully" }),
        )),
        Ok(false) => Err((
            StatusCode::NOT_FOUND,
            Json(ErrorResponse {
                message: format!("Flow run not found with ID: {}", run_id),
                error: None,
            }),
        )),
        Err(e) => Err((
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ErrorResponse {
                message: "Failed to delete flow run".to_string(),
                error: Some(e.to_string()),
            }),
        )),
    }
}

async fn delete_all_flow_runs(
    State(db): State<SqlitePool>,
    Path(flow_id): Path<i32>,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<ErrorResponse>)> {
    verify_flow_exists(&db, flow_id).await?;

    let run_repo = FlowRunRepository::new(&db);
    match run_repo.delete_flow_runs_by_flow_id(flow_id).await {
        Ok(count) => Ok(Json(
            serde_json::json!({ "message": format!("Deleted {} flow runs successfully", count) }),
        )),
        Err(e) => Err((
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ErrorResponse {
                message: "Failed to delete all flow runs".to_string(),
                error: Some(e.to_string()),
            }),
        )),
    }
}

async fn get_flow_run_count(
    State(db): State<SqlitePool>,
    Path(flow_id): Path<i32>,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<ErrorResponse>)> {
    verify_flow_exists(&db, flow_id).await?;

    let run_repo = FlowRunRepository::new(&db);
    match run_repo.get_flow_run_count(flow_id).await {
        Ok(count) => Ok(Json(
            serde_json::json!({ "flow_id": flow_id, "total_runs": count }),
        )),
        Err(e) => Err((
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ErrorResponse {
                message: "Failed to get flow run count".to_string(),
                error: Some(e.to_string()),
            }),
        )),
    }
}
