#!/usr/bin/env python3
"""BETA2-GEO-03 audit: screenshot-case forensics, CURRENT/GENTLE, CORE vs LIVE perf."""
from __future__ import annotations

import json
import time
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from mechanistic_mind.physical_system.ecology_presets import (
    ECOLOGY_CURRENT,
    ECOLOGY_GENTLE,
    make_ecology_config,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.ui.psy_observer_web.experimenter_control import (
    ExperimenterController,
    apply_experimenter_pre_step,
    record_experimenter_post_step,
    spawn_experimenter_body,
)
from mechanistic_mind.ui.psy_observer_web.geometry.action_realization import (
    build_action_realization_receipt,
    collect_from_runtime,
)
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "environment_ecology"


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _forced(rt: PhysicalSystemRuntime, action: str) -> None:
    rt._forced_action_once = action
    rt.step()


def screenshot_case_audit(*, preset: str, seed: int = 17) -> dict:
    """Reproduce MOVE:W weak progress and explain from actual receipt."""
    cfg = make_ecology_config(preset)
    cfg.cognition.cognition_enabled = False
    rt = PhysicalSystemRuntime(seed=seed, config=cfg)
    samples = []
    for _ in range(80):
        _forced(rt, "MOVE:W")
        r = build_action_realization_receipt(rt, agent_id="agent_0")
        samples.append({
            "tick": r["tick"],
            "requested_action": r["requested_action"],
            "realized_delta": r["realized_delta"],
            "realized_distance": r["realized_distance"],
            "action_alignment": r["action_alignment"],
            "work_fraction": r["work_fraction"],
            "work_limited": r["work_limited"],
            "available_work_before": r["available_work_before"],
            "environmental_force": r["environmental_force"],
            "contact_active": r["contact_active"],
            "deformation": r.get("deformation"),
            "outcome": r["outcome"],
            "primary_constraint": r["primary_constraint"],
            "secondary_constraints": r["secondary_constraints"],
            "attribution": r["attribution"],
            "expected_free_progress_status": r["expected_free_progress_status"],
        })
    similar = [
        s for s in samples
        if s["action_alignment"] is not None
        and float(s["action_alignment"]) >= 0.9
        and 0.01 <= float(s["realized_distance"] or 0) <= 0.08
    ]
    weak = [s for s in samples if s["outcome"] == "ALIGNED_WEAK"]
    if similar:
        pick = min(similar, key=lambda s: abs(float(s["realized_distance"]) - 0.035))
    elif weak:
        pick = max(weak, key=lambda s: float(s["action_alignment"] or -1))
    else:
        pick = min(samples, key=lambda s: float(s["realized_distance"] or 99))
    return {
        "preset": preset,
        "seed": seed,
        "n_samples": len(samples),
        "screenshot_like": pick,
        "n_aligned_weak_high_align": len(similar),
        "n_aligned_weak": len(weak),
        "outcome_counts": dict(Counter(s["outcome"] for s in samples)),
        "primary_constraint_counts": dict(Counter(s["primary_constraint"] for s in samples)),
        "samples_tail": samples[-8:],
        "forensic_note": (
            "Per-action primary_constraint from measured work/env/contact — "
            "not inferred from cumulative work_limited counters alone."
        ),
    }


def experimenter_audit() -> dict:
    cfg = make_ecology_config(ECOLOGY_GENTLE)
    rt = TwoAgentRuntime(seed=31, config=cfg, signal_enabled=True)
    ctrl = ExperimenterController()
    spawn_experimenter_body(rt, x=12.0, y=12.0, controller=ctrl)
    rows = []
    for act in ("MOVE:W", "MOVE:W", "MOVE:W", "MOVE:N", "MOVE:E"):
        ctrl.enqueue("ACTION", action=act)
        apply_experimenter_pre_step(rt, ctrl)
        rt.step()
        record_experimenter_post_step(rt, ctrl)
        receipts = collect_from_runtime(rt, experimenter_slot=rt.experimenter_slot)
        exp = next(r for r in receipts if r["agent_id"] == "undercover")
        rows.append({
            "requested": exp["requested_action"],
            "delta": exp["realized_delta"],
            "dist": exp["realized_distance"],
            "align": exp["action_alignment"],
            "work_frac": exp["work_fraction"],
            "outcome": exp["outcome"],
            "primary": exp["primary_constraint"],
        })
    return {"rows": rows, "verdict": "EXPERIMENTER_SUPPORT"}


def autonomous_audit() -> dict:
    cfg = make_ecology_config(ECOLOGY_CURRENT)
    rt = TwoAgentRuntime(seed=43, config=cfg)
    # Force a MOVE on agent_0 so forensic view is exercised (not WAIT-only)
    for i in range(12):
        rt.slots[0]._forced_action_once = "MOVE:N" if i % 2 == 0 else "MOVE:E"
        rt.step()
    receipts = collect_from_runtime(rt)
    return {
        "agents": [
            {
                "agent_id": r["agent_id"],
                "action": r["requested_action"],
                "outcome": r["outcome"],
                "primary": r["primary_constraint"],
                "dist": r["realized_distance"],
                "align": r["action_alignment"],
                "work_frac": r["work_fraction"],
            }
            for r in receipts
        ],
        "verdict": "AUTONOMOUS_AGENT_SUPPORT",
    }


def cognition_boundary_audit() -> dict:
    cfg = make_ecology_config(ECOLOGY_GENTLE)
    rt = PhysicalSystemRuntime(seed=7, config=cfg)
    rt._forced_action_once = "MOVE:W"
    rt.step()
    r = build_action_realization_receipt(rt)
    obs = str(rt.last_agent_observation)
    leaks = [
        k for k in ("ALIGNED_WEAK", "WORK_LIMITED", "action_realization", "PRIMARY CONSTRAINT")
        if k in obs
    ]
    return {
        "receipt_outcome": r["outcome"],
        "leaks_in_observation": leaks,
        "held": len(leaks) == 0,
        "verdict": "COGNITION_INFORMATION_BOUNDARY",
    }


def perf_core_vs_live(*, ticks: int = 120) -> dict:
    """CORE = scientific ticks; LIVE = ObserverSession.step (incl. GEO-03 observe).

    Does not force full current_frame() every tick. Also reports AR-collect overhead.
    """
    cfg = make_ecology_config(ECOLOGY_GENTLE)

    rt = TwoAgentRuntime(seed=17, config=deepcopy(cfg), signal_enabled=True)
    ctrl = ExperimenterController()
    spawn_experimenter_body(rt, x=8.0, y=8.0, controller=ctrl)
    t0 = time.perf_counter()
    for i in range(ticks):
        if i % 2 == 0:
            ctrl.enqueue("ACTION", action="MOVE:W")
        apply_experimenter_pre_step(rt, ctrl)
        rt.step()
        record_experimenter_post_step(rt, ctrl)
    core_s = time.perf_counter() - t0
    core_tps = ticks / max(1e-9, core_s)

    rt2 = TwoAgentRuntime(seed=17, config=deepcopy(cfg), signal_enabled=True)
    ctrl2 = ExperimenterController()
    spawn_experimenter_body(rt2, x=8.0, y=8.0, controller=ctrl2)
    t_ar = time.perf_counter()
    for i in range(ticks):
        if i % 2 == 0:
            ctrl2.enqueue("ACTION", action="MOVE:W")
        apply_experimenter_pre_step(rt2, ctrl2)
        rt2.step()
        record_experimenter_post_step(rt2, ctrl2)
        collect_from_runtime(rt2, experimenter_slot=rt2.experimenter_slot)
    ar_s = time.perf_counter() - t_ar
    ar_tps = ticks / max(1e-9, ar_s)

    sess = ObserverSession(config=SessionConfig(seed=17))
    sess.apply_experiment({
        "seed": 17,
        "ecology_preset": ECOLOGY_GENTLE,
        "agent_count": 2,
        "mechanisms": {"experimental_physical_signal": True, "cognition_enabled": True},
    })
    try:
        sess.experimenter_spawn(x=8.0, y=8.0)
    except Exception:
        pass
    t1 = time.perf_counter()
    for i in range(ticks):
        if i % 2 == 0:
            try:
                sess.experimenter_command(kind="ACTION", action="MOVE:W")
            except Exception:
                pass
        sess.step(1)
    live_s = time.perf_counter() - t1
    live_tps = ticks / max(1e-9, live_s)
    ratio = live_tps / max(1e-9, core_tps)
    ar_ratio = ar_tps / max(1e-9, core_tps)
    return {
        "ticks": ticks,
        "core_seconds": core_s,
        "ar_collect_seconds": ar_s,
        "live_seconds": live_s,
        "core_tps": core_tps,
        "ar_collect_tps": ar_tps,
        "live_tps": live_tps,
        "live_over_core": ratio,
        "ar_collect_over_core": ar_ratio,
        "target": 0.80,
        "pass_live": ratio >= 0.80,
        "pass_ar_overhead": ar_ratio >= 0.80,
        "note": (
            "LIVE=ObserverSession.step (geometry + GEO-03). "
            "AR collect alone should stay near CORE. Full UI frame capture is separate."
        ),
        "verdict": "OBSERVER_PERFORMANCE",
    }


def main() -> None:
    stamp = _ts()
    out_dir = OUT / f"beta2_geo_03_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "task": "BETA2-GEO-03",
        "timestamp": stamp,
        "screenshot_CURRENT": screenshot_case_audit(preset=ECOLOGY_CURRENT),
        "screenshot_GENTLE": screenshot_case_audit(preset=ECOLOGY_GENTLE),
        "experimenter": experimenter_audit(),
        "autonomous": autonomous_audit(),
        "cognition_boundary": cognition_boundary_audit(),
        "performance": perf_core_vs_live(ticks=100),
    }
    report["current_vs_gentle"] = {
        "CURRENT_primaries": report["screenshot_CURRENT"]["primary_constraint_counts"],
        "GENTLE_primaries": report["screenshot_GENTLE"]["primary_constraint_counts"],
        "CURRENT_outcomes": report["screenshot_CURRENT"]["outcome_counts"],
        "GENTLE_outcomes": report["screenshot_GENTLE"]["outcome_counts"],
    }
    path = out_dir / "geo03_audit.json"
    path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    summary = {
        "artifact": str(path),
        "gentle_case": report["screenshot_GENTLE"]["screenshot_like"],
        "current_case": report["screenshot_CURRENT"]["screenshot_like"],
        "perf": report["performance"],
        "cognition_held": report["cognition_boundary"]["held"],
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
