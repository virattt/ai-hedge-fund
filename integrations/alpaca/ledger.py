"""Persist trading cycle results to a local ledger."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from integrations.alpaca.run_cycle import CycleResult


def ledger_dir() -> Path:
    return Path("data/ledger")


def save_cycle(
    result: CycleResult,
    *,
    broker_name: str,
    cycle_kind: str = "heavy",
    trigger_reason: str | None = None,
) -> Path:
    """Write one cycle's decisions and execution results to JSON."""
    out_dir = ledger_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = out_dir / f"{timestamp}_{broker_name}.json"

    payload: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "broker": broker_name,
        "cycle_kind": cycle_kind,
        "trigger_reason": trigger_reason,
        "account_summary": result.account_summary,
        "decisions": result.agent_result.get("decisions"),
        "orders": [o.model_dump() for o in result.orders],
        "execution": [r.model_dump() for r in result.execution_results],
        "portfolio": result.portfolio,
    }

    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return path
