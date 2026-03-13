"""
Build a safe handoff artifact from AIHF second-opinion output to agent-cli.

Default behavior is dry-run: generate a handoff JSON file and print the
agent-cli command that would run. Live command execution is opt-in.

Usage:
    poetry run python scripts/aihf_agent_cli_bridge.py \
      --run-result second_opinion_runs/second_opinion_run_result_14.json \
      --portfolio-draft portfolio_draft_hyperliquid_full.json \
      --symbol-map configs/agent_cli_symbol_map.example.json \
      --strict-symbol-map
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ACTION_TO_EXPOSURE = {
    "buy": "long",
    "cover": "long",
    "sell": "short",
    "short": "short",
    "hold": "flat",
}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _normalize_decisions(run_result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """
    Handle both persisted shapes:
    - {"results": {"decisions": {...}}}
    - {"decisions": {...}}
    """
    if isinstance(run_result.get("results"), dict):
        results = run_result.get("results") or {}
        decisions = results.get("decisions") or {}
    else:
        decisions = run_result.get("decisions") or {}
    if not isinstance(decisions, dict):
        return {}
    return decisions


def _normalize_weights(portfolio_draft: dict[str, Any] | None) -> dict[str, float]:
    if not portfolio_draft:
        return {}
    assets = portfolio_draft.get("assets") or []
    out: dict[str, float] = {}
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        symbol = str(asset.get("symbol") or "").upper().strip()
        if not symbol:
            continue
        try:
            out[symbol] = float(asset.get("target_weight_pct", 0.0))
        except (TypeError, ValueError):
            out[symbol] = 0.0
    return out


def _load_symbol_map(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    data = _load_json(path)
    if not isinstance(data, dict):
        raise ValueError("--symbol-map must be a JSON object: {\"NVDA\": \"NVDA-PERP\"}")
    out: dict[str, str] = {}
    for k, v in data.items():
        if v is None:
            continue
        out[str(k).upper().strip()] = str(v).strip()
    return out


def _resolve_instrument(
    symbol: str,
    symbol_map: dict[str, str],
    strict_symbol_map: bool,
) -> tuple[str | None, str]:
    mapped = symbol_map.get(symbol)
    if mapped:
        return mapped, "map"
    if strict_symbol_map:
        return None, "unmapped"
    return symbol, "identity_fallback"


def _build_handoff(
    *,
    run_result_path: Path,
    portfolio_draft_path: Path | None,
    symbol_map_path: Path | None,
    strict_symbol_map: bool,
    min_confidence: float,
    include_actions: set[str],
) -> dict[str, Any]:
    run_result = _load_json(run_result_path)
    portfolio_draft = _load_json(portfolio_draft_path) if portfolio_draft_path else None
    symbol_map = _load_symbol_map(symbol_map_path)

    decisions = _normalize_decisions(run_result)
    target_weight_by_symbol = _normalize_weights(portfolio_draft)

    skipped: list[dict[str, Any]] = []
    intents: list[dict[str, Any]] = []

    for raw_symbol, decision in decisions.items():
        symbol = str(raw_symbol or "").upper().strip()
        if not symbol or not isinstance(decision, dict):
            continue

        action = str(decision.get("action") or "hold").lower().strip()
        if action not in include_actions:
            skipped.append(
                {
                    "symbol": symbol,
                    "reason": "filtered_action",
                    "action": action,
                }
            )
            continue

        exposure = ACTION_TO_EXPOSURE.get(action)
        if exposure is None:
            skipped.append(
                {
                    "symbol": symbol,
                    "reason": "unsupported_action",
                    "action": action,
                }
            )
            continue

        try:
            confidence = float(decision.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        if confidence < min_confidence:
            skipped.append(
                {
                    "symbol": symbol,
                    "reason": "below_min_confidence",
                    "confidence": confidence,
                }
            )
            continue

        instrument, instrument_source = _resolve_instrument(
            symbol,
            symbol_map,
            strict_symbol_map,
        )
        if not instrument:
            skipped.append(
                {
                    "symbol": symbol,
                    "reason": "missing_symbol_map",
                }
            )
            continue

        try:
            qty = float(decision.get("quantity", 0.0))
        except (TypeError, ValueError):
            qty = 0.0

        intents.append(
            {
                "symbol": symbol,
                "instrument": instrument,
                "instrument_source": instrument_source,
                "desired_exposure": exposure,
                "source_action": action,
                "confidence": confidence,
                "target_weight_pct": target_weight_by_symbol.get(symbol),
                "suggested_quantity": qty if qty > 0 else None,
                "reasoning": decision.get("reasoning"),
            }
        )

    handoff = {
        "schema_version": "1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "source": {
            "run_result_path": str(run_result_path),
            "portfolio_draft_path": str(portfolio_draft_path) if portfolio_draft_path else None,
            "symbol_map_path": str(symbol_map_path) if symbol_map_path else None,
            "run_id": run_result.get("run_id"),
            "status": run_result.get("status"),
        },
        "sleeve": (portfolio_draft or {}).get("sleeve"),
        "params_profile": (portfolio_draft or {}).get("params_profile"),
        "filters": {
            "strict_symbol_map": strict_symbol_map,
            "min_confidence": min_confidence,
            "include_actions": sorted(include_actions),
        },
        "intents": intents,
        "skipped": skipped,
        "summary": {
            "intent_count": len(intents),
            "skipped_count": len(skipped),
            "long_count": sum(1 for i in intents if i["desired_exposure"] == "long"),
            "short_count": sum(1 for i in intents if i["desired_exposure"] == "short"),
            "flat_count": sum(1 for i in intents if i["desired_exposure"] == "flat"),
        },
    }
    return handoff


def _validate_execute_preconditions(args: argparse.Namespace, handoff: dict[str, Any]) -> None:
    if not args.execute_agent_cli:
        return

    if not args.strict_symbol_map or not args.symbol_map:
        raise ValueError(
            "Execution requires --strict-symbol-map and --symbol-map to avoid invalid instruments."
        )

    if not handoff["intents"]:
        raise ValueError("Execution requested but handoff has no intents.")


def _run_agent_cli(command: str, handoff_path: Path, execute: bool) -> int:
    env = os.environ.copy()
    env["AIHF_HANDOFF_PATH"] = str(handoff_path)

    cmd_parts = shlex.split(command)
    if not execute:
        print("\nDry run only. Would execute:")
        print("  " + " ".join(shlex.quote(part) for part in cmd_parts))
        print(f"  with env AIHF_HANDOFF_PATH={handoff_path}")
        return 0

    proc = subprocess.run(cmd_parts, env=env, check=False)
    return int(proc.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bridge AIHF second-opinion output into an agent-cli handoff artifact."
    )
    parser.add_argument(
        "--run-result",
        type=str,
        required=True,
        help="Path to second_opinion_run_result_<id>.json",
    )
    parser.add_argument(
        "--portfolio-draft",
        type=str,
        default=None,
        help="Optional portfolio_draft_*.json for target weights/sleeve context.",
    )
    parser.add_argument(
        "--symbol-map",
        type=str,
        default=None,
        help="Optional JSON mapping from source symbols to agent-cli instruments.",
    )
    parser.add_argument(
        "--strict-symbol-map",
        action="store_true",
        help="Drop unmapped symbols (recommended).",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.0,
        help="Minimum decision confidence to include (default 0).",
    )
    parser.add_argument(
        "--include-actions",
        type=str,
        default="buy,short,cover,sell,hold",
        help="Comma-separated actions to include.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output handoff JSON path. Default: second_opinion_runs/agent_cli_handoff_run_<id>.json",
    )
    parser.add_argument(
        "--agent-cli-cmd",
        type=str,
        default="hl apex run --mock --max-ticks 5",
        help="Command to invoke agent-cli. AIHF_HANDOFF_PATH env var is injected.",
    )
    parser.add_argument(
        "--execute-agent-cli",
        action="store_true",
        help="Actually execute --agent-cli-cmd. Default is dry-run print only.",
    )
    args = parser.parse_args()

    run_result_path = Path(args.run_result)
    if not run_result_path.exists():
        raise FileNotFoundError(f"--run-result not found: {run_result_path}")

    portfolio_draft_path = Path(args.portfolio_draft) if args.portfolio_draft else None
    if portfolio_draft_path and not portfolio_draft_path.exists():
        raise FileNotFoundError(f"--portfolio-draft not found: {portfolio_draft_path}")

    symbol_map_path = Path(args.symbol_map) if args.symbol_map else None
    if symbol_map_path and not symbol_map_path.exists():
        raise FileNotFoundError(f"--symbol-map not found: {symbol_map_path}")

    include_actions = {
        token.strip().lower()
        for token in args.include_actions.split(",")
        if token.strip()
    }

    handoff = _build_handoff(
        run_result_path=run_result_path,
        portfolio_draft_path=portfolio_draft_path,
        symbol_map_path=symbol_map_path,
        strict_symbol_map=bool(args.strict_symbol_map),
        min_confidence=float(args.min_confidence),
        include_actions=include_actions,
    )

    _validate_execute_preconditions(args, handoff)

    run_id = handoff["source"].get("run_id")
    default_output = Path("second_opinion_runs") / f"agent_cli_handoff_run_{run_id}.json"
    output_path = Path(args.output) if args.output else default_output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(handoff, indent=2))

    print(f"Handoff written: {output_path}")
    print(
        "Summary: "
        f"intents={handoff['summary']['intent_count']} "
        f"skipped={handoff['summary']['skipped_count']} "
        f"long={handoff['summary']['long_count']} "
        f"short={handoff['summary']['short_count']} "
        f"flat={handoff['summary']['flat_count']}"
    )

    rc = _run_agent_cli(
        command=args.agent_cli_cmd,
        handoff_path=output_path,
        execute=bool(args.execute_agent_cli),
    )
    if rc != 0:
        print(f"agent-cli command failed with exit code {rc}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
