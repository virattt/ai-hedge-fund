# Bug 修复说明

## 问题描述

在 `src/agents/news_sentiment.py` 文件中发现一个 `UnboundLocalError` bug：

```python
UnboundLocalError: cannot access local variable 'sentiments_classified_by_llm'
where it is not associated with a value
```

### 根本原因

变量 `sentiments_classified_by_llm` 在第 64 行仅在 `if articles_without_sentiment:` 条件块内初始化：

```python
if company_news:
    recent_articles = company_news[:10]
    articles_without_sentiment = [news for news in recent_articles if news.sentiment is None]

    # 只在这里初始化
    sentiments_classified_by_llm = 0
    if articles_without_sentiment:
        # ... 使用变量
```

但在第 132 行，无论条件是否满足，都会使用这个变量：

```python
"articles_classified_by_llm": sentiments_classified_by_llm,  # 第 132 行
```

### 触发条件

当以下任一情况发生时，bug 会被触发：

1. **没有新闻**：`company_news` 为空列表
2. **所有新闻都有情绪标签**：`articles_without_sentiment` 为空列表

在这两种情况下，变量不会被初始化，但仍然会在后续代码中被引用。

## 修复方案

将变量初始化移到更外层的作用域，确保在所有代码路径中都能访问：

### 修改前（第 55-64 行）

```python
news_signals = []
sentiment_confidences = {}  # Store confidence scores for each article

if company_news:
    # Check the 10 most recent articles
    recent_articles = company_news[:10]
    articles_without_sentiment = [news for news in recent_articles if news.sentiment is None]

    # Analyze only the 5 most recent articles without sentiment to reduce LLM calls
    sentiments_classified_by_llm = 0  # ❌ 只在条件内初始化
    if articles_without_sentiment:
```

### 修改后（第 55-65 行）

```python
news_signals = []
sentiment_confidences = {}  # Store confidence scores for each article
sentiments_classified_by_llm = 0  # ✅ 提前初始化，避免 UnboundLocalError

if company_news:
    # Check the 10 most recent articles
    recent_articles = company_news[:10]
    articles_without_sentiment = [news for news in recent_articles if news.sentiment is None]

    # Analyze only the 5 most recent articles without sentiment to reduce LLM calls
    if articles_without_sentiment:
```

## 验证测试

创建了测试脚本 `test_news_sentiment_fix.py` 验证修复：

### 测试 1：没有新闻的情况
```python
# Mock get_company_news 返回空列表
api_module.get_company_news = lambda *args, **kwargs: []
```
**结果**：✅ 通过，`articles_classified_by_llm = 0`

### 测试 2：所有新闻都有情绪标签
```python
# Mock 返回已有情绪的新闻
mock_news = [
    CompanyNews(..., sentiment='positive'),
    CompanyNews(..., sentiment='negative'),
]
```
**结果**：✅ 通过，`articles_classified_by_llm = 0`

### 测试 3：新闻没有情绪标签（需要 LLM 分类）
这个测试需要真实的 LLM API 调用，但由于前两个测试已经覆盖了 bug 的触发条件，可以确认修复有效。

## 影响范围

- **文件**：`src/agents/news_sentiment.py`
- **修改行数**：1 行（将变量初始化从第 64 行移到第 57 行）
- **影响功能**：新闻情绪分析代理
- **向后兼容性**：✅ 完全兼容，只是修复了一个运行时错误

## 提交信息

```
fix: 修复 news_sentiment_agent 中的 UnboundLocalError

- 将 sentiments_classified_by_llm 变量初始化移到循环外层
- 确保在没有新闻或所有新闻都有情绪标签时不会抛出异常
- 添加测试验证修复有效性

Fixes: UnboundLocalError when processing news without sentiment labels
```

## 相关文件

- 修复文件：`src/agents/news_sentiment.py`
- 测试文件：`test_news_sentiment_fix.py`
- 文档更新：`BUG修复说明.md`（本文件）

## 修复日期

2026-03-13

## 修复人员

Claude (AI Assistant)
