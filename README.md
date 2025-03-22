# SmartHedge

This is an enhanced version of the AI-powered hedge fund proof of concept. The goal of this project is to explore the use of AI to make trading decisions with an interactive web interface. This project is for **educational** purposes only and is not intended for real trading or investment.

This system employs several agents working together:

1. Ben Graham Agent - The godfather of value investing, only buys hidden gems with a margin of safety
2. Bill Ackman Agent - An activist investors, takes bold positions and pushes for change
3. Cathie Wood Agent - The queen of growth investing, believes in the power of innovation and disruption
4. Charlie Munger Agent - Warren Buffett's partner, only buys wonderful businesses at fair prices
5. Phil Fisher Agent - Legendary growth investor who mastered scuttlebutt analysis
6. Stanley Druckenmiller Agent - Macro legend who hunts for asymmetric opportunities with growth potential
7. Warren Buffett Agent - The oracle of Omaha, seeks wonderful companies at a fair price
8. Valuation Agent - Calculates the intrinsic value of a stock and generates trading signals
9. Sentiment Agent - Analyzes market sentiment and generates trading signals
10. Fundamentals Agent - Analyzes fundamental data and generates trading signals
11. Technicals Agent - Analyzes technical indicators and generates trading signals
12. Risk Manager - Calculates risk metrics and sets position limits
13. Portfolio Manager - Makes final trading decisions and generates orders

<img width="1020" alt="Screenshot 2025-03-08 at 4 45 22 PM" src="https://github.com/user-attachments/assets/d8ab891e-a083-4fed-b514-ccc9322a3e57" />

**Note**: the system simulates trading decisions, it does not actually trade.

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
  - [Running the Web App](#running-the-web-app)
  - [Running the Hedge Fund CLI](#running-the-hedge-fund-cli)
  - [Running the Backtester CLI](#running-the-backtester-cli)
- [Project Structure](#project-structure)
- [Contributing](#contributing)
- [Feature Requests](#feature-requests)
- [License](#license)

## Setup

Clone the repository:
```bash
git clone https://github.com/mr-jestin-roy/SmartHedge.git
cd SmartHedge
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

# For running LLMs hosted by Anthropic (claude-3-opus, etc.)
# Get your Anthropic API key from https://anthropic.com/
ANTHROPIC_API_KEY=your-anthropic-api-key

# For running LLMs hosted by DeepSeek
# Get your DeepSeek API key from https://deepseek.com/
DEEPSEEK_API_KEY=your-deepseek-api-key

# For getting financial data to power the hedge fund
# Get your Financial Datasets API key from https://financialdatasets.ai/
FINANCIAL_DATASETS_API_KEY=your-financial-datasets-api-key
```

**Important**: You must set at least one of `OPENAI_API_KEY`, `GROQ_API_KEY`, `ANTHROPIC_API_KEY`, or `DEEPSEEK_API_KEY` for the hedge fund to work. If you want to use LLMs from all providers, you will need to set all API keys.

Financial data for AAPL, GOOGL, MSFT, NVDA, and TSLA is free and does not require an API key.

For any other ticker, you will need to set the `FINANCIAL_DATASETS_API_KEY` in the .env file.

## Usage

### Running the Web App

The SmartHedge comes with an interactive Streamlit web interface that allows you to:
- Configure and run backtests with different parameters
- Visualize portfolio performance
- Analyze trading decisions and signals
- Compare different analysts' perspectives

To run the web app:

```bash
# Using the provided script
./run_app.sh

# Or directly with Poetry
poetry run streamlit run app.py
```

The web app will be available at http://localhost:8501 in your browser.

### Running the Hedge Fund CLI

For command-line usage:

```bash
poetry run python src/main.py --ticker AAPL,MSFT,NVDA
```

**Example Output:**
<img width="992" alt="Screenshot 2025-01-06 at 5 50 17 PM" src="https://github.com/user-attachments/assets/e8ca04bf-9989-4a7d-a8b4-34e04666663b" />

You can also specify a `--show-reasoning` flag to print the reasoning of each agent to the console.

```bash
poetry run python src/main.py --ticker AAPL,MSFT,NVDA --show-reasoning
```
You can optionally specify the start and end dates to make decisions for a specific time period.

```bash
poetry run python src/main.py --ticker AAPL,MSFT,NVDA --start-date 2024-01-01 --end-date 2024-03-01
```

### Running the Backtester CLI

```bash
poetry run python src/backtester.py --ticker AAPL,MSFT,NVDA
```

**Example Output:**
<img width="941" alt="Screenshot 2025-01-06 at 5 47 52 PM" src="https://github.com/user-attachments/assets/00e794ea-8628-44e6-9a84-8f8a31ad3b47" />

You can optionally specify the start and end dates to backtest over a specific time period.

```bash
poetry run python src/backtester.py --ticker AAPL,MSFT,NVDA --start-date 2024-01-01 --end-date 2024-03-01
```

## Project Structure
```
SmartHedge/
├── app.py                      # Streamlit web application
├── run_app.sh                  # Script to run the web app
├── src/
│   ├── agents/                 # Agent definitions and workflow
│   │   ├── bill_ackman.py      # Bill Ackman agent
│   │   ├── fundamentals.py     # Fundamental analysis agent
│   │   ├── portfolio_manager.py # Portfolio management agent
│   │   ├── risk_manager.py     # Risk management agent
│   │   ├── sentiment.py        # Sentiment analysis agent
│   │   ├── technicals.py       # Technical analysis agent
│   │   ├── valuation.py        # Valuation analysis agent
│   │   ├── warren_buffett.py   # Warren Buffett agent
│   │   ├── ben_graham.py        # Ben Graham agent
│   │   ├── cathie_wood.py       # Cathie Wood agent
│   │   ├── charlie_munger.py    # Charlie Munger agent
│   │   ├── stanley_druckenmiller.py # Stanley Druckenmiller agent
│   │   ├── warren_buffett.py    # Warren Buffett agent
│   │   ├── valuation.py         # Valuation analysis agent
│   │   ├── sentiment.py         # Sentiment analysis agent
│   │   ├── fundamentals.py      # Fundamental analysis agent
│   │   ├── technicals.py        # Technical analysis agent
│   │   ├── risk_manager.py      # Risk management agent
│   │   ├── portfolio_manager.py  # Portfolio management agent
│   │   ├── ben_graham.py         # Ben Graham agent
│   │   ├── cathie_wood.py         # Cathie Wood agent
│   │   ├── charlie_munger.py      # Charlie Munger agent
│   │   ├── stanley_druckenmiller.py # Stanley Druckenmiller agent
│   │   ├── warren_buffett.py      # Warren Buffett agent
│   │   └── valuation.py           # Valuation analysis agent
│   ├── data/                   # Data handling and processing
│   ├── graph/                  # Visualization components
│   ├── llm/                    # LLM integration and models
│   ├── tools/                  # Agent tools
│   │   ├── api.py              # API tools
│   ├── utils/                  # Utility functions
│   ├── backtester.py           # Backtesting engine
│   ├── main.py                 # Main CLI entry point
├── backtester.py               # CLI backtester entry point
├── pyproject.toml              # Poetry configuration
├── .env.example                # Example environment variables
├── LICENSE                     # MIT License
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.
