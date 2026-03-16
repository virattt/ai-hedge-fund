# 多市场功能测试指南

## 概述

本文档介绍多市场功能的测试体系，包括单元测试、集成测试和端到端测试。

## 测试层次

### 1. 单元测试（Unit Tests）

位置: `tests/markets/`

**测试内容**:
- 单个市场适配器功能
- MarketRouter路由逻辑
- 数据转换函数
- 错误处理逻辑

**示例**:
```bash
# 测试美股适配器
poetry run pytest tests/markets/test_us_stock.py -v

# 测试A股适配器
poetry run pytest tests/markets/test_a_share.py -v

# 测试港股适配器
poetry run pytest tests/markets/test_hk_stock.py -v

# 测试商品适配器
poetry run pytest tests/markets/test_commodity.py -v

# 测试路由器
poetry run pytest tests/markets/test_router.py -v
```

### 2. API集成测试（API Integration Tests）

位置: `tests/tools/`

**测试内容**:
- api.py与适配器的集成
- 缓存机制
- 数据格式转换
- 向后兼容性

**示例**:
```bash
# 测试API集成
poetry run pytest tests/tools/test_api_integration.py -v
```

### 3. 端到端测试（E2E Tests）

位置: `tests/integration/`

**测试内容**:
- 完整数据流（api → router → adapter → 返回）
- 多市场混合场景
- 真实API调用
- 性能基准
- 错误恢复

**示例**:
```bash
# 运行完整E2E测试套件
poetry run pytest tests/integration/test_e2e_multi_market.py -v

# 只测试价格功能
poetry run pytest tests/integration/test_e2e_multi_market.py::TestMultiMarketE2E::test_mixed_market_prices -v

# 只测试性能
poetry run pytest tests/integration/test_e2e_multi_market.py::TestMultiMarketE2E::test_performance_multi_market -v -s
```

## 测试类型说明

### TestMultiMarketE2E（主测试类）

#### 价格数据测试
- `test_mixed_market_prices` - 验证所有市场能返回价格数据
- `test_us_stock_prices_detailed` - 美股价格详细验证（日期、价格关系等）
- `test_a_share_prices_detailed` - A股价格验证
- `test_hk_stock_prices_detailed` - 港股价格验证
- `test_commodity_prices_detailed` - 商品价格验证
- `test_price_data_format_consistency` - 跨市场格式一致性

#### 新闻数据测试
- `test_mixed_market_news` - 混合市场新闻获取
- `test_us_stock_news_content` - 美股新闻内容质量验证
- `test_news_data_format_consistency` - 新闻格式一致性

#### 财务指标测试
- `test_mixed_market_metrics` - 混合市场财务指标（区分有/无财务指标）
- `test_us_stock_metrics_detailed` - 美股财务指标详细验证

#### 错误处理测试
- `test_invalid_ticker` - 无效ticker不抛异常
- `test_invalid_date_range` - 未来日期返回空列表
- `test_reversed_date_range` - 反向日期范围处理

#### 性能测试
- `test_performance_multi_market` - 多市场响应时间（< 10秒/ticker）
- `test_cache_performance` - 缓存加速效果（> 5倍加速）

#### 集成场景测试
- `test_complete_data_flow` - 完整数据获取流程（价格+新闻+指标）
- `test_multi_ticker_batch_processing` - 批量处理多个ticker

### TestEdgeCases（边界情况）

- `test_single_day_range` - 单日数据
- `test_holiday_period` - 节假日期间
- `test_weekend_date_range` - 周末日期
- `test_very_old_data` - 历史数据（10年前）

### TestMarketSpecific（市场特定）

- `test_a_share_trading_days` - A股交易日特性
- `test_hk_stock_currency` - 港股货币单位
- `test_commodity_24h_trading` - 商品24小时交易

## 运行测试

### 快速测试（推荐）

```bash
# 运行所有E2E测试（约1-2分钟）
poetry run pytest tests/integration/test_e2e_multi_market.py -v

# 只看结果，不显示详细日志
poetry run pytest tests/integration/test_e2e_multi_market.py -q
```

### 详细测试

```bash
# 显示print输出（性能数据等）
poetry run pytest tests/integration/test_e2e_multi_market.py -v -s

# 显示完整错误信息
poetry run pytest tests/integration/test_e2e_multi_market.py -v --tb=long

# 失败时立即停止
poetry run pytest tests/integration/test_e2e_multi_market.py -v -x
```

### 选择性测试

```bash
# 只测试某个类
poetry run pytest tests/integration/test_e2e_multi_market.py::TestMultiMarketE2E -v

# 只测试某个方法
poetry run pytest tests/integration/test_e2e_multi_market.py::TestMultiMarketE2E::test_performance_multi_market -v

# 只测试边界情况
poetry run pytest tests/integration/test_e2e_multi_market.py::TestEdgeCases -v

# 只测试市场特定功能
poetry run pytest tests/integration/test_e2e_multi_market.py::TestMarketSpecific -v
```

### 覆盖率测试

```bash
# 生成覆盖率报告
poetry run pytest tests/integration/test_e2e_multi_market.py \
  --cov=src.tools.api \
  --cov=src.markets \
  --cov-report=html \
  --cov-report=term

# 查看HTML报告
open htmlcov/index.html
```

## 测试数据

### 使用的Ticker

| Ticker | 市场 | 公司/商品 | 原因 |
|--------|------|----------|------|
| AAPL | 美股 | Apple Inc. | 流动性好，数据完整 |
| 600000.SH | A股 | 浦发银行 | 上交所大盘股 |
| 0700.HK | 港股 | 腾讯控股 | 港股代表性股票 |
| GC=F | 商品 | 黄金期货 | 商品期货代表 |

### 日期范围

- **默认范围**: 2024-01-01 到 2024-01-31（1个月）
- **单日测试**: 2024-01-15（工作日）
- **节假日**: 2024-01-01（新年）
- **周末**: 2024-01-06, 2024-01-07
- **历史数据**: 2014-01-01（10年前）

## 性能基准

### 响应时间预期

| 操作 | 预期时间 | 测试阈值 |
|------|---------|----------|
| 单ticker价格 | 1-3秒 | < 10秒 |
| 多ticker批量 | 5-15秒 | < 30秒 |
| 缓存读取 | < 0.1秒 | < 1秒 |

### 缓存效果

- **首次调用**: ~1.5秒（网络请求）
- **缓存调用**: ~0.01秒（内存读取）
- **预期加速比**: > 5倍
- **实际加速比**: 通常100-150倍

## 常见问题

### Q1: 为什么有些测试返回空数据？

**A**: 这是正常的，原因包括：
- 节假日无交易（各市场节假日不同）
- 周末无交易
- 某些ticker可能暂时无新闻
- 商品期货无财务指标

测试已经适配这些情况，返回空列表是预期行为。

### Q2: 测试为什么需要这么长时间？

**A**: E2E测试调用真实API：
- 需要网络请求（1-3秒/ticker）
- 测试4个市场 × 多个功能
- 总时间约1-2分钟

如果需要更快，可以：
- 只运行部分测试
- 使用缓存（第二次运行会快得多）
- 考虑添加mock（但失去真实性）

### Q3: 如何调试失败的测试？

**A**: 使用以下选项：
```bash
# 显示详细输出
poetry run pytest tests/integration/test_e2e_multi_market.py::test_name -v -s

# 完整错误堆栈
poetry run pytest tests/integration/test_e2e_multi_market.py::test_name -v --tb=long

# 进入调试器
poetry run pytest tests/integration/test_e2e_multi_market.py::test_name -v --pdb
```

### Q4: 如何添加新的测试？

**A**: 参考现有测试模式：
```python
def test_new_feature(self, mixed_tickers, date_range):
    """测试新功能"""
    for market, ticker in mixed_tickers.items():
        result = api.new_function(ticker, date_range["start"], date_range["end"])

        # 验证
        assert isinstance(result, expected_type)
        # ... 更多验证
```

## 持续集成（CI）

### GitHub Actions配置

```yaml
- name: Run E2E tests
  run: |
    poetry run pytest tests/integration/test_e2e_multi_market.py -v --tb=short
```

### 推荐策略

1. **每次PR**: 运行完整E2E测试
2. **每日**: 运行更全面的测试（包括历史数据）
3. **每周**: 性能基准测试，记录趋势

## 测试报告

### 生成报告

运行测试并生成报告：

```bash
# 运行所有测试并生成覆盖率报告
poetry run pytest --cov=src --cov-report=html

# 查看报告
open htmlcov/index.html
```

### 报告内容

- 测试概述（通过率、执行时间）
- 市场覆盖情况
- 功能测试详情
- 性能数据
- 发现的问题
- 改进建议

## 最佳实践

### 1. 测试隔离

- 每个测试独立运行
- 不依赖测试顺序
- 使用fixtures提供数据

### 2. 错误处理

- 测试不应抛出未捕获异常
- 优雅处理网络错误
- 返回空列表而非None

### 3. 性能意识

- 使用缓存减少API调用
- 并行测试可以加速
- 监控测试执行时间

### 4. 文档完整

- 每个测试都有docstring
- 解释为什么某些行为是预期的
- 记录已知问题

## 相关文档

- [TROUBLESHOOTING.md](../TROUBLESHOOTING.md) - 问题排查和解决方案
- [ANTI_RATE_LIMIT.md](ANTI_RATE_LIMIT.md) - 反限流机制文档
- [TUSHARE_SETUP.md](TUSHARE_SETUP.md) - Tushare Pro 配置指南
- [CLAUDE.md](../CLAUDE.md) - 项目架构和开发指南

## 维护清单

### 定期检查（每月）

- [ ] 运行完整测试套件
- [ ] 检查性能是否退化
- [ ] 更新测试数据（ticker, 日期范围）
- [ ] 审查失败/跳过的测试

### 添加新市场时

- [ ] 添加对应的单元测试
- [ ] 在E2E测试中添加新ticker
- [ ] 更新测试文档
- [ ] 更新性能基准

### 修改API时

- [ ] 运行所有相关测试
- [ ] 检查向后兼容性
- [ ] 更新集成测试
- [ ] 更新测试文档

---

**最后更新**: 2026-03-14
**维护者**: AI Hedge Fund Team
**状态**: ✅ 所有测试通过
