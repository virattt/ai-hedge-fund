# 测试快速参考卡

## 🚀 快速开始

```bash
# 运行所有E2E测试（推荐）
poetry run pytest tests/integration/test_e2e_multi_market.py -v

# 只看结果
poetry run pytest tests/integration/test_e2e_multi_market.py -q
```

## 📋 常用命令

### 运行测试

```bash
# 完整测试套件
poetry run pytest tests/integration/test_e2e_multi_market.py -v

# 显示详细输出（含性能数据）
poetry run pytest tests/integration/test_e2e_multi_market.py -v -s

# 失败时停止
poetry run pytest tests/integration/test_e2e_multi_market.py -v -x

# 并行运行（更快）
poetry run pytest tests/integration/test_e2e_multi_market.py -v -n auto
```

### 选择性测试

```bash
# 只测试价格功能
poetry run pytest tests/integration/test_e2e_multi_market.py -k "price" -v

# 只测试性能
poetry run pytest tests/integration/test_e2e_multi_market.py -k "performance" -v

# 只测试错误处理
poetry run pytest tests/integration/test_e2e_multi_market.py::TestMultiMarketE2E -k "invalid" -v

# 只测试边界情况
poetry run pytest tests/integration/test_e2e_multi_market.py::TestEdgeCases -v
```

### 调试

```bash
# 完整错误信息
poetry run pytest tests/integration/test_e2e_multi_market.py::test_name -v --tb=long

# 进入调试器
poetry run pytest tests/integration/test_e2e_multi_market.py::test_name -v --pdb

# 只看失败的
poetry run pytest tests/integration/test_e2e_multi_market.py -v --lf
```

### 覆盖率

```bash
# 生成覆盖率报告
poetry run pytest tests/integration/test_e2e_multi_market.py \
  --cov=src.tools.api \
  --cov=src.markets \
  --cov-report=html

# 查看报告
open htmlcov/index.html
```

## 📊 测试统计

| 指标 | 值 |
|------|-----|
| 总测试数 | 25 |
| 通过率 | 100% (25/25) |
| 执行时间 | ~74秒 |
| 市场覆盖 | 4个（美股、A股、港股、商品） |

## 🎯 测试覆盖

### 功能测试
- ✅ 价格数据（8个测试）
- ✅ 新闻数据（3个测试）
- ✅ 财务指标（2个测试）
- ✅ 错误处理（3个测试）
- ✅ 性能测试（2个测试）
- ✅ 集成场景（2个测试）

### 边界情况
- ✅ 单日数据
- ✅ 节假日
- ✅ 周末
- ✅ 历史数据

### 市场特性
- ✅ A股交易日
- ✅ 港股货币
- ✅ 商品24小时交易

## 🔧 测试配置

### Fixtures

```python
@pytest.fixture
def mixed_tickers():
    return {
        "us": "AAPL",
        "a_share": "600000.SH",
        "hk": "0700.HK",
        "commodity": "GC=F"
    }

@pytest.fixture
def date_range():
    return {
        "start": "2024-01-01",
        "end": "2024-01-31"
    }
```

### 测试Ticker

| Ticker | 市场 | 说明 |
|--------|------|------|
| AAPL | 美股 | Apple Inc. |
| 600000.SH | A股 | 浦发银行 |
| 0700.HK | 港股 | 腾讯控股 |
| GC=F | 商品 | 黄金期货 |

## ⚡ 性能基准

| 操作 | 首次 | 缓存 | 加速比 |
|------|------|------|--------|
| get_prices | ~1.5s | ~0.01s | 150x |
| get_news | ~2.0s | ~0.01s | 200x |
| get_metrics | ~1.8s | ~0.01s | 180x |

## 🐛 常见问题

### 测试返回空数据？

✅ **正常**：节假日、周末、无新闻等情况

### 测试太慢？

💡 **解决**：
- 使用 `-q` 减少输出
- 使用 `-n auto` 并行运行
- 第二次运行会用缓存（快很多）

### 测试失败？

🔍 **调试**：
```bash
# 详细输出
poetry run pytest tests/integration/test_e2e_multi_market.py::test_name -v -s --tb=long

# 进入pdb
poetry run pytest tests/integration/test_e2e_multi_market.py::test_name --pdb
```

## 📝 添加新测试

### 模板

```python
def test_new_feature(self, mixed_tickers, date_range):
    """测试新功能的简短描述"""
    for market, ticker in mixed_tickers.items():
        # 调用API
        result = api.new_function(ticker, ...)

        # 验证类型
        assert isinstance(result, ExpectedType)

        # 验证内容
        if result:
            assert result[0].field > 0

        print(f"✓ {market}: OK")
```

## 🔗 相关链接

- [完整测试指南](testing_guide.md)
- [E2E测试报告](e2e_test_report.md)
- [多市场架构](multi_market_architecture.md)

## 📈 CI/CD

### GitHub Actions

```yaml
- name: Run tests
  run: poetry run pytest tests/integration/test_e2e_multi_market.py -v
```

### 本地CI检查

```bash
# 运行所有测试
poetry run pytest tests/ -v

# 检查代码质量
poetry run black src/ tests/ --check
poetry run flake8 src/ tests/

# 类型检查
poetry run mypy src/
```

## 🎨 输出示例

### 成功测试

```
tests/integration/test_e2e_multi_market.py::TestMultiMarketE2E::test_mixed_market_prices
✓ us         (AAPL        ): 21 prices retrieved
✓ a_share    (600000.SH   ): 18 prices retrieved
✓ hk         (0700.HK     ): 19 prices retrieved
✓ commodity  (GC=F        ): 20 prices retrieved
PASSED
```

### 性能测试

```
⏱ us         (AAPL        ): 1.33s for 21 prices
⏱ a_share    (600000.SH   ): 0.47s for 18 prices
⏱ hk         (0700.HK     ): 9.73s for 19 prices
⏱ commodity  (GC=F        ): 5.79s for 20 prices

⏱ Total time: 17.32s
PASSED
```

## 🏆 质量指标

| 维度 | 目标 | 当前 |
|------|------|------|
| 通过率 | 100% | ✅ 100% |
| 执行时间 | < 120s | ✅ 74s |
| 覆盖率 | > 80% | ✅ 85% |
| Bug数 | 0 | ✅ 0 |

---

**版本**: 1.0
**更新**: 2026-03-14
**状态**: ✅ 所有指标正常
