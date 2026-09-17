from __future__ import annotations
import json
from pathlib import Path
from mechanistic_mind.body.models import BodyConfig
from mechanistic_mind.body.internal_transition_acquisition import TransitionRelationState, frobenius

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "eco476e3_natural_state_representation_archaeology"

def test_defaults_and_no_x_activation():
    assert BodyConfig().physical_transduction_config is None
    assert BodyConfig().internal_transition_acquisition_config is None
    assert frobenius(TransitionRelationState()) == 0.0
    assert not (ROOT / ".git").exists()

def test_outcome_constraints():
    s = json.loads((OUT / "summary.json").read_text())
    assert s["experiment_id"] == "ECO-4.76-E3"
    assert s["outcome"] == "H"
    assert s["X_activated_by_experiment"] is False
    assert s["acquisition_executed"] is False
    assert s["L_before"] == 0.0 and s["L_after"] == 0.0
    assert s["new_projections"] == 0 and s["new_mappings"] == 0
    assert s["ACTION_INTERFACE_GAP"] == "PRESERVED"
    assert s["CONSEQUENCE_TIMING_GAP"] == "PRESERVED"
    assert s["update477_implemented"] is False
    assert s["best_natural_candidate"] == "NONE"
    assert s["structural_ordinary_S"] is False
    assert s["semantic_leaks_new"] == []
    snaps = json.loads((OUT / "NATURAL_STATE_SNAPSHOTS.json").read_text())
    assert any(x["label"] == "T4_contact_transfer" for x in snaps)
    assert all(x["transducer_state"] == [0.0, 0.0, 0.0] for x in snaps)

def test_priors_preserved():
    assert json.loads((ROOT / "results/eco476e2_natural_episode_acquisition_compatibility/summary.json").read_text())["outcome"] == "L"
    assert json.loads((ROOT / "results/eco476e1_distal_cue_contact_consequence/resume_after_phys476e1a/summary.json").read_text())["outcome"] == "F"
    assert "PHYSICAL_CAPABILITY_GAP" in (ROOT / "results/eco476e1_distal_cue_contact_consequence/CAPABILITY_BOUNDARY.md").read_text()
    assert not (ROOT / "results/update477_acquired_reinstatement_to_action").exists()

def test_no_adapter_files():
    names = {p.name for p in (ROOT / "mechanistic_mind/body").glob("*.py")}
    assert "sensory_to_s.py" not in names
    assert "body_to_s.py" not in names
    assert "natural_s.py" not in names
