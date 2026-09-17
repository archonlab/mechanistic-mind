#!/usr/bin/env python3
"""Two-agent shared-world substrate experiments. No social semantics."""
from __future__ import annotations

import json
import sys
import time
from collections import Counter
from copy import deepcopy
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mechanistic_mind.physical_system import PhysicalSystemRuntime, TwoAgentRuntime
from mechanistic_mind.physical_system.actions import BRIDGE_MISSING
from mechanistic_mind.physical_system.cognition import empty_cognitive_state
from mechanistic_mind.physical_system.complementary_resources import place_source_AB
from mechanistic_mind.physical_system.observation import audit_cognition_payload

OUT = ROOT / "results" / "mm_two_agent_interaction"
SEEDS = (17, 23, 41, 59)
NEAR = ((9.0, 16.0), (10.2, 16.0))
SPEC_NEAR = ((8.0, 16.0), (12.0, 16.0))
FAR = ((8.0, 16.0), (24.0, 16.0))
SYMM = ((8.0, 16.0), (24.0, 16.0))
E1_TICKS = 40
E2_TICKS = 40
E3_INTERACT = 16
E3_SEPARATE = 8
E4_TICKS = 12
DIV_TICKS = 60
PERF_TICKS = 40


def _json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n")


def make_ta(
    seed: int,
    *,
    starts=SPEC_NEAR,
    contact: bool = True,
    field: bool = True,
    order=(0, 1),
) -> TwoAgentRuntime:
    return TwoAgentRuntime(
        seed=int(seed),
        starts=starts,
        contact_enabled=contact,
        field_coupling_enabled=field,
        process_order=tuple(order),
    )


def site_sum(body, name: str) -> float:
    arr = getattr(body, name, None)
    if arr is None:
        return 0.0
    return float(np.sum(arr))


def obs_l1(a: dict, b: dict) -> float:
    keys = set(a) | set(b)
    return float(sum(abs(float(a.get(k) or 0) - float(b.get(k) or 0)) for k in keys))


def hist_size(rt) -> dict:
    cog = rt.cognition
    mem = cog.get("compression") or {}
    prs = cog.get("prospection") or {}
    counts = (cog.get("metrics") or {}).get("action_counts") or {}
    return {
        "raw_retained": int(mem.get("raw_retained") or len(mem.get("raw_log") or [])),
        "structures": int(len(mem.get("structures") or {})),
        "recent": int(len(mem.get("recent") or [])),
        "prospection_n": int(len(prs.get("episodes") or prs.get("continuations") or [])),
        "action_counts": dict(counts),
        "last_action": cog.get("last_action"),
        "source": (cog.get("last_selection") or {}).get("source"),
    }


def slot_row(rt, contact=None) -> dict:
    obs = rt.last_agent_observation or {}
    sel = rt.cognition.get("last_selection") or {}
    comp = sel.get("competition") or {}
    return {
        "tick": int(rt.tick),
        "x": float(rt.body.x),
        "y": float(rt.body.y),
        "vx": float(rt.body.vx),
        "vy": float(rt.body.vy),
        "work": float(getattr(rt.body, "mechanical_work_reservoir", 0.0) or 0.0),
        "body_A": site_sum(rt.body, "R_A_site"),
        "body_B": site_sum(rt.body, "R_B_site"),
        "action": rt.last_selected_action,
        "source": sel.get("source"),
        "supported": list(comp.get("supported_actions") or []),
        "obs_T": float(obs.get("local.T") or 0.0),
        "obs_vx": float(obs.get("local.vx") or 0.0),
        "body_T": float(obs.get("body.T") or 0.0),
        "history": hist_size(rt),
        "contact": bool((contact or {}).get("contact")),
    }


def pair_row(ta: TwoAgentRuntime) -> dict:
    return {
        "tick": int(ta.tick),
        "contact": deepcopy(ta.last_contact),
        "agent_0": slot_row(ta.slots[0], ta.last_contact),
        "agent_1": slot_row(ta.slots[1], ta.last_contact),
        "obs_l1": obs_l1(ta.slots[0].last_agent_observation or {}, ta.slots[1].last_agent_observation or {}),
        "env_A": float(np.sum(ta.world.R_A)) if ta.world.R_A is not None else 0.0,
        "env_B": float(np.sum(ta.world.R_B)) if ta.world.R_B is not None else 0.0,
    }


def pose(ta: TwoAgentRuntime, starts) -> None:
    for rt, (x, y) in zip(ta.slots, starts):
        rt.body.x = float(x)
        rt.body.y = float(y)
        rt.body.vx = 0.0
        rt.body.vy = 0.0


def first_action_divergence(a_actions, b_actions) -> int | None:
    for i, (x, y) in enumerate(zip(a_actions, b_actions)):
        if x != y:
            return i
    return None


def leak_check(ta: TwoAgentRuntime) -> list[str]:
    hits = []
    for obs in ta.observations():
        hits.extend(audit_cognition_payload(obs))
        blob = repr(obs)
        for tok in ("agent_0", "agent_1", "other agent", "enemy", "friend", "competitor"):
            if tok in blob:
                hits.append(tok)
    return hits


def run_e1() -> dict:
    rows = []
    for seed in SEEDS:
        ghost = make_ta(seed, starts=NEAR, contact=False, field=False)
        solid = make_ta(seed, starts=NEAR, contact=True, field=False)
        spec = make_ta(seed, starts=SPEC_NEAR, contact=True, field=False)
        contacts = 0
        spec_contacts = 0
        for _ in range(E1_TICKS):
            ghost.step(1)
            solid.step(1)
            spec.step(1)
            if solid.last_contact and solid.last_contact.get("contact"):
                contacts += 1
            if spec.last_contact and spec.last_contact.get("contact"):
                spec_contacts += 1
        dx = abs(solid.slots[0].body.x - ghost.slots[0].body.x) + abs(solid.slots[1].body.x - ghost.slots[1].body.x)
        dy = abs(solid.slots[0].body.y - ghost.slots[0].body.y) + abs(solid.slots[1].body.y - ghost.slots[1].body.y)
        o0 = obs_l1(solid.slots[0].last_agent_observation or {}, ghost.slots[0].last_agent_observation or {})
        o1 = obs_l1(solid.slots[1].last_agent_observation or {}, ghost.slots[1].last_agent_observation or {})
        rows.append({
            "seed": seed,
            "near_contact_ticks": contacts,
            "spec_near_contact_ticks": spec_contacts,
            "ghost_vs_solid_pos_l1": float(dx + dy),
            "ghost_vs_solid_obs_l1_0": o0,
            "ghost_vs_solid_obs_l1_1": o1,
            "solid_final": pair_row(solid),
            "ghost_final": pair_row(ghost),
            "spec_final_dist": float(abs(spec.slots[0].body.x - spec.slots[1].body.x) + abs(spec.slots[0].body.y - spec.slots[1].body.y)),
            "leaks": leak_check(solid),
        })
    physical_cause = any(r["near_contact_ticks"] > 0 and r["ghost_vs_solid_pos_l1"] > 1e-3 for r in rows)
    return {
        "ticks": E1_TICKS,
        "near_starts": NEAR,
        "spec_starts": SPEC_NEAR,
        "field_coupling": False,
        "seeds": list(SEEDS),
        "rows": rows,
        "other_body_as_physical_cause": physical_cause,
        "note": "Ghost = contact OFF. Solid = contact ON. Field coupling OFF. No social mechanism.",
    }


def run_e2() -> dict:
    rows = []
    for seed in SEEDS:
        s0 = make_ta(seed, starts=NEAR, contact=True, field=False)
        s1 = make_ta(seed, starts=NEAR, contact=True, field=True)
        acts0 = [[], []]
        acts1 = [[], []]
        obs_series = []
        first_obs = None
        first_act = None
        for t in range(E2_TICKS):
            s0.step(1)
            s1.step(1)
            for i in range(2):
                acts0[i].append(s0.slots[i].last_selected_action)
                acts1[i].append(s1.slots[i].last_selected_action)
            d0 = obs_l1(s0.slots[0].last_agent_observation or {}, s1.slots[0].last_agent_observation or {})
            d1 = obs_l1(s0.slots[1].last_agent_observation or {}, s1.slots[1].last_agent_observation or {})
            t0 = abs(float((s0.slots[0].last_agent_observation or {}).get("local.T") or 0) - float((s1.slots[0].last_agent_observation or {}).get("local.T") or 0))
            if first_obs is None and (d0 + d1) > 1e-6:
                first_obs = t + 1
            if first_act is None and (acts0[0][-1] != acts1[0][-1] or acts0[1][-1] != acts1[1][-1]):
                first_act = t + 1
            if t % 8 == 7:
                obs_series.append({"tick": t + 1, "obs_l1_0": d0, "obs_l1_1": d1, "d_local_T_0": t0})
        rows.append({
            "seed": seed,
            "first_obs_divergence_tick": first_obs,
            "first_action_divergence_tick": first_act,
            "final_obs_l1_0": obs_l1(s0.slots[0].last_agent_observation or {}, s1.slots[0].last_agent_observation or {}),
            "final_pos_l1": float(
                abs(s0.slots[0].body.x - s1.slots[0].body.x) + abs(s0.slots[1].body.x - s1.slots[1].body.x)
                + abs(s0.slots[0].body.y - s1.slots[1].body.y) + abs(s0.slots[1].body.y - s1.slots[1].body.y)
            ),
            "actions_s0": {0: Counter(acts0[0]), 1: Counter(acts0[1])},
            "actions_s1": {0: Counter(acts1[0]), 1: Counter(acts1[1])},
            "series": obs_series,
            "s0_hist": [hist_size(s0.slots[0]), hist_size(s0.slots[1])],
            "s1_hist": [hist_size(s1.slots[0]), hist_size(s1.slots[1])],
        })
    return {
        "ticks": E2_TICKS,
        "starts": NEAR,
        "S0": "field_coupling OFF",
        "S1": "field_coupling ON (thermal/material backreact; EMIT still BRIDGE_MISSING)",
        "rows": rows,
        "any_obs_divergence": any(r["first_obs_divergence_tick"] is not None for r in rows),
        "any_action_divergence": any(r["first_action_divergence_tick"] is not None for r in rows),
    }


def run_e3() -> dict:
    rows = []
    encounter = NEAR
    separated = ((6.0, 16.0), (22.0, 16.0))
    for seed in SEEDS:
        ta = make_ta(seed, starts=encounter, contact=True, field=False)
        ta.step(E3_INTERACT)
        after_first = {
            "actions": [ta.slots[0].last_selected_action, ta.slots[1].last_selected_action],
            "hist": [hist_size(ta.slots[0]), hist_size(ta.slots[1])],
            "obs_l1": obs_l1(ta.slots[0].last_agent_observation or {}, ta.slots[1].last_agent_observation or {}),
        }
        pose(ta, separated)
        ta.step(E3_SEPARATE)
        keep = deepcopy(ta.snapshot())
        hist_rt = TwoAgentRuntime.restore(deepcopy(keep))
        wipe_rt = TwoAgentRuntime.restore(deepcopy(keep))
        wipe_rt.slots[0].cognition = empty_cognitive_state(wipe_rt.slots[0].config.cognition)
        wipe_rt.slots[1].cognition = empty_cognitive_state(wipe_rt.slots[1].config.cognition)
        pose(hist_rt, encounter)
        pose(wipe_rt, encounter)
        hist_rt.step(1)
        wipe_rt.step(1)
        same_present = {
            "hist_xy": [(hist_rt.slots[0].body.x, hist_rt.slots[0].body.y), (hist_rt.slots[1].body.x, hist_rt.slots[1].body.y)],
            "wipe_xy": [(wipe_rt.slots[0].body.x, wipe_rt.slots[0].body.y), (wipe_rt.slots[1].body.x, wipe_rt.slots[1].body.y)],
        }
        rows.append({
            "seed": seed,
            "after_first_encounter": after_first,
            "same_present_pose": encounter,
            "kept_actions": [hist_rt.slots[0].last_selected_action, hist_rt.slots[1].last_selected_action],
            "wiped_actions": [wipe_rt.slots[0].last_selected_action, wipe_rt.slots[1].last_selected_action],
            "kept_source": [(hist_rt.slots[i].cognition.get("last_selection") or {}).get("source") for i in range(2)],
            "wiped_source": [(wipe_rt.slots[i].cognition.get("last_selection") or {}).get("source") for i in range(2)],
            "action_differs": (
                hist_rt.slots[0].last_selected_action != wipe_rt.slots[0].last_selected_action
                or hist_rt.slots[1].last_selected_action != wipe_rt.slots[1].last_selected_action
            ),
            "present_pose_l1": float(
                abs(hist_rt.slots[0].body.x - wipe_rt.slots[0].body.x)
                + abs(hist_rt.slots[1].body.x - wipe_rt.slots[1].body.x)
            ),
            "pose_check": same_present,
        })
    return {
        "interact_ticks": E3_INTERACT,
        "separate_ticks": E3_SEPARATE,
        "encounter_pose": encounter,
        "separated_pose": separated,
        "rows": rows,
        "any_history_dependent_action": any(r["action_differs"] for r in rows),
        "note": "Experimenter pose reset. Same present arrangement + kept vs wiped history. Not recognition of Agent B.",
    }


def run_e4() -> dict:
    rows = []
    for seed in SEEDS:
        shared = make_ta(seed, starts=((10.0, 16.0), (10.0, 16.0)), contact=True, field=False)
        place_source_AB(shared.world, 16, 10, A=0.80, B=0.40)
        initial_A = float(shared.world.R_A[16, 10])
        initial_B = float(shared.world.R_B[16, 10])
        solo = PhysicalSystemRuntime(seed=seed)
        solo.body.x, solo.body.y = 10.0, 16.0
        place_source_AB(solo.world, 16, 10, A=0.80, B=0.40)
        solo_initial = float(solo.world.R_A[16, 10])
        ledgers = []
        for _ in range(E4_TICKS):
            shared.step(1)
            solo.step(1)
            if shared.last_resource_sim:
                ledgers.append({
                    "tick": shared.tick,
                    "A0": (shared.last_resource_sim[0].get("A") or {}).get("removed"),
                    "A1": (shared.last_resource_sim[1].get("A") or {}).get("removed"),
                    "scale": (shared.last_resource_sim[0].get("A") or {}).get("scale_min"),
                    "env_A_cell": float(shared.world.R_A[16, 10]),
                })
        a0 = site_sum(shared.slots[0].body, "R_A_site")
        a1 = site_sum(shared.slots[1].body, "R_A_site")
        env = float(shared.world.R_A[16, 10])
        removed = 0.0
        lost = 0.0
        if shared.last_resource_sim:
            for led in shared.last_resource_sim:
                removed += float((led.get("A") or {}).get("removed") or 0)
                lost += float((led.get("A") or {}).get("loss") or 0)
        rows.append({
            "seed": seed,
            "initial_cell_A": initial_A,
            "initial_cell_B": initial_B,
            "final_cell_A": env,
            "final_body_A_0": a0,
            "final_body_A_1": a1,
            "body_A_sum": a0 + a1,
            "no_double_spend": env + a0 + a1 <= initial_A + 1e-4,
            "solo_final_cell_A": float(solo.world.R_A[16, 10]),
            "solo_body_A": site_sum(solo.body, "R_A_site"),
            "shared_depletes_more_or_equal": env <= float(solo.world.R_A[16, 10]) + 1e-6,
            "work_0": float(shared.slots[0].body.mechanical_work_reservoir),
            "work_1": float(shared.slots[1].body.mechanical_work_reservoir),
            "last_scale_min": ledgers[-1]["scale"] if ledgers else None,
            "ledger_tail": ledgers[-4:],
        })
    return {
        "ticks": E4_TICKS,
        "cell": [16, 10],
        "starts_overlapping": True,
        "allocation_rule": "available/sum(requested) on contested cells; conservation, not social fairness",
        "rows": rows,
        "all_no_double_spend": all(r["no_double_spend"] for r in rows),
        "other_agent_alters_remainder": all(r["shared_depletes_more_or_equal"] for r in rows),
    }


def run_e5(e2: dict) -> dict:
    """Signal predictive value. EMIT is BRIDGE_MISSING; only backreact field path exists."""
    rows = []
    for seed in SEEDS[:2]:
        on = make_ta(seed, starts=NEAR, contact=True, field=True)
        for _ in range(48):
            on.step(1)
        keep = deepcopy(on.snapshot())
        stay = TwoAgentRuntime.restore(deepcopy(keep))
        off_prop = TwoAgentRuntime.restore(deepcopy(keep))
        off_prop.field_coupling_enabled = False
        for rt in off_prop.slots:
            rt.config.body.thermal_backreact = 0.0
            rt.config.body.material_backreact = False
        wipe = TwoAgentRuntime.restore(deepcopy(keep))
        wipe.slots[0].cognition = empty_cognitive_state(wipe.slots[0].config.cognition)
        stay.step(12)
        off_prop.step(12)
        wipe.step(12)
        rows.append({
            "seed": seed,
            "stay_actions": [stay.slots[0].last_selected_action, stay.slots[1].last_selected_action],
            "off_prop_actions": [off_prop.slots[0].last_selected_action, off_prop.slots[1].last_selected_action],
            "wipe_actions": [wipe.slots[0].last_selected_action, wipe.slots[1].last_selected_action],
            "stay_vs_off_action_diff": stay.slots[0].last_selected_action != off_prop.slots[0].last_selected_action,
            "stay_vs_wipe_action_diff": stay.slots[0].last_selected_action != wipe.slots[0].last_selected_action,
            "stay_hist": hist_size(stay.slots[0]),
            "off_hist": hist_size(off_prop.slots[0]),
        })
    return {
        "emit_bridge": "BRIDGE_MISSING",
        "physical_path_tested": "thermal/material backreact into shared T/M; receiver local.T/M",
        "e2_any_action_divergence": e2.get("any_action_divergence"),
        "e2_any_obs_divergence": e2.get("any_obs_divergence"),
        "rows": rows,
        "note": "No encoded meaning. No EMIT transducer. Ablation after short exposure only.",
    }


def run_self_other() -> dict:
    return {
        "status": "NOT_DEMONSTRATED",
        "mechanism_in_current_psr": "NOT_IMPLEMENTED",
        "legacy": (
            "update47 / update471 ObjectiveWorldEngine cross-agent trace is a different "
            "world model, not PhysicalSystemRuntime. Not integrated."
        ),
        "accessible_observation": "body-local T/M/vx/vy plus own internal.c; no other-body channels",
        "claim_language_forbidden": ["empathy", "theory of mind"],
        "conservative_label_if_later_shown": "self-other predictive generalization",
    }


def run_symmetry() -> dict:
    rows = []
    for seed in SEEDS:
        far_ab = make_ta(seed, starts=FAR, contact=True, field=True, order=(0, 1))
        far_ba = make_ta(seed, starts=FAR, contact=True, field=True, order=(1, 0))
        close_ab = make_ta(seed, starts=NEAR, contact=True, field=True, order=(0, 1))
        close_ba = make_ta(seed, starts=NEAR, contact=True, field=True, order=(1, 0))
        n = 24
        far_ab.step(n)
        far_ba.step(n)
        close_ab.step(n)
        close_ba.step(n)
        def pos_l1(a, b):
            return float(
                abs(a.slots[0].body.x - b.slots[0].body.x) + abs(a.slots[1].body.x - b.slots[1].body.x)
                + abs(a.slots[0].body.y - b.slots[0].body.y) + abs(a.slots[1].body.y - b.slots[1].body.y)
            )
        tiny = make_ta(seed, starts=((8.0, 16.0), (24.05, 16.0)), contact=True, field=True)
        base = make_ta(seed, starts=FAR, contact=True, field=True)
        tiny.step(n)
        base.step(n)
        rows.append({
            "seed": seed,
            "far_order_pos_l1": pos_l1(far_ab, far_ba),
            "close_order_pos_l1": pos_l1(close_ab, close_ba),
            "far_action_0": [far_ab.slots[0].last_selected_action, far_ba.slots[0].last_selected_action],
            "close_action_0": [close_ab.slots[0].last_selected_action, close_ba.slots[0].last_selected_action],
            "tiny_asymmetry_pos_l1": pos_l1(tiny, base),
        })
    return {
        "ticks": 24,
        "far_starts": FAR,
        "near_starts": NEAR,
        "tiny_delta_x": 0.05,
        "rows": rows,
        "far_max_order_l1": max(r["far_order_pos_l1"] for r in rows),
        "close_max_order_l1": max(r["close_order_pos_l1"] for r in rows),
        "note": "Sequential body backreact is a documented order bias. Far-apart should stay small.",
    }


def run_divergence() -> dict:
    rows = []
    for seed in SEEDS:
        ta = make_ta(seed, starts=SYMM, contact=True, field=True)
        series = []
        first_act = None
        first_obs = None
        for t in range(DIV_TICKS):
            ta.step(1)
            d_obs = obs_l1(ta.slots[0].last_agent_observation or {}, ta.slots[1].last_agent_observation or {})
            a0, a1 = ta.slots[0].last_selected_action, ta.slots[1].last_selected_action
            if first_obs is None and d_obs > 1e-5:
                first_obs = t + 1
            if first_act is None and a0 != a1:
                first_act = t + 1
            if t % 10 == 9:
                series.append({
                    "tick": t + 1,
                    "obs_l1": d_obs,
                    "actions": [a0, a1],
                    "xy": [
                        [float(ta.slots[0].body.x), float(ta.slots[0].body.y)],
                        [float(ta.slots[1].body.x), float(ta.slots[1].body.y)],
                    ],
                    "hist": [hist_size(ta.slots[0]), hist_size(ta.slots[1])],
                })
        rows.append({
            "seed": seed,
            "first_obs_asymmetry_tick": first_obs,
            "first_action_asymmetry_tick": first_act,
            "final_obs_l1": obs_l1(ta.slots[0].last_agent_observation or {}, ta.slots[1].last_agent_observation or {}),
            "final_actions": [ta.slots[0].last_selected_action, ta.slots[1].last_selected_action],
            "final_hist": [hist_size(ta.slots[0]), hist_size(ta.slots[1])],
            "series": series,
        })
    return {
        "ticks": DIV_TICKS,
        "starts": SYMM,
        "rows": rows,
        "any_action_split": any(r["first_action_asymmetry_tick"] is not None for r in rows),
        "any_obs_split": any(r["first_obs_asymmetry_tick"] is not None for r in rows),
        "note": "Initially mirrored far placement. Divergence may be numerical/order/backreact, not personality.",
    }


def run_perf() -> dict:
    one = PhysicalSystemRuntime(seed=17)
    two = make_ta(17, starts=SPEC_NEAR, contact=True, field=True)
    t0 = time.perf_counter()
    one.step(PERF_TICKS)
    t1 = time.perf_counter()
    two.step(PERF_TICKS)
    t2 = time.perf_counter()
    return {
        "ticks": PERF_TICKS,
        "one_agent_s": t1 - t0,
        "two_agent_s": t2 - t1,
        "ratio": (t2 - t1) / max(1e-9, t1 - t0),
        "telemetry": "bounded per-agent summaries in experiment JSON; no multi-GB JSONL",
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    e1 = run_e1()
    e2 = run_e2()
    e3 = run_e3()
    e4 = run_e4()
    e5 = run_e5(e2)
    so = run_self_other()
    sym = run_symmetry()
    div = run_divergence()
    perf = run_perf()
    _json(OUT / "BODY_INTERACTION_RESULTS.json", e1)
    _json(OUT / "SIGNAL_ON_OFF_RESULTS.json", e2)
    _json(OUT / "REPEATED_ENCOUNTER_RESULTS.json", e3)
    _json(OUT / "RESOURCE_INTERACTION_RESULTS.json", e4)
    _json(OUT / "SELF_OTHER_RESULTS.json", so)
    _json(OUT / "SYMMETRY_RESULTS.json", sym)
    _json(OUT / "HISTORY_DIVERGENCE.json", div)
    _json(OUT / "_e5_signal_predictive.json", e5)
    _json(OUT / "_performance.json", perf)
    print(json.dumps({
        "e1_physical_cause": e1["other_body_as_physical_cause"],
        "e2_obs": e2["any_obs_divergence"],
        "e2_act": e2["any_action_divergence"],
        "e3_hist_action": e3["any_history_dependent_action"],
        "e4_no_double": e4["all_no_double_spend"],
        "sym_far_max": sym["far_max_order_l1"],
        "sym_close_max": sym["close_max_order_l1"],
        "div_act": div["any_action_split"],
        "perf_ratio": perf["ratio"],
        "emit": "BRIDGE_MISSING",
        "self_other": so["status"],
    }, indent=2))


if __name__ == "__main__":
    main()
