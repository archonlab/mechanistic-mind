"""Acanthostega conservative surface column transfer.

One researcher-only world-material operation, TRANSFER_SURFACE_COLUMN_SLICE:
a contiguous top slice (never crossing a layer boundary) leaves one procedural
surface column and becomes the new top layer of another column. Both columns
are rewritten as sparse persistent deltas in ONE atomic pair commit that goes
through the existing WORLD_MATERIAL_TRANSACTION contract (plan without
mutation -> commit_material_transaction -> duplicate/stale checks -> single
publish -> one ledger record -> one causal event).

Not DIG/MINE/EXCAVATE, not a motor command, not an agent action, not a
resource spawn, not a pile mechanic, not gravity/support/collision, not 3D.

Geometry (FIXED_LOWER_DATUM_V1):
    fixed_lower_datum       = baseline_surface_elevation - baseline_modelled_depth
    resolved_modelled_depth = resolved_surface_elevation - fixed_lower_datum
                            = baseline_modelled_depth + (resolved_elevation - baseline_elevation)
Source:      elevation -= t, resolved depth -= t (no material created below).
Destination: elevation += t, resolved depth += t (slice is the new [0, t) layer).

Layer quantities (SurfaceMaterialLayer, unchanged):
    quantity_per_area = thickness            (volume per unit horizontal area)
    mass_per_area     = thickness * density
    composition       = anonymous component amounts in quantity units, sum == thickness

Flags: researcher_only=true, agent_action=false, agent_accessible=false,
physical_effects_active=false, geometry_role=METADATA_ONLY.
"""
from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, field
from typing import Any

from mechanistic_mind.physical_system import procedural_surface_columns as psc

MECHANISM_ID = "conservative_surface_column_transfer"
OPERATION_KIND = "TRANSFER_SURFACE_COLUMN_SLICE"
RECEIPT_KIND = "SURFACE_COLUMN_TRANSFER"
RECEIPT_SCHEMA = "SURFACE_COLUMN_TRANSFER_V1"
STATE_SCHEMA = "SURFACE_COLUMN_TRANSFER_STATE_V1"
EVENT_COMMITTED = "SURFACE_COLUMN_TRANSFER_COMMITTED"
EVENT_REJECTED = "SURFACE_COLUMN_TRANSFER_REJECTED"
EVENT_RESTORE_VERIFIED = "SURFACE_COLUMN_TRANSFER_RESTORE_VERIFIED"
TRANSFER_EVENTS = frozenset({EVENT_COMMITTED, EVENT_REJECTED, EVENT_RESTORE_VERIFIED})
SELECTION_PROVENANCE = "INTERVENTION_SETUP"
ROLE_SOURCE = "SOURCE"
ROLE_DESTINATION = "DESTINATION"
DATUM_POLICY = "FIXED_LOWER_DATUM_V1"
MERGE_POLICY = "CANONICAL_ADJACENT_MERGE_V1"
TRANSFER_POLICY = "CONTIGUOUS_TOP_SLICE_SINGLE_LAYER_V1"
ORDER_POLICY = "PROPOSER_ID_THEN_CANONICAL_ADDRESS_V1"
MERGED = "MERGED_WITH_DESTINATION_TOP_LAYER"
SEPARATE = "SEPARATE_TOP_LAYER"

HISTORY_LIMIT = 16
TRANSFER_REF_LIMIT = 4
COMMITTED_TRANSFER_ID_LIMIT = 64
CONSERVATION_TOLERANCE = psc.TOLERANCE  # 1e-12 absolute, per unit area
RESTORE_TOLERANCE = 1e-9

EFFECT_FLAGS = {
    **psc.EFFECT_FLAGS,
    "researcher_only": True,
    "agent_action": False,
    "agent_accessible": False,
    "physical_effects_active": False,
    "resource_spawned": False,
    "recipe_match": False,
    "semantic_effect": False,
    "reward_created": False,
    "motor_vocabulary": False,
    "endogenous_action": False,
    "excavation_action": False,
}

# Rejection codes (receipt.rejection_reason)
R_INACTIVE = "MECHANISM_INACTIVE"
R_PROVENANCE = "INVALID_SELECTION_PROVENANCE"
R_AGENT = "AGENT_ACTION_FORBIDDEN"
R_SEED = "SEED_AUTHORITY_INVALID"
R_GENERATOR = "UNKNOWN_GENERATOR_VERSION"
R_COORD = "NON_FINITE_COORDINATE"
R_SAME = "SAME_WRAPPED_CELL"
R_REV_TYPE = "INVALID_EXPECTED_REVISION"
R_NONFINITE = "NON_FINITE_THICKNESS"
R_ZERO = "ZERO_THICKNESS"
R_NEGATIVE = "NEGATIVE_THICKNESS"
R_BASE_SRC = "SOURCE_BASELINE_CHECKSUM_MISMATCH"
R_BASE_DST = "DESTINATION_BASELINE_CHECKSUM_MISMATCH"
R_STALE_SRC = "STALE_SOURCE_REVISION"
R_STALE_DST = "STALE_DESTINATION_REVISION"
R_NO_TOP = "NO_SOURCE_TOP_LAYER"
R_CROSS = "CROSSES_LAYER_BOUNDARY"
R_DEPTH = "INSUFFICIENT_SOURCE_DEPTH"
R_DST_DEPTH = "DESTINATION_DEPTH_LIMIT"
R_LAYERS = "LAYER_LIMIT_EXCEEDED"
R_INTERVAL = "INTERVAL_VALIDATION_FAILED"
R_CONSERVATION = "CONSERVATION_FAILED"
R_SERIAL = "DELTA_NOT_SERIALIZABLE"
R_CAPACITY = "DELTA_CAPACITY_EXCEEDED"
R_CANDIDATE = "CANDIDATE_CONSTRUCTION_FAILED"
R_DUPLICATE = "ALREADY_COMMITTED"
R_STATE_CHANGED = "COLUMN_STATE_CHANGED_SINCE_PLAN"
R_COMMIT_EXCEPTION = "COMMIT_EXCEPTION"


# ---------------------------------------------------------------------------
# Config / gate
# ---------------------------------------------------------------------------


@dataclass
class ConservativeSurfaceColumnTransferConfig:
    """Fresh default OFF. Missing snapshot/config field keeps the mechanism OFF."""

    enabled: bool = False
    max_layers_per_column: int = 8
    minimum_resolved_depth: float = 0.5
    maximum_resolved_depth: float = 64.0
    merge_tolerance: float = 1e-12

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "max_layers_per_column": int(self.max_layers_per_column),
            "minimum_resolved_depth": float(self.minimum_resolved_depth),
            "maximum_resolved_depth": float(self.maximum_resolved_depth),
            "merge_tolerance": float(self.merge_tolerance),
            "datum_policy": DATUM_POLICY,
            "merge_policy": MERGE_POLICY,
            "transfer_policy": TRANSFER_POLICY,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ConservativeSurfaceColumnTransferConfig":
        if not isinstance(data, dict) or not data:
            return cls(enabled=False)
        return cls(
            enabled=bool(data.get("enabled", False)),
            max_layers_per_column=int(data.get("max_layers_per_column", 8)),
            minimum_resolved_depth=float(data.get("minimum_resolved_depth", 0.5)),
            maximum_resolved_depth=float(data.get("maximum_resolved_depth", 64.0)),
            merge_tolerance=float(data.get("merge_tolerance", 1e-12)),
        )


def validate_transfer_config(cfg: ConservativeSurfaceColumnTransferConfig) -> None:
    if not (2 <= int(cfg.max_layers_per_column) <= 64):
        raise psc.SurfaceColumnValidationError("max_layers_per_column must be in [2, 64]")
    lo, hi = float(cfg.minimum_resolved_depth), float(cfg.maximum_resolved_depth)
    if not (math.isfinite(lo) and math.isfinite(hi) and 0.0 < lo < hi <= 1024.0):
        raise psc.SurfaceColumnValidationError("resolved depth bounds invalid")
    tol = float(cfg.merge_tolerance)
    if not (math.isfinite(tol) and 0.0 <= tol <= 1e-6):
        raise psc.SurfaceColumnValidationError("merge_tolerance must be in [0, 1e-6]")


def _line_ok(config: Any) -> bool:
    return config is not None and str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"


def conservative_surface_column_transfer_is_active(config: Any) -> bool:
    if not _line_ok(config) or not psc.procedural_surface_columns_is_active(config):
        return False
    cfg = getattr(config, "conservative_surface_column_transfer", None)
    return bool(cfg is not None and getattr(cfg, "enabled", False))


def set_conservative_surface_column_transfer(config: Any, enabled: bool) -> None:
    if config is None:
        return
    on = bool(enabled) and _line_ok(config)
    cur = getattr(config, "conservative_surface_column_transfer", None)
    if cur is None:
        if on:
            config.conservative_surface_column_transfer = ConservativeSurfaceColumnTransferConfig(enabled=True)
        # OFF with no config: keep the field absent (previous presets carry no transfer field).
        return
    cur.enabled = on


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class ColumnTransferState:
    config: ConservativeSurfaceColumnTransferConfig
    transfer_sequence: int = 0
    history: list[dict[str, Any]] = field(default_factory=list)
    committed_transfer_ids: list[str] = field(default_factory=list)
    counters: dict[str, int] = field(default_factory=lambda: {
        "planned": 0, "committed": 0, "rejected": 0, "merged": 0, "stale_conflicts": 0,
    })
    residual_max: dict[str, float] = field(default_factory=lambda: {
        "mass": 0.0, "quantity": 0.0, "components": 0.0, "elevation": 0.0,
    })
    cost_max: dict[str, float] = field(default_factory=lambda: {
        "plan_us": 0.0, "commit_us": 0.0, "layer_ops": 0,
    })
    restore_verification: dict[str, Any] = field(default_factory=dict)


def transfer_state_of(world: Any) -> ColumnTransferState | None:
    state = psc.state_of(world)
    raw = getattr(state, "transfer", None) if state is not None else None
    return raw if isinstance(raw, ColumnTransferState) else None


def ensure_column_transfer_for_state(state: psc.SurfaceColumnState, config: Any) -> ColumnTransferState | None:
    """Mechanism ON: keep restored transfer state or start a fresh one. OFF: none.

    Committed transfer deltas stay authoritative world geometry either way.
    """
    if not conservative_surface_column_transfer_is_active(config):
        state.transfer = None
        return None
    if isinstance(getattr(state, "transfer", None), ColumnTransferState):
        return state.transfer
    cfg = ConservativeSurfaceColumnTransferConfig.from_dict(
        getattr(config, "conservative_surface_column_transfer").to_dict()
    )
    validate_transfer_config(cfg)
    state.transfer = ColumnTransferState(config=cfg)
    return state.transfer


# ---------------------------------------------------------------------------
# Pure geometry / slice helpers (no mutation)
# ---------------------------------------------------------------------------


def fixed_lower_datum(baseline: psc.SurfaceColumnBaseline) -> float:
    return float(baseline.surface_elevation) - float(baseline.modelled_depth)


def resolved_depth(baseline: psc.SurfaceColumnBaseline, elevation: float) -> float:
    return psc.resolved_modelled_depth_for(baseline, elevation)


def _proportions(layer: psc.SurfaceMaterialLayer) -> dict[str, float]:
    t = float(layer.thickness)
    return {cid: float(a) / t for cid, a in layer.composition}


def layers_mergeable(upper: psc.SurfaceMaterialLayer, lower: psc.SurfaceMaterialLayer, tol: float) -> dict[str, Any]:
    """Canonical adjacent merge test over every physical field actually in layer state.

    Layer state = (thickness, density, composition, material_property_derivation_version).
    Thickness is extensive and never compared. No component-id special cases.
    """
    reasons = []
    if upper.material_property_derivation_version != lower.material_property_derivation_version:
        reasons.append("derivation_version")
    scale = max(1.0, abs(float(upper.density)), abs(float(lower.density)))
    if abs(float(upper.density) - float(lower.density)) > tol * scale:
        reasons.append("density")
    pu, pl = _proportions(upper), _proportions(lower)
    if set(pu) != set(pl):
        reasons.append("component_set")
    else:
        worst = max((abs(pu[k] - pl[k]) for k in pu), default=0.0)
        if worst > tol:
            reasons.append("composition_proportions")
    return {"mergeable": not reasons, "mismatch": reasons, "tolerance": float(tol)}


def _shift(layer: psc.SurfaceMaterialLayer, offset: float) -> psc.SurfaceMaterialLayer:
    return psc.SurfaceMaterialLayer(
        top_depth=float(layer.top_depth) + offset,
        bottom_depth=float(layer.bottom_depth) + offset,
        thickness=float(layer.thickness),
        density=float(layer.density),
        composition=tuple(layer.composition),
        material_property_derivation_version=layer.material_property_derivation_version,
    )


def split_top_slice(
    layers: tuple[psc.SurfaceMaterialLayer, ...], thickness: float
) -> tuple[psc.SurfaceMaterialLayer, tuple[psc.SurfaceMaterialLayer, ...], bool]:
    """Return (slice as [0, t) layer, remaining source layers, whole_layer_removed).

    The slice keeps the top layer's density, derivation version and exact
    composition proportions: s_i = a_i * (t / T0). No registry recomposition.
    Remaining layers shift up by t (depth is measured down from the new surface).
    """
    top = layers[0]
    t = float(thickness)
    t0 = float(top.thickness)
    if t == t0:
        slice_comp = tuple(top.composition)
        remaining = tuple(_shift(layer, -t0) for layer in layers[1:])
        whole = True
    else:
        frac = t / t0
        slice_comp = tuple((cid, float(a) * frac) for cid, a in top.composition)
        rest_comp = tuple((cid, float(a) - s) for (cid, a), (_, s) in zip(top.composition, slice_comp))
        new_bottom = float(top.bottom_depth) - t
        left = psc.SurfaceMaterialLayer(
            top_depth=0.0,
            bottom_depth=new_bottom,
            thickness=new_bottom,
            density=float(top.density),
            composition=psc._canonical_composition(list(rest_comp)),
            material_property_derivation_version=top.material_property_derivation_version,
        )
        remaining = (left,) + tuple(_shift(layer, -t) for layer in layers[1:])
        whole = False
    sl = psc.SurfaceMaterialLayer(
        top_depth=0.0,
        bottom_depth=t,
        thickness=t,
        density=float(top.density),
        composition=psc._canonical_composition(list(slice_comp)),
        material_property_derivation_version=top.material_property_derivation_version,
    )
    return sl, remaining, whole


def place_slice_on_top(
    layers: tuple[psc.SurfaceMaterialLayer, ...], sl: psc.SurfaceMaterialLayer, tol: float
) -> tuple[tuple[psc.SurfaceMaterialLayer, ...], dict[str, Any]]:
    """Slice becomes the new top layer [0, t); old layers shift deeper by t.

    Canonical adjacent merge with the old top layer only if every physical
    field in layer state matches within strict tolerance. Merged density is
    mass-weighted so mass per area is conserved up to rounding.
    """
    t = float(sl.thickness)
    check = layers_mergeable(sl, layers[0], tol)
    if check["mergeable"]:
        top = layers[0]
        thickness = float(top.thickness) + t
        mass = float(top.thickness) * float(top.density) + t * float(sl.density)
        merged = psc.SurfaceMaterialLayer(
            top_depth=0.0,
            bottom_depth=float(top.bottom_depth) + t,
            thickness=thickness,
            density=mass / thickness,
            composition=psc._canonical_composition(list(top.composition) + list(sl.composition)),
            material_property_derivation_version=top.material_property_derivation_version,
        )
        out = (merged,) + tuple(_shift(layer, t) for layer in layers[1:])
        return out, {"status": MERGED, **check}
    out = (sl,) + tuple(_shift(layer, t) for layer in layers)
    return out, {"status": SEPARATE, **check}


def _pair_summary(a: tuple, b: tuple) -> dict[str, Any]:
    sa, sb = psc.mass_summary(a), psc.mass_summary(b)
    comps: dict[str, list[float]] = {}
    for s in (sa, sb):
        for cid, v in s["component_quantity_per_area"].items():
            comps.setdefault(cid, []).append(float(v))
    return {
        "total_mass_per_area": math.fsum((sa["total_mass_per_area"], sb["total_mass_per_area"])),
        "total_quantity_per_area": math.fsum((sa["total_quantity_per_area"], sb["total_quantity_per_area"])),
        "component_quantity_per_area": {cid: math.fsum(v) for cid, v in sorted(comps.items())},
        "source": sa,
        "destination": sb,
    }


def _domain(before: float, after: float, tol: float = CONSERVATION_TOLERANCE) -> dict[str, Any]:
    residual = float(after) - float(before)
    return {"before": float(before), "after": float(after), "residual": residual, "tolerance": tol,
            "verified": bool(math.isfinite(residual) and abs(residual) <= tol)}


def pair_conservation(before: dict[str, Any], after: dict[str, Any], transferred: dict[str, Any]) -> dict[str, Any]:
    cb, ca = before["component_quantity_per_area"], after["component_quantity_per_area"]
    keys = sorted(set(cb) | set(ca))
    residuals = {k: float(ca.get(k, 0.0)) - float(cb.get(k, 0.0)) for k in keys}
    worst = max((abs(v) for v in residuals.values()), default=0.0)
    src_b, src_a = before["source"], after["source"]
    dst_b, dst_a = before["destination"], after["destination"]
    loss_gain = {
        "mass": (src_b["total_mass_per_area"] - src_a["total_mass_per_area"])
        - (dst_a["total_mass_per_area"] - dst_b["total_mass_per_area"]),
        "quantity": (src_b["total_quantity_per_area"] - src_a["total_quantity_per_area"])
        - (dst_a["total_quantity_per_area"] - dst_b["total_quantity_per_area"]),
    }
    slice_vs_loss = {
        "mass": (src_b["total_mass_per_area"] - src_a["total_mass_per_area"]) - transferred["mass_per_area"],
        "quantity": (src_b["total_quantity_per_area"] - src_a["total_quantity_per_area"])
        - transferred["quantity_per_area"],
    }
    out = {
        "mass": _domain(before["total_mass_per_area"], after["total_mass_per_area"]),
        "quantity": _domain(before["total_quantity_per_area"], after["total_quantity_per_area"]),
        "components": {
            "before": {k: float(cb.get(k, 0.0)) for k in keys},
            "after": {k: float(ca.get(k, 0.0)) for k in keys},
            "residuals": residuals, "residual_max_abs": float(worst), "tolerance": CONSERVATION_TOLERANCE,
            "verified": bool(math.isfinite(worst) and worst <= CONSERVATION_TOLERANCE),
        },
        "source_loss_minus_destination_gain": loss_gain,
        "source_loss_minus_slice": slice_vs_loss,
        "external_source_sink": False,
        "closed_pair": True,
        "scope": "SOURCE_PLUS_DESTINATION_PER_UNIT_AREA",
    }
    extra_ok = all(abs(v) <= 1e-9 for v in list(loss_gain.values()) + list(slice_vs_loss.values()))
    out["verified"] = bool(out["mass"]["verified"] and out["quantity"]["verified"]
                           and out["components"]["verified"] and extra_ok)
    return out


# ---------------------------------------------------------------------------
# Planning helpers
# ---------------------------------------------------------------------------


def _column_key(cell: tuple[int, int]) -> str:
    return f"column:x{int(cell[0])}-y{int(cell[1])}"


def column_revision_for_key(world: Any, key: str) -> int | None:
    """WMT stale-check hook for keys 'column:x{X}-y{Y}'."""
    try:
        body = str(key).split(":", 1)[1]
        xs, ys = body.split("-")
        cell = (int(xs[1:]), int(ys[1:]))
    except (IndexError, ValueError):
        return None
    if psc.state_of(world) is None:
        return None
    current = psc.deltas_of(world).get(cell)
    return 0 if current is None else int(current.revision)


def _resolved(world: Any, cell: tuple[int, int]) -> dict[str, Any]:
    base = psc.baseline_column_at(world, cell[0], cell[1])
    delta = psc.deltas_of(world).get(cell)
    layers = base.layers if delta is None else delta.resulting_layers
    elevation = base.surface_elevation if delta is None else delta.resulting_surface_elevation
    return {
        "cell": cell,
        "baseline": base,
        "delta": delta,
        "layers": tuple(layers),
        "elevation": float(elevation),
        "revision": 0 if delta is None else int(delta.revision),
        "checksum": base.baseline_checksum if delta is None else delta.resolved_checksum(),
        "datum": fixed_lower_datum(base),
        "resolved_depth": resolved_depth(base, elevation),
    }


def _new_provenance(prev: dict[str, Any] | None, *, role: str, opposite: tuple[int, int], transaction_id: str,
                    transfer_id: str, previous_revision: int, baseline_checksum: str, tick: int,
                    researcher_id: str, signed: dict[str, Any]) -> dict[str, Any]:
    """Bounded refs only; never the opposite column itself."""
    prev = dict(prev or {})
    refs = [dict(r) for r in (prev.get("transfer_refs") or [])]
    refs.append({
        "transaction_id": transaction_id,
        "transfer_id": transfer_id,
        "transfer_role": role,
        "opposite_cell": [int(opposite[0]), int(opposite[1])],
        "previous_delta_revision": int(previous_revision),
    })
    net = dict(prev.get("net_exchange") or {})
    comps = dict(net.get("component_quantity_per_area") or {})
    for cid, v in signed["components"].items():
        comps[cid] = math.fsum((float(comps.get(cid, 0.0)), float(v)))
    net_out = {
        "quantity_per_area": math.fsum((float(net.get("quantity_per_area", 0.0)), signed["quantity"])),
        "mass_per_area": math.fsum((float(net.get("mass_per_area", 0.0)), signed["mass"])),
        "component_quantity_per_area": {k: comps[k] for k in sorted(comps)},
    }
    return {
        "kind": psc.PROVENANCE_KIND,
        "researcher_only": True,
        "not_agent_action": True,
        "researcher_id": str(researcher_id),
        "operation_kind": OPERATION_KIND,
        "last_transaction_id": transaction_id,
        "last_transfer_id": transfer_id,
        "transfer_role": role,
        "opposite_cell": [int(opposite[0]), int(opposite[1])],
        "previous_delta_revision": int(previous_revision),
        "baseline_checksum": str(baseline_checksum),
        "creation_tick": int(prev.get("creation_tick", tick)),
        "transfer_refs": refs[-TRANSFER_REF_LIMIT:],
        "net_exchange": net_out,
    }


def _candidate_delta(col: dict[str, Any], *, layers: tuple, elevation: float, tick: int, transaction_id: str,
                     provenance: dict[str, Any]) -> psc.SurfaceColumnDelta:
    base, cur = col["baseline"], col["delta"]
    tx_ids = (list(cur.source_transaction_ids) if cur is not None else []) + [transaction_id]
    return psc.SurfaceColumnDelta(
        delta_id=psc.delta_id_for(*col["cell"]),
        cell_x=int(col["cell"][0]),
        cell_y=int(col["cell"][1]),
        baseline_generator_version=base.generator_version,
        baseline_checksum=base.baseline_checksum,
        resulting_surface_elevation=float(elevation),
        resulting_layers=tuple(layers),
        created_tick=int(cur.created_tick if cur is not None else tick),
        last_updated_tick=int(tick),
        revision=int(col["revision"]) + 1,
        source_transaction_ids=tx_ids[-psc.PROVENANCE_LIMIT:],
        provenance=provenance,
    )


def _serializable(delta: psc.SurfaceColumnDelta) -> bool:
    try:
        row = json.loads(json.dumps(delta.as_dict()))
        back = psc.SurfaceColumnDelta.from_dict(row)
        return back.resolved_checksum() == delta.resolved_checksum() == row["resolved_checksum"]
    except (TypeError, ValueError, KeyError):
        return False


def _hook_candidate_construction(stage: str) -> None:
    """Test seam (no-op). Raising here simulates a failure while building candidates."""


def _hook_before_destination_write() -> None:
    """Test seam (no-op). Raising here simulates a failure between the two delta writes."""


def _hook_before_publish() -> None:
    """Test seam (no-op). Raising here simulates a failure right before the atomic publish."""


def _col_row(col: dict[str, Any]) -> dict[str, Any]:
    return {
        "elevation": col["elevation"],
        "baseline_elevation": float(col["baseline"].surface_elevation),
        "resolved_depth": col["resolved_depth"],
        "fixed_lower_datum": col["datum"],
        "revision": col["revision"],
        "checksum": col["checksum"],
        "baseline_checksum": col["baseline"].baseline_checksum,
        "layer_count": len(col["layers"]),
        "delta_id": psc.delta_id_for(*col["cell"]),
    }


def _as_revision(value: Any) -> int:
    if isinstance(value, bool) or value is None:
        raise TypeError("not a revision")
    if isinstance(value, float):
        if not value.is_integer():
            raise ValueError("non-integer revision")
        return int(value)
    return int(value)


def _jsonable(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return repr(value)
    if isinstance(value, (int, float, str)) or value is None:
        return value
    return repr(value)


# ---------------------------------------------------------------------------
# Planning (preflight builds both candidate columns without mutation)
# ---------------------------------------------------------------------------


def plan_surface_column_transfer(
    world: Any,
    config: Any,
    *,
    source_cell_x: Any,
    source_cell_y: Any,
    destination_cell_x: Any,
    destination_cell_y: Any,
    requested_thickness: Any,
    expected_source_revision: Any,
    expected_destination_revision: Any,
    tick: int,
    researcher_id: str = "researcher",
    selection_provenance: str = SELECTION_PROVENANCE,
    agent_action: bool = False,
    world_seed: int | None = None,
    reason: str = "researcher_intervention",
) -> dict[str, Any]:
    """Validate one transfer and build both candidate deltas without mutating world geometry.

    Only counters/ids advance (WMT transaction sequence, transfer sequence) so ids are never reused.
    """
    from mechanistic_mind.physical_system import world_material_transaction as wmt

    t_start = time.perf_counter()
    transaction_id = wmt.allocate_transaction_id(world, int(tick))
    sequence = int(getattr(world, "material_transaction_sequence", 1) or 1) - 1
    state = psc.state_of(world)
    tstate = transfer_state_of(world)
    transfer_seq = 0
    if tstate is not None:
        transfer_seq = tstate.transfer_sequence
        tstate.transfer_sequence = transfer_seq + 1
        tstate.counters["planned"] = int(tstate.counters.get("planned", 0)) + 1
    transfer_id = f"surface-column-transfer-{int(tick):09d}-{transfer_seq:04d}"
    plan: dict[str, Any] = {
        "transaction_id": transaction_id,
        "transfer_id": transfer_id,
        "sequence": sequence,
        "schema_version": wmt.SCHEMA_VERSION,
        "tick": int(tick),
        "model_line": str(getattr(config, "model_line", "") or ""),
        "public_preset": str(getattr(config, "public_preset", "") or ""),
        "command": None,
        "operation_kind": OPERATION_KIND,
        "actor_body_id": None,
        "actor_agent_id": None,
        "researcher_id": str(researcher_id),
        "selection_provenance": str(selection_provenance),
        "agent_action": bool(agent_action),
        "status": "PLANNED",
        "input_refs": [],
        "output_refs": [],
        "source_event_ids": [],
        "expected_revisions": {},
        "preconditions": {},
        "config": config,
        "raw_inputs": {
            "source_cell_x": _jsonable(source_cell_x), "source_cell_y": _jsonable(source_cell_y),
            "destination_cell_x": _jsonable(destination_cell_x),
            "destination_cell_y": _jsonable(destination_cell_y),
            "requested_thickness": _jsonable(requested_thickness),
            "expected_source_revision": _jsonable(expected_source_revision),
            "expected_destination_revision": _jsonable(expected_destination_revision),
        },
        "reason": str(reason),
    }
    checks: dict[str, bool] = {}

    def reject(code: str, detail: str | None = None) -> dict[str, Any]:
        plan["status"] = "REJECTED"
        plan["rejection_reason"] = code
        plan["rejection_detail"] = detail
        plan["preconditions"] = dict(checks)
        plan["plan_us"] = (time.perf_counter() - t_start) * 1e6
        return plan

    checks["mechanism_active"] = bool(
        conservative_surface_column_transfer_is_active(config) and state is not None and tstate is not None
    )
    if not checks["mechanism_active"]:
        return reject(R_INACTIVE)
    checks["selection_provenance_intervention_setup"] = str(selection_provenance) == SELECTION_PROVENANCE
    if not checks["selection_provenance_intervention_setup"]:
        return reject(R_PROVENANCE)
    checks["not_agent_action"] = not bool(agent_action)
    if not checks["not_agent_action"]:
        return reject(R_AGENT)
    # Generator first: the namespace key (seed check) is itself derived from the generator version.
    checks["generator_versions_known"] = str(state.config.generator_version) in psc.SUPPORTED_GENERATOR_VERSIONS
    if not checks["generator_versions_known"]:
        return reject(R_GENERATOR, f"config:{state.config.generator_version}")
    seed_ok = (
        isinstance(state.world_seed, int) and not isinstance(state.world_seed, bool)
        and state.seed_source == psc.SEED_SOURCE
        and state.namespace_key == psc.namespace_key(state.world_seed, state.config)
        and (world_seed is None or int(world_seed) == int(state.world_seed))
    )
    checks["authoritative_world_seed_valid"] = bool(seed_ok)
    if not seed_ok:
        return reject(R_SEED)
    try:
        finite = all(math.isfinite(float(v)) for v in (
            source_cell_x, source_cell_y, destination_cell_x, destination_cell_y))
    except (TypeError, ValueError):
        finite = False
    checks["coordinates_finite"] = finite
    if not finite:
        return reject(R_COORD)
    # WRAP before any other address logic; world (x, y) order, never NumPy (y, x).
    src = psc.wrap_cell(state, source_cell_x, source_cell_y)
    dst = psc.wrap_cell(state, destination_cell_x, destination_cell_y)
    plan["source_cell"] = [src[0], src[1]]
    plan["destination_cell"] = [dst[0], dst[1]]
    checks["distinct_after_wrap"] = src != dst
    if not checks["distinct_after_wrap"]:
        return reject(R_SAME)
    try:
        exp_src = _as_revision(expected_source_revision)
        exp_dst = _as_revision(expected_destination_revision)
        checks["expected_revisions_integer"] = True
    except (TypeError, ValueError):
        checks["expected_revisions_integer"] = False
        return reject(R_REV_TYPE)
    try:
        t = float(requested_thickness)
    except (TypeError, ValueError):
        t = float("nan")
    checks["thickness_finite"] = math.isfinite(t)
    if not checks["thickness_finite"]:
        return reject(R_NONFINITE)
    checks["thickness_positive"] = t > 0.0
    if t == 0.0:
        return reject(R_ZERO)
    if t < 0.0:
        return reject(R_NEGATIVE)
    try:
        _hook_candidate_construction("resolve")
        s_col = _resolved(world, src)
        d_col = _resolved(world, dst)
        for col in (s_col, d_col):
            d = col["delta"]
            if d is not None and d.baseline_generator_version not in psc.SUPPORTED_GENERATOR_VERSIONS:
                checks["generator_versions_known"] = False
                return reject(R_GENERATOR, f"delta:{d.delta_id}")
        checks["source_baseline_checksum_valid"] = (
            s_col["delta"] is None or s_col["delta"].baseline_checksum == s_col["baseline"].baseline_checksum
        )
        if not checks["source_baseline_checksum_valid"]:
            return reject(R_BASE_SRC)
        checks["destination_baseline_checksum_valid"] = (
            d_col["delta"] is None or d_col["delta"].baseline_checksum == d_col["baseline"].baseline_checksum
        )
        if not checks["destination_baseline_checksum_valid"]:
            return reject(R_BASE_DST)
        checks["source_revision_matches"] = exp_src == s_col["revision"]
        if not checks["source_revision_matches"]:
            return reject(R_STALE_SRC, f"expected={exp_src}:actual={s_col['revision']}")
        checks["destination_revision_matches"] = exp_dst == d_col["revision"]
        if not checks["destination_revision_matches"]:
            return reject(R_STALE_DST, f"expected={exp_dst}:actual={d_col['revision']}")
        checks["source_top_layer_exists"] = bool(s_col["layers"])
        if not checks["source_top_layer_exists"]:
            return reject(R_NO_TOP)
        top = s_col["layers"][0]
        checks["within_source_top_layer"] = t <= float(top.thickness)
        if not checks["within_source_top_layer"]:
            return reject(R_CROSS, f"requested={t!r}:top_layer_thickness={float(top.thickness)!r}")
        tcfg = tstate.config
        src_depth_after = s_col["resolved_depth"] - t
        checks["source_depth_above_minimum"] = src_depth_after >= float(tcfg.minimum_resolved_depth)
        if not checks["source_depth_above_minimum"]:
            return reject(R_DEPTH, f"resolved_depth_after={src_depth_after!r}:minimum={tcfg.minimum_resolved_depth}")
        checks["destination_depth_below_maximum"] = d_col["resolved_depth"] + t <= float(tcfg.maximum_resolved_depth)
        if not checks["destination_depth_below_maximum"]:
            return reject(R_DST_DEPTH)
        _hook_candidate_construction("split")
        sl, src_layers, whole = split_top_slice(s_col["layers"], t)
        _hook_candidate_construction("place")
        dst_layers, merge = place_slice_on_top(d_col["layers"], sl, float(tcfg.merge_tolerance))
        checks["destination_layer_limit_ok"] = len(dst_layers) <= int(tcfg.max_layers_per_column)
        if not checks["destination_layer_limit_ok"]:
            return reject(R_LAYERS, f"layers_after={len(dst_layers)}:max={tcfg.max_layers_per_column}")
        checks["no_negative_thickness"] = all(layer.thickness > 0.0 for layer in src_layers + dst_layers)
        if not checks["no_negative_thickness"]:
            return reject(R_INTERVAL, "negative_or_zero_thickness")
        src_elev_after = s_col["elevation"] - t
        dst_elev_after = d_col["elevation"] + t
        # Surface elevation support: reject destination rise under grounded occupants (no free PE).
        try:
            from mechanistic_mind.physical_system.surface_elevation_support import (
                surface_elevation_support_is_active,
                preflight_occupied_support_rise,
                apply_ground_lowered_to_occupants,
                EVENT_OCCUPIED_RISE_REJECTED,
            )
            if surface_elevation_support_is_active(config):
                rise = preflight_occupied_support_rise(
                    world, config,
                    cell_x=int(dst[0]), cell_y=int(dst[1]),
                    elevation_before=float(d_col["elevation"]),
                    elevation_after=float(dst_elev_after),
                    tick=int(tick),  # G2C1 provenance metadata only
                )
                checks["occupied_support_rise_ok"] = not bool(rise.get("reject"))
                if rise.get("reject"):
                    return reject(EVENT_OCCUPIED_RISE_REJECTED, f"occupants={len(rise.get('occupants') or [])}")
                # Source lowering: mark occupants airborne (z remains) — applied at commit, noted here.
                plan["_ses_source_lower"] = {
                    "cell": [int(src[0]), int(src[1])],
                    "elevation_before": float(s_col["elevation"]),
                    "elevation_after": float(src_elev_after),
                    "tick": int(tick),  # G2C1 provenance metadata only
                    "transaction_id": str(plan.get("transaction_id") or plan.get("id") or "") or None,
                }
        except Exception as _ses_exc:
            checks["occupied_support_rise_ok"] = True
            plan["_ses_preflight_error"] = f"{type(_ses_exc).__name__}:{_ses_exc}"
        src_expected = resolved_depth(s_col["baseline"], src_elev_after)
        dst_expected = resolved_depth(d_col["baseline"], dst_elev_after)
        v_src = psc.validate_layers(src_layers, src_expected)
        v_dst = psc.validate_layers(dst_layers, dst_expected)
        plan["interval_validation"] = {"source": v_src, "destination": v_dst}
        checks["resulting_intervals_valid"] = bool(v_src["verified"] and v_dst["verified"])
        slice_row = {
            "thickness": float(sl.thickness),
            "density": float(sl.density),
            "quantity_per_area": float(sl.quantity_per_area),
            "mass_per_area": float(sl.mass_per_area),
            "volume_per_area": float(sl.thickness),
            "composition": {cid: float(a) for cid, a in sl.composition},
            "composition_proportions": _proportions(sl),
            "material_property_derivation_version": sl.material_property_derivation_version,
            "source_layer_index": 0,
            "source_layer_thickness_before": float(top.thickness),
            "whole_source_layer": bool(whole),
            "generator_version": s_col["baseline"].generator_version,
            "source_baseline_checksum": s_col["baseline"].baseline_checksum,
            "source_state": "PROCEDURAL_BASELINE" if s_col["delta"] is None else "SPARSE_DELTA",
            "source_delta_revision": int(s_col["revision"]),
        }
        conservation = pair_conservation(
            _pair_summary(s_col["layers"], d_col["layers"]), _pair_summary(src_layers, dst_layers), slice_row,
        )
        conservation["elevation_sum"] = _domain(
            s_col["elevation"] + d_col["elevation"], src_elev_after + dst_elev_after,
        )
        plan["conservation"] = conservation
        if not checks["resulting_intervals_valid"]:
            return reject(R_INTERVAL, json.dumps({"source": v_src["problems"], "destination": v_dst["problems"]}))
        checks["conservation_domains_close"] = bool(conservation["verified"])
        if not checks["conservation_domains_close"]:
            return reject(R_CONSERVATION)
        new_cells = sum(1 for c in (s_col, d_col) if c["delta"] is None)
        checks["delta_capacity_ok"] = len(psc.deltas_of(world)) + new_cells <= psc.MAX_DELTAS
        if not checks["delta_capacity_ok"]:
            return reject(R_CAPACITY)
        comp = slice_row["composition"]
        signed_src = {"quantity": -slice_row["quantity_per_area"], "mass": -slice_row["mass_per_area"],
                      "components": {k: -v for k, v in comp.items()}}
        signed_dst = {"quantity": slice_row["quantity_per_area"], "mass": slice_row["mass_per_area"],
                      "components": dict(comp)}
        _hook_candidate_construction("deltas")
        src_delta = _candidate_delta(
            s_col, layers=src_layers, elevation=src_elev_after, tick=int(tick), transaction_id=transaction_id,
            provenance=_new_provenance(
                None if s_col["delta"] is None else s_col["delta"].provenance, role=ROLE_SOURCE, opposite=dst,
                transaction_id=transaction_id, transfer_id=transfer_id, previous_revision=s_col["revision"],
                baseline_checksum=s_col["baseline"].baseline_checksum, tick=int(tick),
                researcher_id=researcher_id, signed=signed_src,
            ),
        )
        dst_delta = _candidate_delta(
            d_col, layers=dst_layers, elevation=dst_elev_after, tick=int(tick), transaction_id=transaction_id,
            provenance=_new_provenance(
                None if d_col["delta"] is None else d_col["delta"].provenance, role=ROLE_DESTINATION, opposite=src,
                transaction_id=transaction_id, transfer_id=transfer_id, previous_revision=d_col["revision"],
                baseline_checksum=d_col["baseline"].baseline_checksum, tick=int(tick),
                researcher_id=researcher_id, signed=signed_dst,
            ),
        )
        checks["resulting_deltas_serializable"] = _serializable(src_delta) and _serializable(dst_delta)
        if not checks["resulting_deltas_serializable"]:
            return reject(R_SERIAL)
    except psc.SurfaceColumnValidationError as exc:
        return reject(R_CANDIDATE, str(exc))
    except Exception as exc:  # candidate construction failure never mutates world geometry
        return reject(R_CANDIDATE, f"{type(exc).__name__}:{exc}")
    plan["preconditions"] = dict(checks)
    plan["input_refs"] = [f"surface-column:x{src[0]}-y{src[1]}", f"surface-column:x{dst[0]}-y{dst[1]}"]
    plan["output_refs"] = [src_delta.delta_id, dst_delta.delta_id]
    plan["expected_revisions"] = {_column_key(src): int(s_col["revision"]), _column_key(dst): int(d_col["revision"])}
    plan["requested_thickness"] = t
    plan["slice"] = slice_row
    plan["merge"] = merge
    plan["candidates"] = {"source": src_delta, "destination": dst_delta}
    plan["before"] = {"source": _col_row(s_col), "destination": _col_row(d_col)}
    plan["after"] = {
        "source": {"elevation": src_elev_after, "resolved_depth": src_expected, "revision": src_delta.revision,
                   "checksum": src_delta.resolved_checksum(), "layer_count": len(src_layers)},
        "destination": {"elevation": dst_elev_after, "resolved_depth": dst_expected, "revision": dst_delta.revision,
                        "checksum": dst_delta.resolved_checksum(), "layer_count": len(dst_layers)},
    }
    plan["layer_ops"] = len(s_col["layers"]) + len(d_col["layers"]) + len(sl.composition)
    plan["plan_us"] = (time.perf_counter() - t_start) * 1e6
    return plan


# ---------------------------------------------------------------------------
# Commit (dispatched from world_material_transaction.commit_material_transaction)
# ---------------------------------------------------------------------------


def commit_planned_transfer(world: Any, plan: dict[str, Any]) -> dict[str, Any]:
    """Atomic pair commit. WMT has already rejected duplicate ids and stale revisions.

    Build every record first; publish both deltas with ONE assignment; then
    record ONE transaction (WMT ledger) and emit ONE causal event.
    """
    from mechanistic_mind.physical_system import world_material_transaction as wmt

    t_start = time.perf_counter()
    state = psc.state_of(world)
    tstate = transfer_state_of(world)
    if state is None or tstate is None:
        return _wmt_reject(world, plan, R_INACTIVE)
    if str(plan.get("transfer_id")) in tstate.committed_transfer_ids:
        return _wmt_reject(world, plan, R_DUPLICATE)
    src_delta: psc.SurfaceColumnDelta = plan["candidates"]["source"]
    dst_delta: psc.SurfaceColumnDelta = plan["candidates"]["destination"]
    src = (src_delta.cell_x, src_delta.cell_y)
    dst = (dst_delta.cell_x, dst_delta.cell_y)
    deltas = psc.deltas_of(world)
    for cell, key in ((src, "source"), (dst, "destination")):
        cur = deltas.get(cell)
        checksum = psc.baseline_column_at(world, *cell).baseline_checksum if cur is None else cur.resolved_checksum()
        if checksum != plan["before"][key]["checksum"]:
            return _wmt_reject(world, plan, R_STATE_CHANGED)
    receipt = build_transfer_receipt(plan, status="COMMITTED")
    new = dict(deltas)
    new[src] = src_delta
    _hook_before_destination_write()
    new[dst] = dst_delta
    _hook_before_publish()
    receipt["cost"]["commit_us"] = (time.perf_counter() - t_start) * 1e6
    # ---- single atomic publish: both columns change together or not at all ----
    world.surface_column_deltas = new
    # Elevation support: source lowered under occupants → airborne, z remains (no snap).
    try:
        from mechanistic_mind.physical_system.surface_elevation_support import (
            surface_elevation_support_is_active,
            apply_ground_lowered_to_occupants,
        )
        cfg = plan.get("config")
        if cfg is not None and surface_elevation_support_is_active(cfg):
            info = plan.get("_ses_source_lower") or {}
            if info:
                apply_ground_lowered_to_occupants(
                    world, cfg,
                    cell_x=int(info["cell"][0]), cell_y=int(info["cell"][1]),
                    elevation_before=(
                        float(info["elevation_before"])
                        if info.get("elevation_before") is not None
                        else None
                    ),
                    elevation_after=float(info["elevation_after"]),
                    tick=info.get("tick"),  # G2C1 provenance metadata only
                    transaction_id=info.get("transaction_id"),
                )
    except Exception:
        pass
    # ---- record: one transaction (ledger) and one causal event (plain list/dict operations) ----
    wmt._remember(world, compact_event(receipt))
    _record(world, state, tstate, receipt)
    return {"legacy": None, "receipt": receipt}


def _wmt_reject(world: Any, plan: dict[str, Any], code: str) -> dict[str, Any]:
    from mechanistic_mind.physical_system import world_material_transaction as wmt

    receipt = wmt._base_receipt(plan, status="REJECTED", reason=code)
    wmt._remember(world, receipt)
    return {"legacy": None, "receipt": receipt}


def _residual_max(conservation: dict[str, Any]) -> dict[str, float] | None:
    if not conservation:
        return None
    return {
        "mass": abs(float((conservation.get("mass") or {}).get("residual") or 0.0)),
        "quantity": abs(float((conservation.get("quantity") or {}).get("residual") or 0.0)),
        "components": float((conservation.get("components") or {}).get("residual_max_abs") or 0.0),
        "elevation": abs(float((conservation.get("elevation_sum") or {}).get("residual") or 0.0)),
    }


def build_transfer_receipt(plan: dict[str, Any], *, status: str, reason: str | None = None) -> dict[str, Any]:
    """Scientific receipt SURFACE_COLUMN_TRANSFER (bounded; no full opposite column)."""
    before = plan.get("before") or {}
    after = plan.get("after") or {}
    sb, db = before.get("source") or {}, before.get("destination") or {}
    sa, da = after.get("source") or {}, after.get("destination") or {}
    ok = status == "COMMITTED"
    slice_row = plan.get("slice") or {}
    conservation = plan.get("conservation") or {}
    merge = plan.get("merge") or {}
    receipt = {
        "event": EVENT_COMMITTED if ok else EVENT_REJECTED,
        "receipt_kind": RECEIPT_KIND,
        "receipt_schema": RECEIPT_SCHEMA,
        "transaction_event_schema": "WORLD_MATERIAL_TRANSACTION",
        "schema_version": plan.get("schema_version"),
        "transaction_id": plan.get("transaction_id"),
        "transfer_id": plan.get("transfer_id"),
        "sequence": plan.get("sequence"),
        "tick": plan.get("tick"),
        "model_line": plan.get("model_line"),
        "public_preset": plan.get("public_preset"),
        "operation_kind": OPERATION_KIND,
        "command": None,
        "actor_body_id": None,
        "actor_agent_id": None,
        "researcher_id": plan.get("researcher_id"),
        "selection_provenance": plan.get("selection_provenance"),
        "status": status,
        "rejection_reason": reason,
        "rejection_detail": None if ok else plan.get("rejection_detail"),
        "raw_inputs": plan.get("raw_inputs"),
        "source_cell": plan.get("source_cell"),
        "destination_cell": plan.get("destination_cell"),
        "input_refs": list(plan.get("input_refs") or []),
        "output_refs": list(plan.get("output_refs") or []),
        "expected_revisions": dict(plan.get("expected_revisions") or {}),
        "preconditions": dict(plan.get("preconditions") or {}),
        "requested_thickness": plan.get("requested_thickness", (plan.get("raw_inputs") or {}).get("requested_thickness")),
        "committed_thickness": float(slice_row.get("thickness", 0.0)) if ok else 0.0,
        "source_revision_before": sb.get("revision"),
        "source_revision_after": sa.get("revision") if ok else sb.get("revision"),
        "destination_revision_before": db.get("revision"),
        "destination_revision_after": da.get("revision") if ok else db.get("revision"),
        "source_elevation_before": sb.get("elevation"),
        "source_elevation_after": sa.get("elevation") if ok else sb.get("elevation"),
        "destination_elevation_before": db.get("elevation"),
        "destination_elevation_after": da.get("elevation") if ok else db.get("elevation"),
        "source_fixed_lower_datum": sb.get("fixed_lower_datum"),
        "destination_fixed_lower_datum": db.get("fixed_lower_datum"),
        "source_resolved_depth_before": sb.get("resolved_depth"),
        "source_resolved_depth_after": sa.get("resolved_depth") if ok else sb.get("resolved_depth"),
        "destination_resolved_depth_before": db.get("resolved_depth"),
        "destination_resolved_depth_after": da.get("resolved_depth") if ok else db.get("resolved_depth"),
        "slice_density": slice_row.get("density"),
        "transferred_volume_per_area": slice_row.get("volume_per_area") if ok else 0.0,
        "transferred_mass_per_area": slice_row.get("mass_per_area") if ok else 0.0,
        "transferred_quantity_per_area": slice_row.get("quantity_per_area") if ok else 0.0,
        "transferred_component_amounts": dict(slice_row.get("composition") or {}) if ok else {},
        "slice": dict(slice_row) if slice_row else None,
        "source_checksum_before": sb.get("checksum"),
        "source_checksum_after": sa.get("checksum") if ok else sb.get("checksum"),
        "destination_checksum_before": db.get("checksum"),
        "destination_checksum_after": da.get("checksum") if ok else db.get("checksum"),
        "source_baseline_checksum": sb.get("baseline_checksum"),
        "destination_baseline_checksum": db.get("baseline_checksum"),
        "conservation": conservation,
        "conservation_verified": bool(conservation.get("verified")) if conservation else None,
        "conservation_residual_max": _residual_max(conservation),
        "interval_validation": {
            k: {"verified": v.get("verified"), "problems": v.get("problems"), "layer_count": v.get("layer_count"),
                "boundary_policy": v.get("boundary_policy")}
            for k, v in (plan.get("interval_validation") or {}).items()
        },
        "layer_merge_status": merge.get("status"),
        "layer_merge_mismatch": merge.get("mismatch"),
        "source_layer_removed": bool(slice_row.get("whole_source_layer")) if ok else False,
        "atomic_pair": {
            "both_columns_written": ok,
            "single_publish": True,
            "touched_columns": 2 if ok else 0,
            "source_revision_increment": 1 if ok else 0,
            "destination_revision_increment": 1 if ok else 0,
        },
        "provenance_refs": {
            "transaction_id": plan.get("transaction_id"),
            "transfer_id": plan.get("transfer_id"),
            "source_delta_id": sb.get("delta_id"),
            "destination_delta_id": db.get("delta_id"),
            "source_previous_revision": sb.get("revision"),
            "destination_previous_revision": db.get("revision"),
            "source_baseline_checksum": sb.get("baseline_checksum"),
            "destination_baseline_checksum": db.get("baseline_checksum"),
            "roles": {"source": ROLE_SOURCE, "destination": ROLE_DESTINATION},
        },
        "policies": {"datum": DATUM_POLICY, "merge": MERGE_POLICY, "transfer": TRANSFER_POLICY,
                     "boundary": psc.BOUNDARY_POLICY, "order": ORDER_POLICY},
        "cost": {"plan_us": float(plan.get("plan_us") or 0.0), "commit_us": 0.0,
                 "touched_columns": 2, "layer_ops": int(plan.get("layer_ops") or 0),
                 "full_world_scan": False, "dense_volume": False, "world_clone": False},
        "legacy_equivalence": True,
        "semantic_effects": False,
        "surface_elevation_changed": ok,
        "geometry_role": psc.GEOMETRY_ROLE,
        "surface_elevation_status": psc.SURFACE_ELEVATION_STATUS,
        "persistent_scar": "PERSISTENT_AUTHORITATIVE_GEOMETRY_SCAR_PHYSICAL_EFFECTS_INACTIVE" if ok else None,
        "reason": plan.get("reason"),
    }
    receipt.update(EFFECT_FLAGS)
    return receipt


_COMPACT_DICT_KEYS = ("conservation_residual_max", "atomic_pair", "cost", "transferred_component_amounts")


def compact_event(receipt: dict[str, Any]) -> dict[str, Any]:
    """Bounded causal-event / ledger form of a transfer receipt (scalars + small refs).

    The full receipt lives once in the bounded transfer history; the WMT ledger and the
    surface-column event stream keep this compact form so snapshot size stays bounded.
    """
    out: dict[str, Any] = {}
    for key, value in receipt.items():
        if value is None or isinstance(value, (bool, int, float, str)):
            out[key] = value
        elif isinstance(value, list) and len(value) <= 4 and all(
            isinstance(v, (int, float, str)) for v in value
        ):
            out[key] = list(value)
    for key in _COMPACT_DICT_KEYS:
        if isinstance(receipt.get(key), dict):
            out[key] = dict(receipt[key])
    out["expected_revisions"] = dict(receipt.get("expected_revisions") or {})
    iv = receipt.get("interval_validation") or {}
    out["interval_validation_verified"] = bool(iv) and all(bool(v.get("verified")) for v in iv.values())
    out["compact"] = True
    return out


def _record(world: Any, state: psc.SurfaceColumnState, tstate: ColumnTransferState, receipt: dict[str, Any]) -> None:
    ok = receipt.get("status") == "COMMITTED"
    tstate.history.append(receipt)
    if len(tstate.history) > HISTORY_LIMIT:
        del tstate.history[: len(tstate.history) - HISTORY_LIMIT]
    if ok:
        tstate.counters["committed"] = int(tstate.counters.get("committed", 0)) + 1
        tstate.committed_transfer_ids.append(str(receipt.get("transfer_id")))
        del tstate.committed_transfer_ids[:-COMMITTED_TRANSFER_ID_LIMIT]
        if receipt.get("layer_merge_status") == MERGED:
            tstate.counters["merged"] = int(tstate.counters.get("merged", 0)) + 1
        for k, v in (receipt.get("conservation_residual_max") or {}).items():
            tstate.residual_max[k] = max(float(tstate.residual_max.get(k, 0.0)), float(v))
        cost = receipt.get("cost") or {}
        for k in ("plan_us", "commit_us", "layer_ops"):
            tstate.cost_max[k] = max(float(tstate.cost_max.get(k, 0.0)), float(cost.get(k, 0.0) or 0.0))
    else:
        tstate.counters["rejected"] = int(tstate.counters.get("rejected", 0)) + 1
        if str(receipt.get("rejection_reason") or "").startswith("STALE_"):
            tstate.counters["stale_conflicts"] = int(tstate.counters.get("stale_conflicts", 0)) + 1
        state.validation_failure_count += 1
    # One causal event in the researcher-only surface-column event stream (bounded, compact).
    psc._remember(world, state, compact_event(receipt))


# ---------------------------------------------------------------------------
# Researcher / controlled-test API (never cognition, never motor vocabulary)
# ---------------------------------------------------------------------------


def _map_wmt_reason(plan: dict[str, Any], reason: str) -> str:
    text = str(reason or "")
    if text.startswith("stale:column:"):
        key = text.split(":", 1)[1]
        src = plan.get("source_cell") or [None, None]
        return R_STALE_SRC if src[0] is not None and key == _column_key(tuple(src)) else R_STALE_DST
    if text.startswith("missing:column:"):
        return R_STATE_CHANGED
    if text == "precondition":
        return str(plan.get("rejection_reason") or R_CANDIDATE)
    if text and text == str(plan.get("rejection_reason") or ""):
        return text
    if text in {R_DUPLICATE, R_INACTIVE, R_STATE_CHANGED, R_STALE_SRC, R_STALE_DST}:
        return text
    return f"{R_COMMIT_EXCEPTION}:{text}" if text else R_COMMIT_EXCEPTION


def commit_surface_column_transfer(world: Any, plan: dict[str, Any]) -> dict[str, Any]:
    """Commit through the existing WMT entry point; return the SURFACE_COLUMN_TRANSFER receipt."""
    from mechanistic_mind.physical_system import world_material_transaction as wmt

    result = wmt.commit_material_transaction(world, plan)
    wreceipt = result.get("receipt") or {}
    if wreceipt.get("status") == "COMMITTED" and wreceipt.get("receipt_kind") == RECEIPT_KIND:
        return wreceipt
    code = _map_wmt_reason(plan, str(wreceipt.get("rejection_reason") or plan.get("rejection_reason") or ""))
    receipt = build_transfer_receipt(plan, status="REJECTED", reason=code)
    state = psc.state_of(world)
    tstate = transfer_state_of(world)
    if state is not None and tstate is not None:
        _record(world, state, tstate, receipt)
    return receipt


def apply_surface_column_transfer(world: Any, config: Any, **kwargs: Any) -> dict[str, Any]:
    """Researcher setup/intervention adapter: plan (no mutation) + atomic WMT commit."""
    plan = plan_surface_column_transfer(world, config, **kwargs)
    return commit_surface_column_transfer(world, plan)


PROPOSAL_FIELDS = (
    "source_cell_x", "source_cell_y", "destination_cell_x", "destination_cell_y",
    "requested_thickness", "expected_source_revision", "expected_destination_revision",
)


def _proposal_sort_key(state: psc.SurfaceColumnState | None, p: dict[str, Any]) -> tuple:
    def cell(x: Any, y: Any) -> tuple:
        try:
            if state is not None and math.isfinite(float(x)) and math.isfinite(float(y)):
                return (0,) + psc.wrap_cell(state, x, y)
        except (TypeError, ValueError):
            pass
        return (1, repr(x), repr(y))

    try:
        th = float(p.get("requested_thickness")).hex()
    except (TypeError, ValueError):
        th = repr(p.get("requested_thickness"))
    return (
        str(p.get("proposer_id") or p.get("researcher_id") or ""),
        cell(p.get("source_cell_x"), p.get("source_cell_y")),
        cell(p.get("destination_cell_x"), p.get("destination_cell_y")),
        th,
        repr(p.get("expected_source_revision")),
        repr(p.get("expected_destination_revision")),
    )


def resolve_transfer_proposals(
    world: Any, config: Any, proposals: list[dict[str, Any]], *, tick: int, world_seed: int | None = None,
) -> list[dict[str, Any]]:
    """Same-tick controlled proposals, deterministic and independent of submission/process order.

    Order: proposer id ascending, then canonical wrapped addresses and thickness
    (same rule family as manipulator contention: sorted ids, never process order).
    All plans are built against the same pre-commit state; commits then run in
    that order, so the first valid commit advances revisions and every later
    proposal holding a stale expected revision is rejected by the WMT stale check.
    """
    state = psc.state_of(world)
    ordered = sorted(proposals, key=lambda p: _proposal_sort_key(state, p))
    plans = []
    for p in ordered:
        kwargs = {k: p.get(k) for k in PROPOSAL_FIELDS}
        plans.append(plan_surface_column_transfer(
            world, config, tick=int(tick), world_seed=world_seed,
            researcher_id=str(p.get("proposer_id") or p.get("researcher_id") or "researcher"),
            selection_provenance=str(p.get("selection_provenance") or SELECTION_PROVENANCE),
            agent_action=bool(p.get("agent_action", False)),
            reason=str(p.get("reason") or "controlled_same_tick_proposal"),
            **kwargs,
        ))
    return [commit_surface_column_transfer(world, plan) for plan in plans]


# ---------------------------------------------------------------------------
# Snapshot / restore / copy
# ---------------------------------------------------------------------------


def _seed_provenance_checksum(state: psc.SurfaceColumnState) -> str:
    return psc._sha16(psc.seed_provenance(state))


def serialize_transfer_state(state: psc.SurfaceColumnState) -> dict[str, Any] | None:
    tstate = getattr(state, "transfer", None)
    if not isinstance(tstate, ColumnTransferState):
        return None
    return {
        "schema": STATE_SCHEMA,
        "mechanism": MECHANISM_ID,
        "config": tstate.config.to_dict(),
        "generator_version": state.config.generator_version,
        "world_seed": int(state.world_seed),
        "seed_provenance_checksum": _seed_provenance_checksum(state),
        "transfer_sequence": int(tstate.transfer_sequence),
        "committed_transfer_ids": list(tstate.committed_transfer_ids)[-COMMITTED_TRANSFER_ID_LIMIT:],
        "history": list(tstate.history)[-HISTORY_LIMIT:],
        "counters": dict(tstate.counters),
        "residual_max": dict(tstate.residual_max),
        "cost_max": dict(tstate.cost_max),
    }


def _state_from_data(data: dict[str, Any]) -> ColumnTransferState:
    cfg = ConservativeSurfaceColumnTransferConfig.from_dict(data.get("config") or {})
    cfg.enabled = True
    validate_transfer_config(cfg)
    tstate = ColumnTransferState(
        config=cfg,
        transfer_sequence=int(data.get("transfer_sequence", 0) or 0),
        history=[dict(r) for r in (data.get("history") or [])][-HISTORY_LIMIT:],
        committed_transfer_ids=[str(v) for v in (data.get("committed_transfer_ids") or [])][
            -COMMITTED_TRANSFER_ID_LIMIT:
        ],
    )
    tstate.counters.update({k: int(v) for k, v in (data.get("counters") or {}).items()})
    tstate.residual_max.update({k: float(v) for k, v in (data.get("residual_max") or {}).items()})
    tstate.cost_max.update({k: float(v) for k, v in (data.get("cost_max") or {}).items()})
    return tstate


def restore_transfer_state(world: Any, state: psc.SurfaceColumnState, data: dict[str, Any] | None,
                           *, tick: int = 0) -> ColumnTransferState | None:
    """Restore bounded transfer bookkeeping; never repeats a transfer or creates a delta."""
    if not isinstance(data, dict) or not data:
        state.transfer = None
        return None
    if data.get("schema") != STATE_SCHEMA:
        raise psc.SurfaceColumnValidationError(f"{psc.EVENT_VALIDATION_FAILED}: unknown transfer state schema")
    if str(data.get("generator_version") or "") != state.config.generator_version:
        raise psc.SurfaceColumnValidationError(
            f"{psc.EVENT_VALIDATION_FAILED}: transfer state generator version mismatch"
        )
    if int(data.get("world_seed", -1)) != int(state.world_seed) or str(
        data.get("seed_provenance_checksum") or ""
    ) != _seed_provenance_checksum(state):
        raise psc.SurfaceColumnValidationError(
            f"{psc.EVENT_VALIDATION_FAILED}: transfer state seed provenance mismatch"
        )
    tstate = _state_from_data(data)
    state.transfer = tstate
    tstate.restore_verification = verify_transfer_deltas(world, state)
    if not tstate.restore_verification["verified"]:
        raise psc.SurfaceColumnValidationError(
            f"{psc.EVENT_VALIDATION_FAILED}: transfer delta verification failed "
            f"{tstate.restore_verification['problems'][:4]}"
        )
    psc._remember(world, state, psc._event(
        EVENT_RESTORE_VERIFIED, tick=int(tick), status="VERIFIED", receipt_kind=RECEIPT_KIND,
        transfer_delta_count=tstate.restore_verification["transfer_delta_count"],
        closed_world_residual_max=tstate.restore_verification["closed_world_residual_max"],
        per_column_residual_max=tstate.restore_verification["per_column_residual_max"],
        provenance="SNAPSHOT_RESTORE", researcher_only=True, agent_action=False,
    ))
    return tstate


def verify_transfer_deltas(world: Any, state: psc.SurfaceColumnState) -> dict[str, Any]:
    """Re-derive every transfer-touched column from baseline + delta.

    Per column: resolved - baseline == recorded net exchange (mass, quantity,
    components) and elevation change == net quantity (volume per unit area).
    World: sum of net exchange over all transfer deltas == 0 (closed system).
    """
    problems: list[str] = []
    per_col = 0.0
    total: dict[str, list[float]] = {"mass": [], "quantity": [], "elevation": []}
    comp_total: dict[str, list[float]] = {}
    count = 0
    for cell, delta in sorted(psc.deltas_of(world).items()):
        net = (delta.provenance or {}).get("net_exchange")
        if not isinstance(net, dict):
            continue
        count += 1
        base = psc.generate_baseline_v1(
            world_seed=state.world_seed, cell_x=cell[0], cell_y=cell[1], width=state.width,
            height=state.height, cfg=state.config, key=state.namespace_key,
        )
        sb, sa = psc.mass_summary(base.layers), psc.mass_summary(delta.resulting_layers)
        d_mass = sa["total_mass_per_area"] - sb["total_mass_per_area"]
        d_qty = sa["total_quantity_per_area"] - sb["total_quantity_per_area"]
        d_elev = float(delta.resulting_surface_elevation) - float(base.surface_elevation)
        net_q = float(net.get("quantity_per_area", 0.0))
        res = [abs(d_mass - float(net.get("mass_per_area", 0.0))), abs(d_qty - net_q), abs(d_elev - net_q)]
        comps = net.get("component_quantity_per_area") or {}
        keys = set(sb["component_quantity_per_area"]) | set(sa["component_quantity_per_area"]) | set(comps)
        for cid in sorted(keys):
            dc = float(sa["component_quantity_per_area"].get(cid, 0.0)) - float(
                sb["component_quantity_per_area"].get(cid, 0.0))
            res.append(abs(dc - float(comps.get(cid, 0.0))))
            comp_total.setdefault(cid, []).append(float(comps.get(cid, 0.0)))
        worst = max(res)
        per_col = max(per_col, worst)
        if worst > RESTORE_TOLERANCE:
            problems.append(f"{delta.delta_id}:net_exchange_residual={worst!r}")
        total["mass"].append(float(net.get("mass_per_area", 0.0)))
        total["quantity"].append(net_q)
        total["elevation"].append(d_elev)
    closed = [abs(math.fsum(v)) for v in total.values()] + [abs(math.fsum(v)) for v in comp_total.values()]
    closed_max = max(closed, default=0.0)
    if closed_max > RESTORE_TOLERANCE:
        problems.append(f"closed_world_residual={closed_max!r}")
    return {
        "status": "VERIFIED" if not problems else "FAILED",
        "verified": not problems,
        "transfer_delta_count": count,
        "per_column_residual_max": float(per_col),
        "closed_world_residual_max": float(closed_max),
        "tolerance": RESTORE_TOLERANCE,
        "problems": problems,
    }


def copy_transfer_state(src_state: psc.SurfaceColumnState, dst_state: psc.SurfaceColumnState) -> None:
    data = serialize_transfer_state(src_state)
    if data is None:
        dst_state.transfer = None
        return
    tstate = _state_from_data(json.loads(json.dumps(data)))
    tstate.restore_verification = dict(getattr(src_state.transfer, "restore_verification", {}) or {})
    dst_state.transfer = tstate


# ---------------------------------------------------------------------------
# Researcher-only views (Observer inspector, Scientific V3). Never cognition.
# ---------------------------------------------------------------------------

VIEW_LABELS = (
    "researcher-only",
    "not agent-accessible",
    "authoritative world geometry",
    "physical body effects inactive",
    "not an excavation action",
)


def cell_transfer_view(world: Any, x: Any, y: Any) -> dict[str, Any] | None:
    """Pure read (no receipt, no mutation) of one column's transfer geometry."""
    state = psc.state_of(world)
    if state is None or transfer_state_of(world) is None:
        return None
    cell = psc.wrap_cell(state, x, y)
    col = _resolved(world, cell)
    base = col["baseline"]
    prov = (col["delta"].provenance if col["delta"] is not None else {}) or {}
    return {
        "cell": [cell[0], cell[1]],
        "surface_elevation": col["elevation"],
        "baseline_surface_elevation": float(base.surface_elevation),
        "elevation_delta": col["elevation"] - float(base.surface_elevation),
        "fixed_lower_datum": col["datum"],
        "resolved_modelled_depth": col["resolved_depth"],
        "baseline_modelled_depth": float(base.modelled_depth),
        "column_revision": col["revision"],
        "layer_count": len(col["layers"]),
        "last_transfer_id": prov.get("last_transfer_id"),
        "last_transaction_id": prov.get("last_transaction_id") if prov.get("last_transfer_id") else None,
        "transfer_role": prov.get("transfer_role"),
        "opposite_cell": prov.get("opposite_cell"),
        "labels": list(VIEW_LABELS),
        "researcher_only": True,
        "agent_accessible": False,
        "authoritative_world_geometry": True,
        "physical_effects_active": False,
        "physical_body_effect": False,
        "excavation_action": False,
        "geometry_role": psc.GEOMETRY_ROLE,
        "datum_policy": DATUM_POLICY,
        "rendering": "NO_3D_PIT_OR_PILE",
    }


def researcher_summary(world: Any) -> dict[str, Any] | None:
    state = psc.state_of(world)
    tstate = transfer_state_of(world)
    if state is None or tstate is None:
        return None
    transfer_cells = []
    for cell, delta in sorted(psc.deltas_of(world).items()):
        prov = delta.provenance or {}
        if prov.get("last_transfer_id"):
            transfer_cells.append({
                "cell": [cell[0], cell[1]], "role": prov.get("transfer_role"), "revision": int(delta.revision),
                "last_transfer_id": prov.get("last_transfer_id"),
            })
    return {
        "mechanism": MECHANISM_ID,
        "operation_kind": OPERATION_KIND,
        "receipt_kind": RECEIPT_KIND,
        "config": tstate.config.to_dict(),
        "counters": dict(tstate.counters),
        "residual_max": dict(tstate.residual_max),
        "cost_max": dict(tstate.cost_max),
        "transfer_sequence": int(tstate.transfer_sequence),
        "committed_transfer_count": len(tstate.committed_transfer_ids),
        "transfer_delta_count": len(transfer_cells),
        "transfer_cells": transfer_cells[:32],
        "receipts": list(tstate.history)[-HISTORY_LIMIT:],
        "restore_verification": dict(tstate.restore_verification),
        "selection_provenance": SELECTION_PROVENANCE,
        "labels": list(VIEW_LABELS),
        **EFFECT_FLAGS,
    }


def conservative_surface_column_transfer_catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "config_path": "conservative_surface_column_transfer.enabled",
        "enabled": bool(enabled),
        "scientific_status": "IMPLEMENTED",
        "promotion_class": "EXPERIMENTAL",
        "description": (
            "Researcher-only TRANSFER_SURFACE_COLUMN_SLICE: one contiguous top slice moves between two "
            "procedural surface columns as one atomic, conservative WORLD_MATERIAL_TRANSACTION; both "
            "columns persist as sparse deltas. selection_provenance=INTERVENTION_SETUP. agent_action=false. "
            "agent_accessible=false. physical_effects_active=false. Not excavation, not a resource spawn."
        ),
    }
