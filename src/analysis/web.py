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

import contextlib
from typing import AsyncIterator

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
    earnings_calendar_page,
    history_page,
    home_page,
    journal_page,
    multi_save_compare_page,
    results_overview_page,
    saved_list_page,
    settings_page,
    ticker_detail_page,
    ticker_not_found_page,
    universe_heatmap_page,
    watchlists_page,
)

@contextlib.asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Startup
    _start_background_refresher()
    yield
    # Shutdown — daemon threads exit automatically; nothing else to clean up.


app = FastAPI(
    title="Strategist — AI Hedge Fund Snapshot UI",
    docs_url=None,
    redoc_url=None,
    lifespan=_lifespan,
)


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


def _ticker_looks_valid(t: str) -> bool:
    """Basic ticker sanity check before hitting yfinance.

    Allow letters, digits, ., -, ^ (for ^GSPC etc). 1-12 chars.
    """
    import re as _re
    if not t or len(t) > 12:
        return False
    return bool(_re.match(r"^[A-Za-z0-9.\-^]+$", t))


def _is_empty_report(rep) -> bool:
    """Detect SnapshotReport produced for a non-existent/garbage ticker.

    yfinance silently returns empty data: we get a report with current_price=None,
    no analyst counts, all fundamentals with value=None (the rows still exist),
    and no technical indicators (we skip them when there's <200 days of history).
    """
    if rep.current_price is not None:
        return False  # real ticker
    if rep.analyst and rep.analyst.total_analysts:
        return False
    # The metric rows always exist; check if any actually have a value
    if any(m.value is not None for m in (rep.fundamental_metrics or [])):
        return False
    if rep.technical_indicators:
        return False
    return True


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

    if not _ticker_looks_valid(ticker):
        from src.analysis.ui_pages import ticker_not_found_page
        return HTMLResponse(ticker_not_found_page(ticker, reason="invalid_format"), status_code=400)

    try:
        rep = _cached(ticker, deep=deep_flag)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Snapshot failed: {exc}")

    # yfinance silently returns empty data for non-existent tickers — detect and show a real error.
    if _is_empty_report(rep):
        from src.analysis.ui_pages import ticker_not_found_page
        return HTMLResponse(ticker_not_found_page(ticker, reason="no_data"), status_code=404)

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

    # Validate date format before running the backtest engine. pandas will
    # raise on malformed input — surface that as a 400 instead of a 500.
    try:
        import pandas as _pd
        _pd.Timestamp(date)
    except Exception:
        raise HTTPException(
            status_code=400,
            detail=f"invalid date '{date}' — use YYYY-MM-DD format",
        )

    close, volume, spx_close = series
    try:
        point = backtest_at_date(close, volume, date, spx_close)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"backtest failed: {exc}")
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


@app.get("/heatmap", response_class=HTMLResponse)
async def heatmap(tickers: str = "") -> HTMLResponse:
    """Universe heatmap — sector × verdict grid."""
    parsed = _parse_tickers(tickers)
    if not parsed:
        return HTMLResponse(universe_heatmap_page([], ""))
    reports, _errors, _elapsed = _fetch_many(parsed)
    return HTMLResponse(universe_heatmap_page(reports, ",".join(parsed)))


@app.get("/calendar", response_class=HTMLResponse)
async def earnings_calendar() -> HTMLResponse:
    """Earnings calendar — aggregate across saves + watchlists."""
    # Build candidate ticker list from saves + watchlists
    tickers: set[str] = set()
    try:
        for item in snapshot_storage.list_saved():
            tickers.add(item["ticker"])
    except Exception:
        pass
    try:
        for w in wl_store.list_watchlists():
            tickers.update(w.get("tickers", []) or [])
    except Exception:
        pass

    rows: list[dict] = []
    if tickers:
        # Best-effort — yfinance .info has 'earningsDate' (list of timestamps)
        try:
            import yfinance as _yf
            from datetime import datetime as _dt
        except Exception:
            tickers = set()

        for t in sorted(tickers):
            try:
                info = _yf.Ticker(t).info or {}
            except Exception:
                continue
            date = None
            ed = info.get("earningsDate") or info.get("earningsTimestamp")
            if isinstance(ed, list) and ed:
                try:
                    date = _dt.fromtimestamp(int(ed[0])).date()
                except Exception:
                    pass
            elif isinstance(ed, (int, float)):
                try:
                    date = _dt.fromtimestamp(int(ed)).date()
                except Exception:
                    pass
            rows.append(
                {
                    "ticker": t,
                    "company_name": info.get("longName") or info.get("shortName") or "",
                    "date": date,
                    "source": "watchlist" if any(t in (w.get("tickers") or []) for w in wl_store.list_watchlists()) else "saved",
                }
            )

    return HTMLResponse(earnings_calendar_page(rows))


# --- Health + background refresher ------------------------------------


@app.get("/healthz")
async def healthz() -> JSONResponse:
    """Liveness probe — used by start-up checks and external monitors."""
    import os
    return JSONResponse(
        {
            "ok": True,
            "pid": os.getpid(),
            "cache_size": len(_CACHE),
            "data_dir": str(snapshot_storage.SAVED_DIR.parent),
        }
    )


def _start_background_refresher() -> None:
    """Pre-warm the snapshot cache for every ticker the user cares about.

    Runs every 6 hours. Iterates over saved tickers + all watchlist tickers,
    fetches a fresh snapshot for each (parallel, max 5 concurrent), and
    seeds the in-process cache. Result: when you open a ticker detail page
    the next morning, it loads instantly with fresh data.

    Idempotent and crash-safe — any single ticker failure is logged and
    skipped. Disabled if the server is run with STRATEGIST_NO_REFRESHER=1.
    """
    import os
    if os.environ.get("STRATEGIST_NO_REFRESHER") == "1":
        return

    import threading
    import time as _time

    INTERVAL_SECONDS = 6 * 60 * 60  # 6 hours
    INITIAL_DELAY_SECONDS = 30      # don't hammer at boot — let the UI come up first

    def _all_tracked_tickers() -> list[str]:
        tickers: set[str] = set()
        try:
            for s in snapshot_storage.list_saved():
                tickers.add(s["ticker"])
        except Exception:
            pass
        try:
            for w in wl_store.list_watchlists():
                tickers.update(w.get("tickers", []) or [])
        except Exception:
            pass
        return sorted(tickers)

    def _refresh_pass() -> None:
        tickers = _all_tracked_tickers()
        if not tickers:
            return
        # Reuse _fetch_many for parallel snapshot fetch
        try:
            _fetch_many(tickers, deep=False)
        except Exception:
            pass

    def _worker() -> None:
        _time.sleep(INITIAL_DELAY_SECONDS)
        while True:
            try:
                _refresh_pass()
            except Exception:
                pass
            _time.sleep(INTERVAL_SECONDS)

    t = threading.Thread(target=_worker, name="strategist-refresher", daemon=True)
    t.start()


# --- Exports: Markdown / HTML / JSON / Print-PDF -------------------------


@app.get("/export/{ticker}.md")
async def export_md(ticker: str) -> "Response":
    """Download the analysis as Markdown."""
    from fastapi.responses import Response
    from src.analysis.exporter import to_markdown
    try:
        rep = _cached(ticker)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Snapshot failed: {exc}")
    if _is_empty_report(rep):
        raise HTTPException(status_code=404, detail=f"No data for ticker {ticker.upper()}")
    md = to_markdown(rep)
    filename = f"{ticker.upper()}_{rep.timestamp:%Y-%m-%d}.md"
    return Response(
        content=md,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/export/{ticker}.json")
async def export_json(ticker: str) -> "Response":
    """Download the snapshot as a JSON file (vs /api/snapshot which is inline)."""
    from fastapi.responses import Response
    try:
        rep = _cached(ticker)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Snapshot failed: {exc}")
    if _is_empty_report(rep):
        raise HTTPException(status_code=404, detail=f"No data for ticker {ticker.upper()}")
    payload = _dataclass_to_dict(rep)
    filename = f"{ticker.upper()}_{rep.timestamp:%Y-%m-%d}.json"
    return Response(
        content=_json.dumps(payload, indent=2, default=str),
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/export/{ticker}.html")
async def export_html(ticker: str) -> "Response":
    """Download a self-contained single-file HTML report."""
    from fastapi.responses import Response
    from src.analysis import render_html_body, HTML_STYLE
    try:
        rep = _cached(ticker)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Snapshot failed: {exc}")
    if _is_empty_report(rep):
        raise HTTPException(status_code=404, detail=f"No data for ticker {ticker.upper()}")
    body = render_html_body(rep)
    standalone = f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"/>
<title>{rep.ticker} — {rep.company_name}</title>
<style>{HTML_STYLE}</style>
</head><body><div class="container shell">{body}</div></body></html>"""
    filename = f"{ticker.upper()}_{rep.timestamp:%Y-%m-%d}.html"
    return Response(
        content=standalone,
        media_type="text/html; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/print/{ticker}", response_class=HTMLResponse)
async def print_view(ticker: str) -> HTMLResponse:
    """Print-optimized view that auto-fires window.print() once the page paints.

    User saves as PDF from the browser print dialog → 100% reliable PDF
    output with no extra Python deps (no weasyprint, no playwright).
    """
    try:
        rep = _cached(ticker)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Snapshot failed: {exc}")
    if _is_empty_report(rep):
        from src.analysis.ui_pages import ticker_not_found_page
        return HTMLResponse(ticker_not_found_page(ticker, reason="no_data"), status_code=404)

    from src.analysis import HTML_STYLE
    from src.analysis.ui_pages import _final_verdict_banner, _verdict_rationale, _multi_horizon_panel, _backtest_panel, _news_panel, _agent_council_panel
    from src.analysis.renderers import render_html_body

    rec = rep.final_verdict
    sections = [
        _final_verdict_banner(rec, rep) if rec else "",
        _verdict_rationale(rec) if rec else "",
        _multi_horizon_panel(rep.price_target_set, rep.current_price),
        _backtest_panel(rep.backtest, rep.current_price),
        _news_panel(rep.ticker),
        _agent_council_panel(rep.agents, deep_url="", has_run=bool(rep.agents and not getattr(rep.agents, "error", None))) if rep.agents else "",
        render_html_body(rep),
    ]

    print_css = """
@media print {
  body { background: white !important; color: black !important; }
  .panel, .verdict-banner, .card { background: white !important; border: 1px solid #ccc !important; box-shadow: none !important; page-break-inside: avoid; }
  .badge { border: 1px solid #888 !important; color: black !important; background: #f5f5f5 !important; }
  a { color: black !important; text-decoration: none !important; }
  h1, h2, h3 { color: black !important; }
  .dim, .meta { color: #555 !important; }
  .pos { color: #006400 !important; }
  .neg { color: #8B0000 !important; }
  table { page-break-inside: auto; }
  tr { page-break-inside: avoid; page-break-after: auto; }
  thead { display: table-header-group; }
  .no-print { display: none !important; }
}
.print-banner {
  background: var(--panel-2); border:1px solid var(--line); border-radius:10px;
  padding:12px 16px; margin-bottom:20px; display:flex; gap:12px; align-items:center;
  font-size:13px;
}
.print-banner button {
  background: var(--accent); color: #07112c; border:none; border-radius:6px;
  padding:6px 12px; font-size:13px; font-weight:600; cursor:pointer;
}
@page { margin: 18mm 16mm; size: A4; }
"""

    return HTMLResponse(f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"/>
<title>{rep.ticker} — {rep.company_name}</title>
<style>{HTML_STYLE}{print_css}</style>
</head><body><div class="container shell" style="max-width: 1000px">
  <div class="print-banner no-print">
    🖨 Print dialog will open in a moment. Choose <b>"Save as PDF"</b> as destination, then click Save.
    <button onclick="window.print()">Print / Save PDF</button>
    <a href="/ticker/{rep.ticker}" class="btn ghost no-print" style="margin-left:auto">← Back to dashboard</a>
  </div>

  <div style="margin-bottom: 22px">
    <h1 style="margin:0 0 4px; font-size:26px">{rep.ticker} — {rep.company_name}</h1>
    <div class="dim" style="font-size:13px">Generated {rep.timestamp:%Y-%m-%d %H:%M} · {(rep.sector or '')}</div>
  </div>

  {''.join(sections)}

  <div style="margin-top:24px; padding-top:14px; border-top:1px solid var(--line); font-size:11px; color:var(--mute)">
    Generated by Strategist · data via yfinance + Financial Datasets · educational/research use only.
  </div>
</div>

<script>
  // Auto-fire print dialog ~600ms after paint so the user doesn't have to click
  // (modern browsers will show their native print UI; user chooses "Save as PDF")
  window.addEventListener('load', () => setTimeout(() => window.print(), 600));
</script>
</body></html>""")


@app.get("/api/news/{ticker}")
async def api_news(ticker: str, limit: int = 12) -> JSONResponse:
    """Recent news for a ticker (cached 10 min)."""
    from src.analysis.news import fetch_news
    try:
        items = fetch_news(ticker, limit=limit)
    except Exception as exc:
        return JSONResponse({"error": str(exc), "items": []}, status_code=500)
    return JSONResponse({"ticker": ticker.upper(), "items": items})


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
