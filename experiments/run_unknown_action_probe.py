#!/usr/bin/env python3
"""Unknown-action probe experiment. Detection vs DESIGN_BOUNDARY; no exploration policy."""
from __future__ import annotations

import json
import sys
from collections import Counter
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mechanistic_mind.physical_system import CognitionConfig, PhysicalSystemConfig, PhysicalSystemRuntime
from mechanistic_mind.physical_system.actions import available_actions
from mechanistic_mind.physical_system.unknown_action_probe import classify_unmodeled_actions
from mechanistic_mind.research import prospective_composition as pr
from mechanistic_mind.physical_system import scenario_competition as sc

OUT = ROOT / "results" / "mm_unknown_action_probe"
ACTIONS = list(available_actions())
SEEDS = (17, 23, 41, 59, 83, 66667, 2148)
AFTER = 40
PERSIST = 12


def restore(snap):
    return PhysicalSystemRuntime.restore(deepcopy(snap))


def make_rt(seed: int, *, probe: bool) -> PhysicalSystemRuntime:
    cfg = PhysicalSystemConfig(cognition=CognitionConfig(unknown_action_physical_probe=bool(probe)))
    return PhysicalSystemRuntime(seed=int(seed), config=cfg)


def east_strip(rt: PhysicalSystemRuntime) -> None:
    w = int(rt.config.planet.width)
    h = int(rt.config.planet.height)
    ix = (int(rt.body.x) + 2) % w
    for iy in range(h):
        rt.world.T[iy, ix] = 0.95
        rt.world.M[0, iy, ix] = 0.55


def lock_of(rows: list[dict]) -> dict:
    for i, rec in enumerate(rows):
        if rec.get("source") != "PROSPECTIVE_SCENARIO" or rec.get("outcome") != "SINGLE_SUPPORTED":
            continue
        if rec.get("k") != 1:
            continue
        w = rows[i:i + PERSIST]
        if len(w) < PERSIST:
            break
        if all(x.get("action") == rec["action"] and x.get("outcome") == "SINGLE_SUPPORTED" for x in w):
            return {"lock_tick": rec["tick"], "locked_action": rec["action"]}
    return {"lock_tick": None, "locked_action": None}


def rec(rt: PhysicalSystemRuntime) -> dict:
    sel = rt.cognition.get("last_selection") or {}
    comp = sel.get("competition") or {}
    probe = sel.get("unknown_action_probe") or {}
    obs = rt.last_agent_observation or {}
    inc = (comp.get("supported_actions") or [None])[0] if (comp.get("supported_actions") or [sel.get("action")]) else sel.get("action")
    one = pr.predict_one_step(rt.cognition["prospection"], obs, inc) if inc else {}
    return {
        "tick": int(rt.tick),
        "action": sel.get("action"),
        "source": sel.get("source"),
        "outcome": comp.get("outcome_class"),
        "k": len(comp.get("supported_actions") or []),
        "supported": list(comp.get("supported_actions") or []),
        "inc_match": one.get("status"),
        "inc_sup": one.get("support") if one.get("status") == "MATCH" else 0,
        "probe_enabled": bool(probe.get("enabled")),
        "unmodeled": list(probe.get("unmodeled_first_actions") or []),
        "modeled": list(probe.get("modeled_first_actions") or []),
        "eligible": list(probe.get("probe_eligible") or []),
        "probe_selected": probe.get("selected_probe_action"),
        "selection_effect": probe.get("selection_effect"),
        "x": float(rt.body.x),
        "y": float(rt.body.y),
        "W": float(getattr(rt.body, "mechanical_work_reservoir", 0.0) or 0.0),
    }


def run_pair(seed: int) -> dict:
    off, on = make_rt(seed, probe=False), make_rt(seed, probe=True)
    rows_off, rows_on = [], []
    for _ in range(30):
        off.step()
        on.step()
        rows_off.append(rec(off))
        rows_on.append(rec(on))
        lock = lock_of(rows_off)
        if lock["lock_tick"] and off.tick >= lock["lock_tick"] + PERSIST - 1:
            break
    lock = lock_of(rows_off)
    snap_off, snap_on = off.snapshot(), on.snapshot()
    east_strip(off)
    east_strip(on)
    post_off, post_on = [], []
    for _ in range(AFTER):
        east_strip(off)
        east_strip(on)
        off.step()
        on.step()
        post_off.append(rec(off))
        post_on.append(rec(on))
    same = [a["action"] for a in post_off] == [a["action"] for a in post_on]
    cls = classify_unmodeled_actions(
        store=on.cognition["prospection"],
        observation=on.last_agent_observation or on.agent_observation(),
        supported_actions=post_on[-1]["supported"] if post_on else [],
    )
    return {
        "seed": seed,
        "lock": lock,
        "same_action_sequence": same,
        "off_counts": dict(Counter(r["action"] for r in post_off)),
        "on_counts": dict(Counter(r["action"] for r in post_on)),
        "on_any_probe_execution": any(r.get("probe_selected") for r in post_on),
        "on_unmodeled_while_match": any(
            r["inc_match"] == "MATCH" and r["unmodeled"] for r in post_on
        ),
        "final_unmodeled": post_on[-1]["unmodeled"] if post_on else [],
        "final_modeled": post_on[-1]["modeled"] if post_on else [],
        "classifier": {k: cls[k] for k in ("modeled_first_actions", "unmodeled_first_actions", "arbitration")},
        "snap_on": snap_on,
        "post_on_head": post_on[:3],
        "post_on_tail": post_on[-2:],
    }


def diagnostic_force_learn(snap: dict, action: str, n: int = 3) -> dict:
    rt = restore(snap)
    east_strip(rt)
    obs0 = rt.agent_observation()
    cls0 = classify_unmodeled_actions(store=rt.cognition["prospection"], observation=obs0)
    rt.step_forced_action(action)
    cons = rt.agent_observation()
    for i in range(n):
        pr.learn_transition(
            rt.cognition["prospection"], tick=800 + i,
            antecedent=obs0, action=action, consequent=cons,
        )
    cls1 = classify_unmodeled_actions(store=rt.cognition["prospection"], observation=obs0)
    groups = sc.collect_scenario_groups(
        store=rt.cognition["prospection"], observation=obs0,
        continuations=pr.compose_trajectories(
            rt.cognition["prospection"], start=obs0, max_depth=3, branch_actions=ACTIONS,
        ).get("continuations") or [],
        actions=ACTIONS,
    )
    comp = sc.compete_scenarios(groups=groups, actions=ACTIONS, rng_value=0.0)
    return {
        "action": action,
        "eligible_before": action in cls0["unmodeled_first_actions"],
        "eligible_after": action in cls1["unmodeled_first_actions"],
        "modeled_after": action in cls1["modeled_first_actions"],
        "supported_after": list((comp.get("competition") or {}).get("supported_actions") or []),
        "outcome_after": (comp.get("competition") or {}).get("outcome_class"),
        "selected_after": comp.get("selected"),
        "source_after": comp.get("source"),
        "l1_obs": sum(
            abs(float(cons.get(k, 0.0)) - float(obs0.get(k, 0.0)))
            for k in set(cons) | set(obs0)
        ) / max(1, len(set(cons) | set(obs0))),
        "note": "harness forced execution + ordinary learn_transition; not live probe selection",
    }


def work_limit_trace(snap: dict, action: str) -> dict:
    rt = restore(snap)
    rt.body.mechanical_work_reservoir = 0.0
    east_strip(rt)
    obs0 = rt.agent_observation()
    rt.step_forced_action(action)
    ledger = rt.last_action_work_ledger or {}
    cons = rt.agent_observation()
    pr.learn_transition(
        rt.cognition["prospection"], tick=900,
        antecedent=obs0, action=action, consequent=cons,
    )
    return {
        "action": action,
        "requested": ledger.get("action_dv_requested"),
        "realized": ledger.get("action_dv_realized"),
        "frac": ledger.get("action_work_limit_fraction"),
        "W_after": float(rt.body.mechanical_work_reservoir or 0.0),
        "obs_l1": sum(
            abs(float(cons.get(k, 0.0)) - float(obs0.get(k, 0.0)))
            for k in set(cons) | set(obs0)
        ) / max(1, len(set(cons) | set(obs0))),
        "learned_from": "realized_observation_not_requested_dv",
        "note": "ordinary learn_transition on actual consequent",
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pairs = []
    snaps = {}
    for seed in SEEDS:
        print("pair", seed, flush=True)
        row = run_pair(seed)
        snaps[seed] = row.pop("snap_on")
        pairs.append(row)

    probe_events = []
    acq = []
    comp_rows = []
    work_rows = []
    abl = []
    for seed, snap in snaps.items():
        inc = next(p["lock"]["locked_action"] for p in pairs if p["seed"] == seed)
        probe_events.append({
            "seed": seed, "incumbent": inc,
            "live_probe_events": [],
            "reason": "DESIGN_BOUNDARY: no selection-side probe; UNKNOWN_ACTION_PROBED never emitted",
        })
        d = diagnostic_force_learn(snap, "MOVE:E", 3)
        acq.append({"seed": seed, "incumbent": inc, **d})
        comp_rows.append({
            "seed": seed, "incumbent": inc,
            "after_diagnostic_force_MOVE_E": {
                "supported": d["supported_after"],
                "outcome": d["outcome_after"],
                "selected": d["selected_after"],
                "source": d["source_after"],
                "true_competition": d["outcome_after"] in {
                    "DOMINANT_SCENARIO", "EXACT_TIE", "INCOMPARABLE", "PARTIAL_ORDER_TIE",
                } and len(d["supported_after"] or []) >= 2,
            },
            "note": "competition only after harness-forced history, not live probe",
        })
        work_rows.append({"seed": seed, **work_limit_trace(snap, "MOVE:E")})

        # ablations after diagnostic acquire
        rt = restore(snap)
        east_strip(rt)
        obs0 = rt.agent_observation()
        rt.step_forced_action("MOVE:E")
        cons = rt.agent_observation()
        for i in range(3):
            pr.learn_transition(rt.cognition["prospection"], tick=800 + i, antecedent=obs0, action="MOVE:E", consequent=cons)
        snap_acq = rt.snapshot()
        rtf = restore(snap_acq)
        rtf.set_ablations(prospective_composition=False)
        rtf.step()
        rtg = restore(snap_acq)
        rtg.set_mechanism("prospective_scenario_competition", False)
        rtg.step()
        rth = restore(snap_acq)
        rth.cognition["prospection"]["transitions"] = {
            k: v for k, v in (rth.cognition["prospection"].get("transitions") or {}).items()
            if v.get("action") != "MOVE:E"
        }
        cls_h = classify_unmodeled_actions(
            store=rth.cognition["prospection"], observation=obs0,
        )
        abl.append({
            "seed": seed,
            "F_pros_ablate_selected": rtf.last_selected_action,
            "F_source": (rtf.cognition.get("last_selection") or {}).get("source"),
            "G_legacy_selected": rtg.last_selected_action,
            "G_source": (rtg.cognition.get("last_selection") or {}).get("source"),
            "H_MOVE_E_unmodeled_after_delete": "MOVE:E" in cls_h["unmodeled_first_actions"],
        })

    # D: no strip, WAIT vs MOVE:E obs difference
    indist = []
    for seed in (17, 66667):
        rt = make_rt(seed, probe=True)
        for _ in range(25):
            rt.step()
        snap = rt.snapshot()
        a = restore(snap)
        a.step_forced_action("WAIT")
        b = restore(snap)
        b.step_forced_action("MOVE:E")
        oa, ob = a.agent_observation(), b.agent_observation()
        l1 = sum(abs(float(oa.get(k, 0)) - float(ob.get(k, 0))) for k in set(oa) | set(ob)) / max(1, len(set(oa) | set(ob)))
        indist.append({"seed": seed, "WAIT_vs_MOVE_E_l1": l1, "distinct": l1 > 0.02})

    (OUT / "PROBE_EVENTS.json").write_text(json.dumps({
        "design_boundary": True,
        "pairs": [{k: v for k, v in p.items() if k != "snap_on"} for p in pairs],
        "events": probe_events,
    }, indent=2, default=str), encoding="utf-8")
    (OUT / "ACQUISITION_TRACES.json").write_text(json.dumps(acq, indent=2, default=str), encoding="utf-8")
    (OUT / "SCENARIO_COMPETITION_RESULTS.json").write_text(json.dumps(comp_rows, indent=2, default=str), encoding="utf-8")
    (OUT / "WORK_LIMIT_RESULTS.json").write_text(json.dumps(work_rows, indent=2, default=str), encoding="utf-8")
    (OUT / "ABLATION_RESULTS.json").write_text(json.dumps({
        "after_diagnostic_acquire": abl,
        "indistinguishable_control": indist,
    }, indent=2, default=str), encoding="utf-8")
    print("done", json.dumps({p["seed"]: p["same_action_sequence"] for p in pairs}), flush=True)


if __name__ == "__main__":
    main()
