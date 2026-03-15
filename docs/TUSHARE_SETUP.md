# Tushare Pro 配置指南

## 🎯 为什么使用 Tushare？

Tushare Pro 是中国市场最稳定的数据源：

- ✅ **稳定可靠**: Token 认证，不会被限流
- ✅ **免费额度**: 120 次/分钟（基础用户）
- ✅ **数据完整**: 完整的历史数据和财务指标
- ✅ **官方支持**: 有完善的文档和社区支持

相比之下：
- ❌ AKShare: 易触发反爬虫，连接经常断开
- ❌ YFinance: 限流严重（429 错误）

---

## 📝 配置步骤

### 步骤 1: 注册 Tushare Pro

1. 访问 **https://tushare.pro/register**
2. 使用手机号或邮箱注册（完全免费）
3. 注册成功后，登录账户

### 步骤 2: 获取 Token

1. 登录后进入 **https://tushare.pro/user/token**
2. 复制你的 Token（格式类似：`abcd1234efgh5678ijkl9012mnop3456qrst7890uvwx1234yz567890`）

### 步骤 3: 配置环境变量

打开项目根目录的 `.env` 文件，找到以下行：

```bash
TUSHARE_TOKEN=your-tushare-token-here
```

将 `your-tushare-token-here` 替换为你的实际 Token：

```bash
TUSHARE_TOKEN=abcd1234efgh5678ijkl9012mnop3456qrst7890uvwx1234yz567890
```

**注意**:
- ⚠️ Token 是私密信息，不要分享给他人
- ⚠️ 不要将 Token 提交到 Git 仓库（.env 已在 .gitignore 中）

### 步骤 4: 验证配置

运行测试脚本验证 Tushare 是否配置成功：

```bash
poetry run python -c "
import os
from dotenv import load_dotenv

load_dotenv()
token = os.getenv('TUSHARE_TOKEN')

if token and token != 'your-tushare-token-here':
    print('✅ Tushare token 已配置')
    print(f'   Token: {token[:10]}...{token[-10:]}')
else:
    print('❌ Tushare token 未配置或无效')
    print('   请在 .env 文件中设置 TUSHARE_TOKEN')
"
```

### 步骤 5: 测试数据获取

```bash
# 测试 Tushare 数据源
poetry run python -c "
from src.markets.sources.tushare_source import TushareSource

source = TushareSource()
prices = source.get_prices('000001', '2024-01-02', '2024-01-05')

if prices:
    print(f'✅ Tushare 工作正常! 获取到 {len(prices)} 条记录')
    print(f'   示例: {prices[0]}')
else:
    print('⚠️  未获取到数据，请检查:')
    print('   1. Token 是否正确')
    print('   2. 网络连接是否正常')
    print('   3. Ticker 格式是否正确')
"
```

### 步骤 6: 完整测试

运行完整的数据源测试：

```bash
poetry run python test_data_sources.py
```

预期输出：
```
✅ 美股数据    - 通过
✅ A股数据    - 通过  ← 应该变成通过了
⚠️  港股数据    - 失败 (Tushare 不支持港股)
✅ 市场路由器  - 通过
```

---

## 🚀 使用 Tushare

配置完成后，所有 A股数据请求会自动优先使用 Tushare：

```bash
# 测试单个 A股
poetry run python src/main.py \
  --ticker 000001 \
  --analysts "warren_buffett" \
  --model "MiniMax-M2.5"

# 测试多个 A股
poetry run python src/main.py \
  --ticker 000001,600000,000002 \
  --analysts-all \
  --model "MiniMax-M2.5"
```

---

## 📊 数据源优先级

配置 Tushare 后，CN 股票的数据源优先级为：

```
1. Tushare Pro    ← 优先使用（稳定、快速）
   ↓ 失败时
2. AKShare        ← 备用 1（免费但可能限流）
   ↓ 失败时
3. YFinance       ← 备用 2（全球覆盖）
```

查看当前配置：

```bash
poetry run python -c "
from src.markets.cn_stock import CNStockAdapter

adapter = CNStockAdapter()
print('CN 股票数据源:')
for i, source in enumerate(adapter.active_sources, 1):
    print(f'  {i}. {source.name}')
"
```

---

## 🔧 故障排查

### 问题 1: "Tushare is not available"

**原因**: Token 未配置或配置错误

**解决**:
```bash
# 检查 .env 文件
cat .env | grep TUSHARE_TOKEN

# 应该看到类似：
# TUSHARE_TOKEN=abcd1234...

# 如果是默认值，需要替换为真实 Token
```

### 问题 2: "权限不足" 或 "积分不足"

**原因**: 某些高级数据需要更高的权限等级

**解决**:
- 基础数据（价格、成交量）免费用户可用
- 高级财务指标需要积分（通过使用积累或购买）
- 查看权限说明: https://tushare.pro/document/2

### 问题 3: "No data returned"

**可能原因**:
1. Ticker 格式错误
2. 日期范围无数据（非交易日）
3. 网络连接问题

**调试**:
```bash
# 测试 Tushare 直接调用
poetry run python -c "
import tushare as ts
import os
from dotenv import load_dotenv

load_dotenv()
ts.set_token(os.getenv('TUSHARE_TOKEN'))
pro = ts.pro_api()

# 获取数据
df = pro.daily(ts_code='000001.SZ', start_date='20240102', end_date='20240105')
print(df)
"
```

### 问题 4: "Rate limit exceeded"

**原因**: 超过免费额度（120次/分钟）

**解决**:
- 基础用户通常不会遇到此问题
- 如果频繁请求，添加延迟或升级账户

---

## 📈 Tushare 权限等级

| 等级 | 积分 | 限流 | 获取方式 |
|------|------|------|---------|
| 注册用户 | 120 | 120次/分 | 免费注册 |
| Lv1 | 2000 | 200次/分 | 使用积累 |
| Lv2 | 5000 | 400次/分 | 使用积累 |
| Lv3 | 10000 | 500次/分 | 购买或积累 |

**获取积分方式**:
1. 每天签到: +1 积分
2. 分享文章: +5 积分
3. 使用接口: 逐步积累
4. 直接购买: https://tushare.pro/pricing

**对于本项目**: 免费的注册用户（120 积分）完全够用！

---

## 🎓 Tushare 使用技巧

### 1. 合理使用缓存

项目已实现 5 分钟缓存，避免重复请求：

```python
# src/data/cache.py
DEFAULT_TTL = 300  # 5 分钟

# 可以增加到 1 小时
DEFAULT_TTL = 3600
```

### 2. 批量获取数据

Tushare 支持批量获取，更高效：

```python
# 单次获取多个日期的数据
df = pro.daily(ts_code='000001.SZ', start_date='20240101', end_date='20241231')
```

### 3. 查看 API 调用次数

```bash
poetry run python -c "
import tushare as ts
import os
from dotenv import load_dotenv

load_dotenv()
ts.set_token(os.getenv('TUSHARE_TOKEN'))

# 查看今日调用情况
# （需要在 Tushare 网站查看: https://tushare.pro/user/token）
print('请访问 https://tushare.pro/user/token 查看今日调用次数')
"
```

---

## 📚 相关资源

- **Tushare 官网**: https://tushare.pro
- **注册页面**: https://tushare.pro/register
- **Token 管理**: https://tushare.pro/user/token
- **API 文档**: https://tushare.pro/document/2
- **数据字典**: https://tushare.pro/document/2?doc_id=25
- **社区论坛**: https://waditu.com

---

## ✅ 配置完成检查清单

- [ ] 在 Tushare 官网注册账号
- [ ] 获取 API Token
- [ ] 在 `.env` 文件中配置 `TUSHARE_TOKEN`
- [ ] 运行 `poetry run python test_data_sources.py` 验证
- [ ] 测试获取 A股数据成功

完成以上步骤后，你就可以稳定地获取 A股数据了！

---

**最后更新**: 2026-03-15
