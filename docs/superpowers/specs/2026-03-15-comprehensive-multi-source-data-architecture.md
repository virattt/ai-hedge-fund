# 全面多源数据架构设计

**日期**: 2026-03-15
**版本**: 1.0
**状态**: 设计完成，待实现
**作者**: Claude + 用户协作

---

## 1. 背景与目标

### 1.1 问题现状

当前 AI 对冲基金项目遇到严重的数据源限流问题：

1. **Financial Datasets API 频繁 429 错误**
   - 18个分析师代理 × 多个股票 = 大量并发请求
   - 免费层限流严格，付费成本高
   - 特别是新闻接口最容易触发限流

2. **单一数据源依赖风险**
   - Financial API 故障时系统完全不可用
   - 无降级方案，用户体验差

3. **对比 stock-picker 项目**
   - stock-picker 使用免费 API（新浪财经、NewsNow、东方财富）
   - 从不限流，稳定运行
   - 本项目已有部分多源架构，但缺少关键免费源

### 1.2 设计目标

1. **彻底解决限流问题** - 添加免费数据源，Financial API 仅作兜底
2. **提升系统可用性** - 多源降级，单点故障不影响整体
3. **降低运营成本** - 优先使用免费源，减少付费 API 调用
4. **保持向后兼容** - 不修改现有 API 接口，无侵入式扩展
5. **覆盖全市场** - 美股、A股、港股全面支持

### 1.3 成功标准

- ✅ 回测运行 18 个分析师不再出现 429 错误
- ✅ 90% 以上的请求使用免费数据源
- ✅ 单个数据源故障不影响系统运行
- ✅ 现有测试用例全部通过

---

## 2. 整体架构

### 2.1 架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                    应用层 (src/tools/api.py)                     │
│                                                                   │
│  get_prices() / get_company_news() / get_financial_metrics()    │
│  • 接口保持不变，向后兼容                                         │
│  • 双层缓存：L1内存(5分钟) + L2 MySQL(智能TTL)                   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                市场路由器 (src/markets/router.py)                │
│                                                                   │
│  根据 ticker 格式自动路由:                                        │
│  • 600000.SH → CNStockAdapter                                   │
│  • 0700.HK   → HKStockAdapter                                   │
│  • AAPL      → USStockAdapter                                   │
│  • GC=F      → CommodityAdapter                                 │
└────────────────────────────┬────────────────────────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│  US Stock       │ │  CN Stock       │ │  HK Stock       │
│  Adapter        │ │  Adapter        │ │  Adapter        │
│                 │ │                 │ │                 │
│ 价格:           │ │ 价格:           │ │ 价格:           │
│ 1. YFinance    │ │ 1. Eastmoney   │ │ 1. Sina        │
│ 2. Financial   │ │ 2. Sina        │ │ 2. YFinance    │
│                 │ │ 3. AKShare     │ │ 3. AKShare     │
│ 新闻:           │ │                 │ │                 │
│ 1. NewsNow     │ │ 新闻:           │ │ 新闻:           │
│ 2. Financial   │ │ 1. NewsNow     │ │ 1. NewsNow     │
│                 │ │ 2. AKShare     │ │ 2. YFinance    │
│ 财务:           │ │                 │ │                 │
│ 1. YFinance    │ │ 财务:           │ │ 财务:           │
│ 2. Financial   │ │ 1. Eastmoney   │ │ 1. Sina        │
│                 │ │ 2. AKShare     │ │ 2. YFinance    │
└─────────────────┘ └─────────────────┘ └─────────────────┘
         │                   │                   │
         └───────────────────┼───────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              数据源层 (src/markets/sources/)                     │
│                                                                   │
│  🆕 新增免费源:                                                   │
│  • NewsNowSource      - 免费新闻聚合 (财联社/华尔街见闻/雪球)      │
│  • SinaFinanceSource  - 新浪财经 (CN/HK/US三市场通用)            │
│  • EastmoneySource    - 东方财富 (CN市场深度数据)                │
│                                                                   │
│  ✅ 现有免费源:                                                   │
│  • YFinanceSource     - 全球市场价格/基础财务                     │
│  • AKShareSource      - CN/HK市场数据                           │
│  • TushareSource      - CN市场专业数据                           │
│                                                                   │
│  💰 付费源(兜底):                                                 │
│  • Financial Datasets API - 完整数据，最后降级                   │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 核心设计原则

1. **渐进式降级** - 优先免费源，失败自动切换，付费源兜底
2. **无侵入扩展** - 基于现有架构扩展，不破坏现有功能
3. **独立可测** - 每个数据源独立实现 `DataSource` 接口
4. **智能缓存** - 历史数据永久缓存，当日数据短期缓存
5. **透明错误处理** - 单源失败不中断，记录日志继续降级

---

## 3. 新增数据源详细设计

### 3.1 NewsNowSource - 免费新闻聚合

#### 功能定位
从 NewsNow API 聚合多个财经新闻源，解决新闻接口限流问题。

#### 技术规格

```python
class NewsNowSource(DataSource):
    """
    NewsNow 免费新闻聚合源

    特点:
    - 完全免费，无 API key
    - 无限流风险
    - 支持多个专业财经新闻源
    """

    BASE_URL = "https://newsnow.busiyi.world/api/s"

    # 支持的新闻源
    SOURCES = {
        "cls": "财联社",           # 专业财经新闻
        "wallstreetcn": "华尔街见闻",  # 国际财经
        "xueqiu": "雪球",          # 投资社区热点
    }

    def __init__(self):
        super().__init__("NewsNow")
        self._cache = {}
        self._cache_ttl = 300  # 5分钟缓存

    def get_company_news(
        self,
        ticker: str,
        end_date: str,
        start_date: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        获取公司相关新闻

        流程:
        1. 检查内部缓存
        2. 从3个新闻源并发获取最新新闻
        3. 关键词过滤 (ticker + 公司名)
        4. 按时间排序
        5. 转换为标准 CompanyNews 格式

        Args:
            ticker: 股票代码
            end_date: 截止日期
            start_date: 开始日期(可选)
            limit: 最大返回数量

        Returns:
            新闻列表，每条包含: title, date, source, url, ticker
        """
```

#### 实现要点

1. **缓存策略**
   - 内存缓存 5 分钟，避免重复请求同一股票
   - 缓存 key: `{ticker}_{end_date}` (注: start_date 不包含在 key 中，因为新闻通常按 end_date 往前获取)
   - 不同日期范围会有独立缓存

2. **关键词过滤**
   ```python
   def _filter_by_ticker(self, news_list, ticker):
       # 基础关键词
       keywords = [ticker.upper()]

       # Phase 4 可扩展: 添加公司名映射以提高召回率
       # TICKER_TO_NAME = {"AAPL": "Apple", "MSFT": "Microsoft"}
       # keywords.append(TICKER_TO_NAME.get(ticker, ""))

       return [n for n in news_list
               if any(kw in n['title'].upper() for kw in keywords)]
   ```

   **注**:
   - Phase 1 仅使用 ticker 匹配（快速上线）
   - Phase 4 可添加公司名映射提高准确率

3. **错误处理**
   - **API 调用失败**: 返回空列表，记录错误日志
   - **关键词过滤零结果**: 返回空列表，记录 warning 日志（与 API 失败区分）
   - 单个源失败不影响其他源
   - 详细日志记录便于调试

#### 优势与限制

**优势**:
- ✅ 完全免费，无限流
- ✅ 多源聚合，覆盖面广
- ✅ 实时性好（分钟级更新）
- ✅ 零配置，无需 API key

**限制**:
- ⚠️ 仅有标题，无正文内容
- ⚠️ 需要关键词匹配，可能有误报/漏报
- ⚠️ 依赖第三方服务稳定性

**适用场景**:
- ✅ 分析师代理获取新闻情绪
- ✅ 新闻事件检测
- ❌ 不适合需要完整新闻正文的场景

---

### 3.2 SinaFinanceSource - 新浪财经

#### 功能定位
三市场通用的实时行情与历史K线数据源。

#### 技术规格

```python
class SinaFinanceSource(DataSource):
    """
    新浪财经数据源

    特点:
    - 支持 CN/HK/US 三个市场
    - 实时报价，延迟 < 1分钟
    - 稳定性高，很少限流
    """

    # API 端点
    QUOTE_API = "https://hq.sinajs.cn/list={symbol}"
    KLINE_API_CN = "https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketDataService.getKLineData"
    KLINE_API_HK = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"

    def get_prices(
        self,
        ticker: str,
        start_date: str,
        end_date: str
    ) -> List[Dict]:
        """
        获取历史价格数据

        流程:
        1. 检测市场 (CN/HK/US)
        2. 转换为新浪格式
        3. 调用对应市场 API
        4. 转换为标准 Price 格式

        返回格式:
        {
            "open": float,
            "close": float,
            "high": float,
            "low": float,
            "volume": int,
            "time": "2024-01-01T00:00:00Z"
        }
        """

    def get_financial_metrics(
        self,
        ticker: str,
        end_date: str
    ) -> Optional[Dict]:
        """
        获取基础财务指标

        注意: 新浪财经仅提供基础指标
        - 市值 (market_cap)
        - 市盈率 (pe_ratio)
        - 市净率 (pb_ratio)

        完整财务指标需使用 Eastmoney 或 Financial API
        """
```

#### Ticker 格式转换

```python
def _to_sina_symbol(self, ticker: str, market: str) -> str:
    """
    转换为新浪格式

    规则:
    - CN: 600000.SH → sh600000
    - CN: 000001.SZ → sz000001
    - HK: 0700.HK   → hk00700
    - US: AAPL      → gb_aapl
    """
    code = ticker.split('.')[0]

    if market == "CN":
        prefix = "sh" if ".SH" in ticker else "sz"
        return f"{prefix}{code}"
    elif market == "HK":
        return f"hk{code.zfill(5)}"
    else:  # US
        return f"gb_{code.lower()}"
```

#### 优势与限制

**优势**:
- ✅ 三市场通用，代码复用度高
- ✅ 实时数据，延迟低
- ✅ 稳定性好，限流少
- ✅ 无需 SDK，直接 HTTP 调用

**限制**:
- ⚠️ 财务指标有限（仅基础指标）
- ⚠️ 无新闻数据
- ⚠️ 美股数据相比 YFinance 略少

**适用场景**:
- ✅ 实时行情监控
- ✅ 历史K线回测
- ✅ 快速获取基础估值指标
- ❌ 不适合深度财务分析

---

### 3.3 EastmoneySource - 东方财富

#### 功能定位
CN 市场专用的深度数据源，提供最全面的 A股数据。

#### 技术规格

```python
class EastmoneySource(DataSource):
    """
    东方财富数据源

    特点:
    - CN 市场数据最全
    - 零依赖，纯 HTTP 调用
    - 支持完整财务报表
    """

    BASE_URL = "http://push2his.eastmoney.com/api/qt/stock/kline/get"

    def get_prices(
        self,
        ticker: str,
        start_date: str,
        end_date: str
    ) -> List[Dict]:
        """
        获取 A股历史价格

        参数配置:
        - klt: K线类型 (101=日K, 102=周K, 103=月K)
        - fqt: 复权方式 (0=不复权, 1=前复权, 2=后复权)
        """

        secid = self._to_eastmoney_secid(ticker)

        params = {
            'secid': secid,
            'fields1': 'f1,f2,f3,f4,f5,f6',
            'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58',
            'klt': '101',  # 日K
            'fqt': '1',    # 前复权
            'beg': start_date.replace('-', ''),
            'end': end_date.replace('-', ''),
        }

        response = requests.get(self.BASE_URL, params=params, timeout=10)
        return self._parse_klines(response.json())

    def get_financial_metrics(
        self,
        ticker: str,
        end_date: str
    ) -> Optional[Dict]:
        """
        获取完整财务指标

        包含:
        - 估值指标: PE, PB, PS, EV/EBITDA
        - 盈利能力: 毛利率, 净利率, ROE, ROA
        - 偿债能力: 资产负债率, 流动比率
        - 成长能力: 营收增长率, 净利润增长率
        """
```

#### Ticker 格式转换

```python
def _to_eastmoney_secid(self, ticker: str) -> str:
    """
    转换为东方财富格式

    规则:
    - 沪市: 600000.SH → 1.600000
    - 深市: 000001.SZ → 0.000001
    """
    code = ticker.split('.')[0]
    market_code = '1' if '.SH' in ticker else '0'
    return f"{market_code}.{code}"
```

#### 优势与限制

**优势**:
- ✅ CN 市场数据最全面
- ✅ 财务指标完整
- ✅ 零依赖，纯 HTTP 调用
- ✅ 支持资金流向、机构持仓等特色数据

**限制**:
- ⚠️ 仅支持 CN 市场
- ⚠️ 无新闻数据
- ⚠️ API 文档不完善（需参考社区实践）

**适用场景**:
- ✅ A股深度分析
- ✅ 财务报表分析
- ✅ 资金流向监控
- ❌ 不适合港股/美股

---

## 4. 降级策略设计

### 4.1 美股 (USStockAdapter)

```python
class USStockAdapter(MarketAdapter):
    """
    美股市场适配器

    降级策略:
    - 价格: YFinance → Financial API
    - 新闻: NewsNow → Financial API
    - 财务: YFinance → Financial API
    """

    def __init__(self):
        super().__init__()
        self.price_sources = [
            YFinanceSource(),
        ]
        self.news_sources = [
            NewsNowSource(),  # 🆕 新增
        ]
        self.metrics_sources = [
            YFinanceSource(),
        ]

    def get_company_news(self, ticker: str, end_date: str, limit: int) -> List[Dict]:
        """
        获取新闻 - 优先使用免费源

        降级链:
        1. NewsNow (免费，无限流)
        2. 返回空 → api.py 调用 Financial API 兜底
        """
        for source in self.news_sources:
            try:
                news = source.get_company_news(ticker, end_date, limit=limit)
                if news:
                    self.logger.info(f"✓ Got {len(news)} news from {source.name}")
                    return news
            except Exception as e:
                self.logger.warning(f"✗ {source.name} failed: {e}")
                continue

        # 所有免费源失败，返回空（由 api.py 调用 Financial API 兜底）
        self.logger.warning(f"All free news sources failed for {ticker}")
        return []
```

**关键点**:
- NewsNow 作为首选，解决 90% 的新闻请求
- Financial API 仅在免费源失败时调用
- 预期可减少 90% 的付费 API 调用

---

### 4.2 A股 (CNStockAdapter)

```python
class CNStockAdapter(MarketAdapter):
    """
    A股市场适配器

    降级策略:
    - 价格: Eastmoney → Sina → AKShare → Tushare
    - 新闻: NewsNow → AKShare
    - 财务: Eastmoney → AKShare → Tushare
    """

    def __init__(self):
        super().__init__()
        self.price_sources = [
            EastmoneySource(),    # 🆕 新增 - 首选
            SinaFinanceSource(),  # 🆕 新增 - 备用
            AKShareSource(),
            TushareSource(),
        ]
        self.news_sources = [
            NewsNowSource(),  # 🆕 新增 - 财联社
            AKShareSource(),
        ]
        self.metrics_sources = [
            EastmoneySource(),  # 🆕 新增 - 完整指标
            AKShareSource(),
            TushareSource(),
        ]

    def get_prices(self, ticker: str, start_date: str, end_date: str) -> List[Dict]:
        """
        获取价格 - 全免费源链

        降级链:
        1. Eastmoney (免费，最全)
        2. Sina Finance (免费，稳定)
        3. AKShare (免费，备用)
        4. Tushare (需token)
        """
        for source in self.price_sources:
            try:
                prices = source.get_prices(ticker, start_date, end_date)
                if prices:
                    self.logger.info(f"✓ Got {len(prices)} prices from {source.name}")
                    return prices
            except Exception as e:
                self.logger.warning(f"✗ {source.name} failed: {e}")
                continue

        self.logger.error(f"All price sources failed for {ticker}")
        return []
```

**关键点**:
- 完全摆脱对付费 API 的依赖
- 4 层免费源降级，可用性极高
- Eastmoney 优先，数据最全

---

### 4.3 港股 (HKStockAdapter)

```python
class HKStockAdapter(MarketAdapter):
    """
    港股市场适配器

    降级策略:
    - 价格: Sina → YFinance → AKShare
    - 新闻: NewsNow → YFinance
    - 财务: Sina → YFinance → AKShare
    """

    def __init__(self):
        super().__init__()
        self.price_sources = [
            SinaFinanceSource(),  # 🆕 新增 - 实时性好
            YFinanceSource(),
            AKShareSource(),
        ]
        self.news_sources = [
            NewsNowSource(),  # 🆕 新增 - 华尔街见闻
            YFinanceSource(),
        ]
        self.metrics_sources = [
            SinaFinanceSource(),  # 🆕 新增 - 基础指标
            YFinanceSource(),
            AKShareSource(),
        ]
```

**关键点**:
- 港股数据源相对较少
- Sina Finance 补充实时报价
- NewsNow 提供国际财经新闻

---

### 4.4 降级链对比表

| 市场 | 数据类型 | 降级链 | 预期免费源占比 |
|------|---------|--------|---------------|
| **美股** | 价格 | YFinance → Financial API | 95% |
| | 新闻 | NewsNow → Financial API | 90% |
| | 财务 | YFinance → Financial API | 80% |
| **A股** | 价格 | Eastmoney → Sina → AKShare → Tushare | 100% |
| | 新闻 | NewsNow → AKShare | 100% |
| | 财务 | Eastmoney → AKShare → Tushare | 100% |
| **港股** | 价格 | Sina → YFinance → AKShare | 100% |
| | 新闻 | NewsNow → YFinance | 95% |
| | 财务 | Sina → YFinance → AKShare | 100% |

**整体预期**:
- 免费源覆盖率: **95%+**
- Financial API 调用量: **降低 90%+**
- 系统可用性: **99%+** (多源冗余)

---

## 5. 数据流与缓存策略

### 5.1 完整数据流

```
用户请求: get_company_news("AAPL", "2024-03-15", limit=10)
    ↓
┌─────────────────────────────────────┐
│ src/tools/api.py                    │
│ 1. 检查 L1 内存缓存 (5分钟TTL)       │
│    → 命中: 直接返回                  │
│    → 未命中: 继续                    │
└────────────┬────────────────────────┘
             ↓
┌─────────────────────────────────────┐
│ src/data/mysql_cache.py             │
│ 2. 检查 L2 MySQL缓存 (智能TTL)       │
│    → 历史数据: 永久有效              │
│    → 当日数据: 1小时有效             │
│    → 命中: 返回并更新 L1             │
│    → 未命中: 继续                    │
└────────────┬────────────────────────┘
             ↓
┌─────────────────────────────────────┐
│ src/markets/router.py               │
│ 3. 路由到市场适配器                  │
│    "AAPL" → USStockAdapter          │
└────────────┬────────────────────────┘
             ↓
┌─────────────────────────────────────┐
│ src/markets/us_stock.py             │
│ 4. 按优先级尝试数据源                │
│    NewsNowSource:                   │
│      • 从财联社/华尔街见闻获取新闻    │
│      • 过滤 "AAPL" 关键词            │
│      • ✅ 成功返回 10 条新闻          │
└────────────┬────────────────────────┘
             ↓
┌─────────────────────────────────────┐
│ src/tools/api.py                    │
│ 5. 保存到缓存                        │
│    • 保存到 L2 MySQL (持久化)        │
│    • 保存到 L1 内存 (快速访问)       │
└────────────┬────────────────────────┘
             ↓
         返回给用户
```

### 5.2 缓存TTL策略

```python
# L1 内存缓存 (src/data/cache.py)
TTL_MEMORY = 300  # 5分钟

# L2 MySQL缓存 (src/data/mysql_cache.py)
# 表结构复用现有 src/data/mysql_models.py:
# - StockPrice: ticker, date, time, ohlcv, data_source, created_at, updated_at
# - CompanyNewsItem: ticker, date, title, content, url, source, data_source, created_at
# - FinancialMetric: ticker, report_period, period, metrics_json, data_source, created_at

def is_data_fresh(data_date: date) -> bool:
    """
    智能判断数据新鲜度

    规则:
    - 历史数据 (date < today): 永久有效
    - 当日数据 (date = today): 1小时内有效

    注: 依赖现有 MySQL 表的 updated_at 字段
    """
    today = date.today()
    if data_date < today:
        return True  # 历史数据永久有效

    # 当日数据检查更新时间
    return (datetime.now() - data.updated_at).seconds < 3600
```

**优势**:
- 历史数据永久缓存，回测时零 API 调用
- 当日数据定时刷新，保证实时性
- 双层缓存，L1 快速访问，L2 持久化
- 复用现有 MySQL 表结构，无需额外迁移

---

## 6. 错误处理与重试

### 6.1 数据源级错误处理

```python
class DataSource(ABC):
    """所有数据源的基类"""

    def get_prices(self, ticker, start_date, end_date, max_retries=3):
        """
        通用错误处理模板

        策略:
        1. 自动重试 3 次
        2. 指数退避 (2^n 秒)
        3. 失败返回空列表，不抛异常
        4. 详细日志记录
        """
        for attempt in range(max_retries):
            try:
                # 请求前延迟 (避免限流)
                if attempt > 0:
                    delay = 2 ** attempt
                    self.logger.info(f"[{self.name}] Retry {attempt+1}, waiting {delay}s")
                    time.sleep(delay)
                else:
                    # 首次请求也加小延迟
                    time.sleep(random.uniform(0.5, 1.5))

                # 发起请求
                data = self._fetch_data(ticker, start_date, end_date)

                # 验证数据
                if not data or len(data) == 0:
                    self.logger.warning(f"[{self.name}] No data for {ticker}")
                    return []

                # 成功返回
                self.logger.info(f"[{self.name}] ✓ Retrieved {len(data)} records")
                return data

            except requests.exceptions.Timeout:
                self.logger.warning(f"[{self.name}] Timeout on attempt {attempt+1}")
                if attempt == max_retries - 1:
                    return []

            except Exception as e:
                self.logger.warning(f"[{self.name}] Error: {e}")
                if attempt == max_retries - 1:
                    return []

        return []
```

### 6.2 适配器级降级处理

```python
class USStockAdapter(MarketAdapter):
    def get_company_news(self, ticker, end_date, limit):
        """
        降级链处理

        策略:
        1. 按优先级顺序尝试各源
        2. 第一个成功立即返回
        3. 单源失败记录日志但不中断
        4. 所有源失败返回空列表
        """
        for source in self.news_sources:
            try:
                news = source.get_company_news(ticker, end_date, limit=limit)
                if news:
                    self.logger.info(f"✓ {source.name} succeeded")
                    return news
                else:
                    self.logger.info(f"⚠ {source.name} returned no data")
            except Exception as e:
                self.logger.warning(f"✗ {source.name} failed: {e}")
                continue

        # 所有源失败
        self.logger.error(f"All news sources failed for {ticker}")
        return []
```

### 6.3 限流保护

```python
# 请求间隔控制
import time
import random

# 每次请求前添加随机延迟
time.sleep(random.uniform(0.5, 1.5))

# 重试时指数退避
for attempt in range(max_retries):
    if attempt > 0:
        delay = 2 ** attempt  # 2s, 4s, 8s...
        time.sleep(delay)
```

**关键点**:
- 主动延迟避免触发限流
- 失败不抛异常，保证降级链继续
- 详细日志便于问题排查

---

## 7. 测试策略

### 7.1 单元测试

每个数据源独立测试：

```python
# tests/markets/sources/test_newsnow_source.py
import pytest
from src.markets.sources.newsnow_source import NewsNowSource

class TestNewsNowSource:
    def test_get_company_news_success(self):
        """测试成功获取新闻"""
        source = NewsNowSource()
        news = source.get_company_news("AAPL", "2024-03-15", limit=10)

        assert isinstance(news, list)
        assert len(news) <= 10
        assert all('title' in n for n in news)
        assert all('date' in n for n in news)

    def test_get_company_news_empty_ticker(self):
        """测试无关股票返回空"""
        source = NewsNowSource()
        news = source.get_company_news("XXXXXX", "2024-03-15", limit=10)

        assert isinstance(news, list)
        assert len(news) == 0

    def test_cache_mechanism(self):
        """测试缓存机制"""
        source = NewsNowSource()

        # 首次请求
        news1 = source.get_company_news("AAPL", "2024-03-15", limit=10)

        # 第二次请求应该从缓存返回
        news2 = source.get_company_news("AAPL", "2024-03-15", limit=10)

        assert news1 == news2

# tests/markets/sources/test_sina_finance_source.py
class TestSinaFinanceSource:
    def test_get_prices_us_stock(self):
        """测试美股价格获取"""
        source = SinaFinanceSource()
        prices = source.get_prices("AAPL", "2024-01-01", "2024-01-31")

        assert len(prices) > 0
        assert all('open' in p for p in prices)
        assert all('close' in p for p in prices)

    def test_get_prices_cn_stock(self):
        """测试A股价格获取"""
        source = SinaFinanceSource()
        prices = source.get_prices("600000.SH", "2024-01-01", "2024-01-31")

        assert len(prices) > 0

    def test_get_prices_hk_stock(self):
        """测试港股价格获取"""
        source = SinaFinanceSource()
        prices = source.get_prices("0700.HK", "2024-01-01", "2024-01-31")

        assert len(prices) > 0

# tests/markets/sources/test_eastmoney_source.py
class TestEastmoneySource:
    def test_get_prices_shanghai(self):
        """测试沪市股票"""
        source = EastmoneySource()
        prices = source.get_prices("600000.SH", "2024-01-01", "2024-01-31")

        assert len(prices) > 0

    def test_get_prices_shenzhen(self):
        """测试深市股票"""
        source = EastmoneySource()
        prices = source.get_prices("000001.SZ", "2024-01-01", "2024-01-31")

        assert len(prices) > 0

    def test_get_financial_metrics(self):
        """测试财务指标"""
        source = EastmoneySource()
        metrics = source.get_financial_metrics("600000.SH", "2024-03-15")

        assert metrics is not None
        assert 'pe_ratio' in metrics
        assert 'market_cap' in metrics
```

### 7.2 集成测试

测试完整降级链：

```python
# tests/markets/test_us_stock_adapter.py
class TestUSStockAdapter:
    def test_news_fallback_chain(self):
        """测试新闻降级链"""
        adapter = USStockAdapter()

        # 应该优先使用 NewsNow
        news = adapter.get_company_news("AAPL", "2024-03-15", limit=10)

        assert len(news) > 0
        # 验证来自 NewsNow (检查 source 字段)

    def test_prices_fallback_chain(self):
        """测试价格降级链"""
        adapter = USStockAdapter()

        prices = adapter.get_prices("AAPL", "2024-01-01", "2024-01-31")

        assert len(prices) > 0

# tests/markets/test_cn_stock_adapter.py
class TestCNStockAdapter:
    def test_multi_source_fallback(self):
        """测试多源降级"""
        adapter = CNStockAdapter()

        # 应该优先使用 Eastmoney
        prices = adapter.get_prices("600000.SH", "2024-01-01", "2024-01-31")

        assert len(prices) > 0
```

### 7.3 端到端测试

```python
# tests/test_e2e_multi_source.py
class TestEndToEnd:
    def test_backtest_no_rate_limit(self):
        """测试回测不再触发限流"""
        # 运行完整回测流程
        # 验证没有 429 错误
        # 验证大部分请求使用免费源
        pass

    def test_cache_hit_rate(self):
        """测试缓存命中率"""
        # 运行两次相同的回测
        # 第二次应该大量命中缓存
        pass
```

### 7.4 手动验证脚本

```bash
# scripts/test_data_sources.sh

echo "=== 测试美股新闻 ==="
poetry run python -c "
from src.tools.api import get_company_news
news = get_company_news('AAPL', '2024-03-15', limit=5)
print(f'获取到 {len(news)} 条新闻')
for n in news[:3]:
    print(f'  - {n[\"title\"][:50]}...')
"

echo "=== 测试A股价格 ==="
poetry run python -c "
from src.tools.api import get_prices
prices = get_prices('600000.SH', '2024-01-01', '2024-01-31')
print(f'获取到 {len(prices)} 条价格数据')
print(f'  首条: {prices[0]}')
"

echo "=== 测试港股价格 ==="
poetry run python -c "
from src.tools.api import get_prices
prices = get_prices('0700.HK', '2024-01-01', '2024-01-31')
print(f'获取到 {len(prices)} 条价格数据')
"

echo "=== 测试缓存效果 ==="
poetry run python -c "
from src.data.cache import get_cache
cache = get_cache()
stats = cache.get_stats()
print(f'缓存统计: {stats}')
"
```

---

## 8. 实施计划

### 8.1 分阶段实施

#### Phase 1: NewsNowSource (优先级最高)
**目标**: 解决新闻接口限流问题

**任务**:
1. 实现 `NewsNowSource` 类
2. 更新 `USStockAdapter` 添加 NewsNow
3. 更新 `CNStockAdapter` 添加 NewsNow
4. 更新 `HKStockAdapter` 添加 NewsNow
5. 编写单元测试
6. 手动验证

**预期收益**: 减少 90% 的新闻 API 调用

**工作量**: 4-6 小时

---

#### Phase 2: SinaFinanceSource
**目标**: 提供三市场通用的价格数据源

**任务**:
1. 实现 `SinaFinanceSource` 类
2. 实现三市场 ticker 转换逻辑
3. 更新各市场适配器
4. 编写单元测试
5. 集成测试

**预期收益**: 港股/美股价格数据稳定性提升

**工作量**: 6-8 小时

---

#### Phase 3: EastmoneySource
**目标**: 提供 A股最全面的数据

**任务**:
1. 实现 `EastmoneySource` 类
2. 实现价格数据获取
3. 实现财务指标获取
4. 更新 `CNStockAdapter`
5. 编写测试

**预期收益**: A股数据完全免费化

**工作量**: 6-8 小时

---

#### Phase 4: 优化与监控
**目标**: 完善系统，添加监控

**任务**:
1. 添加数据源健康监控
2. 优化缓存策略
3. 性能测试
4. 文档完善

**工作量**: 4-6 小时

---

### 8.2 总工作量估算

| 阶段 | 任务 | 工作量 |
|-----|------|-------|
| Phase 1 | NewsNowSource | 4-6 小时 |
| Phase 2 | SinaFinanceSource | 6-8 小时 |
| Phase 3 | EastmoneySource | 6-8 小时 |
| Phase 4 | 优化与监控 | 4-6 小时 |
| **总计** | | **20-28 小时** |

**建议**: 分 2-3 天完成，每天完成 1-2 个 Phase

---

## 9. 风险与应对

### 9.1 潜在风险

| 风险 | 影响 | 概率 | 应对措施 |
|-----|------|------|---------|
| **免费 API 不稳定** | 数据获取失败 | 中 | 多源降级，付费 API 兜底 |
| **数据格式变化** | 解析失败 | 低 | 版本锁定 + 降级处理 |
| **新源限流** | 部分请求失败 | 低 | 请求间隔 + 重试机制 |
| **缓存失效** | 性能下降 | 低 | 双层缓存 + 智能TTL |
| **向后兼容性** | 现有功能受影响 | 低 | 充分测试 + 渐进式部署 |

### 9.2 回滚计划

如果新数据源出现问题：

```python
# 通过环境变量控制
# .env
ENABLE_NEWSNOW=false
ENABLE_SINA_FINANCE=false
ENABLE_EASTMONEY=false
```

```python
# 适配器中添加开关
class USStockAdapter:
    def __init__(self):
        self.news_sources = []

        # 可通过环境变量禁用
        if os.getenv("ENABLE_NEWSNOW", "true").lower() == "true":
            self.news_sources.append(NewsNowSource())
```

**回滚步骤**:
1. 设置环境变量禁用问题源
2. 重启服务
3. 系统自动降级到原有源
4. 无需代码修改

---

## 10. 监控与可观测性

### 10.1 关键指标

```python
# 数据源健康指标
class DataSourceMetrics:
    """
    数据源监控指标

    集成点: 在 DataSource 基类中收集
    - 每次请求前记录开始时间
    - 请求成功/失败后更新计数器
    - 在 adapters 中聚合各源指标
    """

    def __init__(self, source_name: str):
        self.source_name = source_name
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.total_latency = 0.0

    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests

    @property
    def avg_latency(self) -> float:
        """平均延迟 (秒)"""
        if self.successful_requests == 0:
            return 0.0
        return self.total_latency / self.successful_requests

# 在 DataSource 基类中集成
class DataSource(ABC):
    def __init__(self, name: str):
        self.name = name
        self.metrics = DataSourceMetrics(name)  # 添加指标收集

    def get_prices(self, ticker, start_date, end_date):
        start_time = time.time()
        self.metrics.total_requests += 1
        try:
            result = self._fetch_prices(ticker, start_date, end_date)
            self.metrics.successful_requests += 1
            self.metrics.total_latency += time.time() - start_time
            return result
        except Exception as e:
            self.metrics.failed_requests += 1
            raise
```

### 10.2 日志记录

```python
# 统一日志格式
logger.info(f"[{source.name}] ✓ Retrieved {len(data)} records in {elapsed:.2f}s")
logger.warning(f"[{source.name}] ⚠ No data for {ticker}")
logger.error(f"[{source.name}] ✗ Failed: {error}")
```

### 10.3 监控看板 (未来扩展)

建议指标：
- 各数据源调用量分布
- 各数据源成功率
- 缓存命中率
- API 成本趋势
- 平均响应时间

---

## 11. 成功标准验证

### 11.1 功能验证

- [ ] 所有新数据源单元测试通过
- [ ] 集成测试通过
- [ ] 现有测试用例全部通过
- [ ] 手动验证各市场数据获取正常

### 11.2 性能验证

- [ ] 回测 18 个分析师无 429 错误
- [ ] 免费源覆盖率 > 90%
- [ ] 缓存命中率 > 80%
- [ ] 响应时间无明显增加

### 11.3 稳定性验证

- [ ] 连续运行 24 小时无崩溃
- [ ] 单个数据源故障不影响整体
- [ ] 日志无异常错误

---

## 12. 附录

### 12.1 数据源 API 文档

#### NewsNow API
- **文档**: https://newsnow.busiyi.world
- **端点**: `/api/s?id={source_id}`
- **限流**: 无
- **认证**: 无需

#### 新浪财经 API
- **实时行情**: `https://hq.sinajs.cn/list={symbol}`
- **K线数据**: `https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketDataService.getKLineData`
- **限流**: 低
- **认证**: 无需

#### 东方财富 API
- **K线数据**: `http://push2his.eastmoney.com/api/qt/stock/kline/get`
- **限流**: 低
- **认证**: 无需

### 12.2 参考资料

- stock-picker 项目: `/Users/luobotao/.openclaw/workspace/stock-picker`
- 现有多市场架构: `src/markets/`
- 现有缓存系统: `src/data/cache.py`, `src/data/mysql_cache.py`

### 12.3 术语表

- **降级链**: 按优先级顺序尝试多个数据源的策略
- **双层缓存**: L1 内存缓存 + L2 MySQL 持久化缓存
- **智能TTL**: 根据数据类型动态调整缓存有效期
- **无侵入扩展**: 在不修改现有代码的前提下添加新功能

---

## 13. 总结

本设计方案通过添加三个免费数据源（NewsNow、Sina Finance、Eastmoney），在现有架构基础上构建了完整的多源降级体系。

**核心价值**:
1. ✅ **解决限流问题** - 免费源优先，预期减少 90% 付费 API 调用
2. ✅ **提升可用性** - 多源冗余，单点故障不影响系统
3. ✅ **降低成本** - 大幅减少付费 API 费用
4. ✅ **向后兼容** - 无侵入式扩展，现有功能不受影响
5. ✅ **易于维护** - 清晰的架构，独立的数据源实现

**实施建议**:
- 分 4 个阶段实施，优先完成 NewsNowSource（解决最紧急的新闻限流）
- 充分测试，渐进式部署
- 保留回滚能力，通过环境变量控制

**预期效果**:
- 免费源覆盖率: **95%+**
- Financial API 调用量: **降低 90%+**
- 系统可用性: **99%+**
- 回测运行: **无 429 错误**

---

**设计完成，等待用户审核**
