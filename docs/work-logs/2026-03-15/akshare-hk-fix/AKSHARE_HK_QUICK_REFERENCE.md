# AKShare HK Financial Data - Quick Reference

## Quick Commands

### Run Tests
```bash
# Run enhanced HK tests
poetry run pytest tests/markets/test_akshare_hk_enhanced.py -v

# Run all HK stock tests
poetry run pytest tests/markets/test_hk_stock_adapter.py tests/markets/test_akshare_hk_enhanced.py -v

# Run validation script
python3 validate_hk_enhancement.py
```

### Test Single Ticker
```python
from src.markets.sources.akshare_source import AKShareSource

source = AKShareSource()
metrics = source.get_financial_metrics("00700", "2024-12-31")
print(f"Completeness: {sum(1 for v in metrics.values() if v is not None)}/{len(metrics)} fields")
```

## Data Fields Reference

### Direct from API (11 fields)
| Field | Source | Description |
|-------|--------|-------------|
| `return_on_equity` | 股东权益回报率(%) | ROE - Profitability |
| `return_on_assets` | 总资产回报率(%) | ROA - Asset efficiency |
| `net_margin` | 销售净利率(%) | Net profit margin |
| `price_to_earnings_ratio` | 市盈率 | P/E ratio |
| `price_to_book_ratio` | 市净率 | P/B ratio |
| `market_cap` | 总市值(港元) | Market capitalization |
| `revenue` | 营业总收入 | Total revenue |
| `net_income` | 净利润 | Net income |
| `revenue_growth` | 营业总收入滚动环比增长(%) | Revenue growth |
| `earnings_per_share` | 基本每股收益(元) | EPS |
| `book_value_per_share` | 每股净资产(元) | Book value per share |

### Estimated Fields (4 fields)
| Field | Formula | Notes |
|-------|---------|-------|
| `operating_margin` | Net Margin × 1.35 | Conservative estimate |
| `gross_margin` | Net Margin × 2.0 | Industry average |
| `debt_to_equity` | (ROE / ROA) - 1 | Leverage relationship |
| `current_ratio` | Based on ROE | 2.0 if ROE≥15%, 1.5 if ROE≥10% |

## Common Issues & Solutions

### Issue 1: Missing debt_to_equity
**Symptom**: `debt_to_equity` is None
**Cause**: ROE/ROA ratio out of reasonable range (>10 or <0)
**Solution**: Check if company has unusual capital structure

### Issue 2: High debt_to_equity (>5)
**Symptom**: D/E ratio seems too high
**Cause**: Financial services company or highly leveraged
**Solution**: Normal for financial institutions, verify with actual financial statements

### Issue 3: Gross margin > 100%
**Symptom**: `gross_margin` exceeds 1.0 (100%)
**Cause**: Very high net margin causing estimation overflow
**Solution**: Use actual financial statements for precise analysis

## Estimation Formulas

### Operating Margin
```python
# Based on typical cost structure
operating_margin = net_margin * 1.35

# Rationale: Operating margin typically 1.2-1.5x net margin
# 1.35 is conservative middle estimate
```

### Gross Margin
```python
# Industry average relationship
gross_margin = net_margin * 2.0

# Rationale:
# - Tech companies: 2.0-2.5x
# - Industrial: 1.5-2.0x
# - Financial: varies widely
```

### Debt to Equity
```python
# From leverage relationship: ROE = ROA × (1 + D/E)
debt_to_equity = (roe / roa) - 1

# Valid range: 0-10 (0-5 for non-financial, 0-10 for financial)
```

### Current Ratio
```python
# Based on profitability as liquidity indicator
if roe >= 0.15:
    current_ratio = 2.0    # Strong companies maintain good liquidity
elif roe >= 0.10:
    current_ratio = 1.5
elif roe >= 0.05:
    current_ratio = 1.2
else:
    current_ratio = 1.0    # Conservative estimate
```

## Logging Interpretation

### Success Log
```
[AKShare] ✓ Got HK financial metrics for 00700: 30/31 fields populated (6 estimated)
```
- 30/31 = 96.8% completeness
- 6 estimated = includes derived calculations

### Estimation Logs
```
[AKShare] 00700: Estimated operating_margin=41.35% from net_margin=30.63%
[AKShare] 00700: Estimated debt_to_equity=0.80 from ROE=15.53%, ROA=8.64%
```
- Shows calculation transparency
- Values are reasonable for the company

### Warning Logs
```
[AKShare] 00388: Calculated debt_to_equity=7.59 exceeds typical range
[AKShare] 00388: Missing critical fields: debt_to_equity
```
- Indicates unusual values or missing data
- Review company's actual financials

## Field Mapping

### API to System Field Mapping
| API Field (Chinese) | System Field | Conversion |
|---------------------|--------------|------------|
| 股东权益回报率(%) | return_on_equity | ÷ 100 |
| 销售净利率(%) | net_margin | ÷ 100 |
| 市盈率 | price_to_earnings_ratio | Direct |
| 总市值(港元) | market_cap | Direct |
| 营业总收入 | revenue | Direct |
| 净利润 | net_income | Direct |

## Validation Checklist

When adding new tickers or modifying code:

- [ ] Run unit tests: `pytest tests/markets/test_akshare_hk_enhanced.py`
- [ ] Run validation script: `python3 validate_hk_enhancement.py`
- [ ] Test with analyst: Warren Buffett's analyze_fundamentals
- [ ] Check log output for warnings
- [ ] Verify estimated fields are reasonable
- [ ] Compare with actual financial statements if available

## Troubleshooting

### Error: "AKShare is not available"
```bash
pip install akshare
# or
poetry add akshare
```

### Error: "No HK financial data for {ticker}"
- Verify ticker format (5 digits: 00700, not 700)
- Check if ticker exists on HKEX
- Verify API is accessible

### Error: "Fields populated (0/31)"
- API may be down or rate limited
- Check network connectivity
- Add delay between requests

## Performance Tips

1. **Cache Results**: Store metrics to reduce API calls
2. **Batch Processing**: Process multiple tickers with delays
3. **Retry Logic**: Already implemented with exponential backoff
4. **Rate Limiting**: Add 1-3 second delays between requests

## Contact & Support

- **Documentation**: See AKSHARE_HK_ENHANCEMENT.md for detailed info
- **Tests**: tests/markets/test_akshare_hk_enhanced.py
- **Validation**: validate_hk_enhancement.py
- **Code**: src/markets/sources/akshare_source.py (line 229+)
