from pathlib import Path
import json

from mechanistic_mind.body.models import BodyConfig
from mechanistic_mind.body.physical_transduction import DECAY as X_DECAY, SCALE as X_SCALE, MIX, body_vector_from_values
from mechanistic_mind.body.sensorimotor_dynamics import BASE_NON_WAIT, COUPLING
from mechanistic_mind.research.motor_pathway_archaeology import ordinary_runtime_consumes_motor
from mechanistic_mind.world_engine.physical_coupling import SCALE as C_SCALE, FAMILY
from mechanistic_mind.world_engine.physical_effector import THRESHOLD, DECAY as E_DECAY
from mechanistic_mind.world_engine.background_fields import default_field_spec
from mechanistic_mind.research import world_body_path_audit as wb
from mechanistic_mind.research.live_operating_range import SEEDS, PRIMARY


def test_defaults_unchanged():
    assert BodyConfig().physical_coupling_config is None
    assert BodyConfig().physical_effector_config is None
    assert BodyConfig().physical_transduction_config is None
    assert BodyConfig().persistent_process_config is None
    assert BodyConfig().env_exchange_enabled is False
    assert BodyConfig().physical_intake_enabled is False
    assert BASE_NON_WAIT == 0.08


def test_frozen_parameters():
    assert C_SCALE == 1.0
    assert THRESHOLD == 0.60
    assert E_DECAY == 0.50
    assert X_DECAY == 0.70
    assert X_SCALE == 0.25
    assert MIX[0] == (0.70, 0.20, 0.10)
    assert COUPLING[0] == (0.22, -0.13)
    assert set(FAMILY) == {"C0", "C1", "C2", "C3", "C4"}
    assert body_vector_from_values(0.1, 0.2, 0.3) == (0.1, 0.2, 0.3)


def test_field_equation_exact():
    spec = default_field_spec()
    assert spec["body_coupling"]["temperature"]["fatigue_delta"] == 0.0002
    assert spec["body_coupling"]["humidity"]["hydration_delta"] == -0.0001
    assert spec["enabled"] is True


def test_static_table_frozen_ids():
    ids = [c["ID"] for c in wb.static_candidates()]
    assert "P1_FIELD_COUPLING" in ids
    assert "P2_OBJECT_PRESENCE" in ids
    assert "P3_PASSIVE_CONTACT" in ids
    assert "P4_ENV_EXCHANGE" in ids
    assert "S1_USE_BODY_EFFECTS" in ids
    assert wb.SEEDS == (17, 23, 41, 59, 83) if hasattr(wb, "SEEDS") else SEEDS == (17, 23, 41, 59, 83)
    assert PRIMARY == 96
    writers = wb.static_writers()
    assert any(w["id"] == "W10" and w["ORIGIN"] == "WORLD_PHYSICAL" for w in writers)
    assert any(w["id"] == "W01" and w["ORIGIN"] == "BODY_INTERNAL" for w in writers)
    assert any(w["id"] == "W11" and w["ACTION_DEPENDENCY"] == "SEMANTIC_ACTION_REQUIRED" for w in writers)


def test_still_no_ordinary_motor_consumer():
    assert ordinary_runtime_consumes_motor() is False


def test_no_cognition_leaks():
    assert wb.cognition_leaks({"preact": (0.1, 0, 0), "B": (0.7, 0.7, 0.2)}) == []


def test_results_exist():
    root = Path("results/update464_world_body_path_audit")
    for name in (
        "FINAL_REPORT.md", "ARCHITECTURE_INSPECTION.md", "BODY_INPUT_GRAPH.md",
        "BODY_WRITER_INVENTORY.md", "WORLD_BODY_PATHS.md", "SEMANTIC_ACTION_DEPENDENCY.md",
        "PASSIVE_PATH_ANALYSIS.md", "FIELD_AUDIT.md", "OBJECT_CONTACT_AUDIT.md",
        "ENV_EXCHANGE_AUDIT.md", "INTAKE_AUDIT.md", "MOVEMENT_CONSEQUENCE_AUDIT.md",
        "INITIATION_RETURN_ANALYSIS.md", "PHYSICAL_CAUSAL_COVERAGE.md", "ADVERSARIAL_AUDIT.md",
        "claims.json", "body_inputs.json", "body_writers.json", "writer_classification.json",
        "world_body_candidates.json", "semantic_dependency_graph.json", "passive_candidates.json",
        "dynamic_validation.json", "field_audit.json", "object_presence_audit.json",
        "contact_audit.json", "env_exchange_audit.json", "intake_audit.json",
        "movement_cost_audit.json", "position_effects.json", "exogenous_events.json",
        "initiation_path.json", "return_path.json", "body_variable_coverage.json",
        "physical_causal_coverage.json", "edge_status.json", "semantic_leak_audit.json",
        "adversarial_audit.json", "summary.json",
    ):
        assert (root / name).exists(), name
    s = json.loads((root / "summary.json").read_text())
    assert s["outcome"] == "E"
    assert s["canonical"]["4.63"] == "A"
    assert s["canonical"]["4.62"] == "F"
    assert s["implemented_465"] is False
    assert s["audit"]["coupling_none"] is True
    assert s["audit"]["env_exchange_false"] is True
    assert s["leak"] == []
    adv = json.loads((root / "adversarial_audit.json").read_text())
    assert adv["30_Q_selected_candidates"] is False
    assert adv["31_parameter_search"] is False
    assert adv["15_420_activated"] is False
    assert adv["27_hypothetical_hop_executed"] is False
    assert adv["35_ordinary_default_runtime_changed"] is False
    dyn = json.loads((root / "dynamic_validation.json").read_text())
    assert dyn["policy"] == "WAIT"
    assert dyn["Q_used_for_selection"] is False
    assert json.loads((root / "contact_audit.json").read_text())["PASSIVE_CONTACT_TO_BODY"] == "ABSENT"
    assert json.loads((root / "return_path.json").read_text())["status"] == "STRUCTURALLY_PRESENT"
    assert json.loads((root / "initiation_path.json").read_text())["material_passive"] == "NOT_SUPPORTED"
