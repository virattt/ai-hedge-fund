"""The Textual app: one screen stack, rooted at the home screen."""

from __future__ import annotations

from textual.app import App
from textual.binding import Binding

from hedge_fund import paths
from hedge_fund.tui.home import HomeScreen
from hedge_fund.tui.keys import apply_credentials
from hedge_fund.tui.palette import ANSI_THEME
from hedge_fund.tui.shared import VERSION


class HedgeFundApp(App):
    """The v2 terminal app. One screen stack: Home → Backtest / Paper / Builder."""

    TITLE = "AI Hedge Fund"
    SUB_TITLE = f"v{VERSION}"
    CSS_PATH = "app.tcss"
    ansi_theme_dark = ANSI_THEME

    # Textual 8.x deliberately unbinds ctrl+c from quit (it copies inside a
    # focused Input, else just hints how to quit). Users reflexively hit
    # ctrl+c to leave, so restore it: priority=True so it fires before the
    # system binding AND any focused widget, quitting from anywhere.
    BINDINGS = [Binding("ctrl+c", "quit", "quit", priority=True, show=False)]

    def on_mount(self) -> None:
        # Saved keys become environment variables before any screen builds an
        # agent. Anything already exported wins — see hedge_fund/tui/keys.py.
        apply_credentials()
        paths.ensure_mandates_dir()
        self.push_screen(HomeScreen())
