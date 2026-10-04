"""Acanthostega body/ResourceObject IMPACT acoustic emission.

ONLY in ACANTHOSTEGA_PHASE_B_OBJECT_IMPACT_ACOUSTICS. Connects measured body/object
contact RESPONSE (impulse + pairwise KE dissipation) to the existing Local Physical
Signal Transport. Does NOT duplicate transport. Does NOT change impulse physics.

Branch merge (LOCKED): starts from body_object_impulse_config, also enables
OSC_EMIT transport + body-body Audio B + this impact acoustic mechanism.

    body/object contact RESPONSE receipt
    -> impulse_transferred + APPROACHING + |j| > epsilon + E_acoustic > 0
    -> E_dissipated = max(0, ke_pair_pre - ke_pair_post)   [actual post-clamp KE]
    -> E_acoustic = clamp(coupling * E_dissipated, 0, E_max)
    -> uniform broadband anonymous band vector (import broadband_bands from Audio B)
    -> local_physical_signal_transport.emit_local_physical_signal
    -> delayed, attenuated anonymous osc_l_* / osc_r_* at listeners

Near-elastic impacts (E_dissipated == 0) are SILENT by design (dissipation-only;
no impulse*closing-speed proxy). Acoustic energy is NOT withdrawn from mechanics
(same Audio B V1 energy contract). Boolean contact / resting / separating /
correction-only / grasp/release/combine/deposition never sound.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from mechanistic_mind.physical_system.physical_contact_acoustic_emission import (
    BAND_PROFILE,
    broadband_bands,
    toroidal_midpoint,
)

MECHANISM_ID = "body_resource_object_impact_acoustic_emission"
PROFILE_VERSION = "BODY_OBJECT_IMPACT_ACOUSTIC_PROFILE_V1"
STATE_SCHEMA = "BODY_OBJECT_IMPACT_ACOUSTIC_STATE_V1"
ENERGY_LAW = "DISSIPATED_PAIRWISE_KE_TO_ACOUSTIC_ENERGY_V1"
BAND_PROFILE_NAME = BAND_PROFILE  # UNIFORM_BROADBAND_V1 (imported, not copied)
POSITION_DERIVATION = "CONTACT_POINT_FROM_CONTACT_FACT_MEASUREMENT_V1"
POSITION_FALLBACK = "TOROIDAL_MIDPOINT_OF_BODY_OBJECT_CENTRES_V1"
EMISSION_RECEIPT = "BODY_RESOURCE_OBJECT_IMPACT_ACOUSTIC_EMISSION"
MEASUREMENT_RECEIPT = "BODY_RESOURCE_OBJECT_IMPACT_ACOUSTIC_MEASUREMENT"
EVENT_STEP = "BODY_RESOURCE_OBJECT_IMPACT_ACOUSTIC_STEP"
NOT_AVAILABLE = "NOT_AVAILABLE"

# Silence reasons
R_NO_IMPULSE = "NO_IMPULSE_TRANSFERRED"
R_NOT_APPROACHING = "NOT_APPROACHING"
R_BELOW_EPSILON = "IMPULSE_BELOW_EPSILON"
R_NO_DISSIPATION = "NO_DISSIPATED_ENERGY"
R_ALREADY = "ALREADY_PROCESSED"
R_TRANSPORT = "TRANSPORT_REJECTED"
R_ZERO_ENERGY = "ACOUSTIC_ENERGY_ZERO"

# Calibration note: impulse_epsilon mirrors Audio B (0.04 momentum units =
# mass * cells/tick). Body/object j is the same scalar unit family; near-threshold
# soft contacts stay silent identically. acoustic_coupling is energy-per-energy
# (dimensionless relative to KE units) rather than Audio B's energy-per-momentum.
DEFAULT_IMPULSE_EPSILON = 0.04
DEFAULT_ACOUSTIC_COUPLING = 1.0
DEFAULT_MAX_ACOUSTIC_ENERGY = 2.5

RESEARCHER_FLAGS = {
    "semantic_label": False,
    "semantic_sound_class": False,
    "material_dependent": False,
    "agent_accessible": False,
    "researcher_only": True,
    "direct_delivery": False,
}


@dataclass
class BodyObjectImpactAcousticConfig:
    """Acanthostega body/object impact-acoustic profile. Fresh default OFF; absent = OFF."""

    enabled: bool = False
    impulse_epsilon: float = DEFAULT_IMPULSE_EPSILON
    acoustic_coupling: float = DEFAULT_ACOUSTIC_COUPLING
    max_acoustic_energy: float = DEFAULT_MAX_ACOUSTIC_ENERGY
    history_limit: int = 32

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "impulse_epsilon": float(self.impulse_epsilon),
            "acoustic_coupling": float(self.acoustic_coupling),
            "max_acoustic_energy": float(self.max_acoustic_energy),
            "history_limit": int(self.history_limit),
            "profile_version": PROFILE_VERSION,
            "energy_law": ENERGY_LAW,
            "band_profile": BAND_PROFILE_NAME,
            "position_derivation": POSITION_DERIVATION,
            "mechanical_energy_withdrawn": False,
            "near_elastic_policy": "SILENCE_WHEN_DISSIPATION_ZERO",
            "calibration_note": (
                "impulse_epsilon mirrors Audio B (0.04 mass*cells/tick); "
                "coupling is KE->acoustic (default 1.0); dissipation-only source"
            ),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "BodyObjectImpactAcousticConfig":
        if not isinstance(data, dict) or not data:
            return cls(enabled=False)
        for key, expected in (
            ("profile_version", PROFILE_VERSION),
            ("energy_law", ENERGY_LAW),
            ("band_profile", BAND_PROFILE_NAME),
        ):
            val = data.get(key)
            if val is not None and str(val) != expected:
                raise ValueError(f"unknown body/object impact acoustic {key}: {val}")
        return cls(
            enabled=bool(data.get("enabled", False)),
            impulse_epsilon=float(data.get("impulse_epsilon", DEFAULT_IMPULSE_EPSILON)),
            acoustic_coupling=float(data.get("acoustic_coupling", DEFAULT_ACOUSTIC_COUPLING)),
            max_acoustic_energy=float(data.get("max_acoustic_energy", DEFAULT_MAX_ACOUSTIC_ENERGY)),
            history_limit=int(data.get("history_limit", 32)),
        )


def validate_config(cfg: BodyObjectImpactAcousticConfig) -> None:
    eps = float(cfg.impulse_epsilon)
    c = float(cfg.acoustic_coupling)
    emax = float(cfg.max_acoustic_energy)
    if not all(math.isfinite(v) for v in (eps, c, emax)):
        raise ValueError("body/object impact acoustic parameters must be finite")
    if not (eps > 0.0):
        raise ValueError("impulse_epsilon must be > 0")
    if not (0.0 < c <= 100.0):
        raise ValueError("acoustic_coupling must be in (0, 100]")
    if not (0.0 < emax <= 16.0):
        raise ValueError("max_acoustic_energy must be in (0, 16]")
    if not (1 <= int(cfg.history_limit) <= 256):
        raise ValueError("history_limit must be in [1, 256]")


def _line_ok(config: Any) -> bool:
    return config is not None and str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"


def body_object_impact_acoustics_is_active(config: Any) -> bool:
    if not _line_ok(config):
        return False
    cfg = getattr(config, "body_resource_object_impact_acoustic_emission", None)
    if cfg is None or not bool(getattr(cfg, "enabled", False)):
        return False
    from mechanistic_mind.physical_system.local_physical_signal_transport import (
        local_physical_signal_transport_is_active,
    )
    return bool(local_physical_signal_transport_is_active(config))


def set_body_object_impact_acoustics(config: Any, enabled: bool) -> None:
    if config is None:
        return
    on = bool(enabled) and _line_ok(config)
    cur = getattr(config, "body_resource_object_impact_acoustic_emission", None)
    if cur is None:
        if on:
            config.body_resource_object_impact_acoustic_emission = BodyObjectImpactAcousticConfig(
                enabled=True
            )
        return
    cur.enabled = on


def catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "config_path": "body_resource_object_impact_acoustic_emission.enabled",
        "enabled": bool(enabled),
        "scientific_status": "IMPLEMENTED",
        "promotion_class": "EXPERIMENTAL",
        "description": (
            "Acanthostega body/ResourceObject impact acoustics: a measured approaching "
            "impulse with pairwise KE dissipation above epsilon becomes a bounded broadband "
            "physical emission in the existing local physical signal transport. Contact fact "
            "alone, resting, separating, correction-only and near-elastic (zero dissipation) "
            "impacts are silent. No material timbre; mechanical energy not withdrawn."
        ),
    }


# ---------------------------------------------------------------------------
# Pure physics helpers
# ---------------------------------------------------------------------------


def dissipated_pairwise_ke(ke_pre: Any, ke_post: Any) -> float:
    """E_dissipated = max(0, ke_pair_pre - ke_pair_post) from actual post-clamp KE."""
    try:
        pre = float(ke_pre)
        post = float(ke_post)
    except (TypeError, ValueError):
        return 0.0
    if not (math.isfinite(pre) and math.isfinite(post)):
        return 0.0
    return float(max(0.0, pre - post))


def acoustic_energy_from_dissipation(
    e_dissipated: float, cfg: BodyObjectImpactAcousticConfig
) -> tuple[float, float]:
    """(unclamped, emitted). Dissipation-only; zero dissipation -> (0, 0)."""
    d = float(e_dissipated)
    if not math.isfinite(d) or d <= 0.0:
        return 0.0, 0.0
    raw = float(cfg.acoustic_coupling) * d
    return raw, float(min(max(raw, 0.0), float(cfg.max_acoustic_energy)))


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


def _zero_counters() -> dict[str, int]:
    return {
        "responses_observed": 0,
        "impulses_eligible": 0,
        "silent_no_impulse": 0,
        "silent_not_approaching": 0,
        "silent_below_epsilon": 0,
        "silent_no_dissipation": 0,
        "silent_zero_energy": 0,
        "emissions": 0,
        "transport_rejected": 0,
        "reprocess_suppressed": 0,
        "already_processed": 0,
    }


@dataclass
class BodyObjectImpactAcousticState:
    config: BodyObjectImpactAcousticConfig
    processed_response_keys: set[str] = field(default_factory=set)
    measure_tick: int = -1
    measure_next: int = 0
    last_processed_tick: int = -1
    counters: dict[str, int] = field(default_factory=_zero_counters)
    measurement_history: list[dict[str, Any]] = field(default_factory=list)
    emission_history: list[dict[str, Any]] = field(default_factory=list)
    dissipation_energy_samples: list[list[float]] = field(default_factory=list)
    last_step: dict[str, Any] = field(default_factory=dict)


def state_of(world: Any) -> BodyObjectImpactAcousticState | None:
    raw = getattr(world, "body_object_impact_acoustic_state", None)
    return raw if isinstance(raw, BodyObjectImpactAcousticState) else None


def ensure_body_object_impact_acoustics_for_runtime(
    world: Any, config: Any
) -> BodyObjectImpactAcousticState | None:
    if world is None:
        return None
    if not body_object_impact_acoustics_is_active(config):
        if getattr(world, "body_object_impact_acoustic_state", None) is not None:
            world.body_object_impact_acoustic_state = None
        return None
    cur = state_of(world)
    if cur is not None:
        return cur
    cfg = BodyObjectImpactAcousticConfig.from_dict(
        config.body_resource_object_impact_acoustic_emission.to_dict()
    )
    validate_config(cfg)
    world.body_object_impact_acoustic_state = BodyObjectImpactAcousticState(config=cfg)
    return world.body_object_impact_acoustic_state


def _bounded_append(rows: list, item: Any, limit: int) -> None:
    rows.append(item)
    if len(rows) > int(limit):
        del rows[: len(rows) - int(limit)]


def _alloc_measurement(st: BodyObjectImpactAcousticState, te: int) -> str:
    if int(st.measure_tick) != int(te):
        st.measure_tick, st.measure_next = int(te), 0
    seq = int(st.measure_next)
    st.measure_next = seq + 1
    return f"impact-acoustic-{int(te):09d}-{seq:04d}"


def _impulse_step(world: Any) -> dict[str, Any] | None:
    """Prefer world.last_body_object_impulse_step alias, then contact_impulse_step, then state."""
    for attr in (
        "last_body_object_impulse_step",
        "last_body_object_contact_impulse_step",
    ):
        step = getattr(world, attr, None)
        if isinstance(step, dict):
            return step
    try:
        from mechanistic_mind.physical_system.body_resource_object_contact_impulse import (
            state_of as impulse_state_of,
        )
        st = impulse_state_of(world)
        if st is not None and isinstance(st.last_step, dict):
            return st.last_step
    except Exception:
        pass
    return None


def _lookup_contact_point(
    world: Any, *, episode_id: str, pair_key: str, body_id: str, object_id: str
) -> tuple[list[float] | None, str]:
    """Prefer contact_point from contact-fact begin/persist rows matching episode/pair."""
    step = getattr(world, "last_body_object_contact_step", None)
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
        if (
            str(row.get("body_id") or "") == str(body_id)
            and str(row.get("object_id") or "") == str(object_id)
        ):
            cp = row.get("contact_point")
            if isinstance(cp, (list, tuple)) and len(cp) >= 2:
                return [float(cp[0]), float(cp[1])], str(
                    row.get("contact_point_policy") or POSITION_DERIVATION
                )
    return None, "CONTACT_POINT_NOT_FOUND"


def _body_object_centres(
    world: Any, body_id: str, object_id: str
) -> tuple[float, float, float, float] | None:
    """Prefer contact-fact body_pose/object_pose (pre-mutation geometry); else live poses."""
    body_xy = None
    obj_xy = None
    step = getattr(world, "last_body_object_contact_step", None)
    if isinstance(step, dict):
        for row in list(step.get("begin") or []) + list(step.get("persist") or []):
            if str(row.get("body_id") or "") != str(body_id):
                continue
            if object_id and str(row.get("object_id") or "") not in ("", str(object_id)):
                continue
            bp = row.get("body_pose") or row.get("body_end_pose")
            op = row.get("object_pose") or row.get("object_end_pose")
            if isinstance(bp, (list, tuple)) and len(bp) >= 2:
                body_xy = (float(bp[0]), float(bp[1]))
            if isinstance(op, (list, tuple)) and len(op) >= 2:
                obj_xy = (float(op[0]), float(op[1]))
            if body_xy is not None and obj_xy is not None:
                break
    if obj_xy is None:
        for o in list(getattr(world, "resource_objects", None) or []):
            if str(getattr(o, "object_id", "")) == str(object_id):
                obj_xy = (float(o.x), float(o.y))
                break
    if body_xy is None:
        for attr in ("bodies", "agent_bodies"):
            bag = getattr(world, attr, None)
            if isinstance(bag, dict) and body_id in bag:
                b = bag[body_id]
                body_xy = (float(b.x), float(b.y))
                break
    if body_xy is None or obj_xy is None:
        return None
    return body_xy[0], body_xy[1], obj_xy[0], obj_xy[1]



def _resolve_source_position(
    world: Any, receipt: dict[str, Any]
) -> tuple[float, float, str]:
    from mechanistic_mind.physical_system import local_physical_signal_transport as lps

    height, width = lps._shape(world)
    episode_id = str(receipt.get("episode_id") or "")
    pair_key = str(receipt.get("pair_key") or "")
    body_id = str(receipt.get("body_id") or "")
    object_id = str(receipt.get("object_id") or "")
    cp, policy = _lookup_contact_point(
        world,
        episode_id=episode_id,
        pair_key=pair_key,
        body_id=body_id,
        object_id=object_id,
    )
    if cp is not None:
        from mechanistic_mind.planet.topology import wrap_coord

        return (
            float(wrap_coord(cp[0], width)),
            float(wrap_coord(cp[1], height)),
            policy if policy else POSITION_DERIVATION,
        )
    centres = _body_object_centres(world, body_id, object_id)
    if centres is not None:
        bx, by, ox, oy = centres
        mx, my = toroidal_midpoint(bx, by, ox, oy, width, height)
        return mx, my, POSITION_FALLBACK
    # Last resort: object centre alone marked as fallback
    for o in list(getattr(world, "resource_objects", None) or []):
        if str(getattr(o, "object_id", "")) == str(object_id):
            from mechanistic_mind.planet.topology import wrap_coord

            return (
                float(wrap_coord(float(o.x), width)),
                float(wrap_coord(float(o.y), height)),
                "OBJECT_CENTRE_FALLBACK_V1",
            )
    return 0.0, 0.0, "POSITION_UNAVAILABLE"


def _eligible_impulse(receipt: dict[str, Any], cfg: BodyObjectImpactAcousticConfig) -> tuple[bool, str | None]:
    """LOCKED trigger: impulse transferred + approaching + |j| > epsilon."""
    reason = str(receipt.get("reason") or "")
    impulse_transferred = bool(receipt.get("impulse_transferred"))
    try:
        j = abs(float(receipt.get("impulse_scalar_j") or 0.0))
    except (TypeError, ValueError):
        j = 0.0
    approaching = bool(receipt.get("approaching")) or reason == "APPROACHING"
    if reason == "APPROACHING" and (impulse_transferred or j > 0.0):
        impulse_transferred = True
        approaching = True
    if not impulse_transferred and not (reason == "APPROACHING" and j > 0.0):
        return False, R_NO_IMPULSE
    if not approaching and reason != "APPROACHING":
        return False, R_NOT_APPROACHING
    if j <= float(cfg.impulse_epsilon):
        return False, R_BELOW_EPSILON
    return True, None


# ---------------------------------------------------------------------------
# One impact-acoustic pass per tick (after apply impulse, before LPS step_end)
# ---------------------------------------------------------------------------


def process_body_object_impact_acoustics(
    world: Any,
    config: Any,
    *,
    emission_tick: int,
) -> dict[str, Any]:
    """Read last impulse-step receipts; emit at most one LPS signal per response_key."""
    from mechanistic_mind.physical_system import local_physical_signal_transport as lps

    st = state_of(world)
    if st is None:
        st = ensure_body_object_impact_acoustics_for_runtime(world, config)
    if st is None:
        return {"enabled": False}
    te = int(emission_tick)
    if te <= int(st.last_processed_tick):
        st.counters["reprocess_suppressed"] += 1
        return {"enabled": True, "status": "ALREADY_PROCESSED", "tick": te}
    cfg = st.config
    step = _impulse_step(world)
    receipts = list((step or {}).get("responses") or [])
    # Deterministic: reverse-stable sort by response_key
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
        mid = _alloc_measurement(st, te)
        body_id = str(receipt.get("body_id") or "")
        object_id = str(receipt.get("object_id") or "")
        episode_id = str(receipt.get("episode_id") or "")
        pair_key = str(receipt.get("pair_key") or f"{body_id}|{object_id}")

        if response_key and response_key in st.processed_response_keys:
            st.counters["already_processed"] += 1
            measurement = {
                "receipt_kind": MEASUREMENT_RECEIPT,
                "measurement_id": mid,
                "emission_tick": te,
                "response_key": response_key,
                "body_id": body_id,
                "object_id": object_id,
                "episode_id": episode_id,
                "pair_key": pair_key,
                "emitted": False,
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
        # Prefer explicit dissipated_energy; else compute from KE fields
        if receipt.get("dissipated_energy") is not None:
            try:
                e_diss = float(receipt.get("dissipated_energy"))
            except (TypeError, ValueError):
                e_diss = dissipated_pairwise_ke(
                    receipt.get("ke_pair_pre"), receipt.get("ke_pair_post")
                )
        else:
            e_diss = dissipated_pairwise_ke(
                receipt.get("ke_pair_pre"), receipt.get("ke_pair_post")
            )
        unclamped, energy = acoustic_energy_from_dissipation(e_diss, cfg)

        measurement = {
            "receipt_kind": MEASUREMENT_RECEIPT,
            "measurement_id": mid,
            "emission_tick": te,
            "response_key": response_key,
            "body_id": body_id,
            "object_id": object_id,
            "episode_id": episode_id,
            "pair_key": pair_key,
            "impulse_scalar_j": j,
            "impulse_transferred": bool(receipt.get("impulse_transferred")),
            "reason": receipt.get("reason"),
            "approaching": bool(receipt.get("approaching")),
            "ke_pair_pre": receipt.get("ke_pair_pre"),
            "ke_pair_post": receipt.get("ke_pair_post"),
            "dissipated_energy": float(e_diss),
            "impulse_epsilon": float(cfg.impulse_epsilon),
            "acoustic_coupling": float(cfg.acoustic_coupling),
            "unclamped_energy": float(unclamped),
            "selected_acoustic_energy": float(energy),
            "emitted": False,
            "silence_reason": None,
            "energy_law": ENERGY_LAW,
            "near_elastic_policy": "SILENCE_WHEN_DISSIPATION_ZERO",
            **RESEARCHER_FLAGS,
        }

        if not ok:
            measurement["silence_reason"] = silence
            if silence == R_NO_IMPULSE:
                st.counters["silent_no_impulse"] += 1
            elif silence == R_NOT_APPROACHING:
                st.counters["silent_not_approaching"] += 1
            elif silence == R_BELOW_EPSILON:
                st.counters["silent_below_epsilon"] += 1
            if response_key:
                st.processed_response_keys.add(response_key)
            measurements.append(measurement)
            _bounded_append(st.measurement_history, measurement, cfg.history_limit)
            continue

        st.counters["impulses_eligible"] += 1
        if e_diss <= 0.0:
            # LOCKED: near-elastic with applied impulse but zero dissipation → SILENCE
            measurement["silence_reason"] = R_NO_DISSIPATION
            st.counters["silent_no_dissipation"] += 1
            if response_key:
                st.processed_response_keys.add(response_key)
            measurements.append(measurement)
            _bounded_append(st.measurement_history, measurement, cfg.history_limit)
            continue
        if energy <= 0.0:
            measurement["silence_reason"] = R_ZERO_ENERGY
            st.counters["silent_zero_energy"] += 1
            if response_key:
                st.processed_response_keys.add(response_key)
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
                "source_body_id": body_id,
                "source_body_pair": None,
                "graph_source_label": f"IMPACT:{body_id}|{object_id}",
                "cause_receipt_ref": mid,
                "motor_provenance": None,
                "mechanism": MECHANISM_ID,
            },
        )
        if response_key:
            st.processed_response_keys.add(response_key)
        if tr.get("status") != "EMITTED":
            st.counters["transport_rejected"] += 1
            measurement["silence_reason"] = R_TRANSPORT
            measurement["transport_rejection"] = tr.get("rejection_reason")
            measurements.append(measurement)
            _bounded_append(st.measurement_history, measurement, cfg.history_limit)
            continue

        measurement["emitted"] = True
        measurement["emission_id"] = tr["emission_id"]
        st.counters["emissions"] += 1
        emission = {
            "receipt_kind": EMISSION_RECEIPT,
            "emission_id": tr["emission_id"],
            "emission_tick": te,
            "measurement_id": mid,
            "response_key": response_key,
            "body_id": body_id,
            "object_id": object_id,
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
            "max_acoustic_energy": float(cfg.max_acoustic_energy),
            "unclamped_energy": float(unclamped),
            "emitted_energy": float(energy),
            "clamped": bool(unclamped > energy + 1e-12),
            "anonymous_band_vector": bands,
            "band_profile": BAND_PROFILE_NAME,
            "energy_law": ENERGY_LAW,
            "mechanism": MECHANISM_ID,
            "preset": "ACANTHOSTEGA_PHASE_B_OBJECT_IMPACT_ACOUSTICS",
            "mechanical_energy_withdrawn": False,
            "transport_emission_tick": tr.get("emission_tick"),
            "transport_expiry_tick": tr.get("expiry_tick"),
            "graph_source_label": f"IMPACT:{body_id}|{object_id}",
            **RESEARCHER_FLAGS,
        }
        emissions.append(emission)
        measurements.append(measurement)
        _bounded_append(st.measurement_history, measurement, cfg.history_limit)
        _bounded_append(st.emission_history, emission, cfg.history_limit)
        _bounded_append(st.dissipation_energy_samples, [float(e_diss), float(energy)], 256)

    # Bound processed keys
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
    world.last_body_object_impact_acoustic_step = st.last_step
    return {"enabled": True, "status": "PROCESSED", **st.last_step}


# ---------------------------------------------------------------------------
# Snapshot / restore / copy
# ---------------------------------------------------------------------------


def serialize_state(st: BodyObjectImpactAcousticState | None) -> dict[str, Any] | None:
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
) -> BodyObjectImpactAcousticState | None:
    """Missing data -> fresh state if ON; mechanism OFF (old snapshots) -> no state, no sound."""
    if not body_object_impact_acoustics_is_active(config):
        world.body_object_impact_acoustic_state = None
        return None
    if not isinstance(data, dict) or not data:
        world.body_object_impact_acoustic_state = None
        return ensure_body_object_impact_acoustics_for_runtime(world, config)
    if str(data.get("schema_version")) != STATE_SCHEMA:
        raise ValueError(
            f"unknown body/object impact acoustic state schema: {data.get('schema_version')}"
        )
    saved = BodyObjectImpactAcousticConfig.from_dict(data.get("config") or {})
    cfg = BodyObjectImpactAcousticConfig.from_dict(
        config.body_resource_object_impact_acoustic_emission.to_dict()
    )
    validate_config(cfg)
    if saved.to_dict() != cfg.to_dict():
        raise ValueError("body/object impact acoustic parameters differ from the runtime config")
    alloc = data.get("measurement_allocator") or {}
    st = BodyObjectImpactAcousticState(
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
    world.body_object_impact_acoustic_state = st
    return st


def copy_state(
    st: BodyObjectImpactAcousticState | None,
) -> BodyObjectImpactAcousticState | None:
    if st is None:
        return None
    data = serialize_state(st)
    out = BodyObjectImpactAcousticState(
        config=BodyObjectImpactAcousticConfig.from_dict(data["config"])
    )
    out.processed_response_keys = set(data["processed_response_keys"])
    out.measure_tick, out.measure_next = st.measure_tick, st.measure_next
    out.last_processed_tick = st.last_processed_tick
    out.counters = dict(st.counters)
    out.measurement_history = list(st.measurement_history)
    out.emission_history = list(st.emission_history)
    out.dissipation_energy_samples = [list(r) for r in st.dissipation_energy_samples]
    return out


# ---------------------------------------------------------------------------
# Researcher views (never cognition)
# ---------------------------------------------------------------------------


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
                    "body_id",
                    "object_id",
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
        ],
        "overlay_caption": (
            "BODY/OBJECT IMPACT\n"
            "PHYSICAL IMPULSE → DISSIPATED ENERGY → LOCAL SIGNAL\n"
            "NEUTRAL BROADBAND · NO MATERIAL TIMBRE"
        ),
        **RESEARCHER_FLAGS,
    }


def overlay_payload(world: Any) -> dict[str, Any] | None:
    st = state_of(world)
    if st is None:
        return None
    return {
        "caption": (
            "BODY/OBJECT IMPACT\n"
            "PHYSICAL IMPULSE → DISSIPATED ENERGY → LOCAL SIGNAL\n"
            "NEUTRAL BROADBAND · NO MATERIAL TIMBRE"
        ),
        "emissions": list(st.emission_history[-8:]),
        "summary": researcher_summary(world),
    }
