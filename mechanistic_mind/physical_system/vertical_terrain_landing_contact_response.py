"""Acanthostega Free-Space V1B · Vertical terrain landing contact + inelastic response.

Mechanism: vertical_terrain_landing_contact_response
Preset: ACANTHOSTEGA_BETA4_VERTICAL_TERRAIN_LANDING_CONTACT_RESPONSE
Parent: ACANTHOSTEGA_BETA4_FREE_SPACE_STATE_AND_PE_AUTHORITY_CONTRACT
Profile: VERTICAL_TERRAIN_LANDING_CONTACT_RESPONSE_V1
Receipt: VERTICAL_TERRAIN_LANDING_V1

Internal seam: plan → contact fact → inelastic response → atomic commit.
Replaces FGG post-step clamp when ON. Does NOT emit impact sound.
Rebound / material restitution remain deferred (e=0).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

MECHANISM_ID = "vertical_terrain_landing_contact_response"
PROFILE_VERSION = "VERTICAL_TERRAIN_LANDING_CONTACT_RESPONSE_V1"
STATE_SCHEMA = "VERTICAL_TERRAIN_LANDING_STATE_V1"
RECEIPT_KIND = "VERTICAL_TERRAIN_LANDING_V1"
ARCHITECTURE_STAGE = "FREE_SPACE_V1B_VERTICAL_TERRAIN_LANDING_CONTACT_RESPONSE"

BANNER = (
    "FREE-SPACE LANDING V1 · TERRAIN CONTACT + INELASTIC RESPONSE · "
    "e=0 · NO REBOUND · NO IMPACT SOUND · 2D BROAD PHASE"
)

RESEARCHER_FLAGS = {"researcher_only": True, "agent_accessible": False}

PHASE_BEGIN = "BEGIN"
PHASE_PERSIST = "PERSIST"
PHASE_END = "END"

NORMAL = (0.0, 0.0, 1.0)
EPS = 1e-12
APPROACH_EPS = 1e-12
HISTORY_LIMIT_DEFAULT = 64
DEDUP_HISTORY_LIMIT = 128

CLASS_NO_CONTACT = "NO_CONTACT"
CLASS_REST_PERSIST = "REST_PERSIST"
CLASS_LANDING_IMPACT = "LANDING_IMPACT"
CLASS_SEPARATING = "SEPARATING"
CLASS_START_PENETRATION = "START_PENETRATION_ANOMALY"
CLASS_INVALID_MASS = "INVALID_MASS_ANOMALY"
CLASS_SES_BELOW_SUPPORT = "SES_BELOW_SUPPORT_NO_FREE_LIFT"
CLASS_CORRECTION_CLAMPED = "CORRECTION_CLAMPED_ANOMALY"
CLASS_DEDUPED = "DEDUPED"

LIMITATION_COUPLED_3D = "COUPLED_3D_MULTI_CONTACT_NOT_RESOLVED_V1"
LIMITATION_COMMITTED_XY = "SUPPORT_EVALUATED_AT_COMMITTED_XY_NOT_SWEPT_PATH"


@dataclass
class VerticalTerrainLandingContactResponseConfig:
    enabled: bool = False
    history_limit: int = HISTORY_LIMIT_DEFAULT
    approach_eps: float = APPROACH_EPS
    rest_eps: float = EPS
    restitution: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        on = bool(self.enabled)
        return {
            "enabled": on,
            "history_limit": int(self.history_limit),
            "approach_eps": float(self.approach_eps),
            "rest_eps": float(self.rest_eps),
            "restitution": float(self.restitution),
            "profile_version": PROFILE_VERSION,
            "architecture_stage": ARCHITECTURE_STAGE,
            "receipt_kind": RECEIPT_KIND,
            "landing_normal": "VERTICAL_PLUS_Z",
            "contact_geometry": "Z_SEGMENT_AT_COMMITTED_XY",
            "rebound_implemented": False,
            "vertical_impact_sound_implemented": False,
            "old_clamp_bypassed_when_on": True,
            "banner": BANNER if on else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "VerticalTerrainLandingContactResponseConfig":
        if not isinstance(data, dict) or not data:
            return cls(enabled=False)
        ver = data.get("profile_version")
        if ver is not None and str(ver) != PROFILE_VERSION:
            raise ValueError(f"unknown vertical terrain landing profile: {ver}")
        return cls(
            enabled=bool(data.get("enabled", False)),
            history_limit=int(data.get("history_limit", HISTORY_LIMIT_DEFAULT)),
            approach_eps=float(data.get("approach_eps", APPROACH_EPS)),
            rest_eps=float(data.get("rest_eps", EPS)),
            restitution=float(data.get("restitution", 0.0)),
        )


def validate_config(cfg: VerticalTerrainLandingContactResponseConfig) -> None:
    if int(cfg.history_limit) < 1:
        raise ValueError("history_limit must be >= 1")
    if float(cfg.restitution) != 0.0:
        raise ValueError("V1 restitution must be 0")


def vertical_terrain_landing_contact_response_is_active(config: Any) -> bool:
    cfg = getattr(config, "vertical_terrain_landing_contact_response", None)
    if cfg is None:
        return False
    if isinstance(cfg, dict):
        return bool(cfg.get("enabled"))
    return bool(getattr(cfg, "enabled", False))


def set_vertical_terrain_landing_contact_response(config: Any, enabled: bool) -> None:
    on = bool(enabled)
    cur = getattr(config, "vertical_terrain_landing_contact_response", None)
    if cur is None or isinstance(cur, dict):
        cfg = VerticalTerrainLandingContactResponseConfig.from_dict(
            cur if isinstance(cur, dict) else None
        )
        cfg.enabled = on
        config.vertical_terrain_landing_contact_response = cfg
    else:
        cur.enabled = on


@dataclass
class VerticalTerrainLandingContactResponseState:
    config: VerticalTerrainLandingContactResponseConfig
    # contact_key -> episode record
    active_episodes: dict[str, dict[str, Any]] = field(default_factory=dict)
    episode_seq: int = 0
    response_dedup: list[str] = field(default_factory=list)
    history: list[dict[str, Any]] = field(default_factory=list)
    last_receipt: dict[str, Any] | None = None
    counters: dict[str, int] = field(
        default_factory=lambda: {
            "receipts": 0,
            "begin": 0,
            "persist": 0,
            "end": 0,
            "impacts": 0,
            "rest_persists": 0,
            "anomalies": 0,
            "deduped": 0,
            "old_clamp_bypassed": 0,
        }
    )


def state_of(world: Any) -> VerticalTerrainLandingContactResponseState | None:
    return getattr(world, "vertical_terrain_landing_contact_response_state", None)


def ensure_vertical_terrain_landing_contact_response_for_runtime(
    world: Any, config: Any
) -> VerticalTerrainLandingContactResponseState | None:
    if not vertical_terrain_landing_contact_response_is_active(config):
        return None
    st = state_of(world)
    if st is not None:
        return st
    raw = getattr(config, "vertical_terrain_landing_contact_response", None)
    cfg = (
        raw
        if isinstance(raw, VerticalTerrainLandingContactResponseConfig)
        else VerticalTerrainLandingContactResponseConfig.from_dict(
            raw if isinstance(raw, dict) else None
        )
    )
    cfg.enabled = True
    st = VerticalTerrainLandingContactResponseState(config=cfg)
    world.vertical_terrain_landing_contact_response_state = st
    return st


def contact_key(entity_kind: str, entity_id: str) -> str:
    return f"{str(entity_kind)}:{str(entity_id)}|terrain"


def _valid_mass(m: Any) -> bool:
    try:
        v = float(m)
    except (TypeError, ValueError):
        return False
    return bool(math.isfinite(v) and v > 0.0)


def resolve_effective_mass(
    *,
    entity_kind: str,
    entity_id: str,
    mass: float,
    world: Any | None,
    runtime_config: Any | None,
) -> tuple[float, str, bool]:
    """Return (m_eff, provenance, valid)."""
    if not _valid_mass(mass):
        return 0.0, "INVALID_MASS", False
    m = float(mass)
    prov = "RESOURCE_OBJECT_MASS" if entity_kind == "object" else "BODY_CONFIG_MASS"
    if entity_kind == "body" and world is not None and runtime_config is not None:
        try:
            from mechanistic_mind.physical_system.effector_work_and_held_load_inertia_accounting import (
                effector_work_held_load_is_active,
                total_held_mass,
            )

            if effector_work_held_load_is_active(runtime_config):
                held = float(total_held_mass(world, str(entity_id)))
                if held > 0.0 and math.isfinite(held):
                    m = m + held
                    prov = "BODY_CONFIG_MASS_PLUS_HELD_LOAD_EHL"
        except Exception:
            pass
    return float(m), prov, True


def compute_toi(z0: float, z1: float, support_z: float, eps: float) -> float | None:
    """Linear TOI for downward crossing. None if not a crossing."""
    if not (math.isfinite(z0) and math.isfinite(z1) and math.isfinite(support_z)):
        return None
    denom = float(z0) - float(z1)
    if abs(denom) <= float(eps):
        if abs(float(z0) - float(support_z)) <= float(eps):
            return 0.0
        return None
    toi = (float(z0) - float(support_z)) / denom
    if toi < 0.0:
        return 0.0
    if toi > 1.0:
        return 1.0
    return float(toi)


def plan_landing(
    *,
    tick: int,
    entity_id: str,
    entity_kind: str,
    body_slot: str | None,
    x: float,
    y: float,
    z0: float,
    vz0: float,
    z1_proposed: float,
    vz1_proposed: float,
    support_z: float,
    half_extent: float,
    mass: float,
    mass_provenance: str,
    mass_valid: bool,
    was_grounded: bool,
    skip_gravity: bool,
    gravity_applied: bool,
    ses_below_support: bool,
    max_vz: float,
    dt: float,
    cfg: VerticalTerrainLandingContactResponseConfig,
) -> dict[str, Any]:
    eps = float(cfg.rest_eps)
    approach_eps = float(cfg.approach_eps)
    key = contact_key(entity_kind, entity_id)
    centre0 = float(z0) + float(half_extent)
    centre1 = float(z1_proposed) + float(half_extent)
    penetration = max(0.0, float(support_z) - float(z1_proposed))
    max_corr = abs(float(max_vz)) * abs(float(dt)) + eps
    correction_clamped = bool(penetration > max_corr + eps)

    resting = (
        bool(was_grounded)
        and abs(float(z0) - float(support_z)) <= eps
        and abs(float(vz0)) <= eps
        and abs(float(z1_proposed) - float(support_z)) <= eps
        and abs(float(vz1_proposed)) <= eps
    ) or (
        bool(skip_gravity)
        and abs(float(z0) - float(support_z)) <= eps
        and abs(float(vz0)) <= eps
    )

    separating = float(vz1_proposed) > approach_eps and float(z1_proposed) > float(support_z) + eps
    above = float(z1_proposed) > float(support_z) + eps
    start_pen = float(z0) < float(support_z) - eps
    downward_cross = (
        float(z0) > float(support_z) + eps
        and float(z1_proposed) <= float(support_z) + eps
    )
    at_support_approach = (
        abs(float(z1_proposed) - float(support_z)) <= eps and float(vz1_proposed) < -approach_eps
    )
    approaching = float(vz1_proposed) < -approach_eps

    toi = None
    crossing = False
    classification = CLASS_NO_CONTACT
    anomaly: str | None = None

    if not mass_valid:
        classification = CLASS_INVALID_MASS
        anomaly = CLASS_INVALID_MASS
    elif resting:
        classification = CLASS_REST_PERSIST
        crossing = True
        toi = 0.0
    elif separating:
        classification = CLASS_SEPARATING
    elif above and not downward_cross:
        classification = CLASS_NO_CONTACT
    elif start_pen and not was_grounded:
        # Unsupported body with feet already below finite support.
        # Deep / falling cases are contact violations (tunnel or open-bottom re-entry)
        # and must recover via START_PENETRATION. A shallow non-approaching gap keeps
        # the SES free-lift lock so horizontal PE snaps remain unpaid.
        deep_escape = bool(penetration > max_corr + eps)
        if ses_below_support and (not approaching) and (not deep_escape):
            classification = CLASS_SES_BELOW_SUPPORT
            anomaly = CLASS_SES_BELOW_SUPPORT
        else:
            classification = CLASS_START_PENETRATION
            anomaly = CLASS_START_PENETRATION
            crossing = True
            toi = 0.0
    elif ses_below_support and start_pen:
        # Preserve SES free-lift lock when start_pen coincides with other grounded paths.
        classification = CLASS_SES_BELOW_SUPPORT
        anomaly = CLASS_SES_BELOW_SUPPORT
    elif (downward_cross or at_support_approach or (penetration > eps and approaching)) and approaching:
        classification = CLASS_LANDING_IMPACT
        crossing = True
        toi = compute_toi(z0, z1_proposed, support_z, eps)
        if toi is None:
            toi = 1.0
    elif penetration > eps and not approaching:
        # At/below support without approach — treat as rest-like correction without impact KE.
        classification = CLASS_REST_PERSIST if abs(vz1_proposed) <= approach_eps else CLASS_START_PENETRATION
        crossing = True
        toi = 0.0
        if classification == CLASS_START_PENETRATION:
            anomaly = CLASS_START_PENETRATION

    if correction_clamped and classification == CLASS_LANDING_IMPACT:
        anomaly = CLASS_CORRECTION_CLAMPED

    response_planned = classification == CLASS_LANDING_IMPACT and mass_valid and not ses_below_support
    support_planned = classification in (CLASS_LANDING_IMPACT, CLASS_REST_PERSIST) and not ses_below_support
    if classification == CLASS_START_PENETRATION:
        # Bounded correction only; no fabricated impact energy.
        support_planned = True
        response_planned = False

    m_eff = float(mass) if mass_valid else 0.0
    ke_before = 0.5 * m_eff * float(vz1_proposed) * float(vz1_proposed) if mass_valid else 0.0
    j = (-m_eff * float(vz1_proposed)) if response_planned else 0.0
    vz_after = 0.0 if (response_planned or support_planned) else float(vz1_proposed)
    z_after = float(support_z) if support_planned else float(z1_proposed)
    if support_planned and correction_clamped:
        # Conservative: still place at support (safe), mark anomaly.
        z_after = float(support_z)
        vz_after = 0.0

    ke_after = 0.5 * m_eff * float(vz_after) * float(vz_after) if mass_valid else 0.0
    e_diss = max(0.0, ke_before - ke_after) if response_planned else 0.0

    return {
        "tick": int(tick),
        "entity_id": str(entity_id),
        "entity_kind": str(entity_kind),
        "body_slot": body_slot,
        "contact_key": key,
        "x": float(x),
        "y": float(y),
        "z0": float(z0),
        "centre_z0": float(centre0),
        "vz0": float(vz0),
        "z1_proposed": float(z1_proposed),
        "centre_z1_proposed": float(centre1),
        "vz1_proposed": float(vz1_proposed),
        "support_z": float(support_z),
        "vertical_half_extent": float(half_extent),
        "crossing": bool(crossing),
        "classification": classification,
        "approach": bool(approaching),
        "toi": toi,
        "contact_point": [float(x), float(y), float(support_z)] if crossing else None,
        "normal": list(NORMAL),
        "penetration": float(penetration),
        "mass_eff": float(m_eff),
        "mass_provenance": mass_provenance,
        "mass_valid": bool(mass_valid),
        "ke_before": float(ke_before),
        "ke_after_planned": float(ke_after),
        "e_dissipated_planned": float(e_diss),
        "impulse_planned": float(j),
        "vz_after_planned": float(vz_after),
        "z_after_planned": float(z_after),
        "response_planned": bool(response_planned),
        "support_planned": bool(support_planned),
        "rebound_planned": False,
        "correction": float(penetration) if support_planned else 0.0,
        "max_correction": float(max_corr),
        "correction_clamped": bool(correction_clamped),
        "anomaly": anomaly,
        "was_grounded": bool(was_grounded),
        "skip_gravity": bool(skip_gravity),
        "gravity_applied": bool(gravity_applied),
        "ses_below_support": bool(ses_below_support),
        "limitations": [LIMITATION_COMMITTED_XY, LIMITATION_COUPLED_3D],
        "restitution": 0.0,
        "old_clamp_bypassed": True,
    }


def _allocate_episode_id(st: VerticalTerrainLandingContactResponseState, tick: int) -> str:
    st.episode_seq = int(st.episode_seq) + 1
    return f"vtl-{int(tick):06d}-{int(st.episode_seq):04d}"


def _update_episode(
    st: VerticalTerrainLandingContactResponseState,
    plan: dict[str, Any],
) -> tuple[str | None, str | None, bool]:
    """Return (episode_id, phase, is_new_begin)."""
    key = str(plan["contact_key"])
    tick = int(plan["tick"])
    cls = str(plan["classification"])
    active = st.active_episodes.get(key)

    if cls in (CLASS_NO_CONTACT, CLASS_SEPARATING, CLASS_SES_BELOW_SUPPORT):
        if active is not None:
            eid = str(active["episode_id"])
            del st.active_episodes[key]
            st.counters["end"] = int(st.counters.get("end", 0)) + 1
            return eid, PHASE_END, False
        return None, None, False

    if cls == CLASS_REST_PERSIST or (
        cls == CLASS_LANDING_IMPACT and plan.get("support_planned")
    ) or cls == CLASS_START_PENETRATION:
        # Re-contact after flight: z0 above support while was_grounded False → new BEGIN.
        recontact = (
            cls == CLASS_LANDING_IMPACT
            and active is not None
            and not bool(plan.get("was_grounded"))
            and float(plan.get("z0", 0.0)) > float(plan.get("support_z", 0.0)) + float(st.config.rest_eps)
        )
        if recontact:
            del st.active_episodes[key]
            st.counters["end"] = int(st.counters.get("end", 0)) + 1
            active = None
        if active is None:
            if cls == CLASS_REST_PERSIST and plan.get("was_grounded"):
                # Continuity / restore-style rest: open as PERSIST without BEGIN impact semantics.
                eid = _allocate_episode_id(st, tick)
                st.active_episodes[key] = {
                    "episode_id": eid,
                    "phase": PHASE_PERSIST,
                    "begin_tick": tick,
                    "last_tick": tick,
                }
                st.counters["persist"] = int(st.counters.get("persist", 0)) + 1
                return eid, PHASE_PERSIST, False
            eid = _allocate_episode_id(st, tick)
            st.active_episodes[key] = {
                "episode_id": eid,
                "phase": PHASE_BEGIN,
                "begin_tick": tick,
                "last_tick": tick,
            }
            st.counters["begin"] = int(st.counters.get("begin", 0)) + 1
            return eid, PHASE_BEGIN, True
        active["phase"] = PHASE_PERSIST
        active["last_tick"] = tick
        st.counters["persist"] = int(st.counters.get("persist", 0)) + 1
        return str(active["episode_id"]), PHASE_PERSIST, False

    if cls == CLASS_INVALID_MASS:
        return (str(active["episode_id"]), PHASE_PERSIST, False) if active else (None, None, False)

    return None, None, False


def apply_vertical_landing(
    entity: Any,
    *,
    world: Any,
    runtime_config: Any,
    tick: int,
    entity_id: str,
    entity_kind: str,
    mass: float,
    z0: float,
    vz0: float,
    z1_proposed: float,
    vz1_proposed: float,
    support_z: float,
    was_grounded: bool,
    skip_gravity: bool,
    gravity_applied: bool,
    ses_below_support: bool,
    fgg_config: Any,
) -> dict[str, Any] | None:
    """Plan → fact → response → commit. Mutates entity once. Returns landing receipt."""
    if not vertical_terrain_landing_contact_response_is_active(runtime_config):
        return None
    st = ensure_vertical_terrain_landing_contact_response_for_runtime(world, runtime_config)
    if st is None:
        return None
    st.counters["old_clamp_bypassed"] = int(st.counters.get("old_clamp_bypassed", 0)) + 1

    from mechanistic_mind.physical_system.flat_ground_gravity import vertical_half_extent_of

    he = float(vertical_half_extent_of(entity, kind=entity_kind, config=runtime_config))
    m_eff, mass_prov, mass_valid = resolve_effective_mass(
        entity_kind=entity_kind,
        entity_id=entity_id,
        mass=mass,
        world=world,
        runtime_config=runtime_config,
    )
    x = float(getattr(entity, "x", 0.0) or 0.0)
    y = float(getattr(entity, "y", 0.0) or 0.0)
    body_slot = str(entity_id) if entity_kind == "body" else None
    max_vz = float(getattr(fgg_config, "max_vz", 2.0) or 2.0)
    dt = float(getattr(fgg_config, "dt", 1.0) or 1.0)

    plan = plan_landing(
        tick=int(tick),
        entity_id=str(entity_id),
        entity_kind=str(entity_kind),
        body_slot=body_slot,
        x=x,
        y=y,
        z0=float(z0),
        vz0=float(vz0),
        z1_proposed=float(z1_proposed),
        vz1_proposed=float(vz1_proposed),
        support_z=float(support_z),
        half_extent=he,
        mass=m_eff,
        mass_provenance=mass_prov,
        mass_valid=mass_valid,
        was_grounded=bool(was_grounded),
        skip_gravity=bool(skip_gravity),
        gravity_applied=bool(gravity_applied),
        ses_below_support=bool(ses_below_support),
        max_vz=max_vz,
        dt=dt,
        cfg=st.config,
    )

    episode_id, phase, is_begin = _update_episode(st, plan)
    response_key = f"{episode_id}:{int(tick)}" if episode_id else f"{plan['contact_key']}:{int(tick)}"

    # Dedup: one response per entity/tick
    dedup_hit = False
    if plan["response_planned"]:
        if response_key in st.response_dedup:
            dedup_hit = True
            plan["response_planned"] = False
            plan["e_dissipated_planned"] = 0.0
            plan["impulse_planned"] = 0.0
            plan["classification"] = CLASS_DEDUPED
            plan["anomaly"] = CLASS_DEDUPED
            st.counters["deduped"] = int(st.counters.get("deduped", 0)) + 1
        else:
            st.response_dedup.append(response_key)
            if len(st.response_dedup) > DEDUP_HISTORY_LIMIT:
                st.response_dedup = st.response_dedup[-DEDUP_HISTORY_LIMIT:]

    # Atomic commit
    z_commit = float(plan["z_after_planned"])
    vz_commit = float(plan["vz_after_planned"])
    if plan["support_planned"] or plan["response_planned"]:
        entity.z = z_commit
        entity.vz = vz_commit
        entity.grounded = bool(abs(z_commit - float(support_z)) <= float(st.config.rest_eps) and abs(vz_commit) <= float(st.config.rest_eps))
    else:
        entity.z = float(z1_proposed)
        entity.vz = float(vz1_proposed)
        entity.grounded = False

    grounded_after = bool(getattr(entity, "grounded", False))
    landed = bool(plan["response_planned"] and not dedup_hit and not plan.get("was_grounded"))
    support_applied = bool(plan["support_planned"])
    support_dissipated = float(plan["e_dissipated_planned"]) if plan["response_planned"] else 0.0

    if plan["anomaly"]:
        st.counters["anomalies"] = int(st.counters.get("anomalies", 0)) + 1
    if plan["response_planned"]:
        st.counters["impacts"] = int(st.counters.get("impacts", 0)) + 1
    if plan["classification"] == CLASS_REST_PERSIST:
        st.counters["rest_persists"] = int(st.counters.get("rest_persists", 0)) + 1

    # V1A PE handoff via existing contract receipt path (caller also records).
    pe_before = (
        "PE_AUTHORITY_SUPPORTED_TERRAIN"
        if was_grounded
        else "PE_AUTHORITY_UNSUPPORTED_FREE_SPACE"
    )
    pe_after = (
        "PE_AUTHORITY_SUPPORTED_TERRAIN"
        if grounded_after
        else "PE_AUTHORITY_UNSUPPORTED_FREE_SPACE"
    )

    receipt = {
        "receipt_kind": RECEIPT_KIND,
        "tick": int(tick),
        "entity_id": str(entity_id),
        "entity_kind": str(entity_kind),
        "body_slot": body_slot,
        "profile_version": PROFILE_VERSION,
        "architecture_stage": ARCHITECTURE_STAGE,
        # Contact fact
        "episode_id": episode_id,
        "episode_phase": phase,
        "contact_key": plan["contact_key"],
        "crossing": bool(plan["crossing"]),
        "intersection_class": plan["classification"],
        "x": float(x),
        "y": float(y),
        "support_z": float(support_z),
        "contact_point": plan["contact_point"],
        "normal": list(NORMAL),
        "toi": plan["toi"],
        "z0": float(z0),
        "proposed_z1": float(z1_proposed),
        "penetration": float(plan["penetration"]),
        "approach": bool(plan["approach"]),
        # Response
        "response_key": response_key,
        "response_classification": plan["classification"],
        "response_applied": bool(plan["response_planned"]),
        "effective_mass": float(plan["mass_eff"]),
        "mass_provenance": plan["mass_provenance"],
        "restitution": 0.0,
        "vz_pre_response": float(vz1_proposed),
        "vz_post_response": float(getattr(entity, "vz", 0.0) or 0.0),
        "impulse_magnitude": float(plan["impulse_planned"]),
        "correction": float(plan["correction"]),
        "correction_clamped": bool(plan["correction_clamped"]),
        "support_acquired": bool(grounded_after and (landed or plan["classification"] == CLASS_REST_PERSIST)),
        "rebound": False,
        "dedup_hit": bool(dedup_hit),
        "anomaly": plan["anomaly"],
        # Energy
        "ke_before": float(plan["ke_before"]),
        "ke_after": float(0.5 * plan["mass_eff"] * float(entity.vz) ** 2) if plan["mass_valid"] else 0.0,
        "dissipated_energy": float(support_dissipated),
        "ke_creation": False,
        "agent_credit": False,
        "global_conservation_claim": False,
        "acoustic_eligibility": bool(plan["response_planned"] and support_dissipated > 0.0),
        "impact_sound_emitted": False,
        # State
        "support_state_before": "SUPPORTED" if was_grounded else "UNSUPPORTED",
        "support_state_after": "SUPPORTED" if grounded_after else "UNSUPPORTED",
        "pe_authority_before": pe_before,
        "pe_authority_after": pe_after,
        "double_pe_authority": False,
        "grounded_before": bool(was_grounded),
        "grounded_after": bool(grounded_after),
        "old_clamp_bypassed": True,
        "old_clamp_and_response_both_run": False,
        "limitations": list(plan["limitations"]),
        "spatial_reconcile": "NOT_REQUIRED_OR_DEFERRED_TO_EXISTING_SEAM",
        "plan": {
            "z1_proposed": float(z1_proposed),
            "vz1_proposed": float(vz1_proposed),
            "toi": plan["toi"],
            "penetration": float(plan["penetration"]),
            "classification": plan["classification"],
        },
        **RESEARCHER_FLAGS,
    }

    # FGG-compatible flags for outer receipt
    receipt["_fgg_landed"] = bool(landed)
    receipt["_fgg_support_applied"] = bool(support_applied)
    receipt["_fgg_support_dissipated"] = float(support_dissipated)
    receipt["_fgg_grounded"] = bool(grounded_after)
    receipt["_fgg_z"] = float(entity.z)
    receipt["_fgg_vz"] = float(entity.vz)

    st.counters["receipts"] = int(st.counters.get("receipts", 0)) + 1
    st.last_receipt = receipt
    st.history.append(receipt)
    lim = int(st.config.history_limit)
    if len(st.history) > lim:
        st.history = st.history[-lim:]
    world.last_vertical_terrain_landing = receipt

    try:
        setattr(entity, "_fgg_landed_this_tick", bool(landed))
    except Exception:
        pass
    return receipt


def end_episode_for_entity(
    world: Any,
    config: Any,
    *,
    entity_kind: str,
    entity_id: str,
    tick: int,
    reason: str = "SUPPORT_LOSS",
) -> None:
    if not vertical_terrain_landing_contact_response_is_active(config):
        return
    st = state_of(world)
    if st is None:
        return
    key = contact_key(entity_kind, entity_id)
    if key in st.active_episodes:
        del st.active_episodes[key]
        st.counters["end"] = int(st.counters.get("end", 0)) + 1


def serialize_state(st: VerticalTerrainLandingContactResponseState | None) -> dict[str, Any] | None:
    if st is None:
        return None
    return {
        "schema": STATE_SCHEMA,
        "config": st.config.to_dict(),
        "active_episodes": {k: dict(v) for k, v in st.active_episodes.items()},
        "episode_seq": int(st.episode_seq),
        "response_dedup": list(st.response_dedup),
        "counters": dict(st.counters),
        "last_receipt": dict(st.last_receipt) if st.last_receipt else None,
        "history": list(st.history),
        "banner": BANNER,
        **RESEARCHER_FLAGS,
    }


def restore_state(
    world: Any, data: dict[str, Any] | None, config: Any
) -> VerticalTerrainLandingContactResponseState | None:
    if not data or not vertical_terrain_landing_contact_response_is_active(config):
        return None
    raw_cfg = data.get("config")
    if raw_cfg is None:
        cur = getattr(config, "vertical_terrain_landing_contact_response", None)
        raw_cfg = cur.to_dict() if cur is not None and hasattr(cur, "to_dict") else None
    cfg = VerticalTerrainLandingContactResponseConfig.from_dict(raw_cfg)
    cfg.enabled = True
    st = VerticalTerrainLandingContactResponseState(
        config=cfg,
        active_episodes={
            str(k): dict(v) for k, v in dict(data.get("active_episodes") or {}).items()
        },
        episode_seq=int(data.get("episode_seq") or 0),
        response_dedup=list(data.get("response_dedup") or []),
        history=list(data.get("history") or []),
        last_receipt=dict(data["last_receipt"]) if data.get("last_receipt") else None,
        counters=dict(data.get("counters") or {}),
    )
    # Mark active as PERSIST continuity — no BEGIN replay.
    for ep in st.active_episodes.values():
        ep["phase"] = PHASE_PERSIST
    world.vertical_terrain_landing_contact_response_state = st
    return st


def catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "enabled": bool(enabled),
        "profile_version": PROFILE_VERSION,
        "architecture_stage": ARCHITECTURE_STAGE,
        "receipt_kind": RECEIPT_KIND,
        "banner": BANNER if enabled else None,
        "rebound_implemented": False,
        "vertical_impact_sound_implemented": False,
        **RESEARCHER_FLAGS,
    }


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
        "active_episodes": len(st.active_episodes),
        "last_receipt": last,
        "last_step": last,
        "rebound_implemented": False,
        "vertical_impact_sound_implemented": False,
        "banner": BANNER,
        **RESEARCHER_FLAGS,
    }
