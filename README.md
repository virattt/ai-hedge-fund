# 🚀 AI Hedge Fund: Multi-Agent Trading System

*An experimental platform simulating investment strategies of legendary investors using AI agents*

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Poetry](https://img.shields.io/endpoint?url=https://python-poetry.org/badge/v0.json)](https://python-poetry.org/)

![System Architecture Diagram](docs/system-overview.png) <!-- Add actual diagram if available -->

## 📌 Key Features
- **Legendary Investor Simulation**: 10+ AI agents modeled after iconic investment strategies
- **Multi-Paradigm Analysis**: Combines fundamental, technical, sentiment, and quantitative approaches
- **Risk Management Framework**: Dynamic position sizing and portfolio optimization
- **Backtesting Engine**: Historical performance simulation with configurable parameters
- **Multi-LLM Support**: Compatible with OpenAI, Groq, Anthropic, and local Ollama models

## ⚠️ Important Disclaimer
**This is strictly an educational/research project. NOT FINANCIAL ADVICE.**
- ❌ Not intended for real trading
- ❌ No financial guarantees provided
- ❌ Creator assumes no liability for any losses
- ✅ Always consult licensed professionals for investment decisions

*By using this software, you agree to these terms and accept full responsibility for any usage.*

## 🛠️ Setup Guide

### Prerequisites
- Python 3.10+
- Poetry package manager
- API keys for your preferred LLM providers

### Installation
1. Clone repository:
   ```bash
   git clone https://github.com/virattt/ai-hedge-fund.git
   cd ai-hedge-fund
Install Poetry (if needed):

bash
Copy
curl -sSL https://install.python-poetry.org | python3 -
Install dependencies:

bash
Copy
poetry install
Configure environment:

bash
Copy
cp .env.example .env
Edit .env with your API keys:

ini
Copy
# Required: At least one LLM provider
OPENAI_API_KEY=sk-your-key-here
GROQ_API_KEY=gsk-your-key-here

# Optional: Financial Datasets (required for non-free tickers)
FINANCIAL_DATASETS_API_KEY=fd-your-key-here
🧠 Agent Overview
Agent	Investment Style	Key Metrics
Warren Buffett	Quality + Value	ROIC, Durable Advantage
Cathie Wood	Disruptive Innovation	TAM, Adoption Rate
Michael Burry	Contrarian Value	P/B Ratio, Short Interest
Stanley Druckenmiller	Macro Trends	Yield Curves, GDP Growth
Sentiment Analyst	Market Psychology	News Sentiment, Social Volume
Risk Manager	Portfolio Protection	VaR, Maximum Drawdown
See full agent documentation <!-- Link to detailed agent docs if available -->

🚦 Usage
Live Simulation Mode
bash
Copy
poetry run python src/main.py \
  --ticker AAPL,MSFT,NVDA \
  --start-date 2024-01-01 \
  --end-date 2024-03-01 \
  --show-reasoning
Flags:

--ollama: Use local LLMs via Ollama

--risk-level [1-5]: Aggressiveness (1=conservative, 5=aggressive)

--max-positions: Maximum simultaneous holdings

Backtesting Mode
bash
Copy
poetry run python src/backtester.py \
  --ticker TSLA,AMD \
  --strategy momentum \
  --benchmark SPY
Supported Strategies:

value: Ben Graham-style margin of safety

growth: Cathie Wood innovation focus

momentum: Technical trend following

hybrid: Combined approach

📂 Project Structure
Copy
ai-hedge-fund/
├── docs/               # Documentation & research
├── notebooks/          # Analysis & experiments
├── src/
│   ├── agents/         # Investor personality modules
│   ├── analytics/      # Financial metrics calculators
│   ├── data/           # Market data handlers
│   ├── llm/            # Language model integration
│   ├── portfolio/      # Allocation algorithms
│   └── simulation/     # Backtesting engine
└── tests/              # Unit & integration tests
🤝 Contributing
We welcome contributions! Please follow these steps:

Open an issue to discuss proposed changes

Fork the repository

Create a feature branch (git checkout -b feature/amazing-idea)

Commit changes (git commit -m 'Add amazing feature')

Push to branch (git push origin feature/amazing-idea)

Open a Pull Request

Development Tips:

bash
Copy
# Run test suite
poetry run pytest tests/

# Format code
poetry run black src/ tests/

# Generate documentation
poetry run mkdocs serve
🌟 Feature Roadmap
Real-time data streaming integration

Ensemble prediction models

Transaction cost modeling

Regulatory compliance checks

Interactive web interface

📜 License
MIT License - See LICENSE for full text
