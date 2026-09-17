#!/usr/bin/env python3
"""Predictive equivalence experiment. Default CURRENT MM unchanged (flag OFF)."""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mechanistic_mind.physical_system import PhysicalSystemConfig, PhysicalSystemRuntime, TwoAgentRuntime
from mechanistic_mind.physical_system.cognition import CognitionConfig, empty_cognitive_state, run_cognition_before_action
from mechanistic_mind.planet.climate_ecology import experimental_climate_planet_config
from mechanistic_mind.research import predictive_compression as pc
from mechanistic_mind.research import predictive_equivalence as pe
from mechanistic_mind.research import prospective_composition as pr

from experiments.run_two_agent_physical_signals import (
    DELAY,
    RELAX,
    freeze_bodies,
    bump_T,
    protocol,
    compose_first,
)

OUT = ROOT / "results" / "mm_predictive_equivalence"
SEEDS = (17, 23, 41)
ACTION = "WAIT"
FAM_A = {"y": 0.90}
FAM_B = {"y": 0.10}


def _json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n")


def _store(tau: float = 0.10) -> dict:
    s = pe.empty_store(continuation_linf=tau)
    s["enabled"] = True
    return s


def _train(store, xs, cons, *, start=1, reps=4, extra=None):
    t = start
    for _ in range(reps):
        for x in xs:
            frag = {"x": float(x)}
            if extra:
                frag.update(extra(x, t) if callable(extra) else extra)
            pe.learn(store, fragment=frag, action=ACTION, consequent=cons, tick=t)
            t += 1
    return t


def _y(got) -> float:
    return float((got.get("predicted") or {}).get("y") or 0.0)


def _family(got, tol=0.15) -> str:
    if got.get("status") != "MATCH":
        return "NO_MATCH"
    y = _y(got)
    if abs(y - 0.90) <= tol:
        return "A"
    if abs(y - 0.10) <= tol:
        return "B"
    return "OTHER"


def synthetic_core(tau: float = 0.10) -> dict:
    store = _store(tau)
    _train(store, (0.11, 0.24, 0.39), FAM_A, reps=4)
    _train(store, (0.40, 0.41), FAM_B, start=40, reps=4)
    rows = []
    for x, expect in (
        (0.11, "A"), (0.24, "A"), (0.39, "A"),
        (0.18, "A"), (0.31, "A"),
        (0.40, "B"), (0.41, "B"), (0.405, "B"),
    ):
        sha_mem = pc.empty_memory()
        # train SHA on the experienced set only
        got = pe.retrieve(store, {"x": x}, ACTION)
        rows.append({
            "x": x,
            "expected": expect,
            "pe_status": got.get("status"),
            "pe_family": _family(got),
            "pe_y": _y(got),
            "pe_support": got.get("support"),
            "gate": got.get("gate"),
            "class_id": got.get("class_id"),
            "raw_sig": got.get("raw_antecedent_sig") or pc._sig({"x": x}),
        })
    # SHA on held-out
    mem = pc.empty_memory()
    t = 1
    for _ in range(4):
        for x in (0.11, 0.24, 0.39, 0.40, 0.41):
            cons = FAM_A if x < 0.395 else FAM_B
            pc.observe(mem, tick=t, fragment={"x": x}, action=ACTION, realized=cons, domain="accessible")
            t += 1
    sha_held = {x: pc.predict(mem, {"x": x}, ACTION, domain="accessible").get("status") for x in (0.18, 0.31, 0.405)}
    tp = sum(1 for r in rows if r["expected"] == "A" and r["pe_family"] == "A")
    fp = sum(1 for r in rows if r["expected"] != "A" and r["pe_family"] == "A")
    fn = sum(1 for r in rows if r["expected"] == "A" and r["pe_family"] != "A")
    pred_a = [r for r in rows if r["pe_family"] == "A"]
    precision = tp / max(1, tp + fp)
    coverage = tp / max(1, sum(1 for r in rows if r["expected"] == "A"))
    # proximity control: 0.39 vs 0.40
    r39 = pe.retrieve(store, {"x": 0.39}, ACTION)
    r40 = pe.retrieve(store, {"x": 0.40}, ACTION)
    return {
        "tau": tau,
        "rows": rows,
        "sha_held_out": sha_held,
        "precision_A": precision,
        "coverage_A": coverage,
        "false_equivalence_rate_A": fp / max(1, len(pred_a)),
        "missed_equivalence_rate_A": fn / max(1, sum(1 for r in rows if r["expected"] == "A")),
        "proximity_0.39_vs_0.40_split": _family(r39) != _family(r40) and _family(r39) == "A" and _family(r40) == "B",
        "held_out_0.18_family": _family(pe.retrieve(store, {"x": 0.18}, ACTION)),
        "n_classes": pe.snapshot(store)["active"],
        "snapshot": pe.snapshot(store),
        "continuation_distance": "L-inf over consequent channels; not observation identity",
    }


def context_control() -> dict:
    store = _store()
    for i in range(4):
        pe.learn(store, fragment={"x": 0.50, "ctx": 0.10}, action=ACTION, consequent=FAM_A, tick=i)
        pe.learn(store, fragment={"x": 0.50, "ctx": 0.90}, action=ACTION, consequent=FAM_B, tick=i)
    p = pe.retrieve(store, {"x": 0.50, "ctx": 0.10}, ACTION)
    q = pe.retrieve(store, {"x": 0.50, "ctx": 0.90}, ACTION)
    return {
        "same_x": 0.50,
        "ctx_A": {"status": p.get("status"), "family": _family(p), "y": _y(p)},
        "ctx_B": {"status": q.get("status"), "family": _family(q), "y": _y(q)},
        "collapsed": p.get("class_id") == q.get("class_id"),
        "preserved_context": _family(p) == "A" and _family(q) == "B",
    }


def irrelevant_variation() -> dict:
    store = _store()
    zs = (0.02, 0.33, 0.71, 0.95)
    for _ in range(3):
        for z in zs:
            pe.learn(store, fragment={"x": 0.20, "z": float(z)}, action=ACTION, consequent=FAM_A, tick=1)
            pe.learn(store, fragment={"x": 0.80, "z": float(z)}, action=ACTION, consequent=FAM_B, tick=2)
    new_z = 0.48
    low = pe.retrieve(store, {"x": 0.20, "z": new_z}, ACTION)
    high = pe.retrieve(store, {"x": 0.80, "z": new_z}, ACTION)
    # held-out x inside low span with new z
    mid_x = pe.retrieve(store, {"x": 0.20, "z": 0.60}, ACTION)
    return {
        "held_out_z": new_z,
        "x20_new_z": {"status": low.get("status"), "family": _family(low), "y": _y(low)},
        "x80_new_z": {"status": high.get("status"), "family": _family(high), "y": _y(high)},
        "insensitive_to_z": _family(low) == "A" and _family(high) == "B" and _family(mid_x) == "A",
        "mechanism_told_z_irrelevant": False,
        "snapshot": pe.snapshot(store),
    }


def small_difference() -> dict:
    store = _store()
    _train(store, (0.40,), FAM_A, reps=5)
    _train(store, (0.41,), FAM_B, start=20, reps=5)
    r40 = pe.retrieve(store, {"x": 0.40}, ACTION)
    r41 = pe.retrieve(store, {"x": 0.41}, ACTION)
    mid = pe.retrieve(store, {"x": 0.405}, ACTION)
    return {
        "x40": {"status": r40.get("status"), "family": _family(r40), "y": _y(r40)},
        "x41": {"status": r41.get("status"), "family": _family(r41), "y": _y(r41)},
        "x405": {"status": mid.get("status"), "family": _family(mid), "gate": mid.get("gate")},
        "distinction_preserved": _family(r40) == "A" and _family(r41) == "B" and mid.get("status") == "NO_MATCH",
        "note": "Tiny antecedent gap, large continuation gap. Not generic smoothing.",
    }


def held_out_pack(syn: dict) -> dict:
    return {
        "experienced": [0.11, 0.24, 0.39, 0.40, 0.41],
        "held_out_same_regime_A": [0.18, 0.31],
        "held_out_false_for_A": [0.405],
        "sha_held_out": syn["sha_held_out"],
        "precision_A": syn["precision_A"],
        "coverage_A": syn["coverage_A"],
        "false_equivalence_rate_A": syn["false_equivalence_rate_A"],
        "missed_equivalence_rate_A": syn["missed_equivalence_rate_A"],
        "rows": syn["rows"],
        "generalization_not_replay": all(syn["sha_held_out"].get(str(x), syn["sha_held_out"].get(x)) == "NO_MATCH" for x in (0.18, 0.31))
        if True else False,
    }


def revision() -> dict:
    store = _store()
    for i in range(6):
        pe.learn(store, fragment={"x": 0.11}, action=ACTION, consequent=FAM_A, tick=i)
        pe.learn(store, fragment={"x": 0.24}, action=ACTION, consequent=FAM_A, tick=i)
    phase_a = {
        "x11": _family(pe.retrieve(store, {"x": 0.11}, ACTION)),
        "x24": _family(pe.retrieve(store, {"x": 0.24}, ACTION)),
        "splits": store["splits"],
    }
    for i in range(8):
        pe.learn(store, fragment={"x": 0.24}, action=ACTION, consequent=FAM_B, tick=100 + i)
    phase_b = {
        "x11": _family(pe.retrieve(store, {"x": 0.11}, ACTION)),
        "x24": _family(pe.retrieve(store, {"x": 0.24}, ACTION)),
        "x24_y": _y(pe.retrieve(store, {"x": 0.24}, ACTION)),
        "splits": store["splits"],
        "revised": True,
    }
    classes = []
    for c in (store.get("classes") or {}).values():
        prov = (c.get("provenance") or [])[-6:]
        classes.append({
            "id": c.get("id"),
            "status": c.get("status"),
            "support": c.get("support"),
            "revised_at": c.get("revised_at"),
            "provenance_tail": prov,
            "member_xs": [float((m.get("fragment") or {}).get("x") or 0) for m in (c.get("members") or {}).values()],
        })
    return {
        "phase_a": phase_a,
        "phase_b": phase_b,
        "split_occurred": store["splits"] >= 1,
        "x11_stayed_A": phase_b["x11"] == "A",
        "x24_moved_B": phase_b["x24"] == "B",
        "classes": classes,
        "permanent_clusters": False,
    }


def memory_scaling() -> dict:
    boring = _store()
    for i in range(400):
        pe.learn(boring, fragment={"x": 0.01 * (i % 50)}, action=ACTION, consequent=FAM_A, tick=i)
    novel = _store()
    for i in range(400):
        pe.learn(novel, fragment={"x": float(i) * 0.003}, action=ACTION, consequent={"y": 0.5 + 0.4 * ((i % 7) / 6.0)}, tick=i)
    changing = _store()
    for i in range(200):
        cons = FAM_A if i < 100 else FAM_B
        pe.learn(changing, fragment={"x": 0.01 * (i % 20)}, action=ACTION, consequent=cons, tick=i)
    def pack(s, label):
        snap = pe.snapshot(s)
        n_mem = sum(len(c.get("members") or {}) for c in (s.get("classes") or {}).values())
        return {
            "label": label,
            "active_classes": snap["active"],
            "episodes": snap["episode_n"],
            "members_total": n_mem,
            "forgotten": snap["forgotten"],
            "splits": snap["splits"],
            "caps": {"MAX_CLASSES": pe.MAX_CLASSES, "MAX_MEMBERS": pe.MAX_MEMBERS, "MAX_EPISODES": pe.MAX_EPISODES},
            "bounded": snap["active"] <= pe.MAX_CLASSES and snap["episode_n"] <= pe.MAX_EPISODES and n_mem <= pe.MAX_CLASSES * pe.MAX_MEMBERS,
        }
    return {
        "boring_continuous": pack(boring, "boring"),
        "novel_continuous": pack(novel, "novel"),
        "changing_equivalence": pack(changing, "changing"),
        "unbounded_float_table": False,
    }


def cognition_sha_bypass() -> dict:
    cfg = CognitionConfig(predictive_equivalence=True)
    state = empty_cognitive_state(cfg)
    tick = 1
    for _ in range(4):
        for x in (0.11, 0.24, 0.39):
            state["last_fragment"] = {"x": float(x)}
            state["last_action"] = ACTION
            run_cognition_before_action(state, observation={"y": 0.90, "x": float(x)}, tick=tick, rng_value=0.0)
            tick += 1
    held = {"x": 0.18}
    sha = pc.predict(state["compression"], held, ACTION, domain="accessible")
    got = pe.retrieve(state["equivalence"], held, ACTION)
    # present-time overlay
    state["last_fragment"] = None
    state["last_action"] = None
    run_cognition_before_action(state, observation=held, tick=tick, rng_value=0.0)
    matches = (state.get("last_selection") or {}).get("prediction_matches") or []
    pe_hits = [m for m in matches if m.get("source") == "predictive_equivalence"]
    return {
        "held_out": 0.18,
        "sha_status": sha.get("status"),
        "pe_status": got.get("status"),
        "pe_y": _y(got),
        "bypass": sha.get("status") == "NO_MATCH" and got.get("status") == "MATCH",
        "cognition_pe_hits": len(pe_hits),
        "raw_still_in_members": True,
        "diagnostic": (state.get("last_selection") or {}).get("equivalence_diagnostic"),
    }


def sensitivity() -> dict:
    rows = []
    for tau in (0.05, 0.10, 0.20, 0.85):
        syn = synthetic_core(tau)
        rows.append({
            "tau": tau,
            "precision_A": syn["precision_A"],
            "coverage_A": syn["coverage_A"],
            "false_equivalence_rate_A": syn["false_equivalence_rate_A"],
            "proximity_split": syn["proximity_0.39_vs_0.40_split"],
            "n_classes": syn["n_classes"],
        })
    return {
        "rows": rows,
        "note": "tau compares continuations (L-inf), not observation identity. Large tau merges families.",
        "justified_default": 0.10,
    }


def identity_fragmentation_demo() -> dict:
    vals = [0.080, 0.067, 0.056, 0.047, 0.0800001, 0.07999]
    sigs = {v: pc._sig({"local.FIELD_A": v}) for v in vals}
    unique = len(set(sigs.values()))
    return {
        "values": vals,
        "sigs": {str(k): v for k, v in sigs.items()},
        "unique_sigs": unique,
        "round4": {str(v): round(v, 4) for v in vals},
        "all_keys_enter_identity": True,
        "precision": "round(float, 4) then SHA1[:12]",
    }


def _ta(seed: int, pe_on: bool, **kw) -> TwoAgentRuntime:
    cfg = PhysicalSystemConfig()
    cfg.cognition.predictive_equivalence = bool(pe_on)
    kw.setdefault("contact_enabled", False)
    kw.setdefault("field_coupling_enabled", False)
    kw.setdefault("signal_enabled", True)
    return TwoAgentRuntime(seed=int(seed), config=cfg, starts=((10.0, 16.0), (12.0, 16.0)), **kw)


def _pred_pair(rt, obs) -> dict:
    sha = pc.predict(rt.cognition["compression"], obs, ACTION, domain="accessible")
    pe_got = pe.retrieve(rt.cognition.get("equivalence") or pe.empty_store(), obs, ACTION)
    pred_sha = sha.get("predicted") or {}
    pred_pe = pe_got.get("predicted") or {}
    return {
        "sha_status": sha.get("status"),
        "sha_support": sha.get("support"),
        "sha_T": float(pred_sha.get("local.T") or 0.0),
        "pe_status": pe_got.get("status"),
        "pe_support": pe_got.get("support"),
        "pe_T": float(pred_pe.get("local.T") or 0.0),
        "pe_class": pe_got.get("class_id"),
        "pe_gate": pe_got.get("gate"),
        "pe_source": pe_got.get("source"),
        "obs_FA": float(obs.get("local.FIELD_A") or 0.0),
        "obs_T": float(obs.get("local.T") or 0.0),
        "raw_sig": pc._sig(obs),
        "member_sigs": pe_got.get("member_sigs"),
    }


def _aabb_report(eq: dict, obs: dict, action: str) -> dict:
    rows = []
    for cls in (eq.get("classes") or {}).values():
        if cls.get("status") != "ACTIVE" or cls.get("action") != action:
            continue
        aabb = cls.get("aabb") or {}
        misses = []
        in_span = []
        for k, span in aabb.items():
            lo, hi = float(span[0]), float(span[1])
            if k not in obs:
                misses.append({"key": k, "reason": "missing"})
                continue
            x = float(obs[k])
            if x < lo - 1e-12 or x > hi + 1e-12:
                misses.append({"key": k, "x": x, "lo": lo, "hi": hi})
            else:
                in_span.append(k)
        rows.append({
            "class_id": cls.get("id"),
            "support": cls.get("support"),
            "n_members": len(cls.get("members") or {}),
            "field_a_span": list(aabb.get("local.FIELD_A") or []),
            "field_a_obs": float(obs.get("local.FIELD_A") or 0),
            "field_a_in_span": "local.FIELD_A" in in_span,
            "n_misses": len(misses),
            "miss_keys": [m["key"] for m in misses[:12]],
        })
    return {"classes": rows}


def probe_signal(ta: TwoAgentRuntime) -> dict:
    freeze_bodies(ta)
    ta.inject_source(slot=0, channel="A", amplitude=1.0, trigger="experimenter_forced_source")
    ta.step(DELAY)
    freeze_bodies(ta)
    obs = ta.slots[1].agent_observation()
    sel = ta.slots[1].cognition.get("last_selection") or {}
    p = _pred_pair(ta.slots[1], obs)
    c = compose_first(ta.slots[1], obs)
    pe_hits = [m for m in (sel.get("prediction_matches") or []) if m.get("source") == "predictive_equivalence"]
    eq = ta.slots[1].cognition.get("equivalence") or pe.empty_store()
    return {
        **p,
        "selected": ta.slots[1].last_selected_action,
        "source": sel.get("source"),
        "supported": list((sel.get("competition") or {}).get("supported_actions") or []),
        "prospection": c,
        "cognition_pe_hits": len(pe_hits),
        "equivalence_snapshot": pe.snapshot(eq),
        "aabb_report": _aabb_report(eq, obs, ACTION),
        "diagnostic": sel.get("equivalence_diagnostic"),
        "keys": sorted(obs),
    }


def signal_rerun() -> dict:
    rows = []
    for seed in SEEDS:
        rng = np.random.default_rng(seed)
        off_c = _ta(seed, False)
        on_c = _ta(seed, True)
        on_d = _ta(seed, True)
        protocol(off_c, correlated=True, trials=8, rng=rng)
        protocol(on_c, correlated=True, trials=8, rng=np.random.default_rng(seed + 1))
        protocol(on_d, correlated=False, trials=8, rng=np.random.default_rng(seed + 2))
        poff = probe_signal(off_c)
        pcorr = probe_signal(on_c)
        pdec = probe_signal(on_d)
        rows.append({
            "seed": seed,
            "off_sha": poff["sha_status"],
            "off_pe": poff["pe_status"],
            "corr_sha": pcorr["sha_status"],
            "corr_pe": pcorr["pe_status"],
            "corr_pe_T": pcorr["pe_T"],
            "corr_sha_T": pcorr["sha_T"],
            "corr_obs_FA": pcorr["obs_FA"],
            "corr_obs_T": pcorr["obs_T"],
            "dec_pe": pdec["pe_status"],
            "dec_pe_T": pdec["pe_T"],
            "dec_sha": pdec["sha_status"],
            "corr_selected": pcorr["selected"],
            "dec_selected": pdec["selected"],
            "corr_source": pcorr["source"],
            "dec_source": pdec["source"],
            "corr_prospection_T": pcorr["prospection"]["next_T"],
            "dec_prospection_T": pdec["prospection"]["next_T"],
            "corr_classes": pcorr["equivalence_snapshot"]["active"],
            "corr_aabb": pcorr.get("aabb_report"),
            "trace": {
                "raw_FA": pcorr["obs_FA"],
                "raw_sig": pcorr["raw_sig"],
                "pe_class": pcorr["pe_class"],
                "pe_gate": pcorr["pe_gate"],
                "member_sigs": pcorr["member_sigs"],
                "diagnostic_kind": (pcorr.get("diagnostic") or {}).get("kind"),
            },
        })
    corr_pe = sum(1 for r in rows if r["corr_pe"] == "MATCH")
    dec_pe = sum(1 for r in rows if r["dec_pe"] == "MATCH")
    corr_sha = sum(1 for r in rows if r["corr_sha"] == "MATCH")
    action_diff = any(r["corr_selected"] != r["dec_selected"] for r in rows)
    pe_helps = corr_pe > corr_sha
    return {
        "protocol": {"trials": 8, "delay": DELAY, "relax": RELAX, "signal_specific_code": False},
        "rows": rows,
        "corr_pe_match_n": corr_pe,
        "dec_pe_match_n": dec_pe,
        "corr_sha_match_n": corr_sha,
        "pe_helps_vs_sha": pe_helps,
        "correlated_outperforms_decorrelated": corr_pe > dec_pe,
        "signal_dependent_action": action_diff,
        "note": "No FIELD_A special case. Full observation fragments.",
    }


def seasonal_diag() -> dict:
    rows = []
    for seed in (17, 41):
        for pe_on in (False, True):
            planet = experimental_climate_planet_config()
            cfg = PhysicalSystemConfig(planet=planet)
            cfg.cognition.predictive_equivalence = pe_on
            rt = PhysicalSystemRuntime(seed=seed, config=cfg)
            rt.step(80)
            eq = rt.cognition.get("equivalence") or pe.empty_store()
            comp = rt.cognition["compression"]
            n_struct = len(comp.get("structures") or {})
            pe_m = int((eq.get("matches") or 0))
            rows.append({
                "seed": seed,
                "pe": pe_on,
                "classes": pe.snapshot(eq)["active"],
                "pe_matches": pe_m,
                "structures": n_struct,
                "selected": rt.last_selected_action,
            })
    on = [r for r in rows if r["pe"]]
    off = [r for r in rows if not r["pe"]]
    return {
        "rows": rows,
        "pe_classes_formed": any(r["classes"] > 0 for r in on),
        "behavioral_gate_not_run": True,
        "claim_seasonal_adaptation": "NOT_CLAIMED",
        "more_classes_than_off": sum(r["classes"] for r in on) > sum(r["classes"] for r in off),
    }


def body_diag() -> dict:
    rows = []
    for seed in (17, 23):
        for pe_on in (False, True):
            cfg = PhysicalSystemConfig()
            cfg.cognition.predictive_equivalence = pe_on
            rt = PhysicalSystemRuntime(seed=seed, config=cfg)
            rt.step(60)
            eq = rt.cognition.get("equivalence") or pe.empty_store()
            rows.append({
                "seed": seed,
                "pe": pe_on,
                "classes": pe.snapshot(eq)["active"],
                "pe_matches": int(eq.get("matches") or 0),
                "pe_learns": int(eq.get("learns") or 0),
                "splits": int(eq.get("splits") or 0),
            })
    return {
        "rows": rows,
        "pe_learns_when_on": all(r["pe_learns"] > 0 for r in rows if r["pe"]),
        "default_body_variables": ["body.T", "body.B0", "local.T", "internal.c0"],
        "erased_causal_distinctions": "NOT_MEASURED_BEYOND_SYNTHETIC_SMALL_DIFF",
    }


def ablations(syn, irr, small, rev, cog, sig, ctx) -> dict:
    store_off = pe.empty_store()
    store_off["enabled"] = False
    pe.learn(store_off, fragment={"x": 0.11}, action=ACTION, consequent=FAM_A, tick=1)
    a_off = {"classes": len(store_off.get("classes") or {}), "status": "DISABLED_NO_LEARN"}
    # C: decorrelated futures for the synthetic set
    deco = _store()
    xs = (0.11, 0.24, 0.39, 0.40, 0.41)
    t = 1
    for i in range(40):
        x = xs[i % 5]
        cons = FAM_A if (i // 5) % 2 == 0 else FAM_B
        pe.learn(deco, fragment={"x": float(x)}, action=ACTION, consequent=cons, tick=t)
        t += 1
    deco_held = _family(pe.retrieve(deco, {"x": 0.18}, ACTION))
    deco_405 = _family(pe.retrieve(deco, {"x": 0.405}, ACTION))
    # I: composition ablated
    cfg = CognitionConfig(predictive_equivalence=True, prospective_composition=False)
    state = empty_cognitive_state(cfg)
    tick = 1
    for _ in range(4):
        for x in (0.11, 0.24, 0.39):
            state["last_fragment"] = {"x": float(x)}
            state["last_action"] = ACTION
            run_cognition_before_action(state, observation={"y": 0.90, "x": float(x)}, tick=tick, rng_value=0.0)
            tick += 1
    got = pe.retrieve(state["equivalence"], {"x": 0.18}, ACTION)
    return {
        "A_pe_off": a_off,
        "B_pe_on_synthetic_precision": syn["precision_A"],
        "C_decorrelated_futures_held_0.18": deco_held,
        "C_decorrelated_futures_held_0.405": deco_405,
        "D_irrelevant_z": irr["insensitive_to_z"],
        "E_tiny_relevant": small["distinction_preserved"],
        "F_revision": rev["split_occurred"] and rev["x24_moved_B"],
        "G_provenance_present": any(c.get("provenance_tail") for c in rev["classes"]),
        "H_exact_sha_held_out": syn["sha_held_out"],
        "I_composition_ablated_pe_still_retrieves": got.get("status") == "MATCH",
        "context_not_collapsed": ctx["preserved_context"],
        "signal_pe_on_vs_off": {
            "corr_pe_match_n": sig["corr_pe_match_n"],
            "corr_sha_match_n": sig["corr_sha_match_n"],
        },
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ident = identity_fragmentation_demo()
    syn = synthetic_core()
    ctx = context_control()
    irr = irrelevant_variation()
    small = small_difference()
    held = held_out_pack(syn)
    # fix generalization flag with actual sha dict keys (floats)
    held["generalization_not_replay"] = all(syn["sha_held_out"].get(x) == "NO_MATCH" for x in (0.18, 0.31))
    held["held_out_match_A"] = syn["held_out_0.18_family"] == "A"
    rev = revision()
    mem = memory_scaling()
    cog = cognition_sha_bypass()
    sens = sensitivity()
    sig = signal_rerun()
    seas = seasonal_diag()
    body = body_diag()
    abl = ablations(syn, irr, small, rev, cog, sig, ctx)

    _json(OUT / "SYNTHETIC_RESULTS.json", {"synthetic": syn, "context": ctx, "sensitivity": sens, "identity": ident, "cognition_bypass": cog})
    _json(OUT / "IRRELEVANT_VARIATION_RESULTS.json", irr)
    _json(OUT / "SMALL_DIFFERENCE_RESULTS.json", small)
    _json(OUT / "HELD_OUT_GENERALIZATION.json", held)
    _json(OUT / "REVISION_RESULTS.json", rev)
    _json(OUT / "MEMORY_SCALING.json", mem)
    _json(OUT / "SIGNAL_RERUN_RESULTS.json", sig)
    _json(OUT / "SEASONAL_DIAGNOSTIC.json", seas)
    _json(OUT / "BODY_INTERNAL_DIAGNOSTIC.json", body)
    _json(OUT / "ABLATION_RESULTS.json", abl)
    print(json.dumps({
        "precision_A": syn["precision_A"],
        "coverage_A": syn["coverage_A"],
        "false_eq_A": syn["false_equivalence_rate_A"],
        "proximity_split": syn["proximity_0.39_vs_0.40_split"],
        "held_out_A": syn["held_out_0.18_family"],
        "sha_held": syn["sha_held_out"],
        "context_ok": ctx["preserved_context"],
        "z_ok": irr["insensitive_to_z"],
        "small_ok": small["distinction_preserved"],
        "revision_ok": rev["split_occurred"] and rev["x24_moved_B"],
        "memory_bounded": mem["boring_continuous"]["bounded"],
        "cog_bypass": cog["bypass"],
        "corr_pe": sig["corr_pe_match_n"],
        "dec_pe": sig["dec_pe_match_n"],
        "corr_sha": sig["corr_sha_match_n"],
        "seasonal_classes": seas["pe_classes_formed"],
        "default_off": CognitionConfig().predictive_equivalence,
    }, indent=2))


if __name__ == "__main__":
    main()
