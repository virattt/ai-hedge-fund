//! Safe access helpers for partially populated financial data.

/// Working capital = current assets − current liabilities.
pub fn calculate_working_capital(assets: Option<f64>, liabilities: Option<f64>) -> Option<f64> {
    match (assets, liabilities) {
        (Some(a), Some(l)) => Some(a - l),
        _ => None,
    }
}

/// Shareholders' equity = total assets − total liabilities.
pub fn calculate_shareholders_equity(assets: Option<f64>, liabilities: Option<f64>) -> Option<f64> {
    match (assets, liabilities) {
        (Some(a), Some(l)) => Some(a - l),
        _ => None,
    }
}

/// Returns the inner value when present, otherwise `default`.
pub fn option_or<T: Copy>(value: Option<T>, default: T) -> T {
    value.unwrap_or(default)
}

/// Safely divides two optional values, returning `None` on missing inputs or zero divisor.
pub fn safe_divide(numerator: Option<f64>, denominator: Option<f64>) -> Option<f64> {
    match (numerator, denominator) {
        (Some(n), Some(d)) if d.abs() > f64::EPSILON => Some(n / d),
        _ => None,
    }
}

/// Computes gross margin from revenue and gross profit when both are available.
pub fn calculate_gross_margin(revenue: Option<f64>, gross_profit: Option<f64>) -> Option<f64> {
    safe_divide(gross_profit, revenue)
}

/// Computes net margin from revenue and net income when both are available.
pub fn calculate_net_margin(revenue: Option<f64>, net_income: Option<f64>) -> Option<f64> {
    safe_divide(net_income, revenue)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn working_capital_requires_both_inputs() {
        assert_eq!(calculate_working_capital(Some(100.0), Some(40.0)), Some(60.0));
        assert_eq!(calculate_working_capital(Some(100.0), None), None);
        assert_eq!(calculate_working_capital(None, Some(40.0)), None);
    }

    #[test]
    fn shareholders_equity_derived_from_balance_sheet() {
        assert_eq!(
            calculate_shareholders_equity(Some(500.0), Some(300.0)),
            Some(200.0)
        );
    }

    #[test]
    fn safe_divide_handles_zero_denominator() {
        assert_eq!(safe_divide(Some(10.0), Some(0.0)), None);
        assert_eq!(safe_divide(Some(10.0), Some(2.0)), Some(5.0));
    }
}
