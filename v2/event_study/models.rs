use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct MarketModelFit {
    pub alpha: f64,
    pub beta: f64,
    pub r_squared: f64,
    pub n_obs: i32,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct EventCAR {
    pub ticker: String,
    pub event_date: String,
    pub source_type: String,
    pub report_period: String,
    pub eps_surprise: Option<String>,
    pub market_model: MarketModelFit,
    pub daily_ar: Vec<f64>,
    pub car_0_1: Option<f64>,
    pub car_0_5: Option<f64>,
    pub car_0_20: Option<f64>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct BootstrapCI {
    pub lower: f64,
    pub upper: f64,
    pub confidence: f64,
    pub n_bootstrap: i32,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct WindowStats {
    pub window: String,
    pub n_events: i32,
    pub mean_car: f64,
    pub std_car: f64,
    pub t_stat: f64,
    pub p_value: f64,
    pub ci: BootstrapCI,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct AggregateResult {
    pub source_type: String,
    pub n_events: i32,
    pub windows: Vec<WindowStats>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct EventStudyResult {
    pub events: Vec<EventCAR>,
    pub aggregates: Vec<AggregateResult>,
    pub skipped_tickers: Vec<String>,
}
