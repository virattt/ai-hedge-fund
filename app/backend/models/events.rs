use serde::{Serialize, Deserialize};
use axum::response::sse::Event;

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct StartEvent {
    pub r#type: String,
    pub timestamp: Option<String>,
}

impl StartEvent {
    pub fn new() -> Self {
        Self {
            r#type: "start".to_string(),
            timestamp: Some(chrono::Utc::now().to_rfc3339()),
        }
    }

    pub fn to_sse(&self) -> Result<Event, serde_json::Error> {
        let data = serde_json::to_string(self)?;
        Ok(Event::default().event("start").data(data))
    }
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct ProgressUpdateEvent {
    pub r#type: String,
    pub agent: String,
    pub ticker: Option<String>,
    pub status: String,
    pub timestamp: Option<String>,
    pub analysis: Option<String>,
}

impl ProgressUpdateEvent {
    pub fn new(agent: String, ticker: Option<String>, status: String, analysis: Option<String>) -> Self {
        Self {
            r#type: "progress".to_string(),
            agent,
            ticker,
            status,
            timestamp: Some(chrono::Utc::now().to_rfc3339()),
            analysis,
        }
    }

    pub fn to_sse(&self) -> Result<Event, serde_json::Error> {
        let data = serde_json::to_string(self)?;
        Ok(Event::default().event("progress").data(data))
    }
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct ErrorEvent {
    pub r#type: String,
    pub message: String,
    pub timestamp: Option<String>,
}

impl ErrorEvent {
    pub fn new(message: String) -> Self {
        Self {
            r#type: "error".to_string(),
            message,
            timestamp: Some(chrono::Utc::now().to_rfc3339()),
        }
    }

    pub fn to_sse(&self) -> Result<Event, serde_json::Error> {
        let data = serde_json::to_string(self)?;
        Ok(Event::default().event("error").data(data))
    }
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct CompleteEvent {
    pub r#type: String,
    pub data: serde_json::Value,
    pub timestamp: Option<String>,
}

impl CompleteEvent {
    pub fn new(data: serde_json::Value) -> Self {
        Self {
            r#type: "complete".to_string(),
            data,
            timestamp: Some(chrono::Utc::now().to_rfc3339()),
        }
    }

    pub fn to_sse(&self) -> Result<Event, serde_json::Error> {
        let data = serde_json::to_string(self)?;
        Ok(Event::default().event("complete").data(data))
    }
}
