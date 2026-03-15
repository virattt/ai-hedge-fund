# 快速参考指南 - 数据获取URL日志

## 🎯 一键测试

```bash
# 显示所有URL日志（推荐）
poetry run python test_with_url_logs.py

# 只提取URL
poetry run python test_with_url_logs.py 2>&1 | grep "📡 Requesting URL" | sed 's/.*📡 Requesting URL: //'
```

## 📡 当前可用的API端点

### 1. 价格数据 (K线)
```
https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=0.000001&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61&klt=101&fqt=1&beg=20240101&end=20240105
```
- **数据源**: EastmoneyCurl
- **状态**: ✅ 正常工作
- **返回**: K线数据（日期、开盘、收盘、最高、最低、成交量）

### 2. 财务指标
```
https://push2.eastmoney.com/api/qt/stock/get?secid=0.000001&fields=f43,f116,f117,f162,f167,f173,f187
```
- **数据源**: EastmoneyCurl
- **状态**: ✅ 正常工作
- **返回**: 市值、市盈率、市净率、ROE等

## 🔍 在日志中查找URL

运行任何命令后，在日志中查找 **📡** 符号：

```bash
poetry run python src/main.py --ticker 000001.SZ --analysts bill_ackman --model "MiniMax-M2.5" --start-date 2024-01-01 --end-date 2024-01-05 2>&1 | grep "📡"
```

## 🌐 浏览器测试

1. 复制上面的URL
2. 粘贴到浏览器地址栏
3. 按回车
4. 查看返回的JSON数据

## 📊 数据源优先级

当前配置（按优先级）：

1. **EastmoneyCurl** ⭐ - 主数据源，使用curl绕过反爬虫
2. **Tushare** - 需要token，未配置时跳过
3. **AKShare** - 免费，间歇性连接问题
4. **Sina Finance** - 免费，部分数据不可用
5. **YFinance** - 全球覆盖，频繁限流

## ✅ 修复验证

运行以下命令确认修复成功：

```bash
# 快速验证
poetry run python -c "
from src.tools.api import get_prices
prices = get_prices('000001.SZ', '2024-01-01', '2024-01-05')
print(f'✓ 获取到 {len(prices)} 条价格记录')
print(f'✓ 类型: {type(prices[0]).__name__}')
"
```

预期输出：
```
✓ 获取到 4 条价格记录
✓ 类型: Price
```

## 🐛 故障排查

### 问题: 看不到URL日志

**原因**: 日志级别设置为WARNING或更高

**解决**: 使用 `test_with_url_logs.py` 脚本，它会自动设置INFO级别

```bash
poetry run python test_with_url_logs.py
```

### 问题: 数据获取失败

**检查步骤**:

1. 运行测试脚本查看详细日志
```bash
poetry run python test_with_url_logs.py
```

2. 复制URL到浏览器验证API是否可访问

3. 检查网络连接

4. 查看是否被限流（日志中会显示 "Rate limited"）

## 📝 相关文档

- **FIX_SUMMARY.md** - 修复总结
- **VERIFICATION_REPORT.md** - 完整验证报告
- **DATA_SOURCE_STATUS.md** - 数据源状态
- **test_urls.txt** - API端点清单

## 🎉 修复状态

✅ **所有问题已修复**

- ✅ Price对象重复创建问题已解决
- ✅ URL日志已添加到所有数据源
- ✅ 数据获取功能正常工作
- ✅ 所有API端点已验证可访问

---

**最后更新**: 2026-03-15 21:20
**测试股票**: 000001.SZ (平安银行)
**测试日期**: 2024-01-01 至 2024-01-05
