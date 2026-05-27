use serde::{Deserialize, Serialize};

pub type Price = ai_hedge_fund::data::models::Price;
pub type FinancialMetrics = ai_hedge_fund::data::models::FinancialMetrics;
pub type InsiderTrade = ai_hedge_fund::data::models::InsiderTrade;
pub type CompanyNews = ai_hedge_fund::data::models::CompanyNews;

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct CompanyFacts {
    pub ticker: String,
    #[serde(default = "default_true")]
    pub is_active: bool,
    pub name: Option<String>,
    pub cik: Option<String>,
    pub sector: Option<String>,
    pub industry: Option<String>,
    pub category: Option<String>,
    pub exchange: Option<String>,
    pub location: Option<String>,
    pub sec_filings_url: Option<String>,
    pub sic_code: Option<String>,
    pub sic_industry: Option<String>,
    pub sic_sector: Option<String>,
    pub market_cap: Option<f64>,
}

fn default_true() -> bool {
    true
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct EarningsData {
    pub revenue: Option<f64>,
    pub estimated_revenue: Option<f64>,
    pub revenue_surprise: Option<String>,
    pub earnings_per_share: Option<f64>,
    pub estimated_earnings_per_share: Option<f64>,
    pub eps_surprise: Option<String>,
    pub net_income: Option<f64>,
    pub gross_profit: Option<f64>,
    pub operating_income: Option<f64>,
    pub weighted_average_shares: Option<f64>,
    pub weighted_average_shares_diluted: Option<f64>,
    pub free_cash_flow: Option<f64>,
    pub cash_and_equivalents: Option<f64>,
    pub total_debt: Option<f64>,
    pub total_assets: Option<f64>,
    pub total_liabilities: Option<f64>,
    pub shareholders_equity: Option<f64>,
    pub net_cash_flow_from_operations: Option<f64>,
    pub capital_expenditure: Option<f64>,
    pub net_cash_flow_from_investing: Option<f64>,
    pub net_cash_flow_from_financing: Option<f64>,
    pub change_in_cash_and_equivalents: Option<f64>,
    pub revenue_chg: Option<f64>,
    pub net_income_chg: Option<f64>,
    pub operating_income_chg: Option<f64>,
    pub gross_profit_chg: Option<f64>,
    pub free_cash_flow_chg: Option<f64>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct Earnings {
    pub ticker: String,
    pub report_period: String,
    pub fiscal_period: Option<String>,
    pub currency: Option<String>,
    pub quarterly: Option<EarningsData>,
    pub annual: Option<EarningsData>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct EarningsRecord {
    pub ticker: String,
    pub report_period: String,
    pub source_type: String,
    pub filing_date: Option<String>,
    pub filing_datetime: Option<String>,
    pub filing_window: Option<String>,
    pub fiscal_period: Option<String>,
    pub currency: Option<String>,
    pub filing_url: Option<String>,
    pub accession_number: Option<String>,
    pub quarterly: Option<EarningsData>,
    pub annual: Option<EarningsData>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct Filing {
    pub ticker: Option<String>,
    pub cik: Option<String>,
    pub accession_number: Option<String>,
    pub filing_type: Option<String>,
    pub filing_date: Option<String>,
    pub report_period: Option<String>,
    pub document_count: Option<i32>,
    pub is_xbrl: Option<bool>,
    pub url: Option<String>,
}
