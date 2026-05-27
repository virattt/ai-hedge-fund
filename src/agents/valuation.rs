// Source: src/agents/valuation.py
//! Sibling to src/agents/valuation.py
//! Implements four complementary valuation methodologies: DCF (multi-scenario), Owner Earnings, EV/EBITDA, and Residual Income.

use anyhow::{Result, Context};
use crate::graph::state::AgentState;
use crate::tools::api::{get_financial_metrics, get_market_cap, search_line_items};
use crate::data::models::{FinancialMetrics, LineItem};

pub async fn valuation_analyst_agent(state: &mut AgentState, agent_id: &str) -> Result<()> {
    println!("Running Valuation Analyst Agent: {}", agent_id);

    let end_date_str = state.data.get("end_date")
        .and_then(|v| v.as_str())
        .context("Missing end_date in valuation_analyst_agent")?
        .to_string();

    let tickers_json = state.data.get("tickers")
        .context("Missing tickers in valuation_analyst_agent")?;
    let tickers: Vec<String> = serde_json::from_value(tickers_json.clone())?;

    let api_key = state.metadata.get("FINANCIAL_DATASETS_API_KEY")
        .and_then(|v| v.as_str());

    let mut valuation_analysis = serde_json::Map::new();

    for ticker in &tickers {
        // Fetch financial data
        let financial_metrics = get_financial_metrics(ticker, &end_date_str, "ttm", 8, api_key).await.unwrap_or_default();
        if financial_metrics.is_empty() {
            continue;
        }
        let most_recent = &financial_metrics[0];

        let line_items = search_line_items(
            ticker,
            vec![
                "free_cash_flow".to_string(),
                "net_income".to_string(),
                "depreciation_and_amortization".to_string(),
                "capital_expenditure".to_string(),
                "working_capital".to_string(),
                "total_debt".to_string(),
                "cash_and_equivalents".to_string(),
                "interest_expense".to_string(),
                "revenue".to_string(),
                "operating_income".to_string(),
                "ebit".to_string(),
                "ebitda".to_string(),
            ],
            &end_date_str,
            "ttm",
            8,
            api_key,
        ).await.unwrap_or_default();

        if line_items.len() < 2 {
            continue;
        }

        let li_curr = &line_items[0];
        let li_prev = &line_items[1];

        let wc_change = match (li_curr.working_capital, li_prev.working_capital) {
            (Some(a), Some(b)) => a - b,
            _ => 0.0,
        };

        // Owner Earnings valuation
        let owner_val = calculate_owner_earnings_value(
            li_curr.net_income,
            li_curr.depreciation_and_amortization,
            li_curr.capital_expenditure,
            Some(wc_change),
            most_recent.earnings_growth.unwrap_or(0.05),
        );

        // WACC calculation
        let wacc = calculate_wacc(
            most_recent.market_cap.unwrap_or(0.0),
            li_curr.total_debt,
            li_curr.cash_and_equivalents,
            most_recent.interest_coverage,
            most_recent.debt_to_equity,
        );

        // Build FCF history
        let fcf_history: Vec<f64> = line_items.iter().filter_map(|li| li.free_cash_flow).collect();

        // Enhanced DCF with scenarios
        let dcf_results = calculate_dcf_scenarios(
            &fcf_history,
            most_recent.revenue_growth,
            most_recent.free_cash_flow_growth,
            most_recent.earnings_growth,
            wacc,
            most_recent.market_cap.unwrap_or(0.0),
            most_recent.revenue_growth,
        );
        let dcf_val = dcf_results.expected_value;

        // EV/EBITDA implied equity value
        let ev_ebitda_val = calculate_ev_ebitda_value(&financial_metrics);

        // Residual Income Model
        let rim_val = calculate_residual_income_value(
            most_recent.market_cap,
            li_curr.net_income,
            most_recent.price_to_book_ratio,
            most_recent.book_value_growth.unwrap_or(0.03),
        );

        // Fetch current market cap for gap calculation
        let market_cap = get_market_cap(ticker, &end_date_str, api_key).await.unwrap_or(None).unwrap_or(0.0);
        if market_cap <= 0.0 {
            continue;
        }

        // Aggregate with weights
        let methods: Vec<(&str, f64, f64)> = vec![
            ("dcf", dcf_val, 0.35),
            ("owner_earnings", owner_val, 0.35),
            ("ev_ebitda", ev_ebitda_val, 0.20),
            ("residual_income", rim_val, 0.10),
        ];

        let total_weight: f64 = methods.iter().filter(|&&(_, v, _)| v > 0.0).map(|&(_, _, w)| w).sum();
        if total_weight == 0.0 {
            continue;
        }

        let weighted_gap: f64 = methods.iter()
            .filter(|&&(_, v, _)| v > 0.0)
            .map(|&(_, v, w)| {
                let gap = (v - market_cap) / market_cap;
                w * gap
            })
            .sum::<f64>() / total_weight;

        let signal = if weighted_gap > 0.15 {
            "bullish"
        } else if weighted_gap < -0.15 {
            "bearish"
        } else {
            "neutral"
        };

        let confidence = ((weighted_gap.abs() / 0.30 * 100.0).min(100.0).round()) as u32;

        // Build reasoning for each method
        let mut method_details = serde_json::Map::new();
        for &(name, value, weight) in &methods {
            if value > 0.0 {
                let gap = (value - market_cap) / market_cap;
                let method_signal = if gap > 0.15 { "bullish" } else if gap < -0.15 { "bearish" } else { "neutral" };
                let details_str = format!(
                    "Value: ${:.2}, Market Cap: ${:.2}, Gap: {:.1}%, Weight: {:.0}%",
                    value, market_cap, gap * 100.0, weight * 100.0
                );
                method_details.insert(
                    format!("{}_analysis", name),
                    serde_json::json!({
                        "signal": method_signal,
                        "details": details_str,
                    }),
                );
            }
        }

        method_details.insert(
            "dcf_scenario_analysis".to_string(),
            serde_json::json!({
                "bear_case": format!("${:.2}", dcf_results.downside),
                "base_case": format!("${:.2}", dcf_results.scenarios_base),
                "bull_case": format!("${:.2}", dcf_results.upside),
                "wacc_used": format!("{:.1}%", wacc * 100.0),
                "fcf_periods_analyzed": fcf_history.len(),
            }),
        );

        valuation_analysis.insert(
            ticker.clone(),
            serde_json::json!({
                "signal": signal,
                "confidence": confidence,
                "reasoning": serde_json::Value::Object(method_details),
            }),
        );
    }

    let analyst_signals = state.data.entry("analyst_signals".to_string())
        .or_insert_with(|| serde_json::json!({}));
    if let Some(obj) = analyst_signals.as_object_mut() {
        obj.insert(agent_id.to_string(), serde_json::Value::Object(valuation_analysis));
    }

    Ok(())
}

/// Buffett Owner Earnings valuation with margin of safety.
pub fn calculate_owner_earnings_value(
    net_income: Option<f64>,
    depreciation: Option<f64>,
    capex: Option<f64>,
    working_capital_change: Option<f64>,
    growth_rate: f64,
) -> f64 {
    let (ni, dep, cap, wc) = match (net_income, depreciation, capex, working_capital_change) {
        (Some(a), Some(b), Some(c), Some(d)) => (a, b, c, d),
        _ => return 0.0,
    };

    let owner_earnings = ni + dep - cap - wc;
    if owner_earnings <= 0.0 {
        return 0.0;
    }

    let required_return = 0.15_f64;
    let margin_of_safety = 0.25_f64;
    let num_years = 5_i32;

    let mut pv = 0.0_f64;
    for yr in 1_i32..=num_years {
        let future = owner_earnings * (1.0_f64 + growth_rate).powi(yr);
        pv += future / (1.0_f64 + required_return).powi(yr);
    }

    let terminal_growth = growth_rate.min(0.03_f64);
    let term_fcf = owner_earnings * (1.0_f64 + growth_rate).powi(num_years) * (1.0_f64 + terminal_growth);
    let term_val = term_fcf / (required_return - terminal_growth);
    let pv_term = term_val / (1.0_f64 + required_return).powi(num_years);

    let intrinsic = pv + pv_term;
    intrinsic * (1.0 - margin_of_safety)
}

/// Classic DCF on FCF with constant growth and terminal value.
pub fn calculate_intrinsic_value(
    free_cash_flow: Option<f64>,
    growth_rate: f64,
    discount_rate: f64,
    terminal_growth_rate: f64,
    num_years: i32,
) -> f64 {
    match free_cash_flow {
        Some(fcf) if fcf > 0.0 => {
            let mut pv = 0.0_f64;
            for yr in 1_i32..=num_years {
                let fcft = fcf * (1.0_f64 + growth_rate).powi(yr);
                pv += fcft / (1.0_f64 + discount_rate).powi(yr);
            }
            let term_val = (fcf * (1.0_f64 + growth_rate).powi(num_years) * (1.0_f64 + terminal_growth_rate))
                / (discount_rate - terminal_growth_rate);
            let pv_term = term_val / (1.0_f64 + discount_rate).powi(num_years);
            pv + pv_term
        }
        _ => 0.0,
    }
}

/// Implied equity value via median EV/EBITDA multiple.
pub fn calculate_ev_ebitda_value(financial_metrics: &[FinancialMetrics]) -> f64 {
    if financial_metrics.is_empty() {
        return 0.0;
    }
    let m0 = &financial_metrics[0];
    let ev = match m0.enterprise_value { Some(v) if v > 0.0 => v, _ => return 0.0 };
    let ev_ebitda_ratio = match m0.enterprise_value_to_ebitda_ratio { Some(v) if v > 0.0 => v, _ => return 0.0 };
    let ebitda_now = ev / ev_ebitda_ratio;

    let multiples: Vec<f64> = financial_metrics.iter()
        .filter_map(|m| m.enterprise_value_to_ebitda_ratio)
        .filter(|&r| r > 0.0)
        .collect();
    if multiples.is_empty() {
        return 0.0;
    }

    let mut sorted = multiples.clone();
    sorted.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let med_mult = if sorted.len() % 2 == 0 {
        (sorted[sorted.len() / 2 - 1] + sorted[sorted.len() / 2]) / 2.0
    } else {
        sorted[sorted.len() / 2]
    };

    let ev_implied = med_mult * ebitda_now;
    let net_debt = ev - m0.market_cap.unwrap_or(0.0);
    (ev_implied - net_debt).max(0.0)
}

/// Residual Income Model (Edwards-Bell-Ohlson).
pub fn calculate_residual_income_value(
    market_cap: Option<f64>,
    net_income: Option<f64>,
    price_to_book_ratio: Option<f64>,
    book_value_growth: f64,
) -> f64 {
    match (market_cap, net_income, price_to_book_ratio) {
        (Some(mc), Some(ni), Some(pb)) if mc > 0.0 && ni > 0.0 && pb > 0.0 => {
            let cost_of_equity = 0.10_f64;
            let terminal_growth_rate = 0.03_f64;
            let num_years = 5_i32;

            let book_val = mc / pb;
            let ri0 = ni - cost_of_equity * book_val;
            if ri0 <= 0.0 {
                return 0.0;
            }

            let mut pv_ri = 0.0_f64;
            for yr in 1_i32..=num_years {
                let ri_t = ri0 * (1.0_f64 + book_value_growth).powi(yr);
                pv_ri += ri_t / (1.0_f64 + cost_of_equity).powi(yr);
            }

            let term_ri = ri0 * (1.0_f64 + book_value_growth).powi(num_years + 1)
                / (cost_of_equity - terminal_growth_rate);
            let pv_term = term_ri / (1.0_f64 + cost_of_equity).powi(num_years);

            let intrinsic = book_val + pv_ri + pv_term;
            intrinsic * 0.8 // 20% margin of safety
        }
        _ => 0.0,
    }
}

/// Calculate WACC using available financial data.
pub fn calculate_wacc(
    market_cap: f64,
    total_debt: Option<f64>,
    cash: Option<f64>,
    interest_coverage: Option<f64>,
    _debt_to_equity: Option<f64>,
) -> f64 {
    let risk_free_rate = 0.045_f64;
    let market_risk_premium = 0.06_f64;
    let beta_proxy = 1.0_f64;

    let cost_of_equity = risk_free_rate + beta_proxy * market_risk_premium;

    let cost_of_debt = match interest_coverage {
        Some(ic) if ic > 0.0 => (risk_free_rate + 10.0 / ic).max(risk_free_rate + 0.01),
        _ => risk_free_rate + 0.05,
    };

    let net_debt = (total_debt.unwrap_or(0.0) - cash.unwrap_or(0.0)).max(0.0);
    let total_value = market_cap + net_debt;

    let wacc = if total_value > 0.0 {
        let weight_equity = market_cap / total_value;
        let weight_debt = net_debt / total_value;
        weight_equity * cost_of_equity + weight_debt * cost_of_debt * 0.75
    } else {
        cost_of_equity
    };

    wacc.clamp(0.06, 0.20)
}

/// FCF volatility (coefficient of variation).
fn calculate_fcf_volatility(fcf_history: &[f64]) -> f64 {
    if fcf_history.len() < 3 {
        return 0.5;
    }
    let positive: Vec<f64> = fcf_history.iter().cloned().filter(|&f| f > 0.0).collect();
    if positive.len() < 2 {
        return 0.8;
    }
    let n = positive.len() as f64;
    let mean = positive.iter().sum::<f64>() / n;
    let variance = positive.iter().map(|&f| (f - mean).powi(2)).sum::<f64>() / n;
    let std = variance.sqrt();
    if mean > 0.0 { (std / mean).min(1.0) } else { 0.8 }
}

/// Enhanced multi-stage DCF.
fn calculate_enhanced_dcf_value(
    fcf_history: &[f64],
    revenue_growth: f64,
    wacc: f64,
    market_cap: f64,
) -> f64 {
    if fcf_history.is_empty() || fcf_history[0] <= 0.0 {
        return 0.0;
    }

    let fcf_current = fcf_history[0];
    let n_avg = fcf_history.len().min(3);
    let fcf_avg_3yr = fcf_history[..n_avg].iter().sum::<f64>() / n_avg as f64;
    let fcf_volatility = calculate_fcf_volatility(fcf_history);

    // Stage 1: High Growth (Years 1-3)
    let mut high_growth = revenue_growth.min(0.25);
    if market_cap > 50_000_000_000.0 {
        high_growth = high_growth.min(0.10);
    }
    let transition_growth = (high_growth + 0.03) / 2.0;
    let terminal_growth = (high_growth * 0.6).min(0.03);

    let base_fcf = fcf_current.max(fcf_avg_3yr * 0.85);
    let mut pv = 0.0_f64;

    for year in 1_i32..=3_i32 {
        let projected = base_fcf * (1.0_f64 + high_growth).powi(year);
        pv += projected / (1.0_f64 + wacc).powi(year);
    }

    for year in 4_i32..=7_i32 {
        let transition_rate = transition_growth * (8 - year) as f64 / 4.0;
        let projected = base_fcf * (1.0_f64 + high_growth).powi(3) * (1.0_f64 + transition_rate).powi(year - 3);
        pv += projected / (1.0_f64 + wacc).powi(year);
    }

    let final_fcf = base_fcf * (1.0_f64 + high_growth).powi(3) * (1.0_f64 + transition_growth).powi(4);
    let actual_terminal = if wacc <= terminal_growth { wacc * 0.8 } else { terminal_growth };
    let terminal_value = (final_fcf * (1.0_f64 + actual_terminal)) / (wacc - actual_terminal);
    let pv_terminal = terminal_value / (1.0_f64 + wacc).powi(7);

    let quality_factor = (1.0 - fcf_volatility * 0.5).max(0.7);
    (pv + pv_terminal) * quality_factor
}

pub struct DcfResults {
    pub expected_value: f64,
    pub scenarios_base: f64,
    pub upside: f64,
    pub downside: f64,
    pub range: f64,
}

/// Calculate DCF under bear/base/bull scenarios.
pub fn calculate_dcf_scenarios(
    fcf_history: &[f64],
    _revenue_growth_metric: Option<f64>,
    _fcf_growth_metric: Option<f64>,
    _earnings_growth_metric: Option<f64>,
    wacc: f64,
    market_cap: f64,
    revenue_growth: Option<f64>,
) -> DcfResults {
    let base_rev_growth = revenue_growth.unwrap_or(0.05);

    let bear = calculate_enhanced_dcf_value(fcf_history, base_rev_growth * 0.5, wacc * 1.2, market_cap);
    let base = calculate_enhanced_dcf_value(fcf_history, base_rev_growth * 1.0, wacc * 1.0, market_cap);
    let bull = calculate_enhanced_dcf_value(fcf_history, base_rev_growth * 1.5, wacc * 0.9, market_cap);

    let expected = bear * 0.2 + base * 0.6 + bull * 0.2;

    DcfResults {
        expected_value: expected,
        scenarios_base: base,
        upside: bull,
        downside: bear,
        range: bull - bear,
    }
}
