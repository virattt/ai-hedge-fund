```
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║     ██████╗██████╗ ██╗   ██╗██████╗ ████████╗ ██████╗                         ║
║    ██╔════╝██╔══██╗╚██╗ ██╔╝██╔══██╗╚══██╔══╝██╔═══██╗                        ║
║    ██║     ██████╔╝ ╚████╔╝ ██████╔╝   ██║   ██║   ██║                        ║
║    ██║     ██╔══██╗  ╚██╔╝  ██╔═══╝    ██║   ██║   ██║                        ║
║    ╚██████╗██║  ██║   ██║   ██║        ██║   ╚██████╔╝                        ║
║     ╚═════╝╚═╝  ╚═╝   ╚═╝   ╚═╝        ╚═╝    ╚═════╝                         ║
║                                                                               ║
║     The benchmark.  No substitute.                                            ║
║                                                                               ║
║     "The only measure that matters is beating it."                            ║
║                                                                               ║
║     Precision.  No noise.  Just the signal.                                    ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
```

# Crypto Renko Study (BTC, SOL, HYPE)

This note captures:
- how we source historical data for BTC/SOL/HYPE
- how to run Renko + BBWAS tests in this repo
- backtest results
- decision framework for **SOL vs HYPE**

---

## TL;DR

> *The benchmark. No substitute.*

**BTC is our benchmark.** We only hold HYPE/SOL to outperform BTC. If they don't beat BTC, they're not worth holding.

**What works (from backtests):** Renko Timed HYPE — best risk-adjusted profile, true relative strength (not leveraged beta), positive turnover-adjusted alpha. Renko Timed SOL underperforms in this window. 200DMA and 2Y MA bands are macro overlays for when to size the alpha sleeve.

**Quick checks:** `crypto_relative_strength` for alpha vs BTC; `renko_bbwas` for regime; `backtest_crypto_rotation` for full metrics; `--liquidity-stress` before sizing HYPE. See [RENKO.md](RENKO.md) for Renko/BBWAS methodology.

---

## Benchmark mindset

> *The only measure that matters is beating it.*

**BTC is our core position and benchmark.** Same as the stock portfolio: we try to outperform the benchmark.

We only consider HYPE and SOL to **outperform BTC**. If they don't beat BTC, they're not worth holding. All metrics (capture ratios, Renko regime, turnover-adjusted alpha) are evaluated in that light.

---

## 1) Data Sources and Historical Coverage

### BTC and SOL
- Source: `yfinance`
- Symbols: `BTC-USD`, `SOL-USD`
- Coverage pulled: ~2 years daily OHLCV (`731` rows each)

### HYPE
- Source: Hyperliquid API (`candleSnapshot`)
- Coin: `HYPE`
- Coverage pulled: `2024-12-05` to `2026-03-12` (`463` rows)
- Endpoint used: `POST https://api.hyperliquid.xyz/info`

---

## 2) Commands to Refresh Data

Run from repo root.

```bash
poetry run python - <<'PY'
import json
from pathlib import Path
import datetime as dt
import requests
import yfinance as yf

cache = Path('autoresearch/cache')

for symbol, key, out in [('BTC-USD','BTC','prices_btc.json'),('SOL-USD','SOL','prices_sol.json')]:
    df = yf.download(symbol, period='2y', interval='1d', progress=False, auto_adjust=True).reset_index()
    if hasattr(df.columns, 'levels'):
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    recs = [{
        'date': r['Date'].strftime('%Y-%m-%d'),
        'open': float(r['Open']),
        'high': float(r['High']),
        'low': float(r['Low']),
        'close': float(r['Close']),
        'volume': float(r['Volume']),
    } for _, r in df.iterrows()]
    (cache / out).write_text(json.dumps({key: recs}, indent=2))
    print(f'{key}: {len(recs)} rows -> {out}')

end_ms = int(dt.datetime.now(dt.UTC).timestamp() * 1000)
start_ms = int((dt.datetime.now(dt.UTC) - dt.timedelta(days=730)).timestamp() * 1000)
r = requests.post(
    'https://api.hyperliquid.xyz/info',
    json={'type':'candleSnapshot','req':{'coin':'HYPE','interval':'1d','startTime':start_ms,'endTime':end_ms}},
    timeout=40,
)
r.raise_for_status()
rows = r.json()
recs = [{
    'date': dt.datetime.fromtimestamp(int(x['t'])/1000, dt.UTC).strftime('%Y-%m-%d'),
    'open': float(x['o']),
    'high': float(x['h']),
    'low': float(x['l']),
    'close': float(x['c']),
    'volume': float(x.get('v', 0.0)),
} for x in rows]
recs.sort(key=lambda x: x['date'])
(cache / 'prices_hype.json').write_text(json.dumps({'HYPE': recs}, indent=2))
print(f'HYPE: {len(recs)} rows -> prices_hype.json ({recs[0]["date"]}..{recs[-1]["date"]})')
PY
```

---

## 3) Spot Renko Signals (MTF)

See [RENKO.md](RENKO.md) for Renko/BBWAS methodology.

Command:

```bash
poetry run python -m autoresearch.renko_bbwas --ticker BTC --atr-mult 1.0 --atr-mult-slow 2.0
poetry run python -m autoresearch.renko_bbwas --ticker SOL --atr-mult 1.0 --atr-mult-slow 2.0
poetry run python -m autoresearch.renko_bbwas --ticker HYPE --atr-mult 1.0 --atr-mult-slow 2.0
```

Observed:
- **BTC:** `trending_bear`, scale `0.35`, confidence ~`62%`
- **SOL:** `trending_bear`, scale `0.35`, confidence ~`64%`
- **HYPE:** `neutral`, scale `0.60` (mixed conviction)

---

## 4) Portfolio Backtest (Realistic Settings)

Settings used for each overlay ticker:
- `--weights oos`
- `--execution-lag-days 1`
- `--slippage-bps 5`
- `--confirm-days 2`
- `--min-hold-days 5`
- `--atr-mult-fast 1.0`
- `--atr-mult-slow 2.0`

Commands:

```bash
poetry run python -m autoresearch.backtest_regime --weights oos --renko-ticker BTC  --execution-lag-days 1 --slippage-bps 5 --confirm-days 2 --min-hold-days 5 --atr-mult-fast 1.0 --atr-mult-slow 2.0
poetry run python -m autoresearch.backtest_regime --weights oos --renko-ticker SOL  --execution-lag-days 1 --slippage-bps 5 --confirm-days 2 --min-hold-days 5 --atr-mult-fast 1.0 --atr-mult-slow 2.0
poetry run python -m autoresearch.backtest_regime --weights oos --renko-ticker HYPE --execution-lag-days 1 --slippage-bps 5 --confirm-days 2 --min-hold-days 5 --atr-mult-fast 1.0 --atr-mult-slow 2.0
```

### Result Summary

Baseline (same run): Sharpe `2.8390`, Max DD `-8.96%`, Return `+101.20%`

| Overlay Ticker | Regime+Renko Sharpe | Max DD | Return | vs Baseline |
|---|---:|---:|---:|---|
| BTC  | 2.4272 | -4.71% | +37.36% | Lower Sharpe/return, much lower DD |
| SOL  | **2.6590** | -4.71% | **+41.27%** | Best of the 3 tested overlays |
| HYPE | 2.3784 | -4.71% | +37.83% | Weakest Sharpe of the 3 |

All three overlays improved drawdown similarly, but **SOL delivered the best risk-adjusted/return profile among BTC/SOL/HYPE overlays** in this test.

---

## 5) Direct SOL vs HYPE Backtest (the swap question)

To answer the *actual* question ("swap SOL for HYPE?"), we run a dedicated crypto backtest:
- Buy & Hold SOL
- Buy & Hold HYPE
- Static 50/50
- Renko Timed SOL (SOL vs cash)
- Renko Timed HYPE (HYPE vs cash)
- Renko Rotation (HYPE/SOL ratio)

Command:

```bash
poetry run python -m autoresearch.backtest_crypto_rotation \
  --execution-lag-days 1 \
  --slippage-bps 5 \
  --confirm-days 2 \
  --min-hold-days 5 \
  --atr-mult-fast 1.0 \
  --atr-mult-slow 2.0
```

Output includes Calmar, CVaR(99), TUW, Up/Down capture vs BTC, Regime Hit Rate, Turnover-adjusted alpha. Use `--extended` for Ulcer, VaR, Skew, Kurtosis, Rolling stability. Use `--liquidity-stress` for slippage sensitivity (see section 9).

Observed window: `2024-12-06` to `2026-03-12` (462 trading days)

| Strategy | Sharpe | Max DD | Return | Calmar | CVaR99% | TUW% | Notes |
|---|---:|---:|---:|---:|---:|---:|---|
| Buy & Hold SOL | -0.48 | -70.31% | -63.02% | -0.60 | -16.40 | 99.4 | Weak in this window |
| Buy & Hold HYPE | **1.04** | -68.02% | **+192.97%** | 1.24 | -14.45 | 94.8 | Best Sharpe/return |
| Static 50/50 SOL/HYPE | 0.44 | -60.90% | +20.65% | 0.18 | -14.93 | 92.6 | Blended outcome |
| Renko Timed SOL | -0.21 | -28.90% | -6.77% | -0.08 | -4.79 | 98.0 | Lower DD, weak return |
| Renko Timed HYPE | 0.67 | **-26.37%** | +44.30% | 0.93 | **-5.62** | 95.2 | Best DD and tail risk among timed |
| Renko Rotation (HYPE/SOL) | 0.38 | -62.49% | +10.77% | 0.09 | -14.89 | 92.9 | Ratio-tilt, but still volatile |

**Key takeaway:** In the direct crypto test, **HYPE clearly outperformed SOL** in this sampled period.  
However, HYPE also carries deep drawdown and concentration risk, so position sizing still matters.

### Alpha vs BTC (benchmark)

Only strategies with return &gt; BTC return add alpha. To get BTC return over the backtest window:

```bash
poetry run python -c "
import json
from pathlib import Path
import pandas as pd
cache = Path('autoresearch/cache')
btc = json.loads((cache/'prices_btc.json').read_text())['BTC']
df = pd.DataFrame(btc)
df['date'] = pd.to_datetime(df['date'])
df = df.set_index('date').sort_index()
df = df[df.index >= '2024-12-06']
if len(df) > 1:
    ret = (df['close'].iloc[-1] / df['close'].iloc[0] - 1) * 100
    print(f'BTC return (backtest window): {ret:+.2f}%')
"
```

Compare each strategy's return (table above) to this number. Capture ratios (UpCap, DnCap) show whether alpha is true relative strength or leveraged beta.

---

## 6) SOL vs HYPE — Decision from Tests

### Test-based answer
Given both test types:

1) **Stock-portfolio overlay test** (section 4): SOL overlay > HYPE overlay  
2) **Direct crypto swap test** (section 5): HYPE > SOL

So the decision depends on objective:

- If objective is **improving stock portfolio overlay**, keep SOL as preferred overlay.
- If objective is **pure crypto return in this recent regime**, HYPE wins this sample.

Practical recommendation: **partial, staged rotation** (not all-in swap):
- Start with `30-50%` of SOL sleeve moved to HYPE
- Keep risk controls and re-evaluate weekly with section 5 command

### Why (risk controls still required)
1. **HYPE concentration risk** remains higher (holder base is much smaller than SOL/ETH).
2. **Drawdown risk** is still large even when returns are strong.
3. **Regime dependence** is high: a momentum-favored window can reverse quickly.

### Practical allocation rule
- Stage risk in tranches (example: `30%` -> `40%` -> `50%` of SOL sleeve into HYPE)
- Only increase HYPE if:
  - HYPE Renko MTF stays `trending_bull` for 2+ weekly checks
  - Renko Timed HYPE Sharpe remains above Renko Timed SOL
  - max DD stays inside risk budget
  - liquidity/depth metrics remain healthy

---

## 7) Daily Monitoring Commands

### Relative strength vs BTC (alpha at a glance)

```bash
# Returns and alpha over 5d, 21d, 63d, 1y
poetry run python -m autoresearch.crypto_relative_strength

# With Renko regime on HYPE/BTC and SOL/BTC ratios
poetry run python -m autoresearch.crypto_relative_strength --renko
```

**Flags:** `--compact` minimal output · `--no-color` plain text · `--renko` adds regime section

Positive α = outperforming BTC. Use `--windows 5 21 63 252` to customize.

### Renko regime (spot)

```bash
poetry run python -m autoresearch.renko_bbwas --ticker BTC  --atr-mult 1.0 --atr-mult-slow 2.0
poetry run python -m autoresearch.renko_bbwas --ticker SOL  --atr-mult 1.0 --atr-mult-slow 2.0
poetry run python -m autoresearch.renko_bbwas --ticker HYPE --atr-mult 1.0 --atr-mult-slow 2.0
```

If needed, refresh data first using the refresh block in section 2.

---

## 8) 200-Day MA: Why it matters and explicit test

### Why care about 200DMA?

In this framework, 200DMA is a **risk guardrail**, not a primary alpha signal:
- Above 200DMA -> allow normal risk
- One asset below 200DMA -> tilt away from it
- Both below 200DMA -> reduce gross exposure

This helps avoid deep bear legs and can materially improve drawdown behavior.

### Test setup

We ran `backtest_crypto_rotation.py` with and without `--use-200dma-filter`, holding all else equal:
- lag `1d`
- slippage `5 bps`
- confirm `2`
- min-hold `5`
- Renko MTF `1.0 / 2.0`

Commands:

```bash
# baseline (no 200DMA guardrail)
poetry run python -m autoresearch.backtest_crypto_rotation \
  --execution-lag-days 1 --slippage-bps 5 \
  --confirm-days 2 --min-hold-days 5 \
  --atr-mult-fast 1.0 --atr-mult-slow 2.0

# with 200DMA guardrail
poetry run python -m autoresearch.backtest_crypto_rotation \
  --execution-lag-days 1 --slippage-bps 5 \
  --confirm-days 2 --min-hold-days 5 \
  --atr-mult-fast 1.0 --atr-mult-slow 2.0 \
  --use-200dma-filter
```

### Result deltas (from this run window)

| Strategy | No 200DMA | With 200DMA | Interpretation |
|---|---|---|---|
| Renko Timed SOL | Sharpe -0.208, DD -28.90%, Ret -6.77% | Sharpe -0.159, DD **-23.27%**, Ret **+1.19%** | Better DD and return |
| Renko Timed HYPE | Sharpe 0.666, DD -26.37%, Ret +44.30% | Sharpe 0.642, DD **-16.41%**, Ret +32.93% | Big DD improvement, return tradeoff |
| Renko Rotation HYPE/SOL | Sharpe 0.379, DD -62.49%, Ret +10.77% | Sharpe **0.490**, DD **-40.21%**, Ret **+34.99%** | Better on all three metrics |

### Conclusion on 200DMA in this repo

For these crypto strategies, the 200DMA guardrail materially improved drawdown control and improved the ratio-rotation profile.  
This supports using 200DMA as a **core risk filter** layered on top of Renko/BBWAS, especially for volatile pairs like HYPE/SOL.

---

## 9) Extended Metrics: Why Each One Matters

The crypto backtest reports a full suite of risk and performance metrics. Here's the rationale for each.

### Core risk metrics

| Metric | What it measures | Why we care |
|--------|------------------|-------------|
| **Calmar** | CAGR / \|Max DD\| | Return per unit of worst drawdown. Better for trend/momentum assets with fat drawdowns than Sharpe alone. |
| **CVaR(95/99)** | Mean of worst 5%/1% of daily returns (expected shortfall) | Crypto blowups hide in tails; CVaR is especially useful vs VaR. |
| **VaR(95/99)** | 5th/1st percentile of daily returns | Quick tail threshold; CVaR adds "how bad on average" when breached. |
| **Time Under Water (TUW)** | % of days below prior equity high | Psychologically and operationally important for real allocation comfort. |

### Drawdown depth and duration

| Metric | What it measures | Why we care |
|--------|------------------|-------------|
| **Ulcer Index** | sqrt(mean of squared % drawdowns from running high) | Measures depth and duration of drawdowns. |
| **Ulcer Performance Index** | (CAGR - rf) / Ulcer | Risk-adjusted return per unit of ulcer. |

### Distribution shape

| Metric | What it measures | Why we care |
|--------|------------------|-------------|
| **Skew** | Third moment of returns | Distinguishes convex upside profiles from crash-prone profiles. Positive = fat right tail. |
| **Kurtosis** | Fourth moment (excess) | Fat tails vs normal. High kurtosis = more extreme events. |

### Predictive alignment

| Metric | What it measures | Why we care |
|--------|------------------|-------------|
| **Regime Hit Rate (5d/10d)** | % of days where model direction matches next 5/10-day return sign | Not just PnL—actual predictive alignment. Excludes neutral. |

### Efficiency

| Metric | What it measures | Why we care |
|--------|------------------|-------------|
| **Turnover-adjusted alpha** | (Return - cost drag) / turnover | Return net of trading frictions per unit turnover. Prevents overtrading systems that "look good gross." |

### Relative strength vs BTC

| Metric | What it measures | Why we care |
|--------|------------------|-------------|
| **Up-capture %** | Portfolio mean when BTC &gt; 0 / BTC mean when BTC &gt; 0 | For SOL/HYPE, quickly tells if you're leveraged beta or true relative strength. |
| **Down-capture %** | Portfolio mean when BTC &lt; 0 / BTC mean when BTC &lt; 0 | How much you participate in BTC drawdowns. |

### Rolling stability

| Metric | What it measures | Why we care |
|--------|------------------|-------------|
| **Roll60/90 Sharpe mean** | Mean of rolling 60/90d Sharpe | Consistency across regimes. |
| **Roll60/90 DD mean** | Mean of rolling max DD | Stability of drawdown behavior. |
| **Roll60/90 Hit %** | Mean of rolling % positive days | Hit-rate consistency. |

You want consistency, not one lucky regime.

### Liquidity stress

| Command | What it does | Why we care |
|---------|--------------|-------------|
| `--liquidity-stress` | Runs backtest at 5, 10, 20, 50 bps slippage | Biggest hidden risk in SOL→HYPE rotation. HYPE is thinner; stress test shows cost sensitivity. |

### Commands

```bash
# Standard run (includes Calmar, CVaR, TUW, UpCap, DnCap, Hit5d, TurnAdj)
poetry run python -m autoresearch.backtest_crypto_rotation \
  --execution-lag-days 1 --slippage-bps 5 \
  --confirm-days 2 --min-hold-days 5 \
  --atr-mult-fast 1.0 --atr-mult-slow 2.0

# Extended metrics (Ulcer, VaR, Skew, Kurtosis, Rolling 60/90)
poetry run python -m autoresearch.backtest_crypto_rotation --extended

# Liquidity stress at 5/10/20/50 bps
poetry run python -m autoresearch.backtest_crypto_rotation --liquidity-stress
```

### Example: liquidity stress (Renko strategies)

| Slippage | Renko Timed HYPE Return | Cost Drag |
|----------|------------------------|-----------|
| 5 bps | +44.30% | 0.36% |
| 10 bps | +43.78% | 0.72% |
| 20 bps | +42.76% | 1.43% |
| 50 bps | +39.72% | 3.58% |

At 50 bps, Renko Timed HYPE loses ~4.6% to costs. For HYPE (thinner liquidity), this is the main hidden risk in a SOL→HYPE rotation.

---

## 10) 2-Year MA Multiplier: Macro Regime for BTC

### What it is

A long-term overlay for Bitcoin that uses two bands:

| Band | Definition | Historical meaning |
|------|-------------|--------------------|
| **2-Year MA (Buy Zone)** | 730-day simple moving average of BTC price | Historically, BTC has often bottomed near or below this line. Accumulation zone. |
| **2-Year MA × 5 (Sell Target)** | 2-year MA multiplied by 5 | Historically, BTC has often topped near or above this line. Overextension zone. |

BTC cycles between these bands over multi-year periods. The chart is a **macro regime filter for the benchmark**, not a direct alpha signal.

### Why we care (benchmark mindset)

Since **BTC is our benchmark**, the 2Y MA bands tell us when to be aggressive or defensive with the **alpha sleeve** (HYPE/SOL):

- **When BTC is near the sell target (red zone):** Market is historically stretched. HYPE/SOL, being higher beta, are likely even more overextended. **Action:** Reduce or cut HYPE/SOL. Outperforming BTC here means avoiding larger drawdowns.
- **When BTC is near the buy zone (green zone):** Market is historically cheap. HYPE/SOL could magnify upside in recovery. **Action:** Consider adding HYPE/SOL only if they show **relative strength vs BTC** (e.g. up-capture &gt; down-capture, Renko regime improving). If HYPE/SOL lag BTC in the buy zone, they're not adding alpha.
- **When BTC is in the middle:** No strong macro signal. **Action:** Use Renko regime, capture ratios, turnover-adjusted alpha, liquidity stress to size HYPE/SOL.

### How it fits with our metrics

The 2Y MA bands are a **macro overlay**, not a replacement for our metrics:

| BTC zone | Our metrics | Interpretation |
|----------|-------------|----------------|
| Near sell target | Calmar down, TUW up, rolling Sharpe weak | Strong signal to reduce HYPE/SOL. |
| Near sell target | Capture ratios show HYPE/SOL ≈ leveraged BTC | No alpha; cut exposure. |
| Near buy zone | HYPE/SOL show relative strength vs BTC | Consider adding alpha sleeve. |
| Near buy zone | HYPE/SOL lag BTC | No alpha; stay in BTC. |

### Practical takeaway

The 2Y MA bands help us:

1. **Avoid chasing** – When BTC is near the red zone, don't add HYPE/SOL.
2. **Avoid panic selling** – When BTC is near the green zone, don't dump HYPE/SOL if they're showing relative strength.
3. **Time alpha sizing** – Use the bands to decide when to be more or less aggressive with HYPE/SOL, while still judging alpha with capture ratios, Renko regime, and turnover-adjusted alpha.

**Bottom line:** The chart is a macro risk filter for when to size up or down the HYPE/SOL alpha sleeve—not a standalone alpha signal.

### Current 2Y MA status (run after refreshing data)

```bash
poetry run python -c "
import json
from pathlib import Path
import pandas as pd
cache = Path('autoresearch/cache')
btc = json.loads((cache/'prices_btc.json').read_text())['BTC']
df = pd.DataFrame(btc)
df['date'] = pd.to_datetime(df['date'])
df = df.set_index('date').sort_index()
close = df['close']
ma2y = close.rolling(730, min_periods=730).mean().iloc[-1]
ma2y_x5 = ma2y * 5
price = close.iloc[-1]
print(f'BTC price: \${price:,.0f}')
print(f'2Y MA (buy zone): \${ma2y:,.0f}')
print(f'2Y MA x 5 (sell target): \${ma2y_x5:,.0f}')
print(f'Price / 2Y MA: {price/ma2y:.2f}x')
"
```

---

## 11) Quick decision guide

| If... | Then... |
|-------|---------|
| BTC near sell target (2Y MA × 5) | Reduce or cut HYPE/SOL. Don't chase. |
| BTC near buy zone (2Y MA) | Consider adding HYPE/SOL only if relative strength vs BTC. Run `crypto_relative_strength --renko`. |
| HYPE/SOL capture ≈ leveraged BTC | No alpha; stay in BTC. |
| Renko Timed HYPE Sharpe &gt; Renko Timed SOL | HYPE favored for alpha sleeve. |
| Liquidity stress at 50 bps &gt; 3% cost drag | Size down HYPE; slippage risk is real. |

---

## 12) Known limitations

- **Backtest window:** 2024-12-06 to 2026-03-12 (~462 days). Single regime; results may not hold in different market conditions.
- **HYPE history:** HYPE data starts 2024-12-05. No stress test through a full crypto winter.
- **Execution:** Assumes 1-day lag, 5 bps slippage. Real execution may differ, especially for HYPE.
- **2Y MA:** Requires 730 days of BTC data. Refresh `prices_btc.json` if stale.

