"""
World Monitor feature schema + payload normalization (Phase 0 scaffold).

Design goals:
- Canonical, versioned feature shape for downstream strategy code.
- Tolerant extraction from varying upstream payload keys.
- No runtime coupling to trading logic yet.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


def _clamp_0_100(value: float | int | None) -> float | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(100.0, numeric))


def _pick_first(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in data:
            return data[key]
    return None


def _macro_regime_from_risk(global_risk_score: float | None) -> str:
    """
    Map a 0-100 global risk score into a coarse market regime.
    """
    if global_risk_score is None:
        return "neutral"
    if global_risk_score >= 70:
        return "risk_off"
    if global_risk_score <= 35:
        return "risk_on"
    return "neutral"


@dataclass
class WorldMonitorFeatureSnapshot:
    as_of_utc: str
    ttl_seconds: int
    source_endpoint: str
    source_version: str
    mapping_version: str = "wm-v1"

    wm_global_risk_score: float | None = None
    wm_macro_regime: str = "neutral"
    wm_supply_chain_stress: float | None = None
    wm_conflict_escalation: float | None = None
    wm_cb_policy_bias: str | None = None
    wm_country_risk: dict[str, float] = field(default_factory=dict)
    wm_data_freshness_seconds: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_worldmonitor_payload(
    payload: dict[str, Any],
    *,
    source_endpoint: str,
    source_version: str = "unknown",
    ttl_seconds: int = 1800,
) -> WorldMonitorFeatureSnapshot:
    """
    Normalize a raw World Monitor payload into canonical feature fields.

    This parser is intentionally forgiving and checks multiple candidate keys.
    """
    now_iso = datetime.now(UTC).isoformat()

    global_risk = _clamp_0_100(
        _pick_first(
            payload,
            "global_risk_score",
            "risk_score",
            "strategic_risk_score",
            "cii_global_score",
        )
    )
    supply_chain = _clamp_0_100(
        _pick_first(payload, "supply_chain_stress", "logistics_stress", "shipping_stress")
    )
    conflict = _clamp_0_100(
        _pick_first(payload, "conflict_escalation", "hotspot_escalation", "theater_escalation")
    )
    cb_policy_bias = _pick_first(payload, "cb_policy_bias", "central_bank_bias", "macro_policy_bias")

    raw_country = _pick_first(payload, "country_risk", "country_risk_scores", "cii_by_country")
    country_risk: dict[str, float] = {}
    if isinstance(raw_country, dict):
        for iso, score in raw_country.items():
            bounded = _clamp_0_100(score)
            if bounded is not None and isinstance(iso, str):
                country_risk[iso.upper()] = bounded

    freshness = _pick_first(payload, "data_freshness_seconds", "freshness_seconds")
    freshness_seconds: int | None = None
    if isinstance(freshness, (int, float)):
        freshness_seconds = max(0, int(freshness))

    macro_regime = _pick_first(payload, "macro_regime")
    if not isinstance(macro_regime, str) or not macro_regime:
        macro_regime = _macro_regime_from_risk(global_risk)

    return WorldMonitorFeatureSnapshot(
        as_of_utc=now_iso,
        ttl_seconds=ttl_seconds,
        source_endpoint=source_endpoint,
        source_version=source_version,
        wm_global_risk_score=global_risk,
        wm_macro_regime=macro_regime,
        wm_supply_chain_stress=supply_chain,
        wm_conflict_escalation=conflict,
        wm_cb_policy_bias=cb_policy_bias if isinstance(cb_policy_bias, str) else None,
        wm_country_risk=country_risk,
        wm_data_freshness_seconds=freshness_seconds,
    )

