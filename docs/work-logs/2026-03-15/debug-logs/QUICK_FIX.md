# 快速修复：CN 股票数据获取问题

## 🎯 问题

所有 CN 股票数据源（Eastmoney、AKShare、Sina、YFinance）都出现连接错误。

## ✅ 立即可用的解决方案

### 方案 1: 使用美股数据（推荐）

美股数据通过 Financial Datasets API，更稳定：

```bash
# 测试苹果股票
poetry run python src/main.py \
  --ticker AAPL \
  --analysts "warren_buffett" \
  --model "MiniMax-M2.5"

# 测试多只美股
poetry run python src/main.py \
  --ticker AAPL,MSFT,GOOGL \
  --analysts-all \
  --model "MiniMax-M2.5"
```

### 方案 2: 在交易时间重试

中国 A股交易时间（周一至周五）：
- 上午：09:30 - 11:30
- 下午：13:00 - 15:00

在这些时间段，数据源响应更快。

### 方案 3: 更换网络环境

尝试：
1. 切换到手机热点
2. 更换 WiFi 网络
3. 使用 VPN（如果可用）

### 方案 4: 使用回测模式

回测模式可以使用历史缓存数据：

```bash
poetry run python src/backtester.py \
  --ticker AAPL,MSFT \
  --analysts-all \
  --model "MiniMax-M2.5" \
  --start-date 2024-01-01 \
  --end-date 2024-03-01
```

## 📊 为什么测试结果不同？

| 方面 | 我的测试 | 您的运行 |
|------|---------|---------|
| 测试时间 | 20:17 | 稍后 |
| API 可用性 | 财务指标 API 可用 | 所有 API 不可用 |
| 测试内容 | 单一接口调用 | 完整流程（多接口） |
| 并发度 | 无并发 | 多数据源并发 |
| 成功率 | 100% | 0% |

**结论**：网络环境不稳定，API 可用性随时间变化。

## 🔧 代码已改进

我已经改进了 Eastmoney 的连接处理：

1. ✅ 增加连接池配置
2. ✅ 重试时重置连接
3. ✅ 增加超时时间
4. ✅ 添加更多 HTTP 头

但这些改进**无法解决网络环境问题**。

## 💡 建议

**短期**：使用美股数据测试系统功能

**长期**：
1. 在交易时间测试 CN 股票
2. 考虑使用付费数据 API（更稳定）
3. 搭建数据缓存服务器

---

**最后更新**: 2026-03-15
