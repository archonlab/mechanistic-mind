"""External material boundary — OPEN-5 frozen contract (open1_signed_v1).

Default OFF. Explicit mask/K/M_ext required when ON. No geometry RNG.
No BODY/organism/RESP. Law: J=K(M_ext-M) on contact cells; M:=max(M+J,0).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

LAW_VERSION = "open1_signed_v1"
K_MAX_EXCLUSIVE = 2.0  # reject K >= 2 for unit-tick explicit update
ACCOUNTING_TOL = 1e-9


class ExternalMaterialBoundaryConfigError(ValueError):
    """Malformed ON configuration for external material boundary."""


@dataclass
class ExternalMaterialBoundary:
    """Runtime boundary state. Default enabled=False (OFF)."""

    enabled: bool = False
    contact_mask: np.ndarray | None = None  # bool (H, W)
    K: float | None = None
    M_ext: np.ndarray | None = None  # (n_materials,)
    cum_import: np.ndarray | None = None  # (n_materials,)
    cum_export: np.ndarray | None = None
    last_signed_flux: np.ndarray | None = None  # imp - exp this tick
    last_residual_max: float = 0.0
    law_version: str = LAW_VERSION

    def copy(self) -> "ExternalMaterialBoundary":
        return ExternalMaterialBoundary(
            enabled=self.enabled,
            contact_mask=None if self.contact_mask is None else self.contact_mask.copy(),
            K=self.K,
            M_ext=None if self.M_ext is None else self.M_ext.copy(),
            cum_import=None if self.cum_import is None else self.cum_import.copy(),
            cum_export=None if self.cum_export is None else self.cum_export.copy(),
            last_signed_flux=None if self.last_signed_flux is None else self.last_signed_flux.copy(),
            last_residual_max=self.last_residual_max,
            law_version=self.law_version,
        )


def off_boundary(n_materials: int = 3) -> ExternalMaterialBoundary:
    z = np.zeros(int(n_materials), dtype=np.float64)
    return ExternalMaterialBoundary(
        enabled=False,
        contact_mask=None,
        K=None,
        M_ext=None,
        cum_import=z.copy(),
        cum_export=z.copy(),
        last_signed_flux=z.copy(),
        last_residual_max=0.0,
        law_version=LAW_VERSION,
    )


def validate_external_material_boundary(
    *,
    enabled: bool,
    contact_mask: np.ndarray | None,
    K: float | None,
    M_ext: np.ndarray | list | tuple | None,
    height: int,
    width: int,
    n_materials: int,
) -> list[str]:
    """Return list of error messages; empty if valid. OFF always valid."""
    if not enabled:
        return []
    errs: list[str] = []
    if contact_mask is None:
        errs.append("external material boundary is enabled but contact_mask is missing")
    else:
        m = np.asarray(contact_mask)
        if m.shape != (height, width):
            errs.append(
                f"external material boundary contact_mask shape {m.shape} "
                f"!= WORLD ({height}, {width})"
            )
        else:
            if m.dtype != bool and not np.issubdtype(m.dtype, np.bool_):
                if not (np.issubdtype(m.dtype, np.integer) or np.issubdtype(m.dtype, np.floating)):
                    errs.append("external material boundary contact_mask must be boolean or 0/1")
                elif not np.isin(m, [0, 1]).all():
                    errs.append("external material boundary contact_mask must be boolean or 0/1")
            if not np.isfinite(np.asarray(m, dtype=np.float64)).all():
                errs.append("external material boundary contact_mask contains nonfinite values")
            if int(np.asarray(m, dtype=bool).sum()) == 0:
                errs.append("external material boundary contact_mask is empty while enabled")
    if K is None:
        errs.append("external material boundary is enabled but exchange conductance K is missing")
    else:
        try:
            kf = float(K)
        except (TypeError, ValueError):
            errs.append("external material boundary K is not a finite float")
            kf = float("nan")
        if not np.isfinite(kf):
            errs.append("external material boundary K is nonfinite")
        elif kf < 0.0:
            errs.append("external material boundary K is negative")
        elif kf >= K_MAX_EXCLUSIVE:
            errs.append(
                f"external material boundary K={kf} >= {K_MAX_EXCLUSIVE} "
                "is unstable for unit-tick explicit update"
            )
    if M_ext is None:
        errs.append("external material boundary is enabled but reservoir concentration M_ext is missing")
    else:
        me = np.asarray(M_ext, dtype=np.float64).reshape(-1)
        if me.shape != (n_materials,):
            errs.append(
                f"external material boundary M_ext shape {me.shape} != ({n_materials},)"
            )
        if not np.isfinite(me).all():
            errs.append("external material boundary M_ext contains nonfinite values")
        if me.size and np.any(me < 0.0):
            errs.append("external material boundary M_ext is negative")
    return errs


def configure_external_material_boundary(
    state: Any,
    *,
    enabled: bool,
    contact_mask: np.ndarray | None = None,
    K: float | None = None,
    M_ext: np.ndarray | list | tuple | None = None,
) -> None:
    """Set boundary on PlanetState. Raises on invalid ON config."""
    h, w = state.T.shape
    n = int(state.M.shape[0])
    errs = validate_external_material_boundary(
        enabled=enabled,
        contact_mask=contact_mask,
        K=K,
        M_ext=M_ext,
        height=h,
        width=w,
        n_materials=n,
    )
    if errs:
        raise ExternalMaterialBoundaryConfigError("; ".join(errs))
    b = state.external_material_boundary
    if not enabled:
        # preserve counters? OFF clears active mask/K/M_ext; keep counters for provenance
        b.enabled = False
        b.contact_mask = None
        b.K = None
        b.M_ext = None
        return
    mask = np.asarray(contact_mask, dtype=bool)
    me = np.asarray(M_ext, dtype=np.float64).reshape(n)
    b.enabled = True
    b.contact_mask = mask.copy()
    b.K = float(K)
    b.M_ext = me.copy()
    if b.cum_import is None or b.cum_import.shape != (n,):
        b.cum_import = np.zeros(n, dtype=np.float64)
        b.cum_export = np.zeros(n, dtype=np.float64)
        b.last_signed_flux = np.zeros(n, dtype=np.float64)
    b.law_version = LAW_VERSION


def step_external_material_boundary(state: Any) -> None:
    """Apply signed exchange if enabled; skip entirely when OFF (OPEN-5)."""
    b = getattr(state, "external_material_boundary", None)
    if b is None or not b.enabled:
        return
    mask = b.contact_mask
    K = float(b.K)
    M_ext = b.M_ext
    M = state.M
    n = M.shape[0]
    J = np.zeros_like(M)
    for c in range(n):
        J[c, mask] = K * (float(M_ext[c]) - M[c, mask])
    imp = np.where(J > 0.0, J, 0.0).sum(axis=(1, 2))
    exp = np.where(J < 0.0, -J, 0.0).sum(axis=(1, 2))
    M_after = np.maximum(M + J, 0.0)
    residual = np.abs((M_after - M).sum(axis=(1, 2)) - (imp - exp))
    b.last_residual_max = float(residual.max())
    b.last_signed_flux = (imp - exp).astype(np.float64)
    if b.cum_import is None:
        b.cum_import = np.zeros(n, dtype=np.float64)
        b.cum_export = np.zeros(n, dtype=np.float64)
    b.cum_import = b.cum_import + imp
    b.cum_export = b.cum_export + exp
    state.M = M_after


def boundary_to_dict(b: ExternalMaterialBoundary) -> dict[str, Any]:
    return {
        "enabled": bool(b.enabled),
        "K": None if b.K is None else float(b.K),
        "M_ext": None if b.M_ext is None else [float(x) for x in np.asarray(b.M_ext).tolist()],
        "contact_mask": None if b.contact_mask is None else np.asarray(b.contact_mask, dtype=bool).tolist(),
        "cum_import": None if b.cum_import is None else [float(x) for x in np.asarray(b.cum_import).tolist()],
        "cum_export": None if b.cum_export is None else [float(x) for x in np.asarray(b.cum_export).tolist()],
        "last_signed_flux": None
        if b.last_signed_flux is None
        else [float(x) for x in np.asarray(b.last_signed_flux).tolist()],
        "last_residual_max": float(b.last_residual_max),
        "law_version": str(b.law_version),
        "contact_count": 0 if b.contact_mask is None else int(np.asarray(b.contact_mask, dtype=bool).sum()),
        "G_total": None
        if (not b.enabled or b.K is None or b.contact_mask is None)
        else float(b.K) * int(np.asarray(b.contact_mask, dtype=bool).sum()),
    }


def boundary_from_dict(d: dict[str, Any] | None, *, n_materials: int = 3) -> ExternalMaterialBoundary:
    """Legacy missing / None -> OFF."""
    if not d:
        return off_boundary(n_materials)
    enabled = bool(d.get("enabled", False))
    if not enabled:
        b = off_boundary(n_materials)
        # restore counters if present
        if d.get("cum_import") is not None:
            b.cum_import = np.asarray(d["cum_import"], dtype=np.float64)
        if d.get("cum_export") is not None:
            b.cum_export = np.asarray(d["cum_export"], dtype=np.float64)
        return b
    mask = None if d.get("contact_mask") is None else np.asarray(d["contact_mask"], dtype=bool)
    me = None if d.get("M_ext") is None else np.asarray(d["M_ext"], dtype=np.float64)
    b = ExternalMaterialBoundary(
        enabled=True,
        contact_mask=mask,
        K=None if d.get("K") is None else float(d["K"]),
        M_ext=me,
        cum_import=np.asarray(d["cum_import"], dtype=np.float64)
        if d.get("cum_import") is not None
        else np.zeros(n_materials, dtype=np.float64),
        cum_export=np.asarray(d["cum_export"], dtype=np.float64)
        if d.get("cum_export") is not None
        else np.zeros(n_materials, dtype=np.float64),
        last_signed_flux=np.asarray(d["last_signed_flux"], dtype=np.float64)
        if d.get("last_signed_flux") is not None
        else np.zeros(n_materials, dtype=np.float64),
        last_residual_max=float(d.get("last_residual_max", 0.0)),
        law_version=str(d.get("law_version", LAW_VERSION)),
    )
    return b


def mask_sha256(mask: np.ndarray | None) -> str | None:
    if mask is None:
        return None
    import hashlib

    return hashlib.sha256(np.ascontiguousarray(np.asarray(mask, dtype=bool)).tobytes()).hexdigest()
