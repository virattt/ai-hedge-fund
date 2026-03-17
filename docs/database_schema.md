# 数据库架构文档

本文档描述了AI对冲基金系统的完整数据库架构，包含所有表的中文说明。

## 数据库概览

数据库名称: `hedge-fund`

### 表分类

数据库表分为三大类：

1. **业务表（Trading Data）**: 存储交易会话、决策、分析等核心业务数据
2. **缓存表（L2 Cache）**: 存储从外部API获取的市场数据，作为二级缓存
3. **Web应用表（Frontend/Backend）**: 支持Web界面的流程配置和执行追踪

## 表结构详解

### 1. 业务表（Trading Data）

#### 1.1 trading_sessions - 交易会话表

记录每次CLI运行的完整会话信息。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT | 会话ID（主键） |
| created_at | DATETIME | 会话创建时间 |
| completed_at | DATETIME | 会话完成时间 |
| tickers | JSON | 分析的股票代码列表 |
| start_date | VARCHAR(20) | 分析开始日期 YYYY-MM-DD |
| end_date | VARCHAR(20) | 分析结束日期 YYYY-MM-DD |
| model_name | VARCHAR(100) | LLM模型名称 如MiniMax-M2.5 |
| model_provider | VARCHAR(50) | LLM提供商 如meituan/openai |
| initial_cash | FLOAT | 初始现金 默认10万 |
| margin_requirement | FLOAT | 保证金要求比率 0-1之间 |
| status | VARCHAR(20) | 会话状态 RUNNING/COMPLETED/ERROR |
| error_message | TEXT | 错误信息 |

**索引:**
- `idx_session_date`: 按创建时间查询会话

#### 1.2 trading_decisions - 交易决策表

Portfolio Manager的最终投资决策。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT | 决策ID（主键） |
| session_id | INT | 关联的会话ID |
| created_at | DATETIME | 决策创建时间 |
| ticker | VARCHAR(20) | 股票代码 如3690.HK |
| action | VARCHAR(20) | 交易动作 BUY/SELL/SHORT/COVER/HOLD |
| quantity | INT | 交易数量 股数 |
| confidence | FLOAT | 置信度 0-100 |
| reasoning | TEXT | 决策理由 |
| current_price | FLOAT | 当前价格 |
| bullish_signals | INT | 看涨信号数量 |
| bearish_signals | INT | 看跌信号数量 |
| neutral_signals | INT | 中性信号数量 |

**索引:**
- `idx_decision_ticker`: 按股票代码查询
- `idx_decision_action`: 按交易动作查询
- `idx_decision_date`: 按时间查询

#### 1.3 analyst_analyses - 分析师分析表

记录每个AI代理的详细分析结果。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT | 分析ID（主键） |
| session_id | INT | 关联的会话ID |
| created_at | DATETIME | 分析创建时间 |
| analyst_name | VARCHAR(100) | 分析师名称 如bill_ackman/warren_buffett |
| analyst_type | VARCHAR(50) | 分析师类型 fundamental/technical/sentiment |
| ticker | VARCHAR(20) | 股票代码 |
| signal | VARCHAR(20) | 信号类型 BULLISH/BEARISH/NEUTRAL |
| confidence | FLOAT | 置信度 0-100 |
| reasoning | TEXT | 分析理由 |
| analysis_data | JSON | 详细分析数据 |

**索引:**
- `idx_analysis_analyst`: 按分析师查询
- `idx_analysis_ticker`: 按股票代码查询
- `idx_analysis_signal`: 按信号类型查询
- `idx_analysis_date`: 按时间查询

#### 1.4 market_data - 市场数据表

存储获取的市场数据快照。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT | 数据ID（主键） |
| session_id | INT | 关联的会话ID |
| created_at | DATETIME | 数据创建时间 |
| ticker | VARCHAR(20) | 股票代码 |
| data_date | VARCHAR(20) | 数据日期 YYYY-MM-DD |
| open_price | FLOAT | 开盘价 |
| high_price | FLOAT | 最高价 |
| low_price | FLOAT | 最低价 |
| close_price | FLOAT | 收盘价 |
| volume | FLOAT | 成交量 |
| financial_metrics | JSON | 财务指标 |
| news_count | INT | 新闻数量 |
| news_sentiment | VARCHAR(20) | 新闻情绪 positive/negative/neutral |
| technical_indicators | JSON | 技术指标 |

**索引:**
- `idx_market_ticker_date`: 按股票和日期组合查询
- `idx_market_date`: 按日期查询

#### 1.5 performance_metrics - 性能指标表

回测和实时交易的性能统计。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT | 指标ID（主键） |
| session_id | INT | 关联的会话ID |
| created_at | DATETIME | 指标创建时间 |
| start_date | VARCHAR(20) | 统计开始日期 |
| end_date | VARCHAR(20) | 统计结束日期 |
| total_return | FLOAT | 总收益率 |
| annualized_return | FLOAT | 年化收益率 |
| sharpe_ratio | FLOAT | 夏普比率 |
| sortino_ratio | FLOAT | 索提诺比率 |
| max_drawdown | FLOAT | 最大回撤 |
| volatility | FLOAT | 波动率 |
| long_short_ratio | FLOAT | 多空比率 |
| gross_exposure | FLOAT | 总敞口 |
| net_exposure | FLOAT | 净敞口 |
| total_trades | INT | 总交易次数 |
| winning_trades | INT | 盈利交易次数 |
| losing_trades | INT | 亏损交易次数 |
| win_rate | FLOAT | 胜率 |
| daily_returns | JSON | 每日收益 |
| portfolio_values | JSON | 投资组合价值历史 |

**索引:**
- `idx_perf_session`: 按会话ID查询
- `idx_perf_date`: 按结束日期查询

### 2. 缓存表（L2 Cache）

#### 2.1 stock_prices - 股票价格缓存表

L2缓存层，存储OHLCV历史价格数据。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT | 价格ID（主键） |
| ticker | VARCHAR(20) | 股票代码 如3690.HK/AAPL |
| date | DATE | 交易日期 |
| time | DATETIME | 精确时间戳 |
| open | DECIMAL(20,6) | 开盘价 |
| close | DECIMAL(20,6) | 收盘价 |
| high | DECIMAL(20,6) | 最高价 |
| low | DECIMAL(20,6) | 最低价 |
| volume | BIGINT | 成交量 |
| data_source | VARCHAR(50) | 数据来源 financial_api/yfinance/akshare/sina |
| created_at | DATETIME | 记录创建时间 |
| updated_at | DATETIME | 记录更新时间 |

**索引:**
- `idx_stock_prices_ticker_date`: 按股票和日期组合查询
- `uk_stock_prices_ticker_time`: 唯一约束，防止重复数据

#### 2.2 financial_metrics - 财务指标缓存表

L2缓存层，存储公司财务指标如PE/PB/市值等。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT | 指标ID（主键） |
| ticker | VARCHAR(20) | 股票代码 |
| report_period | DATE | 报告期 财报日期 |
| period | VARCHAR(20) | 周期类型 ttm/quarterly/annual |
| currency | VARCHAR(10) | 货币单位 USD/HKD/CNY |
| market_cap | DECIMAL(20,2) | 市值 |
| pe_ratio | DECIMAL(10,4) | 市盈率 PE |
| pb_ratio | DECIMAL(10,4) | 市净率 PB |
| ps_ratio | DECIMAL(10,4) | 市销率 PS |
| revenue | DECIMAL(20,2) | 营业收入 |
| net_income | DECIMAL(20,2) | 净利润 |
| metrics_json | JSON | 完整财务指标 |
| data_source | VARCHAR(50) | 数据来源 |
| created_at | DATETIME | 记录创建时间 |
| updated_at | DATETIME | 记录更新时间 |

**索引:**
- `uk_financial_metrics_ticker_period`: 唯一约束，防止重复数据

#### 2.3 company_news - 公司新闻缓存表

L2缓存层，存储公司相关新闻用于情绪分析。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT | 新闻ID（主键） |
| ticker | VARCHAR(20) | 股票代码 |
| date | DATETIME | 新闻发布时间 |
| title | TEXT | 新闻标题 |
| content | TEXT | 新闻内容 |
| url | VARCHAR(500) | 新闻链接 |
| source | VARCHAR(100) | 新闻来源 如财联社/东方财富 |
| data_source | VARCHAR(50) | 数据源 |
| created_at | DATETIME | 记录创建时间 |
| updated_at | DATETIME | 记录更新时间 |

**索引:**
- `idx_company_news_ticker_date`: 按股票和日期组合查询

### 3. Web应用表（Frontend/Backend）

#### 3.1 hedge_fund_flows - 对冲基金流程配置表

存储React Flow的节点/边/视口配置。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT | 流程ID（主键） |
| created_at | DATETIME | 流程创建时间 |
| updated_at | DATETIME | 流程更新时间 |
| name | VARCHAR(200) | 流程名称 |
| description | TEXT | 流程描述 |
| nodes | JSON | React Flow节点配置 |
| edges | JSON | React Flow边配置 |
| viewport | JSON | 视口状态 缩放和位置信息 |
| data | JSON | 节点内部状态 tickers/models等配置 |
| is_template | BOOLEAN | 是否为模板 用于复用 |
| tags | JSON | 标签 用于分类 |

#### 3.2 hedge_fund_flow_runs - 流程执行记录表

跟踪每次流程执行的完整生命周期。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT | 执行ID（主键） |
| flow_id | INT | 关联的流程ID |
| created_at | DATETIME | 执行创建时间 |
| updated_at | DATETIME | 执行更新时间 |
| status | VARCHAR(50) | 执行状态 IDLE/IN_PROGRESS/COMPLETE/ERROR |
| started_at | DATETIME | 执行开始时间 |
| completed_at | DATETIME | 执行完成时间 |
| trading_mode | VARCHAR(50) | 交易模式 one-time/continuous/advisory |
| schedule | VARCHAR(50) | 执行计划 hourly/daily/weekly |
| duration | VARCHAR(50) | 持续时间 1day/1week/1month |
| request_data | JSON | 请求参数 |
| initial_portfolio | JSON | 初始投资组合状态 |
| final_portfolio | JSON | 最终投资组合状态 |
| results | JSON | 执行结果输出 |
| error_message | TEXT | 错误信息 |
| run_number | INT | 执行序号 |

**索引:**
- `INDEX (flow_id)`: 按流程ID查询所有执行记录

#### 3.3 hedge_fund_flow_run_cycles - 分析周期表

交易会话中的单个分析周期详情。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT | 周期ID（主键） |
| flow_run_id | INT | 关联的执行ID |
| cycle_number | INT | 周期序号 1/2/3等 |
| created_at | DATETIME | 周期创建时间 |
| started_at | DATETIME | 周期开始时间 |
| completed_at | DATETIME | 周期完成时间 |
| analyst_signals | JSON | 分析师信号 |
| trading_decisions | JSON | 交易决策 |
| executed_trades | JSON | 已执行交易 |
| portfolio_snapshot | JSON | 投资组合快照 |
| performance_metrics | JSON | 性能指标 |
| status | VARCHAR(50) | 周期状态 IN_PROGRESS/COMPLETED/ERROR |
| error_message | TEXT | 错误信息 |
| llm_calls_count | INT | LLM调用次数 |
| api_calls_count | INT | 金融API调用次数 |
| estimated_cost | VARCHAR(20) | 预估成本 美元 |
| trigger_reason | VARCHAR(100) | 触发原因 scheduled/manual/market_event |
| market_conditions | JSON | 市场状况快照 |

**索引:**
- `INDEX (flow_run_id)`: 按执行ID查询所有分析周期

#### 3.4 api_keys - API密钥表

存储各种服务的API密钥配置。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT | 密钥ID（主键） |
| created_at | DATETIME | 密钥创建时间 |
| updated_at | DATETIME | 密钥更新时间 |
| provider | VARCHAR(100) | 提供商标识 如ANTHROPIC_API_KEY |
| key_value | TEXT | API密钥值 生产环境需加密 |
| is_active | BOOLEAN | 是否启用 |
| description | TEXT | 描述信息 |
| last_used | DATETIME | 最后使用时间 |

**索引:**
- `UNIQUE INDEX (provider)`: 确保每个提供商只有一个密钥记录

## 数据库注释管理

### 添加注释

使用Python脚本添加注释：

```bash
poetry run python scripts/add_database_comments.py
```

或直接执行SQL文件：

```bash
mysql -u root -p hedge-fund < database_comments.sql
```

### 验证注释

查看表注释：

```sql
SHOW TABLE STATUS LIKE 'table_name';
```

查看字段注释：

```sql
SHOW FULL COLUMNS FROM table_name;
```

### 备份数据库

在执行任何数据库修改前，建议先备份：

```bash
mysqldump -u root -p hedge-fund > backup_$(date +%Y%m%d).sql
```

## 数据关系说明

### 会话相关表

```
trading_sessions (会话)
    ├── trading_decisions (决策)
    ├── analyst_analyses (分析)
    ├── market_data (市场数据)
    └── performance_metrics (性能指标)
```

**注意**: 系统已移除外键约束，使用 `session_id` 进行手动关联。

### 流程相关表

```
hedge_fund_flows (流程配置)
    └── hedge_fund_flow_runs (执行记录)
            └── hedge_fund_flow_run_cycles (分析周期)
```

### 缓存表

缓存表独立于会话，可被多个会话共享：

- `stock_prices`: 价格数据缓存
- `financial_metrics`: 财务指标缓存
- `company_news`: 新闻数据缓存

## 常见查询示例

### 查询会话的所有决策

```sql
SELECT
    td.ticker,
    td.action,
    td.quantity,
    td.confidence,
    td.current_price
FROM trading_decisions td
WHERE td.session_id = ?
ORDER BY td.created_at;
```

### 查询特定股票的分析师信号

```sql
SELECT
    aa.analyst_name,
    aa.signal,
    aa.confidence,
    aa.reasoning
FROM analyst_analyses aa
WHERE aa.session_id = ? AND aa.ticker = ?
ORDER BY aa.confidence DESC;
```

### 查询流程的执行历史

```sql
SELECT
    hfr.id,
    hfr.status,
    hfr.started_at,
    hfr.completed_at,
    hfr.trading_mode,
    hfr.run_number
FROM hedge_fund_flow_runs hfr
WHERE hfr.flow_id = ?
ORDER BY hfr.run_number DESC;
```

### 查询缓存的股票价格

```sql
SELECT
    sp.date,
    sp.open,
    sp.high,
    sp.low,
    sp.close,
    sp.volume
FROM stock_prices sp
WHERE sp.ticker = ? AND sp.date BETWEEN ? AND ?
ORDER BY sp.date;
```

## 维护建议

1. **定期清理**: 定期清理过期的会话数据和缓存数据
2. **索引优化**: 根据实际查询模式调整索引
3. **性能监控**: 监控慢查询，优化查询性能
4. **备份策略**: 建立定期备份机制
5. **数据归档**: 对历史数据进行归档处理

## 参考资料

- [SQLAlchemy文档](https://docs.sqlalchemy.org/)
- [MySQL数据类型](https://dev.mysql.com/doc/refman/8.0/en/data-types.html)
- [数据库设计最佳实践](https://www.mysql.com/why-mysql/presentations/mysql-database-design-best-practices/)
