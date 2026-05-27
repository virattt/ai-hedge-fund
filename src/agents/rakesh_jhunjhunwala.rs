// Source: src/agents/rakesh_jhunjhunwala.py
//! Sibling to src/agents/rakesh_jhunjhunwala.py
//! Analyzes stocks using Rakesh Jhunjhunwala's compound growth, profitability moats, and valuation principles.

use crate::data::models::LineItem;
use crate::graph::state::AgentState;
use crate::tools::api::{get_market_cap, search_line_items};
use crate::utils::llm::call_llm;
use anyhow::{Context, Result};

#[derive(Debug, serde::Serialize, serde::Deserialize, Default)]
pub struct RakeshJhunjhunwalaSignal {
    pub signal: String,  // "bullish" | "bearish" | "neutral"
    pub confidence: u32, // 0-100
    pub reasoning: String,
}

pub async fn rakesh_jhunjhunwala_agent(state: &mut AgentState, agent_id: &str) -> Result<()> {
    println!("Running Rakesh Jhunjhunwala Agent: {}", agent_id);

    let end_date = state
        .data
        .get("end_date")
        .and_then(|v| v.as_str())
        .context("Missing end_date in rakesh_jhunjhunwala_agent")?;

    let tickers_json = state
        .data
        .get("tickers")
        .context("Missing tickers in rakesh_jhunjhunwala_agent")?;
    let tickers: Vec<String> = serde_json::from_value(tickers_json.clone())?;

    let api_key = state
        .metadata
        .get("FINANCIAL_DATASETS_API_KEY")
        .and_then(|v| v.as_str());

    let mut jhunjhunwala_analysis = serde_json::Map::new();

    for ticker in &tickers {
        // Fetch raw data
        let financial_line_items = search_line_items(
            ticker,
            vec![
                "net_income".to_string(),
                "earnings_per_share".to_string(),
                "ebit".to_string(),
                "operating_income".to_string(),
                "revenue".to_string(),
                "operating_margin".to_string(),
                "total_assets".to_string(),
                "total_liabilities".to_string(),
                "current_assets".to_string(),
                "current_liabilities".to_string(),
                "free_cash_flow".to_string(),
                "dividends_and_other_cash_distributions".to_string(),
                "issuance_or_purchase_of_equity_shares".to_string(),
            ],
            end_date,
            "annual",
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
        let growth = analyze_growth(&financial_line_items);
        let profitability = analyze_profitability(&financial_line_items);
        let balance_sheet = analyze_balance_sheet(&financial_line_items);
        let cash_flow = analyze_cash_flow(&financial_line_items);
        let management = analyze_management_actions(&financial_line_items);

        let total_score = growth.score
            + profitability.score
            + balance_sheet.score
            + cash_flow.score
            + management.score;
        let max_score = 24.0;

        let intrinsic_value = calculate_intrinsic_value(&financial_line_items);
        let margin_of_safety = if let Some(iv) = intrinsic_value {
            if market_cap > 0.0 {
                Some((iv - market_cap) / market_cap)
            } else {
                None
            }
        } else {
            None
        };

        // Decision rules: Act with 30% margin of safety or tie-breaker quality check
        let signal = match margin_of_safety {
            Some(mos) if mos >= 0.30 => "bullish",
            Some(mos) if mos <= -0.30 => "bearish",
            _ => {
                let quality_score = assess_quality_metrics(&financial_line_items);
                if quality_score >= 0.7 && total_score as f64 >= max_score * 0.6 {
                    "bullish"
                } else if quality_score <= 0.4 || total_score as f64 <= max_score * 0.3 {
                    "bearish"
                } else {
                    "neutral"
                }
            }
        };

        let _confidence = match margin_of_safety {
            Some(mos) => (mos.abs() * 150.0).clamp(20.0, 95.0).round() as u32,
            None => (total_score as f64 / max_score * 100.0)
                .clamp(10.0, 80.0)
                .round() as u32,
        };

        let intrinsic_value_analysis =
            analyze_rakesh_jhunjhunwala_style(&financial_line_items, intrinsic_value, market_cap);

        let facts = serde_json::json!({
            "signal": signal,
            "score": total_score,
            "max_score": max_score,
            "margin_of_safety": margin_of_safety,
            "growth_analysis": {
                "score": growth.score,
                "details": growth.details,
            },
            "profitability_analysis": {
                "score": profitability.score,
                "details": profitability.details,
            },
            "balancesheet_analysis": {
                "score": balance_sheet.score,
                "details": balance_sheet.details,
            },
            "cashflow_analysis": {
                "score": cash_flow.score,
                "details": cash_flow.details,
            },
            "management_analysis": {
                "score": management.score,
                "details": management.details,
            },
            "intrinsic_value_analysis": intrinsic_value_analysis,
            "intrinsic_value": intrinsic_value,
            "market_cap": market_cap,
        });

        let output = generate_jhunjhunwala_output(ticker, &facts, state, agent_id).await?;

        jhunjhunwala_analysis.insert(
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
            serde_json::Value::Object(jhunjhunwala_analysis),
        );
    }

    Ok(())
}

pub struct JhunjhunwalaSubResult {
    pub score: u32,
    pub details: String,
}

pub fn analyze_profitability(financial_line_items: &[LineItem]) -> JhunjhunwalaSubResult {
    let mut score = 0;
    let mut details = Vec::new();

    if financial_line_items.is_empty() {
        return JhunjhunwalaSubResult {
            score: 0,
            details: "No profitability data available".to_string(),
        };
    }

    let latest = &financial_line_items[0];

    // 1. Return on Equity (ROE)
    if let (Some(net_inc), Some(assets), Some(liab)) = (
        latest.net_income,
        latest.total_assets,
        latest.total_liabilities,
    ) {
        if net_inc > 0.0 && assets > 0.0 {
            let equity = assets - liab;
            if equity > 0.0 {
                let roe = (net_inc / equity) * 100.0;
                if roe > 20.0 {
                    score += 3;
                    details.push(format!("Excellent ROE: {:.1}%", roe));
                } else if roe > 15.0 {
                    score += 2;
                    details.push(format!("Good ROE: {:.1}%", roe));
                } else if roe > 10.0 {
                    score += 1;
                    details.push(format!("Decent ROE: {:.1}%", roe));
                } else {
                    details.push(format!("Low ROE: {:.1}%", roe));
                }
            }
        }
    }

    // 2. Operating Margin
    if let (Some(op_inc), Some(rev)) = (latest.operating_income, latest.revenue) {
        if rev > 0.0 {
            let margin = (op_inc / rev) * 100.0;
            if margin > 20.0 {
                score += 2;
                details.push(format!("Excellent operating margin: {:.1}%", margin));
            } else if margin > 15.0 {
                score += 1;
                details.push(format!("Good operating margin: {:.1}%", margin));
            } else if margin > 0.0 {
                details.push(format!("Positive operating margin: {:.1}%", margin));
            }
        }
    }

    // 3. EPS CAGR (3-year)
    let eps_values: Vec<f64> = financial_line_items
        .iter()
        .filter_map(|item| item.earnings_per_share)
        .collect();
    if eps_values.len() >= 3 {
        let initial_eps = eps_values[eps_values.len() - 1];
        let final_eps = eps_values[0];
        let years = (eps_values.len() - 1) as f64;
        if initial_eps > 0.0 && final_eps > 0.0 {
            let eps_cagr = ((final_eps / initial_eps).powf(1.0 / years) - 1.0) * 100.0;
            if eps_cagr > 20.0 {
                score += 3;
                details.push(format!("High EPS CAGR: {:.1}%", eps_cagr));
            } else if eps_cagr > 15.0 {
                score += 2;
                details.push(format!("Good EPS CAGR: {:.1}%", eps_cagr));
            } else if eps_cagr > 10.0 {
                score += 1;
                details.push(format!("Moderate EPS CAGR: {:.1}%", eps_cagr));
            }
        }
    }

    JhunjhunwalaSubResult {
        score,
        details: details.join("; "),
    }
}

pub fn analyze_growth(financial_line_items: &[LineItem]) -> JhunjhunwalaSubResult {
    let mut score = 0;
    let mut details = Vec::new();

    if financial_line_items.len() < 3 {
        return JhunjhunwalaSubResult {
            score: 0,
            details: "Insufficient data for growth analysis".to_string(),
        };
    }

    // 1. Revenue CAGR Analysis
    let revenues: Vec<f64> = financial_line_items
        .iter()
        .filter_map(|item| item.revenue)
        .collect();
    if revenues.len() >= 3 {
        let initial = revenues[revenues.len() - 1];
        let final_val = revenues[0];
        let years = (revenues.len() - 1) as f64;
        if initial > 0.0 && final_val > 0.0 {
            let rev_cagr = ((final_val / initial).powf(1.0 / years) - 1.0) * 100.0;
            if rev_cagr > 20.0 {
                score += 3;
                details.push(format!("Excellent revenue CAGR: {:.1}%", rev_cagr));
            } else if rev_cagr > 15.0 {
                score += 2;
                details.push(format!("Good revenue CAGR: {:.1}%", rev_cagr));
            } else if rev_cagr > 10.0 {
                score += 1;
                details.push(format!("Moderate revenue CAGR: {:.1}%", rev_cagr));
            }
        }
    }

    // 2. Net Income CAGR Analysis
    let net_incomes: Vec<f64> = financial_line_items
        .iter()
        .filter_map(|item| item.net_income)
        .collect();
    if net_incomes.len() >= 3 {
        let initial = net_incomes[net_incomes.len() - 1];
        let final_val = net_incomes[0];
        let years = (net_incomes.len() - 1) as f64;
        if initial > 0.0 && final_val > 0.0 {
            let inc_cagr = ((final_val / initial).powf(1.0 / years) - 1.0) * 100.0;
            if inc_cagr > 25.0 {
                score += 3;
                details.push(format!("Excellent income CAGR: {:.1}%", inc_cagr));
            } else if inc_cagr > 20.0 {
                score += 2;
                details.push(format!("High income CAGR: {:.1}%", inc_cagr));
            } else if inc_cagr > 15.0 {
                score += 1;
                details.push(format!("Good income CAGR: {:.1}%", inc_cagr));
            }
        }
    }

    // 3. Revenue growth consistency YoY (reversing to chronological for YoY check)
    if revenues.len() >= 3 {
        let revs_chrono: Vec<f64> = revenues.iter().rev().cloned().collect();
        let mut declining_years = 0;
        for i in 1..revs_chrono.len() {
            if revs_chrono[i] < revs_chrono[i - 1] {
                declining_years += 1;
            }
        }
        let consistency = 1.0 - (declining_years as f64 / (revs_chrono.len() - 1) as f64);
        if consistency >= 0.8 {
            score += 1;
            details.push(format!(
                "Consistent growth pattern ({:.0}% of years)",
                consistency * 100.0
            ));
        }
    }

    JhunjhunwalaSubResult {
        score,
        details: details.join("; "),
    }
}

pub fn analyze_balance_sheet(financial_line_items: &[LineItem]) -> JhunjhunwalaSubResult {
    let mut score = 0;
    let mut details = Vec::new();

    if financial_line_items.is_empty() {
        return JhunjhunwalaSubResult {
            score: 0,
            details: "No balance sheet data".to_string(),
        };
    }

    let latest = &financial_line_items[0];

    // 1. Debt to Asset Ratio
    if let (Some(assets), Some(liabilities)) = (latest.total_assets, latest.total_liabilities) {
        if assets > 0.0 {
            let ratio = liabilities / assets;
            if ratio < 0.5 {
                score += 2;
                details.push(format!("Low debt ratio: {:.2}", ratio));
            } else if ratio < 0.7 {
                score += 1;
                details.push(format!("Moderate debt ratio: {:.2}", ratio));
            }
        }
    }

    // 2. Current Ratio
    if let (Some(cur_assets), Some(cur_liab)) = (latest.current_assets, latest.current_liabilities)
    {
        if cur_liab > 0.0 {
            let ratio = cur_assets / cur_liab;
            if ratio > 2.0 {
                score += 2;
                details.push(format!(
                    "Excellent liquidity with current ratio: {:.2}",
                    ratio
                ));
            } else if ratio > 1.5 {
                score += 1;
                details.push(format!("Good liquidity with current ratio: {:.2}", ratio));
            }
        }
    }

    JhunjhunwalaSubResult {
        score,
        details: details.join("; "),
    }
}

pub fn analyze_cash_flow(financial_line_items: &[LineItem]) -> JhunjhunwalaSubResult {
    let mut score = 0;
    let mut details = Vec::new();

    if financial_line_items.is_empty() {
        return JhunjhunwalaSubResult {
            score: 0,
            details: "No cash flow data".to_string(),
        };
    }

    let latest = &financial_line_items[0];

    if let Some(fcf) = latest.free_cash_flow {
        if fcf > 0.0 {
            score += 2;
            details.push(format!("Positive free cash flow: {:.0}", fcf));
        }
    }

    if let Some(div) = latest.dividends_and_other_cash_distributions {
        if div < 0.0 {
            score += 1;
            details.push("Company pays dividends to shareholders".to_string());
        }
    }

    JhunjhunwalaSubResult {
        score,
        details: details.join("; "),
    }
}

pub fn analyze_management_actions(financial_line_items: &[LineItem]) -> JhunjhunwalaSubResult {
    let mut score = 0;
    let mut details = Vec::new();

    if financial_line_items.is_empty() {
        return JhunjhunwalaSubResult {
            score: 0,
            details: "No management action data".to_string(),
        };
    }

    let latest = &financial_line_items[0];
    if let Some(issuance) = latest.issuance_or_purchase_of_equity_shares {
        if issuance < 0.0 {
            score += 2;
            details.push(format!("Company buying back shares: {:.0}", issuance.abs()));
        } else if issuance == 0.0 {
            score += 1;
            details.push("No recent share issuance or buyback".to_string());
        }
    }

    JhunjhunwalaSubResult {
        score,
        details: details.join("; "),
    }
}

pub fn assess_quality_metrics(financial_line_items: &[LineItem]) -> f64 {
    if financial_line_items.is_empty() {
        return 0.5;
    }

    let latest = &financial_line_items[0];
    let mut quality_factors = Vec::new();

    // 1. ROE Quality
    if let (Some(net_inc), Some(assets), Some(liab)) = (
        latest.net_income,
        latest.total_assets,
        latest.total_liabilities,
    ) {
        let equity = assets - liab;
        if equity > 0.0 && net_inc > 0.0 {
            let roe = net_inc / equity;
            if roe > 0.20 {
                quality_factors.push(1.0);
            } else if roe > 0.15 {
                quality_factors.push(0.8);
            } else if roe > 0.10 {
                quality_factors.push(0.6);
            } else {
                quality_factors.push(0.3);
            }
        } else {
            quality_factors.push(0.0);
        }
    } else {
        quality_factors.push(0.5);
    }

    // 2. Debt Levels
    if let (Some(assets), Some(liabilities)) = (latest.total_assets, latest.total_liabilities) {
        if assets > 0.0 {
            let ratio = liabilities / assets;
            if ratio < 0.3 {
                quality_factors.push(1.0);
            } else if ratio < 0.5 {
                quality_factors.push(0.7);
            } else if ratio < 0.7 {
                quality_factors.push(0.4);
            } else {
                quality_factors.push(0.1);
            }
        }
    } else {
        quality_factors.push(0.5);
    }

    // 3. Growth Consistency
    let net_incomes: Vec<f64> = financial_line_items
        .iter()
        .filter_map(|item| item.net_income)
        .collect();
    if net_incomes.len() >= 3 {
        let mut declining_years = 0;
        for i in 1..net_incomes.len() {
            if net_incomes[i] > net_incomes[i - 1] {
                // since newest first, declining means newest < older
                declining_years += 1;
            }
        }
        let consistency = 1.0 - (declining_years as f64 / (net_incomes.len() - 1) as f64);
        quality_factors.push(consistency);
    } else {
        quality_factors.push(0.5);
    }

    quality_factors.iter().sum::<f64>() / quality_factors.len() as f64
}

pub fn calculate_intrinsic_value(financial_line_items: &[LineItem]) -> Option<f64> {
    if financial_line_items.is_empty() {
        return None;
    }

    let latest = &financial_line_items[0];
    let net_income = latest.net_income.unwrap_or(0.0);
    if net_income <= 0.0 {
        return None;
    }

    let net_incomes: Vec<f64> = financial_line_items
        .iter()
        .filter_map(|item| item.net_income)
        .collect();
    if net_incomes.len() < 2 {
        return Some(net_income * 12.0);
    }

    let initial = net_incomes[net_incomes.len() - 1];
    let final_val = net_incomes[0];
    let years = (net_incomes.len() - 1) as f64;

    let historical_growth = if initial > 0.0 {
        (final_val / initial).powf(1.0 / years) - 1.0
    } else {
        0.05
    };

    let sustainable_growth = if historical_growth > 0.25 {
        0.20
    } else if historical_growth > 0.15 {
        historical_growth * 0.8
    } else if historical_growth > 0.05 {
        historical_growth * 0.9
    } else {
        0.05
    };

    let quality_score = assess_quality_metrics(financial_line_items);
    let (discount_rate, terminal_multiple): (f64, f64) = if quality_score >= 0.8 {
        (0.12, 18.0)
    } else if quality_score >= 0.6 {
        (0.15, 15.0)
    } else {
        (0.18, 12.0)
    };

    let mut dcf_value = 0.0_f64;
    for year in 1_i32..=5_i32 {
        let projected = net_income * (1.0_f64 + sustainable_growth).powi(year);
        let pv = projected / (1.0_f64 + discount_rate).powi(year);
        dcf_value += pv;
    }

    let year_5 = net_income * (1.0_f64 + sustainable_growth).powi(5);
    let terminal_value = (year_5 * terminal_multiple) / (1.0_f64 + discount_rate).powi(5);

    Some(dcf_value + terminal_value)
}

pub fn analyze_rakesh_jhunjhunwala_style(
    financial_line_items: &[LineItem],
    intrinsic_value: Option<f64>,
    current_price: f64,
) -> serde_json::Value {
    let profitability = analyze_profitability(financial_line_items);
    let growth = analyze_growth(financial_line_items);
    let balance_sheet = analyze_balance_sheet(financial_line_items);
    let cash_flow = analyze_cash_flow(financial_line_items);
    let management = analyze_management_actions(financial_line_items);

    let total_score = profitability.score
        + growth.score
        + balance_sheet.score
        + cash_flow.score
        + management.score;
    let valuation_gap = intrinsic_value.map(|iv| iv - current_price);

    serde_json::json!({
        "total_score": total_score,
        "details": format!(
            "Profitability: {}; Growth: {}; Balance Sheet: {}; Cash Flow: {}; Management: {}",
            profitability.details, growth.details, balance_sheet.details, cash_flow.details, management.details
        ),
        "intrinsic_value": intrinsic_value,
        "current_price": current_price,
        "valuation_gap": valuation_gap,
    })
}

pub async fn generate_jhunjhunwala_output(
    ticker: &str,
    facts: &serde_json::Value,
    state: &AgentState,
    agent_id: &str,
) -> Result<RakeshJhunjhunwalaSignal> {
    let system_prompt = "You are a Rakesh Jhunjhunwala AI agent making investment decisions using his principles:\n\
        - Emphasize economic moats, scalable profitability, and compound growth.\n\
        - Low leverage, strong returns on equity (>15-20%).\n\
        - Buy wonderful companies at a reasonable price, preferably with a large margin of safety.\n\
        Return JSON matching exactly: {\"signal\": \"bullish\" | \"bearish\" | \"neutral\", \"confidence\": int, \"reasoning\": \"short\"}";

    let user_prompt = format!(
        "Ticker: {}\nFacts:\n{}\n\nReturn structured JSON output.",
        ticker,
        serde_json::to_string_pretty(facts)?
    );

    call_llm(system_prompt, &user_prompt, Some(agent_id), Some(state), 3).await
}
