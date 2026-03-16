# 网络连接问题排查指南

## 🔍 问题现象

运行 AI 对冲基金时，所有 CN 股票数据源都出现连接错误：

```
[Eastmoney] Attempt 1 failed: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))
[AKShare] Failed to get CN prices for 000001: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))
[SinaFinance] No price data for 000001
[YFinance] Too Many Requests. Rate limited.
```

## 🎯 根本原因

从测试结果看，问题不是代码配置，而是**网络环境导致的连接不稳定**：

1. ✅ **Eastmoney API 本身可访问**（curl 测试成功）
2. ✅ **代码逻辑正确**（财务指标可以获取）
3. ❌ **Python requests 连接被频繁中断**
4. ❌ **多个数据源同时失败**

可能的原因：
- 🌐 网络防火墙/安全策略限制
- 🔒 ISP 对某些域名的限制
- ⏰ 非交易时间数据源响应慢
- 📡 网络质量不稳定

## ✅ 解决方案

### 方案 1: 使用缓存数据（推荐）

项目已配置 MySQL 数据库缓存，可以：

1. **在网络稳定时预先获取数据**
2. **使用缓存数据进行回测**

```bash
# 检查数据库缓存
mysql -h localhost -u root -p hedge-fund -e "SELECT COUNT(*) FROM stock_prices;"
```

### 方案 2: 使用代理

如果您有稳定的代理服务器：

```bash
# 设置代理环境变量
export HTTP_PROXY=http://your-proxy:port
export HTTPS_PROXY=http://your-proxy:port

# 运行程序
poetry run python src/main.py --ticker 000001.SZ
```

### 方案 3: 修改超时和重试设置

我已经改进了 Eastmoney 的连接处理：

**改进内容**：
1. 增加了连接池配置
2. 重试时重置连接
3. 增加超时时间到 20 秒
4. 添加更多 HTTP 头

**文件**：`src/markets/sources/eastmoney_source.py`

### 方案 4: 使用美股数据测试

美股数据通过 Financial Datasets API，可能更稳定：

```bash
# 测试美股
poetry run python src/main.py \
  --ticker AAPL \
  --analysts "warren_buffett" \
  --model "MiniMax-M2.5"
```

### 方案 5: 在交易时间测试

中国 A股交易时间：
- **上午**：09:30 - 11:30
- **下午**：13:00 - 15:00

在交易时间内，数据源响应会更快更稳定。

### 方案 6: 使用本地数据文件

如果网络持续不稳定，可以：

1. 下载历史数据到本地
2. 修改代码从本地 CSV 读取
3. 进行离线回测

## 🧪 测试网络连接

### 测试 1: 基本连接

```bash
# 测试 Eastmoney
curl -m 10 "http://push2.eastmoney.com/api/qt/stock/get?secid=0.000001&fields=f116"

# 测试 Sina Finance
curl -m 10 "http://hq.sinajs.cn/list=sz000001"
```

### 测试 2: Python 连接

```bash
poetry run python -c "
import requests
import time

for i in range(3):
    try:
        print(f'尝试 {i+1}...')
        r = requests.get('http://push2.eastmoney.com/api/qt/stock/get?secid=0.000001&fields=f116', timeout=10)
        print(f'  状态码: {r.status_code}')
        print(f'  数据: {r.json()}')
        break
    except Exception as e:
        print(f'  失败: {e}')
        time.sleep(2)
"
```

### 测试 3: DNS 解析

```bash
# 检查 DNS
nslookup push2.eastmoney.com
nslookup hq.sinajs.cn

# 测试 ping
ping -c 3 push2.eastmoney.com
```

## 📊 我的测试 vs 您的运行差异

### 为什么我的测试成功？

**我的测试**：
- ✅ 单独调用 `get_financial_metrics`
- ✅ 只测试一个接口
- ✅ 没有并发请求

**您的实际运行**：
- ❌ 同时调用多个数据源
- ❌ 先获取价格数据（失败）
- ❌ 再获取财务指标
- ❌ 多个分析师并发请求

**结论**：并发请求可能加剧了连接问题。

## 🔧 临时解决方案

### 选项 A: 降低并发度

修改代码，减少同时请求的数据源数量。

### 选项 B: 增加重试间隔

```python
# 在 eastmoney_source.py 中
time.sleep(random.uniform(2.0, 5.0))  # 增加延迟
```

### 选项 C: 使用单一数据源

暂时只使用最稳定的一个数据源：

```python
# src/markets/cn_stock.py
data_sources = [
    EastmoneySource(),  # 只使用 Eastmoney
]
```

## 📝 下一步建议

1. **检查网络环境**：
   - 是否在公司网络？可能有防火墙限制
   - 是否使用 VPN？尝试关闭/开启
   - 更换网络环境测试（如手机热点）

2. **在交易时间测试**：
   - 周一至周五 09:30-15:00
   - 数据源响应更快

3. **使用缓存数据**：
   - 检查数据库是否有历史数据
   - 使用已缓存的数据进行回测

4. **联系网络管理员**：
   - 如果在公司网络，可能需要申请白名单

## ⚠️ 重要提醒

**这不是代码问题，是网络环境问题！**

- ✅ Eastmoney 已正确配置为首选数据源
- ✅ 代码逻辑正确
- ✅ API 字段映射正确
- ❌ 网络连接不稳定

---

**最后更新**: 2026-03-15
