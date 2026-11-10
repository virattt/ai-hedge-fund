import json
import traceback
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

import pytest

from hedge_fund import research

CUTOFF = "2026-11-05T16:00:00Z"
SOURCE = {"source_url": "https://example.com/research", "published_at": None, "source_coverage": "partial"}
COVERAGE = {
    "schema_version": "1", "resource": "beliefs", "as_of": CUTOFF, "tickers": ["NBIS"],
    "coverage": [{"ticker": "NBIS", "security_name": "Example Company"}],
    "discovery": {"results": [
        {"ticker": "NBIS", "name": "Example Company", "direct_research": True, "exchange": "Nasdaq"},
        {"ticker": "OTHER", "name": "Another Company", "direct_research": False, "exchange": "NYSE"},
    ]},
}
BRIEF = {
    "schema_version": "1", "resource": "brief", "view": "current", "as_of": CUTOFF,
    "scope": {"ticker": "NBIS"},
    "beliefs": [{
        "person": {"name": "Example Investor"}, "thesis": "Expansion depends on financing.", "direction": "neutral",
        "evidence": [SOURCE], "qualifications": ["The source is partial."],
        "risks": [{
            "statement": "Financing may dilute shareholders.", "status": "unknown", "evidence": [SOURCE],
            "checking_evidence": [SOURCE], "unknowns": [{"field": "severity", "reason": "Not assessed."}],
        }],
        "catalysts": [{"statement": "Next earnings release.", "status": "pending"}],
        "unknowns": [{"field": "confidence", "reason": "The author did not state it."}],
        "omitted_risk_count": 2, "omitted_catalyst_count": 1,
        "detail_url": "https://beliefstate.ai/v1/belief?id=example",
    }],
    "coverage": {"completeness": "bounded", "omitted_belief_count": 4},
    "warnings": ["The brief has bounded coverage."],
    "quality_gaps": [{"reason": "reviewed_compact_case_missing", "detail_url": "https://example.com/missing"}],
    "detail_reference": "get_beliefs",
}


def stub_http(monkeypatch, *responses):
    connections = []
    for status, payload in responses:
        connection = Mock()
        connection.getresponse.return_value.status = status
        connection.getresponse.return_value.read.return_value = json.dumps(payload).encode()
        connections.append(connection)
    factory = Mock(side_effect=connections)
    monkeypatch.setattr(research, "HTTPSConnection", factory)
    return factory, connections


def test_search_is_free_and_merges_company_identity_with_research_coverage(monkeypatch):
    factory, (free,) = stub_http(monkeypatch, (200, COVERAGE))
    client = research.BeliefStateClient("fixture-secret")
    companies = client.search(" example company ")
    assert [(company.ticker, company.direct_research) for company in companies] == [("NBIS", True), ("OTHER", False)]
    free.request.assert_called_once_with("GET", "/v1/tickers?q=example+company", headers={"Accept": "application/json"})
    factory.assert_called_once_with("beliefstate.ai", timeout=15)
    free.close.assert_called_once()


def test_current_read_reuses_free_search_and_fresh_brief_without_another_debit(monkeypatch):
    factory, (free, paid, _, _) = stub_http(monkeypatch, (200, COVERAGE), (200, BRIEF), (200, COVERAGE), (200, BRIEF))
    clock = [100]
    monkeypatch.setattr(research, "monotonic", lambda: clock[0])
    client = research.BeliefStateClient("fixture-secret")
    client.search("nbis")
    result = client.read("NBIS", cancelled=lambda: False)
    assert result.scope.ticker == "NBIS" and result.beliefs[0].direction == "neutral"
    assert result.beliefs[0].evidence[0].published_at is None
    assert factory.call_count == 2
    method, url = paid.request.call_args.args
    assert method == "GET" and urlsplit(url).path == "/v1/brief"
    assert parse_qs(urlsplit(url).query) == {"ticker": ["NBIS"], "detail": ["current"], "max_results": ["3"]}
    headers = paid.request.call_args.kwargs["headers"]
    assert headers["Authorization"] == "Bearer fixture-secret"
    assert UUID(headers["X-Request-ID"]).version == 4
    assert factory.call_args.kwargs == {"timeout": 45}
    clock[0] = 159
    assert client.read("nbis", cancelled=lambda: False) is result
    assert factory.call_count == 2
    clock[0] = 161
    client.read("NBIS", cancelled=lambda: False)
    assert factory.call_count == 4


def test_missing_coverage_and_missing_key_never_send_a_metered_request(monkeypatch):
    factory, _ = stub_http(monkeypatch, (200, COVERAGE), (200, COVERAGE))
    client = research.BeliefStateClient()
    assert client.read("OTHER", cancelled=lambda: False) is None
    with pytest.raises(research.ResearchError, match="BELIEFSTATE_API_KEY"):
        client.read("NBIS", cancelled=lambda: False)
    assert factory.call_count == 2


def test_cancelling_during_free_discovery_prevents_the_metered_read(monkeypatch):
    factory, (free,) = stub_http(monkeypatch, (200, COVERAGE))
    cancelled = []
    def receive(_limit):
        cancelled.append(True)
        return json.dumps(COVERAGE).encode()
    free.getresponse.return_value.read.side_effect = receive
    with pytest.raises(research.ResearchError, match="cancelled"):
        research.BeliefStateClient("fixture-secret").read("NBIS", cancelled=lambda: bool(cancelled))
    factory.assert_called_once()


@pytest.mark.parametrize("status", [302, 401, 402, 403, 404, 409, 429, 503])
def test_metered_errors_preserve_request_id_and_do_not_retry(monkeypatch, status):
    factory, (_, paid) = stub_http(monkeypatch, (200, COVERAGE), (status, {"secret": "fixture-secret"}))
    with pytest.raises(research.ResearchError, match=f"HTTP {status}") as failure:
        research.BeliefStateClient("fixture-secret").read("NBIS", cancelled=lambda: False)
    assert paid.request.call_args.kwargs["headers"]["X-Request-ID"] in str(failure.value)
    assert "fixture-secret" not in str(failure.value)
    assert factory.call_count == 2
    paid.request.assert_called_once()


@pytest.mark.parametrize("payload", [
    {**BRIEF, "scope": {"ticker": "OTHER"}},
    {**BRIEF, "view": "overview"},
    {**BRIEF, "as_of": "9999-01-01T00:00:00Z"},
    {**BRIEF, "beliefs": [{**BRIEF["beliefs"][0], "evidence": [{**SOURCE, "published_at": "2026-11-06T16:00:00Z"}]}]},
    {**BRIEF, "beliefs": [{**BRIEF["beliefs"][0], "evidence": [{**SOURCE, "source_url": "javascript:alert(1)"}]}]},
])
def test_invalid_briefs_fail_with_request_id_without_echoing_payload(monkeypatch, payload):
    factory, _ = stub_http(monkeypatch, (200, COVERAGE), (200, payload))
    with pytest.raises(research.ResearchError, match="Request ID"):
        research.BeliefStateClient("fixture-secret").read("NBIS", cancelled=lambda: False)
    assert factory.call_count == 2


def test_discovery_flag_does_not_override_absent_released_coverage(monkeypatch):
    payload = {**COVERAGE, "tickers": [], "coverage": []}
    factory, _ = stub_http(monkeypatch, (200, payload), (200, payload))
    assert research.BeliefStateClient("fixture-secret").read("NBIS", cancelled=lambda: False) is None
    assert factory.call_count == 2


def test_no_fit_preserves_coverage_limits_and_warnings(monkeypatch):
    payload = {**BRIEF, "beliefs": [], "coverage": {"completeness": "no_fit", "omitted_belief_count": 0}}
    factory, _ = stub_http(monkeypatch, (200, COVERAGE), (200, payload))
    result = research.BeliefStateClient("fixture-secret").read("NBIS", cancelled=lambda: False)
    assert result.coverage.completeness == "no_fit" and result.warnings == BRIEF["warnings"]
    assert factory.call_count == 2


def test_failed_transport_does_not_expose_rejected_authorization_header(monkeypatch):
    _, (_, paid) = stub_http(monkeypatch, (200, COVERAGE), (200, BRIEF))
    secret = "fixture-secret"
    paid.request.side_effect = ValueError(f"invalid header {secret}")
    with pytest.raises(research.ResearchError, match="Request ID") as failure:
        research.BeliefStateClient(secret).read("NBIS", cancelled=lambda: False)
    assert secret not in "".join(traceback.format_exception(failure.value))
    paid.close.assert_called_once()


def test_concurrent_reads_of_one_ticker_share_one_metered_response(monkeypatch):
    factory, (free, _) = stub_http(monkeypatch, (200, COVERAGE), (200, BRIEF))
    started, release = Event(), Event()
    def receive(_limit):
        started.set()
        assert release.wait(5)
        return json.dumps(COVERAGE).encode()
    free.getresponse.return_value.read.side_effect = receive
    client = research.BeliefStateClient("fixture-secret")
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(client.read, "NBIS", cancelled=lambda: False)
        assert started.wait(5)
        second = executor.submit(client.read, "NBIS", cancelled=lambda: False)
        release.set()
        assert first.result(5) is second.result(5)
    assert factory.call_count == 2


@pytest.mark.parametrize("ticker", ["A", "GOOGL", "BRK-B", "BRK.B", "005930.KS", "0700.HK", "VOW3.DE", "ABC-P-A"])
def test_covered_stock_symbols_pass_through_unchanged(monkeypatch, ticker):
    coverage = {**COVERAGE, "tickers": [ticker], "coverage": [{"ticker": ticker, "security_name": "Example Company"}], "discovery": {"results": []}}
    brief = {**BRIEF, "scope": {"ticker": ticker}}
    factory, (_, paid) = stub_http(monkeypatch, (200, coverage), (200, brief))
    result = research.BeliefStateClient("fixture-secret").read(ticker.lower(), cancelled=lambda: False)
    assert result.scope.ticker == ticker
    assert parse_qs(urlsplit(paid.request.call_args.args[1]).query)["ticker"] == [ticker]
    assert factory.call_count == 2


def test_directory_outage_cannot_hide_released_research_or_duplicate_its_charge(monkeypatch):
    factory, _ = stub_http(monkeypatch, (503, {}), (200, COVERAGE), (200, BRIEF))
    client = research.BeliefStateClient("fixture-secret")
    result = client.read("NBIS", cancelled=lambda: False)
    assert result.beliefs[0].thesis == BRIEF["beliefs"][0]["thesis"]
    assert client.read("NBIS", cancelled=lambda: False) is result
    assert factory.call_count == 3


def test_directory_outage_with_no_library_match_stays_an_error_and_unpaid(monkeypatch):
    factory, _ = stub_http(monkeypatch, (503, {}), (200, COVERAGE))
    with pytest.raises(research.ResearchError, match="HTTP 503"):
        research.BeliefStateClient("fixture-secret").read("UNKNOWN", cancelled=lambda: False)
    assert factory.call_count == 2


def test_valid_directory_results_survive_a_library_outage(monkeypatch):
    uncovered = {**COVERAGE, "tickers": [], "coverage": []}
    factory, _ = stub_http(monkeypatch, (200, uncovered), (503, {}))
    companies = research.BeliefStateClient().search("Another")
    assert any(company.ticker == "OTHER" for company in companies)
    assert not any(company.direct_research for company in companies)
    assert factory.call_count == 2


def test_empty_directory_with_unavailable_library_stays_an_error(monkeypatch):
    empty = {**COVERAGE, "tickers": [], "coverage": [], "discovery": {"results": []}}
    factory, _ = stub_http(monkeypatch, (200, empty), (503, {}))
    with pytest.raises(research.ResearchError, match="HTTP 503"):
        research.BeliefStateClient().search("Unknown")
    assert factory.call_count == 2


def test_missing_coverage_does_not_extend_the_original_search_expiry(monkeypatch):
    missing = {**COVERAGE, "tickers": ["OTHERX"], "coverage": [{"ticker": "OTHERX", "security_name": "Another Company"}]}
    available = {**COVERAGE, "tickers": ["OTHER"], "coverage": [{"ticker": "OTHER", "security_name": "Another Company"}]}
    brief = {**BRIEF, "scope": {"ticker": "OTHER"}}
    factory, _ = stub_http(monkeypatch, (200, missing), (200, available), (200, brief))
    clock = [100]
    monkeypatch.setattr(research, "monotonic", lambda: clock[0])
    client = research.BeliefStateClient("fixture-secret")
    client.search("OTHER")
    clock[0] = 159
    assert client.read("OTHER", cancelled=lambda: False) is None
    clock[0] = 161
    assert client.read("OTHER", cancelled=lambda: False).scope.ticker == "OTHER"
    assert factory.call_count == 3


def test_partial_foreign_names_use_the_library_and_keep_its_original_expiry(monkeypatch):
    empty = {**COVERAGE, "tickers": [], "coverage": [], "discovery": {"results": []}}
    foreign = {**COVERAGE, "tickers": ["005930.KS"], "coverage": [{"ticker": "005930.KS", "security_name": "Example Overseas Company"}], "discovery": None}
    factory, _ = stub_http(monkeypatch, (200, empty), (200, foreign), (200, empty), (200, empty), (200, foreign))
    clock = [100]
    monkeypatch.setattr(research, "monotonic", lambda: clock[0])
    client = research.BeliefStateClient()
    assert client.search("Overseas")[0].ticker == "005930.KS"
    clock[0] = 159
    assert client.search("005930")[0].direct_research
    clock[0] = 161
    assert client.search("005930")[0].direct_research
    assert factory.call_count == 5
