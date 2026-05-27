// Source: src/agents/ben_graham.py
//! Sibling to src/agents/ben_graham.py
//! Analyzes stocks using Benjamin Graham's classic value-investing principles and LLM reasoning.

use anyhow::{Result, Context};
use crate::graph::state::AgentState;
use crate::tools::api::{get_financial_metrics, get_market_cap, search_line_items};
use crate::data::models::{FinancialMetrics, LineItem};
use crate::utils::llm::call_llm;

#[derive(Debug, serde::Serialize, serde::Deserialize, Default)]
pub struct BenGrahamSignal {
    pub signal: String,      // "bullish" | "bearish" | "neutral"
    pub confidence: u32,     // 0-100
    pub reasoning: String,
}

pub async fn ben_graham_agent(state: &mut AgentState, agent_id: &str) -> Result<()> {
    println!("Running Ben Graham Agent: {}", agent_id);

    let start_date = state.data.get("start_date")
        .and_then(|v| v.as_str())
        .context("Missing start_date in ben_graham_agent")?;
    
    let end_date = state.data.get("end_date")
        .and_then(|v| v.as_str())
        .context("Missing end_date in ben_graham_agent")?;
    
    let tickers_json = state.data.get("tickers")
        .context("Missing tickers in ben_graham_agent")?;
    let tickers: Vec<String> = serde_json::from_value(tickers_json.clone())?;

    let api_key = state.metadata.get("FINANCIAL_DATASETS_API_KEY")
        .and_then(|v| v.as_str());

    let mut graham_analysis = serde_json::Map::new();

    for ticker in &tickers {
        // Fetch historical data
        let metrics = get_financial_metrics(ticker, end_date, "annual", 10, api_key).await.unwrap_or_default();
        let financial_line_items = search_line_items(
            ticker,
            vec![
                "earnings_per_share".to_string(),
                "revenue".to_string(),
                "net_income".to_string(),
                "book_value_per_share".to_string(),
                "total_assets".to_string(),
                "total_liabilities".to_string(),
                "current_assets".to_string(),
                "current_liabilities".to_string(),
                "dividends_and_other_cash_distributions".to_string(),
                "outstanding_shares".to_string(),
            ],
            end_date,
            "annual",
            10,
            api_key,
        ).await.unwrap_or_default();

        let market_cap = get_market_cap(ticker, end_date, api_key).await.unwrap_or(None).unwrap_or(0.0);

        // Perform sub-analyses
        let earnings = analyze_earnings_stability(&metrics, &financial_line_items);
        let strength = analyze_financial_strength(&financial_line_items);
        let valuation = analyze_valuation_graham(&financial_line_items, market_cap);

        // Aggregate scoring
        let total_score = earnings.score + strength.score + valuation.score;
        let max_possible_score = 15;

        let facts = serde_json::json!({
            "score": total_score,
            "max_score": max_possible_score,
            "earnings_stability": {
                "score": earnings.score,
                "details": earnings.details,
            },
            "financial_strength": {
                "score": strength.score,
                "details": strength.details,
            },
            "graham_valuation": {
                "score": valuation.score,
                "details": valuation.details,
            },
            "market_cap": market_cap,
        });

        let output = generate_graham_output(ticker, &facts, state, agent_id).await?;

        graham_analysis.insert(
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
        obj.insert(agent_id.to_string(), serde_json::Value::Object(graham_analysis));
    }

    Ok(())
}

pub struct GrahamSubResult {
    pub score: u32,
    pub details: String,
}

pub fn analyze_earnings_stability(_metrics: &[FinancialMetrics], financial_line_items: &[LineItem]) -> GrahamSubResult {
    let mut score = 0;
    let mut details = Vec::new();

    if financial_line_items.is_empty() {
        return GrahamSubResult { score: 0, details: "Insufficient data for earnings stability analysis".to_string() };
    }

    let eps_vals: Vec<f64> = financial_line_items.iter().filter_map(|item| item.earnings_per_share).collect();

    if eps_vals.len() < 2 {
        details.push("Not enough multi-year EPS data.".to_string());
        return GrahamSubResult { score: 0, details: details.join("; ") };
    }

    // 1. Consistently positive EPS
    let positive_eps_years = eps_vals.iter().filter(|&&e| e > 0.0).count();
    let total_eps_years = eps_vals.len();
    if positive_eps_years == total_eps_years {
        score += 3;
        details.push("EPS was positive in all available periods.".to_string());
    } else if positive_eps_years as f64 >= (total_eps_years as f64 * 0.8) {
        score += 2;
        details.push("EPS was positive in most periods.".to_string());
    } else {
        details.push("EPS was negative in multiple periods.".to_string());
    }

    // 2. EPS growth from earliest to latest (earliest is at the end of the list)
    let latest_eps = eps_vals.first().copied().unwrap_or(0.0);
    let earliest_eps = eps_vals.last().copied().unwrap_or(0.0);
    if latest_eps > earliest_eps {
        score += 1;
        details.push("EPS grew from earliest to latest period.".to_string());
    } else {
        details.push("EPS did not grow from earliest to latest period.".to_string());
    }

    GrahamSubResult { score, details: details.join("; ") }
}

pub fn analyze_financial_strength(financial_line_items: &[LineItem]) -> GrahamSubResult {
    let mut score = 0;
    let mut details = Vec::new();

    if financial_line_items.is_empty() {
        return GrahamSubResult { score: 0, details: "No data for financial strength analysis".to_string() };
    }

    let latest_item = &financial_line_items[0];
    let total_assets = latest_item.total_assets.unwrap_or(0.0);
    let total_liabilities = latest_item.total_liabilities.unwrap_or(0.0);
    let current_assets = latest_item.current_assets.unwrap_or(0.0);
    let current_liabilities = latest_item.current_liabilities.unwrap_or(0.0);

    // 1. Current ratio
    if current_liabilities > 0.0 {
        let current_ratio = current_assets / current_liabilities;
        if current_ratio >= 2.0 {
            score += 2;
            details.push(format!("Current ratio = {:.2} (>=2.0: solid)", current_ratio));
        } else if current_ratio >= 1.5 {
            score += 1;
            details.push(format!("Current ratio = {:.2} (moderately strong)", current_ratio));
        } else {
            details.push(format!("Current ratio = {:.2} (<1.5: weaker liquidity)", current_ratio));
        }
    } else {
        details.push("Cannot compute current ratio (missing or zero current_liabilities).".to_string());
    }

    // 2. Debt vs. Assets
    if total_assets > 0.0 {
        let debt_ratio = total_liabilities / total_assets;
        if debt_ratio < 0.5 {
            score += 2;
            details.push(format!("Debt ratio = {:.2}, under 0.50 (conservative)", debt_ratio));
        } else if debt_ratio < 0.8 {
            score += 1;
            details.push(format!("Debt ratio = {:.2}, somewhat high but could be acceptable", debt_ratio));
        } else {
            details.push(format!("Debt ratio = {:.2}, quite high by Graham standards", debt_ratio));
        }
    } else {
        details.push("Cannot compute debt ratio (missing total_assets).".to_string());
    }

    // 3. Dividend track record
    let div_periods: Vec<f64> = financial_line_items.iter().filter_map(|item| item.dividends_and_other_cash_distributions).collect();
    if !div_periods.is_empty() {
        let div_paid_years = div_periods.iter().filter(|&&d| d < 0.0).count();
        if div_paid_years > 0 {
            if div_paid_years >= (div_periods.len() / 2 + 1) {
                score += 1;
                details.push("Company paid dividends in the majority of the reported years.".to_string());
            } else {
                details.push("Company has some dividend payments, but not most years.".to_string());
            }
        } else {
            details.push("Company did not pay dividends in these periods.".to_string());
        }
    } else {
        details.push("No dividend data available to assess payout consistency.".to_string());
    }

    GrahamSubResult { score, details: details.join("; ") }
}

pub fn analyze_valuation_graham(financial_line_items: &[LineItem], market_cap: f64) -> GrahamSubResult {
    if financial_line_items.is_empty() || market_cap <= 0.0 {
        return GrahamSubResult { score: 0, details: "Insufficient data to perform valuation".to_string() };
    }

    let latest = &financial_line_items[0];
    let current_assets = latest.current_assets.unwrap_or(0.0);
    let total_liabilities = latest.total_liabilities.unwrap_or(0.0);
    let book_value_ps = latest.book_value_per_share.unwrap_or(0.0);
    let eps = latest.earnings_per_share.unwrap_or(0.0);
    let shares_outstanding = latest.outstanding_shares.unwrap_or(0) as f64;

    let mut details = Vec::new();
    let mut score = 0;

    // 1. Net-Net Check
    let net_current_asset_value = current_assets - total_liabilities;
    if net_current_asset_value > 0.0 && shares_outstanding > 0.0 {
        let net_current_asset_value_per_share = net_current_asset_value / shares_outstanding;
        let price_per_share = market_cap / shares_outstanding;

        details.push(format!("Net Current Asset Value = {:.2}", net_current_asset_value));
        details.push(format!("NCAV Per Share = {:.2}", net_current_asset_value_per_share));
        details.push(format!("Price Per Share = {:.2}", price_per_share));

        if net_current_asset_value > market_cap {
            score += 4;
            details.push("Net-Net: NCAV > Market Cap (classic Graham deep value).".to_string());
        } else if net_current_asset_value_per_share >= (price_per_share * 0.67) {
            score += 2;
            details.push("NCAV Per Share >= 2/3 of Price Per Share (moderate net-net discount).".to_string());
        }
    } else {
        details.push("NCAV not exceeding market cap or insufficient data for net-net approach.".to_string());
    }

    // 2. Graham Number
    let mut graham_number: Option<f64> = None;
    if eps > 0.0 && book_value_ps > 0.0 {
        let gn = (22.5 * eps * book_value_ps).sqrt();
        graham_number = Some(gn);
        details.push(format!("Graham Number = {:.2}", gn));
    } else {
        details.push("Unable to compute Graham Number (EPS or Book Value missing/<=0).".to_string());
    }

    // 3. Margin of Safety
    if let Some(gn) = graham_number {
        if shares_outstanding > 0.0 {
            let current_price = market_cap / shares_outstanding;
            if current_price > 0.0 {
                let margin_of_safety = (gn - current_price) / current_price;
                details.push(format!("Margin of Safety (Graham Number) = {:.2}%", margin_of_safety * 100.0));
                if margin_of_safety > 0.5 {
                    score += 3;
                    details.push("Price is well below Graham Number (>=50% margin).".to_string());
                } else if margin_of_safety > 0.2 {
                    score += 1;
                    details.push("Some margin of safety relative to Graham Number.".to_string());
                } else {
                    details.push("Price close to or above Graham Number, low margin of safety.".to_string());
                }
            }
        }
    }

    GrahamSubResult { score, details: details.join("; ") }
}

pub async fn generate_graham_output(
    ticker: &str,
    facts: &serde_json::Value,
    state: &AgentState,
    agent_id: &str,
) -> Result<BenGrahamSignal> {
    let system_prompt = "You are a Benjamin Graham AI agent making investment decisions using his principles:\n\
        1. Insist on a margin of safety by buying below intrinsic value (e.g. Graham Number, net-net).\n\
        2. Emphasize financial strength (current ratio >= 2.0, low leverage).\n\
        3. Prefer stable multi-year positive earnings.\n\
        4. Value consistency and dividend records.\n\
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
