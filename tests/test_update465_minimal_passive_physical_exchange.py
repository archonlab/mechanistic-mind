from pathlib import Path
import json

from mechanistic_mind.body.models import BodyConfig
from mechanistic_mind.body.passive_physical_exchange import (
    FROZEN_PER_TICK_EXCHANGE_CAPACITY,
    default_enabled_config,
    exchange_enabled,
)
from mechanistic_mind.body.physical_transduction import DECAY as X_DECAY, SCALE as X_SCALE, MIX, body_vector_from_values
from mechanistic_mind.body.sensorimotor_dynamics import BASE_NON_WAIT, COUPLING
from mechanistic_mind.research.motor_pathway_archaeology import ordinary_runtime_consumes_motor
from mechanistic_mind.world_engine.physical_coupling import SCALE as C_SCALE, FAMILY
from mechanistic_mind.world_engine.physical_effector import THRESHOLD, DECAY as E_DECAY
from mechanistic_mind.world_engine.background_fields import default_field_spec
from mechanistic_mind.research.live_operating_range import SEEDS, PRIMARY


def test_defaults_unchanged():
    cfg = BodyConfig()
    assert cfg.physical_coupling_config is None
    assert cfg.physical_effector_config is None
    assert cfg.physical_transduction_config is None
    assert cfg.persistent_process_config is None
    assert cfg.env_exchange_enabled is False
    assert cfg.physical_intake_enabled is False
    assert cfg.passive_physical_exchange_config is None
    assert exchange_enabled(cfg) is False
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
    assert FROZEN_PER_TICK_EXCHANGE_CAPACITY == 0.008
    cfg = default_enabled_config()
    assert cfg["per_tick_exchange_capacity"] == 0.008
    assert cfg["yields"]["material_a"]["energy_delta"] == 0.8


def test_field_equation_untouched():
    spec = default_field_spec()
    assert spec["body_coupling"]["temperature"]["fatigue_delta"] == 0.0002
    assert spec["body_coupling"]["humidity"]["hydration_delta"] == -0.0001


def test_still_no_ordinary_motor_consumer():
    assert ordinary_runtime_consumes_motor() is False


def test_results_exist():
    root = Path("results/update465_minimal_passive_physical_exchange")
    for name in (
        "ARCHITECTURE_INSPECTION.md", "DESIGN_CANDIDATES.md", "DESIGN_SELECTION.md",
        "DESIGN_FREEZE.md", "PARAMETER_DERIVATION.md", "PHYSICAL_MODEL.md",
        "PREREGISTRATION.md", "BODY_RESULTS.md", "CAUSAL_ABLATIONS.md",
        "IDENTITY_CONTROLS.md", "TEMPORAL_ANALYSIS.md", "BOUNDEDNESS_ANALYSIS.md",
        "RETURN_PATH_COMPATIBILITY.md", "SEMANTIC_LEAK_AUDIT.md",
        "ADVERSARIAL_AUDIT.md", "FINAL_REPORT.md",
        "claims.json", "design_candidates.json", "design_freeze.json",
        "parameter_derivation.json", "physical_model.json", "preregistration.json",
        "conditions.json", "body_trajectories.json", "body_effect_sizes.json",
        "causal_ablations.json", "identity_controls.json", "temporal_analysis.json",
        "boundedness.json", "return_path_compatibility.json", "edge_status.json",
        "semantic_leak_audit.json", "adversarial_audit.json", "summary.json",
    ):
        assert (root / name).exists(), name
    s = json.loads((root / "summary.json").read_text())
    assert s["outcome"] in {"A", "B", "C", "D", "E", "F", "G"}
    assert s["canonical"]["4.64"] == "E"
    assert s["canonical"]["4.63"] == "A"
    assert s["canonical"]["4.62"] == "F"
    assert s["implemented_466"] is False
    assert s["Q_inspected"] is False
    assert s["defaults"]["passive_physical_exchange_config"] is None
    assert s["defaults"]["env_exchange_enabled"] is False
    assert s["leak"] == []
    assert s["policy"] == "WAIT"
    assert s["seeds"] == list(SEEDS)
    assert s["duration"] == PRIMARY
    adv = json.loads((root / "adversarial_audit.json").read_text())
    assert adv["2_Q_inspected_before_freeze"] is False
    assert adv["5_0_60_used_in_parameter_derivation"] is False
    assert adv["42_generic_movement_forced"] is False
    assert adv["45_ordinary_default_runtime_changed"] is False
    assert json.loads((root / "return_path_compatibility.json").read_text())["hop_executed"] is False
    freeze = json.loads((root / "design_freeze.json").read_text())
    assert freeze["duration"] == 96
    assert freeze["Q_inspected"] is False
    claims = json.loads((root / "claims.json").read_text())
    assert len(claims) >= 87
