"""Prediction-error revision. Default OFF. Does not rewrite history or punish."""
from __future__ import annotations

from mechanistic_mind.physical_system.cognition import CognitionConfig
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.physical_system import scenario_competition as sc
from mechanistic_mind.research import future_sensitive_action as fsa
from mechanistic_mind.research import prediction_error_revision as per
from mechanistic_mind.research import predictive_conflict as pcf
from mechanistic_mind.research import prospective_composition as pr

P = {"y": 0.90}
Q = {"y": 0.10}
PRESENT = {"x": 0.50}
KEY = "WAIT||P"


def _on():
    s = per.empty_store()
    s["enabled"] = True
    return s


def _issue(st, *, tick, support=10, pred=None, key=KEY, action="WAIT", lag=1):
    per.remember(
        st, action=action, predicted=pred or P, key=key, tick=tick, lag=lag,
        source="SNAPSHOT", historical_support=support,
    )


def test_default_off():
    assert CognitionConfig().prediction_error_revision is False
    rt = PhysicalSystemRuntime(seed=17)
    assert rt.config.cognition.prediction_error_revision is False
    assert rt.cognition["prediction_revision"]["enabled"] is False
    off = per.empty_store()
    _issue(off, tick=0, support=10)
    got = per.realize(off, observation=Q, tick=1, last_action="WAIT")
    assert got["status"] == "DISABLED"
    assert per.is_active(off, KEY) is True


def test_historical_count_preserved():
    st = _on()
    _issue(st, tick=0, support=10)
    for t in range(1, 8):
        per.realize(st, observation=Q, tick=t, last_action="WAIT")
        _issue(st, tick=t, support=10)
    rel = st["relations"][KEY]
    assert rel["historical_matches"] == 10
    assert rel["mismatches"] >= 5
    assert rel["historical_matches"] != rel["mismatches"]


def test_one_mismatch_does_not_destroy():
    st = _on()
    _issue(st, tick=0, support=10)
    per.realize(st, observation=Q, tick=1, last_action="WAIT")
    rel = st["relations"][KEY]
    assert rel["consecutive_mismatch"] == 1
    assert rel["active"] is True
    _issue(st, tick=1, support=10)
    per.realize(st, observation=P, tick=2, last_action="WAIT")
    assert st["relations"][KEY]["active"] is True
    assert st["relations"][KEY]["consecutive_mismatch"] == 0
    assert st["relations"][KEY]["historical_matches"] == 11


def test_repeated_mismatch_invalidates_without_new_policy():
    st = _on()
    _issue(st, tick=0, support=10)
    for t in range(1, 7):
        per.realize(st, observation=Q, tick=t, last_action="WAIT")
        _issue(st, tick=t, support=10)
    assert st["relations"][KEY]["active"] is False
    assert st["relations"][KEY]["historical_matches"] == 10


def test_stronger_prior_persists_longer():
    def fails_until_inactive(n_hist):
        st = _on()
        key = f"k{n_hist}"
        _issue(st, tick=0, support=n_hist, key=key)
        t = 0
        while st["relations"][key]["active"]:
            t += 1
            per.realize(st, observation=Q, tick=t, last_action="WAIT")
            _issue(st, tick=t, support=n_hist, key=key)
            if t > 40:
                break
        return t

    assert fails_until_inactive(20) > fails_until_inactive(5) >= fails_until_inactive(3)


def test_recovery_without_delete():
    st = _on()
    _issue(st, tick=0, support=6)
    for t in range(1, 6):
        per.realize(st, observation=Q, tick=t, last_action="WAIT")
        _issue(st, tick=t, support=6)
    assert st["relations"][KEY]["active"] is False
    per.realize(st, observation=P, tick=10, last_action="WAIT")
    assert st["relations"][KEY]["active"] is True
    assert KEY in st["relations"]


def test_lag_not_scored_early():
    st = _on()
    _issue(st, tick=0, support=10, lag=4)
    r1 = per.realize(st, observation=Q, tick=1, last_action="WAIT")
    assert r1["receipts"] == []
    assert st["relations"][KEY]["mismatches"] == 0
    r4 = per.realize(st, observation=Q, tick=4, last_action="WAIT")
    assert r4["receipts"] and r4["receipts"][0]["mismatch"] is True


def test_shared_ancestry_not_double_counted():
    st = _on()
    per.remember(st, action="WAIT", predicted=P, key="SHA", tick=0, historical_support=10, ancestry=["t0"])
    per.remember(st, action="WAIT", predicted=P, key="TPS", tick=0, lag=1, historical_support=10, ancestry=["t0"])
    per.realize(st, observation=Q, tick=1, last_action="WAIT")
    assert st["relations"]["SHA"]["mismatches"] == 1
    assert st["relations"].get("TPS", {}).get("mismatches", 0) == 0


def test_weakening_wait_lets_existing_move_win():
    st = _on()
    wait_c = pcf.make_continuation(predicted=P, support=10, present=PRESENT, action="WAIT", structure_id="WP")
    move_c = pcf.make_continuation(predicted=Q, support=5, present=PRESENT, action="MOVE:N", actions=["MOVE:N"], structure_id="MQ")
    key = wait_c["edges"][0]["key"]
    _issue(st, tick=0, support=10, key=key)
    for t in range(1, 8):
        per.realize(st, observation=Q, tick=t, last_action="WAIT")
        _issue(st, tick=t, support=10, key=key)
    assert st["relations"][key]["active"] is False
    filtered = per.filter_continuations(st, [wait_c, move_c])
    assert len(filtered) == 1
    assert filtered[0]["actions"][0] == "MOVE:N"
    store = pcf.empty_store()
    store["enabled"] = True
    org = pcf.organize(store, filtered)
    meta = fsa.empty_meta()
    meta["enabled"] = True
    groups = fsa.build_groups(
        store=pr.empty_store(), observation=PRESENT, continuations=filtered,
        actions=["WAIT", "MOVE:N"], conflict_candidates=org["candidates"], meta=meta,
    )
    groups = per.filter_groups(st, groups)
    out = sc.compete_scenarios(groups=groups, actions=["WAIT", "MOVE:N"], rng_value=0.0)
    assert out["selected"] == "MOVE:N"
    assert not groups.get("WAIT")


def test_no_invented_action_when_only_wait():
    st = _on()
    wait_c = pcf.make_continuation(predicted=P, support=10, present=PRESENT, action="WAIT", structure_id="WP")
    key = wait_c["edges"][0]["key"]
    _issue(st, tick=0, support=10, key=key)
    for t in range(1, 8):
        per.realize(st, observation=Q, tick=t, last_action="WAIT")
        _issue(st, tick=t, support=10, key=key)
    filtered = per.filter_continuations(st, [wait_c])
    assert filtered == []
    groups = per.filter_groups(
        st,
        {"WAIT": [{"first_action": "WAIT", "source_structure_ids": [key], "current_match_evidence": {"key": key}}], "MOVE:N": []},
    )
    out = sc.compete_scenarios(groups=groups, actions=["WAIT", "MOVE:N"], rng_value=0.0)
    assert out["selected"] is None
    assert out["source"] == "NO_SUPPORT"


def test_flags_remain_off():
    cfg = CognitionConfig()
    assert cfg.predictive_equivalence is False
    assert cfg.temporal_prospection_bridge is False
    assert cfg.predictive_conflict is False
    assert cfg.future_sensitive_action is False
    assert cfg.prediction_error_revision is False
    rt = PhysicalSystemRuntime(seed=3)
    rt.set_mechanism("prediction_error_revision", True)
    assert rt.config.cognition.prediction_error_revision is True
    rt.set_mechanism("prediction_error_revision", False)
    assert rt.config.cognition.prediction_error_revision is False
