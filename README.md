# AI Hedge Fund

This is a proof of concept for an AI-powered hedge fund. The goal of this project is to explore the use of AI to make trading decisions. This project is for **educational** purposes only and is not intended for real trading or investment.

> **🚧 The project is evolving.** We're rebuilding it into a persistent, always-on AI hedge fund — a *fund* as a first-class entity you can backtest, paper-trade, and (opt-in) run live, with the investor agents reimagined as pluggable, backtestable "alpha models." Read the **[Vision →](VISION.md)** and the **[Roadmap →](ROADMAP.md)**.

Note: the system does not actually make any trades.

[![Twitter Follow](https://img.shields.io/twitter/follow/virattt?style=social)](https://twitter.com/virattt)

## Disclaimer

This project is for **educational and research purposes only**.

- Not intended for real trading or investment
- No investment advice or guarantees provided
- Creator assumes no liability for financial losses
- Consult a financial advisor for investment decisions
- Past performance does not indicate future results

By using this software, you agree to use it solely for learning purposes.

## How to Install

```bash
pipx install aihf
```

(or `uv tool install aihf`, or `pip install aihf` into an environment of your choice)

Then run it from anywhere:

```bash
aihf
```

### API keys

The app asks for keys the first time it needs them and saves them to `~/.hedge-fund/.env` — nothing to configure up front. It needs:

- A [Financial Datasets](https://financialdatasets.ai) API key, for prices, fundamentals, and earnings.
- One model API key for the investor agents. Supported providers: Anthropic, OpenAI, DeepSeek, Google, xAI, Kimi, TypeSafe (Jev). Or run locally with Ollama — no key; model ids are Ollama tags (`llama3.1`, `qwen2.5`, or `ollama:<tag>` for anything you have pulled).

Keys exported in your shell always win over the saved file.

To point OpenAI-compatible models at a custom host (Groq, a local proxy, ...), set `OPENAI_BASE_URL` or the older `OPENAI_API_BASE` alias. Moonshot/Kimi already uses `MOONSHOT_BASE_URL`. Ollama uses `OLLAMA_BASE_URL` (default `http://127.0.0.1:11434`). Bound hung calls with `LLM_REQUEST_TIMEOUT` (seconds; default 60). A missing Ollama daemon fails inside that timeout instead of hanging.

## How to Run

### Interactive app

```bash
aihf
```

With no arguments, this launches the interactive terminal app. Build a fund — pick stocks, strategies, rebalance cadence — or backtest a saved fund and watch its equity curve draw against its benchmark. Funds you build are saved as mandate files in `~/.hedge-fund/mandates/`.

### Non-interactive

Run one live-clock paper cycle from a mandate file (`PaperBroker`, fills at mark, no live venue). `--paper` is the explicit flag; omitting it is the same path. If this mandate has a prior cycle receipt, the run opens that ending book so cash, positions, and NAV carry forward; otherwise it opens at the mandate's capital. A corrupt or incompatible receipt fails the run. The full cycle record prints to stdout as JSON; a short human summary goes to stderr; the receipt is saved next to the mandate:

```bash
aihf ~/.hedge-fund/mandates/example.yaml --tickers AAPL,MSFT
aihf ~/.hedge-fund/mandates/example.yaml --tickers AAPL,MSFT --paper
```

Run the same mandate with Jev after configuring `TYPESAFE_API_KEY`:

```bash
aihf ~/.hedge-fund/mandates/example.yaml --tickers AAPL,MSFT --model jev-1.13.0
```

Backtest the mandate over history at its rebalance cadence (`SimBroker`, not the paper venue):

```bash
aihf ~/.hedge-fund/mandates/example.yaml --tickers AAPL,MSFT --backtest
```

A mandate is the desk — strategies, staff, risk, capital, cadence — and never names tickers; `--tickers` says what to point it at for this run.

## Development

This fork lives at [bugman666/ai-hedge-fund](https://github.com/bugman666/ai-hedge-fund). See [CONTRIBUTING.md](CONTRIBUTING.md) for the first-test / first-backtest path.

```bash
git clone https://github.com/bugman666/ai-hedge-fund.git
cd ai-hedge-fund
poetry install
poetry run pytest hedge_fund   # offline: no API keys required
poetry run aihf
```

Live Financial Datasets tests skip unless `FINANCIAL_DATASETS_API_KEY` is set.

## How to Contribute

See [CONTRIBUTING.md](CONTRIBUTING.md). In short:

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
