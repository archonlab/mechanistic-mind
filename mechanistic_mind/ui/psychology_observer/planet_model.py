"""Read-only planet WORLD projection for Psychology Observer (MM-OBS-1).

OBSERVER_ACCESS only. Does not write PlanetState, configure boundary mid-run
from UI controls, or feed organism cognition.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

import numpy as np

from mechanistic_mind.planet.boundary import ACCOUNTING_TOL, LAW_VERSION, boundary_from_dict
from mechanistic_mind.planet.runtime import snapshot_stats, serialize_planet_state

SIGN_CONVENTION = "+ = external -> WORLD; - = WORLD -> external"
FIELD_LAYERS = ("M0", "M1", "M2", "Temperature", "Flow", "Wave")
HISTORY_MAX = 256


@dataclass(frozen=True, slots=True)
class BoundaryDisplay:
    enabled: bool
    law_version: str
    K: float | None
    M_ext: tuple[float, ...] | None
    contact_count: int
    mask_sha256: str | None
    contact_mask: np.ndarray | None  # (H,W) bool or None
    last_signed_flux: tuple[float, ...]
    cum_import: tuple[float, ...]
    cum_export: tuple[float, ...]
    last_residual_max: float
    G_total: float | None
    accounting_tol: float = ACCOUNTING_TOL

    @property
    def net_flux(self) -> tuple[float, ...]:
        return tuple(float(i) - float(e) for i, e in zip(self.cum_import, self.cum_export))

    @property
    def residual_within_tolerance(self) -> bool:
        return float(self.last_residual_max) <= float(self.accounting_tol)


@dataclass(frozen=True, slots=True)
class PlanetDisplayState:
    tick: int
    height: int
    width: int
    n_materials: int
    T: np.ndarray
    M: np.ndarray
    vx: np.ndarray
    vy: np.ndarray
    u: np.ndarray
    boundary: BoundaryDisplay
    stats: dict[str, Any]
    config: dict[str, Any]
    topology: str = "toroidal"
    seed: int | None = None
    source: str = "live"  # live | snapshot | legacy

    @property
    def flow_magnitude(self) -> np.ndarray:
        return np.hypot(self.vx, self.vy)


def _as_float_tuple(values: Any, n: int) -> tuple[float, ...]:
    if values is None:
        return tuple(0.0 for _ in range(n))
    arr = np.asarray(values, dtype=np.float64).reshape(-1)
    out = [float(arr[i]) if i < arr.size else 0.0 for i in range(n)]
    return tuple(out)


def boundary_display_from_mapping(
    raw: Mapping[str, Any] | None,
    *,
    height: int,
    width: int,
    n_materials: int,
    mask_sha256: str | None = None,
) -> BoundaryDisplay:
    """Map production boundary dict / missing legacy -> display. Never fabricates ON."""
    if raw is None or not isinstance(raw, dict):
        return BoundaryDisplay(
            enabled=False,
            law_version=LAW_VERSION,
            K=None,
            M_ext=None,
            contact_count=0,
            mask_sha256=None,
            contact_mask=None,
            last_signed_flux=_as_float_tuple(None, n_materials),
            cum_import=_as_float_tuple(None, n_materials),
            cum_export=_as_float_tuple(None, n_materials),
            last_residual_max=0.0,
            G_total=None,
        )
    enabled = bool(raw.get("enabled", False))
    mask = raw.get("contact_mask")
    mask_arr = None
    if enabled and mask is not None:
        mask_arr = np.asarray(mask, dtype=bool)
        if mask_arr.shape != (height, width):
            # malformed: keep metadata but drop overlay rather than invent geometry
            mask_arr = None
    contact_count = int(raw.get("contact_count") or (int(mask_arr.sum()) if mask_arr is not None else 0))
    K = raw.get("K")
    M_ext = raw.get("M_ext")
    return BoundaryDisplay(
        enabled=enabled,
        law_version=str(raw.get("law_version") or LAW_VERSION),
        K=None if K is None else float(K),
        M_ext=None if M_ext is None else _as_float_tuple(M_ext, n_materials),
        contact_count=contact_count,
        mask_sha256=mask_sha256 if mask_sha256 is not None else (
            None if not enabled else None
        ),
        contact_mask=None if not enabled else mask_arr,
        last_signed_flux=_as_float_tuple(raw.get("last_signed_flux"), n_materials),
        cum_import=_as_float_tuple(raw.get("cum_import"), n_materials),
        cum_export=_as_float_tuple(raw.get("cum_export"), n_materials),
        last_residual_max=float(raw.get("last_residual_max") or 0.0),
        G_total=None if raw.get("G_total") is None else float(raw.get("G_total")),
    )


def display_from_planet_state(
    state: Any,
    cfg: Any,
    *,
    seed: int | None = None,
    source: str = "live",
) -> PlanetDisplayState:
    from mechanistic_mind.planet.boundary import mask_sha256

    stats = snapshot_stats(state, cfg, seed=int(seed or 0))
    bdict = stats.get("external_material_boundary")
    h, w = state.T.shape
    n = int(state.M.shape[0])
    boundary = boundary_display_from_mapping(
        bdict,
        height=h,
        width=w,
        n_materials=n,
        mask_sha256=stats.get("external_material_boundary_mask_sha256"),
    )
    # attach hash if ON
    if boundary.enabled and boundary.mask_sha256 is None and state.external_material_boundary.contact_mask is not None:
        boundary = BoundaryDisplay(
            **{**boundary.__dict__, "mask_sha256": mask_sha256(state.external_material_boundary.contact_mask)}
        )
    return PlanetDisplayState(
        tick=int(state.tick),
        height=int(h),
        width=int(w),
        n_materials=n,
        T=np.asarray(state.T, dtype=np.float64),
        M=np.asarray(state.M, dtype=np.float64),
        vx=np.asarray(state.vx, dtype=np.float64),
        vy=np.asarray(state.vy, dtype=np.float64),
        u=np.asarray(state.u, dtype=np.float64),
        boundary=boundary,
        stats=dict(stats),
        config=cfg.to_dict() if hasattr(cfg, "to_dict") else dict(cfg),
        seed=seed,
        source=source,
    )


def display_from_serialized(payload: Mapping[str, Any], *, source: str = "snapshot") -> PlanetDisplayState:
    """Restore via production restore path semantics (legacy missing -> OFF)."""
    from mechanistic_mind.planet.runtime import restore_planet_state

    # tolerate missing boundary key
    data = dict(payload)
    st, cfg = restore_planet_state(data)
    seed = None
    if isinstance(data.get("config"), dict) and "seed" in data:
        seed = data.get("seed")
    return display_from_planet_state(st, cfg, seed=seed if isinstance(seed, int) else None, source=source)


def field_array(display: PlanetDisplayState, layer: str) -> np.ndarray:
    if layer == "M0":
        return display.M[0]
    if layer == "M1":
        return display.M[1] if display.n_materials > 1 else np.zeros_like(display.T)
    if layer == "M2":
        return display.M[2] if display.n_materials > 2 else np.zeros_like(display.T)
    if layer == "Temperature":
        return display.T
    if layer == "Flow":
        return display.flow_magnitude
    if layer == "Wave":
        return display.u
    raise KeyError(f"unknown field layer: {layer}")


def field_minmax(arr: np.ndarray) -> tuple[float, float]:
    return float(np.min(arr)), float(np.max(arr))


def ephemeral_local_J(display: PlanetDisplayState) -> np.ndarray | None:
    """UI-derived per-cell signed J on contact; NOT stored in production.

    J = K * (M_ext - M) on mask; 0 elsewhere. Returns shape (n,H,W) or None if OFF.
    """
    b = display.boundary
    if not b.enabled or b.contact_mask is None or b.K is None or b.M_ext is None:
        return None
    J = np.zeros_like(display.M)
    for c in range(display.n_materials):
        J[c][b.contact_mask] = float(b.K) * (float(b.M_ext[c]) - display.M[c][b.contact_mask])
    return J


def cell_inspector(display: PlanetDisplayState, y: int, x: int) -> dict[str, Any]:
    h, w = display.height, display.width
    y = int(y) % h
    x = int(x) % w
    contact = bool(display.boundary.contact_mask[y, x]) if (
        display.boundary.enabled and display.boundary.contact_mask is not None
    ) else False
    J = ephemeral_local_J(display)
    local_j = None
    if J is not None and contact:
        local_j = tuple(float(J[c, y, x]) for c in range(display.n_materials))
    return {
        "y": y,
        "x": x,
        "T": float(display.T[y, x]),
        "M0": float(display.M[0, y, x]),
        "M1": float(display.M[1, y, x]) if display.n_materials > 1 else None,
        "M2": float(display.M[2, y, x]) if display.n_materials > 2 else None,
        "vx": float(display.vx[y, x]),
        "vy": float(display.vy[y, x]),
        "u": float(display.u[y, x]),
        "boundary_contact": contact,
        "local_J": local_j,
        "sign_convention": SIGN_CONVENTION,
        "observer_only": True,
        "note": "UI inspection does not alter agent observation.",
    }


def format_world_status(display: PlanetDisplayState) -> str:
    s = display.stats
    lines = [
        "PHYSICAL WORLD STATUS",
        f"tick={display.tick}  dims={display.height}x{display.width}  topology={display.topology}",
        f"source={display.source}  seed={display.seed}",
        f"T mean={s.get('T_mean'):.6g}  min={s.get('T_min'):.6g}  max={s.get('T_max'):.6g}",
        f"M0_sum={s.get('M0_sum'):.6g}  M1_sum={s.get('M1_sum'):.6g}  M2_sum={s.get('M2_sum'):.6g}",
        f"M_total={s.get('M_total'):.6g}  matter_err={s.get('matter_err'):.6g}",
        f"speed_mean={s.get('speed_mean'):.6g}  speed_max={s.get('speed_max'):.6g}",
        f"u_abs_mean={s.get('u_abs_mean'):.6g}  u_abs_max={s.get('u_abs_max'):.6g}",
    ]
    return "\n".join(lines)


def format_boundary_panel(display: PlanetDisplayState) -> str:
    b = display.boundary
    lines = ["EXTERNAL MATERIAL BOUNDARY"]
    if not b.enabled:
        lines.append("OFF")
        lines.append("no external material exchange active")
        return "\n".join(lines)
    lines.append("ON")
    lines.append(f"law: {b.law_version}")
    if b.law_version != LAW_VERSION:
        lines.append("visualization detail: unsupported law id (raw shown)")
    lines.append(f"Exchange conductance K: {b.K}")
    if b.M_ext is not None:
        lines.append("External reservoir")
        for i, v in enumerate(b.M_ext):
            lines.append(f"  M{i}: {v:.8g}")
    lines.append(f"contact_count: {b.contact_count}")
    if b.mask_sha256:
        lines.append(f"mask_sha256: {b.mask_sha256}")
    lines.append(f"sign convention: {SIGN_CONVENTION}")
    lines.append("last_signed_flux (per channel):")
    for i, v in enumerate(b.last_signed_flux):
        lines.append(f"  M{i}: {v:.8g}")
    lines.append("cumulative import:")
    for i, v in enumerate(b.cum_import):
        lines.append(f"  M{i}: {v:.8g}")
    lines.append("cumulative export:")
    for i, v in enumerate(b.cum_export):
        lines.append(f"  M{i}: {v:.8g}")
    lines.append("net (= import - export):")
    for i, v in enumerate(b.net_flux):
        lines.append(f"  M{i}: {v:.8g}")
    lines.append("Accounting residual:")
    lines.append(f"  {b.last_residual_max:.6e}")
    lines.append(f"  tolerance: {b.accounting_tol:.6e}")
    lines.append(
        "  within tolerance" if b.residual_within_tolerance else "  ABOVE tolerance"
    )
    return "\n".join(lines)


@dataclass
class BoundedScalarHistory:
    maxlen: int = HISTORY_MAX
    _rows: deque = field(default_factory=deque)

    def __post_init__(self) -> None:
        self._rows = deque(maxlen=self.maxlen)

    def push(self, display: PlanetDisplayState) -> None:
        b = display.boundary
        self._rows.append(
            {
                "tick": display.tick,
                "M0_sum": display.stats.get("M0_sum"),
                "M1_sum": display.stats.get("M1_sum"),
                "M2_sum": display.stats.get("M2_sum"),
                "import_sum": float(sum(b.cum_import)),
                "export_sum": float(sum(b.cum_export)),
                "residual": b.last_residual_max,
            }
        )

    def as_list(self) -> list[dict[str, Any]]:
        return list(self._rows)


def assert_read_only_surface() -> tuple[str, ...]:
    """Symbols that must NOT be exposed as live Observer edit controls."""
    return (
        "live_K_slider",
        "live_mask_paint",
        "live_M_ext_slider",
        "configure_external_material_boundary_from_ui",
    )
