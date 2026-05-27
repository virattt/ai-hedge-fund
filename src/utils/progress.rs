// Source: src/utils/progress.py
//! Sibling to src/utils/progress.py
//! Tracks and displays multi-step interactive loading indicators for executing agent workflows.

pub struct AgentProgress;

impl AgentProgress {
    pub fn new() -> Self {
        Self
    }

    /// Mock progress updating.
    pub fn update_status(&self, agent_name: &str, ticker: Option<&str>, status: &str) {
        let ticker_str = ticker.map(|t| format!(" [{}]", t)).unwrap_or_default();
        println!("\x1b[33mProgress:\x1b[0m {}{} - {}", agent_name, ticker_str, status);
    }
}

pub static PROGRESS: AgentProgress = AgentProgress;
