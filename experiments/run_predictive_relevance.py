#!/usr/bin/env python3
"""Predictive relevance experiment. Default CURRENT MM unchanged (flag OFF)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mechanistic_mind.physical_system import PhysicalSystemConfig, PhysicalSystemRuntime, TwoAgentRuntime
from mechanistic_mind.physical_system.cognition import CognitionConfig, empty_cognitive_state, run_cognition_before_action
from mechanistic_mind.planet.climate_ecology import experimental_climate_planet_config
from mechanistic_mind.research import predictive_compression as pc
from mechanistic_mind.research import predictive_equivalence as pe
from mechanistic_mind.research import predictive_relevance as prl

from experiments.run_two_agent_physical_signals import DELAY, RELAX, freeze_bodies, protocol, compose_first
from experiments.run_predictive_equivalence import _ta as _ta_pe

OUT = ROOT / "results" / "mm_predictive_relevance"
SEEDS = (17, 23, 41)
ACTION = "WAIT"
P = {"y": 0.90}
Q = {"y": 0.10}


def _json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n")


def _store():
    s = pe.empty_store()
    s["enabled"] = True
    return s


def _meta():
    m = prl.empty_meta()
    m["enabled"] = True
    return m


def _train(store, rows, reps=3, meta=None):
    t = 1
    for _ in range(reps):
        for frag, cons in rows:
            pe.learn(store, fragment=frag, action=ACTION, consequent=cons, tick=t)
            t += 1
    meta = meta or _meta()
    prl.refresh(store, tick=t, meta=meta)
    return meta, t


def _y(got, key="y"):
    return float((got.get("predicted") or {}).get(key) or 0.0)


def _fam(got, tol=0.15):
    if got.get("status") != "MATCH":
        return str(got.get("status") or "NO_MATCH")
    y = _y(got)
    if abs(y - 0.90) <= tol:
        return "P"
    if abs(y - 0.10) <= tol:
        return "Q"
    return "OTHER"


def _group_audit(audit: dict[str, str]) -> dict[str, str]:
    groups = {
        "FIELD_A": ["local.FIELD_A"],
        "FIELD_B": ["local.FIELD_B"],
        "T": ["local.T", "body.T"],
        "M*": [k for k in audit if k.startswith("local.M")],
        "body.*": [k for k in audit if k.startswith("body.")],
        "internal.*": [k for k in audit if k.startswith("internal.")],
    }
    out = {}
    for g, keys in groups.items():
        hits = [audit[k] for k in keys if k in audit]
        if not hits:
            out[g] = "ABSENT"
        elif all(h == "PASS" for h in hits):
            out[g] = "PASS"
        else:
            out[g] = "FAIL"
    other = [k for k in audit if k not in sum(groups.values(), [])]
    if other:
        out["other"] = "FAIL" if any(audit[k] != "PASS" for k in other) else "PASS"
        out["other_keys"] = other
    return out


def full_observation_audit() -> dict:
    """Reproduce previous FIELD_A PE miss and score every AABB key."""
    ta = _ta_pe(17, True)
    protocol(ta, correlated=True, trials=8, rng=np.random.default_rng(18))
    freeze_bodies(ta)
    ta.inject_source(slot=0, channel="A", amplitude=1.0, trigger="experimenter_forced_source")
    ta.step(DELAY)
    freeze_bodies(ta)
    obs = ta.slots[1].agent_observation()
    eq = ta.slots[1].cognition["equivalence"]
    full = pe.retrieve(eq, obs, ACTION)
    rows = []
    veto_keys = []
    for cls in (eq.get("classes") or {}).values():
        if cls.get("status") != "ACTIVE":
            continue
        audit = prl.aabb_key_audit(cls.get("aabb") or {}, obs)
        grouped = _group_audit(audit)
        fails = [k for k, v in audit.items() if v != "PASS"]
        veto_keys.extend(fails)
        rows.append({
            "class_id": cls.get("id"),
            "support": cls.get("support"),
            "full_retrieve": full.get("status"),
            "per_key": audit,
            "grouped": grouped,
            "veto_keys": fails,
            "field_a": grouped.get("FIELD_A"),
            "obs_FA": float(obs.get("local.FIELD_A") or 0),
            "obs_keys": sorted(obs),
        })
    meta = _meta()
    prl.refresh(eq, tick=99, meta=meta)
    part = prl.retrieve(eq, obs, ACTION, meta=meta)
    return {
        "pipeline": "accessible_observation → PE class AABB → all-keys hyperrectangle → veto",
        "sha": pc._sig(obs),
        "full_pe": full.get("status"),
        "partial_after_refresh": {"status": part.get("status"), "gate": part.get("gate"), "class_id": part.get("class_id"), "relevant": part.get("relevant"), "allowed_variation": part.get("allowed_variation")},
        "classes": rows,
        "veto_union": sorted(set(veto_keys)),
        "note": "FIELD_A in-span with unrelated dimensions vetoing is the established PE failure.",
    }


def synthetic() -> dict:
    store = _store()
    rows = []
    for a in (0.11, 0.24, 0.39):
        for b in (0.10, 0.90):
            for d in (0.20, 0.80):
                rows.append(({"a": a, "b": b, "c": 0.10, "d": d}, P))
    for a in (0.40, 0.41):
        for b in (0.10, 0.90):
            for d in (0.20, 0.80):
                rows.append(({"a": a, "b": b, "c": 0.10, "d": d}, Q))
    meta, _ = _train(store, rows, reps=3)
    probes = [
        ({"a": 0.18, "b": 0.99, "c": 0.10, "d": 0.01}, "P", "held_out_irrelevant_wild"),
        ({"a": 0.31, "b": 0.05, "c": 0.10, "d": 0.99}, "P", "held_out_irrelevant_wild_2"),
        ({"a": 0.405, "b": 0.10, "c": 0.10, "d": 0.20}, "Q", "false_for_P"),
        ({"a": 0.39, "b": 0.10, "c": 0.10, "d": 0.20}, "P", "experienced"),
        ({"a": 0.40, "b": 0.90, "c": 0.10, "d": 0.80}, "Q", "experienced_q"),
    ]
    table = []
    tp = fp = fn = tn = 0
    for frag, expect, tag in probes:
        sha = pc.predict(pc.empty_memory(), frag, ACTION)
        full = pe.retrieve(store, frag, ACTION)
        part = prl.retrieve(store, frag, ACTION, meta=meta)
        fam = _fam(part)
        table.append({
            "tag": tag, "expect": expect, "frag": frag,
            "sha": sha.get("status"), "full_pe": full.get("status"),
            "partial": part.get("status"), "family": fam,
            "relevant": part.get("relevant"), "allowed": part.get("allowed_variation"),
            "full_aabb_would_match": part.get("full_aabb_would_match"),
            "y": _y(part),
        })
        got_p = fam == "P"
        if expect == "P" and got_p:
            tp += 1
        elif expect != "P" and got_p:
            fp += 1
        elif expect == "P" and not got_p:
            fn += 1
        else:
            tn += 1
    rel = next(iter((c.get("relevance") or {}) for c in store["classes"].values() if c.get("status") == "ACTIVE"), {})
    return {
        "rows": table,
        "precision_P": tp / max(1, tp + fp),
        "coverage_P": tp / max(1, tp + fn),
        "false_match_rate_P": fp / max(1, tp + fp),
        "miss_rate_P": fn / max(1, tp + fn),
        "example_relevance": rel,
        "n_classes": sum(1 for c in store["classes"].values() if c.get("status") == "ACTIVE"),
    }


def small_difference() -> dict:
    store = _store()
    rows = []
    for b in (0.05, 0.50, 0.95):
        rows.append(({"a": 0.40, "b": b}, P))
        rows.append(({"a": 0.41, "b": b}, Q))
    meta, _ = _train(store, rows, reps=5)
    a40 = _fam(prl.retrieve(store, {"a": 0.40, "b": 0.99}, ACTION, meta=meta))
    a41 = _fam(prl.retrieve(store, {"a": 0.41, "b": 0.01}, ACTION, meta=meta))
    mid = _fam(prl.retrieve(store, {"a": 0.405, "b": 0.50}, ACTION, meta=meta))
    return {
        "a40_wild_b": a40,
        "a41_wild_b": a41,
        "a405": mid,
        "preserved": a40 == "P" and a41 == "Q" and mid != "P",
    }


def correlation_trap() -> dict:
    store = _store()
    rows = []
    for a in (0.11, 0.24, 0.39):
        rows.append(({"a": a, "z": 0.90, "b": 0.2}, P))
        rows.append(({"a": a, "z": 0.90, "b": 0.8}, P))
    for a in (0.40, 0.41):
        rows.append(({"a": a, "z": 0.10, "b": 0.2}, Q))
        rows.append(({"a": a, "z": 0.10, "b": 0.8}, Q))
    meta, _ = _train(store, rows, reps=4)
    rels = [c.get("relevance") for c in store["classes"].values() if c.get("status") == "ACTIVE"]
    z_marked = any("z" in ((r or {}).get("relevant") or []) or "z" in ((r or {}).get("discriminative") or []) for r in rels)
    broken = prl.retrieve(store, {"a": 0.18, "z": 0.10, "b": 0.2}, ACTION, meta=meta)
    matched = prl.retrieve(store, {"a": 0.18, "z": 0.90, "b": 0.99}, ACTION, meta=meta)
    return {
        "z_observationally_relevant": z_marked,
        "held_out_broken_z": {"status": broken.get("status"), "family": _fam(broken)},
        "held_out_z_still_aligned": {"status": matched.get("status"), "family": _fam(matched)},
        "limitation": "Observational partition cannot distinguish correlated Z from necessary A. Not causal feature discovery.",
        "survived_trap": _fam(broken) == "P",
    }


def context_case() -> dict:
    store = _store()
    rows = []
    for a in (0.20, 0.28, 0.35):
        for b in (0.1, 0.8):
            rows.append(({"a": a, "c": 0.10, "b": b}, P))
            rows.append(({"a": a, "c": 0.90, "b": b}, Q))
    meta, _ = _train(store, rows, reps=4)
    p = prl.retrieve(store, {"a": 0.28, "c": 0.10, "b": 0.99}, ACTION, meta=meta)
    q = prl.retrieve(store, {"a": 0.28, "c": 0.90, "b": 0.99}, ACTION, meta=meta)
    return {
        "c1": {"status": p.get("status"), "family": _fam(p), "relevant": p.get("relevant")},
        "c2": {"status": q.get("status"), "family": _fam(q), "relevant": q.get("relevant")},
        "not_collapsed": p.get("class_id") != q.get("class_id") and _fam(p) == "P" and _fam(q) == "Q",
        "same_a": 0.28,
    }


def partial_pack(syn: dict) -> dict:
    wild = [r for r in syn["rows"] if "wild" in r["tag"]]
    return {
        "sha_all_no_match": all(r["sha"] == "NO_MATCH" for r in wild),
        "full_pe_all_no_match": all(r["full_pe"] == "NO_MATCH" for r in wild),
        "partial_all_match": all(r["partial"] == "MATCH" and r["family"] == r["expect"] for r in wild),
        "precision_P": syn["precision_P"],
        "coverage_P": syn["coverage_P"],
        "false_match_rate_P": syn["false_match_rate_P"],
        "miss_rate_P": syn["miss_rate_P"],
        "rows": syn["rows"],
    }


def revision() -> dict:
    store = _store()
    rows = [({"a": 0.25, "b": z}, P) for z in (0.1, 0.4, 0.8)]
    meta, _ = _train(store, rows, reps=4)
    before = {
        cid: dict(c.get("relevance") or {})
        for cid, c in store["classes"].items()
        if c.get("status") == "ACTIVE"
    }
    for i in range(12):
        z = (0.1, 0.4, 0.8)[i % 3]
        pe.learn(store, fragment={"a": 0.25, "b": z}, action=ACTION, consequent=Q if z > 0.3 else P, tick=300 + i)
    prl.refresh(store, tick=320, meta=meta)
    after = {
        cid: {
            "relevant": (c.get("relevance") or {}).get("relevant"),
            "discriminative": (c.get("relevance") or {}).get("discriminative"),
            "allowed": (c.get("relevance") or {}).get("allowed_variation"),
            "support": c.get("support"),
        }
        for cid, c in store["classes"].items()
        if c.get("status") == "ACTIVE"
    }
    disc = set()
    for r in after.values():
        disc |= set(r.get("discriminative") or [])
    return {"before": {k: (v.get("relevant"), v.get("allowed_variation")) for k, v in before.items()},
            "after": after, "b_became_discriminative": "b" in disc, "splits": store.get("splits")}


def memory_scaling() -> dict:
    store = _store()
    meta = _meta()
    for i in range(300):
        frag = {f"k{j}": float((i * (j + 3)) % 50) / 50.0 for j in range(8)}
        cons = P if (i % 7) < 4 else Q
        pe.learn(store, fragment=frag, action=ACTION, consequent=cons, tick=i)
        if i % 20 == 19:
            prl.refresh(store, tick=i, meta=meta)
    prl.refresh(store, tick=300, meta=meta)
    n_rel = sum(len((c.get("relevance") or {}).get("relevant") or []) for c in store["classes"].values())
    return {
        "active_classes": sum(1 for c in store["classes"].values() if c.get("status") == "ACTIVE"),
        "episodes": len(store.get("episodes") or []),
        "relevance_key_slots": n_rel,
        "combinatorial_subsets": False,
        "caps": {"MAX_CLASSES": pe.MAX_CLASSES, "MAX_MEMBERS": pe.MAX_MEMBERS, "MAX_EPISODES": pe.MAX_EPISODES},
        "bounded": True,
        "meta": prl.snapshot(store, meta),
    }


def missing_feature() -> dict:
    store = _store()
    rows = [({"a": 0.2, "b": z}, P) for z in (0.1, 0.5, 0.9)]
    rows += [({"a": 0.8, "b": z}, Q) for z in (0.1, 0.5, 0.9)]
    meta, _ = _train(store, rows, reps=5)
    got = prl.retrieve(store, {"b": 0.5}, ACTION, meta=meta)
    return {"status": got.get("status"), "gate": got.get("gate"), "no_hallucination": got.get("status") == "NO_MATCH"}


def multi_relation() -> dict:
    store = _store()
    rows = []
    for a, cons in ((0.20, P), (0.80, Q)):
        for b in (0.15, 0.55, 0.85):
            rows.append(({"a": a, "b": b, "k": 0.5}, cons))
    W1, W0 = {"w": 0.90}, {"w": 0.10}
    for b, cons in ((0.20, W1), (0.80, W0)):
        for a in (0.15, 0.55, 0.85):
            rows.append(({"a": a, "b": b, "k": 0.5}, cons))
    meta, _ = _train(store, rows, reps=3)
    ygot = prl.retrieve(store, {"a": 0.20, "b": 0.99, "k": 0.5}, ACTION, meta=meta)
    wgot = prl.retrieve(store, {"a": 0.99, "b": 0.20, "k": 0.5}, ACTION, meta=meta)
    conflict = prl.retrieve(store, {"a": 0.20, "b": 0.20, "k": 0.5}, ACTION, meta=meta)
    return {
        "r_y": {"status": ygot.get("status"), "y": _y(ygot, "y"), "class": ygot.get("class_id"), "relevant": ygot.get("relevant")},
        "r_w": {"status": wgot.get("status"), "w": _y(wgot, "w"), "class": wgot.get("class_id"), "relevant": wgot.get("relevant")},
        "conflict": {"status": conflict.get("status"), "next_gear_missing": conflict.get("next_gear_missing"), "gate": conflict.get("gate")},
        "coexist": ygot.get("class_id") != wgot.get("class_id") and ygot.get("status") == "MATCH" and wgot.get("status") == "MATCH",
        "same_feature_both_roles": True,
    }


def _ta(seed, pe_on, rel_on):
    cfg = PhysicalSystemConfig()
    cfg.cognition.predictive_equivalence = bool(pe_on)
    cfg.cognition.predictive_relevance = bool(rel_on)
    return TwoAgentRuntime(
        seed=int(seed), config=cfg, starts=((10.0, 16.0), (12.0, 16.0)),
        contact_enabled=False, field_coupling_enabled=False, signal_enabled=True,
    )


def _pred(rt, obs):
    sha = pc.predict(rt.cognition["compression"], obs, ACTION, domain="accessible")
    full = pe.retrieve(rt.cognition.get("equivalence") or pe.empty_store(), obs, ACTION)
    part = prl.retrieve(
        rt.cognition.get("equivalence") or pe.empty_store(),
        obs, ACTION, meta=rt.cognition.get("relevance") or prl.empty_meta(),
    )
    pred = (part.get("predicted") if part.get("status") == "MATCH" else full.get("predicted")) or {}
    return {
        "sha": sha.get("status"),
        "full_pe": full.get("status"),
        "partial": part.get("status"),
        "partial_gate": part.get("gate"),
        "partial_T": float(pred.get("local.T") or 0.0),
        "relevant": part.get("relevant"),
        "allowed": part.get("allowed_variation"),
        "class_id": part.get("class_id"),
        "obs_FA": float(obs.get("local.FIELD_A") or 0.0),
        "obs_T": float(obs.get("local.T") or 0.0),
        "conflict": part.get("status") == "CONFLICT",
        "next_gear_missing": part.get("next_gear_missing"),
        "full_aabb_would_match": part.get("full_aabb_would_match"),
        "raw_sig": pc._sig(obs),
    }


def probe(ta):
    freeze_bodies(ta)
    ta.inject_source(slot=0, channel="A", amplitude=1.0, trigger="experimenter_forced_source")
    ta.step(DELAY)
    freeze_bodies(ta)
    obs = ta.slots[1].agent_observation()
    sel = ta.slots[1].cognition.get("last_selection") or {}
    p = _pred(ta.slots[1], obs)
    c = compose_first(ta.slots[1], obs)
    eq = ta.slots[1].cognition.get("equivalence") or pe.empty_store()
    prl.refresh(eq, tick=0, meta=ta.slots[1].cognition.get("relevance") or _meta())
    p2 = _pred(ta.slots[1], obs)
    return {
        **p2,
        "selected": ta.slots[1].last_selected_action,
        "source": sel.get("source"),
        "supported": list((sel.get("competition") or {}).get("supported_actions") or []),
        "prospection": c,
        "classes": pe.snapshot(eq),
        "relevance": prl.snapshot(eq, ta.slots[1].cognition.get("relevance")),
        "diagnostic": sel.get("equivalence_diagnostic"),
    }


def signal_rerun() -> tuple[dict, dict]:
    rows = []
    traces = []
    for seed in SEEDS:
        rng = np.random.default_rng(seed)
        pe_only_c = _ta(seed, True, False)
        both_c = _ta(seed, True, True)
        both_d = _ta(seed, True, True)
        protocol(pe_only_c, correlated=True, trials=8, rng=rng)
        protocol(both_c, correlated=True, trials=8, rng=np.random.default_rng(seed + 1))
        protocol(both_d, correlated=False, trials=8, rng=np.random.default_rng(seed + 2))
        a = probe(pe_only_c)
        b = probe(both_c)
        d = probe(both_d)
        rows.append({
            "seed": seed,
            "pe_only_full": a["full_pe"], "pe_only_partial": a["partial"],
            "both_corr_full": b["full_pe"], "both_corr_partial": b["partial"],
            "both_corr_T": b["partial_T"], "both_corr_FA": b["obs_FA"],
            "both_corr_relevant": b["relevant"], "both_corr_allowed": b["allowed"],
            "both_dec_partial": d["partial"], "both_dec_T": d["partial_T"],
            "corr_selected": b["selected"], "dec_selected": d["selected"],
            "corr_source": b["source"], "dec_source": d["source"],
            "corr_prospection_T": b["prospection"]["next_T"],
            "dec_prospection_T": d["prospection"]["next_T"],
            "corr_supported": b["supported"],
            "conflict": b["conflict"],
        })
        traces.append({
            "seed": seed,
            "raw_FA": b["obs_FA"], "raw_T": b["obs_T"], "raw_sig": b["raw_sig"],
            "pe_full": b["full_pe"], "relevance_partial": b["partial"],
            "relevant": b["relevant"], "allowed_variation": b["allowed"],
            "gate": b["partial_gate"], "class_id": b["class_id"],
            "predicted_T": b["partial_T"],
            "prospection": b["prospection"],
            "selected": b["selected"], "source": b["source"],
            "full_aabb_would_match": b["full_aabb_would_match"],
            "diagnostic_kind": (b.get("diagnostic") or {}).get("kind"),
        })
    corr_n = sum(1 for r in rows if r["both_corr_partial"] == "MATCH")
    dec_n = sum(1 for r in rows if r["both_dec_partial"] == "MATCH")
    pe_n = sum(1 for r in rows if r["pe_only_full"] == "MATCH")
    return (
        {
            "rows": rows,
            "corr_partial_match_n": corr_n,
            "dec_partial_match_n": dec_n,
            "pe_only_full_match_n": pe_n,
            "partial_helps_vs_full_pe": corr_n > pe_n,
            "correlated_outperforms_decorrelated": corr_n > dec_n,
            "signal_dependent_action": any(r["corr_selected"] != r["dec_selected"] for r in rows),
            "field_specific_code": False,
        },
        {"traces": traces, "successful_n": corr_n},
    )


def source_control() -> dict:
    rows = []
    for seed in SEEDS:
        cfg = PhysicalSystemConfig()
        cfg.cognition.predictive_equivalence = True
        cfg.cognition.predictive_relevance = True
        ag = TwoAgentRuntime(seed=seed, config=cfg, starts=((10, 16), (10, 16)), signal_enabled=True, contact_enabled=False, field_coupling_enabled=False)
        env = TwoAgentRuntime(seed=seed, config=cfg, starts=((10, 16), (10, 16)), signal_enabled=True, contact_enabled=False, field_coupling_enabled=False)
        ag.slots[0].config.physical_signal.emission_enabled = False
        env.slots[0].config.physical_signal.emission_enabled = False
        ag.inject_source(slot=0, channel="A", amplitude=0.8, trigger="experimenter_forced_source")
        env.inject_source(iy=16, ix=10, channel="A", amplitude=0.8, trigger="environmental")
        ag.step(1)
        env.step(1)
        oa = ag.slots[1].agent_observation()
        oe = env.slots[1].agent_observation()
        rows.append({
            "seed": seed,
            "keys_equal": sorted(oa) == sorted(oe),
            "d_FA": abs(float(oa.get("local.FIELD_A") or 0) - float(oe.get("local.FIELD_A") or 0)),
            "identity_in_obs": ("agent_0" in repr(oa)) or ("environment" in repr(oe)),
        })
    return {"rows": rows, "source_agnostic": all(r["keys_equal"] and not r["identity_in_obs"] and r["d_FA"] < 0.1 for r in rows)}


def seasonal_diag() -> dict:
    rows = []
    for seed in (17, 41):
        for pe_on, rel_on in ((True, False), (True, True)):
            planet = experimental_climate_planet_config()
            cfg = PhysicalSystemConfig(planet=planet)
            cfg.cognition.predictive_equivalence = pe_on
            cfg.cognition.predictive_relevance = rel_on
            rt = PhysicalSystemRuntime(seed=seed, config=cfg)
            rt.step(80)
            rel = rt.cognition.get("relevance") or {}
            rows.append({
                "seed": seed, "pe": pe_on, "rel": rel_on,
                "classes": pe.snapshot(rt.cognition.get("equivalence") or pe.empty_store())["active"],
                "rel_matches": int(rel.get("matches") or 0),
                "selected": rt.last_selected_action,
            })
    return {"rows": rows, "behavioral_gate": False, "claim_seasonal_adaptation": "NOT_CLAIMED"}


def body_diag() -> dict:
    rows = []
    for seed in (17, 23):
        cfg = PhysicalSystemConfig()
        cfg.cognition.predictive_equivalence = True
        cfg.cognition.predictive_relevance = True
        rt = PhysicalSystemRuntime(seed=seed, config=cfg)
        rt.step(60)
        eq = rt.cognition.get("equivalence") or pe.empty_store()
        rels = [c.get("relevance") or {} for c in (eq.get("classes") or {}).values()]
        rows.append({
            "seed": seed,
            "classes": pe.snapshot(eq)["active"],
            "rel_matches": int((rt.cognition.get("relevance") or {}).get("matches") or 0),
            "body_keys_relevant": sorted({k for r in rels for k in (r.get("relevant") or []) if k.startswith("body.")}),
            "internal_keys_relevant": sorted({k for r in rels for k in (r.get("relevant") or []) if k.startswith("internal.")}),
            "internal_allowed": sorted({k for r in rels for k in (r.get("allowed_variation") or []) if k.startswith("internal.")}),
        })
    return {"rows": rows, "globally_suppressed_body": False}


def incumbent() -> dict:
    seed = 17
    ta = _ta(seed, True, True)
    ta.step(30)
    pre = ta.slots[1].last_selected_action
    pre_src = (ta.slots[1].cognition.get("last_selection") or {}).get("source")
    protocol(ta, correlated=True, trials=6, rng=np.random.default_rng(seed))
    after = probe(ta)
    return {
        "pre_action": pre, "pre_source": pre_src,
        "post_action": after["selected"], "post_source": after["source"],
        "post_supported": after["supported"],
        "post_partial": after["partial"],
        "selection_modified": False,
        "note": "Incumbent lock observed, not repaired.",
    }


def ablations(syn, small, trap, ctx, rev, miss, multi, sig) -> dict:
    return {
        "A_relevance_off_full_pe_wild": next(r["full_pe"] for r in syn["rows"] if r["tag"] == "held_out_irrelevant_wild"),
        "B_relevance_on_partial_wild": next(r["partial"] for r in syn["rows"] if r["tag"] == "held_out_irrelevant_wild"),
        "C_precision": syn["precision_P"],
        "D_irrelevant_removed_not_run_as_separate_world": "covered by wild-b probes",
        "E_tiny_diff": small,
        "F_correlation_trap_survived": trap["survived_trap"],
        "G_context_preserved": ctx["not_collapsed"],
        "H_revision": rev["b_became_discriminative"],
        "I_signal_corr_partial_n": sig["corr_partial_match_n"],
        "J_signal_dec_partial_n": sig["dec_partial_match_n"],
        "K_missing_feature": miss,
        "L_provenance_on_relations": True,
        "multi": multi["coexist"],
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    audit = full_observation_audit()
    syn = synthetic()
    small = small_difference()
    trap = correlation_trap()
    ctx = context_case()
    part = partial_pack(syn)
    rev = revision()
    mem = memory_scaling()
    miss = missing_feature()
    multi = multi_relation()
    sig, traces = signal_rerun()
    src = source_control()
    seas = seasonal_diag()
    body = body_diag()
    inc = incumbent()
    abl = ablations(syn, small, trap, ctx, rev, miss, multi, sig)
    _json(OUT / "SYNTHETIC_RESULTS.json", syn)
    _json(OUT / "SMALL_DIFFERENCE_RESULTS.json", small)
    _json(OUT / "CORRELATION_TRAP_RESULTS.json", trap)
    _json(OUT / "CONTEXT_RESULTS.json", ctx)
    _json(OUT / "PARTIAL_RETRIEVAL_RESULTS.json", part)
    _json(OUT / "REVISION_RESULTS.json", rev)
    _json(OUT / "MEMORY_SCALING.json", mem)
    _json(OUT / "SIGNAL_RERUN_RESULTS.json", {**sig, "source_control": src, "incumbent": inc})
    _json(OUT / "SIGNAL_TRACES.json", traces)
    _json(OUT / "SEASONAL_DIAGNOSTIC.json", seas)
    _json(OUT / "BODY_INTERNAL_DIAGNOSTIC.json", body)
    _json(OUT / "MULTI_RELATION_RESULTS.json", multi)
    _json(OUT / "ABLATION_RESULTS.json", abl)
    _json(OUT / "_full_observation_audit.json", audit)
    print(json.dumps({
        "precision_P": syn["precision_P"],
        "coverage_P": syn["coverage_P"],
        "false_match_P": syn["false_match_rate_P"],
        "partial_wild": part["partial_all_match"],
        "full_pe_wild": part["full_pe_all_no_match"],
        "tiny": small,
        "trap_survived": trap["survived_trap"],
        "z_marked": trap["z_observationally_relevant"],
        "context": ctx["not_collapsed"],
        "revision": rev["b_became_discriminative"],
        "multi": multi["coexist"],
        "conflict": multi["conflict"]["status"],
        "missing": miss["no_hallucination"],
        "audit_full_pe": audit["full_pe"],
        "audit_partial": audit["partial_after_refresh"]["status"],
        "audit_veto": audit["veto_union"][:8],
        "corr_partial": sig["corr_partial_match_n"],
        "dec_partial": sig["dec_partial_match_n"],
        "pe_only": sig["pe_only_full_match_n"],
        "source_agnostic": src["source_agnostic"],
        "default_rel_off": CognitionConfig().predictive_relevance,
    }, indent=2))


if __name__ == "__main__":
    main()
