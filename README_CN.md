# AI 对冲基金 - 中文使用说明

本项目是一个AI驱动的对冲基金的实现原型，旨在探索使用人工智能（AI）进行交易决策。**本项目仅用于教育和研究目的，不构成任何投资建议，请勿用于真实交易。**

这份文档将指导您如何将本项目的核心股票分析功能集成到您自己的项目中。

## 目录
- [项目架构](#项目架构)
- [快速开始](#快速开始)
  - [第一步：克隆项目](#第一步克隆项目)
  - [第二步：安装依赖](#第二步安装依赖)
  - [第三步：设置API密钥](#第三步设置api密钥)
- [如何调用分析功能](#如何调用分析功能)
  - [核心函数：`run_hedge_fund`](#核心函数run_hedge_fund)
  - [参数详解](#参数详解)
  - [代码示例：`analysis_example.py`](#代码示例analysis_examplepy)
  - [运行示例](#运行示例)
- [结果解析](#结果解析)
- [AI分析师列表](#ai分析师列表)

## 项目架构

本项目的核心是一个基于“代理”（Agent）的系统。每个代理都模仿一位著名投资者的投资理念和分析方法，对输入的股票进行分析。系统架构如下：

1.  **数据接口**：通过 `src/tools/api.py` 从外部API（如 Financial Datasets）获取股票的财务数据、市场行情等。
2.  **AI分析师代理**：在 `src/agents/` 目录下，每个文件代表一个AI分析师（例如 `warren_buffett.py`）。每个代理会：
    *   获取所需的数据。
    *   根据其独特的投资策略进行计算和分析。
    *   调用大型语言模型（LLM）生成最终的投资观点和分析报告。
3.  **工作流引擎**：使用 `langgraph` 构建一个工作流，将多个AI分析师的分析结果进行汇总。
4.  **核心调用函数**：`src/main.py` 中的 `run_hedge_fund` 函数是整个分析流程的入口，负责接收参数、启动工作流并返回最终结果。

## 快速开始

在调用分析功能之前，您需要完成项目的基本设置。

### 第一步：克隆项目

```bash
git clone https://github.com/virattt/ai-hedge-fund.git
cd ai-hedge-fund
```

### 第二步：安装依赖

本项目使用 [Poetry](https://python-poetry.org/) 进行依赖管理。

1.  **安装 Poetry**:
    ```bash
    curl -sSL https://install.python-poetry.org | python3 -
    ```

2.  **安装项目依赖**:
    在项目根目录下运行以下命令，Poetry会自动创建一个虚拟环境并安装所有必需的库。
    ```bash
    poetry install
    ```

### 第三步：设置API密钥

AI分析师需要调用大型语言模型（LLM）和金融数据API，因此您需要配置API密钥。

1.  **创建 `.env` 文件**:
    在项目根目录下，复制 `.env.example` 文件并重命名为 `.env`。
    ```bash
    cp .env.example .env
    ```

2.  **编辑 `.env` 文件**:
    打开 `.env` 文件，并填入您的API密钥。
    ```env
    # 用于运行托管在OpenAI的LLM（例如 gpt-4o, gpt-4o-mini）
    OPENAI_API_KEY="your-openai-api-key"

    # 用于运行托管在Groq的LLM（例如 llama3）
    GROQ_API_KEY="your-groq-api-key"

    # 用于获取金融数据
    # 注意：AAPL, GOOGL, MSFT, NVDA, TSLA 的数据是免费的，无需此密钥。
    # 分析其他股票则必须提供此密钥。
    FINANCIAL_DATASETS_API_KEY="your-financial-datasets-api-key"
    ```
    **重要提示**: 您至少需要提供一个LLM的API密钥才能运行分析。

## 如何调用分析功能

您可以像调用普通的Python函数一样，在您自己的项目中导入并使用本项目的股票分析功能。

### 核心函数：`run_hedge_fund`

这是您需要调用的唯一函数，它封装了所有复杂的分析流程。

```python
from src.main import run_hedge_fund

result = run_hedge_fund(
    tickers=["AAPL", "TSLA"],
    start_date="2024-01-01",
    end_date="2024-03-31",
    portfolio={...},  # 详见下文
    show_reasoning=True,
    selected_analysts=["warren_buffett", "cathie_wood"],
    model_name="gpt-4o",
    model_provider="OpenAI"
)
```

### 参数详解

| 参数 | 类型 | 是否必须 | 默认值 | 描述 |
| --- | --- | --- | --- | --- |
| `tickers` | `list[str]` | 是 | 无 | 要分析的股票代码列表。 |
| `start_date` | `str` | 否 | 90天前 | 分析时间范围的开始日期，格式为 "YYYY-MM-DD"。 |
| `end_date` | `str` | 否 | 今天 | 分析时间范围的结束日期，格式为 "YYYY-MM-DD"。 |
| `portfolio` | `dict` | 是 | 无 | 描述当前投资组合状况的字典，结构见下文示例。 |
| `show_reasoning` | `bool` | 否 | `False` | 是否在控制台打印每个AI分析师的详细分析过程。 |
| `selected_analysts` | `list[str]` | 否 | 所有分析师 | 要使用的AI分析师列表。分析师的key可以在[AI分析师列表](#ai分析师列表)中找到。 |
| `model_name` | `str` | 否 | "gpt-4o" | 要使用的LLM名称。 |
| `model_provider` | `str` | 否 | "OpenAI" | LLM的提供商。 |

### 代码示例：`analysis_example.py`

我们在项目根目录下提供了一个完整的示例文件 `analysis_example.py`。您可以直接运行它来体验分析功能。

```python
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
load_dotenv()

def run_stock_analysis_example():
    """
    一个演示如何调用AI对冲基金股票分析功能的示例函数。
    """
    print("--- 开始运行股票分析示例 ---")

    # --- 1. 定义分析参数 ---
    tickers = ["AAPL", "TSLA"]
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
    portfolio = {
        "cash": 100000.0,
        "margin_requirement": 0.0,
        "margin_used": 0.0,
        "positions": {
            ticker: {
                "long": 0, "short": 0, "long_cost_basis": 0.0,
                "short_cost_basis": 0.0, "short_margin_used": 0.0,
            } for ticker in tickers
        },
        "realized_gains": {
            ticker: {"long": 0.0, "short": 0.0} for ticker in tickers
        },
    }
    selected_analysts = ["warren_buffett", "cathie_wood"]
    model_name = "gpt-4o"
    model_provider = "OpenAI"

    print(f"分析股票: {', '.join(tickers)}")
    print(f"选择的AI分析师: {', '.join(selected_analysts)}")
    print(f"使用的语言模型: {model_name}")

    # --- 2. 调用核心分析函数 ---
    print("\n>>> 正在调用 run_hedge_fund 函数进行分析，请稍候...")
    try:
        result = run_hedge_fund(
            tickers=tickers,
            start_date=start_date,
            end_date=end_date,
            portfolio=portfolio,
            show_reasoning=True,
            selected_analysts=selected_analysts,
            model_name=model_name,
            model_provider=model_provider,
        )
    except Exception as e:
        print(f"\n--- 分析过程中发生错误: {e} ---")
        print("请检查您的 .env 文件中的 API 密钥是否正确配置。")
        return

    # --- 3. 打印分析结果 ---
    print("\n--- 分析完成 ---")
    if result:
        print_trading_output(result)
    else:
        print("未能获取分析结果。")

if __name__ == "__main__":
    run_stock_analysis_example()
```

### 运行示例

1.  确保您已完成[快速开始](#快速开始)中的所有步骤。
2.  在项目根目录下，使用 `poetry run` 命令来运行示例脚本：

    ```bash
    poetry run python analysis_example.py
    ```

## 结果解析

`run_hedge_fund` 函数返回一个字典，包含以下两个关键字段：

*   `decisions`: 一个列表，包含了最终由**投资组合经理**（Portfolio Manager）做出的交易决策。
*   `analyst_signals`: 一个字典，包含了每个AI分析师对每支股票的详细分析结果。

**示例输出** (经过简化):
```json
{
  "decisions": [
    {
      "ticker": "AAPL",
      "action": "BUY",
      "quantity": 10,
      "reasoning": "基于沃伦·巴菲特和凯西·伍德的强烈看涨信号..."
    }
  ],
  "analyst_signals": {
    "warren_buffett_agent": {
      "AAPL": {
        "signal": "bullish",
        "confidence": 90.0,
        "reasoning": "苹果公司拥有强大的品牌护城河和稳定的现金流..."
      },
      "TSLA": {
        "signal": "neutral",
        "confidence": 40.0,
        "reasoning": "特斯拉处于我的能力圈之外，其技术和市场波动性让我难以理解..."
      }
    },
    "cathie_wood_agent": {
      "AAPL": {
        "signal": "bullish",
        "confidence": 85.0,
        "reasoning": "苹果在人工智能和增强现实领域的创新潜力巨大..."
      },
      "TSLA": {
        "signal": "bullish",
        "confidence": 95.0,
        "reasoning": "特斯拉是颠覆性创新的领导者，其在自动驾驶和机器人领域的前景广阔..."
      }
    }
  }
}
```

## AI分析师列表

您可以选择以下一位或多位AI分析师来分析您的股票。

| 分析师 Key (`selected_analysts`) | 显示名称 | 投资风格 |
| --- | --- | --- |
| `aswath_damodaran` | Aswath Damodaran | 注重内在价值和财务指标，通过严谨的估值分析评估投资机会。 |
| `ben_graham` | Ben Graham | 强调安全边际，通过系统的价值分析投资于基本面强劲的被低估公司。 |
| `bill_ackman` | Bill Ackman | 寻求通过战略性激进主义和逆向投资头寸来影响管理层并释放价值。 |
| `cathie_wood` | Cathie Wood | 专注于颠覆性创新和增长，投资于引领技术进步和市场颠覆的公司。 |
| `charlie_munger` | Charlie Munger | 倡导价值投资，注重优质企业和长期增长，通过理性决策进行投资。 |
| `michael_burry` | Michael Burry | 进行逆向押注，通常做空被高估的市场，通过深入的基本面分析投资于被低估的资产。 |
| `peter_lynch` | Peter Lynch | 投资于商业模式易于理解且具有强大增长潜力的公司，采用“买你所知”的策略。 |
| `phil_fisher` | Phil Fisher | 强调投资于管理层强大、产品创新的公司，通过“闲聊法”研究关注长期增长。 |
| `rakesh_jhunjhunwala` | Rakesh Jhunjhunwala | 利用宏观经济洞察力投资于高增长行业，特别是在新兴市场和国内机会。 |
| `stanley_druckenmiller` | Stanley Druckenmiller | 关注宏观经济趋势，通过自上而下的分析对货币、商品和利率进行大额押注。 |
| `warren_buffett` | Warren Buffett | 通过价值投资和长期持有，寻求具有强大基本面和竞争优势的公司。 |
| `technical_analyst` | Technical Analyst | 专注于图表模式和市场趋势，利用技术指标和价格行为分析做出投资决策。 |
| `fundamentals_analyst` | Fundamentals Analyst | 深入研究财务报表和经济指标，通过基本面分析评估公司的内在价值。 |
| `sentiment_analyst` | Sentiment Analyst | 衡量市场情绪和投资者行为，通过行为分析预测市场动向并识别机会。 |
| `valuation_analyst` | Valuation Analyst | 专注于确定公司的公允价值，利用各种估值模型和财务指标进行投资决策。 |
