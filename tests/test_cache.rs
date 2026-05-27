// Source: tests/test_cache.rs
//! Mathematical and logical verification of the thread-safe Cache manager.

use ai_hedge_fund::data::cache::{get_cache, Cache};
use ai_hedge_fund::data::models::Price;

#[test]
fn test_new_cache_has_empty_stores() {
    let cache = Cache::new();
    assert!(cache.get_prices("AAPL").is_none());
    assert!(cache.get_financial_metrics("AAPL").is_none());
    assert!(cache.get_line_items("AAPL").is_none());
    assert!(cache.get_insider_trades("AAPL").is_none());
    assert!(cache.get_company_news("AAPL").is_none());
}

#[test]
fn test_get_cache_singleton() {
    let c1 = get_cache();
    let c2 = get_cache();
    // They should be pointing to the same Arc
    assert!(std::sync::Arc::ptr_eq(&c1, &c2));
}

#[test]
fn test_prices_set_and_get() {
    let mut cache = Cache::new();
    let prices = vec![Price {
        close: 150.0,
        high: 151.0,
        low: 149.0,
        open: 149.5,
        time: "2024-01-01".to_string(),
        volume: 1000000,
    }];
    cache.set_prices("AAPL", prices.clone());

    let retrieved = cache.get_prices("AAPL").unwrap();
    assert_eq!(retrieved.len(), 1);
    assert_eq!(retrieved[0].close, 150.0);
    assert_eq!(retrieved[0].time, "2024-01-01");
}

#[test]
fn test_prices_deduplication() {
    let mut cache = Cache::new();
    let p1 = vec![Price {
        close: 150.0,
        high: 151.0,
        low: 149.0,
        open: 149.5,
        time: "2024-01-01".to_string(),
        volume: 1000000,
    }];

    let p2 = vec![
        Price {
            close: 999.0, // duplicate date, should be ignored
            high: 151.0,
            low: 149.0,
            open: 149.5,
            time: "2024-01-01".to_string(),
            volume: 1000000,
        },
        Price {
            close: 155.0, // new date, should be added
            high: 156.0,
            low: 154.0,
            open: 154.5,
            time: "2024-01-02".to_string(),
            volume: 1000000,
        },
    ];

    cache.set_prices("AAPL", p1);
    cache.set_prices("AAPL", p2);

    let retrieved = cache.get_prices("AAPL").unwrap();
    assert_eq!(retrieved.len(), 2);
    // The first price close should remain 150.0 (original preserved)
    assert_eq!(retrieved[0].close, 150.0);
    assert_eq!(retrieved[0].time, "2024-01-01");
    // The second price close should be 155.0
    assert_eq!(retrieved[1].close, 155.0);
    assert_eq!(retrieved[1].time, "2024-01-02");
}

#[test]
fn test_independent_tickers() {
    let mut cache = Cache::new();
    let p_aapl = vec![Price {
        close: 150.0,
        high: 151.0,
        low: 149.0,
        open: 149.5,
        time: "2024-01-01".to_string(),
        volume: 1000000,
    }];
    let p_msft = vec![Price {
        close: 400.0,
        high: 401.0,
        low: 399.0,
        open: 399.5,
        time: "2024-01-01".to_string(),
        volume: 2000000,
    }];

    cache.set_prices("AAPL", p_aapl);
    cache.set_prices("MSFT", p_msft);

    assert_eq!(cache.get_prices("AAPL").unwrap()[0].close, 150.0);
    assert_eq!(cache.get_prices("MSFT").unwrap()[0].close, 400.0);
}
