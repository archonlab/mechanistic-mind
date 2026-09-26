"""Exact packed-L1 kernel vs dict-oracle _frag_distance."""
from __future__ import annotations

import math
import os
from copy import deepcopy

from mechanistic_mind.research import prospective_composition as pr
from mechanistic_mind.research import psc_opt


CHANNELS_68 = (
    [f"body.{k}" for k in ("T", "B0", "B1", "B2", "mech", "vx", "vy")]
    + [f"local.{k}" for k in ("T", "M0", "M1", "M2", "vx", "vy", "FIELD_A", "FIELD_B")]
    + [f"internal.c{i}" for i in range(5)]
    + [f"exo_{i}" for i in range(3)]
    + [f"surface_c{c}_{i}" for c in range(3) for i in range(3)]
    + [f"spatial_exo_a{i}" for i in range(5)]
    + [f"spatial_surface_c{c}_a{i}" for c in range(3) for i in range(5)]
    + ["vest_0", "vest_1", "prop_neck_0", "prop_neck_1"]
    + [f"osc_{side}_{i}" for i in range(6) for side in ("l", "r")]
)
assert len(CHANNELS_68) == 68


def _qfrag(seed: int) -> dict[str, float]:
    bins = 5
    out = {}
    x = seed
    for i, k in enumerate(CHANNELS_68):
        x = (x * 1103515245 + 12345 + i) & 0x7FFFFFFF
        q = x % bins
        out[k] = (q + 0.5) / bins
    return out


def _store_for_action(n: int, action: str = "WAIT", *, permute_last: bool = False) -> dict:
    st = pr.empty_store()
    for i in range(n):
        ant = _qfrag(1000 + i)
        if permute_last and i == n - 1:
            ant = _qfrag(1000)
            ant[CHANNELS_68[-1]] = 0.9
        cons = _qfrag(2000 + i)
        for _ in range(3):
            pr.learn_transition(
                st, tick=i, antecedent=ant, action=action, consequent=cons,
            )
    return st


def test_channel_count_fixture():
    assert len(CHANNELS_68) == 68


def test_matrix_matches_dict_distance_bitwise():
    st = _store_for_action(32)
    pack = psc_opt.ensure_pack(st)
    q = _qfrag(42)
    psc_opt.set_packed_l1_mode("dict")
    d_row, d_d = psc_opt.soft_match_packed(pack, q, "WAIT")
    psc_opt.set_packed_l1_mode("matrix")
    m_row, m_d = psc_opt.soft_match_packed(pack, q, "WAIT")
    psc_opt.set_packed_l1_mode("auto")
    assert d_row is not None and m_row is not None
    assert d_row["transition_id"] == m_row["transition_id"]
    assert d_row["key"] == m_row["key"]
    assert math.copysign(1.0, d_d) == math.copysign(1.0, m_d)
    assert d_d == m_d


def test_tie_keeps_first_insertion_order():
    st = pr.empty_store()
    base = {k: 0.5 for k in CHANNELS_68}
    for i in range(3):
        ant = dict(base)
        ant[CHANNELS_68[i]] = 0.7
        for _ in range(3):
            pr.learn_transition(
                st, tick=i, antecedent=ant, action="WAIT", consequent=base,
            )
    pack = psc_opt.ensure_pack(st)
    q = dict(base)
    rows = pack["by_action"]["WAIT"]
    assert len(rows) == 3
    psc_opt.set_packed_l1_mode("dict")
    a, da = psc_opt.soft_match_packed(pack, q, "WAIT")
    psc_opt.set_packed_l1_mode("matrix")
    b, db = psc_opt.soft_match_packed(pack, q, "WAIT")
    psc_opt.set_packed_l1_mode("auto")
    assert a is rows[0] and b is rows[0]
    assert da == db


def test_late_channel_difference_selects_same_row():
    st = _store_for_action(16, permute_last=True)
    pack = psc_opt.ensure_pack(st)
    q = _qfrag(1000)
    q[CHANNELS_68[-1]] = 0.9
    psc_opt.set_packed_l1_mode("dict")
    a, da = psc_opt.soft_match_packed(pack, q, "WAIT")
    psc_opt.set_packed_l1_mode("matrix")
    b, db = psc_opt.soft_match_packed(pack, q, "WAIT")
    psc_opt.set_packed_l1_mode("auto")
    assert a["key"] == b["key"]
    assert da == db


def test_missing_query_key_falls_back_and_matches_oracle():
    st = _store_for_action(8)
    pack = psc_opt.ensure_pack(st)
    q = _qfrag(3)
    q.pop(CHANNELS_68[10])
    pa = pack["packed_actions"]["WAIT"]
    assert psc_opt.soft_match_packed_matrix(pa, q) is None
    psc_opt.set_packed_l1_mode("dict")
    a, da = psc_opt.soft_match_packed(pack, q, "WAIT")
    psc_opt.set_packed_l1_mode("auto")
    b, db = psc_opt.soft_match_packed(pack, q, "WAIT")
    assert a["key"] == b["key"]
    assert da == db


def test_absent_field_vs_zero_is_union_semantics_on_fallback():
    st = pr.empty_store()
    for _ in range(3):
        pr.learn_transition(
            st, tick=0, antecedent={"a": 0.5}, action="WAIT", consequent={"a": 0.5},
        )
    pack = psc_opt.ensure_pack(st)
    q = {"a": 0.5, "b": 0.1}
    # extra query key → matrix gate fails
    assert psc_opt.soft_match_packed_matrix(pack["packed_actions"]["WAIT"], q) is None
    from mechanistic_mind.research.prospective_composition import _frag_distance
    row = pack["by_action"]["WAIT"][0]
    d_ref = _frag_distance(q, row["antecedent"])
    _, d = psc_opt.soft_match_packed(pack, q, "WAIT")
    assert d == d_ref


def test_action_partition_not_full_store():
    st = pr.empty_store()
    for i in range(6):
        ant = _qfrag(i)
        for _ in range(3):
            pr.learn_transition(st, tick=i, antecedent=ant, action="WAIT", consequent=ant)
        for _ in range(3):
            pr.learn_transition(
                st, tick=i, antecedent=ant, action="MOVE:N", consequent=_qfrag(50 + i),
            )
    pack = psc_opt.ensure_pack(st)
    assert len(pack["by_action"]["WAIT"]) == 6
    assert len(pack["by_action"]["MOVE:N"]) == 6
    q = _qfrag(0)
    best, _ = psc_opt.soft_match_packed(pack, q, "WAIT")
    assert best is not None
    assert best["action"] == "WAIT"


def test_exact_key_bypasses_soft_match():
    st = pr.empty_store()
    ant = _qfrag(9)
    for _ in range(3):
        pr.learn_transition(st, tick=0, antecedent=ant, action="WAIT", consequent=ant)
    calls = {"n": 0}
    orig = psc_opt.soft_match_packed

    def wrapped(*a, **k):
        calls["n"] += 1
        return orig(*a, **k)

    psc_opt.soft_match_packed = wrapped
    try:
        r = pr.predict_one_step(st, ant, "WAIT")
    finally:
        psc_opt.soft_match_packed = orig
    assert r["status"] == "MATCH"
    assert calls["n"] == 0


def test_exact_miss_uses_soft_match():
    st = _store_for_action(8)
    q = _qfrag(99999)
    calls = {"n": 0}
    orig = psc_opt.soft_match_packed

    def wrapped(*a, **k):
        calls["n"] += 1
        return orig(*a, **k)

    psc_opt.soft_match_packed = wrapped
    try:
        pr.predict_one_step(st, q, "WAIT")
    finally:
        psc_opt.soft_match_packed = orig
    assert calls["n"] == 1


def test_pack_invalidation_after_learn():
    st = _store_for_action(4)
    p1 = psc_opt.ensure_pack(st)
    v1 = p1["version"]
    id1 = id(p1)
    pr.learn_transition(
        st, tick=99, antecedent=_qfrag(4), action="WAIT", consequent=_qfrag(5),
    )
    p2 = psc_opt.ensure_pack(st)
    assert p2["version"] != v1
    assert id(p2) != id1
    q = _qfrag(4)
    psc_opt.set_packed_l1_mode("dict")
    a, da = psc_opt.soft_match_packed(p2, q, "WAIT")
    psc_opt.set_packed_l1_mode("auto")
    b, db = psc_opt.soft_match_packed(p2, q, "WAIT")
    assert a["key"] == b["key"]
    assert da == db


def test_threshold_no_match_same():
    st = _store_for_action(4)
    q = {k: 0.9 for k in CHANNELS_68}
    a = pr.predict_one_step(deepcopy(st), q, "WAIT", backend="packed")
    psc_opt.set_packed_l1_mode("dict")
    b = pr.predict_one_step(deepcopy(st), q, "WAIT", backend="packed")
    psc_opt.set_packed_l1_mode("auto")
    assert a["status"] == b["status"]
    if a["status"] == "MATCH":
        assert a["key"] == b["key"]


def test_legacy_vs_packed_predict_one_step_on_fixture():
    st = _store_for_action(24)
    q = _qfrag(11)
    a = pr.predict_one_step(deepcopy(st), q, "WAIT", backend="legacy")
    b = pr.predict_one_step(deepcopy(st), q, "WAIT", backend="packed")
    assert a["status"] == b["status"]
    if a["status"] == "MATCH":
        assert a["transition_id"] == b["transition_id"]
        assert a["key"] == b["key"]
        assert a["support"] == b["support"]


def test_many_queries_exact_selection():
    st = _store_for_action(96)
    pack = psc_opt.ensure_pack(st)
    n_ok = 0
    for s in range(80):
        q = _qfrag(s)
        psc_opt.set_packed_l1_mode("dict")
        a, da = psc_opt.soft_match_packed(pack, q, "WAIT")
        psc_opt.set_packed_l1_mode("auto")
        b, db = psc_opt.soft_match_packed(pack, q, "WAIT")
        assert (a is None) == (b is None)
        if a is not None:
            assert a["key"] == b["key"]
            assert da == db
            n_ok += 1
    assert n_ok == 80
    psc_opt.set_packed_l1_mode("auto")


def teardown_function(_fn=None):
    os.environ.pop("MM_PSC_BACKEND", None)
    psc_opt.set_packed_l1_mode("auto")
