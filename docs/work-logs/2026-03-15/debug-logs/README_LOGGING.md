# 数据源URL日志使用指南

## 快速开始

现在运行主程序时，您会看到每个数据源的完整请求URL：

```bash
poetry run python src/main.py --ticker 3690.HK --analysts-all --model "MiniMax-M2.5"
```

## 您会看到什么

### 1. 进度条（实时更新）
```
 ⋯ Bill Ackman         [3690.HK] Fetching financial metrics
 ✓ Bill Ackman         [3690.HK] Done
 ⋯ Risk Management     [3690.HK] Fetching price data and calculating volatility
 ✓ Risk Management     [3690.HK] Done
 ⋯ Portfolio Manager   [3690.HK] Generating trading decisions
 ✓ Portfolio Manager   [3690.HK] Done
```

### 2. URL日志（混合显示）
```
[HKAdapter] 🔄 Fetching prices from SinaFinance for 03690...
[SinaFinance] 📡 GET https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=hk03690,day,,,100,qfq
[SinaFinance] ✓ Retrieved 100 prices for 03690
[HKAdapter] ✓ Got 100 prices from SinaFinance for 03690

[HKAdapter] 🔄 Fetching prices from YFinance for 03690...
[YFinance] 📡 Calling Ticker(3690.HK).history(start=2025-12-15, end=2026-03-15)
[YFinance] Attempt 1/3 failed for 03690: Too Many Requests. Rate limited. Try after a while.
[YFinance] 📡 Calling Ticker(3690.HK).history(start=2025-12-15, end=2026-03-15)
```

## 日志符号说明

| 符号 | 含义 | 示例 |
|------|------|------|
| 🔄 | 开始获取数据 | `[HKAdapter] 🔄 Fetching prices from SinaFinance...` |
| 📡 | 发起HTTP请求（显示完整URL） | `[SinaFinance] 📡 GET https://...` |
| ✓ | 成功获取数据 | `[SinaFinance] ✓ Retrieved 100 prices for 03690` |
| ⚠ | 警告（数据源返回空） | `[HKAdapter] ⚠ SinaFinance returned no data` |
| ✗ | 错误（请求失败） | `[YFinance] ✗ Failed to get prices after 3 attempts` |

## 不同市场的URL格式

### CN股票（A股）
```bash
poetry run python src/main.py --ticker 000001.SZ --analysts "bill_ackman" --model "MiniMax-M2.5"
```

**URL日志示例**：
```
[EastmoneyCurl] 📡 Requesting URL: https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=0.000001&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61&klt=101&fqt=1&beg=20260213&end=20260315

[SinaFinance] 📡 GET https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketDataService.getKLineData?symbol=sz000001&scale=240&ma=no&datalen=40

[AKShare] 📡 Calling stock_zh_a_hist(symbol=000001, start_date=20260213, end_date=20260315, adjust=qfq)

[Tushare] 📡 Calling daily(ts_code=000001.SZ, start_date=20260213, end_date=20260315)

[YFinance] 📡 Calling Ticker(000001.SZ).history(start=2026-02-13, end=2026-03-15)
```

### HK股票（港股）
```bash
poetry run python src/main.py --ticker 3690.HK --analysts "bill_ackman" --model "MiniMax-M2.5"
```

**URL日志示例**：
```
[SinaFinance] 📡 GET https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=hk03690,day,,,100,qfq

[YFinance] 📡 Calling Ticker(3690.HK).history(start=2025-12-15, end=2026-03-15)

[AKShare] 📡 Calling stock_hk_hist(symbol=03690, start_date=20251215, end_date=20260315)
```

### US股票（美股）
```bash
poetry run python src/main.py --ticker AAPL --analysts "bill_ackman" --model "MiniMax-M2.5"
```

**URL日志示例**：
```
[YFinance] 📡 Calling Ticker(AAPL).history(start=2025-12-15, end=2026-03-15)
```

## 数据源优先级

### CN股票数据源
1. **EastmoneyCurl** - 主力，最稳定，完整URL
2. **SinaFinance** - 备份，数据丰富，完整URL
3. **Tushare** - 需要token，函数调用格式
4. **AKShare** - 连接不稳定，函数调用格式
5. **YFinance** - 频繁限流，函数调用格式

### HK股票数据源
1. **SinaFinance** - 主力，稳定可靠，完整URL
2. **YFinance** - 备份，频繁限流，函数调用格式
3. **AKShare** - 连接不稳定，函数调用格式

## 调试技巧

### 1. 只看URL日志
```bash
poetry run python src/main.py --ticker 3690.HK --analysts "bill_ackman" --model "MiniMax-M2.5" 2>&1 | grep "📡"
```

### 2. 只看成功的请求
```bash
poetry run python src/main.py --ticker 3690.HK --analysts "bill_ackman" --model "MiniMax-M2.5" 2>&1 | grep "✓"
```

### 3. 只看失败的请求
```bash
poetry run python src/main.py --ticker 3690.HK --analysts "bill_ackman" --model "MiniMax-M2.5" 2>&1 | grep -E "(⚠|✗|Failed)"
```

### 4. 保存日志到文件
```bash
poetry run python src/main.py --ticker 3690.HK --analysts "bill_ackman" --model "MiniMax-M2.5" 2>&1 | tee run.log
```

### 5. 只看特定数据源的日志
```bash
# 只看SinaFinance
poetry run python src/main.py --ticker 3690.HK --analysts "bill_ackman" --model "MiniMax-M2.5" 2>&1 | grep "SinaFinance"

# 只看YFinance
poetry run python src/main.py --ticker 3690.HK --analysts "bill_ackman" --model "MiniMax-M2.5" 2>&1 | grep "YFinance"
```

## 常见问题

### Q1: 为什么看不到URL日志？
**A**: 确保您使用的是最新版本的代码，`src/main.py` 中应该有：
```python
logging.basicConfig(
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stderr)],  # 注意是stderr
    force=True
)
```

### Q2: 为什么有些数据源显示URL，有些显示函数调用？
**A**:
- **HTTP API数据源**（Eastmoney, SinaFinance）显示完整URL
- **Python SDK数据源**（YFinance, AKShare, Tushare）显示函数调用格式

### Q3: 为什么YFinance总是失败？
**A**: YFinance有严格的限流机制。建议：
- 降低YFinance的优先级
- 或者在adapter中注释掉YFinance
- 系统会自动使用其他数据源

### Q4: 如何禁用某个数据源？
**A**: 在对应的adapter中注释掉：

**CN股票** (`src/markets/cn_stock.py`):
```python
data_sources = [
    EastmoneyCurlSource(),
    # TushareSource(),      # 注释掉不需要的
    AKShareSource(),
    SinaFinanceSource(),
    # YFinanceSource(),     # 注释掉频繁限流的
]
```

**HK股票** (`src/markets/hk_stock.py`):
```python
data_sources = [
    SinaFinanceSource(),
    # YFinanceSource(),     # 注释掉频繁限流的
    AKShareSource(),
]
```

### Q5: 如何增加日志详细程度？
**A**: 修改 `src/main.py` 中的日志级别：
```python
logging.basicConfig(
    level=logging.DEBUG,  # 改为DEBUG查看更多信息
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',  # 添加时间戳
    handlers=[logging.StreamHandler(sys.stderr)],
    force=True
)
```

## 技术细节

### 为什么使用stderr而不是stdout？
- **stdout**: Rich进度条使用，会捕获所有输出
- **stderr**: 日志输出，不会被Rich捕获
- **结果**: 进度条和日志可以同时显示

### 日志流程
1. 数据源发起请求前，打印URL日志（INFO级别）
2. 请求成功后，打印成功日志（INFO级别）
3. 请求失败后，打印错误日志（ERROR级别）
4. 所有日志输出到stderr
5. 终端同时显示进度条（stdout）和日志（stderr）

## 相关文档

- **LOGGING_FIX_FINAL.md** - 详细的技术说明
- **FINAL_FIX_SUMMARY.md** - 完整修复总结
- **QUICK_START.md** - 快速开始指南
- **README_LOGGING.md** - 本文件

## 总结

✅ **所有功能已完整实现**

1. ✅ 数据源并行请求
2. ✅ 完整的URL日志
3. ✅ 进度条实时显示
4. ✅ 日志和进度条同时可见
5. ✅ 支持CN/HK/US三个市场

现在您可以清楚地看到：
- 每个数据源请求的完整URL
- 请求参数和方法
- 请求成功或失败状态
- 实时的进度更新

享受完整的调试体验！🎉
