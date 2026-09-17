from mechanistic_mind.body.models import BodyConfig
from mechanistic_mind.body.acquired_sensorimotor_coupling import LEARNING_RATE
from mechanistic_mind.body.sensorimotor_dynamics import BASE_NON_WAIT
from mechanistic_mind.research import motor_pathway_archaeology as mpa


def test_defaults_unchanged():
    assert BodyConfig().physical_transduction_config is None
    assert BodyConfig().persistent_process_config is None
    assert LEARNING_RATE == 0.075
    assert BASE_NON_WAIT == 0.08


def test_ordinary_runtime_does_not_consume_internal_motor():
    assert mpa.ordinary_runtime_consumes_motor() is False


def test_no_cognition_leaks():
    assert mpa.cognition_leaks({
        "u": (0, 0, 0), "N": (0.7, 0, 0), "probs": {"M0": 0.1, "WAIT": 0.9},
    }) == []


def test_internal_motor_probe_does_not_invent_a_consumer():
    # The diagnostic must refuse to create an Engine consumer.
    assert "NOT_RUN" in open(
        "mechanistic_mind/research/motor_pathway_archaeology.py"
    ).read()
