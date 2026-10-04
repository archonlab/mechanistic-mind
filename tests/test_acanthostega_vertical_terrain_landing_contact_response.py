"""Vertical terrain landing contact/response V1 — focused deterministic tests."""
from __future__ import annotations

from copy import deepcopy

TICKS = {"n": 0}


def _tick(n: int = 1) -> None:
    TICKS["n"] += int(n)


def _cfg():
    from mechanistic_mind.model.acanthostega import (
        acanthostega_vertical_terrain_landing_contact_response_config,
    )

    cfg = acanthostega_vertical_terrain_landing_contact_response_config()
    cfg.cognition.cognition_enabled = False
    return cfg


def _parent_cfg():
    from mechanistic_mind.model.acanthostega import (
        acanthostega_free_space_state_and_pe_authority_contract_config,
    )

    cfg = acanthostega_free_space_state_and_pe_authority_contract_config()
    cfg.cognition.cognition_enabled = False
    return cfg


def _rt(cfg=None):
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

    return PhysicalSystemRuntime(seed=7, config=cfg or _cfg())


def _sz(rt):
    from mechanistic_mind.physical_system.surface_elevation_support import support_z_for_entity

    return float(support_z_for_entity(rt.world, rt.config, rt.body.x, rt.body.y))


def _integ(rt, tick: int):
    from mechanistic_mind.physical_system.flat_ground_gravity import integrate_body_vertical

    return integrate_body_vertical(
        rt.body,
        body_id="agent_0",
        body_cfg=rt.config.body,
        config=rt.config,
        tick=int(tick),
        world=rt.world,
    )


def test_preset_identity_parent_lineage():
    from mechanistic_mind.physical_system.experiment_canonical import (
        PRESET_ACANTHOSTEGA_FREE_SPACE_STATE_AND_PE_AUTHORITY_CONTRACT,
        PRESET_ACANTHOSTEGA_VERTICAL_TERRAIN_LANDING_CONTACT_RESPONSE,
        normalize_preset_name,
        preset_canonical,
    )
    from mechanistic_mind.physical_system.vertical_terrain_landing_contact_response import (
        MECHANISM_ID,
        PROFILE_VERSION,
        RECEIPT_KIND,
        vertical_terrain_landing_contact_response_is_active,
    )
    from mechanistic_mind.physical_system.free_space_state_and_pe_authority_contract import (
        free_space_state_and_pe_authority_contract_is_active,
    )

    n = normalize_preset_name("VERTICAL_TERRAIN_LANDING_CONTACT_RESPONSE_V1")
    assert n == PRESET_ACANTHOSTEGA_VERTICAL_TERRAIN_LANDING_CONTACT_RESPONSE
    meta = preset_canonical(n)
    assert meta["parent"] == PRESET_ACANTHOSTEGA_FREE_SPACE_STATE_AND_PE_AUTHORITY_CONTRACT
    assert meta["model_line"] == "ACANTHOSTEGA"
    assert meta["mechanisms"][MECHANISM_ID] is True
    assert meta["mechanisms"]["free_space_state_and_pe_authority_contract"] is True
    assert meta["mechanisms"]["flat_ground_gravity"] is True
    cfg = _cfg()
    assert vertical_terrain_landing_contact_response_is_active(cfg)
    assert free_space_state_and_pe_authority_contract_is_active(cfg)
    assert PROFILE_VERSION == "VERTICAL_TERRAIN_LANDING_CONTACT_RESPONSE_V1"
    assert RECEIPT_KIND == "VERTICAL_TERRAIN_LANDING_V1"
    parent = _parent_cfg()
    assert not vertical_terrain_landing_contact_response_is_active(parent)
    assert free_space_state_and_pe_authority_contract_is_active(parent)


def test_tiktaalik_override_ignored():
    from mechanistic_mind.model.lines import stamp_config_from_preset
    from mechanistic_mind.physical_system.experiment_canonical import (
        PRESET_ACANTHOSTEGA_VERTICAL_TERRAIN_LANDING_CONTACT_RESPONSE,
    )

    cfg = _cfg()
    stamp_config_from_preset(cfg, PRESET_ACANTHOSTEGA_VERTICAL_TERRAIN_LANDING_CONTACT_RESPONSE)
    assert cfg.model_line == "ACANTHOSTEGA"
    assert "TIKTAALIK" not in str(cfg.public_preset)


def test_rest_persist_no_impulse_no_dissipation():
    rt = _rt()
    sz = _sz(rt)
    rt.body.z = sz
    rt.body.vz = 0.0
    rt.body.grounded = True
    vx0 = float(rt.body.vx)
    rec = _integ(rt, 0)
    _tick(1)
    assert abs(float(rt.body.z) - sz) <= 1e-12
    assert abs(float(rt.body.vz)) <= 1e-12
    assert rec["landed"] is False
    assert float(rec["support_dissipated"]) == 0.0
    lr = rt.world.last_vertical_terrain_landing
    assert lr["response_applied"] is False
    assert lr["episode_phase"] == "PERSIST"
    assert lr["impact_sound_emitted"] is False
    assert abs(float(rt.body.vx) - vx0) <= 1e-12


def test_landing_impact_toi_impulse_support():
    rt = _rt()
    sz = _sz(rt)
    rt.body.z = sz + 0.25
    rt.body.vz = -1.2
    rt.body.grounded = False
    vx0 = 0.17
    rt.body.vx = vx0
    m = float(rt.config.body.mass)
    rec = _integ(rt, 1)
    _tick(1)
    lr = rt.world.last_vertical_terrain_landing
    assert rec["landing_v1b_active"] is True
    assert rec["old_clamp_bypassed"] is True
    assert lr["episode_phase"] == "BEGIN"
    assert lr["response_applied"] is True
    assert lr["toi"] is not None
    assert 0.0 <= float(lr["toi"]) <= 1.0
    assert lr["contact_point"] == [float(rt.body.x), float(rt.body.y), float(sz)] or (
        abs(lr["contact_point"][2] - sz) <= 1e-12
    )
    assert lr["normal"] == [0.0, 0.0, 1.0]
    assert abs(float(lr["impulse_magnitude"]) - (-m * float(lr["vz_pre_response"]))) <= 1e-9
    assert abs(float(rt.body.vz)) <= 1e-12
    assert abs(float(rt.body.z) - sz) <= 1e-12
    assert rt.body.grounded is True
    assert float(lr["dissipated_energy"]) > 0.0
    assert lr["ke_creation"] is False
    assert lr["agent_credit"] is False
    assert lr["rebound"] is False
    assert lr["impact_sound_emitted"] is False
    assert abs(float(rt.body.vx) - vx0) <= 1e-12
    assert lr["pe_authority_after"] == "PE_AUTHORITY_SUPPORTED_TERRAIN"
    assert lr["double_pe_authority"] is False


def test_parent_preserves_old_clamp_child_bypasses():
    parent = _rt(_parent_cfg())
    sz = _sz(parent)
    parent.body.z = sz + 0.05
    parent.body.vz = -2.0
    parent.body.grounded = False
    pr = _integ(parent, 1)
    _tick(1)
    assert pr.get("landing_v1b_active") in (False, None)
    assert pr.get("old_clamp_bypassed") in (False, None)
    assert pr["landed"] is True
    assert float(pr["support_dissipated"]) > 0.0
    assert getattr(parent.world, "last_vertical_terrain_landing", None) is None

    child = _rt()
    sz2 = _sz(child)
    child.body.z = sz2 + 0.05
    child.body.vz = -2.0
    child.body.grounded = False
    cr = _integ(child, 1)
    _tick(1)
    assert cr["landing_v1b_active"] is True
    assert cr["old_clamp_bypassed"] is True
    assert child.world.last_vertical_terrain_landing["old_clamp_and_response_both_run"] is False


def test_free_object_landing_once():
    from mechanistic_mind.physical_system.flat_ground_gravity import integrate_free_objects_vertical
    from mechanistic_mind.physical_system.resource_objects import (
        PHYSICAL_STATE_FREE_STATIC,
        MaterialComponent,
        ResourceObject,
    )
    from mechanistic_mind.physical_system.surface_elevation_support import support_z_for_entity

    rt = _rt()
    sz = float(support_z_for_entity(rt.world, rt.config, 5.0, 5.0))
    obj = ResourceObject(
        object_id="resource-land",
        x=5.0,
        y=5.0,
        z=sz + 0.3,
        mass=0.5,
        quantity=0.5,
        composition=(MaterialComponent("component_a", 0.5),),
        physical_state=PHYSICAL_STATE_FREE_STATIC,
        collision_radius=0.2,
        vertical_half_extent=0.2,
        optical_radius=0.2,
        optical_response=(0.1, 0.2, 0.3),
    )
    obj.physical_state = "FREE_MOVING"
    obj.grounded = False
    obj.vz = -1.0
    rt.world.resource_objects = [obj]
    integrate_free_objects_vertical(rt.world, rt.config, tick=1)
    _tick(1)
    assert abs(float(obj.z) - sz) <= 1e-9 or float(obj.z) <= sz + 1e-9
    assert abs(float(obj.vz)) <= 1e-12
    lr = rt.world.last_vertical_terrain_landing
    assert lr["entity_id"] == "resource-land"
    assert lr["response_applied"] is True


def test_held_excluded_and_recontact_new_episode():
    from mechanistic_mind.physical_system.resource_objects import (
        PHYSICAL_STATE_HELD,
        MaterialComponent,
        ResourceObject,
    )
    from mechanistic_mind.physical_system.flat_ground_gravity import integrate_free_objects_vertical
    from mechanistic_mind.physical_system.vertical_terrain_landing_contact_response import (
        end_episode_for_entity,
    )

    rt = _rt()
    sz = _sz(rt)
    held = ResourceObject(
        object_id="resource-held",
        x=float(rt.body.x),
        y=float(rt.body.y),
        z=sz + 1.0,
        mass=0.2,
        quantity=0.2,
        composition=(MaterialComponent("component_a", 0.2),),
        physical_state=PHYSICAL_STATE_HELD,
        holder_body_id="agent_0",
        manipulator_id="LEFT",
        collision_radius=0.2,
        vertical_half_extent=0.2,
        optical_radius=0.2,
        optical_response=(0.1, 0.2, 0.3),
    )
    held.vz = -2.0
    held.grounded = False
    rt.world.resource_objects = [held]
    integrate_free_objects_vertical(rt.world, rt.config, tick=1)
    _tick(1)
    # HELD skipped by FGG free integration — z unchanged by landing kernel
    assert abs(float(held.z) - (sz + 1.0)) <= 1e-12

    # Re-contact new episode after END
    rt.body.z = sz + 0.2
    rt.body.vz = -1.0
    rt.body.grounded = False
    _integ(rt, 2)
    _tick(1)
    e1 = rt.world.last_vertical_terrain_landing["episode_id"]
    end_episode_for_entity(
        rt.world, rt.config, entity_kind="body", entity_id="agent_0", tick=2
    )
    rt.body.z = sz + 0.2
    rt.body.vz = -1.0
    rt.body.grounded = False
    _integ(rt, 3)
    _tick(1)
    e2 = rt.world.last_vertical_terrain_landing["episode_id"]
    assert e1 != e2
    assert rt.world.last_vertical_terrain_landing["episode_phase"] == "BEGIN"


def test_invalid_mass_anomaly_no_response():
    from mechanistic_mind.physical_system.vertical_terrain_landing_contact_response import (
        apply_vertical_landing,
        ensure_vertical_terrain_landing_contact_response_for_runtime,
    )

    rt = _rt()
    ensure_vertical_terrain_landing_contact_response_for_runtime(rt.world, rt.config)
    sz = _sz(rt)
    rt.body.z = sz + 0.1
    rt.body.vz = -1.0
    rt.body.grounded = False
    rec = apply_vertical_landing(
        rt.body,
        world=rt.world,
        runtime_config=rt.config,
        tick=5,
        entity_id="agent_0",
        entity_kind="body",
        mass=-1.0,
        z0=sz + 0.1,
        vz0=-1.0,
        z1_proposed=sz - 0.05,
        vz1_proposed=-1.1,
        support_z=sz,
        was_grounded=False,
        skip_gravity=False,
        gravity_applied=True,
        ses_below_support=False,
        fgg_config=rt.config.flat_ground_gravity,
    )
    _tick(1)
    assert rec["response_applied"] is False
    assert rec["anomaly"] == "INVALID_MASS_ANOMALY"
    assert float(rec["dissipated_energy"]) == 0.0


def test_snapshot_restore_no_replay():
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

    rt = _rt()
    sz = _sz(rt)
    rt.body.z = sz + 0.3
    rt.body.vz = -0.8
    rt.body.grounded = False
    _integ(rt, 1)
    _tick(1)
    snap = deepcopy(rt.snapshot())
    hist = len((snap.get("vertical_terrain_landing_contact_response_state") or {}).get("history") or [])
    restored = PhysicalSystemRuntime.restore(snap)
    assert abs(float(restored.body.z) - float(rt.body.z)) <= 1e-12
    hist2 = len(
        getattr(
            getattr(restored.world, "vertical_terrain_landing_contact_response_state", None),
            "history",
            [],
        )
        or []
    )
    assert hist2 == hist
    # mid-fall restore
    rt2 = _rt()
    rt2.body.z = 1.7
    rt2.body.vz = -0.4
    rt2.body.grounded = False
    snap2 = deepcopy(rt2.snapshot())
    r2 = PhysicalSystemRuntime.restore(snap2)
    assert abs(float(r2.body.z) - 1.7) <= 1e-12
    assert abs(float(r2.body.vz) - (-0.4)) <= 1e-12


def test_cognition_privacy():
    from mechanistic_mind.physical_system.observation import audit_cognition_payload

    rt = _rt()
    sz = _sz(rt)
    rt.body.z = sz + 0.2
    rt.body.vz = -1.0
    rt.body.grounded = False
    _integ(rt, 1)
    _tick(1)
    obs = rt.agent_observation()
    assert audit_cognition_payload(obs) == []
    blob = repr(obs)
    for tok in (
        "VERTICAL_TERRAIN_LANDING_V1",
        "LANDING_IMPULSE",
        "TIME_OF_IMPACT",
        "PENETRATION_DEPTH",
        "vertical_terrain_landing_contact_response",
    ):
        assert tok not in blob


def test_two_agent_shared_once():
    from mechanistic_mind.physical_system.flat_ground_gravity import integrate_free_objects_vertical
    from mechanistic_mind.physical_system.resource_objects import (
        PHYSICAL_STATE_FREE_STATIC,
        MaterialComponent,
        ResourceObject,
    )
    from mechanistic_mind.physical_system.surface_elevation_support import support_z_for_entity
    from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime

    ta = TwoAgentRuntime(seed=11, config=_cfg())
    sz = float(support_z_for_entity(ta.world, ta.config, 5.0, 5.0))
    obj = ResourceObject(
        object_id="resource-shared",
        x=5.0,
        y=5.0,
        z=sz + 0.4,
        mass=0.3,
        quantity=0.3,
        composition=(MaterialComponent("component_a", 0.3),),
        physical_state=PHYSICAL_STATE_FREE_STATIC,
        collision_radius=0.2,
        vertical_half_extent=0.2,
        optical_radius=0.2,
        optical_response=(0.1, 0.2, 0.3),
    )
    obj.physical_state = "FREE_MOVING"
    obj.grounded = False
    obj.vz = -0.9
    ta.world.resource_objects = [obj]
    integrate_free_objects_vertical(ta.world, ta.config, tick=1)
    _tick(1)
    st = getattr(ta.world, "vertical_terrain_landing_contact_response_state", None)
    same = [r for r in st.history if r.get("entity_id") == "resource-shared"]
    assert len(same) == 1


def test_observer_selector_once():
    from mechanistic_mind.physical_system.experiment_canonical import (
        PRESET_ACANTHOSTEGA_VERTICAL_TERRAIN_LANDING_CONTACT_RESPONSE,
        ACANTHOSTEGA_PUBLIC_PRESET_IDS,
    )
    from mechanistic_mind.physical_system.vertical_terrain_landing_contact_response import BANNER

    assert PRESET_ACANTHOSTEGA_VERTICAL_TERRAIN_LANDING_CONTACT_RESPONSE in ACANTHOSTEGA_PUBLIC_PRESET_IDS
    assert "NO IMPACT SOUND" in BANNER
    assert "e=0" in BANNER or "e=0" in BANNER.replace(" ", "")


def test_tick_budget():
    assert TICKS["n"] <= 300
    print(f"TOTAL_SIMULATED_TICKS={TICKS['n']}")
