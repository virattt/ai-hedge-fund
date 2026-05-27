// Source: src/agents/warren_buffett.py
//! Sibling to src/agents/warren_buffett.py
//! Analyzes stocks using Warren Buffett's investment principles and LLM reasoning.

use anyhow::{Result, Context};
use crate::graph::state::AgentState;
use crate::tools::api::{get_financial_metrics, get_market_cap, search_line_items};
use crate::data::models::{FinancialMetrics, LineItem};
use crate::utils::llm::call_llm;

#[derive(Debug, serde::Serialize, serde::Deserialize, Default)]
pub struct WarrenBuffettSignal {
    pub signal: String,      // "bullish" | "bearish" | "neutral"
    pub confidence: u32,     // 0-100
    pub reasoning: String,
}

pub async fn warren_buffett_agent(state: &mut AgentState, agent_id: &str) -> Result<()> {
    println!("Running Warren Buffett Agent: {}", agent_id);

    let start_date = state.data.get("start_date")
        .and_then(|v| v.as_str())
        .context("Missing start_date in warren_buffett_agent")?;
    
    let end_date = state.data.get("end_date")
        .and_then(|v| v.as_str())
        .context("Missing end_date in warren_buffett_agent")?;
    
    let tickers_json = state.data.get("tickers")
        .context("Missing tickers in warren_buffett_agent")?;
    let tickers: Vec<String> = serde_json::from_value(tickers_json.clone())?;

    let api_key = state.metadata.get("FINANCIAL_DATASETS_API_KEY")
        .and_then(|v| v.as_str());

    let mut buffett_analysis = serde_json::Map::new();

    for ticker in &tickers {
        // Fetch historical data
        let metrics = get_financial_metrics(ticker, end_date, "ttm", 10, api_key).await.unwrap_or_default();
        let financial_line_items = search_line_items(
            ticker,
            vec![
                "capital_expenditure".to_string(),
                "depreciation_and_amortization".to_string(),
                "net_income".to_string(),
                "outstanding_shares".to_string(),
                "total_assets".to_string(),
                "total_liabilities".to_string(),
                "shareholders_equity".to_string(),
                "dividends_and_other_cash_distributions".to_string(),
                "issuance_or_purchase_of_equity_shares".to_string(),
                "gross_profit".to_string(),
                "revenue".to_string(),
                "free_cash_flow".to_string(),
            ],
            end_date,
            "ttm",
            10,
            api_key,
        ).await.unwrap_or_default();

        let market_cap = get_market_cap(ticker, end_date, api_key).await.unwrap_or(None).unwrap_or(0.0);

        // Perform Buffett fundamental analyses
        let fundamental = analyze_fundamentals(&metrics);
        let consistency = analyze_consistency(&financial_line_items);
        let moat = analyze_moat(&metrics);
        let mgmt = analyze_management_quality(&financial_line_items);
        let pricing_power = analyze_pricing_power(&financial_line_items, &metrics);
        let book_value = analyze_book_value_growth(&financial_line_items);
        let intrinsic = calculate_intrinsic_value(&financial_line_items);

        let total_score = fundamental.score + consistency.score + moat.score + mgmt.score + pricing_power.score + book_value.score;
        let max_possible_score = 10 + moat.max_score + mgmt.max_score + 5 + 5;

        let mut margin_of_safety: Option<f64> = None;
        if let Some(iv) = intrinsic.intrinsic_value {
            if market_cap > 0.0 {
                margin_of_safety = Some((iv - market_cap) / market_cap);
            }
        }

        let facts = serde_json::json!({
            "score": total_score,
            "max_score": max_possible_score,
            "fundamentals": fundamental.details,
            "consistency": consistency.details,
            "moat": moat.details,
            "pricing_power": pricing_power.details,
            "book_value": book_value.details,
            "management": mgmt.details,
            "intrinsic_value": intrinsic.intrinsic_value,
            "market_cap": market_cap,
            "margin_of_safety": margin_of_safety,
        });

        let output = generate_buffett_output(ticker, &facts, state, agent_id).await?;

        buffett_analysis.insert(
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
        obj.insert(agent_id.to_string(), serde_json::Value::Object(buffett_analysis));
    }

    Ok(())
}

pub struct FundamentalResult {
    pub score: u32,
    pub details: String,
}

pub fn analyze_fundamentals(metrics: &[FinancialMetrics]) -> FundamentalResult {
    if metrics.is_empty() {
        return FundamentalResult { score: 0, details: "Insufficient fundamental data".to_string() };
    }
    let m = &metrics[0];
    let mut score = 0;
    let mut details = Vec::new();

    if let Some(roe) = m.return_on_equity {
        if roe > 0.15 {
            score += 2;
            details.push(format!("Strong ROE of {:.1}%", roe * 100.0));
        } else {
            details.push(format!("Weak ROE of {:.1}%", roe * 100.0));
        }
    } else {
        details.push("ROE data unavailable".to_string());
    }

    if let Some(de) = m.debt_to_equity {
        if de < 0.5 {
            score += 2;
            details.push("Conservative debt levels".to_string());
        } else {
            details.push(format!("High debt ratio of {:.1}", de));
        }
    } else {
        details.push("Debt levels unavailable".to_string());
    }

    if let Some(om) = m.operating_margin {
        if om > 0.15 {
            score += 2;
            details.push("Strong operating margins".to_string());
        } else {
            details.push(format!("Weak operating margins of {:.1}%", om * 100.0));
        }
    }

    if let Some(cr) = m.current_ratio {
        if cr > 1.5 {
            score += 1;
            details.push("Good liquidity position".to_string());
        }
    }

    FundamentalResult { score, details: details.join("; ") }
}

pub struct ScoringResult {
    pub score: u32,
    pub details: String,
}

pub fn analyze_consistency(financial_line_items: &[LineItem]) -> ScoringResult {
    if financial_line_items.len() < 4 {
        return ScoringResult { score: 0, details: "Insufficient historical data".to_string() };
    }
    let mut score = 0;
    let mut details = Vec::new();

    let earnings: Vec<f64> = financial_line_items.iter().filter_map(|i| i.net_income).collect();
    if earnings.len() >= 4 {
        // Check if newest earnings are strictly greater than older periods
        let is_growing = earnings.iter().zip(earnings.iter().skip(1)).all(|(&new, &old)| new > old);
        if is_growing {
            score += 3;
            details.push("Consistent earnings growth over past periods".to_string());
        } else {
            details.push("Inconsistent earnings growth pattern".to_string());
        }

        let first = earnings.first().copied().unwrap_or(0.0);
        let last = earnings.last().copied().unwrap_or(0.0);
        if last != 0.0 {
            let total_growth = (first - last) / last.abs();
            details.push(format!("Total earnings growth of {:.1}% over past periods", total_growth * 100.0));
        }
    }

    ScoringResult { score, details: details.join("; ") }
}

pub struct MoatResult {
    pub score: u32,
    pub max_score: u32,
    pub details: String,
}

pub fn analyze_moat(metrics: &[FinancialMetrics]) -> MoatResult {
    if metrics.len() < 5 {
        return MoatResult { score: 0, max_score: 5, details: "Insufficient data for comprehensive moat analysis".to_string() };
    }
    let mut score = 0;
    let max_score = 5;
    let mut details = Vec::new();

    let roes: Vec<f64> = metrics.iter().filter_map(|m| m.return_on_equity).collect();
    if roes.len() >= 5 {
        let high_roe_count = roes.iter().filter(|&&r| r > 0.15).count();
        if high_roe_count >= 4 {
            score += 2;
            let avg_roe = roes.iter().sum::<f64>() / roes.len() as f64;
            details.push(format!("Excellent ROE consistency: {}/{} periods >15% (avg: {:.1}%)", high_roe_count, roes.len(), avg_roe * 100.0));
        } else if high_roe_count >= 3 {
            score += 1;
            details.push(format!("Good ROE consistency: {}/{} periods >15%", high_roe_count, roes.len()));
        }
    }

    let margins: Vec<f64> = metrics.iter().filter_map(|m| m.operating_margin).collect();
    if margins.len() >= 5 {
        let avg_margin = margins.iter().sum::<f64>() / margins.len() as f64;
        if avg_margin > 0.2 {
            score += 1;
            details.push(format!("Strong and stable operating margins (avg: {:.1}%)", avg_margin * 100.0));
        }
    }

    MoatResult { score, max_score, details: details.join("; ") }
}

pub fn analyze_management_quality(financial_line_items: &[LineItem]) -> MoatResult {
    if financial_line_items.is_empty() {
        return MoatResult { score: 0, max_score: 2, details: "Insufficient data for management quality analysis".to_string() };
    }
    let mut score = 0;
    let mut details = Vec::new();

    let latest = &financial_line_items[0];
    if let Some(buybacks) = latest.issuance_or_purchase_of_equity_shares {
        if buybacks < 0.0 {
            score += 1;
            details.push("Company has been repurchasing shares (shareholder-friendly)".to_string());
        }
    }

    if let Some(divs) = latest.dividends_and_other_cash_distributions {
        if divs < 0.0 {
            score += 1;
            details.push("Company has a track record of paying dividends".to_string());
        }
    }

    MoatResult { score, max_score: 2, details: details.join("; ") }
}

pub fn estimate_maintenance_capex(financial_line_items: &[LineItem]) -> f64 {
    if financial_line_items.is_empty() {
        return 0.0;
    }
    let latest = &financial_line_items[0];
    let capex = latest.capital_expenditure.map(|c| c.abs()).unwrap_or(0.0);
    let depreciation = latest.depreciation_and_amortization.unwrap_or(0.0);

    let method1 = capex * 0.85;
    let method2 = depreciation;

    method1.max(method2)
}

pub fn calculate_owner_earnings(financial_line_items: &[LineItem]) -> Option<f64> {
    if financial_line_items.is_empty() {
        return None;
    }
    let latest = &financial_line_items[0];
    let net_income = latest.net_income?;
    let depreciation = latest.depreciation_and_amortization.unwrap_or(0.0);
    let maintenance_capex = estimate_maintenance_capex(financial_line_items);

    Some(net_income + depreciation - maintenance_capex)
}

pub struct IntrinsicValuation {
    pub intrinsic_value: Option<f64>,
}

pub fn calculate_intrinsic_value(financial_line_items: &[LineItem]) -> IntrinsicValuation {
    if financial_line_items.is_empty() {
        return IntrinsicValuation { intrinsic_value: None };
    }
    let owner_earnings = match calculate_owner_earnings(financial_line_items) {
        Some(e) => e,
        None => return IntrinsicValuation { intrinsic_value: None },
    };

    let latest = &financial_line_items[0];
    let shares = match latest.outstanding_shares {
        Some(s) if s > 0 => s as f64,
        _ => return IntrinsicValuation { intrinsic_value: None },
    };

    // Very conservative DCF estimate
    let discount_rate = 0.10;
    let growth_rate = 0.05;
    let terminal_rate = 0.025;

    let mut pv = 0.0;
    let mut future_earnings = owner_earnings;
    
    // Stage 1 (Years 1-5)
    for _ in 1..=5 {
        future_earnings *= 1.0 + growth_rate;
        pv += future_earnings / (1.0 + discount_rate);
    }

    // Terminal value
    let terminal_earnings = future_earnings * (1.0 + terminal_rate);
    let terminal_val = terminal_earnings / (discount_rate - terminal_rate);
    pv += terminal_val / (1.0 + discount_rate);

    // Apply conservative margin of safety haircut
    let conservative_iv = pv * 0.85;

    IntrinsicValuation { intrinsic_value: Some(conservative_iv / shares) }
}

pub fn analyze_book_value_growth(financial_line_items: &[LineItem]) -> ScoringResult {
    if financial_line_items.len() < 3 {
        return ScoringResult { score: 0, details: "Insufficient data for book value analysis".to_string() };
    }
    let mut score = 0;
    let mut details = Vec::new();

    let book_values: Vec<f64> = financial_line_items.iter()
        .filter_map(|i| {
            if let (Some(equity), Some(shares)) = (i.shareholders_equity, i.outstanding_shares) {
                if shares > 0 { Some(equity / shares as f64) } else { None }
            } else {
                None
            }
        })
        .collect();

    if book_values.len() >= 2 {
        let is_growing = book_values.iter().zip(book_values.iter().skip(1)).all(|(&new, &old)| new > old);
        if is_growing {
            score += 3;
            details.push("Consistent book value growth over past periods".to_string());
        }
    }

    ScoringResult { score, details: details.join("; ") }
}

pub fn analyze_pricing_power(financial_line_items: &[LineItem], _metrics: &[FinancialMetrics]) -> ScoringResult {
    if financial_line_items.is_empty() {
        return ScoringResult { score: 0, details: "Insufficient data for pricing power analysis".to_string() };
    }
    let mut score = 0;
    let mut details = Vec::new();

    let latest = &financial_line_items[0];
    if let (Some(gross_profit), Some(revenue)) = (latest.gross_profit, latest.revenue) {
        if revenue > 0.0 {
            let margin = gross_profit / revenue;
            if margin > 0.4 {
                score += 3;
                details.push(format!("Excellent pricing power with gross margin of {:.1}%", margin * 100.0));
            }
        }
    }

    ScoringResult { score, details: details.join("; ") }
}

pub async fn generate_buffett_output(
    ticker: &str,
    facts: &serde_json::Value,
    state: &AgentState,
    agent_id: &str,
) -> Result<WarrenBuffettSignal> {
    let system_prompt = "You are Warren Buffett. Decide bullish, bearish, or neutral using only the provided facts.\n\
        Bullish: strong business AND margin of safety.\n\
        Bearish: poor business or clearly overvalued.\n\
        Neutral: good business but rich valuation.\n\
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
