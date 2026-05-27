// Source: src/agents/charlie_munger.py
//! Sibling to src/agents/charlie_munger.py
//! Analyzes stocks using Charlie Munger's mental models and qualitative/quantitative checks.

use anyhow::{Result, Context};
use crate::graph::state::AgentState;
use crate::tools::api::{get_financial_metrics, get_market_cap, search_line_items, get_insider_trades, get_company_news};
use crate::data::models::{FinancialMetrics, LineItem, InsiderTrade, CompanyNews};
use crate::utils::llm::call_llm;

#[derive(Debug, serde::Serialize, serde::Deserialize, Default)]
pub struct CharlieMungerSignal {
    pub signal: String,      // "bullish" | "bearish" | "neutral"
    pub confidence: u32,     // 0-100
    pub reasoning: String,
}

pub async fn charlie_munger_agent(state: &mut AgentState, agent_id: &str) -> Result<()> {
    println!("Running Charlie Munger Agent: {}", agent_id);

    let start_date = state.data.get("start_date")
        .and_then(|v| v.as_str())
        .context("Missing start_date in charlie_munger_agent")?;
    
    let end_date = state.data.get("end_date")
        .and_then(|v| v.as_str())
        .context("Missing end_date in charlie_munger_agent")?;
    
    let tickers_json = state.data.get("tickers")
        .context("Missing tickers in charlie_munger_agent")?;
    let tickers: Vec<String> = serde_json::from_value(tickers_json.clone())?;

    let api_key = state.metadata.get("FINANCIAL_DATASETS_API_KEY")
        .and_then(|v| v.as_str());

    let mut munger_analysis = serde_json::Map::new();

    for ticker in &tickers {
        // Fetch historical data
        let metrics = get_financial_metrics(ticker, end_date, "annual", 10, api_key).await.unwrap_or_default();
        let financial_line_items = search_line_items(
            ticker,
            vec![
                "revenue".to_string(),
                "net_income".to_string(),
                "operating_income".to_string(),
                "return_on_invested_capital".to_string(),
                "gross_margin".to_string(),
                "operating_margin".to_string(),
                "free_cash_flow".to_string(),
                "capital_expenditure".to_string(),
                "cash_and_equivalents".to_string(),
                "total_debt".to_string(),
                "shareholders_equity".to_string(),
                "outstanding_shares".to_string(),
                "research_and_development".to_string(),
                "goodwill_and_intangible_assets".to_string(),
            ],
            end_date,
            "annual",
            10,
            api_key,
        ).await.unwrap_or_default();

        let market_cap = get_market_cap(ticker, end_date, api_key).await.unwrap_or(None).unwrap_or(0.0);
        let insider_trades = get_insider_trades(ticker, end_date, None, 100, api_key).await.unwrap_or_default();
        let company_news = get_company_news(ticker, end_date, None, 10, api_key).await.unwrap_or_default();

        // Sub-analyses
        let moat = analyze_moat_strength(&metrics, &financial_line_items);
        let mgmt = analyze_management_quality(&financial_line_items, &insider_trades);
        let predictability = analyze_predictability(&financial_line_items);
        let valuation = calculate_munger_valuation(&financial_line_items, market_cap);

        // Combined scores (quality and predictability are weighted higher than current valuation)
        let total_score = moat.score * 0.35
            + mgmt.score * 0.25
            + predictability.score * 0.25
            + valuation.score * 0.15;

        let max_possible_score = 10.0;

        let signal = if total_score >= 7.5 {
            "bullish"
        } else if total_score <= 5.5 {
            "bearish"
        } else {
            "neutral"
        };

        let confidence_hint = compute_confidence(&moat, &mgmt, &predictability, &valuation, signal);

        let facts = make_munger_facts_bundle(
            signal,
            total_score,
            max_possible_score,
            &moat,
            &mgmt,
            &predictability,
            &valuation,
        );

        let output = generate_munger_output(ticker, &facts, state, agent_id, confidence_hint).await?;

        munger_analysis.insert(
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
        obj.insert(agent_id.to_string(), serde_json::Value::Object(munger_analysis));
    }

    Ok(())
}

pub struct MungerSubResult {
    pub score: f64,
    pub details: String,
}

pub fn analyze_moat_strength(_metrics: &[FinancialMetrics], financial_line_items: &[LineItem]) -> MungerSubResult {
    let mut score = 0.0;
    let mut details = Vec::new();

    if financial_line_items.is_empty() {
        return MungerSubResult { score: 0.0, details: "Insufficient data to analyze moat strength".to_string() };
    }

    // 1. ROIC
    let roic_values: Vec<f64> = financial_line_items.iter().filter_map(|item| item.return_on_invested_capital).collect();
    if !roic_values.is_empty() {
        let high_roic_count = roic_values.iter().filter(|&&r| r > 0.15).count();
        if high_roic_count as f64 >= roic_values.len() as f64 * 0.8 {
            score += 3.0;
            details.push(format!("Excellent ROIC: >15% in {}/{} periods", high_roic_count, roic_values.len()));
        } else if high_roic_count as f64 >= roic_values.len() as f64 * 0.5 {
            score += 2.0;
            details.push(format!("Good ROIC: >15% in {}/{} periods", high_roic_count, roic_values.len()));
        } else if high_roic_count > 0 {
            score += 1.0;
            details.push(format!("Mixed ROIC: >15% in only {}/{} periods", high_roic_count, roic_values.len()));
        } else {
            details.push("Poor ROIC: Never exceeds 15% threshold".to_string());
        }
    } else {
        details.push("No ROIC data available".to_string());
    }

    // 2. Pricing Power (Gross Margins)
    let gross_margins: Vec<f64> = financial_line_items.iter().filter_map(|item| item.gross_margin).collect();
    if gross_margins.len() >= 3 {
        let margin_trend = gross_margins.iter().zip(gross_margins.iter().skip(1)).filter(|(&new, &old)| new >= old).count();
        if margin_trend as f64 >= gross_margins.len() as f64 * 0.7 {
            score += 2.0;
            details.push("Strong pricing power: Gross margins consistently improving".to_string());
        } else {
            let avg_margin: f64 = gross_margins.iter().sum::<f64>() / gross_margins.len() as f64;
            if avg_margin > 0.30 {
                score += 1.0;
                details.push(format!("Good pricing power: Average gross margin {:.1}%", avg_margin * 100.0));
            } else {
                details.push("Limited pricing power: Low or declining gross margins".to_string());
            }
        }
    } else {
        details.push("Insufficient gross margin data".to_string());
    }

    // 3. Capital intensity
    let mut capex_to_revenue = Vec::new();
    for item in financial_line_items {
        if let (Some(capex), Some(rev)) = (item.capital_expenditure, item.revenue) {
            if rev > 0.0 {
                capex_to_revenue.push(capex.abs() / rev);
            }
        }
    }
    if !capex_to_revenue.is_empty() {
        let avg_capex_ratio: f64 = capex_to_revenue.iter().sum::<f64>() / capex_to_revenue.len() as f64;
        if avg_capex_ratio < 0.05 {
            score += 2.0;
            details.push(format!("Low capital requirements: Avg capex {:.1}% of revenue", avg_capex_ratio * 100.0));
        } else if avg_capex_ratio < 0.10 {
            score += 1.0;
            details.push(format!("Moderate capital requirements: Avg capex {:.1}% of revenue", avg_capex_ratio * 100.0));
        } else {
            details.push(format!("High capital requirements: Avg capex {:.1}% of revenue", avg_capex_ratio * 100.0));
        }
    } else {
        details.push("No capital expenditure data available".to_string());
    }

    // 4. Intangibles
    let rd_sum: f64 = financial_line_items.iter().filter_map(|item| item.research_and_development).sum();
    if rd_sum > 0.0 {
        score += 1.0;
        details.push("Invests in R&D, building intellectual property".to_string());
    }

    let has_goodwill = financial_line_items.iter().any(|item| item.goodwill_and_intangible_assets.unwrap_or(0.0) > 0.0);
    if has_goodwill {
        score += 1.0;
        details.push("Significant goodwill/intangible assets, suggesting brand value or IP".to_string());
    }

    let final_score = (score * 10.0_f64 / 9.0_f64).min(10.0_f64);
    MungerSubResult { score: final_score, details: details.join("; ") }
}

pub struct MungerMgmtResult {
    pub score: f64,
    pub details: String,
    pub insider_buy_ratio: Option<f64>,
    pub recent_de_ratio: Option<f64>,
    pub cash_to_revenue: Option<f64>,
    pub share_count_trend: String,
}

pub fn analyze_management_quality(financial_line_items: &[LineItem], insider_trades: &[InsiderTrade]) -> MungerMgmtResult {
    let mut score = 0.0;
    let mut details = Vec::new();

    let mut insider_buy_ratio = None;
    let mut recent_de_ratio = None;
    let mut cash_to_revenue = None;
    let mut share_count_trend = "unknown".to_string();

    if financial_line_items.is_empty() {
        return MungerMgmtResult {
            score: 0.0,
            details: "Insufficient data to analyze management quality".to_string(),
            insider_buy_ratio: None,
            recent_de_ratio: None,
            cash_to_revenue: None,
            share_count_trend: "unknown".to_string(),
        };
    }

    // 1. Capital conversion (FCF / Net Income)
    let fcf_values: Vec<f64> = financial_line_items.iter().filter_map(|item| item.free_cash_flow).collect();
    let net_income_values: Vec<f64> = financial_line_items.iter().filter_map(|item| item.net_income).collect();
    if !fcf_values.is_empty() && fcf_values.len() == net_income_values.len() {
        let mut ratios = Vec::new();
        for i in 0..fcf_values.len() {
            if net_income_values[i] > 0.0 {
                ratios.push(fcf_values[i] / net_income_values[i]);
            }
        }
        if !ratios.is_empty() {
            let avg_ratio: f64 = ratios.iter().sum::<f64>() / ratios.len() as f64;
            if avg_ratio > 1.1 {
                score += 3.0;
                details.push(format!("Excellent cash conversion: FCF/NI ratio of {:.2}", avg_ratio));
            } else if avg_ratio > 0.9 {
                score += 2.0;
                details.push(format!("Good cash conversion: FCF/NI ratio of {:.2}", avg_ratio));
            } else if avg_ratio > 0.7 {
                score += 1.0;
                details.push(format!("Moderate cash conversion: FCF/NI ratio of {:.2}", avg_ratio));
            } else {
                details.push(format!("Poor cash conversion: FCF/NI ratio of only {:.2}", avg_ratio));
            }
        }
    }

    // 2. Debt management (D/E)
    let latest = &financial_line_items[0];
    if let (Some(debt), Some(equity)) = (latest.total_debt, latest.shareholders_equity) {
        let de = if equity > 0.0 { debt / equity } else { 999.0 };
        recent_de_ratio = Some(de);
        if de < 0.3 {
            score += 3.0;
            details.push(format!("Conservative debt management: D/E ratio of {:.2}", de));
        } else if de < 0.7 {
            score += 2.0;
            details.push(format!("Prudent debt management: D/E ratio of {:.2}", de));
        } else if de < 1.5 {
            score += 1.0;
            details.push(format!("Moderate debt level: D/E ratio of {:.2}", de));
        } else {
            details.push(format!("High debt level: D/E ratio of {:.2}", de));
        }
    }

    // 3. Cash management
    if let (Some(cash), Some(rev)) = (latest.cash_and_equivalents, latest.revenue) {
        if rev > 0.0 {
            let ratio = cash / rev;
            cash_to_revenue = Some(ratio);
            if ratio >= 0.1 && ratio <= 0.25 {
                score += 2.0;
                details.push(format!("Prudent cash management: Cash/Revenue ratio of {:.2}", ratio));
            } else if ratio >= 0.05 && ratio <= 0.4 {
                score += 1.0;
                details.push(format!("Acceptable cash position: Cash/Revenue ratio of {:.2}", ratio));
            } else {
                details.push(format!("Inefficient or tight cash reserves: Cash/Revenue ratio of {:.2}", ratio));
            }
        }
    }

    // 4. Insider trades buy ratio
    if !insider_trades.is_empty() {
        let buys = insider_trades.iter().filter(|t| {
            if let Some(ref t_type) = t.transaction_type_desc() {
                t_type.to_lowercase().contains("buy") || t_type.to_lowercase().contains("purchase")
            } else {
                false
            }
        }).count();
        let sells = insider_trades.iter().filter(|t| {
            if let Some(ref t_type) = t.transaction_type_desc() {
                t_type.to_lowercase().contains("sell") || t_type.to_lowercase().contains("sale")
            } else {
                false
            }
        }).count();
        let total = buys + sells;
        if total > 0 {
            let buy_ratio = buys as f64 / total as f64;
            insider_buy_ratio = Some(buy_ratio);
            if buy_ratio > 0.7 {
                score += 2.0;
                details.push(format!("Strong insider buying: {}/{} transactions are purchases", buys, total));
            } else if buy_ratio > 0.4 {
                score += 1.0;
                details.push(format!("Balanced insider trading: {}/{} transactions are purchases", buys, total));
            } else if buy_ratio < 0.1 && sells > 5 {
                score -= 1.0;
                details.push(format!("Concerning insider selling: {}/{} transactions are sales", sells, total));
            }
        }
    }

    // 5. Share count trend
    let share_counts: Vec<f64> = financial_line_items.iter().filter_map(|item| item.outstanding_shares.map(|s| s as f64)).collect();
    if share_counts.len() >= 3 {
        let latest_s = share_counts[0];
        let oldest_s = share_counts[share_counts.len() - 1];
        if latest_s < oldest_s * 0.95 {
            score += 2.0;
            share_count_trend = "decreasing".to_string();
            details.push("Shareholder-friendly: Reducing share count over time".to_string());
        } else if latest_s < oldest_s * 1.05 {
            score += 1.0;
            share_count_trend = "stable".to_string();
            details.push("Stable share count: Limited dilution".to_string());
        } else {
            score -= 1.0;
            share_count_trend = "increasing".to_string();
            details.push("Concerning dilution: Share count increased significantly".to_string());
        }
    }

    let final_score = (score * 10.0_f64 / 12.0_f64).clamp(0.0_f64, 10.0_f64);
    MungerMgmtResult {
        score: final_score,
        details: details.join("; "),
        insider_buy_ratio,
        recent_de_ratio,
        cash_to_revenue,
        share_count_trend,
    }
}

// Quick helper for InsiderTrade since models.rs has transaction_date and titles but might lack explicit descriptor helper
impl InsiderTrade {
    pub fn transaction_type_desc(&self) -> Option<String> {
        self.security_title.clone() // Just returns security_title as an indicator or fallback
    }
}

pub fn analyze_predictability(financial_line_items: &[LineItem]) -> MungerSubResult {
    let mut score = 0.0;
    let mut details = Vec::new();

    if financial_line_items.len() < 5 {
        return MungerSubResult { score: 0.0, details: "Insufficient data to analyze business predictability (need 5+ years)".to_string() };
    }

    // 1. Revenue stability and growth
    let revenues: Vec<f64> = financial_line_items.iter().filter_map(|item| item.revenue).collect();
    if revenues.len() >= 5 {
        let mut growth_rates = Vec::new();
        for i in 0..revenues.len() - 1 {
            let old = revenues[i + 1];
            if old != 0.0 {
                growth_rates.push((revenues[i] - old) / old);
            }
        }
        if !growth_rates.is_empty() {
            let avg_growth: f64 = growth_rates.iter().sum::<f64>() / growth_rates.len() as f64;
            let growth_volatility: f64 = growth_rates.iter().map(|&r| (r - avg_growth).abs()).sum::<f64>() / growth_rates.len() as f64;

            if avg_growth > 0.05 && growth_volatility < 0.1 {
                score += 3.0;
                details.push(format!("Highly predictable revenue: {:.1}% avg growth with low volatility", avg_growth * 100.0));
            } else if avg_growth > 0.0 && growth_volatility < 0.2 {
                score += 2.0;
                details.push(format!("Moderately predictable revenue: {:.1}% avg growth with some volatility", avg_growth * 100.0));
            } else if avg_growth > 0.0 {
                score += 1.0;
                details.push(format!("Growing but less predictable revenue: {:.1}% avg growth with high volatility", avg_growth * 100.0));
            } else {
                details.push(format!("Declining or highly unpredictable revenue: {:.1}% avg growth", avg_growth * 100.0));
            }
        }
    }

    // 2. Operating income stability
    let op_income: Vec<f64> = financial_line_items.iter().filter_map(|item| item.operating_income).collect();
    if op_income.len() >= 5 {
        let positive_periods = op_income.iter().filter(|&&inc| inc > 0.0).count();
        if positive_periods == op_income.len() {
            score += 3.0;
            details.push("Highly predictable operations: Operating income positive in all periods".to_string());
        } else if positive_periods as f64 >= op_income.len() as f64 * 0.8 {
            score += 2.0;
            details.push(format!("Predictable operations: Operating income positive in {}/{} periods", positive_periods, op_income.len()));
        } else if positive_periods as f64 >= op_income.len() as f64 * 0.6 {
            score += 1.0;
            details.push(format!("Somewhat predictable operations: Operating income positive in {}/{} periods", positive_periods, op_income.len()));
        }
    }

    // 3. Margin consistency
    let op_margins: Vec<f64> = financial_line_items.iter().filter_map(|item| item.operating_margin).collect();
    if op_margins.len() >= 5 {
        let avg_margin: f64 = op_margins.iter().sum::<f64>() / op_margins.len() as f64;
        let margin_volatility: f64 = op_margins.iter().map(|&m| (m - avg_margin).abs()).sum::<f64>() / op_margins.len() as f64;

        if margin_volatility < 0.03 {
            score += 2.0;
            details.push(format!("Highly predictable margins: {:.1}% avg with minimal volatility", avg_margin * 100.0));
        } else if margin_volatility < 0.07 {
            score += 1.0;
            details.push(format!("Moderately predictable margins: {:.1}% avg with some volatility", avg_margin * 100.0));
        }
    }

    // 4. Cash generation reliability
    let fcf_values: Vec<f64> = financial_line_items.iter().filter_map(|item| item.free_cash_flow).collect();
    if fcf_values.len() >= 5 {
        let positive_fcf_periods = fcf_values.iter().filter(|&&f| f > 0.0).count();
        if positive_fcf_periods == fcf_values.len() {
            score += 2.0;
            details.push("Highly predictable cash generation: Positive FCF in all periods".to_string());
        } else if positive_fcf_periods as f64 >= fcf_values.len() as f64 * 0.8 {
            score += 1.0;
            details.push(format!("Predictable cash generation: Positive FCF in {}/{} periods", positive_fcf_periods, fcf_values.len()));
        }
    }

    let final_score = (score * 10.0_f64 / 10.0_f64).min(10.0_f64);
    MungerSubResult { score: final_score, details: details.join("; ") }
}

pub struct MungerValuationResult {
    pub score: f64,
    pub details: String,
    pub fcf_yield: f64,
    pub normalized_fcf: f64,
    pub reasonable_value: f64,
    pub margin_of_safety_vs_fair_value: f64,
}

pub fn calculate_munger_valuation(financial_line_items: &[LineItem], market_cap: f64) -> MungerValuationResult {
    if financial_line_items.is_empty() || market_cap <= 0.0 {
        return MungerValuationResult {
            score: 0.0,
            details: "Insufficient data to perform valuation".to_string(),
            fcf_yield: 0.0,
            normalized_fcf: 0.0,
            reasonable_value: 0.0,
            margin_of_safety_vs_fair_value: 0.0,
        };
    }

    let fcf_values: Vec<f64> = financial_line_items.iter().filter_map(|item| item.free_cash_flow).collect();
    if fcf_values.len() < 3 {
        return MungerValuationResult {
            score: 0.0,
            details: "Insufficient free cash flow data for valuation".to_string(),
            fcf_yield: 0.0,
            normalized_fcf: 0.0,
            reasonable_value: 0.0,
            margin_of_safety_vs_fair_value: 0.0,
        };
    }

    let periods = 5.min(fcf_values.len());
    let normalized_fcf: f64 = fcf_values[..periods].iter().sum::<f64>() / periods as f64;

    if normalized_fcf <= 0.0 {
        return MungerValuationResult {
            score: 0.0,
            details: format!("Negative or zero normalized FCF ({:.1}), cannot value", normalized_fcf),
            fcf_yield: 0.0,
            normalized_fcf,
            reasonable_value: 0.0,
            margin_of_safety_vs_fair_value: 0.0,
        };
    }

    let fcf_yield = normalized_fcf / market_cap;
    let mut score = 0.0;
    let mut details = Vec::new();

    if fcf_yield > 0.08 {
        score += 4.0;
        details.push(format!("Excellent value: {:.1}% FCF yield", fcf_yield * 100.0));
    } else if fcf_yield > 0.05 {
        score += 3.0;
        details.push(format!("Good value: {:.1}% FCF yield", fcf_yield * 100.0));
    } else if fcf_yield > 0.03 {
        score += 1.0;
        details.push(format!("Fair value: {:.1}% FCF yield", fcf_yield * 100.0));
    } else {
        details.push(format!("Expensive: Only {:.1}% FCF yield", fcf_yield * 100.0));
    }

    let reasonable_value = normalized_fcf * 15.0;
    let margin_of_safety_vs_fair_value = (reasonable_value - market_cap) / market_cap;

    if margin_of_safety_vs_fair_value > 0.3 {
        score += 3.0;
        details.push(format!("Large margin of safety: {:.1}% upside to reasonable value", margin_of_safety_vs_fair_value * 100.0));
    } else if margin_of_safety_vs_fair_value > 0.1 {
        score += 2.0;
        details.push(format!("Moderate margin of safety: {:.1}% upside to reasonable value", margin_of_safety_vs_fair_value * 100.0));
    } else if margin_of_safety_vs_fair_value > -0.1 {
        score += 1.0;
        details.push(format!("Fair price: Within 10% of reasonable value ({:.1}%)", margin_of_safety_vs_fair_value * 100.0));
    } else {
        details.push(format!("Expensive: {:.1}% premium to reasonable value", -margin_of_safety_vs_fair_value * 100.0));
    }

    if fcf_values.len() >= 3 {
        let recent_avg: f64 = fcf_values[..3].iter().sum::<f64>() / 3.0;
        let older_avg = if fcf_values.len() >= 6 {
            fcf_values[fcf_values.len() - 3..].iter().sum::<f64>() / 3.0
        } else {
            fcf_values[fcf_values.len() - 1]
        };

        if recent_avg > older_avg * 1.2 {
            score += 3.0;
            details.push("Growing FCF trend adds to intrinsic value".to_string());
        } else if recent_avg > older_avg {
            score += 2.0;
            details.push("Stable to growing FCF supports valuation".to_string());
        } else {
            details.push("Declining FCF trend is concerning".to_string());
        }
    }

    let final_score = (score * 10.0_f64 / 10.0_f64).min(10.0_f64);
    MungerValuationResult {
        score: final_score,
        details: details.join("; "),
        fcf_yield,
        normalized_fcf,
        reasonable_value,
        margin_of_safety_vs_fair_value,
    }
}

pub fn compute_confidence(
    moat: &MungerSubResult,
    mgmt: &MungerMgmtResult,
    pred: &MungerSubResult,
    val: &MungerValuationResult,
    signal: &str,
) -> u32 {
    let quality = 0.35 * moat.score + 0.25 * mgmt.score + 0.25 * pred.score;
    let quality_pct = if quality > 0.0 { quality / 8.5 * 100.0 } else { 0.0 };

    let mos = val.margin_of_safety_vs_fair_value;
    let val_adj = (mos * 100.0 / 3.0).clamp(-10.0, 10.0);

    let base = 0.85 * quality_pct + 0.15 * (val.score * 10.0) + val_adj;

    let (lower, upper) = match signal {
        "bullish" => {
            let u = if mos > 0.0 { 100.0 } else { 69.0 };
            let l = if quality_pct >= 55.0 { 50.0 } else { 30.0 };
            (l, u)
        }
        "bearish" => {
            let l = if mos < -0.05 { 10.0 } else { 30.0 };
            (l, 49.0)
        }
        _ => (50.0, 69.0),
    };

    let conf = base.clamp(lower, upper).round() as u32;
    conf.clamp(10, 100)
}

pub fn make_munger_facts_bundle(
    signal: &str,
    score: f64,
    max_score: f64,
    moat: &MungerSubResult,
    mgmt: &MungerMgmtResult,
    pred: &MungerSubResult,
    val: &MungerValuationResult,
) -> serde_json::Value {
    let flags = serde_json::json!({
        "moat_strong": moat.score >= 7.0,
        "predictable": pred.score >= 7.0,
        "owner_aligned": mgmt.score >= 7.0 || mgmt.insider_buy_ratio.unwrap_or(0.0) >= 0.6,
        "low_leverage": mgmt.recent_de_ratio.unwrap_or(99.0) < 0.7,
        "sensible_cash": mgmt.cash_to_revenue.map(|r| r >= 0.1 && r <= 0.25).unwrap_or(false),
        "mos_positive": val.margin_of_safety_vs_fair_value > 0.0,
        "fcf_yield_ok": val.fcf_yield >= 0.05,
        "share_count_friendly": mgmt.share_count_trend == "decreasing",
    });

    serde_json::json!({
        "pre_signal": signal,
        "score": (score * 100.0).round() / 100.0,
        "max_score": max_score,
        "moat_score": (moat.score * 100.0).round() / 100.0,
        "mgmt_score": (mgmt.score * 100.0).round() / 100.0,
        "predictability_score": (pred.score * 100.0).round() / 100.0,
        "valuation_score": (val.score * 100.0).round() / 100.0,
        "fcf_yield": (val.fcf_yield * 10000.0).round() / 10000.0,
        "normalized_fcf": val.normalized_fcf.round(),
        "reasonable_value": val.reasonable_value.round(),
        "margin_of_safety_vs_fair_value": (val.margin_of_safety_vs_fair_value * 1000.0).round() / 1000.0,
        "insider_buy_ratio": mgmt.insider_buy_ratio.map(|r| (r * 100.0).round() / 100.0),
        "recent_de_ratio": mgmt.recent_de_ratio.map(|r| (r * 100.0).round() / 100.0),
        "cash_to_revenue": mgmt.cash_to_revenue.map(|r| (r * 100.0).round() / 100.0),
        "share_count_trend": mgmt.share_count_trend,
        "flags": flags,
        "notes": {
            "moat": moat.details,
            "mgmt": mgmt.details,
            "predictability": pred.details,
            "valuation": val.details,
        }
    })
}

pub async fn generate_munger_output(
    ticker: &str,
    facts: &serde_json::Value,
    state: &AgentState,
    agent_id: &str,
    confidence_hint: u32,
) -> Result<CharlieMungerSignal> {
    let system_prompt = "You are Charlie Munger. Decide bullish, bearish, or neutral using only the facts.\n\
        Return JSON only. Keep reasoning under 120 characters.\n\
        Use the provided confidence exactly; do not change it.\n\
        Return JSON matching exactly: {\"signal\": \"bullish\" | \"bearish\" | \"neutral\", \"confidence\": int, \"reasoning\": \"short\"}";

    let user_prompt = format!(
        "Ticker: {}\nFacts:\n{}\nConfidence: {}\n\nReturn structured JSON output.",
        ticker,
        serde_json::to_string_pretty(facts)?,
        confidence_hint
    );

    call_llm(
        system_prompt,
        &user_prompt,
        Some(agent_id),
        Some(state),
        3,
    ).await
}
