# -*- coding: utf-8 -*-
import os
import sys
from datetime import datetime, timedelta

# -- 设置项目根目录 --
# 为了确保能够正确导入src模块，需要将项目根目录添加到Python的搜索路径中。
# 这对于在项目外部运行此脚本至关重要。
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from src.main import run_hedge_fund
from src.utils.display import print_trading_output
from dotenv import load_dotenv

# 加载环境变量，主要是API密钥
# 请确保您的项目根目录下有一个 .env 文件，并且其中包含了必要的API密钥。
# 例如：
# OPENAI_API_KEY="your-openai-api-key"
# FINANCIAL_DATASETS_API_KEY="your-financial-datasets-api-key"
load_dotenv()

def run_stock_analysis_example():
    """
    一个演示如何调用AI对冲基金股票分析功能的示例函数。
    """
    print("--- 开始运行股票分析示例 ---")

    # --- 1. 定义分析参数 ---

    # 要分析的股票代码列表
    # 注意：免费数据仅支持 AAPL, GOOGL, MSFT, NVDA, TSLA。
    # 分析其他股票需要设置 FINANCIAL_DATASETS_API_KEY。
    tickers = ["AAPL", "TSLA"]
    print(f"分析股票: {', '.join(tickers)}")

    # 定义分析的起止日期
    # 如果不指定，默认分析过去三个月的数据。
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
    print(f"分析时间范围: {start_date} 到 {end_date}")

    # 定义初始投资组合
    # 这是一个简化的结构，用于告知分析模块当前的持仓情况。
    # 在这个例子中，我们假设初始状态为10万美元现金，没有持股。
    portfolio = {
        "cash": 100000.0,
        "margin_requirement": 0.0,
        "margin_used": 0.0,
        "positions": {
            ticker: {
                "long": 0,
                "short": 0,
                "long_cost_basis": 0.0,
                "short_cost_basis": 0.0,
                "short_margin_used": 0.0,
            }
            for ticker in tickers
        },
        "realized_gains": {
            ticker: {"long": 0.0, "short": 0.0} for ticker in tickers
        },
    }

    # 选择要使用的AI分析师
    # 您可以从 `src/utils/analysts.py` 的 `ANALYST_CONFIG` 中找到所有可用的分析师。
    # 在这里，我们选择 "Warren Buffett" 和 "Cathie Wood" 作为示例。
    selected_analysts = ["warren_buffett", "cathie_wood"]
    print(f"选择的AI分析师: {', '.join(selected_analysts)}")

    # 选择语言模型
    # 这里我们使用 "gpt-4o" 作为示例。
    # 您也可以选择其他模型，例如 "gpt-4o-mini" 或 "llama3"。
    model_name = "gpt-4o"
    model_provider = "OpenAI"
    print(f"使用的语言模型: {model_name} ({model_provider})")


    # --- 2. 调用核心分析函数 ---

    print("\n>>> 正在调用 run_hedge_fund 函数进行分析，请稍候...")

    # 调用 run_hedge_fund 函数
    # 这个函数会协调所有选定的分析师，并返回最终的交易决策。
    try:
        result = run_hedge_fund(
            tickers=tickers,
            start_date=start_date,
            end_date=end_date,
            portfolio=portfolio,
            show_reasoning=True,  # 设置为True可以在控制台看到每个分析师的详细分析过程
            selected_analysts=selected_analysts,
            model_name=model_name,
            model_provider=model_provider,
        )
    except Exception as e:
        print(f"\n--- 分析过程中发生错误 ---")
        print(f"错误类型: {type(e).__name__}")
        print(f"错误信息: {e}")
        print("\n请检查以下几点：")
        print("1. 是否在 .env 文件中正确设置了 API 密钥 (例如 OPENAI_API_KEY)。")
        print("2. 如果分析免费股票外的代码，是否设置了 FINANCIAL_DATASETS_API_KEY。")
        print("3. 网络连接是否正常。")
        return

    # --- 3. 打印分析结果 ---

    print("\n--- 分析完成 ---")
    if result:
        # 使用项目提供的工具函数来格式化并打印结果
        print_trading_output(result)
    else:
        print("未能获取分析结果。")

if __name__ == "__main__":
    # 确保在运行前已经安装了所有依赖
    # 在项目根目录下运行: poetry install
    run_stock_analysis_example()
