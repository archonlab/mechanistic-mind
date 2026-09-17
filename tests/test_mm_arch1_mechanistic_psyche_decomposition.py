"""MM-ARCH-1 — mechanistic psyche decomposition (zero production mutation)."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "results" / "mm_arch1_mechanistic_psyche_decomposition"

REQUIRED = [
    "SOURCE_ARCHAEOLOGY.md", "ACTUAL_CAUSAL_GRAPH.md", "actual_causal_graph.json",
    "MODULE_INVENTORY.md", "EDGE_INVENTORY.md", "BODY_N_INTERFACE_AUDIT.md",
    "TONIC_BIAS_DECOMPOSITION.md", "HISTORY_DIFFERENCE_FATE.md", "MOTOR_BASIN_ANALYSIS.md",
    "NECESSITY_MATRIX.md", "MINIMAL_CAUSAL_CORE.md", "PSYCHE_BOUNDARY_AUDIT.md",
    "FINAL_REPORT.md", "CAUSAL_CONTRIBUTION_MATRIX.csv",
]

def test_pack_complete():
    for name in REQUIRED:
        assert (ROOT / name).exists(), name

def test_zero_production_mutation_markers():
    from mechanistic_mind.body.embodied_integration import (
        default_mm_int2_integration_config, project_neural_drive_antagonistic_axes, REINSTATEMENT_GAIN,
    )
    from mechanistic_mind.world_engine.physical_effector import THRESHOLD
    assert THRESHOLD == 0.60
    assert REINSTATEMENT_GAIN == 0.12
    assert default_mm_int2_integration_config()["drive_coupling"] == "antagonistic_axes_v1"
    assert project_neural_drive_antagonistic_axes((0.0, -1.0, 0.0))[0] == 1.0

def test_graph_and_summary_contracts():
    g = json.loads((ROOT / "actual_causal_graph.json").read_text())
    assert len(g["nodes"]) >= 10
    assert len(g["edges"]) >= 10
    s = json.loads((ROOT / "experiment_summary.json").read_text())
    assert s["conditions"]["ablate_body"][0]["hops"] == 0
    assert s["conditions"]["full"][0]["hops"] == 3
    assert s["conditions"]["ablate_memory"][0]["final"] == s["conditions"]["full"][0]["final"]
    assert s["history_fate_seed17"]["hop_always_same"] is True
    # BODY dominates ΔN
    db = s["tonic"]["delta_N_from_body"]
    dm = s["tonic"]["delta_N_from_mem"]
    assert abs(db[1]) > abs(dm[1])

def test_final_report_outcome():
    text = (ROOT / "FINAL_REPORT.md").read_text()
    assert "PARALLEL_OR_WEAKLY_INTEGRATED" in text
    assert "production architecture changed? NO" in text
    assert "STOP" in text
