// Source: src/data/models.py
//! Sibling to src/data/models.py
//! Definitions of primary data schemas for prices, news, metrics, portfolio holdings, and analyst recommendations.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct Price {
    pub open: f64,
    pub close: f64,
    pub high: f64,
    pub low: f64,
    pub volume: i64,
    pub time: String,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct PriceResponse {
    pub ticker: String,
    pub prices: Vec<Price>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct FinancialMetrics {
    pub ticker: String,
    pub report_period: String,
    pub period: String,
    pub currency: String,
    pub market_cap: Option<f64>,
    pub enterprise_value: Option<f64>,
    pub price_to_earnings_ratio: Option<f64>,
    pub price_to_book_ratio: Option<f64>,
    pub price_to_sales_ratio: Option<f64>,
    pub enterprise_value_to_ebitda_ratio: Option<f64>,
    pub enterprise_value_to_revenue_ratio: Option<f64>,
    pub free_cash_flow_yield: Option<f64>,
    pub peg_ratio: Option<f64>,
    pub gross_margin: Option<f64>,
    pub operating_margin: Option<f64>,
    pub net_margin: Option<f64>,
    pub return_on_equity: Option<f64>,
    pub return_on_assets: Option<f64>,
    pub return_on_invested_capital: Option<f64>,
    pub asset_turnover: Option<f64>,
    pub inventory_turnover: Option<f64>,
    pub receivables_turnover: Option<f64>,
    pub days_sales_outstanding: Option<f64>,
    pub operating_cycle: Option<f64>,
    pub working_capital_turnover: Option<f64>,
    pub current_ratio: Option<f64>,
    pub quick_ratio: Option<f64>,
    pub cash_ratio: Option<f64>,
    pub operating_cash_flow_ratio: Option<f64>,
    pub debt_to_equity: Option<f64>,
    pub debt_to_assets: Option<f64>,
    pub interest_coverage: Option<f64>,
    pub revenue_growth: Option<f64>,
    pub earnings_growth: Option<f64>,
    pub book_value_growth: Option<f64>,
    pub earnings_per_share_growth: Option<f64>,
    pub free_cash_flow_growth: Option<f64>,
    pub operating_income_growth: Option<f64>,
    pub ebitda_growth: Option<f64>,
    pub payout_ratio: Option<f64>,
    pub earnings_per_share: Option<f64>,
    pub book_value_per_share: Option<f64>,
    pub free_cash_flow_per_share: Option<f64>,
    pub revenue: Option<f64>,
    pub beta: Option<f64>,
    pub operating_income: Option<f64>,
    pub free_cash_flow: Option<f64>,
    pub ev_to_ebit: Option<f64>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct FinancialMetricsResponse {
    pub financial_metrics: Vec<FinancialMetrics>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct LineItem {
    pub ticker: String,
    pub report_period: String,
    pub period: String,
    pub currency: String,
    
    // Dynamic fields representing the standard line items (we represent them as options)
    pub capital_expenditure: Option<f64>,
    pub depreciation_and_amortization: Option<f64>,
    pub net_income: Option<f64>,
    pub outstanding_shares: Option<i64>,
    pub total_assets: Option<f64>,
    pub total_liabilities: Option<f64>,
    pub shareholders_equity: Option<f64>,
    pub dividends_and_other_cash_distributions: Option<f64>,
    pub issuance_or_purchase_of_equity_shares: Option<f64>,
    pub gross_profit: Option<f64>,
    pub revenue: Option<f64>,
    pub free_cash_flow: Option<f64>,
    pub working_capital: Option<f64>,

    // Additional fields for various superstar agents
    pub earnings_per_share: Option<f64>,
    pub current_assets: Option<f64>,
    pub current_liabilities: Option<f64>,
    pub book_value_per_share: Option<f64>,
    pub operating_margin: Option<f64>,
    pub return_on_invested_capital: Option<f64>,
    pub gross_margin: Option<f64>,
    pub total_debt: Option<f64>,
    pub cash_and_equivalents: Option<f64>,
    pub operating_income: Option<f64>,
    pub ebit: Option<f64>,
    pub ebitda: Option<f64>,
    pub debt_to_equity: Option<f64>,
    pub goodwill_and_intangible_assets: Option<f64>,
    pub operating_expense: Option<f64>,
    pub research_and_development: Option<f64>,
    pub interest_expense: Option<f64>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct LineItemResponse {
    pub search_results: Vec<LineItem>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct InsiderTrade {
    pub ticker: String,
    pub issuer: Option<String>,
    pub name: Option<String>,
    pub title: Option<String>,
    pub is_board_director: Option<bool>,
    pub transaction_date: Option<String>,
    pub transaction_shares: Option<f64>,
    pub transaction_price_per_share: Option<f64>,
    pub transaction_value: Option<f64>,
    pub shares_owned_before_transaction: Option<f64>,
    pub shares_owned_after_transaction: Option<f64>,
    pub security_title: Option<String>,
    pub filing_date: String,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct InsiderTradeResponse {
    pub insider_trades: Vec<InsiderTrade>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct CompanyNews {
    pub ticker: String,
    pub title: String,
    pub author: Option<String>,
    pub source: String,
    pub date: String,
    pub url: String,
    pub sentiment: Option<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct CompanyNewsResponse {
    pub news: Vec<CompanyNews>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct Position {
    #[serde(default)]
    pub cash: f64,
    #[serde(default)]
    pub shares: i64,
    pub ticker: String,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct Portfolio {
    pub positions: HashMap<String, Position>,
    #[serde(default)]
    pub total_cash: f64,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct AnalystSignal {
    pub signal: Option<String>,
    pub confidence: Option<f64>,
    pub reasoning: Option<serde_json::Value>,
    pub max_position_size: Option<f64>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct TickerAnalysis {
    pub ticker: String,
    pub analyst_signals: HashMap<String, AnalystSignal>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct AgentStateData {
    pub tickers: Vec<String>,
    pub portfolio: Portfolio,
    pub start_date: String,
    pub end_date: String,
    pub ticker_analyses: HashMap<String, TickerAnalysis>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct AgentStateMetadata {
    #[serde(default)]
    pub show_reasoning: bool,
}
