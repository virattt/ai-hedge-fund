-- ============================================================================
-- AI对冲基金数据库表注释
-- 为所有表和字段添加中文说明
-- ============================================================================

USE `hedge-fund`;

-- ============================================================================
-- 业务表（Trading Data）
-- ============================================================================

-- 1. trading_sessions - 交易会话表
ALTER TABLE `trading_sessions` COMMENT '交易会话表 - 记录每次CLI运行的完整会话信息';

ALTER TABLE `trading_sessions`
  MODIFY COLUMN `id` INT NOT NULL AUTO_INCREMENT COMMENT '会话ID（主键）',
  MODIFY COLUMN `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '会话创建时间',
  MODIFY COLUMN `completed_at` DATETIME NULL COMMENT '会话完成时间',
  MODIFY COLUMN `tickers` JSON NOT NULL COMMENT '分析的股票代码列表 JSON格式',
  MODIFY COLUMN `start_date` VARCHAR(20) NOT NULL COMMENT '分析开始日期 YYYY-MM-DD',
  MODIFY COLUMN `end_date` VARCHAR(20) NOT NULL COMMENT '分析结束日期 YYYY-MM-DD',
  MODIFY COLUMN `model_name` VARCHAR(100) NOT NULL COMMENT 'LLM模型名称 如MiniMax-M2.5',
  MODIFY COLUMN `model_provider` VARCHAR(50) NOT NULL COMMENT 'LLM提供商 如meituan/openai',
  MODIFY COLUMN `initial_cash` FLOAT NULL DEFAULT 100000.0 COMMENT '初始现金 默认10万',
  MODIFY COLUMN `margin_requirement` FLOAT NULL DEFAULT 0.0 COMMENT '保证金要求比率 0-1之间',
  MODIFY COLUMN `status` VARCHAR(20) NOT NULL DEFAULT 'RUNNING' COMMENT '会话状态 RUNNING/COMPLETED/ERROR',
  MODIFY COLUMN `error_message` TEXT NULL COMMENT '错误信息 状态为ERROR时记录';

-- 2. trading_decisions - 交易决策表
ALTER TABLE `trading_decisions` COMMENT '交易决策表 - Portfolio Manager的最终投资决策';

ALTER TABLE `trading_decisions`
  MODIFY COLUMN `id` INT NOT NULL AUTO_INCREMENT COMMENT '决策ID（主键）',
  MODIFY COLUMN `session_id` INT NOT NULL COMMENT '关联的会话ID',
  MODIFY COLUMN `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '决策创建时间',
  MODIFY COLUMN `ticker` VARCHAR(20) NOT NULL COMMENT '股票代码 如3690.HK',
  MODIFY COLUMN `action` VARCHAR(20) NOT NULL COMMENT '交易动作 BUY/SELL/SHORT/COVER/HOLD',
  MODIFY COLUMN `quantity` INT NOT NULL COMMENT '交易数量 股数',
  MODIFY COLUMN `confidence` FLOAT NOT NULL COMMENT '置信度 0-100',
  MODIFY COLUMN `reasoning` TEXT NULL COMMENT '决策理由 详细说明',
  MODIFY COLUMN `current_price` FLOAT NULL COMMENT '当前价格 决策时的股价',
  MODIFY COLUMN `bullish_signals` INT NULL DEFAULT 0 COMMENT '看涨信号数量',
  MODIFY COLUMN `bearish_signals` INT NULL DEFAULT 0 COMMENT '看跌信号数量',
  MODIFY COLUMN `neutral_signals` INT NULL DEFAULT 0 COMMENT '中性信号数量';

-- 3. analyst_analyses - 分析师分析表
ALTER TABLE `analyst_analyses` COMMENT '分析师分析表 - 记录每个AI代理的详细分析结果';

ALTER TABLE `analyst_analyses`
  MODIFY COLUMN `id` INT NOT NULL AUTO_INCREMENT COMMENT '分析ID（主键）',
  MODIFY COLUMN `session_id` INT NOT NULL COMMENT '关联的会话ID',
  MODIFY COLUMN `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '分析创建时间',
  MODIFY COLUMN `analyst_name` VARCHAR(100) NOT NULL COMMENT '分析师名称 如bill_ackman/warren_buffett',
  MODIFY COLUMN `analyst_type` VARCHAR(50) NOT NULL COMMENT '分析师类型 fundamental/technical/sentiment',
  MODIFY COLUMN `ticker` VARCHAR(20) NOT NULL COMMENT '股票代码 如3690.HK',
  MODIFY COLUMN `signal` VARCHAR(20) NOT NULL COMMENT '信号类型 BULLISH/BEARISH/NEUTRAL',
  MODIFY COLUMN `confidence` FLOAT NOT NULL COMMENT '置信度 0-100',
  MODIFY COLUMN `reasoning` TEXT NULL COMMENT '分析理由 详细推理过程',
  MODIFY COLUMN `analysis_data` JSON NULL COMMENT '详细分析数据 JSON格式存储原始分析结果';

-- 4. market_data - 市场数据表
ALTER TABLE `market_data` COMMENT '市场数据表 - 存储获取的市场数据快照';

ALTER TABLE `market_data`
  MODIFY COLUMN `id` INT NOT NULL AUTO_INCREMENT COMMENT '数据ID（主键）',
  MODIFY COLUMN `session_id` INT NULL COMMENT '关联的会话ID 可为空',
  MODIFY COLUMN `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '数据创建时间',
  MODIFY COLUMN `ticker` VARCHAR(20) NOT NULL COMMENT '股票代码 如3690.HK',
  MODIFY COLUMN `data_date` VARCHAR(20) NOT NULL COMMENT '数据日期 YYYY-MM-DD',
  MODIFY COLUMN `open_price` FLOAT NULL COMMENT '开盘价',
  MODIFY COLUMN `high_price` FLOAT NULL COMMENT '最高价',
  MODIFY COLUMN `low_price` FLOAT NULL COMMENT '最低价',
  MODIFY COLUMN `close_price` FLOAT NULL COMMENT '收盘价',
  MODIFY COLUMN `volume` FLOAT NULL COMMENT '成交量',
  MODIFY COLUMN `financial_metrics` JSON NULL COMMENT '财务指标 JSON格式',
  MODIFY COLUMN `news_count` INT NULL DEFAULT 0 COMMENT '新闻数量',
  MODIFY COLUMN `news_sentiment` VARCHAR(20) NULL COMMENT '新闻情绪 positive/negative/neutral',
  MODIFY COLUMN `technical_indicators` JSON NULL COMMENT '技术指标 JSON格式';

-- 5. performance_metrics - 性能指标表
ALTER TABLE `performance_metrics` COMMENT '性能指标表 - 回测和实时交易的性能统计';

ALTER TABLE `performance_metrics`
  MODIFY COLUMN `id` INT NOT NULL AUTO_INCREMENT COMMENT '指标ID（主键）',
  MODIFY COLUMN `session_id` INT NOT NULL COMMENT '关联的会话ID',
  MODIFY COLUMN `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '指标创建时间',
  MODIFY COLUMN `start_date` VARCHAR(20) NOT NULL COMMENT '统计开始日期 YYYY-MM-DD',
  MODIFY COLUMN `end_date` VARCHAR(20) NOT NULL COMMENT '统计结束日期 YYYY-MM-DD',
  MODIFY COLUMN `total_return` FLOAT NULL COMMENT '总收益率',
  MODIFY COLUMN `annualized_return` FLOAT NULL COMMENT '年化收益率',
  MODIFY COLUMN `sharpe_ratio` FLOAT NULL COMMENT '夏普比率 风险调整后收益',
  MODIFY COLUMN `sortino_ratio` FLOAT NULL COMMENT '索提诺比率 下行风险调整后收益',
  MODIFY COLUMN `max_drawdown` FLOAT NULL COMMENT '最大回撤',
  MODIFY COLUMN `volatility` FLOAT NULL COMMENT '波动率',
  MODIFY COLUMN `long_short_ratio` FLOAT NULL COMMENT '多空比率',
  MODIFY COLUMN `gross_exposure` FLOAT NULL COMMENT '总敞口',
  MODIFY COLUMN `net_exposure` FLOAT NULL COMMENT '净敞口',
  MODIFY COLUMN `total_trades` INT NULL DEFAULT 0 COMMENT '总交易次数',
  MODIFY COLUMN `winning_trades` INT NULL DEFAULT 0 COMMENT '盈利交易次数',
  MODIFY COLUMN `losing_trades` INT NULL DEFAULT 0 COMMENT '亏损交易次数',
  MODIFY COLUMN `win_rate` FLOAT NULL COMMENT '胜率',
  MODIFY COLUMN `daily_returns` JSON NULL COMMENT '每日收益 JSON数组',
  MODIFY COLUMN `portfolio_values` JSON NULL COMMENT '投资组合价值历史 JSON数组';

-- ============================================================================
-- 缓存表（L2 Cache）
-- ============================================================================

-- 6. stock_prices - 股票价格缓存表
ALTER TABLE `stock_prices` COMMENT '股票价格缓存表 - L2缓存层 存储OHLCV历史价格数据';

ALTER TABLE `stock_prices`
  MODIFY COLUMN `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '价格ID（主键）',
  MODIFY COLUMN `ticker` VARCHAR(20) NOT NULL COMMENT '股票代码 如3690.HK/AAPL',
  MODIFY COLUMN `date` DATE NOT NULL COMMENT '交易日期',
  MODIFY COLUMN `time` DATETIME NOT NULL COMMENT '精确时间戳',
  MODIFY COLUMN `open` DECIMAL(20,6) NULL COMMENT '开盘价',
  MODIFY COLUMN `close` DECIMAL(20,6) NULL COMMENT '收盘价',
  MODIFY COLUMN `high` DECIMAL(20,6) NULL COMMENT '最高价',
  MODIFY COLUMN `low` DECIMAL(20,6) NULL COMMENT '最低价',
  MODIFY COLUMN `volume` BIGINT NULL COMMENT '成交量',
  MODIFY COLUMN `data_source` VARCHAR(50) NOT NULL COMMENT '数据来源 financial_api/yfinance/akshare/sina',
  MODIFY COLUMN `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
  MODIFY COLUMN `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '记录更新时间';

-- 7. financial_metrics - 财务指标缓存表
ALTER TABLE `financial_metrics` COMMENT '财务指标缓存表 - L2缓存层 存储公司财务指标如PE/PB/市值等';

ALTER TABLE `financial_metrics`
  MODIFY COLUMN `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '指标ID（主键）',
  MODIFY COLUMN `ticker` VARCHAR(20) NOT NULL COMMENT '股票代码 如3690.HK/AAPL',
  MODIFY COLUMN `report_period` DATE NOT NULL COMMENT '报告期 财报日期',
  MODIFY COLUMN `period` VARCHAR(20) NOT NULL COMMENT '周期类型 ttm/quarterly/annual',
  MODIFY COLUMN `currency` VARCHAR(10) NULL COMMENT '货币单位 USD/HKD/CNY',
  MODIFY COLUMN `market_cap` DECIMAL(20,2) NULL COMMENT '市值',
  MODIFY COLUMN `pe_ratio` DECIMAL(10,4) NULL COMMENT '市盈率 PE',
  MODIFY COLUMN `pb_ratio` DECIMAL(10,4) NULL COMMENT '市净率 PB',
  MODIFY COLUMN `ps_ratio` DECIMAL(10,4) NULL COMMENT '市销率 PS',
  MODIFY COLUMN `revenue` DECIMAL(20,2) NULL COMMENT '营业收入',
  MODIFY COLUMN `net_income` DECIMAL(20,2) NULL COMMENT '净利润',
  MODIFY COLUMN `metrics_json` JSON NULL COMMENT '完整财务指标 JSON格式存储所有指标',
  MODIFY COLUMN `data_source` VARCHAR(50) NOT NULL COMMENT '数据来源 financial_api/akshare/tushare',
  MODIFY COLUMN `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
  MODIFY COLUMN `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '记录更新时间';

-- 8. company_news - 公司新闻缓存表
ALTER TABLE `company_news` COMMENT '公司新闻缓存表 - L2缓存层 存储公司相关新闻用于情绪分析';

ALTER TABLE `company_news`
  MODIFY COLUMN `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '新闻ID（主键）',
  MODIFY COLUMN `ticker` VARCHAR(20) NOT NULL COMMENT '股票代码 如3690.HK/AAPL',
  MODIFY COLUMN `date` DATETIME NOT NULL COMMENT '新闻发布时间',
  MODIFY COLUMN `title` TEXT NULL COMMENT '新闻标题',
  MODIFY COLUMN `content` TEXT NULL COMMENT '新闻内容 完整正文',
  MODIFY COLUMN `url` VARCHAR(500) NULL COMMENT '新闻链接 原文URL',
  MODIFY COLUMN `source` VARCHAR(100) NULL COMMENT '新闻来源 如财联社/东方财富',
  MODIFY COLUMN `data_source` VARCHAR(50) NOT NULL COMMENT '数据源 financial_api/akshare/newsnow',
  MODIFY COLUMN `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
  MODIFY COLUMN `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '记录更新时间';

-- ============================================================================
-- 索引说明
-- ============================================================================

-- trading_sessions 索引
-- idx_session_date: 按创建时间查询会话

-- trading_decisions 索引
-- idx_decision_ticker: 按股票代码查询决策
-- idx_decision_action: 按交易动作查询
-- idx_decision_date: 按时间查询决策

-- analyst_analyses 索引
-- idx_analysis_analyst: 按分析师查询
-- idx_analysis_ticker: 按股票代码查询
-- idx_analysis_signal: 按信号类型查询
-- idx_analysis_date: 按时间查询

-- market_data 索引
-- idx_market_ticker_date: 按股票和日期组合查询
-- idx_market_date: 按日期查询

-- performance_metrics 索引
-- idx_perf_session: 按会话ID查询
-- idx_perf_date: 按结束日期查询

-- stock_prices 索引
-- idx_stock_prices_ticker_date: 按股票和日期组合查询
-- uk_stock_prices_ticker_time: 唯一约束 防止重复数据

-- financial_metrics 索引
-- uk_financial_metrics_ticker_period: 唯一约束 防止重复数据

-- company_news 索引
-- idx_company_news_ticker_date: 按股票和日期组合查询

-- ============================================================================
-- Web应用表（Frontend/Backend）
-- ============================================================================

-- 9. hedge_fund_flows - 对冲基金流程配置表
ALTER TABLE `hedge_fund_flows` COMMENT '对冲基金流程配置表 - 存储React Flow的节点/边/视口配置';

ALTER TABLE `hedge_fund_flows`
  MODIFY COLUMN `id` INT NOT NULL AUTO_INCREMENT COMMENT '流程ID（主键）',
  MODIFY COLUMN `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '流程创建时间',
  MODIFY COLUMN `updated_at` DATETIME NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '流程更新时间',
  MODIFY COLUMN `name` VARCHAR(200) NOT NULL COMMENT '流程名称',
  MODIFY COLUMN `description` TEXT NULL COMMENT '流程描述',
  MODIFY COLUMN `nodes` JSON NOT NULL COMMENT 'React Flow节点配置 JSON格式',
  MODIFY COLUMN `edges` JSON NOT NULL COMMENT 'React Flow边配置 JSON格式',
  MODIFY COLUMN `viewport` JSON NULL COMMENT '视口状态 缩放和位置信息',
  MODIFY COLUMN `data` JSON NULL COMMENT '节点内部状态 tickers/models等配置',
  MODIFY COLUMN `is_template` BOOLEAN NULL DEFAULT FALSE COMMENT '是否为模板 用于复用',
  MODIFY COLUMN `tags` JSON NULL COMMENT '标签 用于分类';

-- 10. hedge_fund_flow_runs - 流程执行记录表
ALTER TABLE `hedge_fund_flow_runs` COMMENT '流程执行记录表 - 跟踪每次流程执行的完整生命周期';

ALTER TABLE `hedge_fund_flow_runs`
  MODIFY COLUMN `id` INT NOT NULL AUTO_INCREMENT COMMENT '执行ID（主键）',
  MODIFY COLUMN `flow_id` INT NOT NULL COMMENT '关联的流程ID',
  MODIFY COLUMN `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '执行创建时间',
  MODIFY COLUMN `updated_at` DATETIME NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '执行更新时间',
  MODIFY COLUMN `status` VARCHAR(50) NOT NULL DEFAULT 'IDLE' COMMENT '执行状态 IDLE/IN_PROGRESS/COMPLETE/ERROR',
  MODIFY COLUMN `started_at` DATETIME NULL COMMENT '执行开始时间',
  MODIFY COLUMN `completed_at` DATETIME NULL COMMENT '执行完成时间',
  MODIFY COLUMN `trading_mode` VARCHAR(50) NOT NULL DEFAULT 'one-time' COMMENT '交易模式 one-time/continuous/advisory',
  MODIFY COLUMN `schedule` VARCHAR(50) NULL COMMENT '执行计划 hourly/daily/weekly 用于continuous模式',
  MODIFY COLUMN `duration` VARCHAR(50) NULL COMMENT '持续时间 1day/1week/1month 用于continuous模式',
  MODIFY COLUMN `request_data` JSON NULL COMMENT '请求参数 tickers/agents/models等',
  MODIFY COLUMN `initial_portfolio` JSON NULL COMMENT '初始投资组合状态',
  MODIFY COLUMN `final_portfolio` JSON NULL COMMENT '最终投资组合状态',
  MODIFY COLUMN `results` JSON NULL COMMENT '执行结果输出',
  MODIFY COLUMN `error_message` TEXT NULL COMMENT '错误信息 状态为ERROR时记录',
  MODIFY COLUMN `run_number` INT NOT NULL DEFAULT 1 COMMENT '执行序号 该流程的第N次执行';

-- 11. hedge_fund_flow_run_cycles - 分析周期表
ALTER TABLE `hedge_fund_flow_run_cycles` COMMENT '分析周期表 - 交易会话中的单个分析周期详情';

ALTER TABLE `hedge_fund_flow_run_cycles`
  MODIFY COLUMN `id` INT NOT NULL AUTO_INCREMENT COMMENT '周期ID（主键）',
  MODIFY COLUMN `flow_run_id` INT NOT NULL COMMENT '关联的执行ID',
  MODIFY COLUMN `cycle_number` INT NOT NULL COMMENT '周期序号 1/2/3等',
  MODIFY COLUMN `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '周期创建时间',
  MODIFY COLUMN `started_at` DATETIME NOT NULL COMMENT '周期开始时间',
  MODIFY COLUMN `completed_at` DATETIME NULL COMMENT '周期完成时间',
  MODIFY COLUMN `analyst_signals` JSON NULL COMMENT '分析师信号 所有代理的决策信号',
  MODIFY COLUMN `trading_decisions` JSON NULL COMMENT '交易决策 Portfolio Manager的决策',
  MODIFY COLUMN `executed_trades` JSON NULL COMMENT '已执行交易 模拟交易记录',
  MODIFY COLUMN `portfolio_snapshot` JSON NULL COMMENT '投资组合快照 现金/持仓/性能指标',
  MODIFY COLUMN `performance_metrics` JSON NULL COMMENT '性能指标 收益率/夏普比率等',
  MODIFY COLUMN `status` VARCHAR(50) NOT NULL DEFAULT 'IN_PROGRESS' COMMENT '周期状态 IN_PROGRESS/COMPLETED/ERROR',
  MODIFY COLUMN `error_message` TEXT NULL COMMENT '错误信息 周期失败时记录',
  MODIFY COLUMN `llm_calls_count` INT NULL DEFAULT 0 COMMENT 'LLM调用次数',
  MODIFY COLUMN `api_calls_count` INT NULL DEFAULT 0 COMMENT '金融API调用次数',
  MODIFY COLUMN `estimated_cost` VARCHAR(20) NULL COMMENT '预估成本 美元',
  MODIFY COLUMN `trigger_reason` VARCHAR(100) NULL COMMENT '触发原因 scheduled/manual/market_event',
  MODIFY COLUMN `market_conditions` JSON NULL COMMENT '市场状况 周期开始时的市场数据快照';

-- 12. api_keys - API密钥表
ALTER TABLE `api_keys` COMMENT 'API密钥表 - 存储各种服务的API密钥配置';

ALTER TABLE `api_keys`
  MODIFY COLUMN `id` INT NOT NULL AUTO_INCREMENT COMMENT '密钥ID（主键）',
  MODIFY COLUMN `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '密钥创建时间',
  MODIFY COLUMN `updated_at` DATETIME NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '密钥更新时间',
  MODIFY COLUMN `provider` VARCHAR(100) NOT NULL COMMENT '提供商标识 如ANTHROPIC_API_KEY',
  MODIFY COLUMN `key_value` TEXT NOT NULL COMMENT 'API密钥值 生产环境需加密',
  MODIFY COLUMN `is_active` BOOLEAN NULL DEFAULT TRUE COMMENT '是否启用 可禁用而不删除',
  MODIFY COLUMN `description` TEXT NULL COMMENT '描述信息 人类可读的说明',
  MODIFY COLUMN `last_used` DATETIME NULL COMMENT '最后使用时间 跟踪使用情况';

-- ============================================================================
-- 索引补充说明
-- ============================================================================

-- hedge_fund_flows 索引
-- PRIMARY KEY (id): 主键索引

-- hedge_fund_flow_runs 索引
-- PRIMARY KEY (id): 主键索引
-- INDEX (flow_id): 按流程ID查询所有执行记录

-- hedge_fund_flow_run_cycles 索引
-- PRIMARY KEY (id): 主键索引
-- INDEX (flow_run_id): 按执行ID查询所有分析周期

-- api_keys 索引
-- PRIMARY KEY (id): 主键索引
-- UNIQUE INDEX (provider): 确保每个提供商只有一个密钥记录

-- ============================================================================
-- 执行说明
-- ============================================================================
-- 1. 备份数据库: mysqldump -u root -p hedge-fund > backup.sql
-- 2. 执行此脚本: mysql -u root -p hedge-fund < database_comments.sql
-- 3. 验证注释: SHOW FULL COLUMNS FROM table_name;
-- ============================================================================
