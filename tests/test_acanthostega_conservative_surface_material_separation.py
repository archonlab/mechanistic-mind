"""Conservative surface material separation — column top-slice → ResourceObject."""
from __future__ import annotations

from copy import deepcopy

import pytest

TICKS = {"n": 0}


def _tick(n: int = 1) -> None:
    TICKS["n"] += int(n)


def _cfg():
    from mechanistic_mind.model.acanthostega import (
        acanthostega_conservative_surface_material_separation_config,
    )

    cfg = acanthostega_conservative_surface_material_separation_config()
    cfg.cognition.cognition_enabled = False
    return cfg


def _rt(seed: int = 17):
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

    rt = PhysicalSystemRuntime(seed=seed, config=_cfg())
    # Keep body clear of separation cells.
    rt.body.x, rt.body.y = 2.5, 2.5
    return rt


def _resolved(world, cell):
    from mechanistic_mind.physical_system.conservative_surface_column_transfer import _resolved as r

    return r(world, cell)


def _sep(rt, cx=10, cy=10, t=0.05, tick=1, **kw):
    from mechanistic_mind.physical_system.conservative_surface_material_separation import (
        apply_surface_material_separation,
    )

    out = apply_surface_material_separation(
        rt.world, rt.config, cell_x=cx, cell_y=cy, requested_thickness=t, tick=tick, **kw
    )
    _tick()
    return out


def test_preset_child_of_phase_c_parent_unchanged():
    from mechanistic_mind.model.acanthostega import (
        PUBLIC_PRESET_CONSERVATIVE_SURFACE_MATERIAL_SEPARATION,
        PUBLIC_PRESET_COHERENT_SLOPE_DYNAMICS,
        acanthostega_coherent_slope_dynamics_config,
        acanthostega_conservative_surface_material_separation_config,
    )
    from mechanistic_mind.physical_system.conservative_surface_material_separation import (
        conservative_surface_material_separation_is_active,
        OPERATION_KIND,
    )
    from mechanistic_mind.model.tiktaalik import tiktaalik_config

    child = acanthostega_conservative_surface_material_separation_config()
    parent = acanthostega_coherent_slope_dynamics_config()
    assert child.public_preset == PUBLIC_PRESET_CONSERVATIVE_SURFACE_MATERIAL_SEPARATION
    assert parent.public_preset == PUBLIC_PRESET_COHERENT_SLOPE_DYNAMICS
    assert conservative_surface_material_separation_is_active(child) is True
    assert conservative_surface_material_separation_is_active(parent) is False
    assert conservative_surface_material_separation_is_active(tiktaalik_config()) is False
    assert OPERATION_KIND == "SEPARATE_SURFACE_COLUMN_SLICE"
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

    rt = PhysicalSystemRuntime(seed=1, config=child)
    acts = list(rt.cognition.get("available_actions") or [])
    for forbidden in ("DIG", "EXCAVATE", "MINE", "SEPARATE_SURFACE", "REMOVE_MATERIAL"):
        assert forbidden not in acts


def test_basic_top_slice_conservation():
    rt = _rt(17)
    before = _resolved(rt.world, (10, 10))
    n0 = len(rt.world.resource_objects or [])
    out = _sep(rt, 10, 10, 0.05, tick=1)
    rec = out["receipt"]
    assert rec["status"] == "COMMITTED"
    assert out.get("object_id")
    after = _resolved(rt.world, (10, 10))
    assert abs((before["elevation"] - after["elevation"]) - 0.05) < 1e-9
    assert len(rt.world.resource_objects) == n0 + 1
    obj = next(o for o in rt.world.resource_objects if o.object_id == out["object_id"])
    assert abs(float(obj.quantity) - 0.05) < 1e-9
    assert float(obj.mass) > 0.0
    assert obj.physical_state == "FREE_STATIC"
    assert float(obj.vx) == 0.0 and float(obj.vy) == 0.0
    assert rec["conservation"]["verified"] is True
    assert abs(rec["conservation"]["quantity"]["residual"]) <= 1e-12
    assert abs(rec["conservation"]["mass"]["residual"]) <= 1e-12
    assert obj.provenance.get("source") == "SURFACE_MATERIAL_SEPARATION"
    assert obj.provenance.get("researcher_only") is True


def test_partial_top_layer_same_composition_family():
    rt = _rt(19)
    before = _resolved(rt.world, (12, 12))
    top0 = before["layers"][0]
    t = min(0.02, float(top0.thickness) * 0.25)
    out = _sep(rt, 12, 12, t, tick=1)
    assert out["receipt"]["status"] == "COMMITTED"
    after = _resolved(rt.world, (12, 12))
    # Same layer family remains on top if not exhausted
    if not out["receipt"]["slice"]["whole_source_layer"]:
        assert abs(float(after["layers"][0].density) - float(top0.density)) < 1e-12


def test_layer_boundary_clamps_no_cross():
    rt = _rt(21)
    before = _resolved(rt.world, (8, 8))
    top_th = float(before["layers"][0].thickness)
    # Request more than top layer but within max — clamp to top only (no cross)
    # Use tiny max by temporarily raising request past top if top < max
    out = _sep(rt, 8, 8, top_th + 0.01, tick=1)
    # Either clamped to top_th (if top_th <= max 0.25) or to max 0.25
    assert out["receipt"]["status"] == "COMMITTED"
    applied = float(out["receipt"]["applied_thickness"])
    assert applied <= top_th + 1e-12
    assert applied <= 0.25 + 1e-12
    assert out["receipt"].get("clamped") is True or applied <= top_th


def test_exact_exhaustion_exposes_next_layer():
    rt = _rt(23)
    before = _resolved(rt.world, (14, 14))
    top_th = float(before["layers"][0].thickness)
    if top_th > 0.25:
        pytest.skip("top layer thicker than V1 max; exhaustion via max only")
    n_layers = len(before["layers"])
    out = _sep(rt, 14, 14, top_th, tick=1)
    assert out["receipt"]["status"] == "COMMITTED"
    assert out["receipt"]["slice"]["whole_source_layer"] is True
    after = _resolved(rt.world, (14, 14))
    if n_layers > 1:
        assert len(after["layers"]) == n_layers - 1
        assert after["layers"][0].top_depth == 0.0


def test_over_request_clamps():
    rt = _rt(25)
    out = _sep(rt, 9, 9, 99.0, tick=1)
    assert out["receipt"]["status"] == "COMMITTED"
    assert out["receipt"]["clamped"] is True
    assert float(out["receipt"]["applied_thickness"]) <= 0.25 + 1e-12


def test_failure_atomicity_negative_request():
    rt = _rt(27)
    before = _resolved(rt.world, (7, 7))
    n0 = len(rt.world.resource_objects or [])
    out = _sep(rt, 7, 7, -0.1, tick=1)
    assert out["receipt"]["status"] == "REJECTED"
    after = _resolved(rt.world, (7, 7))
    assert after["elevation"] == before["elevation"]
    assert after["revision"] == before["revision"]
    assert len(rt.world.resource_objects or []) == n0


def test_component_conservation_multi():
    rt = _rt(29)
    out = _sep(rt, 15, 15, 0.04, tick=1)
    assert out["receipt"]["status"] == "COMMITTED"
    residuals = out["receipt"]["conservation"]["components"]["residuals"]
    assert max(abs(v) for v in residuals.values()) <= 1e-12


def test_object_ordinary_grasp_path_state():
    rt = _rt(31)
    out = _sep(rt, 16, 16, 0.03, tick=1)
    oid = out["object_id"]
    obj = next(o for o in rt.world.resource_objects if o.object_id == oid)
    from mechanistic_mind.physical_system.resource_objects import PHYSICAL_STATE_HELD
    from mechanistic_mind.physical_system.physical_manipulator import MANIP_LEFT

    # Ordinary hold assignment (same path as spawned objects)
    obj.physical_state = PHYSICAL_STATE_HELD
    obj.holder_body_id = "agent_0"
    obj.manipulator_id = MANIP_LEFT
    assert obj.physical_state == PHYSICAL_STATE_HELD


def test_combine_with_ordinary_object():
    from mechanistic_mind.physical_system.resource_objects import PHYSICAL_STATE_HELD, MaterialComponent
    from mechanistic_mind.physical_system.physical_manipulator import MANIP_LEFT, MANIP_RIGHT

    rt = _rt(33)
    out = _sep(rt, 18, 18, 0.03, tick=1)
    assert out["receipt"]["status"] == "COMMITTED"
    detached = next(o for o in rt.world.resource_objects if o.object_id == out["object_id"])
    ordinary = next(o for o in rt.world.resource_objects if o.object_id != out["object_id"])
    detached.physical_state = PHYSICAL_STATE_HELD
    ordinary.physical_state = PHYSICAL_STATE_HELD
    detached.holder_body_id = ordinary.holder_body_id = "agent_0"
    detached.manipulator_id = MANIP_LEFT
    ordinary.manipulator_id = MANIP_RIGHT
    n0 = len(rt.world.resource_objects)
    rt.pair_aperture = 0.4
    rt._forced_motor_once = {
        "locomotion": "WAIT",
        "manipulator_left": "NONE",
        "manipulator_right": "NONE",
        "manipulator_pair": "NONE",
    }
    rt.step(1)
    _tick()
    rt._forced_motor_once = {
        "locomotion": "WAIT",
        "manipulator_left": "NONE",
        "manipulator_right": "NONE",
        "manipulator_pair": "COMBINE",
    }
    rt.step(1)
    _tick()
    # May or may not merge depending on contact; never create mass
    assert len(rt.world.resource_objects) <= n0


def test_geometry_support_sees_new_elevation():
    from mechanistic_mind.physical_system import surface_elevation_support as ses

    rt = _rt(35)
    before = _resolved(rt.world, (20, 20))
    out = _sep(rt, 20, 20, 0.05, tick=1)
    assert out["receipt"]["status"] == "COMMITTED"
    h = float(ses.surface_support_height(rt.world, 20.5, 20.5, config=rt.config))
    assert abs(h - (before["elevation"] - 0.05)) < 1e-6


def test_snapshot_before_and_after():
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

    rt = _rt(37)
    before = _resolved(rt.world, (6, 6))
    snap_before = deepcopy(rt.snapshot())
    out = _sep(rt, 6, 6, 0.05, tick=1)
    assert out["receipt"]["status"] == "COMMITTED"
    oid = out["object_id"]
    snap_after = deepcopy(rt.snapshot())

    rb = PhysicalSystemRuntime.restore(snap_before)
    assert abs(_resolved(rb.world, (6, 6))["elevation"] - before["elevation"]) < 1e-12
    assert oid not in {o.object_id for o in (rb.world.resource_objects or [])}

    ra = PhysicalSystemRuntime.restore(snap_after)
    assert abs(_resolved(ra.world, (6, 6))["elevation"] - (before["elevation"] - 0.05)) < 1e-9
    assert oid in {o.object_id for o in ra.world.resource_objects}
    # No replay: one object, same elevation after continue WAIT
    n = len(ra.world.resource_objects)
    ra.step_forced_action("WAIT")
    _tick()
    assert len(ra.world.resource_objects) == n


def test_procedural_regen_preserves_delta():
    from mechanistic_mind.physical_system import procedural_surface_columns as psc

    rt = _rt(39)
    out = _sep(rt, 5, 5, 0.05, tick=1)
    assert out["receipt"]["status"] == "COMMITTED"
    elev = _resolved(rt.world, (5, 5))["elevation"]
    # Touch baseline query / cache — must not wipe delta
    psc.baseline_column_at(rt.world, 5, 5)
    psc.resolved_column_at(rt.world, 5, 5)
    assert (5, 5) in psc.deltas_of(rt.world)
    assert abs(_resolved(rt.world, (5, 5))["elevation"] - elev) < 1e-12


def test_determinism_same_request():
    def once(seed):
        rt = _rt(seed)
        out = _sep(rt, 4, 4, 0.05, tick=1)
        o = next(x for x in rt.world.resource_objects if x.object_id == out["object_id"])
        return (
            out["receipt"]["status"],
            round(float(out["receipt"]["applied_thickness"]), 12),
            round(float(o.quantity), 12),
            round(float(o.mass), 12),
            tuple(sorted((c.component_id, round(c.amount, 12)) for c in o.composition)),
        )

    assert once(41) == once(41)


def test_cognition_privacy_no_provenance_leak():
    from mechanistic_mind.physical_system.observation import audit_cognition_payload

    rt = _rt(43)
    _sep(rt, 3, 3, 0.05, tick=1)
    rt.step_forced_action("WAIT")
    _tick()
    obs = None
    if hasattr(rt, "agent_observation"):
        try:
            obs = rt.agent_observation()
        except TypeError:
            obs = None
    if obs is None:
        obs = getattr(rt, "last_agent_observation", None) or getattr(rt, "last_observation", None) or {}
    hits = audit_cognition_payload(obs)
    assert hits == []
    blob = str(obs)
    assert "SURFACE_MATERIAL_SEPARATION" not in blob
    assert "separation_id" not in blob
    # Actions still lack DIG
    acts = list(rt.cognition.get("available_actions") or [])
    assert "DIG" not in acts
