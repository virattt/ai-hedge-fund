#!/usr/bin/env python3
"""
商品适配器集成测试脚本

测试CommodityAdapter的实际功能：
1. 识别期货ticker
2. 获取真实的期货价格数据（yfinance）
3. 获取真实的新闻数据（Google News RSS）
4. 验证财务指标返回空字典
"""
from src.markets.commodity import CommodityAdapter
from datetime import datetime, timedelta


def test_commodity_adapter():
    """测试商品适配器的实际功能"""
    adapter = CommodityAdapter()

    print("=" * 60)
    print("商品期货适配器集成测试")
    print("=" * 60)

    # 测试1: ticker识别
    print("\n[测试1] Ticker识别")
    test_tickers = ["GC=F", "SI=F", "CL=F", "AAPL", "600000.SH"]
    for ticker in test_tickers:
        supported = adapter.supports_ticker(ticker)
        print(f"  {ticker}: {'✓ 支持' if supported else '✗ 不支持'}")

    # 测试2: 获取黄金期货价格（最近5天）
    print("\n[测试2] 获取黄金期货(GC=F)价格数据")
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")

    try:
        prices = adapter.get_prices("GC=F", start_date, end_date)
        if prices:
            print(f"  成功获取 {len(prices)} 条价格数据")
            latest = prices[-1]
            print(f"  最新数据: {latest['date']}")
            print(f"    开盘: ${latest['open']:.2f}")
            print(f"    收盘: ${latest['close']:.2f}")
            print(f"    最高: ${latest['high']:.2f}")
            print(f"    最低: ${latest['low']:.2f}")
            print(f"    成交量: {latest['volume']:,}")
        else:
            print("  ⚠ 未获取到价格数据（可能是非交易日）")
    except Exception as e:
        print(f"  ✗ 获取失败: {e}")

    # 测试3: 获取原油期货价格
    print("\n[测试3] 获取原油期货(CL=F)价格数据")
    try:
        prices = adapter.get_prices("CL=F", start_date, end_date)
        if prices:
            print(f"  成功获取 {len(prices)} 条价格数据")
            latest = prices[-1]
            print(f"  最新收盘价: ${latest['close']:.2f} (日期: {latest['date']})")
        else:
            print("  ⚠ 未获取到价格数据（可能是非交易日）")
    except Exception as e:
        print(f"  ✗ 获取失败: {e}")

    # 测试4: 获取新闻
    print("\n[测试4] 获取黄金期货新闻")
    try:
        news = adapter.get_company_news("GC=F", end_date, limit=3)
        if news:
            print(f"  成功获取 {len(news)} 条新闻")
            for i, item in enumerate(news, 1):
                print(f"\n  新闻 {i}:")
                print(f"    标题: {item['title'][:60]}...")
                print(f"    发布时间: {item['published']}")
                print(f"    来源: {item['source']}")
        else:
            print("  ⚠ 未获取到新闻（RSS可能暂时不可用）")
    except Exception as e:
        print(f"  ✗ 获取失败: {e}")

    # 测试5: 财务指标（应该返回空字典）
    print("\n[测试5] 获取财务指标（商品没有财务指标）")
    try:
        metrics = adapter.get_financial_metrics("GC=F", end_date)
        if metrics == {}:
            print("  ✓ 正确返回空字典（商品没有财务指标）")
        else:
            print(f"  ✗ 错误：应返回空字典，实际返回 {metrics}")
    except Exception as e:
        print(f"  ✗ 获取失败: {e}")

    # 测试6: 商品名称提取
    print("\n[测试6] 商品名称提取")
    test_cases = [
        ("GC=F", "Gold"),
        ("SI=F", "Silver"),
        ("CL=F", "Crude Oil"),
        ("NG=F", "Natural Gas"),
        ("XX=F", "XX"),  # 未知代码
    ]
    for ticker, expected in test_cases:
        name = adapter._extract_commodity_name(ticker)
        status = "✓" if name == expected else "✗"
        print(f"  {status} {ticker} -> {name} (预期: {expected})")

    print("\n" + "=" * 60)
    print("集成测试完成")
    print("=" * 60)


if __name__ == "__main__":
    test_commodity_adapter()
