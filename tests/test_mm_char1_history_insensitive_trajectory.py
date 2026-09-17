"""MM-CHAR-1 — history-insensitive trajectory characterization (no production mutation)."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "results" / "mm_char1_history_insensitive_trajectory"


def test_pack_and_protocol():
    assert (ROOT / "PROTOCOL.md").exists()
    assert (ROOT / "FINAL_REPORT.md").exists()
    assert (ROOT / "experiment_summary.json").exists()


def test_outcome_body_dominates():
    data = json.loads((ROOT / "experiment_summary.json").read_text())
    c = data["classification"]
    assert c["body_ablation_hops"] == [0, 0, 0, 0, 0]
    assert c["full_hops"] == [3, 3, 3, 3, 3]
    assert c["world_ablation_hops"] == [3, 3, 3, 3, 3]
    assert c["history_organizes_trajectory"] is False
    assert c["path_identical_to_full"]["ablate_memory"] is True
    assert c["path_identical_to_full"]["ablate_reinstatement"] is True
    assert "BODY" in c["primary_organizer"]
    assert c["wall_saturates_all_seeds"] is True


def test_no_production_coupling_mutation():
    from mechanistic_mind.body.embodied_integration import (
        default_mm_int2_integration_config,
        project_neural_drive_antagonistic_axes,
        DRIVE_COUPLING_ANTAGONISTIC,
    )
    assert default_mm_int2_integration_config()["drive_coupling"] == DRIVE_COUPLING_ANTAGONISTIC
    assert project_neural_drive_antagonistic_axes((0.0, -1.0, 0.0)) == (1.0, 0.0, 0.0, 0.0)


def test_threshold_frozen():
    from mechanistic_mind.world_engine.physical_effector import THRESHOLD
    assert THRESHOLD == 0.60
