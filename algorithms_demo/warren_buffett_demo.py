"""
Warren Buffett 价值投资算法 Demo

这是Warren Buffett投资策略的独立可运行演示。
算法基于巴菲特的核心原则：价值投资、护城河、安全边际。

输入参数：
- ticker: 股票代码
- metrics: 财务指标列表（最近5期TTM数据）
- financial_line_items: 财务明细项（净利润、折旧、资本支出等）
- market_cap: 当前市值

输出结果：
- signal: "bullish", "bearish", or "neutral"
- confidence: 0-100
- detailed analysis breakdown
"""

from typing import List, Dict, Any, Optional


def analyze_fundamentals(metrics: List[Dict]) -> Dict[str, Any]:
    """
    分析公司基本面（基于巴菲特标准）

    评分标准：
    - ROE > 15%: 2分
    - Debt/Equity < 0.5: 2分
    - Operating Margin > 15%: 2分
    - Current Ratio > 1.5: 1分

    最高7分
    """
    if not metrics:
        return {"score": 0, "details": "Insufficient fundamental data"}

    latest_metrics = metrics[0]
    score = 0
    reasoning = []

    # 检查ROE
    roe = latest_metrics.get("return_on_equity")
    if roe and roe > 0.15:
        score += 2
        reasoning.append(f"Strong ROE of {roe:.1%}")
    elif roe:
        reasoning.append(f"Weak ROE of {roe:.1%}")
    else:
        reasoning.append("ROE data not available")

    # 检查债务权益比
    debt_to_equity = latest_metrics.get("debt_to_equity")
    if debt_to_equity and debt_to_equity < 0.5:
        score += 2
        reasoning.append("Conservative debt levels")
    elif debt_to_equity:
        reasoning.append(f"High debt to equity ratio of {debt_to_equity:.1f}")
    else:
        reasoning.append("Debt to equity data not available")

    # 检查营业利润率
    operating_margin = latest_metrics.get("operating_margin")
    if operating_margin and operating_margin > 0.15:
        score += 2
        reasoning.append("Strong operating margins")
    elif operating_margin:
        reasoning.append(f"Weak operating margin of {operating_margin:.1%}")
    else:
        reasoning.append("Operating margin data not available")

    # 检查流动比率
    current_ratio = latest_metrics.get("current_ratio")
    if current_ratio and current_ratio > 1.5:
        score += 1
        reasoning.append("Good liquidity position")
    elif current_ratio:
        reasoning.append(f"Weak liquidity with current ratio of {current_ratio:.1f}")
    else:
        reasoning.append("Current ratio data not available")

    return {
        "score": score,
        "details": "; ".join(reasoning),
        "metrics": latest_metrics
    }


def analyze_consistency(financial_line_items: List[Dict]) -> Dict[str, Any]:
    """
    分析收益一致性和增长

    需要至少4期数据来分析趋势
    如果每期收益都大于上一期，得3分
    """
    if len(financial_line_items) < 4:
        return {"score": 0, "details": "Insufficient historical data"}

    score = 0
    reasoning = []

    # 检查收益增长趋势
    earnings_values = [
        item.get("net_income")
        for item in financial_line_items
        if item.get("net_income")
    ]

    if len(earnings_values) >= 4:
        # 检查是否每期收益都大于下一期（数据是倒序的）
        earnings_growth = all(
            earnings_values[i] > earnings_values[i + 1]
            for i in range(len(earnings_values) - 1)
        )

        if earnings_growth:
            score += 3
            reasoning.append("Consistent earnings growth over past periods")
        else:
            reasoning.append("Inconsistent earnings growth pattern")

        # 计算总增长率
        if len(earnings_values) >= 2 and earnings_values[-1] != 0:
            growth_rate = (earnings_values[0] - earnings_values[-1]) / abs(earnings_values[-1])
            reasoning.append(
                f"Total earnings growth of {growth_rate:.1%} over past {len(earnings_values)} periods"
            )
    else:
        reasoning.append("Insufficient earnings data for trend analysis")

    return {
        "score": score,
        "details": "; ".join(reasoning),
    }


def analyze_moat(metrics: List[Dict]) -> Dict[str, Any]:
    """
    评估公司是否有持久的竞争优势（护城河）

    通过多期ROE和营业利润率的稳定性来判断
    - ROE连续3期 > 15%: 1分
    - Operating Margin连续3期 > 15%: 1分
    - 两者都稳定: 额外1分

    最高3分
    """
    if not metrics or len(metrics) < 3:
        return {"score": 0, "max_score": 3, "details": "Insufficient data for moat analysis"}

    reasoning = []
    moat_score = 0

    # 收集历史ROE
    historical_roes = [m.get("return_on_equity") for m in metrics if m.get("return_on_equity")]

    # 收集历史营业利润率
    historical_margins = [m.get("operating_margin") for m in metrics if m.get("operating_margin")]

    # 检查ROE稳定性
    if len(historical_roes) >= 3:
        stable_roe = all(r > 0.15 for r in historical_roes)
        if stable_roe:
            moat_score += 1
            reasoning.append("Stable ROE above 15% across periods (suggests moat)")
        else:
            reasoning.append("ROE not consistently above 15%")

    # 检查营业利润率稳定性
    if len(historical_margins) >= 3:
        stable_margin = all(m > 0.15 for m in historical_margins)
        if stable_margin:
            moat_score += 1
            reasoning.append("Stable operating margins above 15% (moat indicator)")
        else:
            reasoning.append("Operating margin not consistently above 15%")

    # 如果两者都稳定，额外加分
    if moat_score == 2:
        moat_score += 1
        reasoning.append("Both ROE and margin stability indicate a solid moat")

    return {
        "score": moat_score,
        "max_score": 3,
        "details": "; ".join(reasoning),
    }


def analyze_management_quality(financial_line_items: List[Dict]) -> Dict[str, Any]:
    """
    检查管理层质量

    - 股票回购（股份减少）: 1分
    - 分红记录: 1分

    最高2分
    """
    if not financial_line_items:
        return {"score": 0, "max_score": 2, "details": "Insufficient data for management analysis"}

    reasoning = []
    mgmt_score = 0

    latest = financial_line_items[0]

    # 检查股票回购
    issuance = latest.get("issuance_or_purchase_of_equity_shares")
    if issuance and issuance < 0:
        # 负值表示公司回购股票
        mgmt_score += 1
        reasoning.append("Company has been repurchasing shares (shareholder-friendly)")
    elif issuance and issuance > 0:
        reasoning.append("Recent common stock issuance (potential dilution)")
    else:
        reasoning.append("No significant new stock issuance detected")

    # 检查分红
    dividends = latest.get("dividends_and_other_cash_distributions")
    if dividends and dividends < 0:
        mgmt_score += 1
        reasoning.append("Company has a track record of paying dividends")
    else:
        reasoning.append("No or minimal dividends paid")

    return {
        "score": mgmt_score,
        "max_score": 2,
        "details": "; ".join(reasoning),
    }


def calculate_owner_earnings(financial_line_items: List[Dict]) -> Dict[str, Any]:
    """
    计算所有者收益（巴菲特偏好的真实盈利能力指标）

    公式: 所有者收益 = 净利润 + 折旧 - 维护性资本支出
    维护性资本支出估算为总资本支出的75%
    """
    if not financial_line_items or len(financial_line_items) < 1:
        return {
            "owner_earnings": None,
            "details": ["Insufficient data for owner earnings calculation"]
        }

    latest = financial_line_items[0]

    net_income = latest.get("net_income")
    depreciation = latest.get("depreciation_and_amortization")
    capex = latest.get("capital_expenditure")

    if not all([net_income, depreciation, capex]):
        return {
            "owner_earnings": None,
            "details": ["Missing components for owner earnings calculation"]
        }

    # 估算维护性资本支出（通常为总资本支出的70-80%）
    maintenance_capex = capex * 0.75
    owner_earnings = net_income + depreciation - maintenance_capex

    return {
        "owner_earnings": owner_earnings,
        "components": {
            "net_income": net_income,
            "depreciation": depreciation,
            "maintenance_capex": maintenance_capex
        },
        "details": ["Owner earnings calculated successfully"],
    }


def calculate_intrinsic_value(financial_line_items: List[Dict]) -> Dict[str, Any]:
    """
    使用DCF和所有者收益计算内在价值

    巴菲特的DCF假设（保守方法）:
    - 增长率: 5%
    - 折现率: 9%
    - 终值倍数: 12倍
    - 预测年限: 10年
    """
    if not financial_line_items:
        return {"intrinsic_value": None, "details": ["Insufficient data for valuation"]}

    # 计算所有者收益
    earnings_data = calculate_owner_earnings(financial_line_items)
    if not earnings_data.get("owner_earnings"):
        return {"intrinsic_value": None, "details": earnings_data["details"]}

    owner_earnings = earnings_data["owner_earnings"]

    # 获取流通股数
    latest = financial_line_items[0]
    shares_outstanding = latest.get("outstanding_shares")

    if not shares_outstanding:
        return {"intrinsic_value": None, "details": ["Missing shares outstanding data"]}

    # DCF参数
    growth_rate = 0.05  # 保守5%增长
    discount_rate = 0.09  # 典型~9%折现率
    terminal_multiple = 12
    projection_years = 10

    # 计算未来现金流的现值总和
    future_value = 0
    for year in range(1, projection_years + 1):
        future_earnings = owner_earnings * (1 + growth_rate) ** year
        present_value = future_earnings / (1 + discount_rate) ** year
        future_value += present_value

    # 终值
    terminal_value = (
        owner_earnings * (1 + growth_rate) ** projection_years * terminal_multiple
    ) / ((1 + discount_rate) ** projection_years)

    intrinsic_value = future_value + terminal_value

    return {
        "intrinsic_value": intrinsic_value,
        "owner_earnings": owner_earnings,
        "assumptions": {
            "growth_rate": growth_rate,
            "discount_rate": discount_rate,
            "terminal_multiple": terminal_multiple,
            "projection_years": projection_years,
        },
        "details": ["Intrinsic value calculated using DCF model with owner earnings"],
    }


def warren_buffett_algorithm(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Warren Buffett投资算法主函数

    输入参数:
        data = {
            "ticker": str,
            "metrics": List[Dict],  # 财务指标（5期）
            "financial_line_items": List[Dict],  # 财务明细
            "market_cap": float
        }

    输出结果:
        {
            "signal": "bullish" | "bearish" | "neutral",
            "confidence": float,
            "score": float,
            "max_score": float,
            "fundamental_analysis": {...},
            "consistency_analysis": {...},
            "moat_analysis": {...},
            "management_analysis": {...},
            "intrinsic_value_analysis": {...},
            "margin_of_safety": float | None
        }
    """
    ticker = data["ticker"]
    metrics = data["metrics"]
    financial_line_items = data["financial_line_items"]
    market_cap = data["market_cap"]

    # 执行各项分析
    fundamental_analysis = analyze_fundamentals(metrics)
    consistency_analysis = analyze_consistency(financial_line_items)
    moat_analysis = analyze_moat(metrics)
    mgmt_analysis = analyze_management_quality(financial_line_items)
    intrinsic_value_analysis = calculate_intrinsic_value(financial_line_items)

    # 计算总分
    total_score = (
        fundamental_analysis["score"]
        + consistency_analysis["score"]
        + moat_analysis["score"]
        + mgmt_analysis["score"]
    )

    max_possible_score = (
        7  # fundamentals
        + 3  # consistency
        + moat_analysis["max_score"]  # moat (3)
        + mgmt_analysis["max_score"]  # management (2)
    )  # = 15

    # 计算安全边际
    margin_of_safety = None
    intrinsic_value = intrinsic_value_analysis.get("intrinsic_value")
    if intrinsic_value and market_cap:
        margin_of_safety = (intrinsic_value - market_cap) / market_cap

    # 生成交易信号
    # 要求: 总分>=70%最高分 且 安全边际>=30%
    if (total_score >= 0.7 * max_possible_score) and margin_of_safety and (margin_of_safety >= 0.3):
        signal = "bullish"
        confidence = min(85 + (margin_of_safety - 0.3) * 50, 100)
    elif total_score <= 0.3 * max_possible_score or (margin_of_safety is not None and margin_of_safety < -0.3):
        signal = "bearish"
        confidence = min(70 + abs(margin_of_safety + 0.3) * 100, 100) if margin_of_safety else 70
    else:
        signal = "neutral"
        confidence = 50

    return {
        "ticker": ticker,
        "signal": signal,
        "confidence": round(confidence, 2),
        "score": total_score,
        "max_score": max_possible_score,
        "fundamental_analysis": fundamental_analysis,
        "consistency_analysis": consistency_analysis,
        "moat_analysis": moat_analysis,
        "management_analysis": mgmt_analysis,
        "intrinsic_value_analysis": intrinsic_value_analysis,
        "market_cap": market_cap,
        "margin_of_safety": margin_of_safety,
    }


# ============================================================================
# Demo 示例
# ============================================================================

if __name__ == "__main__":
    # 示例数据
    sample_data = {
        "ticker": "AAPL",
        "metrics": [
            {
                "return_on_equity": 0.18,
                "debt_to_equity": 0.35,
                "operating_margin": 0.25,
                "current_ratio": 1.8,
            },
            {
                "return_on_equity": 0.17,
                "debt_to_equity": 0.38,
                "operating_margin": 0.24,
                "current_ratio": 1.7,
            },
            {
                "return_on_equity": 0.16,
                "debt_to_equity": 0.40,
                "operating_margin": 0.23,
                "current_ratio": 1.6,
            },
            {
                "return_on_equity": 0.16,
                "debt_to_equity": 0.42,
                "operating_margin": 0.22,
                "current_ratio": 1.5,
            },
            {
                "return_on_equity": 0.15,
                "debt_to_equity": 0.45,
                "operating_margin": 0.21,
                "current_ratio": 1.5,
            },
        ],
        "financial_line_items": [
            {
                "net_income": 100_000_000_000,
                "depreciation_and_amortization": 11_000_000_000,
                "capital_expenditure": -10_000_000_000,
                "outstanding_shares": 16_000_000_000,
                "issuance_or_purchase_of_equity_shares": -85_000_000_000,
                "dividends_and_other_cash_distributions": -15_000_000_000,
            },
            {
                "net_income": 95_000_000_000,
                "depreciation_and_amortization": 11_000_000_000,
                "capital_expenditure": -10_000_000_000,
                "outstanding_shares": 16_200_000_000,
            },
            {
                "net_income": 90_000_000_000,
                "depreciation_and_amortization": 10_500_000_000,
                "capital_expenditure": -9_500_000_000,
                "outstanding_shares": 16_500_000_000,
            },
            {
                "net_income": 85_000_000_000,
                "depreciation_and_amortization": 10_000_000_000,
                "capital_expenditure": -9_000_000_000,
                "outstanding_shares": 17_000_000_000,
            },
        ],
        "market_cap": 2_500_000_000_000,  # $2.5T
    }

    # 运行算法
    print("=" * 80)
    print("Warren Buffett 价值投资算法 Demo")
    print("=" * 80)
    print(f"\n分析股票: {sample_data['ticker']}")
    print(f"当前市值: ${sample_data['market_cap']:,.0f}\n")

    result = warren_buffett_algorithm(sample_data)

    # 打印结果
    print(f"交易信号: {result['signal'].upper()}")
    print(f"置信度: {result['confidence']:.1f}%")
    print(f"总评分: {result['score']:.1f} / {result['max_score']}")
    print(f"\n基本面分析 (得分: {result['fundamental_analysis']['score']}/7):")
    print(f"  {result['fundamental_analysis']['details']}")
    print(f"\n一致性分析 (得分: {result['consistency_analysis']['score']}/3):")
    print(f"  {result['consistency_analysis']['details']}")
    print(f"\n护城河分析 (得分: {result['moat_analysis']['score']}/{result['moat_analysis']['max_score']}):")
    print(f"  {result['moat_analysis']['details']}")
    print(f"\n管理层分析 (得分: {result['management_analysis']['score']}/{result['management_analysis']['max_score']}):")
    print(f"  {result['management_analysis']['details']}")

    if result['intrinsic_value_analysis'].get('intrinsic_value'):
        print(f"\n内在价值分析:")
        print(f"  所有者收益: ${result['intrinsic_value_analysis']['owner_earnings']:,.0f}")
        print(f"  计算的内在价值: ${result['intrinsic_value_analysis']['intrinsic_value']:,.0f}")
        print(f"  当前市值: ${result['market_cap']:,.0f}")
        if result['margin_of_safety'] is not None:
            print(f"  安全边际: {result['margin_of_safety']:.1%}")

    print("\n" + "=" * 80)
    print(f"最终决策: {result['signal'].upper()} (置信度: {result['confidence']:.1f}%)")
    print("=" * 80)
