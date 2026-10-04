"""Acanthostega local physical signal transport (LOCAL_PHYSICAL_SIGNAL_TRANSPORT_V1).

Replaces, ONLY in ACANTHOSTEGA_PHASE_B_LOCAL_SIGNAL, the transport seam of the existing
oscillatory signaling path (motor OSC_EMIT -> body emission state -> OSC_BANDS diffusion
-> L/R receptor sampling -> anonymous osc_l_* / osc_r_* channels) with a bounded,
event-based finite-speed wavefront:

    OSC_EMIT (unchanged motor) -> PhysicalSignalEmission at the body pose (end of tick te)
    -> expanding wavefront in a uniform medium (UNIFORM_SIGNAL_MEDIUM_V1)
    -> reception by whichever bodies the wavefront crosses (pose at arrival)
    -> summed anonymous band energy at the existing L/R head-linked receptors
    -> the same anonymous osc_l_k / osc_r_k cognition channels.

Law (versioned):
    d        = toroidal_distance(source, receiver)            (shortest path on the torus)
    n        = observation_tick - emission_tick               (>= 1: no same-tick reception)
    front(n) = n * propagation_speed                           (wavefront radius at tick te+n)
    arrival  : first observation tick A at which the front crossed the receiver between its
               previous and current pose: d_prev > front(n-1) (>= for n == 1) and d_now <= front(n).
               For a static receiver A = te + max(1, ceil(d / v)).
    energy_b = emitted_b / (1 + attenuation_k * d^2)
    accepted iff d <= maximum_range and sum_b energy_b >= reception_threshold (noise_floor = 0).

Not acoustics: no material, geometry, occlusion, reflection, atmosphere, wind or water.
No language, no message, no source identity/position/distance/bearing to cognition.
"""
from __future__ import annotations

import bisect
import math
from dataclasses import dataclass, field
from typing import Any

MECHANISM_ID = "local_physical_signal_transport"
STATE_SCHEMA = "LOCAL_PHYSICAL_SIGNAL_TRANSPORT_STATE_V1"
EMISSION_SCHEMA = "PHYSICAL_SIGNAL_EMISSION_V1"
MEDIUM_VERSION = "UNIFORM_SIGNAL_MEDIUM_V1"
ATTENUATION_VERSION = "INVERSE_QUADRATIC_ATTENUATION_V1"
PROPAGATION_LAW = "WAVEFRONT_CROSSING_CEIL_DISTANCE_OVER_SPEED_V1"
RECEIVER_POLICY = "POSE_AT_ARRIVAL_WAVEFRONT_CROSSING_V1"
AGGREGATION_POLICY = "SUM_THEN_EXISTING_OSC_SENSOR_CLIP_V1"
INDEX_POLICY = "WAVEFRONT_SHELL_CELLS_X_MULTI_CONTENT_BODY_REFS_V1"
EMISSION_RECEIPT = "LOCAL_PHYSICAL_SIGNAL_EMISSION"
RECEPTION_RECEIPT = "LOCAL_PHYSICAL_SIGNAL_RECEPTION"
EVENT_STEP = "LOCAL_PHYSICAL_SIGNAL_STEP"

PROV_ENDOGENOUS = "ENDOGENOUS_MOTOR"
PROV_EXPERIMENTER_BODY = "INTERVENTION_EXPERIMENTER_BODY"
PROV_INTERVENTION = "INTERVENTION_SETUP"
# Uncontrolled physical source (Audio B, ACANTHOSTEGA_PHASE_B_CONTACT_ACOUSTICS only): a measured
# body-body contact impulse. Enters through emit_local_physical_signal(); same transport law.
PROV_PHYSICAL_CONTACT = "PHYSICAL_CONTACT_IMPULSE"

R_BEYOND_RANGE = "BEYOND_MAXIMUM_RANGE"
R_BELOW_THRESHOLD = "BELOW_RECEPTION_THRESHOLD"
R_CAPACITY = "ACTIVE_EMISSION_CAPACITY"

# Bounded receiver displacement per tick assumed by the shell query (cells). Bodies move
# <= v_max (0.3-0.4 cells/tick); faster jumps are researcher teleports (documented).
MAX_RECEIVER_STEP = 1.0
CELL_MARGIN = 1.5  # sub-cell offset of source + receiver inside their cells (<= 2 * 0.7072)

AGENT_VISIBLE_FIELDS = ("osc_l_<k>", "osc_r_<k>")
RESEARCHER_ONLY_FIELDS = (
    "emission_id", "source_body_id", "source_position", "receiver_position",
    "toroidal_distance", "propagation_delay", "attenuation", "self_reception",
)

EFFECT_FLAGS = {
    "semantic_message": False,
    "semantic_payload": False,
    "direct_delivery": False,
    "global_delivery": False,
    "source_identity_exposed": False,
    "exact_distance_exposed": False,
    "bearing_exposed": False,
    "researcher_only": True,
    "agent_accessible": False,
}

OBSERVER_LABELS = (
    "researcher-only",
    "not agent-accessible",
    "not a semantic message",
    "finite range",
    "finite propagation delay",
)


# ---------------------------------------------------------------------------
# Config / gate
# ---------------------------------------------------------------------------


@dataclass
class UniformSignalMediumConfig:
    """Fresh default OFF. Missing snapshot/config field keeps the mechanism OFF."""

    enabled: bool = False
    propagation_speed: float = 2.0       # cells per tick
    attenuation_coefficient: float = 0.08  # per cell^2
    maximum_range: float = 8.0           # cells
    reception_threshold: float = 0.03    # summed band energy at the body
    noise_floor: float = 0.0
    sensor_scale: float = 2.0            # = existing oscillatory field_cap (osc sensor normalisation)
    max_active_emissions: int = 256
    history_limit: int = 32

    @property
    def max_arrival_delay(self) -> int:
        return int(max(1, math.ceil(float(self.maximum_range) / float(self.propagation_speed) - 1e-12)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "propagation_speed": float(self.propagation_speed),
            "attenuation_coefficient": float(self.attenuation_coefficient),
            "maximum_range": float(self.maximum_range),
            "reception_threshold": float(self.reception_threshold),
            "noise_floor": float(self.noise_floor),
            "sensor_scale": float(self.sensor_scale),
            "max_active_emissions": int(self.max_active_emissions),
            "history_limit": int(self.history_limit),
            "medium_version": MEDIUM_VERSION,
            "attenuation_version": ATTENUATION_VERSION,
            "propagation_law": PROPAGATION_LAW,
            "receiver_policy": RECEIVER_POLICY,
            "aggregation_policy": AGGREGATION_POLICY,
            "max_arrival_delay": self.max_arrival_delay,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "UniformSignalMediumConfig":
        if not isinstance(data, dict) or not data:
            return cls(enabled=False)
        mv = data.get("medium_version")
        if mv is not None and str(mv) != MEDIUM_VERSION:
            raise ValueError(f"unknown signal medium version: {mv}")
        av = data.get("attenuation_version")
        if av is not None and str(av) != ATTENUATION_VERSION:
            raise ValueError(f"unknown attenuation version: {av}")
        return cls(
            enabled=bool(data.get("enabled", False)),
            propagation_speed=float(data.get("propagation_speed", 2.0)),
            attenuation_coefficient=float(data.get("attenuation_coefficient", 0.08)),
            maximum_range=float(data.get("maximum_range", 8.0)),
            reception_threshold=float(data.get("reception_threshold", 0.03)),
            noise_floor=float(data.get("noise_floor", 0.0)),
            sensor_scale=float(data.get("sensor_scale", 2.0)),
            max_active_emissions=int(data.get("max_active_emissions", 256)),
            history_limit=int(data.get("history_limit", 32)),
        )


def validate_medium(cfg: UniformSignalMediumConfig) -> None:
    v, k, r, th = (float(cfg.propagation_speed), float(cfg.attenuation_coefficient),
                   float(cfg.maximum_range), float(cfg.reception_threshold))
    for name, val in (("propagation_speed", v), ("attenuation_coefficient", k),
                      ("maximum_range", r), ("reception_threshold", th)):
        if not math.isfinite(val):
            raise ValueError(f"{name} must be finite")
    if not (0.1 <= v <= 16.0):
        raise ValueError("propagation_speed must be in [0.1, 16]")
    if not (0.0 < k <= 10.0):
        raise ValueError("attenuation_coefficient must be in (0, 10]")
    if not (0.5 <= r <= 16.0):
        raise ValueError("maximum_range must be in [0.5, 16] (bounded support on the 32x32 torus)")
    if not (0.0 < th):
        raise ValueError("reception_threshold must be > 0")
    if float(cfg.noise_floor) != 0.0:
        raise ValueError("noise_floor must be 0 in V1")
    if not (1 <= int(cfg.max_active_emissions) <= 4096):
        raise ValueError("max_active_emissions must be in [1, 4096]")
    if not (1 <= int(cfg.history_limit) <= 256):
        raise ValueError("history_limit must be in [1, 256]")


def _line_ok(config: Any) -> bool:
    return config is not None and str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"


def local_physical_signal_transport_is_active(config: Any) -> bool:
    if not _line_ok(config):
        return False
    cfg = getattr(config, "local_physical_signal_transport", None)
    return bool(cfg is not None and getattr(cfg, "enabled", False))


def set_local_physical_signal_transport(config: Any, enabled: bool) -> None:
    if config is None:
        return
    on = bool(enabled) and _line_ok(config)
    cur = getattr(config, "local_physical_signal_transport", None)
    if cur is None:
        if on:
            config.local_physical_signal_transport = UniformSignalMediumConfig(enabled=True)
        # OFF with no config: keep the field absent (previous presets carry no field).
        return
    cur.enabled = on


# ---------------------------------------------------------------------------
# Emission / state
# ---------------------------------------------------------------------------


@dataclass
class PhysicalSignalEmission:
    emission_id: str
    emission_tick: int
    source_x: float
    source_y: float
    band_energies: list[float]
    total_emitted_energy: float
    propagation_speed: float
    attenuation_coefficient: float
    maximum_range: float
    reception_threshold: float
    expiry_tick: int
    provenance: dict[str, Any]
    schema_version: str = EMISSION_SCHEMA
    attenuation_version: str = ATTENUATION_VERSION
    medium_version: str = MEDIUM_VERSION
    evaluated_by: list[str] = field(default_factory=list)  # dedup: receivers already crossed
    received_by: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "emission_id": self.emission_id,
            "schema_version": self.schema_version,
            "emission_tick": int(self.emission_tick),
            "source_x": float(self.source_x),
            "source_y": float(self.source_y),
            "anonymous_band_energies": [float(v) for v in self.band_energies],
            "total_emitted_energy": float(self.total_emitted_energy),
            "propagation_speed": float(self.propagation_speed),
            "attenuation_version": self.attenuation_version,
            "attenuation_coefficient": float(self.attenuation_coefficient),
            "maximum_range": float(self.maximum_range),
            "reception_threshold": float(self.reception_threshold),
            "expiry_tick": int(self.expiry_tick),
            "medium_version": self.medium_version,
            "provenance": dict(self.provenance),
            "evaluated_by": list(self.evaluated_by),
            "received_by": list(self.received_by),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "PhysicalSignalEmission":
        if str(d.get("schema_version") or EMISSION_SCHEMA) != EMISSION_SCHEMA:
            raise ValueError(f"unknown emission schema: {d.get('schema_version')}")
        if str(d.get("attenuation_version") or ATTENUATION_VERSION) != ATTENUATION_VERSION:
            raise ValueError(f"unknown attenuation version: {d.get('attenuation_version')}")
        if str(d.get("medium_version") or MEDIUM_VERSION) != MEDIUM_VERSION:
            raise ValueError(f"unknown medium version: {d.get('medium_version')}")
        return cls(
            emission_id=str(d["emission_id"]),
            emission_tick=int(d["emission_tick"]),
            source_x=float(d["source_x"]),
            source_y=float(d["source_y"]),
            band_energies=[float(v) for v in d.get("anonymous_band_energies") or []],
            total_emitted_energy=float(d.get("total_emitted_energy") or 0.0),
            propagation_speed=float(d["propagation_speed"]),
            attenuation_coefficient=float(d["attenuation_coefficient"]),
            maximum_range=float(d["maximum_range"]),
            reception_threshold=float(d["reception_threshold"]),
            expiry_tick=int(d["expiry_tick"]),
            provenance=dict(d.get("provenance") or {}),
            evaluated_by=[str(x) for x in d.get("evaluated_by") or []],
            received_by=[str(x) for x in d.get("received_by") or []],
        )


def _zero_counters() -> dict[str, int]:
    return {
        "emissions": 0, "endogenous_emissions": 0, "intervention_emissions": 0,
        "experimenter_body_emissions": 0, "capacity_rejected": 0,
        "accepted_receptions": 0, "self_receptions": 0, "foreign_receptions": 0,
        "rejected_beyond_range": 0, "rejected_below_threshold": 0,
        "duplicates_suppressed": 0, "expired": 0, "wrap_receptions": 0,
        "overlap_aggregations": 0, "reprocess_suppressed": 0, "index_fallbacks": 0,
        "direct_delivery_attempts": 0, "steps": 0, "shell_cells_visited": 0,
        "candidate_refs_checked": 0,
    }


@dataclass
class LocalSignalState:
    config: UniformSignalMediumConfig
    n_bands: int = 6
    active: list[PhysicalSignalEmission] = field(default_factory=list)
    alloc_tick: int = -1
    alloc_next: int = 0
    last_processed_tick: int = -1
    auditory: dict[str, dict[str, Any]] = field(default_factory=dict)
    prev_pose: dict[str, list[float]] = field(default_factory=dict)
    pending: list[dict[str, Any]] = field(default_factory=list)
    counters: dict[str, int] = field(default_factory=_zero_counters)
    emission_history: list[dict[str, Any]] = field(default_factory=list)
    reception_history: list[dict[str, Any]] = field(default_factory=list)
    recent_emission_refs: list[str] = field(default_factory=list)
    graph: dict[str, int] = field(default_factory=dict)          # "src->dst" : accepted count
    receivers: list[str] = field(default_factory=list)            # unique receiver body ids
    non_receivers_by_emission: list[dict[str, Any]] = field(default_factory=list)
    distance_samples: list[list[float]] = field(default_factory=list)  # [d, energy, delay, self]
    max_reception_distance: float = 0.0
    last_step: dict[str, Any] = field(default_factory=dict)
    cost_max: dict[str, float] = field(default_factory=lambda: {"step_us": 0.0, "shell_cells": 0, "candidates": 0})


def state_of(world: Any) -> LocalSignalState | None:
    raw = getattr(world, "local_signal_transport", None)
    return raw if isinstance(raw, LocalSignalState) else None


def ensure_local_signal_for_runtime(world: Any, config: Any) -> LocalSignalState | None:
    """Mechanism ON: keep restored state or start fresh. OFF: drop state (never on Tiktaalik)."""
    if world is None:
        return None
    if not local_physical_signal_transport_is_active(config):
        if getattr(world, "local_signal_transport", None) is not None:
            world.local_signal_transport = None
        return None
    cur = state_of(world)
    if cur is not None:
        return cur
    cfg = UniformSignalMediumConfig.from_dict(getattr(config, "local_physical_signal_transport").to_dict())
    validate_medium(cfg)
    osc = getattr(config, "oscillatory_signaling", None)
    n_bands = int(getattr(osc, "n_bands", 6) or 6)
    world.local_signal_transport = LocalSignalState(config=cfg, n_bands=n_bands)
    # Single Acanthostega channel: no OSC_BANDS diffusion field in this preset.
    if getattr(world, "OSC_BANDS", None) is not None:
        world.OSC_BANDS = None
    return world.local_signal_transport


def _bounded_append(rows: list, item: Any, limit: int) -> None:
    rows.append(item)
    if len(rows) > int(limit):
        del rows[: len(rows) - int(limit)]


# ---------------------------------------------------------------------------
# Geometry helpers (pure)
# ---------------------------------------------------------------------------

_OFFSET_CACHE: dict[float, tuple[list[float], list[tuple[int, int]]]] = {}


def offset_table(max_radius: float) -> tuple[list[float], list[tuple[int, int]]]:
    """Integer cell offsets sorted by centre distance, up to max_radius (+margins)."""
    key = round(float(max_radius), 6)
    if key in _OFFSET_CACHE:
        return _OFFSET_CACHE[key]
    lim = float(max_radius) + CELL_MARGIN + 0.5
    r = int(math.ceil(lim))
    rows = []
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            d = math.hypot(dx, dy)
            if d <= lim:
                rows.append((d, dx, dy))
    rows.sort()
    dists = [row[0] for row in rows]
    offs = [(row[1], row[2]) for row in rows]
    _OFFSET_CACHE[key] = (dists, offs)
    return dists, offs


def toroidal_distance(x1: float, y1: float, x2: float, y2: float, width: int, height: int) -> tuple[float, bool]:
    """Shortest toroidal distance (existing planet.topology law) + whether the path wraps."""
    from mechanistic_mind.planet.topology import toroidal_delta

    raw_dx, raw_dy = float(x2) - float(x1), float(y2) - float(y1)
    dx = toroidal_delta(x1, x2, width)
    dy = toroidal_delta(y1, y2, height)
    wraps = abs(dx - raw_dx) > 1e-9 or abs(dy - raw_dy) > 1e-9
    return float(math.hypot(dx, dy)), bool(wraps)


def attenuation(distance: float, k: float) -> float:
    return 1.0 / (1.0 + float(k) * float(distance) * float(distance))


def arrival_delay_for_distance(distance: float, speed: float) -> int:
    return int(max(1, math.ceil(float(distance) / float(speed) - 1e-12)))


def front_radius(n: int, speed: float) -> float:
    return float(max(0, int(n))) * float(speed)


def evaluate_wavefront_crossing_at_point(
    em: PhysicalSignalEmission,
    *,
    x_now: float,
    y_now: float,
    x_prev: float,
    y_prev: float,
    arrival_tick: int,
    width: int,
    height: int,
) -> dict[str, Any] | None:
    """Authoritative mono point-field contribution for one emission at one pose.

    Pure / read-only w.r.t. ``em`` (does not mutate evaluated_by / received_by).
    Shared by body-centre reception accounting and Observer acoustic probe sampling.
    Returns None when the wavefront does not cross the point during this tick.
    """
    A = int(arrival_tick)
    n = A - int(em.emission_tick)
    if n < 1 or A > int(em.expiry_tick):
        return None
    v = float(em.propagation_speed)
    f_prev, f_now = front_radius(n - 1, v), front_radius(n, v)
    d_now, wraps = toroidal_distance(em.source_x, em.source_y, float(x_now), float(y_now), width, height)
    d_prev, _ = toroidal_distance(em.source_x, em.source_y, float(x_prev), float(y_prev), width, height)
    outside_before = d_prev >= f_prev if n == 1 else d_prev > f_prev
    if not (outside_before and d_now <= f_now):
        return None
    att = attenuation(d_now, em.attenuation_coefficient)
    recv = [float(b) * att for b in em.band_energies]
    total = float(sum(recv))
    reason = None
    if d_now > float(em.maximum_range):
        reason = R_BEYOND_RANGE
    elif total < float(em.reception_threshold):
        reason = R_BELOW_THRESHOLD
    return {
        "emission_id": em.emission_id,
        "emission_tick": int(em.emission_tick),
        "arrival_tick": A,
        "propagation_delay": int(n),
        "toroidal_distance": float(d_now),
        "wraps_torus": bool(wraps),
        "attenuation": float(att),
        "emitted_band_energies": [float(b) for b in em.band_energies],
        "received_band_energies": recv,
        "total_received_energy": total,
        "reception_threshold": float(em.reception_threshold),
        "maximum_range": float(em.maximum_range),
        "accepted": reason is None,
        "rejection_reason": reason,
        "source_x": float(em.source_x),
        "source_y": float(em.source_y),
        "point_x": float(x_now),
        "point_y": float(y_now),
        "selection_provenance": em.provenance.get("selection_provenance"),
        "graph_source_label": em.provenance.get("graph_source_label"),
        "source_body_id": em.provenance.get("source_body_id"),
        "medium_version": MEDIUM_VERSION,
        "attenuation_version": ATTENUATION_VERSION,
        "transport_profile": "LOCAL_PHYSICAL_SIGNAL_TRANSPORT_V1",
        "field_authority": "PRE_PHENOTYPE_MONO_POINT_FIELD_V1",
    }


def sample_point_field_passive(
    world: Any,
    *,
    x: float,
    y: float,
    arrival_tick: int | None = None,
    contributor_cap: int = 16,
) -> dict[str, Any]:
    """Passive aggregate mono field at XY for the given arrival tick.

    Does not mutate LPS state, active emissions, or body receivers.
    Aggregates only emissions whose wavefront crosses a *static* point at (x,y) this tick.
    """
    st = state_of(world)
    if st is None:
        return {
            "status": "INACTIVE",
            "anonymous_band_energies": [],
            "total_received_energy": 0.0,
            "contributors": [],
            "contributor_count_total": 0,
            "contributor_count_retained": 0,
            "contributor_count_truncated": 0,
            "active_signals_examined": 0,
            "accepted": False,
        }
    height, width = _shape(world)
    from mechanistic_mind.planet.topology import wrap_coord

    px = float(wrap_coord(float(x), width))
    py = float(wrap_coord(float(y), height))
    A = int(st.last_processed_tick if arrival_tick is None else arrival_tick)
    n_bands = int(st.n_bands)
    bands = [0.0] * n_bands
    contributors: list[dict[str, Any]] = []
    examined = 0
    accepted_n = 0
    for em in sorted(st.active, key=lambda e: e.emission_id):
        examined += 1
        row = evaluate_wavefront_crossing_at_point(
            em,
            x_now=px,
            y_now=py,
            x_prev=px,
            y_prev=py,
            arrival_tick=A,
            width=width,
            height=height,
        )
        if row is None:
            continue
        contributors.append(row)
        if row.get("accepted"):
            accepted_n += 1
            recv = row["received_band_energies"]
            for i in range(min(n_bands, len(recv))):
                bands[i] += float(recv[i])
    # Deterministic contributor order already by emission_id; bound retained list.
    total_c = len(contributors)
    cap = max(0, int(contributor_cap))
    retained = contributors[:cap] if cap else []
    truncated = max(0, total_c - len(retained))
    return {
        "status": "SAMPLED",
        "arrival_tick": A,
        "point_x": px,
        "point_y": py,
        "anonymous_band_energies": bands,
        "total_received_energy": float(sum(bands)),
        "contributors": retained,
        "contributor_count_total": total_c,
        "contributor_count_retained": len(retained),
        "contributor_count_truncated": truncated,
        "accepted_contributor_count": accepted_n,
        "active_signals_examined": examined,
        "n_bands": n_bands,
        "transport_profile": "LOCAL_PHYSICAL_SIGNAL_TRANSPORT_V1",
        "transport_medium": MEDIUM_VERSION,
        "field_authority": "PRE_PHENOTYPE_MONO_POINT_FIELD_V1",
        "sampling_mode": "POINT_MONO_V1",
    }


def shell_cells(emission: PhysicalSignalEmission, n: int, width: int, height: int) -> list[tuple[int, int]]:
    """Wrapped cells that can hold a receiver crossed by the front between ticks te+n-1 and te+n."""
    from mechanistic_mind.planet.topology import wrap_coord

    v = float(emission.propagation_speed)
    hi = min(front_radius(n, v), float(emission.maximum_range) + v)
    lo = front_radius(n - 1, v) - MAX_RECEIVER_STEP
    dists, offs = offset_table(float(emission.maximum_range) + v)
    a = bisect.bisect_left(dists, lo - CELL_MARGIN)
    b = bisect.bisect_right(dists, hi + CELL_MARGIN)
    sx = int(math.floor(float(emission.source_x)))
    sy = int(math.floor(float(emission.source_y)))
    seen: set[tuple[int, int]] = set()
    out: list[tuple[int, int]] = []
    for dx, dy in offs[a:b]:
        c = (int(wrap_coord(sx + dx, width)), int(wrap_coord(sy + dy, height)))
        if c not in seen:  # small worlds: two offsets may wrap onto one cell
            seen.add(c)
            out.append(c)
    return out


def _shape(world: Any) -> tuple[int, int]:
    grid = getattr(world, "T", None)
    if grid is None:
        return 32, 32
    return int(grid.shape[0]), int(grid.shape[1])


def _body_lookup(world: Any, bodies: list[tuple[str, Any]], width: int, height: int, counters: dict[str, int]):
    """cell -> body ids. Uses the multi-content spatial index BODY refs when they match the
    current poses (O(bodies) freshness check once per tick); otherwise a transient bucket."""
    from mechanistic_mind.physical_system.spatial_contents import KIND_BODY, _index, world_cell

    ids = {bid for bid, _ in bodies}
    idx = _index(world)
    if idx is not None and not bool(getattr(idx, "dirty", False)):
        fresh = True
        for bid, body in bodies:
            ref = idx.by_entity.get((KIND_BODY, bid))
            if ref is None or (ref.cell_x, ref.cell_y) != world_cell(body.x, body.y, width=width, height=height):
                fresh = False
                break
        if fresh:
            def lookup(cell: tuple[int, int]) -> list[str]:
                return [r.entity_id for r in idx.by_cell.get(cell, ()) if r.entity_kind == KIND_BODY and r.entity_id in ids]
            return lookup, "MULTI_CONTENT_SPATIAL_INDEX"
    counters["index_fallbacks"] = int(counters.get("index_fallbacks", 0)) + 1
    bucket: dict[tuple[int, int], list[str]] = {}
    for bid, body in bodies:
        bucket.setdefault(world_cell(body.x, body.y, width=width, height=height), []).append(bid)
    return (lambda cell: list(bucket.get(cell, ()))), "TRANSIENT_BODY_BUCKET_FALLBACK"


def _alloc_id(state: LocalSignalState, te: int) -> str:
    if int(state.alloc_tick) != int(te):
        state.alloc_tick = int(te)
        state.alloc_next = 0
    seq = int(state.alloc_next)
    state.alloc_next = seq + 1
    return f"signal-emission-{int(te):09d}-{seq:04d}"


def band_profile(frequency: float, amplitude: float, osc_cfg: Any, n_bands: int) -> list[float]:
    from mechanistic_mind.physical_system.oscillatory_signaling import band_response

    width = float(getattr(osc_cfg, "band_width", 0.22) or 0.22)
    amp = float(max(0.0, min(float(getattr(osc_cfg, "source_cap", 1.0) or 1.0), float(amplitude))))
    w = band_response(float(frequency), n_bands=int(n_bands), width=width)
    return [float(amp * float(x)) for x in w]


def _create_emission(
    state: LocalSignalState,
    *,
    te: int,
    x: float,
    y: float,
    bands: list[float],
    provenance: dict[str, Any],
    width: int,
    height: int,
) -> dict[str, Any]:
    from mechanistic_mind.planet.topology import wrap_coord

    cfg = state.config
    wx, wy = float(wrap_coord(float(x), width)), float(wrap_coord(float(y), height))
    if len(state.active) >= int(cfg.max_active_emissions):
        state.counters["capacity_rejected"] += 1
        return {"receipt_kind": EMISSION_RECEIPT, "status": "REJECTED", "rejection_reason": R_CAPACITY,
                "emission_tick": int(te), **EFFECT_FLAGS}
    eid = _alloc_id(state, te)
    total = float(sum(bands))
    em = PhysicalSignalEmission(
        emission_id=eid, emission_tick=int(te), source_x=wx, source_y=wy,
        band_energies=[float(b) for b in bands], total_emitted_energy=total,
        propagation_speed=float(cfg.propagation_speed),
        attenuation_coefficient=float(cfg.attenuation_coefficient),
        maximum_range=float(cfg.maximum_range),
        reception_threshold=float(cfg.reception_threshold),
        expiry_tick=int(te) + int(cfg.max_arrival_delay),
        provenance=dict(provenance),
    )
    state.active.append(em)
    kind = str(provenance.get("selection_provenance"))
    state.counters["emissions"] += 1
    if kind == PROV_ENDOGENOUS:
        state.counters["endogenous_emissions"] += 1
    elif kind == PROV_EXPERIMENTER_BODY:
        state.counters["experimenter_body_emissions"] += 1
        state.counters["intervention_emissions"] += 1
    elif kind == PROV_PHYSICAL_CONTACT:
        # Lazily created key: presets without contact acoustics keep their exact counter set.
        state.counters["physical_contact_emissions"] = int(state.counters.get("physical_contact_emissions", 0)) + 1
    else:
        state.counters["intervention_emissions"] += 1
    receipt = {
        "receipt_kind": EMISSION_RECEIPT,
        "status": "EMITTED",
        "emission_id": eid,
        "schema_version": EMISSION_SCHEMA,
        "emission_tick": int(te),
        "physical_origin": {"x": wx, "y": wy, "cell": [int(math.floor(wx)), int(math.floor(wy))]},
        "anonymous_band_energies": [float(b) for b in bands],
        "total_emitted_energy": total,
        "propagation": {
            "medium_version": MEDIUM_VERSION,
            "propagation_law": PROPAGATION_LAW,
            "propagation_speed": float(cfg.propagation_speed),
            "attenuation_version": ATTENUATION_VERSION,
            "attenuation_coefficient": float(cfg.attenuation_coefficient),
            "maximum_range": float(cfg.maximum_range),
            "reception_threshold": float(cfg.reception_threshold),
            "max_arrival_delay": int(cfg.max_arrival_delay),
        },
        "expiry_tick": int(em.expiry_tick),
        "source_body_id": provenance.get("source_body_id"),  # researcher-only
        "motor_provenance": provenance.get("motor_provenance"),
        "selection_provenance": kind,
        "endogenous": kind == PROV_ENDOGENOUS,
        **EFFECT_FLAGS,
    }
    if provenance.get("cause_receipt_ref") is not None:  # only physical-contact emissions carry a cause
        receipt["cause_receipt_ref"] = provenance.get("cause_receipt_ref")
        receipt["source_body_pair"] = provenance.get("source_body_pair")
    _bounded_append(state.emission_history, receipt, cfg.history_limit)
    _bounded_append(state.recent_emission_refs, eid, cfg.history_limit)
    return receipt


def queue_researcher_emission(
    world: Any,
    config: Any,
    *,
    x: float,
    y: float,
    frequency: float | None = None,
    amplitude: float | None = None,
    band_energies: list[float] | None = None,
    researcher_id: str = "researcher",
) -> dict[str, Any]:
    """Researcher calibration emission (INTERVENTION_SETUP). It becomes a normal physical
    emission at the next end-of-tick step and reaches bodies only by physical reception."""
    st = state_of(world)
    if st is None or not local_physical_signal_transport_is_active(config):
        return {"status": "REJECTED", "rejection_reason": "MECHANISM_INACTIVE", **EFFECT_FLAGS}
    try:
        fx, fy = float(x), float(y)
    except (TypeError, ValueError):
        return {"status": "REJECTED", "rejection_reason": "NON_FINITE_COORDINATE", **EFFECT_FLAGS}
    if not (math.isfinite(fx) and math.isfinite(fy)):
        return {"status": "REJECTED", "rejection_reason": "NON_FINITE_COORDINATE", **EFFECT_FLAGS}
    if band_energies is not None:
        bands = [float(b) for b in band_energies]
        if len(bands) != int(st.n_bands) or any((not math.isfinite(b)) or b < 0.0 for b in bands):
            return {"status": "REJECTED", "rejection_reason": "INVALID_BAND_ENERGIES", **EFFECT_FLAGS}
    else:
        f = 0.5 if frequency is None else float(frequency)
        a = 0.5 if amplitude is None else float(amplitude)
        if not (math.isfinite(f) and math.isfinite(a)) or a < 0.0:
            return {"status": "REJECTED", "rejection_reason": "INVALID_EMISSION_PARAMETERS", **EFFECT_FLAGS}
        bands = band_profile(f, a, getattr(config, "oscillatory_signaling", None), st.n_bands)
    req = {"x": fx, "y": fy, "bands": bands, "researcher_id": str(researcher_id)}
    st.pending.append(req)
    del st.pending[:-16]
    return {"status": "QUEUED", "selection_provenance": PROV_INTERVENTION, "x": fx, "y": fy,
            "anonymous_band_energies": bands, "direct_cognition_delivery": False, **EFFECT_FLAGS}


def emit_local_physical_signal(
    world: Any,
    *,
    emission_tick: int,
    x: float,
    y: float,
    band_energies: list[float],
    provenance: dict[str, Any],
) -> dict[str, Any]:
    """Generic physical entry point (used by physical_contact_acoustic_emission).

    Creates an ordinary PhysicalSignalEmission for emission tick te at a physical origin; the
    emission then follows exactly the same transport law (finite delay, attenuation, range,
    threshold, pose-at-arrival reception) in the next step_end_of_tick for arrival te+1.. .
    Must be called before step_end_of_tick(tick_now=te+1). Never writes auditory state."""
    st = state_of(world)
    if st is None:
        return {"status": "REJECTED", "rejection_reason": "MECHANISM_INACTIVE", **EFFECT_FLAGS}
    te = int(emission_tick)
    if te < int(st.last_processed_tick):
        return {"status": "REJECTED", "rejection_reason": "RETROACTIVE_EMISSION", **EFFECT_FLAGS}
    bands = [float(b) for b in band_energies]
    if len(bands) != int(st.n_bands) or any((not math.isfinite(b)) or b < 0.0 for b in bands):
        return {"status": "REJECTED", "rejection_reason": "INVALID_BAND_ENERGIES", **EFFECT_FLAGS}
    if not (math.isfinite(float(x)) and math.isfinite(float(y))):
        return {"status": "REJECTED", "rejection_reason": "NON_FINITE_COORDINATE", **EFFECT_FLAGS}
    height, width = _shape(world)
    return _create_emission(st, te=te, x=float(x), y=float(y), bands=bands,
                            provenance=dict(provenance), width=width, height=height)


def bind_body_ids(bodies: list[tuple[str, Any]]) -> None:
    for bid, body in bodies:
        try:
            body._lps_body_id = str(bid)  # non-serialized runtime link for the osc sensor seam
        except Exception:
            pass


# ---------------------------------------------------------------------------
# One end-of-tick step: emissions (te = tick_now - 1) -> receptions for arrival tick tick_now
# ---------------------------------------------------------------------------


def step_end_of_tick(
    world: Any,
    config: Any,
    bodies: list[tuple[str, Any]],
    *,
    tick_now: int,
    articulated_head: bool = False,
    intervention_body_ids: tuple[str, ...] | list[str] = (),
    apply_work_cost: bool = True,
) -> dict[str, Any]:
    """Runs after every body finished tick te (poses final). Deterministic, process-order free:
    emissions sorted by body id, receptions by emission id then body id."""
    import time

    from mechanistic_mind.physical_system.oscillatory_signaling import (
        clamp_amp_u,
        clamp_freq_u,
        frequency_from_control,
        receptor_world_positions,
    )

    st = state_of(world)
    if st is None:
        return {"enabled": False}
    t0 = time.perf_counter()
    cfg = st.config
    osc = getattr(config, "oscillatory_signaling", None)
    A = int(tick_now)
    te = A - 1
    height, width = _shape(world)
    bodies = sorted(((str(b), body) for b, body in bodies), key=lambda r: r[0])
    bind_body_ids(bodies)
    if A <= int(st.last_processed_tick):
        st.counters["reprocess_suppressed"] += 1
        return {"enabled": True, "status": "ALREADY_PROCESSED", "tick": A}
    if getattr(world, "OSC_BANDS", None) is not None:
        world.OSC_BANDS = None  # single channel: no diffusion field in this preset
    body_map = {bid: body for bid, body in bodies}
    emissions: list[dict[str, Any]] = []
    # 1) endogenous / experimenter-body emissions from the unchanged OSC motor state
    osc_on = bool(osc is not None and getattr(osc, "enabled", False) and getattr(osc, "emission_enabled", True))
    for bid, body in bodies:
        rem = int(getattr(body, "osc_emit_remaining", 0) or 0)
        if rem <= 0 or not osc_on:
            body.osc_emit_active = 0.0
            if rem < 0:
                body.osc_emit_remaining = 0
            continue
        freq_u = clamp_freq_u(float(getattr(body, "osc_freq_u", 0.5)))
        amp_u = clamp_amp_u(float(getattr(body, "osc_amp_u", 0.5)))
        freq = frequency_from_control(freq_u, osc)
        bands = band_profile(freq, amp_u, osc, st.n_bands)
        kind = PROV_EXPERIMENTER_BODY if bid in set(intervention_body_ids) else PROV_ENDOGENOUS
        rec = _create_emission(
            st, te=te, x=float(body.x), y=float(body.y), bands=bands, width=width, height=height,
            provenance={
                "selection_provenance": kind,
                "source_body_id": bid,
                "motor_provenance": {
                    "command_family": "OSC_EMIT", "emit_remaining_before": rem,
                    "osc_freq_u": freq_u, "osc_amp_u": amp_u,
                },
            },
        )
        emissions.append(rec)
        if apply_work_cost and float(getattr(osc, "work_cost_per_amp_tick", 0.0) or 0.0) > 0.0:
            cost = float(osc.work_cost_per_amp_tick) * float(amp_u)
            res = float(getattr(body, "mechanical_work_reservoir", 0.0) or 0.0)
            body.mechanical_work_reservoir = res - float(min(res, cost))
        body.osc_emit_remaining = rem - 1  # exactly one emission and one decrement per tick
        body.osc_emit_active = 1.0 if body.osc_emit_remaining > 0 else 0.0
        body.osc_frequency = freq
        body.osc_amplitude = amp_u
    # 2) researcher calibration emissions (INTERVENTION_SETUP)
    for req in list(st.pending):
        emissions.append(_create_emission(
            st, te=te, x=float(req["x"]), y=float(req["y"]), bands=list(req["bands"]),
            width=width, height=height,
            provenance={"selection_provenance": PROV_INTERVENTION, "source_body_id": None,
                        "researcher_id": req.get("researcher_id"), "motor_provenance": None},
        ))
    st.pending = []
    # 3) receptions for arrival tick A (receiver pose at arrival; wavefront crossing test)
    lookup, index_source = _body_lookup(world, bodies, width, height, st.counters)
    aud: dict[str, dict[str, Any]] = {}
    receptions: list[dict[str, Any]] = []
    shell_n = cand_n = 0
    seq = 0
    for em in sorted(st.active, key=lambda e: e.emission_id):
        n = A - int(em.emission_tick)
        if n < 1 or A > int(em.expiry_tick):
            continue
        v = float(em.propagation_speed)
        f_prev, f_now = front_radius(n - 1, v), front_radius(n, v)
        cells = shell_cells(em, n, width, height)
        shell_n += len(cells)
        seen: set[str] = set()
        cand: list[str] = []
        for c in cells:
            for bid in lookup(c):
                if bid not in seen:
                    seen.add(bid)
                    cand.append(bid)
        cand.sort()
        cand_n += len(cand)
        done = set(em.evaluated_by)
        for bid in cand:
            body = body_map[bid]
            prev = st.prev_pose.get(bid) or [float(body.x), float(body.y)]
            crossed = evaluate_wavefront_crossing_at_point(
                em,
                x_now=float(body.x),
                y_now=float(body.y),
                x_prev=float(prev[0]),
                y_prev=float(prev[1]),
                arrival_tick=A,
                width=width,
                height=height,
            )
            if crossed is None:
                continue  # not crossed by the wavefront during this tick: ordinary absence
            if bid in done:
                st.counters["duplicates_suppressed"] += 1
                continue
            em.evaluated_by.append(bid)
            done.add(bid)
            src_bid = em.provenance.get("source_body_id")
            is_self = bool(src_bid is not None and src_bid == bid)
            d_now = float(crossed["toroidal_distance"])
            wraps = bool(crossed["wraps_torus"])
            att = float(crossed["attenuation"])
            recv = list(crossed["received_band_energies"])
            total = float(crossed["total_received_energy"])
            reason = crossed.get("rejection_reason")
            n = int(crossed["propagation_delay"])
            rid = f"signal-reception-{A:09d}-{seq:04d}"
            seq += 1
            receipt = {
                "receipt_kind": RECEPTION_RECEIPT,
                "reception_id": rid,
                "emission_id": em.emission_id,
                "emission_tick": int(em.emission_tick),
                "arrival_tick": A,
                "receiver_body_id": bid,
                "source_body_id": src_bid,  # researcher-only
                "source_position_at_emission": [em.source_x, em.source_y],
                "receiver_position_at_reception": [float(body.x), float(body.y)],
                "receiver_previous_position": [float(prev[0]), float(prev[1])],
                "toroidal_distance": d_now,
                "wraps_torus": wraps,
                "propagation_delay": n,
                "emitted_band_energies": list(em.band_energies),
                "attenuation": att,
                "received_band_energies": recv,
                "total_received_energy": total,
                "reception_threshold": float(em.reception_threshold),
                "maximum_range": float(em.maximum_range),
                "accepted": reason is None,
                "rejection_reason": reason,
                "self_reception": is_self,
                "selection_provenance": em.provenance.get("selection_provenance"),
                "medium_version": MEDIUM_VERSION,
                "attenuation_version": ATTENUATION_VERSION,
                "receiver_policy": RECEIVER_POLICY,
                "index_source": index_source,
                "agent_visible_fields": list(AGENT_VISIBLE_FIELDS),
                "researcher_only_fields": list(RESEARCHER_ONLY_FIELDS),
                **EFFECT_FLAGS,
            }
            receptions.append(receipt)
            _bounded_append(st.reception_history, receipt, cfg.history_limit)
            if reason is not None:
                st.counters["rejected_beyond_range" if reason == R_BEYOND_RANGE else "rejected_below_threshold"] += 1
                continue
            em.received_by.append(bid)
            (lx, ly), (rx, ry) = receptor_world_positions(
                body, articulated_head=bool(articulated_head),
                offset=float(getattr(osc, "receptor_offset", 0.55) or 0.55),
            )
            dl, _ = toroidal_distance(em.source_x, em.source_y, lx, ly, width, height)
            dr, _ = toroidal_distance(em.source_x, em.source_y, rx, ry, width, height)
            al, ar = attenuation(dl, em.attenuation_coefficient), attenuation(dr, em.attenuation_coefficient)
            slot = aud.setdefault(bid, {"tick": A, "left": [0.0] * st.n_bands, "right": [0.0] * st.n_bands, "n": 0})
            for i, b in enumerate(em.band_energies[: st.n_bands]):
                slot["left"][i] += float(b) * al
                slot["right"][i] += float(b) * ar
            slot["n"] += 1
            st.counters["accepted_receptions"] += 1
            st.counters["self_receptions" if is_self else "foreign_receptions"] += 1
            if wraps:
                st.counters["wrap_receptions"] += 1
            src_label = src_bid if src_bid is not None else (em.provenance.get("graph_source_label") or "INTERVENTION")
            key = f"{src_label}->{bid}"
            st.graph[key] = int(st.graph.get(key, 0)) + 1
            if bid not in st.receivers:
                st.receivers.append(bid)
            st.max_reception_distance = max(float(st.max_reception_distance), float(d_now))
            _bounded_append(st.distance_samples, [d_now, total, float(n), 1.0 if is_self else 0.0], 256)
    st.counters["overlap_aggregations"] += sum(1 for s in aud.values() if int(s.get("n", 0)) >= 2)
    st.auditory = aud
    # 4) expiry (bounded active set) + diagnostic non-receivers (researcher-only)
    keep: list[PhysicalSignalEmission] = []
    expired = 0
    for em in st.active:
        if A >= int(em.expiry_tick):
            expired += 1
            missing = sorted(set(body_map) - set(em.received_by))
            _bounded_append(st.non_receivers_by_emission, {
                "emission_id": em.emission_id, "source_body_id": em.provenance.get("source_body_id"),
                "receivers": list(em.received_by), "non_receivers": missing,
            }, cfg.history_limit)
        else:
            keep.append(em)
    st.active = keep
    st.counters["expired"] += expired
    # 5) poses for the next crossing test
    st.prev_pose = {bid: [float(body.x), float(body.y)] for bid, body in bodies}
    st.last_processed_tick = A
    st.counters["steps"] += 1
    st.counters["shell_cells_visited"] += shell_n
    st.counters["candidate_refs_checked"] += cand_n
    us = (time.perf_counter() - t0) * 1e6
    st.cost_max["step_us"] = max(float(st.cost_max.get("step_us", 0.0)), us)
    st.cost_max["shell_cells"] = max(int(st.cost_max.get("shell_cells", 0)), shell_n)
    st.cost_max["candidates"] = max(int(st.cost_max.get("candidates", 0)), cand_n)
    st.last_step = {
        "event": EVENT_STEP, "tick": te, "arrival_tick": A,
        "emissions": [_compact(r) for r in emissions],
        "receptions": [_compact(r) for r in receptions],
        "active_after": len(st.active), "expired": expired, "index_source": index_source,
        "shell_cells_visited": shell_n, "candidates_checked": cand_n, "step_us": us,
    }
    world.last_local_signal_step = st.last_step
    return {"enabled": True, "status": "PROCESSED", **st.last_step}


_COMPACT_KEYS = (
    "receipt_kind", "status", "emission_id", "reception_id", "emission_tick", "arrival_tick",
    "receiver_body_id", "source_body_id", "toroidal_distance", "propagation_delay",
    "total_emitted_energy", "total_received_energy", "accepted", "rejection_reason",
    "self_reception", "wraps_torus", "selection_provenance", "physical_origin",
    "source_position_at_emission", "receiver_position_at_reception", "attenuation",
    "anonymous_band_energies", "received_band_energies",
)


def _compact(receipt: dict[str, Any]) -> dict[str, Any]:
    return {k: receipt[k] for k in _COMPACT_KEYS if k in receipt}


def auditory_fragments(world: Any, body: Any) -> dict[str, float] | None:
    """Anonymous osc_l_k / osc_r_k from physically received energy (None -> legacy path).
    Only summed band energy per receptor, clipped by the existing osc sensor policy."""
    st = state_of(world)
    if st is None:
        return None
    n = int(st.n_bands)
    bid = getattr(body, "_lps_body_id", None)
    entry = st.auditory.get(str(bid)) if bid is not None else None
    if entry is not None and int(entry.get("tick", -1)) != int(getattr(world, "tick", -2)):
        entry = None
    scale = max(1e-9, float(st.config.sensor_scale))
    left = list(entry.get("left") or [0.0] * n) if entry else [0.0] * n
    right = list(entry.get("right") or [0.0] * n) if entry else [0.0] * n
    out: dict[str, float] = {}
    for i in range(n):
        out[f"osc_l_{i}"] = float(max(0.0, min(1.0, float(left[i]) / scale)))
        out[f"osc_r_{i}"] = float(max(0.0, min(1.0, float(right[i]) / scale)))
    return out


# ---------------------------------------------------------------------------
# Snapshot / restore / copy
# ---------------------------------------------------------------------------


def serialize_state(state: LocalSignalState | None) -> dict[str, Any] | None:
    if state is None:
        return None
    return {
        "schema_version": STATE_SCHEMA,
        "config": state.config.to_dict(),
        "n_bands": int(state.n_bands),
        "active_emissions": [e.to_dict() for e in state.active],
        "allocator": {"tick": int(state.alloc_tick), "next_sequence": int(state.alloc_next)},
        "last_processed_tick": int(state.last_processed_tick),
        "auditory": {k: {"tick": int(v.get("tick", -1)), "left": list(v.get("left") or []),
                         "right": list(v.get("right") or []), "n": int(v.get("n", 0))}
                     for k, v in sorted(state.auditory.items())},
        "prev_pose": {k: list(v) for k, v in sorted(state.prev_pose.items())},
        "pending": [dict(p) for p in state.pending],
        "counters": dict(state.counters),
        "emission_history": list(state.emission_history),
        "reception_history": list(state.reception_history),
        "recent_emission_refs": list(state.recent_emission_refs),
        "graph": dict(sorted(state.graph.items())),
        "receivers": list(state.receivers),
        "non_receivers_by_emission": list(state.non_receivers_by_emission),
        "distance_samples": [list(r) for r in state.distance_samples],
        "max_reception_distance": float(state.max_reception_distance),
        "cost_max": dict(state.cost_max),
    }


def restore_state(world: Any, data: dict[str, Any] | None, config: Any) -> LocalSignalState | None:
    """Restore authoritative transport state. Missing data or mechanism OFF -> no state."""
    if not local_physical_signal_transport_is_active(config):
        world.local_signal_transport = None
        return None
    if not isinstance(data, dict) or not data:
        world.local_signal_transport = None
        return ensure_local_signal_for_runtime(world, config)
    if str(data.get("schema_version")) != STATE_SCHEMA:
        raise ValueError(f"unknown local signal state schema: {data.get('schema_version')}")
    saved_cfg = UniformSignalMediumConfig.from_dict(data.get("config") or {})  # rejects unknown versions
    cfg = UniformSignalMediumConfig.from_dict(getattr(config, "local_physical_signal_transport").to_dict())
    validate_medium(cfg)
    if saved_cfg.to_dict() != cfg.to_dict():
        raise ValueError("local signal medium parameters differ from the runtime config")
    alloc = data.get("allocator") or {}
    st = LocalSignalState(
        config=cfg,
        n_bands=int(data.get("n_bands", 6)),
        active=[PhysicalSignalEmission.from_dict(e) for e in data.get("active_emissions") or []],
        alloc_tick=int(alloc.get("tick", -1)),
        alloc_next=int(alloc.get("next_sequence", 0)),
        last_processed_tick=int(data.get("last_processed_tick", -1)),
        auditory={str(k): dict(v) for k, v in (data.get("auditory") or {}).items()},
        prev_pose={str(k): [float(v[0]), float(v[1])] for k, v in (data.get("prev_pose") or {}).items()},
        pending=[dict(p) for p in data.get("pending") or []],
        counters={**_zero_counters(), **{k: int(v) for k, v in (data.get("counters") or {}).items()}},
        emission_history=list(data.get("emission_history") or []),
        reception_history=list(data.get("reception_history") or []),
        recent_emission_refs=list(data.get("recent_emission_refs") or []),
        graph={str(k): int(v) for k, v in (data.get("graph") or {}).items()},
        receivers=[str(x) for x in data.get("receivers") or []],
        non_receivers_by_emission=list(data.get("non_receivers_by_emission") or []),
        distance_samples=[list(r) for r in data.get("distance_samples") or []],
        max_reception_distance=float(data.get("max_reception_distance") or 0.0),
        cost_max=dict(data.get("cost_max") or {"step_us": 0.0, "shell_cells": 0, "candidates": 0}),
    )
    world.local_signal_transport = st
    world.OSC_BANDS = None
    return st


def copy_state(state: LocalSignalState | None) -> LocalSignalState | None:
    if state is None:
        return None
    data = serialize_state(state)
    st = LocalSignalState(config=UniformSignalMediumConfig.from_dict(data["config"]), n_bands=state.n_bands)
    st.active = [PhysicalSignalEmission.from_dict(e) for e in data["active_emissions"]]
    st.alloc_tick, st.alloc_next = state.alloc_tick, state.alloc_next
    st.last_processed_tick = state.last_processed_tick
    st.auditory = {k: dict(v) for k, v in data["auditory"].items()}
    st.prev_pose = {k: list(v) for k, v in data["prev_pose"].items()}
    st.pending = [dict(p) for p in data["pending"]]
    st.counters = dict(state.counters)
    st.emission_history = list(state.emission_history)
    st.reception_history = list(state.reception_history)
    st.recent_emission_refs = list(state.recent_emission_refs)
    st.graph = dict(state.graph)
    st.receivers = list(state.receivers)
    st.non_receivers_by_emission = list(state.non_receivers_by_emission)
    st.distance_samples = [list(r) for r in state.distance_samples]
    st.max_reception_distance = state.max_reception_distance
    st.cost_max = dict(state.cost_max)
    return st


# ---------------------------------------------------------------------------
# Researcher views (never cognition)
# ---------------------------------------------------------------------------


def researcher_summary(world: Any) -> dict[str, Any] | None:
    st = state_of(world)
    if st is None:
        return None
    c = st.counters
    return {
        "mechanism": MECHANISM_ID,
        "medium": st.config.to_dict(),
        "active_emissions": len(st.active),
        "counters": dict(c),
        "communication_graph": dict(sorted(st.graph.items())),
        "receivers": list(st.receivers),
        "max_reception_distance": float(st.max_reception_distance),
        "distance_samples": [list(r) for r in st.distance_samples[-64:]],
        "non_receivers_by_emission": list(st.non_receivers_by_emission[-16:]),
        # Accepted reception beyond maximum_range would be global/unbounded delivery (law violation).
        "global_delivery_observed": bool(float(st.max_reception_distance) > float(st.config.maximum_range) + 1e-9),
        "labels": list(OBSERVER_LABELS),
        **EFFECT_FLAGS,
    }


def observer_overlay(world: Any) -> dict[str, Any] | None:
    """Visualisation of authoritative emission state only (origin, analytic front, range ring)."""
    st = state_of(world)
    if st is None:
        return None
    tick = int(getattr(world, "tick", 0) or 0)
    rows = []
    for em in sorted(st.active, key=lambda e: e.emission_id):
        n = tick - int(em.emission_tick)
        rows.append({
            "emission_id": em.emission_id,
            "origin": [em.source_x, em.source_y],
            "front_radius": min(front_radius(max(0, n), em.propagation_speed), float(em.maximum_range)),
            "maximum_range": float(em.maximum_range),
            "total_emitted_energy": float(em.total_emitted_energy),
            "anonymous_band_energies": list(em.band_energies),
            "status": "ACTIVE" if tick <= int(em.expiry_tick) else "EXPIRED",
            "receivers": list(em.received_by),
            "attenuation_coefficient": float(em.attenuation_coefficient),
            "selection_provenance": em.provenance.get("selection_provenance"),
        })
    last = st.last_step or {}
    return {
        "active": rows,
        "active_count": len(rows),
        "expired_total": int(st.counters.get("expired", 0)),
        "emissions_total": int(st.counters.get("emissions", 0)),
        "accepted_receptions_total": int(st.counters.get("accepted_receptions", 0)),
        "last_receptions": [r for r in (last.get("receptions") or []) if r.get("accepted")],
        "medium": st.config.to_dict(),
        "labels": list(OBSERVER_LABELS),
        **EFFECT_FLAGS,
    }


def catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "config_path": "local_physical_signal_transport.enabled",
        "enabled": bool(enabled),
        "scientific_status": "IMPLEMENTED",
        "promotion_class": "EXPERIMENTAL",
        "description": (
            "Acanthostega single signal channel: OSC_EMIT becomes a local physical emission in "
            "UNIFORM_SIGNAL_MEDIUM_V1 (finite propagation speed, 1/(1+k d^2) attenuation, bounded "
            "range, reception threshold). Receivers get only summed anonymous band energy on the "
            "existing osc_l_*/osc_r_* receptors. No source identity, distance, bearing or message."
        ),
    }
