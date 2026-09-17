from pathlib import Path
import json
import inspect

from mechanistic_mind.agent import Action, Agent
from mechanistic_mind.body.models import BodyConfig
from mechanistic_mind.body.sensorimotor_dynamics import BASE_NON_WAIT, evolve, SensorimotorState
from mechanistic_mind.body.adaptive_internal_coupling import step as w_step
from mechanistic_mind.body.acquired_sensorimotor_coupling import step as r_step
from mechanistic_mind.body.physical_transduction import maybe_step_on_state
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
    assert BASE_NON_WAIT == 0.08


def test_frozen_parameters():
    assert C_SCALE == 1.0
    assert THRESHOLD == 0.60
    assert MIX[0] == (0.70, 0.20, 0.10)
    assert set(FAMILY) == {"C0", "C1", "C2", "C3", "C4"}
    assert ordinary_runtime_consumes_motor() is False


def test_no_runtime_body_setter():
    assert not hasattr(BodyConfig, "set_body_state")
    assert not hasattr(BodyConfig, "inject_body")


def test_w_r_signatures_have_no_body_consequence():
    assert "body" not in str(inspect.signature(w_step))
    assert "energy" not in inspect.getsource(w_step)
    assert "fatigue" not in inspect.getsource(r_step)
    assert "n" in str(inspect.signature(r_step))
    assert "m" in str(inspect.signature(r_step))


def test_evolve_ignores_energy_hydration_fatigue():
    n0 = SensorimotorState()
    a = evolve(n0, body={}, random_value=0.5)
    b = evolve(n0, body={"energy_reserve": 0.1, "hydration": 0.1, "fatigue": 0.9}, random_value=0.5)
    assert a.channels == b.channels


def test_maybe_step_does_not_write_ports():
    src = inspect.getsource(maybe_step_on_state)
    assert "internal_a" not in src
    assert "load_c" not in src


def test_default_wait_energy_smoke():
    world = OrganismWorld()
    registry = MechanismRegistry()
    registry.register(SingleOrganismPsycheV03())
    eng = Engine(world=world, agents={"A001": Agent(agent_id="A001")}, seed=17,
                 mechanisms=registry, run_config={"diagnostic": "4.74-smoke"})
    bodies = eng.state.world.variables["bodies"]["A001"]
    assert abs(float(bodies["energy_reserve"]) - 0.76) < 1e-9
    eng.step({"A001": Action.wait()})
    bodies = eng.state.world.variables["bodies"]["A001"]
    assert abs(float(bodies["energy_reserve"]) - 0.725) < 1e-9


def test_research_module_does_not_import_knowledge():
    src = Path("mechanistic_mind/research/body_response_consequence_acquisition_archaeology.py").read_text()
    assert "knowledge/" not in src
    assert "Does not implement 4.75" in src


def test_results_exist():
    root = Path("results/update474_body_response_consequence_acquisition_archaeology")
    for name in (
        "DESIGN_FREEZE.md", "ARCHITECTURE_INSPECTION.md", "CANONICAL_FRONTIER.md",
        "UPDATE473_REPRODUCTION.md", "PRODUCER_CONSUMER_TABLE.md", "CAUSAL_PATH_GRAPH.md",
        "ACQUISITION_MECHANISM_INVENTORY.md", "BODY_CONSEQUENCE_CONSUMERS.md",
        "BODY_INTERNAL_ACCESS.md", "W_ARCHAEOLOGY.md", "R_ARCHAEOLOGY.md",
        "PREDICTIVE_STRUCTURE_ARCHAEOLOGY.md", "ELIGIBILITY_ARCHAEOLOGY.md",
        "RESPONSE_REPRESENTATION.md", "PHYSICAL_RESPONSE_PATH.md", "TEMPORAL_BRIDGE.md",
        "SUCCESSION_VS_CONTINGENCY.md", "CONTINGENT_YOKED_DESIGN.md",
        "CONTINGENT_YOKED_RESULTS.md", "MATCHING_QUALITY.md",
        "PASSIVE_CONSEQUENCE_CONTROL.md", "SAME_CURRENT_STATE.md",
        "ACQUIRED_STRUCTURE_RESULTS.md", "LATER_RESPONSE_RESULTS.md",
        "EFFECTOR_RESULTS.md", "PHYSICAL_RESPONSE_RESULTS.md", "ABLATIONS.md",
        "LEVEL_LADDER.md", "CAUSAL_EDGE_TABLE.md", "FIRST_UNSUPPORTED_ARROW.md",
        "SEMANTIC_LEAK_AUDIT.md", "ADVERSARIAL_AUDIT.md", "FINAL_REPORT.md", "RETURN_ITEMS.md",
        "design_freeze.json", "architecture.json", "canonical_frontier.json",
        "update473_reproduction.json", "producer_consumer_table.json",
        "causal_path_graph.json", "acquisition_inventory.json",
        "body_consequence_consumers.json", "body_internal_access.json",
        "w_archaeology.json", "r_archaeology.json",
        "predictive_structure_archaeology.json", "eligibility_archaeology.json",
        "response_representation.json", "physical_response_path.json",
        "temporal_bridge.json", "succession_vs_contingency.json",
        "contingent_yoked_design.json", "contingent_yoked_results.json",
        "matching_quality.json", "passive_consequence_control.json",
        "same_current_state.json", "acquired_structure_results.json",
        "later_response_results.json", "effector_results.json",
        "physical_response_results.json", "ablations.json", "level_ladder.json",
        "edge_status.json", "claim_ladder.json", "semantic_leak_audit.json",
        "adversarial_audit.json", "summary.json", "claims.json",
    ):
        assert (root / name).exists(), name
    freeze = json.loads((root / "design_freeze.json").read_text())
    assert freeze["written_before_outcome"] is True
    assert freeze["implemented_475"] is False
    s = json.loads((root / "summary.json").read_text())
    assert s["outcome"] == "I"
    assert s["canonical"]["4.73"] == "H"
    assert s["canonical"]["4.72"] == "E"
    assert s["canonical"]["4.46"] == "D"
    assert s["canonical"]["4.41"] == "F"
    assert s["zero_new_capability"] is True
    assert s["implemented_475"] is False
    assert s["body_to_w"] is False
    assert s["body_to_r"] is False
    assert s["body_to_live_n"] is False
    assert s["x_to_live_n"] is False
    assert s["maybe_writes_ports"] is False
    assert s["ehf_equals_empty_N"] is True
    assert s["contingent_yoked"] == "NOT_RUN"
    assert s["learning"] is False
    assert s["choice"] is False
    assert s["reward"] is False
    assert s["leak"] == []
    assert s["defaults"]["physical_transduction_config"] is None
    assert s["repro_473"]["outcome"] == "H"
    y = json.loads((root / "contingent_yoked_design.json").read_text())
    assert y["status"] == "NOT_RUN"
    claims = json.loads((root / "claims.json").read_text())
    assert len(claims) == 118
