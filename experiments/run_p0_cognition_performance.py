#!/usr/bin/env python3
"""P0 cognition performance: aged microbench + disposable TwoAgent checkpoints.

Does not attach to an existing Observer run. GIT_PUSH=NO.
"""
from __future__ import annotations

import json
import os
import resource
import time
from pathlib import Path

from mechanistic_mind.model.tiktaalik import tiktaalik_config
from mechanistic_mind.physical_system import TwoAgentRuntime
from mechanistic_mind.physical_system import sensorimotor_consequence as smc
from mechanistic_mind.physical_system.psc_motor_resolution_shadow import (
    observed_composites_for_loco,
    observed_composites_for_loco_scan,
)
from mechanistic_mind.research import predictive_compression as pc
from mechanistic_mind.research import predictive_equivalence as pe

OUT = Path("results/p0_cognition_performance")


def _rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def _frag(n: float):
    return {f"k{i}": float(n) + 0.01 * i for i in range(12)}


def _aged_pe(*, extra_forgotten: int) -> dict:
    s = pe.empty_store()
    s["enabled"] = True
    n = pe.MAX_CLASSES + max(0, int(extra_forgotten))
    for i in range(n):
        pe.learn(
            s,
            fragment=_frag(float(i)),
            action=f"A{i % 7}",
            consequent={"out": float(i) * 3.1},
            tick=i,
        )
    return s


def _old_active_count(classes: dict) -> int:
    return len([c for c in classes.values() if c.get("status") == "ACTIVE"])


def _old_forget_victim(classes: dict) -> str:
    victim = min(
        (kv for kv in classes.items() if kv[1].get("status") == "ACTIVE"),
        key=lambda kv: int(kv[1].get("support") or 0),
    )[0]
    return victim


def _time_ms(fn, loops: int) -> float:
    t0 = time.perf_counter()
    for _ in range(loops):
        fn()
    return (time.perf_counter() - t0) * 1000.0 / loops


def microbench() -> dict:
    out: dict = {}
    for label, n_for in (("small", 0), ("medium", 64), ("aged", 512)):
        print(f"  pe {label} extra_forgotten={n_for}…", flush=True)
        t_build = time.perf_counter()
        s = _aged_pe(extra_forgotten=n_for)
        print(f"    built in {time.perf_counter() - t_build:.3f}s classes={len(s['classes'])}", flush=True)
        classes = s["classes"]
        n_all = len(classes)
        n_act = pe.scan_active_class_count(s)
        n_for_real = n_all - n_act
        pe.ensure_class_indexes(s)
        old_c = _time_ms(lambda: _old_active_count(classes), 400)
        new_c = _time_ms(lambda: pe.active_class_count(s), 400)
        old_v = _time_ms(lambda: _old_forget_victim(classes), 200)
        new_v = _time_ms(lambda: min(s["_active_ids"], key=lambda cid: int(classes[cid].get("support") or 0)), 200)
        rebuild = _time_ms(lambda: pe.rebuild_class_indexes(s), 20)
        # typical UPDATE learn (repeat existing member) — no full rebuild
        upd = _time_ms(
            lambda: pe.learn(s, fragment=_frag(0.0), action="A0", consequent={"out": 0.0}, tick=10_000),
            20,
        )
        # Combined hot-path tax: count + victim + (old) full rebuild vs O(1)+active-set min, no rebuild
        old_tax = _time_ms(
            lambda: (
                _old_active_count(classes),
                _old_forget_victim(classes),
                pe.rebuild_class_indexes(s),
            ),
            20,
        )
        new_tax = _time_ms(
            lambda: (
                pe.active_class_count(s),
                min(s["_active_ids"], key=lambda cid: int(classes[cid].get("support") or 0)),
            ),
            20,
        )
        out[label] = {
            "total_classes": n_all,
            "active": n_act,
            "forgotten": n_for_real,
            "old_active_count_ms": round(old_c, 4),
            "new_active_count_ms": round(new_c, 4),
            "old_victim_select_ms": round(old_v, 4),
            "new_victim_select_ms": round(new_v, 4),
            "rebuild_indexes_ms": round(rebuild, 4),
            "learn_update_ms": round(upd, 4),
            "active_count_speedup": round(old_c / new_c, 2) if new_c else None,
            "victim_speedup": round(old_v / new_v, 2) if new_v else None,
            "semantic_active_equal": n_act == pe.active_class_count(s),
            "old_learn_tax_ms": round(old_tax, 4),
            "new_learn_tax_ms": round(new_tax, 4),
            "learn_tax_speedup": round(old_tax / new_tax, 2) if new_tax else None,
        }
    # SMC
    print("  smc fill…", flush=True)
    store = smc.empty_store(enabled=True, capacity=256)
    locos = ["WAIT", "MOVE:N", "MOVE:S", "MOVE:E", "MOVE:W"]
    necks = ["NONE", "NECK_LEFT", "NECK_RIGHT"]
    t = 0
    while len(store["records"]) < 256 and t < 4000:
        # Unique quantized contexts: QUANT_BINS=5 per channel — use several channels.
        obs_t = {k: 0.2 for k in smc.SENSORY_CHANNELS[:8]}
        obs_t["exo_0"] = ((t % 5) + 0.5) / 5.0
        obs_t["exo_1"] = (((t // 5) % 5) + 0.5) / 5.0
        obs_t["exo_2"] = (((t // 25) % 5) + 0.5) / 5.0
        obs_t1 = dict(obs_t)
        obs_t1["exo_0"] = ((t % 4) + 0.5) / 5.0
        m = {
            "locomotion": locos[t % 5],
            "neck": necks[t % 3],
            "oscillator": {"emit_trigger": bool(t % 4 == 0)},
            "push": bool(t % 5 == 0),
        }
        smc.update(store, tick=t, observation_t=obs_t, motor=m, observation_t1=obs_t1)
        t += 1
    print(f"    smc occupancy={len(store['records'])} after {t} updates", flush=True)
    smc.ensure_indexes(store)
    scan_ms = _time_ms(lambda: observed_composites_for_loco_scan(store, "MOVE:E"), 80)
    ix_ms = _time_ms(lambda: observed_composites_for_loco(store, "MOVE:E"), 80)
    a = observed_composites_for_loco(store, "MOVE:E")
    b = observed_composites_for_loco_scan(store, "MOVE:E")
    out["smc_256"] = {
        "occupancy": len(store["records"]),
        "scan_ms": round(scan_ms, 4),
        "index_ms": round(ix_ms, 4),
        "speedup": round(scan_ms / ix_ms, 2) if ix_ms else None,
        "candidate_equal": [r["motor_signature"] for r in a] == [r["motor_signature"] for r in b],
    }
    o = {f"k{i}": 0.03 * i for i in range(40)}
    sig_each = _time_ms(lambda: [pc._sig(o) for _ in range(5)], 200)
    sig_once = _time_ms(lambda: (lambda s: [s] * 5)(pc._sig(o)), 200)
    out["sig_reuse"] = {
        "five_calls_ms": round(sig_each, 4),
        "one_call_reuse_ms": round(sig_once, 4),
        "speedup": round(sig_each / sig_once, 2) if sig_once else None,
    }
    return out


def _beta3_cfg():
    cfg = tiktaalik_config()
    cog = cfg.cognition
    cog.cognition_enabled = True
    cog.predictive_compression = True
    cog.retrieval = True
    cog.bounded_memory = True
    cog.prospective_composition = True
    cog.predictive_equivalence = True
    cog.predictive_relevance = True
    cog.temporal_predictive_structure = True
    cog.temporal_prospection_bridge = True
    cog.sensorimotor_consequence_model = True
    cog.historical_sensorimotor_selection_bridge = True
    cog.psc_motor_resolution = "OBSERVED_COMPOSITE"
    cog.composite_motor = True
    cog.predictive_conflict = True
    cog.future_sensitive_action = True
    cog.prediction_error_revision = True
    cog.temporal_prediction_error = True
    cog.predicted_context_prospection = True
    cog.multistep_action_prospection = True
    cog.contextual_predictive_organization = True
    cog.context_grounded_prospection = True
    cog.persistent_prospective_control = True
    return cfg


def _pe_stats(rt: TwoAgentRuntime) -> dict:
    rows = []
    for i, slot in enumerate(rt.slots):
        eq = slot.cognition.get("equivalence") or {}
        classes = eq.get("classes") or {}
        tps_inner = ((slot.cognition.get("temporal") or {}).get("inner") or {})
        tcls = tps_inner.get("classes") or {}
        smc_st = slot.cognition.get("sensorimotor_consequence") or {}
        rows.append({
            "agent": i,
            "pe_total": len(classes),
            "pe_active": sum(1 for c in classes.values() if c.get("status") == "ACTIVE"),
            "pe_forgotten": sum(1 for c in classes.values() if c.get("status") == "FORGOTTEN"),
            "tps_inner_total": len(tcls),
            "tps_inner_active": sum(1 for c in tcls.values() if c.get("status") == "ACTIVE"),
            "tps_inner_forgotten": sum(1 for c in tcls.values() if c.get("status") == "FORGOTTEN"),
            "smc_occupancy": len(smc_st.get("records") or {}),
            "smc_capacity": int(smc_st.get("capacity") or 0),
        })
    return {"agents": rows}


def disposable_run(ticks: int = 3000, seed: int = 901) -> dict:
    rt = TwoAgentRuntime(seed=seed, config=_beta3_cfg())
    checkpoints = (100, 1000, 2000, 3000)
    points = []
    t0 = time.perf_counter()
    last = 0
    wall0 = t0
    for target in checkpoints:
        if target > ticks:
            break
        n = target - last
        w0 = time.perf_counter()
        rt.step(n)
        w1 = time.perf_counter()
        last = target
        dt = w1 - w0
        ms = (dt / n) * 1000.0 if n else 0.0
        pts = n / dt if dt > 0 else 0.0
        rec = {
            "tick": int(rt.tick),
            "segment_ticks": n,
            "segment_s": round(dt, 3),
            "ms_tick": round(ms, 2),
            "ticks_per_sec": round(pts, 2),
            "rss_mb": round(_rss_mb(), 1),
            **_pe_stats(rt),
        }
        points.append(rec)
        print(json.dumps(rec), flush=True)
    return {
        "seed": seed,
        "ticks": int(rt.tick),
        "total_s": round(time.perf_counter() - wall0, 3),
        "checkpoints": points,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    print("microbench…", flush=True)
    micro = microbench()
    (OUT / "microbench.json").write_text(json.dumps(micro, indent=2), encoding="utf-8")
    print(json.dumps(micro, indent=2), flush=True)
    ticks = int(os.environ.get("P0_DISPOSABLE_TICKS", "3000"))
    if ticks <= 0:
        (OUT / "summary.json").write_text(
            json.dumps({"microbench": micro, "pid": os.getpid()}, indent=2),
            encoding="utf-8",
        )
        return
    print("disposable TwoAgent…", flush=True)
    run = disposable_run(ticks, 901)
    (OUT / "disposable_two_agent.json").write_text(json.dumps(run, indent=2), encoding="utf-8")
    print(json.dumps(run, indent=2), flush=True)
    (OUT / "summary.json").write_text(
        json.dumps({"microbench": micro, "disposable": run, "pid": os.getpid()}, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
