from mechanistic_mind.research import body_context_interaction as bci
from mechanistic_mind.research import distal_consequence as dc


def test_preregistered_bodies_are_distinct_and_unlabeled():
    assert set(bci.BODIES) == {"B_LOW", "B_MID", "B_HIGH"}
    assert bci.BODIES["B_LOW"] != bci.BODIES["B_HIGH"]
    # names are researcher-side; values are generic keys only
    for b in bci.BODIES.values():
        assert set(b) == {"internal_a", "load_c"}


def test_additive_model_zero_residual_when_additive():
    cells = {"H1": {"B_LOW": 0.1, "B_MID": 0.2, "B_HIGH": 0.3},
             "H2": {"B_LOW": 0.15, "B_MID": 0.25, "B_HIGH": 0.35}}
    m = bci.additive_model(cells)
    assert m["span"] < 1e-12
    assert m["max_abs_residual"] < 1e-12


def test_trajectories_end_at_same_body():
    assert bci.T_DOWN[-1] == bci.T_UP[-1] == bci.BODIES["B_MID"]


def test_no_cognition_leaks_on_numeric_payload():
    h2, _, _ = dc.develop("H2", trials=6, seed=17)
    p = bci.probe_cell(h2, bci.BODIES["B_MID"], seed=17, n_samples=4)
    assert bci.cognition_leaks({"q": p["q"], "I": p["I"], "N": p["N"], "p_A": p["p_A"]}) == []
