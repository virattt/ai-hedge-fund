// Source: src/backtesting/controller.py
//! Sibling to src/backtesting/controller.py
//! Coordinates backtesting simulation flow and updates overall execution states.

use crate::backtesting::portfolio::Portfolio;
use crate::workflow::{run_hedge_fund, HedgeFundResult};
use anyhow::Result;

pub struct AgentController;

impl AgentController {
    pub fn new() -> Self {
        Self
    }

    /// Invokes the primary trading agent flow and returns the normalized outputs.
    pub async fn run_agent(
        &self,
        tickers: Vec<String>,
        start_date: &str,
        end_date: &str,
        portfolio: &Portfolio,
        model_name: &str,
        model_provider: &str,
        selected_analysts: Vec<String>,
    ) -> Result<HedgeFundResult> {
        let portfolio_json = serde_json::to_value(portfolio)?;
        
        run_hedge_fund(
            tickers,
            start_date,
            end_date,
            portfolio_json,
            false, // show_reasoning
            selected_analysts,
            model_name,
            model_provider,
        )
        .await
    }
}
