#!/usr/bin/env python3
"""Read-only LIVE tick sampler for an already-running Psy Observer.

Polls GET /api/runtime/progress only (no step_lock, no frame build, no
mechanism/PSC/detail changes). Optionally records host RSS for the process
that owns the given port.

Does not inject instrumentation into the runtime. Safe for an aged run.
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def _pid_for_port(port: int) -> int | None:
    inodes: set[str] = set()

    def parse(path: str) -> None:
        if not os.path.exists(path):
            return
        with open(path, encoding="utf-8") as fh:
            next(fh)
            for line in fh:
                parts = line.split()
                loc, st, inode = parts[1], parts[3], parts[9]
                p = int(loc.rsplit(":", 1)[-1], 16)
                if p == port and st == "0A":
                    inodes.add(inode)

    parse("/proc/net/tcp")
    parse("/proc/net/tcp6")
    if not inodes:
        return None
    import glob

    for fd in glob.glob("/proc/[0-9]*/fd/[0-9]*"):
        try:
            target = os.readlink(fd)
        except OSError:
            continue
        if target.startswith("socket:[") and target[8:-1] in inodes:
            return int(fd.split("/")[2])
    return None


def _rss_kb(pid: int) -> int | None:
    try:
        with open(f"/proc/{pid}/status", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1])
    except OSError:
        return None
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url", default="http://127.0.0.1:8768", help="Observer base URL")
    ap.add_argument("--seconds", type=float, default=120.0)
    ap.add_argument("--interval", type=float, default=0.35)
    ap.add_argument("--port", type=int, default=8768)
    ap.add_argument(
        "--out",
        default="results/beta3_performance_forensics/progress_sample.jsonl",
    )
    args = ap.parse_args()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    pid = _pid_for_port(args.port)
    end = time.time() + float(args.seconds)
    last_tick = None
    n_unique = 0
    with out.open("w", encoding="utf-8") as fh:
        while time.time() < end:
            rec: dict = {
                "wall": datetime.now(timezone.utc).isoformat(),
                "mono": time.monotonic(),
                "sampler": "beta3_readonly_perf_sampler",
            }
            try:
                with urllib.request.urlopen(args.url.rstrip("/") + "/api/runtime/progress", timeout=3) as r:
                    rec.update(json.load(r))
            except Exception as exc:
                rec["error"] = str(exc)
            if pid:
                rec["pid"] = pid
                rec["rss_kb"] = _rss_kb(pid)
            fh.write(json.dumps(rec, default=str) + "\n")
            fh.flush()
            t = rec.get("tick")
            if t is not None and t != last_tick and rec.get("last_tick_wall_ms") is not None:
                n_unique += 1
                last_tick = t
            time.sleep(max(0.05, float(args.interval)))
    print(json.dumps({"out": str(out), "unique_ticks": n_unique, "pid": pid}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
