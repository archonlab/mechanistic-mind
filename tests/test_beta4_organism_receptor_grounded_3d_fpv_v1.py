"""BETA4 organism receptor-grounded 3D FPV — focused tests (≤60 ticks)."""
from __future__ import annotations

import json

from mechanistic_mind.model.acanthostega import acanthostega_beta4_config
from mechanistic_mind.model.tiktaalik import tiktaalik_config
from mechanistic_mind.physical_system.experiment_canonical import public_model_selector_entries
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.physical_system import organism_receptor_grounded_3d_fpv as fpv
from mechanistic_mind.physical_system.observation import FORBIDDEN_TOKENS
from mechanistic_mind.physical_system.organism_physical_optical_reception import (
    SCHEMA as O4_SCHEMA,
)

TICKS = {"n": 0}


def _tick(n: int = 1) -> None:
    TICKS["n"] += int(n)
    assert TICKS["n"] <= 60


def _rt(seed: int = 55):
    cfg = acanthostega_beta4_config()
    cfg.cognition.cognition_enabled = True
    rt = PhysicalSystemRuntime(seed=seed, config=cfg)
    rt.technical_id = "agent_0"
    return rt


def _observe(rt, n: int = 1):
    for _ in range(n):
        rt.tick += 1
        rt.body.tick = rt.tick
        rt.world.tick = rt.tick
        obs = rt.agent_observation()
        _tick(1)
    return obs


def test_01_identity():
    assert fpv.SCHEMA == "ORGANISM_RECEPTOR_GROUNDED_3D_FPV_V1"
    assert fpv.CAPABILITY == "organism_receptor_grounded_3d_fpv"
    assert fpv.PROFILE == "EXACT_O4_RECEPTOR_CONTRIBUTION_FIRST_PERSON_RECONSTRUCTION_V1"
    assert fpv.AUTHORITY == "RESEARCHER_DISPLAY_OVER_AUTHORITATIVE_O4_RECEPTION"
    assert fpv.CLASSIFICATION == "BETA4_REQUIRED_OBSERVABILITY_NOT_NEW_SENSOR"


def test_02_nonzero_o4_produces_receptor_fpv():
    rt = _rt(56)
    obs = _observe(rt, 2)
    exo = sum(float(obs.get(f"exo_{i}", 0) or 0) for i in range(3))
    assert exo > 0
    tr = fpv.latest_exact_trace(rt.world, "agent_0")
    assert tr is not None
    assert tr["availability"] == "AVAILABLE"
    assert int(tr["accepted_count"]) > 0
    assert len(tr["accepted_contributions"]) > 0
    c = tr["accepted_contributions"][0]
    assert c["visibility_status"] == "ACCEPTED"
    assert c.get("azimuth_deg") is not None
    assert c.get("elevation_deg") is not None
    assert c.get("distance_3d") is not None
    assert len(c.get("accepted_raw_six_band") or []) == 6


def test_03_missing_trace_not_darkness():
    payload = fpv.observer_payload(object(), selected_agent_id="agent_0")
    assert payload["available"] is False
    assert payload["missing_reason"] == fpv.REASON_NO_O4_TRACE_YET
    assert payload["render_as_darkness_forbidden"] is True


def test_04_latest_survives_history_eviction():
    rt = _rt(57)
    st = fpv.ensure_state(rt.world)
    st.capacity = 2
    _observe(rt, 5)
    st = fpv.state_of(rt.world)
    assert st is not None
    assert st.evicted_count >= 1
    assert len(st.history) <= 2
    tr = fpv.latest_exact_trace(rt.world, "agent_0")
    assert tr is not None
    assert tr["observation_tick"] == int(rt.tick)


def test_05_historical_evicted_reason():
    rt = _rt(58)
    _observe(rt, 2)
    st = fpv.state_of(rt.world)
    assert st is not None
    gone_id = "never_existed_trace_id"
    p = fpv.observer_payload(rt.world, selected_agent_id="agent_0", historical_trace_id=gone_id)
    assert p["available"] is False
    assert p["missing_reason"] == fpv.REASON_TRACE_EVICTED_HISTORICAL_SELECTION


def test_06_agent_isolation():
    rt = _rt(59)
    _observe(rt, 1)
    # Inject a second agent latest
    st = fpv.state_of(rt.world)
    assert st is not None
    a0 = st.latest_by_agent["agent_0"]
    a1 = dict(a0)
    a1["agent_id"] = "agent_1"
    a1["trace_id"] = "agent1_distinct"
    a1["accepted_contributions"] = []
    a1["accepted_count"] = 0
    st.latest_by_agent["agent_1"] = a1
    p0 = fpv.observer_payload(rt.world, selected_agent_id="agent_0")
    p1 = fpv.observer_payload(rt.world, selected_agent_id="agent_1")
    assert p0["latest"]["trace_id"] != p1["latest"]["trace_id"]
    assert p1["latest"]["accepted_count"] == 0


def test_07_runtime_generation_separated():
    rt = _rt(60)
    _observe(rt, 1)
    st = fpv.state_of(rt.world)
    assert st is not None
    st.latest_by_agent["agent_0"]["runtime_generation"] = 1
    p = fpv.observer_payload(rt.world, selected_agent_id="agent_0", runtime_generation=99)
    assert p["available"] is False
    assert p["missing_reason"] == fpv.REASON_RUNTIME_GENERATION_MISMATCH


def test_08_restore_does_not_create_trace():
    rt = _rt(61)
    _observe(rt, 1)
    st = fpv.state_of(rt.world)
    ser = fpv.serialize_state(st)
    before = st.capture_count
    rt2 = _rt(62)
    # Don't observe — only restore
    fpv.restore_state(rt2.world, ser)
    st2 = fpv.state_of(rt2.world)
    assert st2 is not None
    assert st2.capture_count == before  # restored, not incremented
    # Restore itself is not a new observation event
    assert fpv.latest_exact_trace(rt2.world, "agent_0") is not None


def test_09_polling_does_not_capture():
    rt = _rt(63)
    _observe(rt, 1)
    before = fpv.state_of(rt.world).capture_count
    # Observer-style: call capture without context
    from mechanistic_mind.physical_system.selected_organism_volumetric_vision_view import (
        end_scientific_capture,
    )

    end_scientific_capture(rt.world)
    full = getattr(rt.world, "_o4_last_reception_trace", None)
    out = fpv.capture_from_o4_trace(rt.world, full, diagnostic=False)
    assert out is None
    assert fpv.state_of(rt.world).capture_count == before


def test_10_observation_trace_tick_match():
    rt = _rt(64)
    _observe(rt, 1)
    tr = fpv.latest_exact_trace(rt.world, "agent_0")
    assert tr["observation_tick"] == int(rt.tick)
    assert tr["receptor_tick"] == int(rt.tick)


def test_11_accepted_only_in_fpv():
    rt = _rt(65)
    _observe(rt, 1)
    tr = fpv.latest_exact_trace(rt.world, "agent_0")
    for c in tr["accepted_contributions"]:
        assert c["visibility_status"] == "ACCEPTED"
    assert tr["rejected_contributions_excluded_from_fpv"] is True


def test_12_cognition_fpv_coarser():
    rt = _rt(66)
    _observe(rt, 1)
    tr = fpv.latest_exact_trace(rt.world, "agent_0")
    n_acc = len(tr["accepted_contributions"])
    n_bins = len(tr["cognition_fpv_bins"])
    # Cognition has at most exo channel count (typically 3), not per-contribution
    assert n_bins <= 3 or n_bins < n_acc or n_acc == 0
    for b in tr["cognition_fpv_bins"]:
        assert "elevation_deg" in b
        # elevation resolution not restored for cognition
        assert float(b["elevation_deg"]) == 0.0


def test_13_display_transform_nonphysical():
    assert fpv.DISPLAY_BAND_TRANSFORM_PHYSICAL_AUTHORITY is False
    rgb = fpv._bands_to_display_rgb([1, 0, 0, 0, 0, 0])
    assert rgb[0] > rgb[1]


def test_14_no_vw7_flags():
    rt = _rt(67)
    _observe(rt, 1)
    tr = fpv.latest_exact_trace(rt.world, "agent_0")
    assert tr["vw7_pixels_used"] is False
    assert tr["frontend_raycast_forbidden"] is True
    p = fpv.observer_payload(rt.world, selected_agent_id="agent_0")
    assert p["vw7_pixels_used"] is False


def test_15_privacy_denylist():
    for tok in ("organism_receptor_grounded_3d_fpv", "ORGANISM_RECEPTOR_GROUNDED_3D_FPV_V1", "contribution_id"):
        assert tok in FORBIDDEN_TOKENS or tok in fpv.PRIVACY_DENYLIST


def test_16_selector_and_tiktaalik():
    assert len(public_model_selector_entries()) == 2
    assert tiktaalik_config() is not None


def test_17_serialize_payload_in_live_frame():
    from mechanistic_mind.ui.psy_observer_web.serialize import live_frame
    from mechanistic_mind.ui.psy_observer_web.subscriptions import ObserverInterest, PRODUCT_WORLD

    rt = _rt(68)
    _observe(rt, 1)
    fr = live_frame(
        rt,
        status="PAUSED",
        mode="LIVE",
        target_tick=None,
        previous_body=None,
        detail="compact",
        include_cognition=False,
        observer_interest=ObserverInterest(products=frozenset({PRODUCT_WORLD})),
    )
    block = (fr.get("world") or {}).get("organism_receptor_grounded_3d_fpv")
    assert isinstance(block, dict)
    assert block.get("schema") == fpv.SCHEMA
    assert block.get("available") is True


def test_18_o4_schema_unchanged():
    assert O4_SCHEMA == "ORGANISM_PHYSICAL_OPTICAL_RECEPTION_V1"
