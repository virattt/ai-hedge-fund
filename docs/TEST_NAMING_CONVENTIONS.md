# 测试命名规范

本文档定义了项目中测试文件、测试类和测试函数的命名规范。

## 文件命名规范

### 单元测试

**格式**: `test_<module_name>.py`

**说明**: 测试单个模块/组件的功能，不依赖外部服务

**示例**:
- `test_portfolio.py` - 测试投资组合模块
- `test_execution.py` - 测试交易执行模块
- `test_metrics.py` - 测试性能指标计算
- `test_validation.py` - 测试数据验证功能

**pytest标记**: `@pytest.mark.unit`

### 集成测试

**格式**:
- `test_<feature>_integration.py` 或
- `test_integration_<feature>.py`

**说明**: 测试多个组件的交互，可能使用模拟的外部服务

**示例**:
- `test_yfinance_integration.py` - YFinance API集成测试
- `test_integration_long_only.py` - 纯多头策略集成测试
- `test_integration_short_only.py` - 纯空头策略集成测试
- `test_integration_long_short.py` - 多空策略集成测试
- `test_multi_source_integration.py` - 多数据源集成测试

**pytest标记**: `@pytest.mark.integration`

### E2E测试

**格式**: `test_<feature>_e2e.py`

**说明**: 端到端测试，覆盖完整的用户流程

**示例**:
- `test_newsnow_e2e.py` - NewsNow新闻数据流端到端测试
- `test_eastmoney_e2e.py` - 东方财富数据端到端测试
- `test_hk_news_e2e.py` - 港股新闻端到端测试
- `test_dual_layer_cache_e2e.py` - 双层缓存端到端测试
- `test_e2e_multi_market.py` - 多市场端到端测试

**pytest标记**: `@pytest.mark.e2e` (通常与 `@pytest.mark.integration` 一起使用)

### 快速测试

**格式**: `test_<feature>_fast.py`

**说明**: 快速验证关键功能的测试，运行时间<1秒

**示例**:
- `test_insider_trades_fast.py` - 内部交易功能快速测试
- `test_cache_fast.py` - 缓存功能快速测试

**pytest标记**: `@pytest.mark.fast`

### 慢速测试

**说明**: 涉及真实API调用或大数据量处理的测试

**示例**:
- `test_yfinance_rate_limiting.py` - YFinance限流测试（涉及真实API）
- `test_akshare_hk_enhanced.py` - AKShare港股增强测试

**pytest标记**: `@pytest.mark.slow`

## 类命名规范

### 格式

```python
class Test<FeatureName>:
    """Test class for <FeatureName>"""
```

### 示例

```python
class TestPortfolio:
    """Test class for Portfolio operations"""

class TestMarketRouter:
    """Test class for MarketRouter functionality"""

class TestInsiderTradesFast:
    """Fast unit tests for insider trading data functionality"""

class TestMultiMarketE2E:
    """端到端多市场集成测试"""
```

### 规范

1. 以 `Test` 开头
2. 使用驼峰命名法（CamelCase）
3. 名称应清晰描述被测试的功能或组件
4. 必须包含docstring说明测试范围

## 函数命名规范

### 格式

```python
def test_<action>_<expected_result>():
    """Describe what this test does"""
```

### 示例

```python
def test_buy_long_increases_position():
    """Test that buying long shares increases the position"""

def test_sell_without_position_raises_error():
    """Test that selling without a position raises an error"""

def test_margin_calculation_with_short_positions():
    """Test margin calculation when holding short positions"""

def test_get_prices_returns_valid_data():
    """Test that get_prices returns properly formatted price data"""

def test_cache_hit_returns_cached_value():
    """Test that cache returns cached value on hit"""
```

### 规范

1. 以 `test_` 开头
2. 使用小写字母和下划线（snake_case）
3. 名称应包含：
   - 被测试的动作/操作
   - 预期的结果
4. 名称应足够描述性，不需要阅读代码即可理解测试意图
5. 必须包含docstring详细说明测试内容

## 命名反例

### 文件命名反例

❌ 不规范:
- `test_insider_trades_quick.py` - 应使用 `fast` 而非 `quick`
- `test_hk.py` - 太笼统，应明确指明功能
- `integration_test.py` - 缺少 `test_` 前缀
- `test_all.py` - 太笼统

✅ 规范:
- `test_insider_trades_fast.py`
- `test_hk_stock.py` 或 `test_hk_stock_adapter.py`
- `test_integration_backtest.py` 或 `test_backtest_integration.py`
- `test_backtest_long_only.py`

### 类命名反例

❌ 不规范:
```python
class InsiderTradesTest:  # Test应在前面
class testPortfolio:      # 应使用驼峰命名，Test大写
class TestInsiderTradesQuick:  # 应使用Fast而非Quick
```

✅ 规范:
```python
class TestInsiderTrades:
class TestPortfolio:
class TestInsiderTradesFast:
```

### 函数命名反例

❌ 不规范:
```python
def test1():  # 名称无意义
def testBuyLong():  # 应使用snake_case
def test_buy():  # 缺少预期结果
def test_the_portfolio_can_buy_long_shares_and_increase_position():  # 太冗长
```

✅ 规范:
```python
def test_buy_long_increases_position():
def test_buy_long_with_insufficient_cash_raises_error():
def test_calculate_margin_with_zero_requirement():
```

## Pytest标记使用指南

### 单个标记

```python
import pytest

@pytest.mark.unit
def test_simple_calculation():
    """Simple unit test"""
    pass

@pytest.mark.integration
def test_api_integration():
    """Integration test with API"""
    pass

@pytest.mark.e2e
def test_complete_workflow():
    """End-to-end test"""
    pass
```

### 多个标记组合

```python
@pytest.mark.integration
@pytest.mark.slow
def test_real_api_call():
    """Integration test that makes real API calls"""
    pass

@pytest.mark.e2e
@pytest.mark.integration
class TestMultiMarketE2E:
    """End-to-end multi-market tests"""
    pass
```

### 类级别标记

```python
@pytest.mark.integration
@pytest.mark.slow
class TestBacktestEngine:
    """All tests in this class are integration tests and slow"""

    def test_long_only_strategy(self):
        pass

    def test_short_only_strategy(self):
        pass
```

## 标记定义

### @pytest.mark.unit
- **用途**: 单元测试
- **特点**: 测试单个函数/类，不依赖外部服务，使用mock替代依赖
- **运行时间**: <1秒
- **示例**: 投资组合计算、数据验证、工具函数

### @pytest.mark.integration
- **用途**: 集成测试
- **特点**: 测试多个组件交互，可能使用模拟的外部服务
- **运行时间**: 1-5秒
- **示例**: 市场适配器与数据源交互、缓存层测试

### @pytest.mark.e2e
- **用途**: 端到端测试
- **特点**: 测试完整用户流程，尽可能接近真实环境
- **运行时间**: 5秒以上
- **示例**: 完整回测流程、多市场数据获取流程

### @pytest.mark.fast
- **用途**: 快速测试
- **特点**: 运行时间<1秒的关键功能验证
- **运行时间**: <1秒
- **示例**: 缓存命中、简单计算、数据模型验证

### @pytest.mark.slow
- **用途**: 慢速测试
- **特点**: 涉及真实API调用或大数据量处理
- **运行时间**: >5秒
- **示例**: 真实API调用、大规模回测、限流测试

## 运行测试示例

```bash
# 运行所有单元测试
poetry run pytest -m unit

# 运行所有集成测试（排除E2E）
poetry run pytest -m "integration and not e2e"

# 运行快速测试（开发时频繁使用）
poetry run pytest -m fast

# 运行除慢速测试外的所有测试（CI中使用）
poetry run pytest -m "not slow"

# 运行特定目录的集成测试
poetry run pytest tests/integration/ -m integration

# 运行E2E测试
poetry run pytest -m e2e -v
```

## 测试组织最佳实践

### 1. 文件组织

- 将相关测试放在同一目录下
- 使用清晰的目录层级反映代码结构
- 将fixtures放在 `conftest.py` 中

### 2. 测试独立性

- 每个测试应独立运行，不依赖其他测试
- 使用fixtures准备测试数据
- 测试结束后清理状态

### 3. 测试覆盖

- 单元测试覆盖核心业务逻辑
- 集成测试覆盖组件交互
- E2E测试覆盖关键用户流程

### 4. 命名一致性

- 在整个项目中保持命名风格一致
- 使用描述性名称，避免缩写
- 包含足够的上下文信息

## 参考文档

- 测试指南: `docs/TEST_GUIDE.md`
- Fixtures说明: `tests/fixtures/README.md`
- 项目指南: `CLAUDE.md`
- pytest文档: https://docs.pytest.org/
