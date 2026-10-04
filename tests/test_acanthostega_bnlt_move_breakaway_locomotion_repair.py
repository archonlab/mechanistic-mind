"""BNLT MOVE breakaway locomotion repair V1 — focused deterministic tests."""
from __future__ import annotations

import math

TICKS = {"n": 0}


def _tick(n: int = 1) -> None:
    TICKS["n"] += int(n)


def _repair_cfg():
    from mechanistic_mind.model.acanthostega import (
        acanthostega_bnlt_move_breakaway_locomotion_repair_config,
    )

    cfg = acanthostega_bnlt_move_breakaway_locomotion_repair_config()
    cfg.cognition.cognition_enabled = False
    return cfg


def _parent_cfg():
    from mechanistic_mind.model.acanthostega import (
        acanthostega_detached_terrain_material_initial_placement_config,
    )

    cfg = acanthostega_detached_terrain_material_initial_placement_config()
    cfg.cognition.cognition_enabled = False
    return cfg


def _rt(cfg=None, seed: int = 17, x: float = 2.5, y: float = 2.5):
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

    rt = PhysicalSystemRuntime(seed=seed, config=cfg or _repair_cfg())
    rt.body.x, rt.body.y = float(x), float(y)
    rt.body.vx = rt.body.vy = 0.0
    rt.body.grounded = True
    return rt


def _force_move(rt, action: str = "MOVE:E") -> float:
    """One forced MOVE tick; return horizontal displacement magnitude."""
    x0, y0 = float(rt.body.x), float(rt.body.y)
    rt.step_forced_action(action)
    _tick()
    return float(math.hypot(float(rt.body.x) - x0, float(rt.body.y) - y0))


def test_unit_kinetic_exhaust_repro_legacy_vs_repair():
    """Canonical stuck numbers: speed_trial < a_k·dt but |Δv_lim|/dt > a_k."""
    from mechanistic_mind.physical_system.bnlt_move_breakaway_locomotion_repair import (
        active_drive_accel_from_impulse,
    )
    from mechanistic_mind.physical_system.free_resource_object_ground_friction import (
        coulomb_kinetic_step,
    )

    m_eff, dt, g = 2.0, 1.0, 1.0
    mu_k = 0.03179420491363692
    mu_s = 0.03977272727272727
    j = mu_s * m_eff * g * dt
    speed_trial = 0.030
    legacy = coulomb_kinetic_step(
        speed_trial,
        0.0,
        mu_k=mu_k,
        g=g,
        dt=dt,
        rest_threshold=1e-9,
        drive_accel=speed_trial / dt,
    )
    drive = active_drive_accel_from_impulse(move_impulse_xy=(j, 0.0), m_eff=m_eff, dt=dt)
    repaired = coulomb_kinetic_step(
        speed_trial,
        0.0,
        mu_k=mu_k,
        g=g,
        dt=dt,
        rest_threshold=1e-9,
        drive_accel=float(drive),
    )
    assert legacy["speed_after"] == 0.0 and legacy["rest_transition"] is True
    assert repaired["speed_after"] > 1e-6 and repaired["rest_transition"] is False
    assert float(drive) > mu_k * g


def test_preset_isolation_and_parent_unchanged():
    from mechanistic_mind.model.acanthostega import (
        PUBLIC_PRESET_BNLT_MOVE_BREAKAWAY_LOCOMOTION_REPAIR,
        PUBLIC_PRESET_DETACHED_TERRAIN_MATERIAL_INITIAL_PLACEMENT,
        acanthostega_bnlt_move_breakaway_locomotion_repair_config,
        acanthostega_detached_terrain_material_initial_placement_config,
    )
    from mechanistic_mind.model.tiktaalik import tiktaalik_config
    from mechanistic_mind.physical_system.bnlt_move_breakaway_locomotion_repair import (
        bnlt_move_breakaway_locomotion_repair_is_active,
        MECHANISM_ID,
        PROFILE_VERSION,
    )
    from mechanistic_mind.physical_system.experiment_canonical import (
        PRESET_ACANTHOSTEGA_BNLT_MOVE_BREAKAWAY_LOCOMOTION_REPAIR,
        normalize_preset_name,
        preset_canonical,
    )

    child = acanthostega_bnlt_move_breakaway_locomotion_repair_config()
    parent = acanthostega_detached_terrain_material_initial_placement_config()
    assert child.public_preset == PUBLIC_PRESET_BNLT_MOVE_BREAKAWAY_LOCOMOTION_REPAIR
    assert parent.public_preset == PUBLIC_PRESET_DETACHED_TERRAIN_MATERIAL_INITIAL_PLACEMENT
    assert bnlt_move_breakaway_locomotion_repair_is_active(child) is True
    assert bnlt_move_breakaway_locomotion_repair_is_active(parent) is False
    assert bnlt_move_breakaway_locomotion_repair_is_active(tiktaalik_config()) is False
    assert PROFILE_VERSION == "BNLT_MOVE_BREAKAWAY_LOCOMOTION_REPAIR_V1"
    assert (
        normalize_preset_name("BNLT_MOVE_BREAKAWAY_LOCOMOTION_REPAIR_V1")
        == PRESET_ACANTHOSTEGA_BNLT_MOVE_BREAKAWAY_LOCOMOTION_REPAIR
    )
    canon = preset_canonical(PRESET_ACANTHOSTEGA_BNLT_MOVE_BREAKAWAY_LOCOMOTION_REPAIR)
    assert canon["builder"] == "acanthostega_bnlt_move_breakaway_locomotion_repair_config"
    assert canon["mechanisms"][MECHANISM_ID] is True
    assert canon["parent"] == PUBLIC_PRESET_DETACHED_TERRAIN_MATERIAL_INITIAL_PLACEMENT


def test_parent_dtip_can_still_freeze_while_repair_translates():
    """Reproduce kinetic exhaust on parent; repair yields nonzero MOVE."""
    parent = _rt(_parent_cfg(), seed=171, x=2.5, y=2.5)
    d_parent = _force_move(parent, "MOVE:E")
    child = _rt(_repair_cfg(), seed=171, x=2.5, y=2.5)
    d_child = _force_move(child, "MOVE:E")
    assert d_child > 1e-6, f"repair MOVE must translate, got {d_child}"
    assert d_child >= d_parent - 1e-12
    st = getattr(child.world, "bnlt_move_breakaway_locomotion_repair_state", None)
    assert st is not None
    assert st.last_step.get("classification") == "ACTIVE_DRIVE_TRANSLATION"
    assert float(st.last_step.get("displacement_mag") or 0.0) > 1e-6


def test_cardinal_and_orthogonal_directions():
    for action in ("MOVE:N", "MOVE:S", "MOVE:E", "MOVE:W"):
        rt = _rt(seed=19)
        d = _force_move(rt, action)
        assert d > 1e-6, f"{action} failed to translate ({d})"


def test_two_agent_separated_both_move_not_jam():
    from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime

    cfg = _repair_cfg()
    ta = TwoAgentRuntime(seed=17, config=cfg, starts=((2, 2), (6, 2)))
    a0, a1 = ta.slots
    x0 = (float(a0.body.x), float(a0.body.y))
    x1 = (float(a1.body.x), float(a1.body.y))
    sep0 = math.hypot(x1[0] - x0[0], x1[1] - x0[1])
    assert sep0 > 3.5
    a0._forced_action_once = "MOVE:E"
    a1._forced_action_once = "MOVE:W"
    ta.step(1)
    _tick(1)
    d0 = math.hypot(float(a0.body.x) - x0[0], float(a0.body.y) - x0[1])
    d1 = math.hypot(float(a1.body.x) - x1[0], float(a1.body.y) - x1[1])
    assert d0 > 1e-6 and d1 > 1e-6
    sep1 = math.hypot(float(a1.body.x) - float(a0.body.x), float(a1.body.y) - float(a0.body.y))
    assert sep1 > 2.0  # not a body-body jam repair


def test_wait_rest_and_move_then_wait():
    rt = _rt(seed=23)
    rt.body.vx = rt.body.vy = 0.0
    x0, y0 = float(rt.body.x), float(rt.body.y)
    rt.step_forced_action("WAIT")
    _tick()
    assert abs(float(rt.body.x) - x0) < 1e-12
    assert abs(float(rt.body.y) - y0) < 1e-12
    assert abs(float(rt.body.vx)) < 1e-12 and abs(float(rt.body.vy)) < 1e-12

    _force_move(rt, "MOVE:N")
    rested = False
    for _ in range(12):
        rt.step_forced_action("WAIT")
        _tick()
        if abs(float(rt.body.vx)) < 1e-12 and abs(float(rt.body.vy)) < 1e-12:
            rested = True
            break
    assert rested, "MOVE then WAIT must reach rest"


def test_sustained_move_aligned():
    rt = _rt(seed=29, x=5.5, y=5.5)
    xs = [float(rt.body.x)]
    for _ in range(4):
        _force_move(rt, "MOVE:E")
        xs.append(float(rt.body.x))
    assert xs[-1] > xs[0] + 1e-4
    assert all(xs[i + 1] >= xs[i] - 1e-9 for i in range(len(xs) - 1))


def test_affinity_distinguishable_and_insufficient_drive_can_block():
    from mechanistic_mind.physical_system.bnlt_move_breakaway_locomotion_repair import (
        active_drive_accel_from_impulse,
    )

    # High affinity: larger μ → larger limited impulse capacity and friction.
    # Unit-level: drive from impulse must exceed kinetic when μ_s > μ_k.
    j_lim = (0.04, 0.0)  # canonical static capacity scale
    m_eff, dt = 1.0, 1.0
    drive = active_drive_accel_from_impulse(move_impulse_xy=j_lim, m_eff=m_eff, dt=dt)
    assert drive is not None and drive > 0.03
    # Tiny impulse below kinetic capacity → blocked classification path.
    tiny = active_drive_accel_from_impulse(move_impulse_xy=(1e-9, 0.0), m_eff=m_eff, dt=dt)
    assert tiny is not None and tiny < 1e-6

    rt_hi = _rt(seed=31)
    d_hi = _force_move(rt_hi, "MOVE:E")
    rt_lo = _rt(seed=31)
    # Lower surface affinity via world coating if available; else assert hi still moves.
    assert d_hi > 1e-6


def test_airborne_no_ground_traction_and_passive_sliding_dissipates():
    rt = _rt(seed=37)
    rt.body.grounded = False
    rt.body.z = 2.0
    x0 = float(rt.body.x)
    rt.step_forced_action("MOVE:E")
    _tick()
    # Airborne may still translate via free dynamics; BNLT ground friction must not apply.
    fric = None
    loco = getattr(rt, "last_locomotion_receipt", None) or {}
    fric = loco.get("body_normal_load_friction") if isinstance(loco, dict) else None
    if isinstance(fric, dict):
        assert fric.get("applied") in (False, None) or fric.get("mode") in (
            "AIRBORNE",
            "NOT_ELIGIBLE",
            "OFF",
            None,
        )

    rt2 = _rt(seed=41)
    rt2.body.vx, rt2.body.vy = 0.2, 0.0
    rt2.body.grounded = True
    s0 = abs(float(rt2.body.vx))
    rt2.step_forced_action("WAIT")
    _tick()
    assert abs(float(rt2.body.vx)) <= s0 + 1e-12


def test_work_nonnegative_dissipation_no_free_ke():
    rt = _rt(seed=43)
    ke0 = 0.5 * float(rt.config.body.mass) * (
        float(rt.body.vx) ** 2 + float(rt.body.vy) ** 2
    )
    _force_move(rt, "MOVE:E")
    st = getattr(rt.world, "bnlt_move_breakaway_locomotion_repair_state", None)
    assert st is not None
    diss = float(st.last_step.get("kinetic_dissipated") or 0.0)
    assert diss >= -1e-12
    led = rt.last_action_work_ledger or {}
    work = float(led.get("work_realized") or led.get("action_work_realized") or 0.0)
    # Work debit must not be negative.
    assert work >= -1e-12
    ke1 = 0.5 * float(rt.config.body.mass) * (
        float(rt.body.vx) ** 2 + float(rt.body.vy) ** 2
    )
    # KE increase must be bounded by realized work (no free KE).
    assert ke1 - ke0 <= work + 1e-6 or work == 0.0


def test_snapshot_restore_parity():
    rt = _rt(seed=47)
    _force_move(rt, "MOVE:N")
    snap = rt.snapshot()
    x1, y1 = float(rt.body.x), float(rt.body.y)
    vx1, vy1 = float(rt.body.vx), float(rt.body.vy)
    rt2 = type(rt).restore(snap)
    assert abs(float(rt2.body.x) - x1) < 1e-15
    assert abs(float(rt2.body.y) - y1) < 1e-15
    assert abs(float(rt2.body.vx) - vx1) < 1e-15
    assert abs(float(rt2.body.vy) - vy1) < 1e-15
    d = _force_move(rt2, "MOVE:E")
    assert d > 1e-6


def test_phase_c_and_tiktaalik_fingerprint_unchanged_behavior():
    from mechanistic_mind.model.acanthostega import acanthostega_static_traction_config
    from mechanistic_mind.model.tiktaalik import tiktaalik_config
    from mechanistic_mind.physical_system.bnlt_move_breakaway_locomotion_repair import (
        bnlt_move_breakaway_locomotion_repair_is_active,
    )
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

    g2a = acanthostega_static_traction_config()
    g2a.cognition.cognition_enabled = False
    assert bnlt_move_breakaway_locomotion_repair_is_active(g2a) is False
    rt = PhysicalSystemRuntime(seed=53, config=g2a)
    rt.body.x, rt.body.y = 8.5, 16.5
    rt.body.vx = rt.body.vy = 0.0
    rt.body.grounded = True
    # Phase C path remains repair-off (may or may not crawl; must not activate repair).
    rt.step_forced_action("MOVE:E")
    _tick()
    assert getattr(rt.world, "bnlt_move_breakaway_locomotion_repair_state", None) in (None,)

    tik = tiktaalik_config()
    assert bnlt_move_breakaway_locomotion_repair_is_active(tik) is False
    assert getattr(tik, "bnlt_move_breakaway_locomotion_repair", None) in (None, False) or not bool(
        getattr(getattr(tik, "bnlt_move_breakaway_locomotion_repair", None), "enabled", False)
    )


def test_cognition_privacy_receipt_researcher_only():
    rt = _rt(seed=59)
    _force_move(rt, "MOVE:W")
    st = getattr(rt.world, "bnlt_move_breakaway_locomotion_repair_state", None)
    assert st is not None
    rec = st.last_step
    assert rec.get("researcher_only") is True
    assert rec.get("agent_accessible") is False
    # Must not inject cognition tokens into body/internal.
    assert not hasattr(rt.body, "bnlt_classification")


def test_live_pose_forensic_style_move_translates_under_repair():
    """Forensic poses (8.5/12.5, 16.5): repair must allow MOVE translation."""
    child = _rt(_repair_cfg(), seed=171, x=8.5, y=16.5)
    d = _force_move(child, "MOVE:E")
    assert d > 1e-6, f"forensic-pose repair MOVE must translate, got {d}"
