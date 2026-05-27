// Source: src/llm/models.py
//! Sibling to src/llm/models.py
//! Defines enum of supported LLM providers and configs for querying models (OpenAI, Anthropic, Google, local Ollama).

use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize, Clone, PartialEq, Eq)]
pub enum ModelProvider {
    Alibaba,
    Anthropic,
    DeepSeek,
    Google,
    Groq,
    Kimi,
    Meta,
    Mistral,
    OpenAI,
    Ollama,
    OpenRouter,
    GigaChat,
    #[serde(rename = "Azure OpenAI")]
    AzureOpenAI,
    xAI,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct LLMModel {
    pub display_name: String,
    pub model_name: String,
    pub provider: ModelProvider,
}

impl ModelProvider {
    /// Parse a provider label from workflow metadata or API requests.
    pub fn from_label(label: &str) -> Option<Self> {
        match label.trim().to_ascii_lowercase().as_str() {
            "alibaba" => Some(ModelProvider::Alibaba),
            "anthropic" => Some(ModelProvider::Anthropic),
            "deepseek" => Some(ModelProvider::DeepSeek),
            "google" => Some(ModelProvider::Google),
            "groq" => Some(ModelProvider::Groq),
            "kimi" | "moonshot" => Some(ModelProvider::Kimi),
            "meta" => Some(ModelProvider::Meta),
            "mistral" => Some(ModelProvider::Mistral),
            "openai" => Some(ModelProvider::OpenAI),
            "ollama" => Some(ModelProvider::Ollama),
            "openrouter" => Some(ModelProvider::OpenRouter),
            "gigachat" => Some(ModelProvider::GigaChat),
            "azure openai" | "azure_openai" => Some(ModelProvider::AzureOpenAI),
            "xai" => Some(ModelProvider::xAI),
            _ => None,
        }
    }

    pub fn value(&self) -> &'static str {
        match self {
            ModelProvider::Alibaba => "Alibaba",
            ModelProvider::Anthropic => "Anthropic",
            ModelProvider::DeepSeek => "DeepSeek",
            ModelProvider::Google => "Google",
            ModelProvider::Groq => "Groq",
            ModelProvider::Kimi => "Kimi",
            ModelProvider::Meta => "Meta",
            ModelProvider::Mistral => "Mistral",
            ModelProvider::OpenAI => "OpenAI",
            ModelProvider::Ollama => "Ollama",
            ModelProvider::OpenRouter => "OpenRouter",
            ModelProvider::GigaChat => "GigaChat",
            ModelProvider::AzureOpenAI => "Azure OpenAI",
            ModelProvider::xAI => "xAI",
        }
    }
}

impl LLMModel {
    pub fn is_custom(&self) -> bool {
        self.model_name == "-"
    }

    pub fn has_json_mode(&self) -> bool {
        if self.is_deepseek() || self.is_gemini() {
            return false;
        }
        if self.is_ollama() {
            return self.model_name.contains("llama3") || self.model_name.contains("neural-chat");
        }
        if self.provider == ModelProvider::OpenRouter {
            return true;
        }
        true
    }

    pub fn is_deepseek(&self) -> bool {
        self.model_name.starts_with("deepseek")
    }

    pub fn is_kimi(&self) -> bool {
        self.provider == ModelProvider::Kimi
    }

    pub fn is_gemini(&self) -> bool {
        self.model_name.starts_with("gemini")
    }

    pub fn is_ollama(&self) -> bool {
        self.provider == ModelProvider::Ollama
    }
}

/// Helper function to load model configurations.
pub fn load_models_from_json(json_path: &str) -> Vec<LLMModel> {
    let filename = if json_path.contains("/") {
        json_path.split('/').last().unwrap_or(json_path)
    } else {
        json_path
    };

    let paths = vec![
        json_path.to_string(),
        format!("ai-hedge-fund/src/llm/{}", filename),
        format!("src/llm/{}", filename),
        format!("../src/llm/{}", filename),
        format!("../../src/llm/{}", filename),
    ];

    for p in paths {
        if let Ok(content) = std::fs::read_to_string(&p) {
            if let Ok(models) = serde_json::from_str::<Vec<LLMModel>>(&content) {
                return models;
            }
        }
    }
    Vec::new()
}

/// Retrieves model info matching a name and provider.
pub fn get_model_info(model_name: &str, model_provider: &str) -> Option<LLMModel> {
    let mut models = load_models_from_json("api_models.json");
    models.extend(load_models_from_json("ollama_models.json"));
    
    models.into_iter().find(|m| {
        m.model_name == model_name && format!("{:?}", m.provider).to_lowercase() == model_provider.to_lowercase()
    })
}

/// Resolves a generic request/client instance for the specified LLM setup.
pub fn get_model(
    model_name: &str,
    model_provider: ModelProvider,
    _api_keys: Option<std::collections::HashMap<String, String>>,
) -> Result<serde_json::Value, anyhow::Error> {
    println!("Initializing model connection for {} ({:?})", model_name, model_provider);
    Ok(serde_json::json!({
        "status": "client_placeholder"
    }))
}

pub fn get_models_list() -> Vec<serde_json::Value> {
    let models = load_models_from_json("api_models.json");
    models.into_iter().map(|m| {
        serde_json::json!({
            "display_name": m.display_name,
            "model_name": m.model_name,
            "provider": m.provider.value()
        })
    }).collect()
}

pub fn get_ollama_models() -> Vec<LLMModel> {
    load_models_from_json("ollama_models.json")
}
