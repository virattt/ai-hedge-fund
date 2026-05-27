// Source: src/agents/aswath_damodaran.py
//! Sibling to src/agents/aswath_damodaran.py
//! Analyzes equities using NYU Stern Professor Aswath Damodaran's CAPM and FCFF DCF model.

use crate::data::models::{FinancialMetrics, LineItem};
use crate::graph::state::AgentState;
use crate::tools::api::{get_financial_metrics, get_market_cap, search_line_items};
use crate::utils::llm::call_llm;
use anyhow::{Context, Result};

#[derive(Debug, serde::Serialize, serde::Deserialize, Default)]
pub struct AswathDamodaranSignal {
    pub signal: String,  // "bullish" | "bearish" | "neutral"
    pub confidence: u32, // 0-100
    pub reasoning: String,
}

pub async fn aswath_damodaran_agent(state: &mut AgentState, agent_id: &str) -> Result<()> {
    println!("Running Aswath Damodaran Agent: {}", agent_id);

    let _start_date = state
        .data
        .get("start_date")
        .and_then(|v| v.as_str())
        .context("Missing start_date in aswath_damodaran_agent")?;

    let end_date = state
        .data
        .get("end_date")
        .and_then(|v| v.as_str())
        .context("Missing end_date in aswath_damodaran_agent")?;

    let tickers_json = state
        .data
        .get("tickers")
        .context("Missing tickers in aswath_damodaran_agent")?;
    let tickers: Vec<String> = serde_json::from_value(tickers_json.clone())?;

    let api_key = state
        .metadata
        .get("FINANCIAL_DATASETS_API_KEY")
        .and_then(|v| v.as_str());

    let mut damodaran_signals = serde_json::Map::new();

    for ticker in &tickers {
        // Fetch raw data
        let metrics = get_financial_metrics(ticker, end_date, "ttm", 5, api_key)
            .await
            .unwrap_or_default();
        let line_items = search_line_items(
            ticker,
            vec![
                "free_cash_flow".to_string(),
                "ebit".to_string(),
                "interest_expense".to_string(),
                "capital_expenditure".to_string(),
                "depreciation_and_amortization".to_string(),
                "outstanding_shares".to_string(),
                "net_income".to_string(),
                "total_debt".to_string(),
            ],
            end_date,
            "ttm",
            5,
            api_key,
        )
        .await
        .unwrap_or_default();

        let market_cap = get_market_cap(ticker, end_date, api_key)
            .await
            .unwrap_or(None)
            .unwrap_or(0.0);

        // Sub-analyses
        let growth = analyze_growth_and_reinvestment(&metrics, &line_items);
        let risk = analyze_risk_profile(&metrics, &line_items);
        let intrinsic = calculate_intrinsic_value_dcf(&metrics, &line_items, &risk);
        let relative = analyze_relative_valuation(&metrics);

        let total_score = growth.score + risk.score + relative.score;
        let max_score = growth.max_score + risk.max_score + relative.max_score;

        let intrinsic_value = intrinsic.intrinsic_value.unwrap_or(0.0);
        let margin_of_safety = if intrinsic_value > 0.0 && market_cap > 0.0 {
            Some((intrinsic_value - market_cap) / market_cap)
        } else {
            None
        };

        // Decision rules: Act with 25% margin of safety bounds
        let signal = match margin_of_safety {
            Some(mos) if mos >= 0.25 => "bullish",
            Some(mos) if mos <= -0.25 => "bearish",
            _ => "neutral",
        };

        let facts = serde_json::json!({
            "signal": signal,
            "score": total_score,
            "max_score": max_score,
            "margin_of_safety": margin_of_safety,
            "growth_analysis": {
                "score": growth.score,
                "max_score": growth.max_score,
                "details": growth.details,
            },
            "risk_analysis": {
                "score": risk.score,
                "max_score": risk.max_score,
                "details": risk.details,
                "beta": risk.beta,
                "cost_of_equity": risk.cost_of_equity,
            },
            "relative_val_analysis": {
                "score": relative.score,
                "max_score": relative.max_score,
                "details": relative.details,
            },
            "intrinsic_val_analysis": {
                "intrinsic_value": intrinsic.intrinsic_value,
                "intrinsic_per_share": intrinsic.intrinsic_per_share,
                "details": intrinsic.details,
            },
            "market_cap": market_cap,
        });

        let output = generate_damodaran_output(ticker, &facts, state, agent_id).await?;

        damodaran_signals.insert(
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
            serde_json::Value::Object(damodaran_signals),
        );
    }

    Ok(())
}

pub struct DamodaranSubResult {
    pub score: i32,
    pub max_score: i32,
    pub details: String,
}

pub fn analyze_growth_and_reinvestment(
    metrics: &[FinancialMetrics],
    line_items: &[LineItem],
) -> DamodaranSubResult {
    let max_score = 4;
    let mut score = 0;
    let mut details = Vec::new();

    if metrics.len() < 2 {
        return DamodaranSubResult {
            score: 0,
            max_score,
            details: "Insufficient history".to_string(),
        };
    }

    // Revenue CAGR (oldest to latest)
    let revs: Vec<f64> = metrics.iter().rev().filter_map(|m| m.revenue).collect();
    let mut cagr: Option<f64> = None;
    if revs.len() >= 2 && revs[0] > 0.0 {
        let ratio = revs[revs.len() - 1] / revs[0];
        cagr = Some(ratio.powf(1.0 / (revs.len() - 1) as f64) - 1.0);
    }

    if let Some(c) = cagr {
        if c > 0.08 {
            score += 2;
            details.push(format!("Revenue CAGR {:.1}% (> 8%)", c * 100.0));
        } else if c > 0.03 {
            score += 1;
            details.push(format!("Revenue CAGR {:.1}% (> 3%)", c * 100.0));
        } else {
            details.push(format!("Sluggish revenue CAGR {:.1}%", c * 100.0));
        }
    } else {
        details.push("Revenue data incomplete".to_string());
    }

    // FCFF growth (free cash flow trend, oldest to newest)
    let fcfs: Vec<f64> = line_items
        .iter()
        .rev()
        .filter_map(|li| li.free_cash_flow)
        .collect();
    if fcfs.len() >= 2 && fcfs[fcfs.len() - 1] > fcfs[0] {
        score += 1;
        details.push("Positive FCFF growth".to_string());
    } else {
        details.push("Flat or declining FCFF".to_string());
    }

    // Reinvestment efficiency (ROIC vs 10% hurdle)
    if let Some(roic) = metrics[0].return_on_equity {
        // In models.rs return_on_equity is used if return_on_invested_capital is missing
        if roic > 0.10 {
            score += 1;
            details.push(format!("ROIC {:.1}% (> 10%)", roic * 100.0));
        }
    }

    DamodaranSubResult {
        score,
        max_score,
        details: details.join("; "),
    }
}

pub struct DamodaranRiskResult {
    pub score: i32,
    pub max_score: i32,
    pub details: String,
    pub beta: Option<f64>,
    pub cost_of_equity: f64,
}

pub fn analyze_risk_profile(
    metrics: &[FinancialMetrics],
    _line_items: &[LineItem],
) -> DamodaranRiskResult {
    let max_score = 3;
    let mut score = 0;
    let mut details = Vec::new();

    if metrics.is_empty() {
        return DamodaranRiskResult {
            score: 0,
            max_score,
            details: "No metrics".to_string(),
            beta: None,
            cost_of_equity: 0.09,
        };
    }

    let latest = &metrics[0];

    // Beta
    let beta = latest.beta;
    if let Some(b) = beta {
        if b < 1.3 {
            score += 1;
            details.push(format!("Beta {:.2}", b));
        } else {
            details.push(format!("High beta {:.2}", b));
        }
    } else {
        details.push("Beta NA".to_string());
    }

    // Debt/Equity
    if let Some(de) = latest.debt_to_equity {
        if de < 1.0 {
            score += 1;
            details.push(format!("D/E {:.1}", de));
        } else {
            details.push(format!("High D/E {:.1}", de));
        }
    } else {
        details.push("D/E NA".to_string());
    }

    // Interest coverage (EBIT / Interest Expense)
    if let (Some(ebit), Some(interest)) = (latest.operating_income, latest.debt_to_equity) {
        // Proxy if interest is not in metrics
        let coverage = if interest != 0.0 {
            ebit / interest.abs()
        } else {
            0.0
        };
        if coverage > 3.0 {
            score += 1;
            details.push(format!("Interest coverage x {:.1}", coverage));
        } else {
            details.push(format!("Weak coverage x {:.1}", coverage));
        }
    } else {
        details.push("Interest coverage NA".to_string());
    }

    let cost_of_equity = estimate_cost_of_equity(beta);

    DamodaranRiskResult {
        score,
        max_score,
        details: details.join("; "),
        beta,
        cost_of_equity,
    }
}

pub fn estimate_cost_of_equity(beta: Option<f64>) -> f64 {
    let risk_free = 0.04;
    let erp = 0.05;
    let b = beta.unwrap_or(1.0);
    risk_free + b * erp
}

pub fn analyze_relative_valuation(metrics: &[FinancialMetrics]) -> DamodaranSubResult {
    let max_score = 1;

    if metrics.len() < 5 {
        return DamodaranSubResult {
            score: 0,
            max_score,
            details: "Insufficient P/E history".to_string(),
        };
    }

    let mut pes: Vec<f64> = metrics
        .iter()
        .filter_map(|m| m.price_to_earnings_ratio)
        .collect();
    if pes.len() < 5 {
        return DamodaranSubResult {
            score: 0,
            max_score,
            details: "P/E data sparse".to_string(),
        };
    }

    let ttm_pe = pes[0];
    pes.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let median_pe = pes[pes.len() / 2];

    let (score, desc) = if ttm_pe < 0.7 * median_pe {
        (
            1,
            format!("P/E {:.1} vs. median {:.1} (cheap)", ttm_pe, median_pe),
        )
    } else if ttm_pe > 1.3 * median_pe {
        (
            -1,
            format!("P/E {:.1} vs. median {:.1} (expensive)", ttm_pe, median_pe),
        )
    } else {
        (0, "P/E inline with history".to_string())
    };

    DamodaranSubResult {
        score,
        max_score,
        details: desc,
    }
}

pub struct DamodaranValResult {
    pub intrinsic_value: Option<f64>,
    pub intrinsic_per_share: Option<f64>,
    pub details: Vec<String>,
}

pub fn calculate_intrinsic_value_dcf(
    metrics: &[FinancialMetrics],
    line_items: &[LineItem],
    risk_analysis: &DamodaranRiskResult,
) -> DamodaranValResult {
    if metrics.len() < 2 || line_items.is_empty() {
        return DamodaranValResult {
            intrinsic_value: None,
            intrinsic_per_share: None,
            details: vec!["Insufficient data".to_string()],
        };
    }

    let latest_m = &metrics[0];
    let fcff0 = latest_m.free_cash_flow.unwrap_or(0.0);
    let shares = line_items[0].outstanding_shares.unwrap_or(0) as f64;

    if fcff0 <= 0.0 || shares <= 0.0 {
        return DamodaranValResult {
            intrinsic_value: None,
            intrinsic_per_share: None,
            details: vec!["Missing positive FCFF or share count".to_string()],
        };
    }

    // Growth projection CAGR (oldest to newest)
    let revs: Vec<f64> = metrics.iter().rev().filter_map(|m| m.revenue).collect();
    let base_growth = if revs.len() >= 2 && revs[0] > 0.0 {
        let cagr = (revs[revs.len() - 1] / revs[0]).powf(1.0 / (revs.len() - 1) as f64) - 1.0;
        cagr.min(0.12)
    } else {
        0.04
    };

    let terminal_growth = 0.025;
    let years = 10;
    let discount = risk_analysis.cost_of_equity;

    let mut pv_sum = 0.0;
    let mut g = base_growth;
    let g_step = (terminal_growth - base_growth) / (years - 1) as f64;

    for yr in 1..=years {
        let fcff_t = fcff0 * (1.0 + g);
        let pv = fcff_t / (1.0 + discount).powi(yr);
        pv_sum += pv;
        g += g_step;
    }

    // Terminal Value
    let tv = (fcff0 * (1.0 + terminal_growth))
        / (discount - terminal_growth)
        / (1.0 + discount).powi(years);
    let equity_value = pv_sum + tv;
    let intrinsic_per_share = equity_value / shares;

    DamodaranValResult {
        intrinsic_value: Some(equity_value),
        intrinsic_per_share: Some(intrinsic_per_share),
        details: vec!["FCFF DCF completed".to_string()],
    }
}

pub async fn generate_damodaran_output(
    ticker: &str,
    facts: &serde_json::Value,
    state: &AgentState,
    agent_id: &str,
) -> Result<AswathDamodaranSignal> {
    let system_prompt = "You are Aswath Damodaran, Professor of Finance at NYU Stern.\n\
        Use your valuation framework to issue trading signals on US equities:\n\
        - Connect the business story with numbers: revenue growth, margins, reinvestment, risk.\n\
        - Conclude with intrinsic value based on your FCFF DCF, MOS, and relative valuation.\n\
        Return JSON matching exactly: {\"signal\": \"bullish\" | \"bearish\" | \"neutral\", \"confidence\": int, \"reasoning\": \"short\"}";

    let user_prompt = format!(
        "Ticker: {}\nFacts:\n{}\n\nReturn structured JSON output.",
        ticker,
        serde_json::to_string_pretty(facts)?
    );

    call_llm(system_prompt, &user_prompt, Some(agent_id), Some(state), 3).await
}
