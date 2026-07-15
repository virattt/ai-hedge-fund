"""Tests for end-of-day performance reporting."""

from __future__ import annotations

import json
from datetime import date

from integrations.alpaca import reporting
from integrations.alpaca.reporting import (
    PeriodReport,
    _fallback_advisory,
    _is_period_end,
    build_period_report,
    compute_realized_pnl,
    save_report,
)


def _fill(symbol: str, side: str, qty: float, price: float, ts: str) -> dict:
    return {"symbol": symbol, "side": side, "qty": qty, "price": price, "filled_at": ts}


class TestRealizedPnl:
    def test_long_round_trip(self) -> None:
        fills = [
            _fill("AAPL", "buy", 100, 10.0, "t1"),
            _fill("AAPL", "sell", 100, 12.0, "t2"),
        ]
        assert compute_realized_pnl(fills) == {"AAPL": 200.0}

    def test_partial_close_uses_average_cost(self) -> None:
        fills = [
            _fill("MSFT", "buy", 100, 10.0, "t1"),
            _fill("MSFT", "buy", 100, 20.0, "t2"),  # avg cost 15
            _fill("MSFT", "sell", 50, 18.0, "t3"),
        ]
        assert compute_realized_pnl(fills)["MSFT"] == 150.0  # 50 * (18 - 15)

    def test_short_round_trip(self) -> None:
        fills = [
            _fill("CP", "sell", 200, 90.0, "t1"),
            _fill("CP", "buy", 200, 88.0, "t2"),
        ]
        assert compute_realized_pnl(fills) == {"CP": 400.0}

    def test_flip_long_to_short_realizes_only_closed_leg(self) -> None:
        fills = [
            _fill("NVDA", "buy", 100, 200.0, "t1"),
            _fill("NVDA", "sell", 150, 210.0, "t2"),  # close 100, open 50 short @210
        ]
        assert compute_realized_pnl(fills)["NVDA"] == 1000.0

    def test_open_position_realizes_nothing(self) -> None:
        fills = [_fill("JPM", "buy", 60, 336.0, "t1")]
        assert compute_realized_pnl(fills) == {}


class TestPeriodBoundaries:
    def test_friday_ends_week(self) -> None:
        assert _is_period_end("weekly", date(2026, 7, 10))  # Friday
        assert not _is_period_end("weekly", date(2026, 7, 9))  # Thursday

    def test_last_trading_day_of_month(self) -> None:
        assert _is_period_end("monthly", date(2026, 7, 31))  # Friday, last of July
        assert not _is_period_end("monthly", date(2026, 7, 30))

    def test_year_end_weekend_aware(self) -> None:
        # Dec 31 2026 is a Thursday; Jan 1 2027 is a Friday (next weekday) -> year end.
        assert _is_period_end("yearly", date(2026, 12, 31))
        assert not _is_period_end("yearly", date(2026, 12, 30))


def _daily_report(day: str, *, pnl: float, equity_start: float, equity_end: float) -> PeriodReport:
    return PeriodReport(
        period="daily",
        start_date=day,
        end_date=day,
        equity_start=equity_start,
        equity_end=equity_end,
        pnl=pnl,
        pnl_pct=round(pnl / equity_start * 100, 4),
        fills=10,
        notional=50_000.0,
        realized_total=pnl,
        realized_by_symbol={"AAPL": pnl},
        winners=1 if pnl > 0 else 0,
        losers=0 if pnl > 0 else 1,
        unrealized_total=0.0,
        open_positions=[],
        cycles={"light": 5},
        turnover_x=0.5,
    )


class TestPeriodAggregation:
    def test_weekly_report_aggregates_dailies(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(reporting, "_REPORT_ROOT", tmp_path)
        save_report(_daily_report("2026-07-09", pnl=100.0, equity_start=100_000, equity_end=100_100))
        save_report(_daily_report("2026-07-10", pnl=-350.0, equity_start=100_100, equity_end=99_750))

        report = build_period_report("weekly", date(2026, 7, 10))

        assert report.trading_days == 2
        assert report.fills == 20
        assert report.notional == 100_000.0
        assert report.pnl == -250.0  # equity_start of first day -> equity_end of last
        assert report.realized_by_symbol["AAPL"] == -250.0
        assert report.cycles == {"light": 10}

    def test_period_report_without_dailies_raises(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(reporting, "_REPORT_ROOT", tmp_path)
        import pytest

        with pytest.raises(ValueError, match="No daily reports"):
            build_period_report("weekly", date(2026, 7, 10))

    def test_save_report_writes_json_and_markdown(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(reporting, "_REPORT_ROOT", tmp_path)
        report = _daily_report("2026-07-10", pnl=-262.0, equity_start=99_892, equity_end=99_630)
        report.advisory = "para one\n\npara two"

        md_path = save_report(report)

        assert md_path.exists()
        data = json.loads(md_path.with_suffix(".json").read_text(encoding="utf-8"))
        assert data["pnl"] == -262.0
        assert "para one" in md_path.read_text(encoding="utf-8")


class TestRoundTrips:
    def test_counts_round_trips_and_hold_time(self) -> None:
        from integrations.alpaca.reporting import compute_round_trips

        fills = [
            _fill("NVDA", "buy", 75, 210.0, "2026-07-13T15:04:00-04:00"),
            _fill("NVDA", "sell", 75, 209.0, "2026-07-13T15:38:00-04:00"),
            _fill("JPM", "buy", 60, 336.0, "2026-07-13T14:00:00-04:00"),  # still open
        ]
        trips, avg_hold = compute_round_trips(fills)

        assert trips == 1
        assert avg_hold == 34.0

    def test_digest_never_mislabels_winners_as_losers(self) -> None:
        from integrations.alpaca.reporting import _report_digest

        report = _daily_report("2026-07-13", pnl=50.0, equity_start=99_000, equity_end=99_050)
        report.realized_by_symbol = {"GOOGL": 14.0, "AAPL": 30.0}  # all positive

        digest = _report_digest(report)

        assert "Top losers: none" in digest
        assert "GOOGL" not in digest.split("Top losers:")[1].split("\n")[0]


class TestAdvisory:
    def test_fallback_advisory_is_two_paragraphs(self) -> None:
        report = _daily_report("2026-07-10", pnl=-262.0, equity_start=99_892, equity_end=99_630)
        report.turnover_x = 15.1
        report.winners, report.losers = 15, 20

        advisory = _fallback_advisory(report)

        paragraphs = [p for p in advisory.split("\n\n") if p.strip()]
        assert len(paragraphs) == 2
        assert "turnover" in advisory


class TestDaemonGating:
    def test_session_default_has_no_report_done(self) -> None:
        from integrations.alpaca.session import TradingSessionState

        state = TradingSessionState(trading_day="2026-07-10")
        assert state.eod_report_done is False
