#!/usr/bin/env python3
"""Ecological transition harness. Ordinary step() learning only in primary runs."""
from __future__ import annotations

import csv
import json
import math
import sys
from collections import Counter
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mechanistic_mind.physical_system import PhysicalSystemRuntime
from mechanistic_mind.physical_system.actions import available_actions
from mechanistic_mind.physical_system.complementary_resources import place_source_AB
from mechanistic_mind.physical_system.runtime import _rng_unit
from mechanistic_mind.research import predictive_compression as pc
from mechanistic_mind.research import prospective_composition as pr

OUT = ROOT / "results" / "mm_predictive_scenario_transition"
ACTIONS = list(available_actions())
SEEDS = (17, 66667, 2148)
SWITCH = 60
EPOCH_B = 100
REVERSE = 80
GRADUAL = 30
PERSIST = 20
FOLLOW_A = SWITCH


def _entropy(counts: dict) -> float:
    n = sum(counts.values())
    if n <= 0:
        return 0.0
    h = 0.0
    for c in counts.values():
        if c:
            p = c / n
            h -= p * math.log(p, 2)
    return h


def make_runtime(seed: int, *, clamp_flow: bool) -> PhysicalSystemRuntime:
    rt = PhysicalSystemRuntime(seed=int(seed))
    if clamp_flow:
        rt.config.planet.flow_enabled = False
    return rt


def apply_clamp(rt: PhysicalSystemRuntime, s: float) -> None:
    s = float(max(-1.0, min(1.0, s)))
    rt.world.vx[:, :] = 0.55 * s
    rt.world.vy[:, :] = 0.0
    rt.world.T[:, :] = 0.55 + 0.35 * s
    rt.world.M[0, :, :] = 0.15 + 0.25 * max(0.0, s)
    rt.world.M[1, :, :] = 0.15 + 0.25 * max(0.0, -s)
    rt.world.M[2, :, :] = 0.05


def apply_null_resource(rt: PhysicalSystemRuntime) -> None:
    h, w = rt.world.T.shape
    iy = (int(rt.body.y) + h // 2) % h
    ix = (int(rt.body.x) + w // 2) % w
    place_source_AB(rt.world, iy, ix, A=3.0, B=0.0)


def apply_forcing_shift(rt: PhysicalSystemRuntime, *, shifted: bool) -> None:
    w = int(rt.config.planet.width)
    rt.config.planet.forcing_origin_x = (0.5 * w) if shifted else 0.0


def wipe_predictive(rt: PhysicalSystemRuntime) -> None:
    rt.cognition["prospection"] = pr.empty_store()
    rt.cognition["compression"] = pc.empty_memory()
    cfg = rt.config.cognition
    rt.cognition["prospection"]["ablate_composition"] = not cfg.prospective_composition


def qsig(obs: dict) -> str:
    return pr._sig(pr._q(obs))


def frag_distance(a: dict, b: dict) -> float:
    qa, qb = pr._q(a), pr._q(b)
    return pr._frag_distance(qa, qb)


def supports_now(rt: PhysicalSystemRuntime) -> dict:
    obs = rt.last_agent_observation or rt.agent_observation()
    store = rt.cognition["prospection"]
    out = {}
    for act in ACTIONS:
        one = pr.predict_one_step(store, obs, act)
        key = pr.transition_key(pr._q(obs), act)
        row = (store.get("transitions") or {}).get(key)
        out[act] = {
            "exact": int((row or {}).get("support") or 0),
            "status": one.get("status"),
            "support": int(one.get("support") or 0) if one.get("status") == "MATCH" else 0,
            "reliability": one.get("reliability"),
        }
    return out


def tick_row(rt: PhysicalSystemRuntime, *, epoch: str, incumbent: str | None) -> dict:
    sel = rt.cognition.get("last_selection") or {}
    comp = sel.get("competition") or {}
    obs = rt.last_agent_observation or {}
    sup = supports_now(rt)
    supported = [a for a in ACTIONS if sup[a]["status"] == "MATCH"]
    listed = list(comp.get("supported_actions") or supported)
    inc = incumbent if incumbent in ACTIONS else None
    chl_cands = [a for a in ACTIONS if a != inc]
    chl = max(chl_cands, key=lambda a: sup[a]["support"]) if chl_cands else None
    return {
        "tick": int(rt.tick),
        "epoch": epoch,
        "action": sel.get("action") or rt.last_selected_action,
        "source": sel.get("source"),
        "outcome": comp.get("outcome_class"),
        "k": len(listed),
        "supported": listed,
        "incumbent": inc,
        "inc_sup": None if inc is None else sup[inc]["support"],
        "inc_exact": None if inc is None else sup[inc]["exact"],
        "inc_match": None if inc is None else sup[inc]["status"],
        "challenger": chl,
        "chl_sup": None if chl is None else sup[chl]["support"],
        "chl_match": None if chl is None else sup[chl]["status"],
        "qsig": qsig(obs) if obs else None,
        "local_T": float(obs.get("local.T", 0.0)) if obs else None,
        "local_vx": float(obs.get("local.vx", 0.0)) if obs else None,
        "local_M0": float(obs.get("local.M0", 0.0)) if obs else None,
        "local_M1": float(obs.get("local.M1", 0.0)) if obs else None,
        "body_x": float(rt.body.x),
        "body_y": float(rt.body.y),
        "body_vx": float(rt.body.vx),
        "W": float(getattr(rt.body, "mechanical_work_reservoir", 0.0) or 0.0),
        "pred_n": len(sel.get("prediction_matches") or []),
        "endogenous_would_be": ACTIONS[min(len(ACTIONS) - 1, int(_rng_unit(rt.seed, rt.tick) * len(ACTIONS)))],
    }


def lock_from_rows(rows: list[dict], persist: int = PERSIST) -> dict:
    lock_t = None
    locked = None
    for i, rec in enumerate(rows):
        if rec.get("source") != "PROSPECTIVE_SCENARIO":
            continue
        if rec.get("outcome") != "SINGLE_SUPPORTED":
            continue
        if int(rec.get("k") or 0) != 1:
            continue
        window = rows[i:i + persist]
        if len(window) < persist:
            break
        if all(w.get("action") == rec["action"] and w.get("outcome") == "SINGLE_SUPPORTED" for w in window):
            lock_t = rec["tick"]
            locked = rec["action"]
            break
    return {"lock_tick": lock_t, "locked_action": locked}


def first_change(rows: list[dict], action: str, after_tick: int) -> int | None:
    for rec in rows:
        if rec["tick"] <= after_tick:
            continue
        if rec.get("action") != action:
            return rec["tick"]
    return None


def first_k2(rows: list[dict], after_tick: int) -> int | None:
    for rec in rows:
        if rec["tick"] <= after_tick:
            continue
        if int(rec.get("k") or 0) >= 2:
            return rec["tick"]
    return None


def first_nosupport(rows: list[dict], after_tick: int) -> int | None:
    for rec in rows:
        if rec["tick"] <= after_tick:
            continue
        if rec.get("outcome") in {"NO_SUPPORT", "NOT_RUN"} or rec.get("source") == "ENDOGENOUS_VARIATION":
            return rec["tick"]
    return None


def snapshot_clean(rt: PhysicalSystemRuntime) -> dict:
    return rt.snapshot()


def restore(snap: dict) -> PhysicalSystemRuntime:
    return PhysicalSystemRuntime.restore(deepcopy(snap))


def step_with_ecology(rt: PhysicalSystemRuntime, *, kind: str, s: float, forcing_shifted: bool, null: bool) -> None:
    if kind == "clamp":
        apply_clamp(rt, s)
    elif kind == "forcing":
        apply_forcing_shift(rt, shifted=forcing_shifted)
    elif kind == "null":
        apply_clamp(rt, 1.0)
        apply_null_resource(rt)
    rt.step()


def run_phase(rt, *, n: int, epoch: str, incumbent: str | None, kind: str,
              s_fn, forcing_shifted: bool, null: bool) -> list[dict]:
    rows = []
    for i in range(n):
        step_with_ecology(rt, kind=kind, s=s_fn(i), forcing_shifted=forcing_shifted, null=null)
        rows.append(tick_row(rt, epoch=epoch, incumbent=incumbent))
    return rows


def summarize(run_id: str, seed: int, rows: list[dict], *, switch: int | None, incumbent: str | None) -> dict:
    post = [r for r in rows if switch is None or r["tick"] > switch]
    counts = Counter(r["action"] for r in rows)
    post_counts = Counter(r["action"] for r in post)
    k2 = [r for r in rows if int(r.get("k") or 0) >= 2]
    return {
        "run_id": run_id,
        "seed": seed,
        "incumbent": incumbent,
        "lock": lock_from_rows(rows),
        "counts": dict(counts),
        "entropy": _entropy(counts),
        "post_switch_counts": dict(post_counts),
        "post_entropy": _entropy(post_counts),
        "first_competition_tick": first_k2(rows, switch or 0),
        "first_endogenous_after_switch": first_nosupport(rows, switch or 0) if switch else None,
        "transition_tick": first_change(rows, incumbent, switch) if incumbent and switch else None,
        "k2_event_count": len(k2),
        "true_competition_outcomes": dict(Counter(r["outcome"] for r in k2)),
        "final": rows[-1] if rows else None,
        "n_ticks": len(rows),
    }


def compact_events(rows: list[dict], *, switch: int | None, incumbent: str | None) -> list[dict]:
    ev = []
    prev = None
    for r in rows:
        fire = False
        reason = []
        if switch is not None and r["tick"] in {switch, switch + 1}:
            fire = True
            reason.append("switch_window")
        if int(r.get("k") or 0) >= 2:
            fire = True
            reason.append("k>=2")
        if prev and r.get("action") != prev.get("action"):
            fire = True
            reason.append("action_change")
        if r.get("source") != (prev or {}).get("source"):
            fire = True
            reason.append("source_change")
        if incumbent and r.get("inc_match") != (prev or {}).get("inc_match"):
            fire = True
            reason.append("incumbent_match_change")
        if fire:
            ev.append({**r, "reasons": reason})
        prev = r
    return ev


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    traces = []
    traj_rows = []
    competition = []
    transitions = []
    history = []
    ablations = []
    reversals = []

    def ingest(run_id, seed, rows, *, switch, incumbent, extra=None):
        summ = summarize(run_id, seed, rows, switch=switch, incumbent=incumbent)
        if extra:
            summ.update(extra)
        traces.append(summ)
        for r in rows:
            traj_rows.append({"run_id": run_id, "seed": seed, **r})
        for r in rows:
            if int(r.get("k") or 0) >= 2:
                competition.append({"run_id": run_id, "seed": seed, **r})
        if incumbent and switch:
            t = first_change(rows, incumbent, switch)
            if t is not None:
                rec = next(x for x in rows if x["tick"] == t)
                transitions.append({
                    "run_id": run_id, "seed": seed, "incumbent": incumbent,
                    "switch_tick": switch, "transition_tick": t,
                    "latency": t - switch, "to": rec["action"],
                    "source": rec["source"], "outcome": rec["outcome"],
                    "k": rec["k"], "supported": rec["supported"],
                })
        return summ

    for seed in SEEDS:
        print(f"seed {seed} epoch A", flush=True)
        rt = make_runtime(seed, clamp_flow=True)
        rows_a = run_phase(
            rt, n=FOLLOW_A, epoch="A", incumbent=None, kind="clamp",
            s_fn=lambda i: 1.0, forcing_shifted=False, null=False,
        )
        lock = lock_from_rows(rows_a)
        incumbent = lock["locked_action"]
        if incumbent is None:
            ingest(f"s{seed}_A_nolock", seed, rows_a, switch=None, incumbent=None,
                   extra={"note": "no operational incumbent; skip B forks"})
            continue
        snap = snapshot_clean(rt)
        # Replay A with incumbent tags for support columns (same deterministic seed).
        rt_a = make_runtime(seed, clamp_flow=True)
        rows_a = run_phase(
            rt_a, n=FOLLOW_A, epoch="A", incumbent=incumbent, kind="clamp",
            s_fn=lambda i: 1.0, forcing_shifted=False, null=False,
        )
        snap = snapshot_clean(rt_a)
        obs_a = rt_a.agent_observation()
        ingest(f"s{seed}_A", seed, rows_a, switch=None, incumbent=incumbent,
               extra={"lock": lock, "established": True})

        forks = []

        def fork(name: str, mutate, *, kind="clamp", s_fn=None, forcing_shifted=False, null=False,
                 n_b=EPOCH_B, epoch="B", do_reverse=False):
            rtb = restore(snap)
            mutate(rtb)
            pre_obs = rtb.agent_observation()
            dist = frag_distance(obs_a, pre_obs)
            pre_sup = supports_now(rtb)
            sf = s_fn or (lambda i: -1.0)
            rows_b = run_phase(
                rtb, n=n_b, epoch=epoch, incumbent=incumbent, kind=kind,
                s_fn=sf, forcing_shifted=forcing_shifted, null=null,
            )
            rid = f"s{seed}_{name}"
            extra = {
                "obs_distance_at_switch": dist,
                "pre_switch_supports": {a: {k: pre_sup[a][k] for k in ("exact", "status", "support")} for a in ACTIONS},
                "present_tick": int(rtb.tick) - n_b,
            }
            ingest(rid, seed, rows_a + rows_b, switch=SWITCH, incumbent=incumbent, extra=extra)
            rec = {
                "run_id": rid, "seed": seed, "name": name, "incumbent": incumbent,
                "obs_distance_at_switch": dist,
                "pre_inc_match": pre_sup[incumbent]["status"],
                "pre_inc_support": pre_sup[incumbent]["support"],
                "first_B": rows_b[0] if rows_b else None,
                "summary": summarize(rid, seed, rows_b, switch=0, incumbent=incumbent),
            }
            forks.append(rec)
            rows_r = []
            if do_reverse:
                rows_r = run_phase(
                    rtb, n=REVERSE, epoch="A2", incumbent=incumbent, kind=kind,
                    s_fn=lambda i: 1.0, forcing_shifted=False, null=False,
                )
                b_end = int(rows_b[-1]["tick"])
                ingest(
                    f"{rid}_reverse", seed, rows_b + rows_r, switch=b_end,
                    incumbent=rows_b[-1]["action"],
                    extra={"kind": "reverse_B_to_A", "from_action": rows_b[-1]["action"]},
                )
                reversals.append({
                    "run_id": f"{rid}_reverse", "seed": seed, "incumbent": incumbent,
                    "A_to_B_transition": first_change(rows_b, incumbent, 0),
                    "B_end_action": rows_b[-1]["action"],
                    "B_to_A_transition": first_change(rows_r, rows_b[-1]["action"], 0),
                    "A2_counts": dict(Counter(r["action"] for r in rows_r)),
                    "A2_first": rows_r[0] if rows_r else None,
                })
            return rtb, rows_b, rows_r

        print(f"  forks H/Ø/ablations seed={seed} inc={incumbent}", flush=True)
        _, rows_h, _ = fork("H_abrupt", lambda rt: None, do_reverse=True)
        _, rows_0, _ = fork("O_wipe", wipe_predictive, do_reverse=True)

        def ablate_pros(rt):
            rt.set_ablations(prospective_composition=False)

        def ablate_comp(rt):
            rt.set_mechanism("prospective_scenario_competition", False)

        fork("D_ablate_prospection", ablate_pros)
        fork("E_ablate_competition", ablate_comp)
        fork("A_nochange", lambda rt: None, s_fn=lambda i: 1.0)
        fork("F_null", lambda rt: None, kind="null", null=True, s_fn=lambda i: 1.0)

        def gradual_s(i, n=GRADUAL):
            if i >= n:
                return -1.0
            return 1.0 - 2.0 * (i / max(1, n))

        fork("P2_gradual", lambda rt: None, s_fn=gradual_s, n_b=GRADUAL + EPOCH_B)

        history.append({
            "seed": seed, "incumbent": incumbent, "switch": SWITCH,
            "H": next(f for f in forks if f["name"] == "H_abrupt"),
            "O": next(f for f in forks if f["name"] == "O_wipe"),
            "history_alters_first_B_action": (
                (forks[0]["first_B"] or {}).get("action") != (forks[1]["first_B"] or {}).get("action")
            ),
            "history_alters_first_B_source": (
                (forks[0]["first_B"] or {}).get("source") != (forks[1]["first_B"] or {}).get("source")
            ),
        })
        ablations.append({
            "seed": seed, "incumbent": incumbent,
            "branches": {f["name"]: {
                "first_action": (f["first_B"] or {}).get("action"),
                "first_source": (f["first_B"] or {}).get("source"),
                "first_outcome": (f["first_B"] or {}).get("outcome"),
                "first_k": (f["first_B"] or {}).get("k"),
                "obs_distance": f["obs_distance_at_switch"],
                "pre_inc_match": f["pre_inc_match"],
                "B_counts": f["summary"]["counts"],
                "transition_tick": f["summary"]["transition_tick"],
                "first_competition_tick": f["summary"]["first_competition_tick"],
            } for f in forks},
        })

        # FORCING-only ordinary planet (no clamp)
        print(f"  forcing-only seed={seed}", flush=True)
        rtf = make_runtime(seed, clamp_flow=False)
        rows_fa = run_phase(
            rtf, n=FOLLOW_A, epoch="A", incumbent=None, kind="forcing",
            s_fn=lambda i: 1.0, forcing_shifted=False, null=False,
        )
        lock_f = lock_from_rows(rows_fa)
        inc_f = lock_f["locked_action"]
        rtf = make_runtime(seed, clamp_flow=False)
        rows_fa = run_phase(
            rtf, n=FOLLOW_A, epoch="A", incumbent=inc_f, kind="forcing",
            s_fn=lambda i: 1.0, forcing_shifted=False, null=False,
        )
        snap_f = snapshot_clean(rtf)
        rtb = restore(snap_f)
        apply_forcing_shift(rtb, shifted=True)
        rows_fb = run_phase(
            rtb, n=EPOCH_B, epoch="B", incumbent=inc_f, kind="forcing",
            s_fn=lambda i: 1.0, forcing_shifted=True, null=False,
        )
        ingest(f"s{seed}_forcing", seed, rows_fa + rows_fb, switch=SWITCH, incumbent=inc_f,
               extra={"protocol": "FORCING_ONLY", "lock": lock_f})

        # Diagnostic graft only if H never showed k>=2
        if not any(int(r.get("k") or 0) >= 2 for r in rows_h):
            rtd = restore(snap)
            apply_clamp(rtd, -1.0)
            obs = rtd.agent_observation()
            # one forced physical step to obtain a real consequent, then restore and graft
            tmp = restore(snapshot_clean(rtd))
            apply_clamp(tmp, -1.0)
            chl = "MOVE:W" if incumbent != "MOVE:W" else "MOVE:E"
            tmp.step_forced_action(chl)
            cons = tmp.agent_observation()
            for i in range(3):
                pr.learn_transition(
                    rtd.cognition["prospection"], tick=900 + i,
                    antecedent=obs, action=chl, consequent=cons,
                )
            rows_d = run_phase(
                rtd, n=20, epoch="B_diag", incumbent=incumbent, kind="clamp",
                s_fn=lambda i: -1.0, forcing_shifted=False, null=False,
            )
            ingest(f"s{seed}_DIAGNOSTIC_graft_{chl}", seed, rows_d, switch=0, incumbent=incumbent,
                   extra={"diagnostic": True, "note": "NOT primary; grafted 3 challenger transitions at Epoch-B present"})

    (OUT / "EPOCH_TRACES.json").write_text(json.dumps(traces, indent=2, default=str), encoding="utf-8")
    (OUT / "COMPETITION_EVENTS.json").write_text(json.dumps(competition, indent=2, default=str), encoding="utf-8")
    (OUT / "TRANSITION_EVENTS.json").write_text(json.dumps(transitions, indent=2, default=str), encoding="utf-8")
    (OUT / "HISTORY_CONTROLS.json").write_text(json.dumps(history, indent=2, default=str), encoding="utf-8")
    (OUT / "ABLATION_RESULTS.json").write_text(json.dumps(ablations, indent=2, default=str), encoding="utf-8")
    (OUT / "REVERSAL_RESULTS.json").write_text(json.dumps(reversals, indent=2, default=str), encoding="utf-8")

    fields = [
        "run_id", "seed", "tick", "epoch", "action", "source", "outcome", "k",
        "incumbent", "inc_sup", "inc_exact", "inc_match", "challenger", "chl_sup",
        "chl_match", "qsig", "local_T", "local_vx", "local_M0", "local_M1",
        "body_x", "body_y", "W", "pred_n",
    ]
    with (OUT / "SUPPORT_TRAJECTORIES.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in traj_rows:
            w.writerow(r)
    print("done", "traces", len(traces), "k2", len(competition), "transitions", len(transitions), flush=True)


if __name__ == "__main__":
    main()
