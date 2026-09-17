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
                 mechanisms=registry, run_config={"diagnostic": "4.72-smoke"})
    bodies = eng.state.world.variables["bodies"]["A001"]
    assert abs(float(bodies["energy_reserve"]) - 0.76) < 1e-9
    eng.step({"A001": Action.wait()})
    bodies = eng.state.world.variables["bodies"]["A001"]
    assert abs(float(bodies["energy_reserve"]) - 0.725) < 1e-9
    assert (bodies.get("internal_loads") or {}) == {}


def test_results_exist():
    root = Path("results/update472_state_dependent_physical_consequence")
    for name in (
        "DESIGN_FREEZE.md", "ARCHITECTURE_INSPECTION.md", "CANONICAL_FRONTIER.md",
        "UPDATE471_REPRODUCTION.md", "BODY_STATE_MANIPULATION.md", "BODY_STATE_FAMILY.md",
        "EVENT_MATCHING.md", "PHYSICAL_EVENT.md", "RAW_CONSEQUENCE.md",
        "REALIZED_CONSEQUENCE.md", "DIFFERENCE_IN_DIFFERENCES.md", "BOUND_ANALYSIS.md",
        "CONSEQUENCE_CURVE.md", "RELAXATION.md", "DOWNSTREAM_X.md", "DOWNSTREAM_PORTS.md",
        "PARALLEL_N.md", "NOISE_FLOOR.md", "ABLATIONS.md", "CAUSAL_EDGE_TABLE.md",
        "FIRST_UNSUPPORTED_ARROW.md", "SEMANTIC_LEAK_AUDIT.md", "ADVERSARIAL_AUDIT.md",
        "FINAL_REPORT.md", "RETURN_ITEMS.md",
        "design_freeze.json", "architecture.json", "canonical_frontier.json",
        "update471_reproduction.json", "body_state_manipulation.json",
        "body_state_family.json", "event_matching.json", "physical_event.json",
        "raw_consequence.json", "realized_consequence.json",
        "difference_in_differences.json", "bound_analysis.json",
        "consequence_curve.json", "relaxation.json", "downstream_x.json",
        "downstream_ports.json", "parallel_n.json", "noise_floor.json",
        "ablations.json", "edge_status.json", "claim_ladder.json",
        "semantic_leak_audit.json", "adversarial_audit.json", "summary.json",
        "claims.json", "prediction_match.json",
    ):
        assert (root / name).exists(), name
    freeze = json.loads((root / "design_freeze.json").read_text())
    assert freeze["written_before_outcome"] is True
    assert freeze["implemented_473"] is False
    assert "equation_prediction_frozen" in freeze
    s = json.loads((root / "summary.json").read_text())
    assert s["outcome"] == "E"
    assert s["canonical"]["4.71"] == "H"
    assert s["zero_new_capability"] is True
    assert s["implemented_473"] is False
    assert s["runtime_body_setter_added"] is False
    assert s["pred_ok"] is True
    assert s["eq_state"] is True
    assert s["clip_present"] is True
    assert s["same_stream_loop"] is False
    assert s["learning"] is False
    assert s["defaults"]["physical_transduction_config"] is None
    assert s["leak"] == []
    pred = json.loads((root / "prediction_match.json").read_text())
    assert pred["fat_ok"] and pred["en_ok"] and pred["hy_ok"]
    realized = json.loads((root / "realized_consequence.json").read_text())
    assert realized["fatigue"]["1.00"][2] == 0.0
    assert realized["joint"]["C1_like"] == [0.0, 0.0, 0.0]
    assert realized["joint"]["C23_like"][2] > 1e-6
    claims = json.loads((root / "claims.json").read_text())
    assert len(claims) == 109
