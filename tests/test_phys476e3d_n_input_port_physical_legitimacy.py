from __future__ import annotations
import inspect, json
from pathlib import Path
from mechanistic_mind.body.models import BodyConfig
from mechanistic_mind.body.sensorimotor_dynamics import evolve, COUPLING, DECAY
from mechanistic_mind.body.persistent_processes import PROCESS_KEYS
from mechanistic_mind.body.physical_transduction import maybe_step_on_state, MIX
from mechanistic_mind.body.models import BodyState
from mechanistic_mind.body.internal_transition_acquisition import TransitionRelationState, frobenius
from mechanistic_mind.research.motor_pathway_archaeology import ordinary_runtime_consumes_motor

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "phys476e3d_n_input_port_physical_legitimacy"

def test_invariants():
    assert BodyConfig().physical_transduction_config is None
    assert BodyConfig().persistent_process_config is None
    assert ordinary_runtime_consumes_motor() is False
    assert frobenius(TransitionRelationState()) == 0.0
    assert PROCESS_KEYS == ("internal_a", "internal_b", "load_c", "exchange_d")
    assert COUPLING == ((0.22, -0.13), (-0.09, 0.20), (0.11, 0.08))
    assert DECAY == 0.72
    src = inspect.getsource(evolve)
    assert 'body.get("internal_a"' in src.replace("'", '"') or "internal_a" in src
    assert "evolve(" not in (ROOT / "mechanistic_mind/body/engine.py").read_text()
    s = BodyState(); maybe_step_on_state(s, BodyConfig()); assert s.transducer_state == (0.0, 0.0, 0.0)
    assert MIX == ((0.70, 0.20, 0.10), (0.10, 0.30, 0.60))
    assert not (ROOT / ".git").exists()
    assert not (ROOT / "results/update477_acquired_reinstatement_to_action").exists()

def test_outcome():
    s = json.loads((OUT / "summary.json").read_text())
    assert s["experiment_id"] == "PHYS-4.76-E3D" and s["outcome"] == "E"
    assert s["physically_privileged_ordinary_N_interface"] is False
    assert s["Engine_calls_N"] is False and s["BODY_connected_to_N"] is False
    assert s["N_modified"] is False and s["internal_a_modified"] is False
    assert (OUT / "HISTORICAL_LAYERING.md").exists()
    assert (OUT / "PORT_PHYSICAL_LEGITIMACY_MATRIX.md").exists()

def test_priors():
    assert json.loads((ROOT/"results/phys476e3c_body_intrinsic_interface_archaeology/summary.json").read_text())["outcome"]=="C"
    assert json.loads((ROOT/"results/phys476e3b_x_architectural_legitimacy_provenance/summary.json").read_text())["outcome"]=="C"
