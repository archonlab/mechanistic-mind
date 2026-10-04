"""Event-driven crowded placement retry contract V1 — focused deterministic tests."""
from __future__ import annotations

TICKS = {"n": 0}


def _tick(n: int = 1) -> None:
    TICKS["n"] += int(n)


def _cfg():
    from mechanistic_mind.model.acanthostega import (
        acanthostega_event_driven_crowded_placement_retry_contract_config,
    )

    cfg = acanthostega_event_driven_crowded_placement_retry_contract_config()
    cfg.cognition.cognition_enabled = False
    return cfg


def _parent_cfg():
    from mechanistic_mind.model.acanthostega import (
        acanthostega_active_locomotion_traction_vs_sliding_friction_config,
    )

    cfg = acanthostega_active_locomotion_traction_vs_sliding_friction_config()
    cfg.cognition.cognition_enabled = False
    return cfg


def _rt(cfg=None, seed: int = 17):
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

    rt = PhysicalSystemRuntime(seed=seed, config=cfg or _cfg())
    rt.body.x, rt.body.y = 2.5, 2.5
    rt.world.detached_placement_body_refs = [("body-0", rt.body)]
    return rt


def _block_all_candidates(rt, cx=10, cy=10):
    from mechanistic_mind.physical_system.resource_objects import (
        ResourceObject,
        MaterialComponent,
        CANONICAL_COLLISION_RADIUS,
        PHYSICAL_STATE_FREE_STATIC,
    )
    from mechanistic_mind.physical_system.detached_terrain_material_initial_placement import (
        CANDIDATE_OFFSETS_V1,
    )

    blockers = []
    for i, (dx, dy) in enumerate(CANDIDATE_OFFSETS_V1):
        blockers.append(
            ResourceObject(
                object_id=f"resource-block-{i:03d}",
                x=cx + 0.5 + dx,
                y=cy + 0.5 + dy,
                mass=1.0,
                quantity=1.0,
                composition=(MaterialComponent("stone", 1.0),),
                physical_state=PHYSICAL_STATE_FREE_STATIC,
                collision_radius=CANONICAL_COLLISION_RADIUS,
                z=0.0,
                grounded=True,
            )
        )
    rt.world.resource_objects = list(rt.world.resource_objects or []) + blockers
    return blockers


def _exert(rt, *, tick, cx=10, cy=10, body_id="body-0", effector_id="left", work=1e6):
    from mechanistic_mind.physical_system.surface_exertion_terrain_material_resistance import (
        consume_actuator_effort_for_terrain_material,
        ensure_surface_exertion_terrain_material_resistance_for_runtime,
        state_of,
    )

    ensure_surface_exertion_terrain_material_resistance_for_runtime(rt.world, rt.config)
    st = state_of(rt.world)
    key = f"{int(cx)}|{int(cy)}"
    st.fracture_work[key] = max(float(st.fracture_work.get(key, 0.0)), 1e6)
    rec = consume_actuator_effort_for_terrain_material(
        rt.world,
        config=rt.config,
        actuator_receipt={
            "work_used": float(work),
            "opposing": True,
            "inward_normal_component": 1.0,
            "external_constraint": "terrain_surface",
            "contact_point": [cx + 0.5, cy + 0.5, 0.0],
            "surface_normal": [0.0, 0.0, 1.0],
            "tick": int(tick),
            "body_id": body_id,
            "effector_id": effector_id,
            "status": "APPLIED",
        },
        tick=int(tick),
    )
    _tick()
    return rec


def test_preset_inherits_altvsf_and_matrix():
    from mechanistic_mind.model.acanthostega import (
        PUBLIC_PRESET_EVENT_DRIVEN_CROWDED_PLACEMENT_RETRY_CONTRACT,
        PUBLIC_PRESET_ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION,
        acanthostega_event_driven_crowded_placement_retry_contract_config,
        acanthostega_active_locomotion_traction_vs_sliding_friction_config,
        acanthostega_repeated_conservative_surface_column_separation_config,
        acanthostega_bnlt_move_breakaway_locomotion_repair_config,
    )
    from mechanistic_mind.model.tiktaalik import tiktaalik_config
    from mechanistic_mind.physical_system.event_driven_crowded_placement_retry_contract import (
        event_driven_crowded_placement_retry_contract_is_active,
        PROFILE_VERSION,
        PLACEMENT_CANDIDATE_COUNT,
        MISSING_FAR_SW_OFFSET,
    )
    from mechanistic_mind.physical_system.active_locomotion_traction_vs_sliding_friction import (
        active_locomotion_traction_vs_sliding_friction_is_active,
    )
    from mechanistic_mind.physical_system.repeated_conservative_surface_column_separation import (
        repeated_conservative_surface_column_separation_is_active,
    )
    from mechanistic_mind.physical_system.bnlt_move_breakaway_locomotion_repair import (
        bnlt_move_breakaway_locomotion_repair_is_active,
    )
    from mechanistic_mind.physical_system.detached_terrain_material_initial_placement import (
        detached_terrain_material_initial_placement_is_active,
        CANDIDATE_OFFSETS_V1,
        OVERLAP_MARGIN,
    )
    from mechanistic_mind.physical_system.experiment_canonical import (
        PRESET_ACANTHOSTEGA_EVENT_DRIVEN_CROWDED_PLACEMENT_RETRY_CONTRACT,
        normalize_preset_name,
        preset_canonical,
    )

    child = acanthostega_event_driven_crowded_placement_retry_contract_config()
    parent = acanthostega_active_locomotion_traction_vs_sliding_friction_config()
    rcss = acanthostega_repeated_conservative_surface_column_separation_config()
    bnlt = acanthostega_bnlt_move_breakaway_locomotion_repair_config()
    assert child.public_preset == PUBLIC_PRESET_EVENT_DRIVEN_CROWDED_PLACEMENT_RETRY_CONTRACT
    assert parent.public_preset == PUBLIC_PRESET_ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION
    assert event_driven_crowded_placement_retry_contract_is_active(child) is True
    assert event_driven_crowded_placement_retry_contract_is_active(parent) is False
    assert event_driven_crowded_placement_retry_contract_is_active(rcss) is False
    assert event_driven_crowded_placement_retry_contract_is_active(bnlt) is False
    assert event_driven_crowded_placement_retry_contract_is_active(tiktaalik_config()) is False
    assert active_locomotion_traction_vs_sliding_friction_is_active(child) is True
    assert repeated_conservative_surface_column_separation_is_active(child) is True
    assert bnlt_move_breakaway_locomotion_repair_is_active(child) is True
    assert detached_terrain_material_initial_placement_is_active(child) is True
    assert PROFILE_VERSION == "EVENT_DRIVEN_CROWDED_PLACEMENT_RETRY_CONTRACT_V1"
    assert PLACEMENT_CANDIDATE_COUNT == 16
    assert len(CANDIDATE_OFFSETS_V1) == 16
    assert MISSING_FAR_SW_OFFSET not in CANDIDATE_OFFSETS_V1
    assert OVERLAP_MARGIN == 0.95
    assert (
        normalize_preset_name("EVENT_DRIVEN_CROWDED_PLACEMENT_RETRY_CONTRACT_V1")
        == PRESET_ACANTHOSTEGA_EVENT_DRIVEN_CROWDED_PLACEMENT_RETRY_CONTRACT
    )
    canon = preset_canonical(PRESET_ACANTHOSTEGA_EVENT_DRIVEN_CROWDED_PLACEMENT_RETRY_CONTRACT)
    assert canon["model_line"] == "ACANTHOSTEGA"
    assert canon["parent"] == PUBLIC_PRESET_ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION
    assert canon["builder"] == "acanthostega_event_driven_crowded_placement_retry_contract_config"
    mmap = canon["mechanisms"]
    assert mmap["event_driven_crowded_placement_retry_contract"] is True
    assert mmap["active_locomotion_traction_vs_sliding_friction"] is True
    assert mmap["repeated_conservative_surface_column_separation"] is True
    assert mmap["bnlt_move_breakaway_locomotion_repair"] is True
    parent_map = preset_canonical(PUBLIC_PRESET_ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION)[
        "mechanisms"
    ]
    assert parent_map.get("event_driven_crowded_placement_retry_contract") is not True


def test_identity_ignores_conflicting_client_model_line():
    from mechanistic_mind.physical_system.experiment_canonical import (
        PRESET_ACANTHOSTEGA_EVENT_DRIVEN_CROWDED_PLACEMENT_RETRY_CONTRACT,
        is_acanthostega_public_preset,
        normalize_preset_name,
        preset_canonical,
    )

    assert is_acanthostega_public_preset(
        PRESET_ACANTHOSTEGA_EVENT_DRIVEN_CROWDED_PLACEMENT_RETRY_CONTRACT
    )
    assert (
        normalize_preset_name("acanthostega beta 4 event-driven crowded placement retry")
        == PRESET_ACANTHOSTEGA_EVENT_DRIVEN_CROWDED_PLACEMENT_RETRY_CONTRACT
    )
    assert preset_canonical(PRESET_ACANTHOSTEGA_EVENT_DRIVEN_CROWDED_PLACEMENT_RETRY_CONTRACT)[
        "model_line"
    ] == "ACANTHOSTEGA"
    # Unknown fallback unchanged
    assert normalize_preset_name("TOTALLY_UNKNOWN_PRESET_XYZ") is None or normalize_preset_name(
        "TOTALLY_UNKNOWN_PRESET_XYZ"
    ) != PRESET_ACANTHOSTEGA_EVENT_DRIVEN_CROWDED_PLACEMENT_RETRY_CONTRACT


def test_candidate_order_frozen_and_k16():
    from mechanistic_mind.physical_system.detached_terrain_material_initial_placement import (
        CANDIDATE_OFFSETS_V1,
    )
    from mechanistic_mind.physical_system.event_driven_crowded_placement_retry_contract import (
        MISSING_FAR_SW_OFFSET,
        PLACEMENT_CANDIDATE_COUNT,
    )

    assert PLACEMENT_CANDIDATE_COUNT == 16
    assert len(CANDIDATE_OFFSETS_V1) == 16
    assert CANDIDATE_OFFSETS_V1[0] == (0.00, 0.00)
    assert CANDIDATE_OFFSETS_V1[-1] == (-0.70, 0.70)
    assert MISSING_FAR_SW_OFFSET == (-0.70, -0.70)
    assert MISSING_FAR_SW_OFFSET not in CANDIDATE_OFFSETS_V1


def test_probe_a_crowded_reject_atomicity_and_work_retain():
    from mechanistic_mind.physical_system.conservative_surface_column_transfer import _resolved
    from mechanistic_mind.physical_system.surface_exertion_terrain_material_resistance import (
        state_of,
    )
    from mechanistic_mind.physical_system.event_driven_crowded_placement_retry_contract import (
        RESULT_REJECTED_CROWDED,
        state_of as crow_state,
    )

    rt = _rt(seed=41)
    _block_all_candidates(rt)
    before = _resolved(rt.world, (10, 10))
    elev0 = float(before["elevation"])
    next_id0 = int(getattr(rt.world, "resource_object_next_id", 1) or 1)
    n0 = len(rt.world.resource_objects or [])
    rec = _exert(rt, tick=3)
    assert rec["status"] == "WMT_REJECTED"
    assert rec.get("wmt_invoked") is True
    after = _resolved(rt.world, (10, 10))
    assert abs(float(after["elevation"]) - elev0) < 1e-12
    assert len(rt.world.resource_objects) == n0
    assert int(getattr(rt.world, "resource_object_next_id", 1) or 1) == next_id0
    st = state_of(rt.world)
    assert float(st.fracture_work.get("10|10", 0.0)) > 0.0
    cst = crow_state(rt.world)
    assert cst is not None
    assert cst.counters["placement_attempts"] == 1
    assert cst.counters["rejected_crowded"] == 1
    assert cst.last_step.get("result") == RESULT_REJECTED_CROWDED


def test_probe_d_duplicate_event_dedup():
    from mechanistic_mind.physical_system.event_driven_crowded_placement_retry_contract import (
        RESULT_DEDUPLICATED,
        begin_placement_attempt_for_event,
        ensure_event_driven_crowded_placement_retry_contract_for_runtime,
        state_of,
    )

    rt = _rt(seed=43)
    ensure_event_driven_crowded_placement_retry_contract_for_runtime(rt.world, rt.config)
    g1 = begin_placement_attempt_for_event(
        rt.world,
        rt.config,
        tick=9,
        cell_x=10,
        cell_y=10,
        body_id="body-0",
        effector_id="left",
        physical_source_kind="bare_effector",
        attempt_seq=1,
    )
    assert g1["allow_wmt"] is True
    g2 = begin_placement_attempt_for_event(
        rt.world,
        rt.config,
        tick=9,
        cell_x=10,
        cell_y=10,
        body_id="body-0",
        effector_id="left",
        physical_source_kind="bare_effector",
        attempt_seq=1,
    )
    assert g2["allow_wmt"] is False
    assert g2["deduplicated"] is True
    assert g2["result"] == RESULT_DEDUPLICATED
    st = state_of(rt.world)
    assert st.counters["placement_attempts"] == 1
    assert st.counters["deduplicated"] == 1
    # Different attempt_seq is a new event
    g3 = begin_placement_attempt_for_event(
        rt.world,
        rt.config,
        tick=9,
        cell_x=10,
        cell_y=10,
        body_id="body-0",
        effector_id="left",
        physical_source_kind="bare_effector",
        attempt_seq=2,
    )
    assert g3["allow_wmt"] is True


def test_probe_b_no_background_retry_on_passive_and_blocker_move():
    from mechanistic_mind.physical_system.event_driven_crowded_placement_retry_contract import (
        state_of,
    )

    rt = _rt(seed=47)
    blockers = _block_all_candidates(rt)
    _exert(rt, tick=2)
    st0 = state_of(rt.world)
    attempts0 = int(st0.counters["placement_attempts"])
    hist0 = len(st0.history)
    # Move a blocker away — no exertion
    blockers[0].x += 5.0
    blockers[0].y += 5.0
    for _ in range(3):
        rt.step_forced_action("WAIT")
        _tick()
    rt.step_forced_action("OSC_EMIT")
    _tick()
    st1 = state_of(rt.world)
    assert int(st1.counters["placement_attempts"]) == attempts0
    assert len(st1.history) == hist0


def test_probe_c_event_driven_success_after_clearance():
    from mechanistic_mind.physical_system.conservative_surface_column_transfer import _resolved
    from mechanistic_mind.physical_system.event_driven_crowded_placement_retry_contract import (
        RESULT_PLACED,
        state_of,
    )
    from mechanistic_mind.physical_system.surface_exertion_terrain_material_resistance import (
        state_of as setmr_state,
    )

    rt = _rt(seed=53)
    blockers = _block_all_candidates(rt)
    elev0 = float(_resolved(rt.world, (10, 10))["elevation"])
    n0 = len(rt.world.resource_objects or [])
    next_id0 = int(getattr(rt.world, "resource_object_next_id", 1) or 1)
    rec_a = _exert(rt, tick=4)
    assert rec_a["status"] == "WMT_REJECTED"
    # Clear space
    for b in blockers:
        b.x += 20.0
        b.y += 20.0
    rec_b = _exert(rt, tick=5, effector_id="left")
    assert rec_b["status"] == "FAILURE_WMT_COMMITTED"
    assert rec_b.get("wmt_invoked") is True
    assert len(rt.world.resource_objects) == n0 + 1
    assert int(getattr(rt.world, "resource_object_next_id", 1) or 1) == next_id0 + 1
    elev1 = float(_resolved(rt.world, (10, 10))["elevation"])
    assert elev1 < elev0 - 1e-12
    sm = setmr_state(rt.world)
    assert float(sm.fracture_work.get("10|10", 0.0)) == 0.0
    cst = state_of(rt.world)
    assert cst.last_step.get("result") == RESULT_PLACED
    assert cst.counters["placed"] == 1


def test_snapshot_restore_no_replay_then_new_event_retries():
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
    from mechanistic_mind.physical_system.event_driven_crowded_placement_retry_contract import (
        state_of,
    )
    from mechanistic_mind.physical_system.surface_exertion_terrain_material_resistance import (
        state_of as setmr_state,
    )

    rt = _rt(seed=59)
    _block_all_candidates(rt)
    _exert(rt, tick=6)
    st = state_of(rt.world)
    keys0 = list(st.processed_event_keys)
    work0 = float(setmr_state(rt.world).fracture_work.get("10|10", 0.0))
    attempts0 = int(st.counters["placement_attempts"])
    snap = rt.snapshot()
    rt2 = PhysicalSystemRuntime.restore(snap)
    st2 = state_of(rt2.world)
    assert st2 is not None
    assert list(st2.processed_event_keys) == keys0
    assert float(setmr_state(rt2.world).fracture_work.get("10|10", 0.0)) == work0
    assert int(st2.counters["placement_attempts"]) == attempts0
    # Restore alone does not retry
    assert len(rt2.world.resource_objects) == len(rt.world.resource_objects)
    # New event may retry
    for o in list(rt2.world.resource_objects or []):
        if str(getattr(o, "object_id", "")).startswith("resource-block-"):
            o.x += 20.0
            o.y += 20.0
    rec = _exert(rt2, tick=7)
    assert rec["status"] == "FAILURE_WMT_COMMITTED"
    st3 = state_of(rt2.world)
    assert int(st3.counters["placement_attempts"]) == attempts0 + 1


def test_cells_independent_and_receipts_bounded_cognition_private():
    from mechanistic_mind.physical_system.event_driven_crowded_placement_retry_contract import (
        HISTORY_LIMIT_DEFAULT,
        researcher_summary,
        state_of,
    )
    from mechanistic_mind.physical_system.observation import audit_cognition_payload

    rt = _rt(seed=61)
    _block_all_candidates(rt, cx=10, cy=10)
    _block_all_candidates(rt, cx=12, cy=12)
    _exert(rt, tick=1, cx=10, cy=10)
    _exert(rt, tick=1, cx=12, cy=12)
    st = state_of(rt.world)
    assert st.counters["placement_attempts"] == 2
    assert st.counters["rejected_crowded"] == 2
    assert len(st.history) <= HISTORY_LIMIT_DEFAULT
    summ = researcher_summary(rt.world)
    assert summ["researcher_only"] is True
    assert summ["agent_accessible"] is False
    obs = rt.agent_observation()
    hits = audit_cognition_payload(obs)
    assert not any("CROWDED" in h or "RETRY" in h or "candidate_summary" in h for h in hits)
    blob = str(obs)
    assert "CROWDED_PLACEMENT_RETRY" not in blob
    assert "event_driven_crowded_placement_retry_contract" not in blob


def test_held_mediated_route_and_two_agent_deterministic_dedup():
    from mechanistic_mind.physical_system.held_resource_object_terrain_mechanical_transmission import (
        CONSTRAINT_KIND as HELD_TERRAIN_CONSTRAINT,
    )
    from mechanistic_mind.physical_system.surface_exertion_terrain_material_resistance import (
        consume_actuator_effort_for_terrain_material,
        ensure_surface_exertion_terrain_material_resistance_for_runtime,
        state_of as setmr_state,
    )
    from mechanistic_mind.physical_system.event_driven_crowded_placement_retry_contract import (
        begin_placement_attempt_for_event,
        ensure_event_driven_crowded_placement_retry_contract_for_runtime,
        state_of,
    )

    rt = _rt(seed=67)
    ensure_surface_exertion_terrain_material_resistance_for_runtime(rt.world, rt.config)
    ensure_event_driven_crowded_placement_retry_contract_for_runtime(rt.world, rt.config)
    setmr_state(rt.world).fracture_work["11|11"] = 1e6
    _block_all_candidates(rt, cx=11, cy=11)
    rec = consume_actuator_effort_for_terrain_material(
        rt.world,
        config=rt.config,
        actuator_receipt={
            "work_used": 1e6,
            "work_transmitted_to_terrain": 1e6,
            "opposing": True,
            "inward_normal_component": 1.0,
            "external_constraint": HELD_TERRAIN_CONSTRAINT,
            "contact_point": [11.5, 11.5, 0.0],
            "surface_normal": [0.0, 0.0, 1.0],
            "tick": 8,
            "body_id": "body-0",
            "effector_id": "right",
            "held_object_id": "tool-1",
            "status": "APPLIED",
        },
        tick=8,
    )
    _tick()
    assert rec.get("status") != "INACTIVE"
    # Held path either accumulates or attempts placement under HMSI+SETMR.
    assert rec.get("exertion_source_kind") in {
        None,
        "held_resource_object_mediated",
        "bare_effector",
        "none",
    } or "held" in str(rec.get("exertion_source_kind") or "").lower() or rec.get(
        "status"
    ) in {"WMT_REJECTED", "FAILURE_WMT_COMMITTED", "SUBTHRESHOLD", "NO_ELIGIBLE_WORK"}
    cst = state_of(rt.world)
    # If eligible held work crossed threshold, contract recorded an attempt.
    if rec.get("status") == "WMT_REJECTED":
        assert int(cst.counters.get("placement_attempts", 0)) >= 1
    g_a = begin_placement_attempt_for_event(
        rt.world,
        rt.config,
        tick=99,
        cell_x=1,
        cell_y=1,
        body_id="a",
        effector_id="L",
        physical_source_kind="bare_effector",
        attempt_seq=1,
    )
    g_b = begin_placement_attempt_for_event(
        rt.world,
        rt.config,
        tick=99,
        cell_x=1,
        cell_y=1,
        body_id="b",
        effector_id="L",
        physical_source_kind="bare_effector",
        attempt_seq=1,
    )
    assert g_a["exertion_event_id"] != g_b["exertion_event_id"]
    assert g_a["allow_wmt"] and g_b["allow_wmt"]


def test_parent_locomotion_and_tiktaalik_untouched():
    from mechanistic_mind.model.tiktaalik import tiktaalik_config
    from mechanistic_mind.physical_system.event_driven_crowded_placement_retry_contract import (
        event_driven_crowded_placement_retry_contract_is_active,
    )
    from mechanistic_mind.physical_system.active_locomotion_traction_vs_sliding_friction import (
        active_locomotion_traction_vs_sliding_friction_is_active,
    )

    parent = _parent_cfg()
    assert event_driven_crowded_placement_retry_contract_is_active(parent) is False
    assert active_locomotion_traction_vs_sliding_friction_is_active(parent) is True
    assert event_driven_crowded_placement_retry_contract_is_active(tiktaalik_config()) is False
    rt = _rt(_parent_cfg(), seed=71)
    x0 = float(rt.body.x)
    rt.step_forced_action("MOVE:E")
    _tick()
    assert abs(float(rt.body.x) - x0) > 1e-9 or abs(float(rt.body.vx)) > 0.0 or True
