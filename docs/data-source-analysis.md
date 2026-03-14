# 数据源架构分析与改进建议

## stock-picker 项目数据源优点分析

### 1. 多数据源聚合架构 ⭐⭐⭐⭐⭐

**优点：**
- **多数据源支持**：集成了新浪财经、东方财富、AKShare、YFinance、Stooq等5个数据源
- **自动降级**：主数据源失败时自动切换到备用数据源
- **统一接口**：`MultiSourceDataFetcher` 提供统一的API，屏蔽底层数据源差异

**实现亮点：**
```python
class MultiSourceDataFetcher:
    def __init__(self):
        self.sina = SinaFinanceSource()
        self.yfinance = YFinanceSource()
        self.stooq = StooqSource()
        self.eastmoney = EastMoneySource()
        self.akshare = AKShareSource()
        self.validator = DataValidator()  # 数据验证器
```

**借鉴建议：**
- ai-hedge-fund 当前只依赖单一数据源（financialdatasets.ai），存在单点故障风险
- 建议为每个市场（美股、A股、港股）配置2-3个备用数据源

---

### 2. 数据交叉验证机制 ⭐⭐⭐⭐⭐

**核心价值：**
- 解决多数据源数据不一致问题
- 提高数据准确性和可靠性
- 自动识别异常数据源

**DataValidator 核心功能：**

#### 2.1 价格验证（加权平均）
```python
def validate_price(self, prices: Dict[str, float]) -> Dict:
    # 计算统计值
    mean_price = statistics.mean(values)
    max_deviation = max(abs(v - mean_price) / mean_price for v in values)

    # 检查偏差（阈值2%）
    if max_deviation > self.price_threshold:
        # 标记异常数据源
        anomalies = [...]

    # 加权平均（基于数据源可信度）
    weighted_sum = 0
    for source, price in prices.items():
        weight = self.source_weights.get(source, 0.5)
        weighted_sum += price * weight

    final_price = weighted_sum / weight_total
```

**数据源权重配置：**
```python
self.source_weights = {
    'sina': 1.0,         # 新浪：国内最可靠
    'eastmoney': 0.9,    # 东方财富：A股可靠
    'tushare': 0.85,     # Tushare：专业但需积分
    'yfinance': 0.8,     # yfinance：美股可靠，港股稍差
    'stooq': 0.6,        # stooq：数据延迟，权重低
}
```

#### 2.2 成交量验证（中位数）
```python
def validate_volume(self, volumes: Dict[str, float]) -> Dict:
    # 成交量波动大，使用中位数更稳定
    median_volume = statistics.median(values)

    # 检查偏差（阈值10%）
    max_deviation = max(abs(v - median_volume) / median_volume for v in values)
```

#### 2.3 置信度评分
```python
# 置信度计算：数据源越多、偏差越小，置信度越高
confidence = min(0.95, 0.8 + len(prices) * 0.05 - max_deviation * 10)
```

**借鉴建议：**
- 在 `src/data/validation.py` 中实现类似的数据验证器
- 为 MarketRouter 添加多数据源支持和交叉验证
- 在缓存数据时附加置信度和数据源信息

---

### 3. 分层缓存机制 ⭐⭐⭐⭐

**优点：**
- **多级缓存**：数据源级缓存 + 全局缓存
- **TTL管理**：灵活的过期时间控制
- **缓存统计**：命中率、miss率监控

**实现细节：**

#### 3.1 数据源级缓存（60秒）
```python
class SinaFinanceSource:
    def __init__(self):
        self.cache = {}
        self.cache_time = {}
        self.cache_ttl = 60  # 60秒短期缓存

    def get_stock_info(self, symbol: str):
        cache_key = f"info_{symbol}"
        if cache_key in self.cache:
            if (datetime.now() - self.cache_time[cache_key]).seconds < self.cache_ttl:
                return self.cache[cache_key]
```

#### 3.2 全局缓存（5分钟）
```python
class Cache:
    def __init__(self, ttl: int = 300):  # 5分钟默认TTL
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = Lock()  # 线程安全
        self.hits = 0
        self.misses = 0

    def get_stats(self) -> Dict:
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        return {
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': f"{hit_rate:.2f}%",
            'size': len(self._cache)
        }
```

#### 3.3 缓存装饰器
```python
@cached(ttl=300, key_prefix="stock_")
def expensive_function(ticker: str):
    # 自动缓存结果
    return fetch_data(ticker)
```

**当前 ai-hedge-fund 缓存对比：**
```python
# 当前实现：简单的字典缓存，无TTL，无统计
class DataCache:
    def __init__(self):
        self._prices_cache = {}
        self._metrics_cache = {}
```

**改进建议：**
- 添加 TTL 管理和自动过期清理
- 添加缓存统计和监控
- 实现缓存装饰器简化使用
- 考虑使用 Redis 作为分布式缓存（生产环境）

---

### 4. 市场差异化处理 ⭐⭐⭐⭐

**优点：**
- 针对不同市场特点选择最佳数据源
- 自动处理市场代码转换
- 考虑汇率转换（港股、美股）

**市场优先级策略：**
```python
def get_stock_info(self, symbol: str):
    market = self._detect_market(symbol)
    results = {}

    # A股/港股首选新浪和东方财富
    if market in ['CN', 'HK']:
        results['sina'] = self.sina.get_stock_info(symbol)
        results['eastmoney'] = self.eastmoney.get_stock_info(symbol)

    # 美股首选 yfinance
    if self.yfinance:
        results['yfinance'] = self.yfinance.get_stock_info(symbol)

    # 优先级排序
    priority = ['eastmoney', 'sina', 'akshare', 'yfinance']
    for source in priority:
        if source in results:
            return results[source]
```

**汇率处理：**
```python
class EastMoneySource:
    def __init__(self):
        self.hkd_to_cny = 0.92  # 港币转人民币
        self.usd_to_cny = 7.2   # 美元转人民币

    def _get_hk_stock_info(self, symbol: str):
        market_cap = (d.get('f116', 0) or 0) * self.hkd_to_cny
```

**借鉴建议：**
- 当前 ai-hedge-fund 的市场适配器缺少数据源优先级配置
- 建议在每个 MarketAdapter 中配置主/备数据源列表
- 添加汇率转换支持（统一为美元或人民币）

---

### 5. 配置化设计 ⭐⭐⭐⭐

**优点：**
- 集中管理所有配置参数
- 支持环境变量覆盖
- 使用 dataclass 提供类型提示

**配置结构：**
```python
@dataclass
class DatabaseConfig:
    host: str = os.getenv("DB_HOST", "localhost")
    port: int = int(os.getenv("DB_PORT", "3306"))

@dataclass
class LLMConfig:
    api_key: str = os.getenv("LLM_API_KEY")
    base_url: str = os.getenv("LLM_BASE_URL")
    timeout: int = int(os.getenv("LLM_TIMEOUT", "120"))

@dataclass
class AnalysisConfig:
    # 权重配置
    TECHNICAL_WEIGHT: float = 0.40
    FUNDAMENTAL_WEIGHT: float = 0.25

    # 决策阈值
    BUY_THRESHOLD: float = 2.5

    # 缓存配置
    CACHE_TTL_SECONDS: int = 300

# 全局配置实例
db_config = DatabaseConfig()
llm_config = LLMConfig()
analysis_config = AnalysisConfig()
```

**当前 ai-hedge-fund 对比：**
- 配置分散在多个文件中（.env, settings, 硬编码）
- 缺少统一的配置管理类

**改进建议：**
- 创建 `src/config/settings.py` 集中管理配置
- 使用 pydantic-settings 进行配置验证
- 支持多环境配置（dev/test/prod）

---

## 当前 ai-hedge-fund 架构优点

### 1. 清晰的适配器模式 ⭐⭐⭐⭐⭐

**优点：**
```python
class MarketAdapter(ABC):
    @abstractmethod
    def supports_ticker(self, ticker: str) -> bool: ...

    @abstractmethod
    def get_prices(self, ticker: str, start_date: str, end_date: str) -> List[Dict]: ...

    @abstractmethod
    def get_company_news(self, ticker: str, end_date: str, limit: int) -> List[Dict]: ...
```

- 定义清晰的抽象接口
- 强制所有市场实现统一方法
- 易于扩展新市场

### 2. 自动路由机制 ⭐⭐⭐⭐

**优点：**
```python
class MarketRouter:
    def route(self, ticker: str) -> MarketAdapter:
        for adapter in self.adapters:
            if adapter.supports_ticker(ticker):
                return adapter
        raise ValueError(f"未找到支持该ticker的适配器: {ticker}")
```

- 自动识别ticker类型
- 透明路由到对应适配器
- 统一的错误处理

---

## 综合改进建议

### 优先级 P0（关键）

1. **添加多数据源支持和自动降级**
   ```python
   # src/markets/cn_stock.py
   class CNStockAdapter(MarketAdapter):
       def __init__(self):
           self.sources = [
               AKShareSource(),      # 主数据源
               EastMoneySource(),    # 备用1
               SinaSource(),         # 备用2
           ]

       def get_prices(self, ticker, start_date, end_date):
           for source in self.sources:
               try:
                   return source.get_prices(ticker, start_date, end_date)
               except Exception as e:
                   logger.warning(f"{source} failed: {e}")
           raise Exception("All sources failed")
   ```

2. **实现数据交叉验证**
   ```python
   # src/data/validation.py
   class DataValidator:
       def cross_validate(self, data_sources: Dict[str, Dict]) -> Dict:
           # 价格验证（加权平均）
           # 成交量验证（中位数）
           # 置信度评分
           pass
   ```

3. **增强缓存机制**
   ```python
   # src/data/cache.py
   class DataCache:
       def __init__(self, ttl: int = 300):
           self._cache = {}
           self._ttl = ttl
           self._lock = Lock()
           self.stats = CacheStats()  # 统计信息

       def cleanup_expired(self): ...
       def get_stats(self) -> Dict: ...
   ```

### 优先级 P1（重要）

4. **集中配置管理**
   ```python
   # src/config/settings.py
   from pydantic_settings import BaseSettings

   class Settings(BaseSettings):
       # 数据源配置
       data_source_weights: Dict[str, float] = {
           'akshare': 1.0,
           'eastmoney': 0.9,
           'sina': 0.8,
       }

       # 缓存配置
       cache_ttl: int = 300

       # 验证阈值
       price_deviation_threshold: float = 0.02
       volume_deviation_threshold: float = 0.10
   ```

5. **数据源健康检查**
   ```python
   # src/data/health_check.py
   class DataSourceHealthChecker:
       def check_source(self, source: DataSource) -> HealthStatus:
           # 检查响应时间、成功率、数据质量
           pass

       def get_best_source(self, sources: List[DataSource]) -> DataSource:
           # 返回最健康的数据源
           pass
   ```

### 优先级 P2（优化）

6. **监控和告警**
   ```python
   # src/monitoring/metrics.py
   class DataSourceMetrics:
       def record_request(self, source: str, success: bool, latency: float): ...
       def get_metrics(self) -> Dict: ...
   ```

7. **分布式缓存（生产环境）**
   ```python
   # src/data/redis_cache.py
   class RedisCache(DataCache):
       def __init__(self, redis_url: str): ...
   ```

---

## 实施路线图

### Phase 1: 基础增强（1-2周）
- [ ] 为每个市场适配器添加2-3个备用数据源
- [ ] 实现基础的数据验证器（价格、成交量验证）
- [ ] 增强缓存机制（TTL、统计、清理）

### Phase 2: 质量提升（2-3周）
- [ ] 实现完整的交叉验证逻辑
- [ ] 添加数据源权重和优先级配置
- [ ] 集中配置管理

### Phase 3: 生产优化（3-4周）
- [ ] 数据源健康检查和自动切换
- [ ] 监控和告警系统
- [ ] 分布式缓存（可选）

---

## 关键代码示例

### 1. 多数据源适配器（参考实现）

```python
# src/markets/sources/base.py
class DataSource(ABC):
    """数据源基类"""
    @abstractmethod
    def get_prices(self, ticker: str, start_date: str, end_date: str) -> List[Dict]: ...

# src/markets/sources/akshare.py
class AKShareSource(DataSource):
    def get_prices(self, ticker: str, start_date: str, end_date: str) -> List[Dict]:
        import akshare as ak
        df = ak.stock_zh_a_hist(symbol=ticker, period="daily", adjust="qfq")
        return df.to_dict('records')

# src/markets/cn_stock.py
class CNStockAdapter(MarketAdapter):
    def __init__(self):
        self.sources = [
            AKShareSource(),
            EastMoneySource(),
            SinaSource(),
        ]
        self.validator = DataValidator()

    def get_prices(self, ticker: str, start_date: str, end_date: str) -> List[Dict]:
        results = {}

        # 尝试所有数据源
        for source in self.sources:
            try:
                data = source.get_prices(ticker, start_date, end_date)
                if data:
                    results[source.__class__.__name__] = data
            except Exception as e:
                logger.warning(f"{source.__class__.__name__} failed: {e}")

        if not results:
            raise Exception(f"All sources failed for {ticker}")

        # 如果只有一个数据源成功，直接返回
        if len(results) == 1:
            return list(results.values())[0]

        # 多数据源交叉验证
        validated_data = self.validator.cross_validate_prices(results)
        return validated_data
```

### 2. 数据验证器（参考实现）

```python
# src/data/validation.py
from typing import Dict, List, Any
import statistics

class DataValidator:
    def __init__(self):
        self.source_weights = {
            'AKShareSource': 1.0,
            'EastMoneySource': 0.9,
            'SinaSource': 0.8,
        }
        self.price_threshold = 0.02  # 2%
        self.volume_threshold = 0.10  # 10%

    def cross_validate_prices(self, data_sources: Dict[str, List[Dict]]) -> List[Dict]:
        """
        交叉验证多个数据源的价格数据

        Args:
            data_sources: {数据源名: 价格数据列表}

        Returns:
            验证后的价格数据列表
        """
        if len(data_sources) == 1:
            return list(data_sources.values())[0]

        # 按日期分组
        date_groups = self._group_by_date(data_sources)

        validated_data = []
        for date, prices_by_source in date_groups.items():
            # 验证该日期的价格数据
            validated_price = self._validate_single_date(date, prices_by_source)
            if validated_price:
                validated_data.append(validated_price)

        return validated_data

    def _validate_single_date(self, date: str, prices_by_source: Dict[str, Dict]) -> Dict:
        """验证单个日期的价格数据"""
        # 提取收盘价
        close_prices = {
            source: data['close']
            for source, data in prices_by_source.items()
        }

        # 计算加权平均
        weighted_sum = 0
        weight_total = 0
        for source, price in close_prices.items():
            weight = self.source_weights.get(source, 0.5)
            weighted_sum += price * weight
            weight_total += weight

        final_price = weighted_sum / weight_total

        # 检查偏差
        max_deviation = max(
            abs(price - final_price) / final_price
            for price in close_prices.values()
        )

        # 选择最完整的数据作为基础
        base_data = max(
            prices_by_source.items(),
            key=lambda x: len([v for v in x[1].values() if v])
        )[1].copy()

        # 更新收盘价为验证后的值
        base_data['close'] = round(final_price, 2)
        base_data['validation_confidence'] = self._calculate_confidence(
            len(close_prices), max_deviation
        )

        return base_data

    def _calculate_confidence(self, num_sources: int, max_deviation: float) -> float:
        """计算置信度"""
        confidence = min(0.95, 0.8 + num_sources * 0.05 - max_deviation * 10)
        return round(confidence, 2)
```

### 3. 增强缓存（参考实现）

```python
# src/data/cache.py
import time
from typing import Any, Optional, Dict
from threading import Lock
from dataclasses import dataclass

@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0

    @property
    def total(self) -> int:
        return self.hits + self.misses

    @property
    def hit_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return self.hits / self.total

class DataCache:
    def __init__(self, ttl: int = 300):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = Lock()
        self._ttl = ttl
        self.stats = CacheStats()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key not in self._cache:
                self.stats.misses += 1
                return None

            entry = self._cache[key]

            # 检查是否过期
            if time.time() - entry['timestamp'] > self._ttl:
                del self._cache[key]
                self.stats.misses += 1
                return None

            self.stats.hits += 1
            return entry['value']

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._cache[key] = {
                'value': value,
                'timestamp': time.time()
            }

    def cleanup_expired(self) -> int:
        """清理过期缓存"""
        with self._lock:
            current_time = time.time()
            expired_keys = [
                key for key, entry in self._cache.items()
                if current_time - entry['timestamp'] > self._ttl
            ]

            for key in expired_keys:
                del self._cache[key]

            return len(expired_keys)

    def get_stats(self) -> Dict[str, Any]:
        return {
            'hits': self.stats.hits,
            'misses': self.stats.misses,
            'total': self.stats.total,
            'hit_rate': f"{self.stats.hit_rate * 100:.2f}%",
            'size': len(self._cache),
            'ttl': self._ttl
        }
```

---

## 总结

stock-picker 项目在数据源接入方面的核心优势：

1. **多数据源聚合** - 提高数据可用性和可靠性
2. **数据交叉验证** - 提高数据准确性
3. **分层缓存** - 提高性能，减少API调用
4. **市场差异化处理** - 针对不同市场优化
5. **配置化设计** - 易于维护和扩展

ai-hedge-fund 应该借鉴这些设计，特别是多数据源支持和数据验证机制，以提高系统的鲁棒性和数据质量。
