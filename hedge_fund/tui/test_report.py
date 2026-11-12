"""Pure renderers: verdicts, the live desk, signal and portfolio details."""

import pytest

from hedge_fund.brokers.models import Fill, Order
from hedge_fund.fund import AllocationPolicy
from hedge_fund.models import Signal
from hedge_fund.pipeline.models import Allocated, AllocationRecord
from hedge_fund.tui import report
from hedge_fund.pipeline.stages import stop_out_decision
from hedge_fund.risk.limits import ClampEvent
from hedge_fund.tui.fixtures import make_cycle, make_pending, make_session, make_signal, make_spec, render


@pytest.mark.parametrize("direction,strength", [("bullish", 3.2), ("bearish", 1.6), ("neutral", 4), ("bullish", 0), ("bearish", 0)])
def test_jev_results_show_stored_direction_and_separate_confidence(direction, strength):
    signal = make_signal(direction, strength)
    detail = render(report.signal_detail(make_cycle(signal), 0, 0))
    assert direction.upper() in detail
    assert "investment conviction" in detail
    assert "No written thesis generated." in detail
    assert "Jev answer-option probabilities" in detail
    assert "not investment returns" in detail
    assert "Jev native answer confidence" in detail
    assert "Direction: 60.0%" in detail
    assert "Bullish strength: 40.0%" in detail
    assert "Bearish strength: 40.0%" in detail
    assert f"{direction.capitalize()} 80.0%" in detail
    cached = signal.model_copy(deep=True)
    cached.metadata["cached"] = True
    assert render(report.signal_detail(make_cycle(cached), 0, 0)) == detail
    desk = report.Desk("Buffett")
    desk.begin("TEST")
    assert report._live_verdict(desk).plain == "thinking"
    assert report._live_thesis(desk).plain == ""
    desk.settle(signal)
    assert direction.upper() in report._live_verdict(desk).plain
    assert report._live_thesis(desk).plain == signal.reasoning
    verdict = report.verdict(signal)
    nav = report.report_nav(make_cycle(signal))
    option = next(option for option in nav if option.id == "sig:0:0")
    assert verdict[0] in render(option.prompt)


def test_abstention_overrides_stored_direction():
    signal = Signal(model_name="buffett", ticker="TEST", date="2025-01-15", value=0, reasoning="abstained: TypeSafe returned HTTP 401", metadata={"abstained": True, "signal": "bullish"})
    text = render(report.signal_detail(make_cycle(signal), 0, 0))
    assert "ABSTAIN" in text and "HTTP 401" in text
    assert "Jev native answer confidence" not in text


def test_chat_rendering_and_quantitative_fallback_are_preserved():
    chat = Signal(model_name="buffett", ticker="TEST", date="2025-01-15", value=0.8, reasoning="A durable business.", metadata={"signal": "bullish", "confidence": 80.0})
    text = render(report.signal_detail(make_cycle(chat), 0, 0))
    assert "80% confidence" in text and "conviction +0.80" in text
    assert "A durable business." in text and "Jev" not in text
    desk = report.Desk("Buffett")
    desk.begin("TEST")
    desk.feed('{"signal":"bullish","confidence":80,"reasoning":"A durable business."}')
    assert "BULLISH" in report._live_verdict(desk).plain
    assert "A durable business." in report._live_thesis(desk).plain
    for value, direction in [(0.5, "BULLISH"), (-0.5, "BEARISH"), (0, "NEUTRAL")]:
        quant = Signal(model_name="pead", ticker="TEST", date="2025-01-15", value=value)
        assert report.verdict(quant)[1] == direction
        desk.settle(quant)
        assert report._live_thesis(desk).plain == ""


def test_portfolio_report_explains_rounding_scaling_and_flat_strategies():
    record = make_cycle(make_signal())
    record.spec.strategies[0].blend.mode = "dollar_neutral"
    record.equity_before = record.nav = 10_000
    record.final_weights = {"A": .5, "B": -.5}
    record.positions = {"A": 16, "B": -7}
    record.marks = {"A": 300, "B": 700}
    record.risk_scale_factor = .5
    text = render(report.portfolio_detail(record))
    assert "Target net $+0.00" in text
    assert "Actual net $-100.00" in text
    assert "Difference $-100.00" in text
    assert "scaled all strategy targets to 50.0%" in text
    assert "Whole-share holdings can differ" in text
    record.positions = {}
    record.final_weights = {"A": 0, "B": 0}
    record.strategies[0].flat_reason = "missing_short_side"
    text = render(report.portfolio_detail(record))
    assert "no eligible shorts to balance the longs" in text
    assert "Allocated capital remains unused" in text
    assert "flat — no positions" in text


def test_orders_report_shows_the_fill_beside_the_mark_and_what_it_cost():
    record = make_cycle(make_signal())
    record.orders = [Order(ticker="TEST", side="buy", quantity=100, price=100.0, adv=10_000, volatility=0.0)]
    record.fills = [Fill(ticker="TEST", side="buy", quantity=100, price=100.05)]
    record.cash_before, record.cash = 100_000, 100_000 - 100 * 100.05 - 0.50
    text = render(report.session_detail(_session_with(record), "x:sec:orders"))
    assert "Mark" in text and "Fill" in text and "% ADV" in text
    assert "$100.00" in text and "$100.05" in text and "1.00%" in text
    # $5 of slippage splits into what the mandate's spread explains and the rest.
    spread = 100 * 100.0 * record.spec.costs.spread_bps / 10_000
    assert f"spread ${spread:,.2f} · impact ${5.0 - spread:,.2f} · commission $0.50" in text
    record.orders = [Order(ticker="TEST", side="buy", quantity=100, price=100.0)]
    record.fills = [Fill(ticker="TEST", side="buy", quantity=100, price=100.0)]
    record.cash = 100_000 - 100 * 100.0
    text = render(report.session_detail(_session_with(record), "x:sec:orders"))
    assert "spread" not in text and "% ADV" not in text


def test_cost_line_reads_as_bps_of_what_was_traded():
    assert report.cost_line(312.0, 375_000.0) == "costs $312 · 8.3 bps of $375,000 traded"
    assert report.cost_line(0.0, 0.0) == "no trades"


def _session_with(record):
    return make_session(record.as_of, executed=record)


def test_a_stop_out_reads_as_one_in_the_row_and_the_overview():
    spec = make_spec().model_copy(update={"risk": make_spec().risk.model_copy(update={"max_drawdown_pct": 0.2})})
    decision = stop_out_decision(spec, "2025-01-15", ["TEST"], {"TEST": 80.0}, {"TEST": 100}, 0.213)
    session = make_session("2025-01-15", decision=decision, positions={"TEST": 100}, marks={"TEST": 80.0}, nav=80_000)
    assert "stopped out" in render(report.session_row(session, 100_000))
    text = render(report.session_overview(session))
    assert "STOPPED OUT" in text and "drawdown 21.3% breached the 20.0% limit" in text
    assert "HALVED" not in text and not decision.is_halved


def test_a_halve_reads_as_one_in_the_row_and_the_overview():
    decision = make_halved_decision()
    assert decision.is_halved and not decision.is_stopped_out
    session = make_session(decision.as_of, decision=decision)
    row = render(report.session_row(session, 100_000))
    assert "halved" in row and "decided" not in row
    text = render(report.session_overview(session))
    assert "HALVED" in text and "drawdown 10.3% past the 10.0% line" in text


def test_a_decision_row_and_overview_pair_the_decision_with_its_fills():
    decision = make_halved_decision("2025-01-16")
    decided = make_session("2025-01-16", decision=decision, nav=89_700)
    cycle = make_cycle(make_signal())
    cycle.as_of = "2025-01-16"
    cycle.fills = [Fill(ticker="TEST", side="buy", quantity=2, price=100), Fill(ticker="TEST", side="sell", quantity=1, price=101)]
    executed = make_session("2025-01-17", executed=cycle, nav=90_000)
    row = render(report.decision_row(decided, executed, 100_000))
    assert row.strip() == "2025-01-16  -10.3%  halved · 2 fills"
    assert "halved · pending" in render(report.decision_row(decided, None, 100_000))
    text = render(report.decision_overview(decided, executed))
    assert "HALVED" in text and "DECIDED" in text and "EXECUTED  at 2025-01-17" in text
    assert "BUY  2 TEST" in text and "SELL 1 TEST" in text
    assert "NOT EXECUTED" in render(report.decision_overview(decided, None))


def make_halved_decision(as_of="2025-01-16"):
    """A decision made 10.3% off the peak with a 10% halving tier: one
    whole-book clamp, size 0.5."""
    decision = make_pending(as_of)
    decision.spec = decision.spec.model_copy(
        update={"risk": decision.spec.risk.model_copy(update={"halve_drawdown_pct": 0.10})})
    decision.clamps = [ClampEvent(limit="halve_drawdown_pct", before=0.103, after=0.5)]
    return decision


def test_allocation_section_shows_each_weight_beside_the_mandate_and_its_evidence():
    record = make_cycle(make_signal())
    record.spec.allocation = AllocationPolicy()
    record.allocation = AllocationRecord(
        as_of="2025-01-15",
        strategies={"value": Allocated(mandate=1.0, t_stat=1.5, n=24, weight=1.375)},
        models={"value": {"buffett": Allocated(mandate=1.0, t_stat=-1.0, n=31, weight=0.75),
                          "munger": Allocated(mandate=1.0, t_stat=None, n=8, weight=1.0)}},
    )
    text = render(report.session_detail(_session_with(record), "x:sec:allocation"))
    assert "scored from the ledger at 2025-01-15" in text
    assert "value  slice 1.00 → 1.38  (t +1.5 over 24 periods)" in text
    assert "weight 1.00 → 0.75  (IC t -1.0 over 31 dates)" in text
    assert "weight 1.00 → 1.00  (8 of 20 dates)" in text


def test_exposures_section_shows_the_book_and_every_name_and_a_sector_clamp_names_its_sector():
    from hedge_fund.risk import ClampEvent, Exposures, NameExposure
    record = make_cycle(make_signal())
    record.final_weights = {"TEST": 0.5}
    record.exposures = Exposures(as_of="2025-01-15", benchmark_volatility=0.18, names={
        "TEST": NameExposure(beta=1.2, residual_volatility=0.25, sector="Technology", n_bars=250)})
    record.clamps = [ClampEvent(limit="max_sector_pct", sector="Technology", before=0.6, after=0.3)]
    text = render(report.session_detail(_session_with(record), "x:sec:exposures"))
    assert "single-index model fitted at 2025-01-15" in text
    assert "book  beta +0.60 · vol 16.5% · benchmark vol 18.0%" in text
    assert "TEST" in text and "+1.20" in text and "25.0%" in text and "Technology" in text and "250" in text
    risk = render(report.session_detail(_session_with(record), "x:sec:risk"))
    assert "Technology" in risk and "max_sector_pct" in risk and "+0.60" in risk and "+0.30" in risk
