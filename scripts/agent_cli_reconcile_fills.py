"""
Phase 4: reconcile execution fills into persistent position state.

This script updates a position snapshot from fill events, while keeping:
- append-only journal (JSONL)
- idempotency index (processed fill IDs)

Supported fill inputs:
- JSON object
- JSON array of objects
- JSON with top-level "fills" array
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def _load_positions(path: Path) -> dict[str, float]:
    if not path.exists():
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
            instrument = str(row.get("instrument") or row.get("symbol") or "").upper().strip()
            if not instrument:
                continue
            try:
                out[instrument] = float(row.get("quantity", 0.0))
            except (TypeError, ValueError):
                continue
        return out
    raise ValueError(f"Unsupported positions format: {path}")


def _load_fill_index(path: Path) -> set[str]:
    if not path.exists():
        return set()
    data = _load_json(path)
    if isinstance(data, list):
        return {str(x) for x in data}
    return set()


def _extract_fills(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        if isinstance(data.get("fills"), list):
            return [x for x in data["fills"] if isinstance(x, dict)]
        return [data]
    return []


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_side(fill: dict[str, Any]) -> str | None:
    raw = str(fill.get("side") or "").lower().strip()
    if raw in {"buy", "b"}:
        return "buy"
    if raw in {"sell", "s"}:
        return "sell"
    return None


def _resolve_qty(fill: dict[str, Any]) -> float:
    for key in ("filled_size", "filled_qty", "quantity", "size", "qty"):
        if key in fill:
            q = _to_float(fill.get(key), 0.0)
            if q > 0:
                return q
    return 0.0


def _resolve_instrument(fill: dict[str, Any]) -> str:
    return str(
        fill.get("instrument")
        or fill.get("symbol")
        or fill.get("ticker")
        or ""
    ).upper().strip()


def _fill_id(fill: dict[str, Any]) -> str:
    # Prefer explicit IDs if present.
    for key in ("fill_id", "id", "trade_id", "order_id", "client_order_id"):
        raw = fill.get(key)
        if raw is not None and str(raw).strip():
            return str(raw).strip()

    # Fallback deterministic hash from core fields.
    canonical = {
        "instrument": _resolve_instrument(fill),
        "side": _normalize_side(fill),
        "qty": _resolve_qty(fill),
        "price": _to_float(fill.get("price"), 0.0),
        "timestamp": fill.get("timestamp") or fill.get("ts") or fill.get("time"),
    }
    packed = json.dumps(canonical, sort_keys=True)
    return "hash:" + hashlib.sha256(packed.encode("utf-8")).hexdigest()[:24]


def _signed_delta(side: str, qty: float) -> float:
    return qty if side == "buy" else -qty


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def _append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reconcile fills into persistent position snapshot."
    )
    parser.add_argument(
        "--fills",
        type=str,
        required=True,
        help="Path to fills JSON (object/array or {fills:[...]}).",
    )
    parser.add_argument(
        "--positions",
        type=str,
        default="second_opinion_runs/agent_cli_positions_snapshot.json",
        help="Path to position snapshot JSON (created if missing).",
    )
    parser.add_argument(
        "--journal",
        type=str,
        default="second_opinion_runs/agent_cli_fills_journal.jsonl",
        help="Append-only journal path.",
    )
    parser.add_argument(
        "--fill-index",
        type=str,
        default="second_opinion_runs/agent_cli_fill_index.json",
        help="JSON array of processed fill IDs for idempotency.",
    )
    parser.add_argument(
        "--drop-zero-positions",
        action="store_true",
        help="Remove instruments with near-zero position after reconcile.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing files.",
    )
    args = parser.parse_args()

    fills_path = Path(args.fills)
    if not fills_path.exists():
        raise FileNotFoundError(f"--fills not found: {fills_path}")

    positions_path = Path(args.positions)
    journal_path = Path(args.journal)
    index_path = Path(args.fill_index)

    positions = _load_positions(positions_path)
    processed_ids = _load_fill_index(index_path)
    fills = _extract_fills(_load_json(fills_path))

    applied = 0
    skipped_duplicate = 0
    skipped_invalid = 0
    journal_rows: list[dict[str, Any]] = []

    for fill in fills:
        instrument = _resolve_instrument(fill)
        side = _normalize_side(fill)
        qty = _resolve_qty(fill)
        fid = _fill_id(fill)

        if fid in processed_ids:
            skipped_duplicate += 1
            continue

        if not instrument or side is None or qty <= 0:
            skipped_invalid += 1
            continue

        delta = _signed_delta(side, qty)
        before = float(positions.get(instrument, 0.0))
        after = before + delta
        positions[instrument] = after
        processed_ids.add(fid)
        applied += 1

        journal_rows.append(
            {
                "reconciled_at": datetime.now(UTC).isoformat(),
                "fill_id": fid,
                "instrument": instrument,
                "side": side,
                "qty": qty,
                "delta": delta,
                "position_before": before,
                "position_after": after,
                "raw_fill": fill,
            }
        )

    if args.drop_zero_positions:
        positions = {
            k: v
            for k, v in positions.items()
            if abs(v) > 1e-12
        }

    print(
        "Reconcile summary: "
        f"fills={len(fills)} applied={applied} "
        f"dup_skipped={skipped_duplicate} invalid_skipped={skipped_invalid} "
        f"positions={len(positions)}"
    )

    if args.dry_run:
        print("Dry run: no files written.")
        return 0

    _write_json(positions_path, positions)
    _write_json(index_path, sorted(processed_ids))
    _append_jsonl(journal_path, journal_rows)

    print(f"Positions updated: {positions_path}")
    print(f"Fill index updated: {index_path}")
    print(f"Journal appended: {journal_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
