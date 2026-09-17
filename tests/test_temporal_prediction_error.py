"""Temporal prediction-error residuals into existing TPS. Default OFF."""
from __future__ import annotations

from mechanistic_mind.physical_system.cognition import CognitionConfig
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.research import prediction_error_revision as per
from mechanistic_mind.research import predictive_equivalence as pe
from mechanistic_mind.research import prospective_composition as pr
from mechanistic_mind.research import temporal_prediction_error as tpe

PRED = 0.50
ACTION = "WAIT"
TAU = pe.CONTINUATION_LINF


def _on():
    s = tpe.empty_store()
    s["enabled"] = True
    return s


def _real(err: float, pred: float = PRED) -> dict:
    return {"x": pred + err}


def play(store, errs, *, pred=PRED, action=ACTION, lag=1, key="r"):
    tpe.remember(store, action=action, predicted={"x": pred}, tick=0, lag=lag, key=key, ancestry=[key])
    recs = []
    t = 0
    for e in errs:
        t += lag
        got = tpe.ingest(store, observation=_real(e, pred), tick=t, last_action=action)
        recs.extend(got.get("receipts") or [])
        tpe.remember(store, action=action, predicted={"x": pred}, tick=t, lag=lag, key=key, ancestry=[key])
    return recs


def train_window(store, window, nxt, *, reps=4, pred=PRED, action=ACTION):
    for _ in range(reps):
        lags = store.setdefault("lags", {})
        if "1" in lags:
            lags["1"]["ring"] = []
        play(store, list(window) + [nxt], pred=pred, action=action, key="tw")
    return store


def probe(store, hist, present, *, pred=PRED):
    inner = store.setdefault("lags", {}).setdefault("1", __import__(
        "mechanistic_mind.research.temporal_predictive_structure", fromlist=["empty_store"]
    ).empty_store())
    inner["enabled"] = True
    frags = [{"x": float(e)} for e in list(hist) + [present]]
    inner["ring"] = frags
    return tpe.retrieve(store, {"x": float(present)}, ACTION, lag=1, source_lag=1)


def _nx(got) -> float | None:
    cont = got.get("predicted_continuation") or {}
    if "x" in cont:
        return float(cont["x"])
    pred = got.get("predicted") or {}
    if "x" in pred and not str(list(pred)[0]).startswith("d"):
        return float(pred["x"])
    return float(pred["x"]) if "x" in pred else None


def test_default_off():
    assert CognitionConfig().temporal_prediction_error is False
    rt = PhysicalSystemRuntime(seed=17)
    assert rt.config.cognition.temporal_prediction_error is False
    st = rt.cognition.get("temporal_prediction_error") or {}
    assert st.get("enabled") is False
    off = tpe.empty_store()
    tpe.remember(off, action=ACTION, predicted={"x": PRED}, tick=0)
    got = tpe.ingest(off, observation=_real(0.04), tick=1, last_action=ACTION)
    assert got["status"] == "DISABLED"


def test_subthreshold_not_formal_mismatch():
    st = _on()
    recs = play(st, [0.01, 0.03, 0.05, 0.07, 0.09])
    assert recs
    assert all(abs(r["residual"]["x"]) < TAU for r in recs)
    assert all(r["formal_mismatch"] is False for r in recs)
    assert pr.MATCH_TOL == 0.12
    assert TAU == 0.10


def test_noise_vs_directional_retrieve():
    noise = _on()
    drift = _on()
    nseq = [0.04, -0.03, 0.03, -0.04]
    dseq = [0.01, 0.03, 0.05, 0.07]
    train_window(noise, nseq, 0.00, reps=4)
    train_window(drift, dseq, 0.09, reps=4)
    gn = probe(noise, nseq[:3], nseq[3])
    gd = probe(drift, dseq[:3], dseq[3])
    xn, xd = _nx(gn), _nx(gd)
    assert gn.get("status") == "MATCH"
    assert gd.get("status") == "MATCH"
    assert xd is not None and xn is not None
    assert abs(xd) > abs(xn)
    assert xd > 0.04


def test_same_values_different_order():
    a = _on()
    b = _on()
    seq_a = [0.01, 0.03, 0.05, 0.07]
    seq_b = [0.07, 0.01, 0.09, 0.03]
    train_window(a, seq_a, 0.09, reps=4)
    train_window(b, seq_b, -0.02, reps=4)
    ga = probe(a, seq_a[:3], seq_a[3])
    gb = probe(b, seq_b[:3], seq_b[3])
    assert ga.get("status") == "MATCH"
    assert gb.get("status") == "MATCH"
    assert ga.get("delta_sig") != gb.get("delta_sig")
    assert abs((_nx(ga) or 0) - (_nx(gb) or 0)) > 0.03


def test_direction_reversal():
    up = _on()
    down = _on()
    su = [0.01, 0.03, 0.05, 0.07]
    sd = [0.07, 0.05, 0.03, 0.01]
    train_window(up, su, 0.09, reps=4)
    train_window(down, sd, -0.01, reps=4)
    gu = probe(up, su[:3], su[3])
    gd = probe(down, sd[:3], sd[3])
    assert (_nx(gu) or 0) > 0
    assert (_nx(gd) or 0) < 0.03


def test_oscillation_vs_drift():
    osc = _on()
    dri = _on()
    so = [0.08, -0.08, 0.08, -0.08]
    sd = [0.02, 0.04, 0.06, 0.08]
    train_window(osc, so, 0.08, reps=4)
    train_window(dri, sd, 0.10, reps=4)
    go = probe(osc, so[:3], so[3])
    gd = probe(dri, sd[:3], sd[3])
    assert go.get("delta_sig") != gd.get("delta_sig")
    assert (_nx(gd) or 0) > (_nx(go) or 0) - 0.05


def test_held_out_same_deltas():
    st = _on()
    train_window(st, [0.01, 0.03, 0.05, 0.07], 0.09, reps=4)
    got = probe(st, [0.02, 0.04, 0.06], 0.08)
    assert got.get("status") == "MATCH"
    assert (_nx(got) or 0) > 0.04


def test_precursor_predicts_later_residual():
    st = _on()
    train_window(st, [0.02, 0.04, 0.06, 0.08], 0.11, reps=4)
    got = probe(st, [0.02, 0.04, 0.06], 0.08)
    assert got.get("status") == "MATCH"
    nxt = _nx(got)
    assert nxt is not None and nxt > TAU  # later residual would be a formal mismatch
    # but the current residual 0.08 is still MATCH
    assert 0.08 < TAU


def test_does_not_invalidate_before_hard_mismatch():
    st = _on()
    recs = play(st, [0.01, 0.03, 0.05, 0.07, 0.09])
    assert all(r["formal_mismatch"] is False for r in recs)
    rev = per.empty_store()
    rev["enabled"] = True
    per.remember(rev, action=ACTION, predicted={"x": PRED}, key="W", tick=0, historical_support=10)
    for i, e in enumerate([0.01, 0.03, 0.05, 0.07, 0.09], start=1):
        per.realize(rev, observation=_real(e), tick=i, last_action=ACTION)
        per.remember(rev, action=ACTION, predicted={"x": PRED}, key="W", tick=i, historical_support=10)
    assert rev["relations"]["W"]["active"] is True
    assert rev["relations"]["W"]["historical_matches"] == 15  # 10 + 5 matches


def test_lag_not_mixed():
    st = _on()
    tpe.remember(st, action=ACTION, predicted={"x": PRED}, tick=0, lag=4, key="L4", ancestry=["L4"])
    early = tpe.ingest(st, observation=_real(0.09), tick=1, last_action=ACTION)
    assert early.get("receipts") == []
    late = tpe.ingest(st, observation=_real(0.09), tick=4, last_action=ACTION)
    assert late.get("receipts")
    assert late["receipts"][0]["lag"] == 4
    assert "1" not in (st.get("lags") or {}) or not (st["lags"].get("1") or {}).get("ring")
    assert (st.get("lags") or {}).get("4")


def test_shared_ancestry_one_residual():
    st = _on()
    tpe.remember(st, action=ACTION, predicted={"x": PRED}, tick=0, lag=1, key="SHA", ancestry=["t0"])
    tpe.remember(st, action=ACTION, predicted={"x": PRED}, tick=0, lag=1, key="TPS", ancestry=["t0"])
    got = tpe.ingest(st, observation=_real(0.04), tick=1, last_action=ACTION)
    assert len(got.get("receipts") or []) == 1
    assert st.get("skipped_shared_ancestry") == 1


def test_same_present_cycle_histories():
    st = _on()
    # Next residuals ±0.09 differ by > CONTINUATION_LINF so PE will not merge them.
    train_window(st, [-0.06, -0.09, -0.06, 0.00], 0.09, reps=4)
    train_window(st, [0.06, 0.09, 0.06, 0.00], -0.09, reps=4)
    gu = probe(st, [-0.06, -0.09, -0.06], 0.00)
    gd = probe(st, [0.06, 0.09, 0.06], 0.00)
    assert gu.get("status") == "MATCH"
    assert gd.get("status") == "MATCH"
    assert (_nx(gu) or 0) > 0.04
    assert (_nx(gd) or 0) < -0.04


def test_flags_remain_off():
    cfg = CognitionConfig()
    assert cfg.predictive_equivalence is False
    assert cfg.temporal_predictive_structure is False
    assert cfg.temporal_prospection_bridge is False
    assert cfg.predictive_conflict is False
    assert cfg.future_sensitive_action is False
    assert cfg.prediction_error_revision is False
    assert cfg.temporal_prediction_error is False
    rt = PhysicalSystemRuntime(seed=3)
    rt.set_mechanism("temporal_prediction_error", True)
    assert rt.config.cognition.temporal_prediction_error is True
    rt.set_mechanism("temporal_prediction_error", False)
    assert rt.config.cognition.temporal_prediction_error is False
