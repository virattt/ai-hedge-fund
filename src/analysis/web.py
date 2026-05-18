"""Local web UI for the snapshot system.

Run with:
    poetry run python -m src.analysis.web
or:
    poetry run snapshot-ui

Opens http://127.0.0.1:8765 in your default browser. Type comma-separated
tickers in the box, click Analyze, and the deep snapshot (price, fundamentals,
technicals, analyst consensus, overall verdict) renders for each ticker on
a single page.

Self-contained: no API keys required, pulls data live via yfinance.
"""

from __future__ import annotations

import argparse
import html
import threading
import time
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

from src.analysis import HTML_STYLE, generate_snapshot, render_html_body

app = FastAPI(title="AI Hedge Fund — Ticker Snapshot UI")


_EXTRA_STYLE = """
.shell { padding: 32px 24px; }
.brand { font-size: 28px; font-weight: 700; margin-bottom: 6px; }
.tagline { color: var(--dim); margin-bottom: 24px; }
form.runner { display: flex; gap: 12px; margin-bottom: 32px; flex-wrap: wrap; }
form.runner input[type=text] {
  flex: 1; min-width: 320px; font-size: 16px; padding: 12px 16px;
  border-radius: 10px; border: 1px solid var(--line); background: var(--panel);
  color: var(--text); font-family: inherit;
}
form.runner button {
  font-size: 16px; padding: 12px 28px; border-radius: 10px;
  border: 1px solid var(--buy); background: rgba(30,185,128,0.12);
  color: var(--buy); font-weight: 700; cursor: pointer;
}
form.runner button:hover { background: rgba(30,185,128,0.22); }
.examples { color: var(--dim); font-size: 13px; margin-top: -16px; margin-bottom: 24px; }
.examples a { color: var(--dim); margin-right: 12px; text-decoration: underline dotted; }
.note { color: var(--dim); font-size: 13px; margin-top: 16px; }
.errors { background: rgba(239,83,80,0.15); border:1px solid rgba(239,83,80,0.4);
  color: var(--sell); padding: 12px 16px; border-radius: 10px; margin-bottom: 16px; font-size: 14px; }
.progress { color: var(--hold); margin-bottom: 16px; font-size: 14px; }
hr.sep { border: none; border-top: 1px dashed var(--line); margin: 32px 0; }
"""


def _page_shell(content: str, title: str = "Ticker Snapshot") -> str:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"/>
<title>{html.escape(title)}</title>
<style>{HTML_STYLE}{_EXTRA_STYLE}</style>
</head>
<body><div class="container shell">
<div class="brand">AI Hedge Fund · Ticker Snapshot</div>
<div class="tagline">Live price · 10 fundamentals · 6 technicals · analyst consensus · composite verdict</div>
<form class="runner" method="get" action="/run">
  <input type="text" name="tickers" placeholder="Comma-separated tickers, e.g. NVDA, AAPL, MSFT" autofocus required value="{html.escape(_default_value())}"/>
  <button type="submit">Analyze</button>
</form>
<div class="examples">Try:
<a href="/run?tickers=NVDA">NVDA</a>
<a href="/run?tickers=NVDA,MSFT,GOOGL,META,AMZN">Mag 5</a>
<a href="/run?tickers=AAPL,AVGO,TSM,V,COST">Tier 1B</a>
<a href="/run?tickers=PLTR,SMCI,CRWD">High-risk</a>
</div>
{content}
</div></body></html>"""


_LAST_TICKERS = {"value": ""}


def _default_value() -> str:
    return _LAST_TICKERS["value"]


@app.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    body = '<div class="note">Enter tickers above. Each snapshot takes ~3–5 seconds; multiple tickers run in parallel (max 5 at a time).</div>'
    return HTMLResponse(_page_shell(body))


@app.get("/run", response_class=HTMLResponse)
async def run(tickers: str = "") -> HTMLResponse:
    raw = [t.strip().upper() for t in tickers.replace(";", ",").split(",") if t.strip()]
    # de-dup while preserving order
    seen: set[str] = set()
    cleaned: list[str] = []
    for t in raw:
        if t not in seen:
            seen.add(t)
            cleaned.append(t)
    _LAST_TICKERS["value"] = ", ".join(cleaned)

    if not cleaned:
        return HTMLResponse(_page_shell('<div class="errors">No tickers provided.</div>'))

    started = time.perf_counter()
    bodies: list[str] = []
    errors: list[tuple[str, str]] = []

    # Parallel fetch, bounded to 5 concurrent yfinance calls
    def _one(t: str) -> tuple[str, str | None, str | None]:
        try:
            report = generate_snapshot(t)
            return t, render_html_body(report), None
        except Exception as exc:  # pragma: no cover
            return t, None, f"{type(exc).__name__}: {exc}"

    with ThreadPoolExecutor(max_workers=5) as ex:
        results = list(ex.map(_one, cleaned))

    # Preserve user-entered order
    by_ticker = {t: (body, err) for t, body, err in results}
    for t in cleaned:
        body, err = by_ticker[t]
        if err:
            errors.append((t, err))
        else:
            bodies.append(body)

    elapsed = time.perf_counter() - started
    header = (
        f'<div class="progress">Rendered {len(bodies)} of {len(cleaned)} tickers in {elapsed:.1f}s</div>'
    )
    err_block = ""
    if errors:
        items = "".join(
            f"<li><b>{html.escape(t)}</b>: {html.escape(msg)}</li>" for t, msg in errors
        )
        err_block = f'<div class="errors"><b>Errors:</b><ul>{items}</ul></div>'

    joined = '<hr class="sep"/>'.join(bodies)
    return HTMLResponse(_page_shell(header + err_block + joined))


# --- entry point -----------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Local Ticker Snapshot UI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-open", action="store_true", help="Don't auto-open the browser")
    parser.add_argument("--tickers", default=None, help="Pre-fill tickers in the form")
    args = parser.parse_args()

    if args.tickers:
        _LAST_TICKERS["value"] = args.tickers

    url = f"http://{args.host}:{args.port}/"
    if args.tickers:
        url += f"run?tickers={args.tickers.replace(' ', '')}"

    if not args.no_open:
        # Open browser shortly after the server starts
        def _open():
            time.sleep(1.0)
            try:
                webbrowser.open(url)
            except Exception:
                pass

        threading.Thread(target=_open, daemon=True).start()

    print(f"[snapshot-ui] starting at {url}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
