from pathlib import Path
import json

from mechanistic_mind.agent import Action, Agent
from mechanistic_mind.body.models import BodyConfig
from mechanistic_mind.body.sensorimotor_dynamics import BASE_NON_WAIT
from mechanistic_mind.core import Engine
from mechanistic_mind.mechanisms import MechanismRegistry
from mechanistic_mind.psyche import SingleOrganismPsycheV03
from mechanistic_mind.research.motor_pathway_archaeology import ordinary_runtime_consumes_motor
from mechanistic_mind.world_engine.physical_coupling import FAMILY, SCALE as C_SCALE
from mechanistic_mind.world_engine.physical_effector import THRESHOLD
from mechanistic_mind.body.physical_transduction import MIX
from worlds.organism_world_v03 import OrganismWorld


def test_defaults_unchanged():
    cfg = BodyConfig()
    assert cfg.physical_coupling_config is None
    assert cfg.physical_effector_config is None
    assert cfg.physical_transduction_config is None
    assert cfg.persistent_process_config is None
    assert cfg.passive_physical_exchange_config is None
    assert cfg.env_exchange_enabled is False
    assert cfg.fatigue_effort_multiplier == 0.8
    assert BASE_NON_WAIT == 0.08


def test_no_runtime_body_setter():
    cfg = BodyConfig()
    assert not hasattr(cfg, "set_body_state")
    assert not hasattr(BodyConfig, "inject_body")


def test_frozen_parameters():
    assert C_SCALE == 1.0
    assert THRESHOLD == 0.60
    assert MIX[0] == (0.70, 0.20, 0.10)
    assert set(FAMILY) == {"C0", "C1", "C2", "C3", "C4"}
    assert ordinary_runtime_consumes_motor() is False


def test_default_wait_energy_smoke():
    world = OrganismWorld()
    registry = MechanismRegistry()
    registry.register(SingleOrganismPsycheV03())
    eng = Engine(world=world, agents={"A001": Agent(agent_id="A001")}, seed=17,
                 mechanisms=registry, run_config={"diagnostic": "4.73-smoke"})
    bodies = eng.state.world.variables["bodies"]["A001"]
    assert abs(float(bodies["energy_reserve"]) - 0.76) < 1e-9
    eng.step({"A001": Action.wait()})
    bodies = eng.state.world.variables["bodies"]["A001"]
    assert abs(float(bodies["energy_reserve"]) - 0.725) < 1e-9
    assert (bodies.get("internal_loads") or {}) == {}


def test_research_module_does_not_import_knowledge():
    src = Path("mechanistic_mind/research/physical_intervention_vs_nonintervention.py").read_text()
    assert "knowledge/" not in src
    assert "knowledge\\" not in src


def test_results_exist():
    root = Path("results/update473_physical_intervention_vs_nonintervention")
    for name in (
        "DESIGN_FREEZE.md", "ARCHITECTURE_INSPECTION.md", "CANONICAL_FRONTIER.md",
        "UPDATE472_REPRODUCTION.md", "COUNTERFACTUAL_BRANCH_METHOD.md",
        "PRE_BRANCH_EQUIVALENCE.md", "INITIAL_BODY_STATES.md", "EVENT_DEFINITION.md",
        "WAIT_DEFINITION.md", "ABSOLUTE_WAIT_TRAJECTORIES.md", "ABSOLUTE_EVENT_TRAJECTORIES.md",
        "EVENT_WAIT_DIFFERENCE.md", "BODY_COMPONENT_TRAJECTORIES.md", "TRAJECTORY_DISTANCE.md",
        "RAW_CONSEQUENCE.md", "REALIZED_CONSEQUENCE.md", "BOUND_ANALYSIS.md",
        "FROZEN_PREDICTION.md", "POSITION_TRAJECTORIES.md", "WORLD_RETURN.md",
        "STATE_DEPENDENCE.md", "TRAJECTORY_FATE.md", "NOISE_FLOOR.md", "ABLATIONS.md",
        "CAUSAL_EDGE_TABLE.md", "FIRST_UNSUPPORTED_ARROW.md", "SEMANTIC_LEAK_AUDIT.md",
        "ADVERSARIAL_AUDIT.md", "FINAL_REPORT.md", "RETURN_ITEMS.md",
        "design_freeze.json", "architecture.json", "canonical_frontier.json",
        "update472_reproduction.json", "branch_method.json", "pre_branch_equivalence.json",
        "initial_body_states.json", "event_definition.json", "wait_definition.json",
        "wait_trajectories.json", "event_trajectories.json", "event_wait_difference.json",
        "body_component_trajectories.json", "trajectory_distance.json",
        "raw_consequence.json", "realized_consequence.json", "bound_analysis.json",
        "frozen_prediction.json", "position_trajectories.json", "world_return.json",
        "state_dependence.json", "trajectory_fate.json", "noise_floor.json",
        "ablations.json", "edge_status.json", "claim_ladder.json",
        "semantic_leak_audit.json", "adversarial_audit.json", "summary.json", "claims.json",
    ):
        assert (root / name).exists(), name
    freeze = json.loads((root / "design_freeze.json").read_text())
    assert freeze["written_before_outcome"] is True
    assert freeze["implemented_474"] is False
    assert freeze["horizon"] == 12
    assert freeze["sampling_times"] == [0, 1, 2, 3, 4, 8, 12]
    s = json.loads((root / "summary.json").read_text())
    assert s["outcome"] == "H"
    assert s["canonical"]["4.72"] == "E"
    assert s["canonical"]["4.71"] == "H"
    assert s["canonical"]["4.70"] == "G"
    assert s["canonical"]["4.69"] == "F"
    assert s["zero_new_capability"] is True
    assert s["implemented_474"] is False
    assert s["runtime_body_setter_added"] is False
    assert s["runtime_simulator_added"] is False
    assert s["pred_ok"] is True
    assert s["wait_executes"] is True
    assert s["cognition_accessible"] is False
    assert s["learning"] is False
    assert s["prospection"] is False
    assert s["choice"] is False
    assert s["trajectory_score"] is False
    assert s["leak"] == []
    assert s["defaults"]["physical_transduction_config"] is None
    assert s["repro_472"]["C1_zero"] is True
    assert s["repro_472"]["C23_dF_ok"] is True
    wait_def = json.loads((root / "wait_definition.json").read_text())
    assert wait_def["is_freeze"] is False
    ev = json.loads((root / "event_definition.json").read_text())
    assert ev["EVENT_distance"] == 1.0
    assert ev["WAIT_distance_at_fork"] == 0.0
    claims = json.loads((root / "claims.json").read_text())
    assert len(claims) == 121
    src = Path("mechanistic_mind/research/physical_intervention_vs_nonintervention.py").read_text()
    assert "4.74" in src
    assert "Does not implement 4.74" in src
