# AI Hedge Fund

This is a proof of concept for an AI-powered hedge fund. The goal of this project is to explore the use of AI to make trading decisions. This project is for **educational** purposes only and is not intended for real trading or investment.

This system employs several agents working together:

1. Bill Ackman Agent - Uses Bill Ackman's principles to generate trading signals
2. Warren Buffett Agent - Uses Warren Buffett's principles to generate trading signals
3. Valuation Agent - Calculates the intrinsic value of a stock and generates trading signals
4. Sentiment Agent - Analyzes market sentiment and generates trading signals
5. Fundamentals Agent - Analyzes fundamental data and generates trading signals
6. Technicals Agent - Analyzes technical indicators and generates trading signals
7. Risk Manager - Calculates risk metrics and sets position limits
8. Portfolio Manager - Makes final trading decisions and generates orders

<img width="1117" alt="Screenshot 2025-02-09 at 11 26 14 AM" src="https://github.com/user-attachments/assets/16509cc2-4b64-4c67-8de6-00d224893d58" />

**Note**: the system simulates trading decisions, it does not actually trade.

[![Twitter Follow](https://img.shields.io/twitter/follow/virattt?style=social)](https://twitter.com/virattt)

## Disclaimer

This project is for **educational and research purposes only**.

- Not intended for real trading or investment
- No warranties or guarantees provided
- Past performance does not indicate future results
- Creator assumes no liability for financial losses
- Consult a financial advisor for investment decisions

By using this software, you agree to use it solely for learning purposes.

## Table of Contents

- [Setup](#setup)
- [Usage](#usage)
  - [Running the Hedge Fund](#running-the-hedge-fund)
  - [Running the Backtester](#running-the-backtester)
- [Project Structure](#project-structure)
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
```

**Important**: You must set `OPENAI_API_KEY`, `GROQ_API_KEY`, or `ANTHROPIC_API_KEY` for the hedge fund to work. If you want to use LLMs from all providers, you will need to set all API keys.

Financial data for AAPL, GOOGL, MSFT, NVDA, and TSLA is free and does not require an API key.

For any other ticker, you will need to set the `FINANCIAL_DATASETS_API_KEY` in the .env file.

## Usage

### CLI Arguments

The hedge fund supports the following command line arguments:

| Argument               | Description                                                           | Default                  | Example                                                                                                |
| ---------------------- | --------------------------------------------------------------------- | ------------------------ | ------------------------------------------------------------------------------------------------------ |
| `--tickers`            | Comma-separated list of stock ticker symbols                          | Required                 | `--tickers AAPL,MSFT,NVDA`                                                                             |
| `--analysts`           | Comma-separated list of analysts to use (skips interactive selection) | Interactive prompt       | `--analysts all` or `--analysts technical_analyst,fundamentals_analyst`                                |
| `--model`              | LLM model name (skips interactive selection)                          | Interactive prompt       | `--model gpt-4`                                                                                        |
| `--model-provider`     | Model provider (skips interactive selection)                          | Interactive prompt       | `--model-provider OpenAI`                                                                              |
| `--initial-cash`       | Initial cash position                                                 | 100000.0                 | `--initial-cash 500000`                                                                                |
| `--initial-positions`  | JSON string of initial positions                                      | Empty positions          | `--initial-positions '{"AAPL":{"long":100,"short":0,"long_cost_basis":150.0,"short_cost_basis":0.0}}'` |
| `--margin-requirement` | Initial margin requirement                                            | 0.0                      | `--margin-requirement 0.5`                                                                             |
| `--start-date`         | Start date in YYYY-MM-DD format                                       | 3 months before end date | `--start-date 2024-01-01`                                                                              |
| `--end-date`           | End date in YYYY-MM-DD format                                         | Today                    | `--end-date 2024-03-01`                                                                                |
| `--show-reasoning`     | Show reasoning from each agent                                        | False                    | `--show-reasoning`                                                                                     |
| `--show-agent-graph`   | Generate a visualization of the agent workflow                        | False                    | `--show-agent-graph`                                                                                   |

Available analysts:

- Use `--analysts all` to select all analysts, or specify individual analysts:
  - `technical_analyst`: Technical analysis
  - `fundamentals_analyst`: Fundamental analysis
  - `sentiment_analyst`: Sentiment analysis
  - `valuation_analyst`: Valuation analysis
  - `warren_buffett`: Warren Buffett's principles
  - `bill_ackman`: Bill Ackman's principles

Available model providers:

- `OpenAI`: Requires OPENAI_API_KEY
- `Groq`: Requires GROQ_API_KEY
- `Anthropic`: Requires ANTHROPIC_API_KEY

Available models by provider:

OpenAI models:

- `gpt-4o`: GPT-4 Optimized
- `gpt-4o-mini`: GPT-4 Mini Optimized
- `o1`: OpenAI One
- `o3-mini`: OpenAI Three Mini

Groq models:

- `deepseek-r1-distill-llama-70b`: DeepSeek R1 70B
- `llama-3.3-70b-versatile`: Llama 3.3 70B

Anthropic models:

- `claude-3-5-haiku-latest`: Claude 3.5 Haiku
- `claude-3-5-sonnet-latest`: Claude 3.5 Sonnet
- `claude-3-opus-latest`: Claude 3 Opus

### Running the Hedge Fund

```bash
poetry run python src/main.py --ticker AAPL,MSFT,NVDA
```

**Example Output:**
<img width="992" alt="Screenshot 2025-01-06 at 5 50 17 PM" src="https://github.com/user-attachments/assets/e8ca04bf-9989-4a7d-a8b4-34e04666663b" />

You can also specify a `--show-reasoning` flag to print the reasoning of each agent to the console.

```bash
poetry run python src/main.py --ticker AAPL,MSFT,NVDA --show-reasoning
```

You can optionally specify the start and end dates to make decisions for a specific time period.

```bash
poetry run python src/main.py --ticker AAPL,MSFT,NVDA --start-date 2024-01-01 --end-date 2024-03-01
```

### Running the Backtester

```bash
poetry run python src/backtester.py --ticker AAPL,MSFT,NVDA
```

**Example Output:**
<img width="941" alt="Screenshot 2025-01-06 at 5 47 52 PM" src="https://github.com/user-attachments/assets/00e794ea-8628-44e6-9a84-8f8a31ad3b47" />

You can optionally specify the start and end dates to backtest over a specific time period.

```bash
poetry run python src/backtester.py --ticker AAPL,MSFT,NVDA --start-date 2024-01-01 --end-date 2024-03-01
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

**Important**: Please keep your pull requests small and focused. This will make it easier to review and merge.

## Feature Requests

If you have a feature request, please open an [issue](https://github.com/virattt/ai-hedge-fund/issues) and make sure it is tagged with `enhancement`.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
