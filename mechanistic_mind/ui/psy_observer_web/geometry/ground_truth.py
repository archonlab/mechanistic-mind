"""Observer-only ground-truth sampling of local physical geometry."""
from __future__ import annotations

from typing import Any

import numpy as np


def _world_size(world: Any, runtime: Any | None = None) -> tuple[int, int]:
    """PlanetState has no width/height attrs — use grid shape or config."""
    t = getattr(world, "T", None)
    if t is not None and hasattr(t, "shape") and len(t.shape) >= 2:
        return int(t.shape[1]), int(t.shape[0])  # W, H
    cfg = getattr(runtime, "config", None) if runtime is not None else None
    planet = getattr(cfg, "planet", None) if cfg is not None else None
    if planet is not None:
        return int(planet.width), int(planet.height)
    return 32, 32


def sample_local_flow(
    runtime: Any,
    *,
    x: float,
    y: float,
) -> dict[str, Any]:
    """Sample planet flow (vx, vy) at a world position. Observer ground truth."""
    world = getattr(runtime, "world", None)
    if world is None:
        return {"status": "NOT_AVAILABLE", "reason": "no_world"}
    try:
        w, h = _world_size(world, runtime)
        ix = int(np.floor(float(x))) % w
        iy = int(np.floor(float(y))) % h
        vx = float(world.vx[iy, ix])
        vy = float(world.vy[iy, ix])
        t = float(world.T[iy, ix])
        return {
            "status": "AVAILABLE",
            "cell": [ix, iy],
            "local_flow_vx": vx,
            "local_flow_vy": vy,
            "local_flow_mag": float(np.hypot(vx, vy)),
            "local_T": t,
            "note": "Planet flow field from −∇T (see planet/dynamics.step_flow). Observer GT.",
        }
    except Exception as exc:  # noqa: BLE001 — honesty over crash
        return {"status": "NOT_AVAILABLE", "reason": str(exc)}


def sample_force_contributions(runtime: Any) -> dict[str, Any]:
    """Last force contribution receipt if present (selected slot)."""
    fc = getattr(runtime, "last_force_contributions", None)
    if not isinstance(fc, dict):
        # TwoAgent: try selected slot
        slots = getattr(runtime, "slots", None)
        idx = int(getattr(runtime, "selected_index", 0) or 0)
        if slots and 0 <= idx < len(slots):
            fc = getattr(slots[idx], "last_force_contributions", None)
    if not isinstance(fc, dict):
        return {"status": "NOT_AVAILABLE", "reason": "no_force_contributions"}
    return {"status": "AVAILABLE", "contributions": dict(fc)}


def ground_truth_snapshot(runtime: Any) -> dict[str, Any]:
    """Bounded Observer ground-truth geometry at current tick (not empirical)."""
    slots = getattr(runtime, "slots", None)
    agents = []
    if slots:
        for i, slot in enumerate(slots):
            body = slot.body
            agents.append({
                "agent_id": f"agent_{i}",
                "x": float(body.x),
                "y": float(body.y),
                "vx": float(body.vx),
                "vy": float(body.vy),
                "local_flow": sample_local_flow(runtime, x=float(body.x), y=float(body.y)),
            })
    else:
        body = runtime.body
        agents.append({
            "agent_id": "agent_0",
            "x": float(body.x),
            "y": float(body.y),
            "vx": float(body.vx),
            "vy": float(body.vy),
            "local_flow": sample_local_flow(runtime, x=float(body.x), y=float(body.y)),
        })
    world = getattr(runtime, "world", None)
    flow_stats = {"status": "NOT_AVAILABLE"}
    if world is not None:
        mag = np.hypot(world.vx, world.vy)
        w, h = _world_size(world, runtime)
        flow_stats = {
            "status": "AVAILABLE",
            "flow_mag_mean": float(mag.mean()),
            "flow_mag_max": float(mag.max()),
            "flow_mag_p95": float(np.percentile(mag, 95)),
            "width": w,
            "height": h,
            "boundary": str(
                getattr(getattr(getattr(runtime, "config", None), "planet", None), "boundary_mode", "WRAP_PERIODIC")
            ),
        }
    return {
        "tick": int(getattr(runtime, "tick", -1)),
        "agents": agents,
        "world_flow_stats": flow_stats,
        "force_contributions": sample_force_contributions(runtime),
        "honesty": {
            "no_hard_barriers": True,
            "structure_kind": "emergent_flow_and_soft_contact",
            "observer_only": True,
            "not_agent_perception": True,
        },
    }


def flow_vector_grid(runtime: Any, *, stride: int = 2) -> dict[str, Any]:
    """Downsampled flow vectors for Observer overlay (bounded)."""
    world = getattr(runtime, "world", None)
    if world is None:
        return {"status": "NOT_AVAILABLE"}
    w, h = _world_size(world, runtime)
    s = max(1, int(stride))
    vectors = []
    for iy in range(0, h, s):
        for ix in range(0, w, s):
            vx = float(world.vx[iy, ix])
            vy = float(world.vy[iy, ix])
            mag = float(np.hypot(vx, vy))
            if mag < 1e-6:
                continue
            vectors.append({
                "x": ix + 0.5,
                "y": iy + 0.5,
                "vx": vx,
                "vy": vy,
                "mag": mag,
            })
    # Cap payload
    if len(vectors) > 256:
        vectors = vectors[:: max(1, len(vectors) // 256)][:256]
    return {
        "status": "AVAILABLE",
        "stride": s,
        "n": len(vectors),
        "vectors": vectors,
        "note": "Observer GT flow arrows from planet.vx/vy; not agent-visible map.",
    }
