"""Acanthostega CONTINUOUS SURFACE GEOMETRY G1 — bilinear height + analytic normal.

Preset: ACANTHOSTEGA_PHASE_C_CONTINUOUS_SURFACE_GEOMETRY
Parent: ACANTHOSTEGA_PHASE_C_BODY_NORMAL_LOAD_TRACTION
Mechanism: continuous_surface_geometry
Profile: BILINEAR_HEIGHT_ANALYTIC_NORMAL_V1

G1 CONTRACT
  Authoritative: procedural baseline + sparse deltas (+ seed/generator/material).
  Derived: bilinear h(x,y), weights, analytic ∇h, unit n̂, caches, overlays.
  continuous h IS support height for grounded body/FREE objects when ON.
  analytic n̂ is researcher-visible, reconstructible, PHYSICALLY INACTIVE.
  SES DDA remains sole energy/blocking authority for horizontal transitions.
  HIDDEN_SMOOTHING_OF_PITS_AND_EMBANKMENTS = FORBIDDEN.
  DENSE_AUTHORITATIVE_HEIGHT_RASTER = NO.
  Sample locus: CELL_CENTRE_LATTICE (floor(x-0.5)); at cell centres h == sample.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from mechanistic_mind.planet.topology import wrap_coord
from mechanistic_mind.physical_system.body_normal_load_traction import (
    body_normal_load_traction_is_active,
)
from mechanistic_mind.physical_system.surface_elevation_support import (
    PHYSICAL_HEIGHT_SCALE,
    assert_physical_height_scale_gate,
)

MECHANISM_ID = "continuous_surface_geometry"
PROFILE_VERSION = "BILINEAR_HEIGHT_ANALYTIC_NORMAL_V1"
STATE_SCHEMA = "CONTINUOUS_SURFACE_GEOMETRY_STATE_V1"
RECEIPT_KIND = "CONTINUOUS_SURFACE_GEOMETRY"
EVENT_SAMPLE = "CONTINUOUS_SURFACE_SAMPLE"

BANNER = (
    "CONTINUOUS SURFACE GEOMETRY · BILINEAR HEIGHT V1 · "
    "ANALYTIC NORMAL AVAILABLE · PHYSICALLY INACTIVE · "
    "SES DDA ENERGY/BLOCKING KEPT · NO SLOPE FORCES · NO RADIUS SUPPORT · NO GAIT"
)
OVERLAY_CAPTION = BANNER
ANALYZER_SECTION = "CONTINUOUS SURFACE GEOMETRY"

SAMPLE_LOCUS = "CELL_CENTRE_LATTICE_V1"
INTERPOLANT = "BILINEAR_WRAP_PERIODIC_V1"
NORMAL_LAW = "ANALYTIC_FROM_BILINEAR_GRADIENT_V1"
CONTINUOUS_SLOPES = "GEOMETRY_ONLY_V1"
SES_DISCRETE_DDA = "KEPT_PHASE1"
HIDDEN_SMOOTHING = "FORBIDDEN"
DENSE_HEIGHT_RASTER = "NO"
HEIGHT_PHYSICAL_EFFECTS_ACTIVE = True
NORMAL_PHYSICAL_EFFECTS_ACTIVE = False
SLOPE_GRAVITY = "NO"
TANGENT_PLANE_FRICTION = "NO"
RADIUS_AWARE_SUPPORT = "NO"
GAIT = "NO"
EXCAVATION = "NO"

HISTORY_LIMIT_DEFAULT = 64
EPS_FLAT = 1e-15

RESEARCHER_FLAGS = {
    "researcher_only": True,
    "agent_accessible": False,
    "semantic_label": False,
}


@dataclass
class ContinuousSurfaceGeometryConfig:
    """Fresh default OFF. Missing snapshot field = OFF."""

    enabled: bool = False
    history_limit: int = HISTORY_LIMIT_DEFAULT
    record_samples: bool = True

    def to_dict(self) -> dict[str, Any]:
        on = bool(self.enabled)
        return {
            "enabled": on,
            "history_limit": int(self.history_limit),
            "record_samples": bool(self.record_samples),
            "profile_version": PROFILE_VERSION,
            "sample_locus": SAMPLE_LOCUS,
            "interpolant": INTERPOLANT,
            "normal_law": NORMAL_LAW,
            "CONTINUOUS_SLOPES": CONTINUOUS_SLOPES,
            "SES_DISCRETE_DDA": SES_DISCRETE_DDA,
            "HIDDEN_SMOOTHING": HIDDEN_SMOOTHING,
            "DENSE_HEIGHT_RASTER": DENSE_HEIGHT_RASTER,
            "height_physical_effects_active": bool(on and HEIGHT_PHYSICAL_EFFECTS_ACTIVE),
            "normal_physical_effects_active": False,
            "SLOPE_GRAVITY": SLOPE_GRAVITY,
            "TANGENT_PLANE_FRICTION": TANGENT_PLANE_FRICTION,
            "RADIUS_AWARE_SUPPORT": RADIUS_AWARE_SUPPORT,
            "GAIT": GAIT,
            "EXCAVATION": EXCAVATION,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ContinuousSurfaceGeometryConfig":
        if not isinstance(data, dict) or not data:
            return cls(enabled=False)
        ver = data.get("profile_version")
        if ver is not None and str(ver) != PROFILE_VERSION:
            raise ValueError(f"unknown continuous surface geometry profile: {ver}")
        return cls(
            enabled=bool(data.get("enabled", False)),
            history_limit=int(data.get("history_limit", HISTORY_LIMIT_DEFAULT)),
            record_samples=bool(data.get("record_samples", True)),
        )


def validate_config(cfg: ContinuousSurfaceGeometryConfig) -> None:
    if not (1 <= int(cfg.history_limit) <= 512):
        raise ValueError("history_limit must be in [1, 512]")


def _line_ok(config: Any) -> bool:
    return config is not None and str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"


def continuous_surface_geometry_is_active(config: Any) -> bool:
    if not _line_ok(config):
        return False
    cfg = getattr(config, "continuous_surface_geometry", None)
    if cfg is None or not bool(getattr(cfg, "enabled", False)):
        return False
    # Parent chain: BNLT → SES → FOGF → FGG (BNLT already requires SES+FGG).
    return bool(body_normal_load_traction_is_active(config))


def set_continuous_surface_geometry(config: Any, enabled: bool) -> None:
    if config is None:
        return
    on = bool(enabled) and _line_ok(config)
    cur = getattr(config, "continuous_surface_geometry", None)
    if cur is None:
        if on:
            config.continuous_surface_geometry = ContinuousSurfaceGeometryConfig(enabled=True)
        return
    if isinstance(cur, dict):
        cfg = ContinuousSurfaceGeometryConfig.from_dict(cur)
        cfg.enabled = on
        config.continuous_surface_geometry = cfg
    else:
        cur.enabled = on


def _dims(world: Any) -> tuple[int, int]:
    from mechanistic_mind.physical_system import procedural_surface_columns as psc

    st = psc.state_of(world)
    if st is not None:
        return int(st.width), int(st.height)
    t = getattr(world, "T", None)
    return (int(t.shape[1]), int(t.shape[0])) if t is not None else (32, 32)


def _wrap_pose(x: float, y: float, width: int, height: int) -> tuple[float, float]:
    return float(wrap_coord(float(x), int(width))), float(wrap_coord(float(y), int(height)))


def _cell_centre_height(world: Any, cell_x: int, cell_y: int) -> dict[str, Any]:
    """Authoritative physical height at cell centre sample (SCALE GATE 1.0)."""
    from mechanistic_mind.physical_system import procedural_surface_columns as psc

    scale = assert_physical_height_scale_gate(PHYSICAL_HEIGHT_SCALE)
    col = psc.resolved_column_at(world, float(cell_x) + 0.5, float(cell_y) + 0.5, record=False)
    raw = float(col["surface_elevation"])
    if not math.isfinite(raw):
        raise RuntimeError(
            f"continuous_surface_geometry: non-finite elevation at cell ({cell_x},{cell_y})"
        )
    return {
        "cell_x": int(col["cell_x"]),
        "cell_y": int(col["cell_y"]),
        "height": float(scale) * raw,
        "raw_elevation": raw,
        "has_persistent_delta": bool(col.get("has_persistent_delta")),
        "delta_id": col.get("delta_id"),
        "source": col.get("source"),
        "resolved_checksum": col.get("resolved_checksum"),
    }


def _bilinear_patch(world: Any, x: float, y: float) -> dict[str, Any]:
    """Cell-centre lattice bilinear patch at pose (x,y) with WRAP.

    Samples live at (i+0.5, j+0.5). Parameters:
      i0 = floor(x - 0.5),  u = (x - 0.5) - floor(x - 0.5) ∈ [0,1)
    At a cell centre, u=v=0 on that cell's sample → h equals discrete centre height.
    """
    w, h = _dims(world)
    xp, yp = _wrap_pose(x, y, w, h)
    # Shift into centre-lattice coordinates.
    sx = float(xp) - 0.5
    sy = float(yp) - 0.5
    i0_unwrapped = math.floor(sx)
    j0_unwrapped = math.floor(sy)
    u = sx - float(i0_unwrapped)
    v = sy - float(j0_unwrapped)
    # Clamp numeric noise into [0,1).
    if u < 0.0:
        u = 0.0
    elif u >= 1.0:
        u = 1.0 - 1e-15
    if v < 0.0:
        v = 0.0
    elif v >= 1.0:
        v = 1.0 - 1e-15

    i0 = int(wrap_coord(int(i0_unwrapped), w))
    j0 = int(wrap_coord(int(j0_unwrapped), h))
    i1 = int(wrap_coord(int(i0_unwrapped) + 1, w))
    j1 = int(wrap_coord(int(j0_unwrapped) + 1, h))

    c00 = _cell_centre_height(world, i0, j0)
    c10 = _cell_centre_height(world, i1, j0)
    c01 = _cell_centre_height(world, i0, j1)
    c11 = _cell_centre_height(world, i1, j1)

    h00 = float(c00["height"])
    h10 = float(c10["height"])
    h01 = float(c01["height"])
    h11 = float(c11["height"])

    # Bilinear height (cell size = 1).
    height = (
        (1.0 - u) * (1.0 - v) * h00
        + u * (1.0 - v) * h10
        + (1.0 - u) * v * h01
        + u * v * h11
    )
    # Analytic gradient of the same patch (∂h/∂x, ∂h/∂y).
    hx = (1.0 - v) * (h10 - h00) + v * (h11 - h01)
    hy = (1.0 - u) * (h01 - h00) + u * (h11 - h10)

    n_raw_x = -float(hx)
    n_raw_y = -float(hy)
    n_raw_z = 1.0
    n_mag = math.sqrt(n_raw_x * n_raw_x + n_raw_y * n_raw_y + n_raw_z * n_raw_z)
    if not math.isfinite(n_mag) or n_mag <= EPS_FLAT:
        nx = ny = 0.0
        nz = 1.0
        n_mag = 1.0
    else:
        nx = n_raw_x / n_mag
        ny = n_raw_y / n_mag
        nz = n_raw_z / n_mag

    return {
        "x": float(xp),
        "y": float(yp),
        "u": float(u),
        "v": float(v),
        "i0": int(i0),
        "j0": int(j0),
        "i1": int(i1),
        "j1": int(j1),
        "h00": float(h00),
        "h10": float(h10),
        "h01": float(h01),
        "h11": float(h11),
        "height": float(height),
        "gradient_x": float(hx),
        "gradient_y": float(hy),
        "normal_x": float(nx),
        "normal_y": float(ny),
        "normal_z": float(nz),
        "normal_raw_x": float(n_raw_x),
        "normal_raw_y": float(n_raw_y),
        "normal_raw_z": float(n_raw_z),
        "normal_magnitude": float(n_mag),
        "corner_meta": {
            "00": {"cell": [i0, j0], "delta": c00.get("has_persistent_delta"), "source": c00.get("source")},
            "10": {"cell": [i1, j0], "delta": c10.get("has_persistent_delta"), "source": c10.get("source")},
            "01": {"cell": [i0, j1], "delta": c01.get("has_persistent_delta"), "source": c01.get("source")},
            "11": {"cell": [i1, j1], "delta": c11.get("has_persistent_delta"), "source": c11.get("source")},
        },
        "width": int(w),
        "height_world": int(h),
    }


def sample_surface_geometry(
    world: Any,
    x: float,
    y: float,
    *,
    config: Any | None = None,
    record: bool = False,
    reason: str = "",
) -> dict[str, Any]:
    """ONE authoritative geometry oracle for body/object/Observer/Analyzer.

    Returns height, gradient, unit normal, cell coords, weights, corner heights,
    provenance, profile/version. Non-mutating except optional bounded researcher receipt.
    """
    patch = _bilinear_patch(world, float(x), float(y))
    out = {
        "receipt_kind": RECEIPT_KIND,
        "event_kind": EVENT_SAMPLE,
        "mechanism": MECHANISM_ID,
        "profile_version": PROFILE_VERSION,
        "sample_locus": SAMPLE_LOCUS,
        "interpolant": INTERPOLANT,
        "normal_law": NORMAL_LAW,
        "x": patch["x"],
        "y": patch["y"],
        "height": patch["height"],
        "gradient_x": patch["gradient_x"],
        "gradient_y": patch["gradient_y"],
        "normal_x": patch["normal_x"],
        "normal_y": patch["normal_y"],
        "normal_z": patch["normal_z"],
        "u": patch["u"],
        "v": patch["v"],
        "weights": {
            "w00": (1.0 - patch["u"]) * (1.0 - patch["v"]),
            "w10": patch["u"] * (1.0 - patch["v"]),
            "w01": (1.0 - patch["u"]) * patch["v"],
            "w11": patch["u"] * patch["v"],
        },
        "cells": {
            "00": [patch["i0"], patch["j0"]],
            "10": [patch["i1"], patch["j0"]],
            "01": [patch["i0"], patch["j1"]],
            "11": [patch["i1"], patch["j1"]],
        },
        "corner_heights": {
            "h00": patch["h00"],
            "h10": patch["h10"],
            "h01": patch["h01"],
            "h11": patch["h11"],
        },
        "corner_meta": patch["corner_meta"],
        "height_physical_effects_active": bool(HEIGHT_PHYSICAL_EFFECTS_ACTIVE),
        "normal_physical_effects_active": False,
        "HIDDEN_SMOOTHING": HIDDEN_SMOOTHING,
        "DENSE_HEIGHT_RASTER": DENSE_HEIGHT_RASTER,
        "SES_DISCRETE_DDA": SES_DISCRETE_DDA,
        "CONTINUOUS_SLOPES": CONTINUOUS_SLOPES,
        "reason": str(reason or ""),
        **RESEARCHER_FLAGS,
    }
    # Unit / finite / nz>0 invariants (geometry facts).
    nmag = math.sqrt(out["normal_x"] ** 2 + out["normal_y"] ** 2 + out["normal_z"] ** 2)
    out["normal_is_unit"] = bool(abs(nmag - 1.0) <= 1e-12)
    out["normal_nz_positive"] = bool(out["normal_z"] > 0.0)
    out["flat_patch"] = bool(
        abs(patch["h00"] - patch["h10"]) <= EPS_FLAT
        and abs(patch["h00"] - patch["h01"]) <= EPS_FLAT
        and abs(patch["h00"] - patch["h11"]) <= EPS_FLAT
    )
    if record and config is not None and continuous_surface_geometry_is_active(config):
        _maybe_record(world, config, out)
    return out


def continuous_support_height(
    world: Any, x: float, y: float, *, config: Any | None = None
) -> float:
    """Support height = bilinear h(x,y). Requires columns present."""
    return float(sample_surface_geometry(world, x, y, config=config, record=False)["height"])


def continuous_surface_normal(
    world: Any, x: float, y: float, *, config: Any | None = None
) -> tuple[float, float, float]:
    s = sample_surface_geometry(world, x, y, config=config, record=False)
    return float(s["normal_x"]), float(s["normal_y"]), float(s["normal_z"])


# ---------------------------------------------------------------------------
# State / receipts
# ---------------------------------------------------------------------------


@dataclass
class ContinuousSurfaceGeometryState:
    config: ContinuousSurfaceGeometryConfig
    last_sample: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    counters: dict[str, int] = field(default_factory=dict)
    generation: int = 0  # bump on authoritative surface mutation awareness

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": STATE_SCHEMA,
            "config": self.config.to_dict(),
            "last_sample": dict(self.last_sample) if self.last_sample else {},
            "history": list(self.history[-int(self.config.history_limit) :]),
            "counters": {k: int(v) for k, v in self.counters.items()},
            "generation": int(self.generation),
            # Explicitly NOT serializing any dense height raster.
            "dense_height_raster": None,
        }


def state_of(world: Any) -> ContinuousSurfaceGeometryState | None:
    raw = getattr(world, "continuous_surface_geometry_state", None)
    return raw if isinstance(raw, ContinuousSurfaceGeometryState) else None


def ensure_continuous_surface_geometry_for_runtime(
    world: Any, config: Any
) -> ContinuousSurfaceGeometryState | None:
    if not continuous_surface_geometry_is_active(config):
        if hasattr(world, "continuous_surface_geometry_state"):
            world.continuous_surface_geometry_state = None
        return None
    cur = state_of(world)
    if cur is not None:
        return cur
    raw = getattr(config, "continuous_surface_geometry", None)
    cfg = (
        raw
        if isinstance(raw, ContinuousSurfaceGeometryConfig)
        else ContinuousSurfaceGeometryConfig.from_dict(raw if isinstance(raw, dict) else None)
    )
    validate_config(cfg)
    st = ContinuousSurfaceGeometryState(
        config=cfg,
        counters={
            "samples": 0,
            "support_queries": 0,
            "recorded": 0,
        },
    )
    world.continuous_surface_geometry_state = st
    return st


def _maybe_record(world: Any, config: Any, sample: dict[str, Any]) -> None:
    st = ensure_continuous_surface_geometry_for_runtime(world, config)
    if st is None or not bool(st.config.record_samples):
        return
    # Bounded dedup: skip if identical pose+height+normal within last entry.
    last = st.last_sample or {}
    if (
        last
        and abs(float(last.get("x", 1e9)) - float(sample["x"])) < 1e-12
        and abs(float(last.get("y", 1e9)) - float(sample["y"])) < 1e-12
        and abs(float(last.get("height", 1e9)) - float(sample["height"])) < 1e-12
        and abs(float(last.get("normal_x", 1e9)) - float(sample["normal_x"])) < 1e-12
        and abs(float(last.get("normal_y", 1e9)) - float(sample["normal_y"])) < 1e-12
        and abs(float(last.get("normal_z", 1e9)) - float(sample["normal_z"])) < 1e-12
    ):
        return
    rec = {
        **sample,
        "tick": int(getattr(world, "tick", 0) or 0),
        "generation": int(st.generation),
    }
    st.last_sample = dict(rec)
    st.history.append(rec)
    lim = int(st.config.history_limit)
    if len(st.history) > lim:
        del st.history[: len(st.history) - lim]
    st.counters["recorded"] = int(st.counters.get("recorded", 0)) + 1
    st.counters["samples"] = int(st.counters.get("samples", 0)) + 1
    try:
        world.last_continuous_surface_geometry_sample = dict(rec)
    except Exception:
        pass


def note_authoritative_surface_mutation(world: Any, config: Any | None = None) -> None:
    """Bump generation so caches/receipts know authority changed. No dense rebuild."""
    st = state_of(world)
    if st is None and config is not None:
        st = ensure_continuous_surface_geometry_for_runtime(world, config)
    if st is not None:
        st.generation = int(st.generation) + 1


    try:
        from mechanistic_mind.physical_system.radius_aware_support_points import (
            note_surface_generation,
            radius_aware_support_points_is_active,
            state_of as _rasp_state,
        )
        if config is not None and radius_aware_support_points_is_active(config) and _rasp_state(world) is not None:
            note_surface_generation(world)
    except Exception:
        pass

def serialize_state(st: ContinuousSurfaceGeometryState | None) -> dict[str, Any] | None:
    if st is None:
        return None
    return st.to_dict()


def restore_state(world: Any, config: Any, data: dict[str, Any] | None) -> ContinuousSurfaceGeometryState | None:
    if not continuous_surface_geometry_is_active(config):
        world.continuous_surface_geometry_state = None
        return None
    if not isinstance(data, dict) or not data:
        return ensure_continuous_surface_geometry_for_runtime(world, config)
    raw_cfg = data.get("config")
    cur = getattr(config, "continuous_surface_geometry", None)
    if raw_cfg is None:
        raw_cfg = cur.to_dict() if cur is not None and hasattr(cur, "to_dict") else None
    cfg = ContinuousSurfaceGeometryConfig.from_dict(raw_cfg)
    validate_config(cfg)
    st = ContinuousSurfaceGeometryState(
        config=cfg,
        last_sample=dict(data["last_sample"]) if isinstance(data.get("last_sample"), dict) else {},
        history=list(data.get("history") or []),
        counters={
            **{"samples": 0, "support_queries": 0, "recorded": 0},
            **{k: int(v) for k, v in dict(data.get("counters") or {}).items()},
        },
        generation=int(data.get("generation") or 0),
    )
    world.continuous_surface_geometry_state = st
    return st


def catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "label": "Continuous Surface Geometry · Bilinear Height + Analytic Normal V1",
        "config_path": "continuous_surface_geometry.enabled",
        "enabled": bool(enabled),
        "promotion_class": "EXPERIMENTAL",
        "provenance": "acanthostega_continuous_surface_geometry",
        "default_integrated": True,
        "banner": BANNER,
        "analyzer_section": ANALYZER_SECTION,
        "HIDDEN_SMOOTHING": HIDDEN_SMOOTHING,
        "DENSE_HEIGHT_RASTER": DENSE_HEIGHT_RASTER,
        "height_physical_effects_active": bool(enabled and HEIGHT_PHYSICAL_EFFECTS_ACTIVE),
        "normal_physical_effects_active": False,
        "SES_DISCRETE_DDA": SES_DISCRETE_DDA,
        "scope": {
            "support_height": "bilinear_continuous",
            "normal": "analytic_inactive",
            "slope_forces": False,
            "ses_dda_energy": True,
            "gait": False,
            "excavation": False,
        },
        "historical_compatibility": "missing key means continuous geometry OFF / centre-cell SES as parent",
    }


def researcher_summary(world: Any) -> dict[str, Any] | None:
    st = state_of(world)
    if st is None:
        return None
    return {
        "mechanism": MECHANISM_ID,
        "profile_version": PROFILE_VERSION,
        "banner": BANNER,
        "analyzer_section": ANALYZER_SECTION,
        "counters": dict(st.counters),
        "last_sample": st.last_sample or None,
        "generation": int(st.generation),
        "height_physical_effects_active": True,
        "normal_physical_effects_active": False,
        "HIDDEN_SMOOTHING": HIDDEN_SMOOTHING,
        "DENSE_HEIGHT_RASTER": DENSE_HEIGHT_RASTER,
        "SES_DISCRETE_DDA": SES_DISCRETE_DDA,
        "agent_accessible": False,
        "researcher_only": True,
    }


def overlay_payload(world: Any) -> dict[str, Any] | None:
    """Read-only researcher overlay. Must not change physics when disabled/absent."""
    summary = researcher_summary(world)
    if summary is None:
        return None
    last = summary.get("last_sample") or {}
    return {
        "caption": BANNER,
        "active": summary,
        "height": last.get("height"),
        "normal": {
            "x": last.get("normal_x"),
            "y": last.get("normal_y"),
            "z": last.get("normal_z"),
        },
        "patch_cells": last.get("cells"),
        "corner_heights": last.get("corner_heights"),
        "normal_implies_slope_forces": False,
        "read_only": True,
    }


def status_text() -> str:
    return "\n".join([
        "CONTINUOUS SURFACE GEOMETRY · BILINEAR HEIGHT V1",
        "ANALYTIC NORMAL AVAILABLE · PHYSICALLY INACTIVE",
        "SES DDA ENERGY/BLOCKING KEPT",
        "NO SLOPE FORCES · NO RADIUS SUPPORT · NO GAIT",
    ])
