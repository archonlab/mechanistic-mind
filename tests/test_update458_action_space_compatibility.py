from mechanistic_mind.body.models import BodyConfig
from mechanistic_mind.body.acquired_sensorimotor_coupling import LEARNING_RATE
from mechanistic_mind.body.sensorimotor_dynamics import BASE_NON_WAIT
from mechanistic_mind.research import action_space_compatibility as asc
from mechanistic_mind.research.motor_pathway_archaeology import ordinary_runtime_consumes_motor


def test_defaults_unchanged():
    assert BodyConfig().physical_transduction_config is None
    assert BodyConfig().persistent_process_config is None
    assert LEARNING_RATE == 0.075
    assert BASE_NON_WAIT == 0.08


def test_still_no_ordinary_motor_consumer():
    assert ordinary_runtime_consumes_motor() is False


def test_preact_permutation_is_label_free():
    g = asc.preact_geometry()
    assert g["softmax_follows_preact_permutation"] is True
    assert g["channels"] == 3


def test_no_cognition_leaks():
    assert asc.cognition_leaks({"u": (0, 0, 0), "N": (0.7, 0, 0), "preact": (0.7, 0, 0)}) == []
