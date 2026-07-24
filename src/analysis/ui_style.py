"""Centralized design system for the local Strategist dashboard.

A single CSS string exposed as `DASHBOARD_CSS`. Treat it as the source of
truth for visual styling — pages compose Python f-strings around it.
"""

DASHBOARD_CSS = r"""
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

:root {
  --bg: #060b1a;
  --bg-grad-1: rgba(124, 158, 255, 0.06);
  --bg-grad-2: rgba(46, 204, 122, 0.05);
  --panel: #0f1730;
  --panel-2: #131e3e;
  --panel-hover: #182550;
  --line: #1f2c52;
  --line-strong: #2c3c6e;
  --text: #ecf0f8;
  --dim: #97a3c2;
  --mute: #5e6a87;
  --accent: #7c9eff;
  --accent-2: #5d7fff;
  --buy: #2ecc7a;
  --buy-bg: rgba(46, 204, 122, 0.13);
  --hold: #f5c451;
  --hold-bg: rgba(245, 196, 81, 0.13);
  --sell: #ef5350;
  --sell-bg: rgba(239, 83, 80, 0.13);
  --reduce: #b864c4;
  --reduce-bg: rgba(184, 100, 196, 0.13);
  --na: #6b7280;
  --na-bg: rgba(107, 114, 128, 0.13);
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.3);
  --shadow-md: 0 4px 18px rgba(0,0,0,0.35);
  --shadow-lg: 0 16px 48px rgba(0,0,0,0.5);
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 14px;
  --radius-xl: 22px;
}

* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  background: var(--bg);
  background-image:
    radial-gradient(1200px 600px at 10% -10%, var(--bg-grad-1), transparent 50%),
    radial-gradient(900px 500px at 90% 110%, var(--bg-grad-2), transparent 50%);
  color: var(--text);
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
  font-feature-settings: 'ss01' on, 'cv11' on;
  font-size: 14px;
  line-height: 1.55;
  min-height: 100vh;
}
.mono { font-family: 'JetBrains Mono', ui-monospace, Menlo, monospace; font-feature-settings: 'tnum' on; }

/* ===== Layout shell ===== */
.app { display: grid; grid-template-columns: 240px 1fr; min-height: 100vh; }
@media (max-width: 900px) { .app { grid-template-columns: 1fr; } .sidebar { display: none; } }

.sidebar {
  background: var(--panel);
  border-right: 1px solid var(--line);
  padding: 20px 16px;
  position: sticky;
  top: 0;
  height: 100vh;
  overflow-y: auto;
}
.brand {
  display: flex; align-items: center; gap: 10px;
  font-weight: 800; font-size: 18px; letter-spacing: -0.01em;
  padding: 4px 8px 24px;
}
.brand .logo {
  width: 28px; height: 28px; border-radius: 8px;
  background: linear-gradient(135deg, var(--accent), var(--buy));
  display: grid; place-items: center; color: #0a0f1e; font-weight: 900; font-size: 14px;
  box-shadow: 0 6px 18px rgba(124, 158, 255, 0.4);
}
.brand .sub { color: var(--dim); font-weight: 500; font-size: 12px; }
.nav-section { color: var(--mute); text-transform: uppercase; font-size: 11px; letter-spacing: 0.08em; padding: 12px 10px 6px; }
.nav-item {
  display: flex; align-items: center; gap: 10px;
  padding: 8px 10px; color: var(--dim); border-radius: var(--radius-md);
  text-decoration: none; font-size: 13.5px; font-weight: 500;
  transition: background 120ms ease, color 120ms ease;
}
.nav-item:hover { background: var(--panel-2); color: var(--text); }
.nav-item.active { background: var(--panel-hover); color: var(--text); }
.nav-item .icon { width: 18px; height: 18px; opacity: 0.9; }

.main { padding: 28px 36px 48px; min-width: 0; }
@media (max-width: 900px) { .main { padding: 20px 16px 40px; } }

/* ===== Topbar ===== */
.topbar { display: flex; align-items: center; gap: 16px; margin-bottom: 24px; flex-wrap: wrap; }
.topbar .crumbs { color: var(--dim); font-size: 13px; }
.topbar .crumbs a { color: var(--dim); text-decoration: none; }
.topbar .crumbs a:hover { color: var(--text); }
.topbar .crumbs .sep { color: var(--mute); margin: 0 8px; }
.topbar .pulse { margin-left: auto; display: flex; gap: 12px; color: var(--dim); font-size: 12.5px; }
.topbar .pulse .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--buy); display: inline-block; box-shadow: 0 0 12px var(--buy); }

/* ===== Hero / search ===== */
.hero {
  background: linear-gradient(180deg, var(--panel), var(--panel-2));
  border: 1px solid var(--line);
  border-radius: var(--radius-xl);
  padding: 36px 32px;
  margin-bottom: 24px;
  box-shadow: var(--shadow-md);
  position: relative; overflow: hidden;
}
.hero::before {
  content: ""; position: absolute; inset: 0;
  background: radial-gradient(800px 200px at 20% 0%, rgba(124,158,255,0.15), transparent 60%);
  pointer-events: none;
}
.hero h1 {
  position: relative;
  font-size: 28px; font-weight: 700; margin: 0 0 8px; letter-spacing: -0.015em;
}
.hero .sub { color: var(--dim); margin-bottom: 22px; position: relative; }

form.runner { display: flex; gap: 12px; flex-wrap: wrap; position: relative; }
form.runner .field { flex: 1; min-width: 320px; position: relative; }
form.runner input[type=text] {
  width: 100%;
  font-family: 'JetBrains Mono', monospace; font-size: 15.5px;
  padding: 14px 18px;
  background: rgba(255,255,255,0.03);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius-md);
  color: var(--text);
  outline: none;
  transition: border-color 120ms ease, box-shadow 120ms ease, background 120ms ease;
}
form.runner input[type=text]:focus {
  border-color: var(--accent);
  background: rgba(124, 158, 255, 0.05);
  box-shadow: 0 0 0 3px rgba(124, 158, 255, 0.18);
}
form.runner input::placeholder { color: var(--mute); }
form.runner button {
  font-family: inherit; font-size: 14px; font-weight: 700;
  padding: 14px 28px;
  background: linear-gradient(135deg, var(--accent), var(--accent-2));
  color: #07112c;
  border: none; border-radius: var(--radius-md);
  cursor: pointer;
  transition: transform 120ms ease, box-shadow 120ms ease;
  box-shadow: 0 8px 22px rgba(124,158,255,0.35);
  letter-spacing: 0.02em;
}
form.runner button:hover { transform: translateY(-1px); box-shadow: 0 10px 30px rgba(124,158,255,0.5); }
form.runner button:active { transform: translateY(0); }

.chips { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px; position: relative; }
.chip {
  font-size: 12.5px; font-weight: 600;
  padding: 6px 12px;
  background: rgba(255,255,255,0.04);
  color: var(--dim);
  border: 1px solid var(--line);
  border-radius: 999px;
  text-decoration: none;
  transition: background 120ms ease, color 120ms ease, border-color 120ms ease;
}
.chip:hover { background: var(--panel-hover); color: var(--text); border-color: var(--line-strong); }
.chip .count { color: var(--mute); margin-left: 6px; font-weight: 500; }

/* ===== Cards / panels ===== */
.section { margin-bottom: 32px; }
.section h2 { font-size: 17px; font-weight: 700; margin: 0 0 12px; letter-spacing: -0.005em; display: flex; align-items: center; gap: 10px; }
.section h2 .badge-count { background: var(--panel-2); color: var(--dim); padding: 2px 9px; border-radius: 999px; font-size: 11.5px; font-weight: 600; }
.card-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }
.card {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  padding: 16px;
  transition: transform 140ms ease, border-color 140ms ease, background 140ms ease;
}
.card:hover { border-color: var(--line-strong); background: var(--panel-2); }
.card .title { font-size: 13px; color: var(--dim); margin-bottom: 6px; }
.card .value { font-size: 22px; font-weight: 700; letter-spacing: -0.01em; }
.card .meta { font-size: 12px; color: var(--mute); margin-top: 6px; }

/* ===== Verdict badges ===== */
.badge { display: inline-block; padding: 3px 12px; border-radius: 999px; font-weight: 700; font-size: 11.5px; letter-spacing: 0.04em; text-transform: uppercase; }
.b-BUY, .b-STRONG-BUY { background: var(--buy-bg); color: var(--buy); }
.b-HOLD { background: var(--hold-bg); color: var(--hold); }
.b-REDUCE { background: var(--reduce-bg); color: var(--reduce); }
.b-SELL { background: var(--sell-bg); color: var(--sell); }
.b-N\/A { background: var(--na-bg); color: var(--na); }

.score-pill {
  display: inline-block; padding: 3px 10px; border-radius: 999px; font-weight: 700;
  font-family: 'JetBrains Mono', monospace; font-size: 12px;
  background: rgba(255,255,255,0.05); color: var(--text);
}
.score-pill.score-buy { background: var(--buy-bg); color: var(--buy); }
.score-pill.score-hold { background: var(--hold-bg); color: var(--hold); }
.score-pill.score-sell { background: var(--sell-bg); color: var(--sell); }

/* ===== Overview table ===== */
.tablewrap { background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius-lg); overflow: hidden; }
.tablewrap .toolbar { display: flex; align-items: center; gap: 8px; padding: 12px 16px; border-bottom: 1px solid var(--line); flex-wrap: wrap; }
.tablewrap .toolbar .seg {
  display: inline-flex; background: var(--panel-2); border-radius: 8px; padding: 3px; gap: 2px;
}
.tablewrap .toolbar .seg button {
  background: transparent; border: none; color: var(--dim);
  padding: 6px 12px; font-size: 12.5px; font-weight: 600; border-radius: 6px; cursor: pointer;
}
.tablewrap .toolbar .seg button.active { background: var(--panel-hover); color: var(--text); }
.tablewrap .toolbar input[type=search] {
  background: var(--panel-2); border: 1px solid var(--line); color: var(--text);
  border-radius: 8px; padding: 7px 10px; font-size: 13px; outline: none; font-family: inherit;
}
.tablewrap .toolbar input[type=search]:focus { border-color: var(--accent); }
.tablewrap .toolbar .grow { flex: 1; }
table.data { width: 100%; border-collapse: collapse; font-size: 13.5px; }
table.data th {
  position: sticky; top: 0; background: var(--panel);
  color: var(--mute); font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em;
  font-weight: 600; padding: 10px 14px; text-align: left; cursor: pointer; user-select: none;
  border-bottom: 1px solid var(--line);
}
table.data th .arrow { opacity: 0.4; margin-left: 4px; font-size: 10px; }
table.data th.sorted .arrow { opacity: 1; color: var(--accent); }
table.data td { padding: 12px 14px; border-bottom: 1px solid rgba(31,44,82,0.5); vertical-align: middle; }
table.data tbody tr { cursor: pointer; transition: background 100ms ease; }
table.data tbody tr:hover { background: var(--panel-2); }
table.data tbody tr:last-child td { border-bottom: none; }
table.data td.num { font-family: 'JetBrains Mono', monospace; text-align: right; font-feature-settings: 'tnum' on; }
table.data td.ticker { font-weight: 700; font-size: 14px; }
table.data td.ticker .co { display: block; color: var(--mute); font-size: 11.5px; font-weight: 500; margin-top: 1px; }
.pos { color: var(--buy); }
.neg { color: var(--sell); }
.dim { color: var(--dim); }

/* Sparkline cell */
.spark { width: 110px; height: 28px; }

/* ===== Detail page tabs ===== */
.tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--line); margin-bottom: 20px; overflow-x: auto; }
.tabs a {
  padding: 10px 16px;
  color: var(--dim);
  text-decoration: none;
  font-size: 13px;
  font-weight: 600;
  border-bottom: 2px solid transparent;
  white-space: nowrap;
}
.tabs a:hover { color: var(--text); }
.tabs a.active { color: var(--text); border-color: var(--accent); }

.detail-grid { display: grid; grid-template-columns: 1.4fr 1fr; gap: 16px; margin-bottom: 16px; }
@media (max-width: 1050px) { .detail-grid { grid-template-columns: 1fr; } }

.panel {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  padding: 18px 20px;
  margin-bottom: 16px;
}
.panel h2 { font-size: 15px; margin: 0 0 12px; color: var(--text); display: flex; align-items: center; gap: 8px; }
.panel h2 .count { color: var(--mute); font-weight: 500; font-size: 13px; }
.panel table { width: 100%; border-collapse: collapse; font-size: 13.5px; }
.panel table th, .panel table td { padding: 8px 10px; border-bottom: 1px solid rgba(31,44,82,0.7); }
.panel table th { color: var(--mute); font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em; text-align: left; }
.panel table td.right, .panel table th.right { text-align: right; font-family: 'JetBrains Mono', monospace; }
.panel table tbody tr:last-child td { border-bottom: none; }
.panel .synth { color: var(--text); line-height: 1.65; font-size: 14px; }

.verdict-banner {
  display: flex; flex-wrap: wrap; gap: 28px; padding: 22px 24px;
  background: linear-gradient(135deg, var(--panel), var(--panel-2));
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  margin-bottom: 18px;
}
.verdict-banner .col { display: flex; flex-direction: column; gap: 4px; }
.verdict-banner .lbl { color: var(--mute); font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em; }
.verdict-banner .val { font-size: 22px; font-weight: 700; }
.verdict-banner .meta { color: var(--dim); font-size: 12px; }

.ticker-header { display: flex; flex-wrap: wrap; align-items: baseline; gap: 16px; margin-bottom: 8px; }
.ticker-header .t { font-size: 38px; font-weight: 800; letter-spacing: -0.02em; }
.ticker-header .co { font-size: 16px; color: var(--dim); }
.ticker-header .price { margin-left: auto; font-size: 28px; font-weight: 700; color: var(--accent); font-family: 'JetBrains Mono', monospace; }
.ticker-header .price .chg { font-size: 14px; margin-left: 8px; }
.ticker-meta-row { color: var(--mute); font-size: 12.5px; margin-bottom: 18px; display: flex; gap: 16px; flex-wrap: wrap; }
.ticker-meta-row .pill { padding: 2px 10px; border-radius: 999px; background: var(--panel-2); color: var(--dim); }

/* Actions */
.actions { display: flex; gap: 8px; align-items: center; }
.btn {
  font-family: inherit; font-size: 13px; font-weight: 600;
  padding: 8px 14px; border-radius: 8px; cursor: pointer;
  background: var(--panel-2); color: var(--text); border: 1px solid var(--line);
  text-decoration: none; display: inline-flex; align-items: center; gap: 6px;
  transition: background 120ms ease, border-color 120ms ease;
}
.btn:hover { background: var(--panel-hover); border-color: var(--line-strong); }
.btn.primary { background: linear-gradient(135deg, var(--accent), var(--accent-2)); color: #07112c; border: none; }
.btn.primary:hover { transform: translateY(-1px); box-shadow: 0 8px 22px rgba(124,158,255,0.4); }
.btn.ghost { background: transparent; }

/* ===== Comparison view ===== */
.compare-grid { display: grid; gap: 16px; }
.compare-grid table { background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius-lg); overflow: hidden; }
.compare-grid table th { background: var(--panel-2); }
.compare-grid table td.metric-label { color: var(--dim); font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; width: 180px; }

/* ===== Loading overlay ===== */
.overlay {
  position: fixed; inset: 0;
  background: rgba(6,11,26,0.78); backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);
  display: none; align-items: center; justify-content: center; z-index: 9999;
}
.overlay.show { display: flex; }
.overlay .card {
  background: var(--panel); border: 1px solid var(--line-strong); border-radius: var(--radius-xl);
  padding: 32px 40px; text-align: center; max-width: 420px; box-shadow: var(--shadow-lg);
}
.overlay .spinner {
  width: 40px; height: 40px; border-radius: 50%;
  border: 3px solid var(--line);
  border-top-color: var(--accent);
  animation: spin 0.9s linear infinite;
  margin: 0 auto 16px;
}
@keyframes spin { to { transform: rotate(360deg); } }
.overlay .title { font-size: 16px; font-weight: 700; margin-bottom: 6px; }
.overlay .sub { color: var(--dim); font-size: 13px; }

/* ===== Misc ===== */
.empty {
  border: 1px dashed var(--line-strong);
  border-radius: var(--radius-lg);
  padding: 40px 24px;
  text-align: center;
  color: var(--dim);
}
.empty .big { font-size: 18px; font-weight: 700; color: var(--text); margin-bottom: 4px; }
.error-box {
  background: var(--sell-bg); border: 1px solid rgba(239,83,80,0.4); color: var(--sell);
  border-radius: var(--radius-md); padding: 12px 16px; margin-bottom: 16px; font-size: 13px;
}
.warning-box {
  background: var(--hold-bg); border: 1px solid rgba(245,196,81,0.3); color: var(--hold);
  border-radius: var(--radius-md); padding: 10px 14px; margin-bottom: 12px; font-size: 12.5px;
}

.kbd {
  display: inline-block; font-family: 'JetBrains Mono', monospace; font-size: 11px;
  padding: 2px 6px; background: var(--panel-2); border: 1px solid var(--line-strong);
  border-radius: 4px; color: var(--dim);
}

.report-card { background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius-lg); padding: 22px; margin-bottom: 16px; }
.report-card .header { display: flex; align-items: baseline; gap: 14px; margin-bottom: 16px; }
.report-card .ticker { font-size: 26px; font-weight: 800; letter-spacing: -0.01em; }
.report-card .company { color: var(--dim); font-size: 14px; }
.report-card .price { margin-left: auto; font-family: 'JetBrains Mono', monospace; font-size: 22px; font-weight: 700; color: var(--accent); }

.footer { text-align: center; color: var(--mute); font-size: 11.5px; margin-top: 40px; padding-top: 24px; border-top: 1px solid var(--line); }
.footer a { color: var(--dim); }
"""
