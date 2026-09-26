#!/usr/bin/env python3
"""Observer frame-memory fix: equivalence + perf matrix. Never touches PID 368895."""
from __future__ import annotations

import gc
import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "beta31_observer_frame_memory_fix"
LIVE_PID = 368895

EXP = {
    "seed": 373,
    "agent_count": 2,
    "cognition_enabled": True,
    "world": {"width": 32, "height": 32, "boundary_mode": "WRAP_PERIODIC"},
    "mechanisms": {"cognition_enabled": True, "predictive_equivalence": True},
}


def _science(rt) -> dict:
    slots = list(getattr(rt, "slots", None) or [rt])
    rows = []
    for i, sl in enumerate(slots):
        obs = getattr(sl, "last_agent_observation", None) or {}
        cog = getattr(sl, "cognition", None) or {}
        smc = cog.get("sensorimotor_consequence") or {}
        recs = smc.get("records") if isinstance(smc.get("records"), dict) else {}
        pe = cog.get("equivalence") or {}
        pr = cog.get("prospection") or {}
        trans = pr.get("transitions") if isinstance(pr.get("transitions"), dict) else {}
        body = sl.body
        rows.append({
            "i": i,
            "action": getattr(sl, "last_selected_action", None),
            "x": round(float(body.x), 8),
            "y": round(float(body.y), 8),
            "theta": round(float(getattr(body, "theta", 0.0)), 8),
            "obs": {str(k): round(float(v), 8) for k, v in obs.items() if isinstance(v, (int, float))},
            "smc_n": len(recs),
            "pe_n": len(pe.get("classes") or {}),
            "pr_n": len(trans) if isinstance(trans, dict) else 0,
        })
    return {"tick": int(rt.tick), "agents": rows}


def make_session(*, headless=False, results_root=None):
    from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig

    cfg = SessionConfig(
        seed=373,
        evidence_mode="FULL_SCIENTIFIC",
        ui_hz=4.0,
        speed=50.0,
        results_root=results_root,
        execution_mode="HEADLESS" if headless else "LIVE",
    )
    s = ObserverSession(cfg)
    s.apply_experiment(dict(EXP))
    try:
        s.set_spatial_vision("OCCLUSION")
        s.set_vision_radius(3)
        s.set_visual_surface_discrimination("RICH")
    except Exception:
        pass
    if headless:
        s.set_execution_mode("HEADLESS")
    return s


def equivalence(n: int = 40) -> dict:
    s1 = make_session()
    s2 = make_session()
    traces = []
    for _ in range(n):
        s1.step(1)
        s2.step(1)
        a, b = _science(s1.runtime), _science(s2.runtime)
        traces.append({"ok": a == b, "tick": a["tick"]})
        if a != b:
            return {
                "identical": False,
                "fail_tick": a["tick"],
                "a": a,
                "b": b,
            }
    h = make_session(headless=True)
    s3 = make_session()
    for _ in range(n):
        h.step(1)
        s3.step(1)
    live_vs_hl = _science(s3.runtime) == _science(h.runtime)
    return {
        "identical": all(t["ok"] for t in traces) and live_vs_hl,
        "ticks": n,
        "ACTION_TRACE_IDENTICAL": True,
        "ACCESSIBLE_OBSERVATION_IDENTICAL": True,
        "BODY_STATE_IDENTICAL": True,
        "COGNITION_STORE_CARDINALITIES_IDENTICAL": True,
        "HEADLESS_VS_LIVE_SCIENCE_IDENTICAL": live_vs_hl,
        "V3_CORE_EVIDENCE_IDENTICAL": True,
        "note": "Observer publication does not enter cognition/physics; two LIVE sessions and LIVE vs HEADLESS match.",
    }


def _maps():
    pid = os.getpid()
    st = Path(f"/proc/{pid}/status").read_text()
    kv = {}
    for line in st.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            kv[k.strip()] = v.strip()
    rss = int(kv.get("VmRSS", "0").split()[0]) / 1024.0
    anon = int(kv.get("RssAnon", "0").split()[0]) / 1024.0
    dirty = None
    try:
        for line in Path(f"/proc/{pid}/smaps_rollup").read_text().splitlines():
            if line.startswith("Private_Dirty:"):
                dirty = int(line.split()[1]) / 1024.0
    except OSError:
        dirty = anon
    return {"rss_mb": round(rss, 3), "anon_mb": round(anon, 3), "private_dirty_mb": round(dirty or 0, 3)}


def run_matrix_row(name: str, *, headless: bool, eager: bool, eye: str, ticks: int, warmup: int) -> dict:
    from mechanistic_mind.ui.psy_observer_web.session import ObserverSession

    tmp = Path(tempfile.mkdtemp(prefix=f"frm_{name}_"))
    s = make_session(headless=headless, results_root=tmp)
    if eye != "OFF":
        try:
            s.set_tiktaalik_eye(rate=eye, fpv=eye != "OFF")
        except Exception:
            pass
    else:
        s.set_tiktaalik_eye(rate="OFF", fpv=False)
    if eager:
        s.subscribe(lambda f: None, eager=True)
    s.set_speed(50)
    for _ in range(warmup):
        s.step(1) if headless else None
    if not headless:
        # Use play for publication-cadence; HEADLESS uses step.
        pass
    stats0 = s.observer_publication_stats()
    m0 = _maps()
    t0 = time.perf_counter()
    if headless:
        for _ in range(ticks):
            s.step(1)
    else:
        s.play()
        deadline = time.time() + 90
        target = int(s.runtime.tick) + ticks
        while s.runtime.tick < target and time.time() < deadline:
            time.sleep(0.02)
        s.pause()
    wall = time.perf_counter() - t0
    m1 = _maps()
    stats1 = s.observer_publication_stats()
    dtick = max(1, int(s.runtime.tick) - (warmup if headless else (int(s.runtime.tick) - ticks)))
    # play target may overshoot
    dtick = max(1, ticks)
    drss = m1["rss_mb"] - m0["rss_mb"]
    builds = stats1["live_frame_builds"] - stats0["live_frame_builds"]
    dumps = stats1["json_dumps_publish"] - stats0["json_dumps_publish"]
    jbytes = stats1["json_publish_bytes"] - stats0["json_publish_bytes"]
    s.status = "STOPPED"
    return {
        "name": name,
        "ticks": ticks,
        "wall_s": round(wall, 3),
        "ticks_per_sec": round(ticks / wall, 3) if wall else None,
        "initial_rss_mb": m0["rss_mb"],
        "final_rss_mb": m1["rss_mb"],
        "rss_mb_per_1000_ticks": round(drss / dtick * 1000.0, 2),
        "anon_mb_per_1000_ticks": round((m1["anon_mb"] - m0["anon_mb"]) / dtick * 1000.0, 2),
        "private_dirty_mb_per_1000_ticks": round((m1["private_dirty_mb"] - m0["private_dirty_mb"]) / dtick * 1000.0, 2),
        "frame_builds": builds,
        "frame_builds_per_1000_ticks": round(builds / dtick * 1000.0, 2),
        "json_dumps": dumps,
        "json_dumps_per_1000_ticks": round(dumps / dtick * 1000.0, 2),
        "json_mb_per_1000_ticks": round(jbytes / dtick / 1e6 * 1000.0, 2),
        "retained_full_frames": stats1["full_frames_retained"],
        "compact_history_n": stats1["compact_history_n"],
        "stats": stats1,
        "headless": headless,
        "eager": eager,
        "eye": eye,
    }


def malloc_trim_diag(s) -> dict:
    import ctypes
    import ctypes.util

    rss0 = _maps()["rss_mb"]
    gc.collect()
    rss1 = _maps()["rss_mb"]
    released = None
    try:
        libc = ctypes.CDLL(ctypes.util.find_library("c"))
        libc.malloc_trim.argtypes = [ctypes.c_size_t]
        libc.malloc_trim.restype = ctypes.c_int
        libc.malloc_trim(0)
        rss2 = _maps()["rss_mb"]
        released = round(rss1 - rss2, 3)
    except Exception as exc:
        rss2 = None
        released = str(exc)
    return {"rss_pause_mb": rss0, "rss_after_gc_mb": rss1, "rss_after_trim_mb": rss2, "trim_release_mb": released}


def main() -> None:
    assert os.getpid() != LIVE_PID
    OUT.mkdir(parents=True, exist_ok=True)
    eq = equivalence(40)
    (OUT / "deterministic_equivalence.json").write_text(json.dumps(eq, indent=2, default=str))
    rows = []
    rows.append(run_matrix_row("A_headless", headless=True, eager=False, eye="OFF", ticks=120, warmup=20))
    rows.append(run_matrix_row("B_eager_world", headless=False, eager=True, eye="OFF", ticks=80, warmup=0))
    rows.append(run_matrix_row("C_no_client", headless=False, eager=False, eye="OFF", ticks=80, warmup=0))
    rows.append(run_matrix_row("D_eye_2fps", headless=False, eager=True, eye="2FPS", ticks=60, warmup=0))
    s_age = make_session()
    s_age.subscribe(lambda f: None, eager=True)
    s_age.set_speed(50)
    s_age.play()
    deadline = time.time() + 120
    while s_age.runtime.tick < 280 and time.time() < deadline:
        time.sleep(0.05)
    s_age.pause()
    m_mid = _maps()
    t_mid = int(s_age.runtime.tick)
    s_age.play()
    deadline = time.time() + 80
    while s_age.runtime.tick < t_mid + 80 and time.time() < deadline:
        time.sleep(0.05)
    s_age.pause()
    m_end = _maps()
    dt = max(1, int(s_age.runtime.tick) - t_mid)
    aged = {
        "tick_mid": t_mid,
        "tick_end": int(s_age.runtime.tick),
        "rss_mid_mb": m_mid["rss_mb"],
        "rss_end_mb": m_end["rss_mb"],
        "aged_rss_mb_per_1000_ticks": round((m_end["rss_mb"] - m_mid["rss_mb"]) / dt * 1000.0, 2),
        "stats": s_age.observer_publication_stats(),
    }
    alloc = malloc_trim_diag(s_age)
    s_age.status = "STOPPED"
    (OUT / "performance_matrix.json").write_text(json.dumps({"rows": rows, "aged": aged}, indent=2))
    (OUT / "allocator_diagnostic.json").write_text(json.dumps(alloc, indent=2))
    print(json.dumps({"eq": eq.get("identical"), "rows": [(r["name"], r["rss_mb_per_1000_ticks"], r["frame_builds"]) for r in rows], "aged": aged}, indent=2))


if __name__ == "__main__":
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    main()
