from __future__ import annotations
import inspect, json
from pathlib import Path
from mechanistic_mind.body.models import BodyConfig, BodyState
from mechanistic_mind.body.sensorimotor_dynamics import evolve
from mechanistic_mind.body.physical_transduction import maybe_step_on_state, DECAY, SCALE, MIX
from mechanistic_mind.body.internal_transition_acquisition import TransitionRelationState, frobenius
from mechanistic_mind.research.motor_pathway_archaeology import ordinary_runtime_consumes_motor

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "phys476e3c_body_intrinsic_interface_archaeology"

def test_invariants():
    assert BodyConfig().physical_transduction_config is None
    assert BodyConfig().persistent_process_config is None
    assert ordinary_runtime_consumes_motor() is False
    assert frobenius(TransitionRelationState()) == 0.0
    src = inspect.getsource(evolve)
    assert "energy_reserve" not in src and "hydration" not in src and "fatigue" not in src
    assert "internal_a" in src and "load_c" in src
    assert "evolve(" not in (ROOT / "mechanistic_mind/body/engine.py").read_text()
    s = BodyState(); maybe_step_on_state(s, BodyConfig()); assert s.transducer_state == (0.0, 0.0, 0.0)
    assert DECAY == 0.70 and SCALE == 0.25 and MIX == ((0.70, 0.20, 0.10), (0.10, 0.30, 0.60))
    assert not (ROOT / ".git").exists()
    assert not (ROOT / "results/update477_acquired_reinstatement_to_action").exists()

def test_outcome():
    s = json.loads((OUT / "summary.json").read_text())
    assert s["experiment_id"] == "PHYS-4.76-E3C" and s["outcome"] == "C"
    assert s["direct_BODY_to_N"] == "ABSENT" and s["ordinary_BODY_to_N"] == "ABSENT"
    assert s["X_necessity"] == "PARALLEL_EXPERIMENTAL_ROUTE"
    assert s["same_stream_ordinary_loop"] == "OPEN"
    assert s["new_port"] is False and s["X_enabled"] is False and s["N_modified"] is False
    assert (OUT / "BODY_TO_N_PATH_MATRIX.md").exists()
    assert (OUT / "X_VS_FOUR20.md").exists()

def test_priors():
    assert json.loads((ROOT/"results/phys476e3b_x_architectural_legitimacy_provenance/summary.json").read_text())["outcome"]=="C"
    assert json.loads((ROOT/"results/phys476e3a_generic_internal_physical_state_integration/summary.json").read_text())["outcome"]=="E"
    assert json.loads((ROOT/"results/eco476e3_natural_state_representation_archaeology/summary.json").read_text())["outcome"]=="H"
