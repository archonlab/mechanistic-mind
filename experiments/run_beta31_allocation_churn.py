#!/usr/bin/env python3
"""BETA31 allocation-churn forensic — reproduction process only.

Never attaches to, POSTs to, trims, or restarts live PID 368895.
"""
from __future__ import annotations

import gc
import json
import os
import resource
import subprocess
import sys
import tempfile
import time
import traceback
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "beta31_live_memory_forensic"
LIVE_PID = 368895
WARMUP = int(os.environ.get("PSY_CHURN_WARMUP", "20"))
WINDOW = int(os.environ.get("PSY_CHURN_WINDOW", "50"))
CONDITIONS = (
    "A_full",
    "B_v3_off",
    "C_no_observer_frame",
    "D_fpv_off",
    "E_headless",
    "F_v3_capture_no_write",
    "F2_v3_encode_no_write",
    "G_spatial_legacy",
)


def _kb(path: Path, key: str) -> int:
    try:
        for line in path.read_text().splitlines():
            if line.startswith(key):
                return int(line.split()[1])
    except OSError:
        return 0
    return 0


def proc_maps(pid: int) -> dict:
    st = Path(f"/proc/{pid}/status")
    rss_kb = _kb(st, "VmRSS:")
    anon_st = _kb(st, "RssAnon:")
    file_st = _kb(st, "RssFile:")
    maps = 0
    large = 0
    large_rss_kb = 0
    private_dirty_kb = 0
    anon_kb = 0
    heap_anon_kb = 0
    cur_is_anon = False
    cur_size = 0
    cur_name = ""
    smaps = Path(f"/proc/{pid}/smaps")
    try:
        text = smaps.read_text()
    except OSError:
        text = ""
    for line in text.splitlines():
        if line and not line[0].isspace() and "-" in line[:20] and "kB" not in line:
            parts = line.split()
            cur_name = parts[-1] if parts else ""
            maps += 1
            try:
                a, b = parts[0].split("-", 1)
                cur_size = int(b, 16) - int(a, 16)
            except Exception:
                cur_size = 0
            cur_is_anon = (len(parts) >= 6 and parts[4] == "0" and (
                cur_name in ("", "[heap]", "[anon]") or cur_name.startswith("[anon:")
                or (len(parts) == 5)
            ))
            if cur_name in ("", "[heap]") or "anon" in cur_name.lower() or len(parts) == 5:
                cur_is_anon = True
            if parts[1].startswith("rw") and cur_name.startswith("/"):
                cur_is_anon = False
        elif line.startswith("Anonymous:"):
            v = int(line.split()[1])
            anon_kb += v
            if cur_name == "[heap]":
                heap_anon_kb += v
        elif line.startswith("Private_Dirty:"):
            v = int(line.split()[1])
            private_dirty_kb += v
            if cur_size >= 64 * 1024 * 1024 and not str(cur_name).startswith("/"):
                large += 1
                large_rss_kb += v
    roll = {}
    rp = Path(f"/proc/{pid}/smaps_rollup")
    try:
        for line in rp.read_text().splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                roll[k.strip()] = v.strip()
    except OSError:
        pass
    return {
        "rss_mb": round(rss_kb / 1024.0, 3),
        "rss_anon_mb": round(anon_st / 1024.0, 3),
        "rss_file_mb": round(file_st / 1024.0, 3),
        "smaps_anon_mb": round(anon_kb / 1024.0, 3),
        "smaps_heap_anon_mb": round(heap_anon_kb / 1024.0, 3),
        "private_dirty_mb": round(private_dirty_kb / 1024.0, 3),
        "mappings": maps,
        "large_anon_ge_64mb": large,
        "large_anon_private_dirty_mb": round(large_rss_kb / 1024.0, 3),
        "rollup_anonymous_mb": round(int(str(roll.get("Anonymous", "0")).split()[0] or 0) / 1024.0, 3) if roll else None,
        "rollup_private_dirty_mb": round(int(str(roll.get("Private_Dirty", "0")).split()[0] or 0) / 1024.0, 3) if roll else None,
    }


def allocator_identity() -> dict:
    import ctypes
    import ctypes.util

    py = Path(sys.executable).resolve()
    ldd = ""
    try:
        ldd = subprocess.check_output(["ldd", str(py)], text=True, stderr=subprocess.DEVNULL)
    except Exception as exc:
        ldd = str(exc)
    maps = Path("/proc/self/maps").read_text()
    libs = []
    for needle in ("jemalloc", "tcmalloc", "mimalloc", "libhoard", "libtbbmalloc", "libc.so"):
        if needle in maps or needle in ldd:
            libs.append(needle)
    malloc_info = None
    try:
        libc = ctypes.CDLL(ctypes.util.find_library("c"))
        libc.malloc_info.argtypes = [ctypes.c_int, ctypes.c_void_p]
        libc.malloc_info.restype = ctypes.c_int
        libc.fopen.restype = ctypes.c_void_p
        libc.fopen.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        libc.fclose.argtypes = [ctypes.c_void_p]
        tmp = tempfile.NamedTemporaryFile(prefix="malloc_info_", suffix=".xml", delete=False)
        tmp.close()
        fp = libc.fopen(tmp.name.encode(), b"w")
        if fp:
            libc.malloc_info(0, fp)
            libc.fclose(fp)
            malloc_info = Path(tmp.name).read_text()[:4000]
        Path(tmp.name).unlink(missing_ok=True)
    except Exception as exc:
        malloc_info = f"error:{exc}"
    return {
        "python": sys.version,
        "pythonmalloc_env": os.environ.get("PYTHONMALLOC"),
        "malloc_arena_max": os.environ.get("MALLOC_ARENA_MAX"),
        "ldd": ldd,
        "maps_allocators": libs,
        "malloc_info_head": malloc_info,
        "pymalloc": hasattr(sys, "_debugmallocstats"),
    }


def malloc_trim() -> int:
    import ctypes
    import ctypes.util

    libc = ctypes.CDLL(ctypes.util.find_library("c"))
    libc.malloc_trim.argtypes = [ctypes.c_size_t]
    libc.malloc_trim.restype = ctypes.c_int
    return int(libc.malloc_trim(0))


_ORIG_DUMPS = json.dumps


def _estimate_bytes(obj) -> int:
    try:
        return len(_ORIG_DUMPS(obj, default=str, separators=(",", ":")))
    except Exception:
        return 0


def configure_session(condition: str, results_root: Path, spatial: str):
    from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig

    cfg = SessionConfig(
        seed=373,
        evidence_mode="SEARCH_COMPACT" if condition == "B_v3_off" else "FULL_SCIENTIFIC",
        buffer_capacity=512,
        ui_hz=4.0,
        results_root=results_root,
        execution_mode="HEADLESS" if condition == "E_headless" else "LIVE",
    )
    sess = ObserverSession(cfg)
    sess.apply_experiment({"seed": 373, "agent_count": 2, "cognition_enabled": True})
    try:
        sess.set_spatial_vision(spatial)
    except Exception:
        pass
    try:
        sess.set_vision_radius(3)
    except Exception:
        pass
    try:
        sess.set_visual_surface_discrimination("RICH")
    except Exception:
        pass
    fpv_on = condition not in ("D_fpv_off", "E_headless")
    try:
        sess.set_tiktaalik_eye(rate="2FPS" if fpv_on else "OFF", fpv=fpv_on)
    except Exception:
        pass
    if condition == "E_headless":
        try:
            sess.set_execution_mode("HEADLESS")
        except Exception:
            pass
    return sess


def install_hooks(condition: str, counters: dict) -> None:
    import json as json_mod

    from mechanistic_mind.scientific_v3 import capture as cap
    from mechanistic_mind.scientific_v3 import writer as wr
    from mechanistic_mind.ui.psy_observer_web import serialize as ser
    from mechanistic_mind.ui.psy_observer_web import session as sessmod
    from mechanistic_mind.ui.psy_observer_web import tiktaalik_eye as eye

    orig_dumps = json_mod.dumps
    global _ORIG_DUMPS
    _ORIG_DUMPS = orig_dumps
    orig_capture = cap.capture_v3_tick
    orig_jsonl = wr._jsonl_line
    orig_live = ser.live_frame
    orig_world = ser.world_frame
    orig_compact_obs = None
    from mechanistic_mind.scientific_v3 import receipts as rec

    orig_compact_obs = rec.compact_accessible_observation
    orig_eye = getattr(eye, "build_tiktaalik_eye_payload", None) or getattr(eye, "capture_eye", None)

    def dumps_h(*a, **k):
        s = orig_dumps(*a, **k)
        n = len(s) if isinstance(s, str) else 0
        counters["json_dumps_calls"] += 1
        counters["json_dumps_bytes"] += n
        stack = traceback.extract_stack(limit=12)
        site = "other"
        joined = "".join(f.filename for f in stack)
        if "scientific_v3/writer" in joined or "scientific_v3\\writer" in joined:
            site = "v3_writer"
        elif "scientific_v3/receipts" in joined:
            site = "v3_receipts_hash"
        elif "scientific_v3/capture" in joined:
            site = "v3_capture"
        elif "scientific_history" in joined:
            site = "v2_history"
        elif "serialize.py" in joined:
            site = "observer_serialize"
        elif "session.py" in joined:
            site = "observer_session"
        elif "tiktaalik_eye" in joined:
            site = "fpv_eye"
        elif "server.py" in joined:
            site = "websocket"
        counters[f"json_bytes:{site}"] += n
        counters[f"json_calls:{site}"] += 1
        counters["json_max"] = max(counters["json_max"], n)
        return s

    json_mod.dumps = dumps_h
    wr.json.dumps = dumps_h
    rec.json.dumps = dumps_h
    sessmod.json.dumps = dumps_h

    def cap_h(*a, **k):
        pkg = orig_capture(*a, **k)
        counters["v3_capture_calls"] += 1
        for key in ("spines", "observations", "decisions", "motors", "consequences"):
            rows = pkg.get(key) or []
            counters[f"v3_{key}_n"] += len(rows)
            counters[f"v3_{key}_bytes"] += sum(_estimate_bytes(r) for r in rows)
        return pkg

    cap.capture_v3_tick = cap_h
    wr.capture_v3_tick = cap_h

    def jsonl_h(obj):
        s = orig_jsonl(obj)
        counters["v3_jsonl_lines"] += 1
        counters["v3_jsonl_bytes"] += len(s)
        counters["v3_jsonl_max"] = max(counters["v3_jsonl_max"], len(s))
        return s

    wr._jsonl_line = jsonl_h

    orig_append = wr.ScientificV3Writer.append_runtime_tick

    def append_h(self, runtime):
        if condition == "F_v3_capture_no_write":
            cap.capture_v3_tick(
                runtime,
                run_id=self._run_id or "repro",
                identity_map=self._identity_map,
                generation=self._generation,
            )
            counters["v3_capture_only"] += 1
            return 0
        if condition == "F2_v3_encode_no_write":
            pkg = cap.capture_v3_tick(
                runtime,
                run_id=self._run_id or "repro",
                identity_map=self._identity_map,
                generation=self._generation,
            )
            n = 0
            for key in ("spines", "observations", "decisions", "motors", "consequences"):
                for row in pkg.get(key) or []:
                    wr._jsonl_line(row)
                    n += 1
            counters["v3_encode_only_lines"] += n
            return 0
        return orig_append(self, runtime)

    wr.ScientificV3Writer.append_runtime_tick = append_h

    def live_h(*a, **k):
        counters["live_frame_calls"] += 1
        fr = orig_live(*a, **k)
        counters["live_frame_bytes"] += _estimate_bytes(fr)
        return fr

    def world_h(*a, **k):
        counters["world_frame_calls"] += 1
        return orig_world(*a, **k)

    ser.live_frame = live_h
    ser.world_frame = world_h
    sessmod.live_frame = live_h

    def compact_h(obs):
        counters["compact_obs_calls"] += 1
        out = orig_compact_obs(obs)
        counters["compact_obs_keys"] += len(out)
        return out

    rec.compact_accessible_observation = compact_h
    cap.compact_accessible_observation = compact_h

    if condition in ("C_no_observer_frame", "E_headless"):
        def skip_capture(self, detail="compact"):
            counters["skipped_capture"] += 1
            tick = int(getattr(self.runtime, "tick", 0) or 0)
            return {"header": {"tick": tick, "status": "SKIPPED_FOR_FORENSIC"}}

        sessmod.ObserverSession._capture_locked = skip_capture
        sessmod.ObserverSession._serialize_published = lambda self, frame: None
        sessmod.ObserverSession._maybe_push = lambda self, *a, **k: None

    orig_flush = wr.ScientificV3Writer._flush_unlocked

    def flush_h(self):
        n = sum(len(v) for v in self._bufs.values())
        b = sum(len(x) for buf in self._bufs.values() for x in buf)
        counters["v3_flush_calls"] += 1
        counters["v3_flush_lines"] += n
        counters["v3_flush_buf_bytes"] += b
        return orig_flush(self)

    wr.ScientificV3Writer._flush_unlocked = flush_h


def run_condition(condition: str) -> dict:
    assert os.getpid() != LIVE_PID
    spatial = "LEGACY" if condition == "G_spatial_legacy" else "OCCLUSION"
    tmp = Path(tempfile.mkdtemp(prefix=f"churn_{condition}_"))
    counters = defaultdict(int)
    install_hooks(condition, counters)
    sess = configure_session(condition, tmp, spatial)
    pid = os.getpid()
    for _ in range(WARMUP):
        sess.step(1)
    gc.collect()
    t0 = time.perf_counter()
    m0 = proc_maps(pid)
    blocks0 = sys.getallocatedblocks() if hasattr(sys, "getallocatedblocks") else None
    import tracemalloc

    if not tracemalloc.is_tracing():
        tracemalloc.start(6)
    tracemalloc.reset_peak()
    cur0, _ = tracemalloc.get_traced_memory()
    peaks = []
    for i in range(WINDOW):
        tracemalloc.reset_peak()
        b0 = sys.getallocatedblocks() if hasattr(sys, "getallocatedblocks") else 0
        sess.step(1)
        _, peak = tracemalloc.get_traced_memory()
        b1 = sys.getallocatedblocks() if hasattr(sys, "getallocatedblocks") else 0
        peaks.append({"peak_traced": peak, "d_blocks": (b1 - b0) if b1 and b0 else None})
    wall = time.perf_counter() - t0
    cur1, peak_win = tracemalloc.get_traced_memory()
    snap = tracemalloc.take_snapshot()
    top = []
    for st in snap.statistics("filename")[:15]:
        top.append({
            "file": str(st.traceback[0]) if st.traceback else "",
            "size_mb": round(st.size / 1e6, 4),
            "count": st.count,
        })
    tracemalloc.stop()
    m1 = proc_maps(pid)
    blocks1 = sys.getallocatedblocks() if hasattr(sys, "getallocatedblocks") else None
    tps = WINDOW / wall if wall > 0 else None
    dtick = WINDOW
    drss = m1["rss_mb"] - m0["rss_mb"]
    danon = m1["rss_anon_mb"] - m0["rss_anon_mb"]
    ddirty = m1["private_dirty_mb"] - m0["private_dirty_mb"]

    # V3 path sizes on last tick if writer present
    v3_trace = None
    v3w = getattr(sess, "_v3_writer", None)
    if v3w is not None and condition.startswith("A"):
        from mechanistic_mind.scientific_v3.capture import capture_v3_tick

        pkg = capture_v3_tick(
            sess.runtime,
            run_id=v3w._run_id or "repro",
            identity_map=v3w._identity_map,
            generation=v3w._generation,
        )
        stages = {}
        for key in ("spines", "observations", "decisions", "motors", "consequences"):
            rows = pkg.get(key) or []
            dumped = [json.dumps(r, ensure_ascii=False, separators=(",", ":"), default=str) for r in rows]
            stages[key] = {
                "n": len(rows),
                "receipt_json_bytes": sum(len(s) for s in dumped),
                "max_line": max((len(s) for s in dumped), default=0),
            }
        # copies: receipt dict → dumps str → encode on write
        stages["intermediate_reps"] = [
            "runtime last_selection / last_agent_observation",
            "compact_accessible_observation dict",
            "receipt dict (build_*_receipt)",
            "_json_hash json.dumps(sort_keys) + utf-8 + sha256",
            "_jsonl_line json.dumps(separators) string",
            "writer _bufs list[str]",
            "flush '\\n'.join(buf) extra giant string",
            "utf-8 encode in TextIOWrapper",
        ]
        v3_trace = stages

    rss_before_gc = proc_maps(pid)["rss_mb"]
    gc.collect()
    rss_after_gc = proc_maps(pid)["rss_mb"]
    trim_ok = None
    rss_after_trim = None
    if os.getpid() != LIVE_PID:
        try:
            trim_ok = malloc_trim()
            rss_after_trim = proc_maps(pid)["rss_mb"]
        except Exception as exc:
            trim_ok = f"error:{exc}"

    disk = 0
    if tmp.is_dir():
        for p in tmp.rglob("*"):
            if p.is_file():
                disk += p.stat().st_size

    mean_peak = sum(p["peak_traced"] for p in peaks) / max(len(peaks), 1)
    sess.status = "STOPPED"
    return {
        "condition": condition,
        "pid": pid,
        "live_pid_untouched": LIVE_PID,
        "spatial": spatial,
        "warmup": WARMUP,
        "window_ticks": WINDOW,
        "wall_s": round(wall, 3),
        "ticks_per_sec": round(tps, 3) if tps else None,
        "maps0": m0,
        "maps1": m1,
        "rss_mb_per_1000_ticks": round(drss / dtick * 1000.0, 3),
        "anon_mb_per_1000_ticks": round(danon / dtick * 1000.0, 3),
        "private_dirty_mb_per_1000_ticks": round(ddirty / dtick * 1000.0, 3),
        "mapping_count_delta": m1["mappings"] - m0["mappings"],
        "large_anon_delta": m1["large_anon_ge_64mb"] - m0["large_anon_ge_64mb"],
        "traced_current_delta_mb": round((cur1 - cur0) / 1e6, 4),
        "traced_mean_peak_mb": round(mean_peak / 1e6, 4),
        "traced_window_peak_mb": round(peak_win / 1e6, 4),
        "allocatedblocks0": blocks0,
        "allocatedblocks1": blocks1,
        "json_dumps_calls_per_tick": round(counters["json_dumps_calls"] / dtick, 2),
        "json_dumps_mb_per_tick": round(counters["json_dumps_bytes"] / dtick / 1e6, 4),
        "json_dumps_mb_per_1000_ticks": round(counters["json_dumps_bytes"] / dtick / 1e6 * 1000.0, 2),
        "json_max_bytes": counters["json_max"],
        "json_by_site": {
            k.replace("json_bytes:", ""): {
                "mb_per_tick": round(counters[k] / dtick / 1e6, 4),
                "calls_per_tick": round(counters[k.replace("json_bytes:", "json_calls:")] / dtick, 2),
            }
            for k in list(counters)
            if k.startswith("json_bytes:")
        },
        "v3_capture_calls_per_tick": round(counters["v3_capture_calls"] / dtick, 2),
        "v3_decision_bytes_per_tick": round(counters["v3_decisions_bytes"] / dtick, 1),
        "v3_obs_bytes_per_tick": round(counters["v3_observations_bytes"] / dtick, 1),
        "v3_jsonl_mb_per_tick": round(counters["v3_jsonl_bytes"] / dtick / 1e6, 4),
        "v3_jsonl_max": counters["v3_jsonl_max"],
        "v3_flush_join_mb_per_tick": round(counters["v3_flush_buf_bytes"] / dtick / 1e6, 4),
        "live_frame_calls_per_tick": round(counters["live_frame_calls"] / dtick, 2),
        "live_frame_mb_per_tick": round(counters["live_frame_bytes"] / dtick / 1e6, 4),
        "compact_obs_calls_per_tick": round(counters["compact_obs_calls"] / dtick, 2),
        "compact_obs_keys_per_tick": round(counters["compact_obs_keys"] / dtick, 2),
        "skipped_capture": counters["skipped_capture"],
        "v3_path_one_tick": v3_trace,
        "disk_mb": round(disk / 1e6, 3),
        "rss_before_gc_mb": rss_before_gc,
        "rss_after_gc_mb": rss_after_gc,
        "malloc_trim_rc": trim_ok,
        "rss_after_malloc_trim_mb": rss_after_trim,
        "malloc_trim_release_mb": (
            round(rss_after_gc - rss_after_trim, 3) if isinstance(rss_after_trim, float) else None
        ),
        "tracemalloc_top_retained": top,
        "tmp": str(tmp),
    }


def parent_main() -> dict:
    assert os.getpid() != LIVE_PID
    OUT.mkdir(parents=True, exist_ok=True)
    live_ok = Path(f"/proc/{LIVE_PID}/status").is_file()
    alloc = allocator_identity()
    children = {}
    py = sys.executable
    env = os.environ.copy()
    env["PSY_CHURN_CHILD"] = "1"
    for cond in CONDITIONS:
        print(f"# child {cond}", flush=True)
        p = subprocess.run(
            [py, str(Path(__file__).resolve()), "--child", cond],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=int(os.environ.get("PSY_CHURN_TIMEOUT", "240")),
        )
        if p.returncode != 0:
            children[cond] = {"error": p.stderr[-4000:], "stdout": p.stdout[-2000:], "code": p.returncode}
            print(p.stderr[-800:], flush=True)
            continue
        line = p.stdout.strip().splitlines()[-1]
        children[cond] = json.loads(line)
        print(json.dumps({
            "cond": cond,
            "rss/1000": children[cond].get("rss_mb_per_1000_ticks"),
            "json_mb/tick": children[cond].get("json_dumps_mb_per_tick"),
            "tps": children[cond].get("ticks_per_sec"),
        }), flush=True)
    after = None
    if os.environ.get("PSY_CHURN_AFTER"):
        p = subprocess.run(
            [py, str(Path(__file__).resolve()), "--child", "A_full"],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=240,
        )
        if p.returncode == 0:
            after = json.loads(p.stdout.strip().splitlines()[-1])
    report = {
        "LIVE_PID_368895_alive": live_ok,
        "LIVE_PID_368895_MODIFIED": False,
        "LIVE_PID_368895_RESTARTED": False,
        "allocator": alloc,
        "conditions": children,
        "after_opt": after,
        "warmup": WARMUP,
        "window": WINDOW,
    }
    (OUT / "allocation_churn_conditions.json").write_text(json.dumps(report, indent=2, default=str))
    return report


if __name__ == "__main__":
    os.chdir(ROOT)
    if "--child" in sys.argv:
        cond = sys.argv[sys.argv.index("--child") + 1]
        rec = run_condition(cond)
        print(json.dumps(rec, default=str))
    else:
        out = parent_main()
        print(json.dumps({
            "wrote": str(OUT / "allocation_churn_conditions.json"),
            "conds": {k: (v.get("rss_mb_per_1000_ticks") if isinstance(v, dict) else v) for k, v in (out.get("conditions") or {}).items()},
        }, indent=2))
