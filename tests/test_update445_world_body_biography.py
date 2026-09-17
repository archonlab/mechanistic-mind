from mechanistic_mind.research import world_body_biography as wb
from mechanistic_mind.body.adaptive_internal_coupling import AdaptiveInternalState


def test_coupled_histories_match_marginals_not_pairs():
    _, _, a = wb.develop("H_COUPLED_A", seed=17)
    _, _, b = wb.develop("H_COUPLED_B", seed=17)
    assert a["x_counts"] == b["x_counts"]
    assert a["b_counts"] == b["b_counts"]
    assert wb.PAIRS_A != wb.PAIRS_B


def test_world_and_body_use_distinct_channels():
    assert wb.world_u(0.75)[0] > 0 and wb.world_u(0.75)[1] == 0
    assert wb.body_u(0.75)[1] > 0 and wb.body_u(0.75)[0] == 0


def test_plasticity_off_leaves_W_zero():
    s, _, _ = wb.develop("H_COUPLED_A", seed=23, plasticity=False)
    assert wb.weight_l1(s, AdaptiveInternalState()) == 0


def test_no_cognition_leaks():
    s, _, _ = wb.develop("H_COUPLED_A", seed=41)
    p = wb.probe(s, seed=41)
    assert wb.cognition_leaks({"q": p["q"], "I": p["I"], "N": p["N"], "W": s.weights}) == []
