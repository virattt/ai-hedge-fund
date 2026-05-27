// Source: src/agents/cathie_wood.py
//! Sibling to src/agents/cathie_wood.py
//! Analyzes stocks using Cathie Wood's disruptive innovation investment principles.

use anyhow::{Result, Context};
use crate::graph::state::AgentState;
use crate::tools::api::{get_financial_metrics, get_market_cap, search_line_items};
use crate::data::models::{FinancialMetrics, LineItem};
use crate::utils::llm::call_llm;

#[derive(Debug, serde::Serialize, serde::Deserialize, Default)]
pub struct CathieWoodSignal {
    pub signal: String,      // "bullish" | "bearish" | "neutral"
    pub confidence: u32,     // 0-100
    pub reasoning: String,
}

pub async fn cathie_wood_agent(state: &mut AgentState, agent_id: &str) -> Result<()> {
    println!("Running Cathie Wood Agent: {}", agent_id);

    let start_date = state.data.get("start_date")
        .and_then(|v| v.as_str())
        .context("Missing start_date in cathie_wood_agent")?;
    
    let end_date = state.data.get("end_date")
        .and_then(|v| v.as_str())
        .context("Missing end_date in cathie_wood_agent")?;
    
    let tickers_json = state.data.get("tickers")
        .context("Missing tickers in cathie_wood_agent")?;
    let tickers: Vec<String> = serde_json::from_value(tickers_json.clone())?;

    let api_key = state.metadata.get("FINANCIAL_DATASETS_API_KEY")
        .and_then(|v| v.as_str());

    let mut cw_analysis = serde_json::Map::new();

    for ticker in &tickers {
        // Fetch raw data
        let metrics = get_financial_metrics(ticker, end_date, "annual", 5, api_key).await.unwrap_or_default();
        let financial_line_items = search_line_items(
            ticker,
            vec![
                "revenue".to_string(),
                "gross_margin".to_string(),
                "operating_margin".to_string(),
                "debt_to_equity".to_string(),
                "free_cash_flow".to_string(),
                "total_assets".to_string(),
                "total_liabilities".to_string(),
                "dividends_and_other_cash_distributions".to_string(),
                "outstanding_shares".to_string(),
                "research_and_development".to_string(),
                "capital_expenditure".to_string(),
                "operating_expense".to_string(),
            ],
            end_date,
            "annual",
            5,
            api_key,
        ).await.unwrap_or_default();

        let market_cap = get_market_cap(ticker, end_date, api_key).await.unwrap_or(None).unwrap_or(0.0);

        // Sub-analyses
        let disruptive = analyze_disruptive_potential(&metrics, &financial_line_items);
        let innovation = analyze_innovation_growth(&metrics, &financial_line_items);
        let valuation = analyze_cathie_wood_valuation(&financial_line_items, market_cap);

        let total_score = disruptive.score + innovation.score + valuation.score;
        let max_possible_score = 15.0;

        let signal = if total_score >= 0.7 * max_possible_score {
            "bullish"
        } else if total_score <= 0.3 * max_possible_score {
            "bearish"
        } else {
            "neutral"
        };

        let facts = serde_json::json!({
            "signal": signal,
            "score": (total_score * 100.0).round() / 100.0,
            "max_score": max_possible_score,
            "disruptive_analysis": {
                "score": disruptive.score,
                "details": disruptive.details,
            },
            "innovation_analysis": {
                "score": innovation.score,
                "details": innovation.details,
            },
            "valuation_analysis": {
                "score": valuation.score,
                "details": valuation.details,
                "intrinsic_value": valuation.intrinsic_value,
                "margin_of_safety": valuation.margin_of_safety,
            },
            "market_cap": market_cap,
        });

        let output = generate_cathie_wood_output(ticker, &facts, state, agent_id).await?;

        cw_analysis.insert(
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
        obj.insert(agent_id.to_string(), serde_json::Value::Object(cw_analysis));
    }

    Ok(())
}

pub struct CWSubResult {
    pub score: f64,
    pub details: String,
}

pub fn analyze_disruptive_potential(_metrics: &[FinancialMetrics], financial_line_items: &[LineItem]) -> CWSubResult {
    let mut score = 0.0;
    let mut details = Vec::new();

    if financial_line_items.is_empty() {
        return CWSubResult { score: 0.0, details: "Insufficient data to analyze disruptive potential".to_string() };
    }

    // 1. Revenue growth acceleration (reverse chronological order: newest is at index 0)
    let revenues: Vec<f64> = financial_line_items.iter().filter_map(|item| item.revenue).collect();
    if revenues.len() >= 3 {
        let mut growth_rates = Vec::new();
        for i in 0..revenues.len() - 1 {
            let old = revenues[i + 1];
            if old != 0.0 {
                growth_rates.push((revenues[i] - old) / old.abs());
            }
        }
        if growth_rates.len() >= 2 && growth_rates[0] > growth_rates[growth_rates.len() - 1] {
            score += 2.0;
            details.push(format!("Revenue growth is accelerating: {:.1}% vs {:.1}%", growth_rates[0] * 100.0, growth_rates[growth_rates.len() - 1] * 100.0));
        }
        if !growth_rates.is_empty() {
            let latest_growth = growth_rates[0];
            if latest_growth > 1.0 {
                score += 3.0;
                details.push(format!("Exceptional revenue growth: {:.1}%", latest_growth * 100.0));
            } else if latest_growth > 0.5 {
                score += 2.0;
                details.push(format!("Strong revenue growth: {:.1}%", latest_growth * 100.0));
            } else if latest_growth > 0.2 {
                score += 1.0;
                details.push(format!("Moderate revenue growth: {:.1}%", latest_growth * 100.0));
            }
        }
    }

    // 2. Gross Margin levels
    let gross_margins: Vec<f64> = financial_line_items.iter().filter_map(|item| item.gross_margin).collect();
    if gross_margins.len() >= 2 {
        let margin_trend = gross_margins[0] - gross_margins[gross_margins.len() - 1];
        if margin_trend > 0.05 {
            score += 2.0;
            details.push(format!("Expanding gross margins: +{:.1}%", margin_trend * 100.0));
        } else if margin_trend > 0.0 {
            score += 1.0;
            details.push(format!("Slightly improving gross margins: +{:.1}%", margin_trend * 100.0));
        }
        if gross_margins[0] > 0.50 {
            score += 2.0;
            details.push(format!("High gross margin: {:.1}%", gross_margins[0] * 100.0));
        }
    }

    // 3. Operating Leverage
    let operating_expenses: Vec<f64> = financial_line_items.iter().filter_map(|item| item.operating_expense).collect();
    if revenues.len() >= 2 && operating_expenses.len() >= 2 {
        let old_rev = revenues[revenues.len() - 1];
        let old_opex = operating_expenses[operating_expenses.len() - 1];
        if old_rev != 0.0 && old_opex != 0.0 {
            let rev_growth = (revenues[0] - old_rev) / old_rev.abs();
            let opex_growth = (operating_expenses[0] - old_opex) / old_opex.abs();
            if rev_growth > opex_growth {
                score += 2.0;
                details.push("Positive operating leverage: Revenue growing faster than expenses".to_string());
            }
        }
    }

    // 4. R&D intensity
    let rd_expenses: Vec<f64> = financial_line_items.iter().filter_map(|item| item.research_and_development).collect();
    if !rd_expenses.is_empty() && !revenues.is_empty() && revenues[0] > 0.0 {
        let rd_intensity = rd_expenses[0] / revenues[0];
        if rd_intensity > 0.15 {
            score += 3.0;
            details.push(format!("High R&D investment: {:.1}% of revenue", rd_intensity * 100.0));
        } else if rd_intensity > 0.08 {
            score += 2.0;
            details.push(format!("Moderate R&D investment: {:.1}% of revenue", rd_intensity * 100.0));
        } else if rd_intensity > 0.05 {
            score += 1.0;
            details.push(format!("Some R&D investment: {:.1}% of revenue", rd_intensity * 100.0));
        }
    }

    let max_possible = 12.0;
    let normalized = (score / max_possible) * 5.0;

    CWSubResult { score: normalized, details: details.join("; ") }
}

pub fn analyze_innovation_growth(_metrics: &[FinancialMetrics], financial_line_items: &[LineItem]) -> CWSubResult {
    let mut score = 0.0;
    let mut details = Vec::new();

    if financial_line_items.is_empty() {
        return CWSubResult { score: 0.0, details: "Insufficient data to analyze innovation-driven growth".to_string() };
    }

    let rd_expenses: Vec<f64> = financial_line_items.iter().filter_map(|item| item.research_and_development).collect();
    let revenues: Vec<f64> = financial_line_items.iter().filter_map(|item| item.revenue).collect();

    // 1. R&D growth trend
    if rd_expenses.len() >= 2 && revenues.len() >= 2 {
        let old_rd = rd_expenses[rd_expenses.len() - 1];
        if old_rd != 0.0 {
            let rd_growth = (rd_expenses[0] - old_rd) / old_rd.abs();
            if rd_growth > 0.5 {
                score += 3.0;
                details.push(format!("Strong R&D investment growth: +{:.1}%", rd_growth * 100.0));
            } else if rd_growth > 0.2 {
                score += 2.0;
                details.push(format!("Moderate R&D investment growth: +{:.1}%", rd_growth * 100.0));
            }
        }
        let start_intensity = rd_expenses[rd_expenses.len() - 1] / revenues[revenues.len() - 1];
        let end_intensity = rd_expenses[0] / revenues[0];
        if end_intensity > start_intensity {
            score += 2.0;
            details.push(format!("Increasing R&D intensity: {:.1}% vs {:.1}%", end_intensity * 100.0, start_intensity * 100.0));
        }
    }

    // 2. FCF growth
    let fcf_vals: Vec<f64> = financial_line_items.iter().filter_map(|item| item.free_cash_flow).collect();
    if fcf_vals.len() >= 2 {
        let old_fcf = fcf_vals[fcf_vals.len() - 1];
        let positive_fcf_count = fcf_vals.iter().filter(|&&f| f > 0.0).count();
        if old_fcf != 0.0 {
            let fcf_growth = (fcf_vals[0] - old_fcf) / old_fcf.abs();
            if fcf_growth > 0.3 && positive_fcf_count == fcf_vals.len() {
                score += 3.0;
                details.push("Strong and consistent FCF growth, excellent innovation funding capacity".to_string());
            } else if positive_fcf_count as f64 >= fcf_vals.len() as f64 * 0.75 {
                score += 2.0;
                details.push("Consistent positive FCF, good innovation funding capacity".to_string());
            } else if positive_fcf_count as f64 > fcf_vals.len() as f64 * 0.5 {
                score += 1.0;
                details.push("Moderately consistent FCF, adequate innovation funding capacity".to_string());
            }
        }
    }

    // 3. Operating margin stability
    let op_margin_vals: Vec<f64> = financial_line_items.iter().filter_map(|item| item.operating_margin).collect();
    if op_margin_vals.len() >= 2 {
        let margin_trend = op_margin_vals[0] - op_margin_vals[op_margin_vals.len() - 1];
        if op_margin_vals[0] > 0.15 && margin_trend > 0.0 {
            score += 3.0;
            details.push(format!("Strong and improving operating margin: {:.1}%", op_margin_vals[0] * 100.0));
        } else if op_margin_vals[0] > 0.10 {
            score += 2.0;
            details.push(format!("Healthy operating margin: {:.1}%", op_margin_vals[0] * 100.0));
        } else if margin_trend > 0.0 {
            score += 1.0;
            details.push("Improving operating efficiency".to_string());
        }
    }

    // 4. Capex intensity
    let capex: Vec<f64> = financial_line_items.iter().filter_map(|item| item.capital_expenditure).collect();
    if capex.len() >= 2 && revenues.len() >= 2 {
        let capex_intensity = capex[0].abs() / revenues[0];
        let old_capex = capex[capex.len() - 1].abs();
        if old_capex != 0.0 {
            let capex_growth = (capex[0].abs() - old_capex) / old_capex;
            if capex_intensity > 0.10 && capex_growth > 0.2 {
                score += 2.0;
                details.push("Strong investment in growth infrastructure".to_string());
            } else if capex_intensity > 0.05 {
                score += 1.0;
                details.push("Moderate investment in growth infrastructure".to_string());
            }
        }
    }

    // 5. Reinvestment over dividends
    let dividends: Vec<f64> = financial_line_items.iter().filter_map(|item| item.dividends_and_other_cash_distributions).collect();
    if !dividends.is_empty() && !fcf_vals.is_empty() && fcf_vals[0] != 0.0 {
        let latest_payout_ratio = dividends[0].abs() / fcf_vals[0];
        if latest_payout_ratio < 0.2 {
            score += 2.0;
            details.push("Strong focus on reinvestment over dividends".to_string());
        } else if latest_payout_ratio < 0.4 {
            score += 1.0;
            details.push("Moderate focus on reinvestment over dividends".to_string());
        }
    }

    let max_possible = 15.0;
    let normalized = (score / max_possible) * 5.0;

    CWSubResult { score: normalized, details: details.join("; ") }
}

pub struct CWValuationResult {
    pub score: f64,
    pub details: String,
    pub intrinsic_value: Option<f64>,
    pub margin_of_safety: Option<f64>,
}

pub fn analyze_cathie_wood_valuation(financial_line_items: &[LineItem], market_cap: f64) -> CWValuationResult {
    if financial_line_items.is_empty() || market_cap <= 0.0 {
        return CWValuationResult { score: 0.0, details: "Insufficient data for valuation".to_string(), intrinsic_value: None, margin_of_safety: None };
    }

    let latest = &financial_line_items[0];
    let fcf = latest.free_cash_flow.unwrap_or(0.0);

    if fcf <= 0.0 {
        return CWValuationResult {
            score: 0.0,
            details: format!("No positive FCF for valuation; FCF = {:.2}", fcf),
            intrinsic_value: None,
            margin_of_safety: None,
        };
    }

    let growth_rate = 0.20;
    let discount_rate = 0.15;
    let terminal_multiple = 25.0;
    let projection_years = 5;

    let mut present_value = 0.0;
    for year in 1..=projection_years {
        let future_fcf = fcf * (1.0 + growth_rate as f64).powi(year);
        let pv = future_fcf / (1.0 + discount_rate as f64).powi(year);
        present_value += pv;
    }

    let terminal_value = (fcf * (1.0 + growth_rate as f64).powi(projection_years) * terminal_multiple) / (1.0 + discount_rate as f64).powi(projection_years);
    let intrinsic_value = present_value + terminal_value;

    let margin_of_safety = (intrinsic_value - market_cap) / market_cap;

    let mut score = 0.0;
    if margin_of_safety > 0.5 {
        score += 3.0;
    } else if margin_of_safety > 0.2 {
        score += 1.0;
    }

    let details = vec![
        format!("Calculated intrinsic value: ~{:.2}", intrinsic_value),
        format!("Market cap: ~{:.2}", market_cap),
        format!("Margin of safety: {:.2}%", margin_of_safety * 100.0),
    ];

    CWValuationResult {
        score,
        details: details.join("; "),
        intrinsic_value: Some(intrinsic_value),
        margin_of_safety: Some(margin_of_safety),
    }
}

pub async fn generate_cathie_wood_output(
    ticker: &str,
    facts: &serde_json::Value,
    state: &AgentState,
    agent_id: &str,
) -> Result<CathieWoodSignal> {
    let system_prompt = "You are a Cathie Wood AI agent, making investment decisions using her principles:\n\
        1. Seek companies leveraging disruptive innovation.\n\
        2. Emphasize exponential growth potential, large TAM.\n\
        3. Focus on future-facing tech / robotics / genomic / web3.\n\
        4. Accept short-term volatility for multi-year exponential gains.\n\
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
