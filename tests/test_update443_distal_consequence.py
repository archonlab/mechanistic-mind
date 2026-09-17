from mechanistic_mind.research import distal_consequence as dc
from mechanistic_mind.body.adaptive_internal_coupling import AdaptiveInternalState


def test_x_and_a_remain_distinct():
    assert dc.X != dc.A_PAT


def test_eligibility_in_window_at_d1_out_at_d3():
    in_w = dc.eligibility_snapshot(2)
    out_w = dc.eligibility_snapshot(12)
    assert in_w["in_window"]
    assert not out_w["in_window"]
    assert in_w["update_mag_at_B"] > out_w["update_mag_at_B"]


def test_h1b_and_h2_match_event_counts():
    _, _, a = dc.develop("H1B", trials=12, seed=17)
    _, _, b = dc.develop("H2", trials=12, seed=17)
    assert a["X"] == b["X"] == 12
    assert a["A"] == b["A"] == 12
    assert a["B"] == b["B"] == 12


def test_h1_has_no_b():
    _, _, s = dc.develop("H1", trials=8, seed=17)
    assert s["B"] == 0 and s["A"] == 8


def test_learning_rule_not_reimplemented():
    import inspect
    from mechanistic_mind.body import adaptive_internal_coupling as aic
    src = inspect.getsource(aic.step)
    assert "LEARNING_RATE" in src
    assert "CREDIT" not in src.upper()


def test_no_cognition_leaks():
    h2, _, _ = dc.develop("H2", trials=8, seed=23)
    p = dc.probe(h2, seed=23, n_samples=4)
    assert dc.cognition_leaks({"q": p["q"], "I": p["I"], "N": p["N"], "W": h2.weights}) == []
