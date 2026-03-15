#!/usr/bin/env python3
"""
数据源测试脚本

快速测试各个市场的数据源是否正常工作
"""
import sys
from datetime import datetime, timedelta
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def test_us_stock():
    """测试美股数据"""
    print("\n" + "="*60)
    print("测试 1: 美股数据 (AAPL)")
    print("="*60)

    try:
        from src.tools import api

        ticker = 'AAPL'
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')

        prices = api.get_prices(ticker, start_date, end_date)

        if prices:
            print(f"✅ 成功! 获取到 {len(prices)} 条价格记录")
            print(f"   示例: {prices[0]}")
            return True
        else:
            print(f"❌ 失败: 未获取到数据")
            return False

    except Exception as e:
        print(f"❌ 错误: {e}")
        return False


def test_cn_stock():
    """测试 A股数据"""
    print("\n" + "="*60)
    print("测试 2: A股数据 (000001)")
    print("="*60)

    try:
        from src.markets.cn_stock import CNStockAdapter

        adapter = CNStockAdapter()
        print(f"可用数据源: {[s.name for s in adapter.active_sources]}")

        ticker = '000001'
        prices = adapter.get_prices(ticker, '2024-01-02', '2024-01-05')

        if prices:
            print(f"✅ 成功! 获取到 {len(prices)} 条价格记录")
            print(f"   示例: {prices[0]}")
            return True
        else:
            print(f"⚠️  未获取到数据 (可能是限流)")
            print(f"   建议: 等待 30 分钟后重试，或使用 Tushare")
            return False

    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_hk_stock():
    """测试港股数据"""
    print("\n" + "="*60)
    print("测试 3: 港股数据 (0700.HK)")
    print("="*60)

    try:
        from src.markets.hk_stock import HKStockAdapter

        adapter = HKStockAdapter()
        print(f"可用数据源: {[s.name for s in adapter.active_sources]}")

        ticker = '0700.HK'
        prices = adapter.get_prices(ticker, '2024-01-02', '2024-01-05')

        if prices:
            print(f"✅ 成功! 获取到 {len(prices)} 条价格记录")
            print(f"   示例: {prices[0]}")
            return True
        else:
            print(f"⚠️  未获取到数据 (可能是限流)")
            return False

    except Exception as e:
        print(f"❌ 错误: {e}")
        return False


def test_market_router():
    """测试市场路由器"""
    print("\n" + "="*60)
    print("测试 4: 市场路由器")
    print("="*60)

    try:
        from src.markets.router import MarketRouter

        router = MarketRouter()

        test_cases = [
            ('AAPL', 'US'),
            ('000001', 'CN'),
            ('600000.SH', 'CN'),
            ('0700.HK', 'HK'),
            ('GC=F', 'COMMODITY'),
        ]

        all_passed = True
        for ticker, expected_market in test_cases:
            try:
                adapter = router.route(ticker)
                actual_market = adapter.market

                if actual_market == expected_market:
                    print(f"✅ {ticker:12} -> {actual_market:10} (正确)")
                else:
                    print(f"❌ {ticker:12} -> {actual_market:10} (期望: {expected_market})")
                    all_passed = False

            except Exception as e:
                print(f"❌ {ticker:12} -> 路由失败: {e}")
                all_passed = False

        return all_passed

    except Exception as e:
        print(f"❌ 错误: {e}")
        return False


def print_summary(results):
    """打印测试摘要"""
    print("\n" + "="*60)
    print("测试摘要")
    print("="*60)

    total = len(results)
    passed = sum(results.values())
    failed = total - passed

    for test_name, result in results.items():
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name:20} {status}")

    print(f"\n总计: {total} 个测试, {passed} 个通过, {failed} 个失败")

    if failed > 0:
        print("\n💡 提示:")
        print("  - 如果美股通过、A股/港股失败 → 数据源限流")
        print("  - 解决方案:")
        print("    1. 等待 30-60 分钟后重试")
        print("    2. 使用 Tushare Pro (需要注册)")
        print("    3. 使用代理")
        print("  - 详见: TROUBLESHOOTING.md")


def main():
    """主函数"""
    print("="*60)
    print("AI Hedge Fund - 数据源测试")
    print("="*60)
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    results = {}

    # 运行测试
    results['美股数据'] = test_us_stock()
    results['A股数据'] = test_cn_stock()
    results['港股数据'] = test_hk_stock()
    results['市场路由器'] = test_market_router()

    # 打印摘要
    print_summary(results)

    # 返回退出码
    sys.exit(0 if all(results.values()) else 1)


if __name__ == '__main__':
    main()
