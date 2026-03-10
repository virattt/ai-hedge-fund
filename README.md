# AI Hedge Fund

Someone just open sourced an AI hedge fund with 18 agents that think like Wall Street legends.

Warren Buffett. Charlie Munger. Michael Burry. Cathie Wood. Bill Ackman. Ben Graham. Aswath Damodaran. All running on your laptop.

It is called AI Hedge Fund. You give it stock tickers. Eighteen AI agents analyze the company from every angle, then vote on whether to buy, sell, or hold.

Not a toy. Not a dashboard. A full multi-agent investment research system.

No Bloomberg Terminal. No $25K brokerage minimums. No financial advisor fees. Just AI agents doing the kind of research hedge funds charge 2-and-20 for.

## Meet the Team

- `Warren Buffett Agent` — Looks for wonderful businesses, durable moats, and fair prices
- `Charlie Munger Agent` — Demands quality, discipline, and margin of safety
- `Michael Burry Agent` — Hunts deep value, hidden risks, and contrarian setups
- `Cathie Wood Agent` — Focuses on innovation, disruption, and high-conviction growth
- `Bill Ackman Agent` — Looks for concentrated bets and catalyst-driven upside
- `Ben Graham Agent` — Screens for classic value and mispriced assets
- `Aswath Damodaran Agent` — Balances story, valuation, and intrinsic worth
- `11 more specialized agents` — Cover technicals, sentiment, fundamentals, growth, valuation, and news

## How It Works

1. Enter stock tickers such as `AAPL`, `NVDA`, or `TSLA`
2. Agents pull real financial data: earnings, balance sheets, insider activity, and news
3. Each agent analyzes the company through its own investment philosophy
4. A `Risk Manager` checks position sizing, concentration, and portfolio exposure
5. A `Portfolio Manager` synthesizes the signals and makes the final call
6. You get a `BUY`, `SELL`, or `HOLD` decision with full reasoning from the committee

## Why It Feels Different

Turn on `--show-reasoning` and you can watch each agent explain its logic step by step. The Buffett agent breaks down the moat. The Burry agent flags hidden downside. The Cathie agent makes the disruption case. They do not just generate answers. They debate them.

It also includes a full backtester, so you can run the system against historical data and see how the strategy would have performed.

In our workflow, [Dexter](https://github.com/eliza420ai-beep/dexter) is the primary thesis-driven researcher: it reads `SOUL.md`, builds the sleeves, and defines the bar for what the portfolio is supposed to do. AI Hedge Fund is the second-opinion engine. It runs 18 analyst agents plus risk and portfolio management against the same names so conviction gets challenged before it gets trusted.

> **Disclaimer** — This project is for **educational and research purposes only**. Not financial advice. No guarantees. Options and leveraged perpetuals carry substantial risk of loss. See [full disclaimer](#disclaimer).

---

## Table of Contents

- [Why This Exists](#why-this-exists)
- [Architecture](#architecture)
- [Agent Details](#agent-details)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Configuration](#configuration)
- [Usage](#usage)
  - [CLI](#cli)
  - [Backtester](#backtester)
  - [Web Application](#web-application)
- [How This Fits With Dexter](#how-this-fits-with-dexter)
- [Portfolio Builder](#portfolio-builder)
- [Hyperliquid Integration](#hyperliquid-integration)
- [Tastytrade Daily Options](#tastytrade-daily-options-experimental)
- [Project Structure](#project-structure)
- [Contributing](#contributing)
- [License](#license)
- [Disclaimer](#disclaimer)

---

## Why This Exists

Most retail investors read compelling investment theses — like "AI infrastructure is the biggest capex cycle since postwar" — but lack the tools to systematically evaluate positions, size them for risk, and stress-test the portfolio. This project bridges that gap.

The system takes a list of tickers, runs them through 18 specialized AI analyst agents (each modeled after a real-world investing legend or quantitative discipline), aggregates their signals through a risk manager, and produces position-level trading decisions with confidence scores and reasoning.

That matters even more in a thesis-driven stack. As described in [The Researcher Who Thinks](https://ikigaistudio.substack.com/p/the-researcher-who-thinks), Dexter is built to start from identity and thesis, not from ticker trivia. As described in [The Fund](https://ikigaistudio.substack.com/p/the-fund), that thesis currently expresses itself through two sleeves with zero overlap. This repo exists to be the adversarial committee around that process: a structured second opinion on the names, sizing, and regime assumptions coming out of Dexter.

### The Three Layers

**Layer 1 — AI-Powered Equity Analysis (Core)**
The foundation. 18 analyst agents analyze stocks across fundamentals, technicals, valuation, sentiment, and growth — then a risk manager and portfolio manager synthesize everything into buy/sell/hold decisions with position sizing. This works today.

**Layer 2 — Hyperliquid Integration (Crypto Perpetuals)**
Equities alone can't express every thesis. Hyperliquid provides access to crypto perpetual futures with on-chain transparency, deep liquidity, and up to 50x leverage. See [Hyperliquid Integration](#hyperliquid-integration) for details.

**Layer 3 — Tastytrade Daily Options (Experimental)**
An experimental module for generating income and expressing short-duration views through daily (0DTE) and short-dated options. See [Tastytrade Daily Options](#tastytrade-daily-options-experimental) for details.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        INPUT                                    │
│  Tickers + Portfolio (cash, positions) + Date Range             │
│  + SOUL.md thesis context (optional)                            │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   18 AI ANALYST AGENTS                          │
│                   (run in parallel via LangGraph)               │
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


---

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

An AI-powered portfolio construction and analysis system that combines multi-agent 
intelligence with systematic risk management. Built to translate macro investment 
theses into actionable, regime-aware portfolios across equities, crypto perpetuals, 
and short-dated options.

---

## Getting Started

### Prerequisites

- **Python 3.11+**
- **Poetry** (dependency management)
- **Node.js 18+** (only if running the web application)
- At least one LLM provider API key (OpenAI, Anthropic, Groq, DeepSeek, Google, xAI, or Ollama for local)

### Installation

```bash
# Clone the repository
git clone https://github.com/eliza420ai-beep/ai-hedge-fund.git
cd ai-hedge-fund

# Install Poetry (if not already installed)
curl -sSL https://install.python-poetry.org | python3 -

# Install dependencies
poetry install
```

Poetry is configured to use an in-project virtualenv at `.venv/`. Verify with:

```bash
poetry env info --path   # Should resolve to ./.venv
```

#### Optional extras

```bash
# Hyperliquid crypto perpetuals support
poetry install --extras hyperliquid

# Tastytrade options support
poetry install --extras tastytrade
```

### Configuration

#### 1. Set up API keys

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
XAI_API_KEY=your-key             # Grok 4

# Financial Data
FINANCIAL_DATASETS_API_KEY=your-key   # Required for tickers beyond AAPL, GOOGL, MSFT, NVDA, TSLA
```

**Financial Data**: AAPL, GOOGL, MSFT, NVDA, and TSLA are free. All other tickers require a [Financial Datasets API key](https://financialdatasets.ai/).

#### 2. (Optional) Thesis context — `SOUL.md`

You can provide a structural investment thesis that all 18 analyst agents and the portfolio manager receive as context, so they reason against *your* thesis (e.g., AI infrastructure layers, conviction tiers, sizing rules).

**Loading order:**

1. CLI flag: `--thesis /path/to/SOUL.md`
2. Repo root: `./SOUL.md`
3. Shared config: `~/.ai-hedge-fund/SOUL.md`

If no thesis is found, agents run with no thesis context.

#### 3. (Optional) Shared config directory

Create `~/.ai-hedge-fund/` for config shared between this repo and [Dexter](https://github.com/eliza420ai-beep/dexter):

| File | Purpose |
|------|---------|
| `SOUL.md` | Structural investment thesis |
| `PORTFOLIO.md` | Target allocations *(future)* |
| `VOICE.md` | Brand voice *(future)* |

---

## Usage

### CLI

```bash
# Basic analysis (defaults to GPT-4.1)
poetry run python src/main.py --tickers AAPL,MSFT,NVDA

# Pick specific analysts
poetry run python src/main.py --tickers NVDA,TSM,AMAT \
  --analysts warren_buffett,cathie_wood,technical_analyst

# Use all analysts with reasoning output
poetry run python src/main.py --tickers NVDA,AAPL --analysts-all --show-reasoning

# Specify model provider
poetry run python src/main.py --tickers NVDA --model llama-3.3-70b-versatile

# Custom date range
poetry run python src/main.py --tickers NVDA --start-date 2024-01-01 --end-date 2024-06-01

# Local LLMs via Ollama
poetry run python src/main.py --tickers NVDA --ollama

# Custom portfolio size and margin
poetry run python src/main.py --tickers NVDA,AAPL --initial-cash 500000 --margin-requirement 0.5

# Second-opinion pass on a picks-and-shovels sleeve
poetry run python src/main.py \
  --tickers AMAT,ASML,LRCX,KLAC,VRT,CEG \
  --analysts-all --show-reasoning

### 1. Tastytrade sleeve only

Use this to validate the names Dexter currently included in the tastytrade sleeve.

```bash
poetry run python src/main.py --tickers AMAT,ASML,LRCX,KLAC,TEL,VRT,CEG,EQT,ANET,SNPS,CDNS,BESIY,SNDK,WDC,STX,LITE,COHR,CIEN --analysts-all --show-reasoning
```

### 2. Hyperliquid sleeve only

Use this to validate the names Dexter currently included in the Hyperliquid sleeve.

```bash
poetry run python src/main.py --tickers TSM,NVDA,PLTR,ORCL,COIN,HOOD,CRCL,TSLA,META,MSFT,AMZN,GOOGL,GLD,SLV,SPY,SMH --analysts-all --show-reasoning
```

### 3. Tastytrade sleeve plus the main excluded challengers

This is the best test of whether Dexter left out better non-HL names.

```bash
poetry run python src/main.py --tickers AMAT,ASML,LRCX,KLAC,TEL,VRT,CEG,EQT,ANET,SNPS,CDNS,BESIY,SNDK,WDC,STX,LITE,COHR,CIEN,NVDA,AVGO,MRVL,ARM,AAPL,BE,SEI,CRWV,CORZ --analysts-all --show-reasoning
```

### 4. Hyperliquid sleeve plus the main excluded challengers

This checks whether the current HL basket should include other names such as `MU` or `AMD`.

```bash
poetry run python src/main.py --tickers TSM,NVDA,PLTR,ORCL,COIN,HOOD,CRCL,TSLA,META,MSFT,AMZN,GOOGL,GLD,SLV,SPY,SMH,MU,NFLX,RIVN,AAPL,AMD,MSTR --analysts-all --show-reasoning
```

### 5. Excluded names only

This is often the most useful command. It tells you which omitted names AIHF actually likes.

```bash
poetry run python src/main.py --tickers NVDA,AVGO,MRVL,ARM,AAPL,BE,SEI,CRWV,CORZ,MU,NFLX,RIVN,AMD,MSTR --analysts-all --show-reasoning
```

### 6. Reproducible run with fixed dates

If you want stable comparisons over time, pin the date range:

```bash
poetry run python src/main.py --tickers TSM,NVDA,PLTR,ORCL,COIN,HOOD,CRCL,TSLA,META,MSFT,AMZN,GOOGL --analysts-all --show-reasoning --start-date 2025-12-01 --end-date 2026-03-08
```

## How To Read The Output

You do not want perfect agreement. You want to find **high-conviction disagreement**.

### Good confirmation

- Dexter includes a name
- AIHF is also positive or supportive on it

### Possible problem

- Dexter includes a name
- AIHF is strongly negative on it

### Most valuable signal

- Dexter excluded a name
- AIHF comes back strongly positive on it

That last category is the real reason to run AIHF manually.

## Suggested Workflow

Run the commands in this order:

1. `excluded names only`
2. `tastytrade + challengers`
3. `hyperliquid + challengers`

This sequence gives the fastest feedback on whether Dexter missed anything important.
```

### Backtester

Test how the agent committee would have performed over historical periods:

```bash
poetry run python src/backtester.py --tickers AAPL,MSFT,NVDA
poetry run python src/backtester.py --tickers NVDA --start-date 2024-01-01 --end-date 2024-06-01
```

<img width="941" alt="Backtester output" src="https://github.com/user-attachments/assets/00e794ea-8628-44e6-9a84-8f8a31ad3b47" />

### Web Application

The web UI provides a visual interface for portfolio construction, analysis, and backtesting. Under the hood it uses a FastAPI backend, which also serves as a callable service so Dexter can trigger analyses over HTTP.

```bash
# Mac/Linux
cd app && bash run.sh

# Windows
cd app && run.bat
```

See the [app README](https://github.com/eliza420ai-beep/ai-hedge-fund/tree/main/app) for detailed setup instructions.

<img width="1721" alt="Web application" src="https://github.com/user-attachments/assets/b95ab696-c9f4-416c-9ad1-51feb1f5374b" />

### Docker

A Docker setup is available for containerized deployment:

```bash
cd docker
docker compose up
```

See [`docker/README.md`](docker/README.md) for details.

---

## How This Fits With Dexter

This repo is not meant to replace Dexter. It is meant to challenge it.

- **Dexter** is the primary researcher and portfolio architect. It reads `SOUL.md`, reasons from the thesis inward, and defines the target structure for the fund.
- **AI Hedge Fund** is the second-opinion layer. It runs a diversified committee of analyst agents on the same names and forces the thesis through a more traditional investing lens: fundamentals, valuation, technicals, sentiment, growth, and risk constraints.
- **FastAPI gives us a trigger surface**. Dexter can call AI Hedge Fund over HTTP when the second opinion should be part of the live research loop.
- **The output we care about is disagreement**. If Dexter loves a name and the committee hates it, that gap is useful. If both systems converge, confidence goes up.

For the two-sleeve architecture described in [The Fund](https://ikigaistudio.substack.com/p/the-fund), the practical workflow is:

1. Use [Dexter](https://github.com/eliza420ai-beep/dexter) to define the thesis, sleeves, and candidate names.
2. Run those names through AI Hedge Fund as a second opinion (CLI or FastAPI).
3. Compare committee consensus against thesis conviction.
4. Use the risk manager and portfolio manager to pressure-test sizing before anything becomes portfolio truth.

---

## Portfolio Builder

The portfolio builder defines your capital allocation and existing positions before the agents run.

**What it does:**
1. **Define your portfolio** — Set initial cash, existing long/short positions with entry prices
2. **Choose your analysts** — Select which AI agents evaluate the tickers (or use all 18)
3. **Set your constraints** — Margin requirements, date ranges, risk parameters
4. **Get decisions** — Each ticker receives a BUY/SELL/SHORT/COVER/HOLD decision with quantity, confidence score, and reasoning from every analyst

**Why it matters:**

The portfolio builder isn't just a stock screener — it's a **position-aware decision engine**. When it recommends buying 82 shares of NVDA, that number accounts for:

- Your available cash
- Volatility-adjusted position limits (higher volatility = smaller position)
- Correlation with other holdings (correlated positions get reduced)
- The aggregate signal strength across all selected analysts
- Existing position exposure (won't double up on concentrated bets)

---

## Hyperliquid Integration

> **Status: Planned** — architecture designed, implementation in progress

[Hyperliquid](https://hyperliquid.xyz) is a high-performance L1 blockchain purpose-built for on-chain perpetual futures trading. We chose it for on-chain transparency, deep liquidity, and API-first design.

| Scenario | Equity Action | Hyperliquid Action |
|----------|--------------|-------------------|
| Capitulation regime detected | Reduce equity exposure 20% | Open BTC/ETH short perp as portfolio hedge |
| BTC miner thesis (RIOT, CORZ, HUT) | Small equity positions | Express conviction via BTC long perp with tighter risk |
| High funding rates on ETH | — | Earn funding by shorting perp while holding spot elsewhere |
| Agent consensus: strong bearish on crypto | — | Open short perps with defined stop-loss |

Position sizing follows the same regime overlay as equities: full size in trending-bull, reduced in mean-reverting, minimal in capitulation.

## Tastytrade Daily Options (Experimental)

> **Status: Experimental** — research phase, not production-ready

[Tastytrade](https://tastytrade.com) offers commission-friendly options trading with API support for short-dated and 0DTE strategies. This module tests whether AI agent consensus can improve options strategy selection.

| Agent Signal | Options Strategy |
|-------------|-----------------|
| Bullish at 90%+ confidence | Sell put spreads |
| Bearish at 80%+ confidence | Buy put protection or sell call spreads |
| Neutral / mixed | Sell iron condors |
| High volatility regime | Widen strikes, reduce size, favor defined-risk |

**Risk warning**: Daily options can lose 100% of their value in hours. This module is purely experimental and any real implementation would require extensive backtesting and paper trading before live capital.

---

## Project Structure

```
ai-hedge-fund/
├── src/
│   ├── agents/              # 18 analyst agents + risk & portfolio managers
│   ├── backtesting/         # Backtesting engine, metrics, benchmarks
│   ├── cli/                 # CLI input parsing
│   ├── data/                # Data layer and providers (yfinance, Financial Datasets)
│   ├── execution/           # Broker integrations (paper, Hyperliquid, Tastytrade)
│   │   └── options/         # Options chain, strategy, greeks
│   ├── graph/               # LangGraph state definitions
│   ├── llm/                 # LLM model configuration and routing
│   ├── tools/               # Financial data API tools
│   ├── utils/               # Display, progress, thesis loading, visualization
│   ├── main.py              # Main entry point
│   ├── backtester.py        # Backtester entry point
│   └── scheduler.py         # Scheduling utilities
├── app/
│   ├── backend/             # FastAPI REST API
│   │   ├── routes/          # HTTP endpoints
│   │   ├── services/        # Business logic
│   │   ├── models/          # Pydantic schemas
│   │   ├── database/        # SQLAlchemy + Alembic migrations
│   │   └── repositories/    # Data access layer
│   └── frontend/            # React + Vite + TypeScript + Tailwind
│       ├── src/components/  # UI components
│       ├── src/nodes/       # Flow graph nodes
│       └── src/services/    # API services
├── tests/                   # Integration tests and fixtures
├── docker/                  # Docker Compose setup
├── docs/                    # PRDs and design documents
├── SOUL.md                  # Default investment thesis
├── pyproject.toml           # Poetry config and dependencies
└── .env.example             # Environment variable template
```

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Agent orchestration | [LangGraph](https://github.com/langchain-ai/langgraph) |
| LLM providers | OpenAI, Anthropic, Groq, DeepSeek, Google Gemini, xAI, GigaChat, Ollama |
| Financial data | [Financial Datasets](https://financialdatasets.ai/), Yahoo Finance |
| Backend API | FastAPI, SQLAlchemy, Alembic |
| Frontend | React, Vite, TypeScript, Tailwind CSS |
| Package management | Poetry (Python), npm (frontend) |

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes (`git commit -m 'Add my feature'`)
4. Push to the branch (`git push origin feature/my-feature`)
5. Create a Pull Request

**Please keep pull requests small and focused.**

If you have a feature request, please open an [issue](https://github.com/eliza420ai-beep/ai-hedge-fund/issues) and tag it with `enhancement`.

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

## Disclaimer

This project is for **educational and research purposes only**.

- Not intended for real trading or investment
- No investment advice or guarantees provided
- Creator assumes no liability for financial losses
- Consult a financial advisor for investment decisions
- Past performance does not indicate future results
- Options and leveraged perpetuals carry substantial risk of loss

By using this software, you agree to use it solely for learning purposes.
