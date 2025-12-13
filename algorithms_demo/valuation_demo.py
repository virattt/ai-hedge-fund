"""
Valuation 估值分析算法 Demo

4种估值方法聚合系统：
1. DCF 现金流折现 (35%权重)
2. Owner Earnings 所有者收益法 (35%权重)
3. EV/EBITDA 倍数法 (20%权重)
4. Residual Income Model 剩余收益模型 (10%权重)

输入参数：
- ticker: 股票代码
- financial_metrics: TTM财务指标列表
- line_items: 财务明细(需要2期)
- market_cap: 当前市值

输出结果：
- signal: "bullish", "bearish", or "neutral"
- confidence: 0-100
- 每种估值方法的详细结果
"""

from typing import List, Dict, Any
from statistics import median


def calculate_intrinsic_value_dcf(
    free_cash_flow: float,
    growth_rate: float = 0.05,
    discount_rate: float = 0.10,
    terminal_growth_rate: float = 0.03,
    num_years: int = 5,
) -> float:
    """
    经典DCF自由现金流折现模型

    参数:
        free_cash_flow: 自由现金流
        growth_rate: 增长率 (默认5%)
        discount_rate: 折现率 (默认10%)
        terminal_growth_rate: 永续增长率 (默认3%)
        num_years: 预测年限 (默认5年)
    """
    if not free_cash_flow or free_cash_flow <= 0:
        return 0

    pv = 0.0
    for yr in range(1, num_years + 1):
        fcf_t = free_cash_flow * (1 + growth_rate) ** yr
        pv += fcf_t / (1 + discount_rate) ** yr

    # 终值
    term_val = (
        free_cash_flow * (1 + growth_rate) ** num_years * (1 + terminal_growth_rate)
    ) / (discount_rate - terminal_growth_rate)
    pv_term = term_val / (1 + discount_rate) ** num_years

    return pv + pv_term


def calculate_owner_earnings_value(
    net_income: float,
    depreciation: float,
    capex: float,
    working_capital_change: float,
    growth_rate: float = 0.05,
    required_return: float = 0.15,
    margin_of_safety: float = 0.25,
    num_years: int = 5,
) -> float:
    """
    巴菲特所有者收益估值法（带安全边际）

    公式: 所有者收益 = 净利润 + 折旧 - 资本支出 - 营运资本变化
    """
    if not all([net_income, depreciation, capex, working_capital_change]):
        return 0

    owner_earnings = net_income + depreciation - capex - working_capital_change
    if owner_earnings <= 0:
        return 0

    pv = 0.0
    for yr in range(1, num_years + 1):
        future = owner_earnings * (1 + growth_rate) ** yr
        pv += future / (1 + required_return) ** yr

    terminal_growth = min(growth_rate, 0.03)
    term_val = (
        owner_earnings * (1 + growth_rate) ** num_years * (1 + terminal_growth)
    ) / (required_return - terminal_growth)
    pv_term = term_val / (1 + required_return) ** num_years

    intrinsic = pv + pv_term
    return intrinsic * (1 - margin_of_safety)


def calculate_ev_ebitda_value(
    enterprise_value: float,
    ev_to_ebitda: float,
    historical_ev_ebitda: List[float],
    market_cap: float,
) -> float:
    """
    通过中位数EV/EBITDA倍数计算隐含权益价值
    """
    if not enterprise_value or not ev_to_ebitda or ev_to_ebitda == 0:
        return 0

    ebitda_now = enterprise_value / ev_to_ebitda

    # 使用历史中位数倍数
    valid_multiples = [m for m in historical_ev_ebitda if m and m > 0]
    if not valid_multiples:
        return 0

    med_mult = median(valid_multiples)
    ev_implied = med_mult * ebitda_now

    # 计算净债务
    net_debt = enterprise_value - market_cap
    return max(ev_implied - net_debt, 0)


def calculate_residual_income_value(
    market_cap: float,
    net_income: float,
    price_to_book_ratio: float,
    book_value_growth: float = 0.03,
    cost_of_equity: float = 0.10,
    terminal_growth_rate: float = 0.03,
    num_years: int = 5,
) -> float:
    """
    剩余收益模型 (Edwards-Bell-Ohlson)
    """
    if not all([market_cap, net_income, price_to_book_ratio]) or price_to_book_ratio <= 0:
        return 0

    book_val = market_cap / price_to_book_ratio
    ri0 = net_income - cost_of_equity * book_val
    if ri0 <= 0:
        return 0

    pv_ri = 0.0
    for yr in range(1, num_years + 1):
        ri_t = ri0 * (1 + book_value_growth) ** yr
        pv_ri += ri_t / (1 + cost_of_equity) ** yr

    term_ri = ri0 * (1 + book_value_growth) ** (num_years + 1) / (
        cost_of_equity - terminal_growth_rate
    )
    pv_term = term_ri / (1 + cost_of_equity) ** num_years

    intrinsic = book_val + pv_ri + pv_term
    return intrinsic * 0.8  # 20% 安全边际


def valuation_algorithm(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    估值分析算法主函数

    输入参数:
        data = {
            "ticker": str,
            "financial_metrics": List[Dict],  # TTM财务指标
            "line_items": List[Dict],         # 财务明细(需要2期)
            "market_cap": float
        }

    输出结果:
        {
            "signal": "bullish" | "bearish" | "neutral",
            "confidence": float (0-100),
            "reasoning": {
                "dcf_analysis": {...},
                "owner_earnings_analysis": {...},
                "ev_ebitda_analysis": {...},
                "residual_income_analysis": {...}
            }
        }
    """
    ticker = data["ticker"]
    financial_metrics = data["financial_metrics"]
    line_items = data["line_items"]
    market_cap = data["market_cap"]

    if not financial_metrics or len(line_items) < 2:
        return {
            "ticker": ticker,
            "signal": "neutral",
            "confidence": 0,
            "reasoning": {"error": "Insufficient data"}
        }

    most_recent_metrics = financial_metrics[0]
    li_curr, li_prev = line_items[0], line_items[1]

    # 计算营运资本变化
    wc_change = li_curr.get("working_capital", 0) - li_prev.get("working_capital", 0)

    # ========================================================================
    # 1. DCF 现金流折现
    # ========================================================================
    fcf = li_curr.get("free_cash_flow")
    dcf_val = calculate_intrinsic_value_dcf(
        free_cash_flow=fcf,
        growth_rate=most_recent_metrics.get("earnings_growth", 0.05),
    )

    # ========================================================================
    # 2. Owner Earnings 所有者收益法
    # ========================================================================
    owner_val = calculate_owner_earnings_value(
        net_income=li_curr.get("net_income", 0),
        depreciation=li_curr.get("depreciation_and_amortization", 0),
        capex=li_curr.get("capital_expenditure", 0),
        working_capital_change=wc_change,
        growth_rate=most_recent_metrics.get("earnings_growth", 0.05),
    )

    # ========================================================================
    # 3. EV/EBITDA 倍数法
    # ========================================================================
    historical_ev_ebitda = [
        m.get("enterprise_value_to_ebitda_ratio")
        for m in financial_metrics
        if m.get("enterprise_value_to_ebitda_ratio")
    ]

    ev_ebitda_val = calculate_ev_ebitda_value(
        enterprise_value=most_recent_metrics.get("enterprise_value", 0),
        ev_to_ebitda=most_recent_metrics.get("enterprise_value_to_ebitda_ratio", 0),
        historical_ev_ebitda=historical_ev_ebitda,
        market_cap=market_cap,
    )

    # ========================================================================
    # 4. Residual Income Model 剩余收益模型
    # ========================================================================
    rim_val = calculate_residual_income_value(
        market_cap=market_cap,
        net_income=li_curr.get("net_income", 0),
        price_to_book_ratio=most_recent_metrics.get("price_to_book_ratio", 0),
        book_value_growth=most_recent_metrics.get("book_value_growth", 0.03),
    )

    # ========================================================================
    # 聚合估值并生成信号
    # ========================================================================
    method_values = {
        "dcf": {"value": dcf_val, "weight": 0.35},
        "owner_earnings": {"value": owner_val, "weight": 0.35},
        "ev_ebitda": {"value": ev_ebitda_val, "weight": 0.20},
        "residual_income": {"value": rim_val, "weight": 0.10},
    }

    total_weight = sum(v["weight"] for v in method_values.values() if v["value"] > 0)
    if total_weight == 0:
        return {
            "ticker": ticker,
            "signal": "neutral",
            "confidence": 0,
            "reasoning": {"error": "All valuation methods returned zero"}
        }

    # 计算每个方法的估值差距
    for v in method_values.values():
        v["gap"] = (v["value"] - market_cap) / market_cap if v["value"] > 0 else None

    # 加权平均差距
    weighted_gap = sum(
        v["weight"] * v["gap"] for v in method_values.values() if v["gap"] is not None
    ) / total_weight

    # 生成信号
    signal = (
        "bullish" if weighted_gap > 0.15
        else "bearish" if weighted_gap < -0.15
        else "neutral"
    )
    confidence = round(min(abs(weighted_gap) / 0.30 * 100, 100))

    # 准备详细分析
    reasoning = {}
    for m, vals in method_values.items():
        if vals["value"] > 0:
            method_signal = (
                "bullish" if vals["gap"] and vals["gap"] > 0.15
                else "bearish" if vals["gap"] and vals["gap"] < -0.15
                else "neutral"
            )
            reasoning[f"{m}_analysis"] = {
                "signal": method_signal,
                "details": (
                    f"Value: ${vals['value']:,.2f}, "
                    f"Market Cap: ${market_cap:,.2f}, "
                    f"Gap: {vals['gap']:.1%}, "
                    f"Weight: {vals['weight']*100:.0f}%"
                ),
                "value": vals["value"],
                "gap": vals["gap"],
            }

    return {
        "ticker": ticker,
        "signal": signal,
        "confidence": confidence,
        "weighted_gap": weighted_gap,
        "reasoning": reasoning,
    }


# ============================================================================
# Demo 示例
# ============================================================================

if __name__ == "__main__":
    # 示例数据：价值被低估的公司
    sample_data = {
        "ticker": "VALUE",
        "financial_metrics": [
            {
                "earnings_growth": 0.08,
                "book_value_growth": 0.06,
                "enterprise_value": 150_000_000_000,
                "enterprise_value_to_ebitda_ratio": 10.5,
                "price_to_book_ratio": 2.5,
                "market_cap": 100_000_000_000,
            },
            {
                "enterprise_value_to_ebitda_ratio": 10.2,
            },
            {
                "enterprise_value_to_ebitda_ratio": 10.8,
            },
            {
                "enterprise_value_to_ebitda_ratio": 10.0,
            },
            {
                "enterprise_value_to_ebitda_ratio": 11.0,
            },
        ],
        "line_items": [
            {
                "free_cash_flow": 15_000_000_000,
                "net_income": 12_000_000_000,
                "depreciation_and_amortization": 5_000_000_000,
                "capital_expenditure": -8_000_000_000,
                "working_capital": 20_000_000_000,
            },
            {
                "working_capital": 18_000_000_000,
            },
        ],
        "market_cap": 100_000_000_000,
    }

    # 运行算法
    print("=" * 80)
    print("Valuation 估值分析算法 Demo")
    print("=" * 80)
    print(f"\n分析股票: {sample_data['ticker']}")
    print(f"当前市值: ${sample_data['market_cap']:,.0f}\n")

    result = valuation_algorithm(sample_data)

    # 打印结果
    print(f"估值信号: {result['signal'].upper()}")
    print(f"置信度: {result['confidence']}%")
    print(f"加权估值差距: {result['weighted_gap']:.1%}\n")

    print("-" * 80)
    print("各估值方法详细分析:")
    print("-" * 80)

    reasoning = result['reasoning']

    for i, (method_name, method_data) in enumerate(reasoning.items(), 1):
        method_title = method_name.replace("_analysis", "").replace("_", " ").title()
        print(f"\n{i}. {method_title}:")
        print(f"   信号: {method_data['signal'].upper()}")
        print(f"   {method_data['details']}")

    print("\n" + "=" * 80)
    print(f"最终决策: {result['signal'].upper()} (置信度: {result['confidence']}%)")
    print("=" * 80)

    # 示例2：高估的公司
    print("\n\n")
    print("=" * 80)
    print("示例2: 高估公司")
    print("=" * 80)

    sample_data_2 = {
        "ticker": "OVERPRICED",
        "financial_metrics": [
            {
                "earnings_growth": 0.03,
                "book_value_growth": 0.02,
                "enterprise_value": 200_000_000_000,
                "enterprise_value_to_ebitda_ratio": 25.0,
                "price_to_book_ratio": 8.0,
                "market_cap": 180_000_000_000,
            },
            {"enterprise_value_to_ebitda_ratio": 22.0},
            {"enterprise_value_to_ebitda_ratio": 20.0},
            {"enterprise_value_to_ebitda_ratio": 18.0},
        ],
        "line_items": [
            {
                "free_cash_flow": 5_000_000_000,
                "net_income": 6_000_000_000,
                "depreciation_and_amortization": 3_000_000_000,
                "capital_expenditure": -4_000_000_000,
                "working_capital": 10_000_000_000,
            },
            {
                "working_capital": 9_500_000_000,
            },
        ],
        "market_cap": 180_000_000_000,
    }

    result_2 = valuation_algorithm(sample_data_2)

    print(f"\n分析股票: {sample_data_2['ticker']}")
    print(f"当前市值: ${sample_data_2['market_cap']:,.0f}")
    print(f"\n估值信号: {result_2['signal'].upper()}")
    print(f"置信度: {result_2['confidence']}%")
    print(f"加权估值差距: {result_2['weighted_gap']:.1%}")

    print("\n简要分析:")
    for method_name, method_data in result_2['reasoning'].items():
        method_title = method_name.replace("_analysis", "").replace("_", " ").title()
        print(f"  {method_title}: {method_data['signal'].upper()} (差距: {method_data['gap']:.1%})")

    print("\n" + "=" * 80)
