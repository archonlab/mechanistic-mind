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
from mechanistic_mind.body.physical_transduction import DECAY as X_DECAY, SCALE as X_SCALE, MIX
from worlds.organism_world_v03 import OrganismWorld


def test_defaults_unchanged():
    cfg = BodyConfig()
    assert cfg.physical_coupling_config is None
    assert cfg.physical_effector_config is None
    assert cfg.physical_transduction_config is None
    assert cfg.persistent_process_config is None
    assert cfg.passive_physical_exchange_config is None
    assert cfg.env_exchange_enabled is False
    assert BASE_NON_WAIT == 0.08


def test_frozen_parameters():
    assert C_SCALE == 1.0
    assert THRESHOLD == 0.60
    assert X_DECAY == 0.70
    assert X_SCALE == 0.25
    assert MIX[0] == (0.70, 0.20, 0.10)
    assert set(FAMILY) == {"C0", "C1", "C2", "C3", "C4"}


def test_still_no_ordinary_motor_consumer():
    assert ordinary_runtime_consumes_motor() is False


def test_default_wait_energy_smoke():
    world = OrganismWorld()
    registry = MechanismRegistry()
    registry.register(SingleOrganismPsycheV03())
    eng = Engine(world=world, agents={"A001": Agent(agent_id="A001")}, seed=17,
                 mechanisms=registry, run_config={"diagnostic": "4.70-smoke"})
    bodies = eng.state.world.variables["bodies"]["A001"]
    assert abs(float(bodies["energy_reserve"]) - 0.76) < 1e-9
    eng.step({"A001": Action.wait()})
    bodies = eng.state.world.variables["bodies"]["A001"]
    assert abs(float(bodies["energy_reserve"]) - 0.725) < 1e-9
    assert (bodies.get("internal_loads") or {}) == {}


def test_results_exist():
    root = Path("results/update470_generic_action_body_internal_return")
    for name in (
        "DESIGN_FREEZE.md", "ARCHITECTURE_INSPECTION.md", "CANONICAL_FRONTIER.md",
        "RETURN_PATH_ARCHAEOLOGY.md", "CONDITIONS.md", "MATCHING_METHOD.md",
        "PRE_DIVERGENCE_EQUIVALENCE.md", "TICK_CAUSAL_ORDER.md",
        "PHYSICAL_OUTPUT.md", "DISTANCE_BODY_RETURN.md", "BODY_X_RETURN.md",
        "X_N_RETURN.md", "WORLD_RETURN_CONTROL.md", "SATURATION_ANALYSIS.md",
        "NOISE_ANALYSIS.md", "ABLATIONS.md", "LOOP_ANALYSIS.md",
        "CAUSAL_EDGE_TABLE.md", "FIRST_UNSUPPORTED_ARROW.md",
        "SEMANTIC_LEAK_AUDIT.md", "ADVERSARIAL_AUDIT.md", "FINAL_REPORT.md",
        "design_freeze.json", "conditions.json", "matching.json",
        "pre_divergence_equivalence.json", "per_tick_metrics.json",
        "per_run_metrics.json", "physical_output.json", "body_return.json",
        "x_return.json", "n_return.json", "world_return_control.json",
        "saturation.json", "noise.json", "ablations.json", "loop_analysis.json",
        "edge_status.json", "claim_ladder.json", "semantic_leak_audit.json",
        "adversarial_audit.json", "architecture.json", "summary.json", "claims.json",
    ):
        assert (root / name).exists(), name
    freeze = json.loads((root / "design_freeze.json").read_text())
    assert freeze["written_before_outcome"] is True
    assert freeze["threshold"] == 0.60
    assert freeze["implemented_471"] is False
    s = json.loads((root / "summary.json").read_text())
    assert s["outcome"] == "G"
    assert s["canonical"]["4.69"] == "F"
    assert s["canonical"]["4.66"] == "B"
    assert s["zero_new_capability"] is True
    assert s["implemented_471"] is False
    assert s["same_stream_loop"] is False
    assert s["hops"]["B1"]["C1"] == 15
    assert s["hops"]["B1"]["C2"] == 20
    assert s["hops"]["B1"]["C3"] == 20
    assert s["hops"]["B1"]["C0"] == 0
    assert s["hops"]["B2"]["C1"] == 0
    assert s["hops"]["B0"] == 0
    assert s["hops"]["B3"] == 0
    assert s["hops"]["B4"] == 15
    assert s["dX"] == 0.0
    assert s["dNl"] == 0.0
    assert s["dmod"] == 0.0
    assert abs(s["b1_X"] - 0.4166666666666092) < 1e-12
    assert s["n_return_above_454_floor"] is False
    assert s["defaults"]["persistent_process_config"] is None
    assert s["defaults"]["physical_transduction_config"] is None
    assert s["leak"] == []
    loop = json.loads((root / "loop_analysis.json").read_text())
    assert loop["supported"] is False
    claims = json.loads((root / "claims.json").read_text())
    assert len(claims) == 93
    assert all(c["supported"] for c in claims)
