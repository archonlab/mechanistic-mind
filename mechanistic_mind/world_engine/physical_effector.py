"""Update 4.59 — generic bounded physical effector.

Experimental. Default BodyConfig leaves this OFF.
Drive priority: researcher_physical_drive (RESEARCH_CONTROL), else
neural_physical_drive (MM-INT-1 DESIGNED_SUBSTRATE), else zeros.
Does not emit a semantic action kind.
Does not emit a semantic action kind.
"""
from __future__ import annotations

from typing import Any

# Physical lattice relations of a point occupant. Not direction names.
DEFAULT_SITES: tuple[tuple[int, int], ...] = ((0, -1), (-1, 0), (1, 0), (0, 1))
N_SITES = 4
DECAY = 0.50
BOUND = 1.0
# Preregistered from decay math (pulse 1.0 hops; decayed 0.50 does not), not from movement success.
THRESHOLD = 0.60


def default_effector_config() -> dict[str, Any]:
    return {
        "enabled": True,
        "decay": DECAY,
        "bound": BOUND,
        "threshold": THRESHOLD,
        "sites": [list(s) for s in DEFAULT_SITES],
    }


def clip_e(x: float, bound: float = BOUND) -> float:
    return max(0.0, min(float(bound), float(x)))


def normalize_sites(raw: Any) -> tuple[tuple[int, int], ...]:
    if not raw:
        return DEFAULT_SITES
    out = []
    for item in raw:
        out.append((int(item[0]), int(item[1])))
    return tuple(out)


def step_e(
    e: tuple[float, ...],
    drive: tuple[float, ...],
    *,
    decay: float = DECAY,
    bound: float = BOUND,
) -> tuple[float, ...]:
    n = len(e)
    d = tuple(float(drive[i]) if i < len(drive) else 0.0 for i in range(n))
    return tuple(clip_e(decay * float(e[i]) + d[i], bound) for i in range(n))


def resultant(e: tuple[float, ...], sites: tuple[tuple[int, int], ...]) -> tuple[float, float]:
    qx = sum(float(e[i]) * float(sites[i][0]) for i in range(len(e)))
    qy = sum(float(e[i]) * float(sites[i][1]) for i in range(len(e)))
    return (qx, qy)


def resolve_hop(
    q: tuple[float, float],
    *,
    threshold: float = THRESHOLD,
) -> tuple[tuple[int, int], str]:
    qx, qy = float(q[0]), float(q[1])
    ax, ay = abs(qx), abs(qy)
    if ax < threshold and ay < threshold:
        return (0, 0), "BELOW_THRESHOLD"
    if abs(ax - ay) < 1e-12:
        return (0, 0), "TIE"
    if ax > ay:
        return (1 if qx > 0 else -1, 0), "AXIS_X"
    return (0, 1 if qy > 0 else -1), "AXIS_Y"


def maybe_apply(
    engine: Any,
    state: dict[str, Any],
    agent_id: str,
    config: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Step E from researcher drive, resolve Q, maybe hop. No Action.kind.

    Returns (state, extra) where extra["distance"] is 1.0 on a realized hop.
    No-op if config is missing/disabled.
    """
    extra = {"distance": 0.0, "applied": False}
    if not isinstance(config, dict) or not config.get("enabled", True):
        return state, extra
    sites = normalize_sites(config.get("sites") or DEFAULT_SITES)
    decay = float(config.get("decay", DECAY))
    bound = float(config.get("bound", BOUND))
    threshold = float(config.get("threshold", THRESHOLD))
    rec = state.get("physical_effector")
    if not isinstance(rec, dict):
        rec = {}
    stored_sites = normalize_sites(rec.get("sites") or sites)
    raw_e = rec.get("E") or (0.0,) * len(stored_sites)
    e = tuple(float(raw_e[i]) if i < len(raw_e) else 0.0 for i in range(len(stored_sites)))
    drive_raw = state.pop("researcher_physical_drive", None)
    drive_source = "researcher"
    if drive_raw is None:
        drive_raw = state.pop("neural_physical_drive", None)
        drive_source = "neural"
    if drive_raw is None:
        drive = (0.0,) * len(stored_sites)
        drive_source = "none"
    else:
        drive = tuple(float(drive_raw[i]) if i < len(drive_raw) else 0.0 for i in range(len(stored_sites)))
    e_next = step_e(e, drive, decay=decay, bound=bound)
    q = resultant(e_next, stored_sites)
    hop, rule = resolve_hop(q, threshold=threshold)
    pos = engine.position(state, agent_id)
    dest = (int(pos[0]) + hop[0], int(pos[1]) + hop[1])
    realized = False
    blocked = False
    if hop != (0, 0):
        if engine.is_open(state, dest, ignore_agent_id=agent_id):
            state["agent_positions"][agent_id] = [int(dest[0]), int(dest[1])]
            extra["distance"] = 1.0
            realized = True
        else:
            blocked = True
    state["physical_effector"] = {
        "E": list(e_next),
        "sites": [list(s) for s in stored_sites],
        "Q": [float(q[0]), float(q[1])],
        "hop": [int(hop[0]), int(hop[1])],
        "rule": rule,
        "realized": realized,
        "blocked": blocked,
        "drive": list(drive),
        "drive_source": drive_source,
    }
    extra["applied"] = True
    extra["E"] = e_next
    extra["Q"] = q
    extra["hop"] = hop
    extra["realized"] = realized
    extra["blocked"] = blocked
    extra["rule"] = rule
    return state, extra
