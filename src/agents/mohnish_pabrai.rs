// Source: src/agents/mohnish_pabrai.py
//! Sibling to src/agents/mohnish_pabrai.py
//! Analyzes stocks using Mohnish Pabrai's Dhandho investment principles.

use crate::data::models::LineItem;
use crate::graph::state::AgentState;
use crate::tools::api::{get_financial_metrics, get_market_cap, search_line_items};
use crate::utils::llm::call_llm;
use anyhow::{Context, Result};

#[derive(Debug, serde::Serialize, serde::Deserialize, Default)]
pub struct MohnishPabraiSignal {
    pub signal: String,  // "bullish" | "bearish" | "neutral"
    pub confidence: u32, // 0-100
    pub reasoning: String,
}

pub async fn mohnish_pabrai_agent(state: &mut AgentState, agent_id: &str) -> Result<()> {
    println!("Running Mohnish Pabrai Agent: {}", agent_id);

    let _start_date = state
        .data
        .get("start_date")
        .and_then(|v| v.as_str())
        .context("Missing start_date in mohnish_pabrai_agent")?;

    let end_date = state
        .data
        .get("end_date")
        .and_then(|v| v.as_str())
        .context("Missing end_date in mohnish_pabrai_agent")?;

    let tickers_json = state
        .data
        .get("tickers")
        .context("Missing tickers in mohnish_pabrai_agent")?;
    let tickers: Vec<String> = serde_json::from_value(tickers_json.clone())?;

    let api_key = state
        .metadata
        .get("FINANCIAL_DATASETS_API_KEY")
        .and_then(|v| v.as_str());

    let mut pabrai_analysis = serde_json::Map::new();

    for ticker in &tickers {
        // Fetch raw data
        let _metrics = get_financial_metrics(ticker, end_date, "annual", 8, api_key)
            .await
            .unwrap_or_default();
        let line_items = search_line_items(
            ticker,
            vec![
                "revenue".to_string(),
                "gross_profit".to_string(),
                "gross_margin".to_string(),
                "operating_income".to_string(),
                "operating_margin".to_string(),
                "net_income".to_string(),
                "free_cash_flow".to_string(),
                "total_debt".to_string(),
                "cash_and_equivalents".to_string(),
                "current_assets".to_string(),
                "current_liabilities".to_string(),
                "shareholders_equity".to_string(),
                "capital_expenditure".to_string(),
                "depreciation_and_amortization".to_string(),
                "outstanding_shares".to_string(),
            ],
            end_date,
            "annual",
            8,
            api_key,
        )
        .await
        .unwrap_or_default();

        let market_cap = get_market_cap(ticker, end_date, api_key)
            .await
            .unwrap_or(None)
            .unwrap_or(0.0);

        // Sub-analyses
        let downside = analyze_downside_protection(&line_items);
        let valuation = analyze_pabrai_valuation(&line_items, market_cap);
        let double_potential = analyze_double_potential(&line_items, market_cap);

        let total_score = downside.score as f64 * 0.45
            + valuation.score as f64 * 0.35
            + double_potential.score as f64 * 0.20;

        let max_score = 10.0;

        let signal = if total_score >= 7.5 {
            "bullish"
        } else if total_score <= 4.0 {
            "bearish"
        } else {
            "neutral"
        };

        let facts = serde_json::json!({
            "signal": signal,
            "score": (total_score * 100.0).round() / 100.0,
            "max_score": max_score,
            "downside_protection": {
                "score": downside.score,
                "details": downside.details,
            },
            "valuation": {
                "score": valuation.score,
                "details": valuation.details,
                "fcf_yield": valuation.fcf_yield,
                "normalized_fcf": valuation.normalized_fcf,
            },
            "double_potential": {
                "score": double_potential.score,
                "details": double_potential.details,
            },
            "market_cap": market_cap,
        });

        let output = generate_pabrai_output(ticker, &facts, state, agent_id).await?;

        pabrai_analysis.insert(
            ticker.clone(),
            serde_json::json!({
                "signal": output.signal,
                "confidence": output.confidence,
                "reasoning": output.reasoning,
            }),
        );
    }

    let analyst_signals = state
        .data
        .entry("analyst_signals".to_string())
        .or_insert_with(|| serde_json::json!({}));
    if let Some(obj) = analyst_signals.as_object_mut() {
        obj.insert(
            agent_id.to_string(),
            serde_json::Value::Object(pabrai_analysis),
        );
    }

    Ok(())
}

pub struct PabraiSubResult {
    pub score: u32,
    pub details: String,
}

pub fn analyze_downside_protection(financial_line_items: &[LineItem]) -> PabraiSubResult {
    let mut score = 0;
    let mut details = Vec::new();

    if financial_line_items.is_empty() {
        return PabraiSubResult {
            score: 0,
            details: "Insufficient data".to_string(),
        };
    }

    let latest = &financial_line_items[0];
    let cash = latest.cash_and_equivalents.unwrap_or(0.0);
    let debt = latest.total_debt.unwrap_or(0.0);
    let current_assets = latest.current_assets.unwrap_or(0.0);
    let current_liabilities = latest.current_liabilities.unwrap_or(0.0);
    let equity = latest.shareholders_equity.unwrap_or(0.0);

    // 1. Net Cash
    let net_cash = cash - debt;
    if net_cash > 0.0 {
        score += 3;
        details.push(format!("Net cash position: ${:.0}", net_cash));
    } else {
        details.push(format!("Net debt position: ${:.0}", net_cash));
    }

    // 2. Current ratio
    if current_liabilities > 0.0 {
        let current_ratio = current_assets / current_liabilities;
        if current_ratio >= 2.0 {
            score += 2;
            details.push(format!(
                "Strong liquidity (current ratio {:.2})",
                current_ratio
            ));
        } else if current_ratio >= 1.2 {
            score += 1;
            details.push(format!(
                "Adequate liquidity (current ratio {:.2})",
                current_ratio
            ));
        } else {
            details.push(format!(
                "Weak liquidity (current ratio {:.2})",
                current_ratio
            ));
        }
    }

    // 3. Leverage
    if equity > 0.0 {
        let de_ratio = debt / equity;
        if de_ratio < 0.3 {
            score += 2;
            details.push(format!("Very low leverage (D/E {:.2})", de_ratio));
        } else if de_ratio < 0.7 {
            score += 1;
            details.push(format!("Moderate leverage (D/E {:.2})", de_ratio));
        } else {
            details.push(format!("High leverage (D/E {:.2})", de_ratio));
        }
    }

    // 4. Stable/improving FCF
    let fcf_values: Vec<f64> = financial_line_items
        .iter()
        .filter_map(|li| li.free_cash_flow)
        .collect();
    if fcf_values.len() >= 3 {
        let recent_avg: f64 = fcf_values[..3].iter().sum::<f64>() / 3.0;
        let older = if fcf_values.len() >= 6 {
            fcf_values[fcf_values.len() - 3..].iter().sum::<f64>() / 3.0
        } else {
            fcf_values[fcf_values.len() - 1]
        };

        if recent_avg > 0.0 && recent_avg >= older {
            score += 2;
            details.push("Positive and improving/stable FCF".to_string());
        } else if recent_avg > 0.0 {
            score += 1;
            details.push("Positive but declining FCF".to_string());
        } else {
            details.push("Negative FCF".to_string());
        }
    }

    PabraiSubResult {
        score: score.min(10),
        details: details.join("; "),
    }
}

pub struct PabraiValResult {
    pub score: u32,
    pub details: String,
    pub fcf_yield: Option<f64>,
    pub normalized_fcf: Option<f64>,
}

pub fn analyze_pabrai_valuation(
    financial_line_items: &[LineItem],
    market_cap: f64,
) -> PabraiValResult {
    if financial_line_items.is_empty() || market_cap <= 0.0 {
        return PabraiValResult {
            score: 0,
            details: "Insufficient data".to_string(),
            fcf_yield: None,
            normalized_fcf: None,
        };
    }

    let mut details = Vec::new();
    let fcf_values: Vec<f64> = financial_line_items
        .iter()
        .filter_map(|li| li.free_cash_flow)
        .collect();

    if fcf_values.len() < 3 {
        return PabraiValResult {
            score: 0,
            details: "Insufficient FCF history".to_string(),
            fcf_yield: None,
            normalized_fcf: None,
        };
    }

    let periods = 5.min(fcf_values.len());
    let normalized_fcf: f64 = fcf_values[..periods].iter().sum::<f64>() / periods as f64;
    if normalized_fcf <= 0.0 {
        return PabraiValResult {
            score: 0,
            details: "Non-positive normalized FCF".to_string(),
            fcf_yield: None,
            normalized_fcf: Some(normalized_fcf),
        };
    }

    let fcf_yield = normalized_fcf / market_cap;
    let mut score = 0;

    if fcf_yield > 0.10 {
        score += 4;
        details.push(format!(
            "Exceptional value: {:.1}% FCF yield",
            fcf_yield * 100.0
        ));
    } else if fcf_yield > 0.07 {
        score += 3;
        details.push(format!(
            "Attractive value: {:.1}% FCF yield",
            fcf_yield * 100.0
        ));
    } else if fcf_yield > 0.05 {
        score += 2;
        details.push(format!(
            "Reasonable value: {:.1}% FCF yield",
            fcf_yield * 100.0
        ));
    } else if fcf_yield > 0.03 {
        score += 1;
        details.push(format!(
            "Borderline value: {:.1}% FCF yield",
            fcf_yield * 100.0
        ));
    } else {
        details.push(format!("Expensive: {:.1}% FCF yield", fcf_yield * 100.0));
    }

    // Asset-light tilt (Avg capex < 5% of revenue (+2) or < 10% (+1))
    let mut capex_to_revenue = Vec::new();
    for item in financial_line_items {
        if let (Some(rev), Some(capex)) = (item.revenue, item.capital_expenditure) {
            if rev > 0.0 {
                capex_to_revenue.push(capex.abs() / rev);
            }
        }
    }
    if !capex_to_revenue.is_empty() {
        let avg_ratio: f64 = capex_to_revenue.iter().sum::<f64>() / capex_to_revenue.len() as f64;
        if avg_ratio < 0.05 {
            score += 2;
            details.push(format!(
                "Asset-light: Avg capex {:.1}% of revenue",
                avg_ratio * 100.0
            ));
        } else if avg_ratio < 0.10 {
            score += 1;
            details.push(format!(
                "Moderate capex: Avg capex {:.1}% of revenue",
                avg_ratio * 100.0
            ));
        } else {
            details.push(format!(
                "Capex heavy: Avg capex {:.1}% of revenue",
                avg_ratio * 100.0
            ));
        }
    }

    PabraiValResult {
        score: score.min(10),
        details: details.join("; "),
        fcf_yield: Some(fcf_yield),
        normalized_fcf: Some(normalized_fcf),
    }
}

pub fn analyze_double_potential(
    financial_line_items: &[LineItem],
    market_cap: f64,
) -> PabraiSubResult {
    let mut score = 0;
    let mut details = Vec::new();

    if financial_line_items.is_empty() || market_cap <= 0.0 {
        return PabraiSubResult {
            score: 0,
            details: "Insufficient data".to_string(),
        };
    }

    let revenues: Vec<f64> = financial_line_items
        .iter()
        .filter_map(|li| li.revenue)
        .collect();
    let fcfs: Vec<f64> = financial_line_items
        .iter()
        .filter_map(|li| li.free_cash_flow)
        .collect();

    // 1. Revenue CAGR/Growth proxy
    if revenues.len() >= 3 {
        let recent_rev: f64 = revenues[..3].iter().sum::<f64>() / 3.0;
        let older_rev = if revenues.len() >= 6 {
            revenues[revenues.len() - 3..].iter().sum::<f64>() / 3.0
        } else {
            revenues[revenues.len() - 1]
        };
        if older_rev > 0.0 {
            let rev_growth = (recent_rev / older_rev) - 1.0;
            if rev_growth > 0.15 {
                score += 2;
                details.push(format!(
                    "Strong revenue trajectory ({:.1}%)",
                    rev_growth * 100.0
                ));
            } else if rev_growth > 0.05 {
                score += 1;
                details.push(format!(
                    "Modest revenue growth ({:.1}%)",
                    rev_growth * 100.0
                ));
            }
        }
    }

    // 2. FCF growth proxy
    if fcfs.len() >= 3 {
        let recent_fcf: f64 = fcfs[..3].iter().sum::<f64>() / 3.0;
        let older_fcf = if fcfs.len() >= 6 {
            fcfs[fcfs.len() - 3..].iter().sum::<f64>() / 3.0
        } else {
            fcfs[fcfs.len() - 1]
        };
        if older_fcf != 0.0 {
            let fcf_growth = (recent_fcf / older_fcf) - 1.0;
            if fcf_growth > 0.20 {
                score += 3;
                details.push(format!("Strong FCF growth ({:.1}%)", fcf_growth * 100.0));
            } else if fcf_growth > 0.08 {
                score += 2;
                details.push(format!("Healthy FCF growth ({:.1}%)", fcf_growth * 100.0));
            } else if fcf_growth > 0.0 {
                score += 1;
                details.push(format!("Positive FCF growth ({:.1}%)", fcf_growth * 100.0));
            }
        }
    }

    // 3. FCF yield compounding check
    let val_tmp = analyze_pabrai_valuation(financial_line_items, market_cap);
    if let Some(fcf_yield) = val_tmp.fcf_yield {
        if fcf_yield > 0.08 {
            score += 3;
            details
                .push("High FCF yield can drive doubling via retained cash/buybacks".to_string());
        } else if fcf_yield > 0.05 {
            score += 1;
            details.push("Reasonable FCF yield supports moderate compounding".to_string());
        }
    }

    PabraiSubResult {
        score: score.min(10),
        details: details.join("; "),
    }
}

pub async fn generate_pabrai_output(
    ticker: &str,
    facts: &serde_json::Value,
    state: &AgentState,
    agent_id: &str,
) -> Result<MohnishPabraiSignal> {
    let system_prompt = "You are Mohnish Pabrai. Apply my value investing philosophy:\n\
        - Heads I win; tails I don't lose much: prioritize downside protection first.\n\
        - Buy businesses with simple, understandable models and durable moats.\n\
        - Demand high free cash flow yields and low leverage; prefer asset-light models.\n\
        - Seek potential to double capital in 2-3 years with low risk.\n\
        - Avoid leverage, complexity, and fragile balance sheets.\n\
        Return JSON matching exactly: {\"signal\": \"bullish\" | \"bearish\" | \"neutral\", \"confidence\": int, \"reasoning\": \"short\"}";

    let user_prompt = format!(
        "Ticker: {}\nFacts:\n{}\n\nReturn structured JSON output.",
        ticker,
        serde_json::to_string_pretty(facts)?
    );

    call_llm(system_prompt, &user_prompt, Some(agent_id), Some(state), 3).await
}
