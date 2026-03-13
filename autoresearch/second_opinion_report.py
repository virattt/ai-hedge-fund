"""
autoresearch/second_opinion_report.py — Simple CLI report for second-opinion runs.

Given:
  1. A PortfolioDraft JSON (Dexter output), and
  2. A run result JSON from /api/v1/second-opinion/runs/{id}/result,

this script prints a terminal table grouping tickers into:
  - Strong agree
  - Mild disagree
  - Hard disagree

based on committee stance vs target weights.
"""

import argparse
import json
from pathlib import Path

from app.backend.models.second_opinion import summarize_second_opinion


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize a second-opinion run against a PortfolioDraft.")
    parser.add_argument(
        "--portfolio-draft",
        type=str,
        required=True,
        help="Path to PortfolioDraft JSON file produced by Dexter.",
    )
    parser.add_argument(
        "--run-result",
        type=str,
        required=True,
        help="Path to run result JSON file from /api/v1/second-opinion/runs/{id}/result.",
    )
    args = parser.parse_args()

    draft_path = Path(args.portfolio_draft)
    result_path = Path(args.run_result)
    if not draft_path.exists() or not result_path.exists():
        print("PortfolioDraft or run result file not found.")
        return 1

    draft = json.loads(draft_path.read_text())
    result = json.loads(result_path.read_text())

    sleeve = draft.get("sleeve")
    params_profile = draft.get("params_profile")

    print("=== Second-opinion context ===")
    print(f"  Sleeve         : {sleeve or '-'}")
    print(f"  Params profile : {params_profile or '-'}")

    assets = {a["symbol"]: a for a in draft.get("assets", [])}
    raw_results = result.get("results") or {}
    raw_decisions = raw_results.get("decisions") if isinstance(raw_results, dict) else {}
    decisions = raw_decisions if isinstance(raw_decisions, dict) else {}

    summaries = summarize_second_opinion(decisions, sleeve=sleeve)

    strong_agree = []
    mild_disagree = []
    hard_disagree = []

    for s in summaries:
        asset = assets.get(s.symbol, {})
        target_w = asset.get("target_weight_pct", 0.0)
        stance = s.committee_stance.upper()

        # Simple heuristic: long weight + BUY/HOLD = agree; long weight + SELL/SHORT = disagree.
        if target_w >= 0:
            if stance in ("BUY", "HOLD"):
                strong_agree.append((s, target_w))
            elif stance in ("SELL", "SHORT"):
                if target_w >= 3.0:
                    hard_disagree.append((s, target_w))
                else:
                    mild_disagree.append((s, target_w))
        else:
            # Short or underweight thesis vs committee
            if stance in ("SELL", "SHORT"):
                strong_agree.append((s, target_w))
            elif stance in ("BUY", "HOLD"):
                if abs(target_w) >= 3.0:
                    hard_disagree.append((s, target_w))
                else:
                    mild_disagree.append((s, target_w))

    def _print_bucket(title: str, bucket):
        print(f"\n{title}")
        print("-" * len(title))
        if not bucket:
            print("  (none)")
            return
        print("  symbol  weight  stance  conf")
        for s, w in sorted(bucket, key=lambda x: -abs(x[1])):
            conf = f"{s.confidence:.1f}" if s.confidence is not None else "-"
            print(f"  {s.symbol:6}  {w:6.1f}%  {s.committee_stance:6}  {conf}")

    _print_bucket("Strong agree", strong_agree)
    _print_bucket("Mild disagree", mild_disagree)
    _print_bucket("Hard disagree", hard_disagree)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

