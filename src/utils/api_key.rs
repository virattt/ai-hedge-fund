// Source: src/utils/api_key.py
//! Sibling to src/utils/api_key.py
//! Retrieves and validates financial datasets and model provider API keys from state or system environment.

use std::env;

use crate::graph::state::AgentState;

/// Returns true when a key is present and not a documented placeholder.
pub fn is_valid_api_key(key: &str) -> bool {
    let trimmed = key.trim();
    !trimmed.is_empty() && !trimmed.starts_with("your-")
}

/// Read an environment variable and treat placeholders / empty values as unset.
pub fn env_api_key(name: &str) -> Option<String> {
    env::var(name).ok().filter(|key| is_valid_api_key(key))
}

/// Retrieve an API key from the agent state metadata or the system environment variables.
pub fn get_api_key_from_state(state: &AgentState, api_key_name: &str) -> Option<String> {
    // 1. Direct key lookup in state.metadata
    if let Some(val) = state.metadata.get(api_key_name).and_then(|v| v.as_str()) {
        return Some(val.to_string());
    }

    // 2. Lookup within nested request payload (metadata.request.api_keys)
    if let Some(req) = state.metadata.get("request") {
        if let Some(api_keys) = req.get("api_keys") {
            if let Some(key) = api_keys.get(api_key_name).and_then(|v| v.as_str()) {
                return Some(key.to_string());
            }
        }
    }

    // 3. Fallback to system environment variable
    std::env::var(api_key_name).ok()
}
