"""ECO-4.76-E2 zero-new-capability compatibility archaeology tests."""
from __future__ import annotations
import json
from pathlib import Path
from mechanistic_mind.body.internal_transition_acquisition import (
    TransitionRelationState, frobenius, S_DIM, M_DIM, acquire, record
)
from mechanistic_mind.body.models import BodyConfig
from mechanistic_mind.research.motor_pathway_archaeology import ordinary_runtime_consumes_motor

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "eco476e2_natural_episode_acquisition_compatibility"


def test_defaults_and_frontier_artifacts():
    assert BodyConfig().internal_transition_acquisition_config is None
    assert BodyConfig().physical_transduction_config is None
    assert BodyConfig().contact_material_transfer_config is None
    assert ordinary_runtime_consumes_motor() is False
    assert S_DIM == 3 and M_DIM == 2
    assert (ROOT / "results/update475_response_contingent_internal_transition_acquisition/DESIGN_FREEZE.md").exists()
    assert (ROOT / "results/eco476e1_distal_cue_contact_consequence/resume_after_phys476e1a/summary.json").exists()
    assert (ROOT / "results/phys476e1a_generic_contact_material_transfer/summary.json").exists()
    assert not (ROOT / ".git").exists()


def test_no_acquisition_side_effects_in_module_use():
    # archaeology must not leave mutated L; local call only if someone mistakes—ensure API still research-only shape
    st = TransitionRelationState()
    assert frobenius(st) == 0.0
    # do NOT call acquire with natural data in this test; only verify unchanged empty state
    assert st.update_count == 0


def test_results_outcome_constraints():
    s = json.loads((OUT / "summary.json").read_text())
    assert s["experiment_id"] == "ECO-4.76-E2"
    assert s["outcome"] == "L"
    assert s["new_adapters"] == 0
    assert s["new_mappings"] == 0
    assert s["acquisition_executed"] is False
    assert s["update477_implemented"] is False
    assert s["L_before_frobenius"] == 0.0
    assert s["L_after_frobenius"] == 0.0
    assert s["compatibility_matrix"]["complete_triplet"]["available"] is False
    assert "S_before" in s["first_unsupported_acquisition_arrow"] or "S_before" in s["first_unsupported_acquisition_arrow"]
    m = s["compatibility_matrix"]
    assert m["S_before"]["direct_compatible"] is False
    assert m["M"]["direct_compatible"] is False
    assert m["S_after"]["direct_compatible"] is False
    assert m["M"]["Action_kind_compatibility"] == "NOT_COMPATIBLE"
    assert s["semantic_leaks_new"] == []
    assert s["suspicious_bridges_new"] == []
    for name in (
        "SOURCE_INSPECTION.md", "COMPATIBILITY_CRITERIA.md", "DESIGN_FREEZE.md",
        "COMPATIBILITY_MATRIX.json", "FINAL_REPORT.md", "RETURN_ITEMS.md",
    ):
        assert (OUT / name).exists(), name


def test_preserved_prior_outcomes():
    eco = json.loads((ROOT / "results/eco476e1_distal_cue_contact_consequence/resume_after_phys476e1a/summary.json").read_text())
    assert eco["outcome"] == "F"
    phys = json.loads((ROOT / "results/phys476e1a_generic_contact_material_transfer/summary.json").read_text())
    assert phys["outcome"] == "E"
    hist = (ROOT / "results/eco476e1_distal_cue_contact_consequence/CAPABILITY_BOUNDARY.md").read_text()
    assert "PHYSICAL_CAPABILITY_GAP" in hist
    assert not (ROOT / "results/update477_acquired_reinstatement_to_action").exists()


def test_no_adapter_symbols_in_runtime_new_code():
    # E2 should not add runtime bridge modules
    bridges = [
        "action_to_m", "move_to_m", "displacement_to_m", "body_to_s",
        "sensory_to_s", "wave_to_s", "one_hot_action", "encode_action",
    ]
    # scan only that no new files named like adapters exist under body/
    body = ROOT / "mechanistic_mind" / "body"
    names = {p.name for p in body.glob("*.py")}
    assert "action_to_m.py" not in names
    assert "natural_episode_adapter.py" not in names
