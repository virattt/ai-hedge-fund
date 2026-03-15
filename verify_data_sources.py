#!/usr/bin/env python3
"""验证所有数据源的可用性和URL访问情况"""

import logging
from src.markets.cn_stock import CNStockAdapter

# 设置日志级别为INFO以查看详细日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    print("=" * 80)
    print("验证中国A股数据源")
    print("=" * 80)

    # 初始化适配器
    adapter = CNStockAdapter()

    print(f"\n配置的数据源: {[s.name for s in adapter.data_sources]}")
    print("\n" + "=" * 80)

    # 测试股票代码
    ticker = "000001"
    start_date = "2024-01-01"
    end_date = "2024-01-10"

    print(f"\n测试股票: {ticker}")
    print(f"日期范围: {start_date} 至 {end_date}")
    print("\n" + "=" * 80)

    # 获取价格数据
    print("\n1. 获取价格数据...")
    print("-" * 80)
    prices = adapter.get_prices(ticker, start_date, end_date)
    print(f"\n✓ 成功获取 {len(prices)} 条价格记录")

    if prices:
        print(f"\n示例数据 (前3条):")
        for i, price in enumerate(prices[:3], 1):
            print(f"  {i}. 日期: {price.time}, 开盘: {price.open}, 收盘: {price.close}")

    # 获取财务指标
    print("\n" + "=" * 80)
    print("\n2. 获取财务指标...")
    print("-" * 80)
    metrics = adapter.get_financial_metrics(ticker, end_date)

    if metrics:
        print(f"\n✓ 成功获取财务指标")
        print(f"\n关键指标:")
        print(f"  - 市值: {metrics.get('market_cap', 'N/A')}")
        print(f"  - 市盈率: {metrics.get('price_to_earnings_ratio', 'N/A')}")
        print(f"  - 市净率: {metrics.get('price_to_book_ratio', 'N/A')}")
        print(f"  - ROE: {metrics.get('return_on_equity', 'N/A')}")
    else:
        print(f"\n✗ 未能获取财务指标")

    print("\n" + "=" * 80)
    print("\n✅ 验证完成！")
    print("\n所有URL已在日志中显示（查找 📡 符号）")
    print("=" * 80)

if __name__ == "__main__":
    main()
