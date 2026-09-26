#!/usr/bin/env python3
"""Read-only memory-owner attribution for the live Observer PID.

Does not POST, reset, compact, or attach tracers to the live process.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "beta31_live_memory_forensic"
LIVE_PORT = int(os.environ.get("PSY_LIVE_PORT", "8768"))
LIVE_PID = int(os.environ.get("PSY_LIVE_PID", "368895"))
INTERVAL_S = float(os.environ.get("PSY_ATTR_INTERVAL_S", "40"))
LIVE_DIR = ROOT / "results/psychology_observer/psy_observer_web/.live-psyweb-20260923T121756.427328Z-7efa948d"


def _get(path: str, timeout: float = 8.0) -> tuple[dict | list | str | None, int, str | None]:
    url = f"http://127.0.0.1:{LIVE_PORT}{path}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            raw = r.read()
            n = len(raw)
            ct = r.headers.get("Content-Type") or ""
            if "json" in ct or path.startswith("/api/"):
                try:
                    return json.loads(raw.decode()), n, None
                except Exception as exc:
                    return None, n, str(exc)
            return None, n, None
    except Exception as exc:
        return None, 0, str(exc)


def proc_sample(pid: int) -> dict:
    st = Path(f"/proc/{pid}/status").read_text()
    kv = {}
    for line in st.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            kv[k.strip()] = v.strip()
    rss_kb = int(str(kv.get("VmRSS", "0")).split()[0] or 0)
    heap = {"anon_kb": 0, "file_kb": 0, "heap_kb": 0, "anonhuge_kb": 0, "pss_kb": 0, "mappings": 0}
    smaps = Path(f"/proc/{pid}/smaps")
    try:
        text = smaps.read_text()
    except OSError:
        text = ""
    cur_name = ""
    for line in text.splitlines():
        if line and not line[0].isspace() and "-" in line[:20] and "kB" not in line:
            cur_name = line.split()[-1] if line.split() else ""
            heap["mappings"] += 1
        elif line.startswith("Anonymous:"):
            heap["anon_kb"] += int(line.split()[1])
            if cur_name == "[heap]":
                heap["heap_kb"] += int(line.split()[1])
        elif line.startswith("Private_File:"):
            pass
        elif line.startswith("RssFile:"):
            heap["file_kb"] += int(line.split()[1])
        elif line.startswith("AnonHugePages:"):
            heap["anonhuge_kb"] += int(line.split()[1])
        elif line.startswith("Pss:"):
            heap["pss_kb"] += int(line.split()[1])
    # status-level file/anon
    return {
        "pid": pid,
        "rss_mb": round(rss_kb / 1024.0, 2),
        "vms_mb": round(int(str(kv.get("VmSize", "0")).split()[0] or 0) / 1024.0, 2),
        "threads": int(kv.get("Threads") or 0),
        "rss_anon_status_mb": round(int(str(kv.get("RssAnon", "0")).split()[0] or 0) / 1024.0, 2),
        "rss_file_status_mb": round(int(str(kv.get("RssFile", "0")).split()[0] or 0) / 1024.0, 2),
        "smaps_anon_mb": round(heap["anon_kb"] / 1024.0, 2),
        "smaps_heap_anon_mb": round(heap["heap_kb"] / 1024.0, 2),
        "smaps_file_mb": round(heap["file_kb"] / 1024.0, 2),
        "smaps_anonhuge_mb": round(heap["anonhuge_kb"] / 1024.0, 2),
        "smaps_pss_mb": round(heap["pss_kb"] / 1024.0, 2),
        "smaps_mappings": heap["mappings"],
    }


def disk_inventory(d: Path) -> dict:
    files = {}
    total = 0
    if not d.is_dir():
        return {"error": f"missing {d}"}
    for f in sorted(d.iterdir()):
        if f.is_file():
            b = f.stat().st_size
            files[f.name] = b
            total += b
    return {"path": str(d), "bytes": total, "mb": round(total / 1e6, 3), "files": files}


def tail_jsonl(path: Path, n: int = 8) -> list[dict]:
    if not path.is_file():
        return []
    # last n lines without loading whole file
    data = path.read_bytes()
    if not data:
        return []
    lines = data.splitlines()
    out = []
    for raw in lines[-n:]:
        if not raw.strip():
            continue
        try:
            out.append(json.loads(raw))
        except Exception:
            continue
    return out


def head_jsonl(path: Path, n: int = 400) -> list[dict]:
    rows = []
    if not path.is_file():
        return rows
    with path.open() as f:
        for i, line in enumerate(f):
            if i >= n:
                break
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows


def extract_store_hints(decisions: list[dict]) -> dict:
    by_agent: dict[str, dict] = {}
    for row in decisions:
        aid = str(row.get("cognitive_agent_id") or row.get("agent_id") or "?")
        tick = row.get("tick")
        smc = row.get("sensorimotor_consequence") or {}
        rec = {
            "tick": tick,
            "smc_occupancy": smc.get("occupancy"),
            "smc_capacity": smc.get("capacity"),
            "smc_updates": smc.get("updates"),
            "smc_evictions": None,
            "decision_bytes": len(json.dumps(row, default=str, separators=(",", ":"))),
        }
        by_agent[aid] = rec
    return by_agent


def observation_diversity(rows: list[dict]) -> dict:
    sigs = []
    spatial_present = 0
    key_sets = Counter()
    n_keys = []
    for row in rows:
        acc = row.get("accessible") or row.get("observation") or {}
        if not isinstance(acc, dict):
            continue
        sigs.append(row.get("signature") or json.dumps(sorted(acc.items()), default=str)[:80])
        keys = tuple(sorted(acc))
        key_sets[keys] += 1
        n_keys.append(len(acc))
        if any(str(k).startswith("spatial_") for k in acc):
            spatial_present += 1
    return {
        "n": len(rows),
        "unique_signatures": len(set(sigs)),
        "unique_key_sets": len(key_sets),
        "mean_n_keys": round(sum(n_keys) / max(1, len(n_keys)), 2),
        "max_n_keys": max(n_keys) if n_keys else 0,
        "spatial_rows": spatial_present,
        "spatial_frac": round(spatial_present / max(1, len(rows)), 3),
    }


def one_sample() -> dict:
    prog, _, perr = _get("/api/runtime/progress", 5)
    hdr, _, herr = _get("/api/header", 8)
    data, data_n, derr = _get("/api/data", 8)
    mind, mind_n, merr = _get("/api/mind", 8)
    eye, _, eerr = _get("/api/observer/tiktaalik-eye", 5)
    spat, _, serr = _get("/api/vision/spatial-vision", 5)
    # sizes only
    _, state_n, sterr = _get("/api/state", 12)
    _, world_n, werr = _get("/api/world", 8)
    tick = None
    if isinstance(prog, dict):
        tick = prog.get("tick")
    if tick is None and isinstance(hdr, dict):
        tick = hdr.get("tick")
    disk = disk_inventory(LIVE_DIR)
    dec_path = LIVE_DIR / "scientific_decisions.jsonl"
    obs_path = LIVE_DIR / "scientific_observations.jsonl"
    v3_meta = {}
    mp = LIVE_DIR / "scientific_v3_meta.json"
    if mp.is_file():
        try:
            v3_meta = json.loads(mp.read_text())
        except Exception:
            v3_meta = {}
    decisions = tail_jsonl(dec_path, 6)
    obs_tail = tail_jsonl(obs_path, 40)
    return {
        "tick": tick,
        "status": (prog or {}).get("status") if isinstance(prog, dict) else None,
        "tps": (hdr or {}).get("sim_ticks_per_sec") if isinstance(hdr, dict) else None,
        "proc": proc_sample(LIVE_PID),
        "disk": disk,
        "http_bytes": {
            "state": state_n,
            "world": world_n,
            "data": data_n,
            "mind": mind_n,
        },
        "http_errors": {k: v for k, v in {
            "progress": perr, "header": herr, "data": derr, "mind": merr,
            "eye": eerr, "spatial": serr, "state": sterr, "world": werr,
        }.items() if v},
        "observer": {
            "buffer_len": (data or {}).get("buffer_len") if isinstance(data, dict) else None,
            "buffer_capacity": (data or {}).get("buffer_capacity") if isinstance(data, dict) else None,
            "timeline_len": (data or {}).get("timeline_len") if isinstance(data, dict) else None,
            "history": (data or {}).get("history") if isinstance(data, dict) else None,
            "telemetry_policy": (data or {}).get("telemetry_policy") if isinstance(data, dict) else None,
        },
        "mind_compact": {
            "bytes": mind_n,
            "status": (mind or {}).get("status") if isinstance(mind, dict) else None,
            "detail": (mind or {}).get("detail") if isinstance(mind, dict) else None,
            "memory": (mind or {}).get("memory") if isinstance(mind, dict) else None,
            "metrics": (mind or {}).get("metrics") if isinstance(mind, dict) else None,
            "agent_id": (mind or {}).get("agent_id") if isinstance(mind, dict) else None,
        },
        "eye": eye if isinstance(eye, dict) else {"error": eerr},
        "spatial_vision": spat if isinstance(spat, dict) else {"error": serr},
        "v3_meta": {
            "counts": (v3_meta.get("counts") if isinstance(v3_meta, dict) else None),
            "ticks_captured": v3_meta.get("ticks_captured") if isinstance(v3_meta, dict) else None,
            "health": (v3_meta.get("health") if isinstance(v3_meta, dict) else None),
        },
        "v3_decision_tail": extract_store_hints(decisions),
        "v3_obs_tail_diversity": observation_diversity(obs_tail),
        "header_seed": (hdr or {}).get("seed") if isinstance(hdr, dict) else None,
        "agent_count": (hdr or {}).get("agent_count") if isinstance(hdr, dict) else None,
        "evidence_mode": (hdr or {}).get("evidence_mode") if isinstance(hdr, dict) else None,
        "frame_detail": (hdr or {}).get("frame_detail") if isinstance(hdr, dict) else None,
        "optical_hint": None,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    assert Path(f"/proc/{LIVE_PID}").exists(), f"PID {LIVE_PID} missing"
    s0 = one_sample()
    # cheaper diversity: head vs tail of observations (disk)
    obs_path = LIVE_DIR / "scientific_observations.jsonl"
    s0["obs_head_diversity"] = observation_diversity(head_jsonl(obs_path, 300))
    s0["obs_tail400_diversity"] = observation_diversity(tail_jsonl(obs_path, 400))
    (OUT / "owner_sample_0.json").write_text(json.dumps(s0, indent=2, default=str))
    time.sleep(INTERVAL_S)
    s1 = one_sample()
    s1["obs_tail400_diversity"] = observation_diversity(tail_jsonl(obs_path, 400))
    (OUT / "owner_sample_1.json").write_text(json.dumps(s1, indent=2, default=str))

    dtick = int(s1["tick"] or 0) - int(s0["tick"] or 0)
    drss = float(s1["proc"]["rss_mb"]) - float(s0["proc"]["rss_mb"])
    dheap = float(s1["proc"]["smaps_heap_anon_mb"]) - float(s0["proc"]["smaps_heap_anon_mb"])
    danon = float(s1["proc"]["smaps_anon_mb"]) - float(s0["proc"]["smaps_anon_mb"])
    ddisk = float(s1["disk"].get("mb") or 0) - float(s0["disk"].get("mb") or 0)
    per1000 = lambda x: round(x / max(dtick, 1) * 1000.0, 3)

    # SMC occupancy delta
    a0s = (s0.get("v3_decision_tail") or {}).get("agent_0") or {}
    a1s = (s0.get("v3_decision_tail") or {}).get("agent_1") or {}
    a0e = (s1.get("v3_decision_tail") or {}).get("agent_0") or {}
    a1e = (s1.get("v3_decision_tail") or {}).get("agent_1") or {}

    stores = []
    for name, cap, evict, bounded, bytes0, bytes1, n0, n1, note in [
        (
            "observer_frame_buffer",
            (s1.get("observer") or {}).get("buffer_capacity"),
            "deque maxlen",
            "bounded",
            (s0.get("http_bytes") or {}).get("state"),
            (s1.get("http_bytes") or {}).get("state"),
            (s0.get("observer") or {}).get("buffer_len"),
            (s1.get("observer") or {}).get("buffer_len"),
            "state GET is latest frame JSON bytes, not sum of ring",
        ),
        (
            "v3_decisions_disk",
            None,
            "append-only disk",
            "unbounded_disk",
            (s0.get("disk") or {}).get("files", {}).get("scientific_decisions.jsonl"),
            (s1.get("disk") or {}).get("files", {}).get("scientific_decisions.jsonl"),
            None,
            None,
            "not RSS unless mmap; RssFile is small",
        ),
    ]:
        stores.append({
            "store_name": name,
            "configured_limit": cap,
            "eviction_policy": evict,
            "bounded": bounded,
            "entries_t0": n0,
            "entries_t1": n1,
            "bytes_t0": bytes0,
            "bytes_t1": bytes1,
            "d_entries": (None if n0 is None or n1 is None else n1 - n0),
            "d_bytes": (None if bytes0 is None or bytes1 is None else bytes1 - bytes0),
            "note": note,
        })

    smc_rows = []
    for aid, t0, t1 in (("agent_0", a0s, a0e), ("agent_1", a1s, a1e)):
        n0, n1 = t0.get("smc_occupancy"), t1.get("smc_occupancy")
        # estimate ~5kB JSON/record from prior reproduction
        e0 = None if n0 is None else int(n0) * 5000
        e1 = None if n1 is None else int(n1) * 5000
        smc_rows.append({
            "store_name": "SMC",
            "agent": aid,
            "tick0": t0.get("tick"),
            "tick1": t1.get("tick"),
            "entries_t0": n0,
            "entries_t1": n1,
            "estimated_bytes_t0": e0,
            "estimated_bytes_t1": e1,
            "configured_cap": t1.get("smc_capacity") or t0.get("smc_capacity") or 256,
            "eviction_policy": "FIFO/oldest when occupancy>=capacity",
            "bounded": "bounded",
            "d_entries_per_tick": (None if n0 is None or n1 is None or dtick <= 0 else round((n1 - n0) / dtick, 4)),
            "d_bytes_per_tick": (None if e0 is None or e1 is None or dtick <= 0 else round((e1 - e0) / dtick, 1)),
        })

    slopes = {
        "tick0": s0["tick"],
        "tick1": s1["tick"],
        "dtick": dtick,
        "d_rss_mb": round(drss, 3),
        "rss_mb_per_tick": round(drss / max(dtick, 1), 4),
        "rss_mb_per_1000_ticks": per1000(drss),
        "d_smaps_heap_anon_mb": round(dheap, 3),
        "heap_anon_mb_per_1000_ticks": per1000(dheap),
        "d_smaps_anon_mb": round(danon, 3),
        "anon_mb_per_1000_ticks": per1000(danon),
        "d_disk_mb": round(ddisk, 3),
        "disk_mb_per_1000_ticks": per1000(ddisk),
        "d_state_bytes": (s1["http_bytes"]["state"] or 0) - (s0["http_bytes"]["state"] or 0),
        "d_eye_payload": ((s1.get("eye") or {}).get("payload_bytes") or 0) - ((s0.get("eye") or {}).get("payload_bytes") or 0),
        "d_eye_updates": ((s1.get("eye") or {}).get("update_count") or 0) - ((s0.get("eye") or {}).get("update_count") or 0),
    }
    (OUT / "owner_attribution.json").write_text(json.dumps({
        "CURRENT_RUN_PID": LIVE_PID,
        "LIVE_RUN_MODIFIED": False,
        "LIVE_RUN_RESTARTED": False,
        "slopes": slopes,
        "stores": stores,
        "smc": smc_rows,
        "diversity_t0": s0.get("obs_tail400_diversity"),
        "diversity_t1": s1.get("obs_tail400_diversity"),
        "diversity_head": s0.get("obs_head_diversity"),
        "proc_t0": s0["proc"],
        "proc_t1": s1["proc"],
    }, indent=2, default=str))
    (OUT / "store_cardinality.json").write_text(json.dumps({
        "live_attribution": True,
        "smc": smc_rows,
        "observer": stores,
        "ticks": [s0["tick"], s1["tick"]],
    }, indent=2, default=str))
    print(json.dumps({"slopes": slopes, "smc": smc_rows, "heap": s0["proc"]}, indent=2))


if __name__ == "__main__":
    main()
