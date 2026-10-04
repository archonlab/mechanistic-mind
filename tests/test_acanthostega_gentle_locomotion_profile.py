"""Acanthostega Gentle Locomotion Kernel — physics, map, snapshot, Observer."""
from __future__ import annotations

import math
from copy import deepcopy

from mechanistic_mind.model.acanthostega import (
    PUBLIC_PRESET as PHASE0,
    PUBLIC_PRESET_GENTLE,
    acanthostega_config,
    acanthostega_gentle_config,
)
from mechanistic_mind.model.tiktaalik import tiktaalik_config
from mechanistic_mind.physical_system.experiment_canonical import (
    PRESET_ACANTHOSTEGA,
    PRESET_ACANTHOSTEGA_GENTLE,
    PRESET_BETA31,
    acanthostega_mechanism_map,
    beta31_mechanism_map,
    canonical_fingerprint,
    normalize_preset_name,
    preset_canonical,
)
from mechanistic_mind.physical_system.locomotion_profile import (
    GENTLE_TERRAIN_LOCOMOTION,
    PROFILE_ACANTHOSTEGA_GENTLE,
    profile_is_active,
    set_gentle_terrain_locomotion,
)
from mechanistic_mind.physical_system.physical_push import PhysicalPushConfig
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.planet.topology import toroidal_delta
from mechanistic_mind.ui.psy_observer_web.serialize import header_info
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig

FROZEN_BETA31_FP_SEED17 = "1621ef2c154864d1"
SEED = 17


def _disp(rt, x0, y0):
    w, h = rt.world.T.shape[1], rt.world.T.shape[0]
    return math.hypot(toroidal_delta(x0, rt.body.x, w), toroidal_delta(y0, rt.body.y, h))


def _run(cfg, actions, seed=SEED):
    cfg = cfg.copy()
    cfg.cognition.cognition_enabled = False
    rt = PhysicalSystemRuntime(seed=seed, config=cfg)
    x0, y0 = float(rt.body.x), float(rt.body.y)
    path = 0.0
    w, h = rt.world.T.shape[1], rt.world.T.shape[0]
    px, py = x0, y0
    for a in actions:
        rt.step_forced_action(a)
        path += math.hypot(toroidal_delta(px, rt.body.x, w), toroidal_delta(py, rt.body.y, h))
        px, py = float(rt.body.x), float(rt.body.y)
    return {
        "rt": rt,
        "displacement": _disp(rt, x0, y0),
        "path": path,
        "speed": math.hypot(rt.body.vx, rt.body.vy),
        "xy": (float(rt.body.x), float(rt.body.y)),
        "v": (float(rt.body.vx), float(rt.body.vy)),
        "work": float(rt.body.mechanical_work_reservoir),
        "forces": dict(rt.last_force_contributions or {}),
    }


def test_beta31_map_has_no_gentle_key():
    m = beta31_mechanism_map()
    assert GENTLE_TERRAIN_LOCOMOTION not in m
    am = acanthostega_mechanism_map()
    assert am[GENTLE_TERRAIN_LOCOMOTION] is True
    assert GENTLE_TERRAIN_LOCOMOTION not in beta31_mechanism_map()


def test_beta31_fingerprint_unchanged():
    assert canonical_fingerprint(preset_canonical(PRESET_BETA31, seed=17)) == FROZEN_BETA31_FP_SEED17


def test_phase0_preset_unchanged_mechanisms():
    a = preset_canonical(PRESET_ACANTHOSTEGA, seed=17)
    t = preset_canonical(PRESET_BETA31, seed=17)
    assert a["mechanisms"] == t["mechanisms"]
    assert GENTLE_TERRAIN_LOCOMOTION not in a["mechanisms"]


def test_phase_a_preset_identity():
    assert normalize_preset_name("Acanthostega Phase A Gentle") == PRESET_ACANTHOSTEGA_GENTLE
    p = preset_canonical(PRESET_ACANTHOSTEGA_GENTLE, seed=17)
    assert p["public_preset"] == PUBLIC_PRESET_GENTLE
    assert p["model_line"] == "ACANTHOSTEGA"
    assert p["mechanisms"][GENTLE_TERRAIN_LOCOMOTION] is True
    assert p["mechanisms"][GENTLE_TERRAIN_LOCOMOTION] is True
    assert canonical_fingerprint(p) != FROZEN_BETA31_FP_SEED17


def test_tiktaalik_wait50_matches_phase0():
    t = _run(tiktaalik_config(), ["WAIT"] * 50)
    a = _run(acanthostega_config(), ["WAIT"] * 50)
    assert t["xy"] == a["xy"]
    assert t["v"] == a["v"]


def test_gentle_wait250_rest():
    t = _run(tiktaalik_config(), ["WAIT"] * 250)
    g = _run(acanthostega_gentle_config(), ["WAIT"] * 250)
    assert t["displacement"] > 1.0
    assert g["displacement"] < 0.35
    assert g["speed"] < 0.012
    fc = g["forces"]
    assert fc.get("gentle_terrain_locomotion") is True
    assert fc.get("locomotion_profile") == PROFILE_ACANTHOSTEGA_GENTLE
    assert "support_force" in fc or "environment_force" in fc


def test_gentle_single_move_decay():
    g = _run(acanthostega_gentle_config(), ["MOVE:E"] + ["WAIT"] * 249)
    assert g["displacement"] < 0.8
    cfg = acanthostega_gentle_config()
    cfg.cognition.cognition_enabled = False
    rt = PhysicalSystemRuntime(seed=SEED, config=cfg)
    x0 = float(rt.body.x)
    rt.step_forced_action("MOVE:E")
    step1 = abs(float(rt.body.x) - x0)
    assert step1 > 0.01
    v1 = math.hypot(rt.body.vx, rt.body.vy)
    assert v1 > 0.01
    rt.step_forced_action("WAIT")
    v2 = math.hypot(rt.body.vx, rt.body.vy)
    assert v2 < v1
    assert math.hypot(rt.body.vx, rt.body.vy) > 0.0 or step1 > 0.01


def test_gentle_sustained_move():
    w = _run(acanthostega_gentle_config(), ["WAIT"] * 100)
    m = _run(acanthostega_gentle_config(), ["MOVE:E"] * 100)
    assert m["displacement"] > w["displacement"] + 1.0
    assert m["path"] > 1.0
    w32 = 32
    dx = toroidal_delta(8.5, m["xy"][0], w32)
    # Eastward MOVE may wrap the 32-cell torus; net image may be negative.
    assert abs(dx) > 0.5 or m["path"] > 5.0
    assert abs(m["xy"][1] - 16.5) < 4.0
    assert math.isfinite(m["speed"])


def test_gentle_off_matches_phase0_physics():
    cfg = acanthostega_gentle_config()
    set_gentle_terrain_locomotion(cfg, False)
    assert profile_is_active(cfg) is False
    off = _run(cfg, ["WAIT"] * 80)
    p0 = _run(acanthostega_config(), ["WAIT"] * 80)
    assert off["xy"] == p0["xy"]
    assert off["v"] == p0["v"]


def test_env_force_diagnostics_present():
    g = _run(acanthostega_gentle_config(), ["WAIT"] * 20)
    fc = g["forces"]
    assert fc.get("locomotion_profile") == PROFILE_ACANTHOSTEGA_GENTLE
    assert "environment_force" in fc
    assert "support_force" in fc


def test_push_contact_still_displaces():
    cfg = acanthostega_gentle_config()
    cfg.physical_push = PhysicalPushConfig(mode="EXPERIMENTAL")
    cfg.cognition.cognition_enabled = False
    ta = TwoAgentRuntime(seed=SEED, config=cfg, starts=((8.0, 16.0), (9.0, 16.0)))
    ta.contact_enabled = True
    for rt in ta.slots:
        rt.config.cognition.cognition_enabled = False
        rt.config.physical_push = PhysicalPushConfig(mode="EXPERIMENTAL")
        rt.config.locomotion_profile = cfg.locomotion_profile
    x_b0 = float(ta.slots[1].body.x)
    ta.slots[0]._forced_action_once = "PUSH"
    ta.step()
    moved = abs(float(ta.slots[1].body.x) - x_b0) + abs(float(ta.slots[1].body.vx))
    assert moved > 1e-6


def test_tiktaalik_two_agent_contact_untouched():
    cfg = tiktaalik_config()
    cfg.physical_push = PhysicalPushConfig(mode="EXPERIMENTAL")
    cfg.cognition.cognition_enabled = False
    ta = TwoAgentRuntime(seed=SEED, config=cfg, starts=((8.0, 16.0), (9.0, 16.0)))
    ta.contact_enabled = True
    for rt in ta.slots:
        rt.config.cognition.cognition_enabled = False
        rt.config.physical_push = PhysicalPushConfig(mode="EXPERIMENTAL")
    x_b0 = float(ta.slots[1].body.x)
    ta.slots[0]._forced_action_once = "PUSH"
    ta.step()
    assert abs(float(ta.slots[1].body.x) - x_b0) + abs(float(ta.slots[1].body.vx)) > 1e-6


def test_two_agent_determinism():
    def run():
        cfg = acanthostega_gentle_config()
        cfg.cognition.cognition_enabled = False
        ta = TwoAgentRuntime(seed=SEED, config=cfg)
        for rt in ta.slots:
            rt.config.cognition.cognition_enabled = False
        for _ in range(40):
            ta.step()
        return [(float(s.body.x), float(s.body.y), float(s.body.vx), float(s.body.vy)) for s in ta.slots]

    assert run() == run()


def test_snapshot_restore_continues():
    cfg = acanthostega_gentle_config()
    cfg.cognition.cognition_enabled = False
    rt = PhysicalSystemRuntime(seed=SEED, config=cfg)
    for _ in range(12):
        rt.step_forced_action("MOVE:E")
    snap = rt.snapshot()
    assert snap["config"]["locomotion_profile"]["enabled"] is True
    assert snap["config"]["locomotion_profile"]["name"] == PROFILE_ACANTHOSTEGA_GENTLE
    restored = PhysicalSystemRuntime.restore(deepcopy(snap))
    assert profile_is_active(restored.config)
    assert restored.body.x == rt.body.x
    restored.step_forced_action("WAIT")
    rt.step_forced_action("WAIT")
    assert restored.body.x == rt.body.x
    assert restored.body.vx == rt.body.vx


def test_legacy_phase0_snapshot_does_not_enable_gentle():
    cfg = acanthostega_config()
    cfg.cognition.cognition_enabled = False
    rt = PhysicalSystemRuntime(seed=SEED, config=cfg)
    snap = rt.snapshot()
    snap["config"].pop("locomotion_profile", None)
    restored = PhysicalSystemRuntime.restore(deepcopy(snap))
    assert profile_is_active(restored.config) is False


def test_observer_apply_phase_a():
    s = ObserverSession(SessionConfig(seed=17, buffer_capacity=8))
    s.apply_experiment({
        "seed": 17,
        "load_preset": True,
        "public_preset": PRESET_ACANTHOSTEGA_GENTLE,
        "world": {"width": 16, "height": 16, "boundary_mode": "WRAP_PERIODIC"},
    })
    ident = s.runtime.model_identity()
    assert ident["public_preset"] == PUBLIC_PRESET_GENTLE
    assert ident["model_line"] == "ACANTHOSTEGA"
    assert ident["lifecycle_implemented"] is False
    cfg = s.runtime.slots[0].config if hasattr(s.runtime, "slots") else s.runtime.config
    assert profile_is_active(cfg)
    hdr = header_info(s.runtime, status="PAUSED", mode="LIVE", target_tick=None)
    assert hdr["locomotion_profile"] == PROFILE_ACANTHOSTEGA_GENTLE
    assert hdr["gentle_terrain_locomotion"] is True
    ids = {m["id"] for m in (s.runtime.mechanisms().get("mechanisms") or [])}
    assert GENTLE_TERRAIN_LOCOMOTION in ids


def test_observer_tiktaalik_has_no_gentle_toggle():
    s = ObserverSession(SessionConfig(seed=17, buffer_capacity=8))
    s.apply_experiment({
        "seed": 17,
        "load_preset": True,
        "public_preset": PRESET_BETA31,
        "world": {"width": 16, "height": 16, "boundary_mode": "WRAP_PERIODIC"},
    })
    ids = {m["id"] for m in (s.runtime.mechanisms().get("mechanisms") or [])}
    assert GENTLE_TERRAIN_LOCOMOTION not in ids
    hdr = header_info(s.runtime, status="PAUSED", mode="LIVE", target_tick=None)
    assert hdr["gentle_terrain_locomotion"] is False
    assert hdr["locomotion_profile"] == "TIKTAALIK"


def test_phase0_apply_does_not_enable_gentle():
    s = ObserverSession(SessionConfig(seed=17, buffer_capacity=8))
    s.apply_experiment({
        "seed": 17,
        "load_preset": True,
        "public_preset": PHASE0,
        "world": {"width": 16, "height": 16, "boundary_mode": "WRAP_PERIODIC"},
    })
    cfg = s.runtime.slots[0].config if hasattr(s.runtime, "slots") else s.runtime.config
    assert profile_is_active(cfg) is False
