# 🤖 AI Hedge Fund

<p align="center">
  <a href="docs/README_CN.md"><strong>简体中文</strong></a>
</p>

<p align="center">
  <em>A proof of concept for an AI-powered multi-agent hedge fund.</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-blue.svg" />
  <img src="https://img.shields.io/badge/license-MIT-green.svg" />
  <img src="https://img.shields.io/badge/status-experimental-orange.svg" />
  <img src="https://img.shields.io/badge/AI-Multi--Agent-purple.svg" />
</p>

---

## 📌 Overview

This is a proof of concept for an AI-powered hedge fund.

The goal of this project is to explore the use of AI to make trading decisions.

> ⚠️ This project is for **educational purposes only** and is **not intended for real trading or investment**.

---

# 🧠 Multi-Agent Investment System

> **🚧 The project is evolving.** We're rebuilding it into a persistent, always-on AI hedge fund — a *fund* as a first-class entity you can backtest, paper-trade, and (opt-in) run live, with the investor agents reimagined as pluggable, backtestable "alpha models." Read the **[Vision →](VISION.md)** and the **[Roadmap →](ROADMAP.md)**.

This system employs several agents working together:

| Agent | Description |
|---|---|
| **Aswath Damodaran Agent** | The Dean of Valuation, focuses on story, numbers, and disciplined valuation |
| **Ben Graham Agent** | The godfather of value investing, only buys hidden gems with a margin of safety |
| **Bill Ackman Agent** | An activist investor, takes bold positions and pushes for change |
| **Cathie Wood Agent** | The queen of growth investing, believes in the power of innovation and disruption |
| **Charlie Munger Agent** | Warren Buffett's partner, only buys wonderful businesses at fair prices |
| **Michael Burry Agent** | The Big Short contrarian who hunts for deep value |
| **Mohnish Pabrai Agent** | The Dhandho investor, who looks for doubles at low risk |
| **Nassim Taleb Agent** | The Black Swan risk analyst, focuses on tail risk, antifragility, and asymmetric payoffs |
| **Peter Lynch Agent** | Practical investor who seeks "ten-baggers" in everyday businesses |
| **Phil Fisher Agent** | Meticulous growth investor who uses deep "scuttlebutt" research |
| **Rakesh Jhunjhunwala Agent** | The Big Bull of India |
| **Stanley Druckenmiller Agent** | Macro legend who hunts for asymmetric opportunities with growth potential |
| **Warren Buffett Agent** | The oracle of Omaha, seeks wonderful companies at a fair price |
| **Valuation Agent** | Calculates the intrinsic value of a stock and generates trading signals |
| **Sentiment Agent** | Analyzes market sentiment and generates trading signals |
| **Fundamentals Agent** | Analyzes fundamental data and generates trading signals |
| **Technicals Agent** | Analyzes technical indicators and generates trading signals |
| **Risk Manager** | Calculates risk metrics and sets position limits |
| **Portfolio Manager** | Makes final trading decisions and generates orders |

---

## 🖼️ System Preview

<p align="center">
  <img width="1042" alt="Screenshot 2025-03-22 at 6 19 07 PM" src="https://github.com/user-attachments/assets/cbae3dcf-b571-490d-b0ad-3f0f035ac0d4" />
</p>

> **Note:** The system does not actually make any trades.

---

## 🌐 Community

<p align="left">
  <a href="https://twitter.com/virattt">
    <img src="https://img.shields.io/twitter/follow/virattt?style=social" />
  </a>
</p>

---

# ⚠️ Disclaimer

This project is for **educational and research purposes only**.

- Not intended for real trading or investment
- No investment advice or guarantees provided
- Creator assumes no liability for financial losses
- Consult a financial advisor for investment decisions
- Past performance does not indicate future results

By using this software, you agree to use it solely for learning purposes.

---

# 📚 Table of Contents
- [📦 How to Install](#-how-to-install)
- [🚀 How to Run](#-how-to-run)
  - [⌨️ Command Line Interface](#️-command-line-interface)
  - [🖥️ Web Application](#️-web-application)
- [🤝 How to Contribute](#-how-to-contribute)
- [💡 Feature Requests](#-feature-requests)
- [📄 License](#-license)

---

# 📦 How to Install

Before you can run the AI Hedge Fund, you'll need to install it and set up your API keys.

These steps are common to both the full-stack web application and command line interface.

---

## 1️⃣ Clone the Repository

```bash
git clone https://github.com/virattt/ai-hedge-fund.git
cd ai-hedge-fund
```

---

## 2️⃣ Set up API Keys

Create a `.env` file for your API keys:

```bash
# Create .env file for your API keys (in the root directory)
cp .env.example .env
```

Open and edit the `.env` file to add your API keys:

```bash
# For running LLMs hosted by OpenAI (gpt-4o, gpt-4o-mini, etc.)
OPENAI_API_KEY=your-openai-api-key

# For getting financial data to power the hedge fund
FINANCIAL_DATASETS_API_KEY=your-financial-datasets-api-key
```

> **Important:** You must set at least one LLM API key  
> (`OPENAI_API_KEY`, `GROQ_API_KEY`, `ANTHROPIC_API_KEY`, or `DEEPSEEK_API_KEY`)  
> for the hedge fund to work.

---

# 🚀 How to Run

## ⌨️ Command Line Interface

You can run the AI Hedge Fund directly via terminal.

This approach offers more granular control and is useful for:

- Automation
- Scripting
- Integration workflows

---

<p align="center">
  <img width="992" alt="Screenshot 2025-01-06 at 5 50 17 PM" src="https://github.com/user-attachments/assets/e8ca04bf-9989-4a7d-a8b4-34e04666663b" />
</p>

---

## ⚡ Quick Start

### 1. Install Poetry

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

### 2. Install Dependencies

```bash
poetry install
```

---

## ▶️ Run the AI Hedge Fund

```bash
poetry run python src/main.py --ticker AAPL,MSFT,NVDA
```

---

## 🧠 Run with Local LLMs (Ollama)

```bash
poetry run python src/main.py --ticker AAPL,MSFT,NVDA --ollama
```

---

## 📅 Run with Date Range

```bash
poetry run python src/main.py \
  --ticker AAPL,MSFT,NVDA \
  --start-date 2024-01-01 \
  --end-date 2024-03-01
```

---

# 📈 Run the Backtester

```bash
poetry run python src/backtester.py --ticker AAPL,MSFT,NVDA
```

---

## 📊 Example Output

<p align="center">
  <img width="941" alt="Screenshot 2025-01-06 at 5 47 52 PM" src="https://github.com/user-attachments/assets/00e794ea-8628-44e6-9a84-8f8a31ad3b47" />
</p>

> **Note:** The `--ollama`, `--start-date`, and `--end-date` flags work for the backtester as well.

---

# 🖥️ Web Application

The new way to run the AI Hedge Fund is through our web application that provides a user-friendly interface.

This is recommended for users who prefer visual interfaces over command line tools.

📖 Please see detailed instructions on how to install and run the web application [here](https://github.com/virattt/ai-hedge-fund/tree/main/app).

---

<p align="center">
  <img width="1721" alt="Screenshot 2025-06-28 at 6 41 03 PM" src="https://github.com/user-attachments/assets/b95ab696-c9f4-416c-9ad1-51feb1f5374b" />
</p>

---

# 🤝 How to Contribute

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

> **Important:** Please keep your pull requests small and focused.  
> This will make them easier to review and merge.

---

# 💡 Feature Requests

If you have a feature request:

1. Open an [issue](https://github.com/virattt/ai-hedge-fund/issues)
2. Make sure it is tagged with `enhancement`

---

# 📄 License

This project is licensed under the MIT License.

See the `LICENSE` file for details.
