# AI Hedge Fund

[![Code of Conduct](https://img.shields.io/badge/Contributor%20Covenant-2.1-4baaaa.svg)](code_of_conduct.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE.md)
[![Contributing](https://img.shields.io/badge/Contributing-Guidelines-green.svg)](CONTRIBUTING.md)

An AI-powered hedge fund that uses multiple agents to make trading decisions. The system employs several specialized agents working together:

1. Market Data Agent - Gathers and preprocesses market data
2. Quantitative Agent - Analyzes technical indicators and generates trading signals
3. Risk Management Agent - Evaluates portfolio risk and sets position limits
4. Portfolio Management Agent - Makes final trading decisions and generates orders
   
<img width="1014" alt="Screenshot 2024-11-29 at 1 24 40 PM" src="https://github.com/user-attachments/assets/3c40913a-970e-4ee0-9488-027318a8e189">

## Features

- Multi-agent architecture for sophisticated trading decisions
- Technical analysis using MACD, RSI, Bollinger Bands, and OBV
- Risk management with position sizing recommendations
- Portfolio management with automated trading decisions
- Backtesting capabilities with performance analytics
- Support for multiple stock tickers

## Prerequisites

- Python 3.9+
- Poetry

## Setup

Clone the repository:
```bash
git clone https://github.com/your-repo/ai-hedge-fund.git
cd ai-hedge-fund
```

### Using Poetry

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
cp .env.example .env
export OPENAI_API_KEY='your-api-key-here'
export FINANCIAL_DATASETS_API_KEY='your-api-key-here'
```

## Usage

### Running the Hedge Fund

```bash
poetry run hedge-fund --ticker AAPL --start-date 2024-01-01 --end-date 2024-03-01
```
Or, in vscode go to the debug tab and launch the Hedge fund debug config to run in debug mode. You can modify the args in the launch.json file on the .vscode folder.

**Example Output:**
```json
{
  "action": "buy",
  "quantity": 50000,
}
```

### Running the Backtester

```bash
poetry run backtester --ticker AAPL --start-date 2024-01-01 --end-date 2024-03-01
```
Or in vscode go to the debug tab and launch the Bakctester debug config to run in debug mode. You can modify the args in the launch.json file on the .vscode folder.

**Example Output:**
```
Starting backtest...
Date         Ticker Action Quantity    Price         Cash    Stock  Total Value
----------------------------------------------------------------------
2024-01-01   AAPL   buy       519.0   192.53        76.93    519.0    100000.00
2024-01-02   AAPL   hold          0   185.64        76.93    519.0     96424.09
2024-01-03   AAPL   hold          0   184.25        76.93    519.0     95702.68
2024-01-04   AAPL   hold          0   181.91        76.93    519.0     94488.22
2024-01-05   AAPL   hold          0   181.18        76.93    519.0     94109.35
2024-01-08   AAPL   sell        519   185.56     96382.57      0.0     96382.57
2024-01-09   AAPL   buy       520.0   185.14       109.77    520.0     96382.57
```

## Project Structure 
```
ai-hedge-fund/
├── src/
│   ├── agents.py # Main agent definitions and workflow
│   ├── backtester.py # Backtesting functionality
│   ├── tools.py # Technical analysis tools
├── pyproject.toml # Poetry configuration
├── .env.example # Environment variables
└── README.md # Documentation
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
