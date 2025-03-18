# AI Hedge Fund

This is a proof of concept for an AI-powered hedge fund that integrates with Alpaca Markets for real trading capabilities. The goal of this project is to explore the use of AI to make trading decisions based on multiple agents acting as financial analysts. While designed to make real trades, this system should be used for **educational** and research purposes only.

This system employs several agents working together:

1. Ben Graham Agent - The godfather of value investing, only buys hidden gems with a margin of safety
2. Bill Ackman Agent - An activist investor, takes bold positions and pushes for change
3. Cathie Wood Agent - The queen of growth investing, believes in the power of innovation and disruption
4. Charlie Munger Agent - Warren Buffett's partner, only buys wonderful businesses at fair prices
5. Stanley Druckenmiller Agent - Macro trading legend who hunts for asymmetric opportunities with explosive growth potential
6. Warren Buffett Agent - The oracle of Omaha, seeks wonderful companies at a fair price
7. Valuation Agent - Calculates the intrinsic value of a stock and generates trading signals
8. Sentiment Agent - Analyzes market sentiment and generates trading signals
9. Fundamentals Agent - Analyzes fundamental data and generates trading signals
10. Technicals Agent - Analyzes technical indicators and generates trading signals
11. Risk Manager - Calculates risk metrics, sets position limits, and prevents overtrading
12. Portfolio Manager - Makes final trading decisions and generates orders

<img width="1020" alt="Screenshot 2025-03-08 at 4 45 22 PM" src="https://github.com/user-attachments/assets/d8ab891e-a083-4fed-b514-ccc9322a3e57" />

## Key Features

- **Alpaca Markets Integration**: Execute trades directly with your Alpaca account (paper or live)
- **Transaction Awareness**: Avoids overtrading by tracking trading history and frequency
- **Sophisticated Analysis**: Combines multiple investment philosophies and perspectives
- **Multi-Agent Architecture**: Agents with specific roles collaborate on trading decisions
- **LLM-Powered**: Supports multiple AI models, including cloud-based and local options
- **Backtesting**: Test strategies across historical periods

[![Twitter Follow](https://img.shields.io/twitter/follow/virattt?style=social)](https://twitter.com/virattt)

## Disclaimer

This project is for **educational and research purposes only**.

- Not intended for real trading or investment without proper supervision
- No warranties or guarantees provided
- Past performance does not indicate future results
- Creator assumes no liability for financial losses
- Consult a financial advisor for investment decisions

By using this software, you agree to use it responsibly and understand the risks involved.

## Table of Contents

- [Setup](#setup)
- [Usage](#usage)
  - [Running the Hedge Fund](#running-the-hedge-fund)
  - [Executing Trades with Alpaca](#executing-trades-with-alpaca)
  - [Running the Backtester](#running-the-backtester)
- [Project Structure](#project-structure)
- [Roadmap for Improvement](#roadmap-for-improvement)
- [Contributing](#contributing)
- [Feature Requests](#feature-requests)
- [License](#license)

## Setup

Clone the repository:

```bash
git clone https://github.com/virattt/ai-hedge-fund.git
cd ai-hedge-fund
```

1. Install Poetry (if not already installed):

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

2. Install dependencies:

```bash
poetry install
```

3. Set up your environment variables:

```bash
# Create .env file for your API keys
cp .env.example .env
```

4. Set your API keys:

```bash
# For running LLMs hosted by openai (gpt-4o, gpt-4o-mini, etc.)
# Get your OpenAI API key from https://platform.openai.com/
OPENAI_API_KEY=your-openai-api-key

# For running LLMs hosted by groq (deepseek, llama3, etc.)
# Get your Groq API key from https://groq.com/
GROQ_API_KEY=your-groq-api-key

# For getting financial data to power the hedge fund
# Get your Financial Datasets API key from https://financialdatasets.ai/
FINANCIAL_DATASETS_API_KEY=your-financial-datasets-api-key

# Alpaca Markets API credentials
ALPACA_API_KEY=your-alpaca-api-key
ALPACA_API_SECRET=your-alpaca-api-secret
ALPACA_PAPER_TRADING=true  # Set to false for live trading
```

5. (Optional) Set up OLLAMA for local LLM support:

   - Install OLLAMA from https://ollama.ai/
   - Pull the required model:

   ```bash
   ollama pull huihui_ai/qwen2.5-1m-abliterated:14b
   ```

   - No API key is required for OLLAMA as it runs locally
   - To use different OLLAMA models, you can modify the available models in `src/llm/models.py`

**Important**: You must set at least one of `OPENAI_API_KEY`, `GROQ_API_KEY`, `ANTHROPIC_API_KEY`, `DEEPSEEK_API_KEY`, or have OLLAMA installed with the appropriate model for the hedge fund to work. If you want to use LLMs from all providers, you will need to set all API keys.

**Alpaca Setup**: For live or paper trading, you need to set up Alpaca Markets credentials:

1. Create an account at https://alpaca.markets/
2. Create an API key in your dashboard
3. Add the API key and secret to your .env file
4. Set `ALPACA_PAPER_TRADING=true` for paper trading (recommended) or `false` for live trading

Financial data for AAPL, GOOGL, MSFT, NVDA, and TSLA is free and does not require an API key.

For any other ticker, you will need to set the `FINANCIAL_DATASETS_API_KEY` in the .env file.

## Usage

### Running the Hedge Fund

```bash
poetry run python src/main.py --tickers AAPL,MSFT,NVDA
```

If you don't specify tickers, the system will analyze stocks currently in your Alpaca portfolio.

When prompted, you can select your preferred LLM model, including the local OLLAMA model if installed:

- `[ollama] qwen2.5-1m-abliterated` - Local Qwen 2.5 model (14B parameters)
- Various cloud-based models from OpenAI, Anthropic, etc.

**Example Output:**
`<img width="992" alt="Screenshot 2025-01-06 at 5 50 17 PM" src="https://github.com/user-attachments/assets/e8ca04bf-9989-4a7d-a8b4-34e04666663b" />`

### Executing Trades with Alpaca

By default, the system runs in dry-run mode, analyzing stocks but not executing trades. To execute trades via Alpaca:

```bash
poetry run python src/main.py --tickers AAPL,MSFT,NVDA --execute-trades
```

Additional options:

- `--paper-trading`: Forces paper trading mode (regardless of .env setting)
- `--show-reasoning`: Displays detailed reasoning from each agent
- `--start-date YYYY-MM-DD`: Specify analysis start date
- `--end-date YYYY-MM-DD`: Specify analysis end date

**Trade Execution Protection Features:**

- Maximum 5 trades per day across all tickers
- Waiting period of 2+ days before re-trading the same ticker
- Trade frequency monitoring to prevent excessive portfolio turnover
- Historical transaction awareness to avoid conflicting or redundant trades

### Running the Backtester

```bash
poetry run python src/backtester.py --tickers AAPL,MSFT,NVDA
```

**Example Output:**
`<img width="941" alt="Screenshot 2025-01-06 at 5 47 52 PM" src="https://github.com/user-attachments/assets/00e794ea-8628-44e6-9a84-8f8a31ad3b47" />`

You can optionally specify the start and end dates to backtest over a specific time period:

```bash
poetry run python src/backtester.py --tickers AAPL,MSFT,NVDA --start-date 2024-01-01 --end-date 2024-03-01
```

Other backtester options:

```bash
poetry run python src/backtester.py --tickers AAPL,MSFT,NVDA --initial-capital 100000 --margin-requirement 0.5
```

## Project Structure

```
ai-hedge-fund/
├── src/
│   ├── agents/                   # Agent definitions and workflow
│   │   ├── bill_ackman.py        # Bill Ackman agent
│   │   ├── fundamentals.py       # Fundamental analysis agent
│   │   ├── portfolio_manager.py  # Portfolio management agent
│   │   ├── risk_manager.py       # Risk management agent
│   │   ├── sentiment.py          # Sentiment analysis agent
│   │   ├── technicals.py         # Technical analysis agent
│   │   ├── valuation.py          # Valuation analysis agent
│   │   ├── warren_buffett.py     # Warren Buffett agent
│   │   ├── ben_graham.py         # Ben Graham agent
│   │   ├── cathie_wood.py        # Cathie Wood agent
│   │   ├── charlie_munger.py     # Charlie Munger agent
│   │   ├── stanley_druckenmiller.py # Stanley Druckenmiller agent
│   │   ├── valuation_agent.py    # Valuation agent
│   │   ├── sentiment_agent.py    # Sentiment agent
│   │   ├── fundamentals_agent.py  # Fundamentals agent
│   │   ├── technicals_agent.py   # Technicals agent
│   │   ├── risk_manager.py        # Risk manager
│   │   ├── portfolio_manager.py   # Portfolio manager
│   ├── tools/                    # Agent tools
│   │   ├── api.py                # API tools
│   ├── backtester.py             # Backtesting tools
│   ├── main.py # Main entry point
├── pyproject.toml
├── ...
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

**Important**: Please keep your pull requests small and focused.  This will make it easier to review and merge.

## Feature Requests

If you have a feature request, please open an [issue](https://github.com/virattt/ai-hedge-fund/issues) and make sure it is tagged with `enhancement`.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
