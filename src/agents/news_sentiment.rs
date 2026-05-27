// Source: src/agents/news_sentiment.py
//! Sibling to src/agents/news_sentiment.py
//! Analyzes recent news sentiment for tickers using a combined mathematical and LLM-assisted approach.

use anyhow::{Result, Context};
use std::collections::HashMap;
use crate::graph::state::AgentState;
use crate::tools::api::get_company_news;
use crate::data::models::CompanyNews;
use crate::utils::llm::call_llm;

#[derive(Debug, serde::Serialize, serde::Deserialize, Default)]
pub struct Sentiment {
    pub sentiment: String,   // "positive" | "negative" | "neutral"
    pub confidence: u32,     // 0-100
}

pub async fn news_sentiment_agent(state: &mut AgentState, agent_id: &str) -> Result<()> {
    println!("Running News Sentiment Agent: {}", agent_id);

    let end_date = state.data.get("end_date")
        .and_then(|v| v.as_str())
        .context("Missing end_date in news_sentiment_agent")?;
    
    let tickers_json = state.data.get("tickers")
        .context("Missing tickers in news_sentiment_agent")?;
    let tickers: Vec<String> = serde_json::from_value(tickers_json.clone())?;

    let api_key = state.metadata.get("FINANCIAL_DATASETS_API_KEY")
        .and_then(|v| v.as_str());

    let mut sentiment_analysis = serde_json::Map::new();

    for ticker in &tickers {
        let mut company_news = get_company_news(ticker, end_date, None, 100, api_key).await.unwrap_or_default();
        let mut news_signals = Vec::new();
        let mut sentiment_confidences = HashMap::new();
        let mut sentiments_classified_by_llm = 0;

        if !company_news.is_empty() {
            // We want to inspect the 10 most recent articles
            let limit_len = 10.min(company_news.len());
            let mut articles_to_classify = Vec::new();
            for i in 0..limit_len {
                if company_news[i].sentiment.is_none() {
                    articles_to_classify.push(i);
                }
            }

            // Limit LLM classification to 5 articles
            let classify_limit = 5.min(articles_to_classify.len());
            for i in 0..classify_limit {
                let idx = articles_to_classify[i];
                let headline = &company_news[idx].title;

                let system_prompt = "You are a financial news sentiment analyzer. Classify headline sentiment for the specified ticker only.";
                let user_prompt = format!(
                    "Please analyze the sentiment of the following news headline with the following context:\n\
                    Ticker: {}\n\
                    Headline: {}\n\n\
                    Determine if sentiment is 'positive', 'negative', or 'neutral'.\n\
                    Return JSON matching: {{\"sentiment\": \"positive\" | \"negative\" | \"neutral\", \"confidence\": int}}",
                    ticker, headline
                );

                let classification: Sentiment = call_llm(
                    system_prompt,
                    &user_prompt,
                    Some(agent_id),
                    Some(state),
                    3,
                ).await.unwrap_or_default();

                let resolved_sentiment = if classification.sentiment.is_empty() {
                    "neutral".to_string()
                } else {
                    classification.sentiment.to_lowercase()
                };

                company_news[idx].sentiment = Some(resolved_sentiment.clone());
                sentiment_confidences.insert(company_news[idx].url.clone(), classification.confidence);
                sentiments_classified_by_llm += 1;
            }

            // Collect all news signals
            for news in &company_news {
                if let Some(ref s) = news.sentiment {
                    let sig = match s.as_str() {
                        "negative" | "bearish" => "bearish",
                        "positive" | "bullish" => "bullish",
                        _ => "neutral",
                    };
                    news_signals.push(sig.to_string());
                }
            }
        }

        let bullish_signals = news_signals.iter().filter(|&s| s == "bullish").count();
        let bearish_signals = news_signals.iter().filter(|&s| s == "bearish").count();
        let neutral_signals = news_signals.iter().filter(|&s| s == "neutral").count();

        let overall_signal = if bullish_signals > bearish_signals {
            "bullish"
        } else if bearish_signals > bullish_signals {
            "bearish"
        } else {
            "neutral"
        };

        let total_signals = news_signals.len();
        let confidence = calculate_confidence_score(
            &sentiment_confidences,
            &company_news,
            overall_signal,
            bullish_signals,
            bearish_signals,
            total_signals,
        );

        let reasoning = serde_json::json!({
            "news_sentiment": {
                "signal": overall_signal,
                "confidence": confidence,
                "metrics": {
                    "total_articles": total_signals,
                    "bullish_articles": bullish_signals,
                    "bearish_articles": bearish_signals,
                    "neutral_articles": neutral_signals,
                    "articles_classified_by_llm": sentiments_classified_by_llm,
                }
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

    let analyst_signals = state.data.entry("analyst_signals".to_string())
        .or_insert_with(|| serde_json::json!({}));
    if let Some(obj) = analyst_signals.as_object_mut() {
        obj.insert(agent_id.to_string(), serde_json::Value::Object(sentiment_analysis));
    }

    Ok(())
}

fn calculate_confidence_score(
    sentiment_confidences: &HashMap<String, u32>,
    company_news: &[CompanyNews],
    overall_signal: &str,
    bullish_signals: usize,
    bearish_signals: usize,
    total_signals: usize,
) -> f64 {
    if total_signals == 0 {
        return 0.0;
    }

    let max_sig = bullish_signals.max(bearish_signals) as f64;
    let signal_proportion = (max_sig / total_signals as f64) * 100.0;

    if !sentiment_confidences.is_empty() {
        let mut llm_confidences = Vec::new();
        for news in company_news {
            if let Some(ref s) = news.sentiment {
                let is_match = (overall_signal == "bullish" && (s == "positive" || s == "bullish"))
                    || (overall_signal == "bearish" && (s == "negative" || s == "bearish"))
                    || (overall_signal == "neutral" && s == "neutral");

                if is_match {
                    if let Some(&conf) = sentiment_confidences.get(&news.url) {
                        llm_confidences.push(conf as f64);
                    }
                }
            }
        }

        if !llm_confidences.is_empty() {
            let avg_llm_confidence = llm_confidences.iter().sum::<f64>() / llm_confidences.len() as f64;
            let blended = 0.7 * avg_llm_confidence + 0.3 * signal_proportion;
            return (blended * 100.0).round() / 100.0;
        }
    }

    (signal_proportion * 100.0).round() / 100.0
}
