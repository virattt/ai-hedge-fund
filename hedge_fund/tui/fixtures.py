"""Builders for the records and specs the TUI tests render, and a plain-text renderer."""

import io

from rich.console import Console

from hedge_fund.brokers.models import Fill
from hedge_fund.data import PriceSnapshot
from hedge_fund.fund import custom_strategy, FundSpec
from hedge_fund.llm.contract import normalize_jev_response
from hedge_fund.llm.test_contract import _response
from hedge_fund.models import Signal
from hedge_fund.pipeline import CycleRecord, DecisionRecord, FundState, SessionRecord


def render(renderable):
    output = io.StringIO()
    # soft_wrap: long header lines stay on one line, so assertions can match
    # phrases without guessing where a wrap would land.
    Console(file=output, width=140, color_system=None).print(renderable, soft_wrap=True)
    return output.getvalue()


def make_signal(direction="bullish", strength=3.2, cached=False):
    payload, metadata = normalize_jev_response(_response(direction, bullish=strength, bearish=strength))
    sign = {"bullish": 1, "bearish": -1, "neutral": 0}[direction]
    return Signal(model_name="buffett", ticker="TEST", date="2025-01-15", value=sign * payload["confidence"] / 100, reasoning=payload["reasoning"], horizon_days=252, metadata={"signal": direction, "confidence": payload["confidence"], "abstained": False, "cached": cached, "provider_metadata": {"jev": metadata}})


def make_cycle(signal):
    return CycleRecord(
        fund="test",
        as_of=signal.date,
        spec={"schema_version": 2, "name": "test", "strategies": [{"name": "value", "models": [{"name": "buffett"}], "blend": {"mode": "long_only"}}], "risk": {"max_position_pct": 0.25, "max_gross_exposure": 1}},
        universe=[signal.ticker],
        marks={signal.ticker: 100},
        skipped=[],
        strategies=[{"name": "value", "slice": 1, "signals": [signal], "convictions": {}, "weights": {}}],
        target_weights={},
        clamps=[],
        final_weights={},
        equity_before=100000,
        cash_before=100000,
        orders=[],
        fills=[],
        positions={},
        cash=100000,
        nav=100000,
    )


def make_session(session, *, executed=None, decision=None, nav=100000, positions=None, marks=None, prev_hash=None):
    record = SessionRecord(
        fund="test", session=session, universe=["TEST"], nav=nav, cash=nav - sum((positions or {}).get(t, 0) * (marks or {}).get(t, 0) for t in (positions or {})),
        positions=positions or {}, marks=marks or {}, benchmark="SPY", benchmark_close=100.0,
        rebalance=decision is not None, executed=executed, decision=decision,
        prev_hash=prev_hash, code_version="test", mandate_hash="m",
    )
    record.hash = record.compute_hash()
    return record


def make_spec(names=("buffett", "druckenmiller"), name="test"):
    return FundSpec(schema_version=2, name=name, strategies=[custom_strategy(list(names))],
                       risk={"max_position_pct": 0.25, "max_gross_exposure": 1})


def make_minute_spec(name="fast", interval=5, start="13:00", end="13:10"):
    return FundSpec(**{**make_spec(["pead"], name).model_dump(), "rebalance": "minute", "interval": interval,
                       "window": {"start": start, "end": end}})


def executed_and_decided():
    """A session that executed the 2025-01-15 decision (refreshed on the 19th,
    filled at the 20th's close) and made the next decision at that close."""
    record = make_cycle(make_signal())
    decision = DecisionRecord.model_validate(record.model_dump())
    decision.final_weights = {"TEST": .25}
    record.original_assessment = decision.model_copy(deep=True)
    record.refreshed_assessment = decision.model_copy(deep=True)
    record.refreshed_assessment.as_of = "2025-01-19"
    record.execution_as_of = "2025-01-20"
    record.execution_policy = "next_close"
    record.fills = [Fill(ticker="TEST", side="buy", quantity=10, price=100)]
    decided = decision.model_copy(deep=True)
    decided.as_of = "2025-01-20"
    return record, decided


def make_state(**kwargs):
    return FundState(cash=100000, **kwargs)


def make_pending(as_of="2025-01-17", weights=None):
    record, _ = executed_and_decided()
    decision = DecisionRecord.model_validate(record.model_dump())
    decision.as_of = as_of
    decision.final_weights = {"AAPL": .25, "MSFT": .25, "XOM": 0.0} if weights is None else weights
    return decision


def make_quote(ticker, price, time="2025-01-21T15:05:00Z"):
    return PriceSnapshot(ticker=ticker, price=price, time=time)
