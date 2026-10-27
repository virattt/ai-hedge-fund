"""The AI Hedge Fund interactive app — a Textual TUI.

v2's interactive experience: `python -m hedge_fund.tui`, or `python -m hedge_fund.run` with
no arguments. Build a fund, staff it with AI agents, and time-travel it
through history against its benchmark. The engine is untouched — this
package renders it.

One file per thing on screen:

    app.py         HedgeFundApp — the screen stack, rooted at home
    home.py        the landing screen, model picker, API-key prompt
    funds.py       the mandate library: saved definitions and their backtests
    builder.py     the fund wizard
    paper.py       paper trading screens: fund list, approval, a run, history
    paper_view.py  what those screens show, computed from a fund directory (Rich only)
    backtest.py    the backtest board
    report.py      renderers for recorded signals, orders and the book (Rich only)
    widgets.py     Textual pieces more than one screen composes
    shared.py      presentation constants and the equity chart; the CLI imports from here
    palette.py     the six colours and the ANSI theme
    keys.py        API-key storage
"""

import warnings

# langchain's deprecated-global warning fires when the LLM client loads
# lazily inside worker threads — it would splatter across the live UI.
# Suppress it here so it's set before any entry point triggers an LLM load:
# the TUI (imports hedge_fund.tui.app) and the non-interactive CLI (imports
# hedge_fund.tui.shared) both go through this package.
warnings.filterwarnings(
    "ignore", message="Importing verbose from langchain root module"
)
