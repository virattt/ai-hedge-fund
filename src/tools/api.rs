// Source: src/tools/api.py
//! Sibling to src/tools/api.py
//! Financial API Client to query stock prices, news, metrics, and financials from financialdatasets.ai.

use anyhow::{Result, Context};
use std::env;
use std::time::Duration;
use crate::data::cache::get_cache;
use crate::data::models::{
    Price, PriceResponse, FinancialMetrics, FinancialMetricsResponse,
    LineItem, LineItemResponse, InsiderTrade, InsiderTradeResponse,
    CompanyNews, CompanyNewsResponse
};

/// Performs an API request to financialdatasets.ai, handling rate limiting backoffs.
pub async fn make_api_request(
    url: &str,
    method: &str,
    json_data: Option<serde_json::Value>,
    api_key: Option<&str>,
) -> Result<serde_json::Value> {
    let client = reqwest::Client::new();
    let mut builder = if method.eq_ignore_ascii_case("POST") {
        client.post(url)
    } else {
        client.get(url)
    };

    // Inject financial datasets API key
    let resolved_key = api_key
        .map(|k| k.to_string())
        .or_else(|| env::var("FINANCIAL_DATASETS_API_KEY").ok());

    if let Some(key) = resolved_key {
        builder = builder.header("X-API-KEY", key);
    }

    if let Some(body) = json_data {
        builder = builder.json(&body);
    }

    let max_retries = 3;
    for attempt in 0..=max_retries {
        let req = builder.try_clone().context("Failed to clone request builder")?;
        let response = req.send().await;

        match response {
            Ok(res) => {
                let status = res.status();
                if status == reqwest::StatusCode::TOO_MANY_REQUESTS && attempt < max_retries {
                    let delay = 60 + (30 * attempt);
                    println!(
                        "Rate limited (429). Attempt {}/{}. Waiting {}s before retrying...",
                        attempt + 1,
                        max_retries + 1,
                        delay
                    );
                    tokio::time::sleep(Duration::from_secs(delay)).await;
                    continue;
                }

                if !status.is_success() {
                    let err_text = res.text().await.unwrap_or_default();
                    anyhow::bail!("API request failed with status: {} - {}", status, err_text);
                }

                let parsed_json = res.json::<serde_json::Value>().await?;
                return Ok(parsed_json);
            }
            Err(e) => {
                if attempt < max_retries {
                    let delay = 2_u64.pow(attempt as u32) * 2;
                    tokio::time::sleep(Duration::from_secs(delay)).await;
                    continue;
                }
                return Err(anyhow::Error::from(e).context("HTTP request failed after retries"));
            }
        }
    }

    anyhow::bail!("API request failed after retrying.")
}

/// Fetch historical daily price records for a ticker.
pub async fn get_prices(
    ticker: &str,
    start_date: &str,
    end_date: &str,
    api_key: Option<&str>,
) -> Result<Vec<Price>> {
    let cache_key = format!("{}_{}_{}", ticker, start_date, end_date);
    let cache = get_cache();
    
    // Check in-memory cache
    if let Some(cached) = cache.lock().unwrap().get_prices(&cache_key) {
        return Ok(cached);
    }

    let url = format!(
        "https://api.financialdatasets.ai/prices/?ticker={}&interval=day&interval_multiplier=1&start_date={}&end_date={}",
        ticker, start_date, end_date
    );

    let res_json = make_api_request(&url, "GET", None, api_key).await?;
    let parsed: PriceResponse = serde_json::from_value(res_json)?;
    let prices = parsed.prices;

    if !prices.is_empty() {
        cache.lock().unwrap().set_prices(&cache_key, prices.clone());
    }

    Ok(prices)
}

/// Fetch key financial metrics (ttm, quarterly) up to a date.
pub async fn get_financial_metrics(
    ticker: &str,
    end_date: &str,
    period: &str,
    limit: u32,
    api_key: Option<&str>,
) -> Result<Vec<FinancialMetrics>> {
    let cache_key = format!("{}_{}_{}_{}", ticker, period, end_date, limit);
    let cache = get_cache();

    if let Some(cached) = cache.lock().unwrap().get_financial_metrics(&cache_key) {
        return Ok(cached);
    }

    let url = format!(
        "https://api.financialdatasets.ai/financial-metrics/?ticker={}&report_period_lte={}&limit={}&period={}",
        ticker, end_date, limit, period
    );

    let res_json = make_api_request(&url, "GET", None, api_key).await?;
    let parsed: FinancialMetricsResponse = serde_json::from_value(res_json)?;
    let metrics = parsed.financial_metrics;

    if !metrics.is_empty() {
        cache.lock().unwrap().set_financial_metrics(&cache_key, metrics.clone());
    }

    Ok(metrics)
}

/// Searches and returns financial line item metrics (balance sheets, cash flows, etc.).
pub async fn search_line_items(
    ticker: &str,
    line_items: Vec<String>,
    end_date: &str,
    period: &str,
    limit: u32,
    api_key: Option<&str>,
) -> Result<Vec<LineItem>> {
    let cache_key = format!("{}_{}_{}_{}", ticker, period, end_date, limit);
    let cache = get_cache();

    if let Some(cached) = cache.lock().unwrap().get_line_items(&cache_key) {
        return Ok(cached);
    }

    let url = "https://api.financialdatasets.ai/financials/search/line-items";
    let body = serde_json::json!({
        "tickers": vec![ticker],
        "line_items": line_items,
        "end_date": end_date,
        "period": period,
        "limit": limit
    });

    let res_json = make_api_request(url, "POST", Some(body), api_key).await?;
    let parsed: LineItemResponse = serde_json::from_value(res_json)?;
    let mut items = parsed.search_results;

    if items.len() > limit as usize {
        items.truncate(limit as usize);
    }

    if !items.is_empty() {
        cache.lock().unwrap().set_line_items(&cache_key, items.clone());
    }

    Ok(items)
}

/// Fetch insider trading records for a ticker.
pub async fn get_insider_trades(
    ticker: &str,
    end_date: &str,
    start_date: Option<&str>,
    limit: u32,
    api_key: Option<&str>,
) -> Result<Vec<InsiderTrade>> {
    let cache_key = format!("{}_{:?}_{}_{}", ticker, start_date, end_date, limit);
    let cache = get_cache();

    if let Some(cached) = cache.lock().unwrap().get_insider_trades(&cache_key) {
        return Ok(cached);
    }

    let mut all_trades = Vec::new();
    let mut current_end_date = end_date.to_string();

    loop {
        let mut url = format!(
            "https://api.financialdatasets.ai/insider-trades/?ticker={}&filing_date_lte={}",
            ticker, current_end_date
        );
        if let Some(start) = start_date {
            url.push_str(&format!("&filing_date_gte={}", start));
        }
        url.push_str(&format!("&limit={}", limit));

        let res_json = make_api_request(&url, "GET", None, api_key).await?;
        let parsed: InsiderTradeResponse = serde_json::from_value(res_json)?;
        let trades = parsed.insider_trades;

        if trades.is_empty() {
            break;
        }

        all_trades.extend(trades.clone());

        if start_date.is_none() || trades.len() < limit as usize {
            break;
        }

        // Get the oldest date from the batch to paginate backwards
        let oldest_date = trades
            .iter()
            .map(|t| t.filing_date.split('T').next().unwrap_or("").to_string())
            .min()
            .unwrap_or_default();

        if oldest_date.is_empty() || oldest_date.as_str() <= start_date.unwrap() {
            break;
        }

        current_end_date = oldest_date;
    }

    if !all_trades.is_empty() {
        cache.lock().unwrap().set_insider_trades(&cache_key, all_trades.clone());
    }

    Ok(all_trades)
}

/// Fetch recent company news headlines and pre-calculated sentiment data.
pub async fn get_company_news(
    ticker: &str,
    end_date: &str,
    start_date: Option<&str>,
    limit: u32,
    api_key: Option<&str>,
) -> Result<Vec<CompanyNews>> {
    let cache_key = format!("{}_{:?}_{}_{}", ticker, start_date, end_date, limit);
    let cache = get_cache();

    if let Some(cached) = cache.lock().unwrap().get_company_news(&cache_key) {
        return Ok(cached);
    }

    let mut all_news = Vec::new();
    let mut current_end_date = end_date.to_string();

    loop {
        let mut url = format!(
            "https://api.financialdatasets.ai/news/?ticker={}&end_date={}",
            ticker, current_end_date
        );
        if let Some(start) = start_date {
            url.push_str(&format!("&start_date={}", start));
        }
        url.push_str(&format!("&limit={}", limit));

        let res_json = make_api_request(&url, "GET", None, api_key).await?;
        let parsed: CompanyNewsResponse = serde_json::from_value(res_json)?;
        let news = parsed.news;

        if news.is_empty() {
            break;
        }

        all_news.extend(news.clone());

        if start_date.is_none() || news.len() < limit as usize {
            break;
        }

        let oldest_date = news
            .iter()
            .map(|n| n.date.split('T').next().unwrap_or("").to_string())
            .min()
            .unwrap_or_default();

        if oldest_date.is_empty() || oldest_date.as_str() <= start_date.unwrap() {
            break;
        }

        current_end_date = oldest_date;
    }

    if !all_news.is_empty() {
        cache.lock().unwrap().set_company_news(&cache_key, all_news.clone());
    }

    Ok(all_news)
}

/// Fetches the latest market capitalization.
pub async fn get_market_cap(
    ticker: &str,
    end_date: &str,
    api_key: Option<&str>,
) -> Result<Option<f64>> {
    // If end_date matches today's date, we query company facts
    let today = chrono::Local::now().format("%Y-%m-%d").to_string();
    if end_date == today {
        let url = format!("https://api.financialdatasets.ai/company/facts/?ticker={}", ticker);
        let res_json = make_api_request(&url, "GET", None, api_key).await?;
        if let Some(facts) = res_json.get("company_facts") {
            if let Some(mcap) = facts.get("market_cap") {
                return Ok(mcap.as_f64());
            }
        }
        return Ok(None);
    }

    let metrics = get_financial_metrics(ticker, end_date, "ttm", 1, api_key).await?;
    if let Some(m0) = metrics.first() {
        return Ok(m0.market_cap);
    }

    Ok(None)
}
