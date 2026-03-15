#!/usr/bin/env python3
"""Test Eastmoney integration in CN stock adapter."""
import logging
from src.markets.cn_stock import CNStockAdapter
from datetime import datetime, timedelta

# 设置详细日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_eastmoney_integration():
    """Test Eastmoney as primary data source."""
    print("=" * 80)
    print("测试 Eastmoney 集成")
    print("=" * 80)

    # 初始化适配器
    adapter = CNStockAdapter()

    # 显示数据源优先级
    print("\n✅ 数据源优先级:")
    for i, source in enumerate(adapter.active_sources, 1):
        print(f"  {i}. {source.name}")

    # 测试股票
    ticker = "000001"  # 平安银行
    end_date = datetime.now()
    start_date = end_date - timedelta(days=5)

    # 测试价格数据
    print(f"\n📊 测试价格数据 ({ticker} - 平安银行):")
    print(f"   日期范围: {start_date.strftime('%Y-%m-%d')} 到 {end_date.strftime('%Y-%m-%d')}")

    try:
        prices = adapter.get_prices(
            ticker,
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d')
        )
        if prices:
            print(f"   ✓ 成功获取 {len(prices)} 条记录")
            if prices:
                latest = prices[-1]
                print(f"   最新数据:")
                print(f"     - 日期: {latest['time'][:10]}")
                print(f"     - 收盘价: {latest['close']}")
                print(f"     - 成交量: {latest['volume']:,}")
        else:
            print("   ✗ 未获取到价格数据")
    except Exception as e:
        print(f"   ✗ 价格数据错误: {e}")

    # 测试财务指标
    print(f"\n💰 测试财务指标 ({ticker}):")
    try:
        metrics = adapter.get_financial_metrics(ticker, end_date.strftime('%Y-%m-%d'))
        if metrics:
            print(f"   ✓ 成功获取财务指标")
            print(f"     - 总市值: {metrics['market_cap']/1e8:.2f} 亿 CNY")
            print(f"     - 市盈率 (PE): {metrics['price_to_earnings_ratio']}")
            print(f"     - 市净率 (PB): {metrics['price_to_book_ratio']}")
            print(f"     - ROE: {metrics['return_on_equity']}%")
            print(f"     - 毛利率: {metrics.get('gross_margin', 'N/A')}%")

            # 检查数据来源
            if 'source' in metrics:
                print(f"     - 数据来源: {metrics['source']}")
        else:
            print("   ✗ 未获取到财务指标")
    except Exception as e:
        print(f"   ✗ 财务指标错误: {e}")

    print("\n" + "=" * 80)
    print("✅ 测试完成")
    print("=" * 80)

if __name__ == "__main__":
    test_eastmoney_integration()
