// Source: src/agents/peter_lynch.py
//! Sibling to src/agents/peter_lynch.py
//! Analyzes stocks using Peter Lynch's Growth at a Reasonable Price (GARP) and folksy quality filters.

use anyhow::{Result, Context};
use crate::graph::state::AgentState;
use crate::tools::api::{get_market_cap, search_line_items, get_insider_trades, get_company_news};
use crate::data::models::{FinancialMetrics, LineItem, InsiderTrade, CompanyNews};
use crate::utils::llm::call_llm;

#[derive(Debug, serde::Serialize, serde::Deserialize, Default)]
pub struct PeterLynchSignal {
    pub signal: String,      // "bullish" | "bearish" | "neutral"
    pub confidence: u32,     // 0-100
    pub reasoning: String,
}

pub async fn peter_lynch_agent(state: &mut AgentState, agent_id: &str) -> Result<()> {
    println!("Running Peter Lynch Agent: {}", agent_id);

    let end_date = state.data.get("end_date")
        .and_then(|v| v.as_str())
        .context("Missing end_date in peter_lynch_agent")?;
    
    let tickers_json = state.data.get("tickers")
        .context("Missing tickers in peter_lynch_agent")?;
    let tickers: Vec<String> = serde_json::from_value(tickers_json.clone())?;

    let api_key = state.metadata.get("FINANCIAL_DATASETS_API_KEY")
        .and_then(|v| v.as_str());

    let mut lynch_analysis = serde_json::Map::new();

    for ticker in &tickers {
        // Fetch raw data
        let financial_line_items = search_line_items(
            ticker,
            vec![
                "revenue".to_string(),
                "earnings_per_share".to_string(),
                "net_income".to_string(),
                "operating_income".to_string(),
                "gross_margin".to_string(),
                "operating_margin".to_string(),
                "free_cash_flow".to_string(),
                "capital_expenditure".to_string(),
                "cash_and_equivalents".to_string(),
                "total_debt".to_string(),
                "shareholders_equity".to_string(),
                "outstanding_shares".to_string(),
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
        let growth = analyze_lynch_growth(&financial_line_items);
        let fundamentals = analyze_lynch_fundamentals(&financial_line_items);
        let valuation = analyze_lynch_valuation(&financial_line_items, market_cap);
        let sentiment = analyze_sentiment(&company_news);
        let insider = analyze_insider_activity(&insider_trades);

        // Weights: 30% Growth, 25% Valuation, 20% Fundamentals, 15% Sentiment, 10% Insider
        let total_score = growth.score * 0.30
            + valuation.score * 0.25
            + fundamentals.score * 0.20
            + sentiment.score * 0.15
            + insider.score * 0.10;

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
            "growth_analysis": {
                "score": growth.score,
                "details": growth.details,
            },
            "valuation_analysis": {
                "score": valuation.score,
                "details": valuation.details,
            },
            "fundamentals_analysis": {
                "score": fundamentals.score,
                "details": fundamentals.details,
            },
            "sentiment_analysis": {
                "score": sentiment.score,
                "details": sentiment.details,
            },
            "insider_activity": {
                "score": insider.score,
                "details": insider.details,
            }
        });

        let output = generate_lynch_output(ticker, &facts, state, agent_id).await?;

        lynch_analysis.insert(
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
        obj.insert(agent_id.to_string(), serde_json::Value::Object(lynch_analysis));
    }

    Ok(())
}

pub struct LynchSubResult {
    pub score: f64,
    pub details: String,
}

pub fn analyze_lynch_growth(financial_line_items: &[LineItem]) -> LynchSubResult {
    if financial_line_items.len() < 2 {
        return LynchSubResult { score: 0.0, details: "Insufficient financial data for growth analysis".to_string() };
    }

    let mut details = Vec::new();
    let mut raw_score = 0;

    // 1. Revenue growth (reverse chronological: newest first)
    let revenues: Vec<f64> = financial_line_items.iter().filter_map(|item| item.revenue).collect();
    if revenues.len() >= 2 {
        let latest = revenues[0];
        let older = revenues[revenues.len() - 1];
        if older > 0.0 {
            let rev_growth = (latest - older) / older.abs();
            if rev_growth > 0.25 {
                raw_score += 3;
                details.push(format!("Strong revenue growth: {:.1}%", rev_growth * 100.0));
            } else if rev_growth > 0.10 {
                raw_score += 2;
                details.push(format!("Moderate revenue growth: {:.1}%", rev_growth * 100.0));
            } else if rev_growth > 0.02 {
                raw_score += 1;
                details.push(format!("Slight revenue growth: {:.1}%", rev_growth * 100.0));
            } else {
                details.push(format!("Flat or negative revenue growth: {:.1}%", rev_growth * 100.0));
            }
        }
    }

    // 2. EPS growth
    let eps_values: Vec<f64> = financial_line_items.iter().filter_map(|item| item.earnings_per_share).collect();
    if eps_values.len() >= 2 {
        let latest = eps_values[0];
        let older = eps_values[eps_values.len() - 1];
        if older.abs() > 1e-9 {
            let eps_growth = (latest - older) / older.abs();
            if eps_growth > 0.25 {
                raw_score += 3;
                details.push(format!("Strong EPS growth: {:.1}%", eps_growth * 100.0));
            } else if eps_growth > 0.10 {
                raw_score += 2;
                details.push(format!("Moderate EPS growth: {:.1}%", eps_growth * 100.0));
            } else if eps_growth > 0.02 {
                raw_score += 1;
                details.push(format!("Slight EPS growth: {:.1}%", eps_growth * 100.0));
            } else {
                details.push(format!("Minimal or negative EPS growth: {:.1}%", eps_growth * 100.0));
            }
        }
    }

    let final_score = (raw_score as f64 / 6.0 * 10.0).min(10.0);
    LynchSubResult { score: final_score, details: details.join("; ") }
}

pub fn analyze_lynch_fundamentals(financial_line_items: &[LineItem]) -> LynchSubResult {
    if financial_line_items.is_empty() {
        return LynchSubResult { score: 0.0, details: "Insufficient fundamentals data".to_string() };
    }

    let mut details = Vec::new();
    let mut raw_score = 0;

    // 1. Debt to equity
    let latest = &financial_line_items[0];
    if let (Some(debt), Some(equity)) = (latest.total_debt, latest.shareholders_equity) {
        let de_ratio = if equity != 0.0 { debt / equity } else { 99.0 };
        if de_ratio < 0.5 {
            raw_score += 2;
            details.push(format!("Low debt-to-equity: {:.2}", de_ratio));
        } else if de_ratio < 1.0 {
            raw_score += 1;
            details.push(format!("Moderate debt-to-equity: {:.2}", de_ratio));
        } else {
            details.push(format!("High debt-to-equity: {:.2}", de_ratio));
        }
    }

    // 2. Operating margin
    if let Some(om) = latest.operating_margin {
        if om > 0.20 {
            raw_score += 2;
            details.push(format!("Strong operating margin: {:.1}%", om * 100.0));
        } else if om > 0.10 {
            raw_score += 1;
            details.push(format!("Moderate operating margin: {:.1}%", om * 100.0));
        } else {
            details.push(format!("Low operating margin: {:.1}%", om * 100.0));
        }
    }

    // 3. FCF positive check
    if let Some(fcf) = latest.free_cash_flow {
        if fcf > 0.0 {
            raw_score += 2;
            details.push(format!("Positive free cash flow: {:.0}", fcf));
        } else {
            details.push(format!("Negative FCF: {:.0}", fcf));
        }
    }

    let final_score = (raw_score as f64 / 6.0 * 10.0).min(10.0);
    LynchSubResult { score: final_score, details: details.join("; ") }
}

pub fn analyze_lynch_valuation(financial_line_items: &[LineItem], market_cap: f64) -> LynchSubResult {
    if financial_line_items.is_empty() || market_cap <= 0.0 {
        return LynchSubResult { score: 0.0, details: "Insufficient data for valuation".to_string() };
    }

    let mut details = Vec::new();
    let mut raw_score = 0;

    let latest = &financial_line_items[0];
    let net_income = latest.net_income.unwrap_or(0.0);
    let eps_values: Vec<f64> = financial_line_items.iter().filter_map(|item| item.earnings_per_share).collect();

    let mut pe_ratio = None;
    if net_income > 0.0 {
        let pe = market_cap / net_income;
        pe_ratio = Some(pe);
        details.push(format!("Estimated P/E: {:.2}", pe));
    }

    let mut eps_growth_rate = None;
    if eps_values.len() >= 2 {
        let ending = eps_values[0];
        let beginning = eps_values[eps_values.len() - 1];
        if beginning > 0.0 {
            let num_years = (eps_values.len() - 1) as f64;
            if ending > 0.0 {
                let cagr = (ending / beginning).powf(1.0 / num_years) - 1.0;
                eps_growth_rate = Some(cagr);
            } else {
                eps_growth_rate = Some((ending - beginning) / (beginning * num_years));
            }
            details.push(format!("Annualized EPS growth rate: {:.1}%", eps_growth_rate.unwrap() * 100.0));
        }
    }

    let mut peg_ratio = None;
    if let (Some(pe), Some(growth)) = (pe_ratio, eps_growth_rate) {
        if growth > 0.0 {
            let peg = pe / (growth * 100.0);
            peg_ratio = Some(peg);
            details.push(format!("PEG ratio: {:.2}", peg));
        }
    }

    if let Some(pe) = pe_ratio {
        if pe < 15.0 {
            raw_score += 2;
        } else if pe < 25.0 {
            raw_score += 1;
        }
    }

    if let Some(peg) = peg_ratio {
        if peg < 1.0 {
            raw_score += 3;
        } else if peg < 2.0 {
            raw_score += 2;
        } else if peg < 3.0 {
            raw_score += 1;
        }
    }

    let final_score = (raw_score as f64 / 5.0 * 10.0).min(10.0);
    LynchSubResult { score: final_score, details: details.join("; ") }
}

pub fn analyze_sentiment(news_items: &[CompanyNews]) -> LynchSubResult {
    if news_items.is_empty() {
        return LynchSubResult { score: 5.0, details: "No news data; default to neutral sentiment".to_string() };
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
        details.push("Mostly positive or neutral headlines".to_string());
        8.0
    };

    LynchSubResult { score, details: details.join("; ") }
}

pub fn analyze_insider_activity(insider_trades: &[InsiderTrade]) -> LynchSubResult {
    let mut score = 5.0;
    let mut details = Vec::new();

    if insider_trades.is_empty() {
        details.push("No insider trades data; defaulting to neutral".to_string());
        return LynchSubResult { score, details: details.join("; ") };
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
        details.push("No significant buy/sell transactions found; neutral stance".to_string());
        return LynchSubResult { score, details: details.join("; ") };
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

    LynchSubResult { score, details: details.join("; ") }
}

pub async fn generate_lynch_output(
    ticker: &str,
    facts: &serde_json::Value,
    state: &AgentState,
    agent_id: &str,
) -> Result<PeterLynchSignal> {
    let system_prompt = "You are a Peter Lynch AI agent making investment decisions using his principles:\n\
        1. Invest in what you know (simple, understandable businesses).\n\
        2. Growth at a Reasonable Price (GARP): rely on PEG ratio.\n\
        3. Hunt for multi-year compounders (ten-baggers).\n\
        4. Focus on steady growth, low debt, and strong FCF.\n\
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
