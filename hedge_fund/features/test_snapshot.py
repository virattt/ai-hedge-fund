"""FundamentalsSnapshot tests — mocked data client, no network."""

import re

import pytest

from hedge_fund.data.models import CompanyFacts, FinancialMetrics
from hedge_fund.features.breakpoints import MEBreakpoints
from hedge_fund.features.snapshot import InsufficientData, build_snapshot

# One published month (Nov 2024) with thresholds 100M, 200M, ..., 2000M. The
# canned history files t-0 on 2024-12-31, so this is the row it lands on.
BREAKPOINTS = MEBreakpoints({"202411": tuple(100.0 * i for i in range(1, 21))})


class MockDataClient:
    """Returns canned metrics; records what it was asked for."""

    def __init__(self, metrics=None, facts=None):
        self._metrics = metrics or []
        self._facts = facts
        self.metrics_calls = []

    def get_financial_metrics(self, ticker, end_date, period="ttm", limit=10):
        self.metrics_calls.append(
            {"ticker": ticker, "end_date": end_date, "period": period, "limit": limit}
        )
        return self._metrics

    def get_company_facts(self, ticker):
        return self._facts


def _metric(report_period, **kwargs):
    defaults = {
        "ticker": "TEST",
        "period": "ttm",
        "filing_date": report_period,  # simplification for tests
        "return_on_equity": 0.20,
        "net_margin": 0.25,
        "gross_margin": 0.40,
        "book_value_per_share": 10.0,
        "debt_to_equity": 0.5,
        "market_cap": 1e9,
    }
    defaults.update(kwargs)
    return FinancialMetrics(report_period=report_period, **defaults)


def _history(n=8):
    """n periods, newest first, quarter-spaced."""
    quarters = ["2024-12-31", "2024-09-30", "2024-06-30", "2024-03-31",
                "2023-12-31", "2023-09-30", "2023-06-30", "2023-03-31"]
    return [_metric(q) for q in quarters[:n]]


def test_as_of_passes_through_to_data_client():
    client = MockDataClient(metrics=_history())
    build_snapshot("TEST", "2025-01-15", client)
    call = client.metrics_calls[0]
    assert call["end_date"] == "2025-01-15"
    assert call["ticker"] == "TEST"


def test_insufficient_data_raises():
    client = MockDataClient(metrics=_history(3))  # below MIN_PERIODS
    with pytest.raises(InsufficientData):
        build_snapshot("TEST", "2025-01-15", client)


def test_aggregates():
    metrics = _history(4)
    # oldest gross margin 0.30, newest 0.40 -> trend +0.10
    metrics[-1] = _metric("2024-03-31", gross_margin=0.30)
    # BVPS oldest 8.0 -> newest 10.0 over 3 quarters (0.75y)
    metrics[-1].book_value_per_share = 8.0
    client = MockDataClient(metrics=metrics)

    snap = build_snapshot("TEST", "2025-01-15", client)

    assert snap.roe_avg == pytest.approx(0.20)
    assert snap.gross_margin_trend == pytest.approx(0.10)
    assert snap.debt_to_equity_latest == pytest.approx(0.5)
    assert snap.market_cap_latest == pytest.approx(1e9)
    assert snap.bvps_cagr == pytest.approx((10.0 / 8.0) ** (1 / 0.75) - 1, abs=1e-4)


def test_market_cap_comes_from_pit_metrics_not_facts():
    """company_facts market cap is latest-only (lookahead); the snapshot must
    use the most recent FILED metrics row instead."""
    facts = CompanyFacts(ticker="TEST", sector="Tech")
    client = MockDataClient(metrics=_history(), facts=facts)

    snap = build_snapshot("TEST", "2020-06-30", client)

    assert snap.market_cap_latest == pytest.approx(1e9)  # from metrics row
    assert snap.sector == "Tech"  # facts used only for slow-moving attributes


def test_content_hash_stable_and_sensitive():
    client_a = MockDataClient(metrics=_history())
    client_b = MockDataClient(metrics=_history())
    snap_a = build_snapshot("TEST", "2025-01-15", client_a)
    snap_b = build_snapshot("TEST", "2025-01-15", client_b)
    assert snap_a.content_hash == snap_b.content_hash  # same data -> same key

    changed = _history()
    changed[0] = _metric("2024-12-31", return_on_equity=0.35)
    snap_c = build_snapshot("TEST", "2025-01-15", MockDataClient(metrics=changed))
    assert snap_c.content_hash != snap_a.content_hash  # new filing -> new key


def test_same_data_different_as_of_same_render_and_hash():
    """Between filings the snapshot is unchanged — the hash and the rendered
    prompt must be identical on any as-of date, or the LLM cache never hits."""
    snap_jan = build_snapshot("TEST", "2025-01-15", MockDataClient(metrics=_history()))
    snap_feb = build_snapshot("TEST", "2025-02-15", MockDataClient(metrics=_history()))

    assert snap_jan.as_of != snap_feb.as_of  # the field itself still differs
    assert snap_jan.content_hash == snap_feb.content_hash
    assert snap_jan.render() == snap_feb.render()
    assert snap_jan.render(blind=True) == snap_feb.render(blind=True)


def test_render_contains_the_facts():
    snap = build_snapshot("TEST", "2025-01-15", MockDataClient(metrics=_history()))
    text = snap.render()
    assert "2025-01-15" not in text  # as_of must never leak into the prompt
    assert "2024-12-31" in text
    assert "publicly filed" in text


def test_blind_render_withholds_ticker_dates_and_dollars():
    """Blind mode drops what lets a model recall the outcome: the ticker,
    every report/filing date, absolute size, and per-share dollar values.
    The per-share series survive as an index on the oldest period."""
    facts = CompanyFacts(ticker="TEST", sector="Tech", industry="Widgets")
    # Newest first. t-0 EPS 5.00 vs t-4 EPS 2.50 is +100% yoy. Oldest EPS is
    # 2.00, so t-0 indexes to 250. BVPS and FCF/sh are flat, so they index
    # to 100. Market cap would render as 3200.0B if it leaked.
    earnings = [5.0, 4.5, 4.0, 3.5, 2.5, 2.2, 2.0, 2.0]
    metrics = _history()
    for metric, earning in zip(metrics, earnings):
        metric.market_cap = 3_200_000_000_000
        metric.earnings_per_share = earning
        metric.book_value_per_share = 40.0
        metric.free_cash_flow_per_share = 3.25
    snap = build_snapshot("TEST", "2025-01-15", MockDataClient(metrics=metrics, facts=facts))
    text = snap.render(blind=True)
    shown = snap.render()

    assert "TEST" not in text
    assert "Widgets" not in text  # industry narrows it down too much
    assert "Sector: Tech" in text
    for quarter in ("2024-12-31", "2024-06-30", "2023-03-31"):
        assert quarter not in text
    assert "t-0 | " in text and "t-7 | " in text
    assert "Market cap" not in text
    assert "mktcap" not in text
    assert re.search(r"\d+(?:\.\d+)?[BM]\b", text) is None
    for raw in ("5.00", "40.00", "3.25", "3200.0B"):
        assert raw not in text
        assert raw in shown  # the live prompt still names the dollars
    assert "eps_idx" in text and "bvps_idx" in text and "fcf_idx" in text
    t0 = _cells(next(line for line in text.splitlines() if line.startswith("t-0 |")))
    t7 = _cells(next(line for line in text.splitlines() if line.startswith("t-7 |")))
    assert t0[9:13] == ["250.0", "100.0", "100.0", "1.00"]  # eps yoy only on t-0
    assert t7[9:13] == ["100.0", "100.0", "100.0", "-"]
    assert "Market cap (latest filed): 3200.0B" in shown


def test_blind_size_is_a_percentile_only_when_breakpoints_are_given():
    """$1.5B against 100M..2000M thresholds meets 15 of 20 -> 75th percentile.
    The live prompt never shows the percentile; without a table the blind
    prompt shows no size at all."""
    metrics = _history()
    for metric in metrics:
        metric.market_cap = 1_500_000_000
    with_table = build_snapshot("TEST", "2025-01-15", MockDataClient(metrics=metrics),
                                breakpoints=BREAKPOINTS)
    without = build_snapshot("TEST", "2025-01-15", MockDataClient(metrics=metrics))

    assert with_table.size_percentile == 75
    assert "Size: market cap at or above the 75th percentile of US stocks" in with_table.render(blind=True)
    assert "1.5B" not in with_table.render(blind=True)
    assert "percentile" not in with_table.render()
    assert "Market cap (latest filed): 1.5B" in with_table.render()

    assert without.size_percentile is None
    assert "Size:" not in without.render(blind=True)


def test_blind_size_below_the_fifth_percentile_and_missing_cap():
    tiny = _history()
    for metric in tiny:
        metric.market_cap = 10_000_000
    snap = build_snapshot("TEST", "2025-01-15", MockDataClient(metrics=tiny), breakpoints=BREAKPOINTS)
    assert snap.size_percentile == 0
    assert "Size: market cap below the 5th percentile of US stocks" in snap.render(blind=True)

    unknown = _history()
    for metric in unknown:
        metric.market_cap = None
    snap = build_snapshot("TEST", "2025-01-15", MockDataClient(metrics=unknown), breakpoints=BREAKPOINTS)
    assert snap.size_percentile is None
    assert "Size:" not in snap.render(blind=True)


def test_eps_growth_yoy():
    growing = _history(8)
    for i, metric in enumerate(growing):
        metric.earnings_per_share = float(8 - i)  # t-0 = 8, t-4 = 4
    snap = build_snapshot("TEST", "2025-01-15", MockDataClient(metrics=growing))
    assert snap.eps_growth_yoy == pytest.approx(1.0)

    # Four periods have no t-4 to compare against.
    short = _history(4)
    for metric in short:
        metric.earnings_per_share = 2.0
    assert build_snapshot("TEST", "2025-01-15", MockDataClient(metrics=short)).eps_growth_yoy is None

    # A non-positive year-ago EPS has no meaningful growth rate.
    loss = _history(8)
    for metric in loss:
        metric.earnings_per_share = 2.0
    loss[4].earnings_per_share = -1.0
    assert build_snapshot("TEST", "2025-01-15", MockDataClient(metrics=loss)).eps_growth_yoy is None


def test_blind_index_dashes_without_a_positive_base_and_keeps_sign():
    metrics = _history(4)
    for metric in metrics:
        metric.earnings_per_share = 2.0
        metric.book_value_per_share = -5.0  # non-positive base -> dashed
    metrics[0].earnings_per_share = -1.0  # sign survives: -1 / 2 * 100
    text = build_snapshot("TEST", "2025-01-15", MockDataClient(metrics=metrics)).render(blind=True)
    t0 = _cells(next(line for line in text.splitlines() if line.startswith("t-0 |")))
    assert t0[9:12] == ["-50.0", "-", "-"]


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.split("|")]


def test_blind_render_is_opt_in():
    snap = build_snapshot("TEST", "2025-01-15", MockDataClient(metrics=_history()))
    assert snap.render() == snap.render(blind=False)
    assert "Company: TEST" in snap.render()
