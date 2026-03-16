# 日志优化总结

## 实施日期
2026-03-16

## 优化内容

### 1. 减少重复的Agent状态更新日志

**问题描述：**
控制台显示了大量重复的agent状态更新消息，如：
- "Fetching financial line items"
- "Gathering financial line items"
- "Getting market cap"

这些消息在每个agent执行时都会频繁更新，造成日志噪音。

**解决方案：**
在 `src/utils/progress.py` 中实现了状态更新节流机制：

1. **添加最小更新间隔**：默认0.5秒，避免同一agent的状态更新过于频繁
2. **优先显示重要状态**："Done"和"Error"状态始终立即显示
3. **挂起更新缓存**：被节流的更新会被缓存，在progress停止时统一刷新
4. **时间追踪**：每个agent维护独立的最后更新时间

**代码变更：**
- 新增字段：`min_update_interval`, `last_update_time`, `pending_updates`
- 修改方法：`update_status()` - 添加节流逻辑
- 新增方法：`_flush_pending_updates()` - 刷新挂起的更新
- 修改方法：`stop()` - 在停止前刷新所有挂起更新

**效果：**
- 减少控制台刷新频率，降低日志噪音
- 保留重要状态的即时显示
- 不丢失任何状态信息

---

### 2. 统一API调用的日志输出方式

**问题描述：**
`src/tools/api.py` 中混用了 `print()` 和 `logger` 进行日志输出：
- 第111行：Rate limiting消息使用 `print()`
- 第125行：连接错误使用 `print()`
- 第130行：重试失败使用 `print()`
- 第563行：公司数据获取错误使用 `print()`

`print()` 直接输出到stdout，绕过了日志配置，导致：
- 日志级别无法控制
- 无法统一格式化
- 可能与Rich进度显示冲突

**解决方案：**
将所有 `print()` 调用替换为适当的 `logger` 方法：

| 原代码 | 新代码 | 原因 |
|--------|--------|------|
| `print(f"Rate limited...")` | `logger.warning(...)` | 速率限制是警告级别 |
| `print(f"Connection error...")` | `logger.warning(...)` | 连接错误（重试中）是警告 |
| `print(f"Connection error after...")` | `logger.error(...)` | 最终失败是错误级别 |
| `print(f"Error fetching...")` | `logger.warning(...)` | API错误是警告级别 |

**效果：**
- 统一的日志输出方式
- 遵循日志级别配置
- 可以通过配置控制显示

---

### 3. 改进日志配置和可见性

**问题描述：**
用户报告数据源的URL和参数日志未显示在控制台。

**调查结果：**
经检查，URL/参数日志实际上已经在正常工作，用户日志中可见：
```
[HKAdapter] 🔄 Fetching financial metrics from SinaFinance for 03690...
[AKShare] 📡 Calling stock_hk_financial_indicator_em(symbol=03690)
[SinaFinance] 📡 GET https://...
```

**优化措施：**
尽管日志已经工作，但为了确保更好的可见性，在 `src/main.py` 中进行了以下改进：

1. **显式配置StreamHandler**：
   ```python
   stderr_handler = logging.StreamHandler(sys.stderr)
   stderr_handler.setLevel(logging.INFO)
   stderr_handler.setFormatter(logging.Formatter('%(message)s'))
   ```

2. **明确设置关键模块的日志级别**：
   ```python
   logging.getLogger('src.markets.sources').setLevel(logging.INFO)
   logging.getLogger('src.tools.api').setLevel(logging.INFO)
   logging.getLogger('src.markets.base').setLevel(logging.INFO)
   ```

3. **明确分离stdout和stderr**：
   - Rich进度显示使用stdout
   - 日志输出使用stderr
   - 在 `src/utils/progress.py` 中显式指定：`console = Console(file=sys.stdout)`

**效果：**
- 日志输出更加可靠
- 避免与Rich进度显示冲突
- 更清晰的输出流分离

---

## 数据源日志示例

当前系统会记录以下API调用详情：

### AKShare
```
[AKShare] 📡 Calling stock_zh_a_hist(symbol=000001, start_date=20240101, end_date=20240301, adjust=qfq)
[AKShare] 📡 Calling stock_hk_hist(symbol=00700, start_date=20240101, end_date=20240301, adjust=qfq)
[AKShare] 📡 Calling stock_hk_financial_indicator_em(symbol=03690)
```

### SinaFinance
```
[SinaFinance] 📡 GET https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol=sh000001&scale=240&ma=5&datalen=1023
[SinaFinance] 📡 GET https://stock.finance.sina.com.cn/hkstock/api/jsonp.php/param=HK03690
```

### YFinance
```
[YFinance] Rate limit hit for 03690 on attempt 1/3
[YFinance] Exponential backoff: waiting 5.1s before retry 2/3
```

### API工具
```
Rate limited (429). Attempt 1/4. Waiting 60s before retrying...
Connection error: ReadTimeout. Attempt 1/4. Retrying in 2s...
```

---

## 配置说明

### 调整状态更新频率

如需调整agent状态更新的节流间隔，修改 `src/utils/progress.py`：

```python
# 创建progress实例时指定间隔（秒）
progress = AgentProgress(min_update_interval=1.0)  # 1秒间隔
```

默认值为0.5秒，可根据需要调整：
- 更小的值（如0.2）：更频繁的更新，适合调试
- 更大的值（如1.0）：更少的更新，适合生产环境

### 调整日志级别

修改 `src/main.py` 中的日志配置：

```python
# 全局日志级别
logging.basicConfig(level=logging.DEBUG)  # 显示所有debug信息

# 特定模块日志级别
logging.getLogger('src.markets.sources').setLevel(logging.DEBUG)
```

可用级别：
- `DEBUG`：最详细，包括所有调试信息
- `INFO`：标准信息（默认）
- `WARNING`：警告和错误
- `ERROR`：仅错误

---

## 测试验证

### 测试命令

```bash
# 运行单个股票测试
poetry run python src/main.py --tickers 3690.HK --analysts-all --model "deepseek-chat"

# 观察日志输出：
# 1. Agent状态更新应该更加流畅，减少闪烁
# 2. 应该能看到API调用的详细URL和参数
# 3. 所有错误和警告应该使用统一格式
```

### 预期结果

1. **状态更新优化**：
   - 相同agent的状态更新间隔至少0.5秒
   - "Done"和"Error"状态立即显示
   - 控制台刷新更流畅

2. **日志可见性**：
   - 所有API调用都显示URL和参数
   - 错误和警告使用统一格式
   - 日志不与进度显示冲突

3. **统一输出**：
   - 所有日志使用logger而非print()
   - stderr用于日志，stdout用于进度显示
   - 日志级别可配置

---

## 相关文件

| 文件 | 变更内容 |
|------|----------|
| `src/utils/progress.py` | 添加状态更新节流机制 |
| `src/tools/api.py` | 将print()替换为logger |
| `src/main.py` | 改进日志配置 |
| `src/markets/sources/akshare_source.py` | 已有URL日志（无变更） |
| `src/markets/sources/sina_finance_source.py` | 已有URL日志（无变更） |
| `src/markets/sources/yfinance_source.py` | 已有重试日志（无变更） |

---

## 注意事项

1. **Rich Live Display**：
   - 使用stdout显示进度表格
   - 日志使用stderr避免冲突
   - 不要在agent代码中使用print()

2. **日志级别**：
   - INFO：正常操作信息（API调用、数据获取）
   - WARNING：可恢复的错误（重试、速率限制）
   - ERROR：不可恢复的错误（最终失败）

3. **性能考虑**：
   - 状态更新节流减少了控制台刷新频率
   - 对agent执行性能无影响
   - 日志输出对性能影响可忽略

---

## 未来改进建议

1. **日志文件输出**：
   - 添加FileHandler将日志写入文件
   - 便于事后分析和调试

2. **结构化日志**：
   - 使用JSON格式输出日志
   - 便于日志分析工具处理

3. **日志聚合**：
   - 相似的日志消息可以聚合显示
   - 例如："Fetched data for 10 tickers"而非10条单独消息

4. **进度条替代**：
   - 对于长时间运行的操作，使用进度条而非状态消息
   - 更直观的进度反馈
