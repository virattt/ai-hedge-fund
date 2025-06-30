# AI Hedge Fund

This is a proof of concept for an AI-powered hedge fund.  The goal of this project is to explore the use of AI to make trading decisions.  This project is for **educational** purposes only and is not intended for real trading or investment.

This system employs several agents working together:

1. Aswath Damodaran Agent - The Dean of Valuation, focuses on story, numbers, and disciplined valuation
2. Ben Graham Agent - The godfather of value investing, only buys hidden gems with a margin of safety
3. Bill Ackman Agent - An activist investor, takes bold positions and pushes for change
4. Cathie Wood Agent - The queen of growth investing, believes in the power of innovation and disruption
5. Charlie Munger Agent - Warren Buffett's partner, only buys wonderful businesses at fair prices
6. Michael Burry Agent - The Big Short contrarian who hunts for deep value
7. Peter Lynch Agent - Practical investor who seeks "ten-baggers" in everyday businesses
8. Phil Fisher Agent - Meticulous growth investor who uses deep "scuttlebutt" research 
9. Rakesh Jhunjhunwala Agent - The Big Bull of India
10. Stanley Druckenmiller Agent - Macro legend who hunts for asymmetric opportunities with growth potential
11. Warren Buffett Agent - The oracle of Omaha, seeks wonderful companies at a fair price
12. Valuation Agent - Calculates the intrinsic value of a stock and generates trading signals
13. Sentiment Agent - Analyzes market sentiment and generates trading signals
14. Fundamentals Agent - Analyzes fundamental data and generates trading signals
15. Technicals Agent - Analyzes technical indicators and generates trading signals
16. Risk Manager - Calculates risk metrics and sets position limits
17. Portfolio Manager - Makes final trading decisions and generates orders

<img width="1042" alt="Screenshot 2025-03-22 at 6 19 07 PM" src="https://github.com/user-attachments/assets/cbae3dcf-b571-490d-b0ad-3f0f035ac0d4" />

As of June 2025, there are **two ways** to run the AI Hedge Fund:

1. **⌨️ Command Line Interface** - Terminal-based approach
2. **🖥️ Web Application (NEW!)** - User-friendly web interface

**Note**: the system simulates trading decisions, it does not actually trade.

[![Twitter Follow](https://img.shields.io/twitter/follow/virattt?style=social)](https://twitter.com/virattt)

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
- [How to Run](#how-to-run)
  - [⌨️ Command Line Interface](#️-command-line-interface)
  - [🖥️ Web Application (NEW!)](#️-web-application)
- [Contributing](#contributing)
- [Feature Requests](#feature-requests)
- [License](#license)

## How to Install

Before you can run the AI Hedge Fund, you'll need to install it and set up your API keys. These steps are common to both the full-stack web application and command line interface.

### 1. Clone the Repository

```bash
git clone https://github.com/virattt/ai-hedge-fund.git
cd ai-hedge-fund
```

### 2. Set Up Your API Keys

Create a `.env` file for your API keys:
```bash
# Create .env file for your API keys (in the root directory)
cp .env.example .env
```

Open and edit the `.env` file to add your API keys:
```bash
# For running LLMs hosted by openai (gpt-4o, gpt-4o-mini, etc.)
OPENAI_API_KEY=your-openai-api-key

# For running LLMs hosted by groq (deepseek, llama3, etc.)
GROQ_API_KEY=your-groq-api-key

# For getting financial data to power the hedge fund
FINANCIAL_DATASETS_API_KEY=your-financial-datasets-api-key
```

**Important**: You must set at least one LLM API key (`OPENAI_API_KEY`, `GROQ_API_KEY`, `ANTHROPIC_API_KEY`, or `DEEPSEEK_API_KEY`) for the hedge fund to work. 

**Financial Data**: Data for AAPL, GOOGL, MSFT, NVDA, and TSLA is free and does not require an API key. For any other ticker, you will need to set the `FINANCIAL_DATASETS_API_KEY` in the .env file.

## How to Run

### ⌨️ Command Line Interface

For users who prefer working with command line tools, you can run the AI Hedge Fund directly via terminal. This approach offers more granular control and is useful for automation, scripting, and integration purposes.

<img width="992" alt="Screenshot 2025-01-06 at 5 50 17 PM" src="https://github.com/user-attachments/assets/e8ca04bf-9989-4a7d-a8b4-34e04666663b" />

Choose one of the following installation methods:

#### Using Poetry

1. Install Poetry (if not already installed):
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

2. Install dependencies:
```bash
poetry install
```

#### Using Docker

1. Make sure you have Docker installed on your system. If not, you can download it from [Docker's official website](https://www.docker.com/get-started).

2. Navigate to the docker directory:
```bash
cd docker
```

3. Build the Docker image:
```bash
# On Linux/Mac:
./run.sh build

# On Windows:
run.bat build
```

#### Running the AI Hedge Fund (with Poetry)
```bash
poetry run python src/main.py --ticker AAPL,MSFT,NVDA
```

#### Running the AI Hedge Fund (with Docker)
```bash
# Navigate to the docker directory first
cd docker

# On Linux/Mac:
./run.sh --ticker AAPL,MSFT,NVDA main

# On Windows:
run.bat --ticker AAPL,MSFT,NVDA main
```

You can also specify a `--ollama` flag to run the AI hedge fund using local LLMs.

```bash
# With Poetry:
poetry run python src/main.py --ticker AAPL,MSFT,NVDA --ollama

# With Docker (from docker/ directory):
# On Linux/Mac:
./run.sh --ticker AAPL,MSFT,NVDA --ollama main

# On Windows:
run.bat --ticker AAPL,MSFT,NVDA --ollama main
```

You can also specify a `--show-reasoning` flag to print the reasoning of each agent to the console.

```bash
# With Poetry:
poetry run python src/main.py --ticker AAPL,MSFT,NVDA --show-reasoning

# With Docker (from docker/ directory):
# On Linux/Mac:
./run.sh --ticker AAPL,MSFT,NVDA --show-reasoning main

# On Windows:
run.bat --ticker AAPL,MSFT,NVDA --show-reasoning main
```

You can optionally specify the start and end dates to make decisions for a specific time period.

```bash
# With Poetry:
poetry run python src/main.py --ticker AAPL,MSFT,NVDA --start-date 2024-01-01 --end-date 2024-03-01 

# With Docker (from docker/ directory):
# On Linux/Mac:
./run.sh --ticker AAPL,MSFT,NVDA --start-date 2024-01-01 --end-date 2024-03-01 main

# On Windows:
run.bat --ticker AAPL,MSFT,NVDA --start-date 2024-01-01 --end-date 2024-03-01 main
```

#### Running the Backtester (with Poetry)
```bash
poetry run python src/backtester.py --ticker AAPL,MSFT,NVDA
```

#### Running the Backtester (with Docker)
```bash
# Navigate to the docker directory first
cd docker

# On Linux/Mac:
./run.sh --ticker AAPL,MSFT,NVDA backtest

# On Windows:
run.bat --ticker AAPL,MSFT,NVDA backtest
```

**Example Output:**
<img width="941" alt="Screenshot 2025-01-06 at 5 47 52 PM" src="https://github.com/user-attachments/assets/00e794ea-8628-44e6-9a84-8f8a31ad3b47" />


You can optionally specify the start and end dates to backtest over a specific time period.

```bash
# With Poetry:
poetry run python src/backtester.py --ticker AAPL,MSFT,NVDA --start-date 2024-01-01 --end-date 2024-03-01

# With Docker (from docker/ directory):
# On Linux/Mac:
./run.sh --ticker AAPL,MSFT,NVDA --start-date 2024-01-01 --end-date 2024-03-01 backtest

# On Windows:
run.bat --ticker AAPL,MSFT,NVDA --start-date 2024-01-01 --end-date 2024-03-01 backtest
```

You can also specify a `--ollama` flag to run the backtester using local LLMs.
```bash
# With Poetry:
poetry run python src/backtester.py --ticker AAPL,MSFT,NVDA --ollama

# With Docker (from docker/ directory):
# On Linux/Mac:
./run.sh --ticker AAPL,MSFT,NVDA --ollama backtest

# On Windows:
run.bat --ticker AAPL,MSFT,NVDA --ollama backtest
```

### 🖥️ Web Application

The new way to run the AI Hedge Fund is through our web application that provides a user-friendly interface. **This is recommended for most users, especially those who prefer visual interfaces over command line tools.**

<img width="1721" alt="Screenshot 2025-06-28 at 6 41 03 PM" src="https://github.com/user-attachments/assets/b95ab696-c9f4-416c-9ad1-51feb1f5374b" />

#### For Mac/Linux:
```bash
cd app && ./run.sh
```

If you get a "permission denied" error, run this first:
```bash
cd app && chmod +x run.sh && ./run.sh
```

#### For Windows:
```bash
# Go to /app directory
cd app

# Run the app
\.run.bat
```

**That's it!** These scripts will:
1. Check for required dependencies (Node.js, Python, Poetry)
2. Install all dependencies automatically  
3. Start both frontend and backend services
4. **Automatically open your web browser** to the application


#### Detailed Setup Instructions

For detailed setup instructions, troubleshooting, and advanced configuration options, see:
- [Full-Stack App Documentation](./app/README.md)
- [Frontend Documentation](./app/frontend/README.md)  
- [Backend Documentation](./app/backend/README.md)


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
