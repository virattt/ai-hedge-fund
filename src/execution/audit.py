"""Append-only audit log for orders, fills, rejections, and risk checks."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_audit_dir(log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)


def log_audit_event(
    event_type: str,
    payload: dict[str, Any],
    log_path: str | Path = "src/execution/audit.log.jsonl",
) -> None:
    """
    Append a single JSON line to the audit log. Do not modify or delete.
    event_type: e.g. 'order_submitted', 'order_filled', 'order_rejected', 'risk_check_fail'
    """
    path = Path(log_path)
    _ensure_audit_dir(path)
    record = {
        "ts": _ts(),
        "event": event_type,
        **payload,
    }
    with open(path, "a") as f:
        f.write(json.dumps(record) + "\n")
