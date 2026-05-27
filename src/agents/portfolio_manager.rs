// Source: src/agents/portfolio_manager.py
//! Sibling to src/agents/portfolio_manager.py
//! Makes the final trading decisions, enforcing position sizing limits and capital/margin constraints.

use anyhow::{Result, Context};
use std::collections::HashMap;
use crate::graph::state::AgentState;

/// Struct mirroring the Pydantic `PortfolioDecision` model.
#[derive(Debug, serde::Serialize, serde::Deserialize, Clone)]
pub struct PortfolioDecision {
    pub action: String,      // "buy" | "sell" | "short" | "cover" | "hold"
    pub quantity: u32,
    pub confidence: u32,     // 0-100
    pub reasoning: String,
}

/// Struct mirroring the Pydantic `PortfolioManagerOutput` model.
#[derive(Debug, serde::Serialize, serde::Deserialize, Clone)]
pub struct PortfolioManagerOutput {
    pub decisions: HashMap<String, PortfolioDecision>,
}

/// Main entry node for the portfolio management agent.
pub async fn portfolio_management_agent(state: &mut AgentState, agent_id: &str) -> Result<()> {
    println!("Running Portfolio Management Agent: {}", agent_id);

    let tickers_json = state.data.get("tickers")
        .context("Missing tickers in state data")?;
    let tickers: Vec<String> = serde_json::from_value(tickers_json.clone())?;

    let portfolio = state.data.get("portfolio")
        .context("Missing portfolio in portfolio_manager")?;
    
    let analyst_signals = state.data.get("analyst_signals")
        .context("Missing analyst_signals in state data")?;

    let mut current_prices = HashMap::new();
    let mut max_shares = HashMap::new();
    let mut signals_by_ticker = HashMap::new();

    // Risk manager ID mapping
    let risk_manager_id = "risk_management_agent";
    let risk_data = analyst_signals.get(risk_manager_id);

    for ticker in &tickers {
        let remaining_limit = risk_data
            .and_then(|r| r.get(ticker))
            .and_then(|t| t.get("remaining_position_limit"))
            .and_then(|l| l.as_f64())
            .unwrap_or(0.0);

        let current_price = risk_data
            .and_then(|r| r.get(ticker))
            .and_then(|t| t.get("current_price"))
            .and_then(|p| p.as_f64())
            .unwrap_or(0.0);

        current_prices.insert(ticker.clone(), current_price);

        let max_qty = if current_price > 0.0 {
            (remaining_limit / current_price) as u32
        } else {
            0
        };
        max_shares.insert(ticker.clone(), max_qty);

        // Gather signals from other analysts (excluding risk manager)
        let mut ticker_signals = HashMap::new();
        if let Some(signals_obj) = analyst_signals.as_object() {
            for (agent, sigs) in signals_obj {
                if agent != risk_manager_id {
                    if let Some(t_sig) = sigs.get(ticker) {
                        let sig = t_sig.get("signal").and_then(|s| s.as_str()).unwrap_or("neutral").to_string();
                        let conf = t_sig.get("confidence").and_then(|c| c.as_u64()).unwrap_or(50) as u32;
                        ticker_signals.insert(agent.clone(), (sig, conf));
                    }
                }
            }
        }
        signals_by_ticker.insert(ticker.clone(), ticker_signals);
    }

    // Generate Decisions
    let result = generate_trading_decision(
        tickers,
        signals_by_ticker,
        current_prices,
        max_shares,
        portfolio,
    )?;

    // Append final message to state messages
    let decision_value = serde_json::to_value(result.clone())?;
    state.messages.push(decision_value);

    // Save final decision in state data
    state.data.insert("decisions".to_string(), serde_json::to_value(result.decisions)?);

    Ok(())
}

pub fn compute_allowed_actions(
    tickers: &[String],
    current_prices: &HashMap<String, f64>,
    max_shares: &HashMap<String, u32>,
    portfolio: &serde_json::Value,
) -> HashMap<String, HashMap<String, u32>> {
    let mut allowed = HashMap::new();
    let cash = portfolio.get("cash").and_then(|v| v.as_f64()).unwrap_or(100000.0);
    let positions_map = portfolio.get("positions").and_then(|p| p.as_object());

    for ticker in tickers {
        let price = current_prices.get(ticker).copied().unwrap_or(0.0);
        let max_qty = max_shares.get(ticker).copied().unwrap_or(0);

        let long_shares = positions_map
            .and_then(|p| p.get(ticker))
            .and_then(|pos| pos.get("long"))
            .and_then(|l| l.as_i64())
            .unwrap_or(0) as u32;

        let short_shares = positions_map
            .and_then(|p| p.get(ticker))
            .and_then(|pos| pos.get("short"))
            .and_then(|s| s.as_i64())
            .unwrap_or(0) as u32;

        let mut actions = HashMap::new();
        actions.insert("hold".to_string(), 0);

        // Long capacity
        if long_shares > 0 {
            actions.insert("sell".to_string(), long_shares);
        }
        if cash > 0.0 && price > 0.0 {
            let max_buy_cash = (cash / price) as u32;
            let max_buy = std::cmp::min(max_qty, max_buy_cash);
            if max_buy > 0 {
                actions.insert("buy".to_string(), max_buy);
            }
        }

        // Short capacity
        if short_shares > 0 {
            actions.insert("cover".to_string(), short_shares);
        }
        if price > 0.0 && max_qty > 0 {
            let max_short = max_qty; // Sized by risk limit and cash
            if max_short > 0 {
                actions.insert("short".to_string(), max_short);
            }
        }

        allowed.insert(ticker.clone(), actions);
    }
    allowed
}

pub fn generate_trading_decision(
    tickers: Vec<String>,
    signals_by_ticker: HashMap<String, HashMap<String, (String, u32)>>,
    current_prices: HashMap<String, f64>,
    max_shares: HashMap<String, u32>,
    portfolio: &serde_json::Value,
) -> Result<PortfolioManagerOutput> {
    let allowed_actions = compute_allowed_actions(&tickers, &current_prices, &max_shares, portfolio);
    let mut decisions = HashMap::new();

    for ticker in tickers {
        let allowed = allowed_actions.get(&ticker).context("Missing allowed actions for ticker")?;
        let ticker_signals = signals_by_ticker.get(&ticker).context("Missing signals for ticker")?;

        // Consensus signal voting
        let mut bull_weight = 0.0;
        let mut bear_weight = 0.0;
        for (_agent, (sig, conf)) in ticker_signals {
            let weight = *conf as f64 / 100.0;
            if sig == "bullish" {
                bull_weight += weight;
            } else if sig == "bearish" {
                bear_weight += weight;
            }
        }

        let mut action = "hold".to_string();
        let mut quantity = 0;
        let mut reasoning = "Neutral stance".to_string();

        if bull_weight > bear_weight {
            // We want to buy or cover
            if allowed.contains_key("cover") {
                action = "cover".to_string();
                quantity = *allowed.get("cover").unwrap();
                reasoning = "Covering short position based on bullish consensus".to_string();
            } else if allowed.contains_key("buy") {
                action = "buy".to_string();
                quantity = *allowed.get("buy").unwrap();
                reasoning = "Initiating long buy based on bullish consensus".to_string();
            }
        } else if bear_weight > bull_weight {
            // We want to sell or short
            if allowed.contains_key("sell") {
                action = "sell".to_string();
                quantity = *allowed.get("sell").unwrap();
                reasoning = "Selling long position based on bearish consensus".to_string();
            } else if allowed.contains_key("short") {
                action = "short".to_string();
                quantity = *allowed.get("short").unwrap();
                reasoning = "Initiating short position based on bearish consensus".to_string();
            }
        }

        let conf = if bull_weight + bear_weight > 0.0 {
            (bull_weight.max(bear_weight) / (bull_weight + bear_weight) * 100.0) as u32
        } else {
            100
        };

        decisions.insert(
            ticker,
            PortfolioDecision {
                action,
                quantity,
                confidence: conf,
                reasoning,
            },
        );
    }

    Ok(PortfolioManagerOutput { decisions })
}
