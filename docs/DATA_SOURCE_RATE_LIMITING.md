# 数据源限流问题诊断与解决方案

## 🔍 问题诊断

当运行 `poetry run python src/main.py --ticker 000001` 时，出现以下错误：

```
[AKShare] Failed to get CN prices for 000001: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))
[YFinance] Too Many Requests. Rate limited. Try after a while.
[CNAdapter] No price data available from any source for 000001
```

### 根本原因

1. **AKShare 限流**: 东方财富等数据源检测到频繁请求，主动断开连接
2. **YFinance 限流**: Yahoo Finance API 返回 429 Too Many Requests
3. **短时间内多次请求**: 测试时反复运行导致触发限流

## ✅ 已实施的改进

### 1. AKShare 增强延迟机制

**文件**: `src/markets/sources/akshare_source.py`

```python
# 在每次请求前添加延迟
- 首次请求: 延迟 1 秒
- 重试请求: 延迟 3s, 6s, 9s (递增)
```

### 2. CN股票添加多数据源

**文件**: `src/markets/cn_stock.py`

```python
# 添加 YFinance 作为备用数据源
data_sources = [
    AKShareSource(),    # 主数据源
    YFinanceSource(),   # 备用数据源
]
```

### 3. YFinance 已有的保护机制

**文件**: `src/markets/sources/yfinance_source.py`

- 随机延迟: 0.5-1.5秒
- 指数退避重试: 2-5秒 × (重试次数)
- 使用 curl_cffi 模拟浏览器

## 🛠️ 用户解决方案

### 方案 1: 等待冷却期（推荐）

**等待 5-10 分钟后再运行**，让数据源的限流计数器重置。

```bash
# 等待 10 分钟后
poetry run python src/main.py --ticker 000001 --analysts-all --model "MiniMax-M2.5"
```

### 方案 2: 使用缓存

数据会自动缓存 5 分钟（300秒），如果之前成功获取过数据，会直接使用缓存。

查看缓存配置：
```python
# src/data/cache.py
DEFAULT_TTL = 300  # 5分钟
```

### 方案 3: 使用代理（高级）

如果频繁使用，可以配置代理池来避免限流：

```python
# 在 .env 文件中添加
HTTP_PROXY=http://your-proxy:port
HTTPS_PROXY=http://your-proxy:port
```

### 方案 4: 使用付费API

对于生产环境，建议使用付费数据源：

1. **Tushare Pro** (中国市场)
   - 网址: https://tushare.pro
   - 费用: 免费额度 + 付费套餐
   - 限流: 每分钟 200 次（付费用户）

2. **聚宽数据** (JoinQuant)
   - 网址: https://www.joinquant.com
   - 费用: 按需付费
   - 限流: 根据套餐

3. **Financial Datasets API**
   - 已在 `src/tools/api.py` 中集成
   - 需要 `FINANCIAL_DATASETS_API_KEY`

## 📊 当前数据源状态

| 数据源 | 市场 | 免费额度 | 限流策略 | 状态 |
|--------|------|----------|----------|------|
| AKShare | CN, HK | 无限制 | 反爬虫检测 | ⚠️ 易触发 |
| YFinance | US, HK, CN | 无限制 | 429 限流 | ⚠️ 易触发 |
| Financial Datasets | US | 有限 | API Key | ✅ 稳定 |

## 🔧 调试命令

### 测试数据源连接

```bash
# 测试 AKShare
python3 -c "
from src.markets.sources.akshare_source import AKShareSource
source = AKShareSource()
prices = source.get_prices('000001', '2024-01-01', '2024-01-05')
print(f'Got {len(prices)} records')
"

# 测试 YFinance
python3 -c "
from src.markets.sources.yfinance_source import YFinanceSource
source = YFinanceSource()
prices = source.get_prices('000001.SZ', '2024-01-01', '2024-01-05')
print(f'Got {len(prices)} records')
"
```

### 查看缓存状态

```bash
# 缓存目录
ls -lh ~/.cache/ai-hedge-fund/

# 清除缓存
rm -rf ~/.cache/ai-hedge-fund/
```

## 📝 最佳实践

1. **避免短时间内重复请求同一ticker**
2. **使用缓存**: 5分钟内的数据会自动缓存
3. **批量请求时添加延迟**: 在循环中添加 `time.sleep(2)`
4. **生产环境使用付费API**: 更稳定、更快、更多功能
5. **监控限流日志**: 注意 `Rate limited` 和 `Connection aborted` 错误

## 🚀 未来改进

- [ ] 实现 Tushare Pro 数据源
- [ ] 添加请求队列和限流器
- [ ] 实现数据源健康检查
- [ ] 添加数据源自动切换逻辑
- [ ] 增加缓存 TTL 到 1 小时

## 📞 获取帮助

如果问题持续存在：

1. 检查网络连接
2. 确认防火墙设置
3. 尝试使用 VPN
4. 查看 AKShare 和 YFinance 的官方文档
