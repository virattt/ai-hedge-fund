"""Internal types shared across alert engine and rules."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AlertCandidate:
    """A potential alert produced by a rule before de-dupe + dispatch."""
    rule_type: str
    ticker: str
    title: str
    message: str
    payload: dict[str, Any] = field(default_factory=dict)
    severity: str = "info"  # info | warning | critical
