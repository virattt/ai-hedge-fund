# Test Fixtures 说明

本目录包含用于测试的模拟数据（mock data），用于在不依赖外部API的情况下进行集成测试。

## 目录结构

```
fixtures/
└── api/
    ├── prices/              # 价格数据fixtures
    ├── financial_metrics/   # 财务指标数据fixtures
    ├── insider_trades/      # 内部交易数据fixtures
    └── news/                # 新闻数据fixtures
```

## 各目录说明

### api/prices/

存储股票价格数据的JSON文件。

**文件命名规范**: `{TICKER}_{START_DATE}_{END_DATE}.json`

**示例**: `AAPL_2024-03-01_2024-03-08.json`

**数据格式**:
```json
[
  {
    "date": "2024-03-01",
    "open": 150.0,
    "high": 155.0,
    "low": 149.0,
    "close": 152.0,
    "volume": 1000000
  }
]
```

**用途**: 回测引擎集成测试、投资组合测试

### api/financial_metrics/

存储公司财务指标数据的JSON文件。

**文件命名规范**: `{TICKER}_{START_DATE}_{END_DATE}.json`

**示例**: `AAPL_2024-03-01_2024-03-08.json`

**数据格式**:
```json
{
  "market_cap": 3000000000000,
  "pe_ratio": 28.5,
  "eps": 5.34,
  "revenue": 383000000000,
  "net_income": 100000000000,
  "debt_to_equity": 1.8,
  "roe": 0.15,
  "current_ratio": 0.98,
  "gross_margin": 0.42,
  "operating_margin": 0.26
}
```

**用途**: 基本面分析师测试、财务指标计算测试

### api/insider_trades/

存储内部人交易数据的JSON文件。

**文件命名规范**: `{TICKER}_{START_DATE}_{END_DATE}.json`

**示例**: `AAPL_2024-03-01_2024-03-08.json`

**数据格式**:
```json
[
  {
    "filing_date": "2024-03-01",
    "transaction_date": "2024-02-28",
    "insider": "John Doe",
    "title": "CEO",
    "transaction_type": "Purchase",
    "shares": 10000,
    "price_per_share": 150.0,
    "total_value": 1500000.0
  }
]
```

**用途**: 内部交易分析、市场情绪测试

### api/news/

存储公司新闻数据的JSON文件。

**文件命名规范**: `{TICKER}_{START_DATE}_{END_DATE}.json`

**示例**: `AAPL_2024-03-01_2024-03-08.json`

**数据格式**:
```json
[
  {
    "title": "Apple announces new product",
    "description": "Apple Inc. announced a new...",
    "url": "https://example.com/news/123",
    "source": "TechCrunch",
    "published_at": "2024-03-01T10:00:00Z",
    "sentiment": "positive"
  }
]
```

**用途**: 新闻情绪分析师测试、事件驱动策略测试

## 如何使用Fixtures

### 在conftest.py中使用

集成测试通过`tests/backtesting/integration/conftest.py`加载fixtures：

```python
from pathlib import Path
import json
import pandas as pd

PRICES_ROOT = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "api" / "prices"

def _load_price_df_from_fixture(ticker: str, start: str, end: str) -> pd.DataFrame:
    fixture_file = PRICES_ROOT / f"{ticker}_{start}_{end}.json"
    with open(fixture_file, "r") as f:
        data = json.load(f)
    return pd.DataFrame(data)
```

### 在测试中使用

```python
def test_backtest_with_fixtures():
    # Fixtures会自动通过conftest.py中的mock加载
    engine = BacktestEngine(
        agent=agent,
        tickers=["AAPL", "MSFT"],
        start_date="2024-03-01",
        end_date="2024-03-08",
        initial_capital=100000.0
    )
    results = engine.run_backtest()
    assert results is not None
```

## 如何添加新的Mock数据

### 1. 确定数据类型和时间范围

选择合适的fixture目录（prices、financial_metrics、insider_trades、news）。

### 2. 创建JSON文件

按照命名规范创建文件：`{TICKER}_{START_DATE}_{END_DATE}.json`

### 3. 填充数据

根据对应的数据格式填充真实或模拟的数据。可以参考现有fixture文件的格式。

### 4. 验证数据格式

确保JSON格式正确，数据类型匹配：
```bash
python -m json.tool tests/fixtures/api/prices/NEW_FILE.json
```

### 5. 更新测试

在测试中引用新的fixture文件，验证测试通过：
```bash
poetry run pytest tests/backtesting/integration/ -v
```

## 最佳实践

### 1. 保持数据一致性

- 同一ticker的不同fixture文件应使用一致的日期范围
- 价格数据应与实际市场数据趋势相符（可以简化但不应离谱）

### 2. 最小化数据量

- 只包含测试所需的最少数据点
- 对于回测测试，5-10个交易日通常足够

### 3. 使用真实的ticker

- 使用真实的股票代码（AAPL、MSFT等）便于理解
- 确保fixture数据与测试代码中的ticker匹配

### 4. 注释特殊数据

如果某些数据点是为特定测试场景设计的（如极端波动），在JSON中或测试代码中添加注释说明。

### 5. 定期更新

- 当API数据格式变化时，及时更新fixture格式
- 当添加新的数据源或字段时，更新相应的fixtures

## 常见问题

### Q: 为什么需要fixtures而不是直接调用API?

A:
- 避免测试依赖外部服务（网络、API限流、费用）
- 确保测试结果可重现
- 加快测试速度
- 可以测试边界情况和错误场景

### Q: 如何生成fixture数据?

A:
1. 从真实API获取数据并保存为JSON
2. 手动构造测试数据
3. 使用数据生成脚本（可以创建`scripts/generate_fixtures.py`）

### Q: fixture数据需要多准确?

A:
- 对于单元测试：可以使用简化的模拟数据
- 对于集成测试：应尽量接近真实数据，确保业务逻辑正确性
- 对于边界测试：可以使用极端值

### Q: 如何处理日期范围重叠?

A:
- conftest.py中的`_find_price_fixture_file`函数会自动查找日期范围重叠的fixture
- 可以创建覆盖不同时间段的多个fixture文件

## 参考

- 集成测试配置: `tests/backtesting/integration/conftest.py`
- 回测引擎: `src/backtesting/engine.py`
- 数据模型: `src/data/models.py`
- API接口: `src/tools/api.py`
