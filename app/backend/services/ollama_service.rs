use ai_hedge_fund::utils::ollama;
use anyhow::Result;
use serde::{Deserialize, Serialize};

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct OllamaStatus {
    pub installed: bool,
    pub running: bool,
    pub server_running: bool,
    pub available_models: Vec<String>,
    pub server_url: String,
    pub error: Option<String>,
}

pub struct OllamaService;

impl OllamaService {
    pub async fn check_ollama_status() -> OllamaStatus {
        let installed = ollama::is_ollama_installed();
        let running = ollama::is_ollama_server_running().await;
        let available_models = if running {
            ollama::get_locally_available_models().await
        } else {
            Vec::new()
        };
        let server_url = ollama::get_ollama_base_url();

        OllamaStatus {
            installed,
            running,
            server_running: running,
            available_models,
            server_url,
            error: None,
        }
    }

    pub async fn start_server() -> Result<(bool, String)> {
        let success = ollama::start_ollama_server().await;
        let message = if success {
            "Ollama server started successfully".to_string()
        } else {
            "Failed to start Ollama server".to_string()
        };
        Ok((success, message))
    }

    pub async fn stop_server() -> Result<(bool, String)> {
        let system = std::env::consts::OS;
        let success = if system == "windows" {
            std::process::Command::new("taskkill")
                .args(["/F", "/IM", "ollama.exe"])
                .status()
                .map(|s| s.success())
                .unwrap_or(false)
        } else {
            std::process::Command::new("pkill")
                .args(["-f", "ollama serve"])
                .status()
                .map(|s| s.success())
                .unwrap_or(false)
        };

        let message = if success {
            "Ollama server stopped successfully".to_string()
        } else {
            "Failed to stop Ollama server".to_string()
        };
        Ok((success, message))
    }

    pub async fn download_model(model_name: &str) -> Result<(bool, String)> {
        let success = ollama::download_model(model_name).await;
        let message = if success {
            format!("Model {} downloaded successfully", model_name)
        } else {
            format!("Failed to download model {}", model_name)
        };
        Ok((success, message))
    }

    pub async fn delete_model(model_name: &str) -> Result<(bool, String)> {
        let success = ollama::delete_model(model_name).await;
        let message = if success {
            format!("Model {} deleted successfully", model_name)
        } else {
            format!("Failed to delete model {}", model_name)
        };
        Ok((success, message))
    }
}
