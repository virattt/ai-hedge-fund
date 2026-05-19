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


def _shell(*, active: str, title: str, body: str, breadcrumbs: list[tuple[str, Optional[str]]] | None = None, pulse_html: str = "", show_macro_in_pulse: bool = True) -> str:
    """Wrap page body in sidebar + topbar + footer chrome."""
    nav_items = [
        ("home", "/", "Home", ""),
        ("saved", "/saved", "Saved", ""),
        ("watchlists", "/watchlists", "Watchlists", ""),
        ("history", "/history", "Recent", ""),
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
      <div class="pulse">{pulse_html or (_macro_strip() if show_macro_in_pulse else '<span class="dot"></span><span>Live · yfinance</span>')}</div>
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


# ---- Macro panel rendering ------------------------------------------------


def _macro_strip() -> str:
    """A single-line macro indicator strip — used in the topbar pulse slot."""
    try:
        from src.analysis.macro import get_macro_snapshot
        m = get_macro_snapshot()
    except Exception:
        return '<span class="dot"></span><span>Live · yfinance</span>'

    parts = [f'<span style="color:{m.regime_color}; font-weight:700">{m.regime_emoji} {html.escape(m.regime_label)}</span>']
    if m.vix is not None:
        chg = ""
        if m.vix_change_1d is not None:
            cls = "neg" if m.vix_change_1d >= 0 else "pos"  # high VIX = risk-off
            chg = f' <span class="{cls}" style="font-size:11px">{m.vix_change_1d*100:+.1f}%</span>'
        parts.append(f'<span title="VIX · {html.escape(m.vix_label or "")}">VIX <b class="mono">{m.vix:.1f}</b>{chg}</span>')
    if m.us_10y is not None:
        parts.append(f'<span title="US 10Y">10Y <b class="mono">{m.us_10y*100:.2f}%</b></span>')
    if m.yield_curve_label:
        parts.append(f'<span title="Yield curve">Curve <b>{html.escape(m.yield_curve_label)}</b></span>')
    if m.fear_greed is not None:
        parts.append(f'<span title="CNN Fear &amp; Greed · {html.escape(m.fear_greed_label or "")}">F&amp;G <b class="mono">{m.fear_greed}</b></span>')
    return " · ".join(parts)


def _macro_panel() -> str:
    """A full panel on the home page with the macro tape."""
    try:
        from src.analysis.macro import get_macro_snapshot
        m = get_macro_snapshot()
    except Exception:
        return ""

    def _val(label: str, value: str, sub: str = "", color: str = "") -> str:
        sub_html = f'<div class="meta">{sub}</div>' if sub else ""
        col = f' style="color:{color}"' if color else ""
        return f'<div class="card"><div class="title">{html.escape(label)}</div><div class="value mono"{col}>{value}</div>{sub_html}</div>'

    cards: list[str] = []
    cards.append(
        f'<div class="card" style="border-color:{m.regime_color}"><div class="title">Market regime</div>'
        f'<div class="value" style="font-size:18px; color:{m.regime_color}">{m.regime_emoji} {html.escape(m.regime_label)}</div>'
        f'<div class="meta">{html.escape(m.regime_blurb)}</div></div>'
    )
    if m.vix is not None:
        chg = ""
        if m.vix_change_1d is not None:
            cls = "neg" if m.vix_change_1d >= 0 else "pos"
            chg = f'<span class="{cls}" style="font-size:12px"> {m.vix_change_1d*100:+.1f}%</span>'
        cards.append(_val(
            "VIX", f"{m.vix:.1f}{chg}",
            sub=html.escape(m.vix_label or ""),
            color=("var(--sell)" if (m.vix or 0) > 25 else "var(--buy)" if (m.vix or 0) < 15 else "var(--hold)"),
        ))
    if m.us_10y is not None:
        sub = ""
        if m.us_2y is not None:
            sub = f"2Y {m.us_2y*100:.2f}% · spread {m.yield_curve_spread:+.2f}pp"
        cards.append(_val("US 10Y yield", f"{m.us_10y*100:.2f}%", sub=html.escape(sub)))
    if m.yield_curve_label:
        cards.append(_val("Yield curve", html.escape(m.yield_curve_label), sub="10Y − 2Y"))
    if m.spx_price is not None:
        chg = ""
        if m.spx_change_1d is not None:
            cls = "pos" if m.spx_change_1d >= 0 else "neg"
            chg = f' <span class="{cls}" style="font-size:13px">{m.spx_change_1d*100:+.2f}%</span>'
        regime_note = []
        if m.spx_above_200dma is True:
            regime_note.append("above 200DMA")
        elif m.spx_above_200dma is False:
            regime_note.append("below 200DMA")
        if m.spx_pct_from_52w_high is not None:
            regime_note.append(f"{m.spx_pct_from_52w_high*100:+.1f}% from 52w high")
        cards.append(_val("S&P 500", f"{m.spx_price:,.0f}{chg}", sub=" · ".join(regime_note)))
    if m.fear_greed is not None:
        col = "var(--sell)" if m.fear_greed <= 25 else "var(--hold)" if m.fear_greed <= 55 else "var(--buy)"
        cards.append(_val("Fear &amp; Greed", str(m.fear_greed), sub=html.escape(m.fear_greed_label or ""), color=col))

    return f"""
<div class="section">
  <h2>🌐 Live macro context <span class="badge-count">{len(cards)}</span></h2>
  <div class="card-grid">{''.join(cards)}</div>
</div>
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

    macro_block = _macro_panel()
    body = f"""
{macro_block}
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
    The fixed 4-horizon table above uses TECHNICAL signals only (RSI / MACD / SMA / Bollinger / volume).
    For historical FUNDAMENTAL verdicts (P/E, ROE, D/E, FCF yield as-of any past date),
    use the <a href="#interactive-backtest-panel" style="color:var(--accent)">Interactive backtest</a> below —
    it pulls point-in-time metrics from Financial Datasets when <code>FINANCIAL_DATASETS_API_KEY</code> is set.
  </div>
</div>
"""


def _interactive_backtest_panel(ticker: str) -> str:
    """Date picker + 'Run backtest' button. AJAX hits /api/backtest-at."""
    from datetime import date as _date, timedelta as _td
    today = _date.today()
    default_date = (today - _td(days=180)).isoformat()
    max_date = (today - _td(days=2)).isoformat()
    # Earliest practical: ~250 trading days before today is roughly 350 calendar days
    min_date = (today - _td(days=365 * 4)).isoformat()
    return f"""
<div class="panel" id="interactive-backtest-panel">
  <h2>📅 Interactive backtest <span class="count">any date</span></h2>
  <div class="dim" style="font-size:13px; margin-bottom:14px">
    Pick any date in the past (≥200 trading days of history needed, so practically anything from late 2022 onward for most tickers). We re-compute the technical verdict as if you'd run it then, and show what actually happened. No new network calls — uses the price series already pulled by the snapshot.
  </div>
  <form id="ibt-form" style="display:flex; gap:10px; align-items:center; flex-wrap:wrap" onsubmit="return runInteractiveBacktest(event)">
    <label class="dim" style="font-size:12.5px">As of</label>
    <input type="date" id="ibt-date" min="{min_date}" max="{max_date}" value="{default_date}"
           style="padding:9px 12px; background:var(--panel-2); border:1px solid var(--line); border-radius:8px; color:var(--text); font-family:inherit; font-size:13px"/>
    <button class="btn primary" type="submit">▶ Run backtest</button>
    <span id="ibt-status" class="dim" style="font-size:12.5px"></span>
  </form>
  <div id="ibt-result" style="margin-top:16px"></div>
</div>

<script>
window.__IBT_TICKER = {_quote_json(ticker)};
async function runInteractiveBacktest(e) {{
  e.preventDefault();
  const dateInput = document.getElementById('ibt-date');
  const status = document.getElementById('ibt-status');
  const resultDiv = document.getElementById('ibt-result');
  const date = dateInput.value;
  if (!date) {{ status.textContent = 'Pick a date.'; return false; }}
  status.textContent = 'Running…';
  resultDiv.innerHTML = '';
  try {{
    const resp = await fetch(`/api/backtest-at/${{window.__IBT_TICKER}}?date=${{date}}`);
    if (!resp.ok) {{
      const err = await resp.json().catch(() => ({{ detail: resp.statusText }}));
      status.textContent = '';
      resultDiv.innerHTML = `<div class="error-box">${{err.detail || 'Backtest failed'}}</div>`;
      return false;
    }}
    const d = await resp.json();
    status.textContent = '';
    const v = d.verdict || '—';
    const vClass = 'b-' + v.replace(' ', '-');
    const retCls = d.realized_return >= 0 ? 'pos' : 'neg';
    const alphaCls = d.alpha === null || d.alpha === undefined ? 'dim' : (d.alpha >= 0 ? 'pos' : 'neg');
    const alphaStr = d.alpha === null || d.alpha === undefined ? '—' : `${{(d.alpha*100 >= 0 ? '+' : '')}}${{(d.alpha*100).toFixed(2)}}%`;
    const correctMark = d.correct === true ? '<span class="pos" style="font-size:18px; font-weight:800">✓ The call paid off</span>'
                      : d.correct === false ? '<span class="neg" style="font-size:18px; font-weight:800">✗ The call missed</span>'
                      : '<span class="dim">— neutral</span>';
    const indicatorRows = (d.indicators || []).map(i => {{
      const sigCls = 'b-' + (i.signal || '').replace(' ', '-');
      return `<tr><td><b>${{i.name}}</b></td><td>${{i.state}}</td><td><span class="badge ${{sigCls}}">${{i.signal}}</span></td><td class="dim">${{i.rationale}}</td></tr>`;
    }}).join('');
    let fundBlock = '';
    if (d.fundamentals) {{
      const f = d.fundamentals;
      if (f.error) {{
        fundBlock = `<div class="warning-box" style="margin-top:14px">📚 Historical fundamentals: ${{f.error}}</div>`;
      }} else if (f.metrics && f.metrics.length) {{
        const fvCls = 'b-' + (f.verdict || '').replace(' ', '-');
        const fRows = f.metrics.map(m => {{
          const mCls = 'b-' + (m.verdict || '').replace(' ', '-');
          const val = m.value === null || m.value === undefined ? '—'
                    : (m.unit === '%' ? `${{(m.value*100).toFixed(2)}}%`
                       : m.unit === 'x' ? `${{m.value.toFixed(2)}}x`
                       : `${{m.value.toFixed(2)}}`);
          return `<tr><td><b>${{m.name}}</b></td><td>${{val}}</td><td><span class="badge ${{mCls}}">${{m.verdict}}</span></td><td class="dim">${{m.rationale}}</td></tr>`;
        }}).join('');
        fundBlock = `
          <div style="margin-top:14px">
            <h3 style="font-size:14px; margin:0 0 8px">📚 Point-in-time fundamentals (Financial Datasets · ${{f.report_period}})</h3>
            <div style="margin-bottom:8px">Historical fundamental verdict: <span class="badge ${{fvCls}}">${{f.verdict}}</span> <span class="dim">(conf ${{(f.confidence*100).toFixed(0)}}%)</span></div>
            <div style="overflow-x:auto"><table class="data">
              <thead><tr><th>Metric</th><th>Value then</th><th>Verdict</th><th>Rationale</th></tr></thead>
              <tbody>${{fRows}}</tbody>
            </table></div>
          </div>`;
      }}
    }}
    resultDiv.innerHTML = `
      <div class="verdict-banner" style="border:1px solid var(--line-strong); margin-bottom:14px">
        <div class="col"><div class="lbl">As of</div><div class="val mono">${{d.as_of_date}}</div><div class="meta">${{d.label}}</div></div>
        <div class="col"><div class="lbl">Verdict then</div><div class="val"><span class="badge ${{vClass}}">${{v}}</span></div><div class="meta">conf ${{(d.confidence*100).toFixed(0)}}%</div></div>
        <div class="col"><div class="lbl">Price then → now</div><div class="val mono">$${{d.price_then.toFixed(2)}} → $${{d.price_now.toFixed(2)}}</div></div>
        <div class="col"><div class="lbl">Realized return</div><div class="val mono ${{retCls}}">${{(d.realized_return*100 >= 0 ? '+' : '')}}${{(d.realized_return*100).toFixed(2)}}%</div></div>
        <div class="col"><div class="lbl">Alpha vs S&amp;P</div><div class="val mono ${{alphaCls}}">${{alphaStr}}</div></div>
        <div class="col"><div class="lbl">Result</div><div class="val">${{correctMark}}</div></div>
      </div>
      <div style="overflow-x:auto">
        <table class="data">
          <thead><tr><th>Indicator</th><th>State then</th><th>Signal</th><th>Why</th></tr></thead>
          <tbody>${{indicatorRows}}</tbody>
        </table>
      </div>
      ${{fundBlock}}
    `;
  }} catch (err) {{
    status.textContent = '';
    resultDiv.innerHTML = `<div class="error-box">${{err.message || err}}</div>`;
  }}
  return false;
}}
</script>
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


def _multi_horizon_panel(price_target_set, current_price: Optional[float]) -> str:
    """Render the 3M / 6M / 12M / 24M price-target table + a visual range bar."""
    if not price_target_set or not price_target_set.targets:
        return ""

    pts = price_target_set
    rows: list[str] = []

    def _money(v: Optional[float]) -> str:
        if v is None or v != v:
            return '<span class="dim">—</span>'
        return f"${v:,.2f}"

    def _pct(v: Optional[float], color: bool = True) -> str:
        if v is None or v != v:
            return '<span class="dim">—</span>'
        cls = ("pos" if v >= 0 else "neg") if color else ""
        sign = "+" if v >= 0 else ""
        return f'<span class="{cls}">{sign}{v*100:.1f}%</span>'

    # Pre-compute the global range for the visual bar (current_price ± widest sigma_t)
    all_vals: list[float] = []
    for t in pts.targets:
        for v in (t.bear_case, t.bull_case, t.combined_target):
            if v is not None and v == v:
                all_vals.append(v)
    if current_price:
        all_vals.append(current_price)
    if not all_vals:
        return ""
    g_lo = min(all_vals) * 0.97
    g_hi = max(all_vals) * 1.03
    g_rng = max(g_hi - g_lo, 1e-6)

    def _xpct(v: float) -> float:
        return max(0.0, min(100.0, (v - g_lo) / g_rng * 100))

    for t in pts.targets:
        # Visual bar: bear -- combined -- bull, with current price marker
        bar = ""
        if t.bear_case is not None and t.bull_case is not None and t.combined_target is not None:
            bear_x = _xpct(t.bear_case)
            bull_x = _xpct(t.bull_case)
            mid_x = _xpct(t.combined_target)
            width = max(0.5, bull_x - bear_x)
            curr_x = _xpct(current_price) if current_price else mid_x
            bar = f"""
<div style="position:relative; height:24px; background:rgba(255,255,255,0.04); border-radius:6px;">
  <div style="position:absolute; left:{bear_x:.1f}%; width:{width:.1f}%; height:100%; background:linear-gradient(90deg, var(--sell-bg), var(--hold-bg), var(--buy-bg)); border-radius:6px; opacity:0.85;"></div>
  <div title="Current" style="position:absolute; left:{curr_x:.1f}%; top:0; bottom:0; width:2px; background:var(--accent); transform:translateX(-1px); box-shadow:0 0 6px var(--accent);"></div>
  <div title="Target ${t.combined_target:,.2f}" style="position:absolute; left:{mid_x:.1f}%; top:50%; width:10px; height:10px; background:var(--text); border-radius:50%; transform:translate(-5px,-5px); box-shadow:0 0 0 2px var(--panel);"></div>
</div>"""

        components_str = ""
        if t.components_used == 3:
            components_str = '<span style="color:var(--buy)">●●●</span>'
        elif t.components_used == 2:
            components_str = '<span style="color:var(--hold)">●●○</span>'
        elif t.components_used == 1:
            components_str = '<span style="color:var(--mute)">●○○</span>'

        rows.append(f"""
<tr>
  <td><b>{html.escape(t.label)}</b><div class="dim" style="font-size:11px">{html.escape(t.notes or '—')}</div></td>
  <td class="num">{_money(t.technical_target)}</td>
  <td class="num">{_money(t.fundamental_target)}</td>
  <td class="num">{_money(t.analyst_target)}</td>
  <td class="num mono" style="font-weight:700">{_money(t.combined_target)}</td>
  <td class="num"><span style="color:var(--sell)">{_money(t.bear_case)}</span></td>
  <td class="num"><span style="color:var(--buy)">{_money(t.bull_case)}</span></td>
  <td class="num">{_pct(t.upside_pct)}</td>
  <td class="num">{_pct(t.downside_pct)}</td>
  <td class="num">{t.confidence:.0f}% <span title="Components ({t.components_used}/3)">{components_str}</span></td>
  <td style="min-width:180px">{bar}</td>
</tr>""")

    vol_note = ""
    if pts.annualized_volatility is not None:
        vol_note = f' · Annualised volatility {pts.annualized_volatility*100:.1f}%'

    return f"""
<div class="panel" id="price-targets-panel">
  <h2>🎯 Multi-horizon price targets <span class="count">3M / 6M / 12M / 24M</span></h2>
  <div class="dim" style="font-size:13px; margin-bottom:14px">
    Each horizon is modelled three ways and then weighted (shorter horizons lean technical, longer lean fundamental + analyst). Bear / bull are 1σ-wide bands from realized vol scaled by √time — wider for longer horizons. The blue vertical line on the visual bar is the current price; the white dot is the combined target.{vol_note}.
  </div>
  <div style="overflow-x:auto">
    <table class="data">
      <thead>
        <tr>
          <th>Horizon</th>
          <th class="right" title="From 6M annualized momentum with decay">Technical</th>
          <th class="right" title="Projected EPS × target P/E">Fundamental</th>
          <th class="right" title="Mean analyst 12M target, scaled to horizon">Analyst</th>
          <th class="right" title="Horizon-weighted combination">Combined</th>
          <th class="right" title="−1σ from realized volatility">Bear case</th>
          <th class="right" title="+1σ from realized volatility">Bull case</th>
          <th class="right" title="Combined vs current">Upside</th>
          <th class="right" title="Bear vs current">Downside</th>
          <th class="right" title="Tighter cluster of lenses = higher confidence">Conf.</th>
          <th>Range (bear ⇢ bull)</th>
        </tr>
      </thead>
      <tbody>
        {''.join(rows)}
      </tbody>
    </table>
  </div>
  <div class="dim" style="font-size:11.5px; margin-top:10px">
    Methodology: 3M weights (Tech 55% / Fund 25% / Analyst 20%) → 24M weights (Tech 10% / Fund 55% / Analyst 35%). EPS growth clamped to [-30%, +60%]; technical decay 0.65 (≤6M) / 0.45 (≤12M) / 0.30 (24M); bear/bull from 1σ band on daily log returns scaled by √(months/12). Targets are estimates, not guarantees.
  </div>
</div>
"""


def _saved_count_pill(ticker: str) -> str:
    """Render a small 'N saved' pill that links to /saved/<TICKER>, server-side."""
    try:
        from src.analysis.storage import list_saved
        items = list_saved(ticker)
        if not items:
            return ""
        return f'<a class="btn ghost" href="/saved/{html.escape(ticker)}" title="View saved snapshots">📁 {len(items)} saved</a>'
    except Exception:
        return ""


def _save_form(ticker: str) -> str:
    """Tiny inline save form with optional note."""
    return f"""
<div class="panel" id="save-panel" style="background:linear-gradient(180deg, var(--panel-2), var(--panel)); border:1px solid var(--line-strong)">
  <h2>💾 Save this analysis</h2>
  <div class="dim" style="font-size:13px; margin-bottom:12px">
    Persist the full snapshot (price, fundamentals, technicals, analyst panel, backtest, final verdict, multi-horizon targets, and AI council results if you've run them) to <code>~/.strategist/saved/</code>. Re-run this ticker later and compare what changed.
  </div>
  <form action="/api/save/{html.escape(ticker)}" method="post" style="display:flex; gap:10px; flex-wrap:wrap; align-items:center">
    <input type="text" name="note" placeholder="Optional note: e.g. 'pre-earnings 2026-05-19'"
           style="flex:1; min-width:280px; padding:10px 14px; background:var(--panel-2); border:1px solid var(--line); border-radius:8px; color:var(--text); font-family:inherit; font-size:13px"/>
    <button class="btn primary" type="submit">★ Save snapshot</button>
  </form>
</div>
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

    # Build the streaming URL — opens the live progress page which auto-
    # redirects to ?deep=1 (cached result) when the council finishes.
    deep_url = f"/ticker/{report.ticker}/streaming"
    if from_tickers:
        deep_url += f"?from={from_qs}"

    # Run the deep panels:
    rec = report.final_verdict
    final_banner = _final_verdict_banner(rec, report) if rec else ""
    rationale_block = _verdict_rationale(rec) if rec else ""
    multi_horizon_block = _multi_horizon_panel(report.price_target_set, report.current_price)
    backtest_block = _backtest_panel(report.backtest, report.current_price)
    interactive_backtest_block = _interactive_backtest_panel(report.ticker)
    agents_block = _agent_council_panel(report.agents, deep_url=deep_url, has_run=bool(report.agents))
    save_block = _save_form(report.ticker)
    saved_pill = _saved_count_pill(report.ticker)
    methodology_block = _methodology_panel(rec) if rec else ""

    body = f"""
<div class="topbar" style="margin-bottom:18px">
  <div class="actions">{back_link}</div>
  <div class="actions" style="margin-left:auto">
    {prev_link}
    {next_link}
    {saved_pill}
    {('<a class="btn primary" href="' + html.escape(deep_url) + '">▶ Run deep analysis</a>') if not deep and not report.agents else ''}
    <a class="btn" href="#price-targets-panel">🎯 Targets</a>
    <a class="btn" href="#backtest-panel">⏪ Backtest</a>
    <a class="btn" href="#interactive-backtest-panel">📅 Custom date</a>
    <a class="btn" href="#save-panel">💾 Save</a>
    <a class="btn" href="/api/snapshot/{html.escape(report.ticker)}" target="_blank">{{ }} JSON</a>
  </div>
</div>

{final_banner}
{rationale_block}

{multi_horizon_block}

{backtest_block}

{interactive_backtest_block}

{agents_block}

<div class="panel">
  <h2>📊 Snapshot detail</h2>
  <div class="dim" style="font-size:13px; margin-bottom:14px">
    The deterministic, rule-based pull from yfinance: price action, 10 fundamental metrics, 6 technical indicators, and analyst consensus. This is the input to the snapshot half of the composite score above.
  </div>
  {render_html_body(report)}
</div>

{save_block}

{methodology_block}
"""
    crumbs: list[tuple[str, Optional[str]]] = [("Home", "/")]
    if from_tickers:
        crumbs.append((f"Results ({len(from_tickers)})", f"/run?tickers={from_qs}"))
    crumbs.append((report.ticker, None))
    return _shell(active="home", title=f"Strategist · {report.ticker}", body=body, breadcrumbs=crumbs)


def streaming_progress_page(ticker: str, from_tickers: list[str]) -> str:
    """Live progress page. Opens EventSource immediately; redirects to ?deep=1 on done."""
    from_qs = quote_plus(",".join(from_tickers)) if from_tickers else ""
    back_link = f'<a class="btn ghost" href="/run?tickers={from_qs}">← Back to results</a>' if from_tickers else f'<a class="btn ghost" href="/ticker/{html.escape(ticker)}">← Back to {html.escape(ticker)}</a>'

    # We render a placeholder grid for the known 14 council nodes. As the SSE
    # stream emits, JS fills/updates the matching card by id.
    council_ids = [
        ("warren_buffett_agent", "Warren Buffett"),
        ("charlie_munger_agent", "Charlie Munger"),
        ("ben_graham_agent", "Ben Graham"),
        ("phil_fisher_agent", "Phil Fisher"),
        ("peter_lynch_agent", "Peter Lynch"),
        ("bill_ackman_agent", "Bill Ackman"),
        ("michael_burry_agent", "Michael Burry"),
        ("mohnish_pabrai_agent", "Mohnish Pabrai"),
        ("nassim_taleb_agent", "Nassim Taleb"),
        ("stanley_druckenmiller_agent", "Stanley Druckenmiller"),
        ("cathie_wood_agent", "Cathie Wood"),
        ("aswath_damodaran_agent", "Aswath Damodaran"),
        ("rakesh_jhunjhunwala_agent", "Rakesh Jhunjhunwala"),
        ("valuation_agent", "Valuation Model"),
        ("sentiment_agent", "Sentiment Analyst"),
        ("fundamentals_agent", "Fundamentals Analyst"),
        ("technicals_agent", "Technicals Analyst"),
        ("risk_management_agent", "Risk Manager"),
        ("portfolio_manager", "Portfolio Manager"),
    ]
    cards = "".join(
        f"""
<div class="stream-card" id="card-{html.escape(aid)}" data-state="pending">
  <div class="card-icon">⋯</div>
  <div class="card-body">
    <div class="card-name">{html.escape(name)}</div>
    <div class="card-status dim">Pending</div>
  </div>
</div>"""
        for aid, name in council_ids
    )

    deep_target_qs = f"from={from_qs}&deep=1" if from_tickers else "deep=1"

    body = f"""
<div class="topbar" style="margin-bottom:18px">
  <div class="actions">{back_link}</div>
  <div class="actions" style="margin-left:auto">
    <a class="btn" href="/api/snapshot/{html.escape(ticker)}" target="_blank">{{ }} JSON</a>
  </div>
</div>

<div class="hero" style="padding:28px 30px">
  <h1>🤖 Running AI Investor Council on <span style="color:var(--accent)">{html.escape(ticker)}</span></h1>
  <div class="sub" id="stream-sub">Live progress. Each analyst applies their own framework. Total elapsed: <b id="stream-elapsed">0.0s</b></div>
  <div id="stream-progress-bar" style="margin-top:14px; height:8px; background:var(--panel-2); border-radius:4px; overflow:hidden">
    <div id="stream-progress-fill" style="width:0%; height:100%; background:linear-gradient(90deg, var(--accent), var(--buy)); transition:width 320ms ease"></div>
  </div>
  <div id="stream-counter" class="dim" style="font-size:12.5px; margin-top:8px">Waiting for first event…</div>
</div>

<div class="panel">
  <h2>📡 Live agent feed</h2>
  <div class="dim" style="font-size:13px; margin-bottom:12px">Each card lights up as its analyst completes. When the council is done, this page redirects to your full deep-analysis report automatically.</div>
  <div class="stream-grid">
    {cards}
  </div>
</div>

<div id="stream-error-box" class="error-box" style="display:none"></div>

<style>
.stream-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 10px; }}
.stream-card {{
  display: flex; align-items: center; gap: 12px;
  padding: 12px 14px;
  background: var(--panel-2);
  border: 1px solid var(--line);
  border-radius: 10px;
  transition: background 220ms ease, border-color 220ms ease, transform 220ms ease;
}}
.stream-card[data-state="working"] {{ border-color: var(--hold); background: var(--hold-bg); }}
.stream-card[data-state="working"] .card-icon {{ color: var(--hold); animation: pulse 1.1s ease-in-out infinite; }}
.stream-card[data-state="done"] {{ border-color: var(--buy); background: var(--buy-bg); transform: scale(1.02); }}
.stream-card[data-state="done"] .card-icon {{ color: var(--buy); }}
.stream-card[data-state="error"] {{ border-color: var(--sell); background: var(--sell-bg); }}
.stream-card[data-state="error"] .card-icon {{ color: var(--sell); }}
.stream-card .card-icon {{
  font-size: 22px; line-height: 1; width: 30px; text-align: center; color: var(--mute);
}}
.stream-card .card-name {{ font-weight: 700; font-size: 13.5px; }}
.stream-card .card-status {{ font-size: 11.5px; margin-top: 2px; }}
@keyframes pulse {{ 0%, 100% {{ opacity: 0.6; }} 50% {{ opacity: 1; }} }}
</style>

<script>
(function() {{
  const TICKER = {_quote_json(ticker)};
  const REDIRECT_URL = {_quote_json(f"/ticker/{ticker}?" + deep_target_qs)};
  const TOTAL = 14;  // approximate; counter updates as we see new agents
  const seen = new Set();
  let doneCount = 0;
  let startedAt = Date.now();

  const elapsedEl = document.getElementById('stream-elapsed');
  const counterEl = document.getElementById('stream-counter');
  const fillEl = document.getElementById('stream-progress-fill');
  const errorEl = document.getElementById('stream-error-box');

  function tickElapsed() {{
    elapsedEl.textContent = ((Date.now() - startedAt) / 1000).toFixed(1) + 's';
  }}
  setInterval(tickElapsed, 100);

  function updateCard(agentId, agentName, state, statusText) {{
    let card = document.getElementById('card-' + agentId);
    if (!card) {{
      const grid = document.querySelector('.stream-grid');
      card = document.createElement('div');
      card.id = 'card-' + agentId;
      card.className = 'stream-card';
      card.innerHTML = `<div class="card-icon">⋯</div><div class="card-body"><div class="card-name">${{agentName}}</div><div class="card-status dim"></div></div>`;
      grid.appendChild(card);
    }}
    card.setAttribute('data-state', state);
    const icon = card.querySelector('.card-icon');
    const status = card.querySelector('.card-status');
    if (state === 'done') {{ icon.textContent = '✓'; status.textContent = 'Done'; }}
    else if (state === 'error') {{ icon.textContent = '✗'; status.textContent = statusText || 'Error'; }}
    else if (state === 'working') {{ icon.textContent = '⋯'; status.textContent = statusText || 'Working…'; }}
    else {{ icon.textContent = '⋯'; status.textContent = statusText || 'Pending'; }}
  }}

  const es = new EventSource('/api/stream-deep/' + TICKER);
  es.onmessage = (e) => {{
    let data;
    try {{ data = JSON.parse(e.data); }} catch (err) {{ return; }}

    if (data.type === 'start') {{
      counterEl.textContent = `Starting ${{data.estimated_agents}} analysts… estimated ${{data.estimated_seconds}}s`;
      startedAt = Date.now();
    }}
    else if (data.type === 'agent_update') {{
      updateCard(data.agent_id, data.agent_name, 'working', data.status);
      seen.add(data.agent_id);
      counterEl.textContent = `${{doneCount}} of ${{Math.max(TOTAL, seen.size)}} done · last: ${{data.agent_name}} (${{data.status}})`;
    }}
    else if (data.type === 'agent_done') {{
      updateCard(data.agent_id, data.agent_name, 'done', 'Done');
      seen.add(data.agent_id);
      doneCount += 1;
      const total = Math.max(TOTAL, seen.size);
      const pct = Math.min(100, Math.round((doneCount / total) * 100));
      fillEl.style.width = pct + '%';
      counterEl.textContent = `${{doneCount}} of ${{total}} done`;
    }}
    else if (data.type === 'agent_error') {{
      updateCard(data.agent_id, data.agent_name, 'error', data.status);
      seen.add(data.agent_id);
    }}
    else if (data.type === 'done') {{
      fillEl.style.width = '100%';
      counterEl.textContent = `All analysts complete in ${{data.elapsed.toFixed(1)}}s · redirecting…`;
      es.close();
      setTimeout(() => {{ window.location.href = REDIRECT_URL; }}, 700);
    }}
    else if (data.type === 'error') {{
      errorEl.style.display = 'block';
      errorEl.textContent = 'Pipeline failed: ' + (data.message || 'unknown error');
      counterEl.textContent = 'Stopped on error.';
      es.close();
    }}
  }};
  es.onerror = () => {{
    errorEl.style.display = 'block';
    errorEl.textContent = 'Stream connection lost. The pipeline may still be running — try refreshing /ticker/' + TICKER + '?deep=1 in a minute.';
  }};
}})();
</script>
"""
    crumbs = [
        ("Home", "/"),
        (ticker, f"/ticker/{ticker}"),
        ("Streaming", None),
    ]
    return _shell(active="home", title=f"Strategist · {ticker} · Streaming", body=body, breadcrumbs=crumbs)


def _quote_json(s: str) -> str:
    import json as _j
    return _j.dumps(s)


def saved_list_page(items: list[dict], ticker: Optional[str] = None) -> str:
    """List saved snapshots across (optionally just one) tickers."""
    if not items:
        body = f"""
<div class="section">
  <h2>📁 Saved analyses{(' · ' + html.escape(ticker)) if ticker else ''}</h2>
  <div class="empty">
    <div class="big">No saved snapshots yet</div>
    Run any ticker analysis, scroll to the bottom of the detail page, and click <b>★ Save snapshot</b>. Your saves live in <code>~/.strategist/saved/</code>.
  </div>
</div>
"""
        crumbs: list[tuple[str, Optional[str]]] = [("Home", "/"), ("Saved", None)]
        return _shell(active="watchlists", title="Strategist · Saved", body=body, breadcrumbs=crumbs)

    cards: list[str] = []
    for s in items:
        verdict_badge = _badge(s.get("verdict") or "—") if s.get("verdict") and s.get("verdict") != "—" else ""
        score = s.get("score")
        score_html = f'<span class="mono" style="font-size:13px; color:var(--mute)">{score:.0f}/100</span>' if score is not None else ""
        price_html = _fmt_money(s.get("price_at_save"))
        note_html = html.escape(s.get("note") or "")
        compare_url = f"/compare-saved/{s['ticker']}/{s['timestamp']}"
        cards.append(f"""
<div class="card">
  <div style="display:flex; align-items:baseline; gap:10px; margin-bottom:6px">
    <b style="font-size:16px">{html.escape(s['ticker'])}</b>
    {verdict_badge}
    {score_html}
  </div>
  <div class="dim" style="font-size:12.5px">Saved {html.escape(s['saved_at'])}</div>
  <div class="mono" style="margin-top:4px; font-size:13px">Price @ save: {price_html}</div>
  {f'<div style="margin-top:8px; color:var(--text); font-size:13px; font-style:italic">"{note_html}"</div>' if note_html else ''}
  <div style="margin-top:10px; display:flex; gap:6px; flex-wrap:wrap">
    <a class="btn primary" href="{compare_url}">⇆ Compare with now</a>
    <a class="btn" href="/ticker/{html.escape(s['ticker'])}">Open ticker</a>
  </div>
</div>""")

    body = f"""
<div class="section">
  <div class="topbar" style="margin-bottom:18px">
    <div>
      <h1 style="margin:0; font-size:24px">📁 Saved analyses</h1>
      <div class="dim" style="font-size:13px; margin-top:4px">{len(items)} snapshot{'s' if len(items) != 1 else ''} {('for ' + html.escape(ticker)) if ticker else 'across all tickers'}</div>
    </div>
  </div>
  <div class="card-grid">
    {''.join(cards)}
  </div>
</div>
"""
    crumbs = [("Home", "/"), ("Saved" + ((' · ' + ticker) if ticker else ''), None)]
    return _shell(active="watchlists", title="Strategist · Saved", body=body, breadcrumbs=crumbs)


def compare_saved_page(saved: dict, current: SnapshotReport) -> str:
    """Side-by-side: saved snapshot vs current. Highlights what changed."""
    ticker = current.ticker
    saved_price = saved.get("current_price")
    now_price = current.current_price
    realized = None
    if saved_price and now_price:
        realized = now_price / saved_price - 1.0
    saved_at = saved.get("_meta", {}).get("saved_at", "")
    note = saved.get("_meta", {}).get("note", "")
    saved_fv = saved.get("final_verdict") or {}
    saved_action = saved_fv.get("action") or "—"
    saved_score = saved_fv.get("composite_score")
    saved_target_mid = saved_fv.get("price_target_mid")
    saved_target_low = saved_fv.get("price_target_low")
    saved_target_high = saved_fv.get("price_target_high")
    saved_hold = saved_fv.get("hold_period_label", "—")

    cur_fv = current.final_verdict
    cur_action = cur_fv.action if cur_fv else "—"
    cur_score = cur_fv.composite_score if cur_fv else None
    cur_target = cur_fv.price_target_mid if cur_fv else None
    cur_hold = cur_fv.hold_period_label if cur_fv else "—"

    def _row(label: str, saved_val: str, cur_val: str, delta: str = "") -> str:
        return f"<tr><td class='metric-label'>{html.escape(label)}</td><td>{saved_val}</td><td>{cur_val}</td><td>{delta}</td></tr>"

    def _money_or_dash(v) -> str:
        if v is None:
            return '<span class="dim">—</span>'
        try:
            return _fmt_money(float(v))
        except Exception:
            return str(v)

    def _delta_money(saved_v, cur_v) -> str:
        if saved_v is None or cur_v is None:
            return ""
        try:
            d = float(cur_v) - float(saved_v)
            pct = d / float(saved_v) if float(saved_v) else 0
            cls = "pos" if d >= 0 else "neg"
            return f'<span class="{cls}">{d:+,.2f} ({pct*100:+.1f}%)</span>'
        except Exception:
            return ""

    def _delta_score(saved_v, cur_v) -> str:
        if saved_v is None or cur_v is None:
            return ""
        try:
            d = float(cur_v) - float(saved_v)
            cls = "pos" if d >= 0 else "neg"
            return f'<span class="{cls}">{d:+.1f}</span>'
        except Exception:
            return ""

    # Map saved fundamentals by name for diffing
    saved_fund = {m.get("name"): m for m in (saved.get("fundamental_metrics") or [])}
    cur_fund = {m.name: m for m in current.fundamental_metrics}
    saved_tech = {i.get("name"): i for i in (saved.get("technical_indicators") or [])}
    cur_tech = {i.name: i for i in current.technical_indicators}

    fund_rows: list[str] = []
    for name in cur_fund:
        s_row = saved_fund.get(name) or {}
        c_row = cur_fund[name]
        s_val = s_row.get("value")
        c_val = c_row.value
        s_verdict = s_row.get("verdict", "—")
        c_verdict = c_row.verdict
        verdict_changed = s_verdict and s_verdict != "—" and s_verdict != c_verdict
        change_mark = ' <span class="pos" style="font-size:11px">⬤ changed</span>' if verdict_changed else ""
        fund_rows.append(f"""
<tr>
  <td>{html.escape(name)}</td>
  <td class="num">{html.escape(str(s_val) if s_val is not None else '—')}</td>
  <td>{_badge(s_verdict) if s_verdict and s_verdict != '—' else '<span class="dim">—</span>'}</td>
  <td class="num">{c_row.fmt_value()}</td>
  <td>{_badge(c_verdict)}{change_mark}</td>
</tr>""")

    tech_rows: list[str] = []
    for name in cur_tech:
        s_row = saved_tech.get(name) or {}
        c_row = cur_tech[name]
        s_signal = s_row.get("signal", "—")
        c_signal = c_row.signal
        sig_changed = s_signal and s_signal != "—" and s_signal != c_signal
        change_mark = ' <span class="pos" style="font-size:11px">⬤ flipped</span>' if sig_changed else ""
        tech_rows.append(f"""
<tr>
  <td>{html.escape(name)}</td>
  <td>{_badge(s_signal) if s_signal and s_signal != '—' else '<span class="dim">—</span>'}</td>
  <td>{_badge(c_signal)}{change_mark}</td>
</tr>""")

    realized_block = ""
    if realized is not None:
        cls = "pos" if realized >= 0 else "neg"
        # Was the saved verdict right?
        verdict_call = ""
        if saved_action and saved_action != "—":
            if "BUY" in saved_action:
                hit = realized > 0
            elif "SELL" in saved_action or "REDUCE" in saved_action:
                hit = realized < 0
            elif "HOLD" in saved_action:
                hit = abs(realized) < 0.15
            else:
                hit = None
            if hit is True:
                verdict_call = '<span class="pos">✓ The saved call paid off</span>'
            elif hit is False:
                verdict_call = '<span class="neg">✗ The saved call missed</span>'

        realized_block = f"""
<div class="panel" style="background:linear-gradient(180deg, var(--panel-2), var(--panel))">
  <h2>⏱ Realized since save</h2>
  <div style="display:flex; gap:36px; flex-wrap:wrap; align-items:center">
    <div><div class="dim" style="font-size:11px; text-transform:uppercase">Price at save</div><div class="mono" style="font-size:20px; font-weight:700">{_money_or_dash(saved_price)}</div></div>
    <div><div class="dim" style="font-size:11px; text-transform:uppercase">Price now</div><div class="mono" style="font-size:20px; font-weight:700">{_money_or_dash(now_price)}</div></div>
    <div><div class="dim" style="font-size:11px; text-transform:uppercase">Realized return</div><div class="mono {cls}" style="font-size:22px; font-weight:800">{realized*100:+.2f}%</div></div>
    <div>{verdict_call}</div>
  </div>
</div>"""

    note_block = ""
    if note:
        note_block = f'<div class="warning-box" style="font-style:italic">"{html.escape(note)}"</div>'

    body = f"""
<div class="topbar" style="margin-bottom:18px">
  <div>
    <h1 style="margin:0; font-size:24px">⇆ Comparing {html.escape(ticker)}</h1>
    <div class="dim" style="font-size:13px; margin-top:4px">Saved <b>{html.escape(saved_at)}</b> vs <b>now</b> ({current.timestamp:%Y-%m-%d %H:%M})</div>
  </div>
  <div class="actions" style="margin-left:auto">
    <a class="btn" href="/saved/{html.escape(ticker)}">← All saved</a>
    <a class="btn" href="/ticker/{html.escape(ticker)}">Open current</a>
  </div>
</div>
{note_block}
{realized_block}

<div class="panel">
  <h2>📋 Headline diff</h2>
  <table class="data">
    <thead><tr><th>Field</th><th>Saved</th><th>Now</th><th>Δ</th></tr></thead>
    <tbody>
      <tr><td class="metric-label">Verdict</td><td>{_badge(saved_action)}</td><td>{_badge(cur_action)}</td><td>{('<span class="pos">⬤ unchanged</span>' if saved_action == cur_action else '<span class="neg">⬤ changed</span>')}</td></tr>
      <tr><td class="metric-label">Composite score</td><td class="num mono">{saved_score:.0f}/100</td><td class="num mono">{cur_score:.0f}/100</td><td>{_delta_score(saved_score, cur_score)}</td></tr>
      <tr><td class="metric-label">Current price</td><td class="num mono">{_money_or_dash(saved_price)}</td><td class="num mono">{_money_or_dash(now_price)}</td><td>{_delta_money(saved_price, now_price)}</td></tr>
      <tr><td class="metric-label">12M price target (mid)</td><td class="num mono">{_money_or_dash(saved_target_mid)}</td><td class="num mono">{_money_or_dash(cur_target)}</td><td>{_delta_money(saved_target_mid, cur_target)}</td></tr>
      <tr><td class="metric-label">Hold period</td><td>{html.escape(saved_hold)}</td><td>{html.escape(cur_hold)}</td><td>{('<span class="dim">same</span>' if saved_hold == cur_hold else '<span class="neg">changed</span>')}</td></tr>
    </tbody>
  </table>
</div>

<div class="grid">
  <div class="panel">
    <h2>10 Fundamentals · diff</h2>
    <table class="data">
      <thead><tr><th>Metric</th><th class="right">Saved value</th><th>Saved verdict</th><th class="right">Now</th><th>Now verdict</th></tr></thead>
      <tbody>{''.join(fund_rows)}</tbody>
    </table>
  </div>
  <div class="panel">
    <h2>6 Technicals · diff</h2>
    <table class="data">
      <thead><tr><th>Indicator</th><th>Saved signal</th><th>Now signal</th></tr></thead>
      <tbody>{''.join(tech_rows)}</tbody>
    </table>
  </div>
</div>
"""
    crumbs = [
        ("Home", "/"),
        ("Saved", "/saved"),
        (f"{ticker}", f"/saved/{ticker}"),
        ("Compare", None),
    ]
    return _shell(active="watchlists", title=f"Strategist · Compare {ticker}", body=body, breadcrumbs=crumbs)


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
