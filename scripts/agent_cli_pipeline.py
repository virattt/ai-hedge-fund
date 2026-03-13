"""
One-command orchestrator for AIHF -> agent-cli workflow.

Pipeline:
1) Build handoff artifact (Phase 1)
2) Build netted/constrained command plan (Phases 2+3)
3) Optionally reconcile fills into persistent state (Phase 4)

Safety defaults:
- Dry-run planning by default
- Execution is opt-in
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _run_step(cmd: list[str], step_name: str) -> None:
    print(f"\n=== {step_name} ===")
    print("Command:", " ".join(cmd))
    proc = subprocess.run(cmd, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"{step_name} failed with exit code {proc.returncode}")


def _resolve_default_handoff_path(run_result: Path) -> Path:
    run_id = run_result.stem.split("_")[-1]
    return Path("second_opinion_runs") / f"agent_cli_handoff_run_{run_id}.json"


def _resolve_default_plan_path(run_result: Path) -> Path:
    run_id = run_result.stem.split("_")[-1]
    return Path("second_opinion_runs") / f"agent_cli_exec_plan_run_{run_id}.json"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run end-to-end AIHF -> agent-cli pipeline."
    )

    # Phase 1 inputs
    parser.add_argument("--run-result", type=str, required=True, help="Path to second_opinion_run_result_<id>.json")
    parser.add_argument("--portfolio-draft", type=str, default=None, help="Optional portfolio draft path")
    parser.add_argument("--symbol-map", type=str, default=None, help="Symbol map for bridge")
    parser.add_argument("--strict-symbol-map", action="store_true", help="Use strict symbol mapping in bridge")
    parser.add_argument("--bridge-min-confidence", type=float, default=0.0, help="Bridge-level minimum confidence")
    parser.add_argument(
        "--bridge-include-actions",
        type=str,
        default="buy,short,cover,sell,hold",
        help="Comma-separated actions to include in bridge",
    )
    parser.add_argument("--handoff-output", type=str, default=None, help="Optional handoff output path")

    # Phase 2/3 inputs
    parser.add_argument("--reference-prices", type=str, default=None, help="Optional reference prices JSON")
    parser.add_argument("--current-positions", type=str, default=None, help="Optional current positions JSON")
    parser.add_argument("--sizing-mode", choices=["hybrid", "quantity", "weight"], default="hybrid")
    parser.add_argument("--quantity-scale", type=float, default=1.0)
    parser.add_argument("--account-equity-usd", type=float, default=100000.0)
    parser.add_argument("--leverage", type=float, default=1.0)
    parser.add_argument("--executor-min-confidence", type=float, default=0.0)
    parser.add_argument("--max-orders", type=int, default=10)
    parser.add_argument("--max-gross-notional-usd", type=float, default=0.0)
    parser.add_argument("--max-net-notional-usd", type=float, default=0.0)
    parser.add_argument(
        "--command-template",
        type=str,
        default="hl trade {instrument} {side} {size}",
        help="Executor command template",
    )
    parser.add_argument(
        "--append-flags",
        type=str,
        default="--mock",
        help="Flags appended to each generated command",
    )
    parser.add_argument("--plan-output", type=str, default=None, help="Optional execution plan JSON path")
    parser.add_argument("--shell-output", type=str, default=None, help="Optional execution shell path")
    parser.add_argument("--execute-plan", action="store_true", help="Execute generated plan commands")
    parser.add_argument("--i-understand-live-risk", action="store_true", help="Required for non-mock execution")
    parser.add_argument("--stop-on-error", action="store_true", help="Stop execution on first command failure")

    # Phase 4 inputs (optional)
    parser.add_argument("--fills", type=str, default=None, help="Optional fills JSON path to trigger reconciliation")
    parser.add_argument(
        "--positions-snapshot",
        type=str,
        default="second_opinion_runs/agent_cli_positions_snapshot.json",
        help="Persistent position snapshot path",
    )
    parser.add_argument(
        "--fills-journal",
        type=str,
        default="second_opinion_runs/agent_cli_fills_journal.jsonl",
        help="Fill journal JSONL path",
    )
    parser.add_argument(
        "--fill-index",
        type=str,
        default="second_opinion_runs/agent_cli_fill_index.json",
        help="Processed fill-id index path",
    )
    parser.add_argument("--drop-zero-positions", action="store_true")
    parser.add_argument("--reconcile-dry-run", action="store_true")

    args = parser.parse_args()

    run_result = Path(args.run_result)
    if not run_result.exists():
        raise FileNotFoundError(f"--run-result not found: {run_result}")

    handoff_output = Path(args.handoff_output) if args.handoff_output else _resolve_default_handoff_path(run_result)
    plan_output = Path(args.plan_output) if args.plan_output else _resolve_default_plan_path(run_result)

    # Phase 1: bridge
    bridge_cmd = [
        sys.executable,
        "scripts/aihf_agent_cli_bridge.py",
        "--run-result",
        str(run_result),
        "--min-confidence",
        str(args.bridge_min_confidence),
        "--include-actions",
        args.bridge_include_actions,
        "--output",
        str(handoff_output),
        "--agent-cli-cmd",
        "echo bridge_handoff_generated",
    ]
    if args.portfolio_draft:
        bridge_cmd.extend(["--portfolio-draft", args.portfolio_draft])
    if args.symbol_map:
        bridge_cmd.extend(["--symbol-map", args.symbol_map])
    if args.strict_symbol_map:
        bridge_cmd.append("--strict-symbol-map")
    _run_step(bridge_cmd, "Phase 1: Build Handoff")

    # Phase 2/3: executor
    executor_cmd = [
        sys.executable,
        "scripts/agent_cli_handoff_executor.py",
        "--handoff",
        str(handoff_output),
        "--sizing-mode",
        args.sizing_mode,
        "--quantity-scale",
        str(args.quantity_scale),
        "--account-equity-usd",
        str(args.account_equity_usd),
        "--leverage",
        str(args.leverage),
        "--min-confidence",
        str(args.executor_min_confidence),
        "--max-orders",
        str(args.max_orders),
        "--max-gross-notional-usd",
        str(args.max_gross_notional_usd),
        "--max-net-notional-usd",
        str(args.max_net_notional_usd),
        "--command-template",
        args.command_template,
        f"--append-flags={args.append_flags}",
        "--output-plan",
        str(plan_output),
    ]
    if args.shell_output:
        executor_cmd.extend(["--output-shell", args.shell_output])
    if args.reference_prices:
        executor_cmd.extend(["--reference-prices", args.reference_prices])
    if args.current_positions:
        executor_cmd.extend(["--current-positions", args.current_positions])
    if args.execute_plan:
        executor_cmd.append("--execute")
    if args.i_understand_live_risk:
        executor_cmd.append("--i-understand-live-risk")
    if args.stop_on_error:
        executor_cmd.append("--stop-on-error")
    _run_step(executor_cmd, "Phase 2/3: Build + (Optional) Execute Plan")

    # Phase 4: reconcile (optional)
    if args.fills:
        reconcile_cmd = [
            sys.executable,
            "scripts/agent_cli_reconcile_fills.py",
            "--fills",
            args.fills,
            "--positions",
            args.positions_snapshot,
            "--journal",
            args.fills_journal,
            "--fill-index",
            args.fill_index,
        ]
        if args.drop_zero_positions:
            reconcile_cmd.append("--drop-zero-positions")
        if args.reconcile_dry_run:
            reconcile_cmd.append("--dry-run")
        _run_step(reconcile_cmd, "Phase 4: Reconcile Fills")
    else:
        print("\n=== Phase 4: Reconcile Fills ===")
        print("Skipped (no --fills provided).")

    print("\nPipeline complete.")
    print(f"- Handoff: {handoff_output}")
    print(f"- Execution plan: {plan_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
