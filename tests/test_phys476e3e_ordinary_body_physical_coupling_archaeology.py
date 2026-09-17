from __future__ import annotations
import json
from pathlib import Path
from mechanistic_mind.body.models import BodyConfig, BodyState
from mechanistic_mind.body.physical_transduction import maybe_step_on_state, MIX
from mechanistic_mind.body.sensorimotor_dynamics import COUPLING
from mechanistic_mind.body.persistent_processes import PROCESS_KEYS
from mechanistic_mind.body.internal_transition_acquisition import TransitionRelationState, frobenius
from mechanistic_mind.research.motor_pathway_archaeology import ordinary_runtime_consumes_motor

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "phys476e3e_ordinary_body_physical_coupling_archaeology"

def test_invariants():
    assert BodyConfig().physical_transduction_config is None
    assert BodyConfig().persistent_process_config is None
    assert ordinary_runtime_consumes_motor() is False
    assert frobenius(TransitionRelationState()) == 0.0
    assert PROCESS_KEYS[0] == "internal_a" and "load_c" in PROCESS_KEYS
    assert COUPLING[0][0] == 0.22
    assert MIX[0][0] == 0.70
    s = BodyState(); maybe_step_on_state(s, BodyConfig()); assert s.transducer_state == (0.0, 0.0, 0.0)
    assert "evolve(" not in (ROOT / "mechanistic_mind/body/engine.py").read_text()
    assert not (ROOT / ".git").exists()
    assert not (ROOT / "results/update477_acquired_reinstatement_to_action").exists()
    body = {p.name for p in (ROOT / "mechanistic_mind/body").glob("*.py")}
    assert "universal_body_transition.py" not in body
    assert "generic_body_port.py" not in body

def test_outcome():
    s = json.loads((OUT / "summary.json").read_text())
    assert s["experiment_id"] == "PHYS-4.76-E3E" and s["outcome"] == "C"
    assert s["new_generic_F"] is False and s["new_vector"] is False
    assert s["existing_CA_flattening_ordinary"] is False
    assert s["n_families"] >= 8
    assert (OUT / "CA_FLATTENING_AUDIT.md").exists()
    assert (OUT / "REJECTED_UNIFICATIONS.md").exists()

def test_priors():
    assert json.loads((ROOT/"results/phys476e3d_n_input_port_physical_legitimacy/summary.json").read_text())["outcome"]=="E"
    assert json.loads((ROOT/"results/phys476e3c_body_intrinsic_interface_archaeology/summary.json").read_text())["outcome"]=="C"
