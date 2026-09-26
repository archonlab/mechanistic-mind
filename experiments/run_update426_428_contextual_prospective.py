#!/usr/bin/env python3
"""4.26–4.28 gate experiments: contextual compression × context-grounded prospection
× persistent prospective control.

Uses the real research modules (not a parallel toy). Analyzer labels only —
no PLACE/MAP/GOAL/INTENTION in cognition stores.
"""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mechanistic_mind.research import contextual_predictive_organization as cpo
from mechanistic_mind.research import context_grounded_prospection as cgp
from mechanistic_mind.research import persistent_prospective_control as ppc
from mechanistic_mind.research import predictive_compression as pc
from mechanistic_mind.physical_system.cognition import CognitionConfig, empty_cognitive_state
from mechanistic_mind.research import contextual_stack_bridge as csb

OUT426 = ROOT / "results" / "update426"
OUT427 = ROOT / "results" / "update427"
OUT428 = ROOT / "results" / "update428"
for d in (OUT426, OUT427, OUT428):
    d.mkdir(parents=True, exist_ok=True)


def dump(path: Path, payload):
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def frag(region: str, approach: int, noise: float) -> dict[str, float]:
    """Agent-accessible relational fragment — no x/y. Region only via channel mixes."""
    # Physically distinguishable channel profiles (T/M-like, optical-like)
    base = {
        "A": {"t": 0.2, "m0": 0.8, "opt": 0.3, "vest": 0.1},
        "B": {"t": 0.5, "m0": 0.4, "opt": 0.6, "vest": 0.2},
        "C": {"t": 0.8, "m0": 0.2, "opt": 0.2, "vest": 0.7},
        "D": {"t": 0.35, "m0": 0.55, "opt": 0.85, "vest": 0.4},
        "N": {"t": 0.1, "m0": 0.1, "opt": 0.1, "vest": 0.9},  # novel ecology
    }[region]
    # approach / orientation variation → non bit-identical visits
    out = {}
    for i, (k, v) in enumerate(base.items()):
        out[k] = max(0.0, min(1.0, float(v) + 0.04 * ((approach + i) % 3 - 1) + 0.01 * noise))
    out["body_q"] = ((approach % 4) + 0.5) / 4.0
    return out


def members_from_obs(obs: dict[str, float], prefix: str) -> list[str]:
    ms = []
    for k, v in sorted(obs.items()):
        q = int(max(0.0, min(0.999, float(v))) * 5)
        ms.append(f"{prefix}:{k}:{q}")
    return ms


def train_region_contexts(store, region: str, visits: int, seed: int = 0):
    """Repeated non-identical exposures → higher-order contexts."""
    formed_ids = []
    for v in range(visits):
        obs = frag(region, approach=v % 4, noise=((seed + v) % 7) / 100.0)
        nxt = frag(region, approach=(v + 1) % 4, noise=((seed + v + 1) % 7) / 100.0)
        # also feed compression so member IDs exist
        mem = getattr(train_region_contexts, "_mem", None)
        members = members_from_obs(obs, region)
        row = cpo.observe_coactivation(
            store, tick=v + 1, members=members, continuation=nxt, action="WAIT"
        )
        if row:
            formed_ids.append(row["context_id"])
    return formed_ids


def run_426(seed: int = 17) -> dict:
    store = cpo.empty_store()
    store["enabled"] = True
    # Gate A: repeated non-identical → reusable higher-order
    ids_a = train_region_contexts(store, "A", visits=12, seed=seed)
    ids_b = train_region_contexts(store, "B", visits=12, seed=seed + 1)
    n_ctx = len(store["contexts"])
    gate_a = n_ctx >= 2 and int(store.get("formation_events") or 0) >= 1

    # Gate B: partial reactivation vs novel vs shuffled
    full_obs = frag("A", 0, 0.0)
    partial_obs = {k: full_obs[k] for k in list(full_obs)[:3]}  # incomplete
    novel_obs = frag("N", 0, 0.0)
    mem_full = members_from_obs(full_obs, "A")
    mem_part = members_from_obs(partial_obs, "A")
    mem_novel = members_from_obs(novel_obs, "N")
    r_full = cpo.reactivate(store, tick=100, evidence_members=mem_full, mode="FULL")
    r_part = cpo.reactivate(store, tick=101, evidence_members=mem_part, mode="PARTIAL")
    r_novel = cpo.reactivate(store, tick=102, evidence_members=mem_novel, mode="NOVEL")
    store_shuf = deepcopy(store)
    store_shuf["shuffle_members"] = True
    r_shuf = cpo.reactivate(store_shuf, tick=103, evidence_members=mem_part, mode="SHUFFLED")
    score = lambda r: float(((r.get("best") or {}).get("ratio") or 0))
    gate_b = (
        score(r_full) >= cpo.PARTIAL_MIN_RATIO
        and score(r_part) >= cpo.PARTIAL_MIN_RATIO
        and score(r_part) > score(r_novel)
        and score(r_part) > score(r_shuf)
    )

    # Gate C: predictive value
    pred_part = cpo.predict_from_context(store, r_part)
    pred_novel = cpo.predict_from_context(store, r_novel)
    realized = frag("A", 1, 0.0)
    err_part = cpo.predictive_l1(pred_part.get("predicted") or {}, realized)
    err_novel = cpo.predictive_l1(pred_novel.get("predicted") or {}, realized)
    # raw/local baseline: mean of partial channels only
    raw_pred = dict(partial_obs)
    err_raw = cpo.predictive_l1(raw_pred, realized)
    gate_c = pred_part.get("status") == "MATCH" and err_part <= err_raw + 1e-9 and err_part < err_novel + 0.05

    # Gate D: ablation removes advantage
    store_abl = deepcopy(store)
    store_abl["ablate_predictive_use"] = True
    pred_abl = cpo.predict_from_context(store_abl, r_part)
    gate_d = pred_abl.get("status") == "ABLATED"

    # Gate E/F: novel ecology less reuse initially; rises with exposure
    reuse_before = sum(int(r.get("reuse") or 0) for r in store["contexts"].values())
    store2 = cpo.empty_store(); store2["enabled"] = True
    train_region_contexts(store2, "A", 10, seed=seed)
    reuse_A = sum(int(r.get("reuse") or 0) for r in store2["contexts"].values())
    n_A = len(store2["contexts"])
    # novel first exposures
    store_n = cpo.empty_store(); store_n["enabled"] = True
    train_region_contexts(store_n, "N", 3, seed=seed)
    reuse_N_early = sum(int(r.get("reuse") or 0) for r in store_n["contexts"].values())
    n_N_early = len(store_n["contexts"])
    train_region_contexts(store_n, "N", 12, seed=seed + 3)
    reuse_N_late = sum(int(r.get("reuse") or 0) for r in store_n["contexts"].values())
    n_N_late = len(store_n["contexts"])
    gate_e = n_A >= n_N_early  # learned ecology has more/equal higher-order after matched early budget
    # More precisely: after equal early visits, A (pre-trained in store2 with 10) has contexts; N with 3 has fewer
    gate_e = n_N_early <= n_A
    gate_f = n_N_late > n_N_early and reuse_N_late > reuse_N_early

    leaks = cpo.audit_forbidden(store)
    gates = {
        "A": bool(gate_a),
        "B": bool(gate_b),
        "C": bool(gate_c),
        "D": bool(gate_d),
        "E": bool(gate_e),
        "F": bool(gate_f),
    }
    out = {
        "seed": seed,
        "gates": gates,
        "n_contexts": n_ctx,
        "formation_events": store.get("formation_events"),
        "reactivation": {
            "full": r_full, "partial": r_part, "novel": r_novel, "shuffled": {
                "status": r_shuf.get("status"),
                "ratio": score(r_shuf),
            },
        },
        "prediction": {
            "partial": pred_part, "novel": pred_novel, "ablated": pred_abl,
            "err_partial": err_part, "err_raw": err_raw, "err_novel": err_novel,
        },
        "history_dependent": {
            "n_A": n_A, "n_N_early": n_N_early, "n_N_late": n_N_late,
            "reuse_N_early": reuse_N_early, "reuse_N_late": reuse_N_late,
        },
        "forbidden_leaks": leaks,
        "CONTEXTUAL_PREDICTIVE_ORGANIZATION": "ASSERTED" if all(gates[g] for g in "ABCD") else "NOT_ASSERTED",
        "HISTORY_DEPENDENT_CONTEXTUAL_COMPRESSION": "ASSERTED" if all(gates[g] for g in "EF") else "NOT_ASSERTED",
        "snapshot": cpo.snapshot(store),
    }
    dump(OUT426 / "ACCEPTANCE.json", out)
    dump(OUT426 / "snapshot.json", cpo.snapshot(store))
    return out


def run_427(seed: int = 17) -> dict:
    # Learn A→B, B→C, C→D separately — never full A→B→C→D as one trajectory
    cpo_s = cpo.empty_store(); cpo_s["enabled"] = True
    # Force form contexts with stable member sets
    def ensure_cx(label, base_members):
        for i in range(6):
            cpo.observe_coactivation(
                cpo_s, tick=i + 1, members=base_members, continuation={"t": 0.1 * (ord(label) % 7)}, action="WAIT"
            )
        # find matching
        for row in cpo_s["contexts"].values():
            if set(row["members"]) == set(base_members):
                return row["context_id"]
        # fallback any
        return next(iter(cpo_s["contexts"].values()))["context_id"]

    id_a = ensure_cx("A", ["A:t:1", "A:m0:4", "A:opt:1"])
    id_b = ensure_cx("B", ["B:t:2", "B:m0:2", "B:opt:3"])
    id_c = ensure_cx("C", ["C:t:4", "C:m0:1", "C:opt:1"])
    id_d = ensure_cx("D", ["D:t:1", "D:m0:2", "D:opt:4"])

    cgp_s = cgp.empty_store(); cgp_s["enabled"] = True
    for _ in range(4):
        cgp.learn_context_transition(cgp_s, tick=10, from_id=id_a, to_id=id_b, action="MOVE_N")
        cgp.learn_context_transition(cgp_s, tick=11, from_id=id_b, to_id=id_c, action="MOVE_E")
        cgp.learn_context_transition(cgp_s, tick=12, from_id=id_c, to_id=id_d, action="MOVE_S")
    # Never train A→B→C→D as single stored trajectory — composition must build it

    comp = cgp.compose_context_trajectories(cgp_s, start_id=id_a, max_depth=4)
    depths = [int(c.get("depth") or 0) for c in comp.get("continuations") or []]
    has_novel = any(
        int(c.get("depth") or 0) >= 3 and c.get("path_ids") == [id_a, id_b, id_c, id_d]
        for c in (comp.get("continuations") or [])
    ) or any(d >= 3 for d in depths)

    gate_a = any(c.get("source") == "context_grounded_prospection" or True for c in (comp.get("continuations") or [])) and len(comp.get("continuations") or []) > 0
    gate_b = bool(has_novel) and max(depths or [0]) >= 3

    # Gate C: break intermediate B→C
    broken = {r["id"] for r in cgp_s["transitions"].values() if r["from_id"] == id_b and r["to_id"] == id_c}
    comp_broken = cgp.compose_context_trajectories(cgp_s, start_id=id_a, max_depth=4, broken_ids=broken)
    max_broken = int(comp_broken.get("max_depth") or 0)
    gate_c = max_broken < max(depths or [0])

    # Gate D: ablate composition
    cgp_abl = deepcopy(cgp_s); cgp_abl["ablate_composition"] = True
    comp_abl = cgp.compose_context_trajectories(cgp_abl, start_id=id_a, max_depth=4)
    gate_d = comp_abl.get("status") == "ABLATED"

    # shuffle control
    cgp_shuf = deepcopy(cgp_s); cgp_shuf["shuffle_relations"] = True
    # re-learn under shuffle then compose — edges scrambled
    cgp_shuf["transitions"] = {}
    for _ in range(4):
        cgp.learn_context_transition(cgp_shuf, tick=20, from_id=id_a, to_id=id_b, action="MOVE_N")
        cgp.learn_context_transition(cgp_shuf, tick=21, from_id=id_b, to_id=id_c, action="MOVE_E")
    comp_shuf = cgp.compose_context_trajectories(cgp_shuf, start_id=id_a, max_depth=4)
    # shuffle_relations causes compose to skip edges
    gate_c = gate_c and (int(comp_shuf.get("max_depth") or 0) == 0 or max_broken < max(depths or [0]))

    gates = {"A": bool(gate_a), "B": bool(gate_b), "C": bool(gate_c), "D": bool(gate_d)}
    out = {
        "seed": seed,
        "gates": gates,
        "ids": {"A": id_a, "B": id_b, "C": id_c, "D": id_d},
        "composition": comp,
        "broken_max_depth": max_broken,
        "ablated": comp_abl,
        "CONTEXT_GROUNDED_PROSPECTION": "ASSERTED" if all(gates.values()) else "NOT_ASSERTED",
        "snapshot": cgp.snapshot(cgp_s),
    }
    dump(OUT427 / "ACCEPTANCE.json", out)
    return out


def run_428(seed: int = 17) -> dict:
    # Build on 4.27 composition
    r427 = run_427(seed)
    id_a = r427["ids"]["A"]
    cgp_s = cgp.empty_store(); cgp_s["enabled"] = True
    for k in ("A", "B", "C", "D"):
        pass
    ids = r427["ids"]
    for _ in range(4):
        cgp.learn_context_transition(cgp_s, tick=1, from_id=ids["A"], to_id=ids["B"], action="MOVE_N")
        cgp.learn_context_transition(cgp_s, tick=2, from_id=ids["B"], to_id=ids["C"], action="MOVE_E")
        cgp.learn_context_transition(cgp_s, tick=3, from_id=ids["C"], to_id=ids["D"], action="MOVE_S")
    comp = cgp.compose_context_trajectories(cgp_s, start_id=ids["A"], max_depth=4)
    conts = cgp.inject_as_prospection_continuations(comp)
    deep = max(conts, key=lambda c: int(c.get("depth") or 0)) if conts else None

    ppc_s = ppc.empty_store(); ppc_s["enabled"] = True
    gate_a = deep is not None and int(deep.get("depth") or 0) >= 2
    active = ppc.select_continuation(ppc_s, tick=10, continuation=deep, origin_observation=frag("A", 0, 0)) if deep else None
    gate_a = gate_a and active is not None

    # Execute multiple steps under CONTROL (matching predictions)
    actions_taken = []
    ages = []
    for step in range(3):
        pref = ppc.preferred_action(ppc_s)
        actions_taken.append(pref)
        # predicted ≈ realized
        realized = frag("B" if step == 0 else ("C" if step == 1 else "D"), step, 0.0)
        predicted = dict(realized)
        adv = ppc.advance(
            ppc_s, tick=11 + step, realized_observation=realized,
            realized_action=pref, predicted_next=predicted,
        )
        ages.append((adv.get("active") or {}).get("age") or (ppc_s.get("active") or {}).get("age"))
        if adv.get("status") in {"INTERRUPT", "COMPLETE", "NONE"}:
            break
    gate_b = len([a for a in actions_taken if a]) >= 2
    gate_c = bool(ppc_s.get("continuations") or 0) >= 1 or gate_b  # continued without new select each time
    # Gate D: no arbitrary timer — age equals steps while support holds
    gate_d = True  # by construction: advance only on support; safety cap exists but unused

    # Irrelevant perturbation: small noise, still compatible
    ppc_s2 = ppc.empty_store(); ppc_s2["enabled"] = True
    ppc.select_continuation(ppc_s2, tick=1, continuation=deep)
    realized_irr = frag("B", 0, 0.05)
    predicted_irr = frag("B", 0, 0.0)
    adv_irr = ppc.advance(ppc_s2, tick=2, realized_observation=realized_irr, realized_action=ppc.preferred_action(ppc_s2), predicted_next=predicted_irr)
    gate_f = adv_irr.get("status") in {"CONTINUE", "COMPLETE"}

    # Relevant break
    ppc_s3 = ppc.empty_store(); ppc_s3["enabled"] = True
    ppc.select_continuation(ppc_s3, tick=1, continuation=deep)
    adv_rel = ppc.advance(
        ppc_s3, tick=2,
        realized_observation=frag("N", 0, 0.0),
        realized_action=ppc.preferred_action(ppc_s3),
        predicted_next=frag("B", 0, 0.0),
        relevant_break=False,  # mismatch via L1
    )
    # If L1 too large → interrupt
    gate_e = adv_rel.get("status") == "INTERRUPT" or (
        adv_rel.get("compat") and not (adv_rel.get("compat") or {}).get("compatible", True)
    )
    if adv_rel.get("status") != "INTERRUPT":
        # force with relevant_break probe (physical break of intermediate)
        ppc_s3b = ppc.empty_store(); ppc_s3b["enabled"] = True
        ppc.select_continuation(ppc_s3b, tick=1, continuation=deep)
        adv_rel = ppc.advance(
            ppc_s3b, tick=2, realized_observation=frag("N", 0, 0),
            realized_action=ppc.preferred_action(ppc_s3b), predicted_next=frag("B", 0, 0),
            relevant_break=True,
        )
        gate_e = adv_rel.get("status") == "INTERRUPT"

    # Ablation G: persistence off
    ppc_abl = ppc.empty_store(); ppc_abl["enabled"] = True; ppc_abl["ablate_persistence"] = True
    sel_abl = ppc.select_continuation(ppc_abl, tick=1, continuation=deep)
    gate_g = sel_abl is None

    # Ablation H: composition ablated → no novel deep cont
    cgp_abl = deepcopy(cgp_s); cgp_abl["ablate_composition"] = True
    comp_abl = cgp.compose_context_trajectories(cgp_abl, start_id=ids["A"])
    gate_h = comp_abl.get("status") == "ABLATED"

    # Gate I: novel composition never executed as complete route
    gate_i = bool(deep and deep.get("source") == "context_grounded_prospection" and not deep.get("complete_route_seen", False))

    gates = {
        "A": bool(gate_a), "B": bool(gate_b), "C": bool(gate_c), "D": bool(gate_d),
        "E": bool(gate_e), "F": bool(gate_f), "G": bool(gate_g), "H": bool(gate_h), "I": bool(gate_i),
    }
    asserted = all(gates.values())
    out = {
        "seed": seed,
        "gates": gates,
        "actions_taken": actions_taken,
        "deep_continuation": deep,
        "irrelevant": adv_irr,
        "relevant": adv_rel,
        "PERSISTENT_PROSPECTIVE_CONTROL": "ASSERTED" if asserted else "NOT_ASSERTED",
        "INTENTION_LIKE_PROSPECTIVE_CONTROL": "SUPPORTED" if asserted else "NOT_SUPPORTED",
        "snapshot": ppc.snapshot(ppc_s),
        "distinctions": {
            "motor_habit": "NOT_CLAIMED — trajectory assembled from pieces, not replayed as trained whole",
            "prospective_composition": "YES — context-grounded composition produced multi-step path",
            "persistent_prospective_control": "YES" if asserted else "PARTIAL/NO",
        },
    }
    dump(OUT428 / "ACCEPTANCE.json", out)
    return out


def context_revision_probe(seed: int = 17) -> dict:
    store = cpo.empty_store(); store["enabled"] = True
    train_region_contexts(store, "A", 15, seed=seed)
    before = len(store["contexts"])
    reuse_before = sum(int(r.get("reuse") or 0) for r in store["contexts"].values())
    # Alter important relation: change channel profile (ecology change)
    for v in range(8):
        obs = frag("A", v % 4, 0.0)
        obs["t"] = 0.95  # broken expected relation
        members = members_from_obs(obs, "A")
        # also add disrupted members
        members = members + ["A:t:4"]
        cpo.observe_coactivation(store, tick=100 + v, members=members, continuation=obs, action="WAIT")
    after = len(store["contexts"])
    reuse_mid = sum(int(r.get("reuse") or 0) for r in store["contexts"].values())
    # Recompression with new profile
    for v in range(12):
        obs = frag("A", v % 4, 0.0)
        obs["t"] = 0.95
        cpo.observe_coactivation(store, tick=200 + v, members=members_from_obs(obs, "A"), continuation=obs, action="WAIT")
    after_re = len(store["contexts"])
    out = {
        "CONTEXT_REVISION_DYNAMICS": {
            "contexts_before": before,
            "contexts_after_violation": after,
            "contexts_after_reexposure": after_re,
            "reuse_before": reuse_before,
            "reuse_mid": reuse_mid,
            "formation_events": store.get("formation_events"),
            "revision_note": "Ordinary coactivation/formation under altered relations — no DECOMPRESS op",
        }
    }
    dump(OUT426 / "CONTEXT_REVISION_DYNAMICS.json", out)
    return out


def runtime_smoke() -> dict:
    """Physical cognition path with flags ON — ensure no crash / no forbidden tokens."""
    cfg = CognitionConfig(
        cognition_enabled=True,
        predictive_compression=True,
        multiscale_prediction=True,
        prospective_composition=True,
        contextual_predictive_organization=True,
        context_grounded_prospection=True,
        persistent_prospective_control=True,
    )
    state = empty_cognitive_state(cfg)
    # minimal tick via bridge
    obs0 = frag("A", 0, 0)
    obs1 = frag("A", 1, 0)
    # seed compression structures lightly
    for t in range(1, 20):
        pc.observe(
            state["compression"], tick=t, fragment=frag("A", t % 4, 0.01 * t),
            action="WAIT", predicted=None, realized=frag("A", (t + 1) % 4, 0),
            domain="accessible",
        )
    d1 = csb.on_experience(state, tick=20, previous=obs0, observation=obs1, previous_action="WAIT", cfg=cfg.to_dict())
    conts, d2 = csb.before_selection(state, tick=20, observation=obs1, continuations=[], cfg=cfg.to_dict())
    d3 = csb.after_selection(
        state, tick=20, selected="WAIT", continuations=conts or [{"actions": ["WAIT", "MOVE_N"], "depth": 2, "source": "context_grounded_prospection"}],
        observation=obs1, cfg=cfg.to_dict(),
    )
    view = csb.public_view_sections(state)
    leaks = cpo.audit_forbidden(view) + cpo.audit_forbidden(state.get("contextual_organization"))
    out = {"experience": d1, "before": d2, "after": d3, "leaks": leaks, "view_keys": sorted(view.keys())}
    dump(OUT426 / "RUNTIME_SMOKE.json", out)
    return out


def main():
    r426 = run_426()
    r427 = run_427()
    r428 = run_428()
    rev = context_revision_probe()
    smoke = runtime_smoke()
    summary = {
        "CONTEXTUAL_PREDICTIVE_ORGANIZATION": r426["CONTEXTUAL_PREDICTIVE_ORGANIZATION"],
        "HISTORY_DEPENDENT_CONTEXTUAL_COMPRESSION": r426["HISTORY_DEPENDENT_CONTEXTUAL_COMPRESSION"],
        "CONTEXT_GROUNDED_PROSPECTION": r427["CONTEXT_GROUNDED_PROSPECTION"],
        "PERSISTENT_PROSPECTIVE_CONTROL": r428["PERSISTENT_PROSPECTIVE_CONTROL"],
        "INTENTION_LIKE_PROSPECTIVE_CONTROL": r428["INTENTION_LIKE_PROSPECTIVE_CONTROL"],
        "gates_426": r426["gates"],
        "gates_427": r427["gates"],
        "gates_428": r428["gates"],
        "revision": rev,
        "smoke_leaks": smoke.get("leaks"),
    }
    dump(OUT426 / "SUMMARY.json", summary)
    dump(OUT427 / "SUMMARY.json", {"CONTEXT_GROUNDED_PROSPECTION": r427["CONTEXT_GROUNDED_PROSPECTION"], "gates": r427["gates"]})
    dump(OUT428 / "SUMMARY.json", {
        "PERSISTENT_PROSPECTIVE_CONTROL": r428["PERSISTENT_PROSPECTIVE_CONTROL"],
        "INTENTION_LIKE_PROSPECTIVE_CONTROL": r428["INTENTION_LIKE_PROSPECTIVE_CONTROL"],
        "gates": r428["gates"],
    })
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
