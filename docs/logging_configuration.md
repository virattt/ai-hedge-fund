# 日志配置说明

## 当前日志配置

### 默认行为

系统使用Python的`logging`模块，默认配置如下：

**日志级别**: INFO
**输出位置**: 标准错误输出 (stderr)
**格式**: 简单消息格式（无时间戳）

### 配置位置

主要配置在以下文件：

1. **src/main.py** - CLI主程序的日志配置
2. **src/backtester.py** - 回测器的日志配置
3. **app/backend/main.py** - Web后端的日志配置

### main.py 日志配置

```python
# src/main.py (第30-47行)

# Configure logging to show INFO level messages
# This enables URL logging from data sources
# Use stderr to avoid conflicts with Rich progress display (which uses stdout)
# Add flush=True to ensure immediate output
stderr_handler = logging.StreamHandler(sys.stderr)
stderr_handler.setLevel(logging.INFO)
stderr_handler.setFormatter(logging.Formatter('%(message)s'))

logging.basicConfig(
    level=logging.INFO,
    handlers=[stderr_handler],
    force=True  # Force reconfiguration even if already configured
)

# Set specific loggers to INFO level to ensure they are visible
logging.getLogger('src.markets.sources').setLevel(logging.INFO)
logging.getLogger('src.tools.api').setLevel(logging.INFO)
logging.getLogger('src.markets.base').setLevel(logging.INFO)
```

## 日志存储位置

### 当前状态

**⚠️ 重要**: 系统当前**不会**将日志写入文件，所有日志都输出到终端（stderr）。

### 为什么这样设计？

1. **实时查看**: 开发和调试时可以实时看到日志
2. **避免文件管理**: 不需要担心日志文件大小和清理
3. **灵活重定向**: 用户可以自行决定是否保存日志

### 如何保存日志到文件？

如果你想保存日志到文件，有以下几种方法：

#### 方法1: 使用Shell重定向（推荐）

```bash
# 保存所有输出（包括stderr）到文件
poetry run python src/main.py --tickers AAPL --analysts-all --model "deepseek-chat" 2>&1 | tee hedge_fund.log

# 只保存stderr（日志）到文件
poetry run python src/main.py --tickers AAPL --analysts-all --model "deepseek-chat" 2> hedge_fund.log

# 保存到带时间戳的文件
poetry run python src/main.py --tickers AAPL --analysts-all --model "deepseek-chat" 2>&1 | tee "logs/run_$(date +%Y%m%d_%H%M%S).log"
```

#### 方法2: 修改代码添加文件处理器

在 `src/main.py` 中添加文件处理器：

```python
import logging
from pathlib import Path

# 创建logs目录
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

# 创建文件处理器
file_handler = logging.FileHandler(
    log_dir / f"hedge_fund_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
    encoding='utf-8'
)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))

# 同时输出到终端和文件
logging.basicConfig(
    level=logging.INFO,
    handlers=[stderr_handler, file_handler],  # 添加文件处理器
    force=True
)
```

#### 方法3: 使用环境变量控制

创建一个灵活的日志配置：

```python
import os
import logging
from pathlib import Path
from datetime import datetime

# 从环境变量读取配置
LOG_TO_FILE = os.getenv('LOG_TO_FILE', 'false').lower() == 'true'
LOG_DIR = os.getenv('LOG_DIR', 'logs')
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

handlers = [stderr_handler]

if LOG_TO_FILE:
    log_dir = Path(LOG_DIR)
    log_dir.mkdir(exist_ok=True)

    file_handler = logging.FileHandler(
        log_dir / f"hedge_fund_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
        encoding='utf-8'
    )
    file_handler.setLevel(getattr(logging, LOG_LEVEL))
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    handlers.append(file_handler)

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    handlers=handlers,
    force=True
)
```

使用方式：

```bash
# 启用日志文件
LOG_TO_FILE=true poetry run python src/main.py --tickers AAPL --analysts-all --model "deepseek-chat"

# 自定义日志目录和级别
LOG_TO_FILE=true LOG_DIR=my_logs LOG_LEVEL=DEBUG poetry run python src/main.py --tickers AAPL --analysts-all --model "deepseek-chat"
```

## 日志级别说明

### 当前使用的级别

- **INFO**: 正常运行信息（默认级别）
  - API请求URL
  - 数据源切换
  - 缓存命中/未命中
  - 重要的业务逻辑步骤

- **WARNING**: 警告信息
  - API请求失败但有重试
  - 数据解析错误但可继续
  - 配置问题提示

- **ERROR**: 错误信息
  - API请求完全失败
  - 数据处理错误
  - 系统异常

### 如何调整日志级别？

#### 方法1: 修改代码

```python
# 改为DEBUG级别，查看更详细的信息
logging.basicConfig(
    level=logging.DEBUG,  # 改为DEBUG
    handlers=[stderr_handler],
    force=True
)
```

#### 方法2: 使用环境变量（如果实现了方法3）

```bash
LOG_LEVEL=DEBUG poetry run python src/main.py --tickers AAPL --analysts-all --model "deepseek-chat"
```

## 关键日志记录器

系统中有几个重要的日志记录器：

### 1. src.markets.sources

记录数据源相关的信息：

```python
logger = logging.getLogger(__name__)  # 在各个source文件中
```

日志内容：
- API请求URL
- 数据源选择
- 请求成功/失败
- 重试信息

### 2. src.tools.api

记录API调用信息：

```python
logger = logging.getLogger(__name__)  # 在api.py中
```

日志内容：
- API函数调用
- 缓存命中情况
- 数据转换过程

### 3. src.data.mysql_cache

记录缓存操作：

```python
logger = logging.getLogger(__name__)  # 在mysql_cache.py中
```

日志内容：
- 缓存读取/写入
- 数据库操作
- 缓存失效

## 查看特定模块的日志

### 只看数据源日志

```python
# 设置其他模块为WARNING级别，只显示src.markets.sources的INFO日志
logging.getLogger('src.markets.sources').setLevel(logging.INFO)
logging.getLogger('src.tools.api').setLevel(logging.WARNING)
logging.getLogger('src.data').setLevel(logging.WARNING)
```

### 只看API调用日志

```python
logging.getLogger('src.markets.sources').setLevel(logging.WARNING)
logging.getLogger('src.tools.api').setLevel(logging.INFO)
logging.getLogger('src.data').setLevel(logging.WARNING)
```

## 日志格式说明

### 当前格式（简单）

```
%(message)s
```

输出示例：
```
✅ 数据库连接成功：localhost:3306/hedge-fund
🔍 Fetching prices for AAPL from 2024-01-01 to 2024-03-01
```

### 完整格式（建议用于文件）

```python
'%(asctime)s - %(name)s - %(levelname)s - %(message)s'
```

输出示例：
```
2026-03-16 10:30:45 - src.tools.api - INFO - 🔍 Fetching prices for AAPL from 2024-01-01 to 2024-03-01
2026-03-16 10:30:46 - src.markets.sources.yfinance_source - INFO - ✅ Successfully fetched 60 price records
```

## 常见问题

### Q1: 为什么看不到某些日志？

**A**: 检查以下几点：

1. 日志级别是否正确设置
2. 是否有其他代码覆盖了日志配置
3. 是否在正确的输出流（stderr vs stdout）

### Q2: 如何临时增加日志详细程度？

**A**: 在运行前设置环境变量：

```bash
# 如果实现了环境变量控制
LOG_LEVEL=DEBUG poetry run python src/main.py ...

# 或者修改代码临时改为DEBUG
# 在 src/main.py 中将 logging.INFO 改为 logging.DEBUG
```

### Q3: 日志太多，如何减少？

**A**: 提高日志级别：

```python
# 只显示WARNING和ERROR
logging.basicConfig(
    level=logging.WARNING,  # 改为WARNING
    handlers=[stderr_handler],
    force=True
)
```

### Q4: 如何只保存错误日志？

**A**: 创建一个只记录ERROR的文件处理器：

```python
error_file_handler = logging.FileHandler('errors.log')
error_file_handler.setLevel(logging.ERROR)  # 只记录ERROR及以上
error_file_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))

logging.basicConfig(
    level=logging.INFO,
    handlers=[stderr_handler, error_file_handler],
    force=True
)
```

## 推荐的日志配置

### 开发环境

```python
# 输出到终端，INFO级别，简单格式
logging.basicConfig(
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stderr)],
    format='%(message)s',
    force=True
)
```

### 生产环境

```python
# 同时输出到终端和文件，INFO级别，完整格式
from logging.handlers import RotatingFileHandler

# 终端处理器（简单格式）
stderr_handler = logging.StreamHandler(sys.stderr)
stderr_handler.setFormatter(logging.Formatter('%(message)s'))

# 文件处理器（完整格式，自动轮转）
file_handler = RotatingFileHandler(
    'logs/hedge_fund.log',
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5,  # 保留5个备份
    encoding='utf-8'
)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))

logging.basicConfig(
    level=logging.INFO,
    handlers=[stderr_handler, file_handler],
    force=True
)
```

### 调试环境

```python
# 输出到文件，DEBUG级别，超详细格式
logging.basicConfig(
    level=logging.DEBUG,
    handlers=[
        logging.FileHandler('logs/debug.log', encoding='utf-8')
    ],
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    force=True
)
```

## 日志轮转和清理

### 使用RotatingFileHandler

```python
from logging.handlers import RotatingFileHandler

handler = RotatingFileHandler(
    'logs/hedge_fund.log',
    maxBytes=10*1024*1024,  # 10MB per file
    backupCount=5,  # Keep 5 backup files
    encoding='utf-8'
)
```

文件命名：
- `hedge_fund.log` - 当前日志
- `hedge_fund.log.1` - 第一个备份
- `hedge_fund.log.2` - 第二个备份
- ...

### 使用TimedRotatingFileHandler

```python
from logging.handlers import TimedRotatingFileHandler

handler = TimedRotatingFileHandler(
    'logs/hedge_fund.log',
    when='midnight',  # 每天午夜轮转
    interval=1,
    backupCount=30,  # 保留30天
    encoding='utf-8'
)
```

### 手动清理

```bash
# 删除7天前的日志
find logs/ -name "*.log*" -mtime +7 -delete

# 只保留最新的10个日志文件
ls -t logs/*.log* | tail -n +11 | xargs rm -f
```

## 总结

### 当前配置

✅ **日志级别**: INFO
✅ **输出位置**: 终端 (stderr)
✅ **格式**: 简单消息格式
❌ **文件存储**: 不保存到文件

### 如何保存日志

**快速方法**（无需修改代码）：
```bash
poetry run python src/main.py ... 2>&1 | tee logs/run.log
```

**长期方案**（修改代码）：
1. 添加文件处理器
2. 使用环境变量控制
3. 实现日志轮转

### 相关文件

- `src/main.py` - CLI日志配置
- `src/backtester.py` - 回测器日志配置
- `app/backend/main.py` - Web后端日志配置
- `src/tools/api.py` - API调用日志
- `src/markets/sources/*.py` - 数据源日志
- `src/data/mysql_cache.py` - 缓存日志
