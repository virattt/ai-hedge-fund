"""
Orchestrate daily paper trading run. Reads autoresearch/daily_config.json.
Override with env: REFRESH_PRICES, DRY_RUN, DAILY_ALERT_URL, SMTP_PASSWORD.
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = Path(__file__).resolve().parent / "daily_config.json"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    with open(CONFIG_PATH) as f:
        return json.load(f)


def main():
    cfg = load_config()
    date = datetime.now().strftime("%Y-%m-%d")
    logs_dir = PROJECT_ROOT / "autoresearch" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / f"daily_{date}.log"

    refresh = os.environ.get("REFRESH_PRICES")
    if refresh is None:
        refresh = "1" if cfg.get("refresh_prices", True) else "0"
    dry_run = os.environ.get("DRY_RUN", "0")
    if dry_run == "0" and cfg.get("dry_run"):
        dry_run = "1"

    cost_bps = cfg.get("cost_bps", 10)
    slippage_bps = cfg.get("slippage_bps", 5)
    initial_cash = cfg.get("initial_cash", 100000)
    state_path = cfg.get("state_path", ".paper_broker_state.json")

    with open(log_path, "a") as log:
        def run(cmd: list[str], cwd: Path | None = None) -> int:
            return subprocess.call(cmd, cwd=cwd or PROJECT_ROOT, stdout=log, stderr=subprocess.STDOUT)

        log.write(f"=== Daily paper trading {date} ===\n")
        log.flush()

        if refresh == "1":
            run(["./autoresearch/refresh_all_prices.sh"]) or log.write("Price refresh failed (check API key)\n")

        execute_flag = [] if dry_run == "1" else ["--execute"]
        run([
            "poetry", "run", "python", "-m", "autoresearch.paper_trading",
            "--date", date,
            *execute_flag,
            "--state-path", state_path,
            "--initial-cash", str(initial_cash),
            "--cost-bps", str(cost_bps),
            "--slippage-bps", str(slippage_bps),
        ])

        if (PROJECT_ROOT / state_path).exists():
            run(["poetry", "run", "python", "-m", "autoresearch.performance_tracker", "log", "--state-path", state_path])
            run([
                "poetry", "run", "python", "-m", "autoresearch.performance_tracker", "compare",
                "--state-path", state_path, "--output-csv", "autoresearch/logs/bt_vs_live.csv",
            ])

    # Log rotation
    for f in (PROJECT_ROOT / "autoresearch" / "logs").glob("daily_*.log"):
        if (datetime.now() - datetime.fromtimestamp(f.stat().st_mtime)).days > 30:
            f.unlink(missing_ok=True)

    # Build summary and send alerts
    total = "N/A"
    orders = "0"
    try:
        content = log_path.read_text()
        for line in reversed(content.splitlines()):
            if "total=$" in line:
                import re
                m = re.search(r"total=\$([0-9,.]+)", line)
                if m:
                    total = m.group(1)
                break
        orders = str(content.count("FILLED"))
    except Exception:
        pass
    summary = f"Daily run {date}: total=${total}, orders={orders}"

    # Send via send_daily_alert (Slack + email from config)
    subprocess.run(
        [sys.executable, "-m", "autoresearch.send_daily_alert", summary],
        cwd=PROJECT_ROOT,
        env={**os.environ, "DATE": date},
    )

    print(f"Done. Log: {log_path}")


if __name__ == "__main__":
    main()
