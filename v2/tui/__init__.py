"""The AI Hedge Fund interactive app — a Textual TUI.

v2's interactive experience: `python -m v2.tui`, or `python -m v2.run` with
no arguments. Build a fund, staff it with AI agents, and time-travel it
through history against its benchmark. The engine is untouched — this
package renders it.
"""

import warnings

# langchain's deprecated-global warning fires when the LLM client loads
# lazily inside worker threads — it would splatter across the live UI.
# Suppress it here so it's set before any entry point triggers an LLM load:
# the TUI (imports v2.tui.app) and the non-interactive CLI (imports
# v2.tui.shared) both go through this package.
warnings.filterwarnings(
    "ignore", message="Importing verbose from langchain root module"
)
