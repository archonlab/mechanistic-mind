"""Tests for LOCAL_PHYSICAL_COHERENCE_01 — wrap, locality, WAIT classes."""
from __future__ import annotations

from copy import deepcopy

import pytest

from mechanistic_mind.physical_system.ecology_presets import (
    ECOLOGY_CALIBRATED_TEMPORAL,
    make_ecology_config,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime, _wrap_delta_1d
from mechanistic_mind.research.local_physical_coherence import (
    LOCAL_SENSORY_HORIZON,
    RESTING_SPEED_THRESHOLD,
    calibrated_cfg,
    local_context_replacement_metrics,
    moore_neighborhood,
    neighborhood_identity,
    run_forced_trace,
    trajectory_metrics_extended,
)
from mechanistic_mind.research.world_timescale import wrap_delta


def test_wrap_delta_east_west_sign():
    assert abs(wrap_delta(31.9, 0.1, 32) - 0.2) < 1e-9
    assert abs(wrap_delta(0.1, 31.9, 32) + 0.2) < 1e-9


def test_wrap_delta_north_south():
    assert abs(wrap_delta(31.9, 0.1, 32) - 0.2) < 1e-9
    assert abs(wrap_delta(0.1, 31.9, 32) + 0.2) < 1e-9


def test_diagonal_wrap_path_not_huge():
    xs = [31.8, 0.2]
    ys = [31.8, 0.2]
    m = trajectory_metrics_extended(xs, ys, width=32, height=32)
    assert m["path_length_euclidean"] < 1.0
    assert m["boundary_crossings_x"] == 1
    assert m["boundary_crossings_y"] == 1


def test_multiple_wraps():
    xs = [31.5, 0.2, 31.6, 0.3, 31.7, 0.4]
    ys = [10.0] * 6
    m = trajectory_metrics_extended(xs, ys, width=32, height=32)
    assert m["path_length_euclidean"] < 5.0
    assert m["boundary_crossings_x"] >= 4


def test_moore_neighborhood_torus():
    nb = moore_neighborhood(0, 0, 32, 32)
    assert len(nb) == 9
    assert (31, 31) in nb
    assert (1, 0) in nb
    assert neighborhood_identity(0, 0, 32, 32) == frozenset(nb)


def test_local_context_replacement_on_translation():
    xs = [5.2] * 10
    ys = [5.2] * 10
    m0 = local_context_replacement_metrics(xs, ys, width=32, height=32)
    assert m0["center_cell_changes"] == 0
    xs2 = [5.2, 5.2, 12.2, 20.2]
    ys2 = [5.2, 5.2, 5.2, 5.2]
    m1 = local_context_replacement_metrics(xs2, ys2, width=32, height=32)
    assert m1["center_cell_changes"] >= 2
    assert m1["final_neighbor_retention"] < 1.0


def test_resting_vs_kinetic_wait_classification():
    cfg = calibrated_cfg(cognition=False, terrain=False, ambient=False, thermal_flow=False)
    rest = run_forced_trace(cfg, seed=17, ticks=50, action="WAIT")
    assert rest["wait_class"] == "RESTING_WAIT"
    assert rest["initial_speed"] < RESTING_SPEED_THRESHOLD
    kin = run_forced_trace(cfg, seed=17, ticks=50, action="WAIT", initial_impulse=(0.4, 0.0))
    assert kin["wait_class"] == "KINETIC_WAIT"
    assert kin["trajectory"]["path_length_euclidean"] > rest["trajectory"]["path_length_euclidean"]


def test_velocity_path_consistency_ok_for_smooth_trace():
    xs = [float(i) * 0.01 for i in range(100)]
    ys = [16.0] * 100
    speeds = [0.01] * 100
    m = trajectory_metrics_extended(xs, ys, width=32, height=32, speeds=speeds)
    assert m["path_vs_velocity_consistency"] in ("OK", "NOT_AVAILABLE")
    assert m["path_length_euclidean"] == pytest.approx(0.99, abs=0.02)


def test_no_cognition_gt_leak_calibrated():
    cfg = make_ecology_config(ECOLOGY_CALIBRATED_TEMPORAL, trickle=0.0)
    cfg.cognition.cognition_enabled = True
    rt = PhysicalSystemRuntime(seed=17, config=deepcopy(cfg))
    rt.step_forced_action("WAIT")
    banned = ("terrain_potential", "ambient_Fx", "resource_suitability", "obstacle", "food_label")
    blob = repr(rt.cognition)
    for b in banned:
        assert b not in blob


def test_sensory_horizon_contract_shape():
    assert LOCAL_SENSORY_HORIZON["moore_radius"] == 1
    assert LOCAL_SENSORY_HORIZON["neighbor_count"] == 8
    assert "future_chain" in LOCAL_SENSORY_HORIZON["own_cell_vs_neighbor"]


def test_two_agent_distance_uses_wrap():
    assert abs(_wrap_delta_1d(31.9, 0.1, 32) - 0.2) < 1e-9
    cfg = calibrated_cfg(cognition=False)
    rt = TwoAgentRuntime(seed=17, config=cfg, starts=((31, 16), (30, 16)))
    rt.slots[0].body.x = 31.7
    rt.slots[0].body.y = 16.0
    rt.slots[0].body.vx = 0.3
    for _ in range(20):
        rt.step(1)
    d = float(rt._agent_stats[0]["distance_travelled"])
    assert d < 15.0
