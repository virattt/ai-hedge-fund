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

import json as _json

# Load .env early so FINANCIAL_DATASETS_API_KEY, ANTHROPIC_API_KEY, etc. are
# available when the snapshot / agent / fundamentals modules consult os.environ.
try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv()
except Exception:
    pass

import uvicorn
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse

from src.analysis import generate_snapshot, attach_final_verdict, deep_analyze, shallow_analyze
from src.analysis.snapshot import SnapshotReport
from src.analysis import storage as snapshot_storage
from src.analysis import watchlists as wl_store
from src.analysis import settings as settings_store
from src.analysis.ui_pages import (
    compare_page,
    compare_saved_page,
    history_page,
    home_page,
    journal_page,
    multi_save_compare_page,
    results_overview_page,
    saved_list_page,
    settings_page,
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

    If auto-save is enabled in settings.json AND we haven't already saved
    this ticker today via 'auto', drop a snapshot to disk before rendering.
    """
    raw_from = request.query_params.get("from", "") or ""
    deep_flag = request.query_params.get("deep", "") in ("1", "true", "yes")
    try:
        rep = _cached(ticker, deep=deep_flag)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Snapshot failed: {exc}")

    # Auto-save (idempotent: once per ticker per day)
    try:
        s = settings_store.load_settings()
        if s.auto_save_enabled and not snapshot_storage.already_saved_today(ticker, source="auto"):
            snapshot_storage.save_snapshot(
                rep, note="auto-saved on view", tags=[s.auto_save_default_tag], source="auto"
            )
    except Exception:
        pass

    return HTMLResponse(ticker_detail_page(rep, _parse_tickers(raw_from), deep=deep_flag))


@app.get("/compare", response_class=HTMLResponse)
async def compare(tickers: str = "") -> HTMLResponse:
    parsed = _parse_tickers(tickers)
    if not parsed:
        return HTMLResponse(compare_page([], []))
    reports, errors, _elapsed = _fetch_many(parsed)
    return HTMLResponse(compare_page(reports, errors))


# --- Interactive backtest --------------------------------------------------


@app.get("/api/backtest-at/{ticker}")
async def api_backtest_at(ticker: str, date: str) -> JSONResponse:
    """Run the technical verdict as of an arbitrary historical date.

    Query param `date` is YYYY-MM-DD. Uses the in-memory series cache that
    `generate_snapshot()` populates — call /api/snapshot/{ticker} first if
    the cache is cold.
    """
    from src.analysis import _series_cache
    from src.analysis.backtest import backtest_at_date

    series = _series_cache.get(ticker)
    if not series:
        # Warm the cache with a fresh snapshot fetch
        try:
            _cached(ticker)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"snapshot fetch failed: {exc}")
        series = _series_cache.get(ticker)
        if not series:
            raise HTTPException(status_code=500, detail="series cache empty after snapshot")

    close, volume, spx_close = series
    point = backtest_at_date(close, volume, date, spx_close)
    if not point:
        raise HTTPException(status_code=400, detail="not enough history for that date (need ≥200 trading days before, ≥1 trading day after)")

    # Try the historical fundamentals lookup (Financial Datasets API).
    # Degrades to None gracefully if no key or no data.
    fund_payload = None
    try:
        from src.analysis.fundamentals_backtest import historical_fundamentals_at_date
        fp = historical_fundamentals_at_date(ticker, date, close)
        if fp:
            fund_payload = {
                "report_period": fp.report_period,
                "verdict": fp.fundamental_verdict,
                "confidence": fp.fundamental_confidence,
                "error": fp.error,
                "metrics": [
                    {
                        "name": m.name,
                        "value": m.value,
                        "unit": m.unit,
                        "verdict": m.verdict,
                        "rationale": m.rationale,
                    }
                    for m in fp.metrics
                ],
            }
    except Exception as exc:
        fund_payload = {"error": str(exc)}

    return JSONResponse(
        {
            "label": point.label,
            "as_of_date": point.as_of_date,
            "price_then": point.price_then,
            "price_now": point.price_now,
            "realized_return": point.realized_return,
            "spx_return": point.spx_return,
            "alpha": point.alpha,
            "verdict": point.technical_verdict,
            "confidence": point.technical_confidence,
            "correct": point.correct,
            "indicators": [
                {
                    "name": r.name,
                    "state": r.state,
                    "signal": r.signal,
                    "rationale": r.rationale,
                }
                for r in point.indicator_signals
            ],
            "fundamentals": fund_payload,
        }
    )


# --- SSE streaming for deep analysis ---------------------------------------


@app.get("/api/stream-deep/{ticker}")
async def stream_deep_endpoint(ticker: str) -> StreamingResponse:
    """Server-Sent Events stream of LangGraph agent progress."""
    from src.analysis.agent_streamer import stream_agent_run

    ticker = ticker.upper()

    async def generator():
        try:
            async for event in stream_agent_run(ticker):
                yield f"data: {_json.dumps(event)}\n\n"
        except Exception as exc:  # pragma: no cover — pipeline failures
            yield f"data: {_json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.get("/ticker/{ticker}/streaming", response_class=HTMLResponse)
async def ticker_streaming_page(ticker: str, request: Request) -> HTMLResponse:
    """Live streaming page that opens an EventSource to /api/stream-deep/{ticker}.

    Shows a grid of 14 agent cards. As each completes, the card flips to ✓.
    When the pipeline finishes, JS auto-redirects to ?deep=1 which uses the
    now-cached agent results to render the full report.
    """
    from src.analysis.ui_pages import streaming_progress_page

    raw_from = request.query_params.get("from", "") or ""
    return HTMLResponse(streaming_progress_page(ticker.upper(), _parse_tickers(raw_from)))


# --- Save / Compare routes -------------------------------------------------


@app.post("/api/save/{ticker}")
async def api_save(
    ticker: str,
    note: str = Form(""),
    tags: str = Form(""),  # comma-separated
) -> RedirectResponse:
    """Persist the current snapshot for `ticker` to disk and bounce the user to the saved list (form submit version)."""
    try:
        rep = _cached(ticker)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Snapshot failed: {exc}")
    tag_list = [t.strip() for t in (tags or "").split(",") if t.strip()]
    snapshot_storage.save_snapshot(rep, note=note, tags=tag_list, source="manual")
    return RedirectResponse(url=f"/saved/{ticker.upper()}", status_code=303)


@app.post("/api/save-ajax/{ticker}")
async def api_save_ajax(
    ticker: str,
    note: str = Form(""),
    tags: str = Form(""),
) -> JSONResponse:
    """AJAX save — returns JSON {ok, timestamp, path, tags, has_agents} so the
    detail page can show a toast and stay on the same page instead of bouncing
    the user to /saved/<TICKER>."""
    try:
        rep = _cached(ticker)
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)
    tag_list = [t.strip() for t in (tags or "").split(",") if t.strip()]
    meta = snapshot_storage.save_snapshot(rep, note=note, tags=tag_list, source="manual")
    return JSONResponse(
        {
            "ok": True,
            "timestamp": meta["timestamp"],
            "tags": meta["tags"],
            "saved_at": meta["saved_at"],
            "has_agents": bool(rep.agents and not getattr(rep.agents, "error", None)),
            "council_size": (rep.agents.total_analysts if rep.agents and not getattr(rep.agents, "error", None) else 0),
        }
    )


@app.post("/api/saved/{ticker}/{timestamp}/tags")
async def api_update_tags(ticker: str, timestamp: str, tags: str = Form("")) -> RedirectResponse:
    """Edit tags on an existing saved snapshot."""
    tag_list = [t.strip() for t in (tags or "").split(",") if t.strip()]
    snapshot_storage.update_tags(ticker, timestamp, tag_list)
    return RedirectResponse(url=f"/saved/{ticker.upper()}", status_code=303)


@app.get("/saved", response_class=HTMLResponse)
async def saved_all() -> HTMLResponse:
    items = snapshot_storage.list_saved()
    return HTMLResponse(saved_list_page(items))


@app.get("/saved/{ticker}", response_class=HTMLResponse)
async def saved_for(ticker: str, request: Request) -> HTMLResponse:
    tag = request.query_params.get("tag") or None
    items = snapshot_storage.list_saved(ticker, tag=tag)
    # Enrich with current prices (one fetch per ticker, cached)
    cur_prices = {ticker.upper(): _safe_current_price(ticker)}
    items = snapshot_storage.evaluate_target_hits(items, cur_prices)
    return HTMLResponse(saved_list_page(items, ticker=ticker.upper(), tag=tag))


def _safe_current_price(ticker: str) -> Optional[float]:
    try:
        return _cached(ticker).current_price
    except Exception:
        return None


@app.get("/journal", response_class=HTMLResponse)
async def journal(request: Request) -> HTMLResponse:
    """Saved-verdicts dashboard: aggregate hit rate, avg return, top hits/misses."""
    tag = request.query_params.get("tag") or None
    items = snapshot_storage.list_saved(tag=tag)
    # Build {ticker -> current_price} for all tickers in the journal
    tickers = sorted({i["ticker"] for i in items})
    current_prices: dict[str, float] = {}
    for t in tickers:
        p = _safe_current_price(t)
        if p is not None:
            current_prices[t] = p
    summary = snapshot_storage.journal_summary(items, current_prices)
    all_tags = snapshot_storage.list_all_tags()
    return HTMLResponse(journal_page(summary, current_prices, all_tags, active_tag=tag))


@app.get("/compare-saves", response_class=HTMLResponse)
async def compare_saves(request: Request) -> HTMLResponse:
    """Multi-save comparison page. Query: ?ticker=X&ts=ts1,ts2,ts3 (2-6 timestamps)."""
    ticker = (request.query_params.get("ticker") or "").upper()
    ts_raw = request.query_params.get("ts") or ""
    timestamps = [t.strip() for t in ts_raw.split(",") if t.strip()][:6]
    if not ticker or len(timestamps) < 2:
        raise HTTPException(status_code=400, detail="Need ?ticker=X&ts=ts1,ts2,...")
    saves = []
    for ts in timestamps:
        s = snapshot_storage.load_saved(ticker, ts)
        if s:
            saves.append((ts, s))
    if len(saves) < 2:
        raise HTTPException(status_code=404, detail="Fewer than 2 saved snapshots loaded")
    try:
        current = _cached(ticker)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Current snapshot fetch failed: {exc}")
    return HTMLResponse(multi_save_compare_page(ticker, saves, current))


# --- Settings -------------------------------------------------------------


@app.get("/settings", response_class=HTMLResponse)
async def settings_view() -> HTMLResponse:
    return HTMLResponse(settings_page(settings_store.load_settings(), settings_store.detected_data_sources()))


@app.post("/api/settings")
async def settings_update(
    auto_save_enabled: str = Form(""),
    auto_save_default_tag: str = Form("auto"),
    auto_run_council: str = Form(""),
    default_analysts: str = Form(""),
) -> RedirectResponse:
    s = settings_store.load_settings()
    s.auto_save_enabled = auto_save_enabled in ("1", "on", "true", "yes")
    s.auto_save_default_tag = (auto_save_default_tag or "auto").strip().lower()
    s.auto_run_council = auto_run_council in ("1", "on", "true", "yes")
    s.default_analysts = [a.strip() for a in default_analysts.split(",") if a.strip()]
    settings_store.save_settings(s)
    return RedirectResponse(url="/settings?saved=1", status_code=303)


@app.get("/api/settings")
async def api_get_settings() -> JSONResponse:
    """JSON view of the current settings — used by client-side scripts (e.g.
    the auto-council kickoff on the ticker detail page)."""
    s = settings_store.load_settings()
    import dataclasses as _dc
    return JSONResponse(_dc.asdict(s))


# --- Persistent watchlists ------------------------------------------------


@app.get("/api/watchlists")
async def api_list_watchlists() -> JSONResponse:
    return JSONResponse(wl_store.list_watchlists())


@app.post("/api/watchlists")
async def api_create_watchlist(name: str = Form(...), tickers: str = Form("")) -> RedirectResponse:
    tickers_list = [t.strip() for t in tickers.split(",") if t.strip()]
    wl_store.create_watchlist(name, tickers_list)
    return RedirectResponse(url="/watchlists", status_code=303)


@app.post("/api/watchlists/{wl_id}/delete")
async def api_delete_watchlist(wl_id: str) -> RedirectResponse:
    wl_store.delete_watchlist(wl_id)
    return RedirectResponse(url="/watchlists", status_code=303)


@app.post("/api/watchlists/{wl_id}/update")
async def api_update_watchlist(
    wl_id: str,
    name: str = Form(""),
    tickers: str = Form(""),
) -> RedirectResponse:
    tickers_list = [t.strip() for t in tickers.split(",") if t.strip()]
    wl_store.update_watchlist(wl_id, name=name or None, tickers=tickers_list or None)
    return RedirectResponse(url="/watchlists", status_code=303)


@app.get("/compare-saved/{ticker}/{timestamp}", response_class=HTMLResponse)
async def compare_saved(ticker: str, timestamp: str) -> HTMLResponse:
    saved = snapshot_storage.load_saved(ticker, timestamp)
    if not saved:
        raise HTTPException(status_code=404, detail="Saved snapshot not found")
    try:
        current = _cached(ticker)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Snapshot fetch failed: {exc}")
    return HTMLResponse(compare_saved_page(saved, current))


@app.post("/api/delete-saved/{ticker}/{timestamp}")
async def delete_saved(ticker: str, timestamp: str) -> RedirectResponse:
    snapshot_storage.delete_saved(ticker, timestamp)
    return RedirectResponse(url=f"/saved/{ticker.upper()}", status_code=303)


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
