//! Data provider selection and runtime configuration.

use std::env;
use std::sync::RwLock;

/// Financial data source for prices and fundamentals.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DataProvider {
    FinancialDatasets,
    YahooFinance,
}

impl DataProvider {
    /// Resolve the active provider from an explicit CLI override or environment.
    ///
    /// Defaults to [`YahooFinance`] when `FINANCIAL_DATASETS_API_KEY` is absent or a placeholder.
    pub fn resolve(explicit: Option<DataProvider>) -> Self {
        if let Some(provider) = explicit {
            return provider;
        }

        match env::var("FINANCIAL_DATASETS_API_KEY") {
            Ok(key) if is_valid_api_key(&key) => DataProvider::FinancialDatasets,
            _ => DataProvider::YahooFinance,
        }
    }

    pub fn from_cli_str(value: &str) -> Option<Self> {
        match value.to_ascii_lowercase().as_str() {
            "financial-datasets" | "financial_datasets" => Some(DataProvider::FinancialDatasets),
            "yahoo-finance" | "yahoo_finance" => Some(DataProvider::YahooFinance),
            _ => None,
        }
    }

    pub fn as_str(&self) -> &'static str {
        match self {
            DataProvider::FinancialDatasets => "financial-datasets",
            DataProvider::YahooFinance => "yahoo-finance",
        }
    }
}

fn is_valid_api_key(key: &str) -> bool {
    !key.is_empty() && key != "your-financial-datasets-api-key"
}

static ACTIVE_PROVIDER: RwLock<Option<DataProvider>> = RwLock::new(None);

/// Store the resolved provider for the current process (CLI / workflow entry).
pub fn configure_provider(explicit: Option<DataProvider>) {
    let resolved = DataProvider::resolve(explicit);
    if let Ok(mut guard) = ACTIVE_PROVIDER.write() {
        *guard = Some(resolved);
    }
}

/// Return the configured provider, falling back to environment-based resolution.
pub fn active_provider() -> DataProvider {
    ACTIVE_PROVIDER
        .read()
        .ok()
        .and_then(|guard| *guard)
        .unwrap_or_else(|| DataProvider::resolve(None))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn defaults_to_yahoo_without_api_key() {
        assert_eq!(DataProvider::resolve(None), DataProvider::YahooFinance);
    }

    #[test]
    fn explicit_override_wins() {
        assert_eq!(
            DataProvider::resolve(Some(DataProvider::FinancialDatasets)),
            DataProvider::FinancialDatasets
        );
    }

    #[test]
    fn parses_cli_values() {
        assert_eq!(
            DataProvider::from_cli_str("yahoo-finance"),
            Some(DataProvider::YahooFinance)
        );
        assert_eq!(
            DataProvider::from_cli_str("financial-datasets"),
            Some(DataProvider::FinancialDatasets)
        );
    }
}
