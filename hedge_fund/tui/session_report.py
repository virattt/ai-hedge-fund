"""One recorded session, browsable: the paper fund's tick lands here, its
history opens here, and a backtest's decisions open here too."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, OptionList, Static

from hedge_fund.pipeline import SessionRecord
from hedge_fund.tui.report import (
    book_summary,
    session_detail,
    session_headline,
    session_nav,
)
from hedge_fund.tui.widgets import first_selectable


class SessionReportScreen(Screen):
    """One recorded session, browsable: every signal on the rail, the full
    thesis on the right. The same browser the tick lands on."""

    BINDINGS = [Binding("escape", "back", "back")]

    def __init__(self, name: str, record: SessionRecord) -> None:
        super().__init__()
        self._name = name
        self._record = record

    def compose(self) -> ComposeResult:
        with Vertical(id="run-report"):
            yield Static("", id="report-head")
            with Horizontal(id="report-panes"):
                with Vertical(id="report-rail"):
                    yield OptionList(id="report-nav")
                with VerticalScroll(id="report-detail"):
                    yield Static("", id="detail-pane")
            yield Static("", id="report-foot")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#report-head", Static).update(session_headline(self._name, self._record))
        self.query_one("#report-foot", Static).update(book_summary(self._record))
        nav = self.query_one("#report-nav", OptionList)
        nav.add_options(session_nav(self._record))
        nav.highlighted = first_selectable(nav)
        nav.focus()

    def action_back(self) -> None:
        self.app.pop_screen()

    @on(OptionList.OptionHighlighted, "#report-nav")
    def _browse(self, event: OptionList.OptionHighlighted) -> None:
        oid = (event.option.id or "") if event.option else ""
        detail = session_detail(self._record, oid)
        if detail is not None:
            self.query_one("#detail-pane", Static).update(detail)
            self.query_one("#report-detail", VerticalScroll).scroll_home(animate=False)
