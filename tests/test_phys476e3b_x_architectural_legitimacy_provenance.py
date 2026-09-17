from __future__ import annotations
import json
from pathlib import Path
from mechanistic_mind.body.models import BodyConfig, BodyState
from mechanistic_mind.body.physical_transduction import (
    DECAY, SCALE, X_BOUND, COMPONENT_COUNT, MIX, maybe_step_on_state, step_transducer,
)
from mechanistic_mind.body.internal_transition_acquisition import TransitionRelationState, frobenius

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "phys476e3b_x_architectural_legitimacy_provenance"

def test_x_unchanged_and_default_off():
    assert BodyConfig().physical_transduction_config is None
    assert DECAY == 0.70 and SCALE == 0.25 and X_BOUND == 1.0 and COMPONENT_COUNT == 3
    assert MIX == ((0.70, 0.20, 0.10), (0.10, 0.30, 0.60))
    s = BodyState()
    maybe_step_on_state(s, BodyConfig())
    assert s.transducer_state == (0.0, 0.0, 0.0)
    assert frobenius(TransitionRelationState()) == 0.0
    assert not (ROOT / ".git").exists()
    assert not (ROOT / "results/update477_acquired_reinstatement_to_action").exists()
    body = {p.name for p in (ROOT / "mechanistic_mind/body").glob("*.py")}
    assert "generic_internal_physical_state.py" not in body

def test_outcome_archaeology():
    s = json.loads((OUT / "summary.json").read_text())
    assert s["experiment_id"] == "PHYS-4.76-E3B"
    assert s["outcome"] == "C"
    assert s["new_physical_capabilities"] == 0
    assert s["X_enabled"] is False and s["X_modified"] is False and s["X2_created"] is False
    assert s["S_created"] is False and s["acquisition_executed"] is False
    assert s["generic_core"] is True
    assert s["input_shell"] == "RESEARCH_SPECIFIC"
    assert s["PASSIVE_WAVE_to_X"] == "ABSENT"
    assert (OUT / "GENERIC_CORE_VS_INTERFACE_SHELL.md").exists()
    assert (OUT / "COMPONENT_LEGITIMACY_MATRIX.md").exists()
    # equation identity
    got = step_transducer((0,0,0),(0.8,0.6,0.4),None,mode="ABSOLUTE")
    exp = tuple(max(-1.0,min(1.0,0.25*(b-0.5))) for b in (0.8,0.6,0.4))
    assert got == exp

def test_priors():
    assert json.loads((ROOT/"results/phys476e3a_generic_internal_physical_state_integration/summary.json").read_text())["outcome"]=="E"
    assert json.loads((ROOT/"results/eco476e3_natural_state_representation_archaeology/summary.json").read_text())["outcome"]=="H"
