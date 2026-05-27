use crate::models::events::{CompleteEvent, ErrorEvent, ProgressUpdateEvent, StartEvent};
use crate::models::schemas::{BacktestDayResult, BacktestRequest, ErrorResponse, HedgeFundRequest};
use crate::services::api_key_service::ApiKeyService;
use crate::services::backtest_service::BacktestService;
use crate::services::graph::run_graph_async;
use crate::services::portfolio::create_portfolio;
use ai_hedge_fund::utils::analysts::get_analysts_list;
use ai_hedge_fund::utils::api_key::is_valid_api_key;
use ai_hedge_fund::utils::llm::{log_resolved_llm_config, resolve_llm_config};
use axum::{
    extract::State,
    http::StatusCode,
    response::sse::{Event, Sse},
    routing::{get, post},
    Json, Router,
};
use sqlx::SqlitePool;
use std::convert::Infallible;
use tokio_stream::Stream;

pub fn router() -> Router<SqlitePool> {
    Router::new()
        .route("/run", post(run_hedge_fund_handler))
        .route("/backtest", post(backtest_handler))
        .route("/agents", get(get_agents_handler))
}

async fn run_hedge_fund_handler(
    State(db): State<SqlitePool>,
    Json(mut req): Json<HedgeFundRequest>,
) -> Result<Sse<impl Stream<Item = Result<Event, Infallible>>>, (StatusCode, Json<ErrorResponse>)> {
    // 1. Hydrate API keys from database if not provided
    if req.base.api_keys.is_none() || req.base.api_keys.as_ref().unwrap().is_empty() {
        let api_key_service = ApiKeyService::new(&db);
        if let Ok(keys_map) = api_key_service.get_api_keys_dict().await {
            req.base.api_keys = Some(keys_map);
        }
    }

    // Set standard API key environment variables if provided
    if let Some(ref keys) = req.base.api_keys {
        for (provider, key_val) in keys {
            if !is_valid_api_key(key_val) {
                continue;
            }
            if provider.eq_ignore_ascii_case("financial_datasets") {
                std::env::set_var("FINANCIAL_DATASETS_API_KEY", key_val);
            } else if provider.eq_ignore_ascii_case("openai") {
                std::env::set_var("OPENAI_API_KEY", key_val);
            } else if provider.eq_ignore_ascii_case("openrouter") {
                std::env::set_var("OPENROUTER_API_KEY", key_val);
            } else if provider.eq_ignore_ascii_case("groq") {
                std::env::set_var("GROQ_API_KEY", key_val);
            } else if provider.eq_ignore_ascii_case("anthropic") {
                std::env::set_var("ANTHROPIC_API_KEY", key_val);
            }
        }
    }

    let (tx, rx) = tokio::sync::mpsc::channel::<Result<Event, Infallible>>(20);

    let tickers = req.base.tickers.clone();
    let _start_date = req
        .start_date
        .clone()
        .unwrap_or_else(|| "2024-01-01".to_string());
    let end_date = req
        .end_date
        .clone()
        .unwrap_or_else(|| "2024-01-08".to_string());
    let llm = resolve_llm_config(
        req.base.model_name.as_deref(),
        false,
        req.base.model_provider.clone(),
    );
    log_resolved_llm_config(&llm);
    let model_name = llm.model_name;
    let model_provider = llm.model_provider;

    let portfolio_val = serde_json::to_value(create_portfolio(
        req.initial_cash,
        req.base.margin_requirement,
        &tickers,
        req.base.portfolio_positions.as_deref(),
    ))
    .unwrap_or(serde_json::Value::Null);

    let graph_nodes = req.base.graph_nodes.clone();
    let _graph_edges = req.base.graph_edges.clone();

    tokio::spawn(async move {
        // Send start event
        if let Ok(ev) = StartEvent::new().to_sse() {
            tx.send(Ok(ev)).await.ok();
        }

        // Send simulated progress events to match UI loader sequence
        let progress_events = vec![
            ("system", "Preparing hedge fund run..."),
            (
                "fundamentals",
                "Analyzing fundamental data and financial statements...",
            ),
            (
                "technicals",
                "Scanning technical indicators, moving averages, and MACD...",
            ),
            (
                "sentiment",
                "Aggregating news sentiment and social media signals...",
            ),
            (
                "portfolio_manager",
                "Rebalancing portfolio and checking risk parameters...",
            ),
        ];

        for (agent, status) in progress_events {
            tokio::time::sleep(tokio::time::Duration::from_millis(100)).await;
            if let Ok(ev) =
                ProgressUpdateEvent::new(agent.to_string(), None, status.to_string(), None).to_sse()
            {
                tx.send(Ok(ev)).await.ok();
            }
        }

        // Execute concurrent workflow execution graph run
        match run_graph_async(
            &graph_nodes,
            portfolio_val,
            &tickers,
            &end_date,
            &model_name,
            model_provider.value(),
        )
        .await
        {
            Ok(result) => {
                let complete_data = serde_json::json!({
                    "decisions": result.decisions.unwrap_or(serde_json::json!({})),
                    "analyst_signals": result.analyst_signals,
                });
                if let Ok(ev) = CompleteEvent::new(complete_data).to_sse() {
                    tx.send(Ok(ev)).await.ok();
                }
            }
            Err(e) => {
                if let Ok(ev) =
                    ErrorEvent::new(format!("Hedge fund execution failed: {}", e)).to_sse()
                {
                    tx.send(Ok(ev)).await.ok();
                }
            }
        }
    });

    let stream = tokio_stream::wrappers::ReceiverStream::new(rx);
    Ok(Sse::new(stream))
}

async fn backtest_handler(
    State(db): State<SqlitePool>,
    Json(mut req): Json<BacktestRequest>,
) -> Result<Sse<impl Stream<Item = Result<Event, Infallible>>>, (StatusCode, Json<ErrorResponse>)> {
    // 1. Hydrate API keys
    if req.base.api_keys.is_none() || req.base.api_keys.as_ref().unwrap().is_empty() {
        let api_key_service = ApiKeyService::new(&db);
        if let Ok(keys_map) = api_key_service.get_api_keys_dict().await {
            req.base.api_keys = Some(keys_map);
        }
    }

    if let Some(ref keys) = req.base.api_keys {
        for (provider, key_val) in keys {
            if !is_valid_api_key(key_val) {
                continue;
            }
            if provider.eq_ignore_ascii_case("financial_datasets") {
                std::env::set_var("FINANCIAL_DATASETS_API_KEY", key_val);
            } else if provider.eq_ignore_ascii_case("openai") {
                std::env::set_var("OPENAI_API_KEY", key_val);
            } else if provider.eq_ignore_ascii_case("openrouter") {
                std::env::set_var("OPENROUTER_API_KEY", key_val);
            } else if provider.eq_ignore_ascii_case("groq") {
                std::env::set_var("GROQ_API_KEY", key_val);
            } else if provider.eq_ignore_ascii_case("anthropic") {
                std::env::set_var("ANTHROPIC_API_KEY", key_val);
            }
        }
    }

    let (tx_sse, rx_sse) = tokio::sync::mpsc::channel::<Result<Event, Infallible>>(100);
    let (tx_bt, mut rx_bt) = tokio::sync::mpsc::channel::<anyhow::Result<serde_json::Value>>(100);

    tokio::spawn(async move {
        // Send start event
        if let Ok(ev) = StartEvent::new().to_sse() {
            tx_sse.send(Ok(ev)).await.ok();
        }

        // Run backtest streaming in a background task
        let runner_handle = tokio::spawn(async move {
            if let Err(e) = BacktestService::run_backtest_streaming(req, tx_bt).await {
                eprintln!("Backtest execution failed: {:?}", e);
            }
        });

        // Loop and stream backtest updates
        while let Some(msg) = rx_bt.recv().await {
            match msg {
                Ok(val) => {
                    let msg_type = val.get("type").and_then(|t| t.as_str()).unwrap_or("");
                    if msg_type == "backtest_result" {
                        if let Some(day_data) = val.get("data") {
                            let day_result: Result<BacktestDayResult, _> =
                                serde_json::from_value(day_data.clone());
                            if let Ok(res) = day_result {
                                let analysis_str = serde_json::to_string(&res).unwrap_or_default();
                                let ev = ProgressUpdateEvent::new(
                                    "backtest".to_string(),
                                    None,
                                    format!(
                                        "Completed {} - Portfolio: ${:.2}",
                                        res.date, res.portfolio_value
                                    ),
                                    Some(analysis_str),
                                );
                                if let Ok(ev_sse) = ev.to_sse() {
                                    tx_sse.send(Ok(ev_sse)).await.ok();
                                }
                            }
                        }
                    } else if msg_type == "complete" {
                        let final_data = serde_json::json!({
                            "performance_metrics": val.get("performance_metrics").cloned().unwrap_or(serde_json::Value::Null),
                            "final_portfolio": val.get("final_portfolio").cloned().unwrap_or(serde_json::Value::Null),
                            "total_days": val.get("total_days").cloned().unwrap_or(serde_json::Value::Null),
                        });
                        if let Ok(ev_sse) = CompleteEvent::new(final_data).to_sse() {
                            tx_sse.send(Ok(ev_sse)).await.ok();
                        }
                    }
                }
                Err(e) => {
                    if let Ok(ev_sse) = ErrorEvent::new(format!("Backtest failed: {}", e)).to_sse()
                    {
                        tx_sse.send(Ok(ev_sse)).await.ok();
                    }
                }
            }
        }

        // Ensure we join the runner
        runner_handle.await.ok();
    });

    let stream = tokio_stream::wrappers::ReceiverStream::new(rx_sse);
    Ok(Sse::new(stream))
}

async fn get_agents_handler() -> Result<Json<serde_json::Value>, (StatusCode, Json<ErrorResponse>)>
{
    let analysts = get_analysts_list();
    Ok(Json(serde_json::json!({ "agents": analysts })))
}
