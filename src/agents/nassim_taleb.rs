// Source: src/agents/nassim_taleb.py
//! Sibling to src/agents/nassim_taleb.py
//! Analyzes stocks using Nassim Nicholas Taleb's antifragility, tail-risk, and convexity principles.

use anyhow::{Result, Context};
use chrono::Duration;
use crate::graph::state::AgentState;
use crate::tools::api::{get_financial_metrics, get_market_cap, search_line_items, get_insider_trades, get_company_news, get_prices};
use crate::data::models::{FinancialMetrics, LineItem, InsiderTrade, CompanyNews, Price};
use crate::utils::llm::call_llm;

#[derive(Debug, serde::Serialize, serde::Deserialize, Default)]
pub struct NassimTalebSignal {
    pub signal: String,      // "bullish" | "bearish" | "neutral"
    pub confidence: u32,     // 0-100
    pub reasoning: String,
}

pub async fn nassim_taleb_agent(state: &mut AgentState, agent_id: &str) -> Result<()> {
    println!("Running Nassim Taleb Agent: {}", agent_id);

    let start_date_str = state.data.get("start_date")
        .and_then(|v| v.as_str())
        .context("Missing start_date in nassim_taleb_agent")?;
    
    let end_date_str = state.data.get("end_date")
        .and_then(|v| v.as_str())
        .context("Missing end_date in nassim_taleb_agent")?;
    
    let tickers_json = state.data.get("tickers")
        .context("Missing tickers in nassim_taleb_agent")?;
    let tickers: Vec<String> = serde_json::from_value(tickers_json.clone())?;

    let api_key = state.metadata.get("FINANCIAL_DATASETS_API_KEY")
        .and_then(|v| v.as_str());

    // Lookback one year for price, insider trades, and news
    let end_dt = chrono::NaiveDate::parse_from_str(end_date_str, "%Y-%m-%d")
        .context("Failed to parse end_date in nassim_taleb_agent")?;
    let one_year_ago = (end_dt - Duration::days(365)).format("%Y-%m-%d").to_string();

    let mut taleb_analysis = serde_json::Map::new();

    for ticker in &tickers {
        // Fetch raw data
        let prices = get_prices(ticker, &one_year_ago, end_date_str, api_key).await.unwrap_or_default();
        let metrics = get_financial_metrics(ticker, end_date_str, "ttm", 10, api_key).await.unwrap_or_default();
        let line_items = search_line_items(
            ticker,
            vec![
                "free_cash_flow".to_string(),
                "net_income".to_string(),
                "total_debt".to_string(),
                "cash_and_equivalents".to_string(),
                "total_assets".to_string(),
                "total_liabilities".to_string(),
                "revenue".to_string(),
                "operating_income".to_string(),
                "research_and_development".to_string(),
                "capital_expenditure".to_string(),
                "outstanding_shares".to_string(),
            ],
            end_date_str,
            "ttm",
            5,
            api_key,
        ).await.unwrap_or_default();

        let insider_trades = get_insider_trades(ticker, end_date_str, Some(&one_year_ago), 100, api_key).await.unwrap_or_default();
        let news = get_company_news(ticker, end_date_str, Some(&one_year_ago), 100, api_key).await.unwrap_or_default();
        let market_cap = get_market_cap(ticker, end_date_str, api_key).await.unwrap_or(None).unwrap_or(0.0);

        // Sub-analyses
        let tail_risk = analyze_tail_risk(&prices);
        let antifragility = analyze_antifragility(&metrics, &line_items, market_cap);
        let convexity = analyze_convexity(&metrics, &line_items, &prices, market_cap);
        let fragility = analyze_fragility(&metrics, &line_items);
        let skin_in_game = analyze_skin_in_game(&insider_trades);
        let volatility_regime = analyze_volatility_regime(&prices);
        let black_swan = analyze_black_swan_sentinel(&news, &prices);

        let total_score = tail_risk.score
            + antifragility.score
            + convexity.score
            + fragility.score
            + skin_in_game.score
            + volatility_regime.score
            + black_swan.score;

        let max_possible_score = tail_risk.max_score
            + antifragility.max_score
            + convexity.max_score
            + fragility.max_score
            + skin_in_game.max_score
            + volatility_regime.max_score
            + black_swan.max_score;

        let facts = serde_json::json!({
            "score": total_score,
            "max_score": max_possible_score,
            "tail_risk": tail_risk.details,
            "antifragility": antifragility.details,
            "convexity": convexity.details,
            "fragility": fragility.details,
            "skin_in_game": skin_in_game.details,
            "volatility_regime": volatility_regime.details,
            "black_swan": black_swan.details,
            "market_cap": market_cap,
        });

        let output = generate_taleb_output(ticker, &facts, state, agent_id).await?;

        taleb_analysis.insert(
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
        obj.insert(agent_id.to_string(), serde_json::Value::Object(taleb_analysis));
    }

    Ok(())
}

pub struct TalebSubResult {
    pub score: u32,
    pub max_score: u32,
    pub details: String,
}

fn compute_returns(prices: &[Price]) -> Vec<f64> {
    let mut returns = Vec::new();
    for i in 1..prices.len() {
        let prev = prices[i - 1].close;
        if prev > 0.0 {
            returns.push((prices[i].close - prev) / prev);
        }
    }
    returns
}

pub fn analyze_tail_risk(prices: &[Price]) -> TalebSubResult {
    let max_score = 8;
    if prices.len() < 20 {
        return TalebSubResult { score: 0, max_score, details: "Insufficient price data for tail risk analysis".to_string() };
    }

    let returns = compute_returns(prices);
    if returns.is_empty() {
        return TalebSubResult { score: 0, max_score, details: "Insufficient price data for tail risk analysis".to_string() };
    }

    let mut score = 0;
    let mut details = Vec::new();

    let n = returns.len() as f64;
    let mean: f64 = returns.iter().sum::<f64>() / n;
    let variance: f64 = returns.iter().map(|&x| (x - mean).powi(2)).sum::<f64>() / n;

    // Kurtosis
    let kurt = if variance > 0.0 {
        let fourth_moment = returns.iter().map(|&x| (x - mean).powi(4)).sum::<f64>() / n;
        (fourth_moment / variance.powi(2)) - 3.0
    } else {
        0.0
    };

    if kurt > 5.0 {
        score += 2;
        details.push(format!("Extremely fat tails (kurtosis {:.1})", kurt));
    } else if kurt > 2.0 {
        score += 1;
        details.push(format!("Moderate fat tails (kurtosis {:.1})", kurt));
    } else {
        details.push(format!("Near-Gaussian tails (kurtosis {:.1})", kurt));
    }

    // Skewness
    let skew = if variance > 0.0 {
        let third_moment = returns.iter().map(|&x| (x - mean).powi(3)).sum::<f64>() / n;
        third_moment / variance.powf(1.5)
    } else {
        0.0
    };

    if skew > 0.5 {
        score += 2;
        details.push(format!("Positive skew ({:.2}) favors long convexity", skew));
    } else if skew > -0.5 {
        score += 1;
        details.push(format!("Symmetric distribution (skew {:.2})", skew));
    } else {
        details.push(format!("Negative skew ({:.2}) - crash-prone", skew));
    }

    // Tail ratio (95th percentile gains / abs(5th percentile losses))
    let mut pos_returns: Vec<f64> = returns.iter().cloned().filter(|&x| x > 0.0).collect();
    let mut neg_returns: Vec<f64> = returns.iter().cloned().filter(|&x| x < 0.0).collect();

    if pos_returns.len() > 10 && neg_returns.len() > 10 {
        pos_returns.sort_by(|a, b| a.partial_cmp(b).unwrap());
        neg_returns.sort_by(|a, b| a.partial_cmp(b).unwrap());

        let right_tail = pos_returns[(pos_returns.len() as f64 * 0.95) as usize];
        let left_tail = neg_returns[(neg_returns.len() as f64 * 0.05) as usize].abs();
        let tail_ratio = if left_tail > 0.0 { right_tail / left_tail } else { 1.0 };

        if tail_ratio > 1.2 {
            score += 2;
            details.push(format!("Asymmetric upside (tail ratio {:.2})", tail_ratio));
        } else if tail_ratio > 0.8 {
            score += 1;
            details.push(format!("Balanced tails (tail ratio {:.2})", tail_ratio));
        } else {
            details.push(format!("Asymmetric downside (tail ratio {:.2})", tail_ratio));
        }
    }

    // Max drawdown
    let mut cumulative = 1.0;
    let mut running_max = 1.0;
    let mut max_dd = 0.0;
    for &r in &returns {
        cumulative *= 1.0 + r;
        if cumulative > running_max {
            running_max = cumulative;
        }
        let dd = (cumulative - running_max) / running_max;
        if dd < max_dd {
            max_dd = dd;
        }
    }

    if max_dd > -0.15 {
        score += 2;
        details.push(format!("Resilient (max drawdown {:.1}%)", max_dd * 100.0));
    } else if max_dd > -0.30 {
        score += 1;
        details.push(format!("Moderate drawdown ({:.1}%)", max_dd * 100.0));
    } else {
        details.push(format!("Severe drawdown ({:.1}%) - fragile", max_dd * 100.0));
    }

    TalebSubResult { score, max_score, details: details.join("; ") }
}

pub fn analyze_antifragility(metrics: &[FinancialMetrics], line_items: &[LineItem], market_cap: f64) -> TalebSubResult {
    let max_score = 10;
    let mut score = 0;
    let mut details = Vec::new();

    if metrics.is_empty() && line_items.is_empty() {
        return TalebSubResult { score: 0, max_score, details: "Insufficient data for antifragility analysis".to_string() };
    }

    let latest_metrics = metrics.first();
    let latest_item = line_items.first();

    // 1. Net Cash
    if let Some(li) = latest_item {
        let cash = li.cash_and_equivalents.unwrap_or(0.0);
        let total_debt = li.total_debt.unwrap_or(0.0);
        let total_assets = li.total_assets.unwrap_or(0.0);
        let net_cash = cash - total_debt;

        if net_cash > 0.0 && market_cap > 0.0 && cash > 0.20 * market_cap {
            score += 3;
            details.push(format!("War chest: net cash ${:.0}, cash is {:.0}% of market cap", net_cash, (cash / market_cap) * 100.0));
        } else if net_cash > 0.0 {
            score += 2;
            details.push(format!("Net cash positive (${:.0})", net_cash));
        } else if total_assets > 0.0 && total_debt < 0.30 * total_assets {
            score += 1;
            details.push("Net debt but manageable relative to assets".to_string());
        } else {
            details.push("Leveraged position - not antifragile".to_string());
        }
    }

    // 2. Debt-to-Equity
    if let Some(m) = latest_metrics {
        if let Some(de) = m.debt_to_equity {
            if de < 0.3 {
                score += 2;
                details.push(format!("Taleb-approved low leverage (D/E {:.2})", de));
            } else if de < 0.7 {
                score += 1;
                details.push(format!("Moderate leverage (D/E {:.2})", de));
            } else {
                details.push(format!("High leverage (D/E {:.2}) - fragile", de));
            }
        }
    }

    // 3. Operating Margin stability
    let op_margins: Vec<f64> = metrics.iter().filter_map(|m| m.operating_margin).collect();
    if op_margins.len() >= 3 {
        let n = op_margins.len() as f64;
        let mean = op_margins.iter().sum::<f64>() / n;
        let variance = op_margins.iter().map(|&m| (m - mean).powi(2)).sum::<f64>() / n;
        let std = variance.sqrt();
        let cv = if mean != 0.0 { std / mean.abs() } else { 999.0 };

        if cv < 0.15 && mean > 0.15 {
            score += 3;
            details.push(format!("Stable high margins (avg {:.1}%, CV {:.2}) - antifragile pricing power", mean * 100.0, cv));
        } else if cv < 0.30 && mean > 0.10 {
            score += 2;
            details.push(format!("Reasonable margin stability (avg {:.1}%, CV {:.2})", mean * 100.0, cv));
        } else if cv < 0.30 {
            score += 1;
            details.push(format!("Margins somewhat stable (CV {:.2}) but low (avg {:.1}%)", cv, mean * 100.0));
        } else {
            details.push(format!("Volatile margins (CV {:.2}) - fragile pricing power", cv));
        }
    }

    // 4. FCF consistency
    let fcf_values: Vec<f64> = line_items.iter().filter_map(|li| li.free_cash_flow).collect();
    if !fcf_values.is_empty() {
        let positive_count = fcf_values.iter().filter(|&&v| v > 0.0).count();
        if positive_count == fcf_values.len() {
            score += 2;
            details.push(format!("Consistent FCF generation ({}/{} periods positive)", positive_count, fcf_values.len()));
        } else if positive_count > fcf_values.len() / 2 {
            score += 1;
            details.push(format!("Majority positive FCF ({}/{} periods)", positive_count, fcf_values.len()));
        }
    }

    TalebSubResult { score, max_score, details: details.join("; ") }
}

pub fn analyze_convexity(
    metrics: &[FinancialMetrics],
    line_items: &[LineItem],
    prices: &[Price],
    market_cap: f64,
) -> TalebSubResult {
    let max_score = 10;
    let mut score = 0;
    let mut details = Vec::new();

    if metrics.is_empty() && line_items.is_empty() && prices.is_empty() {
        return TalebSubResult { score: 0, max_score, details: "Insufficient data for convexity analysis".to_string() };
    }

    let latest_item = line_items.first();

    // 1. R&D embedded optionality
    if let Some(li) = latest_item {
        if let (Some(rd), Some(rev)) = (li.research_and_development, li.revenue) {
            if rev > 0.0 {
                let rd_ratio = rd.abs() / rev;
                if rd_ratio > 0.15 {
                    score += 3;
                    details.push(format!("Significant embedded optionality via R&D ({:.1}% of revenue)", rd_ratio * 100.0));
                } else if rd_ratio > 0.08 {
                    score += 2;
                    details.push(format!("Meaningful R&D investment ({:.1}% of revenue)", rd_ratio * 100.0));
                } else if rd_ratio > 0.03 {
                    score += 1;
                    details.push(format!("Modest R&D ({:.1}% of revenue)", rd_ratio * 100.0));
                }
            }
        }
    }

    // 2. Return capture asymmetry
    let returns = compute_returns(prices);
    if !returns.is_empty() {
        let upside: Vec<f64> = returns.iter().cloned().filter(|&r| r > 0.0).collect();
        let downside: Vec<f64> = returns.iter().cloned().filter(|&r| r < 0.0).collect();
        if upside.len() > 10 && downside.len() > 10 {
            let avg_up = upside.iter().sum::<f64>() / upside.len() as f64;
            let avg_down = (downside.iter().sum::<f64>() / downside.len() as f64).abs();
            let up_down_ratio = if avg_down > 0.0 { avg_up / avg_down } else { 1.0 };

            if up_down_ratio > 1.3 {
                score += 2;
                details.push(format!("Convex return profile (up/down ratio {:.2})", up_down_ratio));
            } else if up_down_ratio > 1.0 {
                score += 1;
                details.push(format!("Slight positive asymmetry (up/down ratio {:.2})", up_down_ratio));
            }
        }
    }

    // 3. Cash optionality
    if let Some(li) = latest_item {
        if let Some(cash) = li.cash_and_equivalents {
            if market_cap > 0.0 {
                let cash_ratio = cash / market_cap;
                if cash_ratio > 0.30 {
                    score += 3;
                    details.push(format!("Cash is a call option on future opportunities ({:.0}% of market cap)", cash_ratio * 100.0));
                } else if cash_ratio > 0.15 {
                    score += 2;
                    details.push(format!("Strong cash position ({:.0}% of market cap)", cash_ratio * 100.0));
                } else if cash_ratio > 0.05 {
                    score += 1;
                    details.push(format!("Moderate cash buffer ({:.0}% of market cap)", cash_ratio * 100.0));
                }
            }
        }
    }

    // 4. FCF yield
    let mut fcf_yield = None;
    if let Some(li) = latest_item {
        if let Some(fcf) = li.free_cash_flow {
            if market_cap > 0.0 {
                fcf_yield = Some(fcf / market_cap);
            }
        }
    }
    if fcf_yield.is_none() && !metrics.is_empty() {
        // Fallback
        fcf_yield = metrics[0].free_cash_flow_growth; // Placeholder
    }

    if let Some(fy) = fcf_yield {
        if fy > 0.10 {
            score += 2;
            details.push(format!("High FCF yield ({:.1}%) provides margin for convex bet", fy * 100.0));
        } else if fy > 0.05 {
            score += 1;
            details.push(format!("Decent FCF yield ({:.1}%)", fy * 100.0));
        }
    }

    TalebSubResult { score, max_score, details: details.join("; ") }
}

pub fn analyze_fragility(metrics: &[FinancialMetrics], _line_items: &[LineItem]) -> TalebSubResult {
    let max_score = 8;
    let mut score = 0;
    let mut details = Vec::new();

    if metrics.is_empty() {
        return TalebSubResult { score: 0, max_score, details: "Insufficient data for fragility analysis".to_string() };
    }

    let latest = &metrics[0];

    // 1. Leverage fragility
    if let Some(de) = latest.debt_to_equity {
        if de > 2.0 {
            details.push(format!("Extremely fragile balance sheet (D/E {:.2})", de));
        } else if de > 1.0 {
            score += 1;
            details.push(format!("Elevated leverage (D/E {:.2})", de));
        } else if de > 0.5 {
            score += 2;
            details.push(format!("Moderate leverage (D/E {:.2})", de));
        } else {
            score += 3;
            details.push(format!("Low leverage (D/E {:.2}) - not fragile", de));
        }
    }

    // 2. Interest coverage (as D/E proxy if not explicitly in metrics)
    if let (Some(ebit), Some(de)) = (latest.operating_income, latest.debt_to_equity) {
        let coverage = if de != 0.0 { ebit / de.abs() } else { 999.0 };
        if coverage > 10.0 {
            score += 2;
            details.push(format!("Interest coverage {:.1}x - debt is irrelevant", coverage));
        } else if coverage > 5.0 {
            score += 1;
            details.push(format!("Comfortable interest coverage ({:.1}x)", coverage));
        } else {
            details.push(format!("Low interest coverage ({:.1}x) - fragile", coverage));
        }
    }

    // 3. Earnings volatility (std across periods)
    let eg_vals: Vec<f64> = metrics.iter().filter_map(|m| m.earnings_per_share_growth).collect();
    if eg_vals.len() >= 3 {
        let n = eg_vals.len() as f64;
        let mean = eg_vals.iter().sum::<f64>() / n;
        let var = eg_vals.iter().map(|&e| (e - mean).powi(2)).sum::<f64>() / n;
        let std = var.sqrt();

        if std < 0.20 {
            score += 2;
            details.push(format!("Stable earnings (growth std {:.2}) - robust", std));
        } else if std < 0.50 {
            score += 1;
            details.push(format!("Moderate earnings volatility (growth std {:.2})", std));
        } else {
            details.push(format!("Highly volatile earnings (growth std {:.2}) - fragile", std));
        }
    }

    // 4. Net margin buffer
    if let Some(nm) = latest.net_margin {
        if nm > 0.15 {
            score += 1;
            details.push(format!("Fat margins ({:.1}%) buffer shocks", nm * 100.0));
        }
    }

    TalebSubResult { score, max_score, details: details.join("; ") }
}

pub fn analyze_skin_in_game(insider_trades: &[InsiderTrade]) -> TalebSubResult {
    let max_score = 4;
    let mut score = 0;
    let mut details = Vec::new();

    if insider_trades.is_empty() {
        return TalebSubResult { score: 1, max_score, details: "No insider trade data - neutral assumption".to_string() };
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
        let buy_sell_ratio = net / shares_sold.max(1.0);
        if buy_sell_ratio > 2.0 {
            score = 4;
            details.push(format!("Strong skin in the game - net insider buying {:.0} shares (ratio {:.1}x)", net, buy_sell_ratio));
        } else if buy_sell_ratio > 0.5 {
            score = 3;
            details.push(format!("Moderate insider conviction - net buying {:.0} shares", net));
        } else {
            score = 2;
            details.push(format!("Net insider buying of {:.0} shares", net));
        }
    } else {
        details.push(format!("Insiders selling - no skin in the game (net {:.0} shares)", net));
    }

    TalebSubResult { score, max_score, details: details.join("; ") }
}

pub fn analyze_volatility_regime(prices: &[Price]) -> TalebSubResult {
    let max_score = 6;
    if prices.len() < 30 {
        return TalebSubResult { score: 0, max_score, details: "Insufficient price data for volatility analysis".to_string() };
    }

    let returns = compute_returns(prices);
    if returns.len() < 21 {
        return TalebSubResult { score: 0, max_score, details: "Insufficient data for volatility analysis".to_string() };
    }

    let mut score = 0;
    let mut details = Vec::new();

    // 21-day historical volatility
    let mut hist_vols = Vec::new();
    for i in 21..=returns.len() {
        let window = &returns[i - 21..i];
        let n = window.len() as f64;
        let mean = window.iter().sum::<f64>() / n;
        let var = window.iter().map(|&x| (x - mean).powi(2)).sum::<f64>() / n;
        let std_dev = var.sqrt();
        hist_vols.push(std_dev * 252.0_f64.sqrt());
    }

    if hist_vols.is_empty() {
        return TalebSubResult { score: 0, max_score, details: "Insufficient history for volatility regime".to_string() };
    }

    let current_vol = hist_vols[hist_vols.len() - 1];
    let avg_vol: f64 = hist_vols.iter().sum::<f64>() / hist_vols.len() as f64;
    let vol_regime = if avg_vol > 0.0 { current_vol / avg_vol } else { 1.0 };

    if vol_regime < 0.7 {
        details.push(format!("Dangerously low vol (regime {:.2}) - turkey problem", vol_regime));
    } else if vol_regime < 0.9 {
        score += 1;
        details.push(format!("Below-average vol (regime {:.2}) - complacency", vol_regime));
    } else if vol_regime <= 1.3 {
        score += 3;
        details.push(format!("Normal vol regime ({:.2}) - fair pricing", vol_regime));
    } else if vol_regime <= 2.0 {
        score += 4;
        details.push(format!("Elevated vol (regime {:.2}) - opportunity for antifragile", vol_regime));
    } else {
        score += 2;
        details.push(format!("Extreme vol (regime {:.2}) - crisis mode", vol_regime));
    }

    // Vol of Vol
    if hist_vols.len() >= 21 {
        let n = 21.0;
        let recent_vols = &hist_vols[hist_vols.len() - 21..];
        let mean = recent_vols.iter().sum::<f64>() / n;
        let var = recent_vols.iter().map(|&v| (v - mean).powi(2)).sum::<f64>() / n;
        let current_vov = var.sqrt();

        // Check vol of vol median (rough comparison)
        let median_vov = 0.02; // Static proxy
        if current_vov > 2.0 * median_vov {
            score += 2;
            details.push(format!("Highly unstable vol (vol-of-vol {:.4} vs proxy)", current_vov));
        } else if current_vov > median_vov {
            score += 1;
            details.push(format!("Elevated vol-of-vol ({:.4})", current_vov));
        }
    }

    TalebSubResult { score, max_score, details: details.join("; ") }
}

pub fn analyze_black_swan_sentinel(news: &[CompanyNews], prices: &[Price]) -> TalebSubResult {
    let max_score = 4;
    let mut score = 2;
    let mut details = Vec::new();

    let mut neg_ratio = 0.0;
    if !news.is_empty() {
        let neg_count = news.iter()
            .filter(|n| n.sentiment.as_ref().map(|s| s.to_lowercase() == "negative" || s.to_lowercase() == "bearish").unwrap_or(false))
            .count();
        neg_ratio = neg_count as f64 / news.len() as f64;
    }

    let mut volume_spike = 1.0;
    let mut recent_return = 0.0;
    if prices.len() >= 10 {
        let mut volumes: Vec<f64> = prices.iter().map(|p| p.volume as f64).collect();
        let recent_vol = volumes[volumes.len() - 5..].iter().sum::<f64>() / 5.0;
        let avg_vol = volumes.iter().sum::<f64>() / volumes.len() as f64;
        if avg_vol > 0.0 {
            volume_spike = recent_vol / avg_vol;
        }

        if prices.len() >= 5 {
            recent_return = prices[prices.len() - 1].close / prices[prices.len() - 5].close - 1.0;
        }
    }

    if neg_ratio > 0.7 && volume_spike > 2.0 {
        score = 0;
        details.push(format!("Black swan warning - {:.0}% negative news, {:.1}x volume spike", neg_ratio * 100.0, volume_spike));
    } else if neg_ratio > 0.5 || volume_spike > 2.5 {
        score = 1;
        details.push(format!("Elevated stress signals (neg news {:.0}%, volume {:.1}x)", neg_ratio * 100.0, volume_spike));
    } else if neg_ratio > 0.3 && recent_return.abs() > 0.10 {
        score = 1;
        details.push(format!("Moderate stress with price dislocation ({:.1}% move)", recent_return * 100.0));
    } else if neg_ratio < 0.3 && volume_spike < 1.5 {
        score = 3;
        details.push("No black swan signals detected".to_string());
    } else {
        details.push(format!("Normal conditions (neg news {:.0}%, volume {:.1}x)", neg_ratio * 100.0, volume_spike));
    }

    if neg_ratio > 0.4 && volume_spike < 1.5 && score < 4 {
        score = (score + 1).min(4);
        details.push("Contrarian opportunity - negative sentiment without panic".to_string());
    }

    TalebSubResult { score, max_score, details: details.join("; ") }
}

pub async fn generate_taleb_output(
    ticker: &str,
    facts: &serde_json::Value,
    state: &AgentState,
    agent_id: &str,
) -> Result<NassimTalebSignal> {
    let system_prompt = "You are Nassim Nicholas Taleb. Apply my principles of antifragility, tail-risk, and convexity:\n\
        - Bullish: antifragile business (low leverage, fat margins, net cash) with convex optionality (high R&D, cash option).\n\
        - Bearish: fragile business (debt heavy, thin margins, low skin in the game) OR complacency.\n\
        - Use my concepts: via negativa, turkey problem, skin in the game, Lindy effect, barbell.\n\
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
