# 算法输入输出对照表

本文档详细列出了每种算法的输入参数、输出结果和核心计算公式。

---

## 1. Warren Buffett 价值投资算法

### 输入参数

| 参数名 | 类型 | 说明 | 示例 |
|-------|------|------|------|
| `ticker` | str | 股票代码 | "AAPL" |
| `metrics` | List[Dict] | 财务指标列表（5期TTM） | ROE, D/E, Operating Margin等 |
| `financial_line_items` | List[Dict] | 财务明细项 | 净利润、折旧、资本支出等 |
| `market_cap` | float | 当前市值 | 2500000000000 |

### 输出结果

| 字段名 | 类型 | 说明 | 值范围 |
|-------|------|------|--------|
| `signal` | str | 交易信号 | "bullish" \| "bearish" \| "neutral" |
| `confidence` | float | 置信度 | 0-100 |
| `score` | float | 总评分 | 0-15 |
| `max_score` | float | 最高可能分数 | 15 |
| `fundamental_analysis` | Dict | 基本面分析详情 | score: 0-7 |
| `consistency_analysis` | Dict | 一致性分析详情 | score: 0-3 |
| `moat_analysis` | Dict | 护城河分析详情 | score: 0-3 |
| `management_analysis` | Dict | 管理层分析详情 | score: 0-2 |
| `intrinsic_value_analysis` | Dict | 内在价值分析 | 包含DCF计算结果 |
| `margin_of_safety` | float | 安全边际 | -1.0 到 无穷大 |

### 核心公式

**所有者收益**:
```
所有者收益 = 净利润 + 折旧 - 维护性资本支出 - 营运资本变化
维护性资本支出 = 总资本支出 × 0.75
```

**DCF内在价值**:
```
增长率 = 5%
折现率 = 9%
终值倍数 = 12
预测年限 = 10年

PV = Σ(所有者收益 × (1+0.05)^t / (1+0.09)^t) for t=1 to 10
终值 = 所有者收益 × (1+0.05)^10 × 12 / (1+0.09)^10
内在价值 = PV + 终值
```

**信号生成逻辑**:
```
IF 总分 >= 70%最高分 AND 安全边际 >= 30% THEN
    signal = "bullish"
ELSE IF 总分 <= 30%最高分 OR 安全边际 < -30% THEN
    signal = "bearish"
ELSE
    signal = "neutral"
```

---

## 2. Technical Analysis 技术分析算法

### 输入参数

| 参数名 | 类型 | 说明 | 示例 |
|-------|------|------|------|
| `ticker` | str | 股票代码 | "AAPL" |
| `prices` | List[Dict] | OHLCV价格数据 | 至少200天数据 |

### 输出结果

| 字段名 | 类型 | 说明 | 值范围 |
|-------|------|------|--------|
| `signal` | str | 综合交易信号 | "bullish" \| "bearish" \| "neutral" |
| `confidence` | int | 综合置信度 | 0-100 |
| `strategy_signals` | Dict | 5个策略的详细信号 | 见下表 |

#### 策略信号结构

每个策略包含:

| 字段名 | 类型 | 说明 |
|-------|------|------|
| `signal` | str | 该策略信号 |
| `confidence` | int | 该策略置信度(0-100) |
| `metrics` | Dict | 该策略的技术指标值 |

### 5种策略及指标

#### 策略1: 趋势跟踪 (25%权重)

**指标**:
- `adx`: Average Directional Index
- `trend_strength`: ADX/100

**公式**:
```
EMA(8, 21, 55) 交叉
信号: EMA8 > EMA21 > EMA55 → 看涨
     EMA8 < EMA21 < EMA55 → 看跌
```

#### 策略2: 均值回归 (20%权重)

**指标**:
- `z_score`: (价格 - MA50) / StdDev50
- `price_vs_bb`: 价格在布林带中的位置(0-1)
- `rsi_14`, `rsi_28`: 相对强弱指数

**公式**:
```
Z-Score < -2 AND 价格在BB下20% → 看涨
Z-Score > 2 AND 价格在BB上20% → 看跌
```

#### 策略3: 动量 (25%权重)

**指标**:
- `momentum_1m`: 21日收益率累计
- `momentum_3m`: 63日收益率累计
- `momentum_6m`: 126日收益率累计
- `volume_momentum`: 当前成交量 / 21日均量

**公式**:
```
动量分数 = 0.4×mom_1m + 0.3×mom_3m + 0.3×mom_6m
信号: 分数 > 0.05 AND 成交量 > 均量 → 看涨
```

#### 策略4: 波动率 (15%权重)

**指标**:
- `historical_volatility`: 21日年化波动率
- `volatility_regime`: 当前波动率 / 63日均值
- `volatility_z_score`: 波动率Z-Score
- `atr_ratio`: ATR / 价格

**公式**:
```
历史波动率 = 21日收益率标准差 × √252
信号: 低波动<0.8 AND z<-1 → 看涨(预期扩张)
```

#### 策略5: 统计套利 (15%权重)

**指标**:
- `hurst_exponent`: Hurst指数(<0.5均值回归, >0.5趋势)
- `skewness`: 63日收益率偏度
- `kurtosis`: 63日收益率峰度

**公式**:
```
Hurst < 0.4 AND 偏度 > 1 → 看涨
Hurst < 0.4 AND 偏度 < -1 → 看跌
```

### 加权组合公式

```python
weights = {
    "trend": 0.25,
    "mean_reversion": 0.20,
    "momentum": 0.25,
    "volatility": 0.15,
    "stat_arb": 0.15
}

加权分数 = Σ(策略信号值 × 权重 × 置信度) / Σ(权重 × 置信度)

IF 加权分数 > 0.2 THEN signal = "bullish"
ELSE IF 加权分数 < -0.2 THEN signal = "bearish"
ELSE signal = "neutral"
```

---

## 3. Fundamentals 基本面分析算法

### 输入参数

| 参数名 | 类型 | 说明 | 示例 |
|-------|------|------|------|
| `ticker` | str | 股票代码 | "AAPL" |
| `financial_metrics` | List[Dict] | TTM财务指标 | 至少1期数据 |

### 输出结果

| 字段名 | 类型 | 说明 | 值范围 |
|-------|------|------|--------|
| `signal` | str | 总体信号 | "bullish" \| "bearish" \| "neutral" |
| `confidence` | float | 置信度 | 0-100 |
| `reasoning` | Dict | 4个维度的详细分析 | 见下表 |

### 4个分析维度

#### 1. 盈利能力分析

**评分标准**:
- ROE > 15%: 达标
- Net Margin > 20%: 达标
- Operating Margin > 15%: 达标

**信号**:
```
≥2项达标 → bullish
0项达标 → bearish
其他 → neutral
```

#### 2. 增长分析

**评分标准**:
- Revenue Growth > 10%: 达标
- Earnings Growth > 10%: 达标
- Book Value Growth > 10%: 达标

**信号**: 同上

#### 3. 财务健康分析

**评分标准**:
- Current Ratio > 1.5: 达标
- Debt/Equity < 0.5: 达标
- FCF/Share > 0.8 × EPS: 达标

**信号**: 同上

#### 4. 估值比率分析

**评分标准**:
- P/E > 25: 高估
- P/B > 3: 高估
- P/S > 5: 高估

**信号**:
```
≥2项高估 → bearish (高估)
0项高估 → bullish (合理)
其他 → neutral
```

### 总体信号逻辑

```
看涨信号数 > 看跌信号数 → bullish
看跌信号数 > 看涨信号数 → bearish
相等 → neutral

置信度 = max(看涨数, 看跌数) / 4 × 100%
```

---

## 4. Valuation 估值分析算法

### 输入参数

| 参数名 | 类型 | 说明 | 示例 |
|-------|------|------|------|
| `ticker` | str | 股票代码 | "AAPL" |
| `financial_metrics` | List[Dict] | TTM财务指标(8期) | 用于计算历史倍数 |
| `line_items` | List[Dict] | 财务明细(2期) | 计算营运资本变化 |
| `market_cap` | float | 当前市值 | 100000000000 |

### 输出结果

| 字段名 | 类型 | 说明 | 值范围 |
|-------|------|------|--------|
| `signal` | str | 估值信号 | "bullish" \| "bearish" \| "neutral" |
| `confidence` | int | 置信度 | 0-100 |
| `weighted_gap` | float | 加权估值差距 | -1.0 到 无穷大 |
| `reasoning` | Dict | 4种方法的详细结果 | 见下表 |

### 4种估值方法

#### 方法1: DCF 现金流折现 (35%权重)

**输入**:
- free_cash_flow: 自由现金流

**参数**:
```
增长率 = 5%
折现率 = 10%
永续增长率 = 3%
预测年限 = 5年
```

**公式**:
```
PV = Σ(FCF × (1+g)^t / (1+r)^t) for t=1 to 5
终值 = FCF × (1+g)^5 × (1+g_terminal) / (r - g_terminal)
PV_终值 = 终值 / (1+r)^5
内在价值 = PV + PV_终值
```

#### 方法2: Owner Earnings 所有者收益法 (35%权重)

**输入**:
- net_income: 净利润
- depreciation: 折旧
- capex: 资本支出
- working_capital_change: 营运资本变化

**参数**:
```
增长率 = 5%
要求回报率 = 15%
安全边际 = 25%
预测年限 = 5年
```

**公式**:
```
所有者收益 = 净利润 + 折旧 - 资本支出 - 营运资本变化
PV = Σ(OE × (1+g)^t / (1+r)^t) for t=1 to 5
终值 = OE × (1+g)^5 × (1+g_terminal) / (r - g_terminal)
内在价值 = (PV + PV_终值) × (1 - 安全边际)
```

#### 方法3: EV/EBITDA 倍数法 (20%权重)

**输入**:
- enterprise_value: 企业价值
- ev_to_ebitda: 当前EV/EBITDA倍数
- historical_ev_ebitda: 历史倍数列表

**公式**:
```
当前EBITDA = EV / EV_to_EBITDA
中位数倍数 = median(历史EV/EBITDA)
隐含EV = 中位数倍数 × 当前EBITDA
净债务 = EV - 市值
隐含权益价值 = 隐含EV - 净债务
```

#### 方法4: Residual Income Model 剩余收益模型 (10%权重)

**输入**:
- market_cap: 市值
- net_income: 净利润
- price_to_book_ratio: P/B比率

**参数**:
```
账面价值增长率 = 3%
权益成本 = 10%
永续增长率 = 3%
预测年限 = 5年
```

**公式**:
```
账面价值 = 市值 / P/B
剩余收益0 = 净利润 - 权益成本 × 账面价值
PV_RI = Σ(RI0 × (1+g)^t / (1+r)^t) for t=1 to 5
终值_RI = RI0 × (1+g)^6 / (r - g_terminal)
内在价值 = (账面价值 + PV_RI + PV_终值) × 0.8
```

### 加权聚合逻辑

```python
weights = {
    "dcf": 0.35,
    "owner_earnings": 0.35,
    "ev_ebitda": 0.20,
    "residual_income": 0.10
}

每种方法的差距 = (估值 - 市值) / 市值

加权差距 = Σ(方法权重 × 差距) / Σ(有效方法权重)

IF 加权差距 > 15% THEN signal = "bullish" (低估)
ELSE IF 加权差距 < -15% THEN signal = "bearish" (高估)
ELSE signal = "neutral"

置信度 = min(|加权差距| / 30% × 100, 100)
```

---

## 5. Sentiment 情绪分析算法 (简化版)

### 输入参数

| 参数名 | 类型 | 说明 |
|-------|------|------|
| `ticker` | str | 股票代码 |
| `insider_trades` | List[Dict] | 内部交易记录 |
| `company_news` | List[Dict] | 公司新闻(最多100条) |

### 输出结果

| 字段名 | 类型 | 说明 |
|-------|------|------|
| `signal` | str | 情绪信号 |
| `confidence` | float | 置信度(0-100) |
| `reasoning` | str | 分析详情 |

### 计算逻辑

```python
内部交易权重 = 0.3
新闻权重 = 0.7

内部看涨 = 交易股数 > 0 的次数
内部看跌 = 交易股数 < 0 的次数

新闻看涨 = sentiment = "positive" 的次数
新闻看跌 = sentiment = "negative" 的次数

加权看涨 = 内部看涨×0.3 + 新闻看涨×0.7
加权看跌 = 内部看跌×0.3 + 新闻看跌×0.7

IF 加权看涨 > 加权看跌 THEN signal = "bullish"
ELSE IF 加权看跌 > 加权看涨 THEN signal = "bearish"
ELSE signal = "neutral"
```

---

## 6. Risk Management 风险管理算法 (简化版)

### 输入参数

| 参数名 | 类型 | 说明 |
|-------|------|------|
| `ticker` | str | 股票代码 |
| `portfolio` | Dict | 组合信息(cash, cost_basis) |
| `prices` | List[Dict] | 价格数据 |

### 输出结果

| 字段名 | 类型 | 说明 |
|-------|------|------|
| `remaining_position_limit` | float | 可用仓位额度 |
| `current_price` | float | 当前价格 |
| `reasoning` | Dict | 详细计算过程 |

### 计算逻辑

```python
总组合价值 = 现金 + Σ(所有持仓市值)
单股票限额 = 总组合价值 × 20%
当前持仓 = cost_basis[ticker]
剩余额度 = 单股票限额 - 当前持仓
最大可买 = min(剩余额度, 现金)

return 最大可买
```

---

## 使用建议

### 1. 组合使用策略

建议将多个算法结合使用：

```python
# 示例：综合决策流程
fundamentals_result = fundamentals_algorithm(data)
technical_result = technical_analysis_algorithm(data)
valuation_result = valuation_algorithm(data)

# 投票机制
bullish_votes = 0
if fundamentals_result['signal'] == 'bullish': bullish_votes += 1
if technical_result['signal'] == 'bullish': bullish_votes += 1
if valuation_result['signal'] == 'bullish': bullish_votes += 1

# 最终决策：至少2/3算法看涨
final_signal = 'bullish' if bullish_votes >= 2 else 'neutral'
```

### 2. 参数调优

每个算法的阈值都可以根据历史回测进行优化：

- Warren Buffett: 安全边际阈值（默认30%）
- Technical Analysis: 各策略权重
- Fundamentals: ROE、增长率等阈值
- Valuation: 各方法权重、折现率等

### 3. 数据要求

- **最少数据**: 至少需要1-2期财务数据
- **推荐数据**: 5-8期历史数据用于趋势分析
- **技术分析**: 至少200天价格数据

---

## 依赖库

```bash
# 基础算法（Warren Buffett, Fundamentals, Valuation）
# 不需要额外依赖，仅使用Python标准库

# 技术分析算法
pip install pandas numpy
```

---

## 快速开始

```bash
# 1. 运行单个算法
python algorithms_demo/warren_buffett_demo.py

# 2. 运行所有算法演示
python algorithms_demo/run_all_demos.py

# 3. 在自己的代码中使用
from algorithms_demo.warren_buffett_demo import warren_buffett_algorithm

result = warren_buffett_algorithm({
    "ticker": "AAPL",
    "metrics": [...],
    "financial_line_items": [...],
    "market_cap": 2500000000000
})

print(f"Signal: {result['signal']}, Confidence: {result['confidence']}%")
```

---

**免责声明**: 这些算法仅供教育和研究目的。不构成投资建议。
