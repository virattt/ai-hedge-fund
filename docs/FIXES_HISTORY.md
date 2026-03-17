# 修复历史记录

本文档记录项目中所有重要的Bug修复和改进。

---

## 2024-03-17: ROE数据格式与JSON解析修复

### 问题描述
1. **ROE数据格式错误**: EastmoneyCurlSource返回百分比数值(8.28 = 8.28%)未转换为小数
2. **JSON解析失败**: DeepSeek模型输出包含`<think>`标签导致解析失败

### 修复内容

#### 1. ROE数据格式修复
**位置**: `src/markets/sources/eastmoney_curl_source.py:173-176`

```python
# 修复前
"return_on_equity": self._safe_float(finance_data.get("f173")),
"gross_margin": self._safe_float(finance_data.get("f187")),

# 修复后
"return_on_equity": self._safe_float(finance_data.get("f173")) / 100 if ... else None,
"gross_margin": self._safe_float(finance_data.get("f187")) / 100 if ... else None,
```

**影响**: 所有使用EastmoneyCurlSource的A股财务数据

#### 2. JSON解析增强
**位置**: `src/utils/llm.py:109-157`

增强`extract_json_from_response`函数支持:
- Markdown代码块 (` ```json ... ``` `)
- XML标签清理 (`<think>`, `<output>`, `<reasoning>`)
- 智能括号匹配
- Fallback解析

**影响**: 所有使用非JSON模式的LLM调用

### 验证结果
- ✅ ROE: 从281.52% → 8.28% (正确)
- ✅ JSON解析: 5/5测试用例通过
- ✅ A股验证: 4/4股票数据格式正确
- ✅ 端到端测试: 代理正常分析并生成交易决策

### 相关文件
- `test_fixes.py` - 自动化测试
- `verify_cn_stocks.py` - A股数据验证

---

## 2024-03-16: 财务指标数据质量改进

### 问题描述
财务指标数据源返回格式不一致,导致代理分析错误。

### 修复内容
1. 统一百分比字段格式(ROE, margins, growth rates)
2. 添加数据验证层
3. 改进多源数据合并逻辑

### 影响范围
- 所有财务指标相关代理
- 数据验证器
- 缓存系统

**详细文档**: 见 `docs/archive/FINANCIAL_METRICS_FIX.md`

---

## 2024-03-16: 移除数据库外键约束

### 问题描述
外键约束导致:
- 数据插入顺序依赖
- 级联删除风险
- 性能开销

### 修复内容
移除所有外键约束,改用应用层维护数据完整性。

### 影响范围
- 所有数据库表
- 数据库初始化脚本
- 数据插入逻辑

**详细文档**: 见 `docs/archive/FOREIGN_KEY_REMOVAL_SUMMARY.md`

---

## 2024-03-15: 日志系统优化

### 改进内容
1. 统一日志格式
2. 添加结构化日志
3. 改进进度显示
4. 减少冗余日志

### 影响范围
- 所有数据源
- 市场适配器
- 代理系统

**详细文档**: `docs/logging_configuration.md`

---

## 2024-03-15: 缓存系统重构

### 改进内容
1. 双层缓存架构 (内存L1 + MySQL L2)
2. 智能缓存失效
3. 缓存性能监控

### 影响范围
- 价格数据缓存
- 财务指标缓存
- 新闻数据缓存

**详细文档**: `docs/CACHE_ARCHITECTURE.md`

---

## 2024-03-14: 测试框架优化

### 改进内容
1. 统一测试命名规范
2. 添加集成测试
3. 改进测试覆盖率
4. 优化测试性能

### 影响范围
- 所有测试文件
- CI/CD流程

**详细文档**: `docs/TEST_GUIDE.md`

---

## 查看完整修复细节

历史修复文档已归档到 `docs/archive/`:
- `BUG_FIX_SUMMARY.md` - 早期Bug修复
- `FINANCIAL_METRICS_FIX.md` - 财务指标修复详情
- `FOREIGN_KEY_REMOVAL_SUMMARY.md` - 外键移除总结
- `FOREIGN_KEY_REMOVAL_EXECUTION.md` - 外键移除执行记录

---

## 贡献指南

发现新Bug或完成修复后:
1. 在本文档顶部添加新条目
2. 包含: 问题描述、修复内容、影响范围、验证结果
3. 更新相关测试脚本
4. 更新CHANGELOG.md
