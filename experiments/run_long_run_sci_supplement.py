#!/usr/bin/env python3
"""Supplemental long-run windows WITH scientific history + VF append enabled.

Primary audit windows already showed STABLE tick cost without sci writer
(run_id never opened). Real Play opens scientific history — measure that path.
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from experiments.run_long_run_degradation_audit import (  # noqa: E402
    OUT,
    RAW,
    WINDOWS,
    advance_to,
    capture_stats,
    component_window,
    make_session,
    scientific_only,
    structure_inventory,
    window_stats,
)

SUP = OUT / "raw" / "sci_supplement"


def main() -> None:
    SUP.mkdir(parents=True, exist_ok=True)
    print("=== SCI/VF SUPPLEMENT (Play-like with scientific writer) ===")
    sess = make_session()
    assert sess._sci_writer is not None, "scientific writer must be open"
    print("run_id", sess._active_run_id, "live", sess._sci_live_dir)

    rows = []
    struct = []
    for name, a, b in WINDOWS:
        print(f"Advancing to {a}… (now {int(sess.runtime.tick)})")
        advance_to(sess, a)
        if name in ("W0", "W5"):
            comp = component_window(sess, b - a)
            stats = comp["tick_stats"]
            stages = (comp.get("stages") or {}).get("stages") or []
            stage_map = {s["stage"]: s["mean_ms"] for s in stages}
        else:
            samples = scientific_only(sess, b - a)
            stats = window_stats(samples)
            stage_map = {}
        if int(sess.runtime.tick) < b:
            scientific_only(sess, b - int(sess.runtime.tick))
        inv = structure_inventory(sess, sess.runtime)
        cap = capture_stats(sess)
        sci = inv.get("observer") or {}
        row = {
            "window": name,
            "tick_end": int(sess.runtime.tick),
            "mean_ms": stats.get("mean_ms"),
            "median_ms": stats.get("median_ms"),
            "p95_ms": stats.get("p95_ms"),
            "p99_ms": stats.get("p99_ms"),
            "tps": stats.get("tps"),
            "rss_mb": inv.get("rss_mb"),
            "ws_frame_bytes": cap.get("live_frame_bytes"),
            "sci_rows_written": sci.get("sci_rows_written"),
            "sci_events_written": sci.get("sci_events_written"),
            "sci_timeline_bytes": inv.get("scientific_timeline_bytes"),
            "append_scientific_ms": stage_map.get("sess.append_scientific"),
            "accumulate_events_ms": stage_map.get("sess.accumulate_events"),
            "scientific_step_ms": stage_map.get("sess.scientific_step"),
        }
        rows.append(row)
        struct.append({"window": name, **(inv.get("observer") or {}), "sci_timeline_bytes": inv.get("scientific_timeline_bytes"), "rss_mb": inv.get("rss_mb")})
        (SUP / f"inventory_{name}.json").write_text(
            json.dumps({"inventory": inv, "capture": cap, "stages": stage_map}, indent=2, default=str),
            encoding="utf-8",
        )
        print(
            f"  {name} mean={stats.get('mean_ms'):.2f}ms "
            f"sci_rows={sci.get('sci_rows_written')} "
            f"sci_bytes={inv.get('scientific_timeline_bytes')} "
            f"append_ms={stage_map.get('sess.append_scientific')} "
            f"frame={cap.get('live_frame_bytes')}B"
        )

    # Flush writer
    with sess._lock:
        if sess._sci_writer:
            sess._sci_writer.flush()

    keys = list(rows[0].keys())
    with (OUT / "SCI_SUPPLEMENT_WINDOW_TIMINGS.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)

    early, late = rows[0], rows[-1]
    ratio = float(late["mean_ms"]) / max(1e-9, float(early["mean_ms"]))
    summary = {
        "early_mean_ms": early["mean_ms"],
        "late_mean_ms": late["mean_ms"],
        "ratio": ratio,
        "early_sci_bytes": early.get("sci_timeline_bytes"),
        "late_sci_bytes": late.get("sci_timeline_bytes"),
        "early_sci_rows": early.get("sci_rows_written"),
        "late_sci_rows": late.get("sci_rows_written"),
        "early_append_ms": early.get("append_scientific_ms"),
        "late_append_ms": late.get("append_scientific_ms"),
        "frame_bytes_early": early.get("ws_frame_bytes"),
        "frame_bytes_late": late.get("ws_frame_bytes"),
        "note": "Scientific history + vision_optical compact append enabled (Play-equivalent).",
    }
    (SUP / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (OUT / "SCI_HISTORY_VF_AUDIT.md").write_text(
        "# Scientific history / Visual Forensics supplement\n\n"
        f"- EARLY mean: {early['mean_ms']:.3f} ms\n"
        f"- LATE mean: {late['mean_ms']:.3f} ms\n"
        f"- ratio: {ratio:.3f}\n"
        f"- sci rows: {early.get('sci_rows_written')} → {late.get('sci_rows_written')} (EXPECTED_LINEAR)\n"
        f"- sci timeline bytes: {early.get('sci_timeline_bytes')} → {late.get('sci_timeline_bytes')} (EXPECTED_LINEAR)\n"
        f"- append_scientific ms/tick: {early.get('append_scientific_ms')} → {late.get('append_scientific_ms')}\n"
        f"- WS/live frame bytes: {early.get('ws_frame_bytes')} → {late.get('ws_frame_bytes')} (FLAT)\n"
        "\nAppend path is buffered jsonl write + compact vision_optical per tick — "
        "not a full Analyzer rebuild. Analyzer/VF rehydration is on-demand from jsonl, "
        "not every Play tick.\n",
        encoding="utf-8",
    )
    print("DONE sci supplement ratio", f"{ratio:.3f}")


if __name__ == "__main__":
    main()
