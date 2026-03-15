# Eastmoney API 访问问题解决方案

## 🎯 问题根源

**发现**：Eastmoney API 需要 **cookies** 才能访问！

### 测试结果

| 工具 | 无 Cookies | 有 Cookies |
|------|-----------|-----------|
| curl | ❌ 失败 | ✅ 成功 |
| Python requests | ❌ 失败 | ❌ 失败 |

### 关键发现

1. **curl 带 cookies 可以成功**：
   ```bash
   curl 'https://push2.eastmoney.com/api/qt/stock/get?secid=0.000001&fields=f116' \
     -b 'qgqp_b_id=...; st_nvi=...; mtp=1'
   # 返回: {"rc":0,"data":{"f116":212106685904.13999}}
   ```

2. **Python requests 即使带 cookies 也失败**：
   - 同样的 cookies
   - 同样的 headers
   - 但是 `RemoteDisconnected` 错误

3. **问题在于 TLS/HTTP 层**：
   - curl 使用 libcurl (C 库)
   - Python requests 使用 urllib3 (Python 库)
   - Eastmoney 服务器能识别出差异并拒绝连接

## 💡 解决方案

### 方案 1: 使用 curl_cffi（推荐）

`curl_cffi` 是 curl 的 Python 绑定，使用相同的底层库：

```python
from curl_cffi import requests

cookies = {
    'qgqp_b_id': '815f755023542909e5d7e12bb425b596',
    'st_nvi': 'ScjgG2HuISz39_tWj_aok2a2e',
    'mtp': '1',
}

response = requests.get(
    'https://push2.eastmoney.com/api/qt/stock/get?secid=0.000001&fields=f116',
    cookies=cookies,
    impersonate='chrome',  # 模拟 Chrome 浏览器
    timeout=10
)
```

### 方案 2: 使用 subprocess 调用 curl

最简单但不优雅：

```python
import subprocess
import json

result = subprocess.run([
    'curl', '-s',
    'https://push2.eastmoney.com/api/qt/stock/get?secid=0.000001&fields=f116',
    '-b', 'qgqp_b_id=...; st_nvi=...; mtp=1',
    '-H', 'User-Agent: Mozilla/5.0...'
], capture_output=True, text=True)

data = json.loads(result.stdout)
```

### 方案 3: 放弃 Eastmoney

使用更稳定的数据源：
1. **Tushare**（注册获取 token）
2. **美股数据**（Financial Datasets API）

## 🔧 下一步操作

### 选项 A: 修改 Eastmoney 源使用 curl_cffi

需要修改 `src/markets/sources/eastmoney_source.py`：

```python
# 替换
import requests
# 为
from curl_cffi import requests

# 在 get 请求中添加
response = requests.get(url, impersonate='chrome', ...)
```

### 选项 B: 使用 subprocess 临时方案

最快的解决方案，但不优雅。

### 选项 C: 暂时禁用 Eastmoney

修改 `src/markets/cn_stock.py`，将 Eastmoney 从数据源列表中移除：

```python
data_sources = [
    # EastmoneySource(),  # 暂时禁用
    TushareSource(),
    AKShareSource(),
    ...
]
```

## 📊 技术细节

### 为什么 curl 可以但 Python requests 不行？

1. **TLS 指纹不同**：
   - curl 使用 OpenSSL/BoringSSL
   - requests 使用 Python 的 ssl 模块
   - 服务器能检测出差异

2. **HTTP/2 实现不同**：
   - curl 有成熟的 HTTP/2 支持
   - requests 通过 urllib3 的 HTTP/2 支持不完整

3. **连接管理不同**：
   - curl 的连接池管理更接近浏览器
   - requests 的行为可能被识别为爬虫

### Eastmoney 的反爬虫机制

1. ✅ 需要特定 cookies
2. ✅ 检测 TLS 指纹
3. ✅ 检测 HTTP 客户端特征
4. ⚠️  可能还有其他检测（如请求频率）

## 🎯 推荐方案

**立即可用**：使用美股数据测试
```bash
poetry run python src/main.py --ticker AAPL --analysts "warren_buffett" --model "MiniMax-M2.5"
```

**短期方案**：修改代码使用 curl 命令（subprocess）

**长期方案**：
1. 注册 Tushare 获取稳定的 CN 股票数据
2. 或者使用 curl_cffi 重写 Eastmoney 源

---

**结论**：Eastmoney 的反爬虫机制非常严格，需要使用更底层的工具（如 curl）或真实浏览器才能访问。Python requests 即使完全模拟 curl 的请求也会被识别并拒绝。
