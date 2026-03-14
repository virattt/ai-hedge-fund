# Multi-Source Data Integration Guide

This guide explains how to use the multi-source data integration feature in the AI Hedge Fund system.

## Overview

The multi-source data integration feature allows the system to:

1. **Fetch data from multiple sources** (AKShare, YFinance, etc.)
2. **Cross-validate data** to ensure accuracy
3. **Calculate confidence scores** based on agreement between sources
4. **Automatic fallback** when primary source fails
5. **Weighted averaging** of data from different sources

## Architecture

```
MarketAdapter (CN/HK)
    ├── DataSource 1 (AKShare) [Primary]
    ├── DataSource 2 (YFinance) [Fallback]
    └── DataValidator
        ├── Cross-validation
        ├── Confidence scoring
        └── Weighted averaging
```

## Supported Markets

### China A-Share (CN)
- **Ticker Format**: 6 digits (e.g., `000001`, `600000`)
- **Data Sources**: AKShare
- **Normalization**: Removes exchange prefix (`SH`/`SZ`)

### Hong Kong (HK)
- **Ticker Format**: 5 digits (e.g., `00700`, `01398`)
- **Data Sources**: AKShare (primary), YFinance (fallback)
- **Normalization**: Pads to 5 digits

## Usage Examples

### 1. Basic Usage - CN Stock

```python
from src.markets.cn_stock import CNStockAdapter

# Create adapter
adapter = CNStockAdapter()

# Get price data
prices = adapter.get_prices(
    ticker="000001",
    start_date="2024-01-01",
    end_date="2024-01-31"
)

# Get financial metrics
metrics = adapter.get_financial_metrics(
    ticker="000001",
    end_date="2024-01-31"
)

# Get company news
news = adapter.get_company_news(
    ticker="000001",
    end_date="2024-01-31",
    limit=50
)
```

### 2. Multi-Source Validation - HK Stock

```python
from src.markets.hk_stock import HKStockAdapter
from src.data.validation import DataValidator

# Create validator with custom settings
validator = DataValidator(
    source_weights={
        "AKShare": 1.0,      # Higher weight = more trusted
        "YFinance": 0.8,
    },
    price_threshold=0.02,    # 2% max deviation
    min_sources_for_validation=1
)

# Create adapter with validator
adapter = HKStockAdapter(validator=validator)

# Get prices (will fetch from both sources and merge)
prices = adapter.get_prices(
    ticker="00700",          # Tencent
    start_date="2024-01-01",
    end_date="2024-01-31"
)

# Check confidence (available in internal validation)
# Higher confidence = better agreement between sources
```

### 3. Custom Data Source Weights

```python
from src.data.validation import DataValidator

# Configure source priorities
validator = DataValidator(
    source_weights={
        "AKShare": 1.0,       # Most trusted for CN/HK
        "YFinance": 0.8,      # Good for HK
        "FinancialDatasets": 1.0,  # Primary for US
    },
    price_threshold=0.03,     # 3% deviation allowed
)
```

### 4. Ticker Normalization

```python
from src.markets.cn_stock import CNStockAdapter
from src.markets.hk_stock import HKStockAdapter

cn_adapter = CNStockAdapter()
hk_adapter = HKStockAdapter()

# CN ticker normalization
cn_adapter.normalize_ticker("SH600000")  # -> "600000"
cn_adapter.normalize_ticker("1")          # -> "000001"
cn_adapter.detect_exchange("600000")      # -> "SH"
cn_adapter.get_full_ticker("600000")      # -> "SH600000"

# HK ticker normalization
hk_adapter.normalize_ticker("700")        # -> "00700"
hk_adapter.normalize_ticker("0700.HK")    # -> "00700"
hk_adapter.get_yfinance_ticker("00700")   # -> "0700.HK"
```

## Data Validation Process

### Price Validation

1. **Fetch from all sources** in parallel
2. **Group by date** to align timestamps
3. **Calculate weighted average** for each field
4. **Measure deviation** between sources
5. **Assign confidence score** based on:
   - Number of sources (more = higher confidence)
   - Agreement between sources (less deviation = higher confidence)

### Confidence Scoring

- **Single Source**: 0.5 - 0.8 confidence
- **Two Sources**: 0.7 - 0.9 confidence (if agree)
- **Three+ Sources**: 0.9 - 1.0 confidence (if agree)
- **High Deviation**: Confidence reduced proportionally

### Financial Metrics Validation

Similar to price validation but:
- Merges all available fields
- Uses `None` for missing fields
- Calculates weighted average for numeric fields
- Includes metadata (num_sources, confidence, data_sources)

## Error Handling

### Automatic Fallback

```python
# If primary source (AKShare) fails:
# 1. Log the error
# 2. Try next source (YFinance)
# 3. Continue until data found or all sources exhausted
# 4. Return empty result if all fail

prices = adapter.get_prices("00700", "2024-01-01", "2024-01-31")
# Returns data from any available source
```

### Retry Logic

Each data source has built-in retry logic:
- **Max retries**: 3 attempts
- **Backoff**: Exponential (1s, 2s, 4s)
- **Error logging**: Detailed logs for debugging

## Configuration

### Environment Variables

```bash
# Not required for AKShare or YFinance
# But can configure other data sources:
FINANCIAL_DATASETS_API_KEY=your_key_here
```

### Custom Validator Settings

```python
validator = DataValidator(
    source_weights={
        "AKShare": 1.0,
        "YFinance": 0.8,
    },
    price_threshold=0.02,              # 2% max price deviation
    min_sources_for_validation=1,      # Minimum sources needed
)
```

## Adding New Data Sources

To add a new data source:

1. **Create source class** in `src/markets/sources/`:

```python
from src.markets.sources.base import DataSource

class NewSource(DataSource):
    def __init__(self):
        super().__init__("NewSource")

    def supports_market(self, market: str) -> bool:
        return market in ["US", "CN", "HK"]

    def get_prices(self, ticker, start_date, end_date):
        # Implementation
        pass

    def get_financial_metrics(self, ticker, end_date, period, limit):
        # Implementation
        pass

    def get_company_news(self, ticker, end_date, start_date, limit):
        # Implementation
        pass
```

2. **Add to market adapter**:

```python
from src.markets.sources.new_source import NewSource

class HKStockAdapter(MarketAdapter):
    def __init__(self, validator=None):
        data_sources = [
            AKShareSource(),
            YFinanceSource(),
            NewSource(),  # Add here
        ]
        super().__init__("HK", data_sources, validator)
```

3. **Update validator weights**:

```python
validator = DataValidator(
    source_weights={
        "AKShare": 1.0,
        "YFinance": 0.8,
        "NewSource": 0.9,  # Add weight
    }
)
```

## Testing

Run tests for the multi-source feature:

```bash
# Test market adapters
poetry run pytest tests/markets/ -v

# Test data validation
poetry run pytest tests/data/test_validation.py -v

# Test integration
poetry run pytest tests/markets/test_multi_source_integration.py -v

# Run all tests
poetry run pytest tests/ -v
```

## Performance Considerations

### Caching

All data sources use the existing cache system:
- Prices, financial metrics, and news are cached
- Cache keys include all parameters
- Reduces API calls and improves performance

### Parallel Fetching

Multiple sources are queried in parallel (not sequentially):
- Faster total response time
- Better user experience
- Automatic timeout handling

### Lazy Initialization

Data sources are initialized on first use:
- Faster startup time
- Only imports needed libraries
- Better error handling

## Troubleshooting

### Missing Dependencies

```bash
# Install required packages
poetry install

# Or manually:
pip install akshare yfinance
```

### Data Source Errors

Check logs for detailed error messages:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Validation Issues

If data sources disagree significantly:
1. Check the `max_deviation` in validation results
2. Adjust `price_threshold` if needed
3. Review source weights
4. Investigate data quality issues

## Best Practices

1. **Use appropriate market adapter** for your ticker
2. **Configure validator weights** based on data quality
3. **Monitor confidence scores** to detect issues
4. **Set reasonable thresholds** for your use case
5. **Check fallback logs** to ensure redundancy works
6. **Test with mock data** before production use

## Future Enhancements

Potential improvements:
- Additional data sources (Bloomberg, Reuters, etc.)
- Machine learning for confidence scoring
- Real-time data validation
- Anomaly detection
- Historical validation metrics
- Source ranking based on historical accuracy

## Support

For issues or questions:
1. Check test files for examples
2. Review source code documentation
3. Enable debug logging
4. Create an issue with reproduction steps
