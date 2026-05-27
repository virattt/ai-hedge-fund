// Source: src/utils/llm.py
//! Unified LLM client dispatcher querying live models (OpenAI, Anthropic, Gemini, DeepSeek, Groq, Ollama) over reqwest APIs,
//! with markdown/brace JSON extraction, error retry loops, and deterministic test fallbacks.

use anyhow::{Result, Context};
use serde::de::DeserializeOwned;
use std::env;
use crate::graph::state::AgentState;
use crate::llm::models::{ModelProvider, get_model_info};

/// Resolves model configuration for a specific agent from state metadata.
pub fn get_agent_model_config(state: Option<&AgentState>, _agent_name: Option<&str>) -> (String, ModelProvider) {
    let (mut model_name, mut model_provider) = if let Some(s) = state {
        let name = s.metadata.get("model_name")
            .and_then(|v| v.as_str())
            .unwrap_or("gpt-5.5")
            .to_string();
        
        let model_provider_str = s.metadata.get("model_provider")
            .and_then(|v| v.as_str())
            .unwrap_or("OPENAI");

        let provider = match model_provider_str.to_uppercase().as_str() {
            "ANTHROPIC" => ModelProvider::Anthropic,
            "DEEPSEEK" => ModelProvider::DeepSeek,
            "GOOGLE" => ModelProvider::Google,
            "GROQ" => ModelProvider::Groq,
            "KIMI" => ModelProvider::Kimi,
            "OLLAMA" => ModelProvider::Ollama,
            "OPENROUTER" => ModelProvider::OpenRouter,
            "XAI" => ModelProvider::xAI,
            "AZURE OPENAI" | "AZURE_OPENAI" => ModelProvider::AzureOpenAI,
            _ => ModelProvider::OpenAI,
        };

        (name, provider)
    } else {
        ("gpt-5.5".to_string(), ModelProvider::OpenAI)
    };

    // If provider is OpenAI but we don't have a valid OpenAI key, and we have an OpenRouter key,
    // automatically coerce provider to OpenRouter for OpenAI-compatible execution!
    if model_provider == ModelProvider::OpenAI {
        let has_openai = env::var("OPENAI_API_KEY")
            .map(|k| !k.starts_with("your-") && !k.is_empty())
            .unwrap_or(false);
        let has_openrouter = env::var("OPENROUTER_API_KEY")
            .map(|k| !k.starts_with("your-") && !k.is_empty())
            .unwrap_or(false);

        if !has_openai && has_openrouter {
            model_provider = ModelProvider::OpenRouter;
            if model_name == "gpt-4" || model_name == "gpt-5.5" || model_name == "gpt-4o" {
                model_name = "openai/gpt-4o".to_string();
            }
        }
    }

    (model_name, model_provider)
}

/// Helper function to retrieve the API key from environment for a model provider.
pub fn get_api_key_for_provider(provider: &ModelProvider) -> Option<String> {
    let raw_key = match provider {
        ModelProvider::OpenAI => env::var("OPENAI_API_KEY").ok(),
        ModelProvider::Anthropic => env::var("ANTHROPIC_API_KEY").ok(),
        ModelProvider::DeepSeek => env::var("DEEPSEEK_API_KEY").ok(),
        ModelProvider::Google => env::var("GOOGLE_API_KEY").ok(),
        ModelProvider::Groq => env::var("GROQ_API_KEY").ok(),
        ModelProvider::Kimi => env::var("MOONSHOT_API_KEY").ok().or_else(|| env::var("KIMI_API_KEY").ok()),
        ModelProvider::OpenRouter => env::var("OPENROUTER_API_KEY").ok(),
        ModelProvider::xAI => env::var("XAI_API_KEY").ok(),
        ModelProvider::AzureOpenAI => env::var("AZURE_OPENAI_API_KEY").ok(),
        _ => None,
    };

    // Filter out placeholders
    if let Some(ref k) = raw_key {
        if k.starts_with("your-") || k.is_empty() {
            return None;
        }
    }
    raw_key
}

/// Generates a deterministic mock response for testing offline or when API credentials are absent.
pub fn get_mock_response_for_prompt(user_prompt: &str) -> String {
    let mut ticker = "AAPL";
    if let Some(start) = user_prompt.find("Ticker:") {
        let after = &user_prompt[start + 7..];
        ticker = after.split_whitespace().next().unwrap_or("AAPL").trim_matches(|c| c == ',' || c == ':');
    }

    // Hash the ticker name to produce varying signals deterministically
    let char_sum: usize = ticker.chars().map(|c| c as usize).sum();
    let (signal, confidence, reasoning) = match char_sum % 3 {
        0 => ("bullish", 75, format!("Mocked analysis for {}: Solid balance sheet and margin of safety.", ticker)),
        1 => ("bearish", 80, format!("Mocked analysis for {}: High leverage and rich valuation.", ticker)),
        _ => ("neutral", 60, format!("Mocked analysis for {}: Strong moat but currently fairly valued.", ticker)),
    };

    if user_prompt.contains("decisions") || user_prompt.contains("Portfolio") || user_prompt.contains("quantity") {
        // Return a mock portfolio decision map
        format!(
            r#"{{"{}": {{"action": "{}", "quantity": 100, "confidence": 0.8, "reasoning": "Mocked allocation decision"}}}}"#,
            ticker,
            if signal == "bullish" { "buy" } else if signal == "bearish" { "short" } else { "hold" }
        )
    } else {
        // General analyst recommendation signal
        format!(
            r#"{{"signal": "{}", "confidence": {}, "reasoning": "{}"}}"#,
            signal, confidence, reasoning
        )
    }
}

/// Main async LLM call executor with retry loops and structured JSON extraction.
pub async fn call_llm<T>(
    system_prompt: &str,
    user_prompt: &str,
    agent_name: Option<&str>,
    state: Option<&AgentState>,
    max_retries: usize,
) -> Result<T>
where
    T: DeserializeOwned + Default + std::fmt::Debug,
{
    let (model_name, model_provider) = get_agent_model_config(state, agent_name);
    let api_key = get_api_key_for_provider(&model_provider);

    // Fall back to local mocked results if API key is absent and we are not querying Ollama
    if api_key.is_none() && model_provider != ModelProvider::Ollama {
        let mock_text = get_mock_response_for_prompt(user_prompt);
        if let Some(parsed_json) = extract_json_from_response(&mock_text) {
            if let Ok(res) = serde_json::from_value::<T>(parsed_json) {
                return Ok(res);
            }
        }
        return Ok(T::default());
    }

    let client = reqwest::Client::new();
    let mut response_body = String::new();

    for attempt in 0..max_retries {
        let res = match &model_provider {
            ModelProvider::Anthropic => {
                let url = "https://api.anthropic.com/v1/messages";
                let payload = serde_json::json!({
                    "model": model_name,
                    "system": system_prompt,
                    "messages": [
                        { "role": "user", "content": user_prompt }
                    ],
                    "max_tokens": 1024
                });
                client.post(url)
                    .header("x-api-key", api_key.clone().unwrap_or_default())
                    .header("anthropic-version", "2023-06-01")
                    .header("content-type", "application/json")
                    .json(&payload)
                    .send()
                    .await
            }
            ModelProvider::Google => {
                let url = format!(
                    "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent?key={}",
                    model_name,
                    api_key.clone().unwrap_or_default()
                );
                let payload = serde_json::json!({
                    "contents": [
                        {
                            "role": "user",
                            "parts": [
                                { "text": format!("System Instruction:\n{}\n\nUser Input:\n{}", system_prompt, user_prompt) }
                            ]
                        }
                    ],
                    "generationConfig": {
                        "responseMimeType": "application/json"
                    }
                });
                client.post(&url)
                    .json(&payload)
                    .send()
                    .await
            }
            _ => {
                // OpenAI-compatible chat endpoints
                let url = match &model_provider {
                    ModelProvider::DeepSeek => "https://api.deepseek.com/chat/completions",
                    ModelProvider::Groq => "https://api.groq.com/openai/v1/chat/completions",
                    ModelProvider::Kimi => "https://api.moonshot.cn/v1/chat/completions",
                    ModelProvider::OpenRouter => "https://openrouter.ai/api/v1/chat/completions",
                    ModelProvider::xAI => "https://api.x.ai/v1/chat/completions",
                    ModelProvider::Ollama => {
                        let host = env::var("OLLAMA_HOST").unwrap_or_else(|_| "localhost".to_string());
                        &format!("http://{}:11434/v1/chat/completions", host)
                    }
                    _ => "https://api.openai.com/v1/chat/completions",
                };

                let mut builder = client.post(url);
                if let Some(ref key) = api_key {
                    builder = builder.header("Authorization", format!("Bearer {}", key));
                }

                if model_provider == ModelProvider::OpenRouter {
                    builder = builder
                        .header("HTTP-Referer", "https://github.com/virattt/ai-hedge-fund")
                        .header("X-Title", "AI Hedge Fund");
                }

                let payload = serde_json::json!({
                    "model": model_name,
                    "messages": [
                        { "role": "system", "content": system_prompt },
                        { "role": "user", "content": user_prompt }
                    ],
                    "response_format": { "type": "json_object" }
                });

                builder.json(&payload).send().await
            }
        };

        match res {
            Ok(http_res) => {
                let status = http_res.status();
                if status.is_success() {
                    let parsed: serde_json::Value = http_res.json().await.unwrap_or_default();
                    
                    // Extract text content depending on provider output structures
                    let content = match &model_provider {
                        ModelProvider::Anthropic => {
                            parsed.get("content")
                                .and_then(|c| c.as_array())
                                .and_then(|a| a.first())
                                .and_then(|item| item.get("text"))
                                .and_then(|t| t.as_str())
                                .unwrap_or("")
                                .to_string()
                        }
                        ModelProvider::Google => {
                            parsed.get("candidates")
                                .and_then(|c| c.as_array())
                                .and_then(|a| a.first())
                                .and_then(|item| item.get("content"))
                                .and_then(|cnt| cnt.get("parts"))
                                .and_then(|p| p.as_array())
                                .and_then(|p_arr| p_arr.first())
                                .and_then(|part| part.get("text"))
                                .and_then(|t| t.as_str())
                                .unwrap_or("")
                                .to_string()
                        }
                        _ => {
                            parsed.get("choices")
                                .and_then(|c| c.as_array())
                                .and_then(|a| a.first())
                                .and_then(|item| item.get("message"))
                                .and_then(|msg| msg.get("content"))
                                .and_then(|cnt| cnt.as_str())
                                .unwrap_or("")
                                .to_string()
                        }
                    };

                    if let Some(json_val) = extract_json_from_response(&content) {
                        if let Ok(deserialized) = serde_json::from_value::<T>(json_val) {
                            return Ok(deserialized);
                        }
                    }
                    response_body = content;
                } else {
                    let err_body = http_res.text().await.unwrap_or_default();
                    println!("LLM Error response: {} - {}", status, err_body);
                }
            }
            Err(e) => {
                println!("LLM Connection attempt {} failed: {:?}", attempt + 1, e);
            }
        }

        // Retry sleep delay
        tokio::time::sleep(std::time::Duration::from_millis(500 * (attempt as u64 + 1))).await;
    }

    // Ultimate fallback if parsing fails completely
    if let Some(json_val) = extract_json_from_response(&response_body) {
        if let Ok(deserialized) = serde_json::from_value::<T>(json_val) {
            return Ok(deserialized);
        }
    }

    println!("Warning: call_llm failed to get a structured response after {} attempts.", max_retries);
    Ok(T::default())
}

/// Helper JSON extractor looking for markdown JSON fences and top-level curly braces.
pub fn extract_json_from_response(content: &str) -> Option<serde_json::Value> {
    // 1. Try markdown code block with ```json
    if let Some(start) = content.find("```json") {
        let json_text = &content[start + 7..];
        if let Some(end) = json_text.find("```") {
            let json_text = json_text[..end].trim();
            if let Ok(val) = serde_json::from_str(json_text) {
                return Some(val);
            }
        }
    }

    // 2. Try markdown code block without json specifier
    if let Some(start) = content.find("```") {
        let json_text = &content[start + 3..];
        if let Some(end) = json_text.find("```") {
            let json_text = json_text[..end].trim();
            if let Ok(val) = serde_json::from_str(json_text) {
                return Some(val);
            }
        }
    }

    // 3. Try parsing entire text
    if let Ok(val) = serde_json::from_str(content.trim()) {
        return Some(val);
    }

    // 4. Find first matching balanced curly braces
    if let Some(start) = content.find('{') {
        let mut depth = 0;
        for (i, c) in content[start..].char_indices() {
            if c == '{' {
                depth += 1;
            } else if c == '}' {
                depth -= 1;
                if depth == 0 {
                    let candidate = &content[start..=start + i];
                    if let Ok(val) = serde_json::from_str(candidate) {
                        return Some(val);
                    }
                    break;
                }
            }
        }
    }

    None
}
