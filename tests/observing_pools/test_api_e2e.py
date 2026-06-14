"""End-to-end vertical-slice test through the real API (PRD v4 §17).

Offline (stubbed committee + analyzing flow, no LLM/network): runs the full
pipeline → Serenity grading → monitor, then serves it via the FastAPI routes and
asserts the disclaimer invariant survives to the API surface. This is the Phase-0
acceptance gate in one test.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import src.storage.models as m
from app.backend.database.connection import get_db
from app.backend.routes.observing_pools import router
from src.integrations.tradingagents_adapter import AnalyzingFlowResult
from src.monitoring.runner import create_monitor, run_monitor
from src.observing_pools.pipeline import RefreshConfig, refresh_pool
from src.serenity.integrate import apply_serenity_to_pool
from src.serenity.research import build_record
from src.storage.models import ReportLabel

UNIVERSE = "data/universes/ai_seed.csv"


def _stub_committee(quality):
    def stub(tickers, selected, end_date):
        signals = {f"{k}_agent": {} for k in selected}
        for t in tickers:
            q = quality.get(t, 55)
            for k in selected:
                signals[f"{k}_agent"][t] = {"signal": "bullish", "confidence": q}
        return signals, {"calls": len(selected) * len(tickers)}

    return stub


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    m.Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    # ---- populate: refresh → serenity → apply → monitor (all offline) ----
    s = Session()
    refresh_pool(
        s,
        RefreshConfig(platform_key="ai", universe_csv=UNIVERSE, top_n=10, token_budget=100_000),
        _stub_committee({"NVDA": 92, "MSFT": 80, "TSLA": 75}),
        end_date="2026-06-12",
    )
    build_record(
        s,
        theme="AI accelerator packaging",
        ticker="NVDA",
        platform_key="ai",
        scorecard={"supplier_concentration": 4, "validation_cycle": 4, "capacity_expansion": 4, "certification_strictness": 3, "purity_precision": 3},
        references=[
            {"source_url": "https://www.sec.gov/a", "claim_summary": "CoWoS capacity constrains NVIDIA H100 packaging supply", "excerpt": "CoWoS advanced packaging capacity constrains NVIDIA H100 packaging supply per the 10-K filing"},
            {"source_url": "https://patents.google.com/b", "claim_summary": "CoWoS packaging integration method NVIDIA", "excerpt": "A CoWoS packaging integration method for high bandwidth memory on NVIDIA accelerators improves yield"},
        ],
    )
    apply_serenity_to_pool(s, "ai")
    monitor = create_monitor(s, name="AI weekly", tickers=["NVDA"])
    run_monitor(
        s,
        monitor,
        trade_date="2026-06-12",
        analyzing_flow=lambda t, d: AnalyzingFlowResult(t, ReportLabel.THESIS_SUPPORTIVE, 70.0, False, f"{t} thesis intact", raw_decision="Buy"),
    )
    s.commit()
    s.close()

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_platforms_endpoint(client):
    resp = client.get("/innovation-platforms")
    assert resp.status_code == 200
    keys = {p["key"] for p in resp.json()}
    assert keys == {"ai", "robotics", "energy_storage", "blockchain", "multiomic_sequencing"}


def test_pool_endpoint_ranked_with_serenity(client):
    resp = client.get("/observing-pools/ai")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] >= 1
    top = body["entries"][0]
    assert top["ticker"] == "NVDA"  # highest committee confidence + serenity evidence
    assert top["composite_formula_version"] == "v3-5comp"  # serenity applied
    assert top["components"]["serenity_bottleneck"] is not None
    assert top["rank"] == 1


def test_unknown_platform_404(client):
    assert client.get("/observing-pools/not_a_platform").status_code == 404


def test_reports_carry_disclaimer(client):
    resp = client.get("/opportunity-reports")
    assert resp.status_code == 200
    reports = resp.json()
    assert len(reports) == 1
    r = reports[0]
    assert r["ticker"] == "NVDA"
    assert r["label"] == ReportLabel.THESIS_SUPPORTIVE.value
    assert r["disclaimer"] and r["disclaimer_version"]  # invariant survives to the API
