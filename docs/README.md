# 项目文档索引

本目录包含AI对冲基金项目的所有技术文档。

---

## 📚 核心文档

### 快速开始
- [快速开始指南](../QUICK_START.md) - 5分钟快速上手
- [故障排除](../TROUBLESHOOTING.md) - 常见问题解决方案

### 数据库
- [数据库快速参考](database_quick_reference.md) - 常用查询和操作
- [数据库架构](database_schema.md) - 完整表结构和关系
- [数据库查询指南](DATABASE_QUERY_GUIDE.md) - 高级查询示例

### 系统架构
- [缓存架构](CACHE_ARCHITECTURE.md) - 双层缓存设计与实现
- [日志配置](logging_configuration.md) - 日志系统使用指南
- [反速率限制策略](ANTI_RATE_LIMIT.md) - API速率限制处理

### 测试
- [测试指南](TEST_GUIDE.md) - 测试编写和运行
- [测试命名规范](TEST_NAMING_CONVENTIONS.md) - 测试文件命名约定

### 部署
- [部署检查清单](DEPLOYMENT_CHECKLIST.md) - 生产环境部署步骤
- [Tushare设置](TUSHARE_SETUP.md) - Tushare API配置

---

## 🔧 实现文档

- [MySQL缓存实现](MYSQL_CACHE_IMPLEMENTATION.md) - L2缓存详细设计
- [实现总结](IMPLEMENTATION_SUMMARY.md) - 主要功能实现概览
- [日志优化](LOGGING_OPTIMIZATION.md) - 日志系统优化记录
- [测试优化](TEST_OPTIMIZATION_SUMMARY.md) - 测试框架优化
- [项目清理](PROJECT_CLEANUP_SUMMARY.md) - 代码清理记录

---

## 🐛 修复历史

- [修复历史记录](FIXES_HISTORY.md) - 所有重要Bug修复和改进

---

## 📦 归档文档

历史文档已移至 [`archive/`](archive/) 目录:
- Bug修复详情
- 数据库变更记录
- 过时的实现文档

---

## 🔍 文档导航

### 按角色查找

**开发者**:
1. [快速开始](../QUICK_START.md) - 环境搭建
2. [数据库架构](database_schema.md) - 理解数据模型
3. [测试指南](TEST_GUIDE.md) - 编写测试
4. [缓存架构](CACHE_ARCHITECTURE.md) - 理解缓存机制

**数据分析师**:
1. [数据库快速参考](database_quick_reference.md) - 常用查询
2. [数据库查询指南](DATABASE_QUERY_GUIDE.md) - 高级查询

**运维工程师**:
1. [部署检查清单](DEPLOYMENT_CHECKLIST.md) - 部署步骤
2. [日志配置](logging_configuration.md) - 日志管理
3. [故障排除](../TROUBLESHOOTING.md) - 问题诊断

### 按主题查找

**数据源**:
- [反速率限制策略](ANTI_RATE_LIMIT.md)
- [Tushare设置](TUSHARE_SETUP.md)
- [YFinance禁用说明](YFINANCE_DISABLED.md)

**性能优化**:
- [缓存架构](CACHE_ARCHITECTURE.md)
- [日志优化](LOGGING_OPTIMIZATION.md)
- [测试优化](TEST_OPTIMIZATION_SUMMARY.md)

**数据库**:
- [数据库架构](database_schema.md)
- [数据库快速参考](database_quick_reference.md)
- [数据库查询指南](DATABASE_QUERY_GUIDE.md)

---

## 📝 文档贡献

### 添加新文档
1. 在相应目录创建Markdown文件
2. 在本索引中添加链接
3. 确保文档包含:
   - 清晰的标题和描述
   - 代码示例(如适用)
   - 相关文档链接

### 更新现有文档
1. 保持向后兼容性
2. 更新修改日期
3. 在CHANGELOG.md中记录重大变更

### 归档过时文档
1. 移动到 `archive/` 目录
2. 从主索引中移除
3. 在归档目录添加README说明原因

---

## 🔗 相关资源

- [项目主README](../README.md)
- [变更日志](../CHANGELOG.md)
- [Claude配置](../CLAUDE.md)
- [GitHub仓库](https://github.com/virattt/ai-hedge-fund)

---

**最后更新**: 2024-03-17
