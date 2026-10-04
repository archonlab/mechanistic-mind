"""Acanthostega FREE ResourceObject↔ResourceObject IMPACT acoustic emission.

ONLY in ACANTHOSTEGA_PHASE_B_OBJECT_OBJECT_IMPACT_ACOUSTICS. Connects measured
object/object contact RESPONSE (isolated-pair impulse + pairwise KE dissipation)
to the existing Local Physical Signal Transport. Does NOT duplicate transport.
Does NOT change OO impulse physics.

Branch merge (LOCKED): starts from acanthostega_object_object_impulse_config(),
then enables this OO impact acoustic mechanism. Keeps OSC transport + Audio B +
B/O impact acoustics + OO contact/impulse.

Call chain (LOCKED — single LPS step_end_of_tick after all emitters):

    OSC_EMIT
    | process_contact_pairs (B/B Audio B)
    | process_body_object_impact_acoustics
    | process_resource_object_pair_impact_acoustics   # THIS MODULE
    → single step_end_of_tick

Tick order (LOCKED):

    B/O contact → B/O impulse → B/O impact acoustics
    → OO contact → OO impulse → OO impact acoustics   # NEW
    → LPS step_end_of_tick (once)

    OO response receipt (isolated_pair + impulse_transferred + APPROACHING
                         + |j| > epsilon + E_dissipated > energy_epsilon)
    -> E_dissipated = receipt.dissipated_energy
       (or max(0, ke_pair_pre - ke_pair_post))
    -> E_raw = acoustic_coupling * E_dissipated
    -> E_emit = clamp(E_raw, 0, max_acoustic_energy)
    -> UNIFORM_BROADBAND_V1 (import broadband_bands from Audio B)
    -> local_physical_signal_transport.emit_local_physical_signal
    -> delayed, attenuated anonymous osc_l_* / osc_r_* at body listeners

Silent: contact-fact-only, resting, separating, correction-only, unresolved
multi-contact, near-elastic zero dissipation, below impulse/energy thresholds.
mechanical_energy_withdrawn = false; GLOBAL_ENERGY_CONSERVATION_CLAIMED = NO.
No material timbre. Objects are not receivers.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from mechanistic_mind.physical_system.body_resource_object_impact_acoustic_emission import (
    dissipated_pairwise_ke,
)
from mechanistic_mind.physical_system.physical_contact_acoustic_emission import (
    BAND_PROFILE,
    broadband_bands,
    toroidal_midpoint,
)

MECHANISM_ID = "resource_object_pair_impact_acoustic_emission"
PROFILE_VERSION = "RESOURCE_OBJECT_PAIR_IMPACT_ACOUSTIC_PROFILE_V1"
STATE_SCHEMA = "RESOURCE_OBJECT_PAIR_IMPACT_ACOUSTIC_STATE_V1"
ENERGY_LAW = "DISSIPATED_PAIRWISE_KE_TO_ACOUSTIC_ENERGY_V1"
BAND_PROFILE_NAME = BAND_PROFILE  # UNIFORM_BROADBAND_V1 (imported, not copied)
POSITION_DERIVATION = "CONTACT_POINT_FROM_OO_CONTACT_FACT_MEASUREMENT_V1"
POSITION_FALLBACK = "TOROIDAL_MIDPOINT_OF_OBJECT_CENTRES_V1"
EMISSION_RECEIPT = "RESOURCE_OBJECT_PAIR_IMPACT_ACOUSTIC_EMISSION"
MEASUREMENT_RECEIPT = "RESOURCE_OBJECT_PAIR_IMPACT_ACOUSTIC_MEASUREMENT"
EVENT_STEP = "RESOURCE_OBJECT_PAIR_IMPACT_ACOUSTIC_STEP"
GLOBAL_ENERGY_CONSERVATION_CLAIMED = "NO"
DEDUP_PREFIX = "oop:"

# Silence reasons (LOCKED)
R_NO_IMPULSE = "NO_IMPULSE_TRANSFERRED"
R_NOT_APPROACHING = "NOT_APPROACHING"
R_BELOW_EPSILON = "BELOW_IMPULSE_THRESHOLD"
R_NO_DISSIPATION = "ZERO_DISSIPATION"
R_ALREADY = "ALREADY_PROCESSED"
R_TRANSPORT = "TRANSPORT_REJECTED"
R_ZERO_ENERGY = "ACOUSTIC_ENERGY_ZERO"
R_UNRESOLVED = "UNRESOLVED_PHYSICAL_RESPONSE"
R_INVALID_ENERGY = "INVALID_ENERGY"
R_RESTING = "RESTING"
R_SEPARATING = "SEPARATING"

# Calibration: impulse_epsilon mirrors Audio B / B/O (0.04 mass*cells/tick).
# energy_epsilon gates near-zero numerical dissipation. coupling/max reuse B/O.
DEFAULT_IMPULSE_EPSILON = 0.04
DEFAULT_ENERGY_EPSILON = 1e-12
DEFAULT_ACOUSTIC_COUPLING = 1.0
DEFAULT_MAX_ACOUSTIC_ENERGY = 2.5

OVERLAY_CAPTION = (
    "OBJECT/OBJECT IMPACT · RESOLVED PAIR IMPULSE → DISSIPATED ENERGY → LOCAL SIGNAL · "
    "NEUTRAL BROADBAND · NO MATERIAL TIMBRE · MULTI-CONTACT UNRESOLVED = SILENT"
)

RESEARCHER_FLAGS = {
    "semantic_label": False,
    "semantic_sound_class": False,
    "material_dependent": False,
    "agent_accessible": False,
    "researcher_only": True,
    "direct_delivery": False,
}


@dataclass
class ResourceObjectPairImpactAcousticConfig:
    """Acanthostega OO impact-acoustic profile. Fresh default OFF; absent = OFF."""

    enabled: bool = False
    impulse_epsilon: float = DEFAULT_IMPULSE_EPSILON
    energy_epsilon: float = DEFAULT_ENERGY_EPSILON
    acoustic_coupling: float = DEFAULT_ACOUSTIC_COUPLING
    max_acoustic_energy: float = DEFAULT_MAX_ACOUSTIC_ENERGY
    history_limit: int = 32

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "impulse_epsilon": float(self.impulse_epsilon),
            "energy_epsilon": float(self.energy_epsilon),
            "acoustic_coupling": float(self.acoustic_coupling),
            "max_acoustic_energy": float(self.max_acoustic_energy),
            "history_limit": int(self.history_limit),
            "profile_version": PROFILE_VERSION,
            "energy_law": ENERGY_LAW,
            "band_profile": BAND_PROFILE_NAME,
            "position_derivation": POSITION_DERIVATION,
            "mechanical_energy_withdrawn": False,
            "global_energy_conservation_claimed": GLOBAL_ENERGY_CONSERVATION_CLAIMED,
            "near_elastic_policy": "SILENCE_WHEN_DISSIPATION_ZERO",
            "multi_contact_policy": "SILENCE_UNRESOLVED",
            "calibration_note": (
                "impulse_epsilon mirrors Audio B/B-O (0.04 mass*cells/tick); "
                "coupling is KE->acoustic (default 1.0); dissipation-only; "
                "isolated resolved pairs only"
            ),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ResourceObjectPairImpactAcousticConfig":
        if not isinstance(data, dict) or not data:
            return cls(enabled=False)
        for key, expected in (
            ("profile_version", PROFILE_VERSION),
            ("energy_law", ENERGY_LAW),
            ("band_profile", BAND_PROFILE_NAME),
        ):
            val = data.get(key)
            if val is not None and str(val) != expected:
                raise ValueError(f"unknown OO impact acoustic {key}: {val}")
        return cls(
            enabled=bool(data.get("enabled", False)),
            impulse_epsilon=float(data.get("impulse_epsilon", DEFAULT_IMPULSE_EPSILON)),
            energy_epsilon=float(data.get("energy_epsilon", DEFAULT_ENERGY_EPSILON)),
            acoustic_coupling=float(data.get("acoustic_coupling", DEFAULT_ACOUSTIC_COUPLING)),
            max_acoustic_energy=float(data.get("max_acoustic_energy", DEFAULT_MAX_ACOUSTIC_ENERGY)),
            history_limit=int(data.get("history_limit", 32)),
        )


def validate_config(cfg: ResourceObjectPairImpactAcousticConfig) -> None:
    eps = float(cfg.impulse_epsilon)
    eeps = float(cfg.energy_epsilon)
    c = float(cfg.acoustic_coupling)
    emax = float(cfg.max_acoustic_energy)
    if not all(math.isfinite(v) for v in (eps, eeps, c, emax)):
        raise ValueError("OO impact acoustic parameters must be finite")
    if not (eps > 0.0):
        raise ValueError("impulse_epsilon must be > 0")
    if not (eeps >= 0.0):
        raise ValueError("energy_epsilon must be >= 0")
    if not (0.0 < c <= 100.0):
        raise ValueError("acoustic_coupling must be in (0, 100]")
    if not (0.0 < emax <= 16.0):
        raise ValueError("max_acoustic_energy must be in (0, 16]")
    if not (1 <= int(cfg.history_limit) <= 256):
        raise ValueError("history_limit must be in [1, 256]")


def _line_ok(config: Any) -> bool:
    return config is not None and str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"


def resource_object_pair_impact_acoustics_is_active(config: Any) -> bool:
    if not _line_ok(config):
        return False
    cfg = getattr(config, "resource_object_pair_impact_acoustic_emission", None)
    if cfg is None or not bool(getattr(cfg, "enabled", False)):
        return False
    from mechanistic_mind.physical_system.local_physical_signal_transport import (
        local_physical_signal_transport_is_active,
    )
    return bool(local_physical_signal_transport_is_active(config))


def set_resource_object_pair_impact_acoustics(config: Any, enabled: bool) -> None:
    if config is None:
        return
    on = bool(enabled) and _line_ok(config)
    cur = getattr(config, "resource_object_pair_impact_acoustic_emission", None)
    if cur is None:
        if on:
            config.resource_object_pair_impact_acoustic_emission = (
                ResourceObjectPairImpactAcousticConfig(enabled=True)
            )
        return
    cur.enabled = on


def catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "config_path": "resource_object_pair_impact_acoustic_emission.enabled",
        "enabled": bool(enabled),
        "scientific_status": "IMPLEMENTED",
        "promotion_class": "EXPERIMENTAL",
        "description": (
            "Acanthostega FREE ResourceObject↔ResourceObject impact acoustics: a measured "
            "approaching isolated-pair impulse with pairwise KE dissipation above epsilon "
            "becomes a bounded broadband physical emission in the existing local physical "
            "signal transport. Multi-contact unresolved, resting, separating, correction-only "
            "and near-elastic (zero dissipation) impacts are silent. No material timbre; "
            "mechanical energy not withdrawn. Bodies only via LPS."
        ),
    }


def acoustic_energy_from_dissipation(
    e_dissipated: float, cfg: ResourceObjectPairImpactAcousticConfig
) -> tuple[float, float]:
    """(unclamped, emitted). Dissipation-only; zero/non-finite dissipation -> (0, 0)."""
    d = float(e_dissipated)
    if not math.isfinite(d) or d <= 0.0:
        return 0.0, 0.0
    raw = float(cfg.acoustic_coupling) * d
    return raw, float(min(max(raw, 0.0), float(cfg.max_acoustic_energy)))


def _zero_counters() -> dict[str, int]:
    return {
        "responses_observed": 0,
        "impulses_eligible": 0,
        "silent_no_impulse": 0,
        "silent_not_approaching": 0,
        "silent_below_epsilon": 0,
        "silent_no_dissipation": 0,
        "silent_zero_energy": 0,
        "silent_unresolved": 0,
        "silent_resting": 0,
        "silent_separating": 0,
        "silent_invalid_energy": 0,
        "emissions": 0,
        "transport_rejected": 0,
        "reprocess_suppressed": 0,
        "already_processed": 0,
    }


@dataclass
class ResourceObjectPairImpactAcousticState:
    config: ResourceObjectPairImpactAcousticConfig
    processed_response_keys: set[str] = field(default_factory=set)
    measure_tick: int = -1
    measure_next: int = 0
    last_processed_tick: int = -1
    counters: dict[str, int] = field(default_factory=_zero_counters)
    measurement_history: list[dict[str, Any]] = field(default_factory=list)
    emission_history: list[dict[str, Any]] = field(default_factory=list)
    dissipation_energy_samples: list[list[float]] = field(default_factory=list)
    last_step: dict[str, Any] = field(default_factory=dict)


def state_of(world: Any) -> ResourceObjectPairImpactAcousticState | None:
    raw = getattr(world, "resource_object_pair_impact_acoustic_state", None)
    return raw if isinstance(raw, ResourceObjectPairImpactAcousticState) else None


def ensure_resource_object_pair_impact_acoustics_for_runtime(
    world: Any, config: Any
) -> ResourceObjectPairImpactAcousticState | None:
    if world is None:
        return None
    if not resource_object_pair_impact_acoustics_is_active(config):
        if getattr(world, "resource_object_pair_impact_acoustic_state", None) is not None:
            world.resource_object_pair_impact_acoustic_state = None
        return None
    cur = state_of(world)
    if cur is not None:
        return cur
    cfg = ResourceObjectPairImpactAcousticConfig.from_dict(
        config.resource_object_pair_impact_acoustic_emission.to_dict()
    )
    validate_config(cfg)
    world.resource_object_pair_impact_acoustic_state = ResourceObjectPairImpactAcousticState(
        config=cfg
    )
    return world.resource_object_pair_impact_acoustic_state


def _bounded_append(rows: list, item: Any, limit: int) -> None:
    rows.append(item)
    if len(rows) > int(limit):
        del rows[: len(rows) - int(limit)]


def _alloc_measurement(st: ResourceObjectPairImpactAcousticState, te: int) -> str:
    if int(st.measure_tick) != int(te):
        st.measure_tick, st.measure_next = int(te), 0
    seq = int(st.measure_next)
    st.measure_next = seq + 1
    return f"oo-impact-acoustic-{int(te):09d}-{seq:04d}"


def _dedup_key(response_key: str) -> str:
    """Namespace OO keys so they never collide with B/O processed keys."""
    rk = str(response_key or "")
    if not rk:
        return ""
    if rk.startswith(DEDUP_PREFIX):
        return rk
    return f"{DEDUP_PREFIX}{rk}"


def _impulse_step(world: Any) -> dict[str, Any] | None:
    for attr in (
        "last_resource_object_pair_contact_impulse_step",
        "last_resource_object_pair_impulse_step",
    ):
        step = getattr(world, attr, None)
        if isinstance(step, dict):
            return step
    try:
        from mechanistic_mind.physical_system.resource_object_pair_contact_impulse import (
            state_of as impulse_state_of,
        )
        st = impulse_state_of(world)
        if st is not None and isinstance(st.last_step, dict):
            return st.last_step
    except Exception:
        pass
    return None


def _lookup_contact_point(
    world: Any, *, episode_id: str, pair_key: str, object_id_a: str, object_id_b: str
) -> tuple[list[float] | None, str]:
    """Prefer contact_point from OO contact-fact begin/persist matching episode/pair."""
    step = getattr(world, "last_resource_object_pair_contact_step", None)
    if not isinstance(step, dict):
        return None, "CONTACT_STEP_UNAVAILABLE"
    rows = list(step.get("begin") or []) + list(step.get("persist") or [])
    for row in rows:
        if not isinstance(row, dict):
            continue
        if episode_id and str(row.get("episode_id") or "") == str(episode_id):
            cp = row.get("contact_point")
            if isinstance(cp, (list, tuple)) and len(cp) >= 2:
                return [float(cp[0]), float(cp[1])], str(
                    row.get("contact_point_policy") or POSITION_DERIVATION
                )
        if pair_key and str(row.get("pair_key") or "") == str(pair_key):
            cp = row.get("contact_point")
            if isinstance(cp, (list, tuple)) and len(cp) >= 2:
                return [float(cp[0]), float(cp[1])], str(
                    row.get("contact_point_policy") or POSITION_DERIVATION
                )
        ra = str(row.get("object_id_a") or "")
        rb = str(row.get("object_id_b") or "")
        ids = {ra, rb}
        if object_id_a and object_id_b and object_id_a in ids and object_id_b in ids:
            cp = row.get("contact_point")
            if isinstance(cp, (list, tuple)) and len(cp) >= 2:
                return [float(cp[0]), float(cp[1])], str(
                    row.get("contact_point_policy") or POSITION_DERIVATION
                )
    return None, "CONTACT_POINT_NOT_FOUND"


def _object_centres(
    world: Any, object_id_a: str, object_id_b: str
) -> tuple[float, float, float, float] | None:
    """Prefer contact-fact poses; else live object centres."""
    a_xy = None
    b_xy = None
    step = getattr(world, "last_resource_object_pair_contact_step", None)
    if isinstance(step, dict):
        for row in list(step.get("begin") or []) + list(step.get("persist") or []):
            ra = str(row.get("object_id_a") or "")
            rb = str(row.get("object_id_b") or "")
            ids = {ra, rb}
            if object_id_a not in ids or object_id_b not in ids:
                continue
            pa = row.get("object_a_pose") or row.get("pose_a") or row.get("object_pose_a")
            pb = row.get("object_b_pose") or row.get("pose_b") or row.get("object_pose_b")
            # Also accept generic object_pose keyed by id order in measurement
            if isinstance(pa, (list, tuple)) and len(pa) >= 2:
                if ra == object_id_a:
                    a_xy = (float(pa[0]), float(pa[1]))
                elif ra == object_id_b:
                    b_xy = (float(pa[0]), float(pa[1]))
            if isinstance(pb, (list, tuple)) and len(pb) >= 2:
                if rb == object_id_b:
                    b_xy = (float(pb[0]), float(pb[1]))
                elif rb == object_id_a:
                    a_xy = (float(pb[0]), float(pb[1]))
            if a_xy is not None and b_xy is not None:
                break
    objs = {str(getattr(o, "object_id", "")): o for o in list(getattr(world, "resource_objects", None) or [])}
    if a_xy is None and object_id_a in objs:
        o = objs[object_id_a]
        a_xy = (float(o.x), float(o.y))
    if b_xy is None and object_id_b in objs:
        o = objs[object_id_b]
        b_xy = (float(o.x), float(o.y))
    if a_xy is None or b_xy is None:
        return None
    return a_xy[0], a_xy[1], b_xy[0], b_xy[1]


def _resolve_source_position(
    world: Any, receipt: dict[str, Any]
) -> tuple[float, float, str]:
    from mechanistic_mind.physical_system import local_physical_signal_transport as lps

    height, width = lps._shape(world)
    episode_id = str(receipt.get("episode_id") or "")
    pair_key = str(receipt.get("pair_key") or "")
    oid_a = str(receipt.get("object_id_a") or "")
    oid_b = str(receipt.get("object_id_b") or "")
    cp, policy = _lookup_contact_point(
        world,
        episode_id=episode_id,
        pair_key=pair_key,
        object_id_a=oid_a,
        object_id_b=oid_b,
    )
    if cp is not None:
        from mechanistic_mind.planet.topology import wrap_coord

        return (
            float(wrap_coord(cp[0], width)),
            float(wrap_coord(cp[1], height)),
            policy if policy else POSITION_DERIVATION,
        )
    centres = _object_centres(world, oid_a, oid_b)
    if centres is not None:
        ax, ay, bx, by = centres
        mx, my = toroidal_midpoint(ax, ay, bx, by, width, height)
        return mx, my, POSITION_FALLBACK
    return 0.0, 0.0, "POSITION_UNAVAILABLE"


def _is_unresolved(receipt: dict[str, Any]) -> bool:
    reason = str(receipt.get("reason") or "")
    if reason in (
        "MULTI_CONTACT_COMPONENT_NOT_RESOLVED",
        "UNRESOLVED_PHYSICAL_RESPONSE",
    ):
        return True
    if receipt.get("isolated_pair") is False:
        return True
    # Multi-contact diagnostic receipts lack isolated_pair=True and have component_* fields
    if reason.startswith("MULTI_CONTACT"):
        return True
    if "component_object_count" in receipt and int(receipt.get("component_object_count") or 0) > 2:
        return True
    if "component_edge_count" in receipt and int(receipt.get("component_edge_count") or 0) > 1:
        if not bool(receipt.get("isolated_pair")):
            return True
    return False


def _eligible_impulse(
    receipt: dict[str, Any], cfg: ResourceObjectPairImpactAcousticConfig
) -> tuple[bool, str | None]:
    """LOCKED trigger: isolated/resolved + impulse + approaching + |j| > epsilon."""
    if _is_unresolved(receipt):
        return False, R_UNRESOLVED
    reason = str(receipt.get("reason") or "")
    if reason in ("RESTING_NO_APPROACH", "RESTING"):
        return False, R_RESTING
    if reason == "SEPARATING":
        return False, R_SEPARATING
    impulse_transferred = bool(receipt.get("impulse_transferred"))
    try:
        j = abs(float(receipt.get("impulse_scalar_j") or 0.0))
    except (TypeError, ValueError):
        j = 0.0
    approaching = bool(receipt.get("approaching")) or reason == "APPROACHING"
    if reason == "APPROACHING" and (impulse_transferred or j > 0.0):
        impulse_transferred = True
        approaching = True
    # Require isolated_pair when present (resolved isolated only)
    if "isolated_pair" in receipt and not bool(receipt.get("isolated_pair")):
        return False, R_UNRESOLVED
    if not impulse_transferred and not (reason == "APPROACHING" and j > 0.0):
        return False, R_NO_IMPULSE
    if not approaching and reason != "APPROACHING":
        return False, R_NOT_APPROACHING
    if j <= float(cfg.impulse_epsilon):
        return False, R_BELOW_EPSILON
    return True, None


def process_resource_object_pair_impact_acoustics(
    world: Any,
    config: Any,
    *,
    emission_tick: int,
) -> dict[str, Any]:
    """Read last OO impulse-step receipts; emit at most one LPS signal per response_key."""
    from mechanistic_mind.physical_system import local_physical_signal_transport as lps

    st = state_of(world)
    if st is None:
        st = ensure_resource_object_pair_impact_acoustics_for_runtime(world, config)
    if st is None:
        return {"enabled": False}
    te = int(emission_tick)
    if te <= int(st.last_processed_tick):
        st.counters["reprocess_suppressed"] += 1
        return {"enabled": True, "status": "ALREADY_PROCESSED", "tick": te}
    cfg = st.config
    step = _impulse_step(world)
    receipts = list((step or {}).get("responses") or [])
    receipts = sorted(
        [r for r in receipts if isinstance(r, dict)],
        key=lambda r: str(r.get("response_key") or ""),
    )
    lst = lps.state_of(world)
    n_bands = int(getattr(lst, "n_bands", 6) or 6) if lst is not None else 6
    measurements: list[dict[str, Any]] = []
    emissions: list[dict[str, Any]] = []

    for receipt in receipts:
        st.counters["responses_observed"] += 1
        response_key = str(receipt.get("response_key") or "")
        dkey = _dedup_key(response_key)
        mid = _alloc_measurement(st, te)
        oid_a = str(receipt.get("object_id_a") or "")
        oid_b = str(receipt.get("object_id_b") or "")
        episode_id = str(receipt.get("episode_id") or "")
        pair_key = str(receipt.get("pair_key") or (f"{oid_a}|{oid_b}" if oid_a and oid_b else ""))

        if dkey and dkey in st.processed_response_keys:
            st.counters["already_processed"] += 1
            measurement = {
                "receipt_kind": MEASUREMENT_RECEIPT,
                "measurement_id": mid,
                "emission_tick": te,
                "response_key": response_key,
                "object_id_a": oid_a,
                "object_id_b": oid_b,
                "episode_id": episode_id,
                "pair_key": pair_key,
                "emitted": False,
                "emission_created": False,
                "silence_reason": R_ALREADY,
                **RESEARCHER_FLAGS,
            }
            measurements.append(measurement)
            _bounded_append(st.measurement_history, measurement, cfg.history_limit)
            continue

        ok, silence = _eligible_impulse(receipt, cfg)
        try:
            j = abs(float(receipt.get("impulse_scalar_j") or 0.0))
        except (TypeError, ValueError):
            j = 0.0

        e_diss = 0.0
        energy_invalid = False
        if receipt.get("dissipated_energy") is not None:
            try:
                e_diss = float(receipt.get("dissipated_energy"))
                if not math.isfinite(e_diss):
                    energy_invalid = True
                    e_diss = 0.0
            except (TypeError, ValueError):
                e_diss = dissipated_pairwise_ke(
                    receipt.get("ke_pair_pre"), receipt.get("ke_pair_post")
                )
        else:
            e_diss = dissipated_pairwise_ke(
                receipt.get("ke_pair_pre"), receipt.get("ke_pair_post")
            )
        if e_diss < 0.0:
            e_diss = 0.0
        unclamped, energy = acoustic_energy_from_dissipation(e_diss, cfg)

        measurement = {
            "receipt_kind": MEASUREMENT_RECEIPT,
            "measurement_id": mid,
            "emission_tick": te,
            "response_key": response_key,
            "object_id_a": oid_a,
            "object_id_b": oid_b,
            "episode_id": episode_id,
            "pair_key": pair_key,
            "impulse_scalar_j": j,
            "impulse_transferred": bool(receipt.get("impulse_transferred")),
            "isolated_pair": receipt.get("isolated_pair"),
            "reason": receipt.get("reason"),
            "approaching": bool(receipt.get("approaching")),
            "ke_pair_pre": receipt.get("ke_pair_pre"),
            "ke_pair_post": receipt.get("ke_pair_post"),
            "dissipated_energy": float(e_diss),
            "impulse_epsilon": float(cfg.impulse_epsilon),
            "energy_epsilon": float(cfg.energy_epsilon),
            "acoustic_coupling": float(cfg.acoustic_coupling),
            "unclamped_energy": float(unclamped),
            "selected_acoustic_energy": float(energy),
            "emitted": False,
            "emission_created": False,
            "silence_reason": None,
            "energy_law": ENERGY_LAW,
            "near_elastic_policy": "SILENCE_WHEN_DISSIPATION_ZERO",
            "mechanical_energy_withdrawn": False,
            "global_energy_conservation_claimed": GLOBAL_ENERGY_CONSERVATION_CLAIMED,
            **RESEARCHER_FLAGS,
        }

        if energy_invalid and ok:
            measurement["silence_reason"] = R_INVALID_ENERGY
            st.counters["silent_invalid_energy"] += 1
            if dkey:
                st.processed_response_keys.add(dkey)
            measurements.append(measurement)
            _bounded_append(st.measurement_history, measurement, cfg.history_limit)
            continue

        if not ok:
            measurement["silence_reason"] = silence
            if silence == R_NO_IMPULSE:
                st.counters["silent_no_impulse"] += 1
            elif silence == R_NOT_APPROACHING:
                st.counters["silent_not_approaching"] += 1
            elif silence == R_BELOW_EPSILON:
                st.counters["silent_below_epsilon"] += 1
            elif silence == R_UNRESOLVED:
                st.counters["silent_unresolved"] += 1
            elif silence == R_RESTING:
                st.counters["silent_resting"] += 1
            elif silence == R_SEPARATING:
                st.counters["silent_separating"] += 1
            if dkey:
                st.processed_response_keys.add(dkey)
            measurements.append(measurement)
            _bounded_append(st.measurement_history, measurement, cfg.history_limit)
            continue

        st.counters["impulses_eligible"] += 1
        if e_diss <= float(cfg.energy_epsilon):
            measurement["silence_reason"] = R_NO_DISSIPATION
            st.counters["silent_no_dissipation"] += 1
            if dkey:
                st.processed_response_keys.add(dkey)
            measurements.append(measurement)
            _bounded_append(st.measurement_history, measurement, cfg.history_limit)
            continue
        if energy <= 0.0:
            measurement["silence_reason"] = R_ZERO_ENERGY
            st.counters["silent_zero_energy"] += 1
            if dkey:
                st.processed_response_keys.add(dkey)
            measurements.append(measurement)
            _bounded_append(st.measurement_history, measurement, cfg.history_limit)
            continue

        ox, oy, derivation = _resolve_source_position(world, receipt)
        bands = broadband_bands(energy, n_bands)
        tr = lps.emit_local_physical_signal(
            world,
            emission_tick=te,
            x=ox,
            y=oy,
            band_energies=bands,
            provenance={
                "selection_provenance": lps.PROV_PHYSICAL_CONTACT,
                "source_body_id": None,
                "source_body_pair": None,
                "graph_source_label": f"OO_IMPACT:{oid_a}|{oid_b}",
                "cause_receipt_ref": mid,
                "motor_provenance": None,
                "mechanism": MECHANISM_ID,
            },
        )
        if dkey:
            st.processed_response_keys.add(dkey)
        if tr.get("status") != "EMITTED":
            st.counters["transport_rejected"] += 1
            measurement["silence_reason"] = R_TRANSPORT
            measurement["transport_rejection"] = tr.get("rejection_reason")
            measurements.append(measurement)
            _bounded_append(st.measurement_history, measurement, cfg.history_limit)
            continue

        measurement["emitted"] = True
        measurement["emission_created"] = True
        measurement["emission_id"] = tr["emission_id"]
        st.counters["emissions"] += 1
        emission = {
            "receipt_kind": EMISSION_RECEIPT,
            "emission_id": tr["emission_id"],
            "emission_tick": te,
            "measurement_id": mid,
            "response_key": response_key,
            "object_id_a": oid_a,
            "object_id_b": oid_b,
            "episode_id": episode_id,
            "pair_key": pair_key,
            "position": [ox, oy],
            "position_derivation": derivation,
            "impulse_scalar_j": j,
            "dissipated_energy": float(e_diss),
            "ke_pair_pre": receipt.get("ke_pair_pre"),
            "ke_pair_post": receipt.get("ke_pair_post"),
            "acoustic_coupling": float(cfg.acoustic_coupling),
            "impulse_epsilon": float(cfg.impulse_epsilon),
            "energy_epsilon": float(cfg.energy_epsilon),
            "max_acoustic_energy": float(cfg.max_acoustic_energy),
            "unclamped_energy": float(unclamped),
            "emitted_energy": float(energy),
            "clamped": bool(unclamped > energy + 1e-12),
            "anonymous_band_vector": bands,
            "band_profile": BAND_PROFILE_NAME,
            "energy_law": ENERGY_LAW,
            "mechanism": MECHANISM_ID,
            "preset": "ACANTHOSTEGA_PHASE_B_OBJECT_OBJECT_IMPACT_ACOUSTICS",
            "mechanical_energy_withdrawn": False,
            "global_energy_conservation_claimed": GLOBAL_ENERGY_CONSERVATION_CLAIMED,
            "transport_emission_tick": tr.get("emission_tick"),
            "transport_expiry_tick": tr.get("expiry_tick"),
            "graph_source_label": f"OO_IMPACT:{oid_a}|{oid_b}",
            "emission_created": True,
            **RESEARCHER_FLAGS,
        }
        emissions.append(emission)
        measurements.append(measurement)
        _bounded_append(st.measurement_history, measurement, cfg.history_limit)
        _bounded_append(st.emission_history, emission, cfg.history_limit)
        _bounded_append(st.dissipation_energy_samples, [float(e_diss), float(energy)], 256)

    if len(st.processed_response_keys) > 4096:
        keep = {
            k
            for k in st.processed_response_keys
            if f":{int(te)}:" in k or f":{int(te) - 1}:" in k
        }
        st.processed_response_keys = keep if keep else set(list(st.processed_response_keys)[-512:])

    st.last_processed_tick = te
    st.last_step = {
        "event": EVENT_STEP,
        "tick": te,
        "measurements": measurements,
        "emissions": emissions,
    }
    world.last_resource_object_pair_impact_acoustic_step = st.last_step
    return {"enabled": True, "status": "PROCESSED", **st.last_step}


def serialize_state(st: ResourceObjectPairImpactAcousticState | None) -> dict[str, Any] | None:
    if st is None:
        return None
    return {
        "schema_version": STATE_SCHEMA,
        "config": st.config.to_dict(),
        "processed_response_keys": sorted(st.processed_response_keys),
        "measurement_allocator": {
            "tick": int(st.measure_tick),
            "next_sequence": int(st.measure_next),
        },
        "last_processed_tick": int(st.last_processed_tick),
        "counters": dict(st.counters),
        "measurement_history": list(st.measurement_history),
        "emission_history": list(st.emission_history),
        "dissipation_energy_samples": [list(r) for r in st.dissipation_energy_samples],
    }


def restore_state(
    world: Any, data: dict[str, Any] | None, config: Any
) -> ResourceObjectPairImpactAcousticState | None:
    if not resource_object_pair_impact_acoustics_is_active(config):
        world.resource_object_pair_impact_acoustic_state = None
        return None
    if not isinstance(data, dict) or not data:
        world.resource_object_pair_impact_acoustic_state = None
        return ensure_resource_object_pair_impact_acoustics_for_runtime(world, config)
    if str(data.get("schema_version")) != STATE_SCHEMA:
        raise ValueError(
            f"unknown OO impact acoustic state schema: {data.get('schema_version')}"
        )
    saved = ResourceObjectPairImpactAcousticConfig.from_dict(data.get("config") or {})
    cfg = ResourceObjectPairImpactAcousticConfig.from_dict(
        config.resource_object_pair_impact_acoustic_emission.to_dict()
    )
    validate_config(cfg)
    if saved.to_dict() != cfg.to_dict():
        raise ValueError("OO impact acoustic parameters differ from the runtime config")
    alloc = data.get("measurement_allocator") or {}
    st = ResourceObjectPairImpactAcousticState(
        config=cfg,
        processed_response_keys=set(
            str(k) for k in (data.get("processed_response_keys") or [])
        ),
        measure_tick=int(alloc.get("tick", -1)),
        measure_next=int(alloc.get("next_sequence", 0)),
        last_processed_tick=int(data.get("last_processed_tick", -1)),
        counters={
            **_zero_counters(),
            **{k: int(v) for k, v in (data.get("counters") or {}).items()},
        },
        measurement_history=list(data.get("measurement_history") or []),
        emission_history=list(data.get("emission_history") or []),
        dissipation_energy_samples=[
            list(r) for r in data.get("dissipation_energy_samples") or []
        ],
    )
    world.resource_object_pair_impact_acoustic_state = st
    return st


def copy_state(
    st: ResourceObjectPairImpactAcousticState | None,
) -> ResourceObjectPairImpactAcousticState | None:
    if st is None:
        return None
    data = serialize_state(st)
    out = ResourceObjectPairImpactAcousticState(
        config=ResourceObjectPairImpactAcousticConfig.from_dict(data["config"])
    )
    out.processed_response_keys = set(data["processed_response_keys"])
    out.measure_tick, out.measure_next = st.measure_tick, st.measure_next
    out.last_processed_tick = st.last_processed_tick
    out.counters = dict(st.counters)
    out.measurement_history = list(st.measurement_history)
    out.emission_history = list(st.emission_history)
    out.dissipation_energy_samples = [list(r) for r in st.dissipation_energy_samples]
    return out


def researcher_summary(world: Any) -> dict[str, Any] | None:
    st = state_of(world)
    if st is None:
        return None
    return {
        "mechanism": MECHANISM_ID,
        "profile": st.config.to_dict(),
        "counters": dict(st.counters),
        "recent_emissions": [
            {
                k: e.get(k)
                for k in (
                    "emission_id",
                    "emission_tick",
                    "object_id_a",
                    "object_id_b",
                    "position",
                    "position_derivation",
                    "impulse_scalar_j",
                    "dissipated_energy",
                    "emitted_energy",
                    "measurement_id",
                    "graph_source_label",
                )
            }
            for e in st.emission_history[-8:]
        ],
        "labels": [
            "researcher-only",
            "not agent-accessible",
            "impact-dissipation derived",
            "not a semantic sound class",
            "no material timbre",
            "multi-contact unresolved silent",
        ],
        "overlay_caption": OVERLAY_CAPTION,
        **RESEARCHER_FLAGS,
    }


def overlay_payload(world: Any) -> dict[str, Any] | None:
    st = state_of(world)
    if st is None:
        return None
    return {
        "caption": OVERLAY_CAPTION,
        "emissions": list(st.emission_history[-8:]),
        "summary": researcher_summary(world),
    }
