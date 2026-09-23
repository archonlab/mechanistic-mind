"""PSC prediction backend equivalence and provenance."""
from __future__ import annotations

import os
from copy import deepcopy

from mechanistic_mind.model.tiktaalik import tiktaalik_config
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.research import prospective_composition as pr
from mechanistic_mind.research import psc_opt


def _rt(seed: int = 19):
    cfg = tiktaalik_config()
    cfg.planet.width = 12
    cfg.planet.height = 12
    return TwoAgentRuntime(seed=seed, config=cfg)


def _rk(r: dict):
    return (
        r.get("status"),
        r.get("key"),
        r.get("transition_id"),
        r.get("support"),
        None if r.get("reliability") is None else round(float(r["reliability"]), 10),
        tuple(sorted((k, round(float(v), 10)) for k, v in (r.get("predicted") or {}).items())),
    )


def test_legacy_packed_numba_match_on_live_store():
    rt = _rt(19)
    for _ in range(60):
        rt.step(1)
    store = rt.slots[0].cognition["prospection"]
    obs = rt.slots[0].agent_observation()
    for act in ("WAIT", "MOVE:N", "MOVE:S", "MOVE:E", "MOVE:W"):
        a = pr.predict_one_step(deepcopy(store), obs, act, backend="legacy")
        b = pr.predict_one_step(deepcopy(store), obs, act, backend="packed")
        c = pr.predict_one_step(deepcopy(store), obs, act, backend="numba")
        assert _rk(a) == _rk(b) == _rk(c)


def test_empty_and_single_candidate():
    empty = pr.empty_store()
    r1 = pr.predict_one_step(empty, {"body.T": 0.5}, "WAIT", backend="legacy")
    r2 = pr.predict_one_step(empty, {"body.T": 0.5}, "WAIT", backend="packed")
    assert r1["status"] == r2["status"] == "NO_MATCH"

    st = pr.empty_store()
    for i in range(5):
        pr.learn_transition(
            st, tick=i, antecedent={"body.T": 0.5, "body.B0": 0.1},
            action="WAIT", consequent={"body.T": 0.5, "body.B0": 0.1},
        )
    a = pr.predict_one_step(st, {"body.T": 0.5, "body.B0": 0.1}, "WAIT", backend="legacy")
    b = pr.predict_one_step(st, {"body.T": 0.5, "body.B0": 0.1}, "WAIT", backend="packed")
    assert a["status"] == b["status"] == "MATCH"
    assert _rk(a) == _rk(b)


def test_pack_invalidation_on_learn():
    st = pr.empty_store()
    pr.learn_transition(
        st, tick=1, antecedent={"x": 0.5}, action="WAIT", consequent={"x": 0.5},
    )
    p1 = psc_opt.ensure_pack(st)
    v1 = p1["version"]
    pr.learn_transition(
        st, tick=2, antecedent={"x": 0.5}, action="WAIT", consequent={"x": 0.6},
    )
    p2 = psc_opt.ensure_pack(st)
    assert p2["version"] != v1


def test_backend_env_and_provenance():
    os.environ["MM_PSC_BACKEND"] = "legacy"
    assert psc_opt.resolve_backend() == "legacy"
    os.environ["MM_PSC_BACKEND"] = "packed"
    assert psc_opt.resolve_backend() == "packed"
    prov = psc_opt.backend_provenance()
    assert "psc_prediction_backend" in prov
    assert "note" in prov


def test_seed_trajectory_match_legacy_packed():
    digests = []
    for backend in ("legacy", "packed"):
        os.environ["MM_PSC_BACKEND"] = backend
        rt = _rt(41)
        for _ in range(120):
            rt.step(1)
        digests.append((
            round(rt.slots[0].body.x, 8),
            round(rt.slots[0].body.y, 8),
            rt.slots[0].last_selected_action,
            int(rt.tick),
        ))
    assert digests[0] == digests[1]
    os.environ["MM_PSC_BACKEND"] = "packed"
