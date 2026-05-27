// Source: src/agents/michael_burry.py
//! Sibling to src/agents/michael_burry.py
//! Analyzes stocks using Dr. Michael J. Burry's deep‑value, contrarian framework.

use crate::data::models::{CompanyNews, FinancialMetrics, InsiderTrade, LineItem};
use crate::graph::state::AgentState;
use crate::tools::api::{
    get_company_news, get_financial_metrics, get_insider_trades, get_market_cap, search_line_items,
};
use crate::utils::llm::call_llm;
use anyhow::{Context, Result};
use chrono::Duration;

#[derive(Debug, serde::Serialize, serde::Deserialize, Default)]
pub struct MichaelBurrySignal {
    pub signal: String,  // "bullish" | "bearish" | "neutral"
    pub confidence: u32, // 0-100
    pub reasoning: String,
}

pub async fn michael_burry_agent(state: &mut AgentState, agent_id: &str) -> Result<()> {
    println!("Running Michael Burry Agent: {}", agent_id);

    let _start_date_str = state
        .data
        .get("start_date")
        .and_then(|v| v.as_str())
        .context("Missing start_date in michael_burry_agent")?;

    let end_date_str = state
        .data
        .get("end_date")
        .and_then(|v| v.as_str())
        .context("Missing end_date in michael_burry_agent")?;

    let tickers_json = state
        .data
        .get("tickers")
        .context("Missing tickers in michael_burry_agent")?;
    let tickers: Vec<String> = serde_json::from_value(tickers_json.clone())?;

    let api_key = state
        .metadata
        .get("FINANCIAL_DATASETS_API_KEY")
        .and_then(|v| v.as_str());

    // Lookback one year for insider trades and news
    let end_dt = chrono::NaiveDate::parse_from_str(end_date_str, "%Y-%m-%d")
        .context("Failed to parse end_date in michael_burry_agent")?;
    let one_year_ago = (end_dt - Duration::days(365))
        .format("%Y-%m-%d")
        .to_string();

    let mut burry_analysis = serde_json::Map::new();

    for ticker in &tickers {
        // Fetch raw data
        let metrics = get_financial_metrics(ticker, end_date_str, "ttm", 5, api_key)
            .await
            .unwrap_or_default();
        let line_items = search_line_items(
            ticker,
            vec![
                "free_cash_flow".to_string(),
                "net_income".to_string(),
                "total_debt".to_string(),
                "cash_and_equivalents".to_string(),
                "total_assets".to_string(),
                "total_liabilities".to_string(),
                "outstanding_shares".to_string(),
                "issuance_or_purchase_of_equity_shares".to_string(),
            ],
            end_date_str,
            "ttm",
            5,
            api_key,
        )
        .await
        .unwrap_or_default();

        let insider_trades =
            get_insider_trades(ticker, end_date_str, Some(&one_year_ago), 100, api_key)
                .await
                .unwrap_or_default();
        let news = get_company_news(ticker, end_date_str, Some(&one_year_ago), 250, api_key)
            .await
            .unwrap_or_default();
        let market_cap = get_market_cap(ticker, end_date_str, api_key)
            .await
            .unwrap_or(None)
            .unwrap_or(0.0);

        // Perform sub-analyses
        let value = analyze_value(&metrics, &line_items, market_cap);
        let balance_sheet = analyze_balance_sheet(&metrics, &line_items);
        let insider = analyze_insider_activity(&insider_trades);
        let contrarian = analyze_contrarian_sentiment(&news);

        let total_score = value.score + balance_sheet.score + insider.score + contrarian.score;
        let max_score =
            value.max_score + balance_sheet.max_score + insider.max_score + contrarian.max_score;

        let signal = if total_score as f64 >= 0.7 * max_score as f64 {
            "bullish"
        } else if total_score as f64 <= 0.3 * max_score as f64 {
            "bearish"
        } else {
            "neutral"
        };

        let facts = serde_json::json!({
            "signal": signal,
            "score": total_score,
            "max_score": max_score,
            "value_analysis": {
                "score": value.score,
                "max_score": value.max_score,
                "details": value.details,
            },
            "balance_sheet_analysis": {
                "score": balance_sheet.score,
                "max_score": balance_sheet.max_score,
                "details": balance_sheet.details,
            },
            "insider_analysis": {
                "score": insider.score,
                "max_score": insider.max_score,
                "details": insider.details,
            },
            "contrarian_analysis": {
                "score": contrarian.score,
                "max_score": contrarian.max_score,
                "details": contrarian.details,
            },
            "market_cap": market_cap,
        });

        let output = generate_burry_output(ticker, &facts, state, agent_id).await?;

        burry_analysis.insert(
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
            serde_json::Value::Object(burry_analysis),
        );
    }

    Ok(())
}

pub struct BurrySubResult {
    pub score: u32,
    pub max_score: u32,
    pub details: String,
}

pub fn analyze_value(
    metrics: &[FinancialMetrics],
    line_items: &[LineItem],
    market_cap: f64,
) -> BurrySubResult {
    let mut score = 0;
    let max_score = 6;
    let mut details = Vec::new();

    // 1. FCF yield
    if !line_items.is_empty() && market_cap > 0.0 {
        if let Some(fcf) = line_items[0].free_cash_flow {
            let fcf_yield = fcf / market_cap;
            if fcf_yield >= 0.15 {
                score += 4;
                details.push(format!("Extraordinary FCF yield {:.1}%", fcf_yield * 100.0));
            } else if fcf_yield >= 0.12 {
                score += 3;
                details.push(format!("Very high FCF yield {:.1}%", fcf_yield * 100.0));
            } else if fcf_yield >= 0.08 {
                score += 2;
                details.push(format!("Respectable FCF yield {:.1}%", fcf_yield * 100.0));
            } else {
                details.push(format!("Low FCF yield {:.1}%", fcf_yield * 100.0));
            }
        } else {
            details.push("FCF data unavailable".to_string());
        }
    } else {
        details.push("FCF or Market Cap data unavailable".to_string());
    }

    // 2. EV / EBIT
    if !metrics.is_empty() {
        if let Some(ev_ebit) = metrics[0].ev_to_ebit {
            if ev_ebit < 6.0 {
                score += 2;
                details.push(format!("EV/EBIT {:.1} (<6)", ev_ebit));
            } else if ev_ebit < 10.0 {
                score += 1;
                details.push(format!("EV/EBIT {:.1} (<10)", ev_ebit));
            } else {
                details.push(format!("High EV/EBIT {:.1}", ev_ebit));
            }
        } else {
            details.push("EV/EBIT data unavailable".to_string());
        }
    } else {
        details.push("Financial metrics unavailable".to_string());
    }

    BurrySubResult {
        score,
        max_score,
        details: details.join("; "),
    }
}

pub fn analyze_balance_sheet(
    metrics: &[FinancialMetrics],
    line_items: &[LineItem],
) -> BurrySubResult {
    let mut score = 0;
    let max_score = 3;
    let mut details = Vec::new();

    // 1. Debt-to-Equity
    if !metrics.is_empty() {
        if let Some(de) = metrics[0].debt_to_equity {
            if de < 0.5 {
                score += 2;
                details.push(format!("Low D/E {:.2}", de));
            } else if de < 1.0 {
                score += 1;
                details.push(format!("Moderate D/E {:.2}", de));
            } else {
                details.push(format!("High leverage D/E {:.2}", de));
            }
        } else {
            details.push("Debt-to-equity data unavailable".to_string());
        }
    } else {
        details.push("Financial metrics unavailable".to_string());
    }

    // 2. Net Cash position check
    if !line_items.is_empty() {
        let latest = &line_items[0];
        if let (Some(cash), Some(debt)) = (latest.cash_and_equivalents, latest.total_debt) {
            if cash > debt {
                score += 1;
                details.push("Net cash position".to_string());
            } else {
                details.push("Net debt position".to_string());
            }
        } else {
            details.push("Cash/debt data unavailable".to_string());
        }
    } else {
        details.push("Line items data unavailable".to_string());
    }

    BurrySubResult {
        score,
        max_score,
        details: details.join("; "),
    }
}

pub fn analyze_insider_activity(insider_trades: &[InsiderTrade]) -> BurrySubResult {
    let mut score = 0;
    let max_score = 2;
    let mut details = Vec::new();

    if insider_trades.is_empty() {
        details.push("No insider trade data".to_string());
        return BurrySubResult {
            score,
            max_score,
            details: details.join("; "),
        };
    }

    let mut shares_bought = 0.0;
    let mut shares_sold = 0.0;

    for trade in insider_trades {
        if let Some(shares) = trade.transaction_shares {
            if shares > 0.0 {
                shares_bought += shares;
            } else {
                shares_sold += shares.abs();
            }
        }
    }

    let net = shares_bought - shares_sold;
    if net > 0.0 {
        if shares_sold > 0.0 && (net / shares_sold) > 1.0 {
            score += 2;
        } else {
            score += 1;
        }
        details.push(format!("Net insider buying of {:.0} shares", net));
    } else {
        details.push("Net insider selling".to_string());
    }

    BurrySubResult {
        score,
        max_score,
        details: details.join("; "),
    }
}

pub fn analyze_contrarian_sentiment(news: &[CompanyNews]) -> BurrySubResult {
    let mut score = 0;
    let max_score = 1;
    let mut details = Vec::new();

    if news.is_empty() {
        details.push("No recent news".to_string());
        return BurrySubResult {
            score,
            max_score,
            details: details.join("; "),
        };
    }

    let sentiment_negative_count = news
        .iter()
        .filter(|n| {
            n.sentiment
                .as_ref()
                .map(|s| s.to_lowercase() == "negative" || s.to_lowercase() == "bearish")
                .unwrap_or(false)
        })
        .count();

    if sentiment_negative_count >= 5 {
        score += 1;
        details.push(format!(
            "{} negative headlines (contrarian opportunity)",
            sentiment_negative_count
        ));
    } else {
        details.push("Limited negative press".to_string());
    }

    BurrySubResult {
        score,
        max_score,
        details: details.join("; "),
    }
}

pub async fn generate_burry_output(
    ticker: &str,
    facts: &serde_json::Value,
    state: &AgentState,
    agent_id: &str,
) -> Result<MichaelBurrySignal> {
    let system_prompt = "You are Dr. Michael J. Burry. Hunt for deep value using hard numbers.\n\
        Be contrarian: hated stocks with strong fundamentals and cashflow are your friends.\n\
        Avoid leverage, look for hard catalysts (insider buying, buybacks).\n\
        Communicate in a terse, data-driven style.\n\
        Return JSON matching exactly: {\"signal\": \"bullish\" | \"bearish\" | \"neutral\", \"confidence\": int, \"reasoning\": \"short\"}";

    let user_prompt = format!(
        "Ticker: {}\nFacts:\n{}\n\nReturn structured JSON output.",
        ticker,
        serde_json::to_string_pretty(facts)?
    );

    call_llm(system_prompt, &user_prompt, Some(agent_id), Some(state), 3).await
}
