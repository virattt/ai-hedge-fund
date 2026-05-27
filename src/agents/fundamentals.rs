// Source: src/agents/fundamentals.py
//! Sibling to src/agents/fundamentals.py
//! Performs quantitative fundamental analysis on financial metrics (profitability, growth, health, valuation).

use crate::graph::state::AgentState;
use crate::tools::api::get_financial_metrics;
use anyhow::{Context, Result};

/// Performs fundamental analysis and inserts signals into the AgentState.
pub async fn fundamentals_analyst_agent(state: &mut AgentState, agent_id: &str) -> Result<()> {
    println!("Running Fundamentals Analyst Agent: {}", agent_id);

    let end_date = state
        .data
        .get("end_date")
        .and_then(|v| v.as_str())
        .context("Missing end_date in state data")?;

    let tickers_json = state
        .data
        .get("tickers")
        .context("Missing tickers in state data")?;

    let tickers: Vec<String> = serde_json::from_value(tickers_json.clone())?;

    let api_key = state
        .metadata
        .get("FINANCIAL_DATASETS_API_KEY")
        .and_then(|v| v.as_str());

    let mut fundamental_analysis = serde_json::Map::new();

    for ticker in &tickers {
        // Fetch financial metrics
        let financial_metrics =
            match get_financial_metrics(ticker, end_date, "ttm", 10, api_key).await {
                Ok(m) => m,
                Err(e) => {
                    println!("Warning: Failed to fetch metrics for {}: {:?}", ticker, e);
                    continue;
                }
            };

        if financial_metrics.is_empty() {
            println!("Warning: No financial metrics found for {}", ticker);
            continue;
        }

        let metrics = &financial_metrics[0];

        // 1. Profitability Analysis
        let roe = metrics.return_on_equity.unwrap_or(0.0);
        let net_margin = metrics.net_margin.unwrap_or(0.0);
        let operating_margin = metrics.operating_margin.unwrap_or(0.0);

        let mut profitability_score = 0;
        if metrics.return_on_equity.is_some() && roe > 0.15 {
            profitability_score += 1;
        }
        if metrics.net_margin.is_some() && net_margin > 0.20 {
            profitability_score += 1;
        }
        if metrics.operating_margin.is_some() && operating_margin > 0.15 {
            profitability_score += 1;
        }

        let profitability_signal = if profitability_score >= 2 {
            "bullish"
        } else if profitability_score == 0 {
            "bearish"
        } else {
            "neutral"
        };

        // 2. Growth Analysis
        let rev_growth = metrics.revenue_growth.unwrap_or(0.0);
        let earn_growth = metrics.earnings_growth.unwrap_or(0.0);
        let bv_growth = metrics.book_value_growth.unwrap_or(0.0);

        let mut growth_score = 0;
        if metrics.revenue_growth.is_some() && rev_growth > 0.10 {
            growth_score += 1;
        }
        if metrics.earnings_growth.is_some() && earn_growth > 0.10 {
            growth_score += 1;
        }
        if metrics.book_value_growth.is_some() && bv_growth > 0.10 {
            growth_score += 1;
        }

        let growth_signal = if growth_score >= 2 {
            "bullish"
        } else if growth_score == 0 {
            "bearish"
        } else {
            "neutral"
        };

        // 3. Financial Health
        let current_ratio = metrics.current_ratio.unwrap_or(0.0);
        let debt_to_equity = metrics.debt_to_equity.unwrap_or(0.0);
        let fcf_ps = metrics.free_cash_flow_per_share.unwrap_or(0.0);
        let eps = metrics.earnings_per_share.unwrap_or(0.0);

        let mut health_score = 0;
        if metrics.current_ratio.is_some() && current_ratio > 1.5 {
            health_score += 1;
        }
        if metrics.debt_to_equity.is_some() && debt_to_equity < 0.5 {
            health_score += 1;
        }
        if metrics.free_cash_flow_per_share.is_some()
            && metrics.earnings_per_share.is_some()
            && fcf_ps > eps * 0.8
        {
            health_score += 1;
        }

        let health_signal = if health_score >= 2 {
            "bullish"
        } else if health_score == 0 {
            "bearish"
        } else {
            "neutral"
        };

        // 4. Valuation Ratios
        let pe_ratio = metrics.price_to_earnings_ratio.unwrap_or(0.0);
        let pb_ratio = metrics.price_to_book_ratio.unwrap_or(0.0);
        let ps_ratio = metrics.price_to_sales_ratio.unwrap_or(0.0);

        let mut price_ratio_score = 0;
        if metrics.price_to_earnings_ratio.is_some() && pe_ratio > 25.0 {
            price_ratio_score += 1;
        }
        if metrics.price_to_book_ratio.is_some() && pb_ratio > 3.0 {
            price_ratio_score += 1;
        }
        if metrics.price_to_sales_ratio.is_some() && ps_ratio > 5.0 {
            price_ratio_score += 1;
        }

        let price_ratios_signal = if price_ratio_score >= 2 {
            "bearish"
        } else if price_ratio_score == 0 {
            "bullish"
        } else {
            "neutral"
        };

        // Aggregate overall signal
        let signals = [
            profitability_signal,
            growth_signal,
            health_signal,
            price_ratios_signal,
        ];
        let bullish_count = signals.iter().filter(|&&s| s == "bullish").count();
        let bearish_count = signals.iter().filter(|&&s| s == "bearish").count();

        let overall_signal = if bullish_count > bearish_count {
            "bullish"
        } else if bearish_count > bullish_count {
            "bearish"
        } else {
            "neutral"
        };

        let confidence = (std::cmp::max(bullish_count, bearish_count) as f64 / 4.0 * 100.0) as u32;

        let reasoning = serde_json::json!({
            "profitability_signal": {
                "signal": profitability_signal,
                "details": format!("ROE: {:.2}%, Net Margin: {:.2}%, Op Margin: {:.2}%", roe * 100.0, net_margin * 100.0, operating_margin * 100.0)
            },
            "growth_signal": {
                "signal": growth_signal,
                "details": format!("Revenue Growth: {:.2}%, Earnings Growth: {:.2}%", rev_growth * 100.0, earn_growth * 100.0)
            },
            "financial_health_signal": {
                "signal": health_signal,
                "details": format!("Current Ratio: {:.2}, D/E: {:.2}", current_ratio, debt_to_equity)
            },
            "price_ratios_signal": {
                "signal": price_ratios_signal,
                "details": format!("P/E: {:.2}, P/B: {:.2}, P/S: {:.2}", pe_ratio, pb_ratio, ps_ratio)
            }
        });

        fundamental_analysis.insert(
            ticker.clone(),
            serde_json::json!({
                "signal": overall_signal,
                "confidence": confidence,
                "reasoning": reasoning
            }),
        );
    }

    // Insert into state.data["analyst_signals"][agent_id]
    let analyst_signals = state
        .data
        .entry("analyst_signals".to_string())
        .or_insert_with(|| serde_json::json!({}));

    if let Some(obj) = analyst_signals.as_object_mut() {
        obj.insert(
            agent_id.to_string(),
            serde_json::Value::Object(fundamental_analysis),
        );
    }

    Ok(())
}
