from dataclasses import replace

from mechanistic_mind.body.models import BodyConfig, BodyState
from mechanistic_mind.body.acquired_sensorimotor_coupling import LEARNING_RATE
from mechanistic_mind.body.physical_transduction import (
    default_transducer_config,
    maybe_step_on_state,
    ports_from_x,
    step_transducer,
)
from mechanistic_mind.body.sensorimotor_dynamics import BASE_NON_WAIT
from mechanistic_mind.research import generic_physical_transduction as gpt


def test_defaults_unchanged():
    assert BodyConfig().physical_transduction_config is None
    assert BodyConfig().persistent_process_config is None
    assert LEARNING_RATE == 0.075
    assert BASE_NON_WAIT == 0.08


def test_inactive_transducer_does_not_step():
    s = BodyState()
    maybe_step_on_state(s, BodyConfig())
    assert s.transducer_state == (0.0, 0.0, 0.0)
    assert s.transducer_prev is None


def test_experimental_step_is_bounded_and_causal():
    s = BodyState()
    cfg = replace(BodyConfig(), physical_transduction_config=default_transducer_config("ABSOLUTE"))
    maybe_step_on_state(s, cfg)
    assert s.transducer_prev is not None
    assert all(-1.0 <= x <= 1.0 for x in s.transducer_state)
    assert s.transducer_state != (0.0, 0.0, 0.0)


def test_same_local_rule_no_named_439_map():
    x = step_transducer((0, 0, 0), (0.8, 0.8, 0.8), None, mode="ABSOLUTE")
    assert abs(x[0] - x[1]) < 1e-12 and abs(x[1] - x[2]) < 1e-12
    a, c = ports_from_x(x)
    assert 0.0 <= a <= 1.0 and 0.0 <= c <= 1.0


def test_no_cognition_leaks():
    assert gpt.cognition_leaks({
        "u": (0, 0, 0), "N": (0.1, 0.0, 0.0), "X": (0.05, 0.0, 0.0),
        "ports": (0.52, 0.48),
    }) == []
