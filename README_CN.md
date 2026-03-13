# AI对冲基金 - 项目介绍及使用指南

## 📋 项目概述

**AI对冲基金**是一个基于人工智能的量化交易研究平台，通过模拟多位传奇投资大师的投资理念和决策风格，构建了一个多智能体协作的投资决策系统。该项目旨在探索AI在金融投资领域的应用潜力，**仅供教育和研究目的使用，不构成任何投资建议**。

### 🎯 核心特点

1. **多智能体架构** - 12位传奇投资大师AI化身 + 4个专业分析智能体
2. **全栈Web应用** - 提供可视化的工作流编辑器和实时决策展示
3. **回测系统** - 支持历史数据回测，评估策略表现
4. **灵活的LLM支持** - 支持OpenAI、Anthropic、DeepSeek、Groq等多家LLM提供商
5. **本地运行支持** - 可使用Ollama运行本地大模型

## 🏗️ 系统架构

### 智能体体系

系统采用分层决策架构，包含三类智能体：

#### 1️⃣ 投资大师智能体(12位)

每位大师都有独特的投资理念和分析视角：

- **Warren Buffett** - 价值投资之父，寻找优质企业的合理价格
  - 关注护城河、管理质量、内在价值
  - 使用Owner Earnings计算企业真实盈利能力
  - 采用三阶段DCF模型估值

- **Ben Graham** - 价值投资鼻祖，强调安全边际
  - 严格的财务指标筛选
  - 追求被低估的隐藏宝石

- **Charlie Munger** - 理性思维大师，只买卓越企业
  - 多学科思维模型
  - 关注企业长期竞争优势

- **Peter Lynch** - 实用主义投资者，寻找"十倍股"
  - 从日常生活中发现投资机会
  - PEG比率分析

- **Cathie Wood** - 颠覆性创新投资女王
  - 专注前沿科技和创新
  - 长期增长潜力评估

- **Michael Burry** - 《大空头》主角，逆向投资大师
  - 深度价值挖掘
  - 寻找市场错误定价

- **Bill Ackman** - 激进投资者，推动企业变革
  - 主动参与公司治理
  - 催化剂驱动投资

- **Stanley Druckenmiller** - 宏观传奇，寻找不对称机会
  - 宏观趋势分析
  - 高增长潜力标的

- **Mohnish Pabrai** - Dhandho投资者，低风险高回报
  - 集中投资
  - 寻找确定性机会

- **Phil Fisher** - 成长股投资大师，"闲聊"研究法
  - 深度行业研究
  - 管理层质量评估

- **Rakesh Jhunjhunwala** - 印度股神
  - 新兴市场机会
  - 长期成长投资

#### 2️⃣ 专业分析智能体(4个)

- **Valuation Agent** - 估值分析，计算内在价值
- **Fundamentals Agent** - 基本面分析，评估财务健康度
- **Sentiment Agent** - 情绪分析，解读市场情绪和新闻
- **Technicals Agent** - 技术分析，识别价格趋势和信号

#### 3️⃣ 决策执行智能体(2个)

- **Risk Manager** - 风险管理
  - 计算VaR、夏普比率、最大回撤
  - 设置仓位限制和止损
  - 保证金管理

- **Portfolio Manager** - 组合管理
  - 综合所有分析师信号
  - 做出最终交易决策(买入/卖出/做空/平仓/持有)
  - 生成交易订单

### 工作流程

```
用户输入(股票代码、日期范围)
    ↓
12位投资大师并行分析 + 4个专业分析师并行工作
    ↓
Risk Manager 汇总并评估风险
    ↓
Portfolio Manager 做出最终决策
    ↓
输出交易建议和推理过程
```

## 🛠️ 技术栈

### 后端
- **Python 3.11+** - 核心语言
- **LangChain** - LLM应用框架
- **LangGraph** - 多智能体工作流编排
- **FastAPI** - Web API框架
- **SQLAlchemy** - 数据库ORM
- **Pandas/NumPy** - 数据处理和分析

### 前端
- **React + TypeScript** - UI框架
- **React Flow** - 可视化工作流编辑器
- **Tailwind CSS** - 样式框架
- **Shadcn/UI** - 组件库

### 数据源
- **Financial Datasets API** - 金融数据提供商
  - 股价数据
  - 财务指标
  - 内部交易
  - 公司新闻

## 📦 安装指南

### 前置要求

- Python 3.11或更高版本
- Poetry(Python包管理器)
- Node.js 18+(仅Web应用需要)

### 1. 克隆项目

```bash
git clone https://github.com/virattt/ai-hedge-fund.git
cd ai-hedge-fund
```

### 2. 配置API密钥

```bash
# 复制环境变量模板
cp .env.example .env
```

编辑 `.env` 文件，添加必需的API密钥：

```bash
# 金融数据API(必需，除非只交易AAPL/GOOGL/MSFT/NVDA/TSLA)
FINANCIAL_DATASETS_API_KEY=your-key-here

# 至少配置一个LLM提供商(必需)
OPENAI_API_KEY=your-openai-key          # GPT-4等
ANTHROPIC_API_KEY=your-anthropic-key    # Claude系列
DEEPSEEK_API_KEY=your-deepseek-key      # DeepSeek系列
GROQ_API_KEY=your-groq-key              # 快速推理
GOOGLE_API_KEY=your-google-key          # Gemini系列
XAI_API_KEY=your-xai-key                # Grok系列
```

**重要说明:**
- AAPL、GOOGL、MSFT、NVDA、TSLA这5只股票的数据免费，无需API密钥
- 其他股票需要从 [financialdatasets.ai](https://financialdatasets.ai/) 获取API密钥
- 至少需要配置一个LLM提供商的API密钥

### 3. 安装依赖

```bash
# 安装Poetry(如果尚未安装)
curl -sSL https://install.python-poetry.org | python3 -

# 安装项目依赖
poetry install
```

## 🚀 使用方法

### 方式一：命令行界面(CLI)

CLI模式适合快速测试、自动化脚本和集成开发。

#### 基础使用

```bash
# 分析单只股票
poetry run python src/main.py --ticker AAPL

# 分析多只股票
poetry run python src/main.py --ticker AAPL,MSFT,NVDA

# 指定日期范围
poetry run python src/main.py --ticker AAPL --start-date 2024-01-01 --end-date 2024-03-01

# 显示推理过程
poetry run python src/main.py --ticker AAPL --show-reasoning

# 使用本地Ollama模型
poetry run python src/main.py --ticker AAPL --ollama
```

#### 回测模式

```bash
# 运行回测
poetry run python src/backtester.py --ticker AAPL,MSFT,NVDA

# 指定回测时间范围
poetry run python src/backtester.py --ticker AAPL --start-date 2023-01-01 --end-date 2024-01-01

# 使用本地模型回测
poetry run python src/backtester.py --ticker AAPL --ollama
```

#### 命令行参数说明

| 参数 | 说明 | 示例 |
|------|------|------|
| `--ticker` | 股票代码，多个用逗号分隔 | `AAPL,MSFT` |
| `--start-date` | 开始日期(YYYY-MM-DD) | `2024-01-01` |
| `--end-date` | 结束日期(YYYY-MM-DD) | `2024-12-31` |
| `--show-reasoning` | 显示每个智能体的推理过程 | - |
| `--ollama` | 使用本地Ollama模型 | - |
| `--initial-cash` | 初始资金(美元) | `100000` |
| `--margin-requirement` | 保证金要求(0-1) | `0.5` |

### 方式二：Web应用

Web应用提供直观的可视化界面，适合交互式分析和工作流定制。

#### 启动后端

```bash
cd app/backend
poetry install
poetry run fastapi dev main.py
```

后端将在 `http://localhost:8000` 运行

#### 启动前端

```bash
cd app/frontend
npm install
npm run dev
```

前端将在 `http://localhost:5173` 运行

#### Web应用功能

1. **工作流编辑器**
   - 拖拽式构建自定义分析流程
   - 选择特定的投资大师组合
   - 实时可视化决策流程

2. **配置管理**
   - API密钥管理
   - LLM模型选择
   - 主题和外观设置

3. **实时分析**
   - 查看每个智能体的分析结果
   - 追踪决策推理链
   - 可视化投资建议

4. **回测功能**
   - 图形化展示历史表现
   - 性能指标仪表板
   - 交易历史记录

## 📊 输出解读

### 交易决策输出

系统为每只股票输出以下信息：

```json
{
  "AAPL": {
    "action": "buy",           // 操作：buy/sell/short/cover/hold
    "quantity": 100,            // 数量
    "confidence": 85,           // 信心度(0-100)
    "reasoning": "强劲基本面..."  // 推理说明
  }
}
```

### 智能体信号

每个智能体提供：

```json
{
  "signal": "bullish",         // 信号：bullish/bearish/neutral
  "confidence": 80,            // 信心度
  "reasoning": "详细分析..."    // 推理过程
}
```

### 回测指标

- **夏普比率(Sharpe Ratio)** - 风险调整后收益
- **索提诺比率(Sortino Ratio)** - 下行风险调整收益
- **最大回撤(Max Drawdown)** - 最大损失幅度
- **多空比率(Long/Short Ratio)** - 多头与空头仓位比例
- **总敞口(Gross Exposure)** - 总仓位占比
- **净敞口(Net Exposure)** - 净多头/空头敞口

## 🔬 核心算法解析

### Warren Buffett智能体的估值方法

1. **Owner Earnings计算**
   ```
   Owner Earnings = 净利润 + 折旧摊销 - 维护性资本支出 - 营运资本变化
   ```

2. **三阶段DCF估值**
   - 第一阶段(5年)：较高增长率
   - 第二阶段(5年)：过渡增长率
   - 永续阶段：长期GDP增长率

3. **安全边际评估**
   ```
   安全边际 = (内在价值 - 市值) / 市值
   ```

4. **护城河分析**
   - ROE一致性(>15%)
   - 运营利润率稳定性
   - 资产周转效率
   - 定价权(毛利率趋势)

### 风险管理逻辑

```python
# VaR计算(95%置信度)
VaR_95 = μ - 1.645 * σ

# 夏普比率
Sharpe = (组合收益率 - 无风险利率) / 组合标准差

# 仓位限制
最大仓位 = min(风险预算 / VaR, 账户净值 * 最大集中度)
```

## 🎓 适用场景

### 教育用途
- 学习量化投资策略
- 理解多智能体系统设计
- 研究投资大师的决策框架
- LLM在金融领域的应用实践

### 研究用途
- AI辅助投资决策研究
- 多智能体协作机制探索
- 投资策略回测和优化
- 情绪分析与基本面结合

### 开发用途
- 构建自定义投资智能体
- 集成新的数据源
- 开发新的分析指标
- 扩展工作流编排能力

## ⚠️ 重要声明

**本项目仅供教育和研究目的使用：**

1. ❌ **不提供投资建议** - 所有输出仅为模拟结果
2. ❌ **不执行真实交易** - 系统不会连接券商账户
3. ❌ **不保证收益** - 历史表现不代表未来结果
4. ❌ **不承担责任** - 作者对任何财务损失不承担责任

**投资有风险，入市需谨慎。如需投资建议，请咨询专业的财务顾问。**

## 🤝 贡献指南

欢迎贡献代码、报告问题或提出功能建议！

### 贡献流程

1. Fork本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启Pull Request

**注意：** 请保持PR小而专注，便于审查和合并。

### 功能请求

如有功能建议，请在 [GitHub Issues](https://github.com/virattt/ai-hedge-fund/issues) 中提交，并标记为 `enhancement`。

## 📄 许可证

本项目采用MIT许可证 - 详见 [LICENSE](LICENSE) 文件。

## 🔗 相关资源

- **项目仓库：** https://github.com/virattt/ai-hedge-fund
- **Financial Datasets API：** https://financialdatasets.ai/
- **LangChain文档：** https://python.langchain.com/
- **LangGraph文档：** https://langchain-ai.github.io/langgraph/

## 📞 联系方式

- **Twitter：** [@virattt](https://twitter.com/virattt)
- **GitHub Issues：** 技术问题和bug报告

---

**祝您探索AI投资的旅程愉快！** 🚀📈
