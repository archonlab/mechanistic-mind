#!/usr/bin/env python3
"""Disposable aged Save/Stop memory verification. Does not touch t10231 forensic dirs.

Usage:
  PYTHONPATH=. .venv_psy_web/bin/python experiments/run_beta3_aged_save_memory.py
"""
from __future__ import annotations

import gc
import json
import os
import resource
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "beta3_aged_save_memory"
FORENSIC_LIVE = (
    ROOT / "results/psychology_observer/psy_observer_web"
    / ".live-psyweb-20260922T192322.056455Z-f9b24837"
)
RSS_ABORT_KB = int(os.environ.get("P0_SAVE_RSS_ABORT_KB", str(6 * 1024 * 1024)))  # 6 GiB


def _rss_vm_kb(pid: int | None = None) -> tuple[int, int]:
    path = f"/proc/{pid or os.getpid()}/status"
    rss = vm = 0
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("VmRSS:"):
                rss = int(line.split()[1])
            elif line.startswith("VmSize:"):
                vm = int(line.split()[1])
    return rss, vm


def _kb_mb(kb: int) -> float:
    return round(kb / 1024.0, 2)


def _beta3_cfg():
    from mechanistic_mind.model.tiktaalik import tiktaalik_config

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
    return cfg


def _pe_stats(eq: dict) -> dict[str, int]:
    classes = eq.get("classes") or {}
    return {
        "total": len(classes),
        "active": sum(1 for c in classes.values() if isinstance(c, dict) and c.get("status") == "ACTIVE"),
        "forgotten": sum(1 for c in classes.values() if isinstance(c, dict) and c.get("status") == "FORGOTTEN"),
    }


def _fill_cognition(runtime, *, extra_forgotten: int) -> dict[str, Any]:
    from mechanistic_mind.physical_system import sensorimotor_consequence as smc
    from mechanistic_mind.research import predictive_compression as pc
    from mechanistic_mind.research import predictive_equivalence as pe
    from mechanistic_mind.research import prospective_composition as pr

    stats = []
    for slot in runtime.slots:
        eq = slot.cognition.setdefault("equivalence", pe.empty_store())
        eq["enabled"] = True
        n = pe.MAX_CLASSES + int(extra_forgotten)
        for i in range(n):
            pe.learn(
                eq,
                fragment={f"k{j}": float(i) + 0.01 * j for j in range(10)},
                action=f"A{i % 7}",
                consequent={"out": float(i) * 1.31, "y": 0.01 * (i % 9)},
                tick=i,
            )
        temporal = slot.cognition.setdefault("temporal", {})
        inner = temporal.setdefault("inner", pe.empty_store())
        inner["enabled"] = True
        for i in range(pe.MAX_CLASSES + max(8, extra_forgotten // 2)):
            pe.learn(
                inner,
                fragment={f"t{j}": float(i) * 0.17 + 0.001 * j for j in range(8)},
                action="WAIT" if i % 2 == 0 else "MOVE:N",
                consequent={"z": float(i % 50)},
                tick=i,
            )
        store = slot.cognition.setdefault(
            "sensorimotor_consequence", smc.empty_store(enabled=True, capacity=256)
        )
        store["enabled"] = True
        locos = ["WAIT", "MOVE:N", "MOVE:S", "MOVE:E", "MOVE:W"]
        t = 0
        while len(store.get("records") or {}) < 256 and t < 5000:
            obs = {k: 0.2 for k in smc.SENSORY_CHANNELS[:10]}
            obs["exo_0"] = ((t % 5) + 0.5) / 5.0
            obs["exo_1"] = (((t // 5) % 5) + 0.5) / 5.0
            obs["exo_2"] = (((t // 25) % 5) + 0.5) / 5.0
            nxt = dict(obs)
            nxt["exo_0"] = ((t % 4) + 0.5) / 5.0
            smc.update(
                store,
                tick=t,
                observation_t=obs,
                motor={
                    "locomotion": locos[t % 5],
                    "neck": "NONE",
                    "oscillator": {"emit_trigger": bool(t % 3 == 0)},
                    "push": bool(t % 7 == 0),
                },
                observation_t1=nxt,
            )
            t += 1
        mem = slot.cognition.setdefault("compression", pc.empty_memory())
        for i in range(220):
            frag = {f"c{j}": 0.01 * ((i + j) % 17) for j in range(16)}
            pc.observe(mem, tick=i, fragment=frag, action=f"A{i % 5}", realized={**frag, "c0": frag["c0"] + 0.02})
        prosp = slot.cognition.setdefault("prospection", pr.empty_store())
        p = 0
        while len(prosp.get("transitions") or {}) < pr.MAX_TRANSITIONS and p < 4000:
            ant = {f"q{j}": (((p // (5 ** j)) % 5) + 0.5) / 5.0 for j in range(6)}
            cons = {f"q{j}": (((p // (5 ** ((j + 1) % 6))) % 5) + 0.5) / 5.0 for j in range(6)}
            pr.learn_transition(
                prosp,
                tick=p,
                antecedent=ant,
                action=f"A{p % 5}",
                consequent=cons,
            )
            p += 1
        rss, _ = _rss_vm_kb()
        if rss > RSS_ABORT_KB:
            raise RuntimeError(f"abort fill: RSS {rss} kB exceeds {RSS_ABORT_KB}")
        stats.append({
            "pe": _pe_stats(eq),
            "tps_inner": _pe_stats(inner),
            "smc": len(store.get("records") or {}),
            "compression_structures": len(mem.get("structures") or {}),
            "prospection_transitions": len(prosp.get("transitions") or {}),
        })
    return {"agents": stats}


def _write_jsonl(live: Path, *, lines: int, bytes_per_line: int = 180) -> int:
    live.mkdir(parents=True, exist_ok=True)
    pad = "x" * max(8, bytes_per_line - 40)
    (live / "scientific_meta.json").write_text(
        json.dumps({"run_id": "aged-mem-test", "last_tick_written": max(0, lines - 1), "rows_written": lines}),
        encoding="utf-8",
    )
    written = 0
    with (live / "scientific_timeline.jsonl").open("w", encoding="utf-8") as fh:
        for i in range(lines):
            row = json.dumps({"tick": i, "kind": "TIMELINE", "pad": pad})
            fh.write(row + "\n")
            written += len(row) + 1
    with (live / "scientific_decisions.jsonl").open("w", encoding="utf-8") as fh:
        for i in range(min(lines, max(50, lines // 4))):
            fh.write(json.dumps({"tick": i, "kind": "DECISION", "n": i}) + "\n")
    return written


def _scan_save_path() -> dict[str, Any]:
    rf = (ROOT / "mechanistic_mind/ui/psy_observer_web/run_finalize.py").read_text(encoding="utf-8")
    sess = (ROOT / "mechanistic_mind/ui/psy_observer_web/session.py").read_text(encoding="utf-8")
    rt = (ROOT / "mechanistic_mind/physical_system/runtime.py").read_text(encoding="utf-8")
    sh = (ROOT / "mechanistic_mind/ui/psy_observer_web/scientific_history.py").read_text(encoding="utf-8")
    return {
        "json.dumps(snapshot)": "json.dumps(snapshot" in rf,
        "json.dump(prepared)": "json.dump(prepared" in rf,
        "json_prepare_defined": "def json_prepare" in rf,
        "BytesIO_in_run_finalize": "BytesIO" in rf,
        "StringIO_in_run_finalize": "StringIO" in rf,
        "session_compact_wait_false": "_compact_stop_frame" in sess,
        "json.loads_snapshot_file_in_write_finalized_run": (
            'json.loads((tmp_dir / "physical_system_snapshot.json")' in rf
        ),
        "snapshot_file_read_text_in_write_finalized_run": "physical_system_snapshot.json\").read_text" in rf,
        "deepcopy_cognition_in_PhysicalSystemRuntime.snapshot": "cognition = deepcopy(self.cognition)" in rt,
        "copy_scientific_into_uses_copy2": "shutil.copy2(src, dst)" in sh,
        "read_run_snapshot_loads_full_file": "def read_run_snapshot" in rf,
    }


def child_run(label: str, spec: dict[str, Any], dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    from mechanistic_mind.physical_system import TwoAgentRuntime
    from mechanistic_mind.research import predictive_equivalence as pe
    from mechanistic_mind.physical_system import sensorimotor_consequence as smc
    from mechanistic_mind.ui.psy_observer_web.run_finalize import write_finalized_run, read_run_snapshot

    samples: list[dict[str, Any]] = []
    stop_samp = False

    def sampler():
        while not stop_samp:
            rss, vm = _rss_vm_kb()
            samples.append({"t": time.monotonic(), "rss_kb": rss, "vm_kb": vm})
            time.sleep(0.02)

    th = threading.Thread(target=sampler, daemon=True)
    th.start()
    t_build0 = time.perf_counter()
    rt = TwoAgentRuntime(seed=int(spec.get("seed", 901)), config=_beta3_cfg())
    for _ in range(int(spec.get("steps", 8))):
        rt.step()
    occ = _fill_cognition(rt, extra_forgotten=int(spec["extra_forgotten"]))
    live = dest / "live"
    jsonl_bytes = _write_jsonl(live, lines=int(spec["jsonl_lines"]), bytes_per_line=int(spec.get("jsonl_pad", 180)))
    gc.collect()
    rss_before, vm_before = _rss_vm_kb()
    snap_t0 = time.perf_counter()
    # Isolate snapshot() allocation vs dump: optional
    result_path = dest / "child_result.json"
    tmp_watch = dest / "tmp_watch.txt"
    peak_part = [0]

    def watch_tmp():
        root = dest / "psychology_observer" / "psy_observer_web"
        while not stop_samp:
            peak = 0
            if root.is_dir():
                for p in root.rglob("*"):
                    if p.is_file() and (p.suffix == ".part" or ".tmp-" in p.as_posix()):
                        try:
                            peak = max(peak, p.stat().st_size)
                        except OSError:
                            pass
            peak_part[0] = max(peak_part[0], peak)
            time.sleep(0.05)

    tw = threading.Thread(target=watch_tmp, daemon=True)
    tw.start()
    t0 = time.perf_counter()
    result = write_finalized_run(
        results_root=dest,
        runtime=rt,
        session_meta={"started_at": "2026-09-23T00:00:00Z", "seed": int(spec.get("seed", 901)), "buffer": {}},
        timeline=[{"tick": int(rt.tick), "status": "RUNNING"}],
        telemetry=[{"tick": int(rt.tick), "sim_ticks_per_sec": 1.0}],
        termination_reason="USER_STOP_SAVED",
        run_id=f"aged-mem-{label.lower()}",
        scientific_live_dir=live,
    )
    t1 = time.perf_counter()
    rss_after, vm_after = _rss_vm_kb()
    gc.collect()
    rss_gc, vm_gc = _rss_vm_kb()
    stop_samp = True
    th.join(timeout=1.0)
    peak_rss = max([rss_before] + [s["rss_kb"] for s in samples] + [rss_after])
    peak_vm = max([vm_before] + [s["vm_kb"] for s in samples] + [vm_after])
    (dest / "save_metrics.json").write_text(
        json.dumps(
            {
                "label": label,
                "save_accepted": bool(result.get("accepted")),
                "rss_before_mb": _kb_mb(rss_before),
                "peak_rss_mb": _kb_mb(peak_rss),
                "rss_after_mb": _kb_mb(rss_after),
                "rss_gc_mb": _kb_mb(rss_gc),
                "vm_before_mb": _kb_mb(vm_before),
                "peak_vm_mb": _kb_mb(peak_vm),
                "vm_after_mb": _kb_mb(vm_after),
                "save_s": round(t1 - t0, 3),
                "run_dir": result.get("run_dir"),
                "error": result.get("error"),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    restore_ok = False
    p0_ok = False
    step_ok = False
    snap_file = None
    snap_size = 0
    if result.get("accepted") and result.get("run_dir"):
        run_dir = Path(result["run_dir"])
        snap_file = run_dir / "physical_system_snapshot.json"
        snap_size = snap_file.stat().st_size if snap_file.is_file() else 0
        payload = read_run_snapshot(run_dir)
        restored = TwoAgentRuntime.restore(payload)
        restore_ok = int(restored.tick) == int(rt.tick) and len(restored.slots) == 2
        for slot in restored.slots:
            eq = slot.cognition.get("equivalence") or {}
            pe.ensure_class_indexes(eq)
            assert pe.active_class_count(eq) == pe.scan_active_class_count(eq)
            smc_st = slot.cognition.get("sensorimotor_consequence") or {}
            if smc_st:
                smc.ensure_indexes(smc_st)
        p0_ok = True
        restored.step()
        step_ok = int(restored.tick) == int(rt.tick) + 1

    dt = t1 - t0
    out = {
        "label": label,
        "spec": spec,
        "occupancy": occ,
        "tick": int(rt.tick),
        "save_accepted": bool(result.get("accepted")),
        "run_dir": result.get("run_dir"),
        "phases": result.get("phases"),
        "error": result.get("error"),
        "rss_before_mb": _kb_mb(rss_before),
        "rss_after_mb": _kb_mb(rss_after),
        "rss_gc_mb": _kb_mb(rss_gc),
        "peak_rss_mb": _kb_mb(peak_rss),
        "delta_rss_mb": _kb_mb(peak_rss - rss_before),
        "vm_before_mb": _kb_mb(vm_before),
        "vm_after_mb": _kb_mb(vm_after),
        "vm_gc_mb": _kb_mb(vm_gc),
        "peak_vm_mb": _kb_mb(peak_vm),
        "save_s": round(dt, 3),
        "build_s": round(snap_t0 - t_build0, 3),
        "snapshot_file_bytes": snap_size,
        "snapshot_file_mb": round(snap_size / 1e6, 3),
        "jsonl_source_bytes": jsonl_bytes,
        "tmp_part_peak_bytes": peak_part[0],
        "write_mb_s": round((snap_size / 1e6) / dt, 3) if dt > 0 else None,
        "amplification_vs_file": round((peak_rss - rss_before) * 1024 / max(1, snap_size), 3),
        "peak_over_baseline": round(peak_rss / max(1, rss_before), 3),
        "restore_ok": restore_ok,
        "p0_index_rebuild_ok": p0_ok,
        "post_restore_step_ok": step_ok,
        "persist_timings": result.get("persist_timings"),
        "n_rss_samples": len(samples),
        "ru_maxrss_kb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }
    result_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2), flush=True)


def parent_run_label(label: str, spec: dict[str, Any]) -> dict[str, Any]:
    dest = OUT / label.lower()
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--child",
        "--label",
        label,
        "--spec",
        json.dumps(spec),
        "--dest",
        str(dest),
    ]
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.Popen(
        cmd,
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    peak_rss = peak_vm = 0
    while proc.poll() is None:
        try:
            rss, vm = _rss_vm_kb(proc.pid)
            peak_rss = max(peak_rss, rss)
            peak_vm = max(peak_vm, vm)
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            break
        time.sleep(0.03)
    stdout, stderr = proc.communicate(timeout=30)
    child_file = dest / "child_result.json"
    child = json.loads(child_file.read_text(encoding="utf-8")) if child_file.is_file() else {}
    child["parent_peak_rss_mb"] = _kb_mb(peak_rss)
    child["parent_peak_vm_mb"] = _kb_mb(peak_vm)
    child["child_exit"] = proc.returncode
    child["stderr_tail"] = (stderr or "")[-4000:]
    if proc.returncode != 0 and not child.get("save_accepted"):
        child["label"] = label
        child["save_accepted"] = False
        child["error"] = child.get("error") or f"child_exit={proc.returncode}"
    (dest / "parent_wrap.json").write_text(json.dumps(child, indent=2), encoding="utf-8")
    print(f"=== {label} parent_peak_rss_mb={child.get('parent_peak_rss_mb')} accepted={child.get('save_accepted')} ===", flush=True)
    return child


def run_async_api(dest: Path) -> dict[str, Any]:
    from fastapi.testclient import TestClient
    from mechanistic_mind.ui.psy_observer_web.server import app
    from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig
    import mechanistic_mind.ui.psy_observer_web.session as sessmod

    dest.mkdir(parents=True, exist_ok=True)
    session = ObserverSession(SessionConfig(seed=44, buffer_capacity=32, ui_hz=8, results_root=dest))
    import mechanistic_mind.ui.psy_observer_web.server as server
    orig_get = server.get_session
    server.get_session = lambda: session  # type: ignore[method-assign]
    gate = threading.Event()
    real = sessmod.write_finalized_run

    def slow(**kwargs):
        t0 = time.perf_counter()
        while time.perf_counter() - t0 < 0.35:
            time.sleep(0.02)
        gate.set()
        return real(**kwargs)

    sessmod.write_finalized_run = slow  # type: ignore[method-assign]
    try:
        c = TestClient(app)
        c.post("/api/control/step", json={"n": 4})
        t0 = time.perf_counter()
        started = c.post("/api/control/stop", json={"save": True, "wait": False, "reason": "USER_STOP_SAVED"}).json()
        post_s = time.perf_counter() - t0
        mid = c.get("/api/control/save-job").json()
        deadline = time.monotonic() + 20
        terminal = mid
        while time.monotonic() < deadline:
            terminal = c.get("/api/control/save-job").json()
            if terminal.get("lifecycle") in {"STOPPED", "SAVE_FAILED"}:
                break
            time.sleep(0.05)
        return {
            "post_wait_false_s": round(post_s, 4),
            "post_returned_before_save_done": post_s < 0.3 or started.get("finalize", {}).get("pending") is True,
            "start_lifecycle": started.get("header", {}).get("status") or session.status,
            "mid_pending": bool(mid.get("pending")),
            "terminal_lifecycle": terminal.get("lifecycle"),
            "terminal_save": terminal.get("save"),
            "phases": terminal.get("phases") or started.get("finalize", {}).get("phases"),
            "job_id": started.get("finalize", {}).get("job_id") or terminal.get("job_id"),
        }
    finally:
        sessmod.write_finalized_run = real
        server.get_session = orig_get
        try:
            session.stop(save=False, reason="USER_STOP_NO_SAVE")
        except Exception:
            pass


def run_failure(dest: Path) -> dict[str, Any]:
    from fastapi.testclient import TestClient
    from mechanistic_mind.ui.psy_observer_web.server import app
    from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig
    import mechanistic_mind.ui.psy_observer_web.session as sessmod
    import mechanistic_mind.ui.psy_observer_web.server as server

    dest.mkdir(parents=True, exist_ok=True)
    session = ObserverSession(SessionConfig(seed=45, buffer_capacity=16, ui_hz=8, results_root=dest))
    orig_get = server.get_session
    server.get_session = lambda: session  # type: ignore[method-assign]

    def boom(**kwargs):
        raise MemoryError("injected aged-save verification")

    orig = sessmod.write_finalized_run
    sessmod.write_finalized_run = boom  # type: ignore[method-assign]
    try:
        c = TestClient(app)
        c.post("/api/control/step", json={"n": 3})
        out = c.post("/api/control/stop", json={"save": True, "wait": True}).json()
        job = c.get("/api/control/save-job").json()
        published = list((dest / "psychology_observer" / "psy_observer_web").glob("psyweb-*")) if (dest / "psychology_observer").exists() else []
        published = [p for p in published if p.is_dir() and (p / "run.json").is_file()]
        return {
            "session_status": session.status,
            "not_finalizing": session.status != "FINALIZING",
            "save_failed": session.status == "SAVE_FAILED",
            "finalize_accepted": out.get("finalize", {}).get("accepted"),
            "error": out.get("finalize", {}).get("error"),
            "job_lifecycle": job.get("lifecycle"),
            "job_save_layer": job.get("layers", {}).get("save"),
            "job_http_layer": job.get("layers", {}).get("http"),
            "published_runs": len(published),
            "runtime_tick": int(session.runtime.tick),
        }
    finally:
        sessmod.write_finalized_run = orig
        server.get_session = orig_get


def run_repeat(spec: dict[str, Any], dest: Path) -> dict[str, Any]:
    from mechanistic_mind.physical_system import TwoAgentRuntime
    from mechanistic_mind.ui.psy_observer_web.run_finalize import write_finalized_run

    dest.mkdir(parents=True, exist_ok=True)
    rt = TwoAgentRuntime(seed=46, config=_beta3_cfg())
    for _ in range(6):
        rt.step()
    _fill_cognition(rt, extra_forgotten=int(spec["extra_forgotten"]))
    live = dest / "live"
    _write_jsonl(live, lines=int(spec["jsonl_lines"]))
    gc.collect()
    rss = []
    for i in range(3):
        gc.collect()
        a, _ = _rss_vm_kb()
        write_finalized_run(
            results_root=dest,
            runtime=rt,
            session_meta={"seed": 46, "buffer": {}},
            timeline=[],
            telemetry=[],
            termination_reason="USER_STOP_SAVED",
            run_id=f"repeat-{i}",
            scientific_live_dir=live if i == 0 else None,
        )
        gc.collect()
        b, _ = _rss_vm_kb()
        rss.append({"i": i, "before_mb": _kb_mb(a), "after_gc_mb": _kb_mb(b)})
    growth = rss[-1]["after_gc_mb"] - rss[0]["before_mb"]
    return {"samples": rss, "after_minus_first_before_mb": round(growth, 2)}


def main() -> None:
    if "--child" in sys.argv:
        argv = sys.argv
        label = argv[argv.index("--label") + 1]
        spec = json.loads(argv[argv.index("--spec") + 1])
        dest = Path(argv[argv.index("--dest") + 1])
        child_run(label, spec, dest)
        return

    OUT.mkdir(parents=True, exist_ok=True)
    assert FORENSIC_LIVE.is_dir(), "forensic live dir missing; do not proceed blindly"
    sizes = {
        "SMALL": {"extra_forgotten": 0, "jsonl_lines": 40, "steps": 6, "seed": 11},
        "MEDIUM": {"extra_forgotten": 400, "jsonl_lines": 4000, "steps": 12, "seed": 22, "jsonl_pad": 200},
        "AGED": {"extra_forgotten": 6000, "jsonl_lines": 25000, "steps": 16, "seed": 33, "jsonl_pad": 220},
        "EXTREME": {"extra_forgotten": 14000, "jsonl_lines": 40000, "steps": 16, "seed": 44, "jsonl_pad": 240},
    }
    mem = Path("/proc/meminfo").read_text(encoding="utf-8")
    avail_kb = 0
    for line in mem.splitlines():
        if line.startswith("MemAvailable:"):
            avail_kb = int(line.split()[1])
    if avail_kb < 8 * 1024 * 1024:
        sizes.pop("EXTREME", None)

    scan = _scan_save_path()
    table = {}
    for label, spec in sizes.items():
        table[label] = parent_run_label(label, spec)

    async_r = run_async_api(OUT / "async_api")
    fail_r = run_failure(OUT / "failure")
    repeat_r = run_repeat(sizes["MEDIUM"], OUT / "repeat")

    summary = {
        "forensic_live_untouched": FORENSIC_LIVE.is_dir(),
        "save_path_scan": scan,
        "sizes": table,
        "async_api": async_r,
        "controlled_failure": fail_r,
        "repeat_save": repeat_r,
        "memavailable_mb": _kb_mb(avail_kb),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({k: (v.get("peak_rss_mb"), v.get("delta_rss_mb"), v.get("snapshot_file_mb"), v.get("save_accepted")) if isinstance(v, dict) else v for k, v in table.items()}, indent=2))
    print("async", async_r)
    print("failure", fail_r)
    print("repeat", repeat_r)
    print("wrote", OUT / "summary.json")


if __name__ == "__main__":
    main()
