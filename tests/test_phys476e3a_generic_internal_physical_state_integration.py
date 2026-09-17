from __future__ import annotations
import json
from pathlib import Path
from mechanistic_mind.body.models import BodyConfig
from mechanistic_mind.body.internal_transition_acquisition import TransitionRelationState, frobenius

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "phys476e3a_generic_internal_physical_state_integration"

def test_no_new_capability_and_defaults():
    assert BodyConfig().physical_transduction_config is None
    assert BodyConfig().persistent_process_config is None
    assert frobenius(TransitionRelationState()) == 0.0
    assert not (ROOT / ".git").exists()
    # no new integrator module invented for E3A
    body = {p.name for p in (ROOT / "mechanistic_mind/body").glob("*.py")}
    assert "generic_internal_physical_state.py" not in body
    assert "internal_physical_integrator.py" not in body

def test_outcome_boundary():
    s = json.loads((OUT / "summary.json").read_text())
    assert s["experiment_id"] == "PHYS-4.76-E3A"
    assert s["outcome"] == "E"
    assert s["new_physical_capabilities"] == 0
    assert s["implementation_performed"] is False
    assert s["X_reimplementation_risk"] is True
    assert s["S_created"] is False
    assert s["acquisition_executed"] is False
    assert s["ACTION_INTERFACE_GAP"] == "PRESERVED"
    assert s["CONSEQUENCE_TIMING_GAP"] == "PRESERVED"
    assert s["update477_implemented"] is False
    assert (OUT / "X_COMPARISON.md").exists()
    assert (OUT / "EXISTING_MECHANISM_AUDIT.md").exists()

def test_priors_preserved():
    assert json.loads((ROOT / "results/eco476e3_natural_state_representation_archaeology/summary.json").read_text())["outcome"] == "H"
    assert json.loads((ROOT / "results/eco476e2_natural_episode_acquisition_compatibility/summary.json").read_text())["outcome"] == "L"
    assert not (ROOT / "results/update477_acquired_reinstatement_to_action").exists()
