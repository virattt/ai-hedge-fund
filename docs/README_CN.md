# 这是一个 AI 驱动对冲基金的概念验证项目

本项目旨在探索使用 AI 做出交易决策的可能性。  
通过结合多位传奇投资人的投资理念与现代大语言模型（LLM），系统能够模拟多策略、多角色的投资决策流程。

> ⚠️ 本项目仅供 **教育与研究用途**，并不适用于真实交易或投资。

---

# ✨ 项目亮点

- 🤖 多智能体（Multi-Agent）协同投资分析
- 📊 结合基本面、技术面、情绪面与估值分析
- 🧠 模拟传奇投资人的投资风格
- ⚡ 支持 OpenAI、Anthropic、Groq、DeepSeek 等模型
- 🖥️ 提供 CLI 与 Web UI 两种使用方式
- 📈 支持历史回测（Backtesting）
- 🔌 支持本地 LLM（Ollama）
- 🛠️ 易于扩展新的 Agent 与策略

---

# 🧠 系统架构

整个系统采用“多智能体协作”架构。

每个 Agent 都拥有独立的分析逻辑与投资哲学，最终由 Portfolio Manager 汇总各方意见并生成最终决策。

```text
市场数据
   ↓
数据分析层
 ├── Fundamentals Agent
 ├── Technicals Agent
 ├── Sentiment Agent
 └── Valuation Agent
   ↓
投资大师 Agent 层
 ├── Warren Buffett Agent
 ├── Charlie Munger Agent
 ├── Cathie Wood Agent
 ├── Michael Burry Agent
 └── ...
   ↓
Risk Manager
   ↓
Portfolio Manager
   ↓
最终交易信号（不会真实下单）
```

---

# 👥 智能代理（Agents）

该系统由多个智能代理协同工作：

## 📚 投资大师代理

1. **Aswath Damodaran Agent**  
   “估值学院院长”，专注于故事、数据与纪律化估值

2. **Ben Graham Agent**  
   价值投资之父，只买具备安全边际的隐藏宝石

3. **Bill Ackman Agent**  
   激进投资者，采取大胆仓位并推动企业变革

4. **Cathie Wood Agent**  
   成长投资女王，相信创新与颠覆的力量

5. **Charlie Munger Agent**  
   沃伦·巴菲特的合伙人，只以合理价格买入优秀企业

6. **Michael Burry Agent**  
   《大空头》逆向投资者，专注寻找深度价值

7. **Mohnish Pabrai Agent**  
   Dhandho 投资者，以低风险寻找翻倍机会

8. **Nassim Taleb Agent**  
   “黑天鹅”风险分析师，关注尾部风险、反脆弱性与非对称收益

9. **Peter Lynch Agent**  
   务实投资者，在日常企业中寻找“十倍股”

10. **Phil Fisher Agent**  
    严谨的成长投资者，使用深入的 “scuttlebutt” 调研方法

11. **Rakesh Jhunjhunwala Agent**  
    印度“大牛市之王”

12. **Stanley Druckenmiller Agent**  
    宏观投资传奇，寻找具备成长潜力的非对称机会

13. **Warren Buffett Agent**  
    “奥马哈先知”，以合理价格寻找优秀公司

---

## 📊 分析型代理

14. **Valuation Agent**  
    计算股票内在价值并生成交易信号

15. **Sentiment Agent**  
    分析市场情绪并生成交易信号

16. **Fundamentals Agent**  
    分析基本面数据并生成交易信号

17. **Technicals Agent**  
    分析技术指标并生成交易信号

---

## ⚠️ 风险与组合管理

18. **Risk Manager**  
    计算风险指标并设置仓位限制

19. **Portfolio Manager**  
    汇总所有 Agent 的观点，做出最终交易决策并生成订单

---

<img width="1042" alt="Screenshot 2025-03-22 at 6 19 07 PM" src="https://github.com/user-attachments/assets/cbae3dcf-b571-490d-b0ad-3f0f035ac0d4" />

---

# ⚠️ 重要说明

该系统：

- 不会连接真实券商
- 不会自动执行交易
- 不会管理真实资金
- 不构成投资建议

所有输出仅用于：

- 学习 AI Agent 架构
- 学习量化投资思维
- 研究多模型协作系统
- 金融数据分析实验

---

# 🧪 技术栈

## 后端

- Python
- LangChain
- Pandas
- NumPy
- FastAPI

## AI 模型

支持：

- OpenAI
- Anthropic Claude
- Groq
- DeepSeek
- Ollama（本地模型）

## 数据源

- Financial Datasets API
- 市场行情数据
- 财务报表数据
- 新闻与情绪数据

---

# 📂 项目结构

```text
ai-hedge-fund/
│
├── src/                 # 核心源码
├── agents/              # Agent 定义
├── backtester/          # 回测模块
├── app/                 # Web 应用
├── data/                # 数据处理
├── prompts/             # LLM Prompt
├── examples/            # 示例
├── tests/               # 测试
│
├── .env.example
├── pyproject.toml
└── README.md
```

---

# 📦 安装方法

在运行 AI Hedge Fund 之前，您需要先完成安装并配置 API 密钥。

## 1. 克隆仓库

```bash
git clone https://github.com/virattt/ai-hedge-fund.git
cd ai-hedge-fund
```

---

## 2. 配置 API 密钥

创建 `.env` 文件：

```bash
cp .env.example .env
```

编辑 `.env`：

```bash
# OpenAI
OPENAI_API_KEY=your-openai-api-key

# 金融数据 API
FINANCIAL_DATASETS_API_KEY=your-financial-datasets-api-key
```

### 支持的模型提供商

你也可以使用：

```bash
ANTHROPIC_API_KEY=
GROQ_API_KEY=
DEEPSEEK_API_KEY=
```

> 至少需要配置一个 LLM API Key。

---

# 🚀 运行方法

## ⌨️ 命令行模式

### 安装 Poetry

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

### 安装依赖

```bash
poetry install
```

---

## ▶️ 运行 AI Hedge Fund

```bash
poetry run python src/main.py --ticker AAPL,MSFT,NVDA
```

---

## 🖥️ 使用本地模型（Ollama）

```bash
poetry run python src/main.py --ticker AAPL,MSFT,NVDA --ollama
```

---

## 📅 指定分析时间范围

```bash
poetry run python src/main.py \
  --ticker AAPL,MSFT,NVDA \
  --start-date 2024-01-01 \
  --end-date 2024-03-01
```

---

# 📈 回测系统（Backtester）

运行历史回测：

```bash
poetry run python src/backtester.py --ticker AAPL,MSFT,NVDA
```

系统将：

- 模拟历史投资决策
- 计算收益率
- 分析风险指标
- 输出策略表现

---

# 🖥️ Web 应用

Web UI 提供：

- 图形化股票分析
- Agent 决策展示
- 回测可视化
- 多模型切换
- 更友好的交互体验

安装与运行说明：

https://github.com/virattt/ai-hedge-fund/tree/main/app

---

# 🔧 自定义 Agent

你可以非常容易地创建自己的投资 Agent。

示例：

```python
class MyInvestorAgent:
    def analyze(self, stock_data):
        return {
            "signal": "BUY",
            "confidence": 0.82,
            "reasoning": "Strong revenue growth"
        }
```

---

# 📈 示例分析流程

以 `NVDA` 为例：

1. Fundamentals Agent 分析财务数据
2. Technicals Agent 检查技术指标
3. Sentiment Agent 分析新闻与社交媒体情绪
4. Buffett Agent 判断护城河
5. Cathie Wood Agent 判断成长潜力
6. Risk Manager 控制仓位风险
7. Portfolio Manager 汇总意见

最终生成：

```json
{
  "ticker": "NVDA",
  "action": "BUY",
  "confidence": 0.91
}
```

---

# ⚠️ 免责声明

本项目仅用于 **教育与研究目的**。

- 不适用于真实交易或投资
- 不提供任何投资建议或收益保证
- 项目创建者不对金融损失承担责任
- 请在投资决策前咨询专业财务顾问
- 过去的表现不代表未来结果

使用本软件即表示您同意仅将其用于学习目的。

---

# 🤝 如何贡献

1. Fork 本仓库
2. 创建功能分支
3. 提交修改
4. Push 到分支
5. 创建 Pull Request

---

# 💡 功能建议

如果您有功能建议：

1. 创建 Issue
2. 添加 `enhancement` 标签
3. 描述您的需求与使用场景


---

# 📄 许可证

本项目基于 MIT License 开源。

详情请查看 LICENSE 文件。
