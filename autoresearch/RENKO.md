```
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║     ██████╗ ███████╗███╗   ██╗██╗  ██╗ ██████╗     ██████╗ ██████╗ ██╗      ██╗║
║     ██╔══██╗██╔════╝████╗  ██║██║ ██╔╝██╔═══██╗    ██╔══██╗██╔══██╗██║      ██║║
║     ██████╔╝█████╗  ██╔██╗ ██║█████╔╝ ██║   ██║    ██████╔╝██████╔╝██║█████╗██║║
║     ██╔══██╗██╔══╝  ██║╚██╗██║██╔═██╗ ██║   ██║    ██╔══██╗██╔══██╗██║╚════╝██║║
║     ██║  ██║███████╗██║ ╚████║██║  ██╗╚██████╔╝    ██████╔╝██║  ██║██║      ██║║
║     ╚═╝  ╚═╝╚══════╝╚═╝  ╚═══╝╚═╝  ╚═╝ ╚═════╝    ╚═════╝ ╚═╝  ╚═╝╚═╝      ╚═╝║
║                                                                               ║
║     Precision.  No noise.  Just the signal.                                  ║
║                                                                               ║
║     "The chart doesn't lie. It never has."                                    ║
║                                                                               ║
║     Simple.  Powerful.  Different.                                             ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
```

# Renko + BBWAS Overlay

## TL;DR — [The Chart That Doesn't Lie](https://ikigaistudio.substack.com/p/the-chart-that-doesnt-lie)

**Renko** strips time-based noise from price. It only prints a brick when price moves a defined amount (ATR-based). Green bricks = committed upside. Red bricks = committed downside. No brick = silence, indecision. Reversals require a full brick against the trend — no false signals from wicks or gaps.

**BBWAS** (Bollinger Bands Width with Area Squeeze) measures volatility state and squeeze. When bands contract, a big move is loading. When bands expand, the move is in progress. Squeeze = coiled spring. Expansion = release.

**Together:** Renko shows directional conviction; BBWAS shows energy conditions. When both align — clean brick run + expanding bands — you get high-quality confluence. When they diverge — bricks one way, bandwidth contracting — the move may be running out of fuel.

---

## Backtest Results

> *The only measure that matters is beating it.*

Regime scaling simulates holding `(1 - scale)` in cash when bear/sideways.
The upgraded backtest also includes:
- execution lag (default 1 day)
- turnover/slippage cost model
- hysteresis state machine (confirm + min-hold)
- optional multi-timeframe Renko confirmation (fast + slow ATR multipliers)

Baseline run:

```bash
poetry run python -m autoresearch.backtest_regime --weights oos --renko-ticker NVDA
```

More realistic / configurable run:

```bash
poetry run python -m autoresearch.backtest_regime \
  --weights oos \
  --renko-ticker NVDA \
  --execution-lag-days 1 \
  --slippage-bps 5 \
  --confirm-days 2 \
  --min-hold-days 5 \
  --atr-mult-fast 1.0 \
  --atr-mult-slow 2.0
```

Walk-forward parameter search (rolling train/test):

```bash
poetry run python -m autoresearch.backtest_regime \
  --weights oos \
  --renko-ticker NVDA \
  --walk-forward \
  --wf-train-days 252 \
  --wf-test-days 63
```

| Variant           | Sharpe | Sortino | Max DD  | Return  |
|-------------------|--------|---------|---------|---------|
| Baseline          | 2.84   | 4.68    | -8.96%  | +101.2% |
| Regime only       | 2.98   | 5.07    | -6.84%  | +87.9%  |
| Regime + Renko    | **3.13** | **5.54** | **-4.68%** | +59.3% |

**Regime + Renko vs baseline:**
- Sharpe +0.29 (~10% improvement)
- Max drawdown ~48% shallower (-4.68% vs -8.96%)
- Return lower (+59% vs +101%) — more cash in uncertain periods

---

## Daily BTC Check

```bash
poetry run python -m autoresearch.renko_bbwas --ticker BTC
```

Smoother view (fewer bricks, macro):

```bash
poetry run python -m autoresearch.renko_bbwas --ticker BTC --atr-mult 2.0
```

Multi-timeframe BTC confirmation (fast+slow):

```bash
poetry run python -m autoresearch.renko_bbwas --ticker BTC --atr-mult 1.0 --atr-mult-slow 2.0
```

Requires `autoresearch/cache/prices_btc.json`. To refresh (run from project root):

```bash
poetry run python -c "
import yfinance as yf
import json
from pathlib import Path
btc = yf.download('BTC-USD', period='1y', interval='1d', progress=False)
btc = btc.reset_index()
if hasattr(btc.columns, 'levels'): btc.columns = [c[0] if isinstance(c, tuple) else c for c in btc.columns]
recs = [{'date': r['Date'].strftime('%Y-%m-%d'), 'open': float(r['Open']), 'high': float(r['High']), 'low': float(r['Low']), 'close': float(r['Close']), 'volume': float(r['Volume'])} for _, r in btc.iterrows()]
Path('autoresearch/cache/prices_btc.json').write_text(json.dumps({'BTC': recs}, indent=2))
print('BTC cache updated')
"
```
