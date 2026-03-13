"""
scripts/dexter_second_opinion_client.py — Dexter helper for second-opinion runs.

This script is designed to be called from Dexter (or manually) to:
  1. Read a PortfolioDraft JSON file (one sleeve),
  2. Submit a second-opinion job to the local AI Hedge Fund API, and
  3. Poll until completion and optionally print a disagreement report.

Usage (from ai-hedge-fund repo root):

    python scripts/dexter_second_opinion_client.py \
      --draft path/to/portfolio_draft.json \
      --run-report

Dexter can either:
  - shell out to this script, or
  - copy its logic into a native Python client.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict

import requests


def submit_run(base_url: str, draft: Dict[str, Any]) -> int:
    """POST the draft as a HedgeFundRequest-compatible body and return run_id."""
    url = f"{base_url.rstrip('/')}/api/v1/second-opinion/runs"

    # Minimal mapping: we assume the draft contains tickers and a prebuilt graph
    body = {
        "tickers": [a["symbol"] for a in draft.get("assets", [])],
        "graph_nodes": draft.get("graph_nodes", []),
        "graph_edges": draft.get("graph_edges", []),
        "margin_requirement": draft.get("margin_requirement", 0.0),
        "portfolio_positions": draft.get("portfolio_positions", []),
        "model_name": draft.get("model_name", "gpt-4.1"),
        "model_provider": draft.get("model_provider", "openai"),
        "api_keys": draft.get("api_keys"),
    }

    resp = requests.post(url, json=body, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return int(data["run_id"])


def poll_status(base_url: str, run_id: int, poll_interval: float, timeout_s: float) -> Dict[str, Any]:
    """Poll /runs/{run_id} until terminal status or timeout."""
    url = f"{base_url.rstrip('/')}/api/v1/second-opinion/runs/{run_id}"
    t0 = time.time()
    while True:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 404:
            raise RuntimeError(f"Run {run_id} not found")
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status")
        if status in ("COMPLETE", "ERROR", "FAILED", "CANCELLED"):
            return data
        if time.time() - t0 > timeout_s:
            raise TimeoutError(f"Timed out waiting for run {run_id} (last status={status})")
        time.sleep(poll_interval)


def fetch_result(base_url: str, run_id: int) -> Dict[str, Any]:
    """GET the final result payload once status is COMPLETE/ERROR."""
    url = f"{base_url.rstrip('/')}/api/v1/second-opinion/runs/{run_id}/result"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()


def main() -> int:
    parser = argparse.ArgumentParser(description="Dexter helper: submit a second-opinion run and optionally report.")
    parser.add_argument(
        "--draft",
        type=str,
        required=True,
        help="Path to PortfolioDraft JSON (one sleeve).",
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default="http://localhost:8000",
        help="Base URL for AI Hedge Fund backend (default http://localhost:8000).",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=".",
        help="Directory to write run_result_<run_id>.json (default current dir).",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=2.0,
        help="Seconds between status polls.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=900.0,
        help="Max seconds to wait for a run (default 900s = 15min).",
    )
    parser.add_argument(
        "--run-report",
        action="store_true",
        help="After fetching result, run the terminal disagreement report.",
    )

    args = parser.parse_args()

    draft_path = Path(args.draft)
    if not draft_path.exists():
        print(f"Draft file not found: {draft_path}")
        return 1
    draft = json.loads(draft_path.read_text())

    print(f"Submitting second-opinion run to {args.base_url} for {draft_path}...")
    run_id = submit_run(args.base_url, draft)
    print(f"  → run_id={run_id}")

    print("Polling status...")
    status_data = poll_status(args.base_url, run_id, args.poll_interval, args.timeout)
    print(f"  final status: {status_data.get('status')}")
    if status_data.get("error_message"):
        print(f"  error_message: {status_data['error_message']}")

    print("Fetching result...")
    result = fetch_result(args.base_url, run_id)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    result_path = out_dir / f"second_opinion_run_result_{run_id}.json"
    result_path.write_text(json.dumps(result, indent=2))
    print(f"  result written to {result_path}")

    if args.run_report:
        try:
            from autoresearch.second_opinion_report import main as report_main  # type: ignore

            # Construct a minimal PortfolioDraft-like dict the report expects
            assets = draft.get("assets", [])
            draft_for_report = {
                "sleeve": draft.get("sleeve"),
                "assets": assets,
            }
            tmp_draft = out_dir / f"second_opinion_portfolio_draft_{run_id}.json"
            tmp_draft.write_text(json.dumps(draft_for_report, indent=2))

            print("\n=== Second-opinion comparison ===")
            # The report CLI expects file paths via argv; emulate that
            import sys

            argv_backup = sys.argv
            try:
                sys.argv = [
                    "second_opinion_report",
                    "--portfolio-draft",
                    str(tmp_draft),
                    "--run-result",
                    str(result_path),
                ]
                report_main()
            finally:
                sys.argv = argv_backup
        except Exception as e:
            print(f"(report generation failed: {e})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

