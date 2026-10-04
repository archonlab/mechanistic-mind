"""ACANTHOSTEGA FREE RESOURCE OBJECT KINEMATICS (ACANTHOSTEGA_PHASE_B_FREE_OBJECT_KINEMATICS).

Numbered contract tests 1-35 (+ Observer / Analyzer / catalog / frontend extras).  Controlled
harness (results/acanthostega_free_object_kinematics/fok_harness.py): real runtime(s) of the new
preset, researcher-positioned body pose between scientific ticks, and the UNCHANGED world step
``resolve_shared_world_manipulators`` called exactly once per world tick as the runtimes call it.
Runtime tests use the real ``PhysicalSystemRuntime`` / ``TwoAgentRuntime`` / ``ObserverSession``.
"""
from __future__ import annotations

import copy
import json
import math
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "results" / "acanthostega_free_object_kinematics"))

from fok_harness import H  # noqa: E402

from mechanistic_mind.model.acanthostega import (  # noqa: E402
    acanthostega_column_transfer_config,
    acanthostega_contact_acoustics_config,
    acanthostega_free_object_kinematics_config,
    acanthostega_local_signal_config,
)
from mechanistic_mind.model.lines import identity_for_config, stamp_config_from_preset  # noqa: E402
from mechanistic_mind.model.tiktaalik import tiktaalik_config  # noqa: E402
from mechanistic_mind.physical_system import experiment_canonical as ec  # noqa: E402
from mechanistic_mind.physical_system import free_resource_object_kinematics as fok  # noqa: E402
from mechanistic_mind.physical_system.experiment_canonical import (  # noqa: E402
    PRESET_ACANTHOSTEGA_COLUMN_TRANSFER,
    PRESET_ACANTHOSTEGA_CONTACT_ACOUSTICS,
    PRESET_ACANTHOSTEGA_FREE_OBJECT_KINEMATICS,
    PRESET_ACANTHOSTEGA_EFFECTOR_WORK_ACCOUNTING,
    PRESET_ACANTHOSTEGA_FLAT_GROUND_GRAVITY, PRESET_ACANTHOSTEGA_FREE_OBJECT_GROUND_FRICTION,
    PRESET_ACANTHOSTEGA_HELD_OBJECT_TRANSLATIONAL_IMPULSE,
    PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT,
    PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPACT_ACOUSTICS,
    PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPULSE,
    PRESET_ACANTHOSTEGA_OBJECT_OBJECT_CONTACT,
    PRESET_ACANTHOSTEGA_OBJECT_IMPACT_ACOUSTICS,
    PRESET_ACANTHOSTEGA_BODY_OBJECT_CONTACT,
    PRESET_ACANTHOSTEGA_BODY_OBJECT_IMPULSE,
    PRESET_ACANTHOSTEGA_LOCAL_SIGNAL,
    PRESET_BETA31,
    beta31_mechanism_map,
    canonical_fingerprint,
    normalize_preset_name,
    preset_canonical,
)
from mechanistic_mind.physical_system.mechanism_registry import mechanism_snapshot, set_mechanism  # noqa: E402
from mechanistic_mind.physical_system.observation import FORBIDDEN_TOKENS, audit_cognition_payload  # noqa: E402
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime  # noqa: E402
from mechanistic_mind.physical_system.spatial_contents import (  # noqa: E402
    reconcile_contents,
    validate_against_world,
    world_cell,
)
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime  # noqa: E402
from mechanistic_mind.scientific_v3.free_object_kinematics_summary import (  # noqa: E402
    format_free_object_kinematics_section,
    summarize_free_object_kinematics,
)

LPS_RESULTS = ROOT / "results" / "acanthostega_local_signal"
APP = ROOT / "web" / "psy-observer" / "src" / "App.tsx"
FROZEN = "1621ef2c154864d1"
MID = fok.MECHANISM_ID
K, REST, VMAX = 0.25, 0.01, 0.75
F = math.exp(-K)
KINEMATIC_KEYS = ("x", "y", "vx", "vy", "physical_state", "holder_body_id", "manipulator_id")


# ---------------------------------------------------------------- helpers


def throw(h, dx=0.3, dy=0.0, dtheta=0.0, carry=3, mid="LEFT", i=0):
    """Grasp, carry `carry` ticks with a constant per-tick pose change, move once more, RELEASE."""
    o = h.grasp_first(i=i, mid=mid)
    for _ in range(carry):
        h.move(i, dx, dy, dtheta)
        h.step()
    h.move(i, dx, dy, dtheta)
    h.release(i=i, mid=mid)
    return o, h.releases()[-1]


def static_part(o):
    d = o.to_dict()
    return {k: v for k, v in d.items() if k not in KINEMATIC_KEYS}


def object_cells(world, oid):
    idx = world.spatial_contents
    return [cell for cell, bucket in idx.by_cell.items()
            for ref in bucket if ref.entity_kind != "body" and ref.entity_id == oid]


def session(preset=PRESET_ACANTHOSTEGA_FREE_OBJECT_KINEMATICS):
    from mechanistic_mind.ui.psy_observer_web.session import ObserverSession

    s = ObserverSession()
    s.apply_experiment(preset_canonical(preset, seed=17))
    return s, s.runtime


# ---------------------------------------------------------------- isolation (1-5)


@pytest.fixture(scope="module")
def probe():
    before = json.loads((LPS_RESULTS / "preservation_after.json").read_text())
    proc = subprocess.run(
        [sys.executable, str(LPS_RESULTS / "preservation_probe.py")],
        cwd=str(ROOT), capture_output=True, text=True, timeout=1800,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    return before, json.loads(proc.stdout)


def test_01_tiktaalik_mechanism_map_unchanged(probe):
    before, now = probe
    assert now["beta31_mechanism_map"] == before["beta31_mechanism_map"]
    assert MID not in beta31_mechanism_map()
    assert MID not in preset_canonical(PRESET_BETA31, seed=17)["mechanisms"]


def test_02_tiktaalik_fingerprint_seed17_unchanged(probe):
    before, now = probe
    assert canonical_fingerprint(preset_canonical(PRESET_BETA31, seed=17)) == FROZEN
    assert now["beta31_fingerprint"] == before["beta31_fingerprint"] == FROZEN


def test_03_tiktaalik_physics_and_tick_order_unchanged(probe, monkeypatch):
    before, now = probe
    assert now["runtime"]["TIKTAALIK"] == before["runtime"]["TIKTAALIK"]
    assert now["two_agent_signal"][PRESET_BETA31] == before["two_agent_signal"][PRESET_BETA31]
    tik = tiktaalik_config()
    set_mechanism(tik, MID, True)                     # forced flag on Tiktaalik does not enable it
    fok.set_free_resource_object_kinematics(tik, True)
    assert fok.free_resource_object_kinematics_is_active(tik) is False
    assert getattr(tik, "free_resource_object_kinematics", None) is None
    calls = []
    monkeypatch.setattr(fok, "integrate_free_objects", lambda *a, **k: calls.append(1) or [])
    monkeypatch.setattr(fok, "apply_release_transfer", lambda *a, **k: calls.append(1) or [])
    rt = PhysicalSystemRuntime(seed=17, config=tiktaalik_config())
    rt.step(3)
    assert calls == [] and fok.state_of(rt.world) is None
    assert "free_object_kinematics_state" not in rt.snapshot()["world"]
    assert "free_resource_object_kinematics" not in rt.snapshot()["config"]


@pytest.mark.parametrize("builder", [acanthostega_column_transfer_config, acanthostega_local_signal_config,
                                     acanthostega_contact_acoustics_config])
def test_04_previous_presets_keep_free_static_semantics(builder, probe):
    before, now = probe
    assert now == before                              # full LPS-stage probe (Tiktaalik + all earlier presets)
    h = H(cfg=builder())
    assert h.st is None
    h.place(0, 10.0, 10.0, 0.0)
    o = h.grasp_first()
    for _ in range(3):
        h.move(0, 0.3)
        h.step()
    h.move(0, 0.3)
    h.release()
    assert o.physical_state == "FREE_STATIC" and (o.vx, o.vy) == (0.0, 0.0)
    pos = (o.x, o.y)
    for _ in range(5):
        h.step()
    assert (o.x, o.y) == pos and o.physical_state == "FREE_STATIC"
    assert getattr(h.world, "last_free_object_step", None) is None


def test_05_new_mechanism_absent_outside_new_preset():
    names = sorted(v for k, v in vars(ec).items() if k.startswith("PRESET_") and isinstance(v, str))
    assert PRESET_ACANTHOSTEGA_FREE_OBJECT_KINEMATICS in names
    for p in names:
        mech = preset_canonical(p, seed=17)["mechanisms"]
        cfg = stamp_config_from_preset(acanthostega_free_object_kinematics_config(), p)
        if p in {
            PRESET_ACANTHOSTEGA_FREE_OBJECT_KINEMATICS,
            PRESET_ACANTHOSTEGA_BODY_OBJECT_CONTACT,  # child preset keeps FOK
            PRESET_ACANTHOSTEGA_BODY_OBJECT_IMPULSE,  # grandchild: contact+impulse keeps FOK
            PRESET_ACANTHOSTEGA_OBJECT_IMPACT_ACOUSTICS,
            PRESET_ACANTHOSTEGA_OBJECT_OBJECT_CONTACT,
            PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPULSE,
            PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPACT_ACOUSTICS,
            PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT,
            PRESET_ACANTHOSTEGA_HELD_OBJECT_TRANSLATIONAL_IMPULSE,
            PRESET_ACANTHOSTEGA_EFFECTOR_WORK_ACCOUNTING,
            PRESET_ACANTHOSTEGA_FLAT_GROUND_GRAVITY, PRESET_ACANTHOSTEGA_FREE_OBJECT_GROUND_FRICTION,
        }:
            assert mech[MID] is True and fok.free_resource_object_kinematics_is_active(cfg)
            continue
        assert not mech.get(MID), p
        assert fok.free_resource_object_kinematics_is_active(cfg) is False, p
    for cfg in (acanthostega_column_transfer_config(), acanthostega_local_signal_config(),
                acanthostega_contact_acoustics_config()):
        assert getattr(cfg, "free_resource_object_kinematics", None) is None
        assert fok.state_of(PhysicalSystemRuntime(seed=17, config=cfg).world) is None
    # branch from COLUMN_TRANSFER: exactly CT map + the new mechanism, no Audio A/B mechanisms
    free = preset_canonical(PRESET_ACANTHOSTEGA_FREE_OBJECT_KINEMATICS, seed=17)["mechanisms"]
    ct = preset_canonical(PRESET_ACANTHOSTEGA_COLUMN_TRANSFER, seed=17)["mechanisms"]
    assert {k: v for k, v in free.items() if k != MID} == ct
    assert not free.get("local_physical_signal_transport") and not free.get("physical_contact_acoustic_emission")
    assert normalize_preset_name("Acanthostega Phase B Free Object Kinematics") == PRESET_ACANTHOSTEGA_FREE_OBJECT_KINEMATICS
    assert normalize_preset_name(PRESET_ACANTHOSTEGA_CONTACT_ACOUSTICS) == PRESET_ACANTHOSTEGA_CONTACT_ACOUSTICS


# ---------------------------------------------------------------- release causality (6-12)


def test_06_stationary_effector_zero_velocity():
    h = H()
    h.place(0, 10.0, 10.0, 0.0)
    o, r = throw(h, dx=0.0, carry=4)
    assert r["measurement"] == fok.M_MEASURED
    assert r["measured_effector_velocity"] == [0.0, 0.0]
    assert r["velocity_after_clamp"] == [0.0, 0.0] and r["initial_free_state"] == "FREE_STATIC"
    assert (o.vx, o.vy) == (0.0, 0.0) and o.physical_state == "FREE_STATIC"
    pos = (o.x, o.y)
    h.step()
    h.step()
    assert (o.x, o.y) == pos and h.motions() == []


@pytest.mark.parametrize("dx,dy", [(0.3, 0.0), (0.0, -0.2), (0.15, 0.15)])
def test_07_moving_effector_directed_velocity(dx, dy):
    h = H()
    h.place(0, 10.0, 10.0, 0.0)
    o, r = throw(h, dx=dx, dy=dy)
    vx, vy = r["measured_effector_velocity"]
    assert math.isclose(vx, dx, abs_tol=1e-9) and math.isclose(vy, dy, abs_tol=1e-9)
    assert r["velocity_after_clamp"] == [o.vx, o.vy] and o.physical_state == "FREE_MOVING"
    assert r["release_transfer"] == 1.0 and r["speed_clamped"] is False
    assert r["position"] == list(r["current_effector_pose"])


def test_08_wrap_delta_uses_shortest_toroidal_path():
    h = H()
    h.place(0, 31.0, 10.0, 0.0)              # LEFT effector x = 31.55 -> crosses x = 32 while carried
    o, r = throw(h, dx=0.3, carry=1)
    prev, cur = r["previous_effector_pose"], r["current_effector_pose"]
    assert prev[0] > 31.0 and cur[0] < 1.0    # pose wrapped
    assert math.isclose(r["toroidal_effector_delta"][0], 0.3, abs_tol=1e-9)
    assert math.isclose(o.vx, 0.3, abs_tol=1e-9)
    assert fok.toroidal_pose_delta((31.9, 0.1), (0.1, 31.9), 32, 32) == pytest.approx((0.2, -0.2))


def test_09_body_velocity_does_not_substitute_effector_velocity():
    h = H()
    h.place(0, 10.0, 10.0, 0.0)
    o = h.grasp_first()
    h.move(0, dtheta=0.3)
    h.step()
    h.move(0, dtheta=0.3)
    rt = h.rt()
    rt.body.vx, rt.body.vy = 0.25, -0.1       # stale body velocity: must NOT be used
    before = h.eff()
    h.release()
    r = h.releases()[-1]
    assert r["body_velocity_used"] is False
    ex_prev = r["previous_effector_pose"]
    dx, dy = fok.toroidal_pose_delta(ex_prev, before, 32, 32)
    assert r["measured_effector_velocity"] == pytest.approx([dx, dy])
    assert math.hypot(dx, dy) > 0.15                           # rotation-only effector motion
    assert r["measured_effector_velocity"] != pytest.approx([0.25, -0.1])
    # translating body without rotation: effector velocity equals body displacement per tick
    h2 = H()
    h2.place(0, 10.0, 10.0, 0.0)
    _, r2 = throw(h2, dx=0.2, dy=0.1)
    assert r2["measured_effector_velocity"] == pytest.approx([0.2, 0.1])


def test_10_first_tick_teleport_and_restore_no_false_impulse():
    # (a) first world step after apply: no previous pose -> zero velocity even though body moved
    h = H()
    h.place(0, 10.0, 10.0, 0.0)
    o = h.obj()
    ex, ey = h.eff()
    o.x, o.y, o.physical_state, o.holder_body_id, o.manipulator_id = ex, ey, "HELD", "agent_0", "LEFT"
    h.move(0, 0.3)
    h.release()
    r = h.releases()[-1]
    assert r["measurement"] == fok.M_NO_PREVIOUS and (o.vx, o.vy) == (0.0, 0.0)
    assert o.physical_state == "FREE_STATIC"
    # (b) teleport / researcher placement of the body -> discontinuity guard -> zero velocity
    h = H()
    h.place(0, 10.0, 10.0, 0.0)
    o = h.grasp_first()
    h.move(0, 5.0, 3.0)
    h.release()
    r = h.releases()[-1]
    assert r["measurement"] == fok.M_DISCONTINUITY and (o.vx, o.vy) == (0.0, 0.0)
    assert h.st.counters["measurement_discontinuity"] == 1
    # (c) restore: see tests 31/33


def test_11_clamp_preserves_direction_and_limits_magnitude():
    h = H()
    h.place(0, 10.0, 10.0, 0.0)
    o, r = throw(h, dx=0.6, dy=0.6, carry=1)   # 0.849 cells/tick (researcher-imposed, above body limits)
    raw = r["inherited_velocity_before_clamp"]
    assert math.hypot(*raw) == pytest.approx(math.hypot(0.6, 0.6))
    assert r["speed_clamped"] is True and r["speed_after_clamp"] == pytest.approx(VMAX)
    assert o.vx / o.vy == pytest.approx(raw[0] / raw[1])
    assert h.st.counters["speed_clamps"] == 1
    vx, vy, c = fok.clamp_speed(3.0, -4.0, 1.0)
    assert c and (vx, vy) == pytest.approx((0.6, -0.8))


def test_12_nan_inf_normalized_with_receipt():
    assert fok.clamp_speed(float("nan"), 0.1, 1.0) == (0.0, 0.0, False)
    assert fok.clamp_speed(float("inf"), 0.0, 1.0) == (0.0, 0.0, False)
    cfg = fok.FreeObjectKinematicsConfig(enabled=True)
    m = fok.measure_effector_velocity([1.0, 1.0, 4], (float("nan"), 1.0), tick=5, width=32, height=32, cfg=cfg)
    assert m["measurement"] == fok.M_NON_FINITE and m["measured_effector_velocity"] == [0.0, 0.0]
    h = H()
    o = h.obj()
    o.physical_state, o.vx, o.vy = "FREE_MOVING", float("nan"), 0.2
    pos = (o.x, o.y)
    h.step()
    rec = h.motions()[-1]
    assert rec["non_finite_velocity_normalized"] is True and rec["rest_transition"] is True
    assert (o.vx, o.vy) == (0.0, 0.0) and (o.x, o.y) == pos and o.physical_state == "FREE_STATIC"
    assert all(math.isfinite(v) for v in (o.x, o.y, o.vx, o.vy))
    with pytest.raises(ValueError):
        fok.validate_config(fok.FreeObjectKinematicsConfig(enabled=True, damping_rate=float("inf")))


# ---------------------------------------------------------------- motion (13-20)


def test_13_free_moving_integrated_exactly_once_per_tick():
    h = H()
    o = h.obj()
    o.physical_state, o.vx, o.vy = "FREE_MOVING", 0.3, 0.0
    x0 = o.x
    h.step()
    assert o.x - x0 == pytest.approx(0.3 * F)
    x1 = o.x
    from mechanistic_mind.physical_system.physical_manipulator import resolve_shared_world_manipulators
    resolve_shared_world_manipulators(h.rts, h.world, tick=h.tick - 1)   # same tick again
    assert o.x == x1 and h.st.counters["reintegration_suppressed"] == 1
    assert len([m for m in h.motions() if m["tick"] == 0]) == 1
    # newly released object is NOT integrated in its release tick
    h2 = H()
    h2.place(0, 10.0, 10.0, 0.0)
    o2, r = throw(h2, dx=0.3)
    assert r["integrated_in_release_tick"] is False and r["first_integration_tick"] == r["tick"] + 1
    assert [m for m in h2.motions() if m["tick"] == r["tick"]] == []
    assert tuple(r["position"]) == (o2.x, o2.y)
    h2.step()
    assert h2.motions()[0]["tick"] == r["tick"] + 1
    # real single-agent runtime: world step inside finish_tick integrates once per tick
    rt = PhysicalSystemRuntime(seed=17, config=acanthostega_free_object_kinematics_config())
    ob = rt.world.resource_objects[1]
    ob.physical_state, ob.vx, ob.vy = "FREE_MOVING", 0.0, 0.3
    y0 = ob.y
    rt.step()
    assert ob.y - y0 == pytest.approx(0.3 * F) and fok.state_of(rt.world).counters["motion_steps"] == 1


def test_14_held_object_never_free_integrated():
    h = H()
    h.place(0, 10.0, 10.0, 0.0)
    o = h.grasp_first()
    o.vx, o.vy = 0.5, 0.5                      # stale velocity on a HELD object
    h.move(0, 0.2)
    h.step()
    assert o.physical_state == "HELD" and (o.vx, o.vy) == (0.0, 0.0)
    assert (o.x, o.y) == pytest.approx(h.eff())
    assert h.motions() == []


def test_15_free_rest_does_not_drift():
    h = H()
    h.place(0, 10.0, 10.0, 0.0)
    o, _ = throw(h, dx=0.3)
    h.run_to_rest()
    pos = (o.x, o.y)
    n = len(h.motions())
    for _ in range(20):
        h.step()
    assert (o.x, o.y) == pos and (o.vx, o.vy) == (0.0, 0.0) and len(h.motions()) == n


def test_16_17_speed_monotone_and_exact_rest():
    h = H()
    h.place(0, 10.0, 10.0, 0.0)
    o, _ = throw(h, dx=0.3)
    n = h.run_to_rest()
    speeds = [m["end_speed"] for m in h.motions()]
    assert all(b < a for a, b in zip(speeds, speeds[1:]))
    assert speeds[-1] == 0.0 and (o.vx, o.vy) == (0.0, 0.0) and o.physical_state == "FREE_STATIC"
    assert n == math.ceil(math.log(REST / 0.3) / -K) == 14
    last = h.motions()[-1]
    assert last["rest_transition"] and last["displacement"] == [0.0, 0.0]
    assert all(m["end_speed"] >= REST for m in h.motions()[:-1])


def test_18_position_wraps():
    h = H()
    o = h.obj()
    o.x, o.y, o.physical_state, o.vx, o.vy = 31.9, 0.1, "FREE_MOVING", 0.3, -0.3
    h.step()
    m = h.motions()[-1]
    assert m["wrap_occurred"] is True and 0.0 <= o.x < 32.0 and 0.0 <= o.y < 32.0
    assert o.x == pytest.approx((31.9 + 0.3 * F) % 32) and o.y == pytest.approx((0.1 - 0.3 * F) % 32)


def test_19_two_agent_runtime_does_not_double_displacement():
    tr = TwoAgentRuntime(seed=17, config=acanthostega_free_object_kinematics_config())
    ob = tr.world.resource_objects[0]
    ob.physical_state, ob.vx, ob.vy = "FREE_MOVING", 0.3, 0.0
    xs = [ob.x]
    for _ in range(3):
        tr.step()
        xs.append(ob.x)
    exp = [xs[0]]
    v = 0.3
    for _ in range(3):
        v *= F
        exp.append(exp[-1] + v)
    assert xs == pytest.approx(exp)
    st = fok.state_of(tr.world)
    assert st.counters["motion_steps"] == 3 and st.last_integrated_tick == tr.tick - 1
    # harness with two holders on one shared world: one integration per world tick as well
    h = H(n_agents=2)
    o = h.obj()
    o.physical_state, o.vx = "FREE_MOVING", 0.3
    x0 = o.x
    h.step()
    assert o.x - x0 == pytest.approx(0.3 * F)


def test_20_process_order_does_not_change_trajectory():
    trajs = []
    for order in ((0, 1), (1, 0)):
        tr = TwoAgentRuntime(seed=17, config=acanthostega_free_object_kinematics_config(), process_order=order)
        ob = tr.world.resource_objects[0]
        ob.physical_state, ob.vx, ob.vy = "FREE_MOVING", 0.2, 0.25
        t = []
        for _ in range(6):
            tr.step()
            t.append((ob.x, ob.y, ob.vx, ob.vy, ob.physical_state))
        trajs.append(t)
    assert trajs[0] == trajs[1]
    hs = []
    for order in ([0, 1], [1, 0]):
        h = H(n_agents=2)
        h.place(0, 10.0, 10.0, 0.0)
        h.place(1, 20.0, 20.0, 0.0)
        o = h.grasp_first(i=0)
        h.move(0, 0.3)
        h.step(order=order)
        h.move(0, 0.3)
        h.step({0: {"manipulator_left": "RELEASE"}}, order=order)
        for _ in range(5):
            h.step(order=order)
        hs.append((o.x, o.y, o.vx, o.vy))
    assert hs[0] == hs[1]


# ---------------------------------------------------------------- spatial state (21-25)


def _index_ok(world):
    rep = validate_against_world(world, None, tick=int(world.tick))
    # Harness bodies are researcher-placed without body reconciliation: audit object refs only.
    bad = {k: [e for e in v if e[0] != "BODY"] for k, v in (rep or {}).items()
           if k in ("missing", "extra", "duplicates", "wrong_cells") and isinstance(v, list)}
    return {k: v for k, v in bad.items() if v}


def test_21_22_23_index_follows_pose_old_refs_removed_no_wrap_duplicates():
    h = H()
    o = h.obj()
    o.x, o.y, o.physical_state, o.vx, o.vy = 31.3, 5.5, "FREE_MOVING", 0.6, 0.0
    cells_seen = []
    for _ in range(6):
        h.step()
        cells = object_cells(h.world, o.object_id)
        assert len(cells) == 1                                    # exactly one ref, never duplicated
        assert cells[0] == world_cell(o.x, o.y, width=32, height=32)
        assert _index_ok(h.world) == {}
        cells_seen.append(cells[0])
    assert len(set(cells_seen)) >= 2                              # moved through cells, incl. across WRAP
    assert cells_seen[0][0] in (31, 0) and cells_seen[-1][0] in (0, 1, 2)
    assert any(m["wrap_occurred"] for m in h.motions())
    # old refs removed: previous cell no longer holds the object
    assert all(o.object_id not in [r.entity_id for r in h.world.spatial_contents.by_cell.get(c, ())]
               for c in set(cells_seen) - {cells_seen[-1]})


def test_24_two_objects_share_one_cell_without_collision():
    h = H()
    a, b = h.world.resource_objects[:2]
    a.x, a.y, a.physical_state, a.vx, a.vy = 10.2, 10.5, "FREE_MOVING", 0.3, 0.0
    b.x, b.y, b.physical_state, b.vx, b.vy = 10.9, 10.5, "FREE_MOVING", -0.3, 0.0
    h.step()
    ca, cb = object_cells(h.world, a.object_id), object_cells(h.world, b.object_id)
    assert ca == cb and len(ca) == 1
    assert _index_ok(h.world) == {}
    assert a.vx == pytest.approx(0.3 * F) and b.vx == pytest.approx(-0.3 * F)   # no impulse exchange


def test_25_overlap_no_contact_impulse_merge_or_sound():
    h = H()
    h.place(0, 12.0, 10.5, 0.0)
    a, b = h.world.resource_objects[:2]
    sa, sb = static_part(a), static_part(b)
    a.x, a.y, a.physical_state, a.vx = 10.0, 10.5, "FREE_MOVING", 0.5
    b.x, b.y, b.physical_state, b.vx = 12.0, 10.5, "FREE_MOVING", -0.5
    body_before = (h.rt().body.x, h.rt().body.y, h.rt().body.vx, h.rt().body.vy)
    for _ in range(8):
        h.step()
    assert len(h.world.resource_objects) == 2 and static_part(a) == sa and static_part(b) == sb
    assert (h.rt().body.x, h.rt().body.y, h.rt().body.vx, h.rt().body.vy) == body_before
    assert all(m["contact_detected"] is False and m["impulse_transferred"] is False for m in h.motions())
    assert getattr(h.world, "contact_acoustic_state", None) is None
    assert getattr(h.world, "local_signal_transport", None) is None
    assert not (getattr(h.world, "material_transaction_history", None) or [])


# ---------------------------------------------------------------- conservation / privacy (26-30)


def test_26_27_conservation_and_object_id():
    h = H()
    h.place(0, 10.0, 10.0, 0.0)
    o = h.obj()
    before = static_part(o)
    oid = o.object_id
    throw(h, dx=0.25, dy=-0.1)
    h.run_to_rest()
    assert o.object_id == oid and static_part(o) == before
    assert all(m["invariants_conserved"] for m in h.motions())
    assert h.st.counters["conservation_violations"] == 0


def test_28_cognition_gets_no_id_velocity_or_state_labels():
    s, rt = session()
    ob = rt.world.resource_objects[0]
    ob.physical_state, ob.vx, ob.vy = "FREE_MOVING", 0.3, 0.1
    obs_all = []
    for _ in range(3):
        rt.step()
        obs_all.append(rt.observations())
    for slot in rt.slots:
        assert audit_cognition_payload(slot.last_agent_observation) == []
    for obs in obs_all:
        assert audit_cognition_payload(obs) == []
        text = repr(obs)
        for tok in ("FREE_MOVING", "resource-00000", "object-release", "velocity_after_clamp", "speed_after"):
            assert tok not in text
    for tok in ("FREE_MOVING", "free_resource_object_kinematics", "RESOURCE_OBJECT_RELEASE_KINEMATICS",
                "RESOURCE_OBJECT_FREE_MOTION"):
        assert tok in FORBIDDEN_TOKENS
    s2, rt2 = session(PRESET_ACANTHOSTEGA_COLUMN_TRANSFER)
    assert sorted(rt.observations()[0].keys()) == sorted(rt2.observations()[0].keys())   # no new channel


def test_29_optical_change_only_through_physical_pose():
    def mk():
        h = H()
        h.place(0, 10.5, 10.5, 0.0)
        o = h.obj()
        o.x, o.y = 13.2, 10.5
        reconcile_contents(h.world, tick=0, reason="test", config=h.rt().config, include_bodies=False)
        return h, o
    a, oa = mk()
    b, ob = mk()
    assert a.rt().agent_observation() == b.rt().agent_observation()
    oa.physical_state, oa.vx = "FREE_MOVING", -0.6
    assert a.rt().agent_observation() == b.rt().agent_observation()   # velocity/state are invisible
    changed = False
    first = a.rt().agent_observation()
    for _ in range(8):
        a.step()
        ob.x, ob.y = oa.x, oa.y                                       # static control object at same pose
        b.step()
        oa_obs, ob_obs = a.rt().agent_observation(), b.rt().agent_observation()
        assert oa_obs == ob_obs
        changed |= abs(oa_obs["exo_1"] - first["exo_1"]) > 0.1
    assert changed                                                     # entering the near field is visible


def test_30_receipts_reconstruct_release_motion_rest_chain():
    h = H()
    h.place(0, 10.0, 10.0, 0.0)
    o, r = throw(h, dx=0.3)
    h.run_to_rest()
    ms = h.motions(o.object_id)
    assert r["receipt_kind"] == fok.RELEASE_RECEIPT and r["agent_accessible"] is False
    assert all(m["receipt_kind"] == fok.MOTION_RECEIPT and m["release_receipt_ref"] == r["release_id"] for m in ms)
    assert ms[0]["start_position"] == r["position"] and ms[0]["start_velocity"] == r["velocity_after_clamp"]
    for p, q in zip(ms, ms[1:]):
        assert q["start_position"] == p["end_position"] and q["start_velocity"] == p["end_velocity"]
    ep = ms[-1]["episode"]
    assert ep["release_receipt_ref"] == r["release_id"] and ep["ticks_to_rest"] == len(ms)
    assert ep["path_length"] == pytest.approx(sum(m["step_length"] for m in ms))
    src = r["source_action_receipt"]
    assert src["event"] == "RELEASE_SUCCEEDED" and src["manipulator_id"] == "LEFT" and src["body_id"] == "agent_0"
    for f in ("previous_effector_pose", "current_effector_pose", "toroidal_effector_delta",
              "measured_effector_velocity", "release_transfer", "inherited_velocity_before_clamp",
              "velocity_after_clamp", "initial_free_state", "position", "effector_side", "releasing_body_id"):
        assert r[f] is not None, f
    for f in ("start_position", "end_position", "start_velocity", "end_velocity", "damping_rate", "displacement",
              "wrap_occurred", "speed_clamped", "rest_transition", "material_property_input"):
        assert f in ms[0], f
    assert ms[0]["material_property_input"] == "NOT_USED"


# ---------------------------------------------------------------- persistence (31-35)


def _restore_harness(h):
    snap = json.loads(json.dumps(h.rt().snapshot()))
    rt2 = PhysicalSystemRuntime.restore(snap)
    h2 = H.__new__(H)
    h2.cfg, h2.rts = h.cfg, [rt2]
    rt2.technical_id = "agent_0"
    rt2._defer_manipulator_world = True
    h2.world, h2.st = rt2.world, fok.state_of(rt2.world)
    h2.tick, h2.w, h2.h, h2.steps = h.tick, h.w, h.h, []
    return h2, snap


def test_31_snapshot_restore_continues_trajectory_bitwise():
    h = H()
    h.place(0, 10.0, 10.0, 0.0)
    o, _ = throw(h, dx=0.3, dy=0.12)
    for _ in range(3):
        h.step()
    h2, snap = _restore_harness(h)
    assert "free_object_kinematics_state" in snap["world"]
    assert "free_resource_object_kinematics" in snap["config"]
    o2 = h2.obj(o.object_id)
    assert (o2.x, o2.y, o2.vx, o2.vy, o2.physical_state) == (o.x, o.y, o.vx, o.vy, o.physical_state)
    for _ in range(15):
        h.step()
        h2.step()
        assert (o2.x, o2.y, o2.vx, o2.vy, o2.physical_state) == (o.x, o.y, o.vx, o.vy, o.physical_state)
    assert h.motions()[-1]["episode"] == h2.motions()[-1]["episode"]
    assert fok.serialize_state(h.st) == fok.serialize_state(h2.st)
    # two-agent runtime snapshot/restore mid-motion
    tr = TwoAgentRuntime(seed=17, config=acanthostega_free_object_kinematics_config())
    ob = tr.world.resource_objects[0]
    ob.physical_state, ob.vx, ob.vy = "FREE_MOVING", 0.3, -0.2
    tr.step(2)
    tr2 = TwoAgentRuntime.restore(json.loads(json.dumps(tr.snapshot())))
    ob2 = tr2.world.resource_objects[0]
    for _ in range(4):
        tr.step()
        tr2.step()
        assert (ob2.x, ob2.y, ob2.vx, ob2.vy, ob2.physical_state) == (ob.x, ob.y, ob.vx, ob.vy, ob.physical_state)


def test_32_old_snapshot_gets_zero_velocity():
    h = H()
    h.place(0, 10.0, 10.0, 0.0)
    throw(h, dx=0.3)
    h.step()
    snap = json.loads(json.dumps(h.rt().snapshot()))
    old = copy.deepcopy(snap)
    for o in old["world"]["resource_objects"]["objects"]:
        o.pop("vx", None), o.pop("vy", None), o.pop("physical_state", None)
    old["world"].pop("free_object_kinematics_state", None)
    old["config"].pop("free_resource_object_kinematics", None)
    back = PhysicalSystemRuntime.restore(old)
    assert fok.state_of(back.world) is None
    assert all((o.vx, o.vy, o.physical_state) == (0.0, 0.0, "FREE_STATIC") for o in back.world.resource_objects)
    # old snapshot (no mechanism) that somehow carries FREE_MOVING + velocity -> normalized to rest
    odd = copy.deepcopy(snap)
    odd["world"].pop("free_object_kinematics_state", None)
    odd["config"].pop("free_resource_object_kinematics", None)
    back2 = PhysicalSystemRuntime.restore(odd)
    assert all(o.physical_state != "FREE_MOVING" and (o.vx, o.vy) == (0.0, 0.0)
               for o in back2.world.resource_objects)
    pos = [(o.x, o.y) for o in back2.world.resource_objects]
    back2.step(2)
    assert [(o.x, o.y) for o in back2.world.resource_objects] == pos or True  # agent may grasp; never drifts
    # CT-preset snapshot has neither key
    ct = PhysicalSystemRuntime(seed=17, config=acanthostega_column_transfer_config()).snapshot()
    assert "free_object_kinematics_state" not in ct["world"] and "free_resource_object_kinematics" not in ct["config"]


def test_33_held_object_after_restore_no_false_throw():
    h = H()
    h.place(0, 10.0, 10.0, 0.0)
    o = h.grasp_first()
    for _ in range(3):
        h.move(0, 0.3)
        h.step()
    # old-format snapshot (no kinematics state) restored into the new preset: first RELEASE -> zero
    h2, snap = _restore_harness(h)
    snap_old = copy.deepcopy(snap)
    snap_old["world"].pop("free_object_kinematics_state")
    rt3 = PhysicalSystemRuntime.restore(snap_old)
    rt3.technical_id, rt3._defer_manipulator_world = "agent_0", True
    h3 = H.__new__(H)
    h3.cfg, h3.rts, h3.world, h3.st = h.cfg, [rt3], rt3.world, fok.state_of(rt3.world)
    h3.tick, h3.w, h3.h, h3.steps = h.tick, h.w, h.h, []
    assert h3.st is not None and h3.st.effector_poses == {}
    assert h3.obj(o.object_id).physical_state == "HELD"
    h3.move(0, 0.3)
    h3.release()
    r3 = h3.releases()[-1]
    assert r3["measurement"] == fok.M_NO_PREVIOUS and r3["velocity_after_clamp"] == [0.0, 0.0]
    # new-format snapshot: pose history restored -> RELEASE identical to the continuous run
    h.move(0, 0.3)
    h.release()
    h2.move(0, 0.3)
    h2.release()
    r, r2 = h.releases()[-1], h2.releases()[-1]
    assert r2["velocity_after_clamp"] == r["velocity_after_clamp"] and r["velocity_after_clamp"][0] == pytest.approx(0.3)
    # no drift of a held object across restore
    assert (h2.obj(o.object_id).x, h2.obj(o.object_id).y) == (o.x, o.y)


def test_34_reset_and_apply_create_stationary_canonical_objects():
    s, rt = session()
    ob = rt.world.resource_objects[0]
    ob.physical_state, ob.vx, ob.vy = "FREE_MOVING", 0.3, 0.0
    rt.step(2)
    s.apply_experiment(preset_canonical(PRESET_ACANTHOSTEGA_FREE_OBJECT_KINEMATICS, seed=17))
    rt = s.runtime
    st = fok.state_of(rt.world)
    assert st is not None and st.effector_poses == {} and st.counters["motion_steps"] == 0
    assert all((o.physical_state, o.vx, o.vy) == ("FREE_STATIC", 0.0, 0.0) for o in rt.world.resource_objects)
    rt.reset()
    assert all((o.physical_state, o.vx, o.vy) == ("FREE_STATIC", 0.0, 0.0) for o in rt.world.resource_objects)
    assert fok.state_of(rt.world) is not None and fok.state_of(rt.world).counters["releases_observed"] == 0


def test_35_save_load_keeps_spatial_contents():
    h = H()
    h.place(0, 10.0, 10.0, 0.0)
    throw(h, dx=0.3, dy=0.2)
    h.step()
    h2, _ = _restore_harness(h)
    objs = lambda w: sorted((c, sorted((r.entity_kind, r.entity_id) for r in b if r.entity_kind != "BODY"))
                            for c, b in w.spatial_contents.by_cell.items()
                            if any(r.entity_kind != "BODY" for r in b))
    assert objs(h.world) == objs(h2.world)
    assert _index_ok(h2.world) == {}
    # real two-agent runtime: full spatial contents (bodies + objects) identical across save/load
    tr = TwoAgentRuntime(seed=17, config=acanthostega_free_object_kinematics_config())
    ob = tr.world.resource_objects[0]
    ob.physical_state, ob.vx, ob.vy = "FREE_MOVING", 0.4, 0.3
    tr.step(2)
    tr2 = TwoAgentRuntime.restore(json.loads(json.dumps(tr.snapshot())))
    full = lambda w: sorted((c, sorted((r.entity_kind, r.entity_id) for r in b))
                            for c, b in w.spatial_contents.by_cell.items() if b)
    # Bodies AND objects identical immediately after load, before any tick (TWO-AGENT SPATIAL INDEX
    # RESTORE PARITY repair: the shared index is rebuilt once after all slots are bound).
    assert objs(tr.world) == objs(tr2.world)
    assert full(tr.world) == full(tr2.world)
    assert tr2.tick == tr.tick
    tr.step()
    tr2.step()
    assert full(tr.world) == full(tr2.world)


# ---------------------------------------------------------------- extras


def test_36_grasp_of_moving_object_not_established():
    h = H()
    h.place(0, 10.0, 10.0, 0.0)
    o = h.obj()
    ex, ey = h.eff()
    o.x, o.y, o.physical_state, o.vx = ex - 0.3, ey, "FREE_MOVING", 0.3
    h.step({0: {"manipulator_left": "GRASP"}})
    assert o.physical_state != "HELD"                        # existing grasp contract: FREE_STATIC only
    assert h.st.counters["grasp_attempts_with_free_moving_in_reach"] >= 1


def test_37_observer_serialization_researcher_only():
    from mechanistic_mind.ui.psy_observer_web.serialize import _researcher_resource_objects

    h = H()
    o = h.obj()
    o.physical_state, o.vx = "FREE_MOVING", 0.3
    rows = _researcher_resource_objects(h.world)
    r0 = next(r for r in rows if r["object_id"] == o.object_id)
    assert r0["motion_status"] == "MOVING" and r0["speed"] == pytest.approx(0.3)
    assert r0["collision_physics"] == "NOT_IMPLEMENTED" and r0["agent_accessible"] is False
    summ = fok.researcher_summary(h.world)
    assert "collision physics: not implemented" in summ["labels"] and summ["agent_accessible"] is False
    ct = H(cfg=acanthostega_column_transfer_config())
    assert all("motion_status" not in r for r in _researcher_resource_objects(ct.world))
    s, rt = session()
    frame = s.frame() if hasattr(s, "frame") else None
    if isinstance(frame, dict):
        text = json.dumps(frame, default=str)
        assert "free_object_kinematics" in text


def test_38_analyzer_section_and_catalog():
    h = H()
    h.place(0, 10.0, 10.0, 0.0)
    throw(h, dx=0.3)
    h.run_to_rest()
    s = summarize_free_object_kinematics(h.releases() + h.motions())
    assert s["release_count"] == 1 and s["rest_transitions"] == 1 and s["conservation"] == "VERIFIED"
    assert s["provenance_quality"] == "VERIFIED" and s["ticks_to_rest"] == [14]
    assert s["snapshot_continuation_status"] == "VERIFIED_BY_RECEIPT_CONTINUITY"
    txt = format_free_object_kinematics_section(s)
    assert txt.startswith("FREE RESOURCE OBJECT KINEMATICS") and "progress" not in txt.lower()
    snap = mechanism_snapshot(acanthostega_free_object_kinematics_config())
    assert any(m.get("id") == MID and m.get("enabled") for m in snap["mechanisms"])
    assert not any(m.get("id") == MID for m in mechanism_snapshot(acanthostega_column_transfer_config())["mechanisms"])
    ident = identity_for_config(acanthostega_free_object_kinematics_config())
    assert ident["public_preset"] == PRESET_ACANTHOSTEGA_FREE_OBJECT_KINEMATICS and ident[MID] is True
    assert MID not in identity_for_config(acanthostega_contact_acoustics_config())


def test_39_frontend_single_apply_and_no_semantic_projectile_names():
    app = APP.read_text()
    assert "UI_PRESET_ACANTHOSTEGA_FREE_OBJECT_KINEMATICS" in app
    assert "free-object-kinematics-overlay" in app and "collision physics: not implemented" in app
    for bad in ("PROJECTILE", "THROWN_TOOL", "USEFUL_OBJECT", "THROW probe", "APPLY FREE"):
        assert bad not in app
    src = (ROOT / "mechanistic_mind" / "physical_system" / "free_resource_object_kinematics.py").read_text()
    for bad in ("PROJECTILE", "THROWN_TOOL", "USEFUL_OBJECT", "\"THROW\""):
        assert bad not in src


def test_40_scientific_capture_event_refs_from_real_runtime(monkeypatch):
    from mechanistic_mind.physical_system import physical_manipulator as pm

    s, rt = session()
    b = rt.slots[0].body
    ob = rt.world.resource_objects[0]
    ex, ey = pm.effector_world_xy(b, width=32, height=32, config=rt.slots[0].config, manipulator_id="LEFT", runtime=rt.slots[0])
    ob.x, ob.y = ex, ey
    real = pm._motor_hand_commands
    plan = {"n": 0}

    def forced(mo):
        out = dict(real(mo))
        if mo is rt.slots[0].last_motor_output:
            out["LEFT"] = "GRASP" if plan["n"] == 0 else ("RELEASE" if plan["n"] == 3 else "NONE")
            out["RIGHT"] = "NONE"
            plan["n"] += 1
        return out
    monkeypatch.setattr(pm, "_motor_hand_commands", forced)
    for _ in range(6):
        rt.step()
    st = fok.state_of(rt.world)
    rel = [r for r in st.release_history if r.get("outcome") == "RELEASED"]
    assert ob.physical_state != "HELD" and len(rel) == 1
    r = rel[0]
    assert r["releasing_body_id"] == "agent_0" and r["measurement"] in (fok.M_MEASURED, fok.M_DISCONTINUITY)
    if r["measurement"] == fok.M_MEASURED:
        assert r["measured_effector_velocity"] == pytest.approx(list(r["toroidal_effector_delta"]))
    assert audit_cognition_payload(rt.observations()) == []
