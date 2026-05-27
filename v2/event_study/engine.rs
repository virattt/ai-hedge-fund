use super::data::client::FDClient;
use super::data::models::EarningsRecord;
use super::data::protocol::DataClient;
use super::models::{AggregateResult, EventCAR, EventStudyResult, WindowStats};
use super::stats::{bootstrap_ci, compute_abnormal_returns, fit_market_model, sum_car, ttest_cars};
use chrono::{Duration, NaiveDate};
use std::collections::HashMap;

const MARKET_TICKER: &str = "SPY";
const ESTIMATION_START: i64 = -250;
const ESTIMATION_END: i64 = -11;
const MIN_ESTIMATION_DAYS: usize = 200;
const MAX_EVENT_WINDOW: usize = 20;
const RETROSPECTIVE_CUTOFF_DAYS: i64 = 45;
const CAR_WINDOWS: &[(usize, usize)] = &[(0, 1), (0, 5), (0, 20)];

pub async fn compute_car(
    tickers: &[String],
    fd_client: &FDClient,
    earnings_limit: u32,
    n_bootstrap: i32,
    rng_seed: Option<u64>,
    require_eps_surprise: bool,
) -> EventStudyResult {
    let today_str = chrono::Utc::now().format("%Y-%m-%d").to_string();

    let spy_prices = fd_client
        .get_prices(MARKET_TICKER, "2023-01-01", &today_str)
        .await;
    if spy_prices.is_empty() {
        return EventStudyResult {
            events: Vec::new(),
            aggregates: Vec::new(),
            skipped_tickers: tickers.to_vec(),
        };
    }

    let mut spy_closes = HashMap::new();
    for p in &spy_prices {
        let date_part = p.time.split('T').next().unwrap_or("").to_string();
        if !date_part.is_empty() {
            spy_closes.insert(date_part, p.close);
        }
    }

    let mut all_events = Vec::new();
    let mut skipped_tickers = Vec::new();

    for ticker in tickers {
        let events = compute_ticker_events(ticker, fd_client, &spy_closes, earnings_limit).await;
        if !events.is_empty() {
            all_events.extend(events);
        } else {
            skipped_tickers.push(ticker.clone());
        }
    }

    if require_eps_surprise {
        all_events.retain(|e| e.eps_surprise.is_some());
    }

    let aggregates = aggregate(&all_events, n_bootstrap, rng_seed);

    EventStudyResult {
        events: all_events,
        aggregates,
        skipped_tickers,
    }
}

async fn compute_ticker_events(
    ticker: &str,
    fd_client: &FDClient,
    spy_closes: &HashMap<String, f64>,
    earnings_limit: u32,
) -> Vec<EventCAR> {
    let records = fd_client.get_earnings_history(ticker, earnings_limit).await;
    if records.is_empty() {
        return Vec::new();
    }

    let records = filter_retrospective(records);
    if records.is_empty() {
        return Vec::new();
    }

    let mut min_date = NaiveDate::MAX;
    let mut max_date = NaiveDate::MIN;
    for r in &records {
        if let Some(d) = parse_date(&r.filing_date) {
            if d < min_date {
                min_date = d;
            }
            if d > max_date {
                max_date = d;
            }
        }
    }

    if min_date == NaiveDate::MAX || max_date == NaiveDate::MIN {
        return Vec::new();
    }

    let price_start = (min_date - Duration::days(400))
        .format("%Y-%m-%d")
        .to_string();
    let today = chrono::Utc::now().naive_utc().date();
    let needed_end = max_date + Duration::days(35);
    let price_end = if needed_end < today {
        needed_end
    } else {
        today
    }
    .format("%Y-%m-%d")
    .to_string();

    let stock_prices = fd_client.get_prices(ticker, &price_start, &price_end).await;
    if stock_prices.is_empty() {
        return Vec::new();
    }

    let mut stock_closes = HashMap::new();
    for p in &stock_prices {
        let date_part = p.time.split('T').next().unwrap_or("").to_string();
        if !date_part.is_empty() {
            stock_closes.insert(date_part, p.close);
        }
    }

    let mut trading_days = Vec::new();
    for date_key in stock_closes.keys() {
        if spy_closes.contains_key(date_key) {
            trading_days.push(date_key.clone());
        }
    }
    trading_days.sort();

    if trading_days.len() < MIN_ESTIMATION_DAYS + MAX_EVENT_WINDOW {
        return Vec::new();
    }

    let mut stock_close_arr = Vec::new();
    let mut spy_close_arr = Vec::new();
    for d in &trading_days {
        stock_close_arr.push(*stock_closes.get(d).unwrap());
        spy_close_arr.push(*spy_closes.get(d).unwrap());
    }

    let mut stock_returns = Vec::new();
    let mut spy_returns = Vec::new();
    for i in 0..(trading_days.len() - 1) {
        stock_returns.push((stock_close_arr[i + 1] - stock_close_arr[i]) / stock_close_arr[i]);
        spy_returns.push((spy_close_arr[i + 1] - spy_close_arr[i]) / spy_close_arr[i]);
    }
    let return_days = trading_days[1..].to_vec();

    let mut day_to_idx = HashMap::new();
    for (i, d) in return_days.iter().enumerate() {
        day_to_idx.insert(d.clone(), i);
    }

    let mut events = Vec::new();
    for record in records {
        if let Some(event) = process_event(
            &record,
            &stock_returns,
            &spy_returns,
            &return_days,
            &day_to_idx,
        ) {
            events.push(event);
        }
    }

    events
}

fn process_event(
    record: &EarningsRecord,
    stock_returns: &[f64],
    spy_returns: &[f64],
    return_days: &[String],
    day_to_idx: &HashMap<String, usize>,
) -> Option<EventCAR> {
    let event_date_str = record.filing_date.clone().unwrap_or_default();
    if event_date_str.is_empty() {
        return None;
    }

    let event_idx = find_event_idx(&event_date_str, return_days, day_to_idx)?;

    let est_start = event_idx as i64 + ESTIMATION_START;
    let est_end = event_idx as i64 + ESTIMATION_END;
    if est_start < 0 || est_end < 0 {
        return None;
    }

    let stock_est = &stock_returns[est_start as usize..=est_end as usize];
    let spy_est = &spy_returns[est_start as usize..=est_end as usize];
    if stock_est.len() < MIN_ESTIMATION_DAYS {
        return None;
    }

    let model = fit_market_model(stock_est, spy_est);

    let evt_start = event_idx;
    let evt_end = (event_idx + MAX_EVENT_WINDOW).min(stock_returns.len() - 1);
    let stock_evt = &stock_returns[evt_start..=evt_end];
    let spy_evt = &spy_returns[evt_start..=evt_end];

    let daily_ar = compute_abnormal_returns(stock_evt, spy_evt, model.alpha, model.beta);

    let n_days = daily_ar.len();
    let mut cars = HashMap::new();
    for &(start, end) in CAR_WINDOWS {
        if end < n_days {
            cars.insert(
                format!("car_{}_{}", start, end),
                Some(sum_car(&daily_ar, start, end)),
            );
        } else {
            cars.insert(format!("car_{}_{}", start, end), None);
        }
    }

    let eps_surprise = record
        .quarterly
        .as_ref()
        .and_then(|q| q.eps_surprise.clone());

    Some(EventCAR {
        ticker: record.ticker.clone(),
        event_date: event_date_str,
        source_type: record.source_type.clone(),
        report_period: record.report_period.clone(),
        eps_surprise,
        market_model: model,
        daily_ar,
        car_0_1: *cars.get("car_0_1").unwrap_or(&None),
        car_0_5: *cars.get("car_0_5").unwrap_or(&None),
        car_0_20: *cars.get("car_0_20").unwrap_or(&None),
    })
}

fn aggregate(events: &[EventCAR], n_bootstrap: i32, rng_seed: Option<u64>) -> Vec<AggregateResult> {
    let mut groups: HashMap<String, Vec<EventCAR>> = HashMap::new();
    for e in events {
        groups
            .entry(e.source_type.clone())
            .or_default()
            .push(e.clone());
    }

    let mut results = Vec::new();
    let mut group_names: Vec<String> = groups.keys().cloned().collect();
    group_names.sort();

    for source_type in group_names {
        let group = groups.get(&source_type).unwrap();
        let mut windows = Vec::new();

        let car_windows = vec![
            ("[0,+1]", "car_0_1"),
            ("[0,+5]", "car_0_5"),
            ("[0,+20]", "car_0_20"),
        ];

        for (window_label, attr) in car_windows {
            let values: Vec<f64> = group
                .iter()
                .filter_map(|e| match attr {
                    "car_0_1" => e.car_0_1,
                    "car_0_5" => e.car_0_5,
                    "car_0_20" => e.car_0_20,
                    _ => None,
                })
                .collect();

            if values.len() < 2 {
                continue;
            }

            let n = values.len();
            let sum: f64 = values.iter().sum();
            let mean = sum / n as f64;

            let mut sum_sq_diff = 0.0;
            for &val in &values {
                let diff = val - mean;
                sum_sq_diff += diff * diff;
            }
            let std = (sum_sq_diff / (n - 1) as f64).sqrt();

            let (t_stat, p_value) = ttest_cars(&values);
            let ci = bootstrap_ci(&values, n_bootstrap, 0.95, rng_seed);

            windows.push(WindowStats {
                window: window_label.to_string(),
                n_events: n as i32,
                mean_car: mean,
                std_car: std,
                t_stat,
                p_value,
                ci,
            });
        }

        results.push(AggregateResult {
            source_type: source_type.clone(),
            n_events: group.len() as i32,
            windows,
        });
    }

    results
}

fn parse_date(s: &Option<String>) -> Option<NaiveDate> {
    let s_str = s.as_ref()?;
    let date_part = s_str.split('T').next()?;
    NaiveDate::parse_from_str(date_part, "%Y-%m-%d").ok()
}

fn filter_retrospective(records: Vec<EarningsRecord>) -> Vec<EarningsRecord> {
    let mut kept = Vec::new();
    for r in records {
        let filing = match parse_date(&r.filing_date) {
            Some(d) => d,
            None => continue,
        };
        let date_part = r.report_period.split('T').next().unwrap_or("");
        let report = match NaiveDate::parse_from_str(date_part, "%Y-%m-%d").ok() {
            Some(d) => d,
            None => continue,
        };
        if (filing - report).num_days() < RETROSPECTIVE_CUTOFF_DAYS {
            kept.push(r);
        }
    }
    kept
}

fn find_event_idx(
    event_date: &str,
    _return_days: &[String],
    day_to_idx: &HashMap<String, usize>,
) -> Option<usize> {
    let date_part = event_date.split('T').next()?;
    if let Some(&idx) = day_to_idx.get(date_part) {
        return Some(idx);
    }
    let d = NaiveDate::parse_from_str(date_part, "%Y-%m-%d").ok()?;
    for offset in 1..=4 {
        let candidate = (d + Duration::days(offset)).format("%Y-%m-%d").to_string();
        if let Some(&idx) = day_to_idx.get(&candidate) {
            return Some(idx);
        }
    }
    None
}
