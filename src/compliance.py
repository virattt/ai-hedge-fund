"""Research-only compliance primitives (PRD v4 §9.9, B5).

The disclaimer is carried as data and enforced as an invariant at serialization
(``serialize_report``) and at the DB layer (NOT NULL). This module is the single
source of the disclaimer text/version. Ranked, per-security output retains
regulatory character even with this disclaimer — counsel sign-off is a hard gate
before any non-loopback exposure (PRD §19).
"""

import os

DISCLAIMER_VERSION = os.environ.get("DISCLAIMER_VERSION", "2026-06")

DISCLAIMER = (
    "Research and educational use only. This output is not investment advice, not a "
    "recommendation to buy or sell any security, and carries no guarantee of accuracy or "
    "performance. It contains no trade-execution instructions. Descriptive labels and "
    "promote/hold/demote statuses describe research priority, not trading directives. "
    "Conduct your own due diligence; consult a licensed professional before investing."
)


def research_disclaimer() -> tuple[str, str]:
    """Return (disclaimer_text, disclaimer_version) for stamping records/reports."""
    return DISCLAIMER, DISCLAIMER_VERSION
