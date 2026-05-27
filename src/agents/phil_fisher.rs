// Source: src/agents/phil_fisher.py
//! Sibling to src/agents/phil_fisher.py
//! Analyzes stocks using Phil Fisher's long-term growth and scuttlebutt research principles.

use anyhow::{Result, Context};
use crate::graph::state::AgentState;
use crate::tools::api::{get_market_cap, search_line_items, get_insider_trades, get_company_news};
use crate::data::models::{FinancialMetrics, LineItem, InsiderTrade, CompanyNews};
use crate::utils::llm::call_llm;

#[derive(Debug, serde::Serialize, serde::Deserialize, Default)]
pub struct PhilFisherSignal {
    pub signal: String,      // "bullish" | "bearish" | "neutral"
    pub confidence: u32,     // 0-100
    pub reasoning: String,
}

pub async fn phil_fisher_agent(state: &mut AgentState, agent_id: &str) -> Result<()> {
    println!("Running Phil Fisher Agent: {}", agent_id);

    let end_date = state.data.get("end_date")
        .and_then(|v| v.as_str())
        .context("Missing end_date in phil_fisher_agent")?;
    
    let tickers_json = state.data.get("tickers")
        .context("Missing tickers in phil_fisher_agent")?;
    let tickers: Vec<String> = serde_json::from_value(tickers_json.clone())?;

    let api_key = state.metadata.get("FINANCIAL_DATASETS_API_KEY")
        .and_then(|v| v.as_str());

    let mut fisher_analysis = serde_json::Map::new();

    for ticker in &tickers {
        // Fetch raw data
        let financial_line_items = search_line_items(
            ticker,
            vec![
                "revenue".to_string(),
                "net_income".to_string(),
                "earnings_per_share".to_string(),
                "free_cash_flow".to_string(),
                "research_and_development".to_string(),
                "operating_income".to_string(),
                "operating_margin".to_string(),
                "gross_margin".to_string(),
                "total_debt".to_string(),
                "shareholders_equity".to_string(),
                "cash_and_equivalents".to_string(),
                "ebit".to_string(),
                "ebitda".to_string(),
            ],
            end_date,
            "annual",
            5,
            api_key,
        ).await.unwrap_or_default();

        let market_cap = get_market_cap(ticker, end_date, api_key).await.unwrap_or(None).unwrap_or(0.0);
        let insider_trades = get_insider_trades(ticker, end_date, None, 50, api_key).await.unwrap_or_default();
        let company_news = get_company_news(ticker, end_date, None, 50, api_key).await.unwrap_or_default();

        // Sub-analyses
        let growth_quality = analyze_fisher_growth_quality(&financial_line_items);
        let margins_stability = analyze_margins_stability(&financial_line_items);
        let mgmt_efficiency = analyze_management_efficiency_leverage(&financial_line_items);
        let valuation = analyze_fisher_valuation(&financial_line_items, market_cap);
        let insider = analyze_insider_activity(&insider_trades);
        let sentiment = analyze_sentiment(&company_news);

        // Weights: 30% Growth & Quality, 25% Margins, 20% Mgmt, 15% Valuation, 5% Insider, 5% Sentiment
        let total_score = growth_quality.score * 0.30
            + margins_stability.score * 0.25
            + mgmt_efficiency.score * 0.20
            + valuation.score * 0.15
            + insider.score * 0.05
            + sentiment.score * 0.05;

        let max_possible_score = 10.0;

        let signal = if total_score >= 7.5 {
            "bullish"
        } else if total_score <= 4.5 {
            "bearish"
        } else {
            "neutral"
        };

        let facts = serde_json::json!({
            "signal": signal,
            "score": (total_score * 100.0).round() / 100.0,
            "max_score": max_possible_score,
            "growth_quality": {
                "score": growth_quality.score,
                "details": growth_quality.details,
            },
            "margins_stability": {
                "score": margins_stability.score,
                "details": margins_stability.details,
            },
            "management_efficiency": {
                "score": mgmt_efficiency.score,
                "details": mgmt_efficiency.details,
            },
            "valuation_analysis": {
                "score": valuation.score,
                "details": valuation.details,
            },
            "insider_activity": {
                "score": insider.score,
                "details": insider.details,
            },
            "sentiment_analysis": {
                "score": sentiment.score,
                "details": sentiment.details,
            }
        });

        let output = generate_fisher_output(ticker, &facts, state, agent_id).await?;

        fisher_analysis.insert(
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
        obj.insert(agent_id.to_string(), serde_json::Value::Object(fisher_analysis));
    }

    Ok(())
}

pub struct FisherSubResult {
    pub score: f64,
    pub details: String,
}

pub fn analyze_fisher_growth_quality(financial_line_items: &[LineItem]) -> FisherSubResult {
    if financial_line_items.len() < 2 {
        return FisherSubResult { score: 0.0, details: "Insufficient financial data for growth/quality analysis".to_string() };
    }

    let mut details = Vec::new();
    let mut raw_score = 0;

    let revenues: Vec<f64> = financial_line_items.iter().filter_map(|item| item.revenue).collect();
    if revenues.len() >= 2 {
        let latest = revenues[0];
        let oldest = revenues[revenues.len() - 1];
        let num_years = (revenues.len() - 1) as f64;
        if oldest > 0.0 && latest > 0.0 {
            let rev_growth = (latest / oldest).powf(1.0 / num_years) - 1.0;
            if rev_growth > 0.20 {
                raw_score += 3;
                details.push(format!("Very strong annualized revenue growth: {:.1}%", rev_growth * 100.0));
            } else if rev_growth > 0.10 {
                raw_score += 2;
                details.push(format!("Moderate annualized revenue growth: {:.1}%", rev_growth * 100.0));
            } else if rev_growth > 0.03 {
                raw_score += 1;
                details.push(format!("Slight annualized revenue growth: {:.1}%", rev_growth * 100.0));
            } else {
                details.push(format!("Minimal or negative annualized revenue growth: {:.1}%", rev_growth * 100.0));
            }
        }
    }

    let eps_values: Vec<f64> = financial_line_items.iter().filter_map(|item| item.earnings_per_share).collect();
    if eps_values.len() >= 2 {
        let latest = eps_values[0];
        let oldest = eps_values[eps_values.len() - 1];
        let num_years = (eps_values.len() - 1) as f64;
        if oldest > 0.0 && latest > 0.0 {
            let eps_growth = (latest / oldest).powf(1.0 / num_years) - 1.0;
            if eps_growth > 0.20 {
                raw_score += 3;
                details.push(format!("Very strong annualized EPS growth: {:.1}%", eps_growth * 100.0));
            } else if eps_growth > 0.10 {
                raw_score += 2;
                details.push(format!("Moderate annualized EPS growth: {:.1}%", eps_growth * 100.0));
            } else if eps_growth > 0.03 {
                raw_score += 1;
                details.push(format!("Slight annualized EPS growth: {:.1}%", eps_growth * 100.0));
            } else {
                details.push(format!("Minimal or negative annualized EPS growth: {:.1}%", eps_growth * 100.0));
            }
        }
    }

    let rnd_values: Vec<f64> = financial_line_items.iter().filter_map(|item| item.research_and_development).collect();
    if !rnd_values.is_empty() && !revenues.is_empty() {
        let recent_rnd = rnd_values[0];
        let recent_rev = revenues[0];
        if recent_rev > 0.0 {
            let rnd_ratio = recent_rnd / recent_rev;
            if rnd_ratio >= 0.03 && rnd_ratio <= 0.15 {
                raw_score += 3;
                details.push(format!("R&D ratio {:.1}% indicates significant investment in future growth", rnd_ratio * 100.0));
            } else if rnd_ratio > 0.15 {
                raw_score += 2;
                details.push(format!("R&D ratio {:.1}% is very high", rnd_ratio * 100.0));
            } else if rnd_ratio > 0.0 {
                raw_score += 1;
                details.push(format!("R&D ratio {:.1}% is somewhat low but positive", rnd_ratio * 100.0));
            }
        }
    }

    let final_score = (raw_score as f64 / 9.0 * 10.0).min(10.0);
    FisherSubResult { score: final_score, details: details.join("; ") }
}

pub fn analyze_margins_stability(financial_line_items: &[LineItem]) -> FisherSubResult {
    if financial_line_items.len() < 2 {
        return FisherSubResult { score: 0.0, details: "Insufficient data for margin stability analysis".to_string() };
    }

    let mut details = Vec::new();
    let mut raw_score = 0;

    let op_margins: Vec<f64> = financial_line_items.iter().filter_map(|item| item.operating_margin).collect();
    if len_check(&op_margins) >= 2 {
        let oldest = op_margins[op_margins.len() - 1];
        let newest = op_margins[0];
        if newest >= oldest && oldest > 0.0 {
            raw_score += 2;
            details.push(format!("Operating margin stable or improving ({:.1}% -> {:.1}%)", oldest * 100.0, newest * 100.0));
        } else if newest > 0.0 {
            raw_score += 1;
            details.push("Operating margin positive but slightly declined".to_string());
        }
    }

    let gm_values: Vec<f64> = financial_line_items.iter().filter_map(|item| item.gross_margin).collect();
    if !gm_values.is_empty() {
        let recent = gm_values[0];
        if recent > 0.5 {
            raw_score += 2;
            details.push(format!("Strong gross margin: {:.1}%", recent * 100.0));
        } else if recent > 0.3 {
            raw_score += 1;
            details.push(format!("Moderate gross margin: {:.1}%", recent * 100.0));
        }
    }

    if op_margins.len() >= 3 {
        let n = op_margins.len() as f64;
        let mean = op_margins.iter().sum::<f64>() / n;
        let variance = op_margins.iter().map(|&m| (m - mean).powi(2)).sum::<f64>() / n;
        let stdev = variance.sqrt();

        if stdev < 0.02 {
            raw_score += 2;
            details.push("Operating margin extremely stable over multiple years".to_string());
        } else if stdev < 0.05 {
            raw_score += 1;
            details.push("Operating margin reasonably stable".to_string());
        }
    }

    let final_score = (raw_score as f64 / 6.0 * 10.0).min(10.0);
    FisherSubResult { score: final_score, details: details.join("; ") }
}

fn len_check<T>(v: &[T]) -> usize {
    v.len()
}

pub fn analyze_management_efficiency_leverage(financial_line_items: &[LineItem]) -> FisherSubResult {
    if financial_line_items.is_empty() {
        return FisherSubResult { score: 0.0, details: "No financial data for management efficiency".to_string() };
    }

    let mut details = Vec::new();
    let mut raw_score = 0;

    let ni_values: Vec<f64> = financial_line_items.iter().filter_map(|item| item.net_income).collect();
    let eq_values: Vec<f64> = financial_line_items.iter().filter_map(|item| item.shareholders_equity).collect();

    if !ni_values.is_empty() && ni_values.len() == eq_values.len() {
        let recent_ni = ni_values[0];
        let recent_eq = eq_values[0];
        if recent_ni > 0.0 && recent_eq > 0.0 {
            let roe = recent_ni / recent_eq;
            if roe > 0.2 {
                raw_score += 3;
                details.push(format!("High ROE: {:.1}%", roe * 100.0));
            } else if roe > 0.1 {
                raw_score += 2;
                details.push(format!("Moderate ROE: {:.1}%", roe * 100.0));
            } else {
                raw_score += 1;
                details.push(format!("Positive but low ROE: {:.1}%", roe * 100.0));
            }
        }
    }

    let debt_values: Vec<f64> = financial_line_items.iter().filter_map(|item| item.total_debt).collect();
    if !debt_values.is_empty() && debt_values.len() == eq_values.len() {
        let recent_debt = debt_values[0];
        let recent_equity = eq_values[0];
        if recent_equity > 0.0 {
            let dte = recent_debt / recent_equity;
            if dte < 0.3 {
                raw_score += 2;
                details.push(format!("Low debt-to-equity: {:.2}", dte));
            } else if dte < 1.0 {
                raw_score += 1;
                details.push(format!("Manageable debt-to-equity: {:.2}", dte));
            }
        }
    }

    let fcf_values: Vec<f64> = financial_line_items.iter().filter_map(|item| item.free_cash_flow).collect();
    if fcf_values.len() >= 2 {
        let positive_count = fcf_values.iter().filter(|&&x| x > 0.0).count();
        let ratio = positive_count as f64 / fcf_values.len() as f64;
        if ratio > 0.8 {
            raw_score += 1;
            details.push(format!("Majority of periods have positive FCF ({}/{})", positive_count, fcf_values.len()));
        }
    }

    let final_score = (raw_score as f64 / 6.0 * 10.0).min(10.0);
    FisherSubResult { score: final_score, details: details.join("; ") }
}

pub fn analyze_fisher_valuation(financial_line_items: &[LineItem], market_cap: f64) -> FisherSubResult {
    if financial_line_items.is_empty() || market_cap <= 0.0 {
        return FisherSubResult { score: 0.0, details: "Insufficient data for valuation".to_string() };
    }

    let mut details = Vec::new();
    let mut raw_score = 0;

    let net_incomes: Vec<f64> = financial_line_items.iter().filter_map(|item| item.net_income).collect();
    let fcf_values: Vec<f64> = financial_line_items.iter().filter_map(|item| item.free_cash_flow).collect();

    if !net_incomes.is_empty() && net_incomes[0] > 0.0 {
        let pe = market_cap / net_incomes[0];
        if pe < 20.0 {
            raw_score += 2;
            details.push(format!("Reasonably attractive P/E: {:.2}", pe));
        } else if pe < 30.0 {
            raw_score += 1;
            details.push(format!("Somewhat high but possibly justifiable P/E: {:.2}", pe));
        } else {
            details.push(format!("Very high P/E: {:.2}", pe));
        }
    }

    if !fcf_values.is_empty() && fcf_values[0] > 0.0 {
        let pfcf = market_cap / fcf_values[0];
        if pfcf < 20.0 {
            raw_score += 2;
            details.push(format!("Reasonable P/FCF: {:.2}", pfcf));
        } else if pfcf < 30.0 {
            raw_score += 1;
            details.push(format!("Somewhat high P/FCF: {:.2}", pfcf));
        } else {
            details.push(format!("Excessively high P/FCF: {:.2}", pfcf));
        }
    }

    let final_score = (raw_score as f64 / 4.0 * 10.0).min(10.0);
    FisherSubResult { score: final_score, details: details.join("; ") }
}

pub fn analyze_insider_activity(insider_trades: &[InsiderTrade]) -> FisherSubResult {
    let mut score = 5.0;
    let mut details = Vec::new();

    if insider_trades.is_empty() {
        details.push("No insider trades data; defaulting to neutral".to_string());
        return FisherSubResult { score, details: details.join("; ") };
    }

    let mut buys = 0;
    let mut sells = 0;

    for trade in insider_trades {
        if let Some(shares) = trade.transaction_shares {
            if shares > 0.0 {
                buys += 1;
            } else if shares < 0.0 {
                sells += 1;
            }
        }
    }

    let total = buys + sells;
    if total == 0 {
        details.push("No buy/sell transactions found; neutral".to_string());
        return FisherSubResult { score, details: details.join("; ") };
    }

    let buy_ratio = buys as f64 / total as f64;
    if buy_ratio > 0.7 {
        score = 8.0;
        details.push(format!("Heavy insider buying: {} buys vs. {} sells", buys, sells));
    } else if buy_ratio > 0.4 {
        score = 6.0;
        details.push(format!("Moderate insider buying: {} buys vs. {} sells", buys, sells));
    } else {
        score = 4.0;
        details.push(format!("Mostly insider selling: {} buys vs. {} sells", buys, sells));
    }

    FisherSubResult { score, details: details.join("; ") }
}

pub fn analyze_sentiment(news_items: &[CompanyNews]) -> FisherSubResult {
    if news_items.is_empty() {
        return FisherSubResult { score: 5.0, details: "No news data; defaulting to neutral sentiment".to_string() };
    }

    let negative_keywords = vec!["lawsuit", "fraud", "negative", "downturn", "decline", "investigation", "recall"];
    let mut negative_count = 0;

    for news in news_items {
        let title_lower = news.title.to_lowercase();
        if negative_keywords.iter().any(|word| title_lower.contains(word)) {
            negative_count += 1;
        }
    }

    let mut details = Vec::new();
    let score = if negative_count as f64 > news_items.len() as f64 * 0.3 {
        details.push(format!("High proportion of negative headlines: {}/{}", negative_count, news_items.len()));
        3.0
    } else if negative_count > 0 {
        details.push(format!("Some negative headlines: {}/{}", negative_count, news_items.len()));
        6.0
    } else {
        details.push("Mostly positive/neutral headlines".to_string());
        8.0
    };

    FisherSubResult { score, details: details.join("; ") }
}

pub async fn generate_fisher_output(
    ticker: &str,
    facts: &serde_json::Value,
    state: &AgentState,
    agent_id: &str,
) -> Result<PhilFisherSignal> {
    let system_prompt = "You are a Phil Fisher AI agent making investment decisions using his principles:\n\
        1. Emphasize long-term growth potential and quality of management.\n\
        2. Focus on companies investing in R&D for future products/services.\n\
        3. Look for strong profitability and consistent margins.\n\
        4. Willing to pay more for exceptional companies but still mindful of valuation.\n\
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
