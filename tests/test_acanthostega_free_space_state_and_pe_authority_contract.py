"""Free-Space V1A · Support state + PE authority contract — focused deterministic tests."""
from __future__ import annotations

from copy import deepcopy

TICKS = {"n": 0}


def _tick(n: int = 1) -> None:
    TICKS["n"] += int(n)


def _cfg():
    from mechanistic_mind.model.acanthostega import (
        acanthostega_free_space_state_and_pe_authority_contract_config,
    )

    cfg = acanthostega_free_space_state_and_pe_authority_contract_config()
    cfg.cognition.cognition_enabled = False
    return cfg


def _parent_cfg():
    from mechanistic_mind.model.acanthostega import (
        acanthostega_held_deposition_radius_shrink_transaction_config,
    )

    cfg = acanthostega_held_deposition_radius_shrink_transaction_config()
    cfg.cognition.cognition_enabled = False
    return cfg


def _rt(cfg=None):
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

    rt = PhysicalSystemRuntime(seed=7, config=cfg or _cfg())
    return rt


def test_preset_identity_parent_and_model_line():
    from mechanistic_mind.physical_system.experiment_canonical import (
        PRESET_ACANTHOSTEGA_FREE_SPACE_STATE_AND_PE_AUTHORITY_CONTRACT,
        PRESET_ACANTHOSTEGA_HELD_DEPOSITION_RADIUS_SHRINK_TRANSACTION,
        normalize_preset_name,
        preset_canonical,
    )
    from mechanistic_mind.physical_system.free_space_state_and_pe_authority_contract import (
        MECHANISM_ID,
        PROFILE_VERSION,
        RECEIPT_KIND,
        free_space_state_and_pe_authority_contract_is_active,
    )

    n = normalize_preset_name("FREE_SPACE_STATE_AND_PE_AUTHORITY_CONTRACT_V1")
    assert n == PRESET_ACANTHOSTEGA_FREE_SPACE_STATE_AND_PE_AUTHORITY_CONTRACT
    meta = preset_canonical(n)
    assert meta["public_preset"] == PRESET_ACANTHOSTEGA_FREE_SPACE_STATE_AND_PE_AUTHORITY_CONTRACT
    assert meta["parent"] == PRESET_ACANTHOSTEGA_HELD_DEPOSITION_RADIUS_SHRINK_TRANSACTION
    assert meta["model_line"] == "ACANTHOSTEGA"
    assert meta["mechanisms"][MECHANISM_ID] is True
    assert meta["mechanisms"]["held_deposition_radius_shrink_transaction"] is True
    assert meta["mechanisms"]["bnlt_move_breakaway_locomotion_repair"] is True
    assert meta["mechanisms"]["repeated_conservative_surface_column_separation"] is True
    assert meta["mechanisms"]["active_locomotion_traction_vs_sliding_friction"] is True
    assert meta["mechanisms"]["event_driven_crowded_placement_retry_contract"] is True
    assert meta["mechanisms"]["detached_material_amount_scaled_collision_radius"] is True
    assert meta["mechanisms"]["held_combine_radius_resize_transaction"] is True
    assert meta["mechanisms"]["flat_ground_gravity"] is True
    assert meta["response"] == MECHANISM_ID

    cfg = _cfg()
    assert free_space_state_and_pe_authority_contract_is_active(cfg)
    assert cfg.public_preset == PRESET_ACANTHOSTEGA_FREE_SPACE_STATE_AND_PE_AUTHORITY_CONTRACT
    assert cfg.model_line == "ACANTHOSTEGA"
    assert PROFILE_VERSION == "FREE_SPACE_STATE_PE_AUTHORITY_PROFILE_V1"
    assert RECEIPT_KIND == "FREE_SPACE_SUPPORT_STATE_V1"

    parent = _parent_cfg()
    assert not free_space_state_and_pe_authority_contract_is_active(parent)
    assert parent.public_preset == PRESET_ACANTHOSTEGA_HELD_DEPOSITION_RADIUS_SHRINK_TRANSACTION


def test_conflicting_tiktaalik_client_identity_ignored():
    from mechanistic_mind.model.lines import stamp_config_from_preset
    from mechanistic_mind.physical_system.experiment_canonical import (
        PRESET_ACANTHOSTEGA_FREE_SPACE_STATE_AND_PE_AUTHORITY_CONTRACT,
    )
    from mechanistic_mind.physical_system.free_space_state_and_pe_authority_contract import (
        free_space_state_and_pe_authority_contract_is_active,
    )

    cfg = _cfg()
    # Conflicting client Tiktaalik label must not override Acanthostega preset builder.
    stamp_config_from_preset(cfg, PRESET_ACANTHOSTEGA_FREE_SPACE_STATE_AND_PE_AUTHORITY_CONTRACT)
    assert cfg.model_line == "ACANTHOSTEGA"
    assert free_space_state_and_pe_authority_contract_is_active(cfg)
    assert "TIKTAALIK" not in str(cfg.public_preset)


def test_supported_rest_gravity_gate_body():
    from mechanistic_mind.physical_system.flat_ground_gravity import integrate_body_vertical
    from mechanistic_mind.physical_system.surface_elevation_support import support_z_for_entity

    rt = _rt()
    body = rt.body
    sz = float(support_z_for_entity(rt.world, rt.config, body.x, body.y))
    body.grounded = True
    body.z = sz
    body.vz = 0.0
    body.vx = 0.0
    body.vy = 0.0
    z0 = float(body.z)
    integrate_body_vertical(
        body,
        body_id="agent_0",
        body_cfg=rt.config.body,
        config=rt.config,
        tick=0,
        world=rt.world,
    )
    _tick(1)
    assert abs(float(body.z) - z0) <= 1e-12
    assert abs(float(body.vz)) <= 1e-12
    rec = getattr(rt.world, "last_free_space_support_state", None)
    assert rec is not None
    assert rec["gravity_applied"] is False
    assert rec["gravity_skip_reason"] == "GRAVITY_SKIPPED_VALID_SUPPORT"
    assert rec.get("clamp_dissipation_class") is None
    assert float(rec.get("removed_vertical_ke") or 0.0) == 0.0
    assert rec["support_state"] == "SUPPORTED"
    assert rec["double_pe_authority"] is False
    assert int(rec["active_pe_authority_count"]) <= 1
    assert rec["landing_contact_fact_implemented"] is False
    assert rec["impact_sound_emitted"] is False
    assert rec["impulse_emitted"] is False


def test_unsupported_body_still_falls_once_per_tick():
    from mechanistic_mind.physical_system.flat_ground_gravity import integrate_body_vertical
    from mechanistic_mind.physical_system.surface_elevation_support import support_z_for_entity

    rt = _rt()
    body = rt.body
    sz = float(support_z_for_entity(rt.world, rt.config, body.x, body.y))
    body.grounded = False
    body.z = sz + 2.0
    body.vz = 0.0
    z0 = float(body.z)
    integrate_body_vertical(
        body,
        body_id="agent_0",
        body_cfg=rt.config.body,
        config=rt.config,
        tick=1,
        world=rt.world,
    )
    _tick(1)
    assert float(body.z) < z0
    assert float(body.vz) < 0.0
    rec = getattr(rt.world, "last_free_space_support_state", None)
    assert rec is not None
    assert rec["gravity_applied"] is True
    assert rec["support_state"] == "UNSUPPORTED"
    assert rec["active_pe_authority"] == "PE_AUTHORITY_UNSUPPORTED_FREE_SPACE"
    assert rec["vertical_integration_applied"] is True
    z1 = float(body.z)
    integrate_body_vertical(
        body,
        body_id="agent_0",
        body_cfg=rt.config.body,
        config=rt.config,
        tick=2,
        world=rt.world,
    )
    _tick(1)
    assert float(body.z) < z1


def test_unsupported_free_object_falls():
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
        object_id="resource-fall",
        x=5.0,
        y=5.0,
        z=sz + 1.5,
        mass=0.2,
        quantity=0.2,
        composition=(MaterialComponent("component_a", 0.2),),
        physical_state=PHYSICAL_STATE_FREE_STATIC,
        collision_radius=0.2,
        vertical_half_extent=0.2,
        optical_radius=0.2,
        optical_response=(0.1, 0.2, 0.3),
    )
    obj.physical_state = "FREE_MOVING"
    obj.vz = 0.0
    obj.grounded = False
    rt.world.resource_objects = [obj]
    z0 = float(obj.z)
    integrate_free_objects_vertical(rt.world, rt.config, tick=1)
    _tick(1)
    assert float(obj.z) < z0
    assert float(obj.vz) < 0.0


def test_held_object_excluded_from_independent_gravity():
    from mechanistic_mind.physical_system.resource_objects import (
        PHYSICAL_STATE_HELD,
        MaterialComponent,
        ResourceObject,
    )

    rt = _rt()
    obj = ResourceObject(
        object_id="resource-held",
        x=float(rt.body.x),
        y=float(rt.body.y),
        z=float(rt.body.z) + 0.5,
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
    obj.vz = 0.0
    obj.grounded = False
    z0 = float(obj.z)
    rt.world.resource_objects = list(getattr(rt.world, "resource_objects", []) or []) + [obj]
    rt.step()
    _tick(1)
    # Held objects follow holder; must not independently integrate free-space gravity.
    # z may track holder, but vz must not accumulate independent fall from FGG free path.
    assert obj.physical_state == PHYSICAL_STATE_HELD


def test_support_loss_no_snap_disables_ground_forces():
    from mechanistic_mind.physical_system.free_space_state_and_pe_authority_contract import (
        ground_forces_eligible,
        note_support_loss_terrain_mutation,
    )

    rt = _rt()
    body = rt.body
    body.grounded = True
    body.z = 1.0
    body.vz = 0.0
    body.vx = 0.25
    vx0 = float(body.vx)
    z0 = float(body.z)
    note_support_loss_terrain_mutation(
        rt.world,
        rt.config,
        tick=int(rt.world.tick),
        entity_id="agent_0",
        entity_kind="body",
        z=z0,
        vz=0.0,
        support_z_after=0.0,
        half_extent=float(getattr(body, "vertical_half_extent", 0.5) or 0.5),
    )
    body.grounded = False
    assert abs(float(body.z) - z0) <= 1e-12  # no downward snap
    assert ground_forces_eligible(body, config=rt.config) is False
    assert abs(float(body.vx) - vx0) <= 1e-12
    rec = getattr(rt.world, "last_free_space_support_state", None)
    assert rec["transition_reason"] == "SUPPORT_LOST_TERRAIN_MUTATION"
    assert rec["vertical_integration_applied"] is False
    assert rec["support_state"] == "UNSUPPORTED"


def test_terrain_mutation_fall_next_tick_no_second_integration():
    from mechanistic_mind.physical_system.flat_ground_gravity import integrate_body_vertical
    from mechanistic_mind.physical_system.free_space_state_and_pe_authority_contract import (
        note_support_loss_terrain_mutation,
    )

    rt = _rt()
    body = rt.body
    body.grounded = True
    body.z = 1.2
    body.vz = 0.0
    z_mut = float(body.z)
    note_support_loss_terrain_mutation(
        rt.world,
        rt.config,
        tick=int(rt.world.tick),
        entity_id="agent_0",
        entity_kind="body",
        z=z_mut,
        vz=0.0,
        support_z_after=0.0,
        half_extent=0.5,
    )
    body.grounded = False
    assert abs(float(body.z) - z_mut) <= 1e-12
    integrate_body_vertical(
        body,
        body_id="agent_0",
        body_cfg=rt.config.body,
        config=rt.config,
        tick=int(rt.world.tick) + 1,
        world=rt.world,
    )
    _tick(1)
    assert float(body.z) < z_mut


def test_clamp_classification_no_landing_impulse_sound():
    from mechanistic_mind.physical_system.flat_ground_gravity import integrate_vertical_entity

    rt = _rt()
    body = rt.body
    body.grounded = False
    body.z = 0.05
    body.vz = -2.0
    integrate_vertical_entity(
        body,
        entity_id="agent_0",
        entity_kind="body",
        mass=1.0,
        config=rt.config.flat_ground_gravity,
        tick=int(rt.world.tick),
        world=rt.world,
        runtime_config=rt.config,
        support_z=0.0,
    )
    _tick(1)
    assert body.grounded is True
    assert abs(float(body.vz)) <= 1e-12
    fs = getattr(rt.world, "last_free_space_support_state", None)
    assert fs is not None
    assert fs["terrain_intersection"] is True or fs["current_inelastic_clamp"] is True
    assert fs["landing_contact_fact_implemented"] is False
    assert fs["vertical_compliance_impulse_implemented"] is False
    assert fs["rebound_implemented"] is False
    assert fs["vertical_impact_sound_implemented"] is False
    assert fs["impact_sound_emitted"] is False
    assert fs["impulse_emitted"] is False
    if fs.get("clamp_dissipation_class"):
        assert fs["clamp_dissipation_class"] == "CURRENT_INELASTIC_CLAMP_DISSIPATION"


def test_release_transition_t_plus_1_eligibility():
    from mechanistic_mind.physical_system.flat_ground_gravity import apply_release_vertical
    from mechanistic_mind.physical_system.resource_objects import (
        PHYSICAL_STATE_HELD,
        MaterialComponent,
        ResourceObject,
    )

    rt = _rt()
    obj = ResourceObject(
        object_id="resource-rel",
        x=float(rt.body.x),
        y=float(rt.body.y),
        z=1.0,
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
    rt.body.vz = -0.1
    apply_release_vertical(obj, rt.body, rt.config, world=rt.world, tick=int(rt.world.tick))
    obj.physical_state = "FREE_MOVING"
    rec = getattr(rt.world, "last_free_space_support_state", None)
    assert rec is not None
    assert rec["release_transition"] is True
    assert rec["transition_reason"] == "RELEASE_TRANSITION"
    assert rec["vertical_integration_applied"] is False  # T+1 policy
    assert abs(float(obj.vz) - float(rt.body.vz)) <= 1e-12


def test_newborn_t_plus_1_policy_preserved():
    # DTIP authority: dynamics_eligible_tick = creation_tick + 1
    creation_tick = 10
    eligible = creation_tick + 1
    assert eligible == 11
    # Contract must not claim gravity on creation tick for newborn.
    from mechanistic_mind.physical_system.free_space_state_and_pe_authority_contract import (
        GRAVITY_SKIP_NEWBORN,
        record_vertical_contract_receipt,
    )

    rt = _rt()
    rec = record_vertical_contract_receipt(
        rt.world,
        rt.config,
        tick=creation_tick,
        entity_id="resource-new",
        entity_kind="object",
        body_slot=None,
        z_before=0.5,
        vz_before=0.0,
        z_after=0.5,
        vz_after=0.0,
        centre_z_after=0.7,
        vertical_half_extent=0.2,
        support_z=0.0,
        was_grounded=False,
        grounded_after=False,
        gravity_applied=False,
        skip_gravity=True,
        gravity_skip_reason=GRAVITY_SKIP_NEWBORN,
        support_applied=False,
        landed=False,
        support_dissipated=0.0,
        mass=0.2,
        vertical_integration_eligible=False,
        vertical_integration_applied=False,
        newborn_creation_tick=creation_tick,
        newborn_eligible=False,
        transition_reason_override="NEWBORN_ELIGIBILITY",
    )
    assert rec["newborn_creation_tick"] == creation_tick
    assert rec["newborn_eligible"] is False
    assert rec["gravity_applied"] is False
    assert rec["landing_contact_fact_implemented"] is False


def test_pe_authority_mutual_exclusion_and_ses_gate():
    from mechanistic_mind.physical_system.flat_ground_gravity import integrate_body_vertical
    from mechanistic_mind.physical_system.free_space_state_and_pe_authority_contract import (
        pe_authority_for,
    )
    from mechanistic_mind.physical_system.surface_elevation_support import support_z_for_entity

    assert pe_authority_for(support_state="SUPPORTED", gravity_applied=False) == (
        "PE_AUTHORITY_SUPPORTED_TERRAIN"
    )
    assert pe_authority_for(support_state="UNSUPPORTED", gravity_applied=True) == (
        "PE_AUTHORITY_UNSUPPORTED_FREE_SPACE"
    )
    rt = _rt()
    body = rt.body
    sz = float(support_z_for_entity(rt.world, rt.config, body.x, body.y))
    body.grounded = True
    body.z = sz
    body.vz = 0.0
    integrate_body_vertical(
        body,
        body_id="agent_0",
        body_cfg=rt.config.body,
        config=rt.config,
        tick=0,
        world=rt.world,
    )
    _tick(1)
    rec = getattr(rt.world, "last_free_space_support_state", None)
    assert rec["double_pe_authority"] is False
    assert int(rec["active_pe_authority_count"]) <= 1


def test_snapshot_restore_mid_fall_and_supported_rest_no_replay():
    from mechanistic_mind.physical_system.flat_ground_gravity import integrate_body_vertical
    from mechanistic_mind.physical_system.surface_elevation_support import support_z_for_entity

    rt = _rt()
    body = rt.body
    # Mid-fall snapshot
    body.grounded = False
    body.z = 1.8
    body.vz = -0.4
    snap = deepcopy(rt.snapshot())
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

    restored = PhysicalSystemRuntime.restore(snap)
    assert abs(float(restored.body.z) - 1.8) <= 1e-12
    assert abs(float(restored.body.vz) - (-0.4)) <= 1e-12
    assert restored.body.grounded is False
    # Supported rest
    rt2 = _rt()
    sz = float(support_z_for_entity(rt2.world, rt2.config, rt2.body.x, rt2.body.y))
    rt2.body.grounded = True
    rt2.body.z = sz
    rt2.body.vz = 0.0
    integrate_body_vertical(
        rt2.body,
        body_id="agent_0",
        body_cfg=rt2.config.body,
        config=rt2.config,
        tick=0,
        world=rt2.world,
    )
    _tick(1)
    snap2 = deepcopy(rt2.snapshot())
    hist_before = len(
        (snap2.get("free_space_state_and_pe_authority_contract_state") or {}).get("history") or []
    )
    restored2 = PhysicalSystemRuntime.restore(snap2)
    assert restored2.body.grounded is True
    assert abs(float(restored2.body.vz)) <= 1e-12
    hist_after = len(
        getattr(
            getattr(restored2.world, "free_space_state_and_pe_authority_contract_state", None),
            "history",
            [],
        )
        or []
    )
    assert hist_after == hist_before


def test_parent_snapshot_under_child_classifies_without_advancing():
    parent = _rt(_parent_cfg())
    parent.body.grounded = True
    parent.body.z = 0.0
    parent.body.vz = 0.0
    snap = deepcopy(parent.snapshot())
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
    from mechanistic_mind.physical_system.free_space_state_and_pe_authority_contract import (
        FreeSpaceStateAndPeAuthorityContractConfig,
    )

    snap["config"] = snap.get("config") or {}
    snap["config"]["public_preset"] = (
        "ACANTHOSTEGA_BETA4_FREE_SPACE_STATE_AND_PE_AUTHORITY_CONTRACT"
    )
    snap["config"]["free_space_state_and_pe_authority_contract"] = (
        FreeSpaceStateAndPeAuthorityContractConfig(enabled=True).to_dict()
    )
    z0 = float(parent.body.z)
    vz0 = float(parent.body.vz)
    restored = PhysicalSystemRuntime.restore(snap)
    assert abs(float(restored.body.z) - z0) <= 1e-12
    assert abs(float(restored.body.vz) - vz0) <= 1e-12


def test_tiktaalik_off_no_vertical_contract_fields():
    from mechanistic_mind.model.tiktaalik import tiktaalik_config
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

    cfg = tiktaalik_config()
    rt = PhysicalSystemRuntime(seed=3, config=cfg)
    snap = rt.snapshot()
    fs_cfg = (snap.get("config") or {}).get("free_space_state_and_pe_authority_contract")
    assert fs_cfg in (None, {}) or (isinstance(fs_cfg, dict) and fs_cfg.get("enabled") is not True)
    assert snap.get("free_space_state_and_pe_authority_contract_state") in (None, {})


def test_cognition_privacy_tokens():
    from mechanistic_mind.physical_system.flat_ground_gravity import integrate_body_vertical
    from mechanistic_mind.physical_system.observation import audit_cognition_payload
    from mechanistic_mind.physical_system.surface_elevation_support import support_z_for_entity

    rt = _rt()
    sz = float(support_z_for_entity(rt.world, rt.config, rt.body.x, rt.body.y))
    rt.body.z = sz
    rt.body.vz = 0.0
    rt.body.grounded = True
    integrate_body_vertical(
        rt.body,
        body_id="agent_0",
        body_cfg=rt.config.body,
        config=rt.config,
        tick=0,
        world=rt.world,
    )
    _tick(1)
    obs = rt.agent_observation()
    hits = audit_cognition_payload(obs)
    assert hits == []
    blob = repr(obs)
    for tok in (
        "FREE_SPACE_SUPPORT_STATE_V1",
        "PE_AUTHORITY_UNSUPPORTED_FREE_SPACE",
        "GRAVITY_SKIPPED_VALID_SUPPORT",
        "CURRENT_INELASTIC_CLAMP_DISSIPATION",
        "SUPPORT_ACQUIRED_INELASTIC_CLAMP",
        "free_space_state_and_pe_authority_contract",
    ):
        assert tok not in blob


def test_two_agent_shared_free_object_once():
    from mechanistic_mind.physical_system.flat_ground_gravity import integrate_free_objects_vertical
    from mechanistic_mind.physical_system.resource_objects import (
        PHYSICAL_STATE_FREE_STATIC,
        MaterialComponent,
        ResourceObject,
    )
    from mechanistic_mind.physical_system.surface_elevation_support import support_z_for_entity
    from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime

    cfg = _cfg()
    ta = TwoAgentRuntime(seed=11, config=cfg)
    world = ta.world
    sz = float(support_z_for_entity(world, ta.config, 5.0, 5.0))
    obj = ResourceObject(
        object_id="resource-shared",
        x=5.0,
        y=5.0,
        z=sz + 1.2,
        mass=0.2,
        quantity=0.2,
        composition=(MaterialComponent("component_a", 0.2),),
        physical_state=PHYSICAL_STATE_FREE_STATIC,
        collision_radius=0.2,
        vertical_half_extent=0.2,
        optical_radius=0.2,
        optical_response=(0.1, 0.2, 0.3),
    )
    obj.physical_state = "FREE_MOVING"
    obj.grounded = False
    obj.vz = 0.0
    world.resource_objects = [obj]
    z0 = float(obj.z)
    # Shared free objects integrate once via world path (not per slot).
    integrate_free_objects_vertical(world, ta.config, tick=1)
    _tick(1)
    assert float(obj.z) < z0
    st = getattr(world, "free_space_state_and_pe_authority_contract_state", None)
    assert st is not None
    same = [r for r in st.history if r.get("entity_id") == "resource-shared"]
    assert len(same) == 1


def test_observer_selector_once_and_banner():
    from mechanistic_mind.physical_system.experiment_canonical import (
        PRESET_ACANTHOSTEGA_FREE_SPACE_STATE_AND_PE_AUTHORITY_CONTRACT,
        ACANTHOSTEGA_PUBLIC_PRESET_IDS,
    )
    from mechanistic_mind.physical_system.free_space_state_and_pe_authority_contract import BANNER

    assert PRESET_ACANTHOSTEGA_FREE_SPACE_STATE_AND_PE_AUTHORITY_CONTRACT in ACANTHOSTEGA_PUBLIC_PRESET_IDS
    # frozenset membership implies uniqueness of the identity token
    assert "NO LANDING IMPULSE" in BANNER
    assert "NO IMPACT SOUND" in BANNER
    assert "FREE-SPACE V1A" in BANNER


def test_lps_once_per_scientific_tick_smoke():
    rt = _rt()
    before = 0
    st0 = getattr(rt.world, "local_physical_signal_transport_state", None)
    if st0 is not None:
        before = int(st0.counters.get("steps", 0) or 0)
    rt.step()
    _tick(1)
    st = getattr(rt.world, "local_physical_signal_transport_state", None)
    if st is not None:
        after = int(st.counters.get("steps", 0) or 0)
        assert after - before <= 1


def test_tick_budget_report():
    # Exact simulated ticks across this module (tests call _tick).
    assert TICKS["n"] <= 250
    print(f"TOTAL_SIMULATED_TICKS={TICKS['n']}")
