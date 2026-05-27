// Source: src/agents/stanley_druckenmiller.py
//! Sibling to src/agents/stanley_druckenmiller.py
//! Analyzes stocks using Stanley Druckenmiller's asymmetric risk-reward, growth, and momentum principles.

use crate::data::models::{CompanyNews, InsiderTrade, LineItem, Price};
use crate::graph::state::AgentState;
use crate::tools::api::{
    get_company_news, get_financial_metrics, get_insider_trades, get_market_cap, get_prices,
    search_line_items,
};
use crate::utils::llm::call_llm;
use anyhow::{Context, Result};

#[derive(Debug, serde::Serialize, serde::Deserialize, Default)]
pub struct StanleyDruckenmillerSignal {
    pub signal: String,  // "bullish" | "bearish" | "neutral"
    pub confidence: u32, // 0-100
    pub reasoning: String,
}

pub async fn stanley_druckenmiller_agent(state: &mut AgentState, agent_id: &str) -> Result<()> {
    println!("Running Stanley Druckenmiller Agent: {}", agent_id);

    let start_date_str = state
        .data
        .get("start_date")
        .and_then(|v| v.as_str())
        .context("Missing start_date in stanley_druckenmiller_agent")?
        .to_string();

    let end_date_str = state
        .data
        .get("end_date")
        .and_then(|v| v.as_str())
        .context("Missing end_date in stanley_druckenmiller_agent")?
        .to_string();

    let tickers_json = state
        .data
        .get("tickers")
        .context("Missing tickers in stanley_druckenmiller_agent")?;
    let tickers: Vec<String> = serde_json::from_value(tickers_json.clone())?;

    let api_key = state
        .metadata
        .get("FINANCIAL_DATASETS_API_KEY")
        .and_then(|v| v.as_str());

    let mut druck_analysis = serde_json::Map::new();

    for ticker in &tickers {
        // Fetch financial data
        let _metrics = get_financial_metrics(ticker, &end_date_str, "annual", 5, api_key)
            .await
            .unwrap_or_default();
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
                "ebit".to_string(),
                "ebitda".to_string(),
            ],
            &end_date_str,
            "annual",
            5,
            api_key,
        )
        .await
        .unwrap_or_default();

        let market_cap = get_market_cap(ticker, &end_date_str, api_key)
            .await
            .unwrap_or(None)
            .unwrap_or(0.0);
        let insider_trades = get_insider_trades(ticker, &end_date_str, None, 50, api_key)
            .await
            .unwrap_or_default();
        let company_news = get_company_news(ticker, &end_date_str, None, 50, api_key)
            .await
            .unwrap_or_default();
        let prices = get_prices(ticker, &start_date_str, &end_date_str, api_key)
            .await
            .unwrap_or_default();

        // Sub-analyses
        let growth_momentum = analyze_growth_and_momentum(&financial_line_items, &prices);
        let sentiment = analyze_sentiment(&company_news);
        let insider = analyze_insider_activity(&insider_trades);
        let risk_reward = analyze_risk_reward(&financial_line_items, &prices);
        let valuation = analyze_druckenmiller_valuation(&financial_line_items, market_cap);

        // Weights: 35% Growth/Momentum, 20% Risk/Reward, 20% Valuation, 15% Sentiment, 10% Insider
        let total_score = growth_momentum.score * 0.35
            + risk_reward.score * 0.20
            + valuation.score * 0.20
            + sentiment.score * 0.15
            + insider.score * 0.10;

        let signal = if total_score >= 7.5 {
            "bullish"
        } else if total_score <= 4.5 {
            "bearish"
        } else {
            "neutral"
        };

        let facts = serde_json::json!({
            "signal": signal,
            "score": total_score,
            "max_score": 10,
            "growth_momentum_analysis": {
                "score": growth_momentum.score,
                "details": growth_momentum.details,
            },
            "sentiment_analysis": {
                "score": sentiment.score,
                "details": sentiment.details,
            },
            "insider_activity": {
                "score": insider.score,
                "details": insider.details,
            },
            "risk_reward_analysis": {
                "score": risk_reward.score,
                "details": risk_reward.details,
            },
            "valuation_analysis": {
                "score": valuation.score,
                "details": valuation.details,
            },
        });

        let output = generate_druckenmiller_output(ticker, &facts, state, agent_id).await?;

        druck_analysis.insert(
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
            serde_json::Value::Object(druck_analysis),
        );
    }

    Ok(())
}

pub struct DruckSubResult {
    pub score: f64,
    pub details: String,
}

/// Evaluate revenue growth (CAGR), EPS growth (CAGR), and price momentum.
pub fn analyze_growth_and_momentum(
    financial_line_items: &[LineItem],
    prices: &[Price],
) -> DruckSubResult {
    if financial_line_items.len() < 2 {
        return DruckSubResult {
            score: 0.0,
            details: "Insufficient financial data for growth analysis".to_string(),
        };
    }

    let mut details = Vec::new();
    let mut raw_score = 0_u32;

    // 1. Revenue Growth (CAGR)
    let revenues: Vec<f64> = financial_line_items
        .iter()
        .filter_map(|fi| fi.revenue)
        .collect();
    if revenues.len() >= 2 {
        let latest_rev = revenues[0];
        let older_rev = revenues[revenues.len() - 1];
        let num_years = (revenues.len() - 1) as f64;
        if older_rev > 0.0 && latest_rev > 0.0 {
            let rev_growth = (latest_rev / older_rev).powf(1.0 / num_years) - 1.0;
            if rev_growth > 0.08 {
                raw_score += 3;
                details.push(format!(
                    "Strong annualized revenue growth: {:.1}%",
                    rev_growth * 100.0
                ));
            } else if rev_growth > 0.04 {
                raw_score += 2;
                details.push(format!(
                    "Moderate annualized revenue growth: {:.1}%",
                    rev_growth * 100.0
                ));
            } else if rev_growth > 0.01 {
                raw_score += 1;
                details.push(format!(
                    "Slight annualized revenue growth: {:.1}%",
                    rev_growth * 100.0
                ));
            } else {
                details.push(format!(
                    "Minimal/negative revenue growth: {:.1}%",
                    rev_growth * 100.0
                ));
            }
        } else {
            details
                .push("Older revenue is zero/negative; can't compute revenue growth.".to_string());
        }
    } else {
        details.push("Not enough revenue data points for growth calculation.".to_string());
    }

    // 2. EPS Growth (CAGR)
    let eps_values: Vec<f64> = financial_line_items
        .iter()
        .filter_map(|fi| fi.earnings_per_share)
        .collect();
    if eps_values.len() >= 2 {
        let latest_eps = eps_values[0];
        let older_eps = eps_values[eps_values.len() - 1];
        let num_years = (eps_values.len() - 1) as f64;
        if older_eps > 0.0 && latest_eps > 0.0 {
            let eps_growth = (latest_eps / older_eps).powf(1.0 / num_years) - 1.0;
            if eps_growth > 0.08 {
                raw_score += 3;
                details.push(format!(
                    "Strong annualized EPS growth: {:.1}%",
                    eps_growth * 100.0
                ));
            } else if eps_growth > 0.04 {
                raw_score += 2;
                details.push(format!(
                    "Moderate annualized EPS growth: {:.1}%",
                    eps_growth * 100.0
                ));
            } else if eps_growth > 0.01 {
                raw_score += 1;
                details.push(format!(
                    "Slight annualized EPS growth: {:.1}%",
                    eps_growth * 100.0
                ));
            } else {
                details.push(format!(
                    "Minimal/negative annualized EPS growth: {:.1}%",
                    eps_growth * 100.0
                ));
            }
        } else {
            details.push("Older EPS is near zero; skipping EPS growth calculation.".to_string());
        }
    } else {
        details.push("Not enough EPS data points for growth calculation.".to_string());
    }

    // 3. Price Momentum
    if prices.len() > 30 {
        let mut sorted = prices.to_vec();
        sorted.sort_by(|a, b| a.time.cmp(&b.time));
        let close_prices: Vec<f64> = sorted.iter().map(|p| p.close).collect();
        if close_prices.len() >= 2 {
            let start_price = close_prices[0];
            let end_price = close_prices[close_prices.len() - 1];
            if start_price > 0.0 {
                let pct_change = (end_price - start_price) / start_price;
                if pct_change > 0.50 {
                    raw_score += 3;
                    details.push(format!(
                        "Very strong price momentum: {:.1}%",
                        pct_change * 100.0
                    ));
                } else if pct_change > 0.20 {
                    raw_score += 2;
                    details.push(format!(
                        "Moderate price momentum: {:.1}%",
                        pct_change * 100.0
                    ));
                } else if pct_change > 0.0 {
                    raw_score += 1;
                    details.push(format!(
                        "Slight positive momentum: {:.1}%",
                        pct_change * 100.0
                    ));
                } else {
                    details.push(format!(
                        "Negative price momentum: {:.1}%",
                        pct_change * 100.0
                    ));
                }
            }
        }
    } else {
        details.push("Not enough recent price data for momentum analysis.".to_string());
    }

    // Scale raw (max 9) to 0–10
    let final_score = ((raw_score as f64 / 9.0) * 10.0).min(10.0);
    DruckSubResult {
        score: final_score,
        details: details.join("; "),
    }
}

/// Insider activity: proportion of buys vs sells → score 4/6/8.
pub fn analyze_insider_activity(insider_trades: &[InsiderTrade]) -> DruckSubResult {
    let mut score = 5.0_f64;
    let mut details = Vec::new();

    if insider_trades.is_empty() {
        details.push("No insider trades data; defaulting to neutral".to_string());
        return DruckSubResult {
            score,
            details: details.join("; "),
        };
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
    } else {
        let buy_ratio = buys as f64 / total as f64;
        if buy_ratio > 0.7 {
            score = 8.0;
            details.push(format!(
                "Heavy insider buying: {} buys vs. {} sells",
                buys, sells
            ));
        } else if buy_ratio > 0.4 {
            score = 6.0;
            details.push(format!(
                "Moderate insider buying: {} buys vs. {} sells",
                buys, sells
            ));
        } else {
            score = 4.0;
            details.push(format!(
                "Mostly insider selling: {} buys vs. {} sells",
                buys, sells
            ));
        }
    }

    DruckSubResult {
        score,
        details: details.join("; "),
    }
}

/// Sentiment: negative keyword ratio in news titles.
pub fn analyze_sentiment(news_items: &[CompanyNews]) -> DruckSubResult {
    if news_items.is_empty() {
        return DruckSubResult {
            score: 5.0,
            details: "No news data; defaulting to neutral sentiment".to_string(),
        };
    }

    let negative_keywords = [
        "lawsuit",
        "fraud",
        "negative",
        "downturn",
        "decline",
        "investigation",
        "recall",
    ];
    let mut negative_count = 0;
    for news in news_items {
        let title_lower = news.title.to_lowercase();
        if negative_keywords.iter().any(|w| title_lower.contains(w)) {
            negative_count += 1;
        }
    }

    let mut details = Vec::new();
    let score = if negative_count as f64 > news_items.len() as f64 * 0.3 {
        details.push(format!(
            "High proportion of negative headlines: {}/{}",
            negative_count,
            news_items.len()
        ));
        3.0
    } else if negative_count > 0 {
        details.push(format!(
            "Some negative headlines: {}/{}",
            negative_count,
            news_items.len()
        ));
        6.0
    } else {
        details.push("Mostly positive/neutral headlines".to_string());
        8.0
    };

    DruckSubResult {
        score,
        details: details.join("; "),
    }
}

/// Risk-reward: debt-to-equity ratio and price volatility.
pub fn analyze_risk_reward(financial_line_items: &[LineItem], prices: &[Price]) -> DruckSubResult {
    if financial_line_items.is_empty() || prices.is_empty() {
        return DruckSubResult {
            score: 0.0,
            details: "Insufficient data for risk-reward analysis".to_string(),
        };
    }

    let mut details = Vec::new();
    let mut raw_score = 0_u32;

    // 1. Debt-to-Equity
    let debt_values: Vec<f64> = financial_line_items
        .iter()
        .filter_map(|fi| fi.total_debt)
        .collect();
    let equity_values: Vec<f64> = financial_line_items
        .iter()
        .filter_map(|fi| fi.shareholders_equity)
        .collect();

    if !debt_values.is_empty() && !equity_values.is_empty() {
        let recent_debt = debt_values[0];
        let recent_equity = if equity_values[0].abs() > 1e-9 {
            equity_values[0]
        } else {
            1e-9
        };
        let de_ratio = recent_debt / recent_equity;
        if de_ratio < 0.3 {
            raw_score += 3;
            details.push(format!("Low debt-to-equity: {:.2}", de_ratio));
        } else if de_ratio < 0.7 {
            raw_score += 2;
            details.push(format!("Moderate debt-to-equity: {:.2}", de_ratio));
        } else if de_ratio < 1.5 {
            raw_score += 1;
            details.push(format!("Somewhat high debt-to-equity: {:.2}", de_ratio));
        } else {
            details.push(format!("High debt-to-equity: {:.2}", de_ratio));
        }
    } else {
        details.push("No consistent debt/equity data available.".to_string());
    }

    // 2. Price Volatility
    if prices.len() > 10 {
        let mut sorted = prices.to_vec();
        sorted.sort_by(|a, b| a.time.cmp(&b.time));
        let close_prices: Vec<f64> = sorted.iter().map(|p| p.close).collect();
        if close_prices.len() > 10 {
            let mut daily_returns = Vec::new();
            for i in 1..close_prices.len() {
                let prev = close_prices[i - 1];
                if prev > 0.0 {
                    daily_returns.push((close_prices[i] - prev) / prev);
                }
            }
            if !daily_returns.is_empty() {
                let n = daily_returns.len() as f64;
                let mean = daily_returns.iter().sum::<f64>() / n;
                let variance = daily_returns
                    .iter()
                    .map(|&r| (r - mean).powi(2))
                    .sum::<f64>()
                    / n;
                let stdev = variance.sqrt();

                if stdev < 0.01 {
                    raw_score += 3;
                    details.push(format!(
                        "Low volatility: daily returns stdev {:.2}%",
                        stdev * 100.0
                    ));
                } else if stdev < 0.02 {
                    raw_score += 2;
                    details.push(format!(
                        "Moderate volatility: daily returns stdev {:.2}%",
                        stdev * 100.0
                    ));
                } else if stdev < 0.04 {
                    raw_score += 1;
                    details.push(format!(
                        "High volatility: daily returns stdev {:.2}%",
                        stdev * 100.0
                    ));
                } else {
                    details.push(format!(
                        "Very high volatility: daily returns stdev {:.2}%",
                        stdev * 100.0
                    ));
                }
            }
        }
    } else {
        details.push("Not enough price data for volatility analysis.".to_string());
    }

    // Scale raw (max 6) to 0–10
    let final_score = ((raw_score as f64 / 6.0) * 10.0).min(10.0);
    DruckSubResult {
        score: final_score,
        details: details.join("; "),
    }
}

/// Druckenmiller valuation: P/E, P/FCF, EV/EBIT, EV/EBITDA.
pub fn analyze_druckenmiller_valuation(
    financial_line_items: &[LineItem],
    market_cap: f64,
) -> DruckSubResult {
    if financial_line_items.is_empty() || market_cap <= 0.0 {
        return DruckSubResult {
            score: 0.0,
            details: "Insufficient data to perform valuation".to_string(),
        };
    }

    let mut details = Vec::new();
    let mut raw_score = 0_u32;

    let latest = &financial_line_items[0];
    let net_income = latest.net_income;
    let fcf = latest.free_cash_flow;
    let ebit = latest.ebit;
    let ebitda = latest.ebitda;
    let debt = latest.total_debt.unwrap_or(0.0);
    let cash = latest.cash_and_equivalents.unwrap_or(0.0);
    let enterprise_value = market_cap + debt - cash;

    // 1. P/E
    if let Some(ni) = net_income {
        if ni > 0.0 {
            let pe = market_cap / ni;
            if pe < 15.0 {
                raw_score += 2;
                details.push(format!("Attractive P/E: {:.2}", pe));
            } else if pe < 25.0 {
                raw_score += 1;
                details.push(format!("Fair P/E: {:.2}", pe));
            } else {
                details.push(format!("High or Very high P/E: {:.2}", pe));
            }
        } else {
            details.push("No positive net income for P/E calculation".to_string());
        }
    }

    // 2. P/FCF
    if let Some(f) = fcf {
        if f > 0.0 {
            let pfcf = market_cap / f;
            if pfcf < 15.0 {
                raw_score += 2;
                details.push(format!("Attractive P/FCF: {:.2}", pfcf));
            } else if pfcf < 25.0 {
                raw_score += 1;
                details.push(format!("Fair P/FCF: {:.2}", pfcf));
            } else {
                details.push(format!("High/Very high P/FCF: {:.2}", pfcf));
            }
        } else {
            details.push("No positive free cash flow for P/FCF calculation".to_string());
        }
    }

    // 3. EV/EBIT
    if let Some(eb) = ebit {
        if enterprise_value > 0.0 && eb > 0.0 {
            let ev_ebit = enterprise_value / eb;
            if ev_ebit < 15.0 {
                raw_score += 2;
                details.push(format!("Attractive EV/EBIT: {:.2}", ev_ebit));
            } else if ev_ebit < 25.0 {
                raw_score += 1;
                details.push(format!("Fair EV/EBIT: {:.2}", ev_ebit));
            } else {
                details.push(format!("High EV/EBIT: {:.2}", ev_ebit));
            }
        } else {
            details.push("No valid EV/EBIT because EV <= 0 or EBIT <= 0".to_string());
        }
    }

    // 4. EV/EBITDA
    if let Some(ebd) = ebitda {
        if enterprise_value > 0.0 && ebd > 0.0 {
            let ev_ebitda = enterprise_value / ebd;
            if ev_ebitda < 10.0 {
                raw_score += 2;
                details.push(format!("Attractive EV/EBITDA: {:.2}", ev_ebitda));
            } else if ev_ebitda < 18.0 {
                raw_score += 1;
                details.push(format!("Fair EV/EBITDA: {:.2}", ev_ebitda));
            } else {
                details.push(format!("High EV/EBITDA: {:.2}", ev_ebitda));
            }
        } else {
            details.push("No valid EV/EBITDA because EV <= 0 or EBITDA <= 0".to_string());
        }
    }

    // Scale raw (max 8) to 0–10
    let final_score = ((raw_score as f64 / 8.0) * 10.0).min(10.0);
    DruckSubResult {
        score: final_score,
        details: details.join("; "),
    }
}

pub async fn generate_druckenmiller_output(
    ticker: &str,
    facts: &serde_json::Value,
    state: &AgentState,
    agent_id: &str,
) -> Result<StanleyDruckenmillerSignal> {
    let system_prompt = "You are a Stanley Druckenmiller AI agent, making investment decisions using his principles:\n\
        1. Seek asymmetric risk-reward opportunities (large upside, limited downside).\n\
        2. Emphasize growth, momentum, and market sentiment.\n\
        3. Preserve capital by avoiding major drawdowns.\n\
        4. Willing to pay higher valuations for true growth leaders.\n\
        5. Be aggressive when conviction is high.\n\
        6. Cut losses quickly if the thesis changes.\n\
        Return JSON matching exactly: {\"signal\": \"bullish\" | \"bearish\" | \"neutral\", \"confidence\": int, \"reasoning\": \"short\"}";

    let user_prompt = format!(
        "Ticker: {}\nFacts:\n{}\n\nReturn structured JSON output.",
        ticker,
        serde_json::to_string_pretty(facts)?
    );

    call_llm(system_prompt, &user_prompt, Some(agent_id), Some(state), 3).await
}
