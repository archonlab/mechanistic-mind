"""LIVE world interventions + provenance for Beta 2 (Observer-only).

Does not retune physics/cognition. Records WORLD_INTERVENTION events when
effective configuration changes without rebuilding the runtime.
"""
from __future__ import annotations

import uuid
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from mechanistic_mind.research.climate_authority import (
    effective_world_configuration,
    effective_world_fingerprint,
)

# Controls that require APPLY & RESET WORLD (runtime rebuild).
WORLD_STRUCTURAL_KEYS = frozenset({
    "seed",
    "width",
    "height",
    "boundary_mode",
    "boundary_topology",
    "agent_count",
    "terrain_seed",
    "map_size",
})

# Live-safe ecology / experimental mutation keys (config mutation on existing runtime).
LIVE_ECOLOGY_KEYS = frozenset({
    "ecology_preset",
})

LIVE_MODEL_KEYS = frozenset({
    "cognition_enabled",
})


def classify_control(path: str) -> str:
    """Return WORLD_STRUCTURAL | LIVE | UNKNOWN."""
    p = str(path or "")
    if p in WORLD_STRUCTURAL_KEYS or p.startswith("world.") and any(
        p.endswith(k) for k in ("width", "height", "boundary_mode", "terrain_seed")
    ):
        return "WORLD_STRUCTURAL"
    if p in LIVE_ECOLOGY_KEYS or p.startswith("ecology") or p.startswith("mechanism."):
        return "LIVE"
    if p in LIVE_MODEL_KEYS:
        return "LIVE"
    if p.startswith("resources.") or p.startswith("climate") or p.startswith("experimental"):
        return "LIVE"
    if p.startswith("physical_near_field_vision.") or p.startswith("near_field_exteroception."):
        return "LIVE"
    return "UNKNOWN"


def fingerprint_for_runtime(runtime) -> str:
    return effective_world_fingerprint(runtime=runtime)


def effective_snapshot(runtime) -> dict[str, Any]:
    try:
        return effective_world_configuration(runtime)
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


def build_world_intervention_event(
    *,
    simulation_tick: int,
    runtime_generation: int,
    session_instance_id: str | None,
    category: str,
    changes: dict[str, dict[str, Any]],
    fingerprint_before: str,
    fingerprint_after: str,
    history_reset: bool = False,
    cognition_reset: bool = False,
    body_reset: bool = False,
    source: str = "observer_ui",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Immutable structured provenance for a live world/mechanism mutation."""
    eid = f"wi-{uuid.uuid4().hex[:12]}"
    ev: dict[str, Any] = {
        "type": "WORLD_INTERVENTION",
        "kind": "WORLD_INTERVENTION",
        "event_id": eid,
        "tick": int(simulation_tick),
        "simulation_tick": int(simulation_tick),
        "runtime_generation": int(runtime_generation),
        "session_instance_id": session_instance_id,
        "intervention_category": str(category),
        "category": str(category),
        "changes": deepcopy(changes),
        "effective_world_fingerprint_before": fingerprint_before,
        "effective_world_fingerprint_after": fingerprint_after,
        "history_reset": bool(history_reset),
        "cognition_reset": bool(cognition_reset),
        "body_reset": bool(body_reset),
        "source": str(source),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent_id": "observer",
        "actor_agent_id": "observer",
        "evidence": {
            "intervention_category": category,
            "changes": deepcopy(changes),
            "effective_world_fingerprint_before": fingerprint_before,
            "effective_world_fingerprint_after": fingerprint_after,
            "history_reset": bool(history_reset),
            "cognition_reset": bool(cognition_reset),
            "body_reset": bool(body_reset),
        },
    }
    if extra:
        ev.update(extra)
    return ev


def regimes_from_interventions(
    interventions: list[dict[str, Any]],
    *,
    start_tick: int = 0,
    end_tick: int | None = None,
    initial_fingerprint: str | None = None,
) -> dict[str, Any]:
    """Build STATIC / MULTI-REGIME report from ordered WORLD_INTERVENTION events."""
    ordered = sorted(
        [e for e in interventions if str(e.get("type") or e.get("kind") or "") == "WORLD_INTERVENTION"],
        key=lambda e: (int(e.get("simulation_tick") or e.get("tick") or 0), str(e.get("event_id") or "")),
    )
    if not ordered:
        return {
            "configuration_history": "STATIC",
            "n_interventions": 0,
            "n_regimes": 1,
            "regimes": [
                {
                    "regime_index": 0,
                    "tick_start": int(start_tick),
                    "tick_end": end_tick,
                    "effective_fingerprint": initial_fingerprint,
                    "note": "No live WORLD_INTERVENTION events recorded.",
                }
            ],
            "interventions": [],
        }

    regimes: list[dict[str, Any]] = []
    inter_out: list[dict[str, Any]] = []
    cursor = int(start_tick)
    fp = initial_fingerprint or ordered[0].get("effective_world_fingerprint_before")
    for i, ev in enumerate(ordered):
        t = int(ev.get("simulation_tick") or ev.get("tick") or 0)
        regimes.append({
            "regime_index": i,
            "tick_start": cursor,
            "tick_end": t - 1 if t > cursor else cursor,
            "effective_fingerprint": fp,
        })
        inter_out.append({
            "tick": t,
            "category": ev.get("intervention_category") or ev.get("category"),
            "changes": ev.get("changes") or (ev.get("evidence") or {}).get("changes"),
            "fingerprint_before": ev.get("effective_world_fingerprint_before"),
            "fingerprint_after": ev.get("effective_world_fingerprint_after"),
            "history_reset": bool(ev.get("history_reset", False)),
            "cognition_reset": bool(ev.get("cognition_reset", False)),
            "body_reset": bool(ev.get("body_reset", False)),
            "event_id": ev.get("event_id"),
        })
        fp = ev.get("effective_world_fingerprint_after") or fp
        cursor = t
    regimes.append({
        "regime_index": len(ordered),
        "tick_start": cursor,
        "tick_end": end_tick,
        "effective_fingerprint": fp,
    })
    return {
        "configuration_history": "MULTI_REGIME",
        "n_interventions": len(ordered),
        "n_regimes": len(regimes),
        "regimes": regimes,
        "interventions": inter_out,
        "note": (
            "Configuration history is multi-regime. The final effective configuration "
            "must not be treated as if it existed for the entire biography."
        ),
    }
