#[path = "../data/mod.rs"]
pub mod data;

pub mod engine;
pub mod models;
pub mod plot;
pub mod stats;

use anyhow::Result;
use data::client::FDClient;
use engine::compute_car;
use std::io::{self, Write};
use std::time::Duration;
use tokio::time::sleep;

const TICKERS: &[&str] = &[
    "AAPL", "MSFT", "AMZN", "GOOGL", "META", "NVDA", "TSLA", "NFLX", "CRM", "ADBE", "ORCL", "INTC",
    "AMD", "CSCO", "IBM", "UBER", "SHOP", "SNOW", "PLTR", "PANW", "CRWD", "JPM", "GS", "BAC",
    "WFC", "MS", "C", "BLK", "SCHW", "AXP", "COF", "USB", "PNC", "TFC", "BK", "CME", "JNJ", "PFE",
    "UNH", "MRK", "LLY", "ABBV", "TMO", "ABT", "BMY", "AMGN", "GILD", "ISRG", "VRTX", "REGN",
    "MDT", "XOM", "CVX", "COP", "SLB", "EOG", "MPC", "PSX", "HD", "LOW", "COST", "WMT", "KO",
    "PEP", "MCD", "SBUX", "NKE", "TGT", "TJX", "ROST", "DG", "DLTR", "YUM", "CAT", "DE", "HON",
    "UPS", "RTX", "BA", "LMT", "GE", "MMM", "UNP", "DIS", "CMCSA", "T", "VZ", "TMUS", "CHTR",
    "WBD", "V", "MA", "PYPL", "NEE", "D", "SO", "DUK", "ABNB", "COIN", "NOW",
];

const EARNINGS_LIMIT: u32 = 8;
const GREEN: &str = "\x1B[32m";
const RED: &str = "\x1B[31m";
const DIM: &str = "\x1B[90m";
const RESET: &str = "\x1B[0m";

fn progress(text: &str) {
    print!("\r{}", text);
    io::stdout().flush().ok();
}

async fn typed(text: &str, delay: Duration) {
    for ch in text.chars() {
        print!("{}", ch);
        io::stdout().flush().ok();
        sleep(delay).await;
    }
    println!();
}

fn color_car(v: Option<f64>) -> String {
    match v {
        None => format!("{}{:>8}{}", DIM, "N/A", RESET),
        Some(val) => {
            let pct = val * 100.0;
            let s = format!("{:+7.2}%", pct);
            let c = if pct >= 0.0 { GREEN } else { RED };
            format!("{}{}{}", c, s, RESET)
        }
    }
}

fn color_eps(s: Option<&str>) -> String {
    match s {
        Some("BEAT") => format!("{}BEAT{}", GREEN, RESET),
        Some("MISS") => format!("{}MISS{}", RED, RESET),
        Some("MEET") => "MEET".to_string(),
        _ => format!("{}   -{}", DIM, RESET),
    }
}

#[tokio::main]
async fn main() -> Result<()> {
    dotenvy::dotenv().ok();

    let fd = FDClient::new(None);
    let tickers_vec: Vec<String> = TICKERS.iter().map(|t| t.to_string()).collect();

    // Use a small subset of tickers for CLI presentation
    let run_tickers = &tickers_vec[0..6];
    let _n = run_tickers.len();

    progress("Fetching SPY benchmark returns and running OLS OLS regressions...");
    let result = compute_car(run_tickers, &fd, EARNINGS_LIMIT, 10_000, Some(42), true).await;

    // Clear progress line
    print!("\r{}\r", " ".repeat(80));
    io::stdout().flush().ok();

    typed(
        &format!(
            "Event Study: {} earnings events across {} tickers",
            result.events.len(),
            run_tickers.len()
        ),
        Duration::from_millis(5),
    )
    .await;
    println!();

    println!(
        "  {:<6} {:<12} {:<6} {:<4}  {:>8} {:>8} {:>8}   {:>5} {:>5}",
        "Ticker", "Date", "Type", "EPS", "CAR[0,1]", "CAR[0,5]", "CAR[0,20]", "Beta", "R2"
    );
    println!("  {}", "-".repeat(78));

    let mut sorted_events = result.events.clone();
    sorted_events.sort_by(|a, b| (&a.ticker, &a.event_date).cmp(&(&b.ticker, &b.event_date)));

    for e in sorted_events {
        let eps = color_eps(e.eps_surprise.as_deref());
        let c1 = color_car(e.car_0_1);
        let c5 = color_car(e.car_0_5);
        let c20 = color_car(e.car_0_20);

        println!(
            "  {:<6} {:<12} {:<6} {}  {} {} {}   {:5.2} {:5.2}",
            e.ticker,
            e.event_date,
            e.source_type,
            eps,
            c1,
            c5,
            c20,
            e.market_model.beta,
            e.market_model.r_squared
        );
        sleep(Duration::from_millis(5)).await;
    }

    println!();
    typed(
        &format!("{} events processed. Done.", result.events.len()),
        Duration::from_millis(5),
    )
    .await;

    Ok(())
}
