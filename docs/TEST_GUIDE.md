# 测试指南

## 概述

本项目使用 pytest 作为测试框架，包含单元测试、集成测试和端到端测试。本指南介绍测试结构、命名规范、运行方式和最佳实践。

## 测试结构

```
tests/
├── backtesting/          # 回测系统测试
│   ├── integration/      # 回测集成测试（长仓、短仓、多空策略）
│   └── *.py              # 单元测试（投资组合、交易执行、指标计算）
├── data/                 # 数据层测试（缓存、MySQL、验证）
├── markets/              # 市场适配器测试
│   └── sources/          # 数据源单元测试（NewsNow、Sina、Eastmoney、AKShare）
├── integration/          # 端到端集成测试（多市场、缓存、新闻）
├── monitoring/           # 监控系统测试（健康检查、指标、装饰器）
├── tools/                # 工具测试（API集成）
├── config/               # 配置测试（设置、验证器）
└── fixtures/             # 测试数据fixtures（详见 fixtures/README.md）
```

## 快速运行

### 基本命令

```bash
# 运行所有测试
poetry run pytest

# 运行特定目录的测试
poetry run pytest tests/markets/sources/ -v

# 运行特定文件
poetry run pytest tests/backtesting/test_portfolio.py -v

# 运行特定测试
poetry run pytest tests/backtesting/test_portfolio.py::test_buy_long -v
```

### 按标记运行

```bash
# 只运行单元测试
poetry run pytest -m unit

# 只运行集成测试
poetry run pytest -m integration

# 只运行E2E测试
poetry run pytest -m e2e

# 只运行快速测试
poetry run pytest -m fast

# 只运行慢速测试
poetry run pytest -m slow

# 排除慢速测试
poetry run pytest -m "not slow"

# 运行集成但排除E2E
poetry run pytest -m "integration and not e2e"
```

### 调试选项

```bash
# 详细输出（显示每个测试名称）
poetry run pytest -v

# 更详细的输出（显示assert详情）
poetry run pytest -vv

# 显示print语句输出
poetry run pytest -s

# 第一个失败时停止
poetry run pytest -x

# 最多失败N次后停止
poetry run pytest --maxfail=3

# 显示最慢的10个测试
poetry run pytest --durations=10

# 仅运行上次失败的测试
poetry run pytest --lf

# 先运行上次失败的测试，然后运行其他
poetry run pytest --ff
```

## 测试命名规范

### 文件命名

- **单元测试**: `test_<module_name>.py`
  - 示例: `test_portfolio.py`, `test_execution.py`

- **集成测试**: `test_<feature>_integration.py` 或 `test_integration_<feature>.py`
  - 示例: `test_yfinance_integration.py`, `test_integration_long_only.py`

- **E2E测试**: `test_<feature>_e2e.py`
  - 示例: `test_newsnow_e2e.py`, `test_eastmoney_e2e.py`

- **快速测试**: `test_<feature>_fast.py`
  - 示例: `test_insider_trades_fast.py`
  - 用于需要快速验证的关键功能

### 类命名

```python
class TestFeatureName:
    """Test class for FeatureName"""
```

### 函数命名

- 使用描述性名称，清楚说明测试内容
- 格式: `test_<action>_<expected_result>`

```python
def test_buy_long_increases_position():
    """Test that buying long shares increases the position"""

def test_sell_without_position_raises_error():
    """Test that selling without a position raises an error"""

def test_margin_calculation_with_short_positions():
    """Test margin calculation when holding short positions"""
```

## Pytest标记使用

### 内置标记

项目使用以下pytest标记对测试进行分类：

```python
import pytest

# 单元测试 - 测试单个函数/类，不依赖外部服务
@pytest.mark.unit
def test_portfolio_initialization():
    pass

# 集成测试 - 测试多个组件交互，可能涉及模拟的外部服务
@pytest.mark.integration
def test_market_adapter_with_data_source():
    pass

# E2E测试 - 端到端测试，覆盖完整流程
@pytest.mark.e2e
def test_full_backtest_workflow():
    pass

# 快速测试 - 运行时间<1秒
@pytest.mark.fast
def test_quick_calculation():
    pass

# 慢速测试 - 运行时间>5秒（如涉及实际API调用）
@pytest.mark.slow
def test_real_api_call():
    pass

# 跳过条件测试
@pytest.mark.skipif(condition, reason="...")
def test_conditional_feature():
    pass

# 参数化测试
@pytest.mark.parametrize("input,expected", [
    (1, 2),
    (2, 4),
])
def test_with_parameters(input, expected):
    pass
```

### 标记组合

可以在同一测试上使用多个标记：

```python
@pytest.mark.integration
@pytest.mark.slow
def test_complex_integration():
    """需要较长时间的集成测试"""
    pass

@pytest.mark.e2e
@pytest.mark.integration
class TestMultiMarketE2E:
    """端到端多市场集成测试类"""
    pass
```

### 配置标记

在 `pytest.ini` 或 `pyproject.toml` 中注册标记：

```ini
[tool.pytest.ini_options]
markers = [
    "unit: Unit tests",
    "integration: Integration tests",
    "e2e: End-to-end tests",
    "fast: Fast tests (<1s)",
    "slow: Slow tests (>5s)",
]
```

## Mock和Fixture最佳实践

### 使用Fixtures

Fixtures是pytest提供的用于测试前准备和清理的机制。

#### 定义Fixtures

```python
import pytest

@pytest.fixture
def portfolio():
    """Create a test portfolio"""
    return Portfolio(
        tickers=["AAPL", "MSFT"],
        initial_cash=100_000.0,
        margin_requirement=0.5
    )

@pytest.fixture
def prices():
    """Provide test prices"""
    return {"AAPL": 100.0, "MSFT": 200.0}
```

#### 使用Fixtures

```python
def test_portfolio_initialization(portfolio):
    """Test portfolio initializes correctly"""
    assert portfolio.cash == 100_000.0
    assert "AAPL" in portfolio.positions

def test_trade_execution(portfolio, prices):
    """Test trade execution with prices"""
    portfolio.buy("AAPL", 10, prices["AAPL"])
    assert portfolio.positions["AAPL"]["long"] == 10
```

#### Fixture作用域

```python
@pytest.fixture(scope="function")  # 每个测试函数一次（默认）
def per_test_fixture():
    pass

@pytest.fixture(scope="class")     # 每个测试类一次
def per_class_fixture():
    pass

@pytest.fixture(scope="module")    # 每个模块一次
def per_module_fixture():
    pass

@pytest.fixture(scope="session")   # 整个测试会话一次
def per_session_fixture():
    pass
```

### 使用conftest.py

`conftest.py` 文件中的fixtures可以在整个目录及子目录的测试中使用。

```python
# tests/backtesting/conftest.py
import pytest
from src.backtesting.portfolio import Portfolio

@pytest.fixture
def portfolio():
    """Shared portfolio fixture for all backtesting tests"""
    return Portfolio(
        tickers=["AAPL", "MSFT"],
        initial_cash=100_000.0,
        margin_requirement=0.5
    )
```

### Mock外部依赖

使用 `unittest.mock` 或 `pytest-mock` 来模拟外部依赖：

```python
from unittest.mock import patch, MagicMock
import pytest

def test_api_call_with_mock():
    """Test with mocked API call"""
    with patch('src.tools.api.get_prices') as mock_get_prices:
        # 配置mock返回值
        mock_get_prices.return_value = [
            {"date": "2024-01-01", "close": 150.0}
        ]

        # 执行测试
        result = some_function_that_calls_api()

        # 验证mock被调用
        mock_get_prices.assert_called_once_with("AAPL", "2024-01-01", "2024-01-31")
        assert len(result) == 1

# 使用pytest-mock
def test_with_mocker(mocker):
    """Test using pytest-mock"""
    mock_api = mocker.patch('src.tools.api.get_prices')
    mock_api.return_value = [{"date": "2024-01-01", "close": 150.0}]

    result = some_function_that_calls_api()
    assert len(result) == 1
```

### 使用Fixture数据文件

项目使用JSON文件作为测试数据fixtures（详见 `tests/fixtures/README.md`）：

```python
# tests/backtesting/integration/conftest.py
from pathlib import Path
import json

PRICES_ROOT = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "api" / "prices"

def _load_price_df_from_fixture(ticker: str, start: str, end: str):
    """Load price data from fixture file"""
    fixture_file = PRICES_ROOT / f"{ticker}_{start}_{end}.json"
    with open(fixture_file, "r") as f:
        data = json.load(f)
    return pd.DataFrame(data)
```

## 如何运行特定类型的测试

### 单元测试

单元测试应该：
- 测试单个函数或类
- 不依赖外部服务（数据库、API）
- 使用mock替代外部依赖
- 运行快速（<1秒）

```bash
poetry run pytest -m unit -v
```

### 集成测试

集成测试应该：
- 测试多个组件的交互
- 可以使用内存数据库
- 可以使用模拟的API响应
- 运行时间适中（1-5秒）

```bash
poetry run pytest -m integration -v
```

### E2E测试

E2E测试应该：
- 测试完整的用户流程
- 尽可能接近真实环境
- 可以使用真实API（但注意限流和成本）
- 运行时间较长（5秒以上）

```bash
poetry run pytest -m e2e -v
```

## CI/CD集成

### GitHub Actions示例

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install Poetry
        run: |
          curl -sSL https://install.python-poetry.org | python3 -

      - name: Install dependencies
        run: poetry install

      - name: Run fast tests
        run: poetry run pytest -m "fast or unit" -v

      - name: Run integration tests
        run: poetry run pytest -m "integration and not slow" -v

      - name: Run all tests with coverage
        run: poetry run pytest --cov=src --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

### 本地CI模拟

```bash
# 模拟CI运行的测试套件
poetry run pytest -m "not slow" --cov=src --cov-report=html

# 查看覆盖率报告
open htmlcov/index.html
```

## 核心测试模块说明

### 回测系统测试 (tests/backtesting/)

- `test_portfolio.py`: 投资组合操作（买入、卖出、做空、平仓）
- `test_execution.py`: 交易执行逻辑
- `test_metrics.py`: 性能指标计算（夏普比率、最大回撤等）
- `test_controller.py`: 回测控制器
- `test_valuation.py`: 估值计算
- `integration/test_integration_long_only.py`: 纯多头策略集成测试
- `integration/test_integration_short_only.py`: 纯空头策略集成测试
- `integration/test_integration_long_short.py`: 多空策略集成测试

### 数据源测试 (tests/markets/sources/)

- `test_newsnow_source.py`: NewsNow新闻源测试 (4 tests)
- `test_sina_finance_source.py`: 新浪财经数据源测试 (4 tests)
- `test_eastmoney_source.py`: 东方财富数据源测试 (19 tests)
- `test_akshare_news_source.py`: AKShare新闻数据测试 (4 tests)

### 市场适配器测试 (tests/markets/)

- `test_us_stock.py`: 美股适配器
- `test_cn_stock.py`: A股适配器
- `test_hk_stock.py`: 港股适配器
- `test_commodity.py`: 商品市场适配器
- `test_router.py`: 市场路由器
- `test_insider_trades_fast.py`: 内部交易功能快速测试

### 集成测试 (tests/integration/)

- `test_e2e_multi_market.py`: 跨市场端到端测试
- `test_newsnow_e2e.py`: 新闻数据流验证
- `test_eastmoney_e2e.py`: A股数据验证
- `test_hk_news_e2e.py`: 港股新闻验证
- `test_dual_layer_cache_e2e.py`: 双层缓存端到端测试

### 数据层测试 (tests/data/)

- `test_cache_enhancement.py`: 缓存增强功能
- `test_validation.py`: 数据验证
- `test_mysql_models.py`: MySQL数据模型
- `test_mysql_cache_manager.py`: MySQL缓存管理器

## 测试覆盖率

### 生成覆盖率报告

```bash
# 生成HTML覆盖率报告
poetry run pytest --cov=src --cov-report=html

# 生成终端覆盖率报告
poetry run pytest --cov=src --cov-report=term

# 生成XML覆盖率报告（用于CI）
poetry run pytest --cov=src --cov-report=xml
```

### 覆盖率目标

- 核心业务逻辑: >80%
- 工具函数: >70%
- API集成: >60%

## 常见问题

### Q: 测试运行很慢怎么办？

A:
1. 使用 `-m "not slow"` 排除慢速测试
2. 使用 `--durations=10` 找出最慢的测试
3. 检查是否可以使用mock替代真实API调用
4. 考虑使用pytest-xdist并行运行: `pytest -n auto`

### Q: 如何调试失败的测试？

A:
1. 使用 `-vv` 查看详细输出
2. 使用 `-s` 查看print语句
3. 使用 `--pdb` 在失败时进入调试器
4. 使用 `--lf` 只运行上次失败的测试

### Q: 如何编写好的测试？

A:
1. 遵循AAA模式: Arrange（准备）、Act（执行）、Assert（断言）
2. 一个测试只测试一个功能点
3. 使用描述性的测试名称
4. 添加docstring说明测试目的
5. 使用fixtures减少重复代码
6. 保持测试独立，不依赖执行顺序

### Q: Mock数据应该多真实？

A:
- 单元测试: 可以使用简化数据，只需包含被测试的字段
- 集成测试: 应接近真实数据结构
- E2E测试: 尽可能使用真实数据或真实API

## 相关文档

- Fixtures说明: `tests/fixtures/README.md`
- 项目指南: `CLAUDE.md`
- 回测系统: `src/backtesting/`
- 数据模型: `src/data/models.py`
- API工具: `src/tools/api.py`
