"""Scaffold tests for World Monitor integration helpers."""

from types import SimpleNamespace

import pytest

from autoresearch.cache_worldmonitor import is_snapshot_stale
from autoresearch.factors import apply_worldmonitor_overlay
from src.data.worldmonitor_features import normalize_worldmonitor_payload


def test_normalize_worldmonitor_payload_maps_common_fields():
    payload = {
        "strategic_risk_score": 82,
        "supply_chain_stress": 61,
        "hotspot_escalation": 73,
        "country_risk_scores": {"us": 40, "tw": 88},
        "cb_policy_bias": "hawkish",
        "freshness_seconds": 120,
    }
    snapshot = normalize_worldmonitor_payload(
        payload,
        source_endpoint="/api/mock/v1/risk",
        source_version="test",
        ttl_seconds=900,
    )

    assert snapshot.wm_global_risk_score == 82.0
    assert snapshot.wm_macro_regime == "risk_off"
    assert snapshot.wm_country_risk["US"] == 40.0
    assert snapshot.wm_country_risk["TW"] == 88.0
    assert snapshot.wm_data_freshness_seconds == 120


def test_worldmonitor_overlay_scales_in_risk_off():
    params = SimpleNamespace(
        USE_WM_FILTER=True,
        WM_RISK_OFF_SCALE=0.8,
        WM_COUNTRY_RISK_CAP=85.0,
    )
    wm_snapshot = {
        "wm_macro_regime": "risk_off",
        "wm_country_risk": {"US": 50.0, "TW": 70.0},
    }
    allowed, mult = apply_worldmonitor_overlay(wm_snapshot, params)
    assert allowed is True
    assert mult == 0.8


def test_worldmonitor_overlay_no_change_when_disabled():
    params = SimpleNamespace(
        USE_WM_FILTER=False,
        WM_RISK_OFF_SCALE=0.8,
        WM_COUNTRY_RISK_CAP=85.0,
    )
    wm_snapshot = {"wm_macro_regime": "risk_off", "wm_country_risk": {"TW": 99.0}}
    allowed, mult = apply_worldmonitor_overlay(wm_snapshot, params)
    assert allowed is True
    assert mult == 1.0


def test_worldmonitor_overlay_extra_scale_on_country_risk_cap_breach():
    params = SimpleNamespace(
        USE_WM_FILTER=True,
        WM_RISK_OFF_SCALE=0.8,
        WM_COUNTRY_RISK_CAP=85.0,
    )
    wm_snapshot = {
        "wm_macro_regime": "risk_off",
        "wm_country_risk": {"US": 50.0, "TW": 92.0},
    }
    _, mult = apply_worldmonitor_overlay(wm_snapshot, params)
    assert mult == pytest.approx(0.72)  # 0.8 * 0.9


def test_is_snapshot_stale_when_as_of_missing():
    assert is_snapshot_stale({}, max_age_minutes=10) is True

