"""Read a user-supplied research snapshot during paper approval."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, HttpUrl, StringConstraints
from rich.style import Style
from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, OptionList, Static
from textual.widgets.option_list import Option

RESEARCH_FILE_ENV = "HEDGE_FUND_PAPER_RESEARCH_FILE"
MAX_SNAPSHOT_BYTES = 1_048_576
ResearchText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class _View(BaseModel):
    author: ResearchText
    published_at: AwareDatetime
    source_url: HttpUrl
    stance: ResearchText | None = None
    thesis: ResearchText
    watch: ResearchText


class _TickerResearch(BaseModel):
    as_of: AwareDatetime
    views: list[_View]


def _read_details(path: Path, ticker: str) -> Text:
    path = path.expanduser()
    if not path.is_file():
        raise OSError("expected a regular research file")
    with path.open("rb") as file:
        body = file.read(MAX_SNAPSHOT_BYTES + 1)
    if len(body) > MAX_SNAPSHOT_BYTES:
        raise ValueError("research file exceeds 1 MiB")
    snapshots = json.loads(body)
    if not isinstance(snapshots, dict):
        raise ValueError("expected research keyed by ticker")

    details = Text()
    details.append(ticker, style="bold")
    if ticker not in snapshots:
        details.append("\n\nNo cited research in this file for this ticker.")
        return details
    research = _TickerResearch.model_validate(snapshots[ticker])
    if research.as_of > datetime.now(timezone.utc) or any(view.published_at > research.as_of for view in research.views):
        raise ValueError("inconsistent research dates")

    details.append(f"\nResearch cutoff: {research.as_of.isoformat()}")
    if not research.views:
        details.append("\n\nNo cited research in this file for this ticker.")
    for view in research.views:
        stance = f" · {view.stance}" if view.stance else ""
        excerpt = f"\n\n{view.author}{stance}\n{view.thesis}\nWatch: {view.watch}\nPublished: {view.published_at.isoformat()}\n"
        # Provider text is data. Strip terminal control characters before display.
        details.append(re.sub(r"[\x00-\x09\x0b-\x1f\x7f-\x9f]", "", excerpt))
        url = str(view.source_url)
        details.append(url, style=Style(link=url))
    return details


class PaperResearchScreen(Screen[None]):
    BINDINGS = [Binding("escape", "back", "back to approval")]

    def __init__(self, path: Path, tickers: list[str]) -> None:
        super().__init__()
        self._path = path
        self._tickers = tickers

    def compose(self) -> ComposeResult:
        with Vertical(id="run-report"):
            yield Static("Cited research for pending and held tickers", id="report-head")
            with Horizontal(id="report-panes"):
                with Vertical(id="report-rail"):
                    yield OptionList(*(Option(Text(ticker), id=ticker) for ticker in self._tickers), id="report-nav")
                with VerticalScroll(id="report-detail"):
                    yield Static("Select a ticker and press Enter to read its research.", id="detail-pane")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#report-nav", OptionList).focus()

    @on(OptionList.OptionHighlighted, "#report-nav")
    def _highlight_ticker(self, event: OptionList.OptionHighlighted) -> None:
        prompt = Text(f"Press Enter to read research for {event.option_id}.")
        self.query_one("#detail-pane", Static).update(prompt)
        self.query_one("#report-detail", VerticalScroll).scroll_home(animate=False)

    @on(OptionList.OptionSelected, "#report-nav")
    def _select_ticker(self, event: OptionList.OptionSelected) -> None:
        ticker = event.option_id
        if ticker is None:
            return
        try:
            details = _read_details(self._path, ticker)
        except (OSError, ValueError, RuntimeError):
            details = Text("Could not read cited research. Check the file path and format, then select the ticker again.")
        self.query_one("#detail-pane", Static).update(details)
        self.query_one("#report-detail", VerticalScroll).scroll_home(animate=False)

    def action_back(self) -> None:
        self.dismiss()
