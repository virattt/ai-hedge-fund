#!/usr/bin/env python3
"""测试数据获取并显示所有URL日志"""

import logging
import sys

# 设置详细日志
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:%(name)s:%(message)s',
    stream=sys.stdout
)

from src.tools.api import get_prices, get_financial_metrics

print("=" * 80)
print("测试数据获取 - 显示所有URL日志")
print("=" * 80)

ticker = "000001.SZ"
start_date = "2024-01-01"
end_date = "2024-01-05"

print(f"\n股票: {ticker}")
print(f"日期: {start_date} 至 {end_date}")
print("\n" + "=" * 80)
print("获取价格数据...")
print("-" * 80)

prices = get_prices(ticker, start_date, end_date)

print("\n" + "=" * 80)
print(f"✓ 获取到 {len(prices)} 条价格记录")

if prices:
    print("\n示例数据:")
    for i, price in enumerate(prices[:3], 1):
        print(f"  {i}. {price.time}: 开盘={price.open}, 收盘={price.close}")

print("\n" + "=" * 80)
print("获取财务指标...")
print("-" * 80)

metrics = get_financial_metrics(ticker, end_date)

print("\n" + "=" * 80)
if metrics:
    print(f"✓ 获取到财务指标")
    print("\n关键指标:")
    print(f"  市值: {metrics.get('market_cap', 'N/A')}")
    print(f"  市盈率: {metrics.get('price_to_earnings_ratio', 'N/A')}")
    print(f"  市净率: {metrics.get('price_to_book_ratio', 'N/A')}")
    print(f"  ROE: {metrics.get('return_on_equity', 'N/A')}")
else:
    print("✗ 未能获取财务指标")

print("\n" + "=" * 80)
print("✅ 测试完成！")
print("\n在上面的日志中查找 📡 符号可以看到所有请求的URL")
print("=" * 80)
