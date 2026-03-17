# 数据库快速参考

## 快速命令

```bash
# 验证SQL注释文件
poetry run python scripts/validate_sql_comments.py

# 添加注释到数据库
poetry run python scripts/add_database_comments.py

# 备份数据库
mysqldump -u root -p hedge-fund > backup_$(date +%Y%m%d).sql

# 查看表注释
mysql -u root -p hedge-fund -e "SHOW TABLE STATUS;"

# 查看字段注释
mysql -u root -p hedge-fund -e "SHOW FULL COLUMNS FROM trading_sessions;"
```

## 表结构速查

### 业务表（5个）

| 表名 | 说明 | 主要字段 |
|------|------|---------|
| trading_sessions | 交易会话 | tickers, model_name, status |
| trading_decisions | 交易决策 | ticker, action, quantity, confidence |
| analyst_analyses | 分析师分析 | analyst_name, signal, confidence |
| market_data | 市场数据 | ticker, open/close price, volume |
| performance_metrics | 性能指标 | total_return, sharpe_ratio, max_drawdown |

### 缓存表（3个）

| 表名 | 说明 | 主要字段 |
|------|------|---------|
| stock_prices | 价格缓存 | ticker, date, open/close/high/low |
| financial_metrics | 财务指标 | ticker, pe_ratio, pb_ratio, revenue |
| company_news | 新闻缓存 | ticker, title, content, sentiment |

### Web应用表（4个）

| 表名 | 说明 | 主要字段 |
|------|------|---------|
| hedge_fund_flows | 流程配置 | name, nodes, edges, viewport |
| hedge_fund_flow_runs | 执行记录 | flow_id, status, trading_mode |
| hedge_fund_flow_run_cycles | 分析周期 | flow_run_id, analyst_signals, trading_decisions |
| api_keys | API密钥 | provider, key_value, is_active |

## 常用查询

### 查询最近的交易会话

```sql
SELECT
    id,
    created_at,
    tickers,
    model_name,
    status
FROM trading_sessions
ORDER BY created_at DESC
LIMIT 10;
```

### 查询某个会话的所有决策

```sql
SELECT
    td.ticker,
    td.action,
    td.quantity,
    td.confidence,
    td.current_price,
    td.reasoning
FROM trading_decisions td
WHERE td.session_id = ?
ORDER BY td.confidence DESC;
```

### 查询分析师信号统计

```sql
SELECT
    analyst_name,
    signal,
    COUNT(*) as count,
    AVG(confidence) as avg_confidence
FROM analyst_analyses
WHERE session_id = ?
GROUP BY analyst_name, signal
ORDER BY analyst_name, signal;
```

### 查询股票价格历史

```sql
SELECT
    date,
    open,
    high,
    low,
    close,
    volume
FROM stock_prices
WHERE ticker = 'AAPL'
    AND date BETWEEN '2024-01-01' AND '2024-12-31'
ORDER BY date;
```

### 查询流程执行历史

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

### 查询性能指标

```sql
SELECT
    session_id,
    total_return,
    annualized_return,
    sharpe_ratio,
    max_drawdown,
    win_rate
FROM performance_metrics
ORDER BY sharpe_ratio DESC
LIMIT 10;
```

## 数据关系

```
trading_sessions (会话)
    ├── trading_decisions (决策)
    ├── analyst_analyses (分析)
    ├── market_data (市场数据)
    └── performance_metrics (性能指标)

hedge_fund_flows (流程配置)
    └── hedge_fund_flow_runs (执行记录)
            └── hedge_fund_flow_run_cycles (分析周期)

[独立缓存表]
    ├── stock_prices
    ├── financial_metrics
    └── company_news
```

## 索引说明

### trading_sessions
- `idx_session_date`: 按创建时间查询

### trading_decisions
- `idx_decision_ticker`: 按股票代码查询
- `idx_decision_action`: 按交易动作查询
- `idx_decision_date`: 按时间查询

### analyst_analyses
- `idx_analysis_analyst`: 按分析师查询
- `idx_analysis_ticker`: 按股票代码查询
- `idx_analysis_signal`: 按信号类型查询
- `idx_analysis_date`: 按时间查询

### market_data
- `idx_market_ticker_date`: 按股票和日期组合查询
- `idx_market_date`: 按日期查询

### performance_metrics
- `idx_perf_session`: 按会话ID查询
- `idx_perf_date`: 按结束日期查询

### stock_prices
- `idx_stock_prices_ticker_date`: 按股票和日期组合查询
- `uk_stock_prices_ticker_time`: 唯一约束

### financial_metrics
- `uk_financial_metrics_ticker_period`: 唯一约束

### company_news
- `idx_company_news_ticker_date`: 按股票和日期组合查询

### hedge_fund_flow_runs
- `INDEX (flow_id)`: 按流程ID查询

### hedge_fund_flow_run_cycles
- `INDEX (flow_run_id)`: 按执行ID查询

### api_keys
- `UNIQUE INDEX (provider)`: 提供商唯一约束

## 字段类型速查

### 常用字段类型

| 类型 | 说明 | 示例 |
|------|------|------|
| INT | 整数 | id, quantity, count |
| BIGINT | 大整数 | volume, large_numbers |
| FLOAT | 浮点数 | price, ratio, percentage |
| DECIMAL(20,6) | 精确小数 | precise_price |
| VARCHAR(N) | 可变字符串 | ticker, name, status |
| TEXT | 长文本 | reasoning, content, description |
| JSON | JSON数据 | tickers, metrics, signals |
| DATETIME | 日期时间 | created_at, started_at |
| DATE | 日期 | date, report_period |
| BOOLEAN | 布尔值 | is_active, is_template |

### JSON字段示例

```sql
-- tickers字段
["AAPL", "MSFT", "GOOGL"]

-- analyst_signals字段
{
  "warren_buffett": {
    "AAPL": {
      "signal": "buy",
      "confidence": 85,
      "reasoning": "..."
    }
  }
}

-- portfolio_snapshot字段
{
  "cash": 100000.0,
  "positions": {
    "AAPL": {
      "long": 100,
      "short": 0
    }
  }
}
```

## 维护任务

### 每日

```bash
# 检查数据库连接
poetry run python -c "from src.database.connection import test_connection; test_connection()"
```

### 每周

```bash
# 备份数据库
mysqldump -u root -p hedge-fund > backups/weekly_$(date +%Y%m%d).sql

# 检查表大小
mysql -u root -p hedge-fund -e "
SELECT
    table_name,
    ROUND(((data_length + index_length) / 1024 / 1024), 2) AS 'Size (MB)'
FROM information_schema.TABLES
WHERE table_schema = 'hedge-fund'
ORDER BY (data_length + index_length) DESC;"
```

### 每月

```bash
# 优化表
mysql -u root -p hedge-fund -e "OPTIMIZE TABLE trading_sessions, trading_decisions, analyst_analyses;"

# 分析表
mysql -u root -p hedge-fund -e "ANALYZE TABLE trading_sessions, trading_decisions, analyst_analyses;"

# 清理旧数据（根据需要）
mysql -u root -p hedge-fund -e "
DELETE FROM trading_sessions
WHERE created_at < DATE_SUB(NOW(), INTERVAL 6 MONTH)
    AND status = 'COMPLETED';"
```

## 故障排查

### 连接失败

```bash
# 检查MySQL服务
mysql.server status

# 测试连接
mysql -u root -p -e "SELECT 1;"
```

### 表不存在

```bash
# 初始化数据库
poetry run python -c "from src.database.connection import init_db; init_db()"
```

### 字符编码问题

```sql
-- 检查数据库字符集
SHOW CREATE DATABASE `hedge-fund`;

-- 修改数据库字符集
ALTER DATABASE `hedge-fund`
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;
```

### 慢查询

```sql
-- 启用慢查询日志
SET GLOBAL slow_query_log = 'ON';
SET GLOBAL long_query_time = 2;

-- 查看慢查询
SHOW VARIABLES LIKE 'slow_query%';
```

## 性能优化建议

1. **使用索引**: 在WHERE、JOIN、ORDER BY子句中使用的字段上建立索引
2. **限制结果**: 使用LIMIT限制返回的行数
3. **避免SELECT ***: 只查询需要的字段
4. **使用批量操作**: 批量插入/更新数据
5. **定期维护**: 定期OPTIMIZE和ANALYZE表
6. **监控慢查询**: 启用慢查询日志并定期分析

## 相关文档

- 📊 [完整数据库架构文档](database_schema.md)
- 🛠️ [数据库脚本使用指南](../scripts/README.md)
- 📝 [项目主README](../README.md)
- ✅ [完成总结](../DATABASE_COMMENTS_SUMMARY.md)
