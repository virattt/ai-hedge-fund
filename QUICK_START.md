# 快速开始指南

## 运行主程序（带URL日志）

### CN股票示例
```bash
poetry run python src/main.py --ticker 000001.SZ --analysts-all --model "MiniMax-M2.5"
```

### HK股票示例
```bash
poetry run python src/main.py --ticker 3690.HK --analysts-all --model "MiniMax-M2.5"
```

### 多个股票
```bash
poetry run python src/main.py --ticker 000001.SZ,3690.HK --analysts-all --model "MiniMax-M2.5"
```

### 指定分析师
```bash
poetry run python src/main.py --ticker 000001.SZ --analysts "bill_ackman,charlie_munger" --model "MiniMax-M2.5"
```

## 查看URL日志

现在运行主程序时，您会看到：

### 数据源请求日志
```
[CNAdapter] 🔄 Fetching prices from EastmoneyCurl for 000001...
[EastmoneyCurl] 📡 Requesting URL: https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=0.000001&...
[SinaFinance] 📡 GET https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketDataService.getKLineData?symbol=sz000001&...
```

### 数据源响应日志
```
[EastmoneyCurl] ✓ Retrieved 15 prices for 000001
[CNAdapter] ✓ Got 15 prices from EastmoneyCurl for 000001
[SinaFinance] ✓ Retrieved 40 prices for 000001
[CNAdapter] ✓ Got 40 prices from SinaFinance for 000001
```

### 失败日志
```
[AKShare] Failed to get CN prices for 000001: ('Connection aborted.', ...)
[AKShare] No price data for 000001
[CNAdapter] ⚠ AKShare returned no data for 000001
```

## 日志符号说明

| 符号 | 含义 |
|------|------|
| 📡 | 发起请求（显示完整URL） |
| 🔄 | 开始获取数据 |
| ✓ | 成功获取数据 |
| ⚠ | 警告（数据源返回空数据） |
| ✗ | 错误（请求失败） |

## 数据源优先级

### CN股票
1. **EastmoneyCurl** - 主力，最稳定
2. **SinaFinance** - 备份，数据丰富
3. **Tushare** - 需要token
4. **AKShare** - 连接不稳定
5. **YFinance** - 频繁限流

### HK股票
1. **SinaFinance** - 主力，稳定可靠
2. **YFinance** - 备份，频繁限流
3. **AKShare** - 连接不稳定

## 常见问题

### 1. 看不到URL日志？
确保 `src/main.py` 中有日志配置：
```python
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
```

### 2. YFinance频繁限流？
这是正常现象，系统会自动使用其他数据源。如果想禁用YFinance，可以修改对应的adapter。

### 3. Tushare无法使用？
需要配置 `TUSHARE_TOKEN` 环境变量：
```bash
export TUSHARE_TOKEN="your_token_here"
```

### 4. 数据获取太慢？
- 系统已使用并行请求，性能已优化
- 主要耗时来自YFinance的限流重试
- 考虑降低YFinance优先级或禁用

## 性能优化建议

### 1. 禁用慢速数据源
如果不需要某个数据源，可以在对应的adapter中移除：

**CN股票** (`src/markets/cn_stock.py`):
```python
data_sources = [
    EastmoneyCurlSource(),  # 保留
    # TushareSource(),      # 注释掉
    AKShareSource(),        # 保留
    SinaFinanceSource(),    # 保留
    # YFinanceSource(),     # 注释掉（如果频繁限流）
]
```

### 2. 调整超时时间
在各个数据源中调整 `timeout` 参数。

### 3. 增加缓存
系统已有缓存机制，可以在 `src/data/cache.py` 中调整缓存策略。

## 测试脚本

### 测试CN股票
```bash
poetry run python test_parallel_requests.py
```

### 测试HK股票
```bash
poetry run python test_hk_stock_logging.py
```

## 相关文档

- **FIX_COMPLETE.md** - 完整修复报告
- **VERIFICATION_SUCCESS.md** - 验证报告
- **FINAL_FIX_SUMMARY.md** - 最终总结
- **QUICK_START.md** - 本文件

## 支持的市场

| 市场 | 代码格式 | 示例 | 主力数据源 |
|------|---------|------|-----------|
| 中国A股 | XXXXXX.SH/SZ | 000001.SZ, 600000.SH | EastmoneyCurl, SinaFinance |
| 香港股票 | XXXX.HK | 3690.HK, 0700.HK | SinaFinance |
| 美国股票 | SYMBOL | AAPL, MSFT | YFinance |

## 获取帮助

如果遇到问题，请检查：
1. 日志输出中的错误信息
2. 数据源的URL和响应
3. 网络连接状态
4. API token配置（如Tushare）

---

**提示**：所有修复已完成，系统现在可以高效、可靠地从多个数据源并行获取数据，并提供详细的调试信息！🎉
