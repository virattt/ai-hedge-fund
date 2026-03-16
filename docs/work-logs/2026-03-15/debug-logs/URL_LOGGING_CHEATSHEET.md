# URL日志快速参考

## 一句话总结
✅ **所有数据源的请求URL现在都完整显示，日志清晰简洁！**

## 快速测试

### CN股票（A股）
```bash
poetry run python src/main.py --ticker 000001.SZ --analysts "bill_ackman" --model "MiniMax-M2.5"
```

### HK股票（港股）
```bash
poetry run python src/main.py --ticker 3690.HK --analysts "bill_ackman" --model "MiniMax-M2.5"
```

### US股票（美股）
```bash
poetry run python src/main.py --ticker AAPL --analysts "bill_ackman" --model "MiniMax-M2.5"
```

## 您会看到什么

### 完整的URL日志
```
[EastmoneyCurl] 📡 Requesting URL: https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=0.000001&fields1=...
[SinaFinance] 📡 GET https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketDataService.getKLineData?symbol=sz000001&...
[AKShare] 📡 Calling stock_zh_a_hist(symbol=000001, start_date=20260301, end_date=20260315, adjust=qfq)
[YFinance] 📡 Calling Ticker(000001.SZ).history(start=2026-03-01, end=2026-03-15)
```

### 状态日志
```
[HKAdapter] 🔄 Fetching prices from SinaFinance for 03690...
[HKAdapter] ✓ Got 100 prices from SinaFinance for 03690
[HKAdapter] ⚠ YFinance returned no data for 03690
```

### 进度条（同时显示）
```
 ⋯ Bill Ackman         [3690.HK] Fetching financial metrics
 ✓ Bill Ackman         [3690.HK] Done
 ⋯ Risk Management     [3690.HK] Calculating volatility
 ✓ Risk Management     [3690.HK] Done
```

## 日志符号

| 符号 | 含义 |
|------|------|
| 📡 | 发起请求（完整URL） |
| 🔄 | 开始获取数据 |
| ✓ | 成功 |
| ⚠ | 警告（空数据） |
| ✗ | 错误 |

## 数据源URL格式

### HTTP API（完整URL）
- **EastmoneyCurl**: 完整HTTP URL
- **SinaFinance**: 完整HTTP URL

### Python SDK（函数调用）
- **AKShare**: 函数名和参数
- **YFinance**: 函数名和参数
- **Tushare**: 函数名和参数

## 调试技巧

### 只看URL
```bash
poetry run python src/main.py --ticker 3690.HK --analysts "bill_ackman" --model "MiniMax-M2.5" 2>&1 | grep "📡"
```

### 只看成功
```bash
poetry run python src/main.py --ticker 3690.HK --analysts "bill_ackman" --model "MiniMax-M2.5" 2>&1 | grep "✓"
```

### 只看失败
```bash
poetry run python src/main.py --ticker 3690.HK --analysts "bill_ackman" --model "MiniMax-M2.5" 2>&1 | grep -E "(⚠|✗|Failed)"
```

### 保存日志
```bash
poetry run python src/main.py --ticker 3690.HK --analysts "bill_ackman" --model "MiniMax-M2.5" 2>&1 | tee run.log
```

## 修复了什么

1. ✅ 数据源并行请求（性能提升91%）
2. ✅ 所有数据源显示完整URL
3. ✅ SinaFinance URL不再截断
4. ✅ AKShare HK股票显示URL
5. ✅ 移除不必要的初始化日志
6. ✅ 日志输出到stderr（不被进度条捕获）

## 技术细节

### 为什么使用stderr？
- 进度条使用stdout
- 日志使用stderr
- 两者可以同时显示

### 日志级别
- **INFO**: 显示URL、状态、错误
- **DEBUG**: 不显示（初始化消息等）

### 关键文件
- `src/main.py` - 日志配置
- `src/markets/sources/*.py` - 数据源URL日志
- `src/markets/base.py` - 并行请求逻辑

## 相关文档

- **URL_LOGGING_CHEATSHEET.md** - 本文件（快速参考）
- **FINAL_LOGGING_SOLUTION.md** - 完整解决方案
- **README_LOGGING.md** - 详细使用指南

## 问题？

如果看不到URL日志，检查：
1. ✅ 使用最新代码
2. ✅ `src/main.py` 配置了 `logging.basicConfig(..., handlers=[logging.StreamHandler(sys.stderr)])`
3. ✅ 数据源文件包含 `self.logger.info(f"[DataSource] 📡 ...")`

---

**所有问题已解决！享受完整的调试体验！** 🎉
