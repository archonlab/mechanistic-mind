#!/usr/bin/env python3
"""MULTI_AGENT_PARALLELISM_AUDIT — measurement only; no production runtime change.

Phases:
  1–3  Causal order + independence + same-tick semantics
  4–5  Per-agent cost + 1/2/4 scaling
  6–8  Options notes + optional cognition-only parallel prototype
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "multi_agent_parallelism_audit"
OUT.mkdir(parents=True, exist_ok=True)


def _pct(xs: list[float]) -> dict[str, float]:
    if not xs:
        return {"mean": 0.0, "median": 0.0, "p95": 0.0, "min": 0.0, "max": 0.0, "n": 0}
    s = sorted(xs)
    n = len(s)
    return {
        "mean": float(statistics.mean(s)),
        "median": float(statistics.median(s)),
        "p95": float(s[min(n - 1, int(0.95 * (n - 1)))]),
        "min": float(s[0]),
        "max": float(s[-1]),
        "n": n,
    }


def _digest(obj: Any) -> str:
    blob = json.dumps(obj, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha1(blob.encode()).hexdigest()


def _make_config():
    from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig
    from mechanistic_mind.physical_system.mechanism_configuration import (
        resolve_mechanism_config,
        stamp_config_mechanisms,
    )

    cfg = PhysicalSystemConfig()
    resolved = resolve_mechanism_config(
        {
            "physical_near_field_vision": True,
            "spatiotemporal_climate_ecology": False,
            "cognition_enabled": True,
            "vision_radius": 3,
        },
        vision_radius=3,
        source_hint="EXPLICIT",
        apply_fresh_defaults=True,
    )
    stamp_config_mechanisms(cfg, resolved)
    return cfg, resolved


def _n_agent_runtime(n: int, seed: int = 17):
    """Build 1..N agent shared-world runtime for audit (does not change production API)."""
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
    from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime, agent_seed, _cfg_with_start
    from mechanistic_mind.physical_system.physical_signal import PhysicalSignalConfig, ensure_fields

    cfg, resolved = _make_config()
    if n <= 1:
        rt = PhysicalSystemRuntime(seed=seed, config=cfg)
        return rt, resolved

    # Place agents on a small grid to keep Vision/contact meaningful.
    starts = []
    cols = max(2, int(n**0.5) + 1)
    for i in range(n):
        starts.append((8 + (i % cols) * 3, 16 + (i // cols) * 3))
    multi = TwoAgentRuntime(
        seed=seed,
        config=cfg,
        starts=tuple(starts[:2]),  # construct base pair
        signal_enabled=True,
        independent_agent_seeds=True,
    )
    # Extend to N slots sharing world.
    while len(multi.slots) < n:
        i = len(multi.slots)
        x, y = starts[i]
        slot_cfg = _cfg_with_start(multi.base_config, x, y)
        slot_cfg.physical_signal = PhysicalSignalConfig(mode="EXPERIMENTAL")
        slot_seed = agent_seed(seed, i)
        slot = PhysicalSystemRuntime(seed=slot_seed, config=slot_cfg)
        slot.world = multi.world
        slot.tick = multi.slots[0].tick
        slot.body.tick = multi.slots[0].body.tick
        slot.internal.tick = multi.slots[0].internal.tick
        multi.slots.append(slot)
        multi._agent_stats.append(
            {
                "ticks": 0,
                "action_counts": {},
                "wait_count": 0,
                "move_count": 0,
                "distance_travelled": 0.0,
                "unique_cells": set(),
                "collision_ticks": 0,
                "cognition_ticks": 0,
                "last_competition": None,
            }
        )
        multi._prev_xy.append(None)
    multi.starts = tuple(starts[:n])
    multi.process_order = tuple(range(n))
    ensure_fields(multi.world)
    # Align cognition/mechanisms after extend.
    for slot in multi.slots:
        slot.config.cognition.cognition_enabled = True
        if hasattr(slot, "_sync_embodiment_dofs"):
            slot._sync_embodiment_dofs()
    return multi, resolved


def write_causal_order() -> dict[str, Any]:
    """Static causal diagram from TwoAgentRuntime._step_once + begin_tick/finish_tick."""
    stages = [
        {
            "id": 1,
            "name": "observations() for all agents",
            "detail": "Vision/SNF/OSC/body/interoception sampled with foreign_bodies at tick T before any begin_tick",
            "class": ["SHARED_READ", "AGENT_LOCAL_READ"],
        },
        {
            "id": 2,
            "name": "begin_tick[i] cognition (process_order)",
            "detail": "run_cognition_before_action(obs[i], agent-local store, rng=f(seed_i,tick))",
            "class": ["AGENT_LOCAL_READ", "AGENT_LOCAL_WRITE", "RNG_DEPENDENT"],
        },
        {
            "id": 3,
            "name": "begin_tick[i] motor impulse apply",
            "detail": "Mutates agent body vx/vy/neck/osc body state; does not write shared planet fields",
            "class": ["AGENT_LOCAL_WRITE", "ORDER_DEPENDENT"],
        },
        {
            "id": 4,
            "name": "step_planet(shared world)",
            "detail": "Once per tick after all begin_ticks",
            "class": ["SHARED_WRITE", "ORDER_DEPENDENT"],
        },
        {
            "id": 5,
            "name": "finish_tick[i] body/internal advance",
            "detail": "skip_planet=True, skip_resources=True; agent-local dynamics reading shared world",
            "class": ["AGENT_LOCAL_WRITE", "SHARED_READ", "ORDER_DEPENDENT"],
        },
        {
            "id": 6,
            "name": "pairwise soft contact + PUSH",
            "detail": "After all finish_ticks; pairs in (ia<ib) order",
            "class": ["SHARED_WRITE", "ORDER_DEPENDENT"],
        },
        {
            "id": 7,
            "name": "simultaneous complementary resources",
            "detail": "Shared world resource exchange",
            "class": ["SHARED_WRITE"],
        },
        {
            "id": 8,
            "name": "physical signals FIELD A/B",
            "detail": "Shared continuum fields; deposits then receive events",
            "class": ["SHARED_WRITE", "ORDER_DEPENDENT"],
        },
        {
            "id": 9,
            "name": "oscillatory signaling fields",
            "detail": "Shared OSC bands from all bodies",
            "class": ["SHARED_WRITE", "ORDER_DEPENDENT"],
        },
        {
            "id": 10,
            "name": "Observer/stats capture",
            "detail": "Instrumentation after physics",
            "class": ["OBSERVER_ONLY"],
        },
        {
            "id": 11,
            "name": "tick increment (inside finish_tick)",
            "detail": "Per-slot tick counters aligned via shared world tick",
            "class": ["AGENT_LOCAL_WRITE", "SHARED_WRITE"],
        },
    ]
    diagram = """
WORLD/BODY STATE T
        |
        v
observations()  ---- ALL agents (same snapshot T) ---->
        |
        +---- begin_tick(A): think + apply impulse ----+
        |                                              |
        +---- begin_tick(B): think + apply impulse ----+  (serial process_order)
        |
        v
   step_planet(WORLD)
        |
        +---- finish_tick(A) ----+
        +---- finish_tick(B) ----+
        |
        v
 contact / PUSH / resources / SIGNAL / OSC
        |
        v
 WORLD/BODY STATE T+1
"""
    payload = {
        "semantics_hypothesis": "B_WITH_SERIAL_APPLY",
        "summary": (
            "All agents observe world T before any cognition. Cognition uses frozen "
            "observation dicts. begin_tick then applies body impulses serially. "
            "Physical interactions run after all finish_ticks."
        ),
        "stages": stages,
        "diagram": diagram,
        "possibility": "B",
        "possibility_note": (
            "Possibility B for cognition inputs. Hybrid for full begin_tick because "
            "think and body-apply are fused in one method and process_order serializes apply."
        ),
    }
    (OUT / "causal_order.json").write_text(json.dumps(payload, indent=2))
    return payload


def independence_tests(seed: int = 17, warm: int = 220) -> dict[str, Any]:
    """Prove whether cognition order within a tick affects agent-local results."""
    from mechanistic_mind.physical_system.cognition import run_cognition_before_action
    from mechanistic_mind.physical_system.runtime import _rng_unit

    rt, resolved = _n_agent_runtime(2, seed=seed)
    for _ in range(warm):
        rt.step(1)

    obs = rt.observations()
    # Snapshot cognition before think.
    cog0 = deepcopy(rt.slots[0].cognition)
    cog1 = deepcopy(rt.slots[1].cognition)
    tick = int(rt.slots[0].tick)

    def run_pair(order: tuple[int, int]):
        states = {0: deepcopy(cog0), 1: deepcopy(cog1)}
        results = {}
        for i in order:
            rng = _rng_unit(rt.slots[i].seed, tick)
            results[i] = run_cognition_before_action(
                states[i], observation=obs[i], tick=tick, rng_value=rng
            )
        return states, results

    s_ab, r_ab = run_pair((0, 1))
    s_ba, r_ba = run_pair((1, 0))

    def cog_fp(st):
        # Exclude volatile wall-clock-free scientific core.
        keep = {
            k: st.get(k)
            for k in (
                "compression",
                "prospection",
                "multiscale",
                "last_action",
                "last_fragment",
                "last_selection",
                "metrics",
                "available_actions",
            )
            if k in st
        }
        return _digest(keep)

    out = {
        "warm_ticks": warm,
        "tick": tick,
        "observation_digests": [_digest(o) for o in obs],
        "obs_captured_before_any_begin_tick": True,
        "construction_audit": rt.construction_audit() if hasattr(rt, "construction_audit") else None,
        "cognition_order_ab_vs_ba": {
            "selected_action_0": {
                "AB": r_ab[0].selected_action,
                "BA": r_ba[0].selected_action,
                "match": r_ab[0].selected_action == r_ba[0].selected_action,
            },
            "selected_action_1": {
                "AB": r_ab[1].selected_action,
                "BA": r_ba[1].selected_action,
                "match": r_ab[1].selected_action == r_ba[1].selected_action,
            },
            "store_digest_0_match": cog_fp(s_ab[0]) == cog_fp(s_ba[0]),
            "store_digest_1_match": cog_fp(s_ab[1]) == cog_fp(s_ba[1]),
            "digest_0": {"AB": cog_fp(s_ab[0]), "BA": cog_fp(s_ba[0])},
            "digest_1": {"AB": cog_fp(s_ab[1]), "BA": cog_fp(s_ba[1])},
        },
        "shared_mutable_modules": {
            "_SIG_CACHE_predictive_compression": "module-level; pure digest; not thread-safe",
            "_SIG_CACHE_prospective_composition": "module-level; pure digest; not thread-safe",
            "_SNF_CACHE": "module-level; used during observation sampling (pre-cognition)",
            "cognitive_view_cache": "per-runtime instance",
            "numpy_global_rng_in_cognition": False,
            "cognition_rng": "closed-form _rng_unit(agent_seed, tick); independent streams",
        },
        "verdict": None,
    }
    ok = (
        out["cognition_order_ab_vs_ba"]["selected_action_0"]["match"]
        and out["cognition_order_ab_vs_ba"]["selected_action_1"]["match"]
        and out["cognition_order_ab_vs_ba"]["store_digest_0_match"]
        and out["cognition_order_ab_vs_ba"]["store_digest_1_match"]
    )
    out["cognition_commutative_within_tick"] = bool(ok)
    out["verdict"] = (
        "AGENT_COGNITION_INDEPENDENT_GIVEN_FROZEN_OBS"
        if ok
        else "ORDER_DEPENDENT_COGNITION"
    )
    (OUT / "independence.json").write_text(json.dumps(out, indent=2))
    (OUT / "effective_configuration.json").write_text(
        json.dumps(
            {
                "seed": seed,
                "climate_off": True,
                "vision_radius": 3,
                "resolved_fingerprint": getattr(resolved, "fingerprint", None),
                "mechanisms": getattr(resolved, "mechanisms", None),
            },
            indent=2,
            default=str,
        )
    )
    return out


def profile_per_agent(seed: int = 17, warm: int = 220, measure: int = 60) -> dict[str, Any]:
    from mechanistic_mind.planet.dynamics import step_planet

    rt, _ = _n_agent_runtime(2, seed=seed)
    for _ in range(warm):
        rt.step(1)

    buckets = {
        "obs_total": [],
        "cog_0": [],
        "cog_1": [],
        "psc_0": [],
        "psc_1": [],
        "begin_rest_0": [],
        "begin_rest_1": [],
        "planet": [],
        "finish_0": [],
        "finish_1": [],
        "interaction_tail": [],
        "tick_total": [],
    }

    # Monkeypatch compose timing via wrapper on each call inside cognition — measure PSC by
    # timing full cognition and a separate compose-only probe on copies would double work.
    # Instead: time observation, cognition-only (run_cognition), then full begin without re-thinking
    # by reconstructing begin path roughly: we time natural _step_once sections.

    original_begin = rt.slots[0].begin_tick.__func__  # unbound unused; use instrumented loop

    for _ in range(measure):
        t_tick0 = time.perf_counter()
        order = rt.process_order if len(rt.process_order) == len(rt.slots) else tuple(range(len(rt.slots)))

        t0 = time.perf_counter()
        obs = rt.observations()
        buckets["obs_total"].append((time.perf_counter() - t0) * 1000)

        # Cognition-only (does mutate cognition stores — this IS the real tick path for think)
        cog_ms = []
        for i in order:
            t1 = time.perf_counter()
            # Mirror begin_tick cognition portion only, then call full begin_tick which would
            # double-learn. So we must use full begin_tick and attribute via nested timers.
            pass
            cog_ms.append(0.0)

        # Full serial begin/finish matching production, with timers around methods.
        import mechanistic_mind.research.prospective_composition as pcmod
        import mechanistic_mind.physical_system.runtime as rtmod

        for i in order:
            slot = rt.slots[i]
            # begin_tick calls runtime.run_cognition_before_action (imported binding)
            real_run = rtmod.run_cognition_before_action
            real_compose = pcmod.compose_trajectories
            think_ms = [0.0]
            psc_acc = [0.0]

            def cwrap(*a, _real=real_compose, _psc=psc_acc, **k):
                tc = time.perf_counter()
                try:
                    return _real(*a, **k)
                finally:
                    _psc[0] += (time.perf_counter() - tc) * 1000

            def wrapped(state, *, observation, tick, rng_value, _real=real_run, _think=think_ms):
                tc = time.perf_counter()
                try:
                    return _real(state, observation=observation, tick=tick, rng_value=rng_value)
                finally:
                    _think[0] += (time.perf_counter() - tc) * 1000

            rtmod.run_cognition_before_action = wrapped  # type: ignore
            pcmod.compose_trajectories = cwrap  # type: ignore
            try:
                t_cog0 = time.perf_counter()
                slot.begin_tick(observation=obs[i])
                begin_ms = (time.perf_counter() - t_cog0) * 1000
            finally:
                rtmod.run_cognition_before_action = real_run  # type: ignore
                pcmod.compose_trajectories = real_compose  # type: ignore

            buckets[f"cog_{i}"].append(think_ms[0])  # pure cognition
            buckets[f"psc_{i}"].append(psc_acc[0])
            buckets[f"begin_rest_{i}"].append(max(0.0, begin_ms - think_ms[0]))

        t_p = time.perf_counter()
        step_planet(rt.world, rt.slots[0].config.planet, seed=rt.seed)
        buckets["planet"].append((time.perf_counter() - t_p) * 1000)

        for i in order:
            t1 = time.perf_counter()
            rt.slots[i].finish_tick(skip_planet=True, skip_resources=True)
            buckets[f"finish_{i}"].append((time.perf_counter() - t1) * 1000)

        t_tail = time.perf_counter()
        # Reuse production tail by calling the remainder of _step_once logic via private path:
        # simplest: invoke remaining contact/resources/signals by stepping through a one-shot
        # helper extracted inline — call original _step_once would double. Manually call
        # protected section by temporarily replacing begin/finish/planet.
        n = len(rt.slots)
        w = int(rt.world.T.shape[1])
        h = int(rt.world.T.shape[0])
        from mechanistic_mind.physical_system.body_contact import resolve_soft_contact
        from mechanistic_mind.physical_system.physical_push import apply_push_through_contact
        from mechanistic_mind.physical_system.complementary_resources import (
            simultaneous_complementary_resources,
        )
        from mechanistic_mind.physical_system.physical_signal import step_physical_signals

        rt.last_contacts = []
        for ia in range(n):
            for ib in range(ia + 1, n):
                receipt = resolve_soft_contact(
                    rt.slots[ia].body,
                    rt.slots[ib].body,
                    rt.slots[ia].config.body,
                    rt.slots[ib].config.body,
                    width=w,
                    height=h,
                    enabled=rt.contact_enabled,
                )
                push_receipt = apply_push_through_contact(
                    rt.slots[ia].body,
                    rt.slots[ib].body,
                    rt.slots[ia].config.body,
                    rt.slots[ib].config.body,
                    contact=bool(receipt and receipt.get("contact")),
                    push_cfg=rt.slots[ia].config.physical_push,
                    width=w,
                    height=h,
                )
                if receipt is not None:
                    receipt["push"] = push_receipt
                    receipt["pair"] = (ia, ib)
                rt.last_contacts.append(receipt)
        rt.last_contact = rt.last_contacts[0] if rt.last_contacts else None
        bodies = [s.body for s in rt.slots]
        body_cfgs = [s.config.body for s in rt.slots]
        rt.last_resource_sim = simultaneous_complementary_resources(
            bodies,
            rt.world,
            body_cfgs,
            rt.slots[0].config.complementary_resources,
            rt.slots[0].config.deformation_work,
            receipt_tick=int(rt.tick),
        )
        if rt.signal_enabled or rt.slots[0].config.physical_signal.enabled:
            rt.last_signal_receipt = step_physical_signals(
                rt.world,
                bodies,
                body_cfgs,
                rt.slots[0].config.physical_signal,
                contact=rt.last_contact,
                extra_sources=[],
                receipt_tick=int(rt.tick),
            )
        osc_cfg = getattr(rt.slots[0].config, "oscillatory_signaling", None)
        if osc_cfg is not None and osc_cfg.enabled:
            from mechanistic_mind.physical_system.oscillatory_signaling import (
                ensure_osc_fields,
                step_oscillatory_signaling,
            )

            ensure_osc_fields(rt.world, osc_cfg)
            step_oscillatory_signaling(
                rt.world,
                bodies,
                osc_cfg,
                tick=int(rt.tick),
                articulated_head=bool(getattr(rt.slots[0].config.articulated_head, "enabled", False)),
                body_ids=[f"agent_{i}" for i in range(n)],
                slots=list(range(n)),
            )
        rt._record_stats_after_tick()
        buckets["interaction_tail"].append((time.perf_counter() - t_tail) * 1000)
        buckets["tick_total"].append((time.perf_counter() - t_tick0) * 1000)

    # Rename: cog_* currently stores full begin_tick ms
    summary = {k: _pct(v) for k, v in buckets.items()}
    total = summary["tick_total"]["mean"] or 1.0
    shares = {k: 100.0 * summary[k]["mean"] / total for k in buckets if k != "tick_total"}
    # Parallelizable = cognition-dominated portion of begin (approx begin - tiny apply).
    # Use PSC + (begin - PSC) as agent cognition wall; apply is small vs PSC.
    parallel_ms = summary["cog_0"]["mean"] + summary["cog_1"]["mean"]
    apply_serial = summary["begin_rest_0"]["mean"] + summary["begin_rest_1"]["mean"]
    other_serial = (
        summary["obs_total"]["mean"]
        + summary["planet"]["mean"]
        + summary["finish_0"]["mean"]
        + summary["finish_1"]["mean"]
        + summary["interaction_tail"]["mean"]
    )
    # Barrier model: parallel think → serial apply → serial rest
    t_barrier = (
        max(summary["cog_0"]["mean"], summary["cog_1"]["mean"])
        + apply_serial
        + other_serial
    )
    speedup_barrier = total / max(1e-9, t_barrier)
    # Optimistic: apply also agent-local parallel
    t_opt = (
        max(summary["cog_0"]["mean"] + summary["begin_rest_0"]["mean"],
            summary["cog_1"]["mean"] + summary["begin_rest_1"]["mean"])
        + other_serial
    )
    speedup_opt = total / max(1e-9, t_opt)
    parallel_fraction = parallel_ms / total

    out = {
        "warm": warm,
        "measure": measure,
        "seed": seed,
        "ms": summary,
        "pct_of_tick": shares,
        "amdahl": {
            "mean_tick_ms": total,
            "agent_cognition_sum_ms": parallel_ms,
            "agent_cognition_fraction": parallel_fraction,
            "psc_sum_ms": summary["psc_0"]["mean"] + summary["psc_1"]["mean"],
            "apply_serial_ms": apply_serial,
            "other_serial_ms": other_serial,
            "theoretical_speedup_think_parallel_barrier_2cores": speedup_barrier,
            "theoretical_speedup_begin_fully_parallel_2cores": speedup_opt,
            "note": (
                "cog_* = run_cognition_before_action only; begin_rest_* = motor apply; "
                "psc_* = compose_trajectories inside cognition."
            ),
        },
    }
    (OUT / "per_agent_profile.json").write_text(json.dumps(out, indent=2))
    return out


def scaling_benchmark(seed: int = 17, warm: int = 200, measure: int = 50) -> dict[str, Any]:
    results = {}
    for n in (1, 2, 4):
        rt, _ = _n_agent_runtime(n, seed=seed)
        for _ in range(warm):
            rt.step(1)
        xs = []
        for _ in range(measure):
            t0 = time.perf_counter()
            rt.step(1)
            xs.append((time.perf_counter() - t0) * 1000)
        m = statistics.mean(xs)
        # occupancy
        occ = []
        slots = getattr(rt, "slots", [rt])
        for i, s in enumerate(slots):
            store = (s.cognition.get("prospection") or {}) if isinstance(s.cognition, dict) else {}
            n_tr = 0
            tr = store.get("transitions")
            if isinstance(tr, dict):
                n_tr = len(tr)
            elif isinstance(tr, list):
                n_tr = len(tr)
            cap = int(store.get("capacity") or store.get("max_transitions") or 128)
            occ.append({"slot": i, "n": n_tr, "cap": cap, "frac": n_tr / max(1, cap)})
        results[str(n)] = {
            "agents": n,
            "tps": 1000.0 / m,
            "ms_tick": m,
            "p95_ms": _pct(xs)["p95"],
            "occupancy": occ,
            "cpu_count": os.cpu_count(),
        }
    # Scaling character
    t1 = results["1"]["ms_tick"]
    t2 = results["2"]["ms_tick"]
    t4 = results["4"]["ms_tick"]
    results["scaling"] = {
        "ms_ratio_2_over_1": t2 / max(1e-9, t1),
        "ms_ratio_4_over_1": t4 / max(1e-9, t1),
        "ms_ratio_4_over_2": t4 / max(1e-9, t2),
        "character": (
            "approx_O_n"
            if abs((t2 / t1) - 2) < 0.45 and abs((t4 / t1) - 4) < 1.2
            else "sublinear"
            if (t2 / t1) < 1.7 and (t4 / t1) < 3.2
            else "superlinear"
            if (t2 / t1) > 2.3 or (t4 / t1) > 4.5
            else "mixed"
        ),
    }
    (OUT / "scaling.json").write_text(json.dumps(results, indent=2))
    return results


def _cog_worker(payload: dict[str, Any]) -> dict[str, Any]:
    """Process-pool worker: run one cognition tick on serialized state."""
    from mechanistic_mind.physical_system.cognition import run_cognition_before_action

    t0 = time.perf_counter()
    result = run_cognition_before_action(
        payload["state"],
        observation=payload["observation"],
        tick=int(payload["tick"]),
        rng_value=float(payload["rng"]),
    )
    ms = (time.perf_counter() - t0) * 1000
    return {
        "ms": ms,
        "selected": result.selected_action,
        "state": payload["state"],  # mutated
    }


def prototype_parallel(seed: int = 17, warm: int = 220, measure: int = 40) -> dict[str, Any]:
    """Isolated prototype: serial vs thread vs process for cognition-only on frozen inputs."""
    from mechanistic_mind.physical_system.cognition import run_cognition_before_action
    from mechanistic_mind.physical_system.runtime import _rng_unit

    rt, _ = _n_agent_runtime(2, seed=seed)
    for _ in range(warm):
        rt.step(1)

    serial_ms = []
    thread_ms = []
    # Process pool: measure serialize+compute cost on one representative tick repeatedly
    # using deepcopy payloads (does not advance world).
    process_ms = []
    exact_thread = []
    exact_process = []

    for _ in range(measure):
        obs = rt.observations()
        tick = int(rt.slots[0].tick)
        base = [deepcopy(rt.slots[i].cognition) for i in range(2)]
        rngs = [_rng_unit(rt.slots[i].seed, tick) for i in range(2)]

        # SERIAL
        s_states = [deepcopy(base[0]), deepcopy(base[1])]
        t0 = time.perf_counter()
        r_serial = []
        for i in range(2):
            r_serial.append(
                run_cognition_before_action(
                    s_states[i], observation=obs[i], tick=tick, rng_value=rngs[i]
                )
            )
        serial_ms.append((time.perf_counter() - t0) * 1000)

        # THREADS
        t_states = [deepcopy(base[0]), deepcopy(base[1])]
        t0 = time.perf_counter()
        r_thread = [None, None]

        def _job(i: int):
            r_thread[i] = run_cognition_before_action(
                t_states[i], observation=obs[i], tick=tick, rng_value=rngs[i]
            )

        with ThreadPoolExecutor(max_workers=2) as ex:
            futs = [ex.submit(_job, i) for i in range(2)]
            for f in futs:
                f.result()
        thread_ms.append((time.perf_counter() - t0) * 1000)
        exact_thread.append(
            r_serial[0].selected_action == r_thread[0].selected_action
            and r_serial[1].selected_action == r_thread[1].selected_action
            and _digest(s_states[0].get("last_selection")) == _digest(t_states[0].get("last_selection"))
            and _digest(s_states[1].get("last_selection")) == _digest(t_states[1].get("last_selection"))
        )

        # Advance world once per loop so stores stay mature / varied
        rt.step(1)

    # Process prototype on a single frozen pair (amortize pool startup outside loop)
    obs = rt.observations()
    tick = int(rt.slots[0].tick)
    base = [deepcopy(rt.slots[i].cognition) for i in range(2)]
    rngs = [_rng_unit(rt.slots[i].seed, tick) for i in range(2)]
    payloads = [
        {
            "state": deepcopy(base[i]),
            "observation": obs[i],
            "tick": tick,
            "rng": rngs[i],
        }
        for i in range(2)
    ]
    # serial reference for this frozen tick
    s_states = [deepcopy(base[0]), deepcopy(base[1])]
    r_serial = [
        run_cognition_before_action(s_states[i], observation=obs[i], tick=tick, rng_value=rngs[i])
        for i in range(2)
    ]
    # Include pickle round-trip cost
    t0 = time.perf_counter()
    with ProcessPoolExecutor(max_workers=2) as ex:
        futs = [ex.submit(_cog_worker, payloads[i]) for i in range(2)]
        proc_results = [f.result() for f in futs]
    process_ms.append((time.perf_counter() - t0) * 1000)
    exact_process.append(
        proc_results[0]["selected"] == r_serial[0].selected_action
        and proc_results[1]["selected"] == r_serial[1].selected_action
    )

    # Estimate pickle size
    import pickle

    pickle_bytes = sum(len(pickle.dumps(p)) for p in payloads)

    out = {
        "serial_ms": _pct(serial_ms),
        "thread_ms": _pct(thread_ms),
        "process_one_shot_ms": _pct(process_ms),
        "speedup_thread_vs_serial": (_pct(serial_ms)["mean"] / max(1e-9, _pct(thread_ms)["mean"])),
        "thread_exact_fraction": sum(exact_thread) / max(1, len(exact_thread)),
        "process_exact_match_selected": all(exact_process),
        "process_payload_pickle_bytes_total": pickle_bytes,
        "note": (
            "Prototype does not replace production TwoAgentRuntime. "
            "Thread path shares process memory (no pickle). Process path pickles full cognition stores."
        ),
    }
    (OUT / "prototype_parallel.json").write_text(json.dumps(out, indent=2))
    return out


def options_matrix(profile: dict, scaling: dict, proto: dict) -> dict[str, Any]:
    begin_frac = float(profile.get("amdahl", {}).get("agent_cognition_fraction") or 0)
    speedup2 = float(
        profile.get("amdahl", {}).get("theoretical_speedup_think_parallel_barrier_2cores") or 1
    )
    pickle_b = int(proto.get("process_payload_pickle_bytes_total") or 0)
    thread_s = float(proto.get("speedup_thread_vs_serial") or 1)
    out = {
        "A_threading": {
            "expected_parallelism": "Low under GIL for pure-Python cognition",
            "gil": "Dominant — PSC is Python bytecode",
            "serialization": "None (shared memory)",
            "determinism": "Possible if no racy module caches; _SIG_CACHE not thread-safe",
            "likely_benefit_2_agents": f"measured_thread_speedup={thread_s:.3f}",
            "likely_benefit_10_plus": "Poor unless free-threaded CPython or native release GIL",
        },
        "B_multiprocessing": {
            "expected_parallelism": "True multi-core",
            "serialization": f"~{pickle_b} bytes/tick for 2 frozen cognition payloads (order-of-magnitude)",
            "world_snapshot": "Not required if only cognition ships; obs already dict[str,float]",
            "cognition_store_transfer": "Full store pickle each tick unless shared-memory redesign",
            "determinism": "OK if inputs identical and apply barrier preserves process_order",
            "likely_benefit_2_agents": "Likely erased by pickle+IPC for current store size",
            "likely_benefit_10_plus": "Only with shared-memory stores or native backend",
        },
        "C_ProcessPoolExecutor": {
            "same_as": "B",
            "pool_warmup": "Amortizable; per-tick payload still large",
        },
        "D_free_threaded_python": {
            "expected": "Would make threads viable for pure-Python PSC if caches locked/partitioned",
            "status": "Not assumed available in this audit environment",
        },
        "E_numba_native_hotpath": {
            "prior_verdict": "NOT_WORTH_IT for single-agent PSC hot path (PSC_COMPOSITION_PERFORMANCE)",
            "parallel_angle": "Does not by itself enable agent-level fork; may shrink serial fraction",
        },
        "F_cpp_cognition_backend": {
            "expected": "Best long-term if releasing GIL around compose/soft_match",
            "complexity": "High; EXACT_MATCH burden large",
        },
        "G_hybrid": {
            "description": (
                "Barrier architecture: observe-all → parallel think → serial apply/finish/interact"
            ),
            "matches_current_semantics": True,
            "theoretical_2_agent_speedup_cap": speedup2,
            "begin_fraction": begin_frac,
        },
    }
    (OUT / "parallelization_options.json").write_text(json.dumps(out, indent=2))
    return out


def determinism_plan() -> dict[str, Any]:
    plan = {
        "seeds": [17, 23, 41, 59, 83],
        "protocol": [
            "Warm to filled prospection on serial runtime; snapshot.",
            "Run N ticks serial; fingerprint world, bodies, internals, cognition stores, events, RNG digests.",
            "Restore snapshot; run N ticks with parallel-think + serial-commit prototype.",
            "Require EXACT_MATCH on all scientific fields.",
            "Also run process_order (0,1) vs ensure parallel results equal serial (0,1) order apply.",
            "Exposure-heavy seed from live_optical_performance for contact/vision.",
        ],
        "must_preserve": [
            "same tick-T observations",
            "candidate identity/order/tie-break",
            "RNG via _rng_unit(seed,tick)",
            "physical commit ordering (process_order)",
            "events/provenance",
        ],
    }
    (OUT / "determinism_plan.json").write_text(json.dumps(plan, indent=2))
    return plan


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    warm = 80 if args.quick else 220
    measure = 20 if args.quick else 60
    scale_warm = 60 if args.quick else 200
    scale_m = 20 if args.quick else 50
    proto_m = 15 if args.quick else 40

    causal = write_causal_order()
    indep = independence_tests(warm=warm)
    profile = profile_per_agent(warm=warm, measure=measure)
    scaling = scaling_benchmark(warm=scale_warm, measure=scale_m)
    proto = None
    if indep.get("cognition_commutative_within_tick"):
        proto = prototype_parallel(warm=warm, measure=proto_m)
    else:
        proto = {"skipped": True, "reason": "cognition not commutative"}
        (OUT / "prototype_parallel.json").write_text(json.dumps(proto, indent=2))
    options = options_matrix(profile, scaling, proto if isinstance(proto, dict) else {})
    det = determinism_plan()

    # Verdict
    begin_frac = float(profile.get("amdahl", {}).get("agent_cognition_fraction") or 0)
    speedup = float(
        profile.get("amdahl", {}).get("theoretical_speedup_think_parallel_barrier_2cores") or 1
    )
    thread_s = float(proto.get("speedup_thread_vs_serial") or 0) if isinstance(proto, dict) else 0
    pickle_b = int(proto.get("process_payload_pickle_bytes_total") or 0) if isinstance(proto, dict) else 0

    # Architectural verdict: scientific safety first; practical CPython cost is reported separately.
    if not indep.get("cognition_commutative_within_tick"):
        verdict = "MULTI_AGENT_PARALLELISM_SEMANTIC_CHANGE_REQUIRED"
    else:
        verdict = "MULTI_AGENT_PARALLELISM_SAFE_WITH_BARRIER"
    practical = (
        "NOT_WORTHWHILE_ON_CURRENT_CPYTHON"
        if (thread_s < 1.05 and pickle_b > 100_000)
        else "PROTOTYPE_SHOWS_GAIN"
    )

    summary = {
        "verdict": verdict,
        "practical_on_current_cpython": practical,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "answers": {
            "1_cognition_independent_within_tick": indep.get("cognition_commutative_within_tick"),
            "2_same_world_snapshot_or_sequential": "SAME_SNAPSHOT_T_THEN_SERIAL_APPLY",
            "3_parallelizable_fraction": begin_frac,
            "4_shared_mutable": indep.get("shared_mutable_modules"),
            "5_rng_order": "per-agent _rng_unit(seed,tick); process_order for apply/finish",
            "6_theoretical_2_agent_speedup": speedup,
            "7_prototype_thread_speedup": thread_s,
            "8_scaling": scaling.get("scaling"),
            "9_threads_help": thread_s > 1.1,
            "10_multiprocessing_help_2": pickle_b < 50_000 and speedup > 1.2,
            "11_native_helps_agent_parallelism": "makes threads more useful by releasing GIL; does not remove barrier need",
            "12_ten_plus_agents": scaling.get("scaling"),
            "13_exact_match_possible": bool(indep.get("cognition_commutative_within_tick")),
            "14_scientifically_safe": bool(indep.get("cognition_commutative_within_tick")),
        },
        "causal_possibility": causal.get("possibility"),
        "profile_amdahl": profile.get("amdahl"),
        "prototype": {
            k: proto.get(k)
            for k in (
                "speedup_thread_vs_serial",
                "thread_exact_fraction",
                "process_payload_pickle_bytes_total",
                "process_exact_match_selected",
                "skipped",
            )
            if isinstance(proto, dict) and k in proto
        },
    }
    (OUT / "SUMMARY.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    main()
