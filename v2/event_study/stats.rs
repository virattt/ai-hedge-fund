use super::models::{BootstrapCI, MarketModelFit};

pub fn fit_market_model(stock_returns: &[f64], market_returns: &[f64]) -> MarketModelFit {
    let n = stock_returns.len();
    if n == 0 {
        return MarketModelFit {
            alpha: 0.0,
            beta: 0.0,
            r_squared: 0.0,
            n_obs: 0,
        };
    }

    let sum_x: f64 = market_returns.iter().sum();
    let sum_y: f64 = stock_returns.iter().sum();
    let mean_x = sum_x / n as f64;
    let mean_y = sum_y / n as f64;

    let mut cov_xy = 0.0;
    let mut var_x = 0.0;
    let mut ss_tot = 0.0;

    for i in 0..n {
        let dx = market_returns[i] - mean_x;
        let dy = stock_returns[i] - mean_y;
        cov_xy += dx * dy;
        var_x += dx * dx;
        ss_tot += dy * dy;
    }

    let beta = if var_x > 0.0 { cov_xy / var_x } else { 0.0 };
    let alpha = mean_y - beta * mean_x;

    let mut ss_res = 0.0;
    for i in 0..n {
        let predicted = alpha + beta * market_returns[i];
        let diff = stock_returns[i] - predicted;
        ss_res += diff * diff;
    }

    let r_squared = if ss_tot > 0.0 {
        1.0 - ss_res / ss_tot
    } else {
        0.0
    };

    MarketModelFit {
        alpha,
        beta,
        r_squared,
        n_obs: n as i32,
    }
}

pub fn compute_abnormal_returns(
    stock_returns: &[f64],
    market_returns: &[f64],
    alpha: f64,
    beta: f64,
) -> Vec<f64> {
    stock_returns
        .iter()
        .zip(market_returns.iter())
        .map(|(&s, &m)| s - (alpha + beta * m))
        .collect()
}

pub fn sum_car(daily_ar: &[f64], start: usize, end: usize) -> f64 {
    let limit = end.min(daily_ar.len() - 1);
    if start > limit {
        return 0.0;
    }
    daily_ar[start..=limit].iter().sum()
}

fn erf(x: f64) -> f64 {
    let a1 = 0.254829592;
    let a2 = -0.284496736;
    let a3 = 1.421413741;
    let a4 = -1.453152027;
    let a5 = 1.061405429;
    let p = 0.3275911;

    let sign = if x < 0.0 { -1.0 } else { 1.0 };
    let abs_x = x.abs();

    let t = 1.0 / (1.0 + p * abs_x);
    let y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * (-abs_x * abs_x).exp();

    sign * y
}

fn student_t_p_value(t: f64, _df: f64) -> f64 {
    let abs_t = t.abs();
    // For large degrees of freedom, Student's t matches Normal CDF
    let z = abs_t;
    let cdf = 0.5 * (1.0 + erf(z / 2.0_f64.sqrt()));
    2.0 * (1.0 - cdf)
}

pub fn ttest_cars(cars: &[f64]) -> (f64, f64) {
    let n = cars.len();
    if n < 2 {
        return (0.0, 1.0);
    }

    let sum: f64 = cars.iter().sum();
    let mean = sum / n as f64;

    let mut sum_sq_diff = 0.0;
    for &x in cars {
        let diff = x - mean;
        sum_sq_diff += diff * diff;
    }
    let var = sum_sq_diff / (n - 1) as f64;
    let std = var.sqrt();

    if std == 0.0 {
        return (0.0, 1.0);
    }

    let t_stat = mean / (std / (n as f64).sqrt());
    let p_value = student_t_p_value(t_stat, (n - 1) as f64);

    (t_stat, p_value)
}

struct SimpleRng {
    state: u64,
}

impl SimpleRng {
    fn new(seed: Option<u64>) -> Self {
        let s = seed.unwrap_or(123456789);
        Self { state: s }
    }

    fn next(&mut self) -> u64 {
        let mut x = self.state;
        if x == 0 {
            x = 123456789;
        }
        x ^= x << 13;
        x ^= x >> 7;
        x ^= x << 17;
        self.state = x;
        x
    }

    fn next_range(&mut self, min: usize, max: usize) -> usize {
        let range = max - min;
        if range == 0 {
            return min;
        }
        min + (self.next() as usize % range)
    }
}

pub fn bootstrap_ci(
    cars: &[f64],
    n_bootstrap: i32,
    confidence: f64,
    rng_seed: Option<u64>,
) -> BootstrapCI {
    let mut rng = SimpleRng::new(rng_seed);
    let n = cars.len();
    if n == 0 {
        return BootstrapCI {
            lower: 0.0,
            upper: 0.0,
            confidence,
            n_bootstrap,
        };
    }

    let mut boot_means = Vec::with_capacity(n_bootstrap as usize);
    for _ in 0..n_bootstrap {
        let mut sum = 0.0;
        for _ in 0..n {
            let idx = rng.next_range(0, n);
            sum += cars[idx];
        }
        boot_means.push(sum / n as f64);
    }

    boot_means.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));

    let lower_pct = (1.0 - confidence) / 2.0;
    let upper_pct = (1.0 + confidence) / 2.0;

    let lower_idx =
        ((n_bootstrap as f64 * lower_pct).round() as usize).min(n_bootstrap as usize - 1);
    let upper_idx =
        ((n_bootstrap as f64 * upper_pct).round() as usize).min(n_bootstrap as usize - 1);

    BootstrapCI {
        lower: boot_means[lower_idx],
        upper: boot_means[upper_idx],
        confidence,
        n_bootstrap,
    }
}
