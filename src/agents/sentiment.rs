// Source: src/agents/sentiment.py
//! Sibling to src/agents/sentiment.py
//! Analyzes market sentiment by aggregating insider transaction volumes and company news sentiment.

use anyhow::{Result, Context};
use crate::graph::state::AgentState;
use crate::tools::api::{get_insider_trades, get_company_news};

/// Performs insider trading and news sentiment analysis, updating agent state.
pub async fn sentiment_analyst_agent(state: &mut AgentState, agent_id: &str) -> Result<()> {
    println!("Running Sentiment Analyst Agent: {}", agent_id);

    let end_date = state.data.get("end_date")
        .and_then(|v| v.as_str())
        .context("Missing end_date in sentiment_analyst_agent")?;

    let tickers_json = state.data.get("tickers")
        .context("Missing tickers in sentiment_analyst_agent")?;
    let tickers: Vec<String> = serde_json::from_value(tickers_json.clone())?;

    let api_key = state.metadata.get("FINANCIAL_DATASETS_API_KEY")
        .and_then(|v| v.as_str());

    let mut sentiment_analysis = serde_json::Map::new();

    for ticker in &tickers {
        // Fetch insider trades
        let insider_trades = get_insider_trades(ticker, end_date, None, 1000, api_key)
            .await
            .unwrap_or_default();

        // Get the signals from the insider trades
        let transaction_shares: Vec<f64> = insider_trades
            .iter()
            .filter_map(|t| t.transaction_shares)
            .collect();

        let insider_signals: Vec<&str> = transaction_shares
            .iter()
            .map(|&shares| if shares < 0.0 { "bearish" } else { "bullish" })
            .collect();

        // Fetch company news
        let company_news = get_company_news(ticker, end_date, None, 100, api_key)
            .await
            .unwrap_or_default();

        // Get the sentiment from the company news
        let sentiments: Vec<String> = company_news
            .iter()
            .filter_map(|n| n.sentiment.clone())
            .collect();

        let news_signals: Vec<&str> = sentiments
            .iter()
            .map(|s| {
                if s == "negative" {
                    "bearish"
                } else if s == "positive" {
                    "bullish"
                } else {
                    "neutral"
                }
            })
            .collect();

        // Combine signals from both sources with weights
        let insider_weight = 0.3;
        let news_weight = 0.7;

        let insider_bullish_count = insider_signals.iter().filter(|&&s| s == "bullish").count() as f64;
        let insider_bearish_count = insider_signals.iter().filter(|&&s| s == "bearish").count() as f64;

        let news_bullish_count = news_signals.iter().filter(|&&s| s == "bullish").count() as f64;
        let news_bearish_count = news_signals.iter().filter(|&&s| s == "bearish").count() as f64;
        let news_neutral_count = news_signals.iter().filter(|&&s| s == "neutral").count() as f64;

        // Calculate weighted signal counts
        let bullish_signals = insider_bullish_count * insider_weight + news_bullish_count * news_weight;
        let bearish_signals = insider_bearish_count * insider_weight + news_bearish_count * news_weight;

        let overall_signal = if bullish_signals > bearish_signals {
            "bullish"
        } else if bearish_signals > bullish_signals {
            "bearish"
        } else {
            "neutral"
        };

        // Calculate confidence level based on the weighted proportion
        let total_weighted_signals = (insider_signals.len() as f64) * insider_weight + (news_signals.len() as f64) * news_weight;
        let mut confidence = 0.0;
        if total_weighted_signals > 0.0 {
            let max_signals = if bullish_signals > bearish_signals { bullish_signals } else { bearish_signals };
            confidence = ((max_signals / total_weighted_signals) * 100.0 * 100.0).round() / 100.0;
        }

        let insider_signal = if insider_bullish_count > insider_bearish_count {
            "bullish"
        } else if insider_bearish_count > insider_bullish_count {
            "bearish"
        } else {
            "neutral"
        };

        let max_insider_count = if insider_bullish_count > insider_bearish_count { insider_bullish_count } else { insider_bearish_count };
        let insider_confidence = if !insider_signals.is_empty() {
            ((max_insider_count / insider_signals.len() as f64) * 100.0).round() as u64
        } else {
            0
        };

        let news_signal = if news_bullish_count > news_bearish_count {
            "bullish"
        } else if news_bearish_count > news_bullish_count {
            "bearish"
        } else {
            "neutral"
        };

        let max_news_count = if news_bullish_count > news_bearish_count { news_bullish_count } else { news_bearish_count };
        let news_confidence = if !news_signals.is_empty() {
            ((max_news_count / news_signals.len() as f64) * 100.0).round() as u64
        } else {
            0
        };

        let reasoning = serde_json::json!({
            "insider_trading": {
                "signal": insider_signal,
                "confidence": insider_confidence,
                "metrics": {
                    "total_trades": insider_signals.len(),
                    "bullish_trades": insider_bullish_count,
                    "bearish_trades": insider_bearish_count,
                    "weight": insider_weight,
                    "weighted_bullish": ((insider_bullish_count * insider_weight) * 10.0).round() / 10.0,
                    "weighted_bearish": ((insider_bearish_count * insider_weight) * 10.0).round() / 10.0,
                }
            },
            "news_sentiment": {
                "signal": news_signal,
                "confidence": news_confidence,
                "metrics": {
                    "total_articles": news_signals.len(),
                    "bullish_articles": news_bullish_count,
                    "bearish_articles": news_bearish_count,
                    "neutral_articles": news_neutral_count,
                    "weight": news_weight,
                    "weighted_bullish": ((news_bullish_count * news_weight) * 10.0).round() / 10.0,
                    "weighted_bearish": ((news_bearish_count * news_weight) * 10.0).round() / 10.0,
                }
            },
            "combined_analysis": {
                "total_weighted_bullish": (bullish_signals * 10.0).round() / 10.0,
                "total_weighted_bearish": (bearish_signals * 10.0).round() / 10.0,
                "signal_determination": format!(
                    "{} based on weighted signal comparison",
                    if bullish_signals > bearish_signals { "Bullish" } else if bearish_signals > bullish_signals { "Bearish" } else { "Neutral" }
                )
            }
        });

        sentiment_analysis.insert(
            ticker.clone(),
            serde_json::json!({
                "signal": overall_signal,
                "confidence": confidence,
                "reasoning": reasoning,
            }),
        );
    }

    // Print the reasoning if show_reasoning is enabled
    let show_reasoning = state.metadata.get("show_reasoning")
        .and_then(|v| v.as_bool())
        .unwrap_or(false);

    if show_reasoning {
        crate::graph::state::show_agent_reasoning(&serde_json::json!(sentiment_analysis), "Sentiment Analysis Agent");
    }

    // Add sentiment analysis to state's analyst signals
    let analyst_signals = state.data.entry("analyst_signals".to_string())
        .or_insert_with(|| serde_json::json!({}));
    if let Some(obj) = analyst_signals.as_object_mut() {
        obj.insert(agent_id.to_string(), serde_json::Value::Object(sentiment_analysis.clone()));
    }

    // Add a HumanMessage representing the aggregate analysis to the state messages list
    let message = serde_json::json!({
        "content": serde_json::to_string(&sentiment_analysis)?,
        "name": agent_id,
        "type": "human",
    });
    state.messages.push(message);

    Ok(())
}

