"""FREE RESOURCE OBJECT KINEMATICS (Acanthostega). Researcher receipts only.

Links RESOURCE_OBJECT_RELEASE_KINEMATICS -> RESOURCE_OBJECT_FREE_MOTION -> rest transition by
release_id / object_id. Statuses: OBSERVED / VERIFIED / NOT_AVAILABLE. No progress bar. This is a
kinematic provenance audit, not "throwing", tool use or projectile understanding.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

SECTION = "FREE RESOURCE OBJECT KINEMATICS"
SCHEMA_VERSION = "FREE_RESOURCE_OBJECT_KINEMATICS_SUMMARY_V1"
RELEASE = "RESOURCE_OBJECT_RELEASE_KINEMATICS"
MOTION = "RESOURCE_OBJECT_FREE_MOTION"

EXPLICIT = {
    "FREE_OBJECT_COLLISION": "NOT_IMPLEMENTED",
    "OBJECT_IMPACT_ACOUSTICS": "NOT_IMPLEMENTED",
    "GRAVITY": "NOT_IMPLEMENTED",
    "THROW_COMMAND": "NOT_IMPLEMENTED",
    "GRASP_OF_MOVING_OBJECT": "NOT_ESTABLISHED",
    "THROWING_OR_TOOL_UNDERSTANDING": "NOT_ESTABLISHED",
}


def _dedup(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    seen, out = set(), []
    for r in rows:
        k = r.get(key)
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out


def _rng(vals: list[float]) -> list[float] | None:
    return [min(vals), max(vals)] if vals else None


def _hist(vals: list[float], edges=(0.0, 0.01, 0.05, 0.1, 0.2, 0.3, 0.5, 0.75, 10.0)) -> dict[str, int]:
    out: dict[str, int] = {}
    for a, b in zip(edges, edges[1:]):
        out[f"[{a},{b})"] = sum(1 for v in vals if a <= v < b)
    return out


def summarize_free_object_kinematics(events: list[dict[str, Any]] | None) -> dict[str, Any]:
    rel = _dedup([e for e in events or [] if isinstance(e, dict) and e.get("receipt_kind") == RELEASE], "release_id")
    mot = _dedup([e for e in events or [] if isinstance(e, dict) and e.get("receipt_kind") == MOTION], "motion_id")
    released = [r for r in rel if r.get("outcome") == "RELEASED"]
    moving = [r for r in released if r.get("initial_free_state") == "FREE_MOVING"]
    rests = [m for m in mot if m.get("rest_transition")]
    episodes = [m.get("episode") for m in rests if isinstance(m.get("episode"), dict)]
    inherited = [float(r.get("speed_after_clamp") or 0.0) for r in released]
    clamps = sum(1 for r in released if r.get("speed_clamped")) + sum(1 for m in mot if m.get("speed_clamped"))
    path = sum(float(m.get("step_length") or 0.0) for m in mot)
    wraps = sum(1 for m in mot if m.get("wrap_occurred"))
    violations = sum(1 for m in mot if m.get("invariants_conserved") is False)
    # Trajectory continuity (incl. across snapshot/restore): consecutive motion receipts of one object
    by_obj: dict[str, list[dict[str, Any]]] = {}
    for m in sorted(mot, key=lambda m: (str(m.get("object_id")), int(m.get("tick") or 0))):
        by_obj.setdefault(str(m.get("object_id")), []).append(m)
    links = breaks = 0
    for rows in by_obj.values():
        for a, b in zip(rows, rows[1:]):
            if int(b.get("tick") or 0) != int(a.get("tick") or 0) + 1 or b.get("release_receipt_ref") != a.get("release_receipt_ref"):
                continue
            links += 1
            if list(a.get("end_position") or []) != list(b.get("start_position") or []) or \
                    list(a.get("end_velocity") or []) != list(b.get("start_velocity") or []):
                breaks += 1
    rel_ids = {r.get("release_id") for r in released}
    linked = sum(1 for m in mot if m.get("release_receipt_ref") in rel_ids)
    fields = ("release_id", "object_id", "releasing_body_id", "effector_side", "current_effector_pose",
              "measurement", "measured_effector_velocity", "release_transfer", "inherited_velocity_before_clamp",
              "velocity_after_clamp", "initial_free_state", "position", "source_action_receipt")
    complete = sum(1 for r in released if all(r.get(f) is not None for f in fields)
                   and r.get("agent_accessible") is False)
    n = len(rel) + len(mot)
    return {
        "section": SECTION,
        "schema_version": SCHEMA_VERSION,
        "event_count": n,
        "status": "OBSERVED" if n else "NOT_AVAILABLE",
        "release_count": len(released),
        "releases_regrasped_same_tick": sum(1 for r in rel if r.get("outcome") == "REGRASPED_SAME_TICK"),
        "releases_moving": len(moving),
        "releases_at_rest": len(released) - len(moving),
        "measurement_outcomes": {k: sum(1 for r in released if r.get("measurement") == k)
                                 for k in sorted({str(r.get("measurement")) for r in released})},
        "moving_objects": len({m.get("object_id") for m in mot}),
        "motion_steps": len(mot),
        "rest_transitions": len(rests),
        "inherited_speed_range": _rng(inherited),
        "inherited_speed_distribution": _hist(inherited),
        "clamp_count": clamps,
        "path_length_total": path,
        "path_length_per_episode": [float(e.get("path_length") or 0.0) for e in episodes][:64],
        "ticks_to_rest": [e.get("ticks_to_rest") for e in episodes][:64],
        "wrap_count": wraps,
        "conservation_violations": violations,
        "conservation": "VERIFIED" if mot and violations == 0 else ("VIOLATED" if violations else "NOT_AVAILABLE"),
        "trajectory_links_checked": links,
        "trajectory_discontinuities": breaks,
        "snapshot_continuation_status": (
            ("VERIFIED_BY_RECEIPT_CONTINUITY" if breaks == 0 else "DISCONTINUITY_OBSERVED") if links else "NOT_AVAILABLE"
        ),
        "motion_linked_to_release": linked,
        "provenance_complete_releases": complete,
        "provenance_quality": (
            "VERIFIED" if released and complete == len(released) and linked == len(mot) else
            ("NOT_AVAILABLE" if not released and not mot else "PARTIAL")
        ),
        "explicit_status": dict(EXPLICIT),
        "researcher_only": True,
        "agent_accessible": False,
    }


def format_free_object_kinematics_section(s: dict[str, Any]) -> str:
    lines = [
        SECTION,
        "-" * len(SECTION),
        f"status: {s.get('status')}  (researcher-only kinematic provenance; collision physics: not implemented)",
        f"releases: {s.get('release_count')}  moving: {s.get('releases_moving')}  at rest: {s.get('releases_at_rest')}  "
        f"re-grasped same tick: {s.get('releases_regrasped_same_tick')}  measurement: {s.get('measurement_outcomes')}",
        f"moving objects: {s.get('moving_objects')}  motion steps: {s.get('motion_steps')}  "
        f"rest transitions: {s.get('rest_transitions')}",
        f"inherited speed range: {s.get('inherited_speed_range')}  clamp count: {s.get('clamp_count')}",
        f"path length total: {s.get('path_length_total')}  ticks to rest: {s.get('ticks_to_rest')}  "
        f"wrap count: {s.get('wrap_count')}",
        f"conservation violations: {s.get('conservation_violations')} ({s.get('conservation')})  "
        f"snapshot continuation: {s.get('snapshot_continuation_status')}  provenance: {s.get('provenance_quality')}",
    ]
    for k, v in (s.get("explicit_status") or {}).items():
        lines.append(f"{k} = {v}")
    return "\n".join(lines)


def free_object_receipts_from_consequences(run_dir: Path) -> list[dict[str, Any]]:
    path = Path(run_dir) / "scientific_consequences.jsonl"
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            for ref in row.get("event_refs") or []:
                if isinstance(ref, dict) and ref.get("kind") == "free_resource_object_kinematics":
                    rows.append(ref)
    return rows
