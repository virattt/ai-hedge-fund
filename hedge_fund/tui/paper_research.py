"""Browse cited research from BeliefState or a local paper-review snapshot."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, HttpUrl, StringConstraints
from rich.style import Style
from rich.text import Text
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Input, OptionList, Static
from textual.widgets.option_list import Option
from textual.worker import get_current_worker

from hedge_fund.research import API_KEY_ENV, BeliefStateClient, Company, CurrentBrief, ResearchError

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


def _current_details(ticker: str, brief: CurrentBrief | None) -> Text:
    lines = [f"BeliefState · {ticker}"]
    links: set[str] = set()
    if brief is None:
        return Text(f"BeliefState · {ticker}\n\nNo released direct company research is available for this ticker.")
    lines.append(f"Research cutoff: {brief.as_of.isoformat()}")
    if not brief.beliefs or brief.coverage.completeness == "no_fit":
        lines.append("No matching investor views are available in this brief.")
    for belief in brief.beliefs:
        lines.extend(["", f"{belief.person.name} · {belief.direction}", belief.thesis])
        for label, value in (("Action", belief.action), ("Target", belief.target), ("Horizon", belief.time_horizon)):
            if value:
                lines.append(f"{label}: {value}")
        for evidence in belief.evidence:
            published = evidence.published_at.isoformat() if evidence.published_at else "unknown"
            lines.append(f"Published: {published} · {evidence.source_url} · source coverage: {evidence.source_coverage}")
            links.add(str(evidence.source_url))
        lines.extend(belief.qualifications)
        for label, objects in (("Risk", belief.risks), ("Catalyst", belief.catalysts)):
            for item in objects:
                lines.append(f"{label} · {item.status} · {item.statement}")
                lines.extend(f"Unknown · {unknown.field}: {unknown.reason}" for unknown in item.unknowns)
                lines.extend(f"Source: {evidence.source_url}" for evidence in item.evidence)
                lines.extend(f"Checking evidence: {evidence.source_url}" for evidence in item.checking_evidence)
                links.update(str(evidence.source_url) for evidence in item.evidence + item.checking_evidence)
        lines.extend(f"Unknown · {unknown.field}: {unknown.reason}" for unknown in belief.unknowns)
        if belief.omitted_risk_count or belief.omitted_catalyst_count:
            lines.append(f"Omitted: {belief.omitted_risk_count} risks, {belief.omitted_catalyst_count} catalysts.")
        lines.append(f"Full case: {belief.detail_url}")
        links.add(str(belief.detail_url))
    if brief.coverage.omitted_belief_count:
        lines.append(f"Additional views omitted from this brief: {brief.coverage.omitted_belief_count}")
    lines.extend(brief.warnings)
    lines.extend(f"Research gap: {gap.reason.replace('_', ' ')} · {gap.detail_url}" for gap in brief.quality_gaps)
    links.update(str(gap.detail_url) for gap in brief.quality_gaps)
    if brief.detail_reference:
        lines.append(f"More research: {brief.detail_reference}")
    details = Text(re.sub(r"[\x00-\x09\x0b-\x1f\x7f-\x9f]", "", "\n".join(lines)))
    for url in sorted(links, key=len):
        details.highlight_words([url], style=Style(link=url))
    return details


class PaperResearchScreen(Screen[None]):
    BINDINGS = [
        Binding("escape", "back", "back"),
        Binding("ctrl+k", "set_key", "BeliefState API key", priority=True),
    ]

    def __init__(self, path: Path | None = None, tickers: list[str] | None = None) -> None:
        super().__init__()
        self._path = path
        self._tickers = tickers or []
        self._loading: str | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="run-report"):
            yield Static("Cited investor research" if self._path else "BeliefState · Investor research", id="report-head")
            if self._path is None:
                yield Input(placeholder="Search by ticker or company name (free)", max_length=80, id="research-search")
                yield Static("Research reads use your BeliefState allowance or credits. Search is free. Fresh reads are reused for 60 seconds.", id="research-status")
            with Horizontal(id="report-panes"):
                with Vertical(id="report-rail"):
                    yield OptionList(*(Option(Text(ticker), id=ticker) for ticker in self._tickers), id="report-nav")
                with VerticalScroll(id="report-detail"):
                    yield Static("Select a ticker and press Enter to read its research.", id="detail-pane")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#report-nav" if self._tickers or self._path else "#research-search").focus()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action == "set_key":
            return self._path is None and self._loading is None
        return super().check_action(action, parameters)

    def action_set_key(self) -> None:
        from hedge_fund.tui.home import KeyPromptScreen
        self.app.push_screen(KeyPromptScreen(
            "BeliefState", API_KEY_ENV,
            purpose="Research uses your BeliefState allowance or credits. Get a key at https://beliefstate.ai/account#api-keys.",
        ), self._key_saved)

    def _key_saved(self, saved: bool) -> None:
        if saved:
            self.app.research_client = BeliefStateClient(os.environ.get(API_KEY_ENV, ""))

    @on(Input.Submitted, "#research-search")
    def _submit_search(self, event: Input.Submitted) -> None:
        event.stop()
        self.query_one("#research-status", Static).update("Searching companies…")
        self._search(event.value)

    @work(thread=True, group="research-search", exclusive=True)
    def _search(self, query: str) -> None:
        worker = get_current_worker()
        try:
            companies = self.app.research_client.search(query)
            error = None
        except ResearchError as exc:
            companies, error = [], str(exc)
        if not worker.is_cancelled:
            self.app.call_from_thread(self._show_search, companies, error)

    def _show_search(self, companies: list[Company], error: str | None) -> None:
        if not self.is_attached:
            return
        menu = self.query_one("#report-nav", OptionList)
        menu.clear_options()
        menu.add_options([
            Option(Text(re.sub(r"[\x00-\x1f\x7f-\x9f]", "", f"{company.ticker} · {company.name}") +
                        f"\n{'Research available' if company.direct_research else 'No direct research'}"), id=company.ticker)
            for company in companies
        ])
        self.query_one("#detail-pane", Static).update(Text("Select a ticker and press Enter to load its available research."))
        status = error or (f"{len(companies)} companies. Enter loads research using your allowance or credits." if companies else "No matching company found. Try the listing's ticker or company name.")
        self.query_one("#research-status", Static).update(Text(status))
        if companies:
            menu.highlighted = 0
            menu.focus()

    @on(OptionList.OptionHighlighted, "#report-nav")
    def _highlight_ticker(self, event: OptionList.OptionHighlighted) -> None:
        if event.option_id is None:
            return
        loading = self._loading == event.option_id
        prompt = Text(f"Loading research for {event.option_id}…" if loading else f"Press Enter to read research for {event.option_id}.")
        self.query_one("#detail-pane", Static).update(prompt)
        self.query_one("#report-detail", VerticalScroll).scroll_home(animate=False)

    @on(OptionList.OptionSelected, "#report-nav")
    def _select_ticker(self, event: OptionList.OptionSelected) -> None:
        ticker = event.option_id
        if ticker is None:
            return
        if self._path is None:
            if self._loading is None:
                self._loading = ticker
                self.query_one("#detail-pane", Static).update(Text(f"Loading research for {ticker}…"))
                self.refresh_bindings()
                self._load_current(ticker)
            else:
                self.notify(f"Research for {self._loading} is still loading.")
            return
        try:
            details = _read_details(self._path, ticker)
        except (OSError, ValueError, RuntimeError):
            details = Text("Could not read cited research. Check the file path and format, then select the ticker again.")
        self.query_one("#detail-pane", Static).update(details)
        self.query_one("#report-detail", VerticalScroll).scroll_home(animate=False)

    @work(thread=True, group="research-read", exclusive=True)
    def _load_current(self, ticker: str) -> None:
        worker = get_current_worker()
        try:
            brief = self.app.research_client.read(
                ticker, cancelled=lambda: worker.is_cancelled or not self.is_attached or not self.is_current,
            )
            details = _current_details(ticker, brief)
        except ResearchError as exc:
            details = Text(str(exc))
        if not worker.is_cancelled:
            self.app.call_from_thread(self._show_current, ticker, details)

    def _show_current(self, ticker: str, details: Text) -> None:
        self._loading = None
        if not self.is_attached:
            return
        option = self.query_one("#report-nav", OptionList).highlighted_option
        if option is not None and option.id == ticker:
            self.query_one("#detail-pane", Static).update(details)
        self.refresh_bindings()

    def action_back(self) -> None:
        self.dismiss()
