// Source: src/agents/growth_agent.py
//! Sibling to src/agents/growth_agent.py
//! Analyzes stocks using a growth-focused mathematical framework.

use anyhow::{Context, Result};
use crate::data::models::{FinancialMetrics, InsiderTrade};
use crate::graph::state::AgentState;
use crate::tools::api::{get_financial_metrics, get_insider_trades};

pub const MIN_FULL_PERIODS: usize = 4;
pub const MIN_PARTIAL_PERIODS: usize = 2;
const PARTIAL_CONFIDENCE_CAP: u32 = 50;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DataTier {
    Full,
    Partial,
    Minimal,
}

pub fn classify_data_tier(row_count: usize) -> DataTier {
    if row_count >= MIN_FULL_PERIODS {
        DataTier::Full
    } else if row_count >= MIN_PARTIAL_PERIODS {
        DataTier::Partial
    } else {
        DataTier::Minimal
    }
}

pub async fn growth_analyst_agent(state: &mut AgentState, agent_id: &str) -> Result<()> {
    println!("Running Growth Analyst Agent: {}", agent_id);

    let end_date = state
        .data
        .get("end_date")
        .and_then(|v| v.as_str())
        .context("Missing end_date in growth_analyst_agent")?;

    let tickers_json = state
        .data
        .get("tickers")
        .context("Missing tickers in growth_analyst_agent")?;
    let tickers: Vec<String> = serde_json::from_value(tickers_json.clone())?;

    let api_key = state
        .metadata
        .get("FINANCIAL_DATASETS_API_KEY")
        .and_then(|v| v.as_str());

    let mut growth_analysis = serde_json::Map::new();

    for ticker in &tickers {
        let metrics =
            get_financial_metrics(ticker, end_date, "ttm", 12, api_key).await.unwrap_or_default();
        let tier = classify_data_tier(metrics.len());

        if tier == DataTier::Minimal {
            println!(
                "Growth analyst: insufficient metrics for {} ({} rows) — neutral signal",
                ticker,
                metrics.len()
            );
            growth_analysis.insert(
                ticker.clone(),
                serde_json::json!({
                    "signal": "neutral",
                    "confidence": 0,
                    "reasoning": {
                        "data_tier": "minimal",
                        "period_count": metrics.len(),
                        "final_analysis": {
                            "signal": "neutral",
                            "confidence": 0,
                            "weighted_score": 0.5,
                        }
                    },
                }),
            );
            continue;
        }

        if tier == DataTier::Partial {
            println!(
                "Growth analyst: partial data for {} ({} rows) — level-based scoring",
                ticker,
                metrics.len()
            );
        }

        let insider_trades =
            get_insider_trades(ticker, end_date, None, 1000, api_key).await.unwrap_or_default();
        let most_recent_metrics = &metrics[0];
        let include_trends = tier == DataTier::Full;

        let growth_trends = analyze_growth_trends(&metrics, include_trends);
        let valuation_metrics = analyze_valuation(most_recent_metrics);
        let margin_trends = analyze_margin_trends(&metrics, include_trends);
        let insider_conviction = analyze_insider_conviction(&insider_trades);
        let financial_health = check_financial_health(most_recent_metrics);

        let (growth_w, valuation_w, margin_w, insider_w, health_w) = scoring_weights(tier);

        let weighted_score: f64 = growth_trends.score * growth_w
            + valuation_metrics.score * valuation_w
            + margin_trends.score * margin_w
            + insider_conviction.score * insider_w
            + financial_health.score * health_w;

        let signal = if weighted_score > 0.6 {
            "bullish"
        } else if weighted_score < 0.4 {
            "bearish"
        } else {
            "neutral"
        };

        let confidence = confidence_for_tier(tier, weighted_score);

        let reasoning = serde_json::json!({
            "data_tier": match tier {
                DataTier::Full => "full",
                DataTier::Partial => "partial",
                DataTier::Minimal => "minimal",
            },
            "period_count": metrics.len(),
            "historical_growth": {
                "score": growth_trends.score,
                "revenue_growth": growth_trends.revenue_growth,
                "revenue_trend": growth_trends.revenue_trend,
                "eps_growth": growth_trends.eps_growth,
                "eps_trend": growth_trends.eps_trend,
                "fcf_growth": growth_trends.fcf_growth,
                "fcf_trend": growth_trends.fcf_trend,
            },
            "growth_valuation": {
                "score": valuation_metrics.score,
                "peg_ratio": valuation_metrics.peg_ratio,
                "price_to_sales_ratio": valuation_metrics.price_to_sales_ratio,
            },
            "margin_expansion": {
                "score": margin_trends.score,
                "gross_margin": margin_trends.gross_margin,
                "gross_margin_trend": margin_trends.gross_margin_trend,
                "operating_margin": margin_trends.operating_margin,
                "operating_margin_trend": margin_trends.operating_margin_trend,
                "net_margin": margin_trends.net_margin,
                "net_margin_trend": margin_trends.net_margin_trend,
            },
            "insider_conviction": {
                "score": insider_conviction.score,
                "net_flow_ratio": insider_conviction.net_flow_ratio,
                "buys": insider_conviction.buys,
                "sells": insider_conviction.sells,
            },
            "financial_health": {
                "score": financial_health.score,
                "debt_to_equity": financial_health.debt_to_equity,
                "current_ratio": financial_health.current_ratio,
            },
            "final_analysis": {
                "signal": signal,
                "confidence": confidence,
                "weighted_score": (weighted_score * 100.0).round() / 100.0,
            }
        });

        growth_analysis.insert(
            ticker.clone(),
            serde_json::json!({
                "signal": signal,
                "confidence": confidence,
                "reasoning": reasoning,
            }),
        );
    }

    let analyst_signals = state
        .data
        .entry("analyst_signals".to_string())
        .or_insert_with(|| serde_json::json!({}));
    if let Some(obj) = analyst_signals.as_object_mut() {
        obj.insert(agent_id.to_string(), serde_json::Value::Object(growth_analysis));
    }

    Ok(())
}

fn scoring_weights(tier: DataTier) -> (f64, f64, f64, f64, f64) {
    match tier {
        DataTier::Full => (0.40, 0.25, 0.15, 0.10, 0.10),
        DataTier::Partial => (0.30, 0.30, 0.20, 0.10, 0.10),
        DataTier::Minimal => (0.0, 0.0, 0.0, 0.0, 0.0),
    }
}

pub fn confidence_for_tier(tier: DataTier, weighted_score: f64) -> u32 {
    let raw = ((weighted_score - 0.5).abs() * 2.0 * 100.0).round() as u32;
    match tier {
        DataTier::Full => raw,
        DataTier::Partial => raw.min(PARTIAL_CONFIDENCE_CAP),
        DataTier::Minimal => 0,
    }
}

pub fn calculate_trend(data: &[Option<f64>]) -> f64 {
    let clean_data: Vec<f64> = data.iter().filter_map(|&d| d).collect();
    if clean_data.len() < 2 {
        return 0.0;
    }

    let y = clean_data;
    let n = y.len() as f64;
    let x: Vec<f64> = (0..y.len()).map(|i| i as f64).collect();

    let sum_x: f64 = x.iter().sum();
    let sum_y: f64 = y.iter().sum();
    let sum_xy: f64 = x.iter().zip(y.iter()).map(|(&xi, &yi)| xi * yi).sum();
    let sum_x2: f64 = x.iter().map(|&xi| xi * xi).sum();

    let denominator = n * sum_x2 - sum_x * sum_x;
    if denominator == 0.0 {
        return 0.0;
    }

    (n * sum_xy - sum_x * sum_y) / denominator
}

/// Compute trend slope from a newest-first series by reversing to oldest→newest.
pub fn trend_from_newest_first(series: &[Option<f64>]) -> f64 {
    let mut chronological: Vec<Option<f64>> = series.to_vec();
    chronological.reverse();
    calculate_trend(&chronological)
}

pub struct GrowthTrendsResult {
    pub score: f64,
    pub revenue_growth: Option<f64>,
    pub revenue_trend: f64,
    pub eps_growth: Option<f64>,
    pub eps_trend: f64,
    pub fcf_growth: Option<f64>,
    pub fcf_trend: f64,
}

pub fn analyze_growth_trends(metrics: &[FinancialMetrics], include_trends: bool) -> GrowthTrendsResult {
    let rev_growth: Vec<Option<f64>> = metrics.iter().map(|m| m.revenue_growth).collect();
    let eps_growth: Vec<Option<f64>> = metrics.iter().map(|m| m.earnings_per_share_growth).collect();
    let fcf_growth: Vec<Option<f64>> = metrics.iter().map(|m| m.free_cash_flow_growth).collect();

    let rev_trend = trend_from_newest_first(&rev_growth);
    let eps_trend = trend_from_newest_first(&eps_growth);
    let fcf_trend = trend_from_newest_first(&fcf_growth);

    let mut score = 0.0_f64;

    if let Some(Some(rg)) = rev_growth.first() {
        if *rg > 0.20 {
            score += 0.4;
        } else if *rg > 0.10 {
            score += 0.2;
        }
        if include_trends && rev_trend > 0.0 {
            score += 0.1;
        }
    }

    if let Some(Some(eg)) = eps_growth.first() {
        if *eg > 0.20 {
            score += 0.25;
        } else if *eg > 0.10 {
            score += 0.1;
        }
        if include_trends && eps_trend > 0.0 {
            score += 0.05;
        }
    }

    if let Some(Some(fg)) = fcf_growth.first() {
        if *fg > 0.15 {
            score += 0.1;
        }
        if include_trends && fcf_trend > 0.0 {
            score += 0.05;
        }
    }

    GrowthTrendsResult {
        score: score.min(1.0),
        revenue_growth: rev_growth.first().copied().flatten(),
        revenue_trend: rev_trend,
        eps_growth: eps_growth.first().copied().flatten(),
        eps_trend,
        fcf_growth: fcf_growth.first().copied().flatten(),
        fcf_trend,
    }
}

pub struct GrowthValResult {
    pub score: f64,
    pub peg_ratio: Option<f64>,
    pub price_to_sales_ratio: Option<f64>,
}

pub fn analyze_valuation(metrics: &FinancialMetrics) -> GrowthValResult {
    let peg_ratio = metrics.peg_ratio;
    let ps_ratio = metrics.price_to_sales_ratio;

    let mut score = 0.0_f64;

    if let Some(peg) = peg_ratio {
        if peg < 1.0 {
            score += 0.5;
        } else if peg < 2.0 {
            score += 0.25;
        }
    }

    if let Some(ps) = ps_ratio {
        if ps < 2.0 {
            score += 0.5;
        } else if ps < 5.0 {
            score += 0.25;
        }
    }

    GrowthValResult {
        score: score.min(1.0),
        peg_ratio,
        price_to_sales_ratio: ps_ratio,
    }
}

pub struct MarginTrendsResult {
    pub score: f64,
    pub gross_margin: Option<f64>,
    pub gross_margin_trend: f64,
    pub operating_margin: Option<f64>,
    pub operating_margin_trend: f64,
    pub net_margin: Option<f64>,
    pub net_margin_trend: f64,
}

pub fn analyze_margin_trends(metrics: &[FinancialMetrics], include_trends: bool) -> MarginTrendsResult {
    let gross_margins: Vec<Option<f64>> = metrics.iter().map(|m| m.gross_margin).collect();
    let operating_margins: Vec<Option<f64>> = metrics.iter().map(|m| m.operating_margin).collect();
    let net_margins: Vec<Option<f64>> = metrics.iter().map(|m| m.net_margin).collect();

    let gm_trend = trend_from_newest_first(&gross_margins);
    let om_trend = trend_from_newest_first(&operating_margins);
    let nm_trend = trend_from_newest_first(&net_margins);

    let mut score = 0.0_f64;

    if let Some(Some(gm)) = gross_margins.first() {
        if *gm > 0.5 {
            score += 0.2;
        }
        if include_trends && gm_trend > 0.0 {
            score += 0.2;
        }
    }

    if let Some(Some(om)) = operating_margins.first() {
        if *om > 0.15 {
            score += 0.2;
        }
        if include_trends && om_trend > 0.0 {
            score += 0.2;
        }
    }

    if include_trends && nm_trend > 0.0 {
        score += 0.2;
    }

    MarginTrendsResult {
        score: score.min(1.0),
        gross_margin: gross_margins.first().copied().flatten(),
        gross_margin_trend: gm_trend,
        operating_margin: operating_margins.first().copied().flatten(),
        operating_margin_trend: om_trend,
        net_margin: net_margins.first().copied().flatten(),
        net_margin_trend: nm_trend,
    }
}

pub struct InsiderConvictionResult {
    pub score: f64,
    pub net_flow_ratio: f64,
    pub buys: f64,
    pub sells: f64,
}

pub fn analyze_insider_conviction(trades: &[InsiderTrade]) -> InsiderConvictionResult {
    let mut buys = 0.0;
    let mut sells = 0.0;

    for trade in trades {
        if let (Some(val), Some(shares)) = (trade.transaction_value, trade.transaction_shares) {
            if shares > 0.0 {
                buys += val;
            } else {
                sells += val.abs();
            }
        }
    }

    let net_flow_ratio = if (buys + sells) == 0.0 {
        0.0
    } else {
        (buys - sells) / (buys + sells)
    };

    let score = if net_flow_ratio > 0.5 {
        1.0
    } else if net_flow_ratio > 0.1 {
        0.7
    } else if net_flow_ratio > -0.1 {
        0.5
    } else {
        0.2
    };

    InsiderConvictionResult {
        score,
        net_flow_ratio,
        buys,
        sells,
    }
}

pub struct HealthResult {
    pub score: f64,
    pub debt_to_equity: Option<f64>,
    pub current_ratio: Option<f64>,
}

pub fn check_financial_health(metrics: &FinancialMetrics) -> HealthResult {
    let debt_to_equity = metrics.debt_to_equity;
    let current_ratio = metrics.current_ratio;

    let mut score = 1.0_f64;

    if let Some(de) = debt_to_equity {
        if de > 1.5 {
            score -= 0.5;
        } else if de > 0.8 {
            score -= 0.2;
        }
    }

    if let Some(cr) = current_ratio {
        if cr < 1.0 {
            score -= 0.5;
        } else if cr < 1.5 {
            score -= 0.2;
        }
    }

    HealthResult {
        score: score.max(0.0),
        debt_to_equity,
        current_ratio,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::data::models::FinancialMetrics;

    fn metric_with_growth(
        revenue_growth: Option<f64>,
        eps_growth: Option<f64>,
        fcf_growth: Option<f64>,
    ) -> FinancialMetrics {
        FinancialMetrics {
            ticker: "TEST".to_string(),
            report_period: "2024-01-01".to_string(),
            period: "ttm".to_string(),
            currency: "USD".to_string(),
            market_cap: None,
            enterprise_value: None,
            price_to_earnings_ratio: None,
            price_to_book_ratio: None,
            price_to_sales_ratio: None,
            enterprise_value_to_ebitda_ratio: None,
            enterprise_value_to_revenue_ratio: None,
            free_cash_flow_yield: None,
            peg_ratio: None,
            gross_margin: None,
            operating_margin: None,
            net_margin: None,
            return_on_equity: None,
            return_on_assets: None,
            return_on_invested_capital: None,
            asset_turnover: None,
            inventory_turnover: None,
            receivables_turnover: None,
            days_sales_outstanding: None,
            operating_cycle: None,
            working_capital_turnover: None,
            current_ratio: None,
            quick_ratio: None,
            cash_ratio: None,
            operating_cash_flow_ratio: None,
            debt_to_equity: None,
            debt_to_assets: None,
            interest_coverage: None,
            revenue_growth,
            earnings_growth: None,
            book_value_growth: None,
            earnings_per_share_growth: eps_growth,
            free_cash_flow_growth: fcf_growth,
            operating_income_growth: None,
            ebitda_growth: None,
            payout_ratio: None,
            earnings_per_share: None,
            book_value_per_share: None,
            free_cash_flow_per_share: None,
            revenue: None,
            beta: None,
            operating_income: None,
            free_cash_flow: None,
            ev_to_ebit: None,
        }
    }

    #[test]
    fn classify_data_tier_boundaries() {
        assert_eq!(classify_data_tier(0), DataTier::Minimal);
        assert_eq!(classify_data_tier(1), DataTier::Minimal);
        assert_eq!(classify_data_tier(2), DataTier::Partial);
        assert_eq!(classify_data_tier(3), DataTier::Partial);
        assert_eq!(classify_data_tier(4), DataTier::Full);
    }

    #[test]
    fn trend_from_newest_first_positive_for_accelerating_growth() {
        // newest first: decelerating if read naively, accelerating oldest→newest
        let series = vec![
            Some(0.25),
            Some(0.20),
            Some(0.15),
            Some(0.10),
        ];
        let slope = trend_from_newest_first(&series);
        assert!(slope > 0.0, "expected positive slope for accelerating growth, got {slope}");
    }

    #[test]
    fn partial_tier_caps_confidence() {
        assert_eq!(confidence_for_tier(DataTier::Partial, 0.9), PARTIAL_CONFIDENCE_CAP);
        assert_eq!(confidence_for_tier(DataTier::Minimal, 0.9), 0);
        assert_eq!(confidence_for_tier(DataTier::Full, 0.9), 80);
    }

    #[test]
    fn partial_scoring_omits_trend_bonuses() {
        let metrics = vec![
            metric_with_growth(Some(0.25), Some(0.25), Some(0.20)),
            metric_with_growth(Some(0.10), Some(0.10), Some(0.05)),
        ];
        let with_trends = analyze_growth_trends(&metrics, true);
        let without_trends = analyze_growth_trends(&metrics, false);
        assert!(with_trends.score >= without_trends.score);
        assert!(without_trends.score > 0.0);
    }
}
