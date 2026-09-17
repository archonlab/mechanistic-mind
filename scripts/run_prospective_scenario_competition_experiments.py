#!/usr/bin/env python3
"""Prospective Scenario Competition experiments (LEGACY vs COMPETITION).

Does not overwrite results/mm_wait_persistence_diagnosis/.
"""
from __future__ import annotations

import json
import math
from collections import Counter
from copy import deepcopy
from pathlib import Path

from mechanistic_mind.physical_system.cognition import CognitionConfig
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime
from mechanistic_mind.research import prospective_composition as pr

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "mm_prospective_scenario_competition"
SEEDS = [17, 23, 41, 59, 83]
TICKS = 500


def _entropy(counts: Counter) -> float:
    n = sum(counts.values())
    if n <= 0:
        return 0.0
    h = 0.0
    for c in counts.values():
        p = c / n
        if p > 0:
            h -= p * math.log(p, 2)
    return h


def _spatial(positions: list[dict]) -> dict:
    if len(positions) < 2:
        return {"status": "NOT_AVAILABLE"}
    xs = [p["x"] for p in positions]
    ys = [p["y"] for p in positions]
    cells = {(int(math.floor(p["x"])), int(math.floor(p["y"]))) for p in positions}
    path = 0.0
    wraps = 0
    w = 32
    for i in range(1, len(positions)):
        dx = abs(positions[i]["x"] - positions[i - 1]["x"])
        dy = abs(positions[i]["y"] - positions[i - 1]["y"])
        if dx > w * 0.5 or dy > w * 0.5:
            wraps += 1
        else:
            path += math.hypot(dx, dy)
    return {
        "status": "AVAILABLE",
        "bbox_dx": max(xs) - min(xs),
        "bbox_dy": max(ys) - min(ys),
        "unique_cells": len(cells),
        "path_length_naive": path,
        "wrap_crossings_approx": wraps,
    }


def _longest_run(actions: list[str]) -> int:
    best = cur = 0
    prev = None
    for a in actions:
        if a == prev:
            cur += 1
        else:
            cur = 1
            prev = a
        best = max(best, cur)
    return best


def make_runtime(seed: int, selection: str, **cog_kwargs) -> PhysicalSystemRuntime:
    cog = CognitionConfig(prospective_selection=selection, **cog_kwargs)
    cfg = PhysicalSystemConfig(cognition=cog)
    return PhysicalSystemRuntime(seed=seed, config=cfg)


def run_arm(seed: int, selection: str, ticks: int = TICKS, **cog_kwargs) -> dict:
    rt = make_runtime(seed, selection, **cog_kwargs)
    actions: list[str] = []
    sources: list[str] = []
    positions: list[dict] = []
    supported_hist = Counter()
    scenario_div = []
    cont_div = []
    for t in range(ticks):
        rt.step()
        act = rt.last_selected_action or (rt.cognition.get("last_action"))
        actions.append(str(act))
        sel = rt.cognition.get("last_selection") or {}
        sources.append(str(sel.get("source") or rt.cognition.get("last_selection_source") or "?"))
        body = rt.body
        positions.append({"x": float(body.x), "y": float(body.y), "tick": rt.tick, "action": act})
        groups = sel.get("scenario_groups") or {}
        if selection == "SCENARIO_COMPETITION":
            n_sup = sum(1 for a, g in groups.items() if (g.get("supported") or g.get("count") or g.get("scenarios")))
            # also from competition blob
            comp = sel.get("competition") or {}
            if comp.get("supported_actions") is not None:
                n_sup = len(comp.get("supported_actions") or [])
            supported_hist[n_sup] += 1
            scenario_div.append(sum(int(g.get("count") or len(g.get("scenarios") or [])) for g in groups.values()))
        conts = sel.get("continuations") or []
        cont_div.append(len(conts))
    counts = Counter(actions)
    n = max(1, len(actions))
    wait_f = counts.get("WAIT", 0) / n
    move_f = sum(v for k, v in counts.items() if str(k).startswith("MOVE")) / n
    return {
        "seed": seed,
        "prospective_selection": selection,
        "ticks": ticks,
        "cognition": rt.cognition.get("config"),
        "wait_fraction": wait_f,
        "move_fraction": move_f,
        "action_counts": dict(counts),
        "action_entropy": _entropy(counts),
        "longest_same_action_sequence": _longest_run(actions),
        "source_histogram": dict(Counter(sources)),
        "spatial": _spatial(positions),
        "supported_action_cardinality": {
            "ticks_with_0_supported_actions": int(supported_hist.get(0, 0)),
            "ticks_with_1_supported_action": int(supported_hist.get(1, 0)),
            "ticks_with_2plus_supported_actions": int(sum(v for k, v in supported_hist.items() if k >= 2)),
            "histogram": {str(k): int(v) for k, v in sorted(supported_hist.items())},
        } if selection == "SCENARIO_COMPETITION" else None,
        "mean_scenario_count": (sum(scenario_div) / max(1, len(scenario_div))) if scenario_div else None,
        "mean_continuation_count": sum(cont_div) / max(1, len(cont_div)),
    }


def mean_key(rows: list[dict], key: str) -> float:
    vals = [float(r[key]) for r in rows if r.get(key) is not None]
    return sum(vals) / max(1, len(vals))


def experiment_history_transition() -> dict:
    """Phase A reinforce WAIT; Phase B reinforce MOVE:N; free selection throughout."""
    seed = 41
    rt = make_runtime(seed, "SCENARIO_COMPETITION")
    phase_a, phase_b = 200, 200
    log = []
    first_move_supported = None
    first_move_selected = None
    simultaneous_window = 0
    for t in range(phase_a + phase_b):
        # capture obs before step for learning target after
        obs_before = deepcopy(rt.cognition.get("last_fragment") or rt.last_agent_observation or {})
        rt.step()
        obs_after = deepcopy(rt.cognition.get("last_fragment") or {})
        sel = rt.cognition.get("last_selection") or {}
        groups = sel.get("scenario_groups") or {}
        comp = sel.get("competition") or {}
        supported = set(comp.get("supported_actions") or [a for a, g in groups.items() if g.get("supported") or g.get("scenarios")])
        selected = sel.get("action")
        phase = "A" if t < phase_a else "B"
        if obs_before and obs_after:
            store = rt.cognition["prospection"]
            if phase == "A":
                for _ in range(3):
                    pr.learn_transition(store, tick=rt.tick, antecedent=obs_before, action="WAIT", consequent=obs_after)
            else:
                for _ in range(3):
                    pr.learn_transition(store, tick=rt.tick, antecedent=obs_before, action="MOVE:N", consequent=obs_after)
        if "MOVE:N" in supported and first_move_supported is None:
            first_move_supported = t
        if selected == "MOVE:N" and first_move_selected is None:
            first_move_selected = t
        if "WAIT" in supported and "MOVE:N" in supported:
            simultaneous_window += 1
        if t % 25 == 0 or t in {phase_a - 1, phase_a, phase_a + phase_b - 1}:
            log.append({
                "t": t,
                "phase": phase,
                "selected": selected,
                "supported": sorted(supported),
                "source": sel.get("source"),
                "outcome": (comp or {}).get("outcome_class"),
            })
    return {
        "seed": seed,
        "phase_a_ticks": phase_a,
        "phase_b_ticks": phase_b,
        "first_MOVE_N_supported_tick": first_move_supported,
        "first_MOVE_N_selected_tick": first_move_selected,
        "A_B_simultaneous_support_ticks": simultaneous_window,
        "transition_observed": first_move_selected is not None and first_move_selected >= phase_a,
        "log_sparsed": log,
    }


def experiment_history_swap() -> dict:
    from mechanistic_mind.physical_system import scenario_competition as sc
    seed = 59

    def sc_groups_from(rt, obs):
        return sc.collect_scenario_groups(
            store=rt.cognition["prospection"],
            observation=obs,
            continuations=[],
        )

    def compete_now(rt, obs):
        groups = sc_groups_from(rt, obs)
        return sc.compete_scenarios(groups=groups, actions=list(groups.keys()), rng_value=0.1)

    def primed(label: str, reinforce_action: str) -> dict:
        rt = make_runtime(seed, "SCENARIO_COMPETITION")
        for _ in range(5):
            rt.step()
        obs = deepcopy(rt.cognition.get("last_fragment") or {})
        store = rt.cognition["prospection"]
        cons = {k: float(v) + (0.02 if reinforce_action == "WAIT" else 0.07) for k, v in obs.items()}
        for i in range(12):
            pr.learn_transition(store, tick=1000 + i, antecedent=obs, action=reinforce_action, consequent=cons)
        before = {
            "observation": deepcopy(obs),
            "body": {"x": float(rt.body.x), "y": float(rt.body.y)},
        }
        groups = sc_groups_from(rt, obs)
        out = compete_now(rt, obs)
        return {
            "label": label,
            "reinforce_action": reinforce_action,
            "present": before,
            "supported": out.get("competition", {}).get("supported_actions"),
            "selected": out.get("selected"),
            "source": out.get("source"),
            "outcome": out.get("competition", {}).get("outcome_class"),
            "scenario_counts": {a: len(g) for a, g in groups.items()},
        }

    a = primed("WAIT_HISTORY", "WAIT")
    b = primed("MOVE_N_HISTORY", "MOVE:N")
    return {
        "same_seed_init": seed,
        "agents": [a, b],
        "different_supported_or_selected": (
            a.get("supported") != b.get("supported") or a.get("selected") != b.get("selected")
        ),
    }


def experiment_hysteresis() -> dict:
    seed = 23
    rt = make_runtime(seed, "SCENARIO_COMPETITION")
    phases = [("A", "WAIT", 150), ("B", "MOVE:N", 150), ("A2", "WAIT", 150)]
    t = 0
    events = []
    selected_series = []
    for name, reinforce, n in phases:
        for _ in range(n):
            obs_before = deepcopy(rt.cognition.get("last_fragment") or rt.last_agent_observation or {})
            rt.step()
            obs_after = deepcopy(rt.cognition.get("last_fragment") or {})
            if obs_before and obs_after:
                for __ in range(3):
                    pr.learn_transition(
                        rt.cognition["prospection"],
                        tick=rt.tick,
                        antecedent=obs_before,
                        action=reinforce,
                        consequent=obs_after,
                    )
            sel = (rt.cognition.get("last_selection") or {}).get("action")
            selected_series.append(sel)
            t += 1
        events.append({"phase": name, "reinforce": reinforce, "end_t": t, "last_selected": selected_series[-1]})
    # crude transition detection
    def first_switch(series, start, end, target):
        for i in range(start, min(end, len(series))):
            if series[i] == target:
                return i
        return None
    return {
        "seed": seed,
        "events": events,
        "A_to_B_first_MOVE_N": first_switch(selected_series, 150, 300, "MOVE:N"),
        "B_to_A_first_WAIT": first_switch(selected_series, 300, 450, "WAIT"),
        "note": "Timing asymmetry would support history-dependent hysteresis; equal/absent transitions do not.",
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    print("=== BASELINE LEGACY ===")
    legacy_rows = [run_arm(s, "LEGACY_FIRST") for s in SEEDS]
    baseline = {
        "seeds": SEEDS,
        "ticks": TICKS,
        "prospective_selection": "LEGACY_FIRST",
        "rows": legacy_rows,
        "mean_wait_fraction": mean_key(legacy_rows, "wait_fraction"),
        "mean_move_fraction": mean_key(legacy_rows, "move_fraction"),
        "note": "Control reproduction of diagnosis baseline; diagnosis dir not overwritten.",
    }
    (OUT / "baseline_legacy.json").write_text(json.dumps(baseline, indent=2, default=str))
    print("mean WAIT legacy", baseline["mean_wait_fraction"])

    print("=== COMPETITION ===")
    comp_rows = [run_arm(s, "SCENARIO_COMPETITION") for s in SEEDS]
    competition = {
        "seeds": SEEDS,
        "ticks": TICKS,
        "prospective_selection": "SCENARIO_COMPETITION",
        "rows": comp_rows,
        "mean_wait_fraction": mean_key(comp_rows, "wait_fraction"),
        "mean_move_fraction": mean_key(comp_rows, "move_fraction"),
        "experiment_A_aggregate": {
            "ticks_with_0_supported_actions": sum((r.get("supported_action_cardinality") or {}).get("ticks_with_0_supported_actions", 0) for r in comp_rows),
            "ticks_with_1_supported_action": sum((r.get("supported_action_cardinality") or {}).get("ticks_with_1_supported_action", 0) for r in comp_rows),
            "ticks_with_2plus_supported_actions": sum((r.get("supported_action_cardinality") or {}).get("ticks_with_2plus_supported_actions", 0) for r in comp_rows),
        },
    }
    (OUT / "competition_results.json").write_text(json.dumps(competition, indent=2, default=str))
    print("mean WAIT competition", competition["mean_wait_fraction"])
    print("Experiment A", competition["experiment_A_aggregate"])

    seed_summary = {
        "comparison": [
            {
                "seed": s,
                "legacy_wait": next(r["wait_fraction"] for r in legacy_rows if r["seed"] == s),
                "competition_wait": next(r["wait_fraction"] for r in comp_rows if r["seed"] == s),
                "legacy_entropy": next(r["action_entropy"] for r in legacy_rows if r["seed"] == s),
                "competition_entropy": next(r["action_entropy"] for r in comp_rows if r["seed"] == s),
                "legacy_spatial_cells": (next(r["spatial"] for r in legacy_rows if r["seed"] == s) or {}).get("unique_cells"),
                "competition_spatial_cells": (next(r["spatial"] for r in comp_rows if r["seed"] == s) or {}).get("unique_cells"),
                "competition_2plus_supported": (next(r.get("supported_action_cardinality") or {} for r in comp_rows if r["seed"] == s)).get("ticks_with_2plus_supported_actions"),
            }
            for s in SEEDS
        ]
    }
    (OUT / "seed_summary.json").write_text(json.dumps(seed_summary, indent=2, default=str))

    print("=== ABLATIONS ===")
    ablations = []
    for name, kwargs in [
        ("competition_normal", {"prospective_composition": True}),
        ("prospective_OFF", {"prospective_composition": False}),
        ("retrieval_OFF", {"retrieval": False}),
        ("compression_OFF", {"predictive_compression": False}),
        ("multiscale_OFF", {"multiscale_prediction": False}),
        ("legacy_control", {}),
    ]:
        sel = "LEGACY_FIRST" if name == "legacy_control" else "SCENARIO_COMPETITION"
        rows = [run_arm(s, sel, ticks=300, **kwargs) for s in SEEDS]
        ablations.append({
            "name": name,
            "prospective_selection": sel,
            "kwargs": kwargs,
            "mean_wait": mean_key(rows, "wait_fraction"),
            "mean_move": mean_key(rows, "move_fraction"),
            "rows": rows,
        })
        print(name, "wait", ablations[-1]["mean_wait"])
    (OUT / "ablation_results.json").write_text(json.dumps({"ablations": ablations}, indent=2, default=str))

    print("=== HISTORY TRANSITION / SWAP / HYSTERESIS ===")
    hist = {
        "experiment_B": experiment_history_transition(),
        "experiment_C": experiment_history_swap(),
        "experiment_D": experiment_hysteresis(),
    }
    # fix typo key
    (OUT / "history_transition_results.json").write_text(json.dumps(hist, indent=2, default=str))
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "log_sparsed" and kk != "agents"} for k, v in hist.items()}, indent=2, default=str)[:2000])
    print("DONE", OUT)


if __name__ == "__main__":
    main()
