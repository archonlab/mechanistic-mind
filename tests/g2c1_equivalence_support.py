"""G2C1 parent-vs-child canonical PHYSICAL projection (shared by tests + closure harness).

Projection = the runtime's own authoritative snapshot (bodies, objects, world/terrain deltas,
every mechanism state incl. SES/G2B/contact/acoustics/LPS/material ledgers, cognition, RNG)
PLUS every transient ``last_*`` receipt on the runtime(s) and world, normalized to a
canonical JSON form where every float is encoded by ``float.hex`` (exact, no rounding).

Excluded (and only these):
  * G2C1 metadata: any key containing ``ses_decomposition_contract`` (config block, state);
  * preset identity labels that necessarily differ by name (IDENTITY_KEYS below);
  * wall-clock telemetry (keys ending ``_us`` / ``_ms`` / named ``wall_time*``/``perf*``).
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import math
from typing import Any

G2C1_KEY = "ses_decomposition_contract"
# Name-only identity fields (parent and child are different presets by definition).
# Empirically the ONLY differing non-G2C1 paths (tick 0 and after steps) are these five
# name labels: snapshot.config.public_preset, snapshot.model.{public_preset, classification,
# display_name, phase_label, runtime_stage}, object provenance.public_preset.
IDENTITY_KEYS = frozenset({
    "public_preset", "classification", "phase_label", "runtime_stage", "display_name",
})
WALLCLOCK_SUFFIXES = ("_us", "_ms")


def _is_excluded(key: str) -> bool:
    k = str(key)
    if G2C1_KEY in k:
        return True
    if k in IDENTITY_KEYS:
        return True
    if k.endswith(WALLCLOCK_SUFFIXES) or k.startswith("wall_time") or k.startswith("perf_"):
        return True
    return False


def canon(x: Any, _depth: int = 0, _stack: tuple = ()) -> Any:
    if _depth > 40:
        return "<depth>"
    if x is None or isinstance(x, (bool, str)):
        return x
    if isinstance(x, int):
        return x
    if isinstance(x, float):
        if math.isnan(x):
            return {"f": "nan"}
        return {"f": float.hex(x)}
    if isinstance(x, dict):
        return {str(k): canon(v, _depth + 1, _stack) for k, v in sorted(x.items(), key=lambda kv: str(kv[0]))
                if not _is_excluded(str(k))}
    if isinstance(x, (list, tuple)):
        return [canon(v, _depth + 1, _stack) for v in x]
    if isinstance(x, (set, frozenset)):
        return sorted((canon(v, _depth + 1, _stack) for v in x), key=lambda v: json.dumps(v, sort_keys=True))
    # cycle guard only (object graph traversal); never used as a receipt dedup key
    marker = id(x)
    if marker in _stack:
        return "<cycle>"
    if dataclasses.is_dataclass(x) and not isinstance(x, type):
        d = {f.name: getattr(x, f.name) for f in dataclasses.fields(x)}
        return {"__dc__": type(x).__name__, **canon(d, _depth + 1, _stack + (marker,))}
    if hasattr(x, "to_dict") and callable(getattr(x, "to_dict")):
        try:
            return canon(x.to_dict(), _depth + 1, _stack + (marker,))
        except Exception:
            pass
    if hasattr(x, "__dict__"):
        return {"__obj__": type(x).__name__, **canon(dict(vars(x)), _depth + 1, _stack + (marker,))}
    return repr(x)


def _slots(rt: Any) -> list[Any]:
    slots = getattr(rt, "slots", None)
    return list(slots) if slots else [rt]


def _transients(obj: Any) -> dict[str, Any]:
    out = {}
    for k, v in sorted(vars(obj).items()):
        if k.startswith("last_") and not _is_excluded(k):
            out[k] = v
    return out


def physical_projection(rt: Any) -> dict[str, Any]:
    snap = rt.snapshot()
    world = getattr(rt, "world", None) or _slots(rt)[0].world
    proj = {
        "snapshot": canon(json.loads(json.dumps(snap, default=repr))),
        "world_transients": canon(_transients(world)),
        "slot_transients": [canon(_transients(s)) for s in _slots(rt)],
        "objects_live": canon([vars(o) for o in (getattr(world, "resource_objects", None) or [])]),
        "bodies_live": canon([vars(s.body) for s in _slots(rt)]),
    }
    return proj


def projection_bytes(rt: Any) -> bytes:
    return json.dumps(physical_projection(rt), sort_keys=True, separators=(",", ":")).encode()


def projection_digest(rt: Any) -> str:
    return hashlib.sha256(projection_bytes(rt)).hexdigest()


def first_difference(a: Any, b: Any, path: str = "") -> str | None:
    if type(a) is not type(b):
        return f"{path}: type {type(a).__name__} != {type(b).__name__}"
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                return f"{path}/{k}: missing on {'parent' if k not in a else 'child'}"
            d = first_difference(a[k], b[k], f"{path}/{k}")
            if d:
                return d
        return None
    if isinstance(a, list):
        if len(a) != len(b):
            return f"{path}: len {len(a)} != {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            d = first_difference(x, y, f"{path}[{i}]")
            if d:
                return d
        return None
    return None if a == b else f"{path}: {a!r} != {b!r}"


def g2c1_receipts(rt: Any) -> list[dict[str, Any]]:
    world = getattr(rt, "world", None) or _slots(rt)[0].world
    st = getattr(world, "ses_decomposition_contract_state", None)
    return list(getattr(st, "history", None) or [])
