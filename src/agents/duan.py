import json
from typing import Literal
from pydantic import BaseModel, Field
from src.graph.state import AgentState, show_agent_reasoning
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage
from src.tools.api import get_financial_metrics, search_line_items
from src.utils.progress import progress
from src.utils.api_key import get_api_key_from_state
from src.utils.llm import call_llm

"""
============================================================================
BaseModel 是 Pydantic 的核心类，用来做数据建模 + 校验 + 解析 + 序列化。

你可以把它理解为一句话：

👉 “带类型检查能力的 Python 数据结构（比 dataclass 更强的版本）”
"""


class duanSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: int = Field(description="Confidence 0-100")
    reasoning: str = Field(description="Reasoning for the signal")


def duan_agent(state: AgentState, agent_id: str = "duan_agent"):
    data = state["data"]
    end_date = data["end_date"]
    tickers = data["tickers"]
    api_key = get_api_key_from_state(state, "FINANCIAL_DATASETS_API_KEY")
    # Collect all analysis for LLM reasoning
    analysis_data = {}
    duan_analysis = {}

    for ticker in tickers:
        progress.update_status(agent_id, ticker, "Fetching financial metrics")
        # Fetch required data - request more periods for better trend analysis
        metrics = get_financial_metrics(ticker, end_date, period="ttm", limit=10, api_key=api_key)

        progress.update_status(agent_id, ticker, "Gathering financial line items")
        financial_line_items = search_line_items(
            ticker,
            [
                # 现金流相关
                "capital_expenditure",  # 资本支出 - 公司用于购置/更新固定资产的现金，反映公司的增长投资力度
                "free_cash_flow",  # 自由现金流 - 经营现金流 - 资本支出，是衡量公司真实盈利能力的关键指标
                # 利润相关
                "revenue",  # 收入/营收 - 公司的顶线数据，所有盈利的起点
                "gross_profit",  # 毛利 - 收入 - 成本，反映产品/服务的基础盈利能力
                "net_income",  # 净收入/净利润 - 扣除所有费用和税后的最终利润，是底线数据
                # 折旧相关
                "depreciation_and_amortization",  # 折旧和摊销 - 非现金支出，反映资产价值的消耗，需要加回计算自由现金流
                # 资产和负债结构
                "total_assets",  # 总资产 - 公司拥有的所有资源，用于计算 ROA、资产周转率等
                "total_liabilities",  # 总负债 - 公司欠债的总额，用于评估财务杠杆和偿债能力
                "shareholders_equity",  # 股东权益 - 资产 - 负债，代表股东真正拥有的净资产，用于计算 ROE
                # 股份相关
                "outstanding_shares",  # 流通股数 - 公开流通的股票数量，用于计算每股收益(EPS)、每股净资产等
                "issuance_or_purchase_of_equity_shares",  # 股票发行或回购 - 反映管理层对股价的态度（回购=认为低估，发行=融资需求）
                # 分配相关
                "dividends_and_other_cash_distributions",  # 股息和其他现金分配 - 公司向股东返回的现金，衡量派息率和现金分配能力
            ],
            end_date,
            period="ttm",
            limit=10,
            api_key=api_key,
        )

        progress.update_status(agent_id, ticker, "Analyzing competitive moat")
        moat_analysis = analyze_moat(metrics)

        # Calculate total score without circle of competence (LLM will handle that)
        total_score = moat_analysis["score"]

        # Update max possible score calculation
        max_possible_score = moat_analysis["max_score"] + 5 + 5  # pricing_power (0-5)  # book_value_growth (0-5)

        # Combine all analysis results for LLM evaluation
        analysis_data[ticker] = {
            "ticker": ticker,
            "score": total_score,
            "max_score": max_possible_score,
            "moat_analysis": moat_analysis,
        }

        progress.update_status(agent_id, ticker, "Generating Duan analysis")
        # KEY input  分析指标数据，llM 生成结构化输出
        duan_output = generate_duan_output(
            ticker=ticker,
            analysis_data=analysis_data[ticker],
            state=state,
            agent_id=agent_id,
        )

        # Store analysis in consistent format with other agents
        duan_analysis[ticker] = {
            "signal": duan_output.signal,
            "confidence": duan_output.confidence,
            "reasoning": duan_output.reasoning,
        }

        progress.update_status(agent_id, ticker, "Done", analysis=duan_output.reasoning)

    # Create the message
    message = HumanMessage(content=json.dumps(duan_analysis), name=agent_id)

    # Show reasoning if requested
    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(duan_analysis, agent_id)

    # KEY Add the signal to the analyst_signals list
    state["data"]["analyst_signals"][agent_id] = duan_analysis

    progress.update_status(agent_id, None, "Done")

    return {"messages": [message], "data": state["data"]}


def analyze_moat(metrics: list) -> dict[str, any]:
    """
    Evaluate whether the company likely has a durable competitive advantage (moat).
    Enhanced to include multiple moat indicators that Buffett actually looks for:
    1. Consistent high returns on capital
    2. Pricing power (stable/growing margins)
    3. Scale advantages (improving metrics with size)
    4. Brand strength (inferred from margins and consistency)
    5. Switching costs (inferred from customer retention)
    """
    if not metrics or len(metrics) < 5:  # Need more data for proper moat analysis
        return {"score": 0, "max_score": 5, "details": "Insufficient data for comprehensive moat analysis"}

    reasoning = []
    moat_score = 0
    max_score = 5

    # 1. Return on Capital Consistency (Buffett's favorite moat indicator)
    # ROE (净资产收益率) = 净利润 / 股东权益，衡量公司用股东资金赚钱的效率
    # ROIC (投资资本回报率) = 税后经营利润 / 投资资本，衡量全部投资（债+股）的效率
    historical_roes = [m.return_on_equity for m in metrics if m.return_on_equity is not None]
    historical_roics = [m.return_on_invested_capital for m in metrics if hasattr(m, "return_on_invested_capital") and m.return_on_invested_capital is not None]

    if len(historical_roes) >= 5:
        # 检查是否持续保持高 ROE (超过 15% 被视为"高"，表明强大的竞争优势)
        high_roe_periods = sum(1 for roe in historical_roes if roe > 0.15)
        roe_consistency = high_roe_periods / len(historical_roes)

        if roe_consistency >= 0.8:  # 80%+ of periods with ROE > 15%
            moat_score += 2
            avg_roe = sum(historical_roes) / len(historical_roes)
            reasoning.append(f"Excellent ROE consistency: {high_roe_periods}/{len(historical_roes)} periods >15% (avg: {avg_roe:.1%}) - indicates durable competitive advantage")
        elif roe_consistency >= 0.6:
            moat_score += 1
            reasoning.append(f"Good ROE performance: {high_roe_periods}/{len(historical_roes)} periods >15%")
        else:
            reasoning.append(f"Inconsistent ROE: only {high_roe_periods}/{len(historical_roes)} periods >15%")
    else:
        reasoning.append("Insufficient ROE history for moat analysis")

    # 2. Operating Margin Stability (Pricing Power Indicator)
    # 营业利润率 = 营业利润 / 收入，反映公司的定价权和成本控制能力
    # 稳定/上升的利润率表明公司具有定价权和护城河
    historical_margins = [m.operating_margin for m in metrics if m.operating_margin is not None]
    if len(historical_margins) >= 5:
        # Check for stable or improving margins (sign of pricing power)
        avg_margin = sum(historical_margins) / len(historical_margins)
        recent_margins = historical_margins[:3]  # Last 3 periods
        older_margins = historical_margins[-3:]  # First 3 periods

        recent_avg = sum(recent_margins) / len(recent_margins)
        older_avg = sum(older_margins) / len(older_margins)

        if avg_margin > 0.2 and recent_avg >= older_avg:  # 20%+ margins and stable/improving
            moat_score += 1
            reasoning.append(f"Strong and stable operating margins (avg: {avg_margin:.1%}) indicate pricing power moat")
        elif avg_margin > 0.15:  # At least decent margins
            reasoning.append(f"Decent operating margins (avg: {avg_margin:.1%}) suggest some competitive advantage")
        else:
            reasoning.append(f"Low operating margins (avg: {avg_margin:.1%}) suggest limited pricing power")

    # 3. Asset Efficiency and Scale Advantages
    # 资产周转率 = 收入 / 平均总资产，衡量公司用资产生成收入的效率
    # 高周转率表明公司规模经济好或资产利用效率高
    if len(metrics) >= 5:
        # Check asset turnover trends (revenue efficiency)
        asset_turnovers = []
        for m in metrics:
            if hasattr(m, "asset_turnover") and m.asset_turnover is not None:
                asset_turnovers.append(m.asset_turnover)

        if len(asset_turnovers) >= 3:
            if any(turnover > 1.0 for turnover in asset_turnovers):  # Efficient asset use
                moat_score += 1
                reasoning.append("Efficient asset utilization suggests operational moat")

    # 4. Competitive Position Strength (inferred from trend stability)
    # 通过 ROE 和营业利润率的稳定性来判断竞争地位
    # 高稳定性 (系数变异小) = 强大的竞争优势，能抵抗市场波动
    # 系数变异 (CV) = 标准差 / 平均值，越小表示越稳定
    if len(historical_roes) >= 5 and len(historical_margins) >= 5:
        # Calculate coefficient of variation (stability measure)
        roe_avg = sum(historical_roes) / len(historical_roes)
        roe_variance = sum((roe - roe_avg) ** 2 for roe in historical_roes) / len(historical_roes)
        roe_stability = 1 - (roe_variance**0.5) / roe_avg if roe_avg > 0 else 0

        margin_avg = sum(historical_margins) / len(historical_margins)
        margin_variance = sum((margin - margin_avg) ** 2 for margin in historical_margins) / len(historical_margins)
        margin_stability = 1 - (margin_variance**0.5) / margin_avg if margin_avg > 0 else 0

        overall_stability = (roe_stability + margin_stability) / 2

        if overall_stability > 0.7:  # High stability indicates strong competitive position
            moat_score += 1
            reasoning.append(f"High performance stability ({overall_stability:.1%}) suggests strong competitive moat")

    # Cap the score at max_score
    moat_score = min(moat_score, max_score)

    return {
        "score": moat_score,
        "max_score": max_score,
        "details": "; ".join(reasoning) if reasoning else "Limited moat analysis available",
    }


def generate_duan_output(
    ticker: str,
    analysis_data: dict[str, any],
    state: AgentState,
    agent_id: str = "duan_agent",
) -> duanSignal:
    """Get investment decision from LLM with a compact prompt."""

    # --- Build compact facts here ---
    facts = {
        "score": analysis_data.get("score"),  # 综合评分（0-max_score）
        "max_score": analysis_data.get("max_score"),  # 满分
        "fundamentals": analysis_data.get("fundamental_analysis", {}).get("details"),  # 基本面分析（ROE、负债、利润率等）
        "consistency": analysis_data.get("consistency_analysis", {}).get("details"),  # 盈利稳定性
        "moat": analysis_data.get("moat_analysis", {}).get("details"),  # 竞争护城河（ROE稳定性、定价权等）
        "pricing_power": analysis_data.get("pricing_power_analysis", {}).get("details"),  # 定价权（利润率趋势）
        "book_value": analysis_data.get("book_value_analysis", {}).get("details"),  # 每股净资产增长
        "management": analysis_data.get("management_analysis", {}).get("details"),  # 管理层质量
        "intrinsic_value": analysis_data.get("intrinsic_value_analysis", {}).get("intrinsic_value"),  # 内在价值估计
        "market_cap": analysis_data.get("market_cap"),  # 当前市值
        "margin_of_safety": analysis_data.get("margin_of_safety"),  # 安全边际 = (内在价值 - 市值) / 市值，>0表示低估
    }

    template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are Duan Yongpin. Decide bullish, bearish, or neutral using only the provided facts.\n"
                "\n"
                "Checklist for decision:\n"
                "- Circle of competence\n"
                "- Competitive moat\n"
                "- Management quality\n"
                "- Financial strength\n"
                "- Valuation vs intrinsic value\n"
                "- Long-term prospects\n"
                "\n"
                "Signal rules:\n"
                "- Bullish: strong business AND margin_of_safety > 0.\n"
                "- Bearish: poor business OR clearly overvalued.\n"
                "- Neutral: good business but margin_of_safety <= 0, or mixed evidence.\n"
                "\n"
                "Confidence scale:\n"
                "- 90-100%: Exceptional business within my circle, trading at attractive price\n"
                "- 70-89%: Good business with decent moat, fair valuation\n"
                "- 50-69%: Mixed signals, would need more information or better price\n"
                "- 30-49%: Outside my expertise or concerning fundamentals\n"
                "- 10-29%: Poor business or significantly overvalued\n"
                "\n"
                "Keep reasoning under 120 characters. Do not invent data. Return JSON only.",
            ),
            ("human", "Ticker: {ticker}\n" "Facts:\n{facts}\n\n" "Return exactly:\n" "{{\n" '  "signal": "bullish" | "bearish" | "neutral",\n' '  "confidence": int,\n' '  "reasoning": "short justification"\n' "}}"),
        ]
    )

    prompt = template.invoke(
        {
            "facts": json.dumps(facts, separators=(",", ":"), ensure_ascii=False),
            "ticker": ticker,
        }
    )

    # Default fallback uses int confidence to match schema and avoid parse retries
    def create_default_duan_signal():
        return duanSignal(signal="neutral", confidence=50, reasoning="Insufficient data")

    return call_llm(
        prompt=prompt,
        pydantic_model=duanSignal,
        agent_name=agent_id,
        state=state,
        default_factory=create_default_duan_signal,
    )
