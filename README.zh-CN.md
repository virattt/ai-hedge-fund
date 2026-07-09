# AI 对冲基金

[English](README.md) | **简体中文**

这是一个由 AI 驱动的对冲基金的概念验证（proof of concept）。本项目的目标在于探索如何利用 AI 做出交易决策。本项目**仅供学习与教学**用途，不适用于任何真实交易或投资。

> **🚧 项目正在演进。** 我们正将其重构为一个持久运行、常驻在线的 AI 对冲基金——把"基金（fund）"作为一等公民，你可以对其进行回测、模拟交易，并在（可选开启的）实盘中运行，同时把各位投资者 agent 重新设计为可插拔、可回测的"alpha 模型（alpha models）"。详情请阅读 **[愿景 →](VISION.md)** 与 **[路线图 →](ROADMAP.md)**。

本系统由多个协同工作的 agent 组成：

1. Aswath Damodaran Agent（阿斯瓦特·达摩达兰）——"估值院长"，专注故事、数字与严谨的估值
2. Ben Graham Agent（本·格雷厄姆）——价值投资教父，只买入带有安全边际的"隐藏宝石"
3. Bill Ackman Agent（比尔·阿克曼）——激进型投资者，敢于重仓并推动变革
4. Cathie Wood Agent（凯茜·伍德）——成长投资女王，坚信创新与颠覆的力量
5. Charlie Munger Agent（查理·芒格）——巴菲特的搭档，只以合理价格买入优秀企业
6. Michael Burry Agent（迈克尔·伯里）——《大空头》中的逆向投资者，挖掘深度价值
7. Mohnish Pabrai Agent（莫尼什·帕伯莱）——"Dhandho 投资者"，寻找低风险下的翻倍机会
8. Nassim Taleb Agent（纳西姆·塔勒布）——"黑天鹅"风险分析师，专注尾部风险、反脆弱与非对称收益
9. Peter Lynch Agent（彼得·林奇）——务实的投资者，从日常生意中寻找"十倍股"
10. Phil Fisher Agent（菲利普·费雪）——严谨的成长型投资者，善用深入的"闲聊法（scuttlebutt）"调研
11. Rakesh Jhunjhunwala Agent（拉克什·琼琼瓦拉）——"印度大牛市"
12. Stanley Druckenmiller Agent（斯坦利·德鲁肯米勒）——宏观传奇，寻找具成长潜力的非对称机会
13. Warren Buffett Agent（沃伦·巴菲特）——"奥马哈先知"，以合理价格寻找优秀公司
14. Valuation Agent（估值 Agent）——计算股票内在价值并生成交易信号
15. Sentiment Agent（情绪 Agent）——分析市场情绪并生成交易信号
16. Fundamentals Agent（基本面 Agent）——分析基本面数据并生成交易信号
17. Technicals Agent（技术面 Agent）——分析技术指标并生成交易信号
18. Risk Manager（风险经理）——计算风险指标并设定仓位限制
19. Portfolio Manager（投资组合经理）——做出最终交易决策并生成订单

<img width="1042" alt="Screenshot 2025-03-22 at 6 19 07 PM" src="https://github.com/user-attachments/assets/cbae3dcf-b571-490d-b0ad-3f0f035ac0d4" />

注意：本系统并不会执行任何真实交易。

[![Twitter Follow](https://img.shields.io/twitter/follow/virattt?style=social)](https://twitter.com/virattt)

## 免责声明

本项目**仅供学习与研究用途**。

- 不适用于真实交易或投资
- 不提供任何投资建议或收益保证
- 创作者对任何财务损失不承担责任
- 投资决策请咨询专业的理财顾问
- 历史业绩不代表未来表现

使用本软件即表示您同意仅将其用于学习目的。

## 目录
- [安装方法](#安装方法)
- [运行方式](#运行方式)
  - [⌨️ 命令行界面](#️-命令行界面)
  - [🖥️ Web 应用](#️-web-应用)
- [如何贡献](#如何贡献)
- [功能建议](#功能建议)
- [许可证](#许可证)

## 安装方法

在运行 AI 对冲基金之前，你需要先安装项目并配置 API 密钥。以下步骤对全栈 Web 应用和命令行界面都适用。

### 1. 克隆仓库

```bash
git clone https://github.com/virattt/ai-hedge-fund.git
cd ai-hedge-fund
```

### 2. 配置 API 密钥

为你的 API 密钥创建一个 `.env` 文件：
```bash
# 在根目录下为你的 API 密钥创建 .env 文件
cp .env.example .env
```

打开并编辑 `.env` 文件，填入你的 API 密钥：
```bash
# 用于运行 OpenAI 托管的 LLM（gpt-4o、gpt-4o-mini 等）
OPENAI_API_KEY=your-openai-api-key

# 用于获取驱动对冲基金的金融数据（美股 financialdatasets.ai；A 股默认通过 AKShare/efinance 获取，无需此 key）
FINANCIAL_DATASETS_API_KEY=your-financial-datasets-api-key
```

**重要提示**：你必须至少配置一个 LLM 的 API 密钥（例如 `OPENAI_API_KEY`、`GROQ_API_KEY`、`ANTHROPIC_API_KEY` 或 `DEEPSEEK_API_KEY`），对冲基金才能正常运行。

## 运行方式

### ⌨️ 命令行界面

你可以直接通过终端运行 AI 对冲基金。这种方式提供更细粒度的控制，适合用于自动化、脚本以及集成场景。

<img width="992" alt="Screenshot 2025-01-06 at 5 50 17 PM" src="https://github.com/user-attachments/assets/e8ca04bf-9989-4a7d-a8b4-34e04666663b" />

#### 快速开始

1. 安装 Poetry（如尚未安装）：
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

2. 安装依赖：
```bash
poetry install
```

#### 运行 AI 对冲基金
```bash
poetry run python src/main.py --ticker 600519.SH,000858.SZ,300750.SZ
```

你也可以指定 `--ollama` 参数，使用本地 LLM 来运行 AI 对冲基金。

```bash
poetry run python src/main.py --ticker 600519.SH,000858.SZ,300750.SZ --ollama
```

你还可以选择性地指定起始和结束日期，在特定时间段内做出决策。

```bash
poetry run python src/main.py --ticker 600519.SH,000858.SZ,300750.SZ --start-date 2024-01-01 --end-date 2024-03-01
```

#### A 股说明

- **代码格式**：A 股使用 Tushare 格式——6 位代码 + 交易所后缀：`.SH`（上交所）、`.SZ`（深交所）、`.BJ`（北交所）。例如 `600519.SH`（贵州茅台）、`000858.SZ`（五粮液）、`300750.SZ`（宁德时代）。
- **数据来源**：A 股默认使用免费数据源：[AKShare](https://akshare.akfamily.xyz/) + efinance，必要时再用 Yahoo Finance 做兜底，**无需 `FINANCIAL_DATASETS_API_KEY`**；该密钥仅用于美股（financialdatasets.ai）。
- **可选 Tushare**：如需 Tushare `daily_basic` 的历史时点估值，可设置 `A_SHARE_USE_TUSHARE_VALUATION=true`，并配置 `TUSHARE_TOKEN` 或 `TUSHARE_DATASETS_API_KEY`。默认不开启，避免额度/频率限制影响普通运行。
- **仍需 LLM 密钥**：无论 A 股还是美股，agent 的推理都需要至少一个 LLM 密钥（如 `OPENAI_API_KEY`、`DEEPSEEK_API_KEY`，或使用 `--ollama` 本地模型）。
- **数据局限**：AKShare 的 TTM 财报目前以年报数据近似（详见 [`src/tools/api_akshare.py`](src/tools/api_akshare.py)）。

#### 数据缓存（避免每个 agent 重复拉取数据）

所有 agent 共享同一份**进程内内存缓存**（[`src/data/cache.py`](src/data/cache.py)）。工作流启动时，入口节点会先扫描各 agent 实际请求的财报科目与指标，**一次性预取**每只股票的数据（[`src/utils/data_warming.py`](src/utils/data_warming.py)）；随后 14 个分析 agent 并行运行时直接命中缓存，不再各自重复请求。此外 `search_line_items` 会按"字段子集"复用——后请求的 agent 只会拉取缓存里还没有的字段。

效果（单只股票、全部 agent）：外部 API 调用从约 **27 次降到 7 次（≈74%）**，且预取阶段按股票并发、agent 阶段零调用。

#### 运行回测器
```bash
poetry run python src/backtester.py --ticker 600519.SH,000858.SZ,300750.SZ
```

**示例输出：**
<img width="941" alt="Screenshot 2025-01-06 at 5 47 52 PM" src="https://github.com/user-attachments/assets/00e794ea-8628-44e6-9a84-8f8a31ad3b47" />


注意：`--ollama`、`--start-date` 和 `--end-date` 这些参数在回测器中同样可用！

### 🖥️ Web 应用

运行 AI 对冲基金的新方式是通过我们的 Web 应用，它提供了友好的图形界面。如果你更偏好可视化界面而非命令行工具，推荐使用这种方式。

关于安装和运行 Web 应用的详细说明，请参见[这里](https://github.com/virattt/ai-hedge-fund/tree/main/app)。

<img width="1721" alt="Screenshot 2025-06-28 at 6 41 03 PM" src="https://github.com/user-attachments/assets/b95ab696-c9f4-416c-9ad1-51feb1f5374b" />


## 如何贡献

1. Fork 本仓库
2. 创建功能分支（feature branch）
3. 提交你的修改
4. 推送到该分支
5. 创建 Pull Request

**重要**：请保持你的 Pull Request 小而聚焦，这样更便于审查与合并。

## 功能建议

如果你有功能建议，请提交一个 [issue](https://github.com/virattt/ai-hedge-fund/issues)，并确保打上 `enhancement` 标签。

## 许可证

本项目基于 MIT 许可证授权——详情请参阅 LICENSE 文件。
