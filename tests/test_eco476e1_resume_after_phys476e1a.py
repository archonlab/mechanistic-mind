"""ECO-4.76-E1 resume after PHYS-4.76-E1A."""
from __future__ import annotations

import json
from pathlib import Path

from mechanistic_mind.body.models import BodyConfig
from mechanistic_mind.research.motor_pathway_archaeology import ordinary_runtime_consumes_motor

ROOT = Path(__file__).resolve().parents[1]
HIST = ROOT / "results" / "eco476e1_distal_cue_contact_consequence"
RESUME = HIST / "resume_after_phys476e1a"
PHYS = ROOT / "results" / "phys476e1a_generic_contact_material_transfer"


def test_historical_k_preserved():
    text = (HIST / "CAPABILITY_BOUNDARY.md").read_text()
    assert "PHYSICAL_CAPABILITY_GAP" in text
    assert (HIST / "DESIGN_FREEZE.md").exists()
    assert (HIST / "SOURCE_INSPECTION.md").exists()


def test_phys_e1a_preserved():
    s = json.loads((PHYS / "summary.json").read_text())
    assert s["outcome"] == "E"
    assert s["outcome"] == "E"
    assert s.get("new_physical_capability_count") == 1


def test_resume_outcome_and_boundaries():
    s = json.loads((RESUME / "summary.json").read_text())
    assert s["experiment_id"] == "ECO-4.76-E1"
    assert s["historical_outcome"] == "K"
    assert s["phys_prerequisite"].startswith("E")
    assert s["outcome"] in set("ABCDEFGHIJKL")
    assert s["new_physical_capabilities"] == 0
    assert s["new_cognitive_capabilities"] == 0
    assert s["update477_implemented"] is False
    assert s["classifications"]["CUE_DEPENDENT_ACTION"] == "NOT_CLAIMED"
    assert s["classifications"]["SEEKING"] == "NOT_CLAIMED"
    assert s["classifications"]["LEARNING"] == "OFF"
    assert BodyConfig().contact_material_transfer_config is None
    assert ordinary_runtime_consumes_motor() is False
    assert not (ROOT / ".git").exists()


def test_dual_source_controlled():
    s = json.loads((RESUME / "summary.json").read_text())
    rows = {r["label"]: r for r in s["controlled"]["P3"]["rows"]}
    assert rows["intermediate"]["contact"] is False
    assert rows["intermediate"]["wave_amp_gt"] > 0
    assert rows["contact"]["contact"] is True
    assert rows["contact"]["transfer"] > 0
    assert rows["contact"]["env_field"] in ({}, None)
    assert s["removal"]["amp_before"] > 0
    assert s["removal"]["amp_after_removal"] == 0.0
    assert set(s["wave_component_keys"]) == {"amplitude", "channel", "directionality", "frequency"}


def test_no_use_take_in_autonomous_transfer_path():
    s = json.loads((RESUME / "summary.json").read_text())
    for a in s["autonomous"]:
        assert a.get("use_count", 0) == 0
        assert a.get("take_count", 0) == 0


def test_required_resume_docs():
    for name in (
        "RESUME_INSPECTION.md",
        "FINAL_REPORT.md",
        "RETURN_ITEMS.md",
        "summary.json",
        "CLAIM_LADDER.json",
    ):
        assert (RESUME / name).exists(), name


def test_no_477():
    assert not (ROOT / "results" / "update477_acquired_reinstatement_to_action").exists()
