// Source: src/utils/ollama.py
//! Sibling to src/utils/ollama.py
//! Verifies local Ollama server status and pulls local LLM models when running in offline mode.

use crate::utils::docker;
use std::process::{Command, Stdio};
use std::time::Duration;

pub const DEFAULT_OLLAMA_SERVER_URL: &str = "http://localhost:11434";

pub fn get_ollama_base_url() -> String {
    std::env::var("OLLAMA_BASE_URL")
        .unwrap_or_else(|_| DEFAULT_OLLAMA_SERVER_URL.to_string())
        .trim_end_matches('/')
        .to_string()
}

pub fn is_ollama_installed() -> bool {
    let cmd = if cfg!(target_os = "windows") {
        "where"
    } else {
        "which"
    };
    match Command::new(cmd)
        .arg("ollama")
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
    {
        Ok(status) => status.success(),
        Err(_) => false,
    }
}

pub async fn is_ollama_server_running() -> bool {
    let url = get_ollama_base_url();
    let client = reqwest::Client::new();
    match client
        .get(format!("{}/api/tags", url))
        .timeout(Duration::from_secs(2))
        .send()
        .await
    {
        Ok(res) => res.status().is_success(),
        Err(_) => false,
    }
}

pub async fn get_locally_available_models() -> Vec<String> {
    let url = get_ollama_base_url();
    docker::get_available_models(&url).await
}

pub async fn start_ollama_server() -> bool {
    if is_ollama_server_running().await {
        return true;
    }

    println!("\x1b[33mStarting local Ollama server...\x1b[0m");
    let spawned = if cfg!(target_os = "windows") {
        Command::new("cmd")
            .args(["/C", "ollama serve"])
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
    } else {
        Command::new("ollama")
            .arg("serve")
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
    };

    if spawned.is_err() {
        return false;
    }

    for _ in 0..10 {
        tokio::time::sleep(Duration::from_secs(1)).await;
        if is_ollama_server_running().await {
            println!("\x1b[32mOllama server started successfully.\x1b[0m");
            return true;
        }
    }
    false
}

pub async fn download_model(model_name: &str) -> bool {
    let url = get_ollama_base_url();
    docker::download_model(model_name, &url).await
}

pub async fn ensure_ollama_and_model(model_name: &str) -> bool {
    let url = get_ollama_base_url();
    let env_override = std::env::var("OLLAMA_BASE_URL").is_ok();

    if env_override || url.contains("ollama:") || url.contains("host.docker.internal:") {
        return docker::ensure_ollama_and_model(model_name, &url).await;
    }

    if !is_ollama_installed() {
        println!("\x1b[31mOllama is not installed on your system. Please visit https://ollama.com to install it.\x1b[0m");
        return false;
    }

    if !is_ollama_server_running().await && !start_ollama_server().await {
        return false;
    }

    let available = get_locally_available_models().await;
    if available.contains(&model_name.to_string()) {
        return true;
    }

    println!(
        "\x1b[33mModel {} is not available locally.\x1b[0m",
        model_name
    );
    download_model(model_name).await
}

pub async fn delete_model(model_name: &str) -> bool {
    let url = get_ollama_base_url();
    docker::delete_model(model_name, &url).await
}
