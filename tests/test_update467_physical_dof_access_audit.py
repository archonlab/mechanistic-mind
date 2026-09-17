from pathlib import Path
import json

from mechanistic_mind.body.models import BodyConfig
from mechanistic_mind.body.sensorimotor_dynamics import BASE_NON_WAIT
from mechanistic_mind.research.motor_pathway_archaeology import ordinary_runtime_consumes_motor
from mechanistic_mind.world_engine.physical_coupling import FAMILY, SCALE as C_SCALE
from mechanistic_mind.world_engine.physical_effector import THRESHOLD
from mechanistic_mind.body.physical_transduction import DECAY as X_DECAY, SCALE as X_SCALE, MIX


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


def test_results_exist():
    root = Path("results/update467_physical_dof_access_audit")
    for name in (
        "ARCHITECTURE_INSPECTION.md", "PHYSICAL_DOF_INVENTORY.md",
        "BODY_STATE_INVENTORY.md", "WORLD_STATE_INVENTORY.md",
        "CONFIGURATION_MATRIX.md", "CAUSAL_ACCESS_GRAPH.md",
        "NATURAL_VARIATION.md", "INDEPENDENCE_ANALYSIS.md",
        "DIMENSIONALITY_ANALYSIS.md", "INFORMATION_LOSS_MAP.md",
        "N_INPUT_DECOMPOSITION.md", "UPDATE466_DELTA_ANOMALY.md",
        "EXISTING_UNUSED_PATHS.md", "PHYSICAL_ACCESS_FRONTIER.md",
        "SEMANTIC_LEAK_AUDIT.md", "ADVERSARIAL_AUDIT.md", "FINAL_REPORT.md",
        "claims.json", "physical_dofs.json", "body_state_inventory.json",
        "world_state_inventory.json", "configuration_matrix.json",
        "causal_access_graph.json", "natural_variation.json",
        "independence_analysis.json", "dimensionality.json",
        "information_loss.json", "n_input_decomposition.json",
        "update466_delta_anomaly.json", "existing_unused_paths.json",
        "physical_access_frontier.json", "edge_status.json",
        "semantic_leak_audit.json", "adversarial_audit.json", "summary.json",
    ):
        assert (root / name).exists(), name
    s = json.loads((root / "summary.json").read_text())
    assert s["outcome"] in {"A", "B", "C", "D", "E", "F", "G"}
    assert s["canonical"]["4.66"] == "B"
    assert s["canonical"]["4.65"] == "E"
    assert s["zero_new_capability"] is True
    assert s["implemented_468"] is False
    assert s["defaults"]["passive_physical_exchange_config"] is None
    assert s["leak"] == []
    assert s["Q_optimized"] is False
    anomaly = json.loads((root / "update466_delta_anomaly.json").read_text())
    assert anomaly["C39_status"] == "MEASUREMENT_LIMITED"
    assert anomaly["canonical_466_change"] == "QUALIFICATION_NOT_CORRECTION"
    claims = json.loads((root / "claims.json").read_text())
    assert len(claims) >= 85
