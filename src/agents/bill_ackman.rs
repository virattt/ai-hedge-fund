// Source: src/agents/bill_ackman.py
//! Sibling to src/agents/bill_ackman.py
//! Analyzes stocks using Bill Ackman's activist value investing principles.

use anyhow::{Result, Context};
use crate::graph::state::AgentState;
use crate::tools::api::{get_financial_metrics, get_market_cap, search_line_items};
use crate::data::models::{FinancialMetrics, LineItem};
use crate::utils::llm::call_llm;

#[derive(Debug, serde::Serialize, serde::Deserialize, Default)]
pub struct BillAckmanSignal {
    pub signal: String,      // "bullish" | "bearish" | "neutral"
    pub confidence: u32,     // 0-100
    pub reasoning: String,
}

pub async fn bill_ackman_agent(state: &mut AgentState, agent_id: &str) -> Result<()> {
    println!("Running Bill Ackman Agent: {}", agent_id);

    let start_date = state.data.get("start_date")
        .and_then(|v| v.as_str())
        .context("Missing start_date in bill_ackman_agent")?;
    
    let end_date = state.data.get("end_date")
        .and_then(|v| v.as_str())
        .context("Missing end_date in bill_ackman_agent")?;
    
    let tickers_json = state.data.get("tickers")
        .context("Missing tickers in bill_ackman_agent")?;
    let tickers: Vec<String> = serde_json::from_value(tickers_json.clone())?;

    let api_key = state.metadata.get("FINANCIAL_DATASETS_API_KEY")
        .and_then(|v| v.as_str());

    let mut ackman_analysis = serde_json::Map::new();

    for ticker in &tickers {
        // Fetch raw data
        let metrics = get_financial_metrics(ticker, end_date, "annual", 5, api_key).await.unwrap_or_default();
        let financial_line_items = search_line_items(
            ticker,
            vec![
                "revenue".to_string(),
                "operating_margin".to_string(),
                "debt_to_equity".to_string(),
                "free_cash_flow".to_string(),
                "total_assets".to_string(),
                "total_liabilities".to_string(),
                "dividends_and_other_cash_distributions".to_string(),
                "outstanding_shares".to_string(),
            ],
            end_date,
            "annual",
            5,
            api_key,
        ).await.unwrap_or_default();

        let market_cap = get_market_cap(ticker, end_date, api_key).await.unwrap_or(None).unwrap_or(0.0);

        // Perform sub-analyses
        let quality = analyze_business_quality(&metrics, &financial_line_items);
        let discipline = analyze_financial_discipline(&metrics, &financial_line_items);
        let activism = analyze_activism_potential(&financial_line_items);
        let valuation = analyze_valuation(&financial_line_items, market_cap);

        let total_score = quality.score + discipline.score + activism.score + valuation.score;
        let max_possible_score = 20.0;

        let signal = if total_score as f64 >= 0.7 * max_possible_score {
            "bullish"
        } else if total_score as f64 <= 0.3 * max_possible_score {
            "bearish"
        } else {
            "neutral"
        };

        let facts = serde_json::json!({
            "signal": signal,
            "score": total_score,
            "max_score": max_possible_score,
            "quality_analysis": {
                "score": quality.score,
                "details": quality.details,
            },
            "balance_sheet_analysis": {
                "score": discipline.score,
                "details": discipline.details,
            },
            "activism_analysis": {
                "score": activism.score,
                "details": activism.details,
            },
            "valuation_analysis": {
                "score": valuation.score,
                "details": valuation.details,
                "intrinsic_value": valuation.intrinsic_value,
                "margin_of_safety": valuation.margin_of_safety,
            },
            "market_cap": market_cap,
        });

        let output = generate_ackman_output(ticker, &facts, state, agent_id).await?;

        ackman_analysis.insert(
            ticker.clone(),
            serde_json::json!({
                "signal": output.signal,
                "confidence": output.confidence,
                "reasoning": output.reasoning,
            }),
        );
    }

    let analyst_signals = state.data.entry("analyst_signals".to_string())
        .or_insert_with(|| serde_json::json!({}));
    if let Some(obj) = analyst_signals.as_object_mut() {
        obj.insert(agent_id.to_string(), serde_json::Value::Object(ackman_analysis));
    }

    Ok(())
}

pub struct AckmanSubResult {
    pub score: u32,
    pub details: String,
}

pub fn analyze_business_quality(metrics: &[FinancialMetrics], financial_line_items: &[LineItem]) -> AckmanSubResult {
    let mut score = 0;
    let mut details = Vec::new();

    if metrics.is_empty() || financial_line_items.is_empty() {
        return AckmanSubResult { score: 0, details: "Insufficient data to analyze business quality".to_string() };
    }

    // 1. Revenue growth (reverse chronological: newest first)
    let revenues: Vec<f64> = financial_line_items.iter().filter_map(|item| item.revenue).collect();
    if revenues.len() >= 2 {
        let initial = revenues[revenues.len() - 1];
        let final_val = revenues[0];
        if initial > 0.0 && final_val > initial {
            let growth_rate = (final_val - initial) / initial;
            if growth_rate > 0.5 {
                score += 2;
                details.push(format!("Revenue grew by {:.1}% over the full period (strong growth).", growth_rate * 100.0));
            } else {
                score += 1;
                details.push(format!("Revenue growth is positive but under 50% cumulatively ({:.1}%).", growth_rate * 100.0));
            }
        } else {
            details.push("Revenue did not grow significantly or data insufficient.".to_string());
        }
    } else {
        details.push("Not enough revenue data for trend analysis.".to_string());
    }

    // 2. Margin and FCF consistency
    let op_margin_vals: Vec<f64> = financial_line_items.iter().filter_map(|item| item.operating_margin).collect();
    let fcf_vals: Vec<f64> = financial_line_items.iter().filter_map(|item| item.free_cash_flow).collect();

    if !op_margin_vals.is_empty() {
        let above_15 = op_margin_vals.iter().filter(|&&m| m > 0.15).count();
        if above_15 >= (op_margin_vals.len() / 2 + 1) {
            score += 2;
            details.push("Operating margins have often exceeded 15%.".to_string());
        } else {
            details.push("Operating margin not consistently above 15%.".to_string());
        }
    }

    if !fcf_vals.is_empty() {
        let positive_fcf_count = fcf_vals.iter().filter(|&&f| f > 0.0).count();
        if positive_fcf_count >= (fcf_vals.len() / 2 + 1) {
            score += 1;
            details.push("Majority of periods show positive free cash flow.".to_string());
        } else {
            details.push("Free cash flow not consistently positive.".to_string());
        }
    }

    // 3. Return on Equity
    if let Some(roe) = metrics[0].return_on_equity {
        if roe > 0.15 {
            score += 2;
            details.push(format!("High ROE of {:.1}%, indicating a competitive advantage.", roe * 100.0));
        } else {
            details.push(format!("ROE of {:.1}% is moderate.", roe * 100.0));
        }
    }

    AckmanSubResult { score, details: details.join("; ") }
}

pub fn analyze_financial_discipline(metrics: &[FinancialMetrics], financial_line_items: &[LineItem]) -> AckmanSubResult {
    let mut score = 0;
    let mut details = Vec::new();

    if metrics.is_empty() || financial_line_items.is_empty() {
        return AckmanSubResult { score: 0, details: "Insufficient data to analyze financial discipline".to_string() };
    }

    // 1. Debt to equity trends
    let debt_to_equity_vals: Vec<f64> = financial_line_items.iter().filter_map(|item| item.debt_to_equity).collect();
    if !debt_to_equity_vals.is_empty() {
        let below_one_count = debt_to_equity_vals.iter().filter(|&&d| d < 1.0).count();
        if below_one_count >= (debt_to_equity_vals.len() / 2 + 1) {
            score += 2;
            details.push("Debt-to-equity < 1.0 for the majority of periods.".to_string());
        } else {
            details.push("Debt-to-equity >= 1.0 in many periods.".to_string());
        }
    } else {
        // Fallback to total liabilities / assets
        let mut liab_to_assets = Vec::new();
        for item in financial_line_items {
            if let (Some(l), Some(a)) = (item.total_liabilities, item.total_assets) {
                if a > 0.0 {
                    liab_to_assets.push(l / a);
                }
            }
        }
        if !liab_to_assets.is_empty() {
            let below_50pct = liab_to_assets.iter().filter(|&&r| r < 0.5).count();
            if below_50pct >= (liab_to_assets.len() / 2 + 1) {
                score += 2;
                details.push("Liabilities-to-assets < 50% for majority of periods.".to_string());
            } else {
                details.push("Liabilities-to-assets >= 50% in many periods.".to_string());
            }
        }
    }

    // 2. Dividends history
    let dividends_list: Vec<f64> = financial_line_items.iter().filter_map(|item| item.dividends_and_other_cash_distributions).collect();
    if !dividends_list.is_empty() {
        let paying_dividends_count = dividends_list.iter().filter(|&&d| d < 0.0).count();
        if paying_dividends_count >= (dividends_list.len() / 2 + 1) {
            score += 1;
            details.push("Company paid dividends consistently.".to_string());
        }
    }

    // 3. Buybacks trend
    let shares: Vec<f64> = financial_line_items.iter().filter_map(|item| item.outstanding_shares.map(|s| s as f64)).collect();
    if shares.len() >= 2 {
        if shares[0] < shares[shares.len() - 1] {
            score += 1;
            details.push("Outstanding shares decreased over time (buybacks).".to_string());
        }
    }

    AckmanSubResult { score, details: details.join("; ") }
}

pub fn analyze_activism_potential(financial_line_items: &[LineItem]) -> AckmanSubResult {
    let mut score = 0;
    let mut details = Vec::new();

    if financial_line_items.is_empty() {
        return AckmanSubResult { score: 0, details: "Insufficient data for activism potential".to_string() };
    }

    let revenues: Vec<f64> = financial_line_items.iter().filter_map(|item| item.revenue).collect();
    let op_margins: Vec<f64> = financial_line_items.iter().filter_map(|item| item.operating_margin).collect();

    if revenues.len() < 2 || op_margins.is_empty() {
        return AckmanSubResult { score: 0, details: "Not enough data to assess activism potential.".to_string() };
    }

    let initial = revenues[revenues.len() - 1];
    let final_val = revenues[0];
    let revenue_growth = if initial > 0.0 { (final_val - initial) / initial } else { 0.0 };
    let avg_margin = op_margins.iter().sum::<f64>() / op_margins.len() as f64;

    if revenue_growth > 0.15 && avg_margin < 0.10 {
        score += 2;
        details.push(format!("Revenue growth is healthy (~{:.1}%), but margins are low (avg {:.1}%). Activism could unlock improvements.", revenue_growth * 100.0, avg_margin * 100.0));
    } else {
        details.push("No clear sign of activism opportunity.".to_string());
    }

    AckmanSubResult { score, details: details.join("; ") }
}

pub struct AckmanValResult {
    pub score: u32,
    pub details: String,
    pub intrinsic_value: Option<f64>,
    pub margin_of_safety: Option<f64>,
}

pub fn analyze_valuation(financial_line_items: &[LineItem], market_cap: f64) -> AckmanValResult {
    if financial_line_items.is_empty() || market_cap <= 0.0 {
        return AckmanValResult { score: 0, details: "Insufficient data to perform valuation".to_string(), intrinsic_value: None, margin_of_safety: None };
    }

    let latest = &financial_line_items[0];
    let fcf = latest.free_cash_flow.unwrap_or(0.0);

    if fcf <= 0.0 {
        return AckmanValResult { score: 0, details: format!("No positive FCF for valuation; FCF = {:.2}", fcf), intrinsic_value: None, margin_of_safety: None };
    }

    let growth_rate = 0.06_f64;
    let discount_rate = 0.10_f64;
    let terminal_multiple = 15.0_f64;
    let projection_years: i32 = 5;

    let mut present_value = 0.0_f64;
    for year in 1..=projection_years {
        let future_fcf = fcf * (1.0_f64 + growth_rate).powi(year);
        let pv = future_fcf / (1.0_f64 + discount_rate).powi(year);
        present_value += pv;
    }

    let terminal_value = (fcf * (1.0_f64 + growth_rate).powi(projection_years) * terminal_multiple) / (1.0_f64 + discount_rate).powi(projection_years);
    let intrinsic_value = present_value + terminal_value;
    let margin_of_safety = (intrinsic_value - market_cap) / market_cap;

    let mut score = 0;
    if margin_of_safety > 0.3 {
        score += 3;
    } else if margin_of_safety > 0.1 {
        score += 1;
    }

    let details = vec![
        format!("Calculated intrinsic value: ~{:.2}", intrinsic_value),
        format!("Market cap: ~{:.2}", market_cap),
        format!("Margin of safety: {:.2}%", margin_of_safety * 100.0),
    ];

    AckmanValResult {
        score,
        details: details.join("; "),
        intrinsic_value: Some(intrinsic_value),
        margin_of_safety: Some(margin_of_safety),
    }
}

pub async fn generate_ackman_output(
    ticker: &str,
    facts: &serde_json::Value,
    state: &AgentState,
    agent_id: &str,
) -> Result<BillAckmanSignal> {
    let system_prompt = "You are a Bill Ackman AI agent, making investment decisions using his principles:\n\
        1. Seek high-quality businesses with durable competitive advantages (moats), well-known consumer/service brands.\n\
        2. Prioritize consistent free cash flow and growth.\n\
        3. Advocate for strong financial discipline (reasonable leverage, buybacks).\n\
        4. Valuation: buy at a discount to intrinsic value.\n\
        5. Consider activism where operational improvements unlock upside.\n\
        Return JSON matching exactly: {\"signal\": \"bullish\" | \"bearish\" | \"neutral\", \"confidence\": int, \"reasoning\": \"short\"}";

    let user_prompt = format!(
        "Ticker: {}\nFacts:\n{}\n\nReturn structured JSON output.",
        ticker,
        serde_json::to_string_pretty(facts)?
    );

    call_llm(
        system_prompt,
        &user_prompt,
        Some(agent_id),
        Some(state),
        3,
    ).await
}
