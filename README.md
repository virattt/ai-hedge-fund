# AI Hedge Fund

An AI-powered portfolio construction and analysis system that combines multi-agent intelligence with systematic risk management. Built to translate macro investment theses into actionable, regime-aware portfolios across equities, crypto perpetuals, and short-dated options.

> **This project is for educational and research purposes only.** It does not execute live trades. See [Disclaimer](#disclaimer).

[![Twitter Follow](https://img.shields.io/twitter/follow/virattt?style=social)](https://twitter.com/virattt)

## Why This Exists

Most retail investors read compelling investment theses — like "AI infrastructure is the biggest capex cycle since postwar" — but lack the tools to systematically evaluate positions, size them for risk, and stress-test the portfolio. This project bridges that gap.

The system takes a list of tickers, runs them through 18 specialized AI analyst agents (each modeled after a real-world investing legend or quantitative discipline), aggregates their signals through a risk manager, and produces position-level trading decisions with confidence scores and reasoning.

### The Three Layers

**Layer 1 — AI-Powered Equity Analysis (Core)**
The foundation. 18 analyst agents analyze stocks across fundamentals, technicals, valuation, sentiment, and growth — then a risk manager and portfolio manager synthesize everything into buy/sell/hold decisions with position sizing. This works today.

**Layer 2 — Hyperliquid Integration (Crypto Perpetuals)**
Equities alone can't express every thesis. Hyperliquid provides access to crypto perpetual futures with on-chain transparency, deep liquidity, and up to 50x leverage. We integrated Hyperliquid to enable:

- **Hedging**: Short crypto-correlated positions when the regime detector signals capitulation (e.g., short BTC perps as a risk-off hedge against crypto-adjacent equity holdings like RIOT, CORZ, HUT)
- **Funding rate capture**: Earn yield by holding positions where funding rates are structurally positive — an additional alpha source uncorrelated to directional equity bets
- **Thesis expression**: Some AI infrastructure plays (GPU compute, decentralized inference) have crypto-native proxies that trade 24/7 with better liquidity than their OTC equity equivalents
- **Regime-conditional sizing**: The same regime overlay (trending-bull / mean-reverting / capitulation) that governs equity position sizes also governs leverage and directional exposure on Hyperliquid

The intent is not to "trade crypto" — it's to use perpetual futures as a precision instrument for portfolio-level hedging and thesis expression that equities alone can't provide.

**Layer 3 — Tastytrade Daily Options (Experimental)**
An experimental module for generating income and expressing short-duration views through daily (0DTE) and short-dated options on Tastytrade. This layer explores:

- **Premium selling on high-conviction holds**: Selling covered calls or cash-secured puts on positions the portfolio manager is already bullish on (e.g., selling puts on NVDA during pullbacks when all agents signal BUY at 95% confidence)
- **Defined-risk hedges**: Buying protective puts on positions with binary catalysts (earnings, geopolitical events) — similar to the essay-style "use put options rather than outright shorts for defined downside" approach
- **0DTE income generation**: Harvesting theta on same-day expiration options where the system's intraday sentiment and technical signals have an edge
- **Spread construction**: Using agent confidence scores to calibrate strike selection — higher confidence = tighter spreads (more premium, more risk), lower confidence = wider wings

This layer is **experimental** — options are complex instruments and daily expirations amplify both gains and losses. The goal is to explore whether AI agent consensus signals can inform short-duration options strategies in a systematically profitable way.

## How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│                        INPUT                                    │
│  Tickers + Portfolio (cash, positions) + Date Range             │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   18 AI ANALYST AGENTS                          │
│                   (run in parallel)                              │
│                                                                 │
│  Legend Agents:           Quantitative Agents:                   │
│  ├─ Aswath Damodaran      ├─ Technical Analyst                  │
│  ├─ Ben Graham            ├─ Fundamentals Analyst               │
│  ├─ Bill Ackman           ├─ Growth Analyst                     │
│  ├─ Cathie Wood           ├─ Valuation Analyst                  │
│  ├─ Charlie Munger        ├─ Sentiment Analyst                  │
│  ├─ Michael Burry         └─ News Sentiment Analyst             │
│  ├─ Mohnish Pabrai                                              │
│  ├─ Peter Lynch                                                 │
│  ├─ Phil Fisher                                                 │
│  ├─ Rakesh Jhunjhunwala                                         │
│  ├─ Stanley Druckenmiller                                       │
│  └─ Warren Buffett                                              │
└──────────────────────────┬──────────────────────────────────────┘
                           │ analyst signals (bullish/bearish/neutral + confidence)
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│              RISK MANAGER                                       │
│  Volatility-adjusted position limits, correlation analysis,     │
│  portfolio-level risk constraints                               │
└──────────────────────────┬──────────────────────────────────────┘
                           │ position limits per ticker
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│              PORTFOLIO MANAGER                                  │
│  Synthesizes all signals → BUY / SELL / SHORT / COVER / HOLD    │
│  with quantity, confidence, and reasoning per ticker             │
└──────────────────────────┬──────────────────────────────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
         ┌─────────┐ ┌──────────┐ ┌──────────────┐
         │ Equities │ │  Hyper-  │ │  Tastytrade  │
         │ (core)   │ │  liquid  │ │  Options     │
         │          │ │ (hedge)  │ │ (experiment) │
         └─────────┘ └──────────┘ └──────────────┘
```

<img width="1042" alt="Screenshot 2025-03-22 at 6 19 07 PM" src="https://github.com/user-attachments/assets/cbae3dcf-b571-490d-b0ad-3f0f035ac0d4" />

## Agent Details

| # | Agent | Style | What It Looks For |
|---|-------|-------|-------------------|
| 1 | Aswath Damodaran | Intrinsic valuation | Story + numbers + disciplined DCF |
| 2 | Ben Graham | Deep value | Hidden gems with margin of safety |
| 3 | Bill Ackman | Activist | Bold positions, catalysts for change |
| 4 | Cathie Wood | Disruptive growth | Innovation, TAM expansion, 5+ year horizons |
| 5 | Charlie Munger | Quality compounders | Wonderful businesses at fair prices |
| 6 | Michael Burry | Contrarian | Overvalued shorts, undervalued longs |
| 7 | Mohnish Pabrai | Dhandho | Low-risk doubles, asymmetric bets |
| 8 | Peter Lynch | Practical growth | "Ten-baggers" in everyday businesses |
| 9 | Phil Fisher | Scuttlebutt | Strong management, innovative products |
| 10 | Rakesh Jhunjhunwala | Macro/emerging | High-growth sectors, macro tailwinds |
| 11 | Stanley Druckenmiller | Global macro | Asymmetric macro bets, regime shifts |
| 12 | Warren Buffett | Value + moats | Wonderful companies at fair prices |
| 13 | Technical Analyst | Chart patterns | Trend, momentum, mean reversion, volatility |
| 14 | Fundamentals Analyst | Financial statements | Profitability, growth, health, ratios |
| 15 | Growth Analyst | Growth trends | Revenue acceleration, market expansion |
| 16 | Valuation Analyst | Intrinsic value | DCF, comparable analysis, fair value |
| 17 | Sentiment Analyst | Market behavior | Insider trades, institutional flows |
| 18 | News Sentiment Analyst | News analysis | News-driven sentiment shifts |

Plus **Risk Manager** (volatility/correlation-adjusted position limits) and **Portfolio Manager** (final decision synthesis).

## Disclaimer

This project is for **educational and research purposes only**.

- Not intended for real trading or investment
- No investment advice or guarantees provided
- Creator assumes no liability for financial losses
- Consult a financial advisor for investment decisions
- Past performance does not indicate future results
- Options and leveraged perpetuals carry substantial risk of loss

By using this software, you agree to use it solely for learning purposes.

## Table of Contents
- [How to Install](#how-to-install)
- [How to Run](#how-to-run)
  - [Command Line Interface](#️-command-line-interface)
  - [Web Application](#️-web-application)
- [Portfolio Builder](#portfolio-builder)
- [Hyperliquid Integration](#hyperliquid-integration)
- [Tastytrade Daily Options](#tastytrade-daily-options-experimental)
- [How to Contribute](#how-to-contribute)
- [License](#license)

## How to Install

### 1. Clone the Repository

```bash
git clone https://github.com/virattt/ai-hedge-fund.git
cd ai-hedge-fund
```

### 2. Set up API keys

```bash
cp .env.example .env
```

Edit `.env` with your keys:

```bash
# LLM Provider (at least one required)
OPENAI_API_KEY=your-key          # GPT-4.1, GPT-5.2
ANTHROPIC_API_KEY=your-key       # Claude Sonnet/Opus 4.5
GROQ_API_KEY=your-key            # Llama 3.3 70B (free tier available)
DEEPSEEK_API_KEY=your-key        # DeepSeek R1/V3
GOOGLE_API_KEY=your-key          # Gemini 3 Pro

# Financial Data
FINANCIAL_DATASETS_API_KEY=your-key   # Required for tickers beyond AAPL, GOOGL, MSFT, NVDA, TSLA
```

**Financial Data**: AAPL, GOOGL, MSFT, NVDA, and TSLA are free. All other tickers require a [Financial Datasets API key](https://financialdatasets.ai/).

### 3. (Optional) Shared config directory `~/.ai-hedge-fund/`

You can keep a **thesis document** (SOUL.md) and other config in a shared directory that both this repo and [Dexter](https://github.com/virattt/dexter) can use:

- **`~/.ai-hedge-fund/`** — shared config directory (create it yourself if you want to use it).
  - **SOUL.md** — your structural investment thesis. All 18 analyst agents and the portfolio manager receive this as context so they reason against *your* thesis (e.g. AI infrastructure layers, conviction tiers, sizing rules).
  - **PORTFOLIO.md** — (future) target allocations.
  - **VOICE.md** — (future) brand voice.

Thesis is **optional**. If you don’t set it up, agents run as before with no thesis context.

**Where SOUL.md is loaded (in order):**

1. CLI: `--thesis /path/to/SOUL.md` (if provided).
2. Repo root: `./SOUL.md`.
3. Shared config: `~/.ai-hedge-fund/SOUL.md`.

You can copy the repo’s [SOUL.md](SOUL.md) to `~/.ai-hedge-fund/SOUL.md` and edit it, or symlink it. The same path is used when running the web app.

### 4. Install dependencies

```bash
curl -sSL https://install.python-poetry.org | python3 -
poetry install
```

## How to Run

### ⌨️ Command Line Interface

```bash
# Basic analysis
poetry run python src/main.py --tickers AAPL,MSFT,NVDA

# Pick specific analysts
poetry run python src/main.py --tickers NVDA,TSM,AMAT --analysts warren_buffett,cathie_wood,technical_analyst

# Use all analysts with reasoning output
poetry run python src/main.py --tickers NVDA,AAPL --analysts-all --show-reasoning

# Specify model (useful for non-interactive environments)
poetry run python src/main.py --tickers NVDA --model llama-3.3-70b-versatile

# Custom date range
poetry run python src/main.py --tickers NVDA --start-date 2024-01-01 --end-date 2024-06-01

# Local LLMs via Ollama
poetry run python src/main.py --tickers NVDA --ollama

# Custom portfolio size and margin
poetry run python src/main.py --tickers NVDA,AAPL --initial-cash 500000 --margin-requirement 0.5
```

### Run the Backtester

```bash
poetry run python src/backtester.py --tickers AAPL,MSFT,NVDA
poetry run python src/backtester.py --tickers NVDA --start-date 2024-01-01 --end-date 2024-06-01
```

<img width="941" alt="Screenshot 2025-01-06 at 5 47 52 PM" src="https://github.com/user-attachments/assets/00e794ea-8628-44e6-9a84-8f8a31ad3b47" />

### 🖥️ Web Application

The web UI provides a visual interface for portfolio construction, analysis, and backtesting.

See detailed instructions [here](https://github.com/virattt/ai-hedge-fund/tree/main/app).

<img width="1721" alt="Screenshot 2025-06-28 at 6 41 03 PM" src="https://github.com/user-attachments/assets/b95ab696-c9f4-416c-9ad1-51feb1f5374b" />

## Portfolio Builder

The portfolio builder is the starting point for any analysis. It defines your capital allocation and existing positions before the agents run.

### What it does

1. **Define your portfolio**: Set initial cash, existing long/short positions with entry prices
2. **Choose your analysts**: Select which AI agents evaluate the tickers (or use all 18)
3. **Set your constraints**: Margin requirements, date ranges, risk parameters
4. **Get decisions**: Each ticker receives a BUY/SELL/SHORT/COVER/HOLD decision with quantity, confidence score, and reasoning from every analyst

### Why it matters

The portfolio builder isn't just a stock screener — it's a **position-aware decision engine**. When it recommends buying 82 shares of NVDA, that number accounts for:

- Your available cash
- Volatility-adjusted position limits (higher volatility = smaller position)
- Correlation with other holdings (correlated positions get reduced)
- The aggregate signal strength across all selected analysts
- Existing position exposure (won't double up on concentrated bets)

This is how institutional portfolio construction works, scaled down and made accessible.

## Hyperliquid Integration

> Status: **Planned** — architecture designed, implementation in progress

[Hyperliquid](https://hyperliquid.xyz) is a high-performance L1 blockchain purpose-built for on-chain perpetual futures trading. We chose Hyperliquid over centralized crypto exchanges for three reasons:

1. **On-chain transparency**: All orders, fills, and funding rates are verifiable on-chain — no exchange counterparty risk
2. **Deep liquidity**: Consistently top-3 perp DEX by volume, with tight spreads on majors
3. **API-first design**: The Hyperliquid Python SDK enables programmatic order placement, position management, and real-time market data

### How it fits the portfolio

The equity analysis pipeline produces signals like "RIOT is bearish with 10% confidence" or "NVDA is bullish at 95%." Hyperliquid extends what we can do with those signals:

| Scenario | Equity Action | Hyperliquid Action |
|----------|--------------|-------------------|
| Capitulation regime detected | Reduce equity exposure 20% | Open BTC/ETH short perp as portfolio hedge |
| BTC miner thesis (RIOT, CORZ, HUT) | Small equity positions | Express conviction via BTC long perp with tighter risk |
| High funding rates on ETH | — | Earn funding by shorting perp while holding spot elsewhere |
| Agent consensus: strong bearish on crypto | — | Open short perps with defined stop-loss |

The position sizing follows the same regime overlay as equities: full size in trending-bull, reduced in mean-reverting, minimal in capitulation.

## Tastytrade Daily Options (Experimental)

> Status: **Experimental** — research phase, not production-ready

[Tastytrade](https://tastytrade.com) offers commission-friendly options trading with excellent API support for short-dated and 0DTE (zero days to expiration) strategies. This module explores whether AI agent consensus can improve options strategy selection.

### The experiment

Traditional options selling (theta decay capture) relies on implied volatility being higher than realized volatility. We're testing whether agent signals add a second edge:

- **Agent consensus says BULLISH at 90%+ confidence** → Sell put spreads (collect premium, profit if stock stays flat or rises)
- **Agent consensus says BEARISH at 80%+ confidence** → Buy put protection or sell call spreads
- **Agent consensus is NEUTRAL/MIXED** → Sell iron condors (profit from range-bound movement)
- **High volatility regime detected** → Widen strikes, reduce position size, favor defined-risk structures

### Why daily options

Daily options have the fastest theta decay — an option loses the most time value in its final day. This creates opportunity for premium sellers but demands precision. The hypothesis is that 18 agents producing real-time signals can improve strike selection and directional bias compared to purely mechanical strategies.

### Risk warning

Daily options can lose 100% of their value in hours. This module is purely experimental and any real implementation would require extensive backtesting, paper trading, and strict risk controls before live capital is involved.

## How to Contribute

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

**Important**: Please keep your pull requests small and focused.

## Feature Requests

If you have a feature request, please open an [issue](https://github.com/virattt/ai-hedge-fund/issues) and tag it with `enhancement`.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
