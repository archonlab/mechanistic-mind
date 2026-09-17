from mechanistic_mind.body.acquired_sensorimotor_coupling import LEARNING_RATE, WEIGHT_BOUND
from mechanistic_mind.body.sensorimotor_dynamics import BASE_NON_WAIT
from mechanistic_mind.research import endogenous_dynamic_range as edr


def test_architecture_constants_unchanged():
    assert LEARNING_RATE == 0.075
    assert WEIGHT_BOUND == 0.65
    assert BASE_NON_WAIT == 0.08


def test_probe_is_not_natural():
    assert edr.probe_sample()["klass"] == "PROBE_ONLY"
    g = edr.grid_for_seed(17)
    assert g["N_BASE_MID"][0]["klass"] == "NATURAL_RUNTIME"
    assert g["C_Q_PRESENT"][0]["klass"] == "EXISTING_CONTROLLED_CONDITION"
    assert "H_COUPLED" not in g


def test_no_cognition_leaks():
    g = edr.grid_for_seed(41)
    row = g["N_BASE_MID"][0]
    assert edr.cognition_leaks({"N": row["N"], "q": row["q"]}) == []
