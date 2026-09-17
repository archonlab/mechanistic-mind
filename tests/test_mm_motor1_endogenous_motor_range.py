"""MM-MOTOR-1 diagnostics — no production mutation."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
from mechanistic_mind.body.embodied_integration import DRIVE_PROJECTION, project_neural_drive
from mechanistic_mind.world_engine.physical_effector import (
    step_e, resultant, resolve_hop, THRESHOLD, DECAY, DEFAULT_SITES,
)

ROOT = Path(__file__).resolve().parents[1] / "results" / "mm_motor1_endogenous_motor_range"

def test_results_pack_exists():
    assert (ROOT / "FINAL_REPORT.md").exists()
    assert (ROOT / "profile_summary.json").exists()
    assert (ROOT / "FIRST_FAILURE.md").exists()

def test_threshold_unchanged():
    assert THRESHOLD == 0.60
    assert DECAY == 0.50

def test_historical_pulse_still_hops():
    e = (0.0, 0.0, 0.0, 0.0)
    for _ in range(5):
        e = step_e(e, (1.0, 0.0, 0.0, 0.0))
    q = resultant(e, DEFAULT_SITES)
    hop, rule = resolve_hop(q)
    assert hop != (0, 0)
    assert rule == "AXIS_Y"

def test_natural_profile_subthreshold():
    data = json.loads((ROOT / "profile_summary.json").read_text())
    assert data["aggregate"]["margin"]["any_positive"] is False
    assert data["natural_support"]["natural_D_global_max"] < 0.3
    assert data["aggregate"]["hop_count"] == 0

def test_projection_relu_and_bound():
    d = project_neural_drive((1.0, 1.0, 1.0))
    assert all(x >= 0.0 for x in d)
    assert max(d) <= 1.0 + 1e-12

def test_norm_trap_protection_componentwise_in_profile():
    data = json.loads((ROOT / "profile_summary.json").read_text())
    # component-wise min/max present (not only norms)
    assert "min" in data["aggregate"]["D"] and "max" in data["aggregate"]["D"]
    assert len(data["aggregate"]["D"]["max"]) == 4

def test_no_production_mutation_markers():
    # DRIVE_PROJECTION frozen values
    assert DRIVE_PROJECTION[0][0] == 0.35
