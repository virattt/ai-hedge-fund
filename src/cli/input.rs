// Source: src/cli/input.py
//! Sibling to src/cli/input.py
//! Handles CLI argument parsing and interactive configuration settings using the clap crate.

use crate::data::provider::DataProvider;
use clap::Parser;

/// CLIInputs matches the structure returned by parse_cli_inputs in Python.
#[derive(Parser, Debug, Clone)]
#[clap(name = "ai-hedge-fund", author = "DeepMind Pair Builder")]
pub struct CLIInputs {
    /// Comma-separated list of stock ticker symbols (e.g., AAPL,MSFT)
    #[clap(long, short = 't', value_delimiter = ',')]
    pub tickers: Vec<String>,

    /// Comma-separated list of analysts to use
    #[clap(long, value_delimiter = ',')]
    pub analysts: Option<Vec<String>>,

    /// Use all available analysts
    #[clap(long, action)]
    pub analysts_all: bool,

    /// Use Ollama for local LLM inference
    #[clap(long, action)]
    pub ollama: bool,

    /// Model name to use (e.g., gpt-4o)
    #[clap(long, short = 'm')]
    pub model: Option<String>,

    /// Start date in YYYY-MM-DD format
    #[clap(long)]
    pub start_date: Option<String>,

    /// End date in YYYY-MM-DD format
    #[clap(long)]
    pub end_date: Option<String>,

    /// Initial cash position
    #[clap(long, default_value_t = 100000.0)]
    pub initial_cash: f64,

    /// Initial margin requirement ratio for shorts
    #[clap(long, default_value_t = 0.5)]
    pub margin_requirement: f64,

    /// Show reasoning from each agent
    #[clap(long, action)]
    pub show_reasoning: bool,

    /// Show the agent graph
    #[clap(long, action)]
    pub show_agent_graph: bool,

    /// Financial data provider (`financial-datasets` or `yahoo-finance`).
    /// Defaults to yahoo-finance when FINANCIAL_DATASETS_API_KEY is not set.
    #[clap(long)]
    pub data_provider: Option<String>,
}

/// Resolves start and end dates based on parameters, falling back to months-back offset if needed.
pub fn resolve_dates(
    start_date: Option<String>,
    end_date: Option<String>,
    default_months_back: Option<i32>,
) -> (String, String) {
    let today = chrono::Local::now().naive_local().date();

    let resolved_end = end_date.unwrap_or_else(|| today.format("%Y-%m-%d").to_string());
    let end_dt = chrono::NaiveDate::parse_from_str(&resolved_end, "%Y-%m-%d").unwrap_or(today);

    let resolved_start = start_date.unwrap_or_else(|| {
        let months = default_months_back.unwrap_or(1) as i64;
        let start_dt = end_dt - chrono::Duration::days(months * 30);
        start_dt.format("%Y-%m-%d").to_string()
    });

    (resolved_start, resolved_end)
}

/// Parses the CLI inputs, falling back to interactive selection if requirements are missing.
pub fn parse_cli_inputs() -> CLIInputs {
    CLIInputs::parse()
}

/// Resolve the data provider from CLI flag and environment.
pub fn resolve_data_provider(cli_value: Option<&str>) -> DataProvider {
    let explicit = cli_value.and_then(DataProvider::from_cli_str);
    DataProvider::resolve(explicit)
}
