# AI Hedge Fund

This is a proof of concept for an AI-powered hedge fund. The goal of this project is to explore the use of AI to make trading decisions. This project is for **educational** purposes only and is not intended for real trading or investment.

<img width="2400" height="1460" alt="image" src="https://github.com/user-attachments/assets/e3985623-c226-4c1a-a587-e03fb4eca31e" />


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

## How the investor agents work

**Training.** The five investor agents are prompt-based personas, not custom-trained
or fine-tuned models of those investors. Each defines a system prompt for the shared
[`LLMAgent`](hedge_fund/signals/llm_agent.py), which calls the
[selected provider model](hedge_fund/llm/client.py). The provider supplies the underlying
pretrained model; this repository does not document its training corpus. The personas
are stylized approximations of public investment philosophies, not the actual
individuals or endorsements.

**Inputs.** All five use the same point-in-time
[`FundamentalsSnapshot`](hedge_fund/features/snapshot.py): financial metrics from
Financial Datasets filed by the analysis date, including earnings, growth, margins,
leverage, and valuation, plus derived summaries. These are inputs for analysis, not
training data. Minute funds also add [intraday context](hedge_fund/features/intraday.py):
price-move bands, earnings releases, and news headlines (headlines are withheld in
blind backtests).

**Intended focus.** The system prompts emphasize different analytical lenses, not
proven areas of outperformance:

| Agent (system prompt) | Focus |
|-----------------------|-------|
| [Warren Buffett](hedge_fund/signals/buffett.py) | Durable business quality, financial strength, and a fair price |
| [Charlie Munger](hedge_fund/signals/munger.py) | Consistent quality, capital allocation, and avoiding failure risks |
| [Benjamin Graham](hedge_fund/signals/graham.py) | Margin of safety, balance-sheet strength, and earnings stability |
| [Peter Lynch](hedge_fund/signals/lynch.py) | Growth at a reasonable price, comparing earnings growth with valuation |
| [Stanley Druckenmiller](hedge_fund/signals/druckenmiller.py) | Fundamental inflections in growth, margins, and earnings, rather than a full macro strategy |

Agents return a directional signal, confidence, and thesis; deterministic portfolio
and risk code handles position sizing and limits. The separate
[PEAD model](hedge_fund/signals/pead.py) is rule-based, using earnings surprises
without an LLM or a training step.

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
- One model API key for the investor agents. Supported providers: Anthropic, OpenAI, DeepSeek, Google, xAI, Kimi, TypeSafe (Jev).

Keys exported in your shell always win over the saved file.

## How to Run

### Interactive app

```bash
aihf
```

With no arguments, this launches the interactive terminal app. It has two modes:

- **Paper trading** — your funds, each with a ledger of real market days and fake money. Highlight a fund to see what its next run will do; press enter to run it through the next completed session (an approval step shows the exact decision about to execute before anything trades), `s` for its full session history, `h`/`r` for the kill switch. Build a new fund from the same list: strategies, capital, cadence, tickers, and it is live. Every session is appended to a hash-chained ledger in `~/.hedge-fund/paper/<name>/`, so NAV is a track record, not a reset.
- **Backtesting** — replay a fund over history and watch its equity curve draw against its benchmark. Results are saved to `~/.hedge-fund/research/`. Fund definitions live in `~/.hedge-fund/mandates/` and carry no tickers; you pick the universe per backtest.



## Development

```bash
git clone https://github.com/virattt/ai-hedge-fund.git
cd ai-hedge-fund
poetry install
poetry run aihf
poetry run pytest hedge_fund
```

## How to Contribute

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
