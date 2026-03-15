# 故障排查指南

## ❌ 问题: 获取不到 A股/港股 数据

### 症状

```bash
poetry run python src/main.py --ticker 000001
```

输出错误：
```
[AKShare] Failed to get CN prices for 000001: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))
[YFinance] Too Many Requests. Rate limited. Try after a while.
[CNAdapter] No price data available from any source for 000001
```

### 根本原因

**不是代码问题！** 是数据源限流：

1. **AKShare**: 东方财富网检测到频繁请求，主动断开连接
2. **YFinance**: Yahoo Finance API 限流（429 错误）
3. **IP被标记**: 短时间内多次请求导致 IP 被标记为爬虫

### ✅ 验证诊断

运行以下命令确认问题：

```bash
# 测试美股（应该正常）
python3 -c "
from src.tools import api
prices = api.get_prices('AAPL', '2024-01-02', '2024-01-05')
print(f'US stock: {len(prices)} records')  # 应该显示 4 records
"

# 测试 A股（可能失败）
python3 -c "
from src.markets.sources.akshare_source import AKShareSource
source = AKShareSource()
prices = source.get_prices('000001', '2024-01-02', '2024-01-05')
print(f'CN stock: {len(prices)} records')  # 可能显示 0 records
"
```

如果美股正常、A股失败 → **确认是数据源限流问题**

---

## 🛠️ 解决方案

### 方案 1: 使用美股测试 ✅ (推荐)

```bash
# 美股数据使用 Financial Datasets API，不受限流影响
poetry run python src/main.py --ticker AAPL --analysts-all --model "MiniMax-M2.5"
poetry run python src/main.py --ticker MSFT,GOOGL,NVDA --analysts-all --model "MiniMax-M2.5"
```

### 方案 2: 等待冷却期 ⏰

```bash
# 等待 30-60 分钟后再试
echo "Waiting 30 minutes for rate limit reset..."
sleep 1800

# 然后重试
poetry run python src/main.py --ticker 000001 --analysts-all --model "MiniMax-M2.5"
```

### 方案 3: 使用 Tushare（推荐生产环境）🏆

Tushare 是更稳定的中国市场数据源：

#### 步骤 1: 注册获取 Token

访问 https://tushare.pro/register 注册并获取 token

#### 步骤 2: 配置环境变量

```bash
# 添加到 .env 文件
echo "TUSHARE_TOKEN=your_token_here" >> .env
```

#### 步骤 3: 安装依赖

```bash
poetry add tushare
```

#### 步骤 4: 启用 Tushare 数据源

编辑 `src/markets/cn_stock.py`：

```python
from src.markets.sources.tushare_source import TushareSource

data_sources = [
    TushareSource(),    # 优先使用 Tushare
    AKShareSource(),    # 备用
    YFinanceSource(),   # 备用
]
```

#### 步骤 5: 测试

```bash
poetry run python src/main.py --ticker 000001 --analysts-all --model "MiniMax-M2.5"
```

### 方案 4: 使用代理 🌐

```bash
# 配置代理
export HTTP_PROXY=http://your-proxy:port
export HTTPS_PROXY=http://your-proxy:port

# 运行
poetry run python src/main.py --ticker 000001 --analysts-all --model "MiniMax-M2.5"
```

### 方案 5: 增加缓存时间 💾

编辑 `src/data/cache.py`：

```python
# 将缓存时间从 5 分钟增加到 1 小时
DEFAULT_TTL = 3600  # 原来是 300
```

---

## 📊 数据源对比

| 数据源 | 市场 | 免费额度 | 稳定性 | 限流策略 | 推荐度 |
|--------|------|----------|--------|----------|--------|
| **Tushare Pro** | CN | 120次/分 | ⭐⭐⭐⭐⭐ | Token认证 | 🏆 生产环境首选 |
| **Financial Datasets** | US | 有限 | ⭐⭐⭐⭐⭐ | API Key | 🏆 美股首选 |
| **AKShare** | CN, HK | 无限 | ⭐⭐ | 反爬虫 | ⚠️ 测试环境 |
| **YFinance** | 全球 | 无限 | ⭐⭐⭐ | 429限流 | ⚠️ 备用 |

---

## 🔍 当前架构状态

### ✅ 已实现的功能

- [x] 多数据源架构（AKShare + YFinance）
- [x] 自动路由（CN/HK/US/Commodity）
- [x] 多源交叉验证
- [x] 数据缓存（5分钟）
- [x] 重试机制（指数退避）
- [x] 反限流延迟
- [x] 美股数据正常工作

### ⚠️ 当前限制

- AKShare 易触发限流
- YFinance 易触发限流
- 无 Tushare 集成（已提供代码）
- 缓存时间较短（5分钟）

---

## 🚀 快速验证

运行以下命令验证系统状态：

```bash
# 1. 测试美股（应该正常）
poetry run python src/main.py --ticker AAPL --analysts "warren_buffett" --model "MiniMax-M2.5"

# 2. 测试 A股（可能失败）
poetry run python src/main.py --ticker 000001 --analysts "warren_buffett" --model "MiniMax-M2.5"

# 3. 查看日志
# 如果看到 "Rate limited" 或 "Connection aborted" → 数据源限流
# 如果看到 "✓ Retrieved X records" → 数据获取成功
```

---

## 📝 最佳实践

### 开发环境

1. **使用美股测试**: `AAPL, MSFT, GOOGL`
2. **避免频繁请求**: 等待 5 分钟让缓存生效
3. **使用单个分析师**: `--analysts "warren_buffett"` 减少 LLM 调用

### 生产环境

1. **使用 Tushare Pro**: 注册并配置 token
2. **增加缓存时间**: 改为 1 小时
3. **监控限流日志**: 设置告警
4. **使用付费 API**: 更稳定可靠

---

## 🆘 获取帮助

如果问题持续存在：

1. **检查网络**: `ping baidu.com`
2. **清除缓存**: `rm -rf ~/.cache/ai-hedge-fund/`
3. **更新 AKShare**: `poetry add akshare@latest`
4. **查看日志**: 寻找具体错误信息
5. **使用代理**: 尝试不同的网络环境

---

## 📚 相关文档

- [数据源限流详细说明](docs/DATA_SOURCE_RATE_LIMITING.md)
- [反限流机制文档](docs/ANTI_RATE_LIMIT.md)
- [Tushare 官方文档](https://tushare.pro/document/2)
- [AKShare 官方文档](https://akshare.akfamily.xyz/)
