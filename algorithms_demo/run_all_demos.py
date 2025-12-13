"""
运行所有算法Demo的测试脚本

这个脚本会依次运行所有已实现的算法demo，展示每个算法的功能。
"""

import sys


def print_header(title: str):
    """打印美化的标题"""
    print("\n\n")
    print("=" * 100)
    print(f"{title:^100}")
    print("=" * 100)
    print()


def run_demo(demo_name: str, demo_module: str):
    """运行单个demo"""
    print_header(f"运行 {demo_name}")
    try:
        exec(f"from {demo_module} import *")
        print(f"\n✓ {demo_name} 完成")
    except Exception as e:
        print(f"\n✗ {demo_name} 失败: {str(e)}")


def main():
    """主函数"""
    print_header("AI对冲基金算法 - 完整Demo演示")

    print("""
本演示将依次运行以下算法：

1. Warren Buffett      - 巴菲特价值投资算法
2. Technical Analysis  - 5种技术分析策略
3. Fundamentals        - 4维度基本面分析
4. Valuation           - 4种估值方法聚合

每个算法都是独立可运行的，您可以在各自的文件中查看完整代码。
""")

    input("\n按Enter键开始演示...")

    # ========================================================================
    # 1. Warren Buffett Algorithm
    # ========================================================================
    print_header("1. Warren Buffett 价值投资算法")
    print("这个算法基于巴菲特的投资原则：")
    print("  • 所有者收益计算")
    print("  • DCF内在价值评估")
    print("  • 安全边际 > 30%")
    print("  • 护城河分析")
    print("  • 管理层质量评估\n")

    try:
        import warren_buffett_demo
        print("\n✓ Warren Buffett算法演示完成")
    except Exception as e:
        print(f"\n✗ Warren Buffett算法失败: {str(e)}")

    input("\n\n按Enter键继续下一个算法...")

    # ========================================================================
    # 2. Technical Analysis
    # ========================================================================
    print_header("2. Technical Analysis 技术分析算法")
    print("综合5种技术分析策略：")
    print("  • 趋势跟踪 (25%权重) - EMA + ADX")
    print("  • 均值回归 (20%权重) - Z-Score + 布林带 + RSI")
    print("  • 动量策略 (25%权重) - 多时间框架动量 + 成交量")
    print("  • 波动率分析 (15%权重) - 历史波动率 + ATR")
    print("  • 统计套利 (15%权重) - Hurst指数 + 偏度\n")

    try:
        import technical_analysis_demo
        print("\n✓ Technical Analysis算法演示完成")
    except Exception as e:
        print(f"\n✗ Technical Analysis算法失败: {str(e)}")

    input("\n\n按Enter键继续下一个算法...")

    # ========================================================================
    # 3. Fundamentals Analysis
    # ========================================================================
    print_header("3. Fundamentals 基本面分析算法")
    print("4维度基本面评估：")
    print("  • 盈利能力 - ROE, Net Margin, Operating Margin")
    print("  • 增长性 - Revenue Growth, Earnings Growth")
    print("  • 财务健康 - Current Ratio, D/E, FCF")
    print("  • 估值比率 - P/E, P/B, P/S\n")

    try:
        import fundamentals_demo
        print("\n✓ Fundamentals算法演示完成")
    except Exception as e:
        print(f"\n✗ Fundamentals算法失败: {str(e)}")

    input("\n\n按Enter键继续下一个算法...")

    # ========================================================================
    # 4. Valuation Analysis
    # ========================================================================
    print_header("4. Valuation 估值分析算法")
    print("4种估值方法加权聚合：")
    print("  • DCF 现金流折现 (35%权重)")
    print("  • Owner Earnings 所有者收益法 (35%权重)")
    print("  • EV/EBITDA 倍数法 (20%权重)")
    print("  • Residual Income Model 剩余收益模型 (10%权重)\n")

    try:
        import valuation_demo
        print("\n✓ Valuation算法演示完成")
    except Exception as e:
        print(f"\n✗ Valuation算法失败: {str(e)}")

    # ========================================================================
    # 总结
    # ========================================================================
    print_header("演示完成！")

    print("""
✓ 所有算法演示已完成

每个算法都是完全独立的，可以单独使用：

• warren_buffett_demo.py      - 价值投资算法
• technical_analysis_demo.py   - 技术分析算法
• fundamentals_demo.py         - 基本面分析算法
• valuation_demo.py            - 估值分析算法

您可以直接运行任何一个文件来查看详细输出：
    python algorithms_demo/warren_buffett_demo.py

或者修改示例数据来测试不同场景。

完整文档请参考：algorithms_demo/README.md
""")

    print("=" * 100)


if __name__ == "__main__":
    main()
