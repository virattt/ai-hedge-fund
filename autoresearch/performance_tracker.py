"""
autoresearch/performance_tracker.py — Log daily portfolio value for performance tracking.

Reads PaperBroker state, computes portfolio value using cached prices, appends to
autoresearch/logs/performance.csv. Use `log` to append today, `report` to show rolling Sharpe.

Usage:
    poetry run python -m autoresearch.performance_tracker log
    poetry run python -m autoresearch.performance_tracker report
"""

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

CACHE_DIR = Path(__file__).resolve().parent / "cache"
LOGS_DIR = Path(__file__).resolve().parent / "logs"
PERF_CSV = LOGS_DIR / "performance.csv"


def load_prices_for_tickers(tickers: list[str]) -> dict[str, float]:
    """Load latest close price for each ticker from any sector cache."""
    prices = {}
    for f in CACHE_DIR.glob("prices*.json"):
        try:
            with open(f) as fp:
                data = json.load(fp)
            for ticker in tickers:
                if ticker in data and data[ticker]:
                    recs = data[ticker]
                    if not recs:
                        continue
                    last = recs[-1] if isinstance(recs[0], dict) else recs[-1]
                    if isinstance(last, dict) and "close" in last:
                        prices[ticker] = float(last["close"])
        except Exception:
            pass
    return prices


def compute_portfolio_value(state_path: str = ".paper_broker_state.json") -> tuple[float, float]:
    """Return (cash, positions_value) from PaperBroker state."""
    path = Path(state_path)
    if not path.exists():
        return 0.0, 0.0
    with open(path) as f:
        data = json.load(f)
    cash = data.get("cash", 0.0)
    positions = data.get("positions", {})
    tickers = list(positions.keys())
    prices = load_prices_for_tickers(tickers)
    pos_value = 0.0
    for ticker, p in positions.items():
        qty = p.get("quantity", 0)
        if qty != 0 and ticker in prices:
            pos_value += qty * prices[ticker]
    return cash, pos_value


def cmd_log(state_path: str):
    """Append today's portfolio value to performance.csv."""
    cash, pos_value = compute_portfolio_value(state_path)
    total = cash + pos_value
    date = datetime.now().strftime("%Y-%m-%d")
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    write_header = not PERF_CSV.exists()
    with open(PERF_CSV, "a", newline="") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(["date", "cash", "positions_value", "total"])
        w.writerow([date, f"{cash:.2f}", f"{pos_value:.2f}", f"{total:.2f}"])
    print(f"Logged {date}: total=${total:,.2f} (cash=${cash:,.2f}, positions=${pos_value:,.2f})")


def _load_benchmark_returns(benchmark_ticker: str = "SPY") -> "pd.Series | None":
    """Load benchmark daily returns from cache."""
    import json
    import pandas as pd
    path = CACHE_DIR / "prices_benchmark.json"
    if benchmark_ticker != "SPY":
        path = CACHE_DIR / "prices.json"
    if not path.exists():
        return None
    with open(path) as f:
        raw = json.load(f)
    if benchmark_ticker not in raw or not raw[benchmark_ticker]:
        return None
    df = pd.DataFrame(raw[benchmark_ticker])
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    return df["close"].pct_change().dropna()


def _sector_attribution(perf_df: "pd.DataFrame", sector_returns: dict[str, "pd.Series"], weights: dict[str, float]) -> dict[str, float]:
    """Compute each sector's contribution to portfolio return (attribution)."""
    import numpy as np
    contrib = {}
    for sector, ret in sector_returns.items():
        w = weights.get(sector, 0)
        if w <= 0 or ret is None or len(ret) < 2:
            contrib[sector] = 0.0
            continue
        common = perf_df.set_index("date").index.intersection(ret.index)
        if len(common) < 2:
            contrib[sector] = 0.0
            continue
        r = ret.reindex(common).fillna(0)
        contrib[sector] = float((1 + r).prod() - 1) * w * 100
    return contrib


def _generate_html_report(
    days: int,
    sharpe: float,
    total_ret: float,
    latest: float,
    bench_ret: float | None,
    contrib: dict[str, float] | None,
    perf_df: "pd.DataFrame",
) -> str:
    """Generate HTML dashboard with equity curve and drawdown charts."""
    rows = ""
    if perf_df is not None and len(perf_df) > 0:
        for _, r in perf_df.tail(30).iterrows():
            d = str(r["date"])[:10]
            rows += f"<tr><td>{d}</td><td>${float(r['total']):,.0f}</td></tr>"
    bench_row = f"<tr><td>SPY</td><td>{bench_ret*100:+.1f}%</td></tr>" if bench_ret is not None else ""
    attr_rows = ""
    if contrib:
        for s in sorted(contrib.keys(), key=lambda x: -contrib[x]):
            attr_rows += f"<tr><td>{s}</td><td>{contrib[s]:+.1f}%</td></tr>"
    equity_data = ""
    dd_data = ""
    if perf_df is not None and len(perf_df) > 0:
        vals = perf_df["total"].astype(float).tolist()
        dates = [str(d)[:10] for d in perf_df["date"]]
        equity_data = json.dumps({"labels": dates, "values": vals})
        peak = vals[0]
        dd_vals = []
        for v in vals:
            peak = max(peak, v)
            dd_vals.append((peak - v) / peak * 100 if peak > 0 else 0)
        dd_data = json.dumps({"labels": dates, "values": dd_vals})
    chart_script = ""
    if equity_data and dd_data:
        chart_script = f"""
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<canvas id="equityChart" width="400" height="150"></canvas>
<canvas id="ddChart" width="400" height="150"></canvas>
<script>
const equity = {equity_data};
const dd = {dd_data};
new Chart(document.getElementById('equityChart'), {{
  type: 'line',
  data: {{ labels: equity.labels, datasets: [{{ label: 'Portfolio', data: equity.values, borderColor: '#2563eb', fill: false }}] }},
  options: {{ responsive: true, plugins: {{ title: {{ display: true, text: 'Equity Curve' }} }} }}
}});
new Chart(document.getElementById('ddChart'), {{
  type: 'line',
  data: {{ labels: dd.labels, datasets: [{{ label: 'Drawdown %', data: dd.values, borderColor: '#dc2626', fill: true }}] }},
  options: {{ responsive: true, plugins: {{ title: {{ display: true, text: 'Drawdown' }} }} }}
}});
</script>"""
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>AI Hedge Fund Dashboard</title>
<style>body{{font-family:sans-serif;margin:2em;}} table{{border-collapse:collapse;}} th,td{{padding:6px 12px;text-align:left;border:1px solid #ccc;}} th{{background:#eee;}}</style>
</head><body>
<h1>AI Hedge Fund — Performance</h1>
<p>Rolling {days}d | Generated {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
<table><tr><th>Metric</th><th>Value</th></tr>
<tr><td>Sharpe</td><td>{sharpe:.2f}</td></tr>
<tr><td>Return</td><td>{total_ret:+.1f}%</td></tr>
<tr><td>Latest</td><td>${latest:,.0f}</td></tr>
{bench_row}</table>
{chart_script}
<h2>Daily Values (last 30)</h2><table><tr><th>Date</th><th>Total</th></tr>{rows}</table>
{f'<h2>Sector Attribution</h2><table><tr><th>Sector</th><th>Contribution</th></tr>{attr_rows}</table>' if attr_rows else ''}
</body></html>"""


def cmd_report(days: int = 60, output_json: str | None = None, output_html: str | None = None, attribution: bool = False):
    """Print rolling Sharpe and recent performance. Optionally vs SPY benchmark."""
    if not PERF_CSV.exists():
        print("No performance data. Run 'log' first.")
        return
    import pandas as pd
    import numpy as np
    df = pd.read_csv(PERF_CSV)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")
    if len(df) < 2:
        print("Need at least 2 days of data.")
        return
    df["return"] = df["total"].pct_change()
    recent = df.tail(days)
    returns = recent["return"].dropna()
    latest = float(recent["total"].iloc[-1]) if len(recent) > 0 else 0
    if len(returns) < 2:
        print("Insufficient returns for Sharpe.")
        if output_json:
            out = {"sharpe": None, "total_return_pct": None, "latest_value": latest, "days": days, "note": "Insufficient data"}
            Path(output_json).parent.mkdir(parents=True, exist_ok=True)
            with open(output_json, "w") as f:
                json.dump(out, f, indent=2)
        return
    sharpe = np.sqrt(252) * returns.mean() / returns.std() if returns.std() > 1e-12 else 0
    total_ret = (recent["total"].iloc[-1] / recent["total"].iloc[0] - 1) * 100
    print(f"Rolling {days}d: Sharpe={sharpe:.2f}, Return={total_ret:+.1f}%")
    print(f"Latest: ${latest:,.2f}")

    contrib_dict: dict[str, float] | None = None
    if attribution:
        from autoresearch.portfolio_backtest import run_sector_backtest, SECTOR_CONFIG, SECTOR_OOS_SHARPE, portfolio_values_to_returns
        start_d = recent["date"].min().strftime("%Y-%m-%d")
        end_d = recent["date"].max().strftime("%Y-%m-%d")
        sector_returns = {}
        for sector, (mod, path) in SECTOR_CONFIG.items():
            try:
                pv, _, _ = run_sector_backtest(mod, path, start=start_d, end=end_d)
                sector_returns[sector] = portfolio_values_to_returns(pv)
            except Exception:
                continue
        oos = {s: max(SECTOR_OOS_SHARPE.get(s, 0), 0.01) for s in sector_returns}
        total_oos = sum(oos.values())
        weights = {s: oos[s] / total_oos for s in sector_returns}
        contrib_dict = _sector_attribution(recent, sector_returns, weights)
        print("Sector attribution (contribution to portfolio return):")
        for s in sorted(contrib_dict.keys(), key=lambda x: -contrib_dict[x]):
            print(f"  {s:14} {contrib_dict[s]:+.1f}%")
    bench = _load_benchmark_returns()
    bench_ret: float | None = None
    if bench is not None and len(recent) > 0:
        start_d, end_d = recent["date"].min(), recent["date"].max()
        bench_sub = bench.loc[start_d:end_d].reindex(recent.set_index("date").index).fillna(0)
        if len(bench_sub) >= 2:
            bench_ret = float((1 + bench_sub).prod() - 1)
            print(f"SPY (same period): {bench_ret*100:+.1f}%")
    if output_json:
        out = {
            "sharpe": round(sharpe, 4),
            "total_return_pct": round(total_ret, 2),
            "latest_value": latest,
            "days": days,
        }
        Path(output_json).parent.mkdir(parents=True, exist_ok=True)
        with open(output_json, "w") as f:
            json.dump(out, f, indent=2)
        print(f"Metrics saved to {output_json}")
    if output_html:
        html = _generate_html_report(days, sharpe, total_ret, latest, bench_ret, contrib_dict, recent)
        Path(output_html).parent.mkdir(parents=True, exist_ok=True)
        Path(output_html).write_text(html, encoding="utf-8")
        print(f"HTML report saved to {output_html}")


def cmd_compare(
    state_path: str,
    days: int = 60,
    output_csv: str | None = None,
    alert_threshold_pp: float | None = None,
    alert_url: str | None = None,
):
    """Compare live portfolio returns vs backtest over same period. Optionally persist to CSV."""
    if not PERF_CSV.exists():
        print("No performance data. Run 'log' first.")
        return
    import pandas as pd
    import numpy as np
    from autoresearch.portfolio_backtest import run_sector_backtest, SECTOR_CONFIG, SECTOR_OOS_SHARPE, portfolio_values_to_returns, compute_portfolio_metrics

    df = pd.read_csv(PERF_CSV)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")
    if len(df) < 2:
        print("Need at least 2 days of data.")
        return
    start = df["date"].min().strftime("%Y-%m-%d")
    end = df["date"].max().strftime("%Y-%m-%d")

    returns_by_sector = {}
    for sector, (mod, path) in SECTOR_CONFIG.items():
        try:
            pv, _, _ = run_sector_backtest(mod, path, start=start, end=end)
            ret = portfolio_values_to_returns(pv)
            returns_by_sector[sector] = ret
        except Exception:
            continue
    if not returns_by_sector:
        print("Could not run backtest.")
        return
    aligned = pd.DataFrame(returns_by_sector).dropna(how="all").ffill().bfill().fillna(0)
    oos = {s: max(SECTOR_OOS_SHARPE.get(s, 0), 0.01) for s in returns_by_sector}
    total_oos = sum(oos.values())
    weights = {s: oos[s] / total_oos for s in returns_by_sector}
    bt_ret = pd.Series(0.0, index=aligned.index)
    for s in returns_by_sector:
        bt_ret = bt_ret + weights[s] * aligned[s].reindex(bt_ret.index).fillna(0)
    live_ret = df.set_index("date")["total"].pct_change().dropna()
    common = live_ret.index.intersection(bt_ret.index)
    if len(common) < 2:
        print("Insufficient overlap for comparison.")
        return
    live_sub = live_ret.reindex(common).fillna(0)
    bt_sub = bt_ret.reindex(common).fillna(0)
    live_total = (1 + live_sub).prod() - 1
    bt_total = (1 + bt_sub).prod() - 1
    diff_pp = (live_total - bt_total) * 100
    print(f"Period: {start} → {end} ({len(common)} days)")
    print(f"Live return:  {live_total*100:+.1f}%")
    print(f"Backtest:     {bt_total*100:+.1f}%")
    print(f"Difference:   {diff_pp:+.1f} pp")
    if output_csv:
        out_path = Path(output_csv)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        write_header = not out_path.exists() or out_path.stat().st_size == 0
        with open(out_path, "a", newline="") as f:
            w = csv.writer(f)
            if write_header:
                w.writerow(["date", "live_return", "live_cum", "bt_return", "bt_cum", "diff_pp"])
            w.writerow([
                end, f"{live_total*100:.2f}", f"{(1+live_sub).prod():.4f}",
                f"{bt_total*100:.2f}", f"{(1+bt_sub).prod():.4f}",
                f"{diff_pp:.2f}",
            ])
        print(f"Appended to {output_csv}")
    if alert_threshold_pp is not None and alert_url and abs(diff_pp) >= alert_threshold_pp:
        import urllib.request
        msg = f"Backtest vs live divergence: {diff_pp:+.1f} pp (threshold {alert_threshold_pp})"
        try:
            req = urllib.request.Request(
                alert_url,
                data=json.dumps({"text": msg}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=10)
            print(f"Alert sent: {msg}")
        except Exception as e:
            print(f"Alert failed: {e}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", choices=["log", "report", "compare"])
    parser.add_argument("--state-path", default=".paper_broker_state.json")
    parser.add_argument("--days", type=int, default=60, help="For report/compare: rolling window")
    parser.add_argument("--output-json", type=str, help="Save report metrics to JSON file")
    parser.add_argument("--output-csv", type=str, help="For compare: append row to CSV for backtest vs live tracking")
    parser.add_argument("--alert-threshold-pp", type=float, help="For compare: alert when |live-bt| exceeds this (e.g. 5)")
    parser.add_argument("--alert-url", type=str, help="Slack webhook URL for divergence alert")
    parser.add_argument("--attribution", action="store_true", help="Show sector-level performance attribution")
    parser.add_argument("--output-html", type=str, help="Save HTML dashboard to file")
    args = parser.parse_args()
    if args.cmd == "log":
        cmd_log(args.state_path)
    elif args.cmd == "compare":
        cmd_compare(
            args.state_path, args.days, args.output_csv,
            getattr(args, "alert_threshold_pp", None),
            getattr(args, "alert_url", None) or __import__("os").environ.get("DAILY_ALERT_URL"),
        )
    else:
        cmd_report(args.days, args.output_json, args.output_html, args.attribution)


if __name__ == "__main__":
    main()
