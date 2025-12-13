"""
Fundamentals 基本面分析算法 Demo

4维度基本面评估系统：
1. 盈利能力分析 (Profitability)
2. 增长分析 (Growth)
3. 财务健康分析 (Financial Health)
4. 估值比率分析 (Valuation Ratios)

输入参数：
- ticker: 股票代码
- financial_metrics: TTM财务指标列表

输出结果：
- signal: "bullish", "bearish", or "neutral"
- confidence: 0-100
- 4个维度的详细分析
"""

from typing import List, Dict, Any


def fundamentals_algorithm(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    基本面分析算法主函数

    输入参数:
        data = {
            "ticker": str,
            "financial_metrics": List[Dict]  # TTM财务指标
        }

    输出结果:
        {
            "signal": "bullish" | "bearish" | "neutral",
            "confidence": float (0-100),
            "reasoning": {
                "profitability_signal": {...},
                "growth_signal": {...},
                "financial_health_signal": {...},
                "price_ratios_signal": {...}
            }
        }
    """
    ticker = data["ticker"]
    financial_metrics = data["financial_metrics"]

    if not financial_metrics:
        return {
            "ticker": ticker,
            "signal": "neutral",
            "confidence": 0,
            "reasoning": {"error": "No financial metrics found"}
        }

    # 获取最新的财务指标
    metrics = financial_metrics[0]

    # 初始化信号列表
    signals = []
    reasoning = {}

    # ========================================================================
    # 1. 盈利能力分析
    # ========================================================================
    return_on_equity = metrics.get("return_on_equity")
    net_margin = metrics.get("net_margin")
    operating_margin = metrics.get("operating_margin")

    thresholds = [
        (return_on_equity, 0.15),  # 强ROE > 15%
        (net_margin, 0.20),        # 健康利润率 > 20%
        (operating_margin, 0.15),  # 强运营效率 > 15%
    ]
    profitability_score = sum(
        metric is not None and metric > threshold
        for metric, threshold in thresholds
    )

    profitability_signal = (
        "bullish" if profitability_score >= 2
        else "bearish" if profitability_score == 0
        else "neutral"
    )
    signals.append(profitability_signal)

    reasoning["profitability_signal"] = {
        "signal": profitability_signal,
        "details": (
            (f"ROE: {return_on_equity:.2%}" if return_on_equity else "ROE: N/A") + ", " +
            (f"Net Margin: {net_margin:.2%}" if net_margin else "Net Margin: N/A") + ", " +
            (f"Op Margin: {operating_margin:.2%}" if operating_margin else "Op Margin: N/A")
        ),
    }

    # ========================================================================
    # 2. 增长分析
    # ========================================================================
    revenue_growth = metrics.get("revenue_growth")
    earnings_growth = metrics.get("earnings_growth")
    book_value_growth = metrics.get("book_value_growth")

    thresholds = [
        (revenue_growth, 0.10),    # 10% 收入增长
        (earnings_growth, 0.10),   # 10% 盈利增长
        (book_value_growth, 0.10), # 10% 账面价值增长
    ]
    growth_score = sum(
        metric is not None and metric > threshold
        for metric, threshold in thresholds
    )

    growth_signal = (
        "bullish" if growth_score >= 2
        else "bearish" if growth_score == 0
        else "neutral"
    )
    signals.append(growth_signal)

    reasoning["growth_signal"] = {
        "signal": growth_signal,
        "details": (
            (f"Revenue Growth: {revenue_growth:.2%}" if revenue_growth else "Revenue Growth: N/A") + ", " +
            (f"Earnings Growth: {earnings_growth:.2%}" if earnings_growth else "Earnings Growth: N/A")
        ),
    }

    # ========================================================================
    # 3. 财务健康分析
    # ========================================================================
    current_ratio = metrics.get("current_ratio")
    debt_to_equity = metrics.get("debt_to_equity")
    free_cash_flow_per_share = metrics.get("free_cash_flow_per_share")
    earnings_per_share = metrics.get("earnings_per_share")

    health_score = 0
    if current_ratio and current_ratio > 1.5:  # 强流动性
        health_score += 1
    if debt_to_equity and debt_to_equity < 0.5:  # 保守债务水平
        health_score += 1
    if (free_cash_flow_per_share and earnings_per_share and
        free_cash_flow_per_share > earnings_per_share * 0.8):  # 强FCF转换
        health_score += 1

    financial_health_signal = (
        "bullish" if health_score >= 2
        else "bearish" if health_score == 0
        else "neutral"
    )
    signals.append(financial_health_signal)

    reasoning["financial_health_signal"] = {
        "signal": financial_health_signal,
        "details": (
            (f"Current Ratio: {current_ratio:.2f}" if current_ratio else "Current Ratio: N/A") + ", " +
            (f"D/E: {debt_to_equity:.2f}" if debt_to_equity else "D/E: N/A")
        ),
    }

    # ========================================================================
    # 4. 估值比率分析
    # ========================================================================
    pe_ratio = metrics.get("price_to_earnings_ratio")
    pb_ratio = metrics.get("price_to_book_ratio")
    ps_ratio = metrics.get("price_to_sales_ratio")

    thresholds = [
        (pe_ratio, 25),  # 合理P/E比率
        (pb_ratio, 3),   # 合理P/B比率
        (ps_ratio, 5),   # 合理P/S比率
    ]
    price_ratio_score = sum(
        metric is not None and metric > threshold
        for metric, threshold in thresholds
    )

    # 注意：高估值比率是看跌信号
    price_ratios_signal = (
        "bearish" if price_ratio_score >= 2
        else "bullish" if price_ratio_score == 0
        else "neutral"
    )
    signals.append(price_ratios_signal)

    reasoning["price_ratios_signal"] = {
        "signal": price_ratios_signal,
        "details": (
            (f"P/E: {pe_ratio:.2f}" if pe_ratio else "P/E: N/A") + ", " +
            (f"P/B: {pb_ratio:.2f}" if pb_ratio else "P/B: N/A") + ", " +
            (f"P/S: {ps_ratio:.2f}" if ps_ratio else "P/S: N/A")
        ),
    }

    # ========================================================================
    # 确定总体信号
    # ========================================================================
    bullish_signals = signals.count("bullish")
    bearish_signals = signals.count("bearish")

    if bullish_signals > bearish_signals:
        overall_signal = "bullish"
    elif bearish_signals > bullish_signals:
        overall_signal = "bearish"
    else:
        overall_signal = "neutral"

    # 计算置信度
    total_signals = len(signals)
    confidence = round(max(bullish_signals, bearish_signals) / total_signals, 2) * 100

    return {
        "ticker": ticker,
        "signal": overall_signal,
        "confidence": confidence,
        "reasoning": reasoning,
    }


# ============================================================================
# Demo 示例
# ============================================================================

if __name__ == "__main__":
    # 示例数据：一个财务健康、成长型的公司
    sample_data = {
        "ticker": "AAPL",
        "financial_metrics": [
            {
                # 盈利能力指标
                "return_on_equity": 0.18,      # 18% ROE (优秀)
                "net_margin": 0.25,            # 25% 净利润率 (优秀)
                "operating_margin": 0.28,      # 28% 营业利润率 (优秀)

                # 增长指标
                "revenue_growth": 0.12,        # 12% 收入增长 (良好)
                "earnings_growth": 0.15,       # 15% 盈利增长 (良好)
                "book_value_growth": 0.11,     # 11% 账面价值增长 (良好)

                # 财务健康指标
                "current_ratio": 1.9,          # 1.9 流动比率 (健康)
                "debt_to_equity": 0.35,        # 0.35 债务权益比 (保守)
                "free_cash_flow_per_share": 6.50,
                "earnings_per_share": 6.00,

                # 估值比率
                "price_to_earnings_ratio": 22.5,  # 22.5 P/E (合理)
                "price_to_book_ratio": 2.8,       # 2.8 P/B (合理)
                "price_to_sales_ratio": 4.2,      # 4.2 P/S (合理)
            },
            # 可以包含更多历史数据...
        ]
    }

    # 运行算法
    print("=" * 80)
    print("Fundamentals 基本面分析算法 Demo")
    print("=" * 80)
    print(f"\n分析股票: {sample_data['ticker']}\n")

    result = fundamentals_algorithm(sample_data)

    # 打印结果
    print(f"总体信号: {result['signal'].upper()}")
    print(f"置信度: {result['confidence']:.0f}%\n")

    print("-" * 80)
    print("详细分析:")
    print("-" * 80)

    reasoning = result['reasoning']

    print(f"\n1. 盈利能力分析:")
    print(f"   信号: {reasoning['profitability_signal']['signal'].upper()}")
    print(f"   指标: {reasoning['profitability_signal']['details']}")

    print(f"\n2. 增长分析:")
    print(f"   信号: {reasoning['growth_signal']['signal'].upper()}")
    print(f"   指标: {reasoning['growth_signal']['details']}")

    print(f"\n3. 财务健康分析:")
    print(f"   信号: {reasoning['financial_health_signal']['signal'].upper()}")
    print(f"   指标: {reasoning['financial_health_signal']['details']}")

    print(f"\n4. 估值比率分析:")
    print(f"   信号: {reasoning['price_ratios_signal']['signal'].upper()}")
    print(f"   指标: {reasoning['price_ratios_signal']['details']}")

    print("\n" + "=" * 80)
    print(f"最终决策: {result['signal'].upper()} (置信度: {result['confidence']:.0f}%)")
    print("=" * 80)

    # 示例2：一个高估值、低增长的公司
    print("\n\n")
    print("=" * 80)
    print("示例2: 高估值、低增长公司")
    print("=" * 80)

    sample_data_2 = {
        "ticker": "OVERVALUED",
        "financial_metrics": [
            {
                "return_on_equity": 0.08,      # 8% ROE (低)
                "net_margin": 0.12,            # 12% 净利润率 (一般)
                "operating_margin": 0.10,      # 10% 营业利润率 (低)

                "revenue_growth": 0.03,        # 3% 收入增长 (低)
                "earnings_growth": 0.02,       # 2% 盈利增长 (低)
                "book_value_growth": 0.05,     # 5% 账面价值增长 (低)

                "current_ratio": 1.2,          # 1.2 流动比率 (一般)
                "debt_to_equity": 0.8,         # 0.8 债务权益比 (偏高)
                "free_cash_flow_per_share": 2.00,
                "earnings_per_share": 3.00,

                "price_to_earnings_ratio": 35.0,  # 35 P/E (高估)
                "price_to_book_ratio": 5.5,       # 5.5 P/B (高估)
                "price_to_sales_ratio": 8.0,      # 8.0 P/S (高估)
            }
        ]
    }

    result_2 = fundamentals_algorithm(sample_data_2)

    print(f"\n分析股票: {sample_data_2['ticker']}")
    print(f"总体信号: {result_2['signal'].upper()}")
    print(f"置信度: {result_2['confidence']:.0f}%")

    print(f"\n盈利能力: {result_2['reasoning']['profitability_signal']['signal'].upper()}")
    print(f"增长性: {result_2['reasoning']['growth_signal']['signal'].upper()}")
    print(f"财务健康: {result_2['reasoning']['financial_health_signal']['signal'].upper()}")
    print(f"估值: {result_2['reasoning']['price_ratios_signal']['signal'].upper()}")

    print("\n" + "=" * 80)
