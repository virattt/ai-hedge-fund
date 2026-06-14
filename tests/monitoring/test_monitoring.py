"""Monitoring + adapter tests (PRD v4 §9.7, §12, §17).

Covers the disclaimer serialization invariant, the descriptive-label mapping,
the degraded fallback (never a fabricated signal), and a full monitor run with a
stubbed analyzing flow (no TradingAgents subprocess, no LLM).
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.storage.models as m
from src.integrations.tradingagents_adapter import (
    AnalyzingFlowResult,
    map_runner_payload,
)
from src.monitoring.runner import create_monitor, run_monitor
from src.monitoring.serialize import DisclaimerError, serialize_report
from src.storage.models import ReportLabel


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    m.Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


# ── serialization invariant ─────────────────────────────────────────────────


def test_serialize_rejects_missing_disclaimer(session):
    report = m.OpportunityReport(ticker="NVDA", label=ReportLabel.MIXED.value, disclaimer="", disclaimer_version="")
    with pytest.raises(DisclaimerError):
        serialize_report(report)


def test_serialize_passes_with_disclaimer(session):
    report = m.OpportunityReport(ticker="NVDA", label=ReportLabel.MIXED.value, disclaimer="research only", disclaimer_version="2026-06")
    out = serialize_report(report)
    assert out["disclaimer"] == "research only" and out["disclaimer_version"] == "2026-06"
    assert out["ticker"] == "NVDA"


# ── adapter mapping (pure) ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    "decision,expected",
    [
        ("Buy", ReportLabel.THESIS_SUPPORTIVE),
        ("Overweight", ReportLabel.THESIS_SUPPORTIVE),
        ("Hold", ReportLabel.MIXED),
        ("Underweight", ReportLabel.THESIS_CHALLENGING),
        ("Sell", ReportLabel.THESIS_CHALLENGING),
    ],
)
def test_rating_maps_to_descriptive_label(decision, expected):
    res = map_runner_payload("NVDA", {"ok": True, "decision": decision, "reports": {}})
    assert res.label == expected and res.degraded is False


def test_runner_error_is_degraded_not_fabricated():
    res = map_runner_payload("NVDA", {"ok": False, "error": "no api key"})
    assert res.degraded is True
    assert res.label == ReportLabel.INSUFFICIENT_EVIDENCE
    assert res.confidence == 0.0  # never an optimistic default


# ── monitor run (stubbed flow) ──────────────────────────────────────────────


def test_run_monitor_persists_disclaimer_reports(session):
    def stub_flow(ticker, trade_date):
        if ticker == "BAD":
            return AnalyzingFlowResult(ticker, ReportLabel.INSUFFICIENT_EVIDENCE, 0.0, True, "Analysis unavailable.")
        return AnalyzingFlowResult(ticker, ReportLabel.THESIS_SUPPORTIVE, 70.0, False, f"{ticker} thesis intact", raw_decision="Buy")

    monitor = create_monitor(session, name="AI weekly", tickers=["NVDA", "BAD"], granularity="weekly")
    result = run_monitor(session, monitor, trade_date="2026-06-12", analyzing_flow=stub_flow)
    session.commit()

    assert len(result.reports) == 2
    assert all(r["disclaimer"] and r["disclaimer_version"] for r in result.reports)  # invariant held
    by_ticker = {r["ticker"]: r for r in result.reports}
    assert by_ticker["NVDA"]["label"] == ReportLabel.THESIS_SUPPORTIVE.value
    assert by_ticker["BAD"]["degraded"] is True
    assert by_ticker["BAD"]["label"] == ReportLabel.INSUFFICIENT_EVIDENCE.value
    # persisted
    assert session.query(m.OpportunityReport).count() == 2
