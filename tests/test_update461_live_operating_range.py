from mechanistic_mind.body.models import BodyConfig
from mechanistic_mind.body.acquired_sensorimotor_coupling import LEARNING_RATE
from mechanistic_mind.body.physical_transduction import DECAY as X_DECAY, SCALE as X_SCALE
from mechanistic_mind.body.sensorimotor_dynamics import BASE_NON_WAIT
from mechanistic_mind.research.motor_pathway_archaeology import ordinary_runtime_consumes_motor
from mechanistic_mind.world_engine.physical_coupling import SCALE as C_SCALE, FAMILY
from mechanistic_mind.world_engine.physical_effector import THRESHOLD, DECAY as E_DECAY
from mechanistic_mind.research import live_operating_range as lor


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


def test_preregistered_grid():
    assert lor.SEEDS == (17, 23, 41, 59, 83)
    assert lor.SHORT == 32 and lor.PRIMARY == 96 and lor.LONG == 144
    assert "NO_OVERLAP" in lor.OVERLAP


def test_still_no_ordinary_motor_consumer():
    assert ordinary_runtime_consumes_motor() is False


def test_no_cognition_leaks():
    assert lor.cognition_leaks({"preact": (0.1, 0, 0), "D": (0.1, 0, 0, 0), "Q": (0.0, -0.1)}) == []
