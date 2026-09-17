"""MM-CONFIG-1 — Current Physical World setup (seed + boundary fixture catalog).

Setup-time only. No live K / mask / M_ext editors. No new physics.
Fixture values are inspection fixtures frozen from OPEN-6 / OBS-1 patterns,
not claimed planetary environments.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .planet_session import PlanetInspectionSession

FIXTURE_OFF = "off"
FIXTURE_EDGE = "edge_strip_k016_mext_020304"
FIXTURE_CELL = "single_cell_k01_mext_025"
FIXTURE_FULL = "full_grid_k005_mext_025"

FIXTURE_IDS: tuple[str, ...] = (
    FIXTURE_OFF,
    FIXTURE_EDGE,
    FIXTURE_CELL,
    FIXTURE_FULL,
)

FIXTURE_LABELS: dict[str, str] = {
    FIXTURE_OFF: "OFF (production default)",
    FIXTURE_EDGE: "ON · edge strips · K=0.16 · M_ext=[0.2,0.3,0.4]",
    FIXTURE_CELL: "ON · single cell · K=0.1 · M_ext=[0.25,0.25,0.25]",
    FIXTURE_FULL: "ON · full grid · K=0.05 · M_ext=[0.25,0.25,0.25]",
}


@dataclass(frozen=True, slots=True)
class CurrentPhysicalWorldSetup:
    seed: int = 17
    boundary_fixture_id: str = FIXTURE_OFF

    def validate(self) -> None:
        if int(self.seed) < 0:
            raise ValueError("seed must be >= 0")
        if self.boundary_fixture_id not in FIXTURE_IDS:
            raise ValueError(
                f"Unknown boundary fixture: {self.boundary_fixture_id!r}"
            )


def list_fixture_ids() -> tuple[str, ...]:
    return FIXTURE_IDS


def fixture_label(fixture_id: str) -> str:
    return FIXTURE_LABELS.get(fixture_id, fixture_id)


def build_mask(fixture_id: str, height: int, width: int) -> np.ndarray | None:
    """Return contact mask for ON fixtures; None for off."""
    if fixture_id == FIXTURE_OFF:
        return None
    h, w = int(height), int(width)
    if h < 1 or w < 1:
        raise ValueError("height/width must be >= 1")
    mask = np.zeros((h, w), dtype=bool)
    if fixture_id == FIXTURE_EDGE:
        # Left and right edge strips (1 cell wide) — explicit inspection geometry.
        mask[:, 0] = True
        mask[:, -1] = True
    elif fixture_id == FIXTURE_CELL:
        y = min(4, h - 1)
        x = min(4, w - 1)
        mask[y, x] = True
    elif fixture_id == FIXTURE_FULL:
        mask[:, :] = True
    else:
        raise ValueError(f"Unknown boundary fixture: {fixture_id!r}")
    return mask


def fixture_params(fixture_id: str) -> dict[str, Any]:
    """Explicit K / M_ext for ON fixtures; empty for off."""
    if fixture_id == FIXTURE_OFF:
        return {"enabled": False, "K": None, "M_ext": None}
    if fixture_id == FIXTURE_EDGE:
        return {"enabled": True, "K": 0.16, "M_ext": [0.2, 0.3, 0.4]}
    if fixture_id == FIXTURE_CELL:
        return {"enabled": True, "K": 0.1, "M_ext": [0.25, 0.25, 0.25]}
    if fixture_id == FIXTURE_FULL:
        return {"enabled": True, "K": 0.05, "M_ext": [0.25, 0.25, 0.25]}
    raise ValueError(f"Unknown boundary fixture: {fixture_id!r}")


def apply_current_setup(
    session: PlanetInspectionSession,
    setup: CurrentPhysicalWorldSetup,
) -> Any:
    """Reset planet to setup.seed then apply boundary fixture (setup-time)."""
    setup.validate()
    display = session.reset(seed=int(setup.seed))
    params = fixture_params(setup.boundary_fixture_id)
    if not params["enabled"]:
        return session.apply_boundary_fixture(enabled=False)
    h = int(session.config.height)
    w = int(session.config.width)
    mask = build_mask(setup.boundary_fixture_id, h, w)
    return session.apply_boundary_fixture(
        enabled=True,
        contact_mask=mask,
        K=float(params["K"]),
        M_ext=list(params["M_ext"]),
    )


def apply_fixture_to_session(
    session: PlanetInspectionSession,
    fixture_id: str,
    seed: int | None = None,
) -> Any:
    return apply_current_setup(
        session,
        CurrentPhysicalWorldSetup(
            seed=int(session.seed if seed is None else seed),
            boundary_fixture_id=fixture_id,
        ),
    )
