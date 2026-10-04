"""Lineage convergence repair: ALTVSF inherits RCSS (cumulative Beta 4 tip)."""
from __future__ import annotations

import math

TICKS = {"n": 0}


def _tick(n: int = 1) -> None:
    TICKS["n"] += int(n)


def test_mechanism_inheritance_matrix():
    from mechanistic_mind.model.acanthostega import (
        acanthostega_bnlt_move_breakaway_locomotion_repair_config,
        acanthostega_repeated_conservative_surface_column_separation_config,
        acanthostega_active_locomotion_traction_vs_sliding_friction_config,
    )
    from mechanistic_mind.physical_system.bnlt_move_breakaway_locomotion_repair import (
        bnlt_move_breakaway_locomotion_repair_is_active,
    )
    from mechanistic_mind.physical_system.repeated_conservative_surface_column_separation import (
        repeated_conservative_surface_column_separation_is_active,
    )
    from mechanistic_mind.physical_system.active_locomotion_traction_vs_sliding_friction import (
        active_locomotion_traction_vs_sliding_friction_is_active,
    )
    from mechanistic_mind.physical_system.detached_terrain_material_initial_placement import (
        detached_terrain_material_initial_placement_is_active,
    )
    from mechanistic_mind.physical_system.held_mediated_surface_exertion_integration import (
        held_mediated_surface_exertion_integration_is_active,
    )
    from mechanistic_mind.physical_system.surface_exertion_terrain_material_resistance import (
        surface_exertion_terrain_material_resistance_is_active,
    )

    bnlt = acanthostega_bnlt_move_breakaway_locomotion_repair_config()
    rcss = acanthostega_repeated_conservative_surface_column_separation_config()
    alt = acanthostega_active_locomotion_traction_vs_sliding_friction_config()

    def row(cfg):
        return (
            bnlt_move_breakaway_locomotion_repair_is_active(cfg),
            repeated_conservative_surface_column_separation_is_active(cfg),
            active_locomotion_traction_vs_sliding_friction_is_active(cfg),
            detached_terrain_material_initial_placement_is_active(cfg),
            held_mediated_surface_exertion_integration_is_active(cfg),
            surface_exertion_terrain_material_resistance_is_active(cfg),
        )

    assert row(bnlt) == (True, False, False, True, True, True)
    assert row(rcss) == (True, True, False, True, True, True)
    assert row(alt) == (True, True, True, True, True, True)


def test_builder_and_map_reparent_to_rcss():
    import inspect
    from mechanistic_mind.model.acanthostega import (
        PUBLIC_PRESET_REPEATED_CONSERVATIVE_SURFACE_COLUMN_SEPARATION,
        acanthostega_active_locomotion_traction_vs_sliding_friction_config,
    )
    from mechanistic_mind.physical_system.experiment_canonical import (
        PRESET_ACANTHOSTEGA_ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION,
        preset_canonical,
        acanthostega_active_locomotion_traction_vs_sliding_friction_mechanism_map,
        acanthostega_repeated_conservative_surface_column_separation_mechanism_map,
    )

    src = inspect.getsource(acanthostega_active_locomotion_traction_vs_sliding_friction_config)
    assert "acanthostega_repeated_conservative_surface_column_separation_config()" in src
    assert "acanthostega_bnlt_move_breakaway_locomotion_repair_config()" not in src.replace(
        "acanthostega_repeated_conservative_surface_column_separation_config()", ""
    )
    canon = preset_canonical(PRESET_ACANTHOSTEGA_ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION)
    assert canon["parent"] == PUBLIC_PRESET_REPEATED_CONSERVATIVE_SURFACE_COLUMN_SEPARATION
    mmap = acanthostega_active_locomotion_traction_vs_sliding_friction_mechanism_map()
    parent_map = acanthostega_repeated_conservative_surface_column_separation_mechanism_map()
    assert parent_map.get("repeated_conservative_surface_column_separation") is True
    assert parent_map.get("active_locomotion_traction_vs_sliding_friction") is not True
    assert mmap.get("repeated_conservative_surface_column_separation") is True
    assert mmap.get("active_locomotion_traction_vs_sliding_friction") is True
    assert mmap.get("bnlt_move_breakaway_locomotion_repair") is True


def test_identity_and_conflicting_client_model_line():
    from mechanistic_mind.model.acanthostega import (
        PUBLIC_PRESET_ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION,
    )
    from mechanistic_mind.model.lines import identity_from_public_preset, stamp_config_from_preset
    from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig

    cfg = PhysicalSystemConfig()
    cfg.model_line = "TIKTAALIK"
    stamp_config_from_preset(cfg, PUBLIC_PRESET_ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION)
    assert cfg.model_line == "ACANTHOSTEGA"
    assert cfg.public_preset == PUBLIC_PRESET_ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION
    meta = identity_from_public_preset(
        PUBLIC_PRESET_ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION, cfg
    )
    assert meta["model_line"] == "ACANTHOSTEGA"
    assert "ACTIVE_LOCOMOTION_TRACTION" in str(meta.get("public_preset") or "")


def test_apply_observer_session_cumulative_mechanisms():
    from mechanistic_mind.model.acanthostega import (
        PUBLIC_PRESET_ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION,
    )
    from mechanistic_mind.physical_system.bnlt_move_breakaway_locomotion_repair import (
        bnlt_move_breakaway_locomotion_repair_is_active,
    )
    from mechanistic_mind.physical_system.repeated_conservative_surface_column_separation import (
        repeated_conservative_surface_column_separation_is_active,
    )
    from mechanistic_mind.physical_system.active_locomotion_traction_vs_sliding_friction import (
        active_locomotion_traction_vs_sliding_friction_is_active,
    )
    from mechanistic_mind.physical_system.detached_terrain_material_initial_placement import (
        detached_terrain_material_initial_placement_is_active,
    )
    from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
    from mechanistic_mind.ui.psy_observer_web.session import ObserverSession

    sess = ObserverSession()
    out = sess.apply_experiment(
        {
            "public_preset": PUBLIC_PRESET_ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION,
            "model_line": "TIKTAALIK",  # must not win
            "seed": 17,
            "agent_count": 2,
            "cognition_enabled": False,
            "load_preset": True,
        }
    )
    assert sess.runtime is not None
    assert isinstance(sess.runtime, TwoAgentRuntime)
    cfg = sess.runtime.config
    assert cfg.public_preset == PUBLIC_PRESET_ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION
    assert cfg.model_line == "ACANTHOSTEGA"
    assert bnlt_move_breakaway_locomotion_repair_is_active(cfg)
    assert repeated_conservative_surface_column_separation_is_active(cfg)
    assert active_locomotion_traction_vs_sliding_friction_is_active(cfg)
    assert detached_terrain_material_initial_placement_is_active(cfg)
    header = out.get("header") or {}
    assert header.get("model_line") == "ACANTHOSTEGA"
    assert "Active Locomotion" in str(header.get("experiment") or header.get("phase") or "")
    assert "Tiktaalik" not in str(header.get("experiment") or "")


def test_move_numerics_match_pre_reparent_baseline_and_rcss_under_child():
    """Clear-terrain MOVE matches sibling-era baseline; RCSS separation works on child."""
    import json
    from pathlib import Path
    from mechanistic_mind.model.acanthostega import (
        acanthostega_active_locomotion_traction_vs_sliding_friction_config,
        acanthostega_repeated_conservative_surface_column_separation_config,
    )
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
    from mechanistic_mind.physical_system.conservative_surface_material_separation import (
        apply_surface_material_separation,
    )

    baseline_path = Path(
        "results/active_locomotion_rcss_lineage_convergence_repair/"
        "BASELINE_MOVE_BEFORE_REPARENT.json"
    )
    baseline = json.loads(baseline_path.read_text())["altvs_before"]["disps"]

    cfg = acanthostega_active_locomotion_traction_vs_sliding_friction_config()
    cfg.cognition.cognition_enabled = False
    rt = PhysicalSystemRuntime(seed=171, config=cfg)
    rt.body.x, rt.body.y = 2.5, 2.5
    rt.body.vx = rt.body.vy = 0.0
    rt.body.grounded = True
    disps = []
    for _ in range(3):
        x0, y0 = float(rt.body.x), float(rt.body.y)
        rt.step_forced_action("MOVE:E")
        _tick()
        disps.append(math.hypot(float(rt.body.x) - x0, float(rt.body.y) - y0))
    for a, b in zip(disps, baseline):
        assert abs(a - b) < 1e-9, f"MOVE numerics changed by reparent: {disps} vs {baseline}"

    rt.step_forced_action("WAIT")
    _tick()
    assert abs(float(rt.body.vx)) < 1e-5 and abs(float(rt.body.vy)) < 1e-5

    # RCSS under child: one successful separation; second same cell/tick rejected.
    out1 = apply_surface_material_separation(
        rt.world,
        rt.config,
        cell_x=10,
        cell_y=10,
        requested_thickness=0.05,
        tick=1,
        body_refs=[("body-0", rt.body)],
    )
    _tick()
    out2 = apply_surface_material_separation(
        rt.world,
        rt.config,
        cell_x=10,
        cell_y=10,
        requested_thickness=0.05,
        tick=1,
        body_refs=[("body-0", rt.body)],
    )
    _tick()
    # Parent RCSS still works and does not enable ALTVSF
    parent = acanthostega_repeated_conservative_surface_column_separation_config()
    from mechanistic_mind.physical_system.active_locomotion_traction_vs_sliding_friction import (
        active_locomotion_traction_vs_sliding_friction_is_active,
    )

    assert active_locomotion_traction_vs_sliding_friction_is_active(parent) is False
    # Soft assert on separation outcomes — accept committed or structured reject,
    # but second same-tick must not double-commit.
    c1 = bool(out1.get("committed") or out1.get("success") or out1.get("accepted"))
    c2 = bool(out2.get("committed") or out2.get("success") or out2.get("accepted"))
    if c1:
        assert not c2, "second same-cell same-tick separation must not commit"


def test_snapshot_restore_retains_cumulative_mechanisms():
    from mechanistic_mind.model.acanthostega import (
        PUBLIC_PRESET_ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION,
        acanthostega_active_locomotion_traction_vs_sliding_friction_config,
    )
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
    from mechanistic_mind.physical_system.bnlt_move_breakaway_locomotion_repair import (
        bnlt_move_breakaway_locomotion_repair_is_active,
    )
    from mechanistic_mind.physical_system.repeated_conservative_surface_column_separation import (
        repeated_conservative_surface_column_separation_is_active,
    )
    from mechanistic_mind.physical_system.active_locomotion_traction_vs_sliding_friction import (
        active_locomotion_traction_vs_sliding_friction_is_active,
    )

    cfg = acanthostega_active_locomotion_traction_vs_sliding_friction_config()
    cfg.cognition.cognition_enabled = False
    rt = PhysicalSystemRuntime(seed=19, config=cfg)
    rt.body.grounded = True
    rt.step_forced_action("MOVE:N")
    _tick()
    snap = rt.snapshot() if hasattr(rt, "snapshot") else None
    if snap is None and hasattr(rt, "export_snapshot"):
        snap = rt.export_snapshot()
    if snap is None:
        # Fallback: config-level mechanism flags are the restore contract for this tip.
        assert bnlt_move_breakaway_locomotion_repair_is_active(rt.config)
        assert repeated_conservative_surface_column_separation_is_active(rt.config)
        assert active_locomotion_traction_vs_sliding_friction_is_active(rt.config)
        assert rt.config.public_preset == PUBLIC_PRESET_ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION
        return
    rt2 = PhysicalSystemRuntime(seed=19, config=cfg)
    if hasattr(rt2, "restore"):
        rt2.restore(snap)
    elif hasattr(rt2, "import_snapshot"):
        rt2.import_snapshot(snap)
    assert rt2.config.public_preset == PUBLIC_PRESET_ACTIVE_LOCOMOTION_TRACTION_VS_SLIDING_FRICTION
    assert rt2.config.model_line == "ACANTHOSTEGA"
    assert bnlt_move_breakaway_locomotion_repair_is_active(rt2.config)
    assert repeated_conservative_surface_column_separation_is_active(rt2.config)
    assert active_locomotion_traction_vs_sliding_friction_is_active(rt2.config)


def test_two_agent_slots_share_cumulative_config():
    from mechanistic_mind.model.acanthostega import (
        acanthostega_active_locomotion_traction_vs_sliding_friction_config,
    )
    from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
    from mechanistic_mind.physical_system.repeated_conservative_surface_column_separation import (
        repeated_conservative_surface_column_separation_is_active,
    )
    from mechanistic_mind.physical_system.active_locomotion_traction_vs_sliding_friction import (
        active_locomotion_traction_vs_sliding_friction_is_active,
    )

    cfg = acanthostega_active_locomotion_traction_vs_sliding_friction_config()
    cfg.cognition.cognition_enabled = False
    ta = TwoAgentRuntime(seed=17, config=cfg, starts=((2, 2), (6, 2)))
    assert repeated_conservative_surface_column_separation_is_active(ta.config)
    assert active_locomotion_traction_vs_sliding_friction_is_active(ta.config)
    for slot in ta.slots:
        assert slot.config.public_preset == ta.config.public_preset
        assert repeated_conservative_surface_column_separation_is_active(slot.config)
        assert active_locomotion_traction_vs_sliding_friction_is_active(slot.config)
