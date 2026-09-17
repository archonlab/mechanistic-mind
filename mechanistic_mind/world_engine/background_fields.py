"""Continuous physical background fields (Update 4.19).

Formula-based fields: no full grids in world state (avoids deepcopy blowups and
unbounded storage). Local samples are agent-facing; Observer may request a
coarse ground-truth summary.
"""
from __future__ import annotations

from copy import deepcopy
from math import cos, pi, sin, sqrt
from typing import Any


FIELD_KEYS = (
    "temperature",
    "humidity",
    "pressure",
    "airflow_x",
    "airflow_y",
    "chemical_1",
    "chemical_2",
    "illumination",
    "vibration",
)


def default_field_spec() -> dict[str, Any]:
    return {
        "enabled": True,
        "keys": list(FIELD_KEYS),
        "noise": 0.01,
        "body_coupling": {
            "temperature": {"fatigue_delta": 0.0002},
            "humidity": {"hydration_delta": -0.0001},
        },
        "regions": {
            "A": {
                "center": [4, 3],
                "radius": 3,
                "base": {
                    "temperature": 0.62,
                    "humidity": 0.55,
                    "pressure": 0.48,
                    "airflow_x": 0.10,
                    "airflow_y": -0.05,
                    "chemical_1": 0.70,
                    "chemical_2": 0.20,
                    "illumination": 0.45,
                    "vibration": 0.15,
                },
            },
            "B": {
                "center": [14, 12],
                "radius": 3,
                "base": {
                    "temperature": 0.35,
                    "humidity": 0.72,
                    "pressure": 0.60,
                    "airflow_x": -0.12,
                    "airflow_y": 0.08,
                    "chemical_1": 0.22,
                    "chemical_2": 0.65,
                    "illumination": 0.70,
                    "vibration": 0.40,
                },
            },
        },
        "global_base": {
            "temperature": 0.50,
            "humidity": 0.50,
            "pressure": 0.50,
            "airflow_x": 0.0,
            "airflow_y": 0.0,
            "chemical_1": 0.40,
            "chemical_2": 0.40,
            "illumination": 0.50,
            "vibration": 0.20,
        },
        "temporal": {"period_ticks": 40, "amplitude": 0.06},
        "phase": "STABLE",
        "violations": {},
        "schema": {},
    }


def init_background_state(
    *,
    width: int,
    height: int,
    spec: dict[str, Any] | None,
    seed: int = 17,
) -> dict[str, Any]:
    spec = deepcopy(spec) if isinstance(spec, dict) else default_field_spec()
    if not spec.get("enabled", True):
        return {"enabled": False, "spec": spec, "tick": 0}
    return {
        "enabled": True,
        "spec": spec,
        "tick": 0,
        "width": int(width),
        "height": int(height),
        "seed": int(seed),
        "phase": str(spec.get("phase") or "STABLE"),
    }


def _base_at(spec: dict[str, Any], key: str, x: int, y: int) -> float:
    value = float((spec.get("global_base") or {}).get(key, 0.5))
    for region in (spec.get("regions") or {}).values():
        if not isinstance(region, dict):
            continue
        cx, cy = region.get("center") or [0, 0]
        radius = max(1e-9, float(region.get("radius") or 1))
        dist = sqrt((x - float(cx)) ** 2 + (y - float(cy)) ** 2)
        if dist <= radius:
            blend = max(0.0, 1.0 - dist / radius)
            target = float((region.get("base") or {}).get(key, value))
            value = value * (1.0 - blend) + target * blend
    return max(0.0, min(1.0, value))


def _value_at(bg: dict[str, Any], key: str, x: int, y: int) -> float:
    spec = bg.get("spec") or {}
    tick = int(bg.get("tick") or 0)
    temporal = spec.get("temporal") or {}
    period = max(1, int(temporal.get("period_ticks") or 40))
    amplitude = float(temporal.get("amplitude") or 0.0)
    noise = float(spec.get("noise") or 0.0)
    wave = amplitude * sin(2.0 * pi * (tick % period) / period)
    local_wave = wave * cos((x + 1) * 0.35) * sin((y + 1) * 0.27)
    jitter = noise * (2.0 * (((0.37 * x + 0.19 * y + 0.11 * tick + 0.07 * int(bg.get("seed") or 0)) % 1.0)) - 1.0)
    # Deterministic pseudo-noise in [0,1) without RNG object.
    frac = abs(sin((x + 1) * 12.9898 + (y + 1) * 78.233 + tick * 0.17 + float(bg.get("seed") or 0))) % 1.0
    jitter = noise * (2.0 * frac - 1.0)
    value = _base_at(spec, key, x, y) + local_wave + jitter
    phase = str(bg.get("phase") or spec.get("phase") or "STABLE")
    violations = (spec.get("violations") or {}).get(phase) or {}
    if key in violations:
        value = float(violations[key])
    return max(0.0, min(1.0, value))


def advance_background_fields(
    state: dict[str, Any],
    *,
    rng_uniform: float,
) -> list[dict[str, Any]]:
    bg = state.get("background_fields")
    if not isinstance(bg, dict) or not bg.get("enabled"):
        return []
    bg["tick"] = int(bg.get("tick") or 0) + 1
    # rng_uniform reserved for future stochastic field modes; tick advance is enough.
    _ = rng_uniform
    return [{"kind": "BACKGROUND_FIELD_TICK", "tick": bg["tick"], "phase": bg.get("phase")}]


def sample_local_fields(
    state: dict[str, Any],
    *,
    position: tuple[int, int],
) -> dict[str, float]:
    bg = state.get("background_fields")
    if not isinstance(bg, dict) or not bg.get("enabled"):
        return {}
    width = max(1, int(bg.get("width") or 1))
    height = max(1, int(bg.get("height") or 1))
    x = max(0, min(width - 1, int(position[0])))
    y = max(0, min(height - 1, int(position[1])))
    keys = [str(k) for k in ((bg.get("spec") or {}).get("keys") or FIELD_KEYS)]
    return {key: _value_at(bg, key, x, y) for key in keys}


def local_body_coupling(
    state: dict[str, Any],
    *,
    position: tuple[int, int],
) -> dict[str, float]:
    bg = state.get("background_fields")
    if not isinstance(bg, dict) or not bg.get("enabled"):
        return {}
    coupling = ((bg.get("spec") or {}).get("body_coupling") or {})
    if not coupling:
        return {}
    sample = sample_local_fields(state, position=position)
    effects: dict[str, float] = {}
    for key, mapping in coupling.items():
        if not isinstance(mapping, dict):
            continue
        level = float(sample.get(key, 0.0))
        for body_key, scale in mapping.items():
            effects[str(body_key)] = effects.get(str(body_key), 0.0) + float(scale) * level
    return effects


def set_background_phase(state: dict[str, Any], phase: str) -> None:
    bg = state.get("background_fields")
    if isinstance(bg, dict):
        bg["phase"] = str(phase)
        if isinstance(bg.get("spec"), dict):
            bg["spec"]["phase"] = str(phase)


def apply_schema_override(state: dict[str, Any], schema: dict[str, Any]) -> None:
    bg = state.get("background_fields")
    if not isinstance(bg, dict):
        return
    spec = bg.setdefault("spec", {})
    spec["schema"] = dict(schema or {})


def schema_terrain_multiplier(state: dict[str, Any]) -> float:
    bg = state.get("background_fields")
    if not isinstance(bg, dict):
        return 1.0
    schema = ((bg.get("spec") or {}).get("schema") or {})
    return max(0.05, float(schema.get("movement_cost_multiplier", 1.0)))


def observer_ground_truth(state: dict[str, Any], *, stride: int = 4) -> dict[str, Any]:
    """Coarse GT summary for Observer only — never enter cognition."""
    bg = state.get("background_fields")
    if not isinstance(bg, dict) or not bg.get("enabled"):
        return {"enabled": False}
    width = int(bg.get("width") or 1)
    height = int(bg.get("height") or 1)
    keys = [str(k) for k in ((bg.get("spec") or {}).get("keys") or FIELD_KEYS)]
    summary = {}
    for key in keys:
        vals = []
        for y in range(0, height, max(1, stride)):
            for x in range(0, width, max(1, stride)):
                vals.append(_value_at(bg, key, x, y))
        if not vals:
            continue
        summary[key] = {
            "mean": round(sum(vals) / len(vals), 4),
            "min": round(min(vals), 4),
            "max": round(max(vals), 4),
            "samples": len(vals),
        }
    return {
        "enabled": True,
        "tick": bg.get("tick"),
        "phase": bg.get("phase"),
        "field_summary": summary,
        "schema": ((bg.get("spec") or {}).get("schema") or {}),
        "violations_active": bool(((bg.get("spec") or {}).get("violations") or {}).get(bg.get("phase"))),
        "representation": "formula_based_no_full_grid",
    }
