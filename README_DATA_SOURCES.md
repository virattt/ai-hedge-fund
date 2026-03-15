# 数据源说明与使用指南

## 📊 当前数据源架构

### 架构层次

```
┌─────────────────────────────────────────┐
│         MarketRouter (路由层)            │
│   自动识别ticker并路由到对应适配器        │
└─────────────────────────────────────────┘
                    │
        ┌───────────┼───────────┬──────────┐
        │           │           │          │
   ┌────▼────┐ ┌───▼────┐ ┌───▼────┐ ┌───▼────┐
   │ CN Stock│ │HK Stock│ │US Stock│ │Commodity│
   │ Adapter │ │Adapter │ │Adapter │ │ Adapter│
   └────┬────┘ └───┬────┘ └───┬────┘ └───┬────┘
        │          │          │          │
   ┌────▼────┐ ┌──▼──┐  ┌───▼────┐     │
   │ AKShare │ │AKShare│ │Financial│    (无)
   │         │ │       │ │Datasets│
   └─────────┘ │YFinance│ │  API  │
               └───────┘ └────────┘
```

### 数据源列表

| 数据源 | 支持市场 | 状态 | 限流 | 推荐用途 |
|--------|---------|------|------|---------|
| **Financial Datasets API** | US | ✅ 正常 | API Key 限制 | 🏆 美股生产环境 |
| **AKShare** | CN, HK | ⚠️ 易限流 | 反爬虫 | 测试环境 |
| **YFinance** | 全球 | ⚠️ 易限流 | 429 限流 | 备用数据源 |
| **Tushare Pro** | CN | 📝 待集成 | Token 认证 | 🏆 A股生产环境 |

---

## 🚀 快速开始

### 1. 测试数据源状态

```bash
# 运行测试脚本
poetry run python test_data_sources.py
```

**预期输出**:
```
✅ 美股数据    - 通过
⚠️  A股数据    - 失败 (限流)
⚠️  港股数据    - 失败 (限流)
✅ 市场路由器  - 通过
```

### 2. 使用美股（推荐）

```bash
# 单个股票
poetry run python src/main.py \
  --ticker AAPL \
  --analysts-all \
  --model "MiniMax-M2.5"

# 多个股票
poetry run python src/main.py \
  --ticker AAPL,MSFT,GOOGL,NVDA \
  --analysts-all \
  --model "MiniMax-M2.5"
```

### 3. 使用 A股/港股

**注意**: 由于限流问题，A股/港股数据可能获取失败。

```bash
# A股
poetry run python src/main.py \
  --ticker 000001 \
  --analysts "warren_buffett" \
  --model "MiniMax-M2.5"

# 港股
poetry run python src/main.py \
  --ticker 0700.HK \
  --analysts "warren_buffett" \
  --model "MiniMax-M2.5"
```

如果失败，请参考下面的解决方案。

---

## 🔧 解决 A股/港股 限流问题

### 方案 1: 等待冷却期 ⏰

**最简单的方法**，等待 30-60 分钟让限流计数器重置：

```bash
# 等待 30 分钟
echo "Waiting for rate limit cooldown..."
sleep 1800

# 重试
poetry run python src/main.py --ticker 000001 --analysts-all --model "MiniMax-M2.5"
```

### 方案 2: 集成 Tushare Pro 🏆

**推荐生产环境使用**，Tushare 是最稳定的中国市场数据源。

#### 步骤 1: 注册获取 Token

1. 访问 https://tushare.pro/register
2. 注册账号（免费）
3. 获取 API Token

#### 步骤 2: 安装依赖

```bash
poetry add tushare
```

#### 步骤 3: 配置环境变量

在 `.env` 文件中添加：

```bash
TUSHARE_TOKEN=your_token_here
```

#### 步骤 4: 启用 Tushare

编辑 `src/markets/cn_stock.py`:

```python
from src.markets.sources.tushare_source import TushareSource

def __init__(self, validator: Optional[DataValidator] = None):
    data_sources = [
        TushareSource(),    # 优先使用
        AKShareSource(),    # 备用
        YFinanceSource(),   # 备用
    ]
    # ...
```

#### 步骤 5: 测试

```bash
poetry run python src/main.py --ticker 000001 --analysts-all --model "MiniMax-M2.5"
```

#### Tushare 优势

- ✅ 稳定可靠（Token 认证）
- ✅ 免费用户 120 次/分钟
- ✅ 付费用户 500 次/分钟
- ✅ 完整的历史数据
- ✅ 财务指标支持

### 方案 3: 使用代理 🌐

```bash
# 配置代理
export HTTP_PROXY=http://your-proxy:port
export HTTPS_PROXY=http://your-proxy:port

# 运行
poetry run python src/main.py --ticker 000001 --analysts-all --model "MiniMax-M2.5"
```

### 方案 4: 增加缓存时间 💾

编辑 `src/data/cache.py`:

```python
# 将缓存时间从 5 分钟增加到 1 小时
DEFAULT_TTL = 3600  # 原来是 300
```

这样已经获取过的数据会缓存更长时间，减少请求次数。

---

## 📝 Ticker 格式说明

### 美股

```
AAPL        ✅ Apple
MSFT        ✅ Microsoft
GOOGL       ✅ Google
NVDA        ✅ NVIDIA
TSLA        ✅ Tesla
```

### A股

```
000001      ✅ 平安银行 (深圳)
000001.SZ   ✅ 平安银行 (完整格式)
600000      ✅ 浦发银行 (上海)
600000.SH   ✅ 浦发银行 (完整格式)
```

### 港股

```
0700.HK     ✅ 腾讯控股
00700       ✅ 腾讯控股 (简写)
9988.HK     ✅ 阿里巴巴
```

### 商品期货

```
GC=F        ✅ 黄金期货
CL=F        ✅ 原油期货
```

---

## 🔍 故障排查

### 问题 1: "No price data available"

**症状**:
```
[CNAdapter] No price data available from any source for 000001
```

**原因**: 数据源限流

**解决**:
1. 等待 30-60 分钟
2. 使用美股测试
3. 集成 Tushare
4. 使用代理

### 问题 2: "Connection aborted"

**症状**:
```
[AKShare] Failed to get CN prices: ('Connection aborted.', RemoteDisconnected(...))
```

**原因**: AKShare 反爬虫机制

**解决**:
1. 等待冷却期
2. 切换到 Tushare
3. 使用代理

### 问题 3: "Too Many Requests"

**症状**:
```
[YFinance] Too Many Requests. Rate limited. Try after a while.
```

**原因**: Yahoo Finance API 限流

**解决**:
1. 等待冷却期
2. 使用其他数据源

---

## 📊 性能优化建议

### 开发环境

1. **使用缓存**: 数据会自动缓存 5 分钟
2. **减少分析师**: 使用 `--analysts "warren_buffett"` 而不是 `--analysts-all`
3. **使用美股**: 优先测试美股数据
4. **避免频繁请求**: 等待缓存过期再重新请求

### 生产环境

1. **使用 Tushare Pro**: 注册并配置 token
2. **增加缓存时间**: 改为 1 小时或更长
3. **监控限流**: 设置日志告警
4. **使用付费 API**: 更稳定可靠
5. **实现请求队列**: 控制并发请求数量

---

## 🧪 测试命令

### 测试单个数据源

```bash
# 测试 AKShare
python3 -c "
from src.markets.sources.akshare_source import AKShareSource
source = AKShareSource()
prices = source.get_prices('000001', '2024-01-02', '2024-01-05')
print(f'Got {len(prices)} records')
"

# 测试 YFinance
python3 -c "
from src.markets.sources.yfinance_source import YFinanceSource
source = YFinanceSource()
prices = source.get_prices('AAPL', '2024-01-02', '2024-01-05')
print(f'Got {len(prices)} records')
"

# 测试 Financial Datasets API
python3 -c "
from src.tools import api
prices = api.get_prices('AAPL', '2024-01-02', '2024-01-05')
print(f'Got {len(prices)} records')
"
```

### 测试市场路由

```bash
python3 -c "
from src.markets.router import MarketRouter
router = MarketRouter()

# 测试路由
for ticker in ['AAPL', '000001', '0700.HK', 'GC=F']:
    adapter = router.route(ticker)
    print(f'{ticker:12} -> {adapter.market}')
"
```

### 清除缓存

```bash
# 查看缓存
ls -lh ~/.cache/ai-hedge-fund/

# 清除缓存
rm -rf ~/.cache/ai-hedge-fund/
```

---

## 📚 相关文档

- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - 完整故障排查指南
- [docs/DATA_SOURCE_RATE_LIMITING.md](docs/DATA_SOURCE_RATE_LIMITING.md) - 限流问题详解
- [docs/ANTI_RATE_LIMIT.md](docs/ANTI_RATE_LIMIT.md) - 反限流机制说明
- [CLAUDE.md](CLAUDE.md) - 项目开发指南

---

## 🆘 获取帮助

如果遇到问题：

1. **运行测试脚本**: `poetry run python test_data_sources.py`
2. **查看日志**: 寻找 "Rate limited" 或 "Connection aborted"
3. **清除缓存**: `rm -rf ~/.cache/ai-hedge-fund/`
4. **检查网络**: `ping baidu.com`
5. **查看文档**: [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

---

## ✅ 验证成功的标志

运行成功时应该看到：

```bash
poetry run python src/main.py --ticker AAPL --analysts "warren_buffett" --model "MiniMax-M2.5"

# 输出应包含:
✅ 数据库连接成功
✅ 数据库表初始化完成
 ✓ Warren Buffett    [AAPL] Done
 ✓ Portfolio Manager [AAPL] Done
 ✓ Risk Management   [AAPL] Done
✅ 保存交易决策和分析师信号到数据库

# 交易决策表格
+--------+---------+----------+
| 操作   | 数量    | 置信度   |
+--------+---------+----------+
| 买入   | 100     | 85.0%    |
+--------+---------+----------+
```

---

**最后更新**: 2026-03-15
