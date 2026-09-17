"""MM-INT-2 — physical nervous×effector coupling redesign."""
from __future__ import annotations

import json
from pathlib import Path

from mechanistic_mind.body.embodied_integration import (
    DRIVE_COUPLING_ANTAGONISTIC,
    DRIVE_COUPLING_LEGACY,
    DRIVE_PROJECTION,
    default_embodied_integration_config,
    default_mm_int2_integration_config,
    project_neural_drive,
    project_neural_drive_antagonistic_axes,
    project_neural_drive_legacy,
)
from mechanistic_mind.world_engine.physical_effector import (
    DEFAULT_SITES,
    THRESHOLD,
    DECAY,
    resolve_hop,
    resultant,
    step_e,
)
from worlds.rich_autonomous_signal_ecology_v01 import (
    HORIZON,
    SEEDS,
    make_rich_ecology_world,
)

ROOT = Path(__file__).resolve().parents[1] / "results" / "mm_int2_physical_nervous_effector_coupling"


def test_design_freeze_exists_before_behavior_pack():
    assert (ROOT / "DESIGN_FREEZE.md").exists()
    assert "have NOT been used" in (ROOT / "DESIGN_FREEZE.md").read_text()
    assert (ROOT / "FINAL_REPORT.md").exists()
    assert (ROOT / "experiment_summary.json").exists()


def test_one_candidate_antagonistic():
    assert "antagonistic_axes_v1" in (ROOT / "CANDIDATE_COUPLING.md").read_text()
    assert (ROOT / "REJECTED_ALTERNATIVES.md").exists()


def test_coupling_equation_exactness():
    assert project_neural_drive_antagonistic_axes((0.0, 0.0, 0.0)) == (0.0, 0.0, 0.0, 0.0)
    assert project_neural_drive_antagonistic_axes((1.0, 0.0, 0.0)) == (0.0, 0.0, 1.0, 0.0)
    assert project_neural_drive_antagonistic_axes((-1.0, 0.0, 0.0)) == (0.0, 1.0, 0.0, 0.0)
    assert project_neural_drive_antagonistic_axes((0.0, 1.0, 0.0)) == (0.0, 0.0, 0.0, 1.0)
    assert project_neural_drive_antagonistic_axes((0.0, -1.0, 0.0)) == (1.0, 0.0, 0.0, 0.0)
    # N2 unused
    assert project_neural_drive_antagonistic_axes((0.0, 0.0, 1.0)) == (0.0, 0.0, 0.0, 0.0)


def test_zero_state_and_boundedness():
    for n in [(0, 0, 0), (1, 1, 1), (-1, -1, -1), (0.5, -0.7, 0.2)]:
        d = project_neural_drive_antagonistic_axes(n)
        assert all(0.0 <= x <= 1.0 for x in d)


def test_sign_and_symmetry():
    d_pos = project_neural_drive_antagonistic_axes((0.4, 0.0, 0.0))
    d_neg = project_neural_drive_antagonistic_axes((-0.4, 0.0, 0.0))
    assert d_pos[2] == d_neg[1] and d_pos[1] == d_neg[2]
    d_pos1 = project_neural_drive_antagonistic_axes((0.0, 0.4, 0.0))
    d_neg1 = project_neural_drive_antagonistic_axes((0.0, -0.4, 0.0))
    assert d_pos1[3] == d_neg1[0] and d_pos1[0] == d_neg1[3]


def test_dimensionality_sites_order():
    assert DEFAULT_SITES == ((0, -1), (-1, 0), (1, 0), (0, 1))


def test_legacy_preserved_and_default():
    cfg = default_embodied_integration_config()
    assert cfg["drive_coupling"] == DRIVE_COUPLING_LEGACY
    assert default_mm_int2_integration_config()["drive_coupling"] == DRIVE_COUPLING_ANTAGONISTIC
    d = project_neural_drive((0.5, -0.2, 0.1))  # default legacy
    assert d == project_neural_drive_legacy((0.5, -0.2, 0.1))
    assert DRIVE_PROJECTION[0][0] == 0.35


def test_no_threshold_or_decay_mutation():
    assert THRESHOLD == 0.60
    assert DECAY == 0.50


def test_historical_pulse_still_works_via_effector():
    e = (0.0, 0.0, 0.0, 0.0)
    for _ in range(5):
        e = step_e(e, (1.0, 0.0, 0.0, 0.0))
    hop, rule = resolve_hop(resultant(e, DEFAULT_SITES))
    assert hop != (0, 0)


def test_structural_reachability_alone_sites():
    for n in [(1.0, 0.0, 0.0), (-1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, -1.0, 0.0)]:
        d = project_neural_drive_antagonistic_axes(n)
        e = (0.0, 0.0, 0.0, 0.0)
        for _ in range(20):
            e = step_e(e, d)
        hop, _ = resolve_hop(resultant(e, DEFAULT_SITES))
        assert hop != (0, 0)


def test_world_makers_modes():
    w_leg = make_rich_ecology_world()
    assert w_leg.body_config.embodied_integration_config["drive_coupling"] == DRIVE_COUPLING_LEGACY
    w_new = make_rich_ecology_world(mm_int2=True)
    assert w_new.body_config.embodied_integration_config["drive_coupling"] == DRIVE_COUPLING_ANTAGONISTIC


def test_frozen_seeds_horizon():
    assert HORIZON == 400
    assert tuple(SEEDS) == (17, 23, 41, 59, 83)


def test_experiment_outcome_contract():
    data = json.loads((ROOT / "experiment_summary.json").read_text())
    c = data["classification"]
    assert c["hops_legacy"] == [0, 0, 0, 0, 0]
    assert all(h >= 1 for h in c["hops_int2"])
    assert c["potato"].startswith("P5") or c["potato"].startswith("P6")
    assert data["natural_replay"]["aggregate"]["D_old_global_max"] < 0.3
    assert data["natural_replay"]["aggregate"]["D_new_global_max"] >= 0.3
    assert c["memory_affects_trajectory"] is False  # observed this run
    assert "PHYSICAL_EXPRESSION" in c["outcome"] or "HISTORY" in c["outcome"]


def test_pack_files_present():
    required = [
        "SOURCE_ARCHAEOLOGY.md",
        "DESIGN_FREEZE.md",
        "IMPLEMENTATION_REPORT.md",
        "STRUCTURAL_TESTS.md",
        "NATURAL_REPLAY.md",
        "AUTONOMOUS_RUN.md",
        "LEGACY_CONTROL.md",
        "MEMORY_ABLATION.md",
        "REINSTATEMENT_ABLATION.md",
        "CAUSAL_LOOP_AUDIT.md",
        "SEMANTIC_LEAK_AUDIT.md",
        "INFORMATION_LEAK_AUDIT.md",
        "CLAIM_BOUNDARY.md",
        "NEXT_FRONTIER.md",
        "FINAL_REPORT.md",
    ]
    for name in required:
        assert (ROOT / name).exists(), name
