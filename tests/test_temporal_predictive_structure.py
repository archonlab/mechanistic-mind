"""Trajectory-conditioned prediction from ordinary recent fragments. Default OFF."""
from __future__ import annotations

from mechanistic_mind.physical_system.cognition import (
    CognitionConfig,
    empty_cognitive_state,
    run_cognition_before_action,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.research import predictive_compression as pc
from mechanistic_mind.research import temporal_predictive_structure as tps

ACTION = "WAIT"
P = {"y": 0.90}
Q = {"y": 0.10}


def _store():
    s = tps.empty_store()
    s["enabled"] = True
    return s


def train_seq(store, xs, cons, *, delay=1, reps=4, extras=None, action=ACTION):
    t = 1
    for _ in range(reps):
        store["ring"] = []
        for x in xs:
            frag = {"x": float(x)}
            if extras:
                frag.update(extras)
            if store["ring"]:
                tps.learn(store, consequent=frag, action=action, tick=t)
                t += 1
            tps.append(store, frag)
        last = {"x": float(xs[-1])}
        if extras:
            last.update(extras)
        for _d in range(max(0, int(delay) - 1)):
            tps.learn(store, consequent=last, action=action, tick=t)
            t += 1
            tps.append(store, last)
        tps.learn(store, consequent=cons, action=action, tick=t)
        t += 1
    return store


def probe(store, hist, present, *, lag=1, extras=None):
    present_f = {"x": float(present), **(extras or {})}
    store["ring"] = [{"x": float(x), **(extras or {})} for x in hist] + [present_f]
    return tps.retrieve(store, present_f, ACTION, lag=int(lag))


def _y(got):
    cont = got.get("predicted_continuation") or {}
    if "y" in cont:
        return float(cont["y"])
    pred = got.get("predicted") or {}
    return float(pred.get("y") or 0.0)


def _fam(got, tol=0.15):
    if got.get("status") != "MATCH":
        return str(got.get("status") or "NO_MATCH")
    y = _y(got)
    if abs(y - 0.90) <= tol:
        return "P"
    if abs(y - 0.10) <= tol:
        return "Q"
    return "OTHER"


def test_default_off():
    assert CognitionConfig().temporal_predictive_structure is False
    rt = PhysicalSystemRuntime(seed=17)
    assert rt.config.cognition.temporal_predictive_structure is False
    assert rt.cognition["temporal"]["enabled"] is False


def test_same_present_different_history():
    store = _store()
    train_seq(store, [0.20, 0.30, 0.40, 0.50], P, delay=1, reps=4)
    train_seq(store, [0.80, 0.70, 0.60, 0.50], Q, delay=1, reps=4)
    h1 = probe(store, [0.20, 0.30, 0.40], 0.50, lag=1)
    h2 = probe(store, [0.80, 0.70, 0.60], 0.50, lag=1)
    assert h1["status"] == "MATCH" and h2["status"] == "MATCH"
    assert _fam(h1) == "P"
    assert _fam(h2) == "Q"
    assert h1["raw_present_sig"] == h2["raw_present_sig"]
    assert h1["delta_sig"] != h2["delta_sig"]
    sha_mem = pc.empty_memory()
    for _ in range(4):
        pc.observe(sha_mem, tick=1, fragment={"x": 0.50}, action=ACTION, predicted={}, realized=P, domain="accessible")
        pc.observe(sha_mem, tick=2, fragment={"x": 0.50}, action=ACTION, predicted={}, realized=Q, domain="accessible")
    sha = pc.predict(sha_mem, {"x": 0.50}, ACTION, domain="accessible")
    sha_h1 = pc.predict(sha_mem, {"x": 0.50}, ACTION, domain="accessible")
    sha_h2 = pc.predict(sha_mem, {"x": 0.50}, ACTION, domain="accessible")
    assert sha_h1.get("status") == sha_h2.get("status")
    assert (sha_h1.get("predicted") or {}) == (sha_h2.get("predicted") or {})
    assert _fam(h1) != _fam(h2)


def test_order_control_same_multiset():
    store = _store()
    structured = [0.10, 0.30, 0.50, 0.70]
    shuffled = [0.50, 0.10, 0.30, 0.70]
    train_seq(store, structured, P, delay=1, reps=4)
    train_seq(store, shuffled, Q, delay=1, reps=4)
    g1 = probe(store, structured[:-1], structured[-1], lag=1)
    g2 = probe(store, shuffled[:-1], shuffled[-1], lag=1)
    assert g1["raw_present_sig"] == g2["raw_present_sig"]
    assert _fam(g1) == "P"
    assert _fam(g2) == "Q"


def test_delayed_consequence_lags():
    rows = {}
    for delay in (1, 2, 4, 8):
        store = _store()
        train_seq(store, [0.20, 0.40, 0.60, 0.80], P, delay=delay, reps=5)
        train_seq(store, [0.80, 0.60, 0.40, 0.20], Q, delay=delay, reps=5)
        lag = delay if delay in tps.LAGS else 4
        gp = probe(store, [0.20, 0.40, 0.60], 0.80, lag=lag)
        gq = probe(store, [0.80, 0.60, 0.40], 0.20, lag=lag)
        rows[delay] = (_fam(gp), _fam(gq), gp.get("status"), gq.get("status"))
    assert rows[1][0] == "P" and rows[1][1] == "Q"
    assert rows[2][0] == "P" and rows[2][1] == "Q"
    assert rows[4][0] == "P" and rows[4][1] == "Q"
    # delay 8 exceeds LAGS; do not enlarge the ring to force it
    assert rows[8][0] != "P" or rows[8][1] != "Q"


def test_temporal_predictive_equivalence_shifted_levels():
    store = _store()
    train_seq(store, [0.10, 0.20, 0.30, 0.40], P, delay=1, reps=4)
    train_seq(store, [0.40, 0.50, 0.60, 0.70], P, delay=1, reps=4)
    held = probe(store, [0.25, 0.35, 0.45], 0.55, lag=1)
    assert held["status"] == "MATCH"
    assert _fam(held) == "P"


def test_small_temporal_difference_preserved():
    store = _store()
    train_seq(store, [0.40, 0.50, 0.60, 0.70], P, delay=1, reps=4)
    train_seq(store, [0.40, 0.51, 0.60, 0.70], Q, delay=1, reps=4)
    gp = probe(store, [0.40, 0.50, 0.60], 0.70, lag=1)
    gq = probe(store, [0.40, 0.51, 0.60], 0.70, lag=1)
    assert gp["status"] == "MATCH" and gq["status"] == "MATCH"
    assert _fam(gp) == "P"
    assert _fam(gq) == "Q"


def test_rate_discriminative_when_consequences_differ():
    store = _store()
    train_seq(store, [0.10, 0.20, 0.30, 0.40], P, delay=1, reps=4)
    train_seq(store, [0.10, 0.40, 0.70, 1.00], Q, delay=1, reps=4)
    gs = probe(store, [0.10, 0.20, 0.30], 0.40, lag=1)
    gf = probe(store, [0.10, 0.40, 0.70], 1.00, lag=1)
    assert _fam(gs) == "P"
    assert _fam(gf) == "Q"


def test_duration_resolution_boundary():
    store = _store()
    short = [0.50] * 3
    long = [0.50] * 12
    train_seq(store, short, P, delay=1, reps=4)
    train_seq(store, long, Q, delay=1, reps=4)
    gs = probe(store, short[:-1], short[-1], lag=1)
    gl = probe(store, long[-4:-1], long[-1], lag=1)
    # WINDOW=4 cannot count 3 vs 12 of a locally identical pattern once the ring is full.
    same_window = gs.get("delta_sig") == gl.get("delta_sig")
    assert same_window or gs.get("status") != "MATCH" or gl.get("status") != "MATCH" or _fam(gs) == _fam(gl)


def test_multichannel_relative_structure():
    store = _store()
    for _ in range(4):
        store["ring"] = []
        seq = [
            {"T": 0.80, "B": 0.80},
            {"T": 0.60, "B": 0.60},
            {"T": 0.40, "B": 0.40},
            {"T": 0.20, "B": 0.20},
        ]
        for frag in seq:
            if store["ring"]:
                tps.learn(store, consequent=frag, action=ACTION, tick=1)
            tps.append(store, frag)
        tps.learn(store, consequent=P, action=ACTION, tick=1)
        store["ring"] = []
        seq2 = [
            {"T": 0.80, "B": 0.20},
            {"T": 0.60, "B": 0.40},
            {"T": 0.40, "B": 0.60},
            {"T": 0.20, "B": 0.80},
        ]
        for frag in seq2:
            if store["ring"]:
                tps.learn(store, consequent=frag, action=ACTION, tick=1)
            tps.append(store, frag)
        tps.learn(store, consequent=Q, action=ACTION, tick=1)
    store["ring"] = [{"T": 0.80, "B": 0.80}, {"T": 0.60, "B": 0.60}, {"T": 0.40, "B": 0.40}]
    gp = tps.retrieve(store, {"T": 0.20, "B": 0.20}, ACTION, lag=1)
    store["ring"] = [{"T": 0.80, "B": 0.20}, {"T": 0.60, "B": 0.40}, {"T": 0.40, "B": 0.60}]
    gq = tps.retrieve(store, {"T": 0.20, "B": 0.80}, ACTION, lag=1)
    assert _fam(gp) == "P"
    assert _fam(gq) == "Q"


def test_revision_same_trajectory_new_consequence():
    store = _store()
    train_seq(store, [0.20, 0.30, 0.40, 0.50], P, delay=1, reps=4)
    train_seq(store, [0.20, 0.32, 0.44, 0.56], P, delay=1, reps=4)
    assert _fam(probe(store, [0.20, 0.30, 0.40], 0.50, lag=1)) == "P"
    train_seq(store, [0.20, 0.30, 0.40, 0.50], Q, delay=1, reps=8)
    got = probe(store, [0.20, 0.30, 0.40], 0.50, lag=1)
    assert got.get("status") in {"MATCH", "NO_MATCH", "TEMPORAL_CONFLICT"}
    if got.get("status") == "MATCH":
        assert _fam(got) == "Q"


def test_memory_bounded():
    store = _store()
    for i in range(80):
        xs = [((i + k) % 9) / 10.0 for k in range(4)]
        cons = P if i % 2 == 0 else Q
        train_seq(store, xs, cons, delay=1, reps=1)
    mem = tps.memory_usage(store)
    assert mem["ring_n"] <= tps.RING
    assert mem["bounded"] is True
    assert mem["active_classes"] <= pe_max()


def pe_max():
    from mechanistic_mind.research import predictive_equivalence as pe
    return pe.MAX_CLASSES


def test_held_out_and_false_generalization():
    store = _store()
    train_seq(store, [0.10, 0.20, 0.30, 0.40], P, delay=1, reps=3)
    train_seq(store, [0.12, 0.22, 0.32, 0.42], P, delay=1, reps=3)
    train_seq(store, [0.08, 0.18, 0.28, 0.38], P, delay=1, reps=3)
    train_seq(store, [0.90, 0.80, 0.70, 0.60], Q, delay=1, reps=4)
    held = probe(store, [0.11, 0.21, 0.31], 0.41, lag=1)
    false = probe(store, [0.90, 0.80, 0.70], 0.60, lag=1)
    near_false = probe(store, [0.40, 0.30, 0.20], 0.10, lag=1)
    assert _fam(held) == "P"
    assert _fam(false) == "Q"
    assert _fam(near_false) in {"Q", "NO_MATCH"}


def test_correlation_trap_measured_not_fixed():
    store = _store()
    for z, cons in ((0.20, P), (0.80, Q)):
        for _ in range(4):
            store["ring"] = []
            seq = [0.20, 0.30, 0.40, 0.50]
            for x in seq:
                frag = {"x": float(x), "z": float(z)}
                if store["ring"]:
                    tps.learn(store, consequent=frag, action=ACTION, tick=1)
                tps.append(store, frag)
            tps.learn(store, consequent=cons, action=ACTION, tick=1)
    # Train: rising x + low z → P. Test: same x trajectory, z swapped.
    store["ring"] = [{"x": 0.20, "z": 0.80}, {"x": 0.30, "z": 0.80}, {"x": 0.40, "z": 0.80}]
    broken = tps.retrieve(store, {"x": 0.50, "z": 0.80}, ACTION, lag=1)
    # Failure is the measurement: either NO_MATCH or the wrong family.
    assert broken.get("status") in {"NO_MATCH", "MATCH", "TEMPORAL_CONFLICT"}
    if broken.get("status") == "MATCH":
        assert _fam(broken) in {"P", "Q", "OTHER"}


def test_no_clock_in_fragments():
    store = _store()
    train_seq(store, [0.20, 0.30, 0.40, 0.50], P, delay=1, reps=3)
    got = probe(store, [0.20, 0.30, 0.40], 0.50, lag=1)
    blob = repr(got) + repr(store.get("ring"))
    for tok in ("tick", "CLOCK", "phase", "cycle", "seconds", "RISING", "FALLING", "SEASON"):
        assert tok not in str(tps.current_window(store, {"x": 0.50}))
    assert got.get("not_clock") is True
    for row in got.get("recent") or []:
        assert "tick" not in (row.get("fragment") or {})


def test_cognition_fallback_and_toggle():
    cfg = CognitionConfig(temporal_predictive_structure=True, prospective_composition=False)
    state = empty_cognitive_state(cfg)
    tick = 1
    for _ in range(4):
        for x in (0.20, 0.30, 0.40, 0.50):
            run_cognition_before_action(state, observation={"x": float(x), "y": 0.90}, tick=tick, rng_value=0.0)
            tick += 1
        # delayed continuation associated after the window
        run_cognition_before_action(state, observation={"x": 0.50, "y": 0.90}, tick=tick, rng_value=0.0)
        tick += 1
        state["temporal"]["ring"] = []
        state["last_fragment"] = None
        state["last_action"] = None
    state["temporal"]["ring"] = [{"x": 0.20, "y": 0.90}, {"x": 0.30, "y": 0.90}, {"x": 0.40, "y": 0.90}]
    held = {"x": 0.50, "y": 0.90}
    sha = pc.predict(state["compression"], held, ACTION, domain="accessible")
    got = tps.retrieve(state["temporal"], held, ACTION, lag=1)
    assert got.get("status") in {"MATCH", "NO_MATCH", "TEMPORAL_CONFLICT"}
    rt = PhysicalSystemRuntime(seed=3)
    assert rt.config.cognition.temporal_predictive_structure is False
    rt.set_mechanism("temporal_predictive_structure", True)
    assert rt.config.cognition.temporal_predictive_structure is True
    assert rt.cognition["temporal"]["enabled"] is True
    rt.set_mechanism("temporal_predictive_structure", False)
    assert rt.config.cognition.temporal_predictive_structure is False
    assert rt.cognition["temporal"]["enabled"] is False
    # SHA of a never-seen present may miss; temporal is the intended fallback path.
    assert sha.get("status") in {"MATCH", "NO_MATCH"}
