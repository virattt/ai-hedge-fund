pub mod database;
pub mod models;
pub mod repositories;
pub mod services;
pub mod routes;

use anyhow::Result;
use axum::Router;
use tower_http::cors::{CorsLayer, Any};
use axum::http::{HeaderValue, Method};
use std::net::SocketAddr;

use crate::database::connection::get_db_pool;
use crate::routes::api_router;
use crate::services::ollama_service::OllamaService;

#[tokio::main]
async fn main() -> Result<()> {
    // Load environment variables from .env file
    dotenvy::dotenv().ok();

    println!("Starting AI Hedge Fund Backend Server (Rust Port)...");

    // 1. Initialize SQLite Database Pool & Tables
    println!("Connecting to SQLite database and applying schema tables...");
    let pool = get_db_pool().await?;
    println!("✓ Database initialized successfully.");

    // 2. Configure CORS middleware (supporting the React dashboard at localhost:5173)
    let cors = CorsLayer::new()
        .allow_origin([
            "http://localhost:5173".parse::<HeaderValue>().unwrap(),
            "http://127.0.0.1:5173".parse::<HeaderValue>().unwrap(),
        ])
        .allow_methods([Method::GET, Method::POST, Method::PUT, Method::DELETE, Method::PATCH])
        .allow_headers(Any)
        .allow_credentials(true);

    // 3. Assemble and Merge Router with State
    let app = Router::new()
        .merge(api_router())
        .layer(cors)
        .with_state(pool);

    // 4. Verify Ollama Integration
    tokio::spawn(async {
        println!("Checking Ollama local server availability...");
        match OllamaService::check_ollama_status().await {
            status if status.installed => {
                if status.running {
                    println!("✓ Ollama is installed and running at {}", status.server_url);
                    if !status.available_models.is_empty() {
                        println!("✓ Available Ollama models: {}", status.available_models.join(", "));
                    } else {
                        println!("ℹ No local Ollama models found. Install one (e.g. llama3) to run offline backtests.");
                    }
                } else {
                    println!("ℹ Ollama is installed but NOT currently running.");
                }
            }
            _ => {
                println!("ℹ Ollama is not installed. You can still use OpenAI, Anthropic, or Groq with valid API keys.");
            }
        }
    });

    // 5. Start Axum Listener
    let addr = SocketAddr::from(([0, 0, 0, 0], 8000));
    println!("✓ Backend server listening on http://{}", addr);

    let listener = tokio::net::TcpListener::bind(addr).await?;
    axum::serve(listener, app).await?;

    Ok(())
}
