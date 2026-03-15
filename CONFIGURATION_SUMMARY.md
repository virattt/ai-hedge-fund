# Tushare 配置总结

## ✅ 已完成的配置

### 1. 依赖安装

```bash
✅ poetry add tushare  # 已安装 v1.4.25
```

### 2. 环境变量配置

在 `.env` 文件中已添加：

```bash
# Tushare Pro - Chinese stock data
# Register at: https://tushare.pro/register
TUSHARE_TOKEN=your-tushare-token-here
```

**⚠️ 需要你手动操作**: 将 `your-tushare-token-here` 替换为你的实际 Token

### 3. 代码集成

已更新 `src/markets/cn_stock.py`，数据源优先级：

```python
1. TushareSource()   ← 优先（稳定、快速）
2. AKShareSource()   ← 备用 1（免费但限流）
3. YFinanceSource()  ← 备用 2（全球覆盖）
```

### 4. 文档和工具

已创建：
- ✅ `docs/TUSHARE_SETUP.md` - 详细配置指南
- ✅ `TUSHARE_QUICKSTART.md` - 快速配置（5分钟）
- ✅ `setup_tushare.sh` - 自动配置脚本
- ✅ `test_data_sources.py` - 数据源测试脚本

---

## 🎯 你需要做的（3步）

### 方式 1: 自动配置（推荐）

```bash
./setup_tushare.sh
```

脚本会引导你完成所有步骤。

### 方式 2: 手动配置

#### 步骤 1: 注册 Tushare

访问 https://tushare.pro/register 注册（免费）

#### 步骤 2: 获取 Token

登录后访问 https://tushare.pro/user/token 复制 Token

#### 步骤 3: 配置 Token

编辑 `.env` 文件：

```bash
# 将这行
TUSHARE_TOKEN=your-tushare-token-here

# 改为（粘贴你的实际 Token）
TUSHARE_TOKEN=abcd1234efgh5678ijkl9012mnop3456qrst7890uvwx1234yz567890
```

---

## ✅ 验证配置

### 方法 1: 运行测试脚本

```bash
poetry run python test_data_sources.py
```

预期输出：
```
✅ 美股数据    - 通过
✅ A股数据    - 通过  ← 配置成功后应该通过
⚠️  港股数据    - 失败 (Tushare 不支持港股)
✅ 市场路由器  - 通过
```

### 方法 2: 直接测试 A股

```bash
poetry run python src/main.py \
  --ticker 000001 \
  --analysts "warren_buffett" \
  --model "MiniMax-M2.5"
```

如果能获取到数据并生成交易决策，说明配置成功！

---

## 📊 配置前后对比

### 配置前

```
❌ A股数据获取失败
   - AKShare: Connection aborted
   - YFinance: Too Many Requests
   - 结果: No data available
```

### 配置后

```
✅ A股数据获取成功
   - Tushare: ✓ 4 条记录 (稳定)
   - 结果: 成功生成交易决策
```

---

## 🎓 使用示例

### 单个 A股

```bash
poetry run python src/main.py \
  --ticker 000001 \
  --analysts "warren_buffett,charlie_munger" \
  --model "MiniMax-M2.5"
```

### 多个 A股

```bash
poetry run python src/main.py \
  --ticker 000001,600000,000002,600519 \
  --analysts-all \
  --model "MiniMax-M2.5"
```

### 混合市场

```bash
poetry run python src/main.py \
  --ticker AAPL,000001,0700.HK \
  --analysts-all \
  --model "MiniMax-M2.5"
```

---

## 🔧 故障排查

### 问题: "Tushare is not available"

**检查 Token 配置**:

```bash
cat .env | grep TUSHARE_TOKEN
```

应该看到你的实际 Token，而不是 `your-tushare-token-here`

### 问题: "No data returned"

**测试 Tushare 连接**:

```bash
poetry run python -c "
from src.markets.sources.tushare_source import TushareSource
source = TushareSource()
prices = source.get_prices('000001', '2024-01-02', '2024-01-05')
print(f'获取到 {len(prices)} 条记录')
"
```

### 问题: 仍然获取不到数据

1. 检查 Token 是否正确
2. 检查网络连接
3. 查看详细日志: `docs/TUSHARE_SETUP.md`

---

## 📚 相关文档

| 文档 | 用途 |
|------|------|
| `TUSHARE_QUICKSTART.md` | 快速配置（5分钟） |
| `docs/TUSHARE_SETUP.md` | 详细配置和故障排查 |
| `README_DATA_SOURCES.md` | 数据源使用指南 |
| `TROUBLESHOOTING.md` | 完整故障排查 |

---

## 🎉 配置完成后的好处

1. ✅ **稳定获取 A股数据** - 不再受限流困扰
2. ✅ **快速响应** - Tushare API 速度快
3. ✅ **完整数据** - 历史数据和财务指标齐全
4. ✅ **免费使用** - 基础用户 120 次/分钟完全够用
5. ✅ **官方支持** - 有完善的文档和社区

---

## 📞 需要帮助？

- **Tushare 官网**: https://tushare.pro
- **API 文档**: https://tushare.pro/document/2
- **注册页面**: https://tushare.pro/register
- **Token 管理**: https://tushare.pro/user/token

---

**最后更新**: 2026-03-15

**下一步**: 按照上面的步骤配置 Token，然后运行测试验证！
