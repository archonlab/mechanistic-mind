#!/usr/bin/env python3
"""PSC COMPOSITION PERFORMANCE — Phase A measurement (+ optional Phase B hooks).

Instruments late filled-store science path without changing semantics.
Measures stage wall time, call multiplication, and stage-specific equivalence.
"""
from __future__ import annotations

import hashlib
import json
import os
import statistics
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "psc_composition_performance"
OUT.mkdir(parents=True, exist_ok=True)

SEEDS = (17, 23, 41, 59, 83)
PRIMARY = 17


def _write(name: str, obj: Any) -> None:
    path = OUT / name
    path.write_text(
        obj if isinstance(obj, str) else json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n"
    )
    print("wrote", path, flush=True)


def _pct(xs: list[float], p: float) -> float | None:
    if not xs:
        return None
    s = sorted(xs)
    k = (len(s) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return float(s[f])
    return float(s[f] + (s[c] - s[f]) * (k - f))


def _stats(xs: list[float]) -> dict[str, Any]:
    if not xs:
        return {"n": 0}
    return {
        "n": len(xs),
        "mean": float(statistics.mean(xs)),
        "median": float(statistics.median(xs)),
        "p95": _pct(xs, 95),
        "min": float(min(xs)),
        "max": float(max(xs)),
    }


def make_session(*, seed: int = PRIMARY, place_adjacent: bool = False, mode: str = "HEADLESS"):
    from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig, new_run_id

    s = ObserverSession(
        SessionConfig(
            seed=seed,
            cognition_enabled=True,
            execution_mode=mode,
            ui_hz=1.0 if mode == "HEADLESS" else 5.0,
            buffer_capacity=128,
        )
    )
    s.apply_experiment(
        {
            "seed": seed,
            "agent_count": 2,
            "vision_radius": 3,
            "cognition_enabled": True,
            "mechanisms": {
                "physical_near_field_vision": True,
                "spatiotemporal_climate_ecology": False,
            },
        }
    )
    s.set_execution_mode(mode)
    s.set_vision_radius(3)
    if place_adjacent and getattr(s.runtime, "slots", None):
        s.runtime.slots[0].body.x = 16.0
        s.runtime.slots[0].body.y = 16.0
        s.runtime.slots[0].body.vx = 0.0
        s.runtime.slots[0].body.vy = 0.0
        s.runtime.slots[1].body.x = 17.5
        s.runtime.slots[1].body.y = 16.0
        s.runtime.slots[1].body.vx = 0.0
        s.runtime.slots[1].body.vy = 0.0
    s._run_started_at = datetime.now(timezone.utc).isoformat()
    s._active_run_id = new_run_id()
    with s._step_lock:
        with s._lock:
            s._ensure_scientific_locked()
    return s


def dump_eff(s) -> dict[str, Any]:
    from experiments.run_live_optical_performance import dump_effective_configuration

    return dump_effective_configuration(s)


def sci_step(s) -> None:
    s._scientific_step_once_unlocked()
    with s._lock:
        s._accumulate_events_locked()
        s._record_motion_locked()
        s._append_scientific_locked()
        s._update_perf_locked(tick=True)


def store_occ(s) -> dict[str, Any]:
    out = []
    for i, slot in enumerate(s.runtime.slots):
        tr = (slot.cognition.get("prospection") or {}).get("transitions") or {}
        out.append({"slot": i, "n_transitions": len(tr), "capacity": 128, "frac": len(tr) / 128.0})
    return {"agents": out, "max_frac": max(a["frac"] for a in out) if out else 0.0}


class StageAcc:
    def __init__(self) -> None:
        self.totals: dict[str, float] = defaultdict(float)
        self.counts: dict[str, int] = defaultdict(int)
        self.tick_wall: list[float] = []
        # equivalence / call keys per tick
        self.tick_keys: dict[str, list[list[str]]] = defaultdict(list)
        self.rows_scanned: list[int] = []
        self.soft_exact_hit = 0
        self.soft_scan = 0
        self.sig_req = 0
        self.sig_hit = 0
        self._active_tick_keys: dict[str, list[str]] = defaultdict(list)
        self._in_tick = False

    def begin_tick(self) -> None:
        self._active_tick_keys = defaultdict(list)
        self._in_tick = True

    def end_tick(self, wall_s: float) -> None:
        self._in_tick = False
        self.tick_wall.append(wall_s)
        for name, keys in self._active_tick_keys.items():
            self.tick_keys[name].append(list(keys))

    def add(self, name: str, dt: float) -> None:
        self.totals[name] += dt
        self.counts[name] += 1

    def note_key(self, stage: str, key: str) -> None:
        if self._in_tick:
            self._active_tick_keys[stage].append(key)

    def summary(self) -> dict[str, Any]:
        wall = sum(self.totals.values()) or 1e-12
        stages = []
        for name, tot in sorted(self.totals.items(), key=lambda kv: -kv[1]):
            n = max(1, self.counts[name])
            stages.append(
                {
                    "stage": name,
                    "total_s": tot,
                    "calls": self.counts[name],
                    "mean_ms": 1000.0 * tot / n,
                    "pct_of_staged": 100.0 * tot / wall,
                }
            )
        tw = self.tick_wall
        mean = statistics.mean(tw) if tw else 0.0
        return {
            "stages": stages,
            "tick_ms": {
                "n": len(tw),
                "mean": mean * 1000 if tw else None,
                "tps": (len(tw) / sum(tw)) if tw and sum(tw) > 0 else None,
            },
            "soft_exact_hit": self.soft_exact_hit,
            "soft_scan": self.soft_scan,
            "sig_req": self.sig_req,
            "sig_hit": self.sig_hit,
        }


def install_instruments(acc: StageAcc) -> Callable[[], None]:
    import mechanistic_mind.physical_system.cognition as cog_mod
    import mechanistic_mind.research.prospective_composition as pr
    import mechanistic_mind.research.predictive_compression as pc
    import mechanistic_mind.research.psc_opt as psc

    restores: list[Callable[[], None]] = []

    # --- cognition ---
    orig_cog = cog_mod.run_cognition_before_action

    def wrap_cog(*a, **k):
        t0 = time.perf_counter()
        out = orig_cog(*a, **k)
        acc.add("cognition.run_before_action", time.perf_counter() - t0)
        return out

    cog_mod.run_cognition_before_action = wrap_cog
    restores.append(lambda: setattr(cog_mod, "run_cognition_before_action", orig_cog))

    # --- compose ---
    orig_compose = pr.compose_trajectories

    def wrap_compose(*a, **k):
        t0 = time.perf_counter()
        out = orig_compose(*a, **k)
        acc.add("compose_trajectories", time.perf_counter() - t0)
        # composition semantic key: quantized start + branch_actions tuple + depth
        start = k.get("start") if "start" in k else (a[1] if len(a) > 1 else None)
        if isinstance(start, dict):
            ant = pr._q(start)
            ba = tuple(k.get("branch_actions") or [])
            depth = int(k.get("max_depth") or 3)
            key = f"{pr._sig(ant)}||ba={ba}||d={depth}"
            acc.note_key("composition", key)
        return out

    pr.compose_trajectories = wrap_compose
    restores.append(lambda: setattr(pr, "compose_trajectories", orig_compose))

    # --- predict_one_step ---
    orig_pos = pr.predict_one_step

    def wrap_pos(store, antecedent, action, *, backend=None, _ant_q=None):
        ant = _ant_q if _ant_q is not None else pr._q(antecedent)
        sem = f"{pr._sig(ant)}||{action}"
        acc.note_key("predict_one_step", sem)
        transitions = store.get("transitions") or {}
        exact = transitions.get(sem)
        t0 = time.perf_counter()
        if exact and int(exact.get("support") or 0) >= pr.MIN_SUPPORT:
            acc.soft_exact_hit += 1
            out = orig_pos(store, antecedent, action, backend=backend, _ant_q=ant)
            acc.add("predict_one_step.exact", time.perf_counter() - t0)
            return out
        acc.soft_scan += 1
        out = orig_pos(store, antecedent, action, backend=backend, _ant_q=ant)
        acc.add("predict_one_step.soft_path", time.perf_counter() - t0)
        return out

    pr.predict_one_step = wrap_pos
    restores.append(lambda: setattr(pr, "predict_one_step", orig_pos))

    # --- soft_match packed/legacy ---
    orig_packed = psc.soft_match_packed
    orig_legacy = psc.soft_match_legacy

    def wrap_packed(pack, ant, action):
        rows = (pack.get("by_action") or {}).get(action) or []
        acc.rows_scanned.append(len(rows))
        acc.note_key("soft_match", f"{pr._sig(ant)}||{action}")
        t0 = time.perf_counter()
        out = orig_packed(pack, ant, action)
        acc.add("soft_match", time.perf_counter() - t0)
        return out

    def wrap_legacy(transitions, ant, action):
        n = sum(1 for r in transitions.values() if r.get("action") == action)
        acc.rows_scanned.append(n)
        acc.note_key("soft_match", f"{pr._sig(ant)}||{action}")
        t0 = time.perf_counter()
        out = orig_legacy(transitions, ant, action)
        acc.add("soft_match", time.perf_counter() - t0)
        return out

    psc.soft_match_packed = wrap_packed
    psc.soft_match_legacy = wrap_legacy
    restores.append(lambda: setattr(psc, "soft_match_packed", orig_packed))
    restores.append(lambda: setattr(psc, "soft_match_legacy", orig_legacy))

    # --- _sig ---
    orig_sig = pr._sig
    cache = pr._SIG_CACHE

    def wrap_sig(payload):
        acc.sig_req += 1
        items = tuple(
            sorted(
                (
                    str(k),
                    round(float(v), 4)
                    if isinstance(v, (int, float)) and not isinstance(v, bool)
                    else str(v),
                )
                for k, v in payload.items()
            )
        )
        if items in cache:
            acc.sig_hit += 1
        t0 = time.perf_counter()
        out = orig_sig(payload)
        acc.add("_sig", time.perf_counter() - t0)
        return out

    pr._sig = wrap_sig
    restores.append(lambda: setattr(pr, "_sig", orig_sig))

    # --- compression predict ---
    orig_pc = pc.predict

    def wrap_pc(mem, fragment, action, domain="accessible"):
        # prediction semantic key: quantized fragment + action + domain
        from mechanistic_mind.research.prospective_composition import _q, _sig

        qf = _q(fragment) if isinstance(fragment, dict) else {}
        sem = f"{_sig(qf)}||{action}||{domain}"
        acc.note_key("pc.predict", sem)
        t0 = time.perf_counter()
        out = orig_pc(mem, fragment, action, domain=domain)
        acc.add("pc.predict", time.perf_counter() - t0)
        return out

    pc.predict = wrap_pc
    restores.append(lambda: setattr(pc, "predict", orig_pc))

    def restore_all() -> None:
        for r in restores:
            r()

    return restore_all


def equiv_from_keys(tick_key_lists: list[list[str]]) -> dict[str, Any]:
    raw_n = []
    uniq_n = []
    dup_frac = []
    class_sizes_all: list[int] = []
    for keys in tick_key_lists:
        n = len(keys)
        c = Counter(keys)
        u = len(c)
        raw_n.append(n)
        uniq_n.append(u)
        dup_frac.append(0.0 if n == 0 else 1.0 - (u / n))
        class_sizes_all.extend(c.values())
    return {
        "raw_calls_per_tick": _stats([float(x) for x in raw_n]),
        "unique_keys_per_tick": _stats([float(x) for x in uniq_n]),
        "duplicate_fraction_per_tick": _stats(dup_frac),
        "class_size_distribution": _stats([float(x) for x in class_sizes_all]),
        "example_top_keys_last_tick": Counter(tick_key_lists[-1]).most_common(8) if tick_key_lists else [],
    }


def domain_of(action: str) -> str:
    if action == "WAIT" or action.startswith("MOVE:"):
        return "locomotion"
    if action.startswith("NECK_"):
        return "neck"
    if action.startswith("OSC_"):
        return "oscillator"
    if action == "PUSH":
        return "push"
    return "other"


def action_inventory(s) -> dict[str, Any]:
    from mechanistic_mind.physical_system.actions import available_actions
    from mechanistic_mind.physical_system.composite_motor import locomotion_options
    from mechanistic_mind.research.prospective_composition import _q, _sig

    slot = s.runtime.slots[0]
    acts = list(slot.cognition.get("available_actions") or available_actions())
    # force one step so last observation exists
    obs = slot.last_agent_observation or {}
    q = _q(obs) if isinstance(obs, dict) else {}
    sig = _sig(q) if q else ""
    rows = []
    for a in acts:
        rows.append(
            {
                "action": a,
                "domain": domain_of(a),
                "prediction_key": f"{sig}||{a}||accessible",
                "soft_match_key": f"{sig}||{a}",
                "composition_seed_key": f"{sig}||{a}",
                "note": "Keys use current observation quantized representation; action is part of soft_match/exact key",
            }
        )
    loco = locomotion_options(acts)
    return {
        "n_actions": len(acts),
        "actions": acts,
        "locomotion_subset": loco,
        "n_locomotion": len(loco),
        "by_domain": {d: [r["action"] for r in rows if r["domain"] == d] for d in sorted({r["domain"] for r in rows})},
        "rows": rows,
        "observation_sig": sig,
        "composite_selects_on_locomotion_only": True,
        "compose_branch_actions_uses_full_repertoire": True,
    }


def run_window(
    *,
    seed: int,
    warm: int,
    measure: int,
    place_adjacent: bool = False,
    label: str = "window",
) -> dict[str, Any]:
    s = make_session(seed=seed, place_adjacent=place_adjacent)
    with s._step_lock:
        for _ in range(warm):
            sci_step(s)
        occ_before = store_occ(s)
        acc = StageAcc()
        restore = install_instruments(acc)
        try:
            for _ in range(measure):
                acc.begin_tick()
                t0 = time.perf_counter()
                sci_step(s)
                acc.end_tick(time.perf_counter() - t0)
        finally:
            restore()
        occ_after = store_occ(s)

    summ = acc.summary()
    n_ticks = max(1, measure)
    # wall estimates for duplicate work
    eq = {
        "predict_one_step": equiv_from_keys(acc.tick_keys.get("predict_one_step", [])),
        "soft_match": equiv_from_keys(acc.tick_keys.get("soft_match", [])),
        "composition": equiv_from_keys(acc.tick_keys.get("composition", [])),
        "pc.predict": equiv_from_keys(acc.tick_keys.get("pc.predict", [])),
    }

    def stage_ms(name: str) -> float:
        st = next((x for x in summ["stages"] if x["stage"] == name), None)
        if not st:
            return 0.0
        return 1000.0 * st["total_s"] / n_ticks

    soft_ms = stage_ms("soft_match") + stage_ms("predict_one_step.soft_path")
    pos_exact = stage_ms("predict_one_step.exact")
    compose_ms = stage_ms("compose_trajectories")
    cog_ms = stage_ms("cognition.run_before_action")
    sig_ms = stage_ms("_sig")
    pc_ms = stage_ms("pc.predict")

    # duplicate wall estimate: duplicate_frac * stage_ms
    def dup_wall(stage_eq: dict, stage_ms_val: float) -> float:
        df = (stage_eq.get("duplicate_fraction_per_tick") or {}).get("mean") or 0.0
        return float(df) * stage_ms_val

    rows_per_call = statistics.mean(acc.rows_scanned) if acc.rows_scanned else 0.0

    return {
        "label": label,
        "seed": seed,
        "warm": warm,
        "measure": measure,
        "place_adjacent": place_adjacent,
        "occupancy_before": occ_before,
        "occupancy_after": occ_after,
        "tps": summ["tick_ms"].get("tps"),
        "ms_tick": summ["tick_ms"].get("mean"),
        "stages": summ["stages"][:20],
        "per_tick_ms": {
            "cognition": cog_ms,
            "compose": compose_ms,
            "soft_match_incl_soft_path": soft_ms,
            "predict_exact": pos_exact,
            "pc.predict": pc_ms,
            "_sig": sig_ms,
        },
        "calls": {
            "predict_one_step_exact": acc.soft_exact_hit,
            "predict_one_step_soft_path": acc.soft_scan,
            "soft_match": acc.counts.get("soft_match", 0),
            "compose": acc.counts.get("compose_trajectories", 0),
            "pc.predict": acc.counts.get("pc.predict", 0),
            "sig_req": acc.sig_req,
            "sig_hit": acc.sig_hit,
            "sig_hit_rate": (acc.sig_hit / acc.sig_req) if acc.sig_req else None,
            "per_tick": {
                "predict_one_step": (acc.soft_exact_hit + acc.soft_scan) / n_ticks,
                "soft_match": acc.counts.get("soft_match", 0) / n_ticks,
                "compose": acc.counts.get("compose_trajectories", 0) / n_ticks,
                "pc.predict": acc.counts.get("pc.predict", 0) / n_ticks,
                "rows_scanned_mean_per_soft_match": rows_per_call,
                "transition_comparisons_est": rows_per_call * (acc.counts.get("soft_match", 0) / n_ticks),
            },
        },
        "equivalence": eq,
        "duplicate_wall_ms_est": {
            "predict_one_step": dup_wall(eq["predict_one_step"], soft_ms + pos_exact),
            "soft_match": dup_wall(eq["soft_match"], soft_ms),
            "composition": dup_wall(eq["composition"], compose_ms),
            "pc.predict": dup_wall(eq["pc.predict"], pc_ms),
        },
    }


def fingerprint_run(*, seed: int, ticks: int, place: bool = False) -> str:
    s = make_session(seed=seed, place_adjacent=place)
    rows = []
    with s._step_lock:
        for _ in range(ticks):
            sci_step(s)
            for i, slot in enumerate(s.runtime.slots):
                b = slot.body
                prosp = (slot.cognition.get("prospection") or {}).get("transitions") or {}
                rows.append(
                    [
                        int(s.runtime.tick),
                        i,
                        slot.last_selected_action,
                        round(float(b.x), 6),
                        round(float(b.y), 6),
                        round(float(b.theta), 6),
                        round(float(b.vx), 6),
                        round(float(b.vy), 6),
                        len(prosp),
                        (slot.cognition.get("metrics") or {}).get("prediction_count"),
                    ]
                )
    return hashlib.sha1(json.dumps(rows, separators=(",", ":")).encode()).hexdigest()


def main() -> int:
    os.environ.pop("MM_PSC_BACKEND", None)
    print("=== PSC composition performance Phase A ===", flush=True)
    s0 = make_session(seed=PRIMARY)
    eff = dump_eff(s0)
    _write("effective_configuration.json", eff)
    if not (eff.get("all_required_on") and eff.get("climate_off")):
        print("CONFIG FAIL", eff)
        return 1

    inv = action_inventory(s0)
    _write("action_inventory.json", inv)

    # Semantic dependency definition (from code, not assumptions)
    deps = {
        "predict_one_step": {
            "inputs": ["quantized_antecedent (_q)", "action string", "transition store", "MIN_SUPPORT", "MATCH_TOL"],
            "exact_key": "_sig(_q(antecedent))||action",
            "soft_match_filter": "action equality on transition rows",
            "rng": False,
            "side_effects": "none (read-only); mean/reliability row caches are pure memo",
            "classification": "PURE_DETERMINISTIC",
        },
        "soft_match": {
            "inputs": ["quantized_antecedent", "action", "action-indexed transition rows"],
            "key": "_sig(ant)||action",
            "rng": False,
            "side_effects": False,
            "classification": "PURE_DETERMINISTIC",
        },
        "compose_trajectories": {
            "inputs": ["start observation", "branch_actions list (ordered)", "max_depth", "entry_steps", "store"],
            "key": "_sig(_q(start))||tuple(branch_actions)||max_depth||entry_steps_identity",
            "rng": False,
            "side_effects": "none on store (read-only composition)",
            "classification": "PURE_DETERMINISTIC",
            "note": "Currently called once per agent cognition cycle with FULL action repertoire",
        },
        "pc.predict": {
            "inputs": ["fragment", "action", "domain", "compression memory"],
            "key": "compression lookup keyed by fragment/action",
            "rng": False,
            "classification": "PURE_DETERMINISTIC",
        },
    }
    _write("semantic_dependencies.json", deps)
    _write(
        "equivalence_definition.json",
        {
            "PREDICTION_EQUIVALENCE": "same quantized observation + same action + same domain → identical pc.predict / predict_one_step exact key",
            "SOFT_MATCH_EQUIVALENCE": "same quantized antecedent + same action string → identical soft_match scan set and distances",
            "COMPOSITION_EQUIVALENCE": "same quantized start + identical ordered branch_actions + same max_depth + same entry_steps → identical compose_trajectories",
            "NOT_equivalence": [
                "same motor domain alone",
                "locomotion-only assumption",
                "action name similarity",
            ],
            "implication": (
                "Because soft_match and exact keys INCLUDE the action string, "
                "distinct actions are NEVER soft_match/prediction equivalent to each other "
                "even when they share the same observation. Within-tick reuse can only help "
                "when the SAME (antecedent_q, action) pair is evaluated more than once "
                "(e.g. BFS revisiting a quantized state)."
            ),
        },
    )

    print("=== early / mid / filled / plateau ===", flush=True)
    early = run_window(seed=PRIMARY, warm=5, measure=40, label="early")
    mid = run_window(seed=PRIMARY, warm=80, measure=40, label="mid")
    filled = run_window(seed=PRIMARY, warm=220, measure=60, label="filled")
    plateau = run_window(seed=PRIMARY, warm=400, measure=80, label="plateau")
    filled_adj = run_window(seed=PRIMARY, warm=220, measure=60, place_adjacent=True, label="filled_adjacent")

    _write("early_benchmark.json", early)
    _write("mid_store_benchmark.json", mid)
    _write("filled_store_benchmark.json", filled)
    _write("long_plateau_benchmark.json", plateau)
    _write("baseline_hotpath.json", {"filled": filled, "plateau": plateau, "early": early})

    _write(
        "call_graph.json",
        {
            "per_agent_cognition_cycle": {
                "pc.predict": "× n_actions (full repertoire)",
                "compose_trajectories": "× 1 (branch_actions = full repertoire)",
                "predict_one_step_inside_compose": "≤ MAX_EXPANSIONS (64), typically roots n_actions + BFS expansions",
                "soft_match": "once per predict_one_step miss on exact key",
            },
            "measured_filled_per_tick": filled["calls"]["per_tick"],
            "n_agents": 2,
            "note": "Totals are for whole session step (2 agents)",
        },
    )
    _write("equivalence_classes.json", {
        "early": early["equivalence"],
        "mid": mid["equivalence"],
        "filled": filled["equivalence"],
        "plateau": plateau["equivalence"],
    })
    _write("duplicate_work.json", {
        "early": early["duplicate_wall_ms_est"],
        "mid": mid["duplicate_wall_ms_est"],
        "filled": filled["duplicate_wall_ms_est"],
        "plateau": plateau["duplicate_wall_ms_est"],
        "interpretation": (
            "duplicate_fraction for soft_match/predict across DISTINCT actions is expected near 0 "
            "because action is in the semantic key. Non-zero duplicate_fraction indicates "
            "same (antecedent_q, action) recomputed within the tick (BFS revisit)."
        ),
    })
    _write(
        "store_occupancy_scaling.json",
        {
            "early": {"occ": early["occupancy_after"], "tps": early["tps"], "ms": early["ms_tick"], "dup": early["duplicate_wall_ms_est"]},
            "mid": {"occ": mid["occupancy_after"], "tps": mid["tps"], "ms": mid["ms_tick"], "dup": mid["duplicate_wall_ms_est"]},
            "filled": {"occ": filled["occupancy_after"], "tps": filled["tps"], "ms": filled["ms_tick"], "dup": filled["duplicate_wall_ms_est"]},
            "plateau": {"occ": plateau["occupancy_after"], "tps": plateau["tps"], "ms": plateau["ms_tick"], "dup": plateau["duplicate_wall_ms_est"]},
        },
    )
    _write("soft_match_profile.json", {
        "filled": {
            "calls_per_tick": filled["calls"]["per_tick"]["soft_match"],
            "rows_per_call": filled["calls"]["per_tick"]["rows_scanned_mean_per_soft_match"],
            "comparisons_per_tick": filled["calls"]["per_tick"]["transition_comparisons_est"],
            "ms_per_tick": filled["per_tick_ms"]["soft_match_incl_soft_path"],
            "complexity": "O(soft_match_calls × rows_for_action) with packed by_action index; actions distinct",
        }
    })
    _write("compose_profile.json", {
        "filled": {
            "calls_per_tick": filled["calls"]["per_tick"]["compose"],
            "ms_per_tick": filled["per_tick_ms"]["compose"],
            "unique_composition_keys": filled["equivalence"]["composition"]["unique_keys_per_tick"],
            "note": "One compose per agent; unique keys ≈ n_agents unless identical observations",
        }
    })
    _write("sig_profile.json", {
        "filled": {
            "req": filled["calls"]["sig_req"],
            "hit": filled["calls"]["sig_hit"],
            "hit_rate": filled["calls"]["sig_hit_rate"],
            "ms_per_tick": filled["per_tick_ms"]["_sig"],
        }
    })
    _write("allocation_profile.json", {"note": "Not separately traced; soft_match/_frag_distance dominate over alloc in prior cProfile"})
    _write("serialization_profile.json", {"note": "Cognition hotpath: no json.dumps in PSC; Observer memory_cost already cached"})

    # Loco-only hypothesis test (measurement only)
    loco_hyp = {
        "hypothesis": "non-locomotion actions are not distinct at composition input",
        "measured": {
            "soft_match_includes_action": True,
            "distinct_actions_are_distinct_soft_match_keys": True,
            "n_actions": inv["n_actions"],
            "n_locomotion": inv["n_locomotion"],
            "filled_unique_soft_match_keys_mean": (filled["equivalence"]["soft_match"]["unique_keys_per_tick"] or {}).get("mean"),
            "filled_raw_soft_match_calls_mean": (filled["equivalence"]["soft_match"]["raw_calls_per_tick"] or {}).get("mean"),
        },
        "verdict": "HYPOTHESIS_REJECTED — non-locomotion candidates are genuinely distinct for soft_match/prediction because action is part of the semantic key",
        "compose_once_per_agent": True,
        "fourteen_action_compose_diagnosis": (
            "PARTIALLY_CORRECT: compose is invoked once per agent with branch_actions=full repertoire; "
            "cost is multiplied by action count INSIDE compose via predict_one_step seeds/expansions, "
            "not by 14 separate compose_trajectories calls. Those per-action seeds are semantically distinct."
        ),
    }
    _write("optimization_candidates.json", {
        "loco_only_hypothesis": loco_hyp,
        "candidates": [
            {
                "id": "tick_cache_predict_one_step",
                "why": "Same (ant_q, action) may be recomputed during BFS if duplicate fraction > 0",
                "safe_if": "PURE_DETERMINISTIC and result immutable; preserve call-site order",
                "priority": "depends on measured duplicate_wall_ms_est",
            },
            {
                "id": "do_not_loco_only_compose",
                "why": "Would change scientific fingerprints; non-loco actions are distinct",
                "priority": "REJECT",
            },
            {
                "id": "soft_match_prefilter",
                "why": "Only if necessary-condition exists without false rejects",
                "priority": "evaluate after duplicate analysis",
            },
        ],
    })

    print(json.dumps({
        "early_tps": early["tps"],
        "mid_tps": mid["tps"],
        "filled_tps": filled["tps"],
        "plateau_tps": plateau["tps"],
        "filled_dup": filled["duplicate_wall_ms_est"],
        "filled_unique_sm": filled["equivalence"]["soft_match"]["unique_keys_per_tick"],
        "filled_raw_sm": filled["equivalence"]["soft_match"]["raw_calls_per_tick"],
        "sig_hit_rate": filled["calls"]["sig_hit_rate"],
        "loco_hyp": loco_hyp["verdict"],
    }, indent=2), flush=True)

    # Decide Phase B from measurements
    filled_dup_sm = (filled["duplicate_wall_ms_est"] or {}).get("soft_match") or 0.0
    filled_dup_pos = (filled["duplicate_wall_ms_est"] or {}).get("predict_one_step") or 0.0
    rem = filled_dup_sm + filled_dup_pos
    print(f"estimated removable duplicate wall ms/tick (soft+pos): {rem:.3f}", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
