"""Acanthostega Free-Space V1C · Vertical impact acoustic emission.

Mechanism: vertical_impact_acoustic_emission
Preset: ACANTHOSTEGA_BETA4_VERTICAL_IMPACT_ACOUSTIC_EMISSION
Parent: ACANTHOSTEGA_BETA4_VERTICAL_TERRAIN_LANDING_CONTACT_RESPONSE
Profile: VERTICAL_IMPACT_ACOUSTIC_EMISSION_V1
Receipt: VERTICAL_IMPACT_ACOUSTIC_EMISSION
Architecture stage: FREE_SPACE_V1C_VERTICAL_IMPACT_ACOUSTICS

Consumes committed V1B landing RESPONSE evidence only:
    fall → contact fact → inelastic response → E_diss → E_emit → LPS

Contact fact alone, PERSIST, correction-only, restore, and below-threshold
events remain SILENT. No human playback. No second acoustic reality.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from mechanistic_mind.physical_system.physical_contact_acoustic_emission import (
    BAND_PROFILE,
    broadband_bands,
)
from mechanistic_mind.physical_system.vertical_terrain_landing_contact_response import (
    CLASS_CORRECTION_CLAMPED,
    CLASS_INVALID_MASS,
    CLASS_LANDING_IMPACT,
    CLASS_REST_PERSIST,
    CLASS_START_PENETRATION,
)

MECHANISM_ID = "vertical_impact_acoustic_emission"
PROFILE_VERSION = "VERTICAL_IMPACT_ACOUSTIC_EMISSION_V1"
STATE_SCHEMA = "VERTICAL_IMPACT_ACOUSTIC_STATE_V1"
RECEIPT_KIND = "VERTICAL_IMPACT_ACOUSTIC_EMISSION"
MEASUREMENT_RECEIPT = "VERTICAL_IMPACT_ACOUSTIC_MEASUREMENT"
EVENT_STEP = "VERTICAL_IMPACT_ACOUSTIC_STEP"
ARCHITECTURE_STAGE = "FREE_SPACE_V1C_VERTICAL_IMPACT_ACOUSTICS"
ENERGY_LAW = "LANDING_DISSIPATED_KE_TO_ACOUSTIC_ENERGY_V1"
BAND_PROFILE_NAME = BAND_PROFILE  # UNIFORM_BROADBAND_V1
SOURCE_ID_PREFIX = "vti"
POSITION_POLICY = "AUTHORITATIVE_LANDING_CONTACT_POINT_V1"
POSITION_FALLBACK = "ENTITY_XY_PLUS_SUPPORT_Z_FALLBACK_V1"
LIMITATION_LPS_2D = "LPS_PROPAGATION_REMAINS_HORIZONTAL_XY_ABSTRACTION_V1"
LIMITATION_COUPLED_3D = "COUPLED_3D_MULTI_CONTACT_NOT_RESOLVED_V1"

BANNER = (
    "VERTICAL IMPACT ACOUSTICS · LANDING RESPONSE ENERGY → LPS · "
    "NEUTRAL BANDS · PERSISTENT SUPPORT SILENT · NO HUMAN PLAYBACK YET"
)

# Silence reasons (stable researcher tokens)
R_CONTACT_FACT_ONLY = "CONTACT_FACT_ONLY"
R_PERSISTENT_SUPPORT = "PERSISTENT_SUPPORT"
R_POSITION_CORRECTION_ONLY = "POSITION_CORRECTION_ONLY"
R_SUPPORT_REFRESH = "SUPPORT_REFRESH"
R_RESTORE_REPLAY = "RESTORE_REPLAY_FORBIDDEN"
R_DUPLICATE = "DUPLICATE_RESPONSE"
R_INVALID_MASS = "INVALID_MASS"
R_INVALID_ENERGY = "INVALID_ENERGY"
R_BELOW_IMPULSE = "BELOW_IMPULSE_THRESHOLD"
R_BELOW_ENERGY = "BELOW_ENERGY_THRESHOLD"
R_NON_APPROACHING = "NON_APPROACHING"
R_RESPONSE_NOT_APPLIED = "RESPONSE_NOT_APPLIED"
R_NEWBORN_OR_RELEASE = "NEWBORN_OR_RELEASE_TRANSITION_NOT_ELIGIBLE"
R_TRANSPORT = "TRANSPORT_REJECTED"
R_ZERO_ENERGY = "ACOUSTIC_ENERGY_ZERO"
R_INVALID_CONTACT_POINT = "INVALID_CONTACT_POINT"
R_NO_RESPONSE_KEY = "NO_RESPONSE_KEY"

# Match nearby impact-acoustic conventions (body/object dissipation path).
DEFAULT_IMPULSE_EPSILON = 0.04
DEFAULT_ENERGY_EPSILON = 1e-12
DEFAULT_ACOUSTIC_COUPLING = 1.0
DEFAULT_MAX_EMITTED_ENERGY = 2.5
HISTORY_LIMIT_DEFAULT = 32
DEDUP_BOUND = 4096

RESEARCHER_FLAGS = {
    "semantic_label": False,
    "semantic_sound_class": False,
    "material_dependent": False,
    "agent_accessible": False,
    "researcher_only": True,
    "direct_delivery": False,
    "human_playback": False,
}


@dataclass
class VerticalImpactAcousticEmissionConfig:
    """Fresh default OFF; absent field = OFF (parent V1B unchanged)."""

    enabled: bool = False
    impulse_epsilon: float = DEFAULT_IMPULSE_EPSILON
    energy_epsilon: float = DEFAULT_ENERGY_EPSILON
    acoustic_coupling: float = DEFAULT_ACOUSTIC_COUPLING
    max_emitted_energy: float = DEFAULT_MAX_EMITTED_ENERGY
    history_limit: int = HISTORY_LIMIT_DEFAULT

    def to_dict(self) -> dict[str, Any]:
        on = bool(self.enabled)
        return {
            "enabled": on,
            "impulse_epsilon": float(self.impulse_epsilon),
            "energy_epsilon": float(self.energy_epsilon),
            "acoustic_coupling": float(self.acoustic_coupling),
            "max_emitted_energy": float(self.max_emitted_energy),
            "history_limit": int(self.history_limit),
            "profile_version": PROFILE_VERSION,
            "architecture_stage": ARCHITECTURE_STAGE,
            "receipt_kind": RECEIPT_KIND,
            "energy_law": ENERGY_LAW,
            "band_profile": BAND_PROFILE_NAME,
            "position_policy": POSITION_POLICY,
            "mechanical_energy_withdrawn": False,
            "human_playback_implemented": False,
            "banner": BANNER if on else None,
            "calibration_note": (
                "impulse_epsilon mirrors body/object impact acoustics (0.04); "
                "coupling is KE->acoustic (default 1.0); dissipation-only from "
                "committed landing response; max_emitted_energy=2.5"
            ),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "VerticalImpactAcousticEmissionConfig":
        if not isinstance(data, dict) or not data:
            return cls(enabled=False)
        for key, expected in (
            ("profile_version", PROFILE_VERSION),
            ("energy_law", ENERGY_LAW),
            ("band_profile", BAND_PROFILE_NAME),
        ):
            val = data.get(key)
            if val is not None and str(val) != expected:
                raise ValueError(f"unknown vertical impact acoustic {key}: {val}")
        return cls(
            enabled=bool(data.get("enabled", False)),
            impulse_epsilon=float(data.get("impulse_epsilon", DEFAULT_IMPULSE_EPSILON)),
            energy_epsilon=float(data.get("energy_epsilon", DEFAULT_ENERGY_EPSILON)),
            acoustic_coupling=float(data.get("acoustic_coupling", DEFAULT_ACOUSTIC_COUPLING)),
            max_emitted_energy=float(data.get("max_emitted_energy", DEFAULT_MAX_EMITTED_ENERGY)),
            history_limit=int(data.get("history_limit", HISTORY_LIMIT_DEFAULT)),
        )


def validate_config(cfg: VerticalImpactAcousticEmissionConfig) -> None:
    vals = (
        float(cfg.impulse_epsilon),
        float(cfg.energy_epsilon),
        float(cfg.acoustic_coupling),
        float(cfg.max_emitted_energy),
    )
    if not all(math.isfinite(v) for v in vals):
        raise ValueError("vertical impact acoustic parameters must be finite")
    if not (vals[0] > 0.0):
        raise ValueError("impulse_epsilon must be > 0")
    if not (vals[1] >= 0.0):
        raise ValueError("energy_epsilon must be >= 0")
    if not (0.0 < vals[2] <= 100.0):
        raise ValueError("acoustic_coupling must be in (0, 100]")
    if not (0.0 < vals[3] <= 16.0):
        raise ValueError("max_emitted_energy must be in (0, 16]")
    if not (1 <= int(cfg.history_limit) <= 256):
        raise ValueError("history_limit must be in [1, 256]")


def _line_ok(config: Any) -> bool:
    return config is not None and str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"


def vertical_impact_acoustic_emission_is_active(config: Any) -> bool:
    if not _line_ok(config):
        return False
    cfg = getattr(config, "vertical_impact_acoustic_emission", None)
    if cfg is None:
        return False
    if isinstance(cfg, dict):
        on = bool(cfg.get("enabled"))
    else:
        on = bool(getattr(cfg, "enabled", False))
    if not on:
        return False
    from mechanistic_mind.physical_system.local_physical_signal_transport import (
        local_physical_signal_transport_is_active,
    )
    from mechanistic_mind.physical_system.vertical_terrain_landing_contact_response import (
        vertical_terrain_landing_contact_response_is_active,
    )

    return bool(
        local_physical_signal_transport_is_active(config)
        and vertical_terrain_landing_contact_response_is_active(config)
    )


def set_vertical_impact_acoustic_emission(config: Any, enabled: bool) -> None:
    if config is None:
        return
    on = bool(enabled) and _line_ok(config)
    cur = getattr(config, "vertical_impact_acoustic_emission", None)
    if cur is None or isinstance(cur, dict):
        if on:
            cfg = VerticalImpactAcousticEmissionConfig.from_dict(
                cur if isinstance(cur, dict) else None
            )
            cfg.enabled = True
            config.vertical_impact_acoustic_emission = cfg
        return
    cur.enabled = on


def catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "config_path": "vertical_impact_acoustic_emission.enabled",
        "enabled": bool(enabled),
        "scientific_status": "IMPLEMENTED",
        "promotion_class": "EXPERIMENTAL",
        "profile_version": PROFILE_VERSION,
        "architecture_stage": ARCHITECTURE_STAGE,
        "receipt_kind": RECEIPT_KIND,
        "banner": BANNER if enabled else None,
        "human_playback_implemented": False,
        "description": (
            "Acanthostega vertical terrain-impact acoustics: a committed approaching "
            "landing response with positive dissipated vertical KE becomes a bounded "
            "neutral broadband emission in the existing LPS. Contact fact alone, "
            "persistent support, correction-only, restore, and below-threshold events "
            "are silent. No material timbre; no human playback."
        ),
        **RESEARCHER_FLAGS,
    }


def acoustic_energy_from_landing_dissipation(
    e_diss: float, cfg: VerticalImpactAcousticEmissionConfig
) -> tuple[float, float]:
    """(unclamped, emitted). Uses authoritative E_diss only; does not recompute from vz."""
    d = float(e_diss)
    if not math.isfinite(d) or d <= float(cfg.energy_epsilon):
        return 0.0, 0.0
    raw = float(cfg.acoustic_coupling) * d
    if not math.isfinite(raw):
        return 0.0, 0.0
    return raw, float(min(max(raw, 0.0), float(cfg.max_emitted_energy)))


def source_id_for_response(*, response_key: str, tick: int) -> str:
    return f"{SOURCE_ID_PREFIX}:{str(response_key)}:{int(tick)}"


def classify_eligibility(
    receipt: dict[str, Any],
    cfg: VerticalImpactAcousticEmissionConfig,
    *,
    already_processed: bool = False,
    restore_context: bool = False,
) -> tuple[bool, str | None]:
    """Return (eligible, silence_reason). Researcher-stable reasons."""
    if restore_context or bool(receipt.get("restore_replay")):
        return False, R_RESTORE_REPLAY
    if already_processed:
        return False, R_DUPLICATE
    response_key = str(receipt.get("response_key") or "")
    if not response_key:
        return False, R_NO_RESPONSE_KEY

    phase = str(receipt.get("episode_phase") or "")
    cls = str(
        receipt.get("response_classification")
        or receipt.get("intersection_class")
        or ""
    )
    if phase == "PERSIST" or cls == CLASS_REST_PERSIST:
        return False, R_PERSISTENT_SUPPORT
    if phase == "END" and not bool(receipt.get("response_applied")):
        return False, R_CONTACT_FACT_ONLY
    if bool(receipt.get("support_refresh")) or cls == "SUPPORT_REFRESH":
        return False, R_SUPPORT_REFRESH
    if bool(receipt.get("newborn_creation_tick")) or bool(
        receipt.get("release_transition_tick")
    ):
        return False, R_NEWBORN_OR_RELEASE
    if cls == CLASS_INVALID_MASS or receipt.get("mass_valid") is False:
        return False, R_INVALID_MASS
    if cls == CLASS_START_PENETRATION and not bool(receipt.get("approach")):
        return False, R_POSITION_CORRECTION_ONLY
    if cls == CLASS_CORRECTION_CLAMPED and not bool(receipt.get("approach")):
        return False, R_POSITION_CORRECTION_ONLY
    if bool(receipt.get("correction_only")) and not bool(receipt.get("response_applied")):
        return False, R_POSITION_CORRECTION_ONLY

    if not bool(receipt.get("response_applied")):
        if phase == "BEGIN" and not bool(receipt.get("approach")):
            return False, R_CONTACT_FACT_ONLY
        return False, R_RESPONSE_NOT_APPLIED

    if cls not in (CLASS_LANDING_IMPACT, CLASS_CORRECTION_CLAMPED) and not bool(
        receipt.get("approach")
    ):
        # Applied but not an approaching impact (separating / rest misflag)
        if not bool(receipt.get("approach")):
            return False, R_NON_APPROACHING

    if not bool(receipt.get("approach")):
        return False, R_NON_APPROACHING

    try:
        mass = float(receipt.get("effective_mass"))
    except (TypeError, ValueError):
        mass = float("nan")
    if not math.isfinite(mass) or mass <= 0.0:
        return False, R_INVALID_MASS

    try:
        impulse = abs(float(receipt.get("impulse_magnitude") or 0.0))
    except (TypeError, ValueError):
        impulse = 0.0
    if not math.isfinite(impulse):
        return False, R_INVALID_ENERGY
    if impulse <= float(cfg.impulse_epsilon):
        return False, R_BELOW_IMPULSE

    try:
        e_diss = float(receipt.get("dissipated_energy"))
    except (TypeError, ValueError):
        e_diss = float("nan")
    if not math.isfinite(e_diss):
        return False, R_INVALID_ENERGY
    if e_diss <= float(cfg.energy_epsilon):
        return False, R_BELOW_ENERGY

    cp = receipt.get("contact_point")
    if not (isinstance(cp, (list, tuple)) and len(cp) >= 3):
        # Still eligible if x/y/support_z present for fallback
        try:
            x = float(receipt.get("x"))
            y = float(receipt.get("y"))
            sz = float(receipt.get("support_z"))
            if not all(math.isfinite(v) for v in (x, y, sz)):
                return False, R_INVALID_CONTACT_POINT
        except (TypeError, ValueError):
            return False, R_INVALID_CONTACT_POINT

    return True, None


def _zero_counters() -> dict[str, int]:
    return {
        "responses_observed": 0,
        "eligible": 0,
        "emissions": 0,
        "silent_contact_fact_only": 0,
        "silent_persistent_support": 0,
        "silent_position_correction_only": 0,
        "silent_support_refresh": 0,
        "silent_restore": 0,
        "silent_duplicate": 0,
        "silent_invalid_mass": 0,
        "silent_invalid_energy": 0,
        "silent_below_impulse": 0,
        "silent_below_energy": 0,
        "silent_non_approaching": 0,
        "silent_response_not_applied": 0,
        "silent_newborn_or_release": 0,
        "silent_zero_energy": 0,
        "silent_invalid_contact_point": 0,
        "transport_rejected": 0,
        "reprocess_suppressed": 0,
    }


def _bump_silence(st: "VerticalImpactAcousticEmissionState", reason: str | None) -> None:
    m = {
        R_CONTACT_FACT_ONLY: "silent_contact_fact_only",
        R_PERSISTENT_SUPPORT: "silent_persistent_support",
        R_POSITION_CORRECTION_ONLY: "silent_position_correction_only",
        R_SUPPORT_REFRESH: "silent_support_refresh",
        R_RESTORE_REPLAY: "silent_restore",
        R_DUPLICATE: "silent_duplicate",
        R_INVALID_MASS: "silent_invalid_mass",
        R_INVALID_ENERGY: "silent_invalid_energy",
        R_BELOW_IMPULSE: "silent_below_impulse",
        R_BELOW_ENERGY: "silent_below_energy",
        R_NON_APPROACHING: "silent_non_approaching",
        R_RESPONSE_NOT_APPLIED: "silent_response_not_applied",
        R_NEWBORN_OR_RELEASE: "silent_newborn_or_release",
        R_ZERO_ENERGY: "silent_zero_energy",
        R_INVALID_CONTACT_POINT: "silent_invalid_contact_point",
        R_NO_RESPONSE_KEY: "silent_response_not_applied",
    }
    key = m.get(str(reason or ""))
    if key:
        st.counters[key] = int(st.counters.get(key, 0)) + 1


@dataclass
class VerticalImpactAcousticEmissionState:
    config: VerticalImpactAcousticEmissionConfig
    processed_response_keys: set[str] = field(default_factory=set)
    measure_tick: int = -1
    measure_next: int = 0
    last_processed_tick: int = -1
    counters: dict[str, int] = field(default_factory=_zero_counters)
    measurement_history: list[dict[str, Any]] = field(default_factory=list)
    emission_history: list[dict[str, Any]] = field(default_factory=list)
    last_step: dict[str, Any] = field(default_factory=dict)
    last_receipt: dict[str, Any] | None = None


def state_of(world: Any) -> VerticalImpactAcousticEmissionState | None:
    raw = getattr(world, "vertical_impact_acoustic_emission_state", None)
    return raw if isinstance(raw, VerticalImpactAcousticEmissionState) else None


def ensure_vertical_impact_acoustic_emission_for_runtime(
    world: Any, config: Any
) -> VerticalImpactAcousticEmissionState | None:
    if world is None:
        return None
    if not vertical_impact_acoustic_emission_is_active(config):
        if getattr(world, "vertical_impact_acoustic_emission_state", None) is not None:
            world.vertical_impact_acoustic_emission_state = None
        return None
    cur = state_of(world)
    if cur is not None:
        return cur
    raw = getattr(config, "vertical_impact_acoustic_emission", None)
    cfg = VerticalImpactAcousticEmissionConfig.from_dict(
        raw.to_dict() if raw is not None and hasattr(raw, "to_dict") else None
    )
    cfg.enabled = True
    validate_config(cfg)
    world.vertical_impact_acoustic_emission_state = VerticalImpactAcousticEmissionState(
        config=cfg
    )
    return world.vertical_impact_acoustic_emission_state


def _bounded_append(rows: list, item: Any, limit: int) -> None:
    rows.append(item)
    if len(rows) > int(limit):
        del rows[: len(rows) - int(limit)]


def _alloc_measurement(st: VerticalImpactAcousticEmissionState, te: int) -> str:
    if int(st.measure_tick) != int(te):
        st.measure_tick, st.measure_next = int(te), 0
    seq = int(st.measure_next)
    st.measure_next = seq + 1
    return f"vti-acoustic-{int(te):09d}-{seq:04d}"


def _landing_receipts_for_tick(world: Any, tick: int) -> list[dict[str, Any]]:
    from mechanistic_mind.physical_system.vertical_terrain_landing_contact_response import (
        state_of as landing_state_of,
    )

    st = landing_state_of(world)
    out: list[dict[str, Any]] = []
    if st is not None:
        for row in list(st.history or []):
            if isinstance(row, dict) and int(row.get("tick", -1)) == int(tick):
                out.append(row)
    last = getattr(world, "last_vertical_terrain_landing", None)
    if isinstance(last, dict) and int(last.get("tick", -1)) == int(tick):
        rk = str(last.get("response_key") or "")
        if rk and not any(str(r.get("response_key") or "") == rk for r in out):
            out.append(last)
    # Deterministic order by response_key
    out.sort(key=lambda r: str(r.get("response_key") or ""))
    return out


def _resolve_source_position(
    receipt: dict[str, Any],
) -> tuple[float, float, float, str, bool]:
    """Return (x, y, z, policy, used_fallback)."""
    cp = receipt.get("contact_point")
    if isinstance(cp, (list, tuple)) and len(cp) >= 3:
        try:
            x, y, z = float(cp[0]), float(cp[1]), float(cp[2])
            if all(math.isfinite(v) for v in (x, y, z)):
                return x, y, z, POSITION_POLICY, False
        except (TypeError, ValueError):
            pass
    try:
        x = float(receipt.get("x"))
        y = float(receipt.get("y"))
        z = float(receipt.get("support_z"))
        if all(math.isfinite(v) for v in (x, y, z)):
            return x, y, z, POSITION_FALLBACK, True
    except (TypeError, ValueError):
        pass
    return 0.0, 0.0, 0.0, "POSITION_UNAVAILABLE", True


def process_vertical_impact_acoustic_emission(
    world: Any,
    config: Any,
    *,
    emission_tick: int,
) -> dict[str, Any]:
    """Consume committed landing responses for this tick; emit into LPS at most once per key."""
    from mechanistic_mind.physical_system import local_physical_signal_transport as lps
    from mechanistic_mind.planet.topology import wrap_coord

    st = state_of(world)
    if st is None:
        st = ensure_vertical_impact_acoustic_emission_for_runtime(world, config)
    if st is None:
        return {"enabled": False}
    te = int(emission_tick)
    if te <= int(st.last_processed_tick):
        st.counters["reprocess_suppressed"] = int(st.counters.get("reprocess_suppressed", 0)) + 1
        return {"enabled": True, "status": "ALREADY_PROCESSED", "tick": te}

    cfg = st.config
    receipts = _landing_receipts_for_tick(world, te)
    lst = lps.state_of(world)
    n_bands = int(getattr(lst, "n_bands", 6) or 6) if lst is not None else 6
    height, width = lps._shape(world)
    measurements: list[dict[str, Any]] = []
    emissions: list[dict[str, Any]] = []

    for receipt in receipts:
        st.counters["responses_observed"] = int(st.counters.get("responses_observed", 0)) + 1
        mid = _alloc_measurement(st, te)
        response_key = str(receipt.get("response_key") or "")
        episode_id = str(receipt.get("episode_id") or "")
        entity_id = str(receipt.get("entity_id") or "")
        entity_kind = str(receipt.get("entity_kind") or "")
        phase = str(receipt.get("episode_phase") or "")
        cls = str(
            receipt.get("response_classification")
            or receipt.get("intersection_class")
            or ""
        )

        # Skip flooding measurement history with every resting PERSIST.
        skip_history = phase == "PERSIST" or cls == CLASS_REST_PERSIST

        already = bool(response_key and response_key in st.processed_response_keys)
        ok, silence = classify_eligibility(
            receipt, cfg, already_processed=already, restore_context=False
        )

        try:
            e_diss = float(receipt.get("dissipated_energy") or 0.0)
        except (TypeError, ValueError):
            e_diss = float("nan")
        try:
            impulse = abs(float(receipt.get("impulse_magnitude") or 0.0))
        except (TypeError, ValueError):
            impulse = 0.0
        unclamped, energy = acoustic_energy_from_landing_dissipation(
            e_diss if math.isfinite(e_diss) else 0.0, cfg
        )
        sx, sy, sz, pos_policy, pos_fallback = _resolve_source_position(receipt)
        sx = float(wrap_coord(sx, width))
        sy = float(wrap_coord(sy, height))

        measurement: dict[str, Any] = {
            "receipt_kind": MEASUREMENT_RECEIPT,
            "measurement_id": mid,
            "emission_tick": te,
            "response_key": response_key,
            "episode_id": episode_id,
            "entity_id": entity_id,
            "entity_kind": entity_kind,
            "body_slot": receipt.get("body_slot"),
            "episode_phase": phase,
            "response_classification": cls,
            "response_applied": bool(receipt.get("response_applied")),
            "approach": bool(receipt.get("approach")),
            "impulse_magnitude": float(impulse) if math.isfinite(impulse) else None,
            "effective_mass": receipt.get("effective_mass"),
            "ke_before": receipt.get("ke_before"),
            "ke_after": receipt.get("ke_after"),
            "dissipated_energy": float(e_diss) if math.isfinite(e_diss) else None,
            "impulse_epsilon": float(cfg.impulse_epsilon),
            "energy_epsilon": float(cfg.energy_epsilon),
            "acoustic_coupling": float(cfg.acoustic_coupling),
            "max_emitted_energy": float(cfg.max_emitted_energy),
            "unclamped_energy": float(unclamped),
            "selected_acoustic_energy": float(energy),
            "contact_point": [sx, sy, sz],
            "position_policy": pos_policy,
            "position_fallback": bool(pos_fallback),
            "emitted": False,
            "silence_reason": None,
            "energy_law": ENERGY_LAW,
            "band_profile": BAND_PROFILE_NAME,
            "limitations": [LIMITATION_LPS_2D, LIMITATION_COUPLED_3D],
            "mechanical_energy_withdrawn": False,
            "agent_work_credit": False,
            "global_conservation_claim": False,
            "human_playback": False,
            **RESEARCHER_FLAGS,
        }

        if not ok:
            measurement["silence_reason"] = silence
            _bump_silence(st, silence)
            if response_key and silence != R_DUPLICATE:
                # Mark non-eligible applied responses so they are not reprocessed;
                # duplicates already in the set.
                if silence != R_PERSISTENT_SUPPORT:
                    st.processed_response_keys.add(response_key)
            if not skip_history:
                measurements.append(measurement)
                _bounded_append(st.measurement_history, measurement, cfg.history_limit)
                st.last_receipt = measurement
            continue

        st.counters["eligible"] = int(st.counters.get("eligible", 0)) + 1
        if energy <= 0.0:
            measurement["silence_reason"] = R_ZERO_ENERGY
            _bump_silence(st, R_ZERO_ENERGY)
            if response_key:
                st.processed_response_keys.add(response_key)
            measurements.append(measurement)
            _bounded_append(st.measurement_history, measurement, cfg.history_limit)
            st.last_receipt = measurement
            continue

        bands = broadband_bands(energy, n_bands)
        src_id = source_id_for_response(response_key=response_key, tick=te)
        tr = lps.emit_local_physical_signal(
            world,
            emission_tick=te,
            x=sx,
            y=sy,
            band_energies=bands,
            provenance={
                "selection_provenance": lps.PROV_PHYSICAL_CONTACT,
                "source_body_id": entity_id if entity_kind == "body" else None,
                "source_body_pair": None,
                "graph_source_label": src_id,
                "cause_receipt_ref": mid,
                "motor_provenance": None,
                "mechanism": MECHANISM_ID,
                "source_z": float(sz),
                "landing_response_key": response_key,
            },
        )
        if response_key:
            st.processed_response_keys.add(response_key)

        if tr.get("status") != "EMITTED":
            st.counters["transport_rejected"] = int(st.counters.get("transport_rejected", 0)) + 1
            measurement["silence_reason"] = R_TRANSPORT
            measurement["transport_rejection"] = tr.get("rejection_reason")
            measurements.append(measurement)
            _bounded_append(st.measurement_history, measurement, cfg.history_limit)
            st.last_receipt = measurement
            continue

        measurement["emitted"] = True
        measurement["emission_id"] = tr["emission_id"]
        measurement["source_id"] = src_id
        measurement["anonymous_band_vector"] = bands
        st.counters["emissions"] = int(st.counters.get("emissions", 0)) + 1

        emission = {
            "receipt_kind": RECEIPT_KIND,
            "emission_id": tr["emission_id"],
            "source_id": src_id,
            "emission_tick": te,
            "measurement_id": mid,
            "response_key": response_key,
            "episode_id": episode_id,
            "entity_id": entity_id,
            "entity_kind": entity_kind,
            "body_slot": receipt.get("body_slot"),
            "contact_point": [sx, sy, sz],
            "source_z": float(sz),
            "position_policy": pos_policy,
            "position_fallback": bool(pos_fallback),
            "impulse_magnitude": float(impulse),
            "effective_mass": receipt.get("effective_mass"),
            "ke_before": receipt.get("ke_before"),
            "ke_after": receipt.get("ke_after"),
            "dissipated_energy": float(e_diss),
            "acoustic_coupling": float(cfg.acoustic_coupling),
            "impulse_epsilon": float(cfg.impulse_epsilon),
            "energy_epsilon": float(cfg.energy_epsilon),
            "max_emitted_energy": float(cfg.max_emitted_energy),
            "unclamped_energy": float(unclamped),
            "emitted_energy": float(energy),
            "clamped": bool(unclamped > energy + 1e-12),
            "anonymous_band_vector": bands,
            "band_profile": BAND_PROFILE_NAME,
            "energy_law": ENERGY_LAW,
            "mechanism": MECHANISM_ID,
            "profile_version": PROFILE_VERSION,
            "architecture_stage": ARCHITECTURE_STAGE,
            "preset": "ACANTHOSTEGA_BETA4_VERTICAL_IMPACT_ACOUSTIC_EMISSION",
            "mechanical_energy_withdrawn": False,
            "agent_work_credit": False,
            "global_conservation_claim": False,
            "human_playback": False,
            "transport_emission_tick": tr.get("emission_tick"),
            "transport_expiry_tick": tr.get("expiry_tick"),
            "lps_enqueue_status": tr.get("status"),
            "limitations": [LIMITATION_LPS_2D, LIMITATION_COUPLED_3D],
            **RESEARCHER_FLAGS,
        }
        emissions.append(emission)
        measurements.append(measurement)
        _bounded_append(st.measurement_history, measurement, cfg.history_limit)
        _bounded_append(st.emission_history, emission, cfg.history_limit)
        st.last_receipt = emission

    if len(st.processed_response_keys) > DEDUP_BOUND:
        keep = {
            k
            for k in st.processed_response_keys
            if f":{int(te)}" in k or f":{int(te) - 1}" in k
        }
        st.processed_response_keys = (
            keep if keep else set(list(st.processed_response_keys)[-512:])
        )

    st.last_processed_tick = te
    st.last_step = {
        "event": EVENT_STEP,
        "tick": te,
        "measurements": measurements,
        "emissions": emissions,
        "banner": BANNER,
        "human_playback_implemented": False,
        **RESEARCHER_FLAGS,
    }
    world.last_vertical_impact_acoustic_step = st.last_step
    return {"enabled": True, "status": "PROCESSED", **st.last_step}


def serialize_state(st: VerticalImpactAcousticEmissionState | None) -> dict[str, Any] | None:
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
        "last_receipt": dict(st.last_receipt) if st.last_receipt else None,
        "banner": BANNER,
        **RESEARCHER_FLAGS,
    }


def restore_state(
    world: Any, data: dict[str, Any] | None, config: Any
) -> VerticalImpactAcousticEmissionState | None:
    """Restore processed keys; never replay emission or re-enqueue LPS."""
    if not vertical_impact_acoustic_emission_is_active(config):
        world.vertical_impact_acoustic_emission_state = None
        return None
    if not isinstance(data, dict) or not data:
        world.vertical_impact_acoustic_emission_state = None
        return ensure_vertical_impact_acoustic_emission_for_runtime(world, config)
    if str(data.get("schema_version")) != STATE_SCHEMA:
        raise ValueError(
            f"unknown vertical impact acoustic state schema: {data.get('schema_version')}"
        )
    cfg = VerticalImpactAcousticEmissionConfig.from_dict(
        config.vertical_impact_acoustic_emission.to_dict()
    )
    validate_config(cfg)
    alloc = data.get("measurement_allocator") or {}
    st = VerticalImpactAcousticEmissionState(
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
        last_receipt=dict(data["last_receipt"]) if data.get("last_receipt") else None,
    )
    world.vertical_impact_acoustic_emission_state = st
    return st


def researcher_summary(world: Any) -> dict[str, Any] | None:
    st = state_of(world)
    if st is None:
        return None
    last = dict(st.last_receipt) if st.last_receipt else None
    return {
        "mechanism": MECHANISM_ID,
        "profile_version": PROFILE_VERSION,
        "architecture_stage": ARCHITECTURE_STAGE,
        "receipt_kind": RECEIPT_KIND,
        "counters": dict(st.counters),
        "last_receipt": last,
        "last_step": dict(st.last_step) if st.last_step else None,
        "human_playback_implemented": False,
        "band_profile": BAND_PROFILE_NAME,
        "energy_law": ENERGY_LAW,
        "banner": BANNER,
        "limitations": [LIMITATION_LPS_2D, LIMITATION_COUPLED_3D],
        **RESEARCHER_FLAGS,
    }
