"""MM-TRANS-LOCAL-1 archaeology tests — zero production change."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path("results/mm_trans_local1_local_world_body_interaction_archaeology")


def test_pack():
    assert (ROOT / "FINAL_REPORT.md").exists()
    assert (ROOT / "PHYSICAL_ACCESS_MATRIX.md").exists()
    s = json.loads((ROOT / "experiment_summary.json").read_text())
    assert s["freeze_ok"]
    assert s["det"] == 0.0


def test_matched_mean_no_side():
    s = json.loads((ROOT / "experiment_summary.json").read_text())
    for k in (
        "material_side_distinguishable",
        "thermal_side_distinguishable",
        "flow_side_distinguishable",
        "wave_side_distinguishable",
    ):
        assert s[k] is False
    assert s["temporal_distinguishable"] is True


def test_outcome():
    text = (ROOT / "FINAL_REPORT.md").read_text()
    assert "LOCAL_WORLD_INTERACTION_COLLAPSES_TO_LUMPED_BODY" in text
    assert "STOP" in text
