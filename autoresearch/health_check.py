"""
Health check endpoint. Run with: poetry run python -m autoresearch.health_check
Serves HTTP on port 8765 by default. GET /health returns cache freshness, last run, status.
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = Path(__file__).resolve().parent / "cache"
LOGS_DIR = Path(__file__).resolve().parent / "logs"
PERF_CSV = LOGS_DIR / "performance.csv"


def get_cache_freshness() -> dict:
    """Return latest date in price caches."""
    out = {}
    for f in CACHE_DIR.glob("prices*.json"):
        try:
            data = json.loads(f.read_text())
            all_dates = []
            for ticker, recs in data.items():
                if recs and isinstance(recs[0], dict) and "date" in recs[0]:
                    all_dates.extend(r["date"] for r in recs)
            out[f.name] = max(all_dates) if all_dates else None
        except Exception:
            pass
    return out


def get_last_run() -> str | None:
    """Last daily log date."""
    logs = sorted(LOGS_DIR.glob("daily_*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not logs:
        return None
    return logs[0].stem.replace("daily_", "")


def get_status() -> dict:
    """Full health status."""
    cache = get_cache_freshness()
    last_run = get_last_run()
    has_perf = PERF_CSV.exists()
    latest_value = None
    if has_perf:
        try:
            lines = PERF_CSV.read_text().strip().splitlines()
            if len(lines) > 1:
                latest_value = float(lines[-1].split(",")[-1])
        except Exception:
            pass
    return {
        "status": "ok",
        "cache_freshness": cache,
        "last_run": last_run,
        "performance_csv": has_perf,
        "latest_value": latest_value,
        "timestamp": datetime.now().isoformat(),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--once", action="store_true", help="Print JSON and exit (no HTTP server)")
    args = parser.parse_args()

    if args.once:
        print(json.dumps(get_status(), indent=2))
        return

    from http.server import HTTPServer, BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health" or self.path == "/":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(get_status()).encode())
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, format, *args):
            pass

    server = HTTPServer(("", args.port), Handler)
    print(f"Health check at http://localhost:{args.port}/health")
    server.serve_forever()


if __name__ == "__main__":
    main()
