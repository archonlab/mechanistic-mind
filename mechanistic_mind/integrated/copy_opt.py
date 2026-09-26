"""Causal / receipt copy helpers — observational optimization support.

Preserves JSON-like scientific evidence without ``copy.deepcopy`` on hot paths
when structures are plain dict/list/tuple/scalar trees (no shared mutable DAG
that requires memoization).
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any


def jsonish_copy(obj: Any) -> Any:
    """Deep-copy JSON-like trees (dict/list/tuple/scalars).

    Faster than ``deepcopy`` for cognition/causal payloads that are plain
    nested mappings of immutable leaves. Falls back to ``deepcopy`` for
    unrecognized types (NumPy arrays, custom objects, etc.).
    """
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, dict):
        return {k: jsonish_copy(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [jsonish_copy(v) for v in obj]
    if isinstance(obj, tuple):
        return [jsonish_copy(v) for v in obj]  # receipts historically store lists
    # Bytes / numeric containers / unknown → full deepcopy for safety
    return deepcopy(obj)


def capture_flat_mapping(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Shallow-capture a flat mapping of immutable leaves (causal event payloads)."""
    if not payload:
        return {}
    # Values in causal event payloads are scalars / None; copy the dict container.
    return dict(payload)


def capture_provenance(provenance: Any) -> Any:
    """Capture edge provenance without deepcopy when already immutable/flat."""
    if provenance is None or isinstance(provenance, (bool, int, float, str)):
        return provenance
    if isinstance(provenance, dict):
        return dict(provenance)
    if isinstance(provenance, (list, tuple)):
        return list(provenance)
    return deepcopy(provenance)
