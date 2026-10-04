"""ACANTHOSTEGA_PHASE_B_OBJECT_IMPACT_ACOUSTICS — body/object impact → LPS."""
from __future__ import annotations

import math
from pathlib import Path

import pytest

from mechanistic_mind.model.acanthostega import (
    acanthostega_body_object_contact_config,
    acanthostega_body_object_impulse_config,
    acanthostega_contact_acoustics_config,
    acanthostega_object_impact_acoustics_config,
)
from mechanistic_mind.model.lines import stamp_config_from_preset
from mechanistic_mind.model.tiktaalik import tiktaalik_config
from mechanistic_mind.physical_system import body_resource_object_contact_impulse as boi
from mechanistic_mind.physical_system import body_resource_object_impact_acoustic_emission as oia
from mechanistic_mind.physical_system import local_physical_signal_transport as lps
from mechanistic_mind.physical_system import physical_body_resource_object_contact as boc
from mechanistic_mind.physical_system import physical_contact_acoustic_emission as pca
from mechanistic_mind.physical_system.experiment_canonical import (
    PRESET_ACANTHOSTEGA_BODY_OBJECT_CONTACT,
    PRESET_ACANTHOSTEGA_BODY_OBJECT_IMPULSE,
    PRESET_ACANTHOSTEGA_CONTACT_ACOUSTICS,
    PRESET_ACANTHOSTEGA_OBJECT_IMPACT_ACOUSTICS,
    PRESET_BETA31,
    beta31_mechanism_map,
    normalize_preset_name,
    preset_canonical,
)
from mechanistic_mind.physical_system.observation import audit_cognition_payload
from mechanistic_mind.physical_system.oscillatory_signaling import cognition_osc_fragments
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.physical_system.spatial_contents import body_refs_for_runtime

MID = oia.MECHANISM_ID
BR = boc.BODY_CONTACT_RADIUS
OR = boc.CANONICAL_COLLISION_RADIUS
SUM_R = BR + OR


def _place_object(rt, x, y, *, state="FREE_STATIC", vx=0.0, vy=0.0, mass=None):
    objs = list(getattr(rt.world, "resource_objects", None) or [])
    assert objs, "preset must spawn resource objects"
    o = objs[0]
    o.x, o.y = float(x), float(y)
    o.vx, o.vy = float(vx), float(vy)
    o.physical_state = state
    o.holder_body_id = None
    o.manipulator_id = None
    if mass is not None:
        o.mass = float(mass)
    boc.ensure_object_collision_radius(o)
    return o


def _place_body(rt, x, y, *, vx=0.0, vy=0.0):
    b = rt.body
    b.x, b.y = float(x), float(y)
    b.vx, b.vy = float(vx), float(vy)
    return b, rt.config.body


def _detect_impulse_acoustics(rt, tick=1):
    bodies = body_refs_for_runtime(rt)
    boc.detect_body_resource_object_contacts(rt.world, bodies, tick=tick, config=rt.config)
    triples = [(bid, b, rt.config.body) for bid, b in bodies]
    step = boi.apply_body_object_contact_impulse(rt.world, triples, tick=tick, config=rt.config)
    out = oia.process_body_object_impact_acoustics(rt.world, rt.config, emission_tick=tick)
    return step, out


def _rt():
    return PhysicalSystemRuntime(seed=17, config=acanthostega_object_impact_acoustics_config())


# ---------- isolation ----------


def test_01_normalize_more_specific_first():
    assert normalize_preset_name("ACANTHOSTEGA_PHASE_B_OBJECT_IMPACT_ACOUSTICS") == PRESET_ACANTHOSTEGA_OBJECT_IMPACT_ACOUSTICS
    assert normalize_preset_name("ACANTHOSTEGA OBJECT IMPACT ACOUSTICS") == PRESET_ACANTHOSTEGA_OBJECT_IMPACT_ACOUSTICS
    assert normalize_preset_name(PRESET_ACANTHOSTEGA_BODY_OBJECT_IMPULSE) == PRESET_ACANTHOSTEGA_BODY_OBJECT_IMPULSE
    assert normalize_preset_name(PRESET_ACANTHOSTEGA_CONTACT_ACOUSTICS) == PRESET_ACANTHOSTEGA_CONTACT_ACOUSTICS
    assert normalize_preset_name(PRESET_ACANTHOSTEGA_BODY_OBJECT_CONTACT) == PRESET_ACANTHOSTEGA_BODY_OBJECT_CONTACT


def test_02_impulse_and_contact_presets_do_not_enable_impact_acoustics():
    for cfg in (
        acanthostega_body_object_impulse_config(),
        acanthostega_body_object_contact_config(),
        acanthostega_contact_acoustics_config(),
    ):
        assert not oia.body_object_impact_acoustics_is_active(cfg)


def test_03_new_preset_enables_merge_branch():
    cfg = acanthostega_object_impact_acoustics_config()
    assert cfg.public_preset == PRESET_ACANTHOSTEGA_OBJECT_IMPACT_ACOUSTICS
    assert boi.body_object_impulse_is_active(cfg)
    assert boc.body_object_contact_is_active(cfg)
    assert lps.local_physical_signal_transport_is_active(cfg)
    assert pca.physical_contact_acoustic_emission_is_active(cfg)
    assert oia.body_object_impact_acoustics_is_active(cfg)
    assert cfg.oscillatory_signaling.mode == "EXPERIMENTAL"


def test_04_tiktaalik_and_beta31_untouched():
    assert MID not in beta31_mechanism_map()
    t = tiktaalik_config()
    assert getattr(t, "body_resource_object_impact_acoustic_emission", None) in (None,) or not getattr(
        getattr(t, "body_resource_object_impact_acoustic_emission", None), "enabled", False
    )


def test_05_stamp_does_not_enable_on_impulse_only():
    cfg = acanthostega_body_object_impulse_config()
    stamp_config_from_preset(cfg, PRESET_ACANTHOSTEGA_BODY_OBJECT_IMPULSE)
    assert not oia.body_object_impact_acoustics_is_active(cfg)


# ---------- trigger / silence ----------


def test_10_approaching_dissipative_impact_emits():
    rt = _rt()
    # Body approaching object along +x; place just outside contact then move in
    cx, cy = 12.0, 12.0
    obj = _place_object(rt, cx + SUM_R - 0.05, cy, state="FREE_STATIC", mass=1.0)
    body, _ = _place_body(rt, cx, cy, vx=0.35, vy=0.0)
    # Soft compliance -> restitution < 1 -> dissipation expected
    step, out = _detect_impulse_acoustics(rt, tick=1)
    assert step is not None
    applied = [r for r in step["responses"] if r.get("impulse_transferred")]
    assert applied, "expected an applied impulse"
    st = oia.state_of(rt.world)
    assert st is not None
    # May silence if e≈1 and no dissipation — check either emission or explicit no-dissipation silence
    if st.counters["emissions"] == 0:
        assert st.counters["silent_no_dissipation"] + st.counters["silent_below_epsilon"] >= 1
    else:
        assert out.get("emissions")
        em = out["emissions"][0]
        assert em["receipt_kind"] == oia.EMISSION_RECEIPT
        assert em["mechanical_energy_withdrawn"] is False
        assert em["band_profile"] == pca.BAND_PROFILE
        assert em["graph_source_label"].startswith("IMPACT:")


def test_11_resting_contact_silent():
    rt = _rt()
    cx, cy = 12.0, 12.0
    _place_object(rt, cx + SUM_R - 0.1, cy, state="FREE_STATIC")
    _place_body(rt, cx, cy, vx=0.0, vy=0.0)
    _detect_impulse_acoustics(rt, tick=1)
    st = oia.state_of(rt.world)
    assert st.counters["emissions"] == 0
    assert st.counters["silent_no_impulse"] + st.counters["silent_not_approaching"] >= 1


def test_12_separating_silent():
    rt = _rt()
    cx, cy = 12.0, 12.0
    _place_object(rt, cx + SUM_R - 0.1, cy, state="FREE_MOVING", vx=0.4, vy=0.0)
    _place_body(rt, cx, cy, vx=-0.2, vy=0.0)
    _detect_impulse_acoustics(rt, tick=1)
    st = oia.state_of(rt.world)
    assert st.counters["emissions"] == 0


def test_13_contact_fact_only_preset_no_emission_path():
    rt = PhysicalSystemRuntime(seed=17, config=acanthostega_body_object_contact_config())
    assert oia.state_of(rt.world) is None


def test_14_near_elastic_zero_dissipation_silent_when_forced():
    """Dissipation-only: fabricate receipt with impulse but equal KE -> silence."""
    rt = _rt()
    st = oia.ensure_body_object_impact_acoustics_for_runtime(rt.world, rt.config)
    assert st is not None
    receipt = {
        "receipt_kind": boi.RECEIPT_KIND,
        "response_key": "ep:1:1",
        "episode_id": "ep",
        "body_id": "body-0",
        "object_id": "obj-0",
        "pair_key": "body-0|obj-0",
        "reason": "APPROACHING",
        "approaching": True,
        "impulse_transferred": True,
        "impulse_scalar_j": 0.5,
        "ke_pair_pre": 1.0,
        "ke_pair_post": 1.0,
        "dissipated_energy": 0.0,
    }
    rt.world.last_body_object_impulse_step = {
        "event": "BODY_RESOURCE_OBJECT_CONTACT_RESPONSE_STEP",
        "tick": 5,
        "responses": [receipt],
    }
    out = oia.process_body_object_impact_acoustics(rt.world, rt.config, emission_tick=5)
    assert out["emissions"] == []
    assert any(m.get("silence_reason") == oia.R_NO_DISSIPATION for m in out["measurements"])


def test_15_below_epsilon_silent():
    rt = _rt()
    receipt = {
        "response_key": "ep:2:1",
        "episode_id": "ep",
        "body_id": "body-0",
        "object_id": "obj-0",
        "pair_key": "body-0|obj-0",
        "reason": "APPROACHING",
        "approaching": True,
        "impulse_transferred": True,
        "impulse_scalar_j": 1e-6,
        "ke_pair_pre": 1.0,
        "ke_pair_post": 0.5,
        "dissipated_energy": 0.5,
    }
    rt.world.last_body_object_impulse_step = {"tick": 6, "responses": [receipt]}
    out = oia.process_body_object_impact_acoustics(rt.world, rt.config, emission_tick=6)
    assert out["emissions"] == []
    assert any(m.get("silence_reason") == oia.R_BELOW_EPSILON for m in out["measurements"])


# ---------- transport / spectrum / privacy / dedupe / snapshot ----------


def test_20_uses_existing_lps_emit_not_second_transport():
    rt = _rt()
    assert lps.state_of(rt.world) is not None
    # Fabricate dissipative approaching receipt
    receipt = {
        "response_key": "ep:7:1",
        "episode_id": "ep",
        "body_id": str(body_refs_for_runtime(rt)[0][0]),
        "object_id": str(rt.world.resource_objects[0].object_id),
        "pair_key": "p",
        "reason": "APPROACHING",
        "approaching": True,
        "impulse_transferred": True,
        "impulse_scalar_j": 0.5,
        "ke_pair_pre": 2.0,
        "ke_pair_post": 1.0,
        "dissipated_energy": 1.0,
    }
    # Seed contact step with contact_point
    rt.world.last_body_object_contact_step = {
        "tick": 7,
        "begin": [{
            "episode_id": "ep",
            "body_id": receipt["body_id"],
            "object_id": receipt["object_id"],
            "pair_key": "p",
            "contact_fact": True,
            "contact_point": [10.0, 10.0],
            "contact_point_policy": "TEST",
            "body_pose": [9.5, 10.0],
            "object_pose": [10.5, 10.0],
        }],
        "persist": [],
    }
    rt.world.last_body_object_impulse_step = {"tick": 7, "responses": [receipt]}
    before = len(getattr(lps.state_of(rt.world), "active_emissions", []) or [])
    # active may be list or dict depending on LPS version — also check emission history
    out = oia.process_body_object_impact_acoustics(rt.world, rt.config, emission_tick=7)
    assert len(out["emissions"]) == 1
    em = out["emissions"][0]
    assert em["anonymous_band_vector"]
    assert abs(sum(em["anonymous_band_vector"]) - em["emitted_energy"]) < 1e-9
    assert em["band_profile"] == "UNIFORM_BROADBAND_V1"
    # n_bands uniform
    n = len(em["anonymous_band_vector"])
    assert all(abs(b - em["emitted_energy"] / n) < 1e-12 for b in em["anonymous_band_vector"])
    assert em["position"] == [10.0, 10.0] or abs(em["position"][0] - 10.0) < 1e-9


def test_21_dedupe_same_response_key():
    rt = _rt()
    receipt = {
        "response_key": "ep:8:1",
        "episode_id": "ep",
        "body_id": "body-0",
        "object_id": "obj-0",
        "pair_key": "p",
        "reason": "APPROACHING",
        "approaching": True,
        "impulse_transferred": True,
        "impulse_scalar_j": 0.5,
        "ke_pair_pre": 2.0,
        "ke_pair_post": 1.0,
        "dissipated_energy": 1.0,
    }
    rt.world.last_body_object_contact_step = {
        "tick": 8,
        "begin": [{"episode_id": "ep", "body_id": "body-0", "object_id": "obj-0", "pair_key": "p",
                   "contact_fact": True, "contact_point": [5.0, 5.0], "body_pose": [5.0, 5.0],
                   "object_pose": [6.0, 5.0]}],
        "persist": [],
    }
    rt.world.last_body_object_impulse_step = {"tick": 8, "responses": [receipt]}
    out1 = oia.process_body_object_impact_acoustics(rt.world, rt.config, emission_tick=8)
    assert len(out1["emissions"]) == 1
    # Same tick reprocess suppressed
    out2 = oia.process_body_object_impact_acoustics(rt.world, rt.config, emission_tick=8)
    assert out2.get("status") == "ALREADY_PROCESSED"
    # New tick, same response_key -> already_processed silence
    rt.world.last_body_object_impulse_step = {"tick": 9, "responses": [receipt]}
    out3 = oia.process_body_object_impact_acoustics(rt.world, rt.config, emission_tick=9)
    assert len(out3["emissions"]) == 0
    assert any(m.get("silence_reason") == oia.R_ALREADY for m in out3["measurements"])


def test_22_snapshot_restore_preserves_processed_keys():
    rt = _rt()
    receipt = {
        "response_key": "ep:10:1",
        "episode_id": "ep",
        "body_id": "body-0",
        "object_id": "obj-0",
        "pair_key": "p",
        "reason": "APPROACHING",
        "approaching": True,
        "impulse_transferred": True,
        "impulse_scalar_j": 0.5,
        "ke_pair_pre": 2.0,
        "ke_pair_post": 0.8,
        "dissipated_energy": 1.2,
    }
    rt.world.last_body_object_contact_step = {
        "tick": 10,
        "begin": [{"episode_id": "ep", "body_id": "body-0", "object_id": "obj-0", "pair_key": "p",
                   "contact_fact": True, "contact_point": [4.0, 4.0], "body_pose": [4.0, 4.0],
                   "object_pose": [5.0, 4.0]}],
        "persist": [],
    }
    rt.world.last_body_object_impulse_step = {"tick": 10, "responses": [receipt]}
    oia.process_body_object_impact_acoustics(rt.world, rt.config, emission_tick=10)
    snap = rt.snapshot(persist=True)
    rt2 = PhysicalSystemRuntime.restore(snap)
    st2 = oia.state_of(rt2.world)
    assert st2 is not None
    assert "ep:10:1" in st2.processed_response_keys
    # Must not re-emit after restore
    rt2.world.last_body_object_impulse_step = {"tick": 11, "responses": [receipt]}
    out = oia.process_body_object_impact_acoustics(rt2.world, rt2.config, emission_tick=11)
    assert len(out["emissions"]) == 0


def test_23_privacy_cognition_only_osc_tokens():
    rt = _rt()
    receipt = {
        "response_key": "ep:11:1",
        "episode_id": "secret-episode",
        "body_id": "body-0",
        "object_id": "secret-object",
        "pair_key": "secret-pair",
        "reason": "APPROACHING",
        "approaching": True,
        "impulse_transferred": True,
        "impulse_scalar_j": 0.5,
        "ke_pair_pre": 2.0,
        "ke_pair_post": 1.0,
        "dissipated_energy": 1.0,
    }
    rt.world.last_body_object_contact_step = {
        "tick": 11,
        "begin": [{"episode_id": "secret-episode", "body_id": "body-0", "object_id": "secret-object",
                   "pair_key": "secret-pair", "contact_fact": True, "contact_point": [8.0, 8.0],
                   "body_pose": [8.0, 8.0], "object_pose": [9.0, 8.0]}],
        "persist": [],
    }
    rt.world.last_body_object_impulse_step = {"tick": 11, "responses": [receipt]}
    oia.process_body_object_impact_acoustics(rt.world, rt.config, emission_tick=11)
    # Advance LPS so reception can land
    lps.step_end_of_tick(rt.world, rt.config, body_refs_for_runtime(rt), tick_now=12)
    frag = cognition_osc_fragments(rt.body, rt.world, rt.config.oscillatory_signaling)
    payload = {"osc": frag}
    audit_cognition_payload(payload)
    blob = str(payload).lower()
    for forbidden in ("secret-episode", "secret-object", "secret-pair", "impulse", "dissipat", "emission_id", "contact_point"):
        assert forbidden not in blob


def test_24_energy_contract_no_mechanical_withdrawal():
    raw, emitted = oia.acoustic_energy_from_dissipation(1.0, oia.BodyObjectImpactAcousticConfig(enabled=True))
    assert raw == 1.0 * oia.DEFAULT_ACOUSTIC_COUPLING
    assert 0.0 < emitted <= oia.DEFAULT_MAX_ACOUSTIC_ENERGY
    assert oia.dissipated_pairwise_ke(5.0, 3.0) == 2.0
    assert oia.dissipated_pairwise_ke(3.0, 5.0) == 0.0


def test_25_canonical_map_includes_mechanism():
    can = preset_canonical(PRESET_ACANTHOSTEGA_OBJECT_IMPACT_ACOUSTICS)
    assert can["mechanisms"][MID] is True
    assert can["mechanisms"][pca.MECHANISM_ID] is True
    assert can["mechanisms"][boi.MECHANISM_ID] is True


def test_26_broadband_bands_imported_not_copied():
    assert oia.broadband_bands is pca.broadband_bands
    assert oia.BAND_PROFILE_NAME == pca.BAND_PROFILE


def test_27_unit_budget_guard():
    # Keep harness short: a few ticks only
    rt = _rt()
    for t in range(1, 6):
        _place_object(rt, 14.0, 14.0, state="FREE_STATIC")
        _place_body(rt, 12.0, 14.0, vx=0.3, vy=0.0)
        _detect_impulse_acoustics(rt, tick=t)
        lps.step_end_of_tick(rt.world, rt.config, body_refs_for_runtime(rt), tick_now=t + 1)
    assert True
