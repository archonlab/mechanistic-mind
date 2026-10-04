"""Acanthostega physical contact acoustic emission (Audio B).

ONLY in ACANTHOSTEGA_PHASE_B_CONTACT_ACOUSTICS. First uncontrolled acoustic source:

    relative motion / PUSH
    -> existing soft contact solver (body_contact.resolve_soft_contact) and
       contact-mediated PUSH (physical_push.apply_push_through_contact)   [both UNCHANGED]
    -> measured impulse delivered to the canonical second body of the pair (solver receipts)
    -> new impulse above the contact episode's already-sounded level     (onset policy)
    -> bounded acoustic energy  E = clamp(coupling * |J_new|, 0, E_max)   if |J_new| > epsilon
    -> uniform broadband anonymous band vector (E / n per band)
    -> local_physical_signal_transport.emit_local_physical_signal        (same transport law)
    -> delayed, attenuated anonymous osc_l_* / osc_r_* at listeners.

A boolean contact never sounds on its own. No semantic sound classes, no material, no event
name reaches cognition. Acoustic energy is NOT withdrawn from the mechanical system: the
emission is a researcher-declared model abstraction outside any conservation ledger (V1).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

MECHANISM_ID = "physical_contact_acoustic_emission"
PROFILE_VERSION = "CONTACT_ACOUSTIC_PROFILE_V1"
STATE_SCHEMA = "PHYSICAL_CONTACT_ACOUSTIC_STATE_V1"
ENERGY_LAW = "LINEAR_CLAMPED_IMPULSE_TO_ACOUSTIC_ENERGY_V1"
ONSET_POLICY = "CONTACT_EPISODE_SOUNDED_IMPULSE_LEVEL_V1"
BAND_PROFILE = "UNIFORM_BROADBAND_V1"
POSITION_DERIVATION = "TOROIDAL_MIDPOINT_OF_BODY_CENTRES_AT_CONTACT_DETECTION_V1"
IMPULSE_SOURCE = "SOFT_CONTACT_SOLVER_RECEIPT_PLUS_CONTACT_PUSH_RECEIPT_V1"
EMISSION_RECEIPT = "PHYSICAL_CONTACT_ACOUSTIC_EMISSION"
MEASUREMENT_RECEIPT = "PHYSICAL_CONTACT_IMPULSE_MEASUREMENT"
EVENT_STEP = "PHYSICAL_CONTACT_ACOUSTIC_STEP"
NOT_AVAILABLE = "NOT_AVAILABLE"

R_BELOW_EPSILON = "NEW_IMPULSE_BELOW_EPSILON"
R_RESTING = "RESTING_CONTACT_NO_NEW_IMPULSE"
R_TRANSPORT = "TRANSPORT_REJECTED"

RESEARCHER_FLAGS = {
    "semantic_label": False,
    "semantic_sound_class": False,
    "material_dependent": False,
    "agent_accessible": False,
    "researcher_only": True,
    "direct_delivery": False,
}


@dataclass
class ContactAcousticConfig:
    """Acanthostega contact-acoustic profile. Fresh default OFF; absent field = OFF."""

    enabled: bool = False
    impulse_epsilon: float = 0.04        # momentum units (mass * cells/tick); solver min nonzero = 0.0375
    acoustic_coupling: float = 5.0       # energy units per momentum unit
    max_acoustic_energy: float = 2.5     # upper bound per emission (same units as OSC band energy)
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
            "onset_policy": ONSET_POLICY,
            "band_profile": BAND_PROFILE,
            "position_derivation": POSITION_DERIVATION,
            "impulse_source": IMPULSE_SOURCE,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ContactAcousticConfig":
        if not isinstance(data, dict) or not data:
            return cls(enabled=False)
        for key, expected in (("profile_version", PROFILE_VERSION), ("energy_law", ENERGY_LAW),
                              ("onset_policy", ONSET_POLICY), ("band_profile", BAND_PROFILE)):
            val = data.get(key)
            if val is not None and str(val) != expected:
                raise ValueError(f"unknown contact acoustic {key}: {val}")
        return cls(
            enabled=bool(data.get("enabled", False)),
            impulse_epsilon=float(data.get("impulse_epsilon", 0.04)),
            acoustic_coupling=float(data.get("acoustic_coupling", 5.0)),
            max_acoustic_energy=float(data.get("max_acoustic_energy", 2.5)),
            history_limit=int(data.get("history_limit", 32)),
        )


def validate_config(cfg: ContactAcousticConfig) -> None:
    eps, c, emax = float(cfg.impulse_epsilon), float(cfg.acoustic_coupling), float(cfg.max_acoustic_energy)
    if not all(math.isfinite(v) for v in (eps, c, emax)):
        raise ValueError("contact acoustic parameters must be finite")
    if not (eps > 0.0):
        raise ValueError("impulse_epsilon must be > 0 (zero impulse can never sound)")
    if not (0.0 < c <= 100.0):
        raise ValueError("acoustic_coupling must be in (0, 100]")
    if not (0.0 < emax <= 16.0):
        raise ValueError("max_acoustic_energy must be in (0, 16]")
    if not (1 <= int(cfg.history_limit) <= 256):
        raise ValueError("history_limit must be in [1, 256]")


def _line_ok(config: Any) -> bool:
    return config is not None and str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"


def physical_contact_acoustic_emission_is_active(config: Any) -> bool:
    if not _line_ok(config):
        return False
    cfg = getattr(config, "physical_contact_acoustic_emission", None)
    if cfg is None or not bool(getattr(cfg, "enabled", False)):
        return False
    from mechanistic_mind.physical_system.local_physical_signal_transport import (
        local_physical_signal_transport_is_active,
    )
    return bool(local_physical_signal_transport_is_active(config))  # needs the existing transport


def set_physical_contact_acoustic_emission(config: Any, enabled: bool) -> None:
    if config is None:
        return
    on = bool(enabled) and _line_ok(config)
    cur = getattr(config, "physical_contact_acoustic_emission", None)
    if cur is None:
        if on:
            config.physical_contact_acoustic_emission = ContactAcousticConfig(enabled=True)
        return  # OFF with no config: field stays absent (every earlier preset)
    cur.enabled = on


# ---------------------------------------------------------------------------
# Pure physics helpers
# ---------------------------------------------------------------------------


def acoustic_energy(impulse_magnitude: float, cfg: ContactAcousticConfig) -> tuple[float, float]:
    """(unclamped, emitted). Monotone non-decreasing, >= 0, bounded; |J| <= epsilon -> 0."""
    j = float(impulse_magnitude)
    if not math.isfinite(j) or j <= float(cfg.impulse_epsilon):
        return 0.0, 0.0
    raw = float(cfg.acoustic_coupling) * j
    return raw, float(min(max(raw, 0.0), float(cfg.max_acoustic_energy)))


def broadband_bands(energy: float, n_bands: int) -> list[float]:
    """UNIFORM_BROADBAND_V1: an impulse is a broadband transient in the uniform medium; the
    energy is shared equally by the anonymous bands. No event class, material or identity."""
    n = max(1, int(n_bands))
    return [float(energy) / n] * n


def toroidal_midpoint(ax: float, ay: float, bx: float, by: float, width: int, height: int) -> tuple[float, float]:
    from mechanistic_mind.planet.topology import toroidal_delta, wrap_coord

    dx = toroidal_delta(float(ax), float(bx), int(width))
    dy = toroidal_delta(float(ay), float(by), int(height))
    return float(wrap_coord(float(ax) + 0.5 * dx, int(width))), float(wrap_coord(float(ay) + 0.5 * dy, int(height)))


def _norm(v: tuple[float, float] | list[float]) -> float:
    return float(math.hypot(float(v[0]), float(v[1])))


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


def _zero_counters() -> dict[str, int]:
    return {
        "contact_pairs_observed": 0, "impulses_measured": 0, "silent_below_epsilon": 0,
        "silent_resting_contact": 0, "emissions": 0, "push_contributions": 0,
        "contact_onsets": 0, "separations": 0, "transport_rejected": 0,
        "reprocess_suppressed": 0, "duplicate_pair_suppressed": 0,
    }


@dataclass
class ContactAcousticState:
    config: ContactAcousticConfig
    sounded_level: dict[str, float] = field(default_factory=dict)  # canonical pair -> level (in contact)
    measure_tick: int = -1
    measure_next: int = 0
    last_processed_tick: int = -1
    counters: dict[str, int] = field(default_factory=_zero_counters)
    measurement_history: list[dict[str, Any]] = field(default_factory=list)
    emission_history: list[dict[str, Any]] = field(default_factory=list)
    impulse_energy_samples: list[list[float]] = field(default_factory=list)  # [J_new, E] (bounded)
    last_step: dict[str, Any] = field(default_factory=dict)


def state_of(world: Any) -> ContactAcousticState | None:
    raw = getattr(world, "contact_acoustic_state", None)
    return raw if isinstance(raw, ContactAcousticState) else None


def ensure_contact_acoustics_for_runtime(world: Any, config: Any) -> ContactAcousticState | None:
    if world is None:
        return None
    if not physical_contact_acoustic_emission_is_active(config):
        if getattr(world, "contact_acoustic_state", None) is not None:
            world.contact_acoustic_state = None
        return None
    cur = state_of(world)
    if cur is not None:
        return cur
    cfg = ContactAcousticConfig.from_dict(config.physical_contact_acoustic_emission.to_dict())
    validate_config(cfg)
    world.contact_acoustic_state = ContactAcousticState(config=cfg)
    return world.contact_acoustic_state


def _bounded_append(rows: list, item: Any, limit: int) -> None:
    rows.append(item)
    if len(rows) > int(limit):
        del rows[: len(rows) - int(limit)]


def _alloc_measurement(st: ContactAcousticState, te: int) -> str:
    if int(st.measure_tick) != int(te):
        st.measure_tick, st.measure_next = int(te), 0
    seq = int(st.measure_next)
    st.measure_next = seq + 1
    return f"contact-impulse-{int(te):09d}-{seq:04d}"


def capture_pre_contact(bodies: list[tuple[str, Any]]) -> dict[str, tuple[float, float, float, float]]:
    """Read-only pose/velocity snapshot taken after body integration, before contact resolution."""
    return {str(b): (float(body.x), float(body.y), float(getattr(body, "vx", 0.0) or 0.0),
                     float(getattr(body, "vy", 0.0) or 0.0)) for b, body in bodies}


# ---------------------------------------------------------------------------
# One contact-acoustic pass per tick (after the whole contact/PUSH loop, before transport step)
# ---------------------------------------------------------------------------


def process_contact_pairs(
    world: Any,
    config: Any,
    rows: list[dict[str, Any]],
    *,
    emission_tick: int,
    pre_contact: dict[str, tuple[float, float, float, float]] | None = None,
) -> dict[str, Any]:
    """rows: one per solved body pair with keys a_id, b_id, mass_a, mass_b, contact_receipt,
    push_receipt (the unchanged solver receipts). Order of rows / of a,b inside a row does not
    matter: pairs are canonicalised (sorted body ids) and processed in canonical order.
    At most one acoustic emission per canonical pair per tick."""
    from mechanistic_mind.physical_system import local_physical_signal_transport as lps

    st = state_of(world)
    if st is None:
        return {"enabled": False}
    te = int(emission_tick)
    if te <= int(st.last_processed_tick):
        st.counters["reprocess_suppressed"] += 1
        return {"enabled": True, "status": "ALREADY_PROCESSED", "tick": te}
    cfg = st.config
    lst = lps.state_of(world)
    n_bands = int(getattr(lst, "n_bands", 6) or 6)
    height, width = lps._shape(world)
    pre = dict(pre_contact or {})
    canon: dict[str, dict[str, Any]] = {}
    for row in rows:
        a_id, b_id = str(row["a_id"]), str(row["b_id"])
        first_is_a = a_id <= b_id
        p0, p1 = (a_id, b_id) if first_is_a else (b_id, a_id)
        key = f"{p0}|{p1}"
        if key in canon:
            st.counters["duplicate_pair_suppressed"] += 1
            continue
        side = "b" if first_is_a else "a"          # canonical second body in the solver's a/b frame
        m2 = float(row["mass_b"] if first_is_a else row["mass_a"])
        canon[key] = {"p0": p0, "p1": p1, "side": side, "m2": m2, "row": row}
    measurements: list[dict[str, Any]] = []
    emissions: list[dict[str, Any]] = []
    in_contact_now: set[str] = set()
    for key in sorted(canon):
        c = canon[key]
        rec = c["row"].get("contact_receipt") or {}
        push = c["row"].get("push_receipt") or {}
        if not bool(rec.get("contact")):
            continue
        in_contact_now.add(key)
        st.counters["contact_pairs_observed"] += 1
        side, m2 = c["side"], c["m2"]
        dv_c = rec.get(f"impulse_{side}") or [0.0, 0.0]
        j_now_vec = (m2 * float(dv_c[0]), m2 * float(dv_c[1]))      # momentum delivered to body p1
        j_now = _norm(j_now_vec)
        onset = key not in st.sounded_level
        if onset:
            st.counters["contact_onsets"] += 1
        level = float(st.sounded_level.get(key, 0.0))
        excess = max(0.0, j_now - level)
        scale = (excess / j_now) if j_now > 1e-15 else 0.0
        contact_new = (j_now_vec[0] * scale, j_now_vec[1] * scale)
        push_applied = bool(push.get("push_applied"))
        if push_applied:
            dv_p = push.get(f"impulse_{side}") or [0.0, 0.0]
            push_vec = (m2 * float(dv_p[0]), m2 * float(dv_p[1]))
            st.counters["push_contributions"] += 1
        else:
            push_vec = (0.0, 0.0)
        new_vec = (contact_new[0] + push_vec[0], contact_new[1] + push_vec[1])
        j_new = _norm(new_vec)
        unclamped, energy = acoustic_energy(j_new, cfg)
        mid = _alloc_measurement(st, te)
        st.counters["impulses_measured"] += 1
        pa, pb = pre.get(c["p0"]), pre.get(c["p1"])
        rel_v: Any = NOT_AVAILABLE
        rel_vn: Any = NOT_AVAILABLE
        if pa is not None and pb is not None:
            from mechanistic_mind.planet.topology import toroidal_delta

            dx = toroidal_delta(pa[0], pb[0], width)
            dy = toroidal_delta(pa[1], pb[1], height)
            dist = math.hypot(dx, dy)
            rel_v = [pb[2] - pa[2], pb[3] - pa[3]]
            rel_vn = ((rel_v[0] * dx + rel_v[1] * dy) / dist) if dist > 1e-12 else NOT_AVAILABLE
        measurement = {
            "receipt_kind": MEASUREMENT_RECEIPT,
            "measurement_id": mid,
            "emission_tick": te,
            "canonical_body_pair": [c["p0"], c["p1"]],
            "contact_detected": True,
            "contact_onset": onset,
            "overlap_cells": len(rec.get("overlap_cells") or []),
            "com_distance": rec.get("com_distance", NOT_AVAILABLE),
            "contact_impulse_vector": [float(j_now_vec[0]), float(j_now_vec[1])],
            "contact_impulse_magnitude": j_now,
            "sounded_level_before": level,
            "new_contact_impulse_magnitude": excess,
            "push_applied": push_applied,
            "push_impulse_vector": [float(push_vec[0]), float(push_vec[1])],
            "push_impulse_magnitude": _norm(push_vec),
            "new_impulse_vector": [float(new_vec[0]), float(new_vec[1])],
            "new_impulse_magnitude": j_new,
            "relative_velocity_pre_contact": rel_v,
            "relative_normal_velocity_pre_contact": rel_vn,
            "impulse_units": "mass * cells/tick (solver momentum, pre velocity clamp)",
            "impulse_epsilon": float(cfg.impulse_epsilon),
            "emitted": False,
            "silence_reason": None,
            **RESEARCHER_FLAGS,
        }
        if energy <= 0.0:
            reason = R_RESTING if (not onset and excess <= 1e-15 and not push_applied) else R_BELOW_EPSILON
            measurement["silence_reason"] = reason
            st.counters["silent_resting_contact" if reason == R_RESTING else "silent_below_epsilon"] += 1
            st.sounded_level.setdefault(key, level)  # mark "in contact" (episode continues)
            measurements.append(measurement)
            _bounded_append(st.measurement_history, measurement, cfg.history_limit)
            continue
        if pa is not None and pb is not None:
            ox, oy = toroidal_midpoint(pa[0], pa[1], pb[0], pb[1], width, height)
            derivation = POSITION_DERIVATION
        else:
            ba = c["row"].get("body_a"); bb = c["row"].get("body_b")
            ox, oy = toroidal_midpoint(float(ba.x), float(ba.y), float(bb.x), float(bb.y), width, height)
            derivation = "TOROIDAL_MIDPOINT_OF_BODY_CENTRES_AFTER_RESOLUTION_V1"
        bands = broadband_bands(energy, n_bands)
        tr = lps.emit_local_physical_signal(
            world, emission_tick=te, x=ox, y=oy, band_energies=bands,
            provenance={
                "selection_provenance": lps.PROV_PHYSICAL_CONTACT,
                "source_body_id": None,                 # a contact has no single source body
                "source_body_pair": [c["p0"], c["p1"]],
                "graph_source_label": f"CONTACT:{c['p0']}|{c['p1']}",
                "cause_receipt_ref": mid,
                "motor_provenance": None,
                "mechanism": MECHANISM_ID,
            },
        )
        st.sounded_level[key] = max(level, j_now)
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
        receipt = {
            "receipt_kind": EMISSION_RECEIPT,
            "emission_id": tr["emission_id"],
            "emission_tick": te,
            "canonical_body_pair": [c["p0"], c["p1"]],
            "position": [ox, oy],
            "position_derivation": derivation,
            "contact_receipt_ref": mid,
            "contact_impulse_magnitude": j_now,
            "new_impulse_vector": [float(new_vec[0]), float(new_vec[1])],
            "new_impulse_magnitude": j_new,
            "push_impulse_magnitude": _norm(push_vec),
            "relative_velocity_pre_contact": rel_v,
            "relative_normal_velocity_pre_contact": rel_vn,
            "acoustic_coupling": float(cfg.acoustic_coupling),
            "impulse_epsilon": float(cfg.impulse_epsilon),
            "max_acoustic_energy": float(cfg.max_acoustic_energy),
            "unclamped_energy": unclamped,
            "emitted_energy": energy,
            "clamped": bool(unclamped > energy + 1e-12),
            "anonymous_band_vector": bands,
            "band_profile": BAND_PROFILE,
            "energy_law": ENERGY_LAW,
            "onset_policy": ONSET_POLICY,
            "mechanism": MECHANISM_ID,
            "preset": "ACANTHOSTEGA_PHASE_B_CONTACT_ACOUSTICS",
            "mechanical_energy_withdrawn": False,  # model abstraction: outside conservation ledger
            "transport_emission_tick": tr.get("emission_tick"),
            "transport_expiry_tick": tr.get("expiry_tick"),
            **RESEARCHER_FLAGS,
        }
        emissions.append(receipt)
        measurements.append(measurement)
        _bounded_append(st.measurement_history, measurement, cfg.history_limit)
        _bounded_append(st.emission_history, receipt, cfg.history_limit)
        _bounded_append(st.impulse_energy_samples, [j_new, energy], 256)
    # separation ends a contact episode (renewed impact can sound again)
    for key in sorted(set(st.sounded_level) - in_contact_now):
        del st.sounded_level[key]
        st.counters["separations"] += 1
    st.last_processed_tick = te
    st.last_step = {"event": EVENT_STEP, "tick": te, "measurements": measurements, "emissions": emissions}
    world.last_contact_acoustic_step = st.last_step
    return {"enabled": True, "status": "PROCESSED", **st.last_step}


# ---------------------------------------------------------------------------
# Snapshot / restore / copy
# ---------------------------------------------------------------------------


def serialize_state(st: ContactAcousticState | None) -> dict[str, Any] | None:
    if st is None:
        return None
    return {
        "schema_version": STATE_SCHEMA,
        "config": st.config.to_dict(),
        "sounded_level": {k: float(v) for k, v in sorted(st.sounded_level.items())},
        "measurement_allocator": {"tick": int(st.measure_tick), "next_sequence": int(st.measure_next)},
        "last_processed_tick": int(st.last_processed_tick),
        "counters": dict(st.counters),
        "measurement_history": list(st.measurement_history),
        "emission_history": list(st.emission_history),
        "impulse_energy_samples": [list(r) for r in st.impulse_energy_samples],
    }


def restore_state(world: Any, data: dict[str, Any] | None, config: Any) -> ContactAcousticState | None:
    """Missing data -> fresh state if ON; mechanism OFF (old snapshots) -> no state, no sound."""
    if not physical_contact_acoustic_emission_is_active(config):
        world.contact_acoustic_state = None
        return None
    if not isinstance(data, dict) or not data:
        world.contact_acoustic_state = None
        return ensure_contact_acoustics_for_runtime(world, config)
    if str(data.get("schema_version")) != STATE_SCHEMA:
        raise ValueError(f"unknown contact acoustic state schema: {data.get('schema_version')}")
    saved = ContactAcousticConfig.from_dict(data.get("config") or {})
    cfg = ContactAcousticConfig.from_dict(config.physical_contact_acoustic_emission.to_dict())
    validate_config(cfg)
    if saved.to_dict() != cfg.to_dict():
        raise ValueError("contact acoustic parameters differ from the runtime config")
    alloc = data.get("measurement_allocator") or {}
    st = ContactAcousticState(
        config=cfg,
        sounded_level={str(k): float(v) for k, v in (data.get("sounded_level") or {}).items()},
        measure_tick=int(alloc.get("tick", -1)),
        measure_next=int(alloc.get("next_sequence", 0)),
        last_processed_tick=int(data.get("last_processed_tick", -1)),
        counters={**_zero_counters(), **{k: int(v) for k, v in (data.get("counters") or {}).items()}},
        measurement_history=list(data.get("measurement_history") or []),
        emission_history=list(data.get("emission_history") or []),
        impulse_energy_samples=[list(r) for r in data.get("impulse_energy_samples") or []],
    )
    world.contact_acoustic_state = st
    return st


def copy_state(st: ContactAcousticState | None) -> ContactAcousticState | None:
    if st is None:
        return None
    data = serialize_state(st)
    out = ContactAcousticState(config=ContactAcousticConfig.from_dict(data["config"]))
    out.sounded_level = dict(data["sounded_level"])
    out.measure_tick, out.measure_next = st.measure_tick, st.measure_next
    out.last_processed_tick = st.last_processed_tick
    out.counters = dict(st.counters)
    out.measurement_history = list(st.measurement_history)
    out.emission_history = list(st.emission_history)
    out.impulse_energy_samples = [list(r) for r in st.impulse_energy_samples]
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
        "pairs_in_contact": sorted(st.sounded_level),
        "recent_emissions": [
            {k: e.get(k) for k in ("emission_id", "emission_tick", "canonical_body_pair", "position",
                                   "position_derivation", "new_impulse_magnitude", "emitted_energy",
                                   "contact_receipt_ref")}
            for e in st.emission_history[-8:]
        ],
        "labels": ["researcher-only", "not agent-accessible", "contact-impulse derived",
                   "not a semantic sound class"],
        **RESEARCHER_FLAGS,
    }


def catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "config_path": "physical_contact_acoustic_emission.enabled",
        "enabled": bool(enabled),
        "scientific_status": "IMPLEMENTED",
        "promotion_class": "EXPERIMENTAL",
        "description": (
            "Acanthostega Audio B: a measured new body-body contact impulse (existing soft contact / "
            "contact PUSH receipts) above epsilon becomes a bounded broadband physical emission in the "
            "existing local physical signal transport. Boolean contact alone is silent; resting contact "
            "is silent. No semantic sound class, material or source identity reaches cognition."
        ),
    }
