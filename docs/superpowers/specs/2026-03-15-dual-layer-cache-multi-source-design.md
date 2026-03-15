# 双层缓存 + 多源数据获取系统设计

**日期**: 2026-03-15
**版本**: 1.0
**状态**: 设计完成，待实现

---

## 1. 背景与目标

### 问题现状

当前项目遇到数据源限流问题：
- Financial Datasets API 频繁返回 429 错误
- 内存缓存（TTL 5分钟）无法持久化，重启后数据丢失
- 回测时需要重复获取相同的历史数据
- 无降级数据源，API失败后无备用方案

### 设计目标

1. **解决限流问题**：通过MySQL持久化缓存减少API调用
2. **提升响应速度**：主动预取数据，用户请求时直接读缓存
3. **增强可用性**：多源降级保证数据获取成功率
4. **降低成本**：历史数据永久缓存，避免重复付费API调用

### 参考借鉴

借鉴 `/Users/luobotao/.agents/skills/alphaear-stock/scripts/stock_tools.py` 的成功实践：
- 双层缓存（内存 + SQLite）
- 东方财富直接HTTP调用（零依赖）
- 代理自动检测和重试
- 多源降级链（akshare → 东方财富 → yfinance）

---

## 2. 系统架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│           后台数据预取服务 (Background Data Fetcher)          │
│                                                               │
│  ┌──────────────┐    ┌──────────────┐   ┌─────────────────┐│
│  │ 定时调度器    │───▶│ 股票池管理器  │──▶│ 多源数据获取器  ││
│  │ (Scheduler)  │    │ (Stock Pool) │   │ (Multi-Source)  ││
│  │              │    │              │   │                 ││
│  │ 每日: 历史数据│    │ • 配置的股票  │   │ 1. 东方财富HTTP ││
│  │ 每小时: 当日  │    │ • 最近使用    │   │ 2. Financial API││
│  │              │    │ • 用户关注    │   │ 3. YFinance     ││
│  └──────────────┘    └──────────────┘   │ 4. AKShare      ││
│                                          └────────┬────────┘│
└───────────────────────────────────────────────────┼─────────┘
                                                    │
                                         批量写入   │
                                                    ▼
┌─────────────────────────────────────────────────────────────┐
│                    MySQL 持久化缓存层                         │
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────┐ │
│  │ stock_prices │  │financial_    │  │ company_news      │ │
│  │              │  │metrics       │  │                   │ │
│  │ • ticker     │  │              │  │ • ticker          │ │
│  │ • date       │  │ • ticker     │  │ • date            │ │
│  │ • ohlcv      │  │ • period     │  │ • title/content   │ │
│  │ • source     │  │ • metrics    │  │ • source          │ │
│  │ • created_at │  │ • created_at │  │ • created_at      │ │
│  └──────────────┘  └──────────────┘  └───────────────────┘ │
│                                                               │
│  索引: (ticker, date), created_at                            │
└───────────────────────────┬───────────────────────────────────┘
                            │
                            │ 读取
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   应用层查询接口 (API Layer)                  │
│                                                               │
│  用户请求 ──▶ L1内存缓存 ──▶ L2 MySQL缓存 ──▶ 返回结果       │
│              (5分钟TTL)     (智能判断新鲜度)                  │
│                                                               │
│              缓存未命中 ──▶ 触发实时获取 (降级链)             │
│                           (仅用于未预取的股票)                │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 核心设计原则

1. **主动预取优先**：后台服务独立运行，不依赖用户请求
2. **被动补充**：仅在查询未预取的股票时触发实时获取
3. **无侵入性**：扩展现有代码，不破坏现有功能
4. **向后兼容**：现有API接口保持不变
5. **渐进式降级**：主源失败自动切换备用源
6. **智能缓存**：历史数据永久缓存，当日数据定时刷新

---

## 3. 数据库设计

### 3.1 表结构

#### 3.1.1 stock_prices（股票价格表）

```sql
CREATE TABLE stock_prices (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    date DATE NOT NULL,
    time DATETIME NOT NULL,
    open DECIMAL(20, 6),
    close DECIMAL(20, 6),
    high DECIMAL(20, 6),
    low DECIMAL(20, 6),
    volume BIGINT,
    data_source VARCHAR(50) NOT NULL,  -- 'financial_api', 'eastmoney', 'yfinance', 'akshare'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uk_ticker_time (ticker, time),
    INDEX idx_ticker_date (ticker, date),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

#### 3.1.2 financial_metrics（财务指标表）

```sql
CREATE TABLE financial_metrics (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    report_period DATE NOT NULL,
    period VARCHAR(20) NOT NULL,  -- 'ttm', 'quarterly', 'annual'
    market_cap DECIMAL(20, 2),
    pe_ratio DECIMAL(10, 4),
    pb_ratio DECIMAL(10, 4),
    ps_ratio DECIMAL(10, 4),
    revenue DECIMAL(20, 2),
    net_income DECIMAL(20, 2),
    metrics_json JSON,  -- 存储完整的财务指标
    data_source VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uk_ticker_period (ticker, report_period, period),
    INDEX idx_ticker (ticker),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

#### 3.1.3 company_news（公司新闻表）

```sql
CREATE TABLE company_news (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    date DATETIME NOT NULL,
    title TEXT,
    content TEXT,
    url VARCHAR(500),
    source VARCHAR(100),
    data_source VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_ticker_date (ticker, date),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

#### 3.1.4 insider_trades（内幕交易表）

```sql
CREATE TABLE insider_trades (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    filing_date DATE NOT NULL,
    trade_date DATE,
    insider_name VARCHAR(200),
    title VARCHAR(200),
    transaction_type VARCHAR(50),
    shares BIGINT,
    price DECIMAL(20, 6),
    value DECIMAL(20, 2),
    data_source VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_ticker_filing (ticker, filing_date),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

#### 3.1.5 stock_pool（股票池配置表）

```sql
CREATE TABLE stock_pool (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL UNIQUE,
    priority INT DEFAULT 1,  -- 优先级：1=高频, 2=中频, 3=低频
    is_active BOOLEAN DEFAULT TRUE,
    last_fetched_at TIMESTAMP NULL,
    fetch_frequency VARCHAR(20) DEFAULT 'hourly',  -- 'hourly', 'daily'
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_priority (priority, is_active),
    INDEX idx_last_fetched (last_fetched_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

#### 3.1.6 data_fetch_logs（数据获取日志表）

```sql
CREATE TABLE data_fetch_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    data_type VARCHAR(50) NOT NULL,  -- 'prices', 'metrics', 'news', 'trades'
    data_source VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,  -- 'success', 'failed', 'partial'
    records_count INT DEFAULT 0,
    error_message TEXT,
    fetch_duration_ms INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_ticker_type (ticker, data_type),
    INDEX idx_created_at (created_at),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 3.2 表设计说明

1. **data_source字段**：记录数据来源，用于质量追溯和调试
2. **唯一索引**：防止重复数据（ticker + time/period）
3. **JSON字段**：存储完整原始数据，便于扩展和回溯
4. **stock_pool表**：管理预取股票池，支持优先级和频率配置
5. **日志表**：监控数据获取状态，便于排查问题和性能优化

---

## 4. 多源数据获取器

### 4.1 数据源降级链

```python
class DataSourceChain:
    """
    多源降级链：按优先级尝试不同数据源

    降级顺序（根据市场类型智能选择）：
    - 美股: Financial API → YFinance → (无其他源)
    - A股/港股: 东方财富HTTP → AKShare → Financial API
    """

    sources = [
        EastMoneyDirectSource(),      # 优先级1: 无API Key，稳定
        FinancialDatasetsSource(),    # 优先级2: 官方API
        YFinanceSource(),             # 优先级3: 免费美股
        AKShareSource(),              # 优先级4: 备用
    ]
```

### 4.2 东方财富直接HTTP源（核心新增）

参考alphaear-stock脚本，实现零依赖的东方财富API调用：

```python
class EastMoneyDirectSource:
    """
    东方财富HTTP直接调用 - 零依赖降级方案

    特点：
    - 无需API Key
    - 国内网络直连
    - 支持A股、港股
    - 自动处理secid转换（600000 → 1.600000）

    API端点：
    - K线数据: https://push2his.eastmoney.com/api/qt/stock/kline/get
    - 股票列表: https://push2.eastmoney.com/api/qt/clist/get
    """

    KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    LIST_URL = "https://push2.eastmoney.com/api/qt/clist/get"
    UT = "fa5fd1943c7b386f172d6893dbfba10b"

    @staticmethod
    def _secid(ticker: str) -> str:
        """
        将纯数字ticker转为东方财富secid格式

        规则：
        - A股: 6开头 -> 1.{ticker}(上交所) | 其他 -> 0.{ticker}(深交所)
        - 港股: 5位数字 -> 116.{ticker}
        """
        if len(ticker) == 5:
            return f"116.{ticker}"
        if ticker.startswith(('6', '9')):
            return f"1.{ticker}"
        return f"0.{ticker}"

    @classmethod
    def fetch_prices(cls, ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        获取K线数据

        参数：
        - ticker: 纯数字股票代码（如 600519, 00700）
        - start_date: YYYYMMDD
        - end_date: YYYYMMDD

        返回：
        - DataFrame: 包含日期、开盘、收盘、最高、最低、成交量等字段
        """
        params = {
            'secid': cls._secid(ticker),
            'fields1': 'f1,f2,f3,f4,f5,f6',
            'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61',
            'klt': '101',   # 日K
            'fqt': '1',     # 前复权
            'beg': start_date,
            'end': end_date,
            'lmt': '1000',
            'ut': cls.UT,
        }

        # 使用代理降级机制
        response = fetch_with_proxy_fallback(
            lambda: requests.get(cls.KLINE_URL, params=params, timeout=10)
        )

        # 解析数据...
```

### 4.3 代理自动检测机制

```python
@contextmanager
def temporary_no_proxy():
    """
    临时禁用代理的上下文管理器

    特点：
    - 仅在请求上下文内禁用（with块内）
    - 自动恢复原始代理设置
    - 不会永久修改环境变量

    使用场景：
    - 检测到代理错误时自动重试
    - 国内API直连（东方财富、AKShare）
    """
    proxies = {
        k: os.environ.get(k)
        for k in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY']
    }

    # 临时删除代理环境变量
    for k in proxies:
        if k in os.environ:
            del os.environ[k]

    try:
        yield
    finally:
        # 恢复原始代理设置
        for k, v in proxies.items():
            if v is not None:
                os.environ[k] = v


def fetch_with_proxy_fallback(fetch_func, *args, **kwargs):
    """
    带代理降级的请求包装器

    流程：
    1. 尝试正常请求（带代理）
    2. 检测到代理错误 → 临时禁用代理重试
    3. 仍失败 → 抛出异常

    代理错误检测：
    - RequestException 包含 "Proxy" 或 "proxy" 关键字
    """
    try:
        return fetch_func(*args, **kwargs)
    except (RequestException, Exception) as e:
        if "Proxy" in str(e) or "proxy" in str(e):
            logger.warning(f"⚠️ Proxy error detected: {e}. Retrying without proxy...")
            with temporary_no_proxy():
                return fetch_func(*args, **kwargs)
        else:
            raise
```

### 4.4 智能路由逻辑

```python
class MultiSourceDataFetcher:
    """智能多源数据获取器"""

    def __init__(self):
        self.sources = {
            'eastmoney': EastMoneyDirectSource(),
            'financial_api': FinancialDatasetsSource(),
            'yfinance': YFinanceSource(),
            'akshare': AKShareSource(),
        }

    def get_prices(self, ticker: str, start_date: str, end_date: str) -> List[Price]:
        """
        智能路由获取价格数据

        流程：
        1. 判断市场类型（美股/A股/港股）
        2. 选择最优数据源顺序
        3. 逐个尝试，直到成功或全部失败
        4. 记录成功的数据源，下次优先使用
        """
        market_type = self._detect_market(ticker)
        source_order = self._get_source_order(market_type)

        for source_name in source_order:
            source = self.sources[source_name]
            try:
                logger.info(f"📡 Fetching {ticker} from {source_name}...")
                data = source.fetch_prices(ticker, start_date, end_date)

                if data:
                    logger.info(f"✅ Successfully fetched {len(data)} records from {source_name}")
                    self._log_success(ticker, source_name, len(data))
                    return data

            except Exception as e:
                logger.warning(f"⚠️ {source_name} failed for {ticker}: {e}")
                self._log_failure(ticker, source_name, str(e))
                continue

        raise AllSourcesFailedError(f"All data sources failed for {ticker}")

    def _detect_market(self, ticker: str) -> str:
        """
        检测市场类型

        规则：
        - 纯字母 → 美股
        - 包含点号 → 根据后缀判断（.SH/.SZ=A股, .HK=港股）
        - 5位数字 → 港股
        - 6位数字 → A股
        """
        if '.' in ticker:
            suffix = ticker.split('.')[-1].upper()
            if suffix in ['SH', 'SZ']:
                return 'a_share'
            elif suffix == 'HK':
                return 'hk_share'

        if ticker.isalpha():
            return 'us_stock'

        if len(ticker) == 5:
            return 'hk_share'

        if len(ticker) == 6:
            return 'a_share'

        return 'unknown'

    def _get_source_order(self, market_type: str) -> List[str]:
        """
        根据市场类型返回数据源优先级顺序

        美股: financial_api → yfinance
        A股/港股: eastmoney → akshare → financial_api
        """
        if market_type == 'us_stock':
            return ['financial_api', 'yfinance']
        elif market_type in ['a_share', 'hk_share']:
            return ['eastmoney', 'akshare', 'financial_api']
        else:
            return ['eastmoney', 'financial_api', 'yfinance', 'akshare']
```

---

## 5. 后台预取服务

### 5.1 调度器设计

```python
class DataFetchScheduler:
    """
    后台数据预取调度器

    任务：
    1. 每日凌晨2点：批量获取历史数据（T-1及之前）
    2. 每小时：更新当日数据（T日）
    3. 动态管理股票池（添加最近使用的股票）

    实现方式：
    - 使用APScheduler或Celery
    - 独立进程运行，不影响主应用
    """

    def __init__(self, mysql_cache: MySQLCache, fetcher: MultiSourceDataFetcher):
        self.cache = mysql_cache
        self.fetcher = fetcher
        self.scheduler = BackgroundScheduler()

    def start(self):
        """启动调度器"""
        # 每日凌晨2点：历史数据批量获取
        self.scheduler.add_job(
            self.daily_historical_fetch,
            'cron',
            hour=2,
            minute=0
        )

        # 每小时：当日数据更新
        self.scheduler.add_job(
            self.hourly_current_fetch,
            'cron',
            minute=5
        )

        # 每天更新股票池
        self.scheduler.add_job(
            self.update_stock_pool,
            'cron',
            hour=1,
            minute=0
        )

        self.scheduler.start()

    def daily_historical_fetch(self):
        """
        批量获取历史数据（一次性任务）

        策略：
        - 获取股票池中所有股票的历史数据
        - 日期范围：最近1年（或自定义）
        - 跳过已存在的数据（增量更新）
        """
        logger.info("🔄 Starting daily historical data fetch...")
        stock_pool = self.cache.get_active_stock_pool()

        for ticker in stock_pool:
            try:
                # 查询数据库中已有的最新日期
                latest_date = self.cache.get_latest_price_date(ticker)

                # 计算需要获取的日期范围
                start_date = latest_date + timedelta(days=1) if latest_date else (datetime.now() - timedelta(days=365))
                end_date = datetime.now() - timedelta(days=1)  # 昨天

                if start_date >= end_date:
                    logger.info(f"✓ {ticker} is up-to-date")
                    continue

                # 获取数据
                prices = self.fetcher.get_prices(ticker, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))

                # 保存到数据库
                self.cache.save_prices(ticker, prices)
                logger.info(f"✅ {ticker}: saved {len(prices)} records")

            except Exception as e:
                logger.error(f"❌ Failed to fetch historical data for {ticker}: {e}")

    def hourly_current_fetch(self):
        """
        更新当日数据（高频任务）

        策略：
        - 仅更新当日数据（T日）
        - 覆盖已存在的当日数据（更新最新价格）
        """
        logger.info("🔄 Starting hourly current data fetch...")
        stock_pool = self.cache.get_active_stock_pool()
        today = datetime.now().strftime('%Y-%m-%d')

        for ticker in stock_pool:
            try:
                prices = self.fetcher.get_prices(ticker, today, today)
                self.cache.save_prices(ticker, prices, overwrite_today=True)
                logger.info(f"✅ {ticker}: updated current data")
            except Exception as e:
                logger.error(f"❌ Failed to fetch current data for {ticker}: {e}")

    def update_stock_pool(self):
        """
        动态更新股票池

        策略：
        - 添加最近7天查询过的股票
        - 保留配置的核心股票
        - 清理30天未使用的股票
        """
        logger.info("🔄 Updating stock pool...")
        # 实现逻辑...
```

### 5.2 股票池管理

```python
class StockPoolManager:
    """股票池管理器"""

    def __init__(self, mysql_cache: MySQLCache):
        self.cache = mysql_cache

    def initialize_default_pool(self):
        """
        初始化默认股票池

        包含：
        - 常用美股：AAPL, MSFT, GOOGL, NVDA, TSLA, AMZN, META
        - 常用A股：600519.SH(茅台), 000001.SZ(平安), 600036.SH(招行)
        - 常用港股：00700.HK(腾讯), 09988.HK(阿里)
        """
        default_stocks = [
            # 美股
            {'ticker': 'AAPL', 'priority': 1, 'fetch_frequency': 'hourly'},
            {'ticker': 'MSFT', 'priority': 1, 'fetch_frequency': 'hourly'},
            {'ticker': 'GOOGL', 'priority': 1, 'fetch_frequency': 'hourly'},
            {'ticker': 'NVDA', 'priority': 1, 'fetch_frequency': 'hourly'},
            {'ticker': 'TSLA', 'priority': 2, 'fetch_frequency': 'daily'},
            # A股
            {'ticker': '600519.SH', 'priority': 2, 'fetch_frequency': 'daily'},
            {'ticker': '000001.SZ', 'priority': 2, 'fetch_frequency': 'daily'},
            # 港股
            {'ticker': '00700.HK', 'priority': 2, 'fetch_frequency': 'daily'},
        ]

        for stock in default_stocks:
            self.cache.add_to_stock_pool(**stock)

    def add_recently_used_stocks(self, days: int = 7):
        """
        添加最近使用的股票到股票池

        策略：
        - 查询最近N天的查询日志
        - 自动添加到股票池（低优先级）
        """
        # 实现逻辑...

    def cleanup_unused_stocks(self, days: int = 30):
        """
        清理长期未使用的股票

        策略：
        - 保留priority=1的核心股票
        - 删除30天未查询的低优先级股票
        """
        # 实现逻辑...
```

---

## 6. 缓存查询流程

### 6.1 双层缓存查询逻辑

```python
class CachedDataAPI:
    """带缓存的数据API"""

    def __init__(self):
        self.memory_cache = get_cache()  # 现有的内存缓存
        self.mysql_cache = MySQLCache()   # 新增的MySQL缓存
        self.fetcher = MultiSourceDataFetcher()

    def get_prices(self, ticker: str, start_date: str, end_date: str) -> List[Price]:
        """
        双层缓存查询

        流程：
        1. L1内存缓存（5分钟TTL）→ 命中返回
        2. L2 MySQL缓存 → 检查数据新鲜度
           - 历史数据（date < 今天）：直接返回
           - 当日数据（date = 今天）：检查updated_at是否1小时内
        3. 缓存未命中/过期 → 触发实时获取（多源降级）
        4. 保存到MySQL + 内存缓存
        """
        cache_key = f"{ticker}_{start_date}_{end_date}"

        # L1: 内存缓存
        if cached_data := self.memory_cache.get_prices(cache_key):
            logger.debug(f"✓ L1 cache hit: {cache_key}")
            return [Price(**price) for price in cached_data]

        # L2: MySQL缓存
        mysql_data = self.mysql_cache.get_prices(ticker, start_date, end_date)
        if mysql_data and self._is_data_fresh(mysql_data, end_date):
            logger.debug(f"✓ L2 cache hit: {cache_key}")
            # 回填到L1缓存
            self.memory_cache.set_prices(cache_key, [p.model_dump() for p in mysql_data])
            return mysql_data

        # 缓存未命中：实时获取
        logger.info(f"⚠️ Cache miss: {cache_key}, fetching from network...")
        prices = self.fetcher.get_prices(ticker, start_date, end_date)

        # 保存到两层缓存
        self.mysql_cache.save_prices(ticker, prices)
        self.memory_cache.set_prices(cache_key, [p.model_dump() for p in prices])

        return prices

    def _is_data_fresh(self, data: List[Price], end_date: str) -> bool:
        """
        判断数据是否新鲜

        规则：
        - 历史数据（date < 今天）：永久有效
        - 当日数据（date = 今天）：1小时内有效
        """
        today = datetime.now().date()
        request_end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

        # 如果请求的是历史数据，直接返回True
        if request_end_date < today:
            return True

        # 如果请求包含当日数据，检查最新数据的更新时间
        if request_end_date == today:
            latest_record = max(data, key=lambda x: x.time)
            if hasattr(latest_record, 'updated_at'):
                time_diff = datetime.now() - latest_record.updated_at
                return time_diff.total_seconds() < 3600  # 1小时

        return True
```

### 6.2 MySQL缓存管理器

```python
class MySQLCache:
    """MySQL持久化缓存管理器"""

    def __init__(self):
        self.engine = create_engine(DATABASE_URL)
        self.Session = sessionmaker(bind=self.engine)

    def get_prices(self, ticker: str, start_date: str, end_date: str) -> List[Price]:
        """从MySQL获取价格数据"""
        session = self.Session()
        try:
            query = session.query(StockPriceModel).filter(
                StockPriceModel.ticker == ticker,
                StockPriceModel.date >= start_date,
                StockPriceModel.date <= end_date
            ).order_by(StockPriceModel.time)

            results = query.all()
            return [self._model_to_price(r) for r in results]
        finally:
            session.close()

    def save_prices(self, ticker: str, prices: List[Price], overwrite_today: bool = False):
        """
        保存价格数据到MySQL

        参数：
        - overwrite_today: 是否覆盖当日数据（用于更新最新价格）
        """
        session = self.Session()
        try:
            for price in prices:
                # 检查是否已存在
                existing = session.query(StockPriceModel).filter(
                    StockPriceModel.ticker == ticker,
                    StockPriceModel.time == price.time
                ).first()

                if existing:
                    if overwrite_today and price.time.date() == datetime.now().date():
                        # 更新当日数据
                        existing.open = price.open
                        existing.close = price.close
                        existing.high = price.high
                        existing.low = price.low
                        existing.volume = price.volume
                        existing.updated_at = datetime.now()
                else:
                    # 插入新数据
                    model = StockPriceModel(
                        ticker=ticker,
                        date=price.time.date(),
                        time=price.time,
                        open=price.open,
                        close=price.close,
                        high=price.high,
                        low=price.low,
                        volume=price.volume,
                        data_source=price.source if hasattr(price, 'source') else 'unknown'
                    )
                    session.add(model)

            session.commit()
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()

    def get_latest_price_date(self, ticker: str) -> Optional[date]:
        """获取某股票在数据库中的最新日期"""
        session = self.Session()
        try:
            result = session.query(func.max(StockPriceModel.date)).filter(
                StockPriceModel.ticker == ticker
            ).scalar()
            return result
        finally:
            session.close()

    def get_active_stock_pool(self) -> List[str]:
        """获取活跃股票池"""
        session = self.Session()
        try:
            query = session.query(StockPoolModel.ticker).filter(
                StockPoolModel.is_active == True
            ).order_by(StockPoolModel.priority)

            return [row.ticker for row in query.all()]
        finally:
            session.close()
```

---

## 7. 实现分阶段

### 第一阶段：MySQL缓存层（核心）✅ 优先级最高

**目标**：解决限流问题，实现数据持久化

**任务**：
1. 创建数据库表（Alembic迁移）
2. 实现MySQLCache类
3. 修改api.py，集成双层缓存
4. 测试缓存读写和数据新鲜度判断

**交付物**：
- `app/backend/alembic/versions/xxx_add_cache_tables.py`
- `src/data/mysql_cache.py`
- 修改后的 `src/tools/api.py`
- 单元测试

**预期效果**：
- 历史数据永久缓存，减少90%以上的API调用
- 回测速度提升10倍以上

---

### 第二阶段：东方财富降级源 ✅ 优先级高

**目标**：实现多源降级，提升数据获取成功率

**任务**：
1. 实现EastMoneyDirectSource类
2. 实现代理检测机制（temporary_no_proxy）
3. 实现MultiSourceDataFetcher智能路由
4. 集成到api.py的数据获取流程

**交付物**：
- `src/data/sources/eastmoney_direct.py`
- `src/data/sources/multi_source_fetcher.py`
- `src/data/sources/proxy_utils.py`
- 修改后的 `src/tools/api.py`

**预期效果**：
- 主API限流时自动切换到东方财富
- A股/港股数据获取成功率接近100%

---

### 第三阶段：后台预取服务 ⚠️ 优先级中

**目标**：实现主动预取，提升用户体验

**任务**：
1. 实现DataFetchScheduler调度器
2. 实现StockPoolManager股票池管理
3. 配置定时任务（每日、每小时）
4. 添加监控和日志

**交付物**：
- `src/data/scheduler.py`
- `src/data/stock_pool_manager.py`
- 独立运行脚本 `scripts/start_scheduler.py`
- 监控仪表盘（可选）

**预期效果**：
- 用户请求时直接读缓存，零延迟
- 数据始终保持最新

---

### 第四阶段：监控和优化 📊 优先级低

**目标**：监控系统运行状态，持续优化

**任务**：
1. 实现数据获取日志记录
2. 缓存命中率统计
3. 数据源成功率监控
4. 性能优化（查询优化、批量操作）

**交付物**：
- 日志分析脚本
- 监控指标API
- 性能优化报告

**预期效果**：
- 可视化监控数据获取状态
- 持续优化缓存策略

---

## 8. 技术细节

### 8.1 数据库连接配置

```python
# app/backend/database/connection.py (复用现有)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.getenv('DATABASE_URL', 'mysql+pymysql://user:pass@localhost/ai_hedge_fund')

engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # 自动检测连接是否有效
    pool_recycle=3600,   # 1小时回收连接
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
```

### 8.2 Alembic迁移脚本

```bash
# 创建迁移
cd app/backend
poetry run alembic revision --autogenerate -m "add_cache_tables"

# 应用迁移
poetry run alembic upgrade head
```

### 8.3 环境变量配置

```bash
# .env
DATABASE_URL=mysql+pymysql://root:password@localhost:3306/ai_hedge_fund

# 数据源配置
FINANCIAL_DATASETS_API_KEY=your_key_here

# 调度器配置
SCHEDULER_ENABLED=true
DAILY_FETCH_HOUR=2
HOURLY_FETCH_MINUTE=5
```

---

## 9. 测试策略

### 9.1 单元测试

```python
# tests/data/test_mysql_cache.py
def test_save_and_get_prices():
    """测试价格数据的保存和读取"""

def test_data_freshness():
    """测试数据新鲜度判断"""

def test_overwrite_today():
    """测试当日数据覆盖"""

# tests/data/test_multi_source_fetcher.py
def test_source_fallback():
    """测试数据源降级"""

def test_market_detection():
    """测试市场类型识别"""

def test_proxy_fallback():
    """测试代理降级"""
```

### 9.2 集成测试

```python
# tests/integration/test_cached_api.py
def test_full_cache_flow():
    """测试完整的缓存流程（L1 → L2 → 网络）"""

def test_historical_data_caching():
    """测试历史数据永久缓存"""

def test_current_data_refresh():
    """测试当日数据定时刷新"""
```

### 9.3 性能测试

```python
# tests/performance/test_cache_performance.py
def test_cache_hit_rate():
    """测试缓存命中率（目标>90%）"""

def test_query_speed():
    """测试查询速度（目标<100ms）"""

def test_backtest_speed():
    """测试回测速度提升（目标10x）"""
```

---

## 10. 风险与注意事项

### 10.1 数据一致性

**风险**：双层缓存可能导致数据不一致

**缓解措施**：
- L1缓存TTL设置为5分钟，快速过期
- L2缓存为权威数据源
- 当日数据定时刷新

### 10.2 数据库性能

**风险**：大量数据写入可能影响数据库性能

**缓解措施**：
- 使用批量插入（bulk_insert）
- 合理设置索引
- 定期清理过期日志数据

### 10.3 调度器稳定性

**风险**：调度器进程崩溃导致数据不更新

**缓解措施**：
- 使用进程监控（systemd/supervisor）
- 添加健康检查接口
- 失败重试机制

### 10.4 数据源变更

**风险**：外部API接口变更导致获取失败

**缓解措施**：
- 多源降级保证可用性
- 版本锁定依赖（yfinance, akshare）
- 监控数据源成功率

---

## 11. 未来扩展

### 11.1 分布式缓存

使用Redis作为L1缓存，支持多实例共享：
```
L1: Redis (分布式) → L2: MySQL (持久化) → L3: 网络获取
```

### 11.2 实时数据流

集成WebSocket实时数据源（如Polygon.io）：
- 盘中实时价格推送
- 减少轮询请求

### 11.3 数据质量监控

- 数据异常检测（价格突变、缺失值）
- 数据源质量评分
- 自动切换到高质量数据源

### 11.4 智能预取

- 基于用户查询模式的预测性预取
- 机器学习预测热门股票
- 动态调整预取频率

---

## 12. 总结

本设计方案通过**双层缓存 + 多源降级 + 主动预取**的架构，解决了当前项目的限流问题，并为未来扩展奠定了基础。

### 核心优势

1. **性能提升**：双层缓存，历史数据零延迟
2. **成本降低**：减少90%以上的付费API调用
3. **可用性高**：多源降级，成功率接近100%
4. **易于扩展**：模块化设计，便于添加新数据源
5. **无侵入性**：扩展现有代码，向后兼容

### 实施建议

1. **优先实现第一阶段**：MySQL缓存层是核心，可快速解决限流问题
2. **渐进式上线**：先在开发环境验证，再部署到生产
3. **监控先行**：实施前建立监控指标，便于评估效果
4. **文档同步**：更新README和TROUBLESHOOTING文档

---

**设计完成日期**: 2026-03-15
**设计者**: Claude Code
**审核状态**: 待审核
