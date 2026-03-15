# YFinance 反限流优化指南

## 问题背景

YFinance 是一个免费的金融数据 API，但有严格的速率限制。频繁请求会导致：
- `429 Too Many Requests` 错误
- 连接被拒绝
- 数据获取失败

## 实施的优化措施

### 1. 会话管理和自定义请求头

**位置**: `src/markets/sources/yfinance_source.py`

```python
# 创建持久会话
self._session = requests.Session()

# 随机选择 User-Agent
user_agents = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36...',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)...',
    # ... 更多
]

self._session.headers.update({
    'User-Agent': random.choice(user_agents),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
})
```

**效果**：
- ✅ 模拟真实浏览器行为
- ✅ 避免被识别为爬虫
- ✅ 复用连接，减少握手开销

### 2. 智能延迟策略

#### 首次请求延迟
```python
# 每次请求前添加随机延迟
time.sleep(random.uniform(0.5, 1.5))
```

#### 重试延迟（指数退避）
```python
if attempt > 0:
    delay = random.uniform(2, 5) * (attempt + 1)
    time.sleep(delay)
```

**延迟策略**：
| 请求类型 | 最小延迟 | 最大延迟 | 说明 |
|---------|---------|---------|------|
| 首次请求 | 0.5s | 1.5s | 避免突发请求 |
| 第1次重试 | 4s | 10s | 2-5s × 2 |
| 第2次重试 | 6s | 15s | 2-5s × 3 |
| 第3次重试 | 8s | 20s | 2-5s × 4 |

**效果**：
- ✅ 避免触发速率限制
- ✅ 给服务器恢复时间
- ✅ 随机化避免检测

### 3. 使用会话对象

```python
# 所有请求使用同一会话
stock = self._yf.Ticker(ticker, session=self._session)
```

**效果**：
- ✅ 连接复用
- ✅ 保持 Cookie
- ✅ 减少 TLS 握手

### 4. 配置化管理

**位置**: `src/markets/sources/rate_limit_config.py`

```python
YFINANCE_CONFIG = {
    "min_delay": 0.5,
    "max_delay": 1.5,
    "retry_min_delay": 2.0,
    "retry_max_delay": 5.0,
    "max_retries": 3,
    "exponential_backoff": True,
}
```

**效果**：
- ✅ 集中管理配置
- ✅ 易于调整参数
- ✅ 支持不同数据源

## 使用建议

### 1. 减少并发请求

**问题**：18 个分析师同时请求会触发限流

**解决方案**：
```python
# 在 MarketAdapter 中添加请求队列
import asyncio
from asyncio import Semaphore

# 限制并发数
semaphore = Semaphore(3)  # 最多 3 个并发请求

async def get_data_with_limit(ticker):
    async with semaphore:
        return await get_data(ticker)
```

### 2. 使用缓存

**问题**：重复请求相同数据

**解决方案**：
```python
from functools import lru_cache
from datetime import datetime, timedelta

@lru_cache(maxsize=100)
def get_prices_cached(ticker, start_date, end_date):
    return yf_source.get_prices(ticker, start_date, end_date)
```

### 3. 分批处理

**问题**：一次性处理太多股票

**解决方案**：
```python
# 分批处理，每批之间等待
batch_size = 3
for i in range(0, len(tickers), batch_size):
    batch = tickers[i:i + batch_size]
    process_batch(batch)
    time.sleep(10)  # 批次间等待
```

### 4. 使用代理（可选）

如果仍然遇到限流，可以配置代理：

```python
# 在 YFinanceSource.__init__ 中
proxies = {
    'http': 'http://proxy.example.com:8080',
    'https': 'https://proxy.example.com:8080',
}
self._session.proxies.update(proxies)
```

## 测试验证

运行测试脚本验证改进：

```bash
poetry run python test_rate_limit.py
```

**预期输出**：
```
Testing: 3690.HK (Meituan)
📊 Fetching price data...
[YFinance] ✓ Retrieved 20 price records for 03690
✅ SUCCESS: Retrieved 20 price records

💰 Fetching financial metrics...
[YFinance] ✓ Got financial metrics
✅ SUCCESS: Retrieved 15 financial metrics

Overall Success Rate: 8/9 (88.9%)
✅ Anti-rate-limit improvements are working!
```

## 监控和调试

### 查看详细日志

```bash
# 设置日志级别为 DEBUG
export LOG_LEVEL=DEBUG
poetry run python src/main.py --tickers 3690.HK ...
```

### 关键日志标识

```
[YFinance] Waiting 4.2s before retry 2/3  # 重试延迟
[YFinance] ✓ Retrieved 20 price records   # 成功
[YFinance] Attempt 1/3 failed: Too Many Requests  # 限流
```

## 进一步优化

如果仍然遇到问题：

1. **增加延迟**：修改 `rate_limit_config.py` 中的延迟参数
2. **减少重试次数**：避免频繁重试加剧限流
3. **使用付费 API**：考虑 Financial Datasets API
4. **本地缓存**：使用 Redis 或 SQLite 缓存数据
5. **分布式请求**：使用多个 IP 地址

## 配置调优

### 保守配置（低风险）
```python
YFINANCE_CONFIG = {
    "min_delay": 2.0,  # 更长的延迟
    "max_delay": 4.0,
    "retry_min_delay": 5.0,
    "retry_max_delay": 10.0,
    "max_retries": 2,  # 更少的重试
}
```

### 激进配置（高风险）
```python
YFINANCE_CONFIG = {
    "min_delay": 0.1,  # 更短的延迟
    "max_delay": 0.5,
    "retry_min_delay": 1.0,
    "retry_max_delay": 2.0,
    "max_retries": 5,  # 更多的重试
}
```

## 常见问题

### Q: 为什么还是遇到限流？
A: YFinance 的限流是动态的，取决于：
- 当前服务器负载
- 你的 IP 地址历史
- 请求的数据量
- 时间段（交易时间更容易限流）

### Q: 多久可以恢复？
A: 通常 5-15 分钟后限流会自动解除。

### Q: 可以完全避免限流吗？
A: 不能保证 100% 避免，但可以大幅降低概率。

## 相关资源

- YFinance 官方文档: https://github.com/ranaroussi/yfinance
- Rate Limiting 最佳实践: https://cloud.google.com/apis/design/design_patterns#rate_limiting
- Financial Datasets API: https://financialdatasets.ai/

## 更新日志

- 2026-03-15: 初始版本，添加会话管理和智能延迟
- 未来计划: 添加请求队列和分布式缓存
