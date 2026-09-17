"""PHYS-4.76-E1A generic contact material transfer tests."""
from __future__ import annotations

import json
from pathlib import Path

from mechanistic_mind.body.models import BodyConfig
from mechanistic_mind.body.physical_intake import (
    apply_bounded_object_intake,
    contact_material_transfer_enabled,
    same_cell_contact,
    IntakeParams,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "phys476e1a_generic_contact_material_transfer"


def test_capability_default_off():
    assert BodyConfig().contact_material_transfer_config is None
    assert contact_material_transfer_enabled(BodyConfig()) is False


def test_same_cell_contact_predicate():
    assert same_cell_contact((5, 2), [5, 2]) is True
    assert same_cell_contact((5, 2), (4, 2)) is False
    assert same_cell_contact(None, (5, 2)) is False


def test_shared_primitive_conserves_before_processing():
    rec = {
        "quantity": 1.0,
        "transferable_materials": {"material_a": 1.0},
        "intake_enabled": True,
    }
    params = IntakeParams(enabled=True)
    before = float(rec["quantity"])
    result = apply_bounded_object_intake(rec, params=params, internal_materials={})
    accepted = float(result["accepted"])
    assert accepted == 0.03
    assert abs((before - float(rec["quantity"])) - accepted) < 1e-12
    assert abs(sum(result["intake_transfer"].values()) - accepted) < 1e-12


def test_results_exist_and_outcome():
    required = [
        "SOURCE_INSPECTION.md",
        "DESIGN_FREEZE.md",
        "CAPABILITY_BOUNDARY.md",
        "EXISTING_USE_PATH.md",
        "CONTACT_GEOMETRY.md",
        "TRANSFER_EQUATION.md",
        "CONSERVATION_BOUNDARY.md",
        "FINAL_REPORT.md",
        "RETURN_ITEMS.md",
        "summary.json",
        "CONDITION_MATRIX.json",
        "CLAIM_LADDER.json",
        "ADVERSARIAL_AUDIT.json",
    ]
    for name in required:
        assert (OUT / name).exists(), name
    summary = json.loads((OUT / "summary.json").read_text())
    assert summary["experiment_id"] == "PHYS-4.76-E1A"
    assert summary["outcome"] == "E"
    assert summary["update477_implemented"] is False
    assert summary["eco476e1"] == "K"
    assert summary["new_cognitive_capability_count"] == 0
    assert summary["new_physical_capability_count"] == 1
    matrix = json.loads((OUT / "CONDITION_MATRIX.json").read_text())
    assert abs(matrix["primary_contact_transfer"]["transfer"] - 0.03) < 1e-9
    assert abs(matrix["no_contact"]["transfer_exact"]) < 1e-9
    assert abs(matrix["no_material"]["transfer"]) < 1e-9
    assert abs(matrix["capability_off"]["transfer"]) < 1e-9
    assert matrix["use_regression"]["match"] is True
    assert matrix["contact_plus_use"]["single_event"] is True
    assert matrix["semantic_leak_runtime"] == []
    assert not (ROOT / ".git").exists()


def test_no_477_knowledge_or_module():
    # 4.77 must not appear as an implemented update module/result.
    assert not (ROOT / "results" / "update477_acquired_reinstatement_to_action").exists()
    knowledge = ROOT / "knowledge" / "experiments"
    if knowledge.exists():
        names = [p.name for p in knowledge.iterdir()]
        assert "EXP-4.77" not in names
        assert not any("4.77" in n and "PHYS-4.76-E1A" not in n for n in names)


def test_eco_e1_remains_k():
    eco = ROOT / "results" / "eco476e1_distal_cue_contact_consequence"
    text = (eco / "CAPABILITY_BOUNDARY.md").read_text()
    assert "PHYSICAL_CAPABILITY_GAP" in text
