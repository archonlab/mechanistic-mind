from mechanistic_mind.body.adaptive_internal_coupling import AdaptiveInternalState
from mechanistic_mind.research import body_coupled_development as bcd


def test_x_and_a_are_distinct_channels():
    assert bcd.X != bcd.A_PAT
    assert bcd.X[0] > 0 and bcd.A_PAT[1] > 0
    assert bcd.INTERACT_ACTION == "M1"


def test_wait_continues_body_physics():
    b = bcd.initial_body()
    later = bcd.autonomous_drift(b)
    assert bcd.body_l1(later, b) > 0


def test_immediate_matched_distal_differs():
    ctrl = bcd.immediate_vs_distal_control()
    assert ctrl["matched_immediate"]
    assert ctrl["distal_differs"]


def test_h1_modifies_w_h5_does_not():
    h1, _, _ = bcd.develop("H1", trials=12, seed=17)
    h5, _, _ = bcd.develop("H5", trials=12, seed=17, plasticity=False)
    naive = AdaptiveInternalState()
    assert bcd.weight_l1(h1, naive) > 0.05
    assert bcd.weight_l1(h5, naive) == 0


def test_probe_omits_future_event_and_has_no_osv():
    h1, _, _ = bcd.develop("H1", trials=8, seed=23)
    p = bcd.autonomous_probe(h1, seed=23, n_samples=8)
    assert p["event_present"] is False
    assert p["ordinary_state_value"] == 0
    assert p["prediction_runtime_contribution"] == 0.0
    assert p["motor"]["provenance"]["ordinary_state_value"] == 0


def test_cognition_payload_has_no_semantic_leaks():
    h1, _, _ = bcd.develop("H1", trials=6, seed=41)
    p = bcd.autonomous_probe(h1, seed=41, n_samples=4)
    leak = bcd.cognition_leaks({"q": p["q"], "I": p["I"], "N": p["N"], "probs": p["motor"]["probs"], "body": p["body0"]})
    assert leak == []
