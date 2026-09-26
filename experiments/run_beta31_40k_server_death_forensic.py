#!/usr/bin/env python3
"""Preserve 40k crash evidence (read-only on live dir) + Analyzer 1.2 reconstruction.

Does not rewrite the failed run directory. Compact artifacts only under
results/beta31_40k_server_death_forensic/.
"""
from __future__ import annotations

import json
import os
import resource
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/home/thehost/Desktop/psy")
LIVE = ROOT / "results/psychology_observer/psy_observer_web/.live-psyweb-20260923T180243.860310Z-e02e833b"
OUT = ROOT / "results/beta31_40k_server_death_forensic"
OUT.mkdir(parents=True, exist_ok=True)

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

JSONL = (
    "scientific_spine.jsonl",
    "scientific_observations.jsonl",
    "scientific_decisions.jsonl",
    "scientific_motors.jsonl",
    "scientific_consequences.jsonl",
    "scientific_events.jsonl",
    "scientific_timeline.jsonl",
    "scientific_checkpoints.jsonl",
)


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stream_jsonl_stats(path: Path, *, max_malformed_tail: int = 8) -> dict:
    if not path.is_file():
        return {"exists": False, "path": str(path)}
    n = 0
    first_tick = None
    last_tick = None
    last_complete = True
    agents: set[str] = set()
    malformed_tail = 0
    size = path.stat().st_size
    with path.open("rb") as f:
        # first record
        line = f.readline()
        if line:
            last_complete = line.endswith(b"\n")
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    t = obj.get("tick")
                    if t is None:
                        t = obj.get("tick_from")
                    if t is not None:
                        first_tick = int(t)
                    aid = obj.get("cognitive_agent_id")
                    if aid:
                        agents.add(str(aid))
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
            n = 1
        for raw in f:
            n += 1
            last_complete = raw.endswith(b"\n")
            if n % 4096 == 0:
                continue
        # cheap last-tick: last 512KB
        if size > 0:
            f.seek(max(0, size - 524288))
            tail = f.read().splitlines()
            parsed_last = None
            for raw in reversed(tail):
                if not raw.strip():
                    continue
                try:
                    obj = json.loads(raw)
                except json.JSONDecodeError:
                    malformed_tail += 1
                    if malformed_tail >= max_malformed_tail:
                        break
                    continue
                if not isinstance(obj, dict):
                    continue
                t = obj.get("tick")
                if t is None:
                    t = obj.get("tick_to") or obj.get("tick_from")
                if t is not None:
                    parsed_last = int(t)
                aid = obj.get("cognitive_agent_id")
                if aid:
                    agents.add(str(aid))
                if parsed_last is not None:
                    last_tick = parsed_last
                    break
    return {
        "exists": True,
        "path": str(path),
        "size_bytes": size,
        "size_mb": round(size / (1024 * 1024), 3),
        "line_count": n,
        "first_tick": first_tick,
        "last_tick": last_tick,
        "final_newline": last_complete,
        "malformed_tail_records": malformed_tail,
        "agent_ids": sorted(agents),
    }


def _frontier(spine: Path, n_last: int = 400) -> dict:
    if not spine.is_file():
        return {"error": "missing spine"}
    rows = []
    with spine.open("rb") as f:
        f.seek(max(0, spine.stat().st_size - 2_000_000))
        lines = f.read().splitlines()
    for raw in lines[-n_last:]:
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    ticks = {}
    for r in rows:
        try:
            t = int(r.get("tick"))
        except (TypeError, ValueError):
            continue
        ticks.setdefault(t, []).append(r)
    complete = []
    incomplete = []
    for t, recs in sorted(ticks.items()):
        agents = {}
        for r in recs:
            aid = str(r.get("cognitive_agent_id") or "")
            agents.setdefault(aid, r)
        ok = True
        for aid, r in agents.items():
            if not (r.get("observation_id") and r.get("decision_id") and r.get("motor_id") and r.get("consequence_id")):
                ok = False
        if ok and agents:
            complete.append(t)
        else:
            incomplete.append({"tick": t, "agents": list(agents)})
    return {
        "sampled_rows": len(rows),
        "latest_spine_tick": max(ticks) if ticks else None,
        "latest_complete_odmc_tick": complete[-1] if complete else None,
        "incomplete_frontier": incomplete[-8:],
        "complete_tick_sample_n": len(complete),
    }


def _journal() -> str:
    chunks = []
    cmds = [
        ["journalctl", "-k", "--since", "2026-09-23 23:00:00", "--until", "2026-09-24 02:00:00", "-n", "200"],
        ["journalctl", "--since", "2026-09-23 23:00:00", "--until", "2026-09-24 02:00:00", "-g", "oom|Out of memory|Killed process|python", "-n", "80"],
        ["dmesg", "-T"],
    ]
    for cmd in cmds:
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            chunks.append("$ " + " ".join(cmd) + "\n" + (p.stdout or "")[-12000:] + (p.stderr or "")[:500])
        except Exception as exc:
            chunks.append(f"$ {' '.join(cmd)}\nERROR {exc}")
    return "\n\n".join(chunks)


def _copy_small(src: Path, dest: Path) -> None:
    if src.is_file() and src.stat().st_size < 2_000_000:
        shutil.copy2(src, dest)


def main() -> None:
    compact = OUT / "copied_compact"
    compact.mkdir(exist_ok=True)
    if LIVE.is_dir():
        for name in ("identity_map.json", "scientific_v3_meta.json", "scientific_meta.json"):
            _copy_small(LIVE / name, compact / name)

    surviving = {"live_dir": str(LIVE), "exists": LIVE.is_dir(), "files": {}}
    if LIVE.is_dir():
        for p in sorted(LIVE.iterdir()):
            if p.is_file():
                st = p.stat()
                rec = {
                    "size_bytes": st.st_size,
                    "mtime": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
                }
                if p.name in JSONL or p.suffix == ".jsonl":
                    rec.update(_stream_jsonl_stats(p))
                surviving["files"][p.name] = rec
        surviving["total_bytes"] = sum(x.get("size_bytes") or 0 for x in surviving["files"].values())
        surviving["total_gb"] = round(surviving["total_bytes"] / (1024 ** 3), 4)

    frontier = _frontier(LIVE / "scientific_spine.jsonl") if LIVE.is_dir() else {}
    (OUT / "surviving_artifacts.json").write_text(json.dumps(surviving, indent=2, default=str) + "\n")
    (OUT / "v3_frontier_integrity.json").write_text(json.dumps(frontier, indent=2, default=str) + "\n")

    last_v3 = None
    last_odmc = frontier.get("latest_complete_odmc_tick")
    spine_st = (surviving.get("files") or {}).get("scientific_spine.jsonl") or {}
    last_v3 = spine_st.get("last_tick") or frontier.get("latest_spine_tick")
    events = (surviving.get("files") or {}).get("scientific_events.jsonl") or {}
    visible = events.get("last_tick") or last_v3

    disk_mb = (surviving.get("total_bytes") or 0) / (1024 * 1024)
    ticks = float(last_v3 or 40164) or 1.0
    mb_per_1k = disk_mb / ticks * 1000.0
    disk_growth = {
        "JSONL_MB_PER_1000_TICKS": round(mb_per_1k, 3),
        "TOTAL_RUN_DISK_GB_AT_40K": surviving.get("total_gb"),
        "projection_gb": {
            "10k": round(mb_per_1k * 10 / 1024, 3),
            "20k": round(mb_per_1k * 20 / 1024, 3),
            "40k": round(mb_per_1k * 40 / 1024, 3),
            "100k": round(mb_per_1k * 100 / 1024, 3),
        },
        "note": "Disk JSONL growth is evidence density, not a RAM leak.",
    }
    (OUT / "disk_growth.json").write_text(json.dumps(disk_growth, indent=2) + "\n")

    rss_mb_per_1k = round((19120832 / 1024) / 40.165, 2)  # kernel anon-rss kB / 40165 ticks * 1000
    memory_growth = {
        "kernel_anon_rss_kb_at_death": 19120832,
        "approx_rss_gb": 18.24,
        "LONG_RUN_RSS_GROWTH_MB_PER_1000": rss_mb_per_1k,
        "smc_occupancy_at_last_decision": "256/256 cap (bounded)",
        "observer_full_frames": 1,
        "UNBOUNDED_RAM_OWNER_FOUND": "INCONCLUSIVE",
        "note": "Kernel OOM at ~19.1 GB RSS. SMC occupancy bounded. Decision JSONL is disk. Allocator/PE/cognition object graph not sampled live.",
    }
    (OUT / "memory_growth.json").write_text(json.dumps(memory_growth, indent=2) + "\n")

    process_identity = {
        "pid": 14381,
        "command": "python (Observer / Psy Web)",
        "death_kernel_time": "2026-09-24 00:34:55",
        "invoker": "containerd",
        "cgroup": "session-3.scope",
        "anon_rss_kb": 19120832,
        "total_vm_kb": "~20900000",
        "observer_port_at_crash": 8768,
        "working_directory": str(LIVE),
        "run_id": "e02e833b",
        "seed": 575,
        "final_known_tick_v3_meta": 40166,
        "PROCESS_DEATH_MODE": "OOM_KILL",
        "current_instance_json_is_new_process": True,
        "new_process_note": ".psy_observer/instance.json pid 60087 started after crash; not the dead run.",
    }
    (OUT / "process_identity.json").write_text(json.dumps(process_identity, indent=2) + "\n")

    (OUT / "journal_evidence.txt").write_text(_journal())

    analyzer_note = {
        "ANALYZER_INVOLVED_IN_40K_DEATH": "UNKNOWN",
        "lean": "NO",
        "reason": (
            "Live dir has no analysis/ job artifacts. Death timestamp aligns with RUNNING "
            "scientific append (spine/timeline ~40166). Historical 15.4GB OOM was a different "
            "PID (269596) Analyzer materialization. Dead process code identity not sampled from RAM."
        ),
        "current_tree_analyzer": "1.2 streamed/bounded; not proof of loaded binary",
    }

    root_cause = {
        "ROOT_CAUSE": "Linux OOM killer SIGKILL of python PID 14381 (~19.1 GB anon-rss) during naturalistic TwoAgent Observer run e02e833b ~t40165",
        "ROOT_CAUSE_CONFIDENCE": "STRONG",
        "OOM_CONFIRMED": "YES",
        "ENOSPC_CONFIRMED": "NO",
        "PROCESS_DEATH_MODE": "OOM_KILL",
        "unbounded_python_owner": "INCONCLUSIVE",
        "not_causes": [
            "ENOSPC (disk had free space; no kernel ENOSPC in window)",
            "controlled spawn/remove (prior 50-cycle forensic passed)",
            "historical Analyzer 15.4GB incident (different PID/day)",
        ],
        "ANALYZER_INVOLVED": analyzer_note,
    }
    (OUT / "root_cause.json").write_text(json.dumps(root_cause, indent=2) + "\n")

    v3_recon = None
    if LIVE.is_dir():
        try:
            from mechanistic_mind.scientific_v3.analyzer_adapter import build_v3_core_reconstruction

            v3_recon = build_v3_core_reconstruction(LIVE)
            (OUT / "v3_core_reconstruction.json").write_text(json.dumps(v3_recon, indent=2, default=str) + "\n")
        except Exception as exc:
            v3_recon = {"error": str(exc)}
            (OUT / "v3_core_reconstruction.json").write_text(json.dumps(v3_recon, indent=2) + "\n")

    crash_summary = {
        "written_at": _utc(),
        "FAILED_RUN_FINAL_VISIBLE_TICK": visible,
        "FAILED_RUN_LAST_V3_TICK": last_v3,
        "FAILED_RUN_LAST_COMPLETE_ODMC_TICK": last_odmc,
        "LIVE_RUNTIME_RECOVERABLE": "NO",
        "SCIENTIFIC_HISTORY_RECOVERABLE": "YES" if last_odmc else "PARTIAL",
        "ANALYZABLE_UP_TO_TICK": last_odmc,
        "corpus_treatment": "CRASH-TERMINATED NATURALISTIC CORPUS",
        "do_not_merge_post_checkpoint_dead_ticks": True,
        "analyzer_reconstruction_status": "ok" if v3_recon and "error" not in v3_recon else v3_recon,
        "scientific_checkpoints_jsonl_is_geometry_not_runtime_restore": True,
    }
    (OUT / "crash_summary.json").write_text(json.dumps(crash_summary, indent=2, default=str) + "\n")
    print(json.dumps({"out": str(OUT), "last_odmc": last_odmc, "last_v3": last_v3, "disk_gb": surviving.get("total_gb")}, indent=2))


if __name__ == "__main__":
    os.chdir(ROOT)
    main()
