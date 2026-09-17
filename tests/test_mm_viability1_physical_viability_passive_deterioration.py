"""MM-VIABILITY-1 research tests — zero production change."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path("results/mm_viability1_physical_viability_passive_deterioration")


def test_pack():
    assert (ROOT / "FINAL_REPORT.md").exists()
    assert (ROOT / "SEMANTIC_VIABILITY_FIREWALL.md").exists()
    s = json.loads((ROOT / "experiment_summary.json").read_text())
    assert s["freeze_ok"]
    assert s["semantic"]["dynamics_health_death_reward"] is False


def test_passive_recovery_no_mortality():
    s = json.loads((ROOT / "experiment_summary.json").read_text())
    assert s["B0_recovered_from_WORLD"] is True
    assert s["passive_recovery_toward_baseline_traj"] is True
    assert s["medium_required_for_reaction"] is False
    assert s["matched_full_future_d"] == 0.0


def test_outcome():
    text = (ROOT / "FINAL_REPORT.md").read_text()
    assert "PASSIVE_RECOVERABILITY_WITHOUT_MORTALITY" in text
    assert "NO_PHYSICAL_MORTALITY" in text
    assert "STOP" in text
