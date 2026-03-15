# 数据源日志增强总结

## 修改内容

### 1. 数据源层面 (YFinance & AKShare)

#### YFinance (`src/markets/sources/yfinance_source.py`)
- ✅ 所有错误日志添加 `[YFinance]` 前缀
- ✅ 成功日志添加 `✓` 标记
- ✅ 重试日志显示数据源名称

**示例输出**：
```
[YFinance] ✓ Retrieved 20 price records for 03690
[YFinance] Attempt 1/3 failed for 03690: Too Many Requests
[YFinance] Failed to get prices for 03690 after 3 attempts
```

#### AKShare (`src/markets/sources/akshare_source.py`)
- ✅ 所有错误日志添加 `[AKShare]` 前缀
- ✅ 成功日志添加 `✓` 标记
- ✅ 重试日志显示数据源名称

**示例输出**：
```
[AKShare] ✓ Retrieved 20 price records for 03690
[AKShare] Attempt 1/3 failed for 03690: Connection aborted
[AKShare] Failed to get HK prices for 03690: RemoteDisconnected
```

### 2. 适配器层面 (MarketAdapter)

#### 基类 (`src/markets/base.py`)
- ✅ 所有日志添加 `[{market}Adapter]` 前缀（HK/CN/US/COMMODITY）
- ✅ 成功日志添加 `✓` 标记
- ✅ 显示使用的数据源名称

**示例输出**：
```
[HKAdapter] ✓ Got 20 prices from YFinance for 03690
[HKAdapter] Failed to get prices from AKShare for 03690: Connection error
[HKAdapter] No price data available from any source for 03690
[HKAdapter] ✓ Retrieved 15 validated prices for 03690
```

## 日志层级

| 级别 | 用途 | 示例 |
|------|------|------|
| **INFO** | 成功操作 | `[YFinance] ✓ Retrieved 20 price records` |
| **WARNING** | 重试/降级 | `[YFinance] Attempt 1/3 failed` |
| **ERROR** | 最终失败 | `[YFinance] Failed after 3 attempts` |

## 快速定位问题

现在可以轻松识别问题来源：

### API 限流问题
```
[YFinance] Attempt 1/3 failed for 03690: Too Many Requests. Rate limited
[YFinance] Attempt 2/3 failed for 03690: Too Many Requests. Rate limited
[YFinance] Failed to get prices for 03690 after 3 attempts
```
**解决方案**：等待限流恢复，或使用付费 API

### 连接问题
```
[AKShare] Failed to get HK prices for 03690: Connection aborted
```
**解决方案**：检查网络连接，或切换数据源

### 数据不可用
```
[HKAdapter] No price data available from any source for 03690
```
**解决方案**：检查股票代码是否正确，或尝试其他日期范围

## 测试命令

```bash
# 测试港股（美团）
poetry run python src/main.py --tickers 3690.HK --analysts warren_buffett --model "MiniMax-M2.5"

# 测试A股（贵州茅台）
poetry run python src/main.py --tickers 600519.SH --analysts warren_buffett --model "MiniMax-M2.5"

# 测试美股（苹果）
poetry run python src/main.py --tickers AAPL --analysts warren_buffett --model "MiniMax-M2.5"
```

## 日志示例

### 成功场景
```
INFO - [HKAdapter] ✓ Got 20 prices from YFinance for 03690
INFO - [HKAdapter] ✓ Retrieved 20 validated prices for 03690
INFO - [HKAdapter] ✓ Got financial metrics from YFinance for 03690
INFO - [HKAdapter] ✓ Got 5 news items from YFinance for 03690
```

### 失败场景（限流）
```
WARNING - [YFinance] Attempt 1/3 failed for 03690: Too Many Requests
WARNING - [YFinance] Attempt 2/3 failed for 03690: Too Many Requests
WARNING - [YFinance] Attempt 3/3 failed for 03690: Too Many Requests
ERROR - [YFinance] Failed to get prices for 03690 after 3 attempts
WARNING - [HKAdapter] No price data available from any source for 03690
```

### 混合场景（部分成功）
```
ERROR - [AKShare] Failed to get HK prices for 03690: Connection error
INFO - [YFinance] ✓ Retrieved 20 price records for 03690
INFO - [HKAdapter] ✓ Got 20 prices from YFinance for 03690
WARNING - [HKAdapter] Using fallback data from first source (20 records)
```
