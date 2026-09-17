from pathlib import Path
import json
import inspect

from mechanistic_mind.agent import Action, Agent
from mechanistic_mind.body.models import BodyConfig
from mechanistic_mind.body.sensorimotor_dynamics import BASE_NON_WAIT, evolve, SensorimotorState, motor_distribution
from mechanistic_mind.body.adaptive_internal_coupling import AdaptiveInternalState, step as w_step
from mechanistic_mind.body.acquired_sensorimotor_coupling import AcquiredCouplingState, step as r_step
from mechanistic_mind.body.internal_transition_acquisition import (
    LEARNING_RATE, TRACE_DECAY, WEIGHT_BOUND, TransitionRelationState,
    acquire, frobenius, record, readout, reset_traces,
)
from mechanistic_mind.body.physical_transduction import MIX
from mechanistic_mind.core import Engine
from mechanistic_mind.mechanisms import MechanismRegistry
from mechanistic_mind.psyche import SingleOrganismPsycheV03
from mechanistic_mind.research.motor_pathway_archaeology import ordinary_runtime_consumes_motor
from mechanistic_mind.world_engine.physical_coupling import FAMILY, SCALE as C_SCALE
from mechanistic_mind.world_engine.physical_effector import THRESHOLD
from worlds.organism_world_v03 import OrganismWorld

ROOT = Path("results/update475_response_contingent_internal_transition_acquisition")


def test_defaults_unchanged():
    cfg = BodyConfig()
    assert cfg.physical_coupling_config is None
    assert cfg.physical_effector_config is None
    assert cfg.physical_transduction_config is None
    assert cfg.persistent_process_config is None
    assert cfg.passive_physical_exchange_config is None
    assert cfg.internal_transition_acquisition_config is None
    assert cfg.env_exchange_enabled is False
    assert BASE_NON_WAIT == 0.08


def test_frozen_parameters():
    assert C_SCALE == 1.0
    assert THRESHOLD == 0.60
    assert MIX[0] == (0.70, 0.20, 0.10)
    assert set(FAMILY) == {"C0", "C1", "C2", "C3", "C4"}
    assert ordinary_runtime_consumes_motor() is False
    assert LEARNING_RATE == 0.075
    assert TRACE_DECAY == 0.62
    assert WEIGHT_BOUND == 0.65


def test_no_runtime_body_setter():
    assert not hasattr(BodyConfig, "set_body_state")
    assert not hasattr(BodyConfig, "inject_body")


def test_learner_bounded_and_local():
    st = TransitionRelationState()
    st = record(st, s=(0.3, 0.1, -0.1), m=(1.0, 0.0))
    st = acquire(st, s_after=(0.2, 0.0, 0.0))
    assert frobenius(st) > 0
    flat = [x for row in st.weights for pair in row for x in pair]
    assert all(abs(x) <= WEIGHT_BOUND + 1e-12 for x in flat)
    assert len(flat) == 18


def test_sign_symmetry():
    a = acquire(record(TransitionRelationState(), s=(0.3, 0.1, -0.1), m=(1.0, 0.0)), s_after=(0.2, 0.0, 0.0))
    b = acquire(record(TransitionRelationState(), s=(0.3, 0.1, -0.1), m=(1.0, 0.0)), s_after=(-0.2, 0.0, 0.0))
    assert abs(a.weights[0][0][0] + b.weights[0][0][0]) <= 1e-12
    assert a.weights[0][0][0] * b.weights[0][0][0] < 0


def test_c0_no_acquisition():
    st = TransitionRelationState()
    st = record(st, s=(0.3, 0.1, -0.1), m=(1.0, 0.0))
    st = acquire(st, s_after=(0.2, 0.0, 0.0), plasticity=False)
    assert frobenius(st) == 0.0


def test_no_reward_value_terms_in_learner():
    src = Path("mechanistic_mind/body/internal_transition_acquisition.py").read_text()
    for w in ("reward", "reinforcement", "utility", "preference", "desire", "motivation", "goal", "hunger", "punishment"):
        assert w not in src.lower()


def test_w_r_signatures_unchanged():
    assert "body" not in str(inspect.signature(w_step))
    assert "s_after" not in inspect.getsource(w_step)
    assert "s_after" not in inspect.getsource(r_step)


def test_evolve_ignores_L():
    n0 = SensorimotorState()
    a = evolve(n0, body={"internal_a": 0.55, "load_c": 0.45}, random_value=0.5)
    b = evolve(n0, body={"internal_a": 0.55, "load_c": 0.45}, random_value=0.5)
    assert a.channels == b.channels
    assert "L" not in inspect.signature(evolve).parameters
    assert "acquired_transition" not in inspect.getsource(evolve)
    assert "acquired_transition" not in inspect.getsource(motor_distribution)


def test_research_module_does_not_import_knowledge():
    src = Path("mechanistic_mind/research/response_contingent_internal_transition_acquisition.py").read_text()
    tok = "know" + "ledge"
    for ln in src.splitlines():
        s = ln.strip()
        assert not (s.startswith("from ") and tok in s and "import" in s.split()[:3] or False)
        assert not s.startswith("import " + tok)
    assert "Does not implement 4.76" in src


def test_no_476_module():
    assert not Path("mechanistic_mind/research/response_contingent_internal_transition_to_dynamics.py").exists()
    assert not Path("results/update476_acquired_structure_to_internal_dynamics").exists()


def test_default_wait_energy_smoke():
    world = OrganismWorld()
    registry = MechanismRegistry()
    registry.register(SingleOrganismPsycheV03())
    eng = Engine(world=world, agents={"A001": Agent(agent_id="A001")}, seed=17,
                 mechanisms=registry, run_config={"diagnostic": "4.75-smoke"})
    bodies = eng.state.world.variables["bodies"]["A001"]
    assert abs(float(bodies["energy_reserve"]) - 0.76) < 1e-9
    eng.step({"A001": Action.wait()})
    bodies = eng.state.world.variables["bodies"]["A001"]
    assert abs(float(bodies["energy_reserve"]) - 0.725) < 1e-9


def test_results_exist_and_outcome():
    for name in (
        "DESIGN_FREEZE.md", "SOURCE_INSPECTION.md", "CANONICAL_FRONTIER.md",
        "UPDATE474_REPRODUCTION.md", "CAPABILITY_BOUNDARY.md", "INTERNAL_REPRESENTATION.md",
        "RESPONSE_REPRESENTATION.md", "LEARNER_SPECIFICATION.md", "TRACE_SPECIFICATION.md",
        "BOUNDEDNESS.md", "PRODUCER_CONSUMER_TABLE.md", "CAUSAL_PATH_GRAPH.md",
        "PHYSICAL_CONSEQUENCE.md", "DEVELOPMENTAL_CONDITIONS.md", "MATCHING_PLAN.md",
        "MATCHING_RESULTS.md", "CONTINGENT_RESULTS.md", "YOKED_RESULTS.md",
        "RESPONSE_ONLY_RESULTS.md", "PASSIVE_CONSEQUENCE_RESULTS.md", "SHUFFLED_RESULTS.md",
        "DELAY_RESULTS.md", "ACQUISITION_READOUT.md", "REPRESENTATIONAL_PROBE.md",
        "SIGN_SYMMETRY.md", "BASIS_INVARIANCE.md", "TRACE_ABLATION.md",
        "RESPONSE_TRACE_ABLATION.md", "PRESTATE_ABLATION.md", "AFTERSTATE_ABLATION.md",
        "CONSEQUENCE_ABLATION.md", "BODY_SIGNAL_ABLATION.md", "W_R_ISOLATION.md",
        "BEHAVIORAL_ISOLATION.md", "RAW_HISTORY_PURGE.md", "REVERSAL.md",
        "LEVEL_LADDER.md", "CAUSAL_EDGE_TABLE.md", "FIRST_UNSUPPORTED_ARROW.md",
        "SEMANTIC_LEAK_AUDIT.md", "ADVERSARIAL_AUDIT.md", "FINAL_REPORT.md", "RETURN_ITEMS.md",
        "design_freeze.json", "source_inspection.json", "summary.json",
        "matching_results.json", "contingent_results.json", "yoked_results.json",
        "behavioral_isolation.json", "claim_ladder.json",
    ):
        assert (ROOT / name).exists(), name
    freeze = json.loads((ROOT / "design_freeze.json").read_text())
    assert freeze["written_before_outcome"] is True
    assert freeze["implemented_476"] is False
    s = json.loads((ROOT / "summary.json").read_text())
    assert s["outcome"] == "E"
    assert s["outcome_text"] == "CONTINGENCY_SENSITIVE_ACQUISITION"
    assert s["claim_asserted"] == s["claim_total"] == 143
    assert s["new_capability_count"] == 1
    assert s["implemented_476"] is False
    assert s["canonical"]["4.74"] == "I"
    assert s["canonical"]["4.73"] == "H"
    assert s["canonical"]["4.72"] == "E"
    assert s["repro_474"]["outcome"] == "I"
    assert s["match12"]["classification"] == "EXACT_MARGINAL_MATCH"
    assert s["L0"]["frobenius"] == 0.0
    assert s["L4"]["frobenius"] == 0.0
    assert s["L1"]["frobenius"] > 1e-6
    assert s["d12"] > 1e-6
    assert s["sign_sym"]["abs_equal"] is True
    assert s["basis"]["transforms"] is True
    assert s["beh"]["N_equal"] is True
    assert s["beh"]["Q_equal"] is True
    assert s["leak"] == []
    assert s["defaults"]["internal_transition_acquisition_config"] is None
    assert s["reward"] is False
    assert s["choice"] is False
    claims = json.loads((ROOT / "claim_ladder.json").read_text())
    assert all(v["ok"] for v in claims.values())
