from mechanistic_mind.body.acquired_sensorimotor_coupling import LEARNING_RATE, TRACE_DECAY, WEIGHT_BOUND
from mechanistic_mind.body.sensorimotor_dynamics import BASE_NON_WAIT
from mechanistic_mind.research import acquired_sensorimotor_coupling as smc
from mechanistic_mind.research import endogenous_motor_access as ema


def test_architecture_constants_unchanged():
    assert LEARNING_RATE == 0.075
    assert WEIGHT_BOUND == 0.65
    assert TRACE_DECAY == 0.62
    assert BASE_NON_WAIT == 0.08


def test_446_endogenous_vector_reproduced():
    traj = ema.capture_endogenous_traj(17)
    N = smc.endogenous_n(seed=17)
    assert traj[-1]["N"] == N.channels


def test_same_N_same_R_same_motor():
    ha, _, _ = smc.develop("H_A", seed=17)
    N = smc.endogenous_n(seed=17)
    a = smc.probe_endogenous(ha, N)
    b = ema.apply_motor(N.channels, ha.weights)
    assert ema.l1(tuple(a["probs"][k] - b["probs"][k] for k in a["probs"])) < 1e-12


def test_no_cognition_leaks():
    ha, _, _ = smc.develop("H_A", seed=41)
    N = smc.endogenous_n(seed=41)
    p = smc.probe_endogenous(ha, N)
    assert ema.cognition_leaks({"N": N.channels, "R": ha.weights, "probs": p["probs"]}) == []
