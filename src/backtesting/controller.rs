// Source: src/backtesting/controller.py
//! Sibling to src/backtesting/controller.py
//! Coordinates backtesting simulation flow and updates overall execution states.

use crate::backtesting::portfolio::Portfolio;
use crate::data::provider::DataProvider;
use crate::workflow::{run_hedge_fund, HedgeFundOptions, HedgeFundResult, HedgeFundRunRequest};
use anyhow::Result;

pub struct AgentController;

pub struct AgentRunRequest<'a> {
    pub tickers: Vec<String>,
    pub end_date: &'a str,
    pub portfolio: &'a Portfolio,
    pub model_name: &'a str,
    pub model_provider: &'a str,
    pub selected_analysts: Vec<String>,
    pub data_provider: Option<DataProvider>,
}

impl AgentController {
    pub fn new() -> Self {
        Self
    }

    /// Invokes the primary trading agent flow and returns the normalized outputs.
    pub async fn run_agent(&self, request: AgentRunRequest<'_>) -> Result<HedgeFundResult> {
        let portfolio_json = serde_json::to_value(request.portfolio)?;

        run_hedge_fund(HedgeFundRunRequest {
            tickers: request.tickers,
            end_date: request.end_date,
            portfolio: portfolio_json,
            options: HedgeFundOptions {
                show_reasoning: false,
                selected_analysts: request.selected_analysts,
                model_name: request.model_name,
                model_provider: request.model_provider,
                data_provider: request.data_provider,
            },
        })
        .await
    }
}

impl Default for AgentController {
    fn default() -> Self {
        Self::new()
    }
}
