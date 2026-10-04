"""G2C2 parent-vs-child physical projection (excludes classifier + G2C1 metadata)."""
from __future__ import annotations

from tests.g2c1_equivalence_support import (
    IDENTITY_KEYS,
    WALLCLOCK_SUFFIXES,
    first_difference,
)

G2C2_KEY = "ses_runtime_transition_classifier"
G2C1_KEY = "ses_decomposition_contract"


def _is_excluded(key: str) -> bool:
    k = str(key)
    if G2C2_KEY in k or G2C1_KEY in k:
        return True
    if k in IDENTITY_KEYS:
        return True
    if k.endswith(WALLCLOCK_SUFFIXES) or k.startswith("wall_time") or k.startswith("perf_"):
        return True
    return False


def physical_projection(rt):
    """Parent G2C1 and child G2C2 both carry G2C1 contract state; exclude both."""
    from tests import g2c1_equivalence_support as g1

    orig = g1._is_excluded
    try:
        g1._is_excluded = _is_excluded  # type: ignore[assignment]
        return g1.physical_projection(rt)
    finally:
        g1._is_excluded = orig


def projection_digest(rt) -> str:
    import hashlib
    import json
    return hashlib.sha256(
        json.dumps(physical_projection(rt), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def g2c2_receipts(rt) -> list[dict]:
    world = getattr(rt, "world", None)
    if world is None:
        slots = getattr(rt, "slots", None)
        world = slots[0].world if slots else None
    st = getattr(world, "ses_runtime_transition_classifier_state", None)
    return list(getattr(st, "history", None) or [])
