"""Active locomotion traction vs sliding friction V1 — focused deterministic tests."""
from __future__ import annotations

import math

TICKS = {"n": 0}


def _tick(n: int = 1) -> None:
    TICKS["n"] += int(n)


def _child_cfg():
    from mechanistic_mind.model.acanthostega import (
        acanthostega_active_locomotion_traction_vs_sliding_friction_config,
    )

    cfg = acanthostega_active_locomotion_traction_vs_sliding_friction_config()
    cfg.cognition.cognition_enabled = False
    return cfg


def _parent_cfg():
    from mechanistic_mind.model.acanthostega import (
        acanthostega_bnlt_move_breakaway_locomotion_repair_config,
    )

    cfg = acanthostega_bnlt_move_breakaway_locomotion_repair_config()
    cfg.cognition.cognition_enabled = False
    return cfg


def _rt(cfg=None, seed: int = 17, x: float = 2.5, y: float = 2.5):
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

    rt = PhysicalSystemRuntime(seed=seed, config=cfg or _child_cfg())
    rt.body.x, rt.body.y = float(x), float(y)
    rt.body.vx = rt.body.vy = 0.0
    rt.body.grounded = True
    return rt


def _force_move(rt, action: str = "MOVE:E") -> float:
    x0, y0 = float(rt.body.x), float(rt.body.y)
    rt.step_forced_action(action)
    _tick()
    return float(math.hypot(float(rt.body.x) - x0, float(rt.body.y) - y0))


def test_unit_protect_drive_from_kinetic():
    from mechanistic_mind.physical_system.active_locomotion_traction_vs_sliding_friction import (
        apply_traction_protected_kinetic,
        decompose_traction_protected_velocity,
    )
    from mechanistic_mind.physical_system.free_resource_object_ground_friction import (
        coulomb_kinetic_step,
    )

    m_eff, dt, g = 2.0, 1.0, 0.01818181818181818
    mu_k = 1.75
    mu_s = 2.1875
    j = mu_s * m_eff * g * dt  # ≈ 0.0795
    dv = j / m_eff
    # Trial ≈ drive (MOVE from rest after mild env)
    vx_trial = dv
    option_c = coulomb_kinetic_step(
        vx_trial,
        0.0,
        mu_k=mu_k,
        g=g,
        dt=dt,
        rest_threshold=1e-9,
        drive_accel=dv / dt,
    )
    protected = apply_traction_protected_kinetic(
        vx_trial,
        0.0,
        move_impulse_xy=(j, 0.0),
        m_eff=m_eff,
        mu_k=mu_k,
        g=g,
        dt=dt,
        rest_threshold=1e-9,
    )
    decomp = decompose_traction_protected_velocity(
        vx_trial, 0.0, move_impulse_xy=(j, 0.0), m_eff=m_eff
    )
    assert decomp["has_drive"] and decomp["protected_mag"] > 1e-6
    assert protected["traction_protection_applied"] is True
    assert float(protected["speed_after"]) > float(option_c["speed_after"]) + 1e-4
    assert float(protected["speed_after"]) + 1e-9 >= float(decomp["protected_mag"])


def test_preset_isolation_parent_and_tiktaalik_unchanged():
    from mechanistic_mind.model.acanthostega import (
        PUBLIC_PRESET_ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION,
        PUBLIC_PRESET_BNLT_MOVE_BREAKAWAY_LOCOMOTION_REPAIR,
        PUBLIC_PRESET_REPEATED_CONSERVATIVE_SURFACE_COLUMN_SEPARATION,
        acanthostega_active_locomotion_traction_vs_sliding_friction_config,
        acanthostega_bnlt_move_breakaway_locomotion_repair_config,
        acanthostega_repeated_conservative_surface_column_separation_config,
    )
    from mechanistic_mind.model.tiktaalik import tiktaalik_config
    from mechanistic_mind.physical_system.active_locomotion_traction_vs_sliding_friction import (
        MECHANISM_ID,
        PROFILE_VERSION,
        active_locomotion_traction_vs_sliding_friction_is_active,
    )
    from mechanistic_mind.physical_system.bnlt_move_breakaway_locomotion_repair import (
        bnlt_move_breakaway_locomotion_repair_is_active,
    )
    from mechanistic_mind.physical_system.repeated_conservative_surface_column_separation import (
        repeated_conservative_surface_column_separation_is_active,
    )
    from mechanistic_mind.physical_system.experiment_canonical import (
        PRESET_ACANTHOSTEGA_ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION,
        is_acanthostega_public_preset,
        normalize_preset_name,
        preset_canonical,
    )

    child = acanthostega_active_locomotion_traction_vs_sliding_friction_config()
    parent = acanthostega_repeated_conservative_surface_column_separation_config()
    grand = acanthostega_bnlt_move_breakaway_locomotion_repair_config()
    assert child.public_preset == PUBLIC_PRESET_ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION
    assert parent.public_preset == PUBLIC_PRESET_REPEATED_CONSERVATIVE_SURFACE_COLUMN_SEPARATION
    assert grand.public_preset == PUBLIC_PRESET_BNLT_MOVE_BREAKAWAY_LOCOMOTION_REPAIR
    assert active_locomotion_traction_vs_sliding_friction_is_active(child) is True
    assert active_locomotion_traction_vs_sliding_friction_is_active(parent) is False
    assert active_locomotion_traction_vs_sliding_friction_is_active(grand) is False
    assert repeated_conservative_surface_column_separation_is_active(child) is True
    assert repeated_conservative_surface_column_separation_is_active(parent) is True
    assert repeated_conservative_surface_column_separation_is_active(grand) is False
    assert bnlt_move_breakaway_locomotion_repair_is_active(child) is True
    assert bnlt_move_breakaway_locomotion_repair_is_active(parent) is True
    assert bnlt_move_breakaway_locomotion_repair_is_active(grand) is True
    assert active_locomotion_traction_vs_sliding_friction_is_active(tiktaalik_config()) is False
    assert PROFILE_VERSION == "ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION_V1"
    assert (
        normalize_preset_name("ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION_V1")
        == PRESET_ACANTHOSTEGA_ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION
    )
    assert is_acanthostega_public_preset(
        PRESET_ACANTHOSTEGA_ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION
    )
    canon = preset_canonical(PRESET_ACANTHOSTEGA_ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION)
    assert canon["builder"] == "acanthostega_active_locomotion_traction_vs_sliding_friction_config"
    assert canon["mechanisms"][MECHANISM_ID] is True
    assert canon["parent"] == PUBLIC_PRESET_REPEATED_CONSERVATIVE_SURFACE_COLUMN_SEPARATION
    assert canon["mechanisms"].get("repeated_conservative_surface_column_separation") is True


def test_child_moves_farther_than_bnlt_parent_microslide():
    parent = _rt(_parent_cfg(), seed=171, x=2.5, y=2.5)
    d_parent = _force_move(parent, "MOVE:E")
    child = _rt(_child_cfg(), seed=171, x=2.5, y=2.5)
    d_child = _force_move(child, "MOVE:E")
    assert d_child > 1e-6
    assert d_child > d_parent + 1e-4, f"child {d_child} should beat parent microslide {d_parent}"
    st = getattr(child.world, "active_locomotion_traction_vs_sliding_friction_state", None)
    assert st is not None
    assert st.counters.get("traction_protect_ticks", 0) >= 1


def test_wait_still_rests_and_mu_not_weakened():
    rt = _rt(seed=23)
    rt.body.vx = rt.body.vy = 0.0
    x0, y0 = float(rt.body.x), float(rt.body.y)
    rt.step_forced_action("WAIT")
    _tick()
    assert abs(float(rt.body.x) - x0) < 1e-12
    assert abs(float(rt.body.y) - y0) < 1e-12
    cfg = rt.config.active_locomotion_traction_vs_sliding_friction
    assert cfg.to_dict()["mu_k_weakened"] is False
    assert cfg.to_dict()["magic_displacement_floor"] is False
    assert cfg.to_dict()["move_strength_inflated"] is False


def test_cardinal_moves_and_sustained_progress():
    for action in ("MOVE:N", "MOVE:S", "MOVE:E", "MOVE:W"):
        rt = _rt(seed=19)
        assert _force_move(rt, action) > 1e-5, action
    rt = _rt(seed=29, x=5.5, y=5.5)
    xs = [float(rt.body.x)]
    for _ in range(4):
        _force_move(rt, "MOVE:E")
        xs.append(float(rt.body.x))
    assert xs[-1] > xs[0] + 0.05


def test_identity_stamp_acanthostega_not_tiktaalik():
    from mechanistic_mind.model.lines import identity_from_public_preset, stamp_config_from_preset
    from mechanistic_mind.model.acanthostega import (
        PUBLIC_PRESET_ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION,
        acanthostega_active_locomotion_traction_vs_sliding_friction_config,
    )

    cfg = acanthostega_active_locomotion_traction_vs_sliding_friction_config()
    stamp_config_from_preset(cfg, PUBLIC_PRESET_ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION)
    assert cfg.model_line == "ACANTHOSTEGA"
    assert cfg.public_preset == PUBLIC_PRESET_ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION
    meta = identity_from_public_preset(
        PUBLIC_PRESET_ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION, cfg
    )
    assert meta["model_line"] == "ACANTHOSTEGA"
    assert "ACTIVE_LOCOMOTION_TRACTION" in str(meta.get("public_preset") or "")
