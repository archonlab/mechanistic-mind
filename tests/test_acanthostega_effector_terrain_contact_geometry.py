"""Effector ↔ authoritative terrain contact geometry — deterministic fixtures."""
from __future__ import annotations

from copy import deepcopy

import pytest

TICKS = {"n": 0}


def _tick(n: int = 1) -> None:
    TICKS["n"] += int(n)


def _cfg():
    from mechanistic_mind.model.acanthostega import (
        acanthostega_effector_terrain_contact_geometry_config,
    )

    cfg = acanthostega_effector_terrain_contact_geometry_config()
    cfg.cognition.cognition_enabled = False
    return cfg


def _rt(seed: int = 17):
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

    return PhysicalSystemRuntime(seed=seed, config=_cfg())


def _dims(world):
    t = world.T
    return int(t.shape[1]), int(t.shape[0])


def _holders(rt):
    from mechanistic_mind.physical_system.spatial_contents import body_refs_for_runtime

    return [
        {"body_id": bid, "body": b, "config": rt.config, "runtime": rt}
        for bid, b in body_refs_for_runtime(rt)
    ]


def _detect(rt, tick: int):
    from mechanistic_mind.physical_system.effector_terrain_contact_geometry import (
        detect_effector_terrain_contacts,
    )

    step = detect_effector_terrain_contacts(
        rt.world, _holders(rt), tick=tick, config=rt.config
    )
    _tick()
    return step


def _lower_to_touch(rt, manipulator_id: str = "LEFT", *, eps: float = 0.0):
    """Set body.z so effector centre_z exactly touches surface under that effector."""
    from mechanistic_mind.physical_system.effector_terrain_contact_geometry import (
        effector_world_pose,
        sample_terrain_at,
    )
    from mechanistic_mind.physical_system.flat_ground_gravity import vertical_half_extent_of

    w, h = _dims(rt.world)
    ex, ey, _ez = effector_world_pose(
        rt.body,
        width=w,
        height=h,
        config=rt.config,
        manipulator_id=manipulator_id,
        runtime=rt,
    )
    terrain = sample_terrain_at(rt.world, ex, ey, config=rt.config)
    half = float(vertical_half_extent_of(rt.body, kind="body", config=rt.config))
    # centre_z = body.z + half = height + eps → body.z = height - half + eps
    rt.body.z = float(terrain["height"]) - half + float(eps)
    rt.body.vz = 0.0
    rt.body.grounded = False
    return ex, ey, float(terrain["height"])


def test_preset_child_of_separation_parent_unchanged():
    from mechanistic_mind.model.acanthostega import (
        PUBLIC_PRESET_CONSERVATIVE_SURFACE_MATERIAL_SEPARATION,
        PUBLIC_PRESET_EFFECTOR_TERRAIN_CONTACT_GEOMETRY,
        PUBLIC_PRESET_COHERENT_SLOPE_DYNAMICS,
        acanthostega_coherent_slope_dynamics_config,
        acanthostega_conservative_surface_material_separation_config,
        acanthostega_effector_terrain_contact_geometry_config,
    )
    from mechanistic_mind.physical_system.effector_terrain_contact_geometry import (
        effector_terrain_contact_geometry_is_active,
    )
    from mechanistic_mind.physical_system.conservative_surface_material_separation import (
        conservative_surface_material_separation_is_active,
    )
    from mechanistic_mind.model.tiktaalik import tiktaalik_config

    child = acanthostega_effector_terrain_contact_geometry_config()
    parent = acanthostega_conservative_surface_material_separation_config()
    phase_c = acanthostega_coherent_slope_dynamics_config()
    assert child.public_preset == PUBLIC_PRESET_EFFECTOR_TERRAIN_CONTACT_GEOMETRY
    assert parent.public_preset == PUBLIC_PRESET_CONSERVATIVE_SURFACE_MATERIAL_SEPARATION
    assert phase_c.public_preset == PUBLIC_PRESET_COHERENT_SLOPE_DYNAMICS
    assert effector_terrain_contact_geometry_is_active(child) is True
    assert effector_terrain_contact_geometry_is_active(parent) is False
    assert effector_terrain_contact_geometry_is_active(phase_c) is False
    assert effector_terrain_contact_geometry_is_active(tiktaalik_config()) is False
    assert conservative_surface_material_separation_is_active(child) is True
    acts = list(
        __import__(
            "mechanistic_mind.physical_system.runtime", fromlist=["PhysicalSystemRuntime"]
        ).PhysicalSystemRuntime(seed=1, config=child).cognition.get("available_actions")
        or []
    )
    for forbidden in ("DIG", "EXCAVATE", "TOUCH_GROUND", "MINE", "LOWER_HAND"):
        assert forbidden not in acts


def test_no_contact_ordinary_wait_grounded():
    rt = _rt(17)
    # Leave grounded support as initialized.
    step = _detect(rt, tick=1)
    assert step["begin"] == 0
    assert step["persist"] == 0
    assert step["end"] == 0
    assert step["active_episodes"] == 0


def test_exact_touch_begin_persist_end():
    from mechanistic_mind.physical_system.effector_terrain_contact_geometry import (
        PHASE_BEGIN,
        PHASE_END,
        PHASE_PERSIST,
        state_of,
    )

    rt = _rt(19)
    _lower_to_touch(rt, "LEFT")
    s1 = _detect(rt, tick=1)
    assert s1["begin"] == 1
    assert s1["persist"] == 0
    r0 = s1["receipts"][0]
    assert r0["phase"] == PHASE_BEGIN
    assert r0["effector_id"] == "LEFT"
    assert r0["contact_point"] is not None
    assert r0["normal"] is not None
    assert abs(float(r0["normal"][2])) > 0.0
    assert r0["researcher_only"] is True
    assert r0["cognition_exposed"] is False
    assert r0["collision_response_applied"] is False

    s2 = _detect(rt, tick=2)
    assert s2["begin"] == 0
    assert s2["persist"] == 1
    assert s2["receipts"][0]["phase"] == PHASE_PERSIST
    assert s2["receipts"][0]["episode_id"] == r0["episode_id"]

    # Move away: raise body.
    rt.body.z += 1.0
    s3 = _detect(rt, tick=3)
    assert s3["end"] == 1
    assert s3["begin"] == 0
    assert s3["receipts"][0]["phase"] == PHASE_END
    assert s3["receipts"][0]["episode_id"] == r0["episode_id"]
    assert state_of(rt.world).active == {}


def test_swept_crossing_no_tunneling():
    from mechanistic_mind.physical_system.effector_terrain_contact_geometry import (
        DETECTION_SWEPT,
        PHASE_BEGIN,
    )

    rt = _rt(21)
    # Start clearly above.
    _lower_to_touch(rt, "LEFT", eps=0.5)
    _detect(rt, tick=1)  # establish prev pose; no contact
    # Jump to exact touch — endpoint would also catch; use intermediate miss then deep.
    # First store high pose, then drop through surface in one tick.
    rt.body.z += 0.0  # already high by eps=0.5
    # Drop deep so trajectory crosses surface between prev and current.
    _lower_to_touch(rt, "LEFT", eps=-0.05)
    s = _detect(rt, tick=2)
    left_begins = [r for r in s["receipts"] if r["phase"] == "BEGIN" and r["effector_id"] == "LEFT"]
    assert len(left_begins) == 1
    rec = left_begins[0]
    assert rec["toi"] is not None
    assert rec["contact_point"] is not None
    if rec["detection_mode"] == DETECTION_SWEPT:
        assert 0.0 <= float(rec["toi"]) <= 1.0


def test_near_miss():
    rt = _rt(23)
    _lower_to_touch(rt, "LEFT", eps=1e-3)  # just above epsilon (1e-9)
    # Raise slightly more to ensure miss
    rt.body.z += 0.01
    s = _detect(rt, tick=1)
    assert s["begin"] == 0
    assert s["active_episodes"] == 0


def test_body_motion_carries_effector():
    """Body translation changes world effector xy while body-relative offsets fixed."""
    rt = _rt(25)
    w, h = _dims(rt.world)
    # Place body so LEFT effector will sit over a cell after a shift; lower for touch after move.
    rt.body.x, rt.body.y, rt.body.theta = 8.0, 16.0, 0.0
    # Establish prev pose away from contact.
    rt.body.z = 5.0
    _detect(rt, tick=1)
    # Move body + lower into contact.
    rt.body.x = 8.5
    _lower_to_touch(rt, "LEFT")
    s = _detect(rt, tick=2)
    assert s["begin"] >= 1


def test_left_right_independent():
    rt = _rt(27)
    _lower_to_touch(rt, "LEFT")
    # Right may or may not contact depending on local height; force both.
    from mechanistic_mind.physical_system.effector_terrain_contact_geometry import (
        effector_world_pose,
        sample_terrain_at,
    )
    from mechanistic_mind.physical_system.flat_ground_gravity import vertical_half_extent_of

    w, h = _dims(rt.world)
    # Set z to the higher of the two required touch heights so both penetrate/touch.
    half = float(vertical_half_extent_of(rt.body, kind="body", config=rt.config))
    heights = []
    for mid in ("LEFT", "RIGHT"):
        ex, ey, _ = effector_world_pose(
            rt.body, width=w, height=h, config=rt.config, manipulator_id=mid, runtime=rt
        )
        heights.append(float(sample_terrain_at(rt.world, ex, ey, config=rt.config)["height"]))
    # body.z such that centre_z <= min(h) → both contact (may penetrate the lower one)
    rt.body.z = min(heights) - half
    s = _detect(rt, tick=1)
    ids = sorted(r["effector_id"] for r in s["receipts"] if r["phase"] == "BEGIN")
    assert ids == ["LEFT", "RIGHT"]
    eids = [r["episode_id"] for r in s["receipts"] if r["phase"] == "BEGIN"]
    assert len(set(eids)) == 2


def test_slope_normal_matches_csg():
    from mechanistic_mind.physical_system.continuous_surface_geometry import sample_surface_geometry
    from mechanistic_mind.physical_system.effector_terrain_contact_geometry import effector_world_pose

    rt = _rt(29)
    _lower_to_touch(rt, "LEFT")
    s = _detect(rt, tick=1)
    rec = s["receipts"][0]
    w, h = _dims(rt.world)
    ex, ey, _ = effector_world_pose(
        rt.body, width=w, height=h, config=rt.config, manipulator_id="LEFT", runtime=rt
    )
    geom = sample_surface_geometry(rt.world, ex, ey, config=rt.config)
    assert abs(float(rec["normal"][0]) - float(geom["normal_x"])) < 1e-12
    assert abs(float(rec["normal"][1]) - float(geom["normal_y"])) < 1e-12
    assert abs(float(rec["normal"][2]) - float(geom["normal_z"])) < 1e-12


def test_mutated_column_surface_authoritative():
    from mechanistic_mind.physical_system.conservative_surface_material_separation import (
        apply_surface_material_separation,
    )
    from mechanistic_mind.physical_system.effector_terrain_contact_geometry import (
        effector_world_pose,
        sample_terrain_at,
    )

    rt = _rt(31)
    w, h = _dims(rt.world)
    ex, ey, _ = effector_world_pose(
        rt.body, width=w, height=h, config=rt.config, manipulator_id="LEFT", runtime=rt
    )
    cx, cy = int(ex), int(ey)
    h0 = float(sample_terrain_at(rt.world, ex, ey, config=rt.config)["height"])
    out = apply_surface_material_separation(
        rt.world, rt.config, cell_x=cx, cell_y=cy, requested_thickness=0.05, tick=1
    )
    assert out["receipt"]["status"] == "COMMITTED"
    h1 = float(sample_terrain_at(rt.world, ex, ey, config=rt.config)["height"])
    assert h1 < h0 - 1e-9
    # Contact using new height.
    _lower_to_touch(rt, "LEFT")
    s = _detect(rt, tick=2)
    left = [r for r in s["receipts"] if r["phase"] == "BEGIN" and r["effector_id"] == "LEFT"]
    assert len(left) == 1
    assert abs(float(left[0]["surface_height"]) - h1) < 1e-9


def test_wrap_single_contact_no_duplicate():
    rt = _rt(33)
    w, h = _dims(rt.world)
    rt.body.x = float(w) - 0.1
    rt.body.y = 16.0
    rt.body.theta = 0.0
    _lower_to_touch(rt, "LEFT")
    s = _detect(rt, tick=1)
    # At most one BEGIN per effector.
    begins = [r for r in s["receipts"] if r["phase"] == "BEGIN" and r["effector_id"] == "LEFT"]
    assert len(begins) <= 1


def test_determinism():
    def once(seed):
        rt = _rt(seed)
        _lower_to_touch(rt, "LEFT")
        s1 = _detect(rt, tick=1)
        s2 = _detect(rt, tick=2)
        return deepcopy(s1), deepcopy(s2)

    a1, a2 = once(41)
    b1, b2 = once(41)
    assert a1["receipts"] == b1["receipts"]
    assert a2["receipts"] == b2["receipts"]


def test_snapshot_during_contact_no_replay_begin():
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

    rt = _rt(43)
    _lower_to_touch(rt, "LEFT")
    _detect(rt, tick=1)
    snap = rt.snapshot()
    rt2 = PhysicalSystemRuntime.restore(snap)
    from mechanistic_mind.physical_system.effector_terrain_contact_geometry import (
        detect_effector_terrain_contacts,
        state_of,
    )

    st = state_of(rt2.world)
    assert st is not None
    assert len(st.active) == 1
    step = detect_effector_terrain_contacts(
        rt2.world, _holders(rt2), tick=2, config=rt2.config
    )
    assert step["begin"] == 0
    assert step["persist"] >= 1
    assert step["end"] == 0


def test_snapshot_before_contact_clean():
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
    from mechanistic_mind.physical_system.effector_terrain_contact_geometry import (
        detect_effector_terrain_contacts,
        state_of,
    )

    rt = _rt(45)
    snap = rt.snapshot()
    rt2 = PhysicalSystemRuntime.restore(snap)
    assert state_of(rt2.world) is not None
    assert state_of(rt2.world).active == {}
    step = detect_effector_terrain_contacts(
        rt2.world, _holders(rt2), tick=1, config=rt2.config
    )
    assert step["begin"] == 0


def test_separation_researcher_still_works():
    from mechanistic_mind.physical_system.conservative_surface_material_separation import (
        apply_surface_material_separation,
    )

    rt = _rt(47)
    out = apply_surface_material_separation(
        rt.world, rt.config, cell_x=10, cell_y=10, requested_thickness=0.05, tick=1
    )
    assert out["receipt"]["status"] == "COMMITTED"
    _tick()


def test_phase_c_parent_has_no_etc():
    from mechanistic_mind.model.acanthostega import acanthostega_coherent_slope_dynamics_config
    from mechanistic_mind.physical_system.effector_terrain_contact_geometry import (
        effector_terrain_contact_geometry_is_active,
    )
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

    rt = PhysicalSystemRuntime(seed=1, config=acanthostega_coherent_slope_dynamics_config())
    assert effector_terrain_contact_geometry_is_active(rt.config) is False
    assert getattr(rt.world, "last_effector_terrain_contact_step", None) is None


def test_runtime_finish_tick_emits_receipt():
    rt = _rt(49)
    _lower_to_touch(rt, "LEFT")
    # Drive one finish_tick path (WAIT).
    rt.begin_tick()
    rt.finish_tick()
    step = getattr(rt.world, "last_effector_terrain_contact_step", None)
    assert isinstance(step, dict)
    assert step.get("begin", 0) + step.get("persist", 0) >= 1
    _tick()


def test_tiktaalik_unchanged():
    from mechanistic_mind.model.tiktaalik import tiktaalik_config
    from mechanistic_mind.physical_system.effector_terrain_contact_geometry import (
        effector_terrain_contact_geometry_is_active,
    )

    assert effector_terrain_contact_geometry_is_active(tiktaalik_config()) is False


def test_total_simulated_ticks_budget():
    assert TICKS["n"] <= 120
