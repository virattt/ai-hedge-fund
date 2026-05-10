"""Event study engine — compute CARs around earnings announcements.

This is the main orchestration module. The pipeline:

    1. Fetch SPY prices once (market benchmark for all tickers).
    2. For each ticker:
       a. Get earnings history from FD API.
       b. Filter out retrospective rows (45-day rule).
       c. Fetch stock prices (one call per ticker, wide date range).
       d. Build aligned return series (stock ∩ SPY trading days).
       e. For each earnings event:
          - Fit market model on estimation window [-250, -11].
          - Compute abnormal returns on event window [0, +20].
          - Sum to get CARs for [0,+1], [0,+5], [0,+20].
    3. Aggregate CARs cross-sectionally, segmented by source_type.
    4. Return EventStudyResult with per-event detail + aggregate stats.

Usage:
    from v2.data import FDClient
    from v2.event_study import compute_car

    with FDClient() as fd:
        result = compute_car(["AAPL", "MSFT"], fd, earnings_limit=12)
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime, timedelta

import numpy as np

from v2.data.client import FDClient
from v2.data.models import EarningsRecord
from v2.event_study.models import (
    AggregateResult,
    EventCAR,
    EventStudyResult,
    WindowStats,
)
from v2.event_study.stats import (
    bootstrap_ci,
    compute_abnormal_returns,
    fit_market_model,
    sum_car,
    ttest_cars,
)

logger = logging.getLogger(__name__)

# --- Configuration ---
# These could become function params later, but are constants for v0.

_MARKET_TICKER = "SPY"             # market proxy for the market model
_ESTIMATION_START = -250           # start of estimation window (trading days before event)
_ESTIMATION_END = -11              # end of estimation window (10-day buffer avoids contamination)
_MIN_ESTIMATION_DAYS = 200         # skip events without enough pre-event price history
_MAX_EVENT_WINDOW = 20             # widest post-event window (day 0 through day +20)
_RETROSPECTIVE_CUTOFF_DAYS = 45    # max days between filing_date and report_period
_CAR_WINDOWS = [(0, 1), (0, 5), (0, 20)]  # the three event windows we compute CARs for


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_car(
    tickers: list[str],
    fd_client: FDClient,
    *,
    earnings_limit: int = 12,
    market_ticker: str = _MARKET_TICKER,
    n_bootstrap: int = 10_000,
    rng_seed: int | None = None,
) -> EventStudyResult:
    """Compute CARs for earnings events across multiple tickers.

    This is the main entry point. It:
    1. Fetches SPY prices once (shared across all tickers).
    2. Loops through tickers, computing per-event CARs.
    3. Aggregates results cross-sectionally by source_type.

    Args:
        tickers:         List of stock ticker symbols.
        fd_client:       FDClient instance (manages API auth + retries).
        earnings_limit:  Max earnings periods to fetch per ticker.
        market_ticker:   Market benchmark ticker (default "SPY").
        n_bootstrap:     Number of bootstrap resamples for CIs.
        rng_seed:        Seed for bootstrap reproducibility (None = random).

    Returns:
        EventStudyResult with per-event CARs, aggregate stats, and skipped tickers.
    """
    today = date.today().isoformat()

    # Fetch market (SPY) prices once — covers all tickers.
    # Start from 2023-01-01 to have enough history for any event's estimation window.
    spy_prices = fd_client.get_prices(market_ticker, "2023-01-01", today)
    if not spy_prices:
        logger.warning("No SPY prices returned — cannot compute CARs")
        return EventStudyResult(skipped_tickers=list(tickers))

    # Build a lookup: date string -> closing price
    spy_closes = {p.time[:10]: p.close for p in spy_prices}

    all_events: list[EventCAR] = []
    skipped: list[str] = []

    for ticker in tickers:
        events = _compute_ticker_events(
            ticker, fd_client, spy_closes, earnings_limit=earnings_limit,
        )
        if events:
            all_events.extend(events)
        else:
            skipped.append(ticker)

    # Cross-sectional aggregation: mean CAR, t-test, bootstrap CI, by source_type
    aggregates = _aggregate(all_events, n_bootstrap, rng_seed)

    return EventStudyResult(
        events=all_events, aggregates=aggregates, skipped_tickers=skipped,
    )


# ---------------------------------------------------------------------------
# Per-ticker processing
# ---------------------------------------------------------------------------

def _compute_ticker_events(
    ticker: str,
    fd_client: FDClient,
    spy_closes: dict[str, float],
    *,
    earnings_limit: int = 12,
) -> list[EventCAR]:
    """Compute CARs for all valid earnings events of a single ticker.

    Steps:
    1. Fetch earnings history (list of filings: 8-K, 10-Q, 10-K, 20-F).
    2. Filter out retrospective rows (45-day rule).
    3. Fetch stock prices for the widest needed date range (one API call).
    4. Build aligned return series where both stock and SPY have data.
    5. Process each event through the market model pipeline.
    """
    # Step 1: Get earnings filings for this ticker
    records = fd_client.get_earnings_history(ticker, limit=earnings_limit)
    if not records:
        return []

    # Step 2: Drop retrospective rows (e.g., Q4 data parsed from a Q1 8-K)
    records = _filter_retrospective(records)
    if not records:
        return []

    # Step 3: Fetch stock prices — one call covering all events.
    # Earliest event needs ~400 calendar days of history for the estimation window.
    # Latest event needs ~35 calendar days after for the post-event window.
    min_date = min(_parse_date(r.filing_date) for r in records)
    max_date = max(_parse_date(r.filing_date) for r in records)
    today = date.today()
    price_start = (min_date - timedelta(days=400)).isoformat()
    price_end = min(max_date + timedelta(days=35), today).isoformat()

    stock_prices = fd_client.get_prices(ticker, price_start, price_end)
    if not stock_prices:
        return []

    # Step 4: Build aligned return series.
    # Only use dates where BOTH stock and SPY have closing prices.
    stock_closes = {p.time[:10]: p.close for p in stock_prices}
    trading_days = sorted(set(stock_closes) & set(spy_closes))
    if len(trading_days) < _MIN_ESTIMATION_DAYS + _MAX_EVENT_WINDOW:
        return []

    # Convert aligned closes to numpy arrays in date order
    stock_close_arr = np.array([stock_closes[d] for d in trading_days])
    spy_close_arr = np.array([spy_closes[d] for d in trading_days])

    # Simple daily returns: r_t = (P_t - P_{t-1}) / P_{t-1}
    # returns[i] is the return "on" trading_days[i+1]
    stock_returns = np.diff(stock_close_arr) / stock_close_arr[:-1]
    spy_returns = np.diff(spy_close_arr) / spy_close_arr[:-1]
    return_days = trading_days[1:]  # each return corresponds to this date

    # Index for O(1) lookup: date string -> position in return_days
    day_to_idx = {d: i for i, d in enumerate(return_days)}

    # Step 5: Process each earnings event
    events: list[EventCAR] = []
    for record in records:
        event = _process_event(
            record, stock_returns, spy_returns, return_days, day_to_idx,
        )
        if event is not None:
            events.append(event)

    return events


# ---------------------------------------------------------------------------
# Per-event processing
# ---------------------------------------------------------------------------

def _process_event(
    record: EarningsRecord,
    stock_returns: np.ndarray,
    spy_returns: np.ndarray,
    return_days: list[str],
    day_to_idx: dict[str, int],
) -> EventCAR | None:
    """Process a single earnings event into an EventCAR.

    Returns None if the event is skipped (not enough data, can't find
    the event date in the trading calendar, etc.).

    The pipeline for one event:
    1. Find event day 0 in the trading day index.
    2. Extract estimation window [-250, -11] for market model OLS.
    3. Fit alpha, beta.
    4. Extract event window [0, +20] for abnormal returns.
    5. Compute daily AR and cumulate into CARs for each window.
    """
    event_date_str = record.filing_date

    # Find day 0: the trading day on or immediately after the filing date.
    # (Filing may land on a weekend/holiday — snap to next trading day.)
    event_idx = _find_event_idx(event_date_str, return_days, day_to_idx)
    if event_idx is None:
        return None

    # Estimation window: [-250, -11] trading days relative to event.
    # The 10-day buffer (-11 instead of -1) prevents pre-announcement
    # drift / leakage from contaminating the alpha/beta estimates.
    est_start = event_idx + _ESTIMATION_START
    est_end = event_idx + _ESTIMATION_END
    if est_start < 0 or est_end < 0:
        return None

    stock_est = stock_returns[est_start : est_end + 1]
    spy_est = spy_returns[est_start : est_end + 1]
    if len(stock_est) < _MIN_ESTIMATION_DAYS:
        return None

    # Fit market model: R_stock = alpha + beta * R_spy
    model = fit_market_model(stock_est, spy_est)

    # Event window: [0, +20] trading days starting from event day.
    # May be shorter if the event is too recent.
    evt_start = event_idx
    evt_end = min(event_idx + _MAX_EVENT_WINDOW, len(stock_returns) - 1)
    stock_evt = stock_returns[evt_start : evt_end + 1]
    spy_evt = spy_returns[evt_start : evt_end + 1]

    # Abnormal returns: what the stock did minus what the market model predicted
    daily_ar = compute_abnormal_returns(stock_evt, spy_evt, model.alpha, model.beta)

    # Cumulate ARs into CARs for each window.
    # If not enough post-event days for a window, set that CAR to None.
    n_days = len(daily_ar)
    cars: dict[str, float | None] = {}
    for start, end in _CAR_WINDOWS:
        if end < n_days:
            cars[f"car_{start}_{end}"] = sum_car(daily_ar, start, end)
        else:
            cars[f"car_{start}_{end}"] = None

    # Pull EPS surprise from the quarterly data (if available)
    eps_surprise = None
    if record.quarterly is not None:
        eps_surprise = record.quarterly.eps_surprise

    return EventCAR(
        ticker=record.ticker,
        event_date=event_date_str,
        source_type=record.source_type,
        report_period=record.report_period,
        eps_surprise=eps_surprise,
        market_model=model,
        daily_ar=[float(x) for x in daily_ar],
        car_0_1=cars["car_0_1"],
        car_0_5=cars["car_0_5"],
        car_0_20=cars["car_0_20"],
    )


# ---------------------------------------------------------------------------
# Cross-sectional aggregation
# ---------------------------------------------------------------------------

def _aggregate(
    events: list[EventCAR],
    n_bootstrap: int,
    rng_seed: int | None,
) -> list[AggregateResult]:
    """Aggregate CARs across events, segmented by source_type.

    For each source_type group (e.g. all 8-K events):
      - For each window ([0,+1], [0,+5], [0,+20]):
        - Collect all non-null CARs
        - Compute mean, std, t-test, bootstrap CI
        - Build a WindowStats

    Segmenting by source_type is the built-in robustness check:
    8-K events have precise announcement dates, so CARs should be
    sharper. 10-Q/K filing dates lag by 0-45 days, diluting the signal.
    """
    if not events:
        return []

    # Group events by source_type
    groups: dict[str, list[EventCAR]] = defaultdict(list)
    for e in events:
        groups[e.source_type].append(e)

    # Map window labels to EventCAR attribute names
    car_attr = {"[0,+1]": "car_0_1", "[0,+5]": "car_0_5", "[0,+20]": "car_0_20"}
    results: list[AggregateResult] = []

    for source_type in sorted(groups):
        group = groups[source_type]
        windows: list[WindowStats] = []

        for window_label, attr in car_attr.items():
            # Collect non-null CARs for this window
            values = [getattr(e, attr) for e in group if getattr(e, attr) is not None]
            if len(values) < 2:
                continue  # need at least 2 events for meaningful stats

            cars_arr = np.array(values)
            mean = float(cars_arr.mean())
            std = float(cars_arr.std(ddof=1))  # sample std (Bessel's correction)
            t, p = ttest_cars(cars_arr)
            ci = bootstrap_ci(cars_arr, n_bootstrap=n_bootstrap, rng_seed=rng_seed)

            windows.append(WindowStats(
                window=window_label,
                n_events=len(values),
                mean_car=mean,
                std_car=std,
                t_stat=t,
                p_value=p,
                ci=ci,
            ))

        results.append(AggregateResult(
            source_type=source_type, n_events=len(group), windows=windows,
        ))

    return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_date(s: str) -> date:
    """Parse 'YYYY-MM-DD' string to a date object."""
    return datetime.strptime(s[:10], "%Y-%m-%d").date()


def _filter_retrospective(records: list[EarningsRecord]) -> list[EarningsRecord]:
    """Drop records where filing_date is >45 days after report_period.

    The ER extractor sometimes parses prior-period comparison data from
    a current 8-K, producing rows that look like a real Q4 event but are
    actually anchored on a Q1 filing date (e.g., GS: report_period=2025-12-31,
    filing_date=2026-04-13 → 103 days, clearly retrospective).

    Without this filter, CARs would be computed around the wrong dates.
    """
    kept: list[EarningsRecord] = []
    for r in records:
        filing = _parse_date(r.filing_date)
        report = _parse_date(r.report_period)
        if (filing - report).days < _RETROSPECTIVE_CUTOFF_DAYS:
            kept.append(r)
        else:
            logger.debug(
                "Filtered retrospective: %s %s filed %s (report %s, %d days)",
                r.ticker, r.source_type, r.filing_date, r.report_period,
                (filing - report).days,
            )
    return kept


def _find_event_idx(
    event_date: str,
    return_days: list[str],
    day_to_idx: dict[str, int],
) -> int | None:
    """Find index of event_date in return_days, snapping to next trading day.

    If filing_date falls on a weekend or market holiday, look ahead up to
    4 calendar days to find the next trading day. Returns None if no
    trading day is found within that range.
    """
    if event_date in day_to_idx:
        return day_to_idx[event_date]
    # Weekend/holiday — find next trading day
    d = _parse_date(event_date)
    for offset in range(1, 5):
        candidate = (d + timedelta(days=offset)).isoformat()
        if candidate in day_to_idx:
            return day_to_idx[candidate]
    return None
