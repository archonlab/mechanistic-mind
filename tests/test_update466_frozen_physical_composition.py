from pathlib import Path
import json

from mechanistic_mind.body.models import BodyConfig
from mechanistic_mind.body.physical_transduction import DECAY as X_DECAY, SCALE as X_SCALE, MIX
from mechanistic_mind.body.sensorimotor_dynamics import BASE_NON_WAIT
from mechanistic_mind.research.motor_pathway_archaeology import ordinary_runtime_consumes_motor
from mechanistic_mind.world_engine.physical_coupling import SCALE as C_SCALE, FAMILY
from mechanistic_mind.world_engine.physical_effector import THRESHOLD, DECAY as E_DECAY
from mechanistic_mind.research.live_operating_range import SEEDS, PRIMARY


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
    assert E_DECAY == 0.50
    assert X_DECAY == 0.70
    assert X_SCALE == 0.25
    assert MIX[0] == (0.70, 0.20, 0.10)
    assert set(FAMILY) == {"C0", "C1", "C2", "C3", "C4"}


def test_still_no_ordinary_motor_consumer():
    assert ordinary_runtime_consumes_motor() is False


def test_results_exist():
    root = Path("results/update466_frozen_physical_composition")
    for name in (
        "ARCHITECTURE_INSPECTION.md", "FREEZE_AUDIT.md", "PREREGISTRATION.md",
        "COMPOSITION_PATH.md", "OPERATING_RANGE.md", "CAUSAL_PROPAGATION.md",
        "THRESHOLD_ANALYSIS.md", "PHYSICAL_ACTION_ANALYSIS.md",
        "RETURN_PATH_ANALYSIS.md", "LOOP_CLOSURE_ANALYSIS.md",
        "BOUND_CONFOUND_ANALYSIS.md", "TIMING_ANALYSIS.md",
        "INVARIANCE_ANALYSIS.md", "SEMANTIC_LEAK_AUDIT.md",
        "ADVERSARIAL_AUDIT.md", "FINAL_REPORT.md",
        "claims.json", "freeze_audit.json", "preregistration.json",
        "conditions.json", "traces.json", "causal_propagation.json",
        "operating_range.json", "threshold_analysis.json",
        "physical_actions.json", "return_path.json", "loop_closure.json",
        "bound_confound.json", "timing.json", "invariance.json",
        "edge_status.json", "semantic_leak_audit.json",
        "adversarial_audit.json", "summary.json",
    ):
        assert (root / name).exists(), name
    s = json.loads((root / "summary.json").read_text())
    assert s["outcome"] in {"A", "B", "C", "D", "E", "F", "G"}
    assert s["canonical"]["4.65"] == "E"
    assert s["canonical"]["4.64"] == "E"
    assert s["zero_new_capability"] is True
    assert s["implemented_467"] is False
    assert s["threshold"] == 0.60
    assert s["duration"] == PRIMARY
    assert s["seeds"] == list(SEEDS)
    assert s["defaults"]["passive_physical_exchange_config"] is None
    assert s["leak"] == []
    freeze = json.loads((root / "freeze_audit.json").read_text())
    assert freeze["threshold"] == 0.60
    assert freeze["Q_observed_before_freeze"] is False
    adv = json.loads((root / "adversarial_audit.json").read_text())
    assert adv["1_new_capability"] is False
    assert adv["10_threshold_changed"] is False
    assert adv["22_movement_forced"] is False
    claims = json.loads((root / "claims.json").read_text())
    assert len(claims) >= 90
