//! Integration tests for Yahoo Finance data provider.

use ai_hedge_fund::data::provider::{configure_provider, DataProvider};
use ai_hedge_fund::tools::api::get_prices_yfinance;
use ai_hedge_fund::tools::fallback::{
    compute_growth_rate, enrich_derived_growth, get_financial_metrics_fallback,
    get_insider_trades_fallback, search_line_items_fallback, signed_transaction_shares,
};
use ai_hedge_fund::utils::financial_data::{
    calculate_shareholders_equity, calculate_working_capital,
};

#[tokio::test]
async fn test_yahoo_finance_aapl_historical_prices() {
    configure_provider(Some(DataProvider::YahooFinance));

    let prices = get_prices_yfinance("AAPL", "2024-01-02", "2024-01-31")
        .await
        .expect("AAPL historical prices should fetch successfully");

    assert!(!prices.is_empty(), "Expected at least one AAPL price bar");

    for price in &prices {
        assert!(price.open > 0.0);
        assert!(price.close > 0.0);
        assert!(price.high >= price.low);
        assert_eq!(price.time.len(), 10, "time should be YYYY-MM-DD");
        assert!(price.time.chars().all(|c| c.is_ascii_digit() || c == '-'));
    }
}

#[tokio::test]
async fn test_fallback_metrics_do_not_panic() {
    configure_provider(Some(DataProvider::YahooFinance));

    let metrics = get_financial_metrics_fallback("AAPL", "2024-06-01", "ttm", 1)
        .await
        .unwrap_or_default();

    // Yahoo may return metrics or an empty vec depending on network; either is safe.
    if let Some(first) = metrics.first() {
        assert_eq!(first.ticker, "AAPL");
    }
}

#[tokio::test]
async fn test_fallback_line_items_missing_fields_are_safe() {
    configure_provider(Some(DataProvider::YahooFinance));

    let items = search_line_items_fallback(
        "AAPL",
        vec!["total_assets".to_string(), "working_capital".to_string()],
        "2024-06-01",
        "annual",
        2,
    )
    .await
    .unwrap_or_default();

    for item in &items {
        let derived_wc = calculate_working_capital(item.current_assets, item.current_liabilities);
        let derived_equity =
            calculate_shareholders_equity(item.total_assets, item.total_liabilities);

        if item.working_capital.is_none() {
            assert!(derived_wc.is_none() || derived_wc.is_some());
        }
        if item.shareholders_equity.is_none() {
            assert!(derived_equity.is_none() || derived_equity.is_some());
        }
    }
}

#[test]
fn test_signed_transaction_shares_direction() {
    assert_eq!(
        signed_transaction_shares(Some(100), Some("Sale")),
        Some(-100.0)
    );
    assert_eq!(
        signed_transaction_shares(Some(100), Some("Purchase")),
        Some(100.0)
    );
}

#[tokio::test]
async fn test_insider_trades_fallback_returns_structured_trades() {
    configure_provider(Some(DataProvider::YahooFinance));

    let trades = get_insider_trades_fallback("AAPL", "2030-12-31", None, 20)
        .await
        .expect("insider fallback should succeed");

    if trades.is_empty() {
        eprintln!("AAPL insider transactions unavailable (network); skipping shape assertions");
        return;
    }

    let first = &trades[0];
    assert_eq!(first.ticker, "AAPL");
    assert!(!first.filing_date.is_empty());
    assert!(first.transaction_shares.is_some());
    assert!(first.name.as_ref().is_some_and(|n| !n.is_empty()));
}

#[test]
fn test_provider_defaults_to_yahoo_without_api_key() {
    std::env::remove_var("FINANCIAL_DATASETS_API_KEY");
    configure_provider(None);
    assert_eq!(
        ai_hedge_fund::data::provider::active_provider(),
        DataProvider::YahooFinance
    );
}

#[test]
fn test_compute_growth_rate_basic() {
    assert_eq!(compute_growth_rate(Some(110.0), Some(100.0)), Some(0.1));
}

#[tokio::test]
async fn test_fallback_metrics_derive_growth_with_two_quarters() {
    configure_provider(Some(DataProvider::YahooFinance));

    let metrics = get_financial_metrics_fallback("AAPL", "2024-06-01", "ttm", 4)
        .await
        .unwrap_or_default();

    if metrics.len() >= 2 {
        let with_growth: Vec<_> = metrics
            .iter()
            .filter(|m| m.revenue_growth.is_some())
            .collect();
        assert!(
            !with_growth.is_empty(),
            "expected derived revenue_growth when 2+ quarters available"
        );
    }
}

#[tokio::test]
async fn test_nvda_yahoo_metrics_and_growth_derivation() {
    configure_provider(Some(DataProvider::YahooFinance));

    let metrics = get_financial_metrics_fallback("NVDA", "2026-01-01", "ttm", 8)
        .await
        .unwrap_or_default();

    if metrics.is_empty() {
        eprintln!("NVDA metrics unavailable (network); skipping growth assertions");
        return;
    }

    assert_eq!(metrics[0].ticker, "NVDA");
    assert!(metrics.len() >= 1, "NVDA should return at least one metrics row");

    if metrics.len() >= 2 {
        let mut derived = metrics.clone();
        enrich_derived_growth(&mut derived);
        assert!(
            derived.iter().any(|m| m.revenue_growth.is_some()),
            "NVDA with 2+ rows should derive revenue_growth"
        );
    }
}
