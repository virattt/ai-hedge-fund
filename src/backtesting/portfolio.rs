// Source: src/backtesting/portfolio.py
//! Sibling to src/backtesting/portfolio.py
//! Tracks active cash, long/short share counts, cost basis, margins, and realized gains.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Serialize, Deserialize, Clone, Default)]
pub struct PositionDetail {
    pub long: i64,
    pub short: i64,
    pub long_cost_basis: f64,
    pub short_cost_basis: f64,
    pub short_margin_used: f64,
}

#[derive(Debug, Serialize, Deserialize, Clone, Default)]
pub struct RealizedGains {
    pub long: f64,
    pub short: f64,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct Portfolio {
    pub cash: f64,
    pub margin_requirement: f64,
    pub margin_used: f64,
    pub positions: HashMap<String, PositionDetail>,
    pub realized_gains: HashMap<String, RealizedGains>,
}

impl Portfolio {
    pub fn new(tickers: Vec<String>, initial_cash: f64, margin_requirement: f64) -> Self {
        let mut positions = HashMap::new();
        let mut realized_gains = HashMap::new();

        for ticker in tickers {
            positions.insert(ticker.clone(), PositionDetail::default());
            realized_gains.insert(ticker, RealizedGains::default());
        }

        Self {
            cash: initial_cash,
            margin_requirement,
            margin_used: 0.0,
            positions,
            realized_gains,
        }
    }

    pub fn apply_long_buy(&mut self, ticker: &str, quantity: u32, price: f64) -> u32 {
        if quantity == 0 || price <= 0.0 {
            return 0;
        }
        let pos = self.positions.entry(ticker.to_string()).or_insert_with(PositionDetail::default);
        let cost = quantity as f64 * price;
        if cost <= self.cash {
            let old_shares = pos.long;
            let old_cost_basis = pos.long_cost_basis;
            let total_shares = old_shares + quantity as i64;
            if total_shares > 0 {
                let total_old_cost = old_cost_basis * old_shares as f64;
                let total_new_cost = cost;
                pos.long_cost_basis = (total_old_cost + total_new_cost) / total_shares as f64;
            }
            pos.long = total_shares;
            self.cash -= cost;
            return quantity;
        }
        let max_qty = (self.cash / price) as u32;
        if max_qty > 0 {
            let actual_cost = max_qty as f64 * price;
            let old_shares = pos.long;
            let old_cost_basis = pos.long_cost_basis;
            let total_shares = old_shares + max_qty as i64;
            if total_shares > 0 {
                let total_old_cost = old_cost_basis * old_shares as f64;
                let total_new_cost = actual_cost;
                pos.long_cost_basis = (total_old_cost + total_new_cost) / total_shares as f64;
            }
            pos.long = total_shares;
            self.cash -= actual_cost;
            return max_qty;
        }
        0
    }

    pub fn apply_long_sell(&mut self, ticker: &str, quantity: u32, price: f64) -> u32 {
        if quantity == 0 || price <= 0.0 {
            return 0;
        }
        let pos = self.positions.entry(ticker.to_string()).or_insert_with(PositionDetail::default);
        let gains = self.realized_gains.entry(ticker.to_string()).or_insert_with(RealizedGains::default);
        let sell_qty = std::cmp::min(quantity as i64, pos.long) as u32;
        if sell_qty > 0 {
            let avg_cost = if pos.long > 0 { pos.long_cost_basis } else { 0.0 };
            let realized_gain = (price - avg_cost) * sell_qty as f64;
            gains.long += realized_gain;
            pos.long -= sell_qty as i64;
            self.cash += sell_qty as f64 * price;
            if pos.long == 0 {
                pos.long_cost_basis = 0.0;
            }
            return sell_qty;
        }
        0
    }

    pub fn apply_short_open(&mut self, ticker: &str, quantity: u32, price: f64) -> u32 {
        if quantity == 0 || price <= 0.0 {
            return 0;
        }
        let pos = self.positions.entry(ticker.to_string()).or_insert_with(PositionDetail::default);
        let proceeds = price * quantity as f64;
        let margin_ratio = self.margin_requirement;
        let margin_required = proceeds * margin_ratio;
        let available_cash = (self.cash - self.margin_used).max(0.0);

        if margin_required <= available_cash {
            let old_short_shares = pos.short;
            let old_cost_basis = pos.short_cost_basis;
            let total_shares = old_short_shares + quantity as i64;
            if total_shares > 0 {
                let total_old_cost = old_cost_basis * old_short_shares as f64;
                let total_new_cost = price * quantity as f64;
                pos.short_cost_basis = (total_old_cost + total_new_cost) / total_shares as f64;
            }
            pos.short = total_shares;
            pos.short_margin_used += margin_required;
            self.margin_used += margin_required;
            self.cash += proceeds;
            self.cash -= margin_required;
            return quantity;
        }

        let max_qty = if margin_ratio > 0.0 && price > 0.0 {
            (available_cash / (price * margin_ratio)) as u32
        } else {
            0
        };

        if max_qty > 0 {
            let actual_proceeds = price * max_qty as f64;
            let actual_margin_required = actual_proceeds * margin_ratio;
            let old_short_shares = pos.short;
            let old_cost_basis = pos.short_cost_basis;
            let total_shares = old_short_shares + max_qty as i64;
            if total_shares > 0 {
                let total_old_cost = old_cost_basis * old_short_shares as f64;
                let total_new_cost = price * max_qty as f64;
                pos.short_cost_basis = (total_old_cost + total_new_cost) / total_shares as f64;
            }
            pos.short = total_shares;
            pos.short_margin_used += actual_margin_required;
            self.margin_used += actual_margin_required;
            self.cash += actual_proceeds;
            self.cash -= actual_margin_required;
            return max_qty;
        }
        0
    }

    pub fn apply_short_cover(&mut self, ticker: &str, quantity: u32, price: f64) -> u32 {
        if quantity == 0 || price <= 0.0 {
            return 0;
        }
        let pos = self.positions.entry(ticker.to_string()).or_insert_with(PositionDetail::default);
        let gains = self.realized_gains.entry(ticker.to_string()).or_insert_with(RealizedGains::default);
        let cover_qty = std::cmp::min(quantity as i64, pos.short) as u32;
        if cover_qty > 0 {
            let cover_cost = cover_qty as f64 * price;
            let avg_short_price = if pos.short > 0 { pos.short_cost_basis } else { 0.0 };
            let realized_gain = (avg_short_price - price) * cover_qty as f64;
            let portion = if pos.short > 0 {
                cover_qty as f64 / pos.short as f64
            } else {
                1.0
            };
            let margin_to_release = portion * pos.short_margin_used;
            pos.short -= cover_qty as i64;
            pos.short_margin_used -= margin_to_release;
            self.margin_used = (self.margin_used - margin_to_release).max(0.0);
            self.cash += margin_to_release;
            self.cash -= cover_cost;
            gains.short += realized_gain;
            if pos.short == 0 {
                pos.short_cost_basis = 0.0;
                pos.short_margin_used = 0.0;
            }
            return cover_qty;
        }
        0
    }
}
