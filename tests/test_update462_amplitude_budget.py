from pathlib import Path

from mechanistic_mind.body.models import BodyConfig
from mechanistic_mind.body.acquired_sensorimotor_coupling import LEARNING_RATE
from mechanistic_mind.body.physical_transduction import DECAY as X_DECAY, SCALE as X_SCALE
from mechanistic_mind.body.sensorimotor_dynamics import BASE_NON_WAIT
from mechanistic_mind.research.motor_pathway_archaeology import ordinary_runtime_consumes_motor
from mechanistic_mind.world_engine.physical_coupling import SCALE as C_SCALE, FAMILY
from mechanistic_mind.world_engine.physical_effector import THRESHOLD, DECAY as E_DECAY
from mechanistic_mind.research import amplitude_budget as ab
from mechanistic_mind.research.live_operating_range import SEEDS, PRIMARY


def test_defaults_unchanged():
    assert BodyConfig().physical_coupling_config is None
    assert BodyConfig().physical_effector_config is None
    assert BodyConfig().physical_transduction_config is None
    assert BodyConfig().persistent_process_config is None
    assert LEARNING_RATE == 0.075
    assert BASE_NON_WAIT == 0.08


def test_frozen_parameters():
    assert C_SCALE == 1.0
    assert THRESHOLD == 0.60
    assert E_DECAY == 0.50
    assert X_DECAY == 0.70
    assert X_SCALE == 0.25
    assert set(FAMILY) == {"C0", "C1", "C2", "C3", "C4"}


def test_preregistered_stage_labels():
    assert "DOMINANT" in ab.STAGE_LABELS
    assert "AMPLIFYING" in ab.STAGE_LABELS
    assert SEEDS == (17, 23, 41, 59, 83)
    assert PRIMARY == 96


def test_still_no_ordinary_motor_consumer():
    assert ordinary_runtime_consumes_motor() is False


def test_no_cognition_leaks():
    assert ab.cognition_leaks({"preact": (0.1, 0, 0), "Z": (0.1, 0, 0, 0), "D": (0.1, 0, 0, 0)}) == []


def test_x_grid_stays_inside_observed_domain():
    grid = ab.x_grid_response(0.42)
    assert grid["xmax_probed"] <= 0.42 + 1e-12
    assert grid["n_probes"] > 0


def test_results_exist_and_no_threshold_tuning():
    root = Path("results/update462_amplitude_budget")
    assert (root / "FINAL_REPORT.md").exists()
    assert (root / "claims.json").exists()
    assert (root / "adversarial_audit.json").exists()
    import json
    adv = json.loads((root / "adversarial_audit.json").read_text())
    assert adv["2_threshold"] is False
    assert adv["1_gain"] is False
    assert adv["33_connected"] is False
    assert adv["34_420"] is False
    s = json.loads((root / "summary.json").read_text())
    assert s["r1_maxQ"] < 0.60
    assert abs(s["r1_maxQ"] - 0.4629102228566071) < 0.002
    assert s["any_thresh"] is False
    assert s["uncomposed"] == "ABSENT"
