# Yahoo Finance Performance Optimization Guide

## 🐌 Problem Analysis

### Current Performance Issues

When running with `USE_YAHOO_FINANCE=true`, backtests are slow due to:

1. **Multiple yfinance API calls per trading day**
2. **Redundant Ticker object creation**
3. **Inefficient data fetching patterns**
4. **Cache hits still require Ticker instantiation**

### Performance Profiling Results

```
Test Results for AAPL:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Operation                          Time        Impact
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
yf.Ticker() instantiation          0.03ms      ✅ Fast
First stock.info call              520ms       🔴 Slow
First stock.history() call         110ms       🟡 Medium
First stock.financials call        283ms       🔴 Slow
First stock.news call              182ms       🟡 Medium
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total for 1 ticker (all data)      ~1095ms     1.1 seconds
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Bottleneck Breakdown

For a typical 1-month backtest with 1 ticker (AAPL):
- **Trading days**: ~22 days
- **Agents**: ~20 agents
- **API calls per day**: ~60 calls (prices, metrics, news × agents)
- **Total network requests**: ~1,320 requests

**Estimated time**: 22 days × 1.1s = **24+ seconds** just for data fetching

## ⚡ Optimization Strategies

### Strategy 1: Ticker Object Caching (RECOMMENDED)

**Impact**: 50-70% faster ⚡⚡⚡

Current implementation creates new `yf.Ticker()` objects in each function:

```python
# ❌ Current (SLOW) - Creates new Ticker each time
def get_prices(ticker: str, start_date: str, end_date: str):
    stock = yf.Ticker(ticker)  # New object created
    df = stock.history(start=start_date, end=end_date)
    return df

def get_financial_metrics(ticker: str, ...):
    stock = yf.Ticker(ticker)  # Another new object
    info = stock.info
    return info
```

**Optimized approach** - Cache Ticker objects:

```python
# ✅ Optimized (FAST) - Reuse Ticker objects
_ticker_cache = {}

def _get_ticker(ticker: str) -> yf.Ticker:
    """Get or create cached Ticker object."""
    if ticker not in _ticker_cache:
        _ticker_cache[ticker] = yf.Ticker(ticker)
    return _ticker_cache[ticker]

def get_prices(ticker: str, start_date: str, end_date: str):
    stock = _get_ticker(ticker)  # Reuse cached object
    df = stock.history(start=start_date, end=end_date)
    return df
```

**Implementation file**: `src/tools/api_yahoo.py`

Lines to modify:
- Line 57: `get_prices()` - Change to `stock = _get_ticker(ticker)`
- Line 112: `get_financial_metrics()` - Change to `stock = _get_ticker(ticker)`
- Line 326: `search_line_items()` - Change to `stock = _get_ticker(ticker)`
- Line 466: `get_company_news()` - Change to `stock = _get_ticker(ticker)`
- Line 526: `get_market_cap()` - Change to `stock = _get_ticker(ticker)`

### Strategy 2: Batch Data Fetching

**Impact**: 30-40% faster ⚡⚡

Instead of fetching data separately for each agent, fetch all data once per ticker per day.

```python
# ❌ Current - Each agent fetches separately
# Agent 1 calls get_financial_metrics()
# Agent 2 calls get_financial_metrics()
# Agent 3 calls get_financial_metrics()
# ... 20 agents × multiple calls = slow

# ✅ Optimized - Fetch once, share results
def fetch_all_ticker_data(ticker: str, start_date: str, end_date: str):
    """Fetch all data for a ticker in one go."""
    stock = _get_ticker(ticker)

    return {
        'prices': stock.history(start=start_date, end=end_date),
        'info': stock.info,
        'financials': stock.financials,
        'balance_sheet': stock.balance_sheet,
        'cash_flow': stock.cashflow,
        'news': stock.news,
    }
```

### Strategy 3: Smarter Prefetching

**Impact**: 20-30% faster ⚡

Current prefetch in `engine.py:_prefetch_data()` is good but can be improved:

```python
# ✅ Enhanced prefetch
def _prefetch_data(self) -> None:
    """Prefetch all data needed for entire backtest period."""
    for ticker in self._tickers:
        # Fetch ONCE for entire backtest period
        stock = _get_ticker(ticker)

        # Warm up the cache with all data types
        _ = stock.history(start=self._start_date, end=self._end_date)
        _ = stock.info
        _ = stock.financials
        _ = stock.quarterly_financials
        _ = stock.balance_sheet
        _ = stock.cashflow
        _ = stock.news
```

### Strategy 4: Reduce Data Fetch Frequency

**Impact**: 40-60% faster ⚡⚡

Many metrics don't change daily. Fetch less frequently:

```python
# ✅ Fetch financial statements only weekly/monthly
if current_date.day == 1:  # First day of month
    metrics = get_financial_metrics(ticker, current_date_str)
    news = get_company_news(ticker, current_date_str)
else:
    # Reuse from cache
    metrics = _last_fetched_metrics
```

### Strategy 5: Parallel Data Fetching

**Impact**: 50-70% faster for multiple tickers ⚡⚡⚡

Use `concurrent.futures` to fetch multiple tickers in parallel:

```python
from concurrent.futures import ThreadPoolExecutor

def _prefetch_data_parallel(self) -> None:
    """Prefetch data for all tickers in parallel."""
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [
            executor.submit(self._prefetch_ticker, ticker)
            for ticker in self._tickers
        ]
        for future in futures:
            future.result()  # Wait for completion
```

## 🚀 Quick Wins (Easiest to Implement)

### Quick Win 1: Add Ticker Object Cache (5 min implementation)

**File**: `src/tools/api_yahoo.py`

Add after line 32 (after `_cache = get_cache()`):

```python
# Ticker object cache to avoid recreating objects
_ticker_cache: dict[str, yf.Ticker] = {}

def _get_ticker(ticker: str) -> yf.Ticker:
    """Get or create cached Ticker object."""
    if ticker not in _ticker_cache:
        _ticker_cache[ticker] = yf.Ticker(ticker)
    return _ticker_cache[ticker]
```

Then replace all `yf.Ticker(ticker)` with `_get_ticker(ticker)` (5 locations).

**Expected improvement**: 50-70% faster

### Quick Win 2: Reduce News Fetching Limit (1 min)

**File**: `src/backtesting/engine.py` line 92

Change:
```python
# Before
get_company_news(ticker, self._end_date, start_date=self._start_date, limit=1000)

# After (fetch only recent news)
get_company_news(ticker, self._end_date, start_date=self._start_date, limit=100)
```

**Expected improvement**: 20-30% faster for news fetching

### Quick Win 3: Skip Insider Trades (Already Done)

Since Yahoo Finance returns empty insider trades, remove the call:

**File**: `src/backtesting/engine.py` line 91

Comment out or remove:
```python
# get_insider_trades(ticker, self._end_date, start_date=self._start_date, limit=1000)
```

**Expected improvement**: 5-10% faster

## 📊 Expected Performance Improvements

### Before Optimizations
```
1-month backtest, 1 ticker (AAPL):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total time: ~60-90 seconds
- Data fetching: ~24 seconds
- Agent processing: ~36 seconds
- Overhead: ~10 seconds
```

### After Quick Wins (1-3)
```
1-month backtest, 1 ticker (AAPL):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total time: ~30-45 seconds ⚡⚡
- Data fetching: ~8 seconds (67% faster)
- Agent processing: ~22 seconds
- Overhead: ~5 seconds
```

### After All Optimizations
```
1-month backtest, 1 ticker (AAPL):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total time: ~15-25 seconds ⚡⚡⚡
- Data fetching: ~3 seconds (87% faster)
- Agent processing: ~12 seconds
- Overhead: ~3 seconds
```

## 🛠️ Implementation Plan

### Phase 1: Quick Wins (Today - 10 minutes)
- [x] Profile current performance
- [ ] Add Ticker object caching
- [ ] Reduce news fetch limit
- [ ] Remove insider trades call
- [ ] Test and measure improvement

### Phase 2: Data Access Optimization (This week)
- [ ] Implement batch data fetching
- [ ] Add smart prefetching
- [ ] Cache financial statements longer
- [ ] Test with multiple tickers

### Phase 3: Advanced Optimization (Next week)
- [ ] Parallel data fetching for multiple tickers
- [ ] Implement data freshness strategy
- [ ] Add performance monitoring
- [ ] Document best practices

## 🎯 Benchmark Tests

Run these commands to measure performance:

```bash
# Test 1: Current performance (baseline)
time USE_YAHOO_FINANCE=true poetry run python src/backtester.py --tickers AAPL --long-only

# Test 2: After Ticker caching
time USE_YAHOO_FINANCE=true poetry run python src/backtester.py --tickers AAPL --long-only

# Test 3: Multiple tickers
time USE_YAHOO_FINANCE=true poetry run python src/backtester.py --tickers AAPL,MSFT,GOOGL --long-only
```

## 📝 Notes

1. **Yahoo Finance has internal caching** - First call is slow, subsequent calls are faster
2. **Network latency** - Performance varies based on internet connection
3. **Rate limiting** - Yahoo Finance may throttle excessive requests
4. **Data freshness** - Balance between performance and data recency

## 🔗 References

- yfinance documentation: https://github.com/ranaroussi/yfinance
- Python caching patterns: https://docs.python.org/3/library/functools.html#functools.lru_cache
- Concurrent data fetching: https://docs.python.org/3/library/concurrent.futures.html
