from pathlib import Path
import json
import inspect

from mechanistic_mind.agent import Action, Agent
from mechanistic_mind.body.models import BodyConfig
from mechanistic_mind.body.sensorimotor_dynamics import BASE_NON_WAIT, evolve, SensorimotorState, motor_distribution
from mechanistic_mind.body.internal_transition_acquisition import LEARNING_RATE, TRACE_DECAY, WEIGHT_BOUND, TransitionRelationState
from mechanistic_mind.body.acquired_transition_reinstatement import R_BOUND, frobenius_r, linf_r, reinstate
from mechanistic_mind.body.physical_transduction import MIX
from mechanistic_mind.core import Engine
from mechanistic_mind.mechanisms import MechanismRegistry
from mechanistic_mind.psyche import SingleOrganismPsycheV03
from mechanistic_mind.research.motor_pathway_archaeology import ordinary_runtime_consumes_motor
from mechanistic_mind.world_engine.physical_coupling import FAMILY, SCALE as C_SCALE
from mechanistic_mind.world_engine.physical_effector import THRESHOLD
from worlds.organism_world_v03 import OrganismWorld

ROOT = Path("results/update476_acquired_transition_reinstatement")


def test_defaults_unchanged():
    cfg = BodyConfig()
    assert cfg.physical_coupling_config is None
    assert cfg.physical_effector_config is None
    assert cfg.physical_transduction_config is None
    assert cfg.persistent_process_config is None
    assert cfg.passive_physical_exchange_config is None
    assert cfg.internal_transition_acquisition_config is None
    assert cfg.acquired_transition_reinstatement_config is None
    assert cfg.env_exchange_enabled is False
    assert BASE_NON_WAIT == 0.08


def test_frozen_475_constants():
    assert C_SCALE == 1.0
    assert THRESHOLD == 0.60
    assert MIX[0] == (0.70, 0.20, 0.10)
    assert set(FAMILY) == {"C0", "C1", "C2", "C3", "C4"}
    assert ordinary_runtime_consumes_motor() is False
    assert LEARNING_RATE == 0.075
    assert TRACE_DECAY == 0.62
    assert WEIGHT_BOUND == 0.65
    assert abs(R_BOUND - 1.95) < 1e-12


def test_null_L_and_null_S():
    z = TransitionRelationState().weights
    r = reinstate((0.2, 0.1, -0.1), z)
    assert frobenius_r(r) == 0.0
    w = (((0.1, 0.0, 0.0), (0.0, 0.0, 0.0)), ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)), ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)))
    assert frobenius_r(reinstate((0.0, 0.0, 0.0), w)) == 0.0


def test_bilinear_and_sign():
    w = (((0.1, 0.0, 0.0), (0.0, 0.0, 0.0)), ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)), ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)))
    s = (0.5, 0.0, 0.0)
    r = reinstate(s, w)
    assert abs(r[0][0] - 0.05) < 1e-15
    wneg = (((-0.1, 0.0, 0.0), (0.0, 0.0, 0.0)), ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)), ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)))
    rn = reinstate(s, wneg)
    assert abs(rn[0][0] + r[0][0]) < 1e-15


def test_no_write_into_evolve():
    assert "reinstate" not in inspect.getsource(evolve)
    assert "reinstate" not in inspect.getsource(motor_distribution)


def test_no_reward_terms():
    src = Path("mechanistic_mind/body/acquired_transition_reinstatement.py").read_text()
    for w in ("reward", "preference", "desire", "motivation", "goal", "utility"):
        assert w not in src.lower()


def test_research_no_knowledge_import():
    src = Path("mechanistic_mind/research/acquired_transition_reinstatement.py").read_text()
    tok = "know" + "ledge"
    for ln in src.splitlines():
        s = ln.strip()
        assert not s.startswith("import " + tok)
    assert "Does not implement 4.77" in src
    assert "generate()" in src  # refers to not calling 4.75 generate


def test_no_477():
    assert not Path("results/update477_reinstatement_to_action").exists()


def test_default_wait_energy_smoke():
    world = OrganismWorld()
    registry = MechanismRegistry()
    registry.register(SingleOrganismPsycheV03())
    eng = Engine(world=world, agents={"A001": Agent(agent_id="A001")}, seed=17,
                 mechanisms=registry, run_config={"diagnostic": "4.76-smoke"})
    bodies = eng.state.world.variables["bodies"]["A001"]
    assert abs(float(bodies["energy_reserve"]) - 0.76) < 1e-9
    eng.step({"A001": Action.wait()})
    bodies = eng.state.world.variables["bodies"]["A001"]
    assert abs(float(bodies["energy_reserve"]) - 0.725) < 1e-9


def test_results_and_outcome():
    for name in (
        "DESIGN_FREEZE.md", "SOURCE_INSPECTION.md", "CAPABILITY_BOUNDARY.md",
        "CANONICAL_FRONTIER.md", "UPDATE475_REPRODUCTION.md", "REINSTATEMENT_SPECIFICATION.md",
        "BOUNDEDNESS.md", "PRODUCER_CONSUMER_TABLE.md", "CAUSAL_PATH_GRAPH.md",
        "DEVELOPMENTAL_HISTORY_REPRODUCTION.md", "CURRENT_PROBE_FREEZE.md",
        "CURRENT_STATE_MATCHING.md", "PRIMARY_REINSTATEMENT.md", "HISTORY_COMPARISON.md",
        "CURRENT_STATE_SPECIFICITY.md", "HISTORY_STATE_FACTORIAL.md", "NULL_CONTROL.md",
        "CURRENT_S_ABLATION.md", "L_ABLATION.md", "PASSIVE_CONTROL.md",
        "RESPONSE_ONLY_CONTROL.md", "SHUFFLED_CONTROL.md", "SIGN_SYMMETRY.md",
        "BASIS_INVARIANCE.md", "RESPONSE_AXIS_PERMUTATION.md", "ANALYTICAL_BASELINE.md",
        "DIRECT_L_PERTURBATION.md", "SCALE_LINEARITY.md", "BODY_SIGNAL_ABLATION.md",
        "RAW_HISTORY_PURGE.md", "TRACE_CLEARING.md", "REVISION_REINSTATEMENT.md",
        "BEHAVIORAL_ISOLATION.md", "LEVEL_LADDER.md", "CAUSAL_EDGE_TABLE.md",
        "FIRST_UNSUPPORTED_ARROW.md", "SEMANTIC_LEAK_AUDIT.md", "ADVERSARIAL_AUDIT.md",
        "FINAL_REPORT.md", "RETURN_ITEMS.md",
        "design_freeze.json", "source_inspection.json", "summary.json",
        "update475_reproduction.json", "primary_reinstatement.json",
        "analytical_baseline.json", "behavioral_isolation.json", "claim_ladder.json",
    ):
        assert (ROOT / name).exists(), name
    freeze = json.loads((ROOT / "design_freeze.json").read_text())
    assert freeze["written_before_outcome"] is True
    assert freeze["implemented_477"] is False
    s = json.loads((ROOT / "summary.json").read_text())
    assert s["outcome"] == "D"
    assert s["outcome_text"] == "CONTINGENCY_SENSITIVE_REINSTATEMENT"
    assert s["claim_asserted"] == s["claim_total"] == 138
    assert s["implemented_477"] is False
    assert s["canonical"]["4.75"] == "E"
    assert s["repro_475"]["LC_ok"] is True
    assert s["repro_475"]["d12_ok"] is True
    assert abs(s["repro_475"]["d12"] - 0.004599862650311365) < 1e-15
    assert s["anal_err"] == 0.0
    assert s["algebraic"] == "EXACT_BILINEAR_PROPAGATION"
    assert s["rC_f"] > 0
    assert s["d_linf"] > 0
    assert s["sign_ok"] is True
    assert s["basis_err"] == 0.0
    assert s["m_err"] == 0.0
    assert s["half_ok"] is True
    assert s["beh"]["N_equal"] is True
    assert s["beh"]["Q_equal"] is True
    assert s["leak"] == []
    assert s["defaults"]["acquired_transition_reinstatement_config"] is None
    assert s["orthogonal"] == "NOT_RUN"
    claims = json.loads((ROOT / "claim_ladder.json").read_text())
    assert all(v["ok"] for v in claims.values())
