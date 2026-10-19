"""Paper trading rows and plans, rendered from a fund directory without a screen."""

import os
from datetime import datetime, timedelta

from hedge_fund import paths
from hedge_fund.data.sessions import NEW_YORK
from hedge_fund.paper import deploy, Ledger, PID_FILE
from hedge_fund.tui import paper_view, report
from hedge_fund.tui.fixtures import (
    executed_and_decided,
    make_minute_spec,
    make_pending,
    make_quote,
    make_session,
    make_spec,
    make_state,
    render,
)
from hedge_fund.tui.palette import MUTED


def test_run_plan_says_exactly_what_the_run_will_do():
    spec = make_spec(["pead"], "alpha")  # weekly by default
    # Pending decision, and the due session opens a new week: execute, then decide.
    plan = paper_view.run_plan("alpha", make_state(last_session="2025-01-17", pending=make_pending()), "2025-01-21", spec).plain
    assert "Execute the 2025-01-17 decision at the 2025-01-21 close" in plan
    assert "AAPL +25%  ·  MSFT +25%" in plan and "XOM" not in plan
    assert "views refreshed before sizing" in plan
    assert "make a new decision" in plan and "first session of the week" in plan
    # Pending decision mid-week: execute, then only mark the book.
    plan = paper_view.run_plan("alpha", make_state(last_session="2025-01-20", pending=make_pending("2025-01-20")), "2025-01-21", spec).plain
    assert "Execute the 2025-01-20 decision" in plan and "Then mark the book." in plan
    assert "new decision" not in plan
    # Nothing pending, mid-week: a mark only.
    plan = paper_view.run_plan("alpha", make_state(last_session="2025-01-20"), "2025-01-21", spec).plain
    assert plan.startswith("Mark the book at the 2025-01-21 close.  No trades.")
    assert "decision" not in plan
    # A brand-new fund: mark, then its first decision.
    plan = paper_view.run_plan("alpha", make_state(), "2025-01-21", spec).plain
    assert "Mark the book at the 2025-01-21 close" in plan and "first decision" in plan
    # A pending decision that went flat says so rather than listing nothing,
    # and says why when the blender recorded a reason: a dollar-neutral desk
    # with conviction but no short to balance it is not "no conviction".
    flat = make_pending("2025-01-20", {})
    plan = paper_view.run_plan("alpha", make_state(last_session="2025-01-20", pending=flat), "2025-01-21", spec).plain
    assert "flat — no conviction cleared the bar" in plan
    flat.strategies[0].flat_reason = "missing_short_side"
    plan = paper_view.run_plan("alpha", make_state(last_session="2025-01-20", pending=flat), "2025-01-21", spec).plain
    assert "flat — no eligible shorts to balance the longs" in plan
    overview = render(report.session_overview(make_session("2025-01-20", decision=flat)))
    assert "flat — no eligible shorts to balance the longs" in overview
    # Nothing due: when the next close is, Friday rolling to Monday.
    plan = paper_view.run_plan("alpha", make_state(last_session="2025-01-17"), None, spec).plain
    assert plan.startswith("Up to date through 2025-01-17.  Next session: 2025-01-20 close.")
    assert "Run 2025-01-17 again?" in plan and "recorded session is replaced" in plan
    friday = datetime(2025, 1, 17, 18, 0, tzinfo=NEW_YORK)
    assert paper_view.run_plan("alpha", make_state(), None, spec, now=friday).plain == (
        "No completed SPY session to run yet.  Next: 2025-01-20 close.")


def test_run_plan_on_a_bar_names_the_print_and_how_late_it_is_taken():
    spec = make_minute_spec()  # every 5m, 13:00–13:10
    at = lambda h, m, s=0: datetime(2025, 1, 21, h, m, s, tzinfo=NEW_YORK)  # noqa: E731
    state = make_state(last_session="2025-01-21T13:00:00", pending=make_pending("2025-01-21T13:00:00"))
    plan = paper_view.run_plan("fast", state, "2025-01-21T13:05:00", spec, now=at(13, 5, 20)).plain
    assert "Execute the 2025-01-21 13:00:00 ET decision at the 2025-01-21 13:05:00 ET print, taken now\n" in plan
    assert "after the bar" not in plan and "make a new decision  (every bar)" in plan
    late = paper_view.run_plan("fast", state, "2025-01-21T13:05:00", spec, now=at(13, 7, 30)).plain
    assert "print, taken now (2 minutes after the bar)" in late
    plan = paper_view.run_plan("fast", make_state(), "2025-01-21T13:00:00", spec, now=at(13, 0, 5)).plain
    assert plan.startswith("Mark the book at the 2025-01-21 13:00:00 ET print, taken now.  No trades.")
    # Nothing due between bars, and before the first bar of the day.
    plan = paper_view.run_plan("fast", make_state(last_session="2025-01-21T13:05:00"), None, spec, now=at(13, 7)).plain
    assert plan.startswith("Up to date through 2025-01-21 13:05:00 ET.  Next session: 13:10:00 ET.")
    assert "sized again at the prints it saw" in plan
    assert paper_view.run_plan("fast", make_state(), None, spec, now=at(12, 0)).plain == (
        "No bar to run yet.  Next: 13:00:00 ET.")


def test_live_rows_value_the_book_at_the_latest_prints():
    spec = make_spec(["pead"], "alpha")
    directory = deploy("alpha", spec, ["TEST"], root=paths.PAPER_DIR)
    ledger = Ledger(directory)
    record, _ = executed_and_decided()
    ledger.append(make_session("2025-01-20", executed=record, nav=101000, positions={"TEST": 10}, marks={"TEST": 100}))
    snap = paper_view.PaperSnapshot(directory)
    # A daily fund has the same next-run row as a minute fund: when, and whether a runner will take it.
    rows = dict(paper_view.next_run_rows(snap, now=datetime(2025, 1, 21, 12, 0, tzinfo=NEW_YORK)))
    assert render(rows["Next close"]).strip() == "2025-01-21   ○ idle · space to start a runner"
    assert "○ idle" in render(snap.badge())  # a session recorded, no runner up
    # Every held name needs a print; cash alone has nothing live to say.
    assert paper_view.live_rows(snap, {}, today="2025-01-21") == []
    label, line = paper_view.live_rows(snap, {"TEST": make_quote("TEST", 110)}, today="2025-01-21")[0]
    text = render(line)
    assert label == "Live" and "$101,100" in text and "+0.10%" in text and "as of 10:05 ET" in text
    # A print from before today is shown, but muted and dated: not a live gain.
    _, line = paper_view.live_rows(snap, {"TEST": make_quote("TEST", 110, "2025-01-20T21:00:00Z")}, today="2025-01-21")[0]
    assert "as of Jan 20 16:00 ET" in render(line)
    assert all(span.style == MUTED for span in line.spans)
    assert "Live" in render(paper_view.paper_detail(snap, quotes={"TEST": make_quote("TEST", 110)}))
    assert "Live" not in render(paper_view.paper_detail(snap))


def test_minute_fund_rows_are_pure(monkeypatch):
    directory = deploy("fast", make_minute_spec(), ["TEST"], root=paths.PAPER_DIR)
    ledger = Ledger(directory)
    noon = datetime(2025, 1, 21, 12, 0, tzinfo=NEW_YORK)
    snap = paper_view.PaperSnapshot(directory)
    assert not snap.running and snap.intraday
    rows = dict(paper_view.next_run_rows(snap, now=noon))
    assert render(rows["Next bar"]).strip() == "13:00:00 ET   ○ idle · space to start a runner"
    assert rows["First"] == "mark the book at the first bar's prints" and rows["Then"] == "make the first decision"
    assert paper_view.today_rows(snap, now=noon) == []
    assert "● new" in render(paper_view.paper_slot(0, snap)) and "● new" in render(snap.badge())
    assert render(snap.status()).startswith("● NEW  no sessions yet")

    record, decided = executed_and_decided()
    first = make_session("2025-01-21T13:00:00", decision=decided, nav=100000)
    second = make_session("2025-01-21T13:05:00", executed=record, nav=101000, positions={"TEST": 10},
                      marks={"TEST": 100}, prev_hash=first.hash)
    ledger.append(first)
    ledger.append(second)
    (directory / PID_FILE).write_text(str(os.getpid()))
    snap = paper_view.PaperSnapshot(directory)
    assert snap.running
    rows = dict(paper_view.next_run_rows(snap, now=noon.replace(hour=13, minute=6)))
    assert render(rows["Next bar"]).strip() == "13:10:00 ET   ● running · space to stop"
    assert rows["Then"] == "make a new decision"
    # After the day's last bar the next one is tomorrow's open, named by weekday.
    assert render(dict(paper_view.next_run_rows(snap, now=noon.replace(hour=15)))["Next bar"]).startswith("Wed 13:00:00 ET")
    today = dict(paper_view.today_rows(snap, now=noon.replace(hour=13, minute=6)))
    assert render(today["Bars"]).strip() == "2 / 3   last 13:05:00 ET"
    assert render(today["Since open"]).strip() == "+1.00%   1 fill"
    assert paper_view.today_rows(snap, now=noon + timedelta(days=1)) == []  # yesterday's bars are not today's
    detail = render(paper_view.paper_detail(snap, now=noon.replace(hour=13, minute=6)))
    assert "every 5m · 13:00–13:10 ET" in detail and "TODAY" in detail and "● running" in detail
    assert "SESSIONS" in detail and "2025-01-21T13:05:00" in detail
    assert "+1.0%  ● running" in render(paper_view.paper_slot(0, snap))
    assert snap.metrics().n_cycles == 1  # bar keys do not trip the metrics' date math
