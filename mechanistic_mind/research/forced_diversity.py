\
"""Forced-diversity diagnostic schedules (experiment-only, not agent capability)."""
from __future__ import annotations

from typing import Iterable

from mechanistic_mind.agent import Action


def cycle_schedule(actions: Iterable[str], length: int) -> list[Action]:
    pool = [str(a) for a in actions]
    if not pool:
        raise ValueError("actions required")
    out: list[Action] = []
    for i in range(length):
        out.append(Action(pool[i % len(pool)]))
    return out


def default_diversity_kinds() -> tuple[str, ...]:
    """Representative physical kinds; MOVE targets filled at runtime from availability."""
    return ("WAIT", "EMIT", "MOVE", "USE")


def build_forced_actions_for_tick(
    *,
    tick: int,
    available: list[str] | tuple[str, ...],
    phase_length: int,
) -> Action | None:
    """Return a forced Action during [0, phase_length), else None (free policy).

    Does not prefer resources: cycles through available families fairly.
    """
    if tick >= phase_length:
        return None
    available = [str(a) for a in available]
    families = {
        "WAIT": [a for a in available if a == "WAIT"],
        "EMIT": [a for a in available if a == "EMIT"],
        "MOVE": [a for a in available if a.startswith("MOVE:")],
        "USE": [a for a in available if a.startswith(("USE:", "TAKE:", "PUSH:"))],
    }
    order = ["WAIT", "MOVE", "EMIT", "USE", "MOVE", "WAIT", "EMIT", "MOVE"]
    kind = order[tick % len(order)]
    choices = families.get(kind) or []
    if not choices:
        # fall back to any available non-identical preference
        for key in ("MOVE", "WAIT", "EMIT", "USE"):
            if families.get(key):
                choices = families[key]
                break
    if not choices:
        return Action("WAIT")
    return Action(choices[tick % len(choices)])
