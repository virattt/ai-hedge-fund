# YFinance Rate Limiting Fix

## Problem
YFinance was experiencing frequent "Too Many Requests. Rate limited" errors, causing failures in:
- HK stock price data retrieval
- Financial metrics fetching
- Company news gathering

## Solution Implemented

### 1. Enhanced Rate Limiting (2-5 second delays)
- **Previous**: 0.5-1.5 second delays
- **New**: 2-5 second delays with intelligent spacing
- Added `_enforce_rate_limit()` method that:
  - Enforces minimum 2-5 second delay between requests
  - Tracks last request time to prevent rapid successive calls
  - Adds random jitter to avoid synchronized requests

### 2. Exponential Backoff Retry Strategy
- **Retry delays**: 4s, 8s, 16s (capped at 30s)
- Automatic detection of rate limit errors (429, "Too Many Requests", etc.)
- More aggressive backoff on rate limit vs. other errors
- Up to 3 retry attempts by default

### 3. Request-Level Caching
- **In-memory cache** with configurable TTL:
  - Price data: 5 minutes (300s)
  - Financial metrics: 10 minutes (600s)
  - Company news: 10 minutes (600s)
- Cache keys based on MD5 hash of method + parameters
- Prevents duplicate requests for same data
- Significantly reduces API load

## Code Changes

### Modified File: `src/markets/sources/yfinance_source.py`

#### New Instance Variables
```python
self._request_cache = {}  # Simple in-memory cache
self._last_request_time = 0  # Track last request time
```

#### New Helper Methods
1. `_enforce_rate_limit(min_delay=2.0, max_delay=5.0)` - Rate limiting with jitter
2. `_get_cache_key(method, **kwargs)` - Generate deterministic cache keys
3. `_get_from_cache(cache_key, max_age)` - Retrieve cached data if fresh
4. `_save_to_cache(cache_key, data)` - Save data to cache with timestamp

#### Enhanced Methods
All three main API methods now include:
- ✅ Cache check before API call
- ✅ Rate limiting on first attempt
- ✅ Exponential backoff on retries
- ✅ Rate limit error detection
- ✅ Cache storage after successful retrieval

1. **`get_prices()`**
   - Cache TTL: 5 minutes
   - Retry logic with exponential backoff
   - Rate limit detection

2. **`get_financial_metrics()`**
   - Cache TTL: 10 minutes
   - Added `max_retries` parameter
   - Enhanced error handling

3. **`get_company_news()`**
   - Cache TTL: 10 minutes
   - Added `max_retries` parameter
   - Rate limit protection

## Testing

### Unit Tests: `tests/markets/test_yfinance_rate_limiting.py`
- ✅ Rate limiting enforces delays (2-5s)
- ✅ Rate limiting prevents rapid successive requests
- ✅ Cache key generation is deterministic
- ✅ Cache saves and retrieves data correctly
- ✅ Cache expires old data
- ✅ `get_prices()` uses cache to avoid duplicate requests
- ✅ `get_prices()` retries on rate limit with exponential backoff
- ✅ `get_financial_metrics()` uses cache
- ✅ `get_company_news()` uses cache

**Test Results**: 9/9 tests passed

### Integration Tests: `tests/markets/test_yfinance_integration.py`
Optional slow tests for real API validation:
- Real API price retrieval
- Cache performance verification
- Rate limiting delay verification
- Financial metrics and news retrieval

Run with: `RUN_SLOW_TESTS=1 pytest tests/markets/test_yfinance_integration.py -v -s`

## Benefits

1. **Reduced Rate Limit Errors**: 2-5s delays prevent hitting rate limits
2. **Better Error Recovery**: Exponential backoff handles transient rate limits
3. **Lower API Load**: Caching eliminates duplicate requests within TTL window
4. **Improved Performance**: Cached responses are instant (no network delay)
5. **Cost Reduction**: Fewer API calls = lower usage/costs

## Performance Impact

### Before
- Delay: 0.5-1.5s per request
- No caching
- Simple linear retry
- High rate limit errors

### After
- Delay: 2-5s per request (first call)
- Cached responses: ~0ms (instant)
- Exponential backoff: 4s, 8s, 16s
- Minimal rate limit errors

### Expected Behavior
- **First request**: 2-5s delay + API call time
- **Cached request**: <1ms (instant)
- **Rate limit retry**: 4s → 8s → 16s backoff
- **Cache hit rate**: Expected 60-80% for repeated queries

## Monitoring

Enhanced logging provides visibility:
```
[YFinance] Rate limit: waiting 3.45s before request
[YFinance] 📡 Calling Ticker(0700.HK).history(start=2024-01-01, end=2024-12-31)
[YFinance] ✓ Retrieved 245 price records for 00700
[YFinance] Cached data for 8f3c9d2a...
[YFinance] Using cached price data for 00700
[YFinance] Exponential backoff: waiting 4.3s before retry 2/3
[YFinance] Rate limit hit for 00700 on attempt 1/3
```

## Recommendations

1. **Monitor cache hit rates** - Adjust TTL if hit rate is too low
2. **Track retry counts** - If retries are frequent, increase base delays
3. **Consider Redis cache** - For multi-process deployments
4. **Add cache statistics** - Monitor cache size and eviction

## Backward Compatibility

✅ All existing tests pass
✅ No breaking API changes
✅ Optional parameters added (backward compatible)
✅ Default behavior enhanced but compatible

## Future Enhancements

1. **Persistent cache**: Use Redis/file cache for cross-session caching
2. **Adaptive rate limiting**: Adjust delays based on error rates
3. **Circuit breaker**: Temporarily disable source after repeated failures
4. **Cache warming**: Pre-fetch commonly used data
5. **Cache statistics**: Track hit/miss rates, API call counts
