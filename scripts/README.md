# 数据库注释管理脚本

本目录包含用于管理数据库表和字段中文注释的脚本。

## 脚本说明

### 1. validate_sql_comments.py - SQL注释验证工具

验证 `database_comments.sql` 文件的语法和完整性。

**功能:**
- 检查SQL文件是否存在
- 统计表和注释数量
- 验证所有表是否都有注释
- 检查SQL语法错误
- 显示数据库表结构概览

**使用方法:**

```bash
poetry run python scripts/validate_sql_comments.py
```

**输出示例:**

```
✅ 找到 12 个表的注释
✅ 找到 170 个中文注释
✅ 验证完成: SQL文件格式正确
```

### 2. add_database_comments.py - 数据库注释添加工具

将中文注释添加到实际的MySQL数据库中。

**功能:**
- 测试数据库连接
- 读取和解析SQL注释文件
- 执行ALTER TABLE语句添加注释
- 验证注释是否添加成功
- 显示执行结果统计

**使用方法:**

```bash
# 方法1: 使用Python脚本（推荐）
poetry run python scripts/add_database_comments.py

# 方法2: 直接执行SQL文件
mysql -u root -p hedge-fund < database_comments.sql
```

**前置条件:**
1. 确保MySQL服务正在运行
2. 配置正确的数据库连接信息（.env文件）
3. 数据库 `hedge-fund` 已创建
4. 所有表已创建

**输出示例:**

```
1. 测试数据库连接...
✅ 数据库连接成功: localhost:3306/hedge-fund

2. 读取SQL注释文件...
✅ 成功读取SQL文件 (15744 字符)

3. 解析SQL语句...
✅ 解析出 26 条SQL语句

4. 执行SQL语句...
[1/26] 执行: ALTER TABLE `trading_sessions` COMMENT '交易会话表 - 记录每次CLI运行的完整会话信息';
...
执行完成: ✅ 26 成功, ❌ 0 失败

5. 验证注释...
✅ trading_sessions                      交易会话表 - 记录每次CLI运行的完整会话信息
✅ trading_decisions                     交易决策表 - Portfolio Manager的最终投资决策
...
```

## 数据库注释文件

### database_comments.sql

位置: `/Users/luobotao/.openclaw/workspace/ai-hedge-fund/database_comments.sql`

这是主要的SQL注释文件，包含所有表和字段的中文注释。

**结构:**

```sql
-- ============================================================================
-- 业务表（Trading Data）
-- ============================================================================

ALTER TABLE `trading_sessions` COMMENT '交易会话表 - 记录每次CLI运行的完整会话信息';

ALTER TABLE `trading_sessions`
  MODIFY COLUMN `id` INT NOT NULL AUTO_INCREMENT COMMENT '会话ID（主键）',
  MODIFY COLUMN `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '会话创建时间',
  ...
```

**覆盖的表:**

1. **业务表 (5个)**
   - trading_sessions - 交易会话表
   - trading_decisions - 交易决策表
   - analyst_analyses - 分析师分析表
   - market_data - 市场数据表
   - performance_metrics - 性能指标表

2. **缓存表 (3个)**
   - stock_prices - 股票价格缓存表
   - financial_metrics - 财务指标缓存表
   - company_news - 公司新闻缓存表

3. **Web应用表 (4个)**
   - hedge_fund_flows - 对冲基金流程配置表
   - hedge_fund_flow_runs - 流程执行记录表
   - hedge_fund_flow_run_cycles - 分析周期表
   - api_keys - API密钥表

**总计:** 12个表，170+个字段注释

## 工作流程

### 初次设置

```bash
# 1. 验证SQL文件
poetry run python scripts/validate_sql_comments.py

# 2. 备份数据库（可选但推荐）
mysqldump -u root -p hedge-fund > backup_$(date +%Y%m%d).sql

# 3. 添加注释
poetry run python scripts/add_database_comments.py
```

### 更新注释

如果需要修改或添加新的注释：

```bash
# 1. 编辑 database_comments.sql 文件

# 2. 验证修改
poetry run python scripts/validate_sql_comments.py

# 3. 应用到数据库
poetry run python scripts/add_database_comments.py
```

### 查看注释

在MySQL中查看注释：

```sql
-- 查看表注释
SHOW TABLE STATUS LIKE 'trading_sessions';

-- 查看字段注释
SHOW FULL COLUMNS FROM trading_sessions;

-- 查看所有表的注释
SELECT
    TABLE_NAME,
    TABLE_COMMENT
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = 'hedge-fund'
ORDER BY TABLE_NAME;
```

## 故障排查

### 问题1: 数据库连接失败

**错误信息:**
```
❌ 数据库连接失败: (2003, "Can't connect to MySQL server on 'localhost'")
```

**解决方案:**
1. 检查MySQL服务是否运行: `mysql.server status`
2. 检查.env文件中的数据库配置
3. 确认数据库用户名和密码正确

### 问题2: 表不存在

**错误信息:**
```
❌ 执行失败: (1146, "Table 'hedge-fund.trading_sessions' doesn't exist")
```

**解决方案:**
```bash
# 初始化数据库表
poetry run python -c "from src.database.connection import init_db; init_db()"
```

### 问题3: 权限不足

**错误信息:**
```
❌ 执行失败: (1142, "ALTER command denied to user")
```

**解决方案:**
```sql
-- 授予ALTER权限
GRANT ALTER ON `hedge-fund`.* TO 'your_user'@'localhost';
FLUSH PRIVILEGES;
```

### 问题4: 字符编码问题

**错误信息:**
```
UnicodeDecodeError: 'utf-8' codec can't decode byte
```

**解决方案:**
1. 确保SQL文件使用UTF-8编码
2. 确保数据库使用UTF-8字符集:
```sql
ALTER DATABASE `hedge-fund` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

## 最佳实践

1. **定期备份**: 在修改数据库前始终备份
2. **版本控制**: 将 `database_comments.sql` 纳入Git版本控制
3. **一致性**: 保持注释与代码模型的一致性
4. **可读性**: 使用清晰、简洁的中文注释
5. **完整性**: 确保所有表和重要字段都有注释

## 相关文档

- [数据库架构文档](../docs/database_schema.md) - 完整的数据库表结构说明
- [CLAUDE.md](../CLAUDE.md) - 项目开发指南

## 维护日志

| 日期 | 修改内容 | 修改人 |
|------|---------|--------|
| 2026-03-16 | 初始创建，添加12个表的中文注释 | Claude |

## 贡献指南

如果需要添加或修改注释：

1. 编辑 `database_comments.sql` 文件
2. 运行验证脚本确保语法正确
3. 测试在开发环境中应用注释
4. 更新 `docs/database_schema.md` 文档
5. 提交Pull Request

## 许可证

本项目采用 MIT 许可证。
