use crate::database::models::HedgeFundFlow;
use crate::models::schemas::{
    ErrorResponse, FlowCreateRequest, FlowResponse, FlowSummaryResponse, FlowUpdateRequest,
};
use crate::repositories::flow_repository::{FlowCreateInput, FlowRepository, FlowUpdateInput};
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
        .route("/", post(create_flow).get(get_flows))
        .route(
            "/:flow_id",
            get(get_flow).put(update_flow).delete(delete_flow),
        )
        .route("/:flow_id/duplicate", post(duplicate_flow))
        .route("/search/:name", get(search_flows))
}

fn map_flow_to_response(f: HedgeFundFlow) -> FlowResponse {
    FlowResponse {
        id: f.id,
        name: f.name,
        description: f.description,
        nodes: serde_json::from_value(f.nodes).unwrap_or_default(),
        edges: serde_json::from_value(f.edges).unwrap_or_default(),
        viewport: f.viewport,
        data: f.data,
        is_template: f.is_template,
        tags: f.tags,
        created_at: f.created_at.map(|t| t.to_rfc3339()).unwrap_or_default(),
        updated_at: f.updated_at.map(|t| t.to_rfc3339()),
    }
}

fn map_flow_to_summary(f: HedgeFundFlow) -> FlowSummaryResponse {
    FlowSummaryResponse {
        id: f.id,
        name: f.name,
        description: f.description,
        is_template: f.is_template,
        tags: f.tags,
        created_at: f.created_at.map(|t| t.to_rfc3339()).unwrap_or_default(),
        updated_at: f.updated_at.map(|t| t.to_rfc3339()),
    }
}

async fn create_flow(
    State(db): State<SqlitePool>,
    Json(req): Json<FlowCreateRequest>,
) -> Result<Json<FlowResponse>, (StatusCode, Json<ErrorResponse>)> {
    let repo = FlowRepository::new(&db);
    let nodes_val = serde_json::to_value(&req.nodes).unwrap_or(serde_json::Value::Null);
    let edges_val = serde_json::to_value(&req.edges).unwrap_or(serde_json::Value::Null);
    let tags_val = req
        .tags
        .map(|t| serde_json::to_value(t).unwrap_or(serde_json::Value::Null));

    match repo
        .create_flow(FlowCreateInput {
            name: &req.name,
            nodes: &nodes_val,
            edges: &edges_val,
            description: req.description.as_deref(),
            viewport: req.viewport.as_ref(),
            data: req.data.as_ref(),
            is_template: req.is_template,
            tags: tags_val.as_ref(),
        })
        .await
    {
        Ok(flow) => Ok(Json(map_flow_to_response(flow))),
        Err(e) => Err((
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ErrorResponse {
                message: "Failed to create flow".to_string(),
                error: Some(e.to_string()),
            }),
        )),
    }
}

#[derive(Debug, Deserialize)]
struct GetFlowsQuery {
    #[serde(default = "default_true")]
    include_templates: bool,
}

fn default_true() -> bool {
    true
}

async fn get_flows(
    State(db): State<SqlitePool>,
    Query(query): Query<GetFlowsQuery>,
) -> Result<Json<Vec<FlowSummaryResponse>>, (StatusCode, Json<ErrorResponse>)> {
    let repo = FlowRepository::new(&db);
    match repo.get_all_flows(query.include_templates).await {
        Ok(flows) => Ok(Json(flows.into_iter().map(map_flow_to_summary).collect())),
        Err(e) => Err((
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ErrorResponse {
                message: "Failed to retrieve flows".to_string(),
                error: Some(e.to_string()),
            }),
        )),
    }
}

async fn get_flow(
    State(db): State<SqlitePool>,
    Path(flow_id): Path<i32>,
) -> Result<Json<FlowResponse>, (StatusCode, Json<ErrorResponse>)> {
    let repo = FlowRepository::new(&db);
    match repo.get_flow_by_id(flow_id).await {
        Ok(Some(flow)) => Ok(Json(map_flow_to_response(flow))),
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
                message: "Failed to retrieve flow".to_string(),
                error: Some(e.to_string()),
            }),
        )),
    }
}

async fn update_flow(
    State(db): State<SqlitePool>,
    Path(flow_id): Path<i32>,
    Json(req): Json<FlowUpdateRequest>,
) -> Result<Json<FlowResponse>, (StatusCode, Json<ErrorResponse>)> {
    let repo = FlowRepository::new(&db);
    let nodes_val = req
        .nodes
        .map(|n| serde_json::to_value(n).unwrap_or(serde_json::Value::Null));
    let edges_val = req
        .edges
        .map(|e| serde_json::to_value(e).unwrap_or(serde_json::Value::Null));
    let tags_val = req
        .tags
        .map(|t| serde_json::to_value(t).unwrap_or(serde_json::Value::Null));

    match repo
        .update_flow(FlowUpdateInput {
            flow_id,
            name: req.name.as_deref(),
            description: req.description.as_deref(),
            nodes: nodes_val.as_ref(),
            edges: edges_val.as_ref(),
            viewport: req.viewport.as_ref(),
            data: req.data.as_ref(),
            is_template: req.is_template,
            tags: tags_val.as_ref(),
        })
        .await
    {
        Ok(Some(flow)) => Ok(Json(map_flow_to_response(flow))),
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
                message: "Failed to update flow".to_string(),
                error: Some(e.to_string()),
            }),
        )),
    }
}

async fn delete_flow(
    State(db): State<SqlitePool>,
    Path(flow_id): Path<i32>,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<ErrorResponse>)> {
    let repo = FlowRepository::new(&db);
    match repo.delete_flow(flow_id).await {
        Ok(true) => Ok(Json(
            serde_json::json!({ "message": "Flow deleted successfully" }),
        )),
        Ok(false) => Err((
            StatusCode::NOT_FOUND,
            Json(ErrorResponse {
                message: format!("Flow not found with ID: {}", flow_id),
                error: None,
            }),
        )),
        Err(e) => Err((
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ErrorResponse {
                message: "Failed to delete flow".to_string(),
                error: Some(e.to_string()),
            }),
        )),
    }
}

#[derive(Debug, Deserialize)]
struct DuplicateFlowQuery {
    new_name: Option<String>,
}

async fn duplicate_flow(
    State(db): State<SqlitePool>,
    Path(flow_id): Path<i32>,
    Query(query): Query<DuplicateFlowQuery>,
) -> Result<Json<FlowResponse>, (StatusCode, Json<ErrorResponse>)> {
    let repo = FlowRepository::new(&db);
    match repo
        .duplicate_flow(flow_id, query.new_name.as_deref())
        .await
    {
        Ok(Some(flow)) => Ok(Json(map_flow_to_response(flow))),
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
                message: "Failed to duplicate flow".to_string(),
                error: Some(e.to_string()),
            }),
        )),
    }
}

async fn search_flows(
    State(db): State<SqlitePool>,
    Path(name): Path<String>,
) -> Result<Json<Vec<FlowSummaryResponse>>, (StatusCode, Json<ErrorResponse>)> {
    let repo = FlowRepository::new(&db);
    match repo.get_flows_by_name(&name).await {
        Ok(flows) => Ok(Json(flows.into_iter().map(map_flow_to_summary).collect())),
        Err(e) => Err((
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ErrorResponse {
                message: "Failed to search flows".to_string(),
                error: Some(e.to_string()),
            }),
        )),
    }
}
