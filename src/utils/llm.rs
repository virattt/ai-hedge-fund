// Source: src/utils/llm.py
//! Unified LLM client dispatcher querying live models (OpenAI, Anthropic, Gemini, DeepSeek, Groq, Ollama) over reqwest APIs,
//! with markdown/brace JSON extraction, error retry loops, and deterministic test fallbacks.

use anyhow::Result;
use serde::de::DeserializeOwned;
use std::env;
use crate::graph::state::AgentState;
use crate::llm::models::ModelProvider;
use crate::utils::api_key::env_api_key;

/// Resolved LLM model and provider after environment-based auto-detection.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ResolvedLlmConfig {
    pub model_name: String,
    pub model_provider: ModelProvider,
}

const DEFAULT_MODEL: &str = "gpt-4.1";

/// Resolve the LLM provider and model from explicit inputs and environment keys.
///
/// When the requested provider has no valid API key, falls back to the first
/// provider with a configured key (e.g. OpenRouter when OpenAI is absent).
pub fn resolve_llm_config(
    model_name: Option<&str>,
    ollama: bool,
    explicit_provider: Option<ModelProvider>,
) -> ResolvedLlmConfig {
    if ollama {
        return ResolvedLlmConfig {
            model_name: model_name.unwrap_or("llama3").to_string(),
            model_provider: ModelProvider::Ollama,
        };
    }

    let requested_model = model_name.unwrap_or(DEFAULT_MODEL);

    if let Some(ref provider) = explicit_provider {
        if provider_has_valid_key(provider) {
            return ResolvedLlmConfig {
                model_name: normalize_model_for_provider(requested_model, provider),
                model_provider: provider.clone(),
            };
        }
    }

    if let Some(detected) = detect_provider_from_env() {
        return ResolvedLlmConfig {
            model_name: normalize_model_for_provider(requested_model, &detected),
            model_provider: detected,
        };
    }

    let fallback_provider = explicit_provider.unwrap_or(ModelProvider::OpenAI);
    ResolvedLlmConfig {
        model_name: normalize_model_for_provider(requested_model, &fallback_provider),
        model_provider: fallback_provider,
    }
}

/// Log the resolved LLM configuration for CLI / server entry points.
pub fn log_resolved_llm_config(config: &ResolvedLlmConfig) {
    if config.model_provider == ModelProvider::Ollama {
        println!(
            "Using Ollama ({}) for LLM inference.",
            config.model_name
        );
        return;
    }

    let key_status = if provider_has_valid_key(&config.model_provider) {
        "configured"
    } else {
        "missing — agents will use mock responses"
    };

    println!(
        "Using {} ({}) as the LLM provider (API key: {}).",
        config.model_provider.value(),
        config.model_name,
        key_status
    );
}

fn detect_provider_from_env() -> Option<ModelProvider> {
    const PROVIDERS: &[(ModelProvider, &str)] = &[
        (ModelProvider::OpenAI, "OPENAI_API_KEY"),
        (ModelProvider::OpenRouter, "OPENROUTER_API_KEY"),
        (ModelProvider::Anthropic, "ANTHROPIC_API_KEY"),
        (ModelProvider::Groq, "GROQ_API_KEY"),
        (ModelProvider::DeepSeek, "DEEPSEEK_API_KEY"),
        (ModelProvider::Google, "GOOGLE_API_KEY"),
        (ModelProvider::Kimi, "MOONSHOT_API_KEY"),
        (ModelProvider::xAI, "XAI_API_KEY"),
        (ModelProvider::GigaChat, "GIGACHAT_API_KEY"),
        (ModelProvider::AzureOpenAI, "AZURE_OPENAI_API_KEY"),
    ];

    for (provider, env_var) in PROVIDERS {
        if env_api_key(env_var).is_some() {
            return Some(provider.clone());
        }
    }

    if env_api_key("KIMI_API_KEY").is_some() {
        return Some(ModelProvider::Kimi);
    }

    None
}

fn provider_has_valid_key(provider: &ModelProvider) -> bool {
    get_api_key_for_provider(provider).is_some()
}

fn normalize_model_for_provider(model_name: &str, provider: &ModelProvider) -> String {
    if *provider != ModelProvider::OpenRouter || model_name.contains('/') {
        return model_name.to_string();
    }

    if model_name.starts_with("gpt-") {
        return format!("openai/{}", model_name);
    }
    if model_name.starts_with("claude-") {
        return format!("anthropic/{}", model_name);
    }
    if model_name.starts_with("gemini-") {
        return format!("google/{}", model_name);
    }
    if model_name.starts_with("deepseek-") {
        return format!("deepseek/{}", model_name);
    }
    if model_name.starts_with("grok-") {
        return format!("x-ai/{}", model_name);
    }

    model_name.to_string()
}

/// Resolves model configuration for a specific agent from state metadata.
pub fn get_agent_model_config(state: Option<&AgentState>, _agent_name: Option<&str>) -> (String, ModelProvider) {
    let (model_name, explicit_provider) = if let Some(s) = state {
        let name = s.metadata
            .get("model_name")
            .and_then(|v| v.as_str())
            .map(str::to_string);
        let provider = s.metadata
            .get("model_provider")
            .and_then(|v| v.as_str())
            .and_then(ModelProvider::from_label);
        (name, provider)
    } else {
        (None, None)
    };

    let resolved = resolve_llm_config(model_name.as_deref(), false, explicit_provider);
    (resolved.model_name, resolved.model_provider)
}

/// Helper function to retrieve the API key from environment for a model provider.
pub fn get_api_key_for_provider(provider: &ModelProvider) -> Option<String> {
    let raw_key = match provider {
        ModelProvider::OpenAI => env_api_key("OPENAI_API_KEY"),
        ModelProvider::Anthropic => env_api_key("ANTHROPIC_API_KEY"),
        ModelProvider::DeepSeek => env_api_key("DEEPSEEK_API_KEY"),
        ModelProvider::Google => env_api_key("GOOGLE_API_KEY"),
        ModelProvider::Groq => env_api_key("GROQ_API_KEY"),
        ModelProvider::Kimi => env_api_key("MOONSHOT_API_KEY").or_else(|| env_api_key("KIMI_API_KEY")),
        ModelProvider::OpenRouter => env_api_key("OPENROUTER_API_KEY"),
        ModelProvider::xAI => env_api_key("XAI_API_KEY"),
        ModelProvider::AzureOpenAI => env_api_key("AZURE_OPENAI_API_KEY"),
        _ => None,
    };

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

#[cfg(test)]
mod tests {
    use super::*;

    fn clear_llm_env() {
        for key in [
            "OPENAI_API_KEY",
            "OPENROUTER_API_KEY",
            "ANTHROPIC_API_KEY",
            "GROQ_API_KEY",
        ] {
            env::remove_var(key);
        }
    }

    #[test]
    fn openrouter_selected_when_openai_missing() {
        clear_llm_env();
        env::set_var("OPENROUTER_API_KEY", "sk-or-test-key");

        let resolved = resolve_llm_config(
            Some("gpt-4.1"),
            false,
            Some(ModelProvider::OpenAI),
        );

        assert_eq!(resolved.model_provider, ModelProvider::OpenRouter);
        assert_eq!(resolved.model_name, "openai/gpt-4.1");
        clear_llm_env();
    }

    #[test]
    fn placeholder_keys_are_ignored() {
        clear_llm_env();
        env::set_var("OPENAI_API_KEY", "your-openai-api-key");
        env::set_var("OPENROUTER_API_KEY", "sk-or-real-key");

        let resolved = resolve_llm_config(None, false, Some(ModelProvider::OpenAI));
        assert_eq!(resolved.model_provider, ModelProvider::OpenRouter);
        clear_llm_env();
    }

    #[test]
    fn empty_keys_are_ignored() {
        clear_llm_env();
        env::set_var("OPENAI_API_KEY", "   ");
        env::set_var("OPENROUTER_API_KEY", "sk-or-real-key");

        let resolved = resolve_llm_config(None, false, None);
        assert_eq!(resolved.model_provider, ModelProvider::OpenRouter);
        clear_llm_env();
    }

    #[test]
    fn ollama_flag_wins_over_env_keys() {
        clear_llm_env();
        env::set_var("OPENROUTER_API_KEY", "sk-or-real-key");

        let resolved = resolve_llm_config(None, true, None);
        assert_eq!(resolved.model_provider, ModelProvider::Ollama);
        clear_llm_env();
    }
}
