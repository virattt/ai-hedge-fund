"""Strategist — local web dashboard for AI hedge fund snapshots.

Run with:
    poetry run snapshot-ui
or:
    poetry run python -m src.analysis.web

Opens http://127.0.0.1:8765 in your default browser. Five pages:
    /                       Home: hero search + presets + recents + watchlists
    /run?tickers=NVDA,AAPL  Results overview: sortable, filterable table
    /ticker/{T}?from=...    Single-ticker deep-dive (drill-down)
    /compare?tickers=...    Side-by-side metric comparison
    /watchlists, /history   Saved lists & recent searches (localStorage)
    /api/snapshot/{T}       JSON snapshot
    /api/snapshots?tickers=  Bulk JSON
"""

from __future__ import annotations

import argparse
import dataclasses
import threading
import time
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

from src.analysis import generate_snapshot, attach_final_verdict, deep_analyze, shallow_analyze
from src.analysis.snapshot import SnapshotReport
from src.analysis.ui_pages import (
    compare_page,
    history_page,
    home_page,
    results_overview_page,
    ticker_detail_page,
    watchlists_page,
)

app = FastAPI(title="Strategist — AI Hedge Fund Snapshot UI", docs_url=None, redoc_url=None)


# --- In-memory snapshot cache ----------------------------------------------

_CACHE: dict[str, tuple[float, SnapshotReport]] = {}
_CACHE_TTL_SECONDS = 300  # 5 minutes — long enough for navigation, short enough for fresh data


def _cached(ticker: str, *, deep: bool = False) -> SnapshotReport:
    """Fetch a snapshot, reusing recent results within the TTL.

    If `deep=True` and the cached version doesn't have AI council results yet,
    upgrade it: re-run the LangGraph pipeline and re-attach the final verdict.
    """
    ticker = ticker.upper().strip()
    now = time.time()
    cached = _CACHE.get(ticker)
    if cached and now - cached[0] < _CACHE_TTL_SECONDS:
        rep = cached[1]
        if deep and not rep.agents:
            # Upgrade in place — keep the snapshot, attach agents + new verdict
            from src.analysis.agent_runner import run_agents
            rep.agents = run_agents(ticker)
            attach_final_verdict(rep)
            _CACHE[ticker] = (now, rep)
        return rep

    # Cold load
    rep = shallow_analyze(ticker) if not deep else deep_analyze(ticker)
    _CACHE[ticker] = (now, rep)
    return rep


def _parse_tickers(raw: str) -> list[str]:
    """Parse a comma/semicolon/space-separated ticker string into a clean list."""
    parts = [t.strip().upper() for t in raw.replace(";", ",").replace(" ", ",").split(",") if t.strip()]
    seen: set[str] = set()
    out: list[str] = []
    for t in parts:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def _fetch_many(tickers: list[str], *, deep: bool = False) -> tuple[list[SnapshotReport], list[tuple[str, str]], float]:
    """Fetch snapshots for many tickers in parallel. Returns (reports, errors, elapsed_seconds).

    Always runs at least the shallow analysis (snapshot + backtest + verdict).
    If `deep=True`, also runs the LangGraph council per ticker — much slower,
    so the caller should set expectations in the UI.
    """
    started = time.perf_counter()
    results: dict[str, tuple[Optional[SnapshotReport], Optional[str]]] = {}

    def _one(t: str) -> tuple[str, Optional[SnapshotReport], Optional[str]]:
        try:
            rep = _cached(t, deep=deep)
            # Make sure final verdict is attached for the overview rendering
            if not rep.final_verdict:
                attach_final_verdict(rep)
            return t, rep, None
        except Exception as exc:  # pragma: no cover — yfinance failure surface
            return t, None, f"{type(exc).__name__}: {exc}"

    with ThreadPoolExecutor(max_workers=5) as ex:
        for t, rep, err in ex.map(_one, tickers):
            results[t] = (rep, err)

    reports: list[SnapshotReport] = []
    errors: list[tuple[str, str]] = []
    for t in tickers:
        rep, err = results[t]
        if err:
            errors.append((t, err))
        elif rep is not None:
            reports.append(rep)
    elapsed = time.perf_counter() - started
    return reports, errors, elapsed


def _dataclass_to_dict(obj):
    if dataclasses.is_dataclass(obj):
        return {k: _dataclass_to_dict(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, (list, tuple)):
        return [_dataclass_to_dict(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _dataclass_to_dict(v) for k, v in obj.items()}
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj


# --- HTML page routes -------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
async def home() -> HTMLResponse:
    return HTMLResponse(home_page())


@app.get("/watchlists", response_class=HTMLResponse)
async def watchlists() -> HTMLResponse:
    return HTMLResponse(watchlists_page())


@app.get("/history", response_class=HTMLResponse)
async def history() -> HTMLResponse:
    return HTMLResponse(history_page())


@app.get("/run", response_class=HTMLResponse)
async def run(tickers: str = "") -> HTMLResponse:
    parsed = _parse_tickers(tickers)
    if not parsed:
        return HTMLResponse(home_page())
    reports, errors, elapsed = _fetch_many(parsed)
    return HTMLResponse(results_overview_page(reports, errors, elapsed, parsed))


@app.get("/ticker/{ticker}", response_class=HTMLResponse)
async def ticker_detail(ticker: str, request: Request) -> HTMLResponse:
    """Single-ticker detail page.

    `?deep=1` triggers the LangGraph AI investor council on top of the
    snapshot. Adds 30-60 seconds but yields a fuller report.
    """
    raw_from = request.query_params.get("from", "") or ""
    deep_flag = request.query_params.get("deep", "") in ("1", "true", "yes")
    try:
        rep = _cached(ticker, deep=deep_flag)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Snapshot failed: {exc}")
    return HTMLResponse(ticker_detail_page(rep, _parse_tickers(raw_from), deep=deep_flag))


@app.get("/compare", response_class=HTMLResponse)
async def compare(tickers: str = "") -> HTMLResponse:
    parsed = _parse_tickers(tickers)
    if not parsed:
        return HTMLResponse(compare_page([], []))
    reports, errors, _elapsed = _fetch_many(parsed)
    return HTMLResponse(compare_page(reports, errors))


# --- JSON API ---------------------------------------------------------------


@app.get("/api/snapshot/{ticker}")
async def api_snapshot(ticker: str):
    try:
        rep = _cached(ticker)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Snapshot failed: {exc}")
    return JSONResponse(_dataclass_to_dict(rep))


@app.get("/api/snapshots")
async def api_snapshots(tickers: str = ""):
    parsed = _parse_tickers(tickers)
    if not parsed:
        return JSONResponse({"reports": [], "errors": [], "elapsed": 0})
    reports, errors, elapsed = _fetch_many(parsed)
    return JSONResponse(
        {
            "reports": [_dataclass_to_dict(r) for r in reports],
            "errors": [{"ticker": t, "message": m} for t, m in errors],
            "elapsed": elapsed,
        }
    )


# --- Entry point -----------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Strategist — local snapshot UI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-open", action="store_true", help="Don't auto-open the browser")
    parser.add_argument("--tickers", default=None, help="Pre-run analysis on these tickers (comma-separated)")
    args = parser.parse_args()

    url = f"http://{args.host}:{args.port}/"
    if args.tickers:
        url = f"http://{args.host}:{args.port}/run?tickers={args.tickers.replace(' ', '')}"

    if not args.no_open:
        def _open():
            time.sleep(1.0)
            try:
                webbrowser.open(url)
            except Exception:
                pass

        threading.Thread(target=_open, daemon=True).start()

    print(f"[strategist] starting at {url}")
    print(f"[strategist]   home:        http://{args.host}:{args.port}/")
    print(f"[strategist]   compare:     http://{args.host}:{args.port}/compare?tickers=NVDA,AAPL")
    print(f"[strategist]   watchlists:  http://{args.host}:{args.port}/watchlists")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
