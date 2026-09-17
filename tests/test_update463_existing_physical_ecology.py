from pathlib import Path
import json

from mechanistic_mind.body.models import BodyConfig
from mechanistic_mind.body.physical_transduction import DECAY as X_DECAY, SCALE as X_SCALE, MIX
from mechanistic_mind.body.sensorimotor_dynamics import BASE_NON_WAIT, COUPLING
from mechanistic_mind.research.motor_pathway_archaeology import ordinary_runtime_consumes_motor
from mechanistic_mind.world_engine.physical_coupling import SCALE as C_SCALE, FAMILY
from mechanistic_mind.world_engine.physical_effector import THRESHOLD, DECAY as E_DECAY
from mechanistic_mind.research import existing_physical_ecology as epe


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


def test_ecology_preregistered_without_q():
    assert set(epe.ECOLOGY) == {"ECO0", "ECO1", "ECO2", "ECO3"}
    assert epe.ECOLOGY["ECO0"]["start"] == (4, 3)
    assert epe.ECOLOGY["ECO2"]["start"] == (1, 1)
    assert epe.ECOLOGY["ECO3"]["start"] == (0, 0)
    assert "Q" not in epe.ECOLOGY["ECO1"]["why"]
    assert epe.SEEDS == (17, 23, 41, 59, 83)
    assert epe.PRIMARY == 96


def test_still_no_ordinary_motor_consumer():
    assert ordinary_runtime_consumes_motor() is False


def test_no_cognition_leaks():
    assert epe.cognition_leaks({"preact": (0.1, 0, 0), "B": (0.7, 0.7, 0.2)}) == []


def test_results_exist():
    root = Path("results/update463_existing_physical_ecology")
    assert (root / "FINAL_REPORT.md").exists()
    assert (root / "PREREGISTRATION.md").exists()
    s = json.loads((root / "summary.json").read_text())
    assert s["audit"]["coupling_none"] is True
    assert s["leak"] == []
    adv = json.loads((root / "adversarial_audit.json").read_text())
    assert adv["5_Q_select"] is False
    assert adv["31_MOVE"] is False
    assert adv["32_USE"] is False
    assert adv["30_threshold"] is False
