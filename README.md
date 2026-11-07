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

- A [Financial Datasets](https://financialdatasets.ai) API key, for prices, fundamentals, and earnings. Or, instead of a key, the private key of a Base wallet holding USDC: every call then pays for itself with [x402](https://docs.financialdatasets.ai/x402) (`pip install 'aihf[x402]'`; last 365 days of data, non-professional use).
- One model API key for the investor agents. Supported providers: Anthropic, OpenAI, DeepSeek, Google, xAI, Kimi, TypeSafe (Jev).

Keys exported in your shell always win over the saved file.

## How to Run

### Interactive app

```bash
aihf
```

With no arguments, this launches the interactive terminal app with paper trading,
backtesting, and investor research.

- **Paper trading** — your funds, each with a ledger of real market days and fake money. Highlight a fund to see what its next run will do; press enter to run it through the next completed session (an approval step shows the exact decision about to execute before anything trades), `s` for its full session history, `h`/`r` for the kill switch. Build a new fund from the same list: strategies, capital, cadence, tickers, and it is live. Every session is appended to a hash-chained ledger in `~/.hedge-fund/paper/<name>/`, so NAV is a track record, not a reset.
- **Backtesting** — replay a fund over history and watch its equity curve draw against its benchmark. Results are saved to `~/.hedge-fund/research/`. Fund definitions live in `~/.hedge-fund/mandates/` and carry no tickers; you pick the universe per backtest.

### Investor research

Choose **Investor research** on the home screen. Enter a ticker or company name
and press Enter to search BeliefState's company directory and available research.
Search is free and labels companies with released direct research separately.
The company directory covers SEC-registered U.S. listings. Released research can
include additional tickers.

Select a result and press Enter to load its current investor views. Each brief
includes up to three views, with authors, source links, publication dates,
qualifications, risks, catalysts, and coverage gaps. The panel shows omitted
views and links to the full cases. Fresh searches and briefs are reused in memory
for 60 seconds during the app session.

Press `Ctrl+K` in the research screen to enter your BeliefState API key, or set
`BELIEFSTATE_API_KEY` in your shell or AI Hedge Fund credentials file. Keys entered
in the app use its existing masked input and owner-only credentials file.
Loading available research uses your BeliefState account allowance or credits.
The screen shows the research cutoff. Missing coverage is labelled explicitly.
If a brief times out, keep its request ID and check account usage before loading
it again.
Press Escape to return.

### Optional research at paper approval

When a paper run has a pending decision, press `i` at approval to open research
for its pending and held tickers. You can also search for another company.
Escape returns to approval and refreshes the run preview before you decide.

For a local snapshot, set `HEDGE_FUND_PAPER_RESEARCH_FILE` to the path of a JSON
file up to 1 MiB. The approval panel then reads that file when you select a
ticker and press Enter.

Use uppercase ticker keys and timestamps with time zones. This example uses
fictional research.

```json
{
  "EXAMPLE": {
    "as_of": "2025-01-17T21:00:00Z",
    "views": [
      {
        "author": "Example Analyst",
        "published_at": "2025-01-17T15:00:00Z",
        "source_url": "https://example.com/research",
        "stance": "neutral",
        "thesis": "New customers may offset slower renewals.",
        "watch": "Check renewal rates at the next earnings release."
      }
    ]
  }
}
```

The `stance` field is optional. A missing ticker or empty `views` list is shown
as missing research. Each publication timestamp must be at or before its
research cutoff.


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
