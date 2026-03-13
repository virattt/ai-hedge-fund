# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在此代码库中工作时提供指导。

## 项目概述

这是一个使用多个 AI 代理进行交易决策的 AI 对冲基金系统。这是一个概念验证项目，仅用于教育目的，不用于实际交易。

### 架构

系统采用基于 LangGraph 的多代理架构：

1. **分析师代理**（共18个）：著名投资者角色（沃伦·巴菲特、查理·芒格等）和专业分析师（基本面、技术面、情绪、估值、成长、新闻情绪）。每个代理分析市场数据并生成带有置信度评分的交易信号。

2. **风险管理器**：基于投资组合约束、保证金要求和风险指标计算仓位限制。

3. **投资组合管理器**：通过综合分析师信号和风险约束做出最终交易决策。使用确定性行动验证来确保交易符合现金、保证金和仓位限制。

4. **状态管理**：`AgentState`（src/graph/state.py）在图中流转，包含：
   - `messages`：代理通信
   - `data`：投资组合状态、分析师信号、股票代码数据、当前价格
   - `metadata`：配置（show_reasoning、model_name、model_provider）

### 核心组件

- **src/agents/**：各个代理的实现及其投资策略
- **src/graph/state.py**：LangGraph 状态定义和工具函数
- **src/backtesting/**：回测引擎，包含投资组合跟踪、交易执行和性能指标
- **src/llm/models.py**：LLM 提供商抽象层，支持 OpenAI、Anthropic、Google、Groq、DeepSeek、Ollama、Azure OpenAI、xAI、GigaChat、OpenRouter 和美团/MiniMax
- **src/tools/api.py**：金融数据 API 集成
- **app/backend/**：FastAPI Web 应用后端
- **app/frontend/**：React + Vite 前端，使用 XyFlow 进行图可视化

## 开发命令

### Python 后端

```bash
# 安装依赖
poetry install

# 运行对冲基金（CLI）- 需要指定所有参数以避免交互式提示
poetry run python src/main.py --tickers AAPL,MSFT,NVDA --analysts-all --model "deepseek-chat"

# 运行指定日期范围
poetry run python src/main.py --tickers AAPL --analysts-all --model "deepseek-chat" --start-date 2024-01-01 --end-date 2024-03-01

# 使用本地 Ollama 模型运行
poetry run python src/main.py --tickers AAPL --analysts-all --ollama --model "llama3"

# 指定特定分析师（而不是全部）
poetry run python src/main.py --tickers AAPL --analysts "warren_buffett,charlie_munger" --model "deepseek-chat"

# 运行回测器
poetry run python src/backtester.py --tickers AAPL,MSFT,NVDA --analysts-all --model "deepseek-chat"

# 备用回测器命令
poetry run backtester --tickers AAPL --analysts-all --model "deepseek-chat"

# 运行测试
poetry run pytest

# 运行特定测试文件
poetry run pytest tests/backtesting/test_portfolio.py

# 运行测试并输出详细信息
poetry run pytest -v

# 代码格式化
poetry run black src/ tests/

# 代码检查
poetry run flake8 src/ tests/
```

### 命令行参数说明

- `--tickers`: 必需，股票代码列表，用逗号分隔（例如：AAPL,MSFT,GOOGL）
- `--analysts-all`: 使用所有可用的分析师（推荐）
- `--analysts`: 指定特定分析师，用逗号分隔（例如：warren_buffett,charlie_munger）
- `--model`: 指定模型名称（例如：deepseek-chat, glm-5, MiniMax-M2.5）
- `--ollama`: 使用本地 Ollama 模型
- `--start-date`: 开始日期（YYYY-MM-DD）
- `--end-date`: 结束日期（YYYY-MM-DD）
- `--initial-cash`: 初始现金（默认：100000.0）
- `--margin-requirement`: 空头保证金要求比率（例如：0.5 表示 50%，默认：0.0）
- `--show-reasoning`: 显示每个代理的推理过程
- `--show-agent-graph`: 显示代理图

**重要提示**：在非交互式环境（如 CI/CD 或脚本）中运行时，必须指定 `--analysts-all` 或 `--analysts` 以及 `--model` 参数，否则程序会尝试启动交互式选择界面并失败。

### Web 应用

```bash
# 后端（从 app/backend/ 目录）
poetry run uvicorn main:app --reload

# 前端（从 app/frontend/ 目录）
npm install
npm run dev
npm run build
npm run lint
```

## 重要模式

### 代理信号格式

代理以标准化格式返回信号，存储在 `state["data"]["analyst_signals"]` 中：

```python
{
    "agent_name": {
        "ticker": {
            "signal": "buy" | "sell" | "short" | "cover" | "hold",
            "confidence": 0-100,
            "reasoning": "..."
        }
    }
}
```

### 投资组合状态结构

`state["data"]["portfolio"]` 中的投资组合状态包含：

```python
{
    "cash": float,
    "margin_requirement": float,  # 例如：0.5 表示 50% 保证金
    "margin_used": float,
    "equity": float,  # 从现金 + 持仓计算得出
    "positions": {
        "TICKER": {
            "long": int,  # 股票数量
            "short": int,
            "long_cost_basis": float,
            "short_cost_basis": float,
            "short_margin_used": float
        }
    },
    "realized_gains": {
        "TICKER": {
            "long": float,
            "short": float
        }
    }
}
```

### 投资组合管理器决策流程

投资组合管理器（src/agents/portfolio_manager.py）使用确定性约束系统：

1. **计算允许的操作**：`compute_allowed_actions()` 基于现金、保证金和仓位限制确定有效交易和最大数量
2. **预填充持有**：没有有效交易的股票代码预填充为"hold"，以减少 LLM token 使用
3. **LLM 决策**：只有可操作交易的股票代码才会发送给 LLM，并附带精简的信号
4. **验证**：所有决策都根据预计算的约束进行验证

### LLM 提供商支持

系统通过 `src/llm/models.py` 中的统一接口支持多个 LLM 提供商：

- 模型在 `src/llm/api_models.json` 和 `src/llm/ollama_models.json` 中定义
- 使用 `get_model(model_name, model_provider, api_keys)` 实例化 LLM 客户端
- 检查 `LLMModel.has_json_mode()` 以确定是否支持结构化输出
- 美团/MiniMax：通过 `MEITUAN_API_KEY` 和 `MEITUAN_API_BASE` 使用 OpenAI 兼容 API

### 回测

回测引擎（src/backtesting/）模拟历史日期的交易：

- **BacktestEngine**：协调回测循环，为每个交易日调用代理
- **Portfolio**：跟踪持仓、现金、保证金和损益
- **TradeExecutor**：执行交易并更新投资组合状态
- **PerformanceMetricsCalculator**：计算夏普比率、索提诺比率、最大回撤
- **BenchmarkCalculator**：将投资组合表现与 SPY 基准进行比较

### 添加新代理

要添加新的分析师代理：

1. 在 `src/agents/` 中按照现有模式创建代理文件
2. 将配置添加到 `src/utils/analysts.py` 中的 `ANALYST_CONFIG`
3. 代理应接受 `AgentState` 并返回更新后的状态，信号存储在 `state["data"]["analyst_signals"]` 中

## 测试说明

- `tests/backtesting/integration/` 中的集成测试测试完整的回测场景（纯多头、纯空头、多空）
- 单元测试覆盖投资组合操作、交易执行、指标计算
- 使用 `conftest.py` fixtures 进行模拟数据和投资组合设置
- 测试使用模拟的代理响应以避免 LLM API 调用

## 配置文件

- **.env**：LLM 提供商和金融数据的 API 密钥（从 .env.example 复制）
- **pyproject.toml**：Python 依赖和 Poetry 配置
- **src/llm/api_models.json**：可用的 LLM 模型和提供商
- **src/utils/analysts.py**：分析师代理配置和排序

## 常见陷阱

1. **保证金计算**：空头持仓需要保证金。`margin_used` 跟踪已承诺的总保证金，可用保证金为 `(equity / margin_requirement) - margin_used`

2. **仓位限制**：风险管理器为每个股票代码设置 `remaining_position_limit`，投资组合管理器使用它来限制交易规模

3. **JSON 模式**：并非所有模型都支持 JSON 模式（DeepSeek、Gemini）。在使用结构化输出之前使用 `LLMModel.has_json_mode()` 检查

4. **日期范围**：金融数据 API 可能有有限的免费数据。AAPL、GOOGL、MSFT、NVDA、TSLA 是免费的；其他需要 `FINANCIAL_DATASETS_API_KEY`

5. **代理信号**：风险管理器信号被排除在投资组合管理器的信号聚合之外（通过 `not agent.startswith("risk_management_agent")` 过滤）
