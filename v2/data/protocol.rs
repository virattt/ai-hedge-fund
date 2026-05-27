use async_trait::async_trait;
use super::models::{Price, FinancialMetrics, CompanyNews, InsiderTrade, CompanyFacts, Earnings};

#[async_trait]
pub trait DataClient: Send + Sync {
    async fn get_prices(&self, ticker: &str, start_date: &str, end_date: &str) -> Vec<Price>;
    async fn get_financial_metrics(&self, ticker: &str, end_date: &str, period: &str, limit: u32) -> Vec<FinancialMetrics>;
    async fn get_news(&self, ticker: &str, end_date: &str, start_date: Option<&str>, limit: u32) -> Vec<CompanyNews>;
    async fn get_insider_trades(&self, ticker: &str, end_date: &str, start_date: Option<&str>, limit: u32) -> Vec<InsiderTrade>;
    async fn get_company_facts(&self, ticker: &str) -> Option<CompanyFacts>;
    async fn get_earnings(&self, ticker: &str) -> Option<Earnings>;
}
