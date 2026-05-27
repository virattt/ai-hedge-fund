use async_trait::async_trait;
use super::protocol::DataClient;
use super::models::{Price, FinancialMetrics, CompanyNews, InsiderTrade, CompanyFacts, Earnings, EarningsRecord};

pub struct FDClient {
    pub api_key: Option<String>,
}

impl FDClient {
    pub fn new(api_key: Option<String>) -> Self {
        Self { api_key }
    }

    pub async fn get_market_cap(&self, ticker: &str, end_date: &str) -> Option<f64> {
        if let Some(facts) = self.get_company_facts(ticker).await {
            if let Some(mcap) = facts.market_cap {
                return Some(mcap);
            }
        }
        let metrics = self.get_financial_metrics(ticker, end_date, "ttm", 1).await;
        if let Some(m0) = metrics.first() {
            return m0.market_cap;
        }
        None
    }

    pub async fn get_earnings_history(&self, ticker: &str, limit: u32) -> Vec<EarningsRecord> {
        let url = format!("https://api.financialdatasets.ai/earnings/?ticker={}&limit={}", ticker, limit);
        let res_json = match ai_hedge_fund::tools::api::make_api_request(&url, "GET", None, self.api_key.as_deref()).await {
            Ok(v) => v,
            Err(_) => return Vec::new(),
        };
        let earnings_arr = match res_json.get("earnings").and_then(|v| v.as_array()) {
            Some(a) => a,
            None => return Vec::new(),
        };
        serde_json::from_value(serde_json::Value::Array(earnings_arr.clone())).unwrap_or_default()
    }
}

#[async_trait]
impl DataClient for FDClient {
    async fn get_prices(&self, ticker: &str, start_date: &str, end_date: &str) -> Vec<Price> {
        ai_hedge_fund::tools::api::get_prices(ticker, start_date, end_date, self.api_key.as_deref())
            .await
            .unwrap_or_default()
    }

    async fn get_financial_metrics(&self, ticker: &str, end_date: &str, period: &str, limit: u32) -> Vec<FinancialMetrics> {
        ai_hedge_fund::tools::api::get_financial_metrics(ticker, end_date, period, limit, self.api_key.as_deref())
            .await
            .unwrap_or_default()
    }

    async fn get_news(&self, ticker: &str, end_date: &str, start_date: Option<&str>, limit: u32) -> Vec<CompanyNews> {
        ai_hedge_fund::tools::api::get_company_news(ticker, end_date, start_date, limit, self.api_key.as_deref())
            .await
            .unwrap_or_default()
    }

    async fn get_insider_trades(&self, ticker: &str, end_date: &str, start_date: Option<&str>, limit: u32) -> Vec<InsiderTrade> {
        ai_hedge_fund::tools::api::get_insider_trades(ticker, end_date, start_date, limit, self.api_key.as_deref())
            .await
            .unwrap_or_default()
    }

    async fn get_company_facts(&self, ticker: &str) -> Option<CompanyFacts> {
        let url = format!("https://api.financialdatasets.ai/company/facts/?ticker={}", ticker);
        let res_json = ai_hedge_fund::tools::api::make_api_request(&url, "GET", None, self.api_key.as_deref()).await.ok()?;
        let facts_val = res_json.get("company_facts")?;
        serde_json::from_value(facts_val.clone()).ok()
    }

    async fn get_earnings(&self, ticker: &str) -> Option<Earnings> {
        let url = format!("https://api.financialdatasets.ai/earnings/?ticker={}&limit=1", ticker);
        let res_json = ai_hedge_fund::tools::api::make_api_request(&url, "GET", None, self.api_key.as_deref()).await.ok()?;
        let earnings_arr = res_json.get("earnings")?.as_array()?;
        let first = earnings_arr.first()?;
        serde_json::from_value(first.clone()).ok()
    }
}
