"""Offline geometry analysis from scientific history JSONL."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from mechanistic_mind.ui.psy_observer_web.geometry.context import geometry_context
from mechanistic_mind.ui.psy_observer_web.geometry.trajectory import detect_episodes
from mechanistic_mind.ui.psy_observer_web.geometry.traversability import (
    accumulate_traversability,
    steps_from_timeline_rows,
    top_deflection_cells,
)


def load_timeline_jsonl(path: Path, *, max_rows: int | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open() as fh:
        for ln in fh:
            ln = ln.strip()
            if not ln:
                continue
            rows.append(json.loads(ln))
            if max_rows is not None and len(rows) >= max_rows:
                break
    return rows


def load_body_moved_forces(
    events_path: Path,
    *,
    max_events: int | None = 500_000,
) -> dict[tuple[str, int], dict[str, Any]]:
    """Map (agent_id, tick) → forces from BODY_MOVED evidence."""
    out: dict[tuple[str, int], dict[str, Any]] = {}
    n = 0
    with events_path.open() as fh:
        for ln in fh:
            ln = ln.strip()
            if not ln:
                continue
            n += 1
            if max_events is not None and n > max_events:
                break
            ev = json.loads(ln)
            if str(ev.get("type") or ev.get("kind") or "") != "BODY_MOVED":
                continue
            tick = int(ev.get("tick") or -1)
            aid = str(ev.get("agent_id") or ev.get("actor_agent_id") or "agent_0")
            evidence = ev.get("evidence") if isinstance(ev.get("evidence"), dict) else {}
            forces = evidence.get("forces")
            if isinstance(forces, dict):
                out[(aid, tick)] = forces
    return out


def analyze_scientific_run(
    run_dir: Path,
    *,
    width: int = 32,
    height: int = 32,
    run_id: str | None = None,
    generation: int | None = None,
    attach_forces: bool = True,
    max_timeline_rows: int | None = None,
) -> dict[str, Any]:
    """Full Observer geometry analysis package for one saved run."""
    run_dir = Path(run_dir)
    timeline_path = run_dir / "scientific_timeline.jsonl"
    if not timeline_path.exists():
        raise FileNotFoundError(timeline_path)
    rows = load_timeline_jsonl(timeline_path, max_rows=max_timeline_rows)
    steps = steps_from_timeline_rows(rows, width=width, height=height)
    if attach_forces:
        events_path = run_dir / "scientific_events.jsonl"
        if events_path.exists():
            fmap = load_body_moved_forces(events_path)
            for st in steps:
                key = (str(st["agent_id"]), int(st["tick"]))
                if key in fmap:
                    st["forces"] = fmap[key]

    rid = run_id or run_dir.name
    trav = accumulate_traversability(steps)
    episodes = detect_episodes(steps, run_id=rid, generation=generation, width=width, height=height)
    deflection = top_deflection_cells(trav, min_attempts=8, limit=30)

    # Per-agent outcome tallies
    by_agent: dict[str, dict[str, int]] = {}
    for st in steps:
        aid = str(st["agent_id"])
        by_agent.setdefault(aid, {})
        oc = str(st.get("outcome") or "UNKNOWN")
        by_agent[aid][oc] = by_agent[aid].get(oc, 0) + 1

    # Sample geometry_context at a few interesting ticks
    context_samples = []
    for ep in episodes:
        if ep["kind"] in ("STRONG_DEFLECTION", "TRAVERSAL_REVERSAL", "CONTACT_CONDITIONED_TRAVERSAL"):
            context_samples.append(
                geometry_context(
                    steps,
                    agent_id=ep["agent_id"],
                    tick=int(ep["start_tick"]),
                    window=8,
                )
            )
            if len(context_samples) >= 12:
                break

    return {
        "run_id": rid,
        "generation": generation,
        "world": {"width": width, "height": height},
        "n_timeline_rows": len(rows),
        "n_steps": len(steps),
        "n_traversability_bins": len(trav),
        "n_episodes": len(episodes),
        "outcome_counts_by_agent": by_agent,
        "top_deflection_cells": deflection,
        "episodes": episodes,
        "geometry_context_samples": context_samples,
        "traversability_stats": list(trav.values()),
        "honesty": {
            "observer_only": True,
            "no_semantic_terrain_labels": True,
            "forces_source": "BODY_MOVED events (PARTIAL)" if attach_forces else "omitted",
        },
    }


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    n = 0
    with path.open("w") as fh:
        for row in rows:
            fh.write(json.dumps(row, default=str) + "\n")
            n += 1
    return n
