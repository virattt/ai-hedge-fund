# YFinance数据源禁用说明

## 实施日期
2026-03-16

## 背景

YFinance在中国大陆无法访问，因此需要禁用所有使用YFinance的数据源。为了保持代码的完整性和未来可能的恢复，我们采用注释禁用的方式，而不是删除代码。

---

## 禁用范围

### 1. 港股市场 (HK Stock)

**文件：** `src/markets/hk_stock.py`

**禁用内容：**
- 从data_sources列表中移除YFinanceSource
- 从news_sources列表中移除YFinanceSource

**数据源优先级（调整后）：**
```python
# 价格数据源
data_sources = [
    SinaFinanceSource(),    # Primary: Free, stable
    # YFinanceSource(),     # Disabled: Not available in China
    AKShareSource(),        # Fallback: Backup
]

# 新闻数据源
news_sources = [
    AKShareNewsSource(),  # Primary: Eastmoney news
    NewsNowSource(),      # Fallback: News aggregator
    # YFinanceSource(),   # Disabled: Not available in China
]
```

**影响：**
- 港股数据获取仍然可用，使用SinaFinance作为主要数据源
- 新闻获取使用AKShareNews和NewsNow
- 不影响现有功能

---

### 2. A股市场 (CN Stock)

**文件：** `src/markets/cn_stock.py`

**禁用内容：**
- 从data_sources列表中移除YFinanceSource

**数据源优先级（调整后）：**
```python
data_sources = [
    EastmoneyCurlSource(),  # Primary: Most comprehensive, bypasses anti-bot
    TushareSource(),        # Fallback 1: Requires token
    AKShareSource(),        # Fallback 2: Free, good coverage
    SinaFinanceSource(),    # Fallback 3: Free, stable
    # YFinanceSource(),     # Disabled: Not available in China
]
```

**影响：**
- A股数据获取仍然可用，使用EastmoneyCurl作为主要数据源
- 有4个备用数据源，数据获取更加可靠
- 不影响现有功能

---

### 3. 商品期货市场 (Commodity)

**文件：** `src/markets/commodity.py`

**禁用内容：**
- 整个CommodityAdapter依赖YFinance，无法完全替代
- 添加全局禁用标志：`COMMODITY_ADAPTER_ENABLED = False`
- 在所有关键方法中添加检查，返回空数据

**禁用方式：**
```python
# 全局禁用标志
COMMODITY_ADAPTER_ENABLED = False

# 在__init__中添加警告
if not COMMODITY_ADAPTER_ENABLED:
    logger.warning("⚠️ CommodityAdapter is DISABLED: YFinance is not available in China.")

# 在get_prices中添加检查
def get_prices(self, ticker: str, start_date: str, end_date: str) -> List[Dict]:
    if not COMMODITY_ADAPTER_ENABLED:
        logger.warning(f"CommodityAdapter is disabled: Cannot fetch prices for {ticker}")
        return []
    # ... rest of the code

# 在get_company_news中添加检查
def get_company_news(self, ticker: str, end_date: str, limit: int) -> List[Dict]:
    if not COMMODITY_ADAPTER_ENABLED:
        logger.warning(f"CommodityAdapter is disabled: Cannot fetch news for {ticker}")
        return []
    # ... rest of the code
```

**影响：**
- ⚠️ **商品期货功能完全不可用**
- 尝试获取商品数据时会返回空列表
- 会在日志中显示警告信息
- 不会抛出异常，不影响其他市场的正常运行

---

## 恢复指南

如果将来需要在海外环境中恢复YFinance功能，请按照以下步骤操作：

### 1. 恢复港股和A股市场的YFinance

**步骤：**
1. 在 `src/markets/hk_stock.py` 中：
   - 取消注释：`from src.markets.sources.yfinance_source import YFinanceSource`
   - 在data_sources中取消注释：`YFinanceSource(),`
   - 在news_sources中取消注释：`YFinanceSource(),`

2. 在 `src/markets/cn_stock.py` 中：
   - 取消注释：`from src.markets.sources.yfinance_source import YFinanceSource`
   - 在data_sources中取消注释：`YFinanceSource(),`

### 2. 恢复商品期货市场

**步骤：**
1. 在 `src/markets/commodity.py` 中：
   - 修改全局标志：`COMMODITY_ADAPTER_ENABLED = True`
   - 取消注释：`import yfinance as yf`
   - 取消注释：`import feedparser`
   - 取消注释：`from dateutil import parser as date_parser`
   - 移除 `get_prices` 和 `get_company_news` 中的禁用检查

2. 安装依赖（如果尚未安装）：
   ```bash
   poetry add yfinance feedparser python-dateutil
   ```

---

## 测试验证

### 测试港股数据获取（应该正常工作）

```bash
poetry run python src/main.py --tickers 3690.HK --analysts-all --model "deepseek-chat"
```

**预期结果：**
- ✅ 成功获取港股数据
- ✅ 使用SinaFinance和AKShare作为数据源
- ✅ 不显示YFinance相关的错误或警告

### 测试A股数据获取（应该正常工作）

```bash
poetry run python src/main.py --tickers 000001 --analysts-all --model "deepseek-chat"
```

**预期结果：**
- ✅ 成功获取A股数据
- ✅ 使用EastmoneyCurl、Tushare、AKShare或SinaFinance作为数据源
- ✅ 不显示YFinance相关的错误或警告

### 测试商品期货（应该返回警告）

如果尝试使用商品期货ticker（如 GC=F），应该看到：

```bash
# 不推荐测试，因为会失败
poetry run python src/main.py --tickers GC=F --analysts-all --model "deepseek-chat"
```

**预期结果：**
- ⚠️ 显示警告：`CommodityAdapter is DISABLED: YFinance is not available in China`
- ⚠️ 返回空数据
- ⚠️ 不会崩溃或抛出异常

---

## 技术细节

### 为什么使用注释而不是删除？

1. **保持代码完整性**：未来可能在海外环境中需要YFinance
2. **便于对比**：可以清楚地看到原有的数据源配置
3. **易于恢复**：只需取消注释即可恢复功能
4. **文档价值**：代码本身记录了完整的数据源选项

### 为什么商品期货使用标志而不是注释？

商品期货适配器完全依赖YFinance，没有替代方案：
- 使用标志可以在运行时检查并返回空数据
- 避免导入错误（yfinance、feedparser等可能未安装）
- 提供更友好的错误提示
- 保持代码结构完整，便于未来恢复

### 性能影响

禁用YFinance后的性能影响：
- ✅ **港股**：无影响，SinaFinance响应速度快
- ✅ **A股**：无影响，EastmoneyCurl和其他数据源充足
- ⚠️ **商品期货**：完全不可用，但不影响其他市场

---

## 相关文件

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `src/markets/hk_stock.py` | 注释禁用 | 移除YFinance数据源和新闻源 |
| `src/markets/cn_stock.py` | 注释禁用 | 移除YFinance数据源 |
| `src/markets/commodity.py` | 标志禁用 | 添加禁用标志和检查 |
| `src/markets/sources/yfinance_source.py` | 保留 | 代码完整保留，未修改 |

---

## 注意事项

1. **不要删除YFinanceSource代码**：
   - `src/markets/sources/yfinance_source.py` 文件保持完整
   - 未来可能需要在海外环境中使用

2. **商品期货功能不可用**：
   - 如果业务需要商品期货数据，需要寻找替代数据源
   - 可能的替代方案：
     - Tushare Pro（支持部分期货数据）
     - AKShare（支持部分国内期货数据）
     - 专业期货数据提供商

3. **监控和告警**：
   - 系统会在日志中显示禁用警告
   - 不会影响港股和A股的正常运行
   - 如果尝试使用商品期货，会优雅地返回空数据

4. **依赖包**：
   - yfinance包仍然在pyproject.toml中（为了保持环境一致性）
   - 如果需要完全移除，可以运行：`poetry remove yfinance`
   - 但建议保留，以便未来恢复使用

---

## 未来改进建议

1. **添加配置选项**：
   - 在配置文件中添加 `ENABLE_YFINANCE` 选项
   - 根据部署环境自动启用/禁用

2. **替代数据源**：
   - 研究国内可用的商品期货数据源
   - 可能的选项：Tushare Pro、AKShare期货接口

3. **代理支持**：
   - 添加代理配置选项
   - 在有代理的环境中可以使用YFinance

4. **数据源健康检查**：
   - 自动检测YFinance可用性
   - 动态调整数据源优先级

---

## 相关文档

- [数据源架构说明](./DATA_SOURCES.md)
- [市场适配器文档](./MARKET_ADAPTERS.md)
- [日志优化说明](./LOGGING_OPTIMIZATION.md)
