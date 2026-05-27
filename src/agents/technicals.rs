// Source: src/agents/technicals.py
//! Sibling to src/agents/technicals.py
//! Combines trend following, mean reversion, momentum, and volatility indicators for weighted ensemble trading signals.

use anyhow::{Result, Context};
use crate::graph::state::AgentState;
use crate::tools::api::get_prices;

/// Performs sophisticated technical indicator analysis and updates state signals.
pub async fn technical_analyst_agent(state: &mut AgentState, agent_id: &str) -> Result<()> {
    println!("Running Technical Analyst Agent: {}", agent_id);

    let start_date = state.data.get("start_date")
        .and_then(|v| v.as_str())
        .context("Missing start_date in state data")?;
    
    let end_date = state.data.get("end_date")
        .and_then(|v| v.as_str())
        .context("Missing end_date in state data")?;
    
    let tickers_json = state.data.get("tickers")
        .context("Missing tickers in state data")?;
    
    let tickers: Vec<String> = serde_json::from_value(tickers_json.clone())?;
    
    let api_key = state.metadata.get("FINANCIAL_DATASETS_API_KEY")
        .and_then(|v| v.as_str());

    let mut technical_analysis = serde_json::Map::new();

    for ticker in &tickers {
        // Fetch daily price data
        let prices = match get_prices(ticker, start_date, end_date, api_key).await {
            Ok(p) => p,
            Err(e) => {
                println!("Warning: Failed to fetch prices for {}: {:?}", ticker, e);
                continue;
            }
        };

        if prices.len() < 10 {
            println!("Warning: Insufficient price data for {}", ticker);
            continue;
        }

        // Extract close, high, low, volume arrays
        let closes: Vec<f64> = prices.iter().map(|p| p.close).collect();
        let highs: Vec<f64> = prices.iter().map(|p| p.high).collect();
        let lows: Vec<f64> = prices.iter().map(|p| p.low).collect();
        let volumes: Vec<f64> = prices.iter().map(|p| p.volume as f64).collect();

        // 1. Trend Following
        let ema_8 = calculate_ema(&closes, 8);
        let ema_21 = calculate_ema(&closes, 21);
        let ema_55 = calculate_ema(&closes, 55);
        let adx = calculate_adx(&highs, &lows, &closes, 14);

        let last_idx = closes.len() - 1;
        let short_trend = ema_8[last_idx] > ema_21[last_idx];
        let medium_trend = ema_21[last_idx] > ema_55[last_idx];
        let last_adx = adx[last_idx];
        let trend_strength = last_adx / 100.0;

        let (trend_signal, trend_confidence) = if short_trend && medium_trend {
            ("bullish", trend_strength)
        } else if !short_trend && !medium_trend {
            ("bearish", trend_strength)
        } else {
            ("neutral", 0.5)
        };

        // 2. Mean Reversion
        let ma_50 = calculate_sma(&closes, 50);
        let std_50 = calculate_stddev(&closes, 50);
        let z_score = (closes[last_idx] - ma_50[last_idx]) / if std_50[last_idx] == 0.0 { 1e-8 } else { std_50[last_idx] };

        let (bb_upper, bb_lower) = calculate_bollinger_bands(&closes, 20);
        let price_vs_bb = (closes[last_idx] - bb_lower[last_idx]) / if (bb_upper[last_idx] - bb_lower[last_idx]) == 0.0 { 1e-8 } else { bb_upper[last_idx] - bb_lower[last_idx] };

        let rsi_14 = calculate_rsi(&closes, 14);
        let rsi_28 = calculate_rsi(&closes, 28);

        let (mr_signal, mr_confidence) = if z_score < -2.0 && price_vs_bb < 0.2 {
            ("bullish", (z_score.abs() / 4.0).min(1.0))
        } else if z_score > 2.0 && price_vs_bb > 0.8 {
            ("bearish", (z_score.abs() / 4.0).min(1.0))
        } else {
            ("neutral", 0.5)
        };

        // 3. Momentum
        let mut daily_returns = vec![0.0];
        for i in 1..closes.len() {
            let prev = closes[i - 1];
            daily_returns.push((closes[i] - prev) / if prev == 0.0 { 1e-8 } else { prev });
        }
        let mom_1m: f64 = daily_returns.iter().rev().take(21).sum();
        let mom_3m: f64 = daily_returns.iter().rev().take(63).sum();
        let mom_6m: f64 = daily_returns.iter().rev().take(126).sum();

        let volume_ma_21 = calculate_sma(&volumes, 21);
        let volume_momentum = volumes[last_idx] / if volume_ma_21[last_idx] == 0.0 { 1e-8 } else { volume_ma_21[last_idx] };

        let momentum_score = 0.4 * mom_1m + 0.3 * mom_3m + 0.3 * mom_6m;
        let volume_confirmation = volume_momentum > 1.0;

        let (mom_signal, mom_confidence) = if momentum_score > 0.05 && volume_confirmation {
            ("bullish", (momentum_score.abs() * 5.0).min(1.0))
        } else if momentum_score < -0.05 && volume_confirmation {
            ("bearish", (momentum_score.abs() * 5.0).min(1.0))
        } else {
            ("neutral", 0.5)
        };

        // 4. Volatility Regime
        let mut rolling_std_21 = Vec::new();
        for i in 0..daily_returns.len() {
            if i < 21 {
                rolling_std_21.push(0.05);
            } else {
                let slice = &daily_returns[i - 21..=i];
                let mean = slice.iter().sum::<f64>() / slice.len() as f64;
                let variance = slice.iter().map(|&x| (x - mean).powi(2)).sum::<f64>() / slice.len() as f64;
                rolling_std_21.push(variance.sqrt() * 252.0_f64.sqrt());
            }
        }
        let hist_vol = rolling_std_21[last_idx];
        let vol_ma = calculate_sma(&rolling_std_21, 63)[last_idx];
        let vol_regime = hist_vol / if vol_ma == 0.0 { 1e-8 } else { vol_ma };

        let mut rolling_vol_std_63 = Vec::new();
        for i in 0..rolling_std_21.len() {
            if i < 63 {
                rolling_vol_std_63.push(0.05);
            } else {
                let slice = &rolling_std_21[i - 63..=i];
                let mean = slice.iter().sum::<f64>() / slice.len() as f64;
                let variance = slice.iter().map(|&x| (x - mean).powi(2)).sum::<f64>() / slice.len() as f64;
                rolling_vol_std_63.push(variance.sqrt());
            }
        }
        let vol_std_63 = rolling_vol_std_63[last_idx];
        let vol_z_score = (hist_vol - vol_ma) / if vol_std_63 == 0.0 { 1e-8 } else { vol_std_63 };

        let atr = calculate_atr(&highs, &lows, &closes, 14);
        let atr_ratio = atr[last_idx] / if closes[last_idx] == 0.0 { 1e-8 } else { closes[last_idx] };

        let (vol_signal, vol_confidence) = if vol_regime < 0.8 && vol_z_score < -1.0 {
            ("bullish", (vol_z_score.abs() / 3.0).min(1.0))
        } else if vol_regime > 1.2 && vol_z_score > 1.0 {
            ("bearish", (vol_z_score.abs() / 3.0).min(1.0))
        } else {
            ("neutral", 0.5)
        };

        // 5. Statistical Arbitrage (Hurst exponent)
        let hurst = calculate_hurst_exponent(&closes, 20);
        let (sa_signal, sa_confidence) = if hurst < 0.4 {
            // Check short term skew (last 63 days returns skew)
            let skew = calculate_skewness(&daily_returns, 63);
            if skew > 1.0 {
                ("bullish", (0.5 - hurst) * 2.0)
            } else if skew < -1.0 {
                ("bearish", (0.5 - hurst) * 2.0)
            } else {
                ("neutral", 0.5)
            }
        } else {
            ("neutral", 0.5)
        };

        // Combined Signal Ensemble
        let signal_values = |s: &str| -> f64 {
            match s {
                "bullish" => 1.0,
                "bearish" => -1.0,
                _ => 0.0,
            }
        };

        let weighted_score =
            signal_values(trend_signal) * 0.25 * trend_confidence +
            signal_values(mr_signal) * 0.20 * mr_confidence +
            signal_values(mom_signal) * 0.25 * mom_confidence +
            signal_values(vol_signal) * 0.15 * vol_confidence +
            signal_values(sa_signal) * 0.15 * sa_confidence;

        let total_conf = 0.25 * trend_confidence + 0.20 * mr_confidence + 0.25 * mom_confidence + 0.15 * vol_confidence + 0.15 * sa_confidence;
        let final_score = if total_conf > 0.0 { weighted_score / total_conf } else { 0.0 };

        let overall_signal = if final_score > 0.2 {
            "bullish"
        } else if final_score < -0.2 {
            "bearish"
        } else {
            "neutral"
        };

        let confidence = (final_score.abs() * 100.0) as u32;

        let reasoning = serde_json::json!({
            "trend_following": {
                "signal": trend_signal,
                "confidence": (trend_confidence * 100.0) as u32,
                "metrics": {
                    "adx": last_adx,
                    "trend_strength": trend_strength
                }
            },
            "mean_reversion": {
                "signal": mr_signal,
                "confidence": (mr_confidence * 100.0) as u32,
                "metrics": {
                    "z_score": z_score,
                    "price_vs_bb": price_vs_bb,
                    "rsi_14": rsi_14[last_idx],
                    "rsi_28": rsi_28[last_idx]
                }
            },
            "momentum": {
                "signal": mom_signal,
                "confidence": (mom_confidence * 100.0) as u32,
                "metrics": {
                    "momentum_1m": mom_1m,
                    "momentum_3m": mom_3m,
                    "momentum_6m": mom_6m,
                    "volume_momentum": volume_momentum
                }
            },
            "volatility": {
                "signal": vol_signal,
                "confidence": (vol_confidence * 100.0) as u32,
                "metrics": {
                    "historical_volatility": hist_vol,
                    "volatility_regime": vol_regime,
                    "volatility_z_score": vol_z_score,
                    "atr_ratio": atr_ratio
                }
            },
            "statistical_arbitrage": {
                "signal": sa_signal,
                "confidence": (sa_confidence * 100.0) as u32,
                "metrics": {
                    "hurst_exponent": hurst
                }
            }
        });

        technical_analysis.insert(
            ticker.clone(),
            serde_json::json!({
                "signal": overall_signal,
                "confidence": confidence,
                "reasoning": reasoning
            }),
        );
    }

    let analyst_signals = state.data.entry("analyst_signals".to_string())
        .or_insert_with(|| serde_json::json!({}));
    
    if let Some(obj) = analyst_signals.as_object_mut() {
        obj.insert(agent_id.to_string(), serde_json::Value::Object(technical_analysis));
    }

    Ok(())
}

// -------------------------------------------------------------
// Mathematical Helpers
// -------------------------------------------------------------

pub fn calculate_sma(data: &[f64], window: usize) -> Vec<f64> {
    let mut sma = vec![0.0; data.len()];
    for i in 0..data.len() {
        if i < window - 1 {
            sma[i] = data[..=i].iter().sum::<f64>() / (i + 1) as f64;
        } else {
            let sum: f64 = data[i + 1 - window..=i].iter().sum();
            sma[i] = sum / window as f64;
        }
    }
    sma
}

pub fn calculate_stddev(data: &[f64], window: usize) -> Vec<f64> {
    let mut std = vec![0.0; data.len()];
    let sma = calculate_sma(data, window);
    for i in 0..data.len() {
        let size = if i < window - 1 { i + 1 } else { window };
        let start = i + 1 - size;
        let mean = sma[i];
        let variance = data[start..=i].iter().map(|&x| (x - mean).powi(2)).sum::<f64>() / size as f64;
        std[i] = variance.sqrt();
    }
    std}

pub fn calculate_ema(data: &[f64], window: usize) -> Vec<f64> {
    let mut ema = vec![0.0; data.len()];
    if data.is_empty() {
        return ema;
    }
    ema[0] = data[0];
    let k = 2.0 / (window + 1) as f64;
    for i in 1..data.len() {
        ema[i] = data[i] * k + ema[i - 1] * (1.0 - k);
    }
    ema
}

pub fn calculate_rsi(data: &[f64], window: usize) -> Vec<f64> {
    let mut rsi = vec![50.0; data.len()];
    if data.len() < window {
        return rsi;
    }

    let mut gains = vec![0.0; data.len()];
    let mut losses = vec![0.0; data.len()];
    for i in 1..data.len() {
        let diff = data[i] - data[i - 1];
        if diff > 0.0 {
            gains[i] = diff;
        } else {
            losses[i] = diff.abs();
        }
    }

    let mut avg_gain = gains[1..=window].iter().sum::<f64>() / window as f64;
    let mut avg_loss = losses[1..=window].iter().sum::<f64>() / window as f64;
    
    rsi[window] = if avg_loss == 0.0 {
        if avg_gain == 0.0 { 50.0 } else { 100.0 }
    } else {
        100.0 - (100.0 / (1.0 + avg_gain / avg_loss))
    };

    for i in (window + 1)..data.len() {
        avg_gain = (avg_gain * (window - 1) as f64 + gains[i]) / window as f64;
        avg_loss = (avg_loss * (window - 1) as f64 + losses[i]) / window as f64;
        rsi[i] = if avg_loss == 0.0 {
            if avg_gain == 0.0 { 50.0 } else { 100.0 }
        } else {
            100.0 - (100.0 / (1.0 + avg_gain / avg_loss))
        };
    }
    rsi
}

pub fn calculate_bollinger_bands(data: &[f64], window: usize) -> (Vec<f64>, Vec<f64>) {
    let sma = calculate_sma(data, window);
    let std = calculate_stddev(data, window);
    let mut upper = vec![0.0; data.len()];
    let mut lower = vec![0.0; data.len()];
    for i in 0..data.len() {
        upper[i] = sma[i] + std[i] * 2.0;
        lower[i] = sma[i] - std[i] * 2.0;
    }
    (upper, lower)
}

pub fn calculate_adx(highs: &[f64], lows: &[f64], closes: &[f64], period: usize) -> Vec<f64> {
    let mut adx = vec![50.0; closes.len()];
    if closes.len() < period * 2 {
        return adx;
    }

    let mut tr = vec![0.0; closes.len()];
    let mut plus_dm = vec![0.0; closes.len()];
    let mut minus_dm = vec![0.0; closes.len()];

    for i in 1..closes.len() {
        let hl = highs[i] - lows[i];
        let hc = (highs[i] - closes[i - 1]).abs();
        let lc = (lows[i] - closes[i - 1]).abs();
        tr[i] = hl.max(hc).max(lc);

        let up_move = highs[i] - highs[i - 1];
        let down_move = lows[i - 1] - lows[i];

        if up_move > down_move && up_move > 0.0 {
            plus_dm[i] = up_move;
        }
        if down_move > up_move && down_move > 0.0 {
            minus_dm[i] = down_move;
        }
    }

    let tr_ema = calculate_ema(&tr, period);
    let plus_dm_ema = calculate_ema(&plus_dm, period);
    let minus_dm_ema = calculate_ema(&minus_dm, period);

    let mut dx = vec![0.0; closes.len()];
    for i in 1..closes.len() {
        let tr_val = if tr_ema[i] == 0.0 { 1e-8 } else { tr_ema[i] };
        let plus_di = 100.0 * plus_dm_ema[i] / tr_val;
        let minus_di = 100.0 * minus_dm_ema[i] / tr_val;
        let diff = (plus_di - minus_di).abs();
        let sum = plus_di + minus_di;
        dx[i] = 100.0 * diff / if sum == 0.0 { 1e-8 } else { sum };
    }

    calculate_ema(&dx, period)
}

pub fn calculate_atr(highs: &[f64], lows: &[f64], closes: &[f64], period: usize) -> Vec<f64> {
    let mut tr = vec![0.0; closes.len()];
    for i in 1..closes.len() {
        let hl = highs[i] - lows[i];
        let hc = (highs[i] - closes[i - 1]).abs();
        let lc = (lows[i] - closes[i - 1]).abs();
        tr[i] = hl.max(hc).max(lc);
    }
    calculate_sma(&tr, period)
}

pub fn calculate_hurst_exponent(closes: &[f64], max_lag: usize) -> f64 {
    if closes.len() < max_lag + 10 {
        return 0.5;
    }

    let mut lags = Vec::new();
    let mut tau = Vec::new();

    for lag in 2..max_lag {
        let mut diffs = Vec::new();
        for i in 0..(closes.len() - lag) {
            diffs.push(closes[i + lag] - closes[i]);
        }
        
        let mean = diffs.iter().sum::<f64>() / diffs.len() as f64;
        let variance = diffs.iter().map(|&x| (x - mean).powi(2)).sum::<f64>() / diffs.len() as f64;
        let std_dev = variance.sqrt().max(1e-8);
        
        lags.push(lag as f64);
        tau.push(std_dev);
    }

    // Linear regression on ln(lags) vs ln(tau)
    let x: Vec<f64> = lags.iter().map(|&val| val.ln()).collect();
    let y: Vec<f64> = tau.iter().map(|&val| val.ln()).collect();

    let n = x.len() as f64;
    let sum_x: f64 = x.iter().sum();
    let sum_y: f64 = y.iter().sum();
    let sum_xx: f64 = x.iter().map(|&val| val.powi(2)).sum();
    let sum_xy: f64 = x.iter().zip(y.iter()).map(|(&a, &b)| a * b).sum();

    let denom = n * sum_xx - sum_x.powi(2);
    if denom == 0.0 {
        0.5
    } else {
        (n * sum_xy - sum_x * sum_y) / denom
    }
}

pub fn calculate_skewness(returns: &[f64], window: usize) -> f64 {
    if returns.len() < window {
        return 0.0;
    }
    let slice = &returns[returns.len() - window..];
    let mean = slice.iter().sum::<f64>() / slice.len() as f64;
    let variance = slice.iter().map(|&x| (x - mean).powi(2)).sum::<f64>() / slice.len() as f64;
    let std_dev = variance.sqrt();
    if std_dev == 0.0 {
        return 0.0;
    }
    let skew: f64 = slice.iter().map(|&x| ((x - mean) / std_dev).powi(3)).sum::<f64>() / slice.len() as f64;
    skew
}
