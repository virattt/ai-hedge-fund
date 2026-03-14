# API集成快速参考

## 基本使用

### 统一接口
所有市场使用相同的API接口，无需关心底层实现：

```python
from src.tools import api

# 获取价格数据
prices = api.get_prices(ticker, start_date, end_date)

# 获取财务指标
metrics = api.get_financial_metrics(ticker, end_date)

# 获取新闻
news = api.get_company_news(ticker, end_date)
```

## 支持的Ticker格式

| 市场 | 格式 | 示例 | 说明 |
|------|------|------|------|
| 美股 | 纯字母 | `AAPL`, `MSFT`, `GOOGL` | 自动使用financialdatasets |
| A股 | 数字.SH/SZ | `600000.SH`, `000001.SZ` | 自动使用AkShare/Yahoo |
| 港股 | 数字.HK | `0700.HK`, `9988.HK` | 自动使用Yahoo Finance |
| 商品 | 符号=F | `GC=F`, `CL=F`, `SI=F` | 自动使用Yahoo Finance |

## 返回格式

所有市场返回统一的Pydantic模型：

```python
# 价格数据
list[Price]  # 包含: open, close, high, low, volume, time

# 财务指标
list[FinancialMetrics]  # 包含: ticker, market_cap, pe_ratio等

# 新闻
list[CompanyNews]  # 包含: title, date, description, url
```

## 错误处理

API自动处理错误，返回空列表：

```python
# 网络错误
prices = api.get_prices("600000.SH", "2024-01-01", "2024-01-31")
# 返回: [] (不抛出异常)

# ticker不存在
prices = api.get_prices("INVALID", "2024-01-01", "2024-01-31")
# 返回: [] (不抛出异常)

# 数据源不可用
metrics = api.get_financial_metrics("000001.SZ", "2024-01-31")
# 返回: [] (记录警告日志)
```

## 完整示例

### 单一市场分析

```python
from src.tools import api

def analyze_us_stock():
    """分析美股"""
    ticker = "AAPL"
    prices = api.get_prices(ticker, "2024-01-01", "2024-01-31")
    metrics = api.get_financial_metrics(ticker, "2024-01-31")
    news = api.get_company_news(ticker, "2024-01-31", limit=10)

    print(f"价格数据: {len(prices)}条")
    print(f"财务指标: {len(metrics)}条")
    print(f"新闻: {len(news)}条")
```

### 多市场组合分析

```python
from src.tools import api

def analyze_multi_market():
    """分析多个市场"""
    tickers = [
        "AAPL",        # 美股
        "600000.SH",   # A股
        "0700.HK",     # 港股
        "GC=F"         # 黄金
    ]

    for ticker in tickers:
        prices = api.get_prices(ticker, "2024-01-01", "2024-01-31")
        print(f"{ticker}: {len(prices)}条价格数据")
```

### 在代理中使用

```python
from src.graph.state import AgentState
from src.tools import api

def my_analyst_agent(state: AgentState) -> AgentState:
    """自定义分析师代理"""
    tickers = state["data"]["tickers"]
    signals = {}

    for ticker in tickers:
        # 自动支持所有市场！
        prices = api.get_prices(ticker, start_date, end_date)

        if not prices:
            signals[ticker] = {"signal": "hold", "confidence": 0}
            continue

        # 分析逻辑...
        latest_price = prices[-1].close

        signals[ticker] = {
            "signal": "buy" if latest_price > 100 else "hold",
            "confidence": 75,
            "reasoning": f"当前价格: {latest_price}"
        }

    # 更新状态
    state["data"]["analyst_signals"]["my_analyst"] = signals
    return state
```

## 性能优化

### 缓存机制
所有API调用都自动缓存：

```python
# 第一次调用 - 从API获取
prices1 = api.get_prices("AAPL", "2024-01-01", "2024-01-31")

# 第二次调用 - 从缓存获取（瞬间返回）
prices2 = api.get_prices("AAPL", "2024-01-01", "2024-01-31")
```

### 批量获取
对于多个ticker，使用循环：

```python
tickers = ["AAPL", "MSFT", "GOOGL"]
all_prices = {}

for ticker in tickers:
    all_prices[ticker] = api.get_prices(ticker, start_date, end_date)
```

## 数据可用性

| 功能 | 美股 | A股 | 港股 | 商品 |
|------|------|-----|------|------|
| 价格数据 | ✅ | ✅ | ✅ | ✅ |
| 财务指标 | ✅ | ⚠️ | ⚠️ | ❌ |
| 公司新闻 | ✅ | ⚠️ | ⚠️ | ✅ |

注：
- ✅ 完全支持
- ⚠️ 部分支持（可能返回空列表）
- ❌ 不支持（返回空列表）

## 常见问题

### Q1: 如何知道某个ticker支持哪些功能？

A: 调用相应函数，如果返回空列表则不支持。不会抛出异常。

```python
metrics = api.get_financial_metrics("GC=F", "2024-01-31")
if not metrics:
    print("商品期货不支持财务指标")
```

### Q2: 如何处理数据不可用的情况？

A: 检查返回列表是否为空：

```python
prices = api.get_prices(ticker, start_date, end_date)
if not prices:
    # 处理无数据情况
    return default_signal
```

### Q3: 日期格式要求？

A: 统一使用 `YYYY-MM-DD` 格式：

```python
# 正确
prices = api.get_prices("AAPL", "2024-01-01", "2024-01-31")

# 错误
prices = api.get_prices("AAPL", "2024/01/01", "2024/01/31")  # ❌
```

### Q4: 如何添加新市场支持？

A: 参考 `src/markets/` 目录下的适配器实现，创建新的适配器并在 `MarketRouter` 中注册。

## 调试技巧

### 查看日志
启用日志查看详细信息：

```python
import logging
logging.basicConfig(level=logging.INFO)

prices = api.get_prices("600000.SH", "2024-01-01", "2024-01-31")
# 会看到: MarketRouter error for 600000.SH: ...
```

### 测试连接
使用小日期范围测试：

```python
# 测试API连接
prices = api.get_prices("AAPL", "2024-01-01", "2024-01-02")
if prices:
    print("API连接正常")
else:
    print("API连接失败或ticker无效")
```

## 相关文档

- 详细实现: `docs/task7_api_integration_summary.md`
- 完成报告: `TASK7_API_INTEGRATION_COMPLETE.md`
- 市场适配器: `src/markets/README.md` (如果存在)
- 测试示例: `tests/tools/test_api_integration.py`
