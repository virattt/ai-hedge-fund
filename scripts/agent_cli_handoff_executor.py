"""
Phase 3 adapter: convert AIHF handoff intents into concrete agent-cli commands.

Default behavior is dry-run. The script emits:
- an execution plan JSON,
- a shell script with commands, and
- projected post-trade positions.

Command execution is opt-in.

It can read the handoff path from:
1) --handoff
2) AIHF_HANDOFF_PATH environment variable

Example:
    poetry run python scripts/agent_cli_handoff_executor.py \
      --handoff second_opinion_runs/agent_cli_handoff_run_15.json \
      --append-flags="--mock" \
      --sizing-mode hybrid
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


EXPOSURE_TO_SIDE = {
    "long": "buy",
    "short": "sell",
}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _load_price_map(path: Path | None) -> dict[str, float]:
    if path is None:
        return {}
    data = _load_json(path)
    if not isinstance(data, dict):
        raise ValueError("--reference-prices must be a JSON object")
    out: dict[str, float] = {}
    for k, v in data.items():
        try:
            out[str(k).upper().strip()] = float(v)
        except (TypeError, ValueError):
            continue
    return out


def _load_current_positions(path: Path | None) -> dict[str, float]:
    """
    Supported shapes:
    - {"COIN": -2.5, "MSFT": 1}
    - [{"instrument":"COIN","quantity":-2.5}, {"symbol":"MSFT","quantity":1}]
    """
    if path is None:
        return {}
    data = _load_json(path)
    out: dict[str, float] = {}
    if isinstance(data, dict):
        for k, v in data.items():
            try:
                out[str(k).upper().strip()] = float(v)
            except (TypeError, ValueError):
                continue
        return out
    if isinstance(data, list):
        for row in data:
            if not isinstance(row, dict):
                continue
            instrument = str(
                row.get("instrument")
                or row.get("symbol")
                or ""
            ).upper().strip()
            if not instrument:
                continue
            try:
                out[instrument] = float(row.get("quantity", 0.0))
            except (TypeError, ValueError):
                continue
        return out
    raise ValueError("--current-positions must be an object or array")


def _resolve_handoff_path(cli_value: str | None) -> Path:
    if cli_value:
        return Path(cli_value)
    env_value = os.environ.get("AIHF_HANDOFF_PATH")
    if env_value:
        return Path(env_value)
    raise ValueError("Provide --handoff or set AIHF_HANDOFF_PATH.")


def _size_from_weight(
    *,
    target_weight_pct: float | None,
    account_equity_usd: float,
    reference_price: float | None,
    leverage: float,
) -> float | None:
    if target_weight_pct is None or target_weight_pct <= 0:
        return None
    if reference_price is None or reference_price <= 0:
        return None
    notion = account_equity_usd * (target_weight_pct / 100.0) * leverage
    qty = notion / reference_price
    return max(qty, 0.0)


def _compute_size(
    *,
    intent: dict[str, Any],
    mode: str,
    quantity_scale: float,
    account_equity_usd: float,
    leverage: float,
    price_map: dict[str, float],
) -> tuple[float | None, str]:
    symbol = str(intent.get("symbol") or "").upper()
    instrument = str(intent.get("instrument") or "").upper()

    quantity_val = intent.get("suggested_quantity")
    qty = None
    if quantity_val is not None:
        try:
            qty = float(quantity_val) * quantity_scale
        except (TypeError, ValueError):
            qty = None

    target_weight_pct = intent.get("target_weight_pct")
    try:
        tw = float(target_weight_pct) if target_weight_pct is not None else None
    except (TypeError, ValueError):
        tw = None

    ref_price = price_map.get(instrument)
    if ref_price is None:
        ref_price = price_map.get(symbol)

    weight_qty = _size_from_weight(
        target_weight_pct=tw,
        account_equity_usd=account_equity_usd,
        reference_price=ref_price,
        leverage=leverage,
    )

    if mode == "quantity":
        return (qty if qty and qty > 0 else None, "quantity")
    if mode == "weight":
        return (weight_qty if weight_qty and weight_qty > 0 else None, "weight")

    # hybrid
    if qty and qty > 0:
        return qty, "quantity"
    if weight_qty and weight_qty > 0:
        return weight_qty, "weight"
    return None, "none"


def _positions_notional(
    positions: dict[str, float],
    price_map: dict[str, float],
) -> tuple[float, float, list[str]]:
    gross = 0.0
    net = 0.0
    missing: list[str] = []
    for instrument, qty in positions.items():
        if abs(qty) <= 0:
            continue
        px = price_map.get(instrument)
        if px is None or px <= 0:
            missing.append(instrument)
            continue
        notion = qty * px
        gross += abs(notion)
        net += notion
    return gross, abs(net), missing


def _build_command(
    *,
    template: str,
    append_flags: str,
    instrument: str,
    side: str,
    size: float,
    confidence: float,
    symbol: str,
) -> str:
    cmd = template.format(
        instrument=instrument,
        side=side,
        size=f"{size:.6f}".rstrip("0").rstrip("."),
        confidence=f"{confidence:.2f}",
        symbol=symbol,
    ).strip()
    if append_flags.strip():
        cmd = f"{cmd} {append_flags.strip()}"
    return cmd


def _build_plan(
    *,
    handoff: dict[str, Any],
    sizing_mode: str,
    quantity_scale: float,
    account_equity_usd: float,
    leverage: float,
    price_map: dict[str, float],
    current_positions: dict[str, float],
    min_confidence: float,
    max_orders: int,
    max_gross_notional_usd: float,
    max_net_notional_usd: float,
    command_template: str,
    append_flags: str,
) -> dict[str, Any]:
    intents = handoff.get("intents") or []
    if not isinstance(intents, list):
        intents = []

    selected: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    projected_positions: dict[str, float] = dict(current_positions)

    # Highest confidence first so max_orders keeps strongest conviction.
    sorted_intents = sorted(
        [i for i in intents if isinstance(i, dict)],
        key=lambda x: float(x.get("confidence", 0.0) or 0.0),
        reverse=True,
    )

    for intent in sorted_intents:
        symbol = str(intent.get("symbol") or "").upper()
        instrument = str(intent.get("instrument") or "")
        desired_exposure = str(intent.get("desired_exposure") or "").lower()
        confidence = float(intent.get("confidence", 0.0) or 0.0)

        if confidence < min_confidence:
            skipped.append(
                {"symbol": symbol, "reason": "below_min_confidence", "confidence": confidence}
            )
            continue

        initial_side = EXPOSURE_TO_SIDE.get(desired_exposure)
        if not initial_side:
            skipped.append({"symbol": symbol, "reason": "unsupported_exposure", "exposure": desired_exposure})
            continue

        target_size, size_source = _compute_size(
            intent=intent,
            mode=sizing_mode,
            quantity_scale=quantity_scale,
            account_equity_usd=account_equity_usd,
            leverage=leverage,
            price_map=price_map,
        )
        if target_size is None or target_size <= 0:
            skipped.append({"symbol": symbol, "reason": "missing_size", "size_source": size_source})
            continue

        # Netting layer: convert intent into target signed quantity and route only delta.
        desired_signed_qty = target_size if desired_exposure == "long" else -target_size
        current_signed_qty = float(projected_positions.get(instrument, 0.0))
        delta_qty = desired_signed_qty - current_signed_qty
        if abs(delta_qty) <= 1e-12:
            skipped.append({"symbol": symbol, "reason": "already_at_target"})
            continue
        side = "buy" if delta_qty > 0 else "sell"
        size = abs(delta_qty)

        # Enforce notional limits against projected post-trade state.
        tentative_positions = dict(projected_positions)
        tentative_positions[instrument] = desired_signed_qty
        if abs(tentative_positions[instrument]) <= 1e-12:
            tentative_positions.pop(instrument, None)
        gross_after, net_after, missing_for_limits = _positions_notional(
            tentative_positions,
            price_map,
        )
        if (max_gross_notional_usd > 0 or max_net_notional_usd > 0) and missing_for_limits:
            skipped.append(
                {
                    "symbol": symbol,
                    "reason": "missing_price_for_limits",
                    "instruments": missing_for_limits,
                }
            )
            continue
        if max_gross_notional_usd > 0 and gross_after > max_gross_notional_usd:
            skipped.append(
                {
                    "symbol": symbol,
                    "reason": "max_gross_limit",
                    "gross_after": gross_after,
                    "limit": max_gross_notional_usd,
                }
            )
            continue
        if max_net_notional_usd > 0 and net_after > max_net_notional_usd:
            skipped.append(
                {
                    "symbol": symbol,
                    "reason": "max_net_limit",
                    "net_after": net_after,
                    "limit": max_net_notional_usd,
                }
            )
            continue

        cmd = _build_command(
            template=command_template,
            append_flags=append_flags,
            instrument=instrument,
            side=side,
            size=size,
            confidence=confidence,
            symbol=symbol,
        )
        selected.append(
            {
                "symbol": symbol,
                "instrument": instrument,
                "side": side,
                "size": size,
                "size_source": size_source,
                "confidence": confidence,
                "source_action": intent.get("source_action"),
                "current_position_qty": current_signed_qty,
                "desired_position_qty": desired_signed_qty,
                "delta_qty": delta_qty,
                "gross_notional_after_usd": gross_after,
                "net_notional_after_usd": net_after,
                "command": cmd,
            }
        )
        projected_positions = tentative_positions
        if len(selected) >= max_orders:
            break

    gross_final, net_final, missing_final = _positions_notional(projected_positions, price_map)
    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "handoff_source": handoff.get("source"),
        "params_profile": handoff.get("params_profile"),
        "sleeve": handoff.get("sleeve"),
        "execution": {
            "sizing_mode": sizing_mode,
            "quantity_scale": quantity_scale,
            "account_equity_usd": account_equity_usd,
            "leverage": leverage,
            "min_confidence": min_confidence,
            "max_orders": max_orders,
            "max_gross_notional_usd": max_gross_notional_usd,
            "max_net_notional_usd": max_net_notional_usd,
            "command_template": command_template,
            "append_flags": append_flags,
        },
        "orders": selected,
        "skipped": skipped,
        "projected_positions": projected_positions,
        "projected_notional": {
            "gross_usd": gross_final,
            "net_usd": net_final,
            "missing_price_instruments": missing_final,
        },
        "summary": {
            "order_count": len(selected),
            "skipped_count": len(skipped),
            "buy_count": sum(1 for row in selected if row["side"] == "buy"),
            "sell_count": sum(1 for row in selected if row["side"] == "sell"),
        },
    }


def _write_shell_script(path: Path, commands: list[str]) -> None:
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        "# Auto-generated by scripts/agent_cli_handoff_executor.py",
    ]
    lines.extend(commands)
    path.write_text("\n".join(lines) + "\n")


def _execute_plan(
    *,
    commands: list[str],
    execute: bool,
    stop_on_error: bool,
) -> int:
    if not execute:
        print("\nDry run only. Planned commands:")
        for idx, cmd in enumerate(commands, start=1):
            print(f"  {idx:02d}. {cmd}")
        return 0

    for idx, cmd in enumerate(commands, start=1):
        print(f"[{idx}/{len(commands)}] {cmd}")
        proc = subprocess.run(shlex.split(cmd), check=False)
        if proc.returncode != 0 and stop_on_error:
            return int(proc.returncode)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build and optionally execute agent-cli commands from AIHF handoff."
    )
    parser.add_argument(
        "--handoff",
        type=str,
        default=None,
        help="Path to handoff JSON. If omitted, uses AIHF_HANDOFF_PATH.",
    )
    parser.add_argument(
        "--reference-prices",
        type=str,
        default=None,
        help="Optional JSON map for weight-based sizing: {\"NVDA\": 900, \"BTC\": 70000}",
    )
    parser.add_argument(
        "--current-positions",
        type=str,
        default=None,
        help="Optional JSON current positions for netting. Supports object or array formats.",
    )
    parser.add_argument(
        "--sizing-mode",
        choices=["hybrid", "quantity", "weight"],
        default="hybrid",
        help="How to derive order size.",
    )
    parser.add_argument(
        "--quantity-scale",
        type=float,
        default=1.0,
        help="Multiplier on suggested_quantity when available.",
    )
    parser.add_argument(
        "--account-equity-usd",
        type=float,
        default=100000.0,
        help="Used by weight sizing mode.",
    )
    parser.add_argument(
        "--leverage",
        type=float,
        default=1.0,
        help="Used by weight sizing mode as notional multiplier.",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.0,
        help="Filter intents below this confidence.",
    )
    parser.add_argument(
        "--max-orders",
        type=int,
        default=10,
        help="Maximum number of commands to include.",
    )
    parser.add_argument(
        "--max-gross-notional-usd",
        type=float,
        default=0.0,
        help="Portfolio gross notional cap (0 disables). Requires price map coverage.",
    )
    parser.add_argument(
        "--max-net-notional-usd",
        type=float,
        default=0.0,
        help="Portfolio absolute net notional cap (0 disables). Requires price map coverage.",
    )
    parser.add_argument(
        "--command-template",
        type=str,
        default="hl trade {instrument} {side} {size}",
        help="Template with placeholders: {instrument} {side} {size} {confidence} {symbol}",
    )
    parser.add_argument(
        "--append-flags",
        type=str,
        default="--mock",
        help="Extra flags appended to each command.",
    )
    parser.add_argument(
        "--output-plan",
        type=str,
        default=None,
        help="Output plan JSON path. Default: second_opinion_runs/agent_cli_exec_plan_run_<id>.json",
    )
    parser.add_argument(
        "--output-shell",
        type=str,
        default=None,
        help="Output shell script path. Default: second_opinion_runs/agent_cli_exec_plan_run_<id>.sh",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute generated commands. Default is dry-run.",
    )
    parser.add_argument(
        "--i-understand-live-risk",
        action="store_true",
        help="Required for execute when --append-flags does not include --mock.",
    )
    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Stop at first command failure when executing.",
    )
    args = parser.parse_args()

    handoff_path = _resolve_handoff_path(args.handoff)
    if not handoff_path.exists():
        raise FileNotFoundError(f"Handoff file not found: {handoff_path}")

    if args.execute and "--mock" not in args.append_flags and not args.i_understand_live_risk:
        raise ValueError(
            "Live execution safety check failed. Either use --append-flags '--mock' "
            "or pass --i-understand-live-risk."
        )

    handoff = _load_json(handoff_path)
    price_map = _load_price_map(Path(args.reference_prices)) if args.reference_prices else {}
    current_positions = (
        _load_current_positions(Path(args.current_positions))
        if args.current_positions
        else {}
    )

    plan = _build_plan(
        handoff=handoff,
        sizing_mode=args.sizing_mode,
        quantity_scale=args.quantity_scale,
        account_equity_usd=args.account_equity_usd,
        leverage=args.leverage,
        price_map=price_map,
        current_positions=current_positions,
        min_confidence=args.min_confidence,
        max_orders=args.max_orders,
        max_gross_notional_usd=args.max_gross_notional_usd,
        max_net_notional_usd=args.max_net_notional_usd,
        command_template=args.command_template,
        append_flags=args.append_flags,
    )

    run_id = (handoff.get("source") or {}).get("run_id")
    default_plan = Path("second_opinion_runs") / f"agent_cli_exec_plan_run_{run_id}.json"
    default_shell = Path("second_opinion_runs") / f"agent_cli_exec_plan_run_{run_id}.sh"
    output_plan = Path(args.output_plan) if args.output_plan else default_plan
    output_shell = Path(args.output_shell) if args.output_shell else default_shell

    output_plan.parent.mkdir(parents=True, exist_ok=True)
    output_shell.parent.mkdir(parents=True, exist_ok=True)

    output_plan.write_text(json.dumps(plan, indent=2))
    _write_shell_script(output_shell, [row["command"] for row in plan["orders"]])

    print(f"Execution plan written: {output_plan}")
    print(f"Execution shell written: {output_shell}")
    print(
        "Summary: "
        f"orders={plan['summary']['order_count']} "
        f"buys={plan['summary']['buy_count']} "
        f"sells={plan['summary']['sell_count']} "
        f"skipped={plan['summary']['skipped_count']}"
    )

    rc = _execute_plan(
        commands=[row["command"] for row in plan["orders"]],
        execute=bool(args.execute),
        stop_on_error=bool(args.stop_on_error),
    )
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
