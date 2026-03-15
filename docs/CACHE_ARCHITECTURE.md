# Dual-Layer Cache Architecture

## Overview

The AI Hedge Fund system uses a dual-layer caching strategy to optimize performance and reduce API calls:

- **L1 Cache**: In-memory cache (fast, ephemeral)
- **L2 Cache**: Database cache (persistent, survives restarts)

This architecture balances speed with persistence, significantly reducing latency and API costs while ensuring data availability across system restarts.

## Cache Flow

```
Request → L1 Cache → L2 Cache → API → Populate L2 → Populate L1 → Response
            ↓           ↓
          Hit        Hit (if fresh)
```

### Query Flow

1. **L1 Check**: First check in-memory cache
   - If found: Return immediately (fastest path)
   - If not found: Continue to L2

2. **L2 Check**: Check database cache
   - If found and fresh: Return data and populate L1
   - If found but stale: Continue to API
   - If not found: Continue to API

3. **API Call**: Fetch from external API
   - Save to L2 (persistent)
   - Save to L1 (fast access)
   - Return data

## Data Freshness Rules

The system implements smart freshness logic based on data characteristics:

### Historical Data (date < today)
- **永久有效** (Permanent)
- Historical stock prices, metrics, and news never change
- Once cached, they remain valid forever
- Eliminates redundant API calls for backtesting

### Current Data (date = today)
- **1 hour freshness**
- Market data changes throughout the trading day
- Cached data expires after 1 hour
- Ensures relatively fresh data without excessive API calls

## Configuration

### Database Setup

The L2 cache requires a database connection. Configure via the `DATABASE_URL` environment variable:

#### SQLite (Development/Testing)
```bash
# Local file (recommended for development)
DATABASE_URL=sqlite:///./ai_hedge_fund.db

# In-memory (for testing only)
DATABASE_URL=sqlite:///:memory:
```

#### MySQL (Production)
```bash
DATABASE_URL=mysql+pymysql://username:password@localhost:3306/ai_hedge_fund
```

#### PostgreSQL (Production Alternative)
```bash
DATABASE_URL=postgresql://username:password@localhost:5432/ai_hedge_fund
```

### Disabling L2 Cache

If `DATABASE_URL` is not set, the system automatically falls back to L1 cache only:

```bash
# L1 cache only (no persistent cache)
unset DATABASE_URL
```

## Database Schema

The L2 cache uses three main tables:

### stock_prices
Stores historical and current stock price data.

```sql
CREATE TABLE stock_prices (
    id INT PRIMARY KEY AUTO_INCREMENT,
    ticker VARCHAR(20) NOT NULL,
    date DATE NOT NULL,
    time DATETIME NOT NULL,
    open DECIMAL(15, 4),
    close DECIMAL(15, 4),
    high DECIMAL(15, 4),
    low DECIMAL(15, 4),
    volume BIGINT,
    data_source VARCHAR(50) DEFAULT 'financial_api',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY idx_ticker_time (ticker, time),
    KEY idx_ticker_date (ticker, date)
);
```

### financial_metrics
Stores financial metrics (P/E ratio, market cap, etc.).

```sql
CREATE TABLE financial_metrics (
    id INT PRIMARY KEY AUTO_INCREMENT,
    ticker VARCHAR(20) NOT NULL,
    report_period DATE NOT NULL,
    period VARCHAR(20) NOT NULL,
    currency VARCHAR(10),
    market_cap DECIMAL(20, 2),
    pe_ratio DECIMAL(10, 4),
    pb_ratio DECIMAL(10, 4),
    ps_ratio DECIMAL(10, 4),
    metrics_json JSON,
    data_source VARCHAR(50) DEFAULT 'financial_api',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY idx_ticker_period (ticker, report_period, period)
);
```

### company_news
Stores company news articles.

```sql
CREATE TABLE company_news (
    id INT PRIMARY KEY AUTO_INCREMENT,
    ticker VARCHAR(20) NOT NULL,
    date DATETIME NOT NULL,
    title TEXT,
    content TEXT,
    url TEXT,
    source VARCHAR(100),
    data_source VARCHAR(50) DEFAULT 'financial_api',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    KEY idx_ticker_date (ticker, date)
);
```

## Performance Benefits

### API Call Reduction

- **Historical backtests**: ~95% reduction in API calls
  - First run: Full API calls
  - Subsequent runs: L2 cache hits

- **Current data**: ~50-70% reduction
  - 1-hour freshness window balances freshness vs API cost

### Latency Improvement

- **L1 cache hit**: < 1ms
- **L2 cache hit**: 5-20ms
- **API call**: 200-1000ms

### Cost Savings

For a typical backtest of 3 stocks over 1 year:
- **Without cache**: ~3,000 API calls
- **With L1 only**: ~1,500 calls (per session)
- **With L1+L2**: ~100 calls (first run) + ~50 calls (subsequent runs)

## Implementation Details

### Dual-Layer Cache Manager

The `DualLayerCacheManager` (src/data/dual_cache.py) coordinates L1 and L2:

```python
from src.data.dual_cache import get_dual_cache

# Get dual cache instance
cache = get_dual_cache(enable_l2=True)

# Retrieve prices (checks L1 → L2 → API)
prices = cache.get_prices("AAPL", "2024-01-01", "2024-01-31")

# Save prices (populates both L1 and L2)
cache.set_prices("AAPL", "2024-01-01", "2024-01-31", prices)
```

### API Integration

The `src/tools/api.py` module automatically uses dual-layer caching:

```python
from src.tools.api import get_prices

# Automatically uses dual-layer cache
prices = get_prices("AAPL", "2024-01-01", "2024-01-31")
```

No code changes required in existing agents or workflows.

## Monitoring and Debugging

### Cache Statistics

Check L1 cache performance:

```python
from src.data.cache import get_cache

cache = get_cache()
stats = cache.get_stats()

print(f"Hit rate: {stats['hit_rate']}")
print(f"Total hits: {stats['hits']}")
print(f"Total misses: {stats['misses']}")
```

### Database Inspection

For SQLite:
```bash
sqlite3 ai_hedge_fund.db "SELECT COUNT(*) FROM stock_prices;"
sqlite3 ai_hedge_fund.db "SELECT ticker, COUNT(*) FROM stock_prices GROUP BY ticker;"
```

For MySQL:
```sql
SELECT COUNT(*) as total_prices FROM stock_prices;
SELECT ticker, COUNT(*) as count FROM stock_prices GROUP BY ticker;
```

## Troubleshooting

### Issue: "No L2 cache available"

**Cause**: DATABASE_URL not set or database connection failed

**Solution**:
1. Check .env file has DATABASE_URL
2. Verify database credentials
3. Test connection: `poetry run python -c "from src.data.database import test_connection; test_connection()"`

### Issue: "Stale data returned"

**Cause**: Requesting current data and cached data is > 1 hour old

**Solution**: This is expected behavior. The cache will automatically refresh on next request.

### Issue: "High memory usage"

**Cause**: L1 cache growing too large

**Solution**:
1. Reduce L1 cache TTL (default: 300s)
2. Manually clear cache: `cache.clear()`
3. Run cleanup: `cache.cleanup_expired()`

## Migration from L1-Only

If you're currently using L1-only caching, the upgrade is automatic:

1. Set DATABASE_URL in .env
2. Restart application
3. L2 cache initializes automatically

No code changes required. The system gracefully falls back to L1 if L2 initialization fails.

## Best Practices

1. **Development**: Use SQLite for simplicity
   ```bash
   DATABASE_URL=sqlite:///./ai_hedge_fund.db
   ```

2. **Production**: Use MySQL or PostgreSQL for reliability
   ```bash
   DATABASE_URL=mysql+pymysql://user:pass@host:3306/aihedgefund
   ```

3. **Testing**: Use in-memory SQLite
   ```bash
   DATABASE_URL=sqlite:///:memory:
   ```

4. **Backups**: Regularly backup your L2 cache database to preserve historical data

5. **Monitoring**: Track cache hit rates to optimize performance

## Future Enhancements

Potential improvements to the cache system:

- [ ] Add cache warming (pre-populate common queries)
- [ ] Implement cache compression for large datasets
- [ ] Add distributed caching (Redis) for multi-instance deployments
- [ ] Implement query result caching for complex analytics
- [ ] Add cache analytics dashboard
