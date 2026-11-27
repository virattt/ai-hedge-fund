# AI 对冲基金

这是一个 AI 驱动的对冲基金概念项目。本项目的目标是探索 AI 在交易决策中的应用。**本项目仅用于教育目的**，不适用于真实交易或投资。

该系统采用多个 Agent 协同工作：

1. **Aswath Damodaran Agent** - 估值学泰斗，注重故事、数据和严谨的估值方法
2. **Ben Graham Agent** - 价值投资教父，只买具有安全边际的隐藏宝石
3. **Bill Ackman Agent** - 激进投资者，采取大胆持仓并推动变革
4. **Cathie Wood Agent** - 增长投资女王，相信创新和颠覆的力量
5. **Charlie Munger Agent** - 巴菲特搭档，只以合理价格买入优秀企业
6. **Michael Burry Agent** - 大空头逆向投资者，寻找深度价值
7. **Mohnish Pabrai Agent** - Dhandho 投资者，寻找低风险的双倍机会
8. **Peter Lynch Agent** - 务实投资者，寻找日常业务中的"十倍股"
9. **Phil Fisher Agent** - 精益求精的增长投资者，使用深度"小道消息"研究
10. **Rakesh Jhunjhunwala Agent** - 印度股市大牛
11. **Stanley Druckenmiller Agent** - 宏观传奇，寻找具有增长潜力的非对称机会
12. **Warren Buffett Agent** - 奥马哈先知，以公平价格寻找优秀公司
13. **Valuation Agent** - 计算股票内在价值并生成交易信号
14. **Sentiment Agent** - 分析市场情绪并生成交易信号
15. **Fundamentals Agent** - 分析基本面数据并生成交易信号
16. **Technicals Agent** - 分析技术指标并生成交易信号
17. **Risk Manager** - 计算风险指标并设置仓位限制
18. **Portfolio Manager** - 最终交易决策并生成订单

> 注意：该系统不会实际进行任何交易。

## 免责声明

本项目仅用于**教育和研究目的**。

- 不适用于真实交易或投资
- 不提供投资建议或任何保证
- 创建者不对任何财务损失承担任何责任
- 投资决策请咨询 financial advisor
- 过往业绩不代表未来表现

使用本软件即表示您同意仅将其用于学习目的。

## 目录

- [如何安装](#如何安装)
- [如何运行](#如何运行)
  - [⌨️ 命令行界面](#️-命令行界面)
  - [🖥️ Web 应用](#️-web-应用)
- [如何贡献](#如何贡献)
- [功能建议](#功能建议)
- [许可证](#许可证)

## 如何安装

在运行 AI 对冲基金之前，您需要安装并设置 API 密钥。这些步骤适用于 Web 应用和命令行界面。

### 1. 克隆仓库

```bash
git clone https://github.com/virattt/ai-hedge-fund.git
cd ai-hedge-fund
```

### 2. 设置 API 密钥

创建 `.env` 文件用于存储您的 API 密钥：

```bash
# 在根目录创建 .env 文件
cp .env.example .env
```

打开并编辑 `.env` 文件以添加您的 API 密钥：

```bash
# 用于运行 LLM（gpt-4o, gpt-4o-mini 等）
OPENAI_API_KEY=your-openai-api-key

# 用于获取财务数据
FINANCIAL_DATASETS_API_KEY=your-financial-datasets-api-key
```

**重要**：您必须至少设置一个 LLM API 密钥（如 `OPENAI_API_KEY`、`GROQ_API_KEY`、`ANTHROPIC_API_KEY` 或 `DEEPSEEK_API_KEY`），对冲基金才能运行。

**财务数据**：AAPL、GOOGL、MSFT、NVDA 和 TSLA 的数据是免费的，无需 API 密钥。其他任何股票需要设置 `FINANCIAL_DATASETS_API_KEY`。

## 如何运行

### ⌨️ 命令行界面

您可以直接通过终端运行 AI 对冲基金。这种方式提供更精细的控制，适用于自动化、脚本和集成目的。

#### 快速开始

1. 安装 Poetry（如果尚未安装）：

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

2. 安装依赖：

```bash
poetry install
```

#### 运行 AI 对冲基金

```bash
poetry run python src/main.py --ticker AAPL,MSFT,NVDA
```

您还可以指定 `--ollama` 标志来使用本地 LLM 运行：

```bash
poetry run python src/main.py --ticker AAPL,MSFT,NVDA --ollama
```

您可以选择指定开始和结束日期来在特定时间段内做出决策：

```bash
poetry run python src/main.py --ticker AAPL,MSFT,NVDA --start-date 2024-01-01 --end-date 2024-03-01
```

#### 运行回测

```bash
poetry run python src/backtester.py --ticker AAPL,MSFT,NVDA
```

> 注意：`--ollama`、`--start-date` 和 `--end-date` 标志也适用于回测！

### 🖥️ Web 应用

运行 AI 对冲基金的新方式是通过我们的 Web 应用，提供友好的用户界面。建议喜欢图形界面的用户使用。

详细安装和运行说明请查看 [这里](https://github.com/virattt/ai-hedge-fund/tree/main/app)。

## 如何贡献

1. Fork 仓库
2. 创建功能分支
3. 提交更改
4. 推送到分支
5. 创建 Pull Request

**重要**：请保持您的 Pull Request 小而专注，这样可以更容易地审查和合并。

## 功能建议

如果您有功能请求，请打开一个 issue 并确保标记为 `enhancement`。

## 许可证

本项目基于 MIT 许可证 - 详见 LICENSE 文件。