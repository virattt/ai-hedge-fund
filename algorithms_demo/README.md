# AI对冲基金算法演示文档

本目录包含AI对冲基金项目中所有算法的独立可运行演示代码。

## 📋 算法总览

| 算法名称 | 文件名 | 类型 | 描述 |
|---------|--------|------|------|
| Warren Buffett | `warren_buffett_demo.py` | 价值投资 | 巴菲特风格的价值投资算法 |
| Bill Ackman | `bill_ackman_demo.py` | 激进价值投资 | 阿克曼风格的激进价值投资 |
| Michael Burry | `michael_burry_demo.py` | 深度价值/逆向投资 | 迈克尔·伯里的深度价值挖掘 |
| Cathie Wood | `cathie_wood_demo.py` | 创新/颠覆性增长 | 凯茜·伍德的创新增长策略 |
| Technical Analysis | `technical_analysis_demo.py` | 技术分析 | 5种技术分析策略组合 |
| Fundamentals | `fundamentals_demo.py` | 基本面分析 | 4维度基本面评估 |
| Valuation | `valuation_demo.py` | 估值分析 | 4种估值方法聚合 |
| Sentiment | `sentiment_demo.py` | 情绪分析 | 内部交易+新闻情绪 |
| Risk Management | `risk_management_demo.py` | 风险管理 | 持仓规模和风险控制 |

---

## 📊 算法详细说明

### 1. Warren Buffett 算法

**文件**: `warren_buffett_demo.py`

**输入参数**:
```python
{
    "ticker": str,              # 股票代码，如 "AAPL"
    "metrics": List[dict],      # 财务指标列表（最近5期TTM数据）
    "financial_line_items": List[dict],  # 财务明细项
    "market_cap": float         # 当前市值
}
```

**输出结果**:
```python
{
    "signal": "bullish" | "bearish" | "neutral",
    "confidence": float,  # 0-100
    "score": float,      # 总得分
    "max_score": float,  # 最高可能分数
    "fundamental_analysis": {
        "score": float,
        "details": str,
        "metrics": dict  # ROE, Debt/Equity, Operating Margin, Current Ratio
    },
    "consistency_analysis": {
        "score": float,
        "details": str   # 收益增长一致性
    },
    "moat_analysis": {
        "score": float,
        "max_score": 3,
        "details": str   # 护城河指标
    },
    "management_analysis": {
        "score": float,
        "max_score": 2,
        "details": str   # 管理层质量
    },
    "intrinsic_value_analysis": {
        "intrinsic_value": float,
        "owner_earnings": float,
        "assumptions": dict  # DCF假设
    },
    "margin_of_safety": float  # 安全边际百分比
}
```

**核心算法**:
1. **所有者收益计算**: `净利润 + 折旧 - 维护性资本支出`
2. **DCF估值**: 10年现金流折现，5%增长率，9%折现率
3. **质量评分**: ROE>15%(2分) + D/E<0.5(2分) + OpMargin>15%(2分) + CurrentRatio>1.5(1分)
4. **护城河评分**: 多期ROE稳定>15%(1分) + 多期OpMargin稳定>15%(1分) + 两者都稳定(额外1分)
5. **管理质量**: 股票回购(1分) + 分红记录(1分)
6. **信号生成**: 总分>=70%最高分 且 安全边际>=30% → 看涨

---

### 2. Bill Ackman 算法

**文件**: `bill_ackman_demo.py`

**输入参数**:
```python
{
    "ticker": str,
    "metrics": List[dict],      # 年度财务指标（5期）
    "financial_line_items": List[dict],  # 年度财务明细（5期）
    "market_cap": float
}
```

**输出结果**:
```python
{
    "signal": "bullish" | "bearish" | "neutral",
    "confidence": float,  # 0-100
    "score": float,
    "max_score": 20,
    "quality_analysis": {
        "score": float,  # 最高5分
        "details": str   # 收入增长、营业利润率、自由现金流、ROE
    },
    "balance_sheet_analysis": {
        "score": float,  # 最高5分
        "details": str   # 债务比率、分红、回购
    },
    "activism_analysis": {
        "score": float,  # 最高2分
        "details": str   # 激进主义机会（收入增长但利润率低）
    },
    "valuation_analysis": {
        "score": float,  # 最高3分
        "intrinsic_value": float,
        "margin_of_safety": float,
        "details": str
    }
}
```

**核心算法**:
1. **业务质量**: 多期收入增长>50%(2分) + 营业利润率常>15%(2分) + 自由现金流多数为正(1分) + ROE>15%(2分)
2. **财务纪律**: 负债权益比多数<1.0(2分) + 持续分红(1分) + 股份减少(1分)
3. **激进主义潜力**: 收入增长>15% 但 平均利润率<10%(2分) → 运营改善机会
4. **DCF估值**: 6%增长率，10%折现率，15倍终值倍数
5. **信号生成**: 总分>=14/20(70%) → 看涨

---

### 3. Michael Burry 算法

**文件**: `michael_burry_demo.py`

**输入参数**:
```python
{
    "ticker": str,
    "metrics": List[dict],      # TTM财务指标（5期）
    "line_items": List[dict],   # 财务明细
    "insider_trades": List[dict],  # 内部交易（12个月）
    "news": List[dict],         # 公司新闻（250条）
    "market_cap": float
}
```

**输出结果**:
```python
{
    "signal": "bullish" | "bearish" | "neutral",
    "confidence": float,  # 0-100
    "score": float,
    "max_score": 12,
    "value_analysis": {
        "score": float,  # 最高6分
        "max_score": 6,
        "details": str   # FCF收益率、EV/EBIT
    },
    "balance_sheet_analysis": {
        "score": float,  # 最高3分
        "max_score": 3,
        "details": str   # 债务权益比、净现金头寸
    },
    "insider_analysis": {
        "score": float,  # 最高2分
        "max_score": 2,
        "details": str   # 净内部人买入
    },
    "contrarian_analysis": {
        "score": float,  # 最高1分
        "max_score": 1,
        "details": str   # 负面新闻数量（逆向指标）
    }
}
```

**核心算法**:
1. **深度价值指标**:
   - FCF收益率: >=15%(4分), >=12%(3分), >=8%(2分)
   - EV/EBIT: <6(2分), <10(1分)
2. **资产负债表**: D/E<0.5(2分), 现金>债务(1分)
3. **内部人活动**: 净买入(2分或1分，取决于买入规模)
4. **逆向情绪**: >=5条负面新闻(1分) → 市场过度悲观
5. **信号生成**: 总分>=8.4/12(70%) → 看涨

---

### 4. Cathie Wood 算法

**文件**: `cathie_wood_demo.py`

**输入参数**:
```python
{
    "ticker": str,
    "metrics": List[dict],      # 年度财务指标（5期）
    "financial_line_items": List[dict],  # 年度财务明细（5期）
    "market_cap": float
}
```

**输出结果**:
```python
{
    "signal": "bullish" | "bearish" | "neutral",
    "confidence": float,  # 0-100
    "score": float,
    "max_score": 15,
    "disruptive_analysis": {
        "score": float,     # 标准化到5分
        "raw_score": float,
        "max_score": 12,
        "details": str      # 收入增长加速、毛利率、运营杠杆、研发强度
    },
    "innovation_analysis": {
        "score": float,     # 标准化到5分
        "raw_score": float,
        "max_score": 15,
        "details": str      # 研发投资趋势、FCF、运营效率、CAPEX、股息
    },
    "valuation_analysis": {
        "score": float,     # 最高3分
        "intrinsic_value": float,
        "margin_of_safety": float,
        "details": str
    }
}
```

**核心算法**:
1. **颠覆性潜力**:
   - 收入增长加速(2分) + 高增长>100%(3分) 或 >50%(2分) 或 >20%(1分)
   - 毛利率扩张>5%(2分) + 高毛利率>50%(2分)
   - 正向运营杠杆(收入增速>费用增速)(2分)
   - 研发强度: >15%(3分), >8%(2分), >5%(1分)
2. **创新增长**:
   - 研发增长>50%(3分) + 研发强度提升(2分)
   - FCF强劲一致增长(3分)
   - 高且改善的营业利润率>15%(3分)
   - CAPEX强度>10%且增长>20%(2分)
   - 低股息率<20%(2分) → 专注再投资
3. **高增长DCF**: 20%增长率，15%折现率，25倍终值倍数
4. **信号生成**: 总分>=10.5/15(70%) → 看涨

---

### 5. Technical Analysis 算法

**文件**: `technical_analysis_demo.py`

**输入参数**:
```python
{
    "ticker": str,
    "prices": List[dict]  # OHLCV价格数据（建议至少200天）
}
```

**输出结果**:
```python
{
    "signal": "bullish" | "bearish" | "neutral",
    "confidence": float,  # 0-100
    "strategy_signals": {
        "trend_following": {
            "signal": "bullish" | "bearish" | "neutral",
            "confidence": float,  # 0-100
            "metrics": {
                "adx": float,
                "trend_strength": float
            }
        },
        "mean_reversion": {
            "signal": "bullish" | "bearish" | "neutral",
            "confidence": float,
            "metrics": {
                "z_score": float,
                "price_vs_bb": float,  # 价格在布林带中的位置 0-1
                "rsi_14": float,
                "rsi_28": float
            }
        },
        "momentum": {
            "signal": "bullish" | "bearish" | "neutral",
            "confidence": float,
            "metrics": {
                "momentum_1m": float,
                "momentum_3m": float,
                "momentum_6m": float,
                "volume_momentum": float
            }
        },
        "volatility": {
            "signal": "bullish" | "bearish" | "neutral",
            "confidence": float,
            "metrics": {
                "historical_volatility": float,  # 年化
                "volatility_regime": float,
                "volatility_z_score": float,
                "atr_ratio": float
            }
        },
        "statistical_arbitrage": {
            "signal": "bullish" | "bearish" | "neutral",
            "confidence": float,
            "metrics": {
                "hurst_exponent": float,  # <0.5均值回归, >0.5趋势
                "skewness": float,
                "kurtosis": float
            }
        }
    }
}
```

**核心算法**:
1. **趋势跟踪**(25%权重):
   - EMA(8, 21, 55)交叉
   - ADX趋势强度
   - 看涨: EMA8 > EMA21 > EMA55
2. **均值回归**(20%权重):
   - Z-score: <-2 且 价格在BB下20% → 看涨
   - RSI(14, 28)超卖/超买
3. **动量**(25%权重):
   - 动量分数 = 0.4×1月 + 0.3×3月 + 0.3×6月
   - 成交量确认
   - 看涨: 分数>0.05 且 成交量>21日均值
4. **波动率**(15%权重):
   - 21日历史波动率年化
   - 波动率regime vs 63日均值
   - 低波<0.8 且 z<-1 → 看涨（预期扩张）
5. **统计套利**(15%权重):
   - Hurst指数<0.4 → 均值回归
   - 偏度>1 → 看涨，偏度<-1 → 看跌
6. **加权组合**: 5种策略加权聚合，>0.2看涨，<-0.2看跌

---

### 6. Fundamentals 算法

**文件**: `fundamentals_demo.py`

**输入参数**:
```python
{
    "ticker": str,
    "financial_metrics": List[dict]  # TTM财务指标（10期）
}
```

**输出结果**:
```python
{
    "signal": "bullish" | "bearish" | "neutral",
    "confidence": float,  # 0-100
    "reasoning": {
        "profitability_signal": {
            "signal": "bullish" | "bearish" | "neutral",
            "details": str  # ROE, Net Margin, Op Margin
        },
        "growth_signal": {
            "signal": "bullish" | "bearish" | "neutral",
            "details": str  # Revenue Growth, Earnings Growth
        },
        "financial_health_signal": {
            "signal": "bullish" | "bearish" | "neutral",
            "details": str  # Current Ratio, D/E
        },
        "price_ratios_signal": {
            "signal": "bullish" | "bearish" | "neutral",
            "details": str  # P/E, P/B, P/S
        }
    }
}
```

**核心算法**:
1. **盈利能力**(4个信号中的1个):
   - ROE>15%(1分) + NetMargin>20%(1分) + OpMargin>15%(1分)
   - >=2分 → 看涨
2. **增长性**:
   - RevenueGrowth>10%(1分) + EarningsGrowth>10%(1分) + BookValueGrowth>10%(1分)
   - >=2分 → 看涨
3. **财务健康**:
   - CurrentRatio>1.5(1分) + D/E<0.5(1分) + FCF/Share>0.8×EPS(1分)
   - >=2分 → 看涨
4. **估值比率**:
   - P/E>25(1分) + P/B>3(1分) + P/S>5(1分)
   - >=2分 → 看跌（高估）
5. **最终信号**: 4个维度中看涨信号多 → 看涨

---

### 7. Valuation 算法

**文件**: `valuation_demo.py`

**输入参数**:
```python
{
    "ticker": str,
    "financial_metrics": List[dict],  # TTM财务指标（8期）
    "line_items": List[dict],         # TTM财务明细（2期）
    "market_cap": float
}
```

**输出结果**:
```python
{
    "signal": "bullish" | "bearish" | "neutral",
    "confidence": float,  # 0-100
    "reasoning": {
        "dcf_analysis": {
            "signal": "bullish" | "bearish" | "neutral",
            "details": str,  # 估值、市值、差距、权重
            "value": float,
            "gap": float
        },
        "owner_earnings_analysis": {...},
        "ev_ebitda_analysis": {...},
        "residual_income_analysis": {...}
    }
}
```

**核心算法**:
1. **DCF现金流折现**(35%权重):
   - 输入: 自由现金流
   - 参数: 5%增长率, 10%折现率, 3%永续增长, 5年预测
2. **所有者收益法**(35%权重):
   - 公式: 净利润 + 折旧 - 资本支出 - 营运资本变化
   - 参数: 5%增长率, 15%要求回报, 25%安全边际
3. **EV/EBITDA倍数法**(20%权重):
   - 使用历史中位数EV/EBITDA倍数
   - 隐含权益价值 = EV - 净债务
4. **剩余收益模型**(10%权重):
   - Edwards-Bell-Ohlson模型
   - 参数: 10%权益成本, 3%永续增长, 20%安全边际
5. **加权聚合**:
   - 加权差距 = Σ(方法权重 × 价值差距)
   - >15%低估 → 看涨，<-15%高估 → 看跌

---

### 8. Sentiment 算法

**文件**: `sentiment_demo.py`

**输入参数**:
```python
{
    "ticker": str,
    "insider_trades": List[dict],  # 内部交易记录
    "company_news": List[dict]     # 公司新闻（最多100条）
}
```

**输出结果**:
```python
{
    "signal": "bullish" | "bearish" | "neutral",
    "confidence": float,  # 0-100
    "reasoning": str  # "Weighted Bullish signals: X, Weighted Bearish signals: Y"
}
```

**核心算法**:
1. **内部交易分析**(30%权重):
   - 正交易股数 → 看涨
   - 负交易股数 → 看跌
2. **新闻情绪分析**(70%权重):
   - 正面情绪 → 看涨
   - 负面情绪 → 看跌
   - 中性 → 中性
3. **加权组合**:
   - 看涨信号 = 内部看涨×0.3 + 新闻看涨×0.7
   - 看跌信号 = 内部看跌×0.3 + 新闻看跌×0.7
   - 比较两者确定最终信号

---

### 9. Risk Management 算法

**文件**: `risk_management_demo.py`

**输入参数**:
```python
{
    "ticker": str,
    "portfolio": {
        "cash": float,
        "cost_basis": {ticker: float}  # 每个股票的持仓市值
    },
    "prices": List[dict]  # 价格数据
}
```

**输出结果**:
```python
{
    "remaining_position_limit": float,  # 可用仓位额度
    "current_price": float,
    "reasoning": {
        "portfolio_value": float,       # 总组合价值
        "current_position": float,      # 当前该股票持仓价值
        "position_limit": float,        # 单股票限额（总价值×20%）
        "remaining_limit": float,       # 剩余限额
        "available_cash": float         # 可用现金
    }
}
```

**核心算法**:
1. **总组合价值**: 现金 + 所有持仓市值
2. **单股票持仓限制**: 总价值 × 20%
3. **剩余额度**: 持仓限制 - 当前持仓
4. **最大可买入**: min(剩余额度, 可用现金)
5. **目的**: 确保任何单一股票不超过组合的20%，避免过度集中风险

---

## 🚀 使用方法

### 运行单个算法示例

```bash
# 运行Warren Buffett算法demo
python algorithms_demo/warren_buffett_demo.py

# 运行Technical Analysis算法demo
python algorithms_demo/technical_analysis_demo.py
```

### 运行所有算法测试

```bash
python algorithms_demo/run_all_demos.py
```

### 自定义输入数据

每个demo文件中都包含示例数据。您可以修改示例数据来测试不同场景：

```python
# 在demo文件中找到示例数据部分
sample_data = {
    "ticker": "AAPL",
    "metrics": [...],  # 修改这里的数据
    ...
}

# 运行算法
result = algorithm_function(sample_data)
print(result)
```

---

## 📦 依赖安装

```bash
pip install pandas numpy
```

---

## 📝 注意事项

1. **数据要求**:
   - 所有算法都需要真实的财务数据才能产生有意义的结果
   - Demo中使用的是示例/模拟数据，仅供演示算法逻辑

2. **独立运行**:
   - 每个算法都是完全独立的，不依赖其他算法
   - 可以单独复制任何算法文件到您的项目中使用

3. **扩展性**:
   - 所有算法都接受标准化的输入格式
   - 可以轻松集成到您自己的数据源
   - 可以调整算法参数以适应不同的交易策略

---

## 🎯 实际应用建议

1. **组合使用**: 建议组合使用多个算法，通过投票或加权方式做最终决策
2. **参数调优**: 每个算法中的阈值和参数都可以根据历史回测进行优化
3. **风险管理**: 始终使用Risk Management算法来控制单一持仓规模
4. **定期更新**: 定期更新财务数据以保持信号的时效性
5. **回测验证**: 在实盘前务必进行充分的历史回测

---

## 📚 参考资料

- Warren Buffett投资原则: 《巴菲特致股东的信》
- Bill Ackman策略: Pershing Square公开信
- Michael Burry方法: 《大空头》及其投资记录
- Cathie Wood理念: ARK Invest研究报告
- 技术分析: 《技术分析精论》
- 估值方法: 《估值》Aswath Damodaran

---

**免责声明**: 这些算法仅供教育和研究目的。不构成投资建议。投资有风险，决策需谨慎。
