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
                 mechanisms=registry, run_config={"diagnostic": "4.71-smoke"})
    bodies = eng.state.world.variables["bodies"]["A001"]
    assert abs(float(bodies["energy_reserve"]) - 0.76) < 1e-9
    eng.step({"A001": Action.wait()})
    bodies = eng.state.world.variables["bodies"]["A001"]
    assert abs(float(bodies["energy_reserve"]) - 0.725) < 1e-9
    assert (bodies.get("internal_loads") or {}) == {}


def test_results_exist():
    root = Path("results/update471_post_consequence_relaxation_latent_return")
    for name in (
        "DESIGN_FREEZE.md", "ARCHITECTURE_INSPECTION.md", "CANONICAL_FRONTIER.md",
        "UPDATE470_REPRODUCTION.md", "MATCHING.md", "TEMPORAL_ALIGNMENT.md",
        "BODY_RELAXATION.md", "X_VECTOR_RELAXATION.md", "NORM_TRAP_ANALYSIS.md",
        "BOUND_OCCUPANCY.md", "PORT_RELAXATION.md", "PARALLEL_N_RELAXATION.md",
        "NOISE_FLOOR.md", "ATTENUATION_ANALYSIS.md", "WORLD_CONFOUND_CONTROL.md",
        "ABLATIONS.md", "CAUSAL_EDGE_TABLE.md", "FIRST_ATTENUATION_STAGE.md",
        "SEMANTIC_LEAK_AUDIT.md", "ADVERSARIAL_AUDIT.md", "FINAL_REPORT.md",
        "RETURN_ITEMS.md",
        "design_freeze.json", "architecture.json", "canonical_frontier.json",
        "update470_reproduction.json", "matching.json", "temporal_alignment.json",
        "body_relaxation.json", "x_vector_relaxation.json", "norm_trap.json",
        "bound_occupancy.json", "port_relaxation.json", "parallel_n_relaxation.json",
        "noise_floor.json", "attenuation.json", "world_confound.json",
        "ablations.json", "edge_status.json", "claim_ladder.json",
        "semantic_leak_audit.json", "adversarial_audit.json", "summary.json",
        "claims.json",
    ):
        assert (root / name).exists(), name
    freeze = json.loads((root / "design_freeze.json").read_text())
    assert freeze["written_before_outcome"] is True
    assert freeze["duration"] == 96
    assert freeze["implemented_472"] is False
    assert freeze["observation_horizon"] == [0, 1, 2, 3, 4, 5, 8, 12, 16, 24, 32]
    s = json.loads((root / "summary.json").read_text())
    assert s["outcome"] == "H"
    assert s["canonical"]["4.70"] == "G"
    assert s["canonical"]["4.69"] == "F"
    assert s["zero_new_capability"] is True
    assert s["implemented_472"] is False
    assert s["same_stream_loop"] is False
    assert s["operating_range_n_return"] is False
    assert s["hops"]["B1"]["C1"] == 15
    assert s["hops"]["B1"]["C2"] == 20
    assert s["hops"]["B1"]["C3"] == 20
    assert s["hops"]["B2"]["C1"] == 0
    assert s["peaks"]["d_normX"] == 0.0
    assert s["peaks"]["dX"] > 0.0
    assert s["peaks"]["dNl"] == 0.0
    assert s["nr_op_any"] is False
    assert s["bm_any"] is True
    assert s["late_any"] is False
    assert s["defaults"]["physical_transduction_config"] is None
    assert s["leak"] == []
    trap = json.loads((root / "norm_trap.json").read_text())
    assert trap["C3"]["17"]["trap_reproduced"] is True
    assert trap["C1"]["17"]["trap_reproduced"] is False
    assert abs(trap["C3"]["17"]["d_normX_0"]) <= 1e-12
    assert trap["C3"]["17"]["linf_dX_0"] > 1e-6
    claims = json.loads((root / "claims.json").read_text())
    assert len(claims) == 104
    assert all(c["supported"] for c in claims)
