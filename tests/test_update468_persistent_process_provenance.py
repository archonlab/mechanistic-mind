from pathlib import Path
import json

from mechanistic_mind.agent import Action, Agent
from mechanistic_mind.body.models import BodyConfig
from mechanistic_mind.body.persistent_processes import default_process_config, env_modulator
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
    assert env_modulator(None) == 0.0
    assert env_modulator({}) == 0.0
    assert default_process_config()["base_rate"] == 0.035


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
                 mechanisms=registry, run_config={"diagnostic": "4.68-smoke"})
    bodies = eng.state.world.variables["bodies"]["A001"]
    assert abs(float(bodies["energy_reserve"]) - 0.76) < 1e-9
    eng.step({"A001": Action.wait()})
    bodies = eng.state.world.variables["bodies"]["A001"]
    assert abs(float(bodies["energy_reserve"]) - 0.725) < 1e-9
    assert (bodies.get("internal_loads") or {}) == {}


def test_results_exist():
    root = Path("results/update468_persistent_process_provenance")
    for name in (
        "ARCHITECTURE_INSPECTION.md", "UPDATE420_SOURCE_RECONSTRUCTION.md",
        "PERSISTENT_STATE_INVENTORY.md", "INPUT_PROVENANCE.md",
        "WRITER_READER_GRAPH.md", "WORLD_UPSTREAM_ANALYSIS.md",
        "BODY_UPSTREAM_ANALYSIS.md", "RESEARCHER_UPSTREAM_ANALYSIS.md",
        "U1_DECOMPOSITION.md", "U3_WORLD_FIELD_ANALYSIS.md",
        "DYNAMIC_CAUSAL_TESTS.md", "N_CONTRIBUTION_DECOMPOSITION.md",
        "TIMING_ANALYSIS.md", "PHYSICAL_PROVENANCE_GRAPH.md",
        "SEMANTIC_LEAK_AUDIT.md", "ADVERSARIAL_AUDIT.md", "FINAL_REPORT.md",
        "claims.json", "persistent_state_inventory.json", "input_provenance.json",
        "writer_reader_graph.json", "world_upstream.json", "body_upstream.json",
        "researcher_upstream.json", "u1_decomposition.json", "u3_analysis.json",
        "dynamic_tests.json", "n_contribution.json", "timing.json",
        "physical_provenance_graph.json", "edge_status.json",
        "semantic_leak_audit.json", "adversarial_audit.json", "summary.json",
    ):
        assert (root / name).exists(), name
    s = json.loads((root / "summary.json").read_text())
    assert s["outcome"] == "F"
    assert s["outcome_text"] == "MIXED_PERSISTENT_PROCESS_PROVENANCE"
    assert s["canonical"]["4.67"] == "F"
    assert s["canonical"]["4.66"] == "B"
    assert s["canonical"]["4.65"] == "E"
    assert s["zero_new_capability"] is True
    assert s["implemented_469"] is False
    assert s["Q_used"] is False
    assert s["movement_tested"] is False
    assert s["defaults"]["persistent_process_config"] is None
    assert s["leak"] == []
    assert s["world_drives"] is True
    assert s["default_inert"] is True
    assert s["p0_has_keys"] is False
    assert s["p2_mod_span"] == 0.0
    assert s["p1_mod_span"] > 0.0
    u1 = json.loads((root / "u1_decomposition.json").read_text())
    assert u1["U1b"]["supported"] is False
    assert u1["U1c"]["supported"] is True
    u3 = json.loads((root / "u3_analysis.json").read_text())
    assert u3["live_WORLD_sampling"] is True
    assert u3["researcher_trajectory"] is False
    claims = json.loads((root / "claims.json").read_text())
    assert len(claims) == 85
    assert all(c["supported"] for c in claims)
