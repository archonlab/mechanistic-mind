from mechanistic_mind.body.acquired_sensorimotor_coupling import LEARNING_RATE
from mechanistic_mind.body.sensorimotor_dynamics import BASE_NON_WAIT
from mechanistic_mind.research import ordinary_physical_excitation as ope


def test_architecture_constants_unchanged():
    assert LEARNING_RATE == 0.075
    assert BASE_NON_WAIT == 0.08


def test_field_sample_does_not_write_u():
    st = ope.world_state(seed=17, enabled=True)
    ope.advance(st)
    fields = ope.sample(st, ope.POS_A)
    assert fields.get("chemical_1", 0) > 0.4
    # no API maps fields → physical_input
    assert "physical_input" not in fields


def test_no_cognition_leaks():
    assert ope.cognition_leaks({"u": (0, 0, 0), "N": (0.1, 0.0, 0.0)}) == []
