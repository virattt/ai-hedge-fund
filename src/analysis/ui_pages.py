"""HTML page templates for the Strategist dashboard.

Each function returns a complete <!doctype html>...</html> string. Pages share
the chrome (sidebar, topbar, footer) via `_shell()`. Heavy use of f-strings on
purpose — keeps the templating mental model trivial and lets us evolve the UI
without adding a templating engine.
"""

from __future__ import annotations

import html
import json
from datetime import datetime
from typing import Iterable, Optional
from urllib.parse import quote_plus

from src.analysis.renderers import render_html_body
from src.analysis.snapshot import SnapshotReport
from src.analysis.ui_style import DASHBOARD_CSS

# ---- Presets shown as chips on the home page ------------------------------

PRESETS: list[tuple[str, str, list[str]]] = [
    ("Mag 7", "Largest US tech", ["AAPL", "MSFT", "GOOGL", "META", "AMZN", "NVDA", "TSLA"]),
    ("Tier 1 Compounders", "Best risk-adj. now", ["NVDA", "MSFT", "GOOGL", "META", "AMZN", "AAPL", "AVGO", "TSM", "V", "COST"]),
    ("AI Compute", "Picks-and-shovels", ["NVDA", "AVGO", "TSM", "AMD", "ASML", "MU", "SMCI"]),
    ("Defense", "Geopolitical tailwind", ["LMT", "RTX", "NOC", "GD", "PLTR"]),
    ("GLP-1 / Healthcare", "Obesity + pipelines", ["LLY", "NVO", "ABBV", "MRK", "PFE", "ISRG"]),
    ("Financial leaders", "Best-in-class banks", ["JPM", "GS", "MS", "BRK.B", "V", "MA"]),
    ("High-risk thematic", "Higher beta", ["PLTR", "SMCI", "CRWD", "MDB", "SNOW", "TSLA"]),
    ("Contrarian", "Beaten-down quality", ["CVS", "PFE", "NKE", "SBUX", "PYPL", "F", "GM"]),
]


# ---- Common chrome --------------------------------------------------------


def _shell(*, active: str, title: str, body: str, breadcrumbs: list[tuple[str, Optional[str]]] | None = None, pulse_html: str = "") -> str:
    """Wrap page body in sidebar + topbar + footer chrome."""
    nav_items = [
        ("home", "/", "Home", "M3 9l9-7 9 7v11a2 2 0 0 1-2 2h-4v-7H9v7H5a2 2 0 0 1-2-2V9z"),
        ("watchlists", "/watchlists", "Watchlists", "M5 5h14v14H5z M5 9h14 M5 13h14 M5 17h14"),
        ("history", "/history", "Recent", "M12 8v5l3 3 M21 12a9 9 0 1 1-3-6.7"),
    ]
    nav_html = []
    for key, href, label, _path in nav_items:
        cls = "nav-item active" if active == key else "nav-item"
        nav_html.append(f'<a class="{cls}" href="{href}"><span class="icon">•</span>{html.escape(label)}</a>')

    crumb_html = ""
    if breadcrumbs:
        parts: list[str] = []
        for i, (label, href) in enumerate(breadcrumbs):
            if href and i < len(breadcrumbs) - 1:
                parts.append(f'<a href="{href}">{html.escape(label)}</a>')
            else:
                parts.append(f'<span>{html.escape(label)}</span>')
        crumb_html = '<span class="sep">/</span>'.join(parts)

    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{html.escape(title)}</title>
<style>{DASHBOARD_CSS}</style>
</head>
<body>
<div class="app">
  <aside class="sidebar">
    <div class="brand">
      <div class="logo">S</div>
      <div>Strategist<div class="sub">AI hedge fund · local</div></div>
    </div>
    <div class="nav-section">Navigate</div>
    {''.join(nav_html)}
    <div class="nav-section" style="margin-top:24px">Shortcuts</div>
    <div style="padding:0 10px; color:var(--mute); font-size:12px; line-height:1.8">
      <div><span class="kbd">/</span> Focus search</div>
      <div><span class="kbd">Enter</span> Analyze</div>
      <div><span class="kbd">Esc</span> Close</div>
    </div>
  </aside>
  <main class="main">
    <div class="topbar">
      <div class="crumbs">{crumb_html}</div>
      <div class="pulse">{pulse_html or '<span class="dot"></span><span>Live · yfinance</span>'}</div>
    </div>
    {body}
    <div class="footer">
      Educational and research use only. Not investment advice.
      · <a href="https://github.com/virattt/ai-hedge-fund" target="_blank" rel="noopener">Upstream repo</a>
    </div>
  </main>
</div>

<div id="overlay" class="overlay">
  <div class="card">
    <div class="spinner"></div>
    <div class="title" id="overlay-title">Analyzing tickers...</div>
    <div class="sub" id="overlay-sub">Pulling live data — usually 3-5 sec per ticker, run in parallel.</div>
  </div>
</div>

<script>
{_CLIENT_JS}
</script>
</body></html>
"""


_CLIENT_JS = r"""
// --- Loading overlay on form submit -------------------------------------
(function(){
  const form = document.querySelector('form.runner');
  if (!form) return;
  form.addEventListener('submit', (e) => {
    const input = form.querySelector('input[name=tickers]');
    if (!input || !input.value.trim()) return;
    const tickers = input.value.split(',').map(s => s.trim().toUpperCase()).filter(Boolean);
    const overlay = document.getElementById('overlay');
    const title = document.getElementById('overlay-title');
    const sub = document.getElementById('overlay-sub');
    title.textContent = 'Analyzing ' + tickers.length + ' ticker' + (tickers.length>1?'s':'');
    sub.textContent = tickers.join(', ');
    overlay.classList.add('show');
  });
})();

// --- '/' keyboard shortcut to focus the search ---------------------------
window.addEventListener('keydown', (e) => {
  if (e.key === '/' && !['INPUT','TEXTAREA'].includes(document.activeElement.tagName)) {
    const inp = document.querySelector('input[name=tickers]');
    if (inp) { inp.focus(); e.preventDefault(); }
  }
  if (e.key === 'Escape') {
    document.getElementById('overlay')?.classList.remove('show');
  }
});

// --- Recent searches in localStorage -------------------------------------
const RECENT_KEY = 'strategist:recent';
function getRecent() {
  try { return JSON.parse(localStorage.getItem(RECENT_KEY)) || []; } catch { return []; }
}
function pushRecent(tickers) {
  if (!tickers || !tickers.length) return;
  const norm = tickers.join(',');
  let list = getRecent().filter(x => x.tickers !== norm);
  list.unshift({tickers: norm, when: Date.now()});
  list = list.slice(0, 12);
  localStorage.setItem(RECENT_KEY, JSON.stringify(list));
}
// Populate recents block if present on this page
(function(){
  const slot = document.getElementById('recents-slot');
  if (!slot) return;
  const list = getRecent();
  if (!list.length) { slot.innerHTML = '<div class="empty"><div class="big">No history yet</div>Run an analysis and it will land here.</div>'; return; }
  slot.innerHTML = list.map(r => {
    const t = new Date(r.when);
    const ago = (Date.now() - r.when) / 1000;
    const lbl = ago < 60 ? Math.floor(ago) + 's ago'
      : ago < 3600 ? Math.floor(ago/60) + 'm ago'
      : ago < 86400 ? Math.floor(ago/3600) + 'h ago'
      : t.toLocaleDateString();
    return `<a class="chip" href="/run?tickers=${encodeURIComponent(r.tickers)}"><b>${r.tickers}</b><span class="count">${lbl}</span></a>`;
  }).join(' ');
})();
// Record recent on a results page
(function(){
  const tickers = window.STRATEGIST_TICKERS;
  if (Array.isArray(tickers) && tickers.length) pushRecent(tickers);
})();

// --- Watchlists ----------------------------------------------------------
const WATCH_KEY = 'strategist:watchlists';
function getWatchlists() {
  try { return JSON.parse(localStorage.getItem(WATCH_KEY)) || []; } catch { return []; }
}
function saveWatchlists(list) { localStorage.setItem(WATCH_KEY, JSON.stringify(list)); }
function renderWatchlists(targetId) {
  const el = document.getElementById(targetId);
  if (!el) return;
  const list = getWatchlists();
  if (!list.length) { el.innerHTML = '<div class="empty"><div class="big">No watchlists yet</div>Create one from an analysis results page.</div>'; return; }
  el.innerHTML = list.map((w, i) => `
    <div class="card">
      <div class="title">${w.name}</div>
      <div class="value mono">${w.tickers.length} tickers</div>
      <div class="meta">${w.tickers.join(', ')}</div>
      <div style="margin-top:10px; display:flex; gap:6px;">
        <a class="btn primary" href="/run?tickers=${encodeURIComponent(w.tickers.join(','))}">Analyze</a>
        <button class="btn" onclick="deleteWatchlist(${i})">Delete</button>
      </div>
    </div>
  `).join('');
}
function deleteWatchlist(i) {
  const list = getWatchlists();
  list.splice(i, 1);
  saveWatchlists(list);
  renderWatchlists('watchlists-slot');
}
function saveCurrentAsWatchlist() {
  const tickers = window.STRATEGIST_TICKERS;
  if (!Array.isArray(tickers) || !tickers.length) return;
  const name = prompt('Name this watchlist:', tickers.slice(0,3).join(', '));
  if (!name) return;
  const list = getWatchlists();
  list.unshift({name, tickers, when: Date.now()});
  saveWatchlists(list);
  alert('Watchlist saved.');
}
renderWatchlists('watchlists-slot');

// --- Table sort + filter -------------------------------------------------
(function(){
  const table = document.getElementById('overview-table');
  if (!table) return;
  const search = document.getElementById('overview-search');
  const filterButtons = document.querySelectorAll('[data-filter]');
  let activeFilter = 'all';
  let sortCol = -1;
  let sortDir = 1;

  function applyFilters() {
    const term = (search?.value || '').toLowerCase().trim();
    Array.from(table.tBodies[0].rows).forEach(row => {
      const ticker = row.dataset.ticker || '';
      const verdict = (row.dataset.verdict || '').toLowerCase();
      const sector = (row.dataset.sector || '').toLowerCase();
      const matchTerm = !term || ticker.toLowerCase().includes(term) || sector.includes(term);
      const matchFilter = activeFilter === 'all'
        || (activeFilter === 'buy' && (verdict === 'buy' || verdict === 'strong buy'))
        || (activeFilter === 'hold' && verdict === 'hold')
        || (activeFilter === 'sell' && (verdict === 'sell' || verdict === 'reduce'));
      row.style.display = (matchTerm && matchFilter) ? '' : 'none';
    });
  }

  search?.addEventListener('input', applyFilters);
  filterButtons.forEach(b => b.addEventListener('click', () => {
    filterButtons.forEach(x => x.classList.remove('active'));
    b.classList.add('active');
    activeFilter = b.dataset.filter;
    applyFilters();
  }));

  Array.from(table.tHead.rows[0].cells).forEach((th, i) => {
    th.addEventListener('click', () => {
      if (sortCol === i) sortDir = -sortDir; else { sortCol = i; sortDir = 1; }
      Array.from(table.tHead.rows[0].cells).forEach(c => c.classList.remove('sorted'));
      th.classList.add('sorted');
      const rows = Array.from(table.tBodies[0].rows);
      rows.sort((a, b) => {
        const av = a.cells[i].dataset.sort ?? a.cells[i].textContent.trim();
        const bv = b.cells[i].dataset.sort ?? b.cells[i].textContent.trim();
        const an = parseFloat(av), bn = parseFloat(bv);
        if (!isNaN(an) && !isNaN(bn)) return (an - bn) * sortDir;
        return av.localeCompare(bv) * sortDir;
      });
      const tb = table.tBodies[0];
      rows.forEach(r => tb.appendChild(r));
    });
  });
})();
"""


# ---- Sparkline rendering --------------------------------------------------


def _sparkline_svg(prices: list[float], *, width: int = 110, height: int = 28) -> str:
    if not prices or len(prices) < 2:
        return '<svg class="spark"></svg>'
    lo = min(prices)
    hi = max(prices)
    rng = hi - lo or 1.0
    n = len(prices)
    pts = []
    for i, p in enumerate(prices):
        x = (i / (n - 1)) * (width - 2) + 1
        y = height - 2 - ((p - lo) / rng) * (height - 4)
        pts.append(f"{x:.1f},{y:.1f}")
    is_up = prices[-1] >= prices[0]
    stroke = "var(--buy)" if is_up else "var(--sell)"
    fill = "rgba(46,204,122,0.12)" if is_up else "rgba(239,83,80,0.12)"
    path = "M " + " L ".join(pts)
    poly = path + f" L {pts[-1].split(',')[0]},{height} L {pts[0].split(',')[0]},{height} Z"
    return (
        f'<svg class="spark" viewBox="0 0 {width} {height}" preserveAspectRatio="none">'
        f'<path d="{poly}" fill="{fill}" stroke="none"/>'
        f'<path d="{path}" fill="none" stroke="{stroke}" stroke-width="1.5" stroke-linejoin="round"/>'
        f"</svg>"
    )


# ---- Formatting helpers ---------------------------------------------------


def _fmt_pct(x: Optional[float], *, color: bool = False, na: str = "—") -> str:
    if x is None or x != x:
        return f'<span class="dim">{na}</span>'
    cls = ("pos" if x >= 0 else "neg") if color else ""
    sign = "+" if x >= 0 else ""
    return f'<span class="{cls}">{sign}{x*100:.2f}%</span>'


def _fmt_money(x: Optional[float], na: str = "—") -> str:
    if x is None or x != x:
        return na
    if abs(x) >= 1e12:
        return f"${x/1e12:.2f}T"
    if abs(x) >= 1e9:
        return f"${x/1e9:.2f}B"
    if abs(x) >= 1e6:
        return f"${x/1e6:.2f}M"
    return f"${x:,.2f}"


def _badge(verdict: str) -> str:
    cls = "b-" + verdict.replace(" ", "-")
    return f'<span class="badge {cls}">{html.escape(verdict)}</span>'


def _score_pill(score: float, verdict: str) -> str:
    v = verdict.upper()
    if "BUY" in v:
        cls = "score-buy"
    elif "SELL" in v or "REDUCE" in v:
        cls = "score-sell"
    else:
        cls = "score-hold"
    return f'<span class="score-pill {cls}">{score:.0f}</span>'


# ---- Pages ----------------------------------------------------------------


def home_page() -> str:
    preset_chips = "".join(
        f'<a class="chip" href="/run?tickers={quote_plus(",".join(tk))}">'
        f"<b>{html.escape(name)}</b><span class=\"count\">{len(tk)} · {html.escape(sub)}</span>"
        f"</a>"
        for name, sub, tk in PRESETS
    )

    body = f"""
<div class="hero">
  <h1>Run deep analysis on any US stock — locally, in seconds</h1>
  <div class="sub">Live price action vs S&P 500, 10 fundamentals graded BUY / HOLD / SELL, 6 technicals signaled, analyst consensus with target prices — and a single composite verdict.</div>
  <form class="runner" method="get" action="/run">
    <div class="field">
      <input type="text" name="tickers" placeholder="Type tickers: NVDA, AAPL, MSFT, GOOGL, META…" autofocus required />
    </div>
    <button type="submit">Analyze ↗</button>
  </form>
  <div class="chips">{preset_chips}</div>
</div>

<div class="section">
  <h2>Recent analyses <span class="badge-count" id="recents-count">·</span></h2>
  <div id="recents-slot" class="chips" style="min-height:48px"></div>
</div>

<div class="section">
  <h2>Your watchlists</h2>
  <div id="watchlists-slot" class="card-grid"></div>
</div>
"""
    return _shell(active="home", title="Strategist · Home", body=body, breadcrumbs=[("Home", "/")])


def watchlists_page() -> str:
    body = """
<div class="section">
  <h2>Your watchlists</h2>
  <div id="watchlists-slot" class="card-grid"></div>
</div>
"""
    return _shell(
        active="watchlists",
        title="Strategist · Watchlists",
        body=body,
        breadcrumbs=[("Home", "/"), ("Watchlists", "/watchlists")],
    )


def history_page() -> str:
    body = """
<div class="section">
  <h2>Recent analyses</h2>
  <div id="recents-slot" class="chips" style="min-height:48px"></div>
</div>
"""
    return _shell(
        active="history",
        title="Strategist · Recent",
        body=body,
        breadcrumbs=[("Home", "/"), ("Recent", "/history")],
    )


def results_overview_page(reports: list[SnapshotReport], errors: list[tuple[str, str]], elapsed: float, tickers: list[str]) -> str:
    ticker_qs = quote_plus(",".join(tickers))

    # Summary KPI cards
    n_buy = sum(1 for r in reports if "BUY" in r.overall_verdict_label)
    n_hold = sum(1 for r in reports if r.overall_verdict_label == "HOLD")
    n_sell = sum(1 for r in reports if "SELL" in r.overall_verdict_label or "REDUCE" in r.overall_verdict_label)
    avg_score = (sum(r.composite_score for r in reports) / len(reports)) if reports else 0
    avg_1y = (sum((r.price_returns[4].ticker_return or 0) for r in reports) / len(reports)) if reports else 0

    summary_cards = f"""
<div class="card-grid">
  <div class="card"><div class="title">Tickers analyzed</div><div class="value">{len(reports)}</div><div class="meta">{elapsed:.1f}s elapsed</div></div>
  <div class="card"><div class="title">Buys</div><div class="value pos">{n_buy}</div><div class="meta">{(n_buy/len(reports)*100 if reports else 0):.0f}% of universe</div></div>
  <div class="card"><div class="title">Holds</div><div class="value" style="color:var(--hold)">{n_hold}</div><div class="meta">{(n_hold/len(reports)*100 if reports else 0):.0f}% of universe</div></div>
  <div class="card"><div class="title">Sells / Reduces</div><div class="value neg">{n_sell}</div><div class="meta">{(n_sell/len(reports)*100 if reports else 0):.0f}% of universe</div></div>
  <div class="card"><div class="title">Avg composite</div><div class="value mono">{avg_score:.0f}<span style="font-size:14px; color:var(--mute)">/100</span></div><div class="meta">Higher = more bullish</div></div>
  <div class="card"><div class="title">Avg 1Y return</div><div class="value mono {('pos' if avg_1y>=0 else 'neg')}">{('+' if avg_1y>=0 else '')}{avg_1y*100:.1f}%</div><div class="meta">Universe average</div></div>
</div>
"""

    rows_html = []
    for r in reports:
        # If a final verdict has been attached, use it; otherwise fall back to snapshot composite
        rec = getattr(r, "final_verdict", None)
        display_verdict = rec.action if rec else r.overall_verdict_label
        display_score = rec.composite_score if rec else r.composite_score

        # Backtest hit rate for the column
        hit_rate = None
        if r.backtest and r.backtest.hit_rate is not None:
            hit_rate = r.backtest.hit_rate

        ret_1d = r.price_returns[0].ticker_return if r.price_returns else None
        ret_1w = r.price_returns[1].ticker_return if r.price_returns else None
        ret_1m = r.price_returns[2].ticker_return if r.price_returns else None
        ret_1y = r.price_returns[4].ticker_return if r.price_returns else None
        ret_3y = r.price_returns[5].ticker_return if r.price_returns else None
        # Find specific metrics by name
        metrics = {m.name: m for m in r.fundamental_metrics}
        pe = metrics.get("P/E (TTM)")
        roe = metrics.get("ROE (TTM)")
        rsi_state = next((i.state for i in r.technical_indicators if i.name == "RSI (14)"), "—")

        href = f"/ticker/{r.ticker}?from={ticker_qs}"
        spark = _sparkline_svg(r.price_sparkline) if r.price_sparkline else ""

        def _cell(val: Optional[float], color: bool = True) -> str:
            return f'<td class="num" data-sort="{(val if val is not None and val == val else -999):.6f}">{_fmt_pct(val, color=color)}</td>'

        hit_str = f"{hit_rate*100:.0f}%" if hit_rate is not None else "—"
        hit_sort = (hit_rate or 0)
        rows_html.append(f"""
<tr data-ticker="{html.escape(r.ticker)}" data-verdict="{html.escape(display_verdict)}" data-sector="{html.escape(r.sector or '')}" onclick="location.href='{href}'">
  <td class="ticker">{html.escape(r.ticker)}<span class="co">{html.escape(r.company_name)}</span></td>
  <td class="num" data-sort="{r.current_price or 0:.6f}">{_fmt_money(r.current_price)}</td>
  <td>{spark}</td>
  {_cell(ret_1d)}
  {_cell(ret_1w)}
  {_cell(ret_1m)}
  {_cell(ret_1y)}
  {_cell(ret_3y)}
  <td class="num" data-sort="{(pe.value if pe and pe.value and pe.value==pe.value else 999):.4f}">{pe.fmt_value() if pe else '—'}</td>
  <td class="num" data-sort="{(roe.value if roe and roe.value and roe.value==roe.value else -1):.6f}">{roe.fmt_value() if roe else '—'}</td>
  <td class="num">{html.escape(rsi_state)}</td>
  <td class="num" data-sort="{hit_sort:.4f}">{hit_str}</td>
  <td data-sort="{display_score:.2f}">{_badge(display_verdict)}</td>
  <td class="num" data-sort="{display_score:.2f}">{_score_pill(display_score, display_verdict)}</td>
  <td class="dim">{html.escape(r.sector or '—')}</td>
</tr>""")

    err_block = ""
    if errors:
        items = "".join(f"<li><b>{html.escape(t)}</b>: {html.escape(msg)}</li>" for t, msg in errors)
        err_block = f'<div class="error-box"><b>Errors:</b><ul style="margin:6px 0 0 18px">{items}</ul></div>'

    save_btn = (
        f'<button class="btn" onclick="saveCurrentAsWatchlist()">★ Save as watchlist</button>'
        if reports else ""
    )

    body = f"""
<div class="section">
  <div class="topbar" style="margin-bottom:18px">
    <div>
      <h1 style="margin:0; font-size:24px">Analysis results</h1>
      <div class="dim" style="font-size:13px; margin-top:4px">{html.escape(", ".join(t.ticker for t in reports))}</div>
    </div>
    <div class="actions" style="margin-left:auto">
      <a class="btn" href="/compare?tickers={ticker_qs}">⇆ Compare</a>
      {save_btn}
      <a class="btn ghost" href="/api/snapshots?tickers={ticker_qs}" target="_blank">{{ }} JSON</a>
    </div>
  </div>
  {err_block}
  {summary_cards}
</div>

<div class="section">
  <h2>Overview <span class="badge-count">{len(reports)}</span></h2>
  <div class="tablewrap">
    <div class="toolbar">
      <div class="seg">
        <button class="active" data-filter="all">All</button>
        <button data-filter="buy">Buys</button>
        <button data-filter="hold">Holds</button>
        <button data-filter="sell">Sells / Reduces</button>
      </div>
      <div class="grow"></div>
      <input type="search" id="overview-search" placeholder="Filter ticker or sector…"/>
    </div>
    <div style="overflow-x:auto">
      <table class="data" id="overview-table">
        <thead>
          <tr>
            <th>Ticker</th>
            <th>Price <span class="arrow">▲▼</span></th>
            <th>90d</th>
            <th>1D <span class="arrow">▲▼</span></th>
            <th>1W <span class="arrow">▲▼</span></th>
            <th>1M <span class="arrow">▲▼</span></th>
            <th>1Y <span class="arrow">▲▼</span></th>
            <th>3Y <span class="arrow">▲▼</span></th>
            <th>P/E <span class="arrow">▲▼</span></th>
            <th>ROE <span class="arrow">▲▼</span></th>
            <th>RSI</th>
            <th>Hit rate <span class="arrow">▲▼</span></th>
            <th>Verdict</th>
            <th>Score <span class="arrow">▲▼</span></th>
            <th>Sector</th>
          </tr>
        </thead>
        <tbody>
          {''.join(rows_html)}
        </tbody>
      </table>
    </div>
  </div>
</div>

<script>
window.STRATEGIST_TICKERS = {json.dumps([r.ticker for r in reports])};
</script>
"""
    return _shell(
        active="home",
        title=f"Strategist · {', '.join(t.ticker for t in reports[:3])}{'…' if len(reports)>3 else ''}",
        body=body,
        breadcrumbs=[("Home", "/"), (f"Analysis ({len(reports)})", None)],
    )


# ---- Deep-analysis section renderers -------------------------------------


def _final_verdict_banner(rec, snapshot: SnapshotReport) -> str:
    """Big-glance verdict card at the very top of the detail page."""
    badge = _badge(rec.action)
    score_pct = max(0, min(100, rec.composite_score))
    conf_pct = max(0, min(100, rec.confidence_pct))
    # Color the score bar by verdict family
    bar_color = "var(--buy)" if "BUY" in rec.action else ("var(--sell)" if rec.action in ("SELL","REDUCE") else "var(--hold)")

    upside_block = ""
    if rec.upside_pct is not None and rec.price_target_mid is not None:
        upside_cls = "pos" if rec.upside_pct >= 0 else "neg"
        upside_block = f'<div class="col"><div class="lbl">Price target (mid)</div><div class="val mono">${rec.price_target_mid:,.2f}</div><div class="meta {upside_cls}">{rec.upside_pct*100:+.1f}% upside</div></div>'

    range_block = ""
    if rec.price_target_low and rec.price_target_high:
        range_block = f'<div class="col"><div class="lbl">Target range</div><div class="val mono" style="font-size:15px">${rec.price_target_low:,.0f} – ${rec.price_target_high:,.0f}</div><div class="meta">low / high analyst</div></div>'

    size_color = "var(--buy)" if rec.position_size_pct > 0 else "var(--mute)"

    return f"""
<div class="verdict-banner" style="border: 1px solid var(--line-strong)">
  <div class="col">
    <div class="lbl">Final verdict</div>
    <div class="val">{badge}</div>
    <div class="meta">Confidence {conf_pct:.0f}%</div>
  </div>
  <div class="col">
    <div class="lbl">Composite score</div>
    <div class="val mono">{score_pct:.0f}<span style="font-size:14px;color:var(--mute)">/100</span></div>
    <div style="margin-top:6px; width:140px; height:6px; background:rgba(255,255,255,0.06); border-radius:3px; overflow:hidden">
      <div style="height:100%; width:{score_pct:.0f}%; background:{bar_color}; border-radius:3px"></div>
    </div>
  </div>
  {upside_block}
  {range_block}
  <div class="col">
    <div class="lbl">Hold period</div>
    <div class="val" style="font-size:18px">{html.escape(rec.hold_period_label)}</div>
    <div class="meta">{rec.hold_period_months_min}–{rec.hold_period_months_max} months</div>
  </div>
  <div class="col">
    <div class="lbl">Position size</div>
    <div class="val mono" style="color:{size_color}">{rec.position_size_pct:.1f}%</div>
    <div class="meta">of portfolio</div>
  </div>
  <div class="col">
    <div class="lbl">Risk grade</div>
    <div class="val" style="font-size:18px">{html.escape(rec.risk_grade)}</div>
    <div class="meta">{html.escape(snapshot.ticker)} · {html.escape(snapshot.sector or '—')}</div>
  </div>
</div>
"""


def _verdict_rationale(rec) -> str:
    cat_html = ""
    if rec.key_catalysts:
        items = "".join(f"<li>{html.escape(c)}</li>" for c in rec.key_catalysts)
        cat_html = f'<div class="panel" style="flex:1;min-width:280px"><h2>🔼 Key catalysts <span class="count">{len(rec.key_catalysts)}</span></h2><ul style="margin:0 0 0 18px; line-height:1.7">{items}</ul></div>'
    risk_html = ""
    if rec.key_risks:
        items = "".join(f"<li>{html.escape(r)}</li>" for r in rec.key_risks)
        risk_html = f'<div class="panel" style="flex:1;min-width:280px"><h2>🔻 Key risks <span class="count">{len(rec.key_risks)}</span></h2><ul style="margin:0 0 0 18px; line-height:1.7">{items}</ul></div>'

    return f"""
<div class="panel" style="background: linear-gradient(180deg, var(--panel), var(--panel-2))">
  <h2>📋 How we got there</h2>
  <p class="synth">{html.escape(rec.rationale)}</p>
</div>
<div style="display:flex; gap:16px; flex-wrap:wrap">
  {cat_html}
  {risk_html}
</div>
"""


def _backtest_panel(backtest, current_price: Optional[float], commentary_url: str = "") -> str:
    """Render the multi-horizon technical backtest table + summary."""
    if not backtest or not backtest.points:
        return f"""
<div class="panel" id="backtest-panel">
  <h2>⏪ Track record (backtest) <span class="count">technical</span></h2>
  <div class="dim" style="font-size:13px">
    Backtest requires at least 252 + 200 trading days of price history. Not enough data for this ticker yet.
  </div>
</div>
"""

    pts = backtest.points
    hit = backtest.hit_count
    miss = backtest.miss_count
    hr = backtest.hit_rate
    hr_str = f"{hr*100:.0f}%" if hr is not None else "—"
    aa = backtest.avg_alpha
    aa_str = f"{aa*100:+.1f}%" if aa is not None else "—"

    rows_html = []
    for p in pts:
        # Realized return color
        ret_cls = "pos" if p.realized_return >= 0 else "neg"
        alpha_str = f"{p.alpha*100:+.1f}%" if p.alpha is not None else "—"
        alpha_cls = ("pos" if (p.alpha or 0) >= 0 else "neg") if p.alpha is not None else "dim"
        # Hit/miss icon
        icon = "✓" if p.correct else ("✗" if p.correct is False else "—")
        icon_cls = "pos" if p.correct else ("neg" if p.correct is False else "dim")
        verdict_badge = _badge(p.technical_verdict)
        rows_html.append(f"""
<tr>
  <td><b>{html.escape(p.label)}</b><div class="dim" style="font-size:11.5px">{html.escape(p.as_of_date)}</div></td>
  <td>{verdict_badge}</td>
  <td class="num">${p.price_then:,.2f}</td>
  <td class="num">${p.price_now:,.2f}</td>
  <td class="num {ret_cls}">{p.realized_return*100:+.2f}%</td>
  <td class="num {alpha_cls}">{alpha_str}</td>
  <td class="num {icon_cls}" style="font-size:16px; font-weight:700">{icon}</td>
</tr>""")

    return f"""
<div class="panel" id="backtest-panel">
  <h2>⏪ Track record (backtest) <span class="count">{len(pts)} horizons</span></h2>
  <div class="dim" style="font-size:13px; margin-bottom:14px">
    What would our technical signal model have recommended if you ran it back then — and how did the call play out? Hit / miss compares the BUY / HOLD / SELL direction against the actual realized return. Alpha is excess return vs S&P 500 over the same window.
  </div>

  <div class="card-grid" style="margin-bottom:14px">
    <div class="card"><div class="title">Hit rate</div><div class="value mono">{hr_str}</div><div class="meta">{hit} hits · {miss} misses</div></div>
    <div class="card"><div class="title">Avg α on BUY calls</div><div class="value mono">{aa_str}</div><div class="meta">vs S&amp;P 500</div></div>
    <div class="card"><div class="title">Horizons tested</div><div class="value mono">{len(pts)}</div><div class="meta">1M · 3M · 6M · 1Y</div></div>
  </div>

  <div style="overflow-x:auto">
    <table class="data">
      <thead>
        <tr>
          <th>As of</th>
          <th>Verdict then</th>
          <th class="right">Price then</th>
          <th class="right">Price now</th>
          <th class="right">Realized return</th>
          <th class="right">Alpha vs S&amp;P</th>
          <th class="right">Hit?</th>
        </tr>
      </thead>
      <tbody>
        {''.join(rows_html)}
      </tbody>
    </table>
  </div>

  <div class="dim" style="font-size:12px; margin-top:10px">
    Caveat: backtest uses TECHNICAL signals only (RSI / MACD / SMA / Bollinger / volume), not fundamentals or analyst consensus, since yfinance does not provide historical point-in-time ratios. Treat hit rate as one input — not a guarantee.
  </div>
</div>
"""


def _agent_council_panel(agents, *, deep_url: str, has_run: bool) -> str:
    """Render the AI investor council. Two states: (a) not yet run — show
    CTA + skeleton; (b) run complete — show all signals."""
    if not has_run:
        return f"""
<div class="panel" id="agent-council-panel">
  <h2>🤖 AI Investor Council <span class="count">14+ analysts</span></h2>
  <div class="dim" style="font-size:13px; margin-bottom:16px">
    Run the multi-agent LangGraph pipeline. 14 LLM-driven analyst personas (Buffett, Munger, Lynch, Druckenmiller, Marks, Klarman, Fisher, Pabrai, Taleb, Cathie Wood, Damodaran, Jhunjhunwala, plus Risk &amp; Portfolio Manager) each apply their own framework and produce an independent signal. The Portfolio Manager then weighs all signals into a final BUY / SELL / HOLD with size and confidence.
  </div>
  <div style="display:flex; gap:12px; align-items:center; flex-wrap:wrap; margin-bottom:8px">
    <a class="btn primary" href="{html.escape(deep_url)}">▶ Run deep analysis (≈30-60s)</a>
    <span class="dim" style="font-size:12.5px">Uses your Claude Code subscription (no API key needed) via the fallback wired in <code>src/llm/models.py</code>.</span>
  </div>
</div>
"""

    if agents.error:
        return f"""
<div class="panel" id="agent-council-panel">
  <h2>🤖 AI Investor Council</h2>
  <div class="error-box">
    Agent run failed: {html.escape(agents.error)}<br/>
    The snapshot + backtest verdict above is still valid — it does not depend on the LLM call.
  </div>
</div>
"""

    # Sentiment header bars
    total = agents.total_analysts or 1
    bull = agents.bullish_count
    bear = agents.bearish_count
    neut = agents.neutral_count
    bull_pct = bull / total * 100
    bear_pct = bear / total * 100
    neut_pct = neut / total * 100

    rows_html = []
    for s in agents.agent_signals:
        sig_label = {
            "bullish": "BUY",
            "bearish": "SELL",
            "neutral": "HOLD",
        }.get(s.signal, "HOLD")
        snippet = s.reasoning[:240] + ("…" if len(s.reasoning) > 240 else "")
        rows_html.append(f"""
<tr>
  <td><b>{html.escape(s.agent_name)}</b><div class="dim" style="font-size:11px">{html.escape(s.agent_id)}</div></td>
  <td>{_badge(sig_label)}</td>
  <td class="num">{s.confidence:.0f}%</td>
  <td style="max-width:520px; line-height:1.5; font-size:13px; color:var(--text)">{html.escape(snippet) or '<span class="dim">— no reasoning provided</span>'}</td>
</tr>""")

    pm_block = ""
    if agents.pm_decision:
        pm = agents.pm_decision
        action_badge = _badge(
            "STRONG BUY" if pm.confidence >= 80 and "buy" in pm.action else
            "BUY" if "buy" in pm.action else
            "SELL" if "sell" in pm.action or "short" in pm.action else
            "HOLD"
        )
        pm_block = f"""
<div class="panel" style="border:1px solid var(--line-strong); background:linear-gradient(180deg, var(--panel-2), var(--panel))">
  <h2>👔 Portfolio Manager — Final Decision</h2>
  <div style="display:flex; gap:24px; flex-wrap:wrap; align-items:center; margin-bottom:14px">
    <div><div class="dim" style="font-size:11px; text-transform:uppercase; letter-spacing:0.05em">Action</div><div style="font-size:18px; font-weight:700; margin-top:4px">{action_badge}</div></div>
    <div><div class="dim" style="font-size:11px; text-transform:uppercase; letter-spacing:0.05em">Quantity</div><div class="mono" style="font-size:20px; font-weight:700; margin-top:4px">{pm.quantity:,}</div></div>
    <div><div class="dim" style="font-size:11px; text-transform:uppercase; letter-spacing:0.05em">Confidence</div><div class="mono" style="font-size:20px; font-weight:700; margin-top:4px">{pm.confidence:.0f}%</div></div>
  </div>
  <div style="color:var(--text); font-size:13.5px; line-height:1.6">{html.escape(pm.reasoning[:1200] + ('…' if len(pm.reasoning)>1200 else '')) or '<span class="dim">No reasoning provided.</span>'}</div>
</div>
"""

    return f"""
<div class="panel" id="agent-council-panel">
  <h2>🤖 AI Investor Council <span class="count">{agents.total_analysts} analysts</span></h2>
  <div class="dim" style="font-size:13px; margin-bottom:14px">
    14 LLM-driven analyst personas applied their own framework to this ticker. Below: each verdict + reasoning, sorted bullish → bearish.
    Total elapsed: <b>{agents.elapsed_seconds:.1f}s</b>.
  </div>

  <div style="display:flex; gap:6px; margin-bottom:14px; align-items:center; flex-wrap:wrap">
    <div style="flex:1; min-width:220px; height:36px; background:var(--panel-2); border-radius:8px; overflow:hidden; display:flex">
      <div style="background:var(--buy); width:{bull_pct}%" title="{bull} bullish"></div>
      <div style="background:var(--hold); width:{neut_pct}%" title="{neut} neutral"></div>
      <div style="background:var(--sell); width:{bear_pct}%" title="{bear} bearish"></div>
    </div>
    <div style="font-size:12.5px; color:var(--dim)">
      <span style="color:var(--buy); font-weight:700">{bull} bullish</span> ·
      <span style="color:var(--hold); font-weight:700">{neut} neutral</span> ·
      <span style="color:var(--sell); font-weight:700">{bear} bearish</span>
    </div>
  </div>

  <div style="overflow-x:auto">
    <table class="data">
      <thead>
        <tr><th>Analyst</th><th>Signal</th><th class="right">Conf.</th><th>Reasoning</th></tr>
      </thead>
      <tbody>
        {''.join(rows_html)}
      </tbody>
    </table>
  </div>
</div>

{pm_block}
"""


def _methodology_panel(rec) -> str:
    from src.analysis.final_verdict import compose_methodology
    return f"""
<details class="panel" style="cursor:pointer">
  <summary style="font-size:15px; font-weight:700; cursor:pointer">📐 Methodology — how the final verdict was computed</summary>
  <div style="margin-top:14px; font-size:13.5px; line-height:1.7; color:var(--text)">
    {compose_methodology(rec)}
  </div>
</details>
"""


def ticker_detail_page(report: SnapshotReport, from_tickers: list[str], *, deep: bool = False) -> str:
    """Detail page with the full combined report.

    When `deep=True`, the page assumes `report.agents` is populated. The
    `deep=1` query param triggers this — the orchestrator runs LangGraph
    before rendering. The Final Verdict banner respects either mode.
    """
    # Prev/next nav across the originating result set
    prev_link = next_link = ""
    if from_tickers and report.ticker in from_tickers:
        idx = from_tickers.index(report.ticker)
        if idx > 0:
            prev = from_tickers[idx - 1]
            prev_link = f'<a class="btn" href="/ticker/{prev}?from={quote_plus(",".join(from_tickers))}{"&deep=1" if deep else ""}">← {prev}</a>'
        if idx < len(from_tickers) - 1:
            nxt = from_tickers[idx + 1]
            next_link = f'<a class="btn" href="/ticker/{nxt}?from={quote_plus(",".join(from_tickers))}{"&deep=1" if deep else ""}">{nxt} →</a>'

    from_qs = quote_plus(",".join(from_tickers)) if from_tickers else ""
    back_link = f'<a class="btn ghost" href="/run?tickers={from_qs}">← Back to results</a>' if from_tickers else ""

    # Build the deep-analysis URL (same page with ?deep=1)
    deep_url = f"/ticker/{report.ticker}?deep=1"
    if from_tickers:
        deep_url += f"&from={from_qs}"

    # Run the deep panels:
    rec = report.final_verdict
    final_banner = _final_verdict_banner(rec, report) if rec else ""
    rationale_block = _verdict_rationale(rec) if rec else ""
    backtest_block = _backtest_panel(report.backtest, report.current_price)
    agents_block = _agent_council_panel(report.agents, deep_url=deep_url, has_run=bool(report.agents))
    methodology_block = _methodology_panel(rec) if rec else ""

    body = f"""
<div class="topbar" style="margin-bottom:18px">
  <div class="actions">{back_link}</div>
  <div class="actions" style="margin-left:auto">
    {prev_link}
    {next_link}
    {('<a class="btn primary" href="' + html.escape(deep_url) + '">▶ Run deep analysis</a>') if not deep and not report.agents else ''}
    <a class="btn" href="#backtest-panel">⏪ Backtest</a>
    <a class="btn" href="/api/snapshot/{html.escape(report.ticker)}" target="_blank">{{ }} JSON</a>
  </div>
</div>

{final_banner}
{rationale_block}

{backtest_block}

{agents_block}

<div class="panel">
  <h2>📊 Snapshot detail</h2>
  <div class="dim" style="font-size:13px; margin-bottom:14px">
    The deterministic, rule-based pull from yfinance: price action, 10 fundamental metrics, 6 technical indicators, and analyst consensus. This is the input to the snapshot half of the composite score above.
  </div>
  {render_html_body(report)}
</div>

{methodology_block}
"""
    crumbs: list[tuple[str, Optional[str]]] = [("Home", "/")]
    if from_tickers:
        crumbs.append((f"Results ({len(from_tickers)})", f"/run?tickers={from_qs}"))
    crumbs.append((report.ticker, None))
    return _shell(active="home", title=f"Strategist · {report.ticker}", body=body, breadcrumbs=crumbs)


def compare_page(reports: list[SnapshotReport], errors: list[tuple[str, str]]) -> str:
    if not reports:
        return _shell(
            active="home",
            title="Strategist · Compare",
            body='<div class="empty"><div class="big">Nothing to compare</div>Add 2-5 tickers to the URL: <code>/compare?tickers=NVDA,AAPL</code></div>',
            breadcrumbs=[("Home", "/"), ("Compare", None)],
        )

    headers = "".join(f'<th class="right">{html.escape(r.ticker)}</th>' for r in reports)

    def _row(label: str, cells: Iterable[str]) -> str:
        return f'<tr><td class="metric-label">{html.escape(label)}</td>' + "".join(f'<td class="right">{c}</td>' for c in cells) + "</tr>"

    metric_keys = [
        ("P/E (TTM)", "P/E (TTM)"),
        ("Forward P/E", "Forward P/E"),
        ("PEG", "PEG"),
        ("EV/EBITDA", "EV/EBITDA"),
        ("Debt / Equity", "Debt / Equity"),
        ("ROE (TTM)", "ROE (TTM)"),
        ("ROE (3Y avg)", "ROE (3Y avg)"),
        ("ROIC (proxy)", "ROIC (proxy)"),
        ("FCF Yield", "FCF Yield"),
        ("Revenue Growth (3Y CAGR)", "Revenue Growth (3Y CAGR)"),
    ]

    def cell_for_metric(r: SnapshotReport, key: str) -> str:
        m = next((x for x in r.fundamental_metrics if x.name == key), None)
        if not m:
            return "—"
        return f"<span class='mono'>{html.escape(m.fmt_value())}</span> {_badge(m.verdict)}"

    rows: list[str] = []
    rows.append(_row("Overall verdict", [_badge(r.overall_verdict_label) for r in reports]))
    rows.append(_row("Composite score", [_score_pill(r.composite_score, r.overall_verdict_label) for r in reports]))
    rows.append(_row("Fundamental", [_badge(r.fundamental_verdict) for r in reports]))
    rows.append(_row("Technical", [_badge(r.technical_verdict) for r in reports]))
    rows.append(_row("Analyst consensus", [_badge(r.analyst_verdict_label) for r in reports]))
    rows.append(_row("Current price", [f"<span class='mono'>{_fmt_money(r.current_price)}</span>" for r in reports]))
    rows.append(_row("Market cap", [_fmt_money(r.market_cap) for r in reports]))
    rows.append(_row("Sector", [html.escape(r.sector or '—') for r in reports]))
    rows.append('<tr><td colspan="' + str(1 + len(reports)) + '" style="height:6px;background:var(--bg)"></td></tr>')
    # period returns
    for i, label in enumerate(["1D return", "1W return", "1M return", "6M return", "1Y return", "3Y return"]):
        rows.append(_row(label, [_fmt_pct(r.price_returns[i].ticker_return, color=True) for r in reports]))
    rows.append('<tr><td colspan="' + str(1 + len(reports)) + '" style="height:6px;background:var(--bg)"></td></tr>')
    for _, mk in metric_keys:
        rows.append(_row(mk, [cell_for_metric(r, mk) for r in reports]))
    rows.append('<tr><td colspan="' + str(1 + len(reports)) + '" style="height:6px;background:var(--bg)"></td></tr>')
    # analyst targets
    rows.append(_row("Analysts covering", [str(r.analyst.total_analysts or '—') for r in reports]))
    rows.append(_row("Mean price target", [_fmt_money(r.analyst.mean_target) for r in reports]))
    rows.append(_row("Upside vs current", [_fmt_pct(r.analyst.upside_pct, color=True) for r in reports]))

    err_block = ""
    if errors:
        items = "".join(f"<li><b>{html.escape(t)}</b>: {html.escape(msg)}</li>" for t, msg in errors)
        err_block = f'<div class="error-box"><b>Errors:</b><ul style="margin:6px 0 0 18px">{items}</ul></div>'

    ticker_qs = quote_plus(",".join(r.ticker for r in reports))

    body = f"""
<div class="topbar" style="margin-bottom:18px">
  <div><h1 style="margin:0; font-size:24px">Side-by-side compare</h1>
    <div class="dim" style="font-size:13px; margin-top:4px">{html.escape(' · '.join(r.ticker for r in reports))}</div></div>
  <div class="actions" style="margin-left:auto">
    <a class="btn" href="/run?tickers={ticker_qs}">← Back to overview</a>
  </div>
</div>
{err_block}
<div class="compare-grid">
  <table class="data">
    <thead><tr><th>Metric</th>{headers}</tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
</div>
"""
    return _shell(
        active="home",
        title=f"Strategist · Compare {', '.join(r.ticker for r in reports[:3])}",
        body=body,
        breadcrumbs=[("Home", "/"), ("Results", f"/run?tickers={ticker_qs}"), ("Compare", None)],
    )
