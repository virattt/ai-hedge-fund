# AI Hedge Fund 
人工智能对冲基金

This is a proof of concept for an AI-powered hedge fund.  The goal of this project is to explore the use of AI to make trading decisions.  This project is for **educational** purposes only and is not intended for real trading or investment.
这是一个人工智能驱动对冲基金的概念验证。本项目的目标是探索如何利用人工智能做出交易决策。本项目仅用于 ** 教育 ** 目的，并非针对实际交易或投资。
This system employs several agents working together:
这个系统使用多个代理人共同工作：
1. Aswath Damodaran Agent - The Dean of Valuation, focuses on story, numbers, and disciplined valuation
1. 达摩德仁经纪人 —— 估值主任，专注于故事、数字和有纪律的估值
2. Ben Graham Agent - The godfather of value investing, only buys hidden gems with a margin of safety
2. 本杰明・格雷厄姆经纪人 —— 价值投资的教父，只买有安全程度的隐藏宝石
3. Bill Ackman Agent - An activist investor, takes bold positions and pushes for change
3. 比尔・阿克曼经纪人 —— 一位活跃的投资者，采取大胆立场并推动变革
4. Cathie Wood Agent - The queen of growth investing, believes in the power of innovation and disruption
4. 凯西・伍德经纪人 —— 增长投资女王，相信创新和颠覆的力量
5. Charlie Munger Agent - Warren Buffett's partner, only buys wonderful businesses at fair prices
5. 查理・芒格经纪人 —— 沃伦・巴菲特的合伙人，只以合理价格收购优秀企业
6. Michael Burry Agent - The Big Short contrarian who hunts for deep value
6. 迈克尔・巴里经纪人 —— 寻找深层价值的大空头逆势者
7. Mohnish Pabrai Agent - The Dhandho investor, who looks for doubles at low risk
7. 莫尼什・帕布莱经纪人 ——Dhandho 的投资者，他寻找低风险的替身
8. Peter Lynch Agent - Practical investor who seeks "ten-baggers" in everyday businesses
8. 彼得・林奇经纪人 —— 在日常业务中寻找 “十包” 的务实投资者
9. Phil Fisher Agent - Meticulous growth investor who uses deep "scuttlebutt" research
9. 菲尔・费希尔经纪人 —— 一位使用深度 “暗桩” 研究的细致成长型投资者
10. Rakesh Jhunjhunwala Agent - The Big Bull of India
10. 拉凯什・亨亨瓦拉经纪人 —— 印度的大牛
11. Stanley Druckenmiller Agent - Macro legend who hunts for asymmetric opportunities with growth potential
11. 斯坦利・德鲁肯米勒经纪人 —— 宏的传奇人物，寻找具有增长潜力的非对称机会
12. Warren Buffett Agent - The oracle of Omaha, seeks wonderful companies at a fair price
12. 沃伦・巴菲特经纪人 —— 奥马哈的神谕，寻找价格合理的优秀公司
13. Valuation Agent - Calculates the intrinsic value of a stock and generates trading signals
13. 价值代理 —— 计算股票的内在价值并生成交易信号
14. Sentiment Agent - Analyzes market sentiment and generates trading signals
14. 情绪代理 —— 分析市场情绪并生成交易信号
15. Fundamentals Agent - Analyzes fundamental data and generates trading signals
15. 基本面代理 —— 分析基本面数据并生成交易信号
16. Technicals Agent - Analyzes technical indicators and generates trading signals
16. 技术代理 - 分析技术指标并生成交易信号
17. Risk Manager - Calculates risk metrics and sets position limits
17. 风险经理 —— 计算风险指标并设定头寸限制
17. Portfolio Manager - Makes final trading decisions and generates orders
17. 投资组合经理 —— 做出最终交易决策并生成订单
<img width="1042" alt="Screenshot 2025-03-22 at 6 19 07 PM" src="https://github.com/user-attachments/assets/cbae3dcf-b571-490d-b0ad-3f0f035ac0d4" />

Note: the system does not actually make any trades.
注意：系统实际上不会进行任何交易。

[![Twitter Follow](https://img.shields.io/twitter/follow/virattt?style=social)](https://twitter.com/virattt)

## Disclaimer
声明
This project is for **educational and research purposes only**.
这个项目仅用于教育和研究目的。
- Not intended for real trading or investment
- No investment advice or guarantees provided
- Creator assumes no liability for financial losses
- Consult a financial advisor for investment decisions
- Past performance does not indicate future results
不适用于实际交易或投资

未提供投资建议或保证

创造者对财务损失不承担任何责任

就投资决策咨询财务顾问

过去的表现并不能预示未来的结果
By using this software, you agree to use it solely for learning purposes.
使用此软件，即表示您同意仅将其用于学习目的。
## Table of Contents
- [How to Install](#how-to-install)
- [How to Run](#how-to-run)
  - [⌨️ Command Line Interface](#️-command-line-interface)
  - [🖥️ Web Application](#️-web-application)
- [How to Contribute](#how-to-contribute)
- [Feature Requests](#feature-requests)
- [License](#license)

## How to Install
如何安装

Before you can run the AI Hedge Fund, you'll need to install it and set up your API keys. These steps are common to both the full-stack web application and command line interface.
在运行 AI 对冲基金之前，您需要安装它并设置 API 密钥。这些步骤对于全栈 Web 应用程序和命令行界面都是常见的。

### 1. Clone the Repository
克隆仓库
```bash
git clone https://github.com/virattt/ai-hedge-fund.git
cd ai-hedge-fund
```

### 2. Set up API keys
设置 API 密钥

Create a `.env` file for your API keys:
```bash
# Create .env file for your API keys (in the root directory)
cp .env.example .env
```

Open and edit the `.env` file to add your API keys:
```bash
# For running LLMs hosted by openai (gpt-4o, gpt-4o-mini, etc.)
OPENAI_API_KEY=your-openai-api-key

# For getting financial data to power the hedge fund
FINANCIAL_DATASETS_API_KEY=your-financial-datasets-api-key
```

**Important**: You must set at least one LLM API key (e.g. `OPENAI_API_KEY`, `GROQ_API_KEY`, `ANTHROPIC_API_KEY`, or `DEEPSEEK_API_KEY`) for the hedge fund to work. 

**Financial Data**: Data for AAPL, GOOGL, MSFT, NVDA, and TSLA is free and does not require an API key. For any other ticker, you will need to set the `FINANCIAL_DATASETS_API_KEY` in the .env file.

## How to Run
如何运行

### ⌨️ Command Line Interface
命令行界面

You can run the AI Hedge Fund directly via terminal. This approach offers more granular control and is useful for automation, scripting, and integration purposes.
您可以直接通过终端运行 AI 对冲基金。这种方法提供了更细粒度的控制，对自动化、脚本编写和集成目的非常有用。

<img width="992" alt="Screenshot 2025-01-06 at 5 50 17 PM" src="https://github.com/user-attachments/assets/e8ca04bf-9989-4a7d-a8b4-34e04666663b" />

#### Quick Start
快速启动

1. Install Poetry (if not already installed):
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

2. Install dependencies:
```bash
poetry install
```

#### Run the AI Hedge Fund
运营 AI 对冲基金

```bash
poetry run python src/main.py --ticker AAPL,MSFT,NVDA
```

You can also specify a `--ollama` flag to run the AI hedge fund using local LLMs.

```bash
poetry run python src/main.py --ticker AAPL,MSFT,NVDA --ollama
```

You can optionally specify the start and end dates to make decisions over a specific time period.

```bash
poetry run python src/main.py --ticker AAPL,MSFT,NVDA --start-date 2024-01-01 --end-date 2024-03-01
```

#### Run the Backtester
运行 Backtester

```bash
poetry run python src/backtester.py --ticker AAPL,MSFT,NVDA
```

**Example Output:**
<img width="941" alt="Screenshot 2025-01-06 at 5 47 52 PM" src="https://github.com/user-attachments/assets/00e794ea-8628-44e6-9a84-8f8a31ad3b47" />


Note: The `--ollama`, `--start-date`, and `--end-date` flags work for the backtester, as well!

### 🖥️ Web Application

The new way to run the AI Hedge Fund is through our web application that provides a user-friendly interface. This is recommended for users who prefer visual interfaces over command line tools.

Please see detailed instructions on how to install and run the web application [here](https://github.com/virattt/ai-hedge-fund/tree/main/app).
运行 AI 对冲基金的新方式是通过我们的 Web 应用程序，它提供了用户友好的界面。建议那些更喜欢可视化界面而非命令行工具的用户使用这种方式。

请参阅如何安装和运行 Web 应用的详细说明 [此处](https://github.com/virattt/ai-hedge-fund/tree/main/app)。

<img width="1721" alt="Screenshot 2025-06-28 at 6 41 03 PM" src="https://github.com/user-attachments/assets/b95ab696-c9f4-416c-9ad1-51feb1f5374b" />


## How to Contribute
如何贡献

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

1. 分叉代码仓库
2. 创建一个功能分支
3. 提交你的修改
4. 推送到分支
5. 创建拉动请求
   
**Important**: Please keep your pull requests small and focused.  This will make it easier to review and merge
****

## Feature Requests

If you have a feature request, please open an [issue](https://github.com/virattt/ai-hedge-fund/issues) and make sure it is tagged with `enhancement`.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
