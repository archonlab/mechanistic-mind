from mechanistic_mind.body.acquired_sensorimotor_coupling import AcquiredCouplingState
from mechanistic_mind.body.sensorimotor_dynamics import SensorimotorState, motor_distribution
from mechanistic_mind.research import acquired_sensorimotor_coupling as smc


def test_default_readout_unchanged_with_zero_R():
    n = SensorimotorState(channels=(0.2, -0.1, 0.3))
    a = motor_distribution(n)
    b = motor_distribution(n, acquired=AcquiredCouplingState().weights, use_acquired=True)
    assert a["probs"] == b["probs"]
    c = motor_distribution(n, acquired=AcquiredCouplingState().weights, use_acquired=False)
    assert a["probs"] == c["probs"]


def test_R_init_is_zero_not_identity():
    r = AcquiredCouplingState()
    assert r.weights == ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
    assert r.weights[0][0] == r.weights[1][2] == 0.0


def test_histories_match_marginals_not_pairs():
    _, _, a = smc.develop("H_A", seed=17)
    _, _, b = smc.develop("H_B", seed=17)
    assert a["n_counts"] == b["n_counts"] == [12, 12, 12]
    assert a["m_counts"] == b["m_counts"] == [12, 12, 12]
    assert a["co_occurrence"] != b["co_occurrence"]
    assert smc.MAP_A != smc.MAP_B


def test_plasticity_off_leaves_R_zero():
    s, _, _ = smc.develop("H_A", seed=23, plasticity=False)
    assert smc.l1(s, AcquiredCouplingState()) == 0


def test_no_cognition_leaks():
    s, _, _ = smc.develop("H_A", seed=41)
    p = smc.probe_n(s, 0)
    assert smc.cognition_leaks({"N": p["N"], "R": s.weights, "probs": p["probs"]}) == []
