#!/usr/bin/env python3
"""
验证多个A股股票的财务数据格式

检查ROE、毛利率等百分比字段是否在合理范围内(0-1)
"""

from src.tools.api import get_financial_metrics


def verify_ticker(ticker: str, end_date: str = "2024-03-01"):
    """验证单个股票的数据格式"""
    print(f"\n{'='*60}")
    print(f"验证股票: {ticker}")
    print(f"{'='*60}")

    try:
        metrics = get_financial_metrics(ticker, end_date, period='ttm', limit=1)

        if not metrics:
            print(f"❌ 无法获取 {ticker} 的财务指标")
            return False

        m = metrics[0]
        all_valid = True

        # 检查百分比字段
        checks = [
            ("ROE", m.return_on_equity, -1, 1),  # 允许负ROE(亏损公司)
            ("ROA", m.return_on_assets, -1, 1),  # 允许负ROA
            ("毛利率", m.gross_margin, -1, 1),
            ("净利率", m.net_margin, -1, 1),
            ("营业利润率", m.operating_margin, -1, 1),
            ("营收增长率", m.revenue_growth, -1, 5),  # 允许500%增长
            ("盈利增长率", m.earnings_growth, -1, 5),
        ]

        print(f"\n报告期: {m.report_period}")
        print(f"数据来源: {getattr(m, 'data_source', 'N/A')}")
        print(f"\n财务指标验证:")

        for name, value, min_val, max_val in checks:
            if value is None:
                print(f"  {name:12s}: N/A")
            elif min_val <= value <= max_val:
                print(f"  {name:12s}: {value:8.4f} ({value:7.2%}) ✅")
            else:
                print(f"  {name:12s}: {value:8.4f} ({value:7.2%}) ❌ 超出范围 [{min_val}, {max_val}]")
                all_valid = False

        # 检查估值指标
        print(f"\n估值指标:")
        if m.price_to_earnings_ratio:
            # PE可以为负(亏损公司),只检查是否在合理范围
            if -10000 <= m.price_to_earnings_ratio <= 10000:
                status = "✅" if m.price_to_earnings_ratio > 0 else "⚠️ (负PE,公司亏损)"
                print(f"  PE比率: {m.price_to_earnings_ratio:.2f} {status}")
            else:
                print(f"  PE比率: {m.price_to_earnings_ratio:.2f} ❌ 超出合理范围")
                all_valid = False
        else:
            print(f"  PE比率: N/A")

        if m.price_to_book_ratio:
            if m.price_to_book_ratio > 0:
                print(f"  PB比率: {m.price_to_book_ratio:.2f} ✅")
            else:
                print(f"  PB比率: {m.price_to_book_ratio:.2f} ❌ 应为正数")
                all_valid = False
        else:
            print(f"  PB比率: N/A")

        if all_valid:
            print(f"\n✅ {ticker} 数据格式验证通过")
        else:
            print(f"\n❌ {ticker} 数据格式存在问题")

        return all_valid

    except Exception as e:
        print(f"❌ 验证失败: {e}")
        return False


def main():
    """验证多个A股股票"""
    print("\n🔍 开始验证A股数据格式...\n")

    # 测试股票列表
    test_tickers = [
        "000001.SZ",  # 平安银行
        "600000.SH",  # 浦发银行
        "000002.SZ",  # 万科A
        "600519.SH",  # 贵州茅台
    ]

    results = {}

    for ticker in test_tickers:
        results[ticker] = verify_ticker(ticker)

    # 总结
    print(f"\n{'='*60}")
    print("验证总结")
    print(f"{'='*60}")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for ticker, result in results.items():
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{ticker:12s}: {status}")

    print(f"\n通过率: {passed}/{total} ({passed/total*100:.0f}%)")

    if passed == total:
        print("\n🎉 所有股票验证通过!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} 个股票验证失败")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
