// Source: src/agents/risk_manager.py
//! Sibling to src/agents/risk_manager.py
//! Manages portfolio risk by calculating position sizing limits adjusted for volatility and asset correlation.

use anyhow::{Result, Context};
use std::collections::{HashMap, HashSet};
use crate::graph::state::AgentState;
use crate::tools::api::get_prices;

/// Volatility adjusted risk management agent entry node.
pub async fn risk_management_agent(state: &mut AgentState, agent_id: &str) -> Result<()> {
    println!("Running Risk Management Agent: {}", agent_id);

    let start_date = state.data.get("start_date")
        .and_then(|v| v.as_str())
        .context("Missing start_date in state data")?;

    let end_date = state.data.get("end_date")
        .and_then(|v| v.as_str())
        .context("Missing end_date in state data")?;

    let tickers_json = state.data.get("tickers")
        .context("Missing tickers in state data")?;
    let tickers: Vec<String> = serde_json::from_value(tickers_json.clone())?;

    let portfolio = state.data.get("portfolio")
        .context("Missing portfolio in state data")?;

    let api_key = state.metadata.get("FINANCIAL_DATASETS_API_KEY")
        .and_then(|v| v.as_str());

    let mut risk_analysis = serde_json::Map::new();
    let mut current_prices = HashMap::new();
    let mut annualized_vols = HashMap::new();
    let mut returns_by_ticker = HashMap::new();

    // Determine all active positions
    let positions_map = portfolio.get("positions")
        .and_then(|p| p.as_object());
    
    let mut all_tickers = HashSet::new();
    for t in &tickers {
        all_tickers.insert(t.clone());
    }
    if let Some(pos_obj) = positions_map {
        for k in pos_obj.keys() {
            all_tickers.insert(k.clone());
        }
    }

    for ticker in &all_tickers {
        let prices = match get_prices(ticker, start_date, end_date, api_key).await {
            Ok(p) => p,
            Err(_) => {
                current_prices.insert(ticker.clone(), 0.0);
                annualized_vols.insert(ticker.clone(), 0.25);
                continue;
            }
        };

        if prices.len() < 2 {
            current_prices.insert(ticker.clone(), 0.0);
            annualized_vols.insert(ticker.clone(), 0.25);
            continue;
        }

        let closes: Vec<f64> = prices.iter().map(|p| p.close).collect();
        let last_price = closes[closes.len() - 1];
        current_prices.insert(ticker.clone(), last_price);

        // Daily returns volatility
        let mut daily_returns = Vec::new();
        for i in 1..closes.len() {
            let prev = closes[i - 1];
            daily_returns.push((closes[i] - prev) / if prev == 0.0 { 1e-8 } else { prev });
        }

        let mean = daily_returns.iter().sum::<f64>() / daily_returns.len() as f64;
        let variance = daily_returns.iter().map(|&x| (x - mean).powi(2)).sum::<f64>() / daily_returns.len() as f64;
        let daily_vol = variance.sqrt();
        let ann_vol = daily_vol * 252.0_f64.sqrt();

        annualized_vols.insert(ticker.clone(), ann_vol);
        returns_by_ticker.insert(ticker.clone(), daily_returns);
    }

    // Correlation multiplier calculation
    let mut avg_correlations = HashMap::new();
    for t1 in &tickers {
        let mut correlations = Vec::new();
        if let Some(r1) = returns_by_ticker.get(t1) {
            for t2 in &all_tickers {
                if t1 == t2 {
                    continue;
                }
                if let Some(r2) = returns_by_ticker.get(t2) {
                    let len = std::cmp::min(r1.len(), r2.len());
                    if len > 5 {
                        let slice1 = &r1[r1.len() - len..];
                        let slice2 = &r2[r2.len() - len..];
                        let mean1 = slice1.iter().sum::<f64>() / len as f64;
                        let mean2 = slice2.iter().sum::<f64>() / len as f64;
                        let cov = slice1.iter().zip(slice2.iter()).map(|(&x, &y)| (x - mean1) * (y - mean2)).sum::<f64>() / len as f64;
                        let var1 = slice1.iter().map(|&x| (x - mean1).powi(2)).sum::<f64>() / len as f64;
                        let var2 = slice2.iter().map(|&x| (x - mean2).powi(2)).sum::<f64>() / len as f64;
                        let std1 = var1.sqrt();
                        let std2 = var2.sqrt();
                        let corr = if std1 > 0.0 && std2 > 0.0 { cov / (std1 * std2) } else { 0.0 };
                        correlations.push(corr);
                    }
                }
            }
        }
        let avg_corr = if correlations.is_empty() {
            0.0
        } else {
            correlations.iter().sum::<f64>() / correlations.len() as f64
        };
        avg_correlations.insert(t1.clone(), avg_corr);
    }

    // Portfolio Value Points
    let cash = portfolio.get("cash").and_then(|v| v.as_f64()).unwrap_or(100000.0);
    let mut total_portfolio_value = cash;
    if let Some(pos_obj) = positions_map {
        for (ticker, pos_val) in pos_obj {
            if let Some(price) = current_prices.get(ticker) {
                let long = pos_val.get("long").and_then(|v| v.as_i64()).unwrap_or(0) as f64;
                let short = pos_val.get("short").and_then(|v| v.as_i64()).unwrap_or(0) as f64;
                total_portfolio_value += long * price;
                total_portfolio_value -= short * price;
            }
        }
    }

    // Calculate limit per ticker
    for ticker in &tickers {
        let current_price = current_prices.get(ticker).copied().unwrap_or(0.0);
        if current_price <= 0.0 {
            risk_analysis.insert(
                ticker.clone(),
                serde_json::json!({
                    "remaining_position_limit": 0.0,
                    "current_price": 0.0,
                    "reasoning": {
                        "error": "Missing price data for risk calculation"
                    }
                })
            );
            continue;
        }

        let ann_vol = annualized_vols.get(ticker).copied().unwrap_or(0.25);
        let vol_limit_pct = calculate_volatility_adjusted_limit(ann_vol);

        let avg_corr = avg_correlations.get(ticker).copied().unwrap_or(0.0);
        let corr_mult = calculate_correlation_multiplier(avg_corr);

        let combined_limit_pct = vol_limit_pct * corr_mult;
        let position_limit = total_portfolio_value * combined_limit_pct;

        // Current position absolute exposure
        let mut current_exposure = 0.0;
        if let Some(pos_obj) = positions_map {
            if let Some(pos_val) = pos_obj.get(ticker) {
                let long = pos_val.get("long").and_then(|v| v.as_i64()).unwrap_or(0) as f64;
                let short = pos_val.get("short").and_then(|v| v.as_i64()).unwrap_or(0) as f64;
                current_exposure = (long * current_price - short * current_price).abs();
            }
        }

        let remaining_limit = (position_limit - current_exposure).max(0.0);
        let max_position_size = remaining_limit.min(cash);

        risk_analysis.insert(
            ticker.clone(),
            serde_json::json!({
                "remaining_position_limit": max_position_size,
                "current_price": current_price,
                "volatility_metrics": {
                    "annualized_volatility": ann_vol
                },
                "correlation_metrics": {
                    "avg_correlation_with_active": avg_corr
                },
                "reasoning": {
                    "portfolio_value": total_portfolio_value,
                    "current_position_value": current_exposure,
                    "base_position_limit_pct": vol_limit_pct,
                    "correlation_multiplier": corr_mult,
                    "combined_position_limit_pct": combined_limit_pct,
                    "position_limit": position_limit,
                    "remaining_limit": remaining_limit,
                    "available_cash": cash
                }
            })
        );
    }

    let analyst_signals = state.data.entry("analyst_signals".to_string())
        .or_insert_with(|| serde_json::json!({}));
    
    if let Some(obj) = analyst_signals.as_object_mut() {
        obj.insert(agent_id.to_string(), serde_json::Value::Object(risk_analysis));
    }

    Ok(())
}

pub fn calculate_volatility_adjusted_limit(annualized_volatility: f64) -> f64 {
    let base_limit = 0.20;
    let vol_multiplier = if annualized_volatility < 0.15 {
        1.25
    } else if annualized_volatility < 0.30 {
        1.0 - (annualized_volatility - 0.15) * 0.5
    } else if annualized_volatility < 0.50 {
        0.75 - (annualized_volatility - 0.30) * 0.5
    } else {
        0.50
    };
    let vol_multiplier = vol_multiplier.max(0.25).min(1.25);
    base_limit * vol_multiplier
}

pub fn calculate_correlation_multiplier(avg_correlation: f64) -> f64 {
    if avg_correlation >= 0.80 {
        0.70
    } else if avg_correlation >= 0.60 {
        0.85
    } else if avg_correlation >= 0.40 {
        1.00
    } else if avg_correlation >= 0.20 {
        1.05
    } else {
        1.10
    }
}
