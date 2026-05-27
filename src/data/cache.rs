// Source: src/data/cache.py
//! Sibling to src/data/cache.py
//! Provides thread-safe in-memory caching for retrieved prices, metrics, and news.

use crate::data::models::{CompanyNews, FinancialMetrics, InsiderTrade, LineItem, Price};
use std::collections::{HashMap, HashSet};
use std::sync::{Arc, Mutex, OnceLock};

/// Thread-safe in-memory cache for API results.
#[derive(Debug, Default)]
pub struct Cache {
    pub prices_cache: HashMap<String, Vec<Price>>,
    pub financial_metrics_cache: HashMap<String, Vec<FinancialMetrics>>,
    pub line_items_cache: HashMap<String, Vec<LineItem>>,
    pub insider_trades_cache: HashMap<String, Vec<InsiderTrade>>,
    pub company_news_cache: HashMap<String, Vec<CompanyNews>>,
}

impl Cache {
    pub fn new() -> Self {
        Self::default()
    }

    /// Generic data merger that prevents duplicates based on key fields.
    fn merge_data<T, F, K>(&self, existing: Option<&Vec<T>>, new_data: Vec<T>, key_fn: F) -> Vec<T>
    where
        T: Clone,
        K: Eq + std::hash::Hash,
        F: Fn(&T) -> K,
    {
        let mut merged = existing.cloned().unwrap_or_default();
        let mut existing_keys = merged.iter().map(&key_fn).collect::<HashSet<_>>();
        for item in new_data {
            let key = key_fn(&item);
            if !existing_keys.contains(&key) {
                existing_keys.insert(key);
                merged.push(item);
            }
        }
        merged
    }

    pub fn get_prices(&self, ticker: &str) -> Option<Vec<Price>> {
        self.prices_cache.get(ticker).cloned()
    }

    pub fn set_prices(&mut self, ticker: &str, data: Vec<Price>) {
        let existing = self.prices_cache.get(ticker);
        let merged = self.merge_data(existing, data, |p| p.time.clone());
        self.prices_cache.insert(ticker.to_string(), merged);
    }

    pub fn get_financial_metrics(&self, ticker: &str) -> Option<Vec<FinancialMetrics>> {
        self.financial_metrics_cache.get(ticker).cloned()
    }

    pub fn set_financial_metrics(&mut self, ticker: &str, data: Vec<FinancialMetrics>) {
        let existing = self.financial_metrics_cache.get(ticker);
        let merged = self.merge_data(existing, data, |m| m.report_period.clone());
        self.financial_metrics_cache
            .insert(ticker.to_string(), merged);
    }

    pub fn get_line_items(&self, ticker: &str) -> Option<Vec<LineItem>> {
        self.line_items_cache.get(ticker).cloned()
    }

    pub fn set_line_items(&mut self, ticker: &str, data: Vec<LineItem>) {
        let existing = self.line_items_cache.get(ticker);
        let merged = self.merge_data(existing, data, |li| li.report_period.clone());
        self.line_items_cache.insert(ticker.to_string(), merged);
    }

    pub fn get_insider_trades(&self, ticker: &str) -> Option<Vec<InsiderTrade>> {
        self.insider_trades_cache.get(ticker).cloned()
    }

    pub fn set_insider_trades(&mut self, ticker: &str, data: Vec<InsiderTrade>) {
        let existing = self.insider_trades_cache.get(ticker);
        let merged = self.merge_data(existing, data, |it| it.filing_date.clone());
        self.insider_trades_cache.insert(ticker.to_string(), merged);
    }

    pub fn get_company_news(&self, ticker: &str) -> Option<Vec<CompanyNews>> {
        self.company_news_cache.get(ticker).cloned()
    }

    pub fn set_company_news(&mut self, ticker: &str, data: Vec<CompanyNews>) {
        let existing = self.company_news_cache.get(ticker);
        let merged = self.merge_data(existing, data, |n| n.date.clone());
        self.company_news_cache.insert(ticker.to_string(), merged);
    }
}

/// Retrieves the global cache instance.
pub fn get_cache() -> Arc<Mutex<Cache>> {
    static CACHE: OnceLock<Arc<Mutex<Cache>>> = OnceLock::new();
    CACHE
        .get_or_init(|| Arc::new(Mutex::new(Cache::new())))
        .clone()
}
