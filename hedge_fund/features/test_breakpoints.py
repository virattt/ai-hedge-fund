"""Market-cap breakpoints tests — canned CSV, no network."""

import os
import time

import pytest

from hedge_fund.features.breakpoints import MEBreakpoints, load_breakpoints


def _row(month: str, start: int) -> str:
    """20 thresholds in $ millions: start, 2*start, ..., 20*start."""
    values = ", ".join(f"{start * i:.2f}" for i in range(1, 21))
    return f"{month}, 1100, {values}"


SAMPLE = "\n".join([
    "This file contains every 5th market-cap percentile (divided by 1000000).",
    "",
    _row("202405", 100),
    _row("202406", 110),
    _row("202407", 120),
    "",
    "Copyright footer line",
])


def test_parse_skips_prose_and_keeps_every_month():
    table = MEBreakpoints.parse(SAMPLE)
    assert table.latest_month == "202407"
    month, thresholds = table.row_for("2024-08-15")
    assert month == "202407"
    assert thresholds[0] == pytest.approx(120.0) and thresholds[-1] == pytest.approx(2400.0)


def test_parse_empty_raises():
    with pytest.raises(ValueError):
        MEBreakpoints.parse("no rows here")


def test_row_is_the_latest_month_strictly_before_the_filing_month():
    """Month M's breakpoints use end-of-M prices — not knowable inside M."""
    table = MEBreakpoints.parse(SAMPLE)
    assert table.row_for("2024-07-15")[0] == "202406"
    assert table.row_for("2024-07-01")[0] == "202406"
    assert table.row_for("2024-12-31")[0] == "202407"  # gap: fall back to latest published
    assert table.row_for("2024-05-20") is None  # nothing published before May


def test_size_percentile_counts_thresholds_met():
    table = MEBreakpoints.parse(SAMPLE)
    # Filed in July -> June row: thresholds 110M, 220M, ..., 2200M.
    assert table.size_percentile(1_500_000_000, "2024-07-15") == 65   # >= 13 of them
    assert table.size_percentile(110_000_000, "2024-07-15") == 5      # exactly the 5th
    assert table.size_percentile(50_000_000, "2024-07-15") == 0       # below the 5th
    assert table.size_percentile(2_200_000_000, "2024-07-15") == 95   # meets all 20, capped
    assert table.size_percentile(3_000_000_000_000, "2024-07-15") == 95
    assert table.size_percentile(None, "2024-07-15") is None
    assert table.size_percentile(0.0, "2024-07-15") is None
    assert table.size_percentile(1_500_000_000, "2024-05-20") is None  # no row


def test_load_fetches_once_then_reads_the_cache(tmp_path):
    calls = []

    def fetch():
        calls.append(1)
        return SAMPLE

    path = tmp_path / "breakpoints" / "ME_Breakpoints.csv"
    first = load_breakpoints(path, fetch=fetch)
    second = load_breakpoints(path, fetch=fetch)
    assert calls == [1]
    assert path.exists()
    assert first.latest_month == second.latest_month == "202407"


def test_load_refreshes_a_stale_cache(tmp_path):
    path = tmp_path / "ME_Breakpoints.csv"
    path.write_text(SAMPLE)
    old = time.time() - 40 * 86400
    os.utime(path, (old, old))

    newer = SAMPLE.replace("Copyright", _row("202408", 130) + "\nCopyright")
    table = load_breakpoints(path, fetch=lambda: newer)
    assert table.latest_month == "202408"
    assert "202408" in path.read_text()


def test_load_keeps_a_stale_cache_when_the_fetch_fails(tmp_path):
    path = tmp_path / "ME_Breakpoints.csv"
    path.write_text(SAMPLE)
    old = time.time() - 40 * 86400
    os.utime(path, (old, old))

    def fetch():
        raise ConnectionError("offline")

    assert load_breakpoints(path, fetch=fetch).latest_month == "202407"


def test_load_raises_with_no_cache_and_no_fetch(tmp_path):
    def fetch():
        raise ConnectionError("offline")

    with pytest.raises(ConnectionError):
        load_breakpoints(tmp_path / "missing.csv", fetch=fetch)
