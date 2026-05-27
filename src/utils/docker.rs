// Source: src/utils/docker.py
//! Sibling to src/utils/docker.py
//! Verifies and manages local Docker integrations and background container status.

use serde_json::Value;
use std::time::Duration;

pub async fn is_ollama_available(ollama_url: &str) -> bool {
    let client = reqwest::Client::new();
    match client
        .get(format!("{}/api/version", ollama_url))
        .timeout(Duration::from_secs(5))
        .send()
        .await
    {
        Ok(res) => res.status().is_success(),
        Err(_) => false,
    }
}

pub async fn get_available_models(ollama_url: &str) -> Vec<String> {
    let client = reqwest::Client::new();
    let mut names = Vec::new();
    if let Ok(res) = client
        .get(format!("{}/api/tags", ollama_url))
        .timeout(Duration::from_secs(5))
        .send()
        .await
    {
        if let Ok(val) = res.json::<Value>().await {
            if let Some(models) = val.get("models").and_then(|m| m.as_array()) {
                for m in models {
                    if let Some(name) = m.get("name").and_then(|n| n.as_str()) {
                        names.push(name.to_string());
                    }
                }
            }
        }
    }
    names
}

pub async fn download_model(model_name: &str, ollama_url: &str) -> bool {
    println!(
        "\x1b[33mDownloading model {} to Docker Ollama container...\x1b[0m",
        model_name
    );
    let client = reqwest::Client::new();
    let body = serde_json::json!({ "name": model_name });

    match client
        .post(format!("{}/api/pull", ollama_url))
        .json(&body)
        .send()
        .await
    {
        Ok(res) => {
            if !res.status().is_success() {
                return false;
            }

            // Monitor download progress
            for i in 1..=180 {
                // up to 30 minutes (10s interval)
                tokio::time::sleep(Duration::from_secs(10)).await;
                let available = get_available_models(ollama_url).await;
                if available.contains(&model_name.to_string()) {
                    println!(
                        "\x1b[32mModel {} downloaded successfully.\x1b[0m",
                        model_name
                    );
                    return true;
                }
                if i % 6 == 0 {
                    println!(
                        "\x1b[36mDownload in progress... ({} minutes elapsed)\x1b[0m",
                        i / 6
                    );
                }
            }
            false
        }
        Err(_) => false,
    }
}

pub async fn ensure_ollama_and_model(model_name: &str, ollama_url: &str) -> bool {
    println!("\x1b[36mUsing Ollama endpoint at {}\x1b[0m", ollama_url);
    if !is_ollama_available(ollama_url).await {
        return false;
    }

    let available = get_available_models(ollama_url).await;
    if available.contains(&model_name.to_string()) {
        println!(
            "\x1b[32mModel {} is available in the Docker Ollama container.\x1b[0m",
            model_name
        );
        return true;
    }

    println!(
        "\x1b[33mModel {} is not available in the Docker Ollama container.\x1b[0m",
        model_name
    );
    download_model(model_name, ollama_url).await
}

pub async fn delete_model(model_name: &str, ollama_url: &str) -> bool {
    println!(
        "\x1b[33mDeleting model {} from Docker container...\x1b[0m",
        model_name
    );
    let client = reqwest::Client::new();
    let body = serde_json::json!({ "name": model_name });

    match client
        .delete(format!("{}/api/delete", ollama_url))
        .json(&body)
        .send()
        .await
    {
        Ok(res) => res.status().is_success(),
        Err(_) => false,
    }
}
