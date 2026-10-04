"""ACANTHOSTEGA_PHASE_B_OBJECT_OBJECT_IMPACT_ACOUSTICS — OO impact → LPS."""
from __future__ import annotations

from mechanistic_mind.model.acanthostega import (
    acanthostega_object_impact_acoustics_config,
    acanthostega_object_object_contact_config,
    acanthostega_object_object_impact_acoustics_config,
    acanthostega_object_object_impulse_config,
)
from mechanistic_mind.model.lines import stamp_config_from_preset
from mechanistic_mind.model.tiktaalik import tiktaalik_config
from mechanistic_mind.physical_system import body_resource_object_impact_acoustic_emission as oia
from mechanistic_mind.physical_system import local_physical_signal_transport as lps
from mechanistic_mind.physical_system import physical_contact_acoustic_emission as pca
from mechanistic_mind.physical_system import physical_resource_object_pair_contact as ooc
from mechanistic_mind.physical_system import resource_object_pair_contact_impulse as ooi
from mechanistic_mind.physical_system import resource_object_pair_impact_acoustic_emission as ooia
from mechanistic_mind.physical_system.experiment_canonical import (
    PRESET_ACANTHOSTEGA_OBJECT_IMPACT_ACOUSTICS,
    PRESET_ACANTHOSTEGA_OBJECT_OBJECT_CONTACT,
    PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPACT_ACOUSTICS,
    PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPULSE,
    PRESET_BETA31,
    beta31_mechanism_map,
    normalize_preset_name,
    preset_canonical,
)
from mechanistic_mind.physical_system.observation import audit_cognition_payload
from mechanistic_mind.physical_system.oscillatory_signaling import cognition_osc_fragments
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.physical_system.spatial_contents import body_refs_for_runtime

MID = ooia.MECHANISM_ID
OR = ooc.CANONICAL_COLLISION_RADIUS


def _place_object(rt, idx, x, y, *, state="FREE_STATIC", vx=0.0, vy=0.0, mass=1.0):
    objs = list(getattr(rt.world, "resource_objects", None) or [])
    assert len(objs) > idx, "preset must spawn enough resource objects"
    o = objs[idx]
    o.x, o.y = float(x), float(y)
    o.vx, o.vy = float(vx), float(vy)
    o.physical_state = state
    o.holder_body_id = None
    o.manipulator_id = None
    o.mass = float(mass)
    ooc.ensure_object_collision_radius(o)
    # Soft material for dissipation
    if getattr(o, "material", None) is None:
        try:
            from mechanistic_mind.physical_system.passive_material_properties import ensure_material
            ensure_material(o)
        except Exception:
            pass
    return o


def _detect_impulse_acoustics(rt, tick=1):
    ooc.detect_resource_object_pair_contacts(rt.world, tick=tick, config=rt.config)
    step = ooi.apply_resource_object_pair_contact_impulse(
        rt.world, tick=tick, config=rt.config, bodies=body_refs_for_runtime(rt)
    )
    out = ooia.process_resource_object_pair_impact_acoustics(
        rt.world, rt.config, emission_tick=tick
    )
    return step, out


def _rt():
    return PhysicalSystemRuntime(
        seed=17, config=acanthostega_object_object_impact_acoustics_config()
    )


# ---------- isolation ----------


def test_01_normalize_more_specific_first():
    assert (
        normalize_preset_name("ACANTHOSTEGA_PHASE_B_OBJECT_OBJECT_IMPACT_ACOUSTICS")
        == PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPACT_ACOUSTICS
    )
    assert (
        normalize_preset_name("ACANTHOSTEGA OBJECT OBJECT IMPACT ACOUSTICS")
        == PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPACT_ACOUSTICS
    )
    assert (
        normalize_preset_name(PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPULSE)
        == PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPULSE
    )
    assert (
        normalize_preset_name(PRESET_ACANTHOSTEGA_OBJECT_IMPACT_ACOUSTICS)
        == PRESET_ACANTHOSTEGA_OBJECT_IMPACT_ACOUSTICS
    )
    assert (
        normalize_preset_name(PRESET_ACANTHOSTEGA_OBJECT_OBJECT_CONTACT)
        == PRESET_ACANTHOSTEGA_OBJECT_OBJECT_CONTACT
    )


def test_02_prior_presets_do_not_enable_oo_impact():
    for cfg in (
        acanthostega_object_object_impulse_config(),
        acanthostega_object_object_contact_config(),
        acanthostega_object_impact_acoustics_config(),
    ):
        assert not ooia.resource_object_pair_impact_acoustics_is_active(cfg)


def test_03_new_preset_enables_merge_branch():
    cfg = acanthostega_object_object_impact_acoustics_config()
    assert cfg.public_preset == PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPACT_ACOUSTICS
    assert ooi.resource_object_pair_impulse_is_active(cfg)
    assert ooc.resource_object_pair_contact_is_active(cfg)
    assert lps.local_physical_signal_transport_is_active(cfg)
    assert pca.physical_contact_acoustic_emission_is_active(cfg)
    assert oia.body_object_impact_acoustics_is_active(cfg)
    assert ooia.resource_object_pair_impact_acoustics_is_active(cfg)
    assert cfg.oscillatory_signaling.mode == "EXPERIMENTAL"


def test_04_tiktaalik_and_beta31_untouched():
    assert MID not in beta31_mechanism_map()
    t = tiktaalik_config()
    assert getattr(t, "resource_object_pair_impact_acoustic_emission", None) in (None,) or not getattr(
        getattr(t, "resource_object_pair_impact_acoustic_emission", None), "enabled", False
    )


def test_05_stamp_does_not_enable_on_impulse_only():
    cfg = acanthostega_object_object_impulse_config()
    stamp_config_from_preset(cfg, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPULSE)
    assert not ooia.resource_object_pair_impact_acoustics_is_active(cfg)


# ---------- trigger / silence ----------


def test_10_approaching_dissipative_isolated_impact_emits_or_zero_dissipation():
    rt = _rt()
    # Two soft objects approaching along x; just overlapping
    cx, cy = 12.0, 12.0
    a = _place_object(rt, 0, cx, cy, state="FREE_MOVING", vx=0.35, vy=0.0, mass=1.0)
    b = _place_object(
        rt, 1, cx + 2 * OR - 0.05, cy, state="FREE_STATIC", vx=0.0, vy=0.0, mass=1.0
    )
    # Soften compliance if available
    for o in (a, b):
        mat = getattr(o, "material", None)
        if mat is not None and hasattr(mat, "compliance"):
            mat.compliance = 0.6
    step, out = _detect_impulse_acoustics(rt, tick=1)
    assert step is not None
    st = ooia.state_of(rt.world)
    assert st is not None
    if st.counters["emissions"] == 0:
        assert (
            st.counters["silent_no_dissipation"]
            + st.counters["silent_below_epsilon"]
            + st.counters["silent_no_impulse"]
            + st.counters["silent_not_approaching"]
            + st.counters["silent_resting"]
            + st.counters["silent_separating"]
        ) >= 1
    else:
        assert out.get("emissions")
        em = out["emissions"][0]
        assert em["receipt_kind"] == ooia.EMISSION_RECEIPT
        assert em["mechanical_energy_withdrawn"] is False
        assert em["band_profile"] == pca.BAND_PROFILE
        assert em["graph_source_label"].startswith("OO_IMPACT:")


def test_11_resting_contact_silent():
    rt = _rt()
    cx, cy = 12.0, 12.0
    _place_object(rt, 0, cx, cy, state="FREE_STATIC", vx=0.0, vy=0.0)
    _place_object(rt, 1, cx + 2 * OR - 0.1, cy, state="FREE_STATIC", vx=0.0, vy=0.0)
    _detect_impulse_acoustics(rt, tick=1)
    st = ooia.state_of(rt.world)
    assert st.counters["emissions"] == 0


def test_12_separating_silent():
    rt = _rt()
    cx, cy = 12.0, 12.0
    _place_object(rt, 0, cx, cy, state="FREE_MOVING", vx=-0.3, vy=0.0)
    _place_object(rt, 1, cx + 2 * OR - 0.1, cy, state="FREE_MOVING", vx=0.3, vy=0.0)
    _detect_impulse_acoustics(rt, tick=1)
    st = ooia.state_of(rt.world)
    assert st.counters["emissions"] == 0


def test_13_impulse_only_preset_no_emission_path():
    rt = PhysicalSystemRuntime(seed=17, config=acanthostega_object_object_impulse_config())
    assert ooia.state_of(rt.world) is None


def test_14_near_elastic_zero_dissipation_silent_when_forced():
    rt = _rt()
    st = ooia.ensure_resource_object_pair_impact_acoustics_for_runtime(rt.world, rt.config)
    assert st is not None
    receipt = {
        "receipt_kind": ooi.RECEIPT_KIND,
        "response_key": "ep:1:1",
        "episode_id": "ep",
        "object_id_a": "obj-0",
        "object_id_b": "obj-1",
        "pair_key": "obj-0|obj-1",
        "reason": "APPROACHING",
        "approaching": True,
        "impulse_transferred": True,
        "impulse_scalar_j": 0.5,
        "isolated_pair": True,
        "ke_pair_pre": 1.0,
        "ke_pair_post": 1.0,
        "dissipated_energy": 0.0,
    }
    rt.world.last_resource_object_pair_contact_impulse_step = {
        "event": ooi.EVENT_STEP,
        "tick": 5,
        "responses": [receipt],
    }
    out = ooia.process_resource_object_pair_impact_acoustics(rt.world, rt.config, emission_tick=5)
    assert out["emissions"] == []
    assert any(m.get("silence_reason") == ooia.R_NO_DISSIPATION for m in out["measurements"])


def test_15_below_epsilon_silent():
    rt = _rt()
    receipt = {
        "response_key": "ep:2:1",
        "episode_id": "ep",
        "object_id_a": "obj-0",
        "object_id_b": "obj-1",
        "pair_key": "obj-0|obj-1",
        "reason": "APPROACHING",
        "approaching": True,
        "impulse_transferred": True,
        "impulse_scalar_j": 1e-6,
        "isolated_pair": True,
        "ke_pair_pre": 1.0,
        "ke_pair_post": 0.5,
        "dissipated_energy": 0.5,
    }
    rt.world.last_resource_object_pair_contact_impulse_step = {"tick": 6, "responses": [receipt]}
    out = ooia.process_resource_object_pair_impact_acoustics(rt.world, rt.config, emission_tick=6)
    assert out["emissions"] == []
    assert any(m.get("silence_reason") == ooia.R_BELOW_EPSILON for m in out["measurements"])


def test_16_multi_contact_unresolved_silent():
    rt = _rt()
    receipt = {
        "response_key": "multi:a|b|c:7:1",
        "reason": "MULTI_CONTACT_COMPONENT_NOT_RESOLVED",
        "impulse_transferred": False,
        "impulse_scalar_j": 0.0,
        "component_object_count": 3,
        "component_edge_count": 2,
        "isolated_pair": False,
    }
    rt.world.last_resource_object_pair_contact_impulse_step = {"tick": 7, "responses": [receipt]}
    out = ooia.process_resource_object_pair_impact_acoustics(rt.world, rt.config, emission_tick=7)
    assert out["emissions"] == []
    assert any(m.get("silence_reason") == ooia.R_UNRESOLVED for m in out["measurements"])
    assert any(m.get("emission_created") is False for m in out["measurements"])
    st = ooia.state_of(rt.world)
    assert st.counters["silent_unresolved"] >= 1
    assert st.counters["emissions"] == 0


# ---------- transport / spectrum / privacy / dedupe / snapshot ----------


def test_20_uses_existing_lps_emit_not_second_transport():
    rt = _rt()
    assert lps.state_of(rt.world) is not None
    objs = list(rt.world.resource_objects)
    oid_a = str(objs[0].object_id)
    oid_b = str(objs[1].object_id)
    receipt = {
        "response_key": "ep:7:1",
        "episode_id": "ep",
        "object_id_a": oid_a,
        "object_id_b": oid_b,
        "pair_key": f"{min(oid_a, oid_b)}|{max(oid_a, oid_b)}",
        "reason": "APPROACHING",
        "approaching": True,
        "impulse_transferred": True,
        "impulse_scalar_j": 0.5,
        "isolated_pair": True,
        "ke_pair_pre": 2.0,
        "ke_pair_post": 1.0,
        "dissipated_energy": 1.0,
    }
    rt.world.last_resource_object_pair_contact_step = {
        "tick": 7,
        "begin": [{
            "episode_id": "ep",
            "object_id_a": oid_a,
            "object_id_b": oid_b,
            "pair_key": receipt["pair_key"],
            "contact_fact": True,
            "contact_point": [10.0, 10.0],
            "contact_point_policy": "TEST",
        }],
        "persist": [],
    }
    rt.world.last_resource_object_pair_contact_impulse_step = {"tick": 7, "responses": [receipt]}
    out = ooia.process_resource_object_pair_impact_acoustics(rt.world, rt.config, emission_tick=7)
    assert len(out["emissions"]) == 1
    em = out["emissions"][0]
    assert em["anonymous_band_vector"]
    assert abs(sum(em["anonymous_band_vector"]) - em["emitted_energy"]) < 1e-9
    assert em["band_profile"] == "UNIFORM_BROADBAND_V1"
    n = len(em["anonymous_band_vector"])
    assert all(abs(b - em["emitted_energy"] / n) < 1e-12 for b in em["anonymous_band_vector"])
    assert abs(em["position"][0] - 10.0) < 1e-9


def test_21_dedupe_same_response_key():
    rt = _rt()
    receipt = {
        "response_key": "ep:8:1",
        "episode_id": "ep",
        "object_id_a": "obj-0",
        "object_id_b": "obj-1",
        "pair_key": "obj-0|obj-1",
        "reason": "APPROACHING",
        "approaching": True,
        "impulse_transferred": True,
        "impulse_scalar_j": 0.5,
        "isolated_pair": True,
        "ke_pair_pre": 2.0,
        "ke_pair_post": 1.0,
        "dissipated_energy": 1.0,
    }
    rt.world.last_resource_object_pair_contact_step = {
        "tick": 8,
        "begin": [{"episode_id": "ep", "object_id_a": "obj-0", "object_id_b": "obj-1",
                   "pair_key": "obj-0|obj-1", "contact_fact": True,
                   "contact_point": [5.0, 5.0]}],
        "persist": [],
    }
    rt.world.last_resource_object_pair_contact_impulse_step = {"tick": 8, "responses": [receipt]}
    out1 = ooia.process_resource_object_pair_impact_acoustics(rt.world, rt.config, emission_tick=8)
    assert len(out1["emissions"]) == 1
    out2 = ooia.process_resource_object_pair_impact_acoustics(rt.world, rt.config, emission_tick=8)
    assert out2.get("status") == "ALREADY_PROCESSED"
    rt.world.last_resource_object_pair_contact_impulse_step = {"tick": 9, "responses": [receipt]}
    out3 = ooia.process_resource_object_pair_impact_acoustics(rt.world, rt.config, emission_tick=9)
    assert len(out3["emissions"]) == 0
    assert any(m.get("silence_reason") == ooia.R_ALREADY for m in out3["measurements"])


def test_22_snapshot_restore_preserves_processed_keys():
    rt = _rt()
    receipt = {
        "response_key": "ep:10:1",
        "episode_id": "ep",
        "object_id_a": "obj-0",
        "object_id_b": "obj-1",
        "pair_key": "obj-0|obj-1",
        "reason": "APPROACHING",
        "approaching": True,
        "impulse_transferred": True,
        "impulse_scalar_j": 0.5,
        "isolated_pair": True,
        "ke_pair_pre": 2.0,
        "ke_pair_post": 0.8,
        "dissipated_energy": 1.2,
    }
    rt.world.last_resource_object_pair_contact_step = {
        "tick": 10,
        "begin": [{"episode_id": "ep", "object_id_a": "obj-0", "object_id_b": "obj-1",
                   "pair_key": "obj-0|obj-1", "contact_fact": True,
                   "contact_point": [4.0, 4.0]}],
        "persist": [],
    }
    rt.world.last_resource_object_pair_contact_impulse_step = {"tick": 10, "responses": [receipt]}
    ooia.process_resource_object_pair_impact_acoustics(rt.world, rt.config, emission_tick=10)
    snap = rt.snapshot(persist=True)
    rt2 = PhysicalSystemRuntime.restore(snap)
    st2 = ooia.state_of(rt2.world)
    assert st2 is not None
    assert "oop:ep:10:1" in st2.processed_response_keys
    rt2.world.last_resource_object_pair_contact_impulse_step = {"tick": 11, "responses": [receipt]}
    out = ooia.process_resource_object_pair_impact_acoustics(rt2.world, rt2.config, emission_tick=11)
    assert len(out["emissions"]) == 0


def test_23_privacy_cognition_only_osc_tokens():
    rt = _rt()
    objs = list(rt.world.resource_objects)
    oid_a, oid_b = str(objs[0].object_id), str(objs[1].object_id)
    receipt = {
        "response_key": "ep:11:1",
        "episode_id": "secret-episode",
        "object_id_a": oid_a,
        "object_id_b": oid_b,
        "pair_key": "secret-pair",
        "reason": "APPROACHING",
        "approaching": True,
        "impulse_transferred": True,
        "impulse_scalar_j": 0.5,
        "isolated_pair": True,
        "ke_pair_pre": 2.0,
        "ke_pair_post": 1.0,
        "dissipated_energy": 1.0,
    }
    rt.world.last_resource_object_pair_contact_step = {
        "tick": 11,
        "begin": [{"episode_id": "secret-episode", "object_id_a": oid_a, "object_id_b": oid_b,
                   "pair_key": "secret-pair", "contact_fact": True,
                   "contact_point": [8.0, 8.0]}],
        "persist": [],
    }
    rt.world.last_resource_object_pair_contact_impulse_step = {"tick": 11, "responses": [receipt]}
    ooia.process_resource_object_pair_impact_acoustics(rt.world, rt.config, emission_tick=11)
    lps.step_end_of_tick(rt.world, rt.config, body_refs_for_runtime(rt), tick_now=12)
    frag = cognition_osc_fragments(rt.body, rt.world, rt.config.oscillatory_signaling)
    payload = {"osc": frag}
    audit_cognition_payload(payload)
    blob = str(payload).lower()
    for forbidden in ("secret-episode", "secret-pair", "impulse", "dissipat", "emission_id", "contact_point"):
        assert forbidden not in blob


def test_24_energy_contract_no_mechanical_withdrawal():
    raw, emitted = ooia.acoustic_energy_from_dissipation(
        1.0, ooia.ResourceObjectPairImpactAcousticConfig(enabled=True)
    )
    assert raw == 1.0 * ooia.DEFAULT_ACOUSTIC_COUPLING
    assert 0.0 < emitted <= ooia.DEFAULT_MAX_ACOUSTIC_ENERGY
    assert ooia.dissipated_pairwise_ke(5.0, 3.0) == 2.0
    assert ooia.GLOBAL_ENERGY_CONSERVATION_CLAIMED == "NO"


def test_25_canonical_map_includes_mechanism():
    can = preset_canonical(PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPACT_ACOUSTICS)
    assert can["mechanisms"][MID] is True
    assert can["mechanisms"][ooi.MECHANISM_ID] is True
    assert can["mechanisms"][pca.MECHANISM_ID] is True


def test_26_broadband_bands_imported_not_copied():
    assert ooia.broadband_bands is pca.broadband_bands
    assert ooia.BAND_PROFILE_NAME == pca.BAND_PROFILE


def test_27_dedup_namespace_distinct_from_bo():
    assert ooia._dedup_key("ep:1:1") == "oop:ep:1:1"
    assert ooia.DEDUP_PREFIX == "oop:"


def test_28_unit_budget_guard():
    rt = _rt()
    for t in range(1, 6):
        _place_object(rt, 0, 12.0, 14.0, state="FREE_MOVING", vx=0.3, vy=0.0)
        _place_object(rt, 1, 14.0, 14.0, state="FREE_STATIC")
        _detect_impulse_acoustics(rt, tick=t)
        lps.step_end_of_tick(rt.world, rt.config, body_refs_for_runtime(rt), tick_now=t + 1)
    assert True
