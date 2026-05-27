# Open Hedge (100% Native Rust Port)

> [!NOTE]
> **Upstream Credit:** This project is a complete high-performance, 100% native Rust port of the original Python-based [virattt/ai-hedge-fund](https://github.com/virattt/ai-hedge-fund) repository. All credit for the brilliant agentic design, collaborative trading workflows, and educational framework goes to the original upstream repository.

This is a proof of concept for **Open Hedge**, a high-performance agentic trading simulator. The goal of this project is to explore the use of AI to make trading decisions. This project is for **educational** purposes only and is not intended for real trading or investment.

This system employs several high-performance agents working in parallel:

1. Aswath Damodaran Agent - The Dean of Valuation, focuses on story, numbers, and disciplined valuation
2. Ben Graham Agent - The godfather of value investing, only buys hidden gems with a margin of safety
3. Bill Ackman Agent - An activist investor, takes bold positions and pushes for change
4. Cathie Wood Agent - The queen of growth investing, believes in the power of innovation and disruption
5. Charlie Munger Agent - Warren Buffett's partner, only buys wonderful businesses at fair prices
6. Michael Burry Agent - The Big Short contrarian who hunts for deep value
7. Mohnish Pabrai Agent - The Dhandho investor, who looks for doubles at low risk
8. Nassim Taleb Agent - The Black Swan risk analyst, focuses on tail risk, antifragility, and asymmetric payoffs
9. Peter Lynch Agent - Practical investor who seeks "ten-baggers" in everyday businesses
10. Phil Fisher Agent - Meticulous growth investor who uses deep "scuttlebutt" research 
11. Rakesh Jhunjhunwala Agent - The Big Bull of India
12. Stanley Druckenmiller Agent - Macro legend who hunts for asymmetric opportunities with growth potential
13. Warren Buffett Agent - The oracle of Omaha, seeks wonderful companies at a fair price
14. Valuation Agent - Calculates the intrinsic value of a stock and generates trading signals
15. Sentiment Agent - Analyzes market sentiment and generates trading signals
16. Fundamentals Agent - Analyzes fundamental data and generates trading signals
17. Technicals Agent - Analyzes technical indicators and generates trading signals
18. Risk Manager - Calculates risk metrics and sets position limits
19. Portfolio Manager - Makes final trading decisions and generates orders

<img width="1042" alt="Screenshot 2025-03-22 at 6 19 07 PM" src="https://github.com/user-attachments/assets/cbae3dcf-b571-490d-b0ad-3f0f035ac0d4" />

Note: the system does not actually make any trades.

## Disclaimer

This project is for **educational and research purposes only**.

- Not intended for real trading or investment
- No investment advice or guarantees provided
- Creator assumes no liability for financial losses
- Consult a financial advisor for investment decisions
- Past performance does not indicate future results

By using this software, you agree to use it solely for learning purposes.

## Table of Contents
- [How to Install](#how-to-install)
- [Financial Data Providers](#financial-data-providers)
- [How to Run](#how-to-run)
  - [⌨️ Command Line Interface](#️-command-line-interface)
  - [🖥️ Web Application](#️-web-application)
  - [📊 V2 Quantitative Engine](#-v2-quantitative-engine)
- [Verification & Testing](#verification--testing)
- [How to Contribute](#how-to-contribute)
- [License](#license)

## How to Install

Before you can run Open Hedge, set up your environment. You need **LLM** API keys to run agents; **market data** works out of the box via Yahoo Finance without a paid data key.

### 1. Clone the Repository

```bash
git clone https://github.com/wheregmis/open-hedge.git
cd open-hedge
```

### 2. Set up API keys

Create a `.env` file in the repository root:
```bash
cp .env.example .env
```

Open and edit `.env`:

```bash
# Required for agent reasoning — set at least one LLM provider
OPENAI_API_KEY=your-openai-api-key

# Optional — premium market data from https://financialdatasets.ai/
# Omit or leave as the placeholder to use Yahoo Finance (free, default)
FINANCIAL_DATASETS_API_KEY=your-financial-datasets-api-key
```

**Important:** You must set at least one LLM API key (e.g. `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, `GROQ_API_KEY`, `ANTHROPIC_API_KEY`, or `DEEPSEEK_API_KEY`) for the hedge fund to work. Placeholder values from `.env.example` and empty keys are ignored; if the default provider has no valid key, Open Hedge auto-selects the first configured provider (OpenRouter is checked when OpenAI is absent).

You do **not** need a Financial Datasets key to fetch prices and fundamentals; Open Hedge defaults to Yahoo Finance when `FINANCIAL_DATASETS_API_KEY` is unset or still the `.env.example` placeholder.

## Financial Data Providers

Open Hedge supports two market-data sources:

| Provider | When it is used |
| :--- | :--- |
| **Yahoo Finance** (free) | Default when no valid `FINANCIAL_DATASETS_API_KEY` is configured |
| **Financial Datasets** (paid) | When a real API key is set, or when forced via `--data-provider financial-datasets` |

**Resolution order:** explicit `--data-provider` CLI flag → valid `FINANCIAL_DATASETS_API_KEY` in the environment → Yahoo Finance.

### Quickstart without a market-data API key

```bash
cp .env.example .env
# Set OPENAI_API_KEY (or another LLM key); leave FINANCIAL_DATASETS_API_KEY as placeholder

cargo run --bin backtester -- --tickers AAPL,MSFT,NVDA --start-date 2026-01-01 --end-date 2026-02-01
```

### Choose a provider (CLI)

On the backtester (and any binary using the shared CLI parser):

```bash
# Force Yahoo Finance
cargo run --bin backtester -- --ticker AAPL --data-provider yahoo-finance

# Force Financial Datasets (requires a valid FINANCIAL_DATASETS_API_KEY)
cargo run --bin backtester -- --ticker AAPL --data-provider financial-datasets
```

Accepted values: `yahoo-finance`, `financial-datasets` (underscore variants also work).

### Premium data (Financial Datasets)

Set a real key from [financialdatasets.ai](https://financialdatasets.ai/) in `.env` to unlock fuller fundamentals, insider trades, and news sentiment. Yahoo Finance covers daily prices and basic fundamentals with **derived fallbacks** for missing metrics; insider activity is empty on the Yahoo path so related agents stay neutral.

**Further reading:** [docs/data_providers.md](docs/data_providers.md) (setup and resolution) · [docs/yahoo_finance_limitations.md](docs/yahoo_finance_limitations.md) (feature matrix and backtest caveats).

The web dashboard uses the same environment-based resolution when you run flows or backtests; there is no provider toggle in the UI yet.

## How to Run

### ⌨️ Command Line Interface

You can run Open Hedge directly via the terminal. The native Rust orchestrator parses standard arguments and executes the full parallel agent workflow in seconds.

<img width="992" alt="Screenshot 2025-01-06 at 5 50 17 PM" src="https://github.com/user-attachments/assets/e8ca04bf-9989-4a7d-a8b4-34e04666663b" />

#### Run Open Hedge (Rust CLI Orchestrator)
```bash
cargo run --bin ai-hedge-fund -- --ticker AAPL,MSFT,NVDA
```

You can also specify a `--ollama` flag to run Open Hedge using local LLMs.
```bash
cargo run --bin ai-hedge-fund -- --ticker AAPL,MSFT,NVDA --ollama
```

You can optionally specify the start and end dates to make decisions over a specific time period:
```bash
cargo run --bin ai-hedge-fund -- --ticker AAPL,MSFT,NVDA --start-date 2026-01-01 --end-date 2026-02-01
```

#### Run the Backtester CLI
```bash
cargo run --bin backtester -- --ticker AAPL,MSFT,NVDA --start-date 2026-01-01 --end-date 2026-02-01
```

*(Note: Use standard double dashes `--` to pass command-line options directly to the Rust binary. The backtester supports `--ticker`, `--start-date`, `--end-date`, `--data-provider`, `--ollama`, and related flags via the shared clap parser.)*

### 🖥️ Web Application

The high-performance interactive web dashboard provides a user-friendly interface to manage and backtest your funds.

<img width="1721" alt="Screenshot 2025-06-28 at 6 41 03 PM" src="https://github.com/user-attachments/assets/b95ab696-c9f4-416c-9ad1-51feb1f5374b" />

#### 1. Start the Axum Web Server (Backend API)
```bash
cargo run --bin app-backend
```
*This starts the Axum 0.7 web server on `http://localhost:8000`. It automatically handles SQLite migrations on first boot and sets up CORS for the frontend.*

#### 2. Start the Vite React Frontend
```bash
cd app/frontend
npm install
npm run dev
```
*This launches the React dashboard at `http://localhost:5173`. You can now visually build agent graphs and stream daily simulation runs in real-time!*

### 📊 V2 Quantitative Engine

The V2 engine represents a principled quantitative trading architecture built from the ground up in native Rust, replacing famous investor personalities with robust statistical estimation pipelines.

#### 1. Run the Earnings announcement Event Study Tool
Estimate Cumulative Abnormal Returns (CARs), market model OLS regressions, and bootstrap significance statistics:
```bash
cargo run --bin v2-event-study
```

#### 2. Run the V2 backtesting runner
```bash
cargo run --bin v2-backtesting
```

## Verification & Testing

Verify the mathematical precision and memory safety of the entire Rust codebase by executing the native test suite:
```bash
cargo test
```
*Runs all 42 unit and integration test cases covering cash management, short-covering calculations, stats approximations, technical signals, and caching layers.*

## How to Contribute

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
