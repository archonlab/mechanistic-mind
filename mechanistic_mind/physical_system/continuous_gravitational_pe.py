"""Acanthostega PHASE C · CONTINUOUS GRAVITATIONAL PE (Policy C).

Preset: ACANTHOSTEGA_PHASE_C_CONTINUOUS_PE_POLICY_C
Parent: ACANTHOSTEGA_PHASE_C_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW
Mechanism: continuous_gravitational_pe
Profile: POLICY_C_UNIFIED_CONTINUOUS_ENDPOINT_PE_V1

Exclusive gravitational PE authority mutex:

  gravitational_pe_authority ∈ {
      PE_AUTHORITY_SES_DDA,
      CONTINUOUS_SUPPORT_HEIGHT_ENDPOINT_DELTA_U,
  }

Exactly one active authority per config. Dual-active is unrepresentable:
  - mechanism OFF  → SES_DDA owns gravitational PE (legacy)
  - mechanism ON   → must select ENDPOINT; endpoint owns gravitational PE

Under Policy C:
  SES DDA + Face Sweep remain traversal / topology gates.
  Committed supported displacement gravitational ΔU =
      m_eff · g · (z_end − z_start)   (reuse shadow compute_endpoint_delta_u)
  SES climb work_debit / kinetic_paid / dissipated_pe are suppressed for the
  same displacement (no double charge).

NOT activated:
  projected normal load, tangent gravity, passive slope sliding.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from mechanistic_mind.physical_system.continuous_gravitational_pe_diagnostic_shadow import (
    ENDPOINT_AUTHORITY,
    compute_endpoint_delta_u,
)
from mechanistic_mind.physical_system.ses_decomposition_contract import (
    PE_AUTHORITY_SES_DDA,
)

MECHANISM_ID = "continuous_gravitational_pe"
PROFILE_VERSION = "POLICY_C_UNIFIED_CONTINUOUS_ENDPOINT_PE_V1"
STAGE_ALIAS = "POLICY_C_UNIFIED_CONTINUOUS_ENDPOINT_PE_V1"
STATE_SCHEMA = "CONTINUOUS_GRAVITATIONAL_PE_POLICY_C_STATE_V1"
RECEIPT_KIND = "CONTINUOUS_GRAVITATIONAL_PE_POLICY_C"

GRAV_PE_AUTH_SES_DDA = PE_AUTHORITY_SES_DDA
GRAV_PE_AUTH_ENDPOINT = ENDPOINT_AUTHORITY  # CONTINUOUS_SUPPORT_HEIGHT_ENDPOINT_DELTA_U
GRAVITATIONAL_PE_AUTHORITIES = (GRAV_PE_AUTH_SES_DDA, GRAV_PE_AUTH_ENDPOINT)

BANNER = (
    "CONTINUOUS GRAVITATIONAL PE\n"
    "POLICY C ACTIVE\n"
    "PE AUTHORITY: CONTINUOUS ENDPOINT ΔU\n"
    "SES/FACE SWEEP: TRAVERSAL GATE ONLY\n"
    "PROJECTED N: SHADOW ONLY · g_t OFF · SLIDE OFF"
)
OVERLAY_CAPTION = BANNER
ANALYZER_SECTION = "CONTINUOUS GRAVITATIONAL PE POLICY C"

HISTORY_LIMIT_DEFAULT = 64
EPS_ZERO = 1e-12

RESEARCHER_FLAGS = {
    "researcher_only": True,
    "agent_accessible": False,
    "semantic_label": False,
    "projected_normal_load_active": False,
    "tangent_gravity_active": False,
    "passive_slope_sliding_active": False,
}


@dataclass
class ContinuousGravitationalPeConfig:
    """Exclusive gravitational PE authority selector.

    enabled=False → SES_DDA (Policy C inactive; previous presets).
    enabled=True  → gravitational_pe_authority MUST be ENDPOINT (Policy C).
    """

    enabled: bool = False
    gravitational_pe_authority: str = GRAV_PE_AUTH_SES_DDA
    history_limit: int = HISTORY_LIMIT_DEFAULT

    def to_dict(self) -> dict[str, Any]:
        on = bool(self.enabled)
        auth = active_authority_from_fields(on, self.gravitational_pe_authority)
        return {
            "enabled": on,
            "gravitational_pe_authority": str(auth),
            "history_limit": int(self.history_limit),
            "profile_version": PROFILE_VERSION,
            "stage_alias": STAGE_ALIAS,
            "continuous_pe_active": bool(on and auth == GRAV_PE_AUTH_ENDPOINT),
            "ses_gravitational_charge_suppressed": bool(on and auth == GRAV_PE_AUTH_ENDPOINT),
            "projected_normal_load_active": False,
            "tangent_gravity_active": False,
            "passive_slope_sliding_active": False,
            "mutex": "EXCLUSIVE_SINGLE_AUTHORITY",
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ContinuousGravitationalPeConfig":
        if not isinstance(data, dict) or not data:
            return cls(enabled=False)
        ver = data.get("profile_version")
        if ver is not None and str(ver) != PROFILE_VERSION:
            raise ValueError(f"unknown continuous_gravitational_pe profile: {ver}")
        enabled = bool(data.get("enabled", False))
        raw_auth = data.get("gravitational_pe_authority", GRAV_PE_AUTH_SES_DDA)
        auth = validate_authority_selection(enabled=enabled, authority=raw_auth)
        return cls(
            enabled=enabled,
            gravitational_pe_authority=auth,
            history_limit=int(data.get("history_limit", HISTORY_LIMIT_DEFAULT)),
        )


def validate_authority_selection(*, enabled: bool, authority: Any) -> str:
    """Reject dual / mixed / reserved-invalid selections. Return canonical authority."""
    if isinstance(authority, (list, tuple, set, frozenset, dict)):
        raise ValueError(f"MIXED_PE_AUTHORITY_REJECTED: {authority!r}")
    if not isinstance(authority, str) or not authority:
        raise ValueError(f"MISSING_OR_INVALID_PE_AUTHORITY: {authority!r}")
    if "|" in authority or "+" in authority or "," in authority:
        raise ValueError(f"MIXED_PE_AUTHORITY_REJECTED: {authority!r}")
    if authority not in GRAVITATIONAL_PE_AUTHORITIES:
        raise ValueError(f"UNKNOWN_GRAVITATIONAL_PE_AUTHORITY: {authority!r}")
    if enabled and authority != GRAV_PE_AUTH_ENDPOINT:
        raise ValueError(
            "POLICY_C_ENABLED_REQUIRES_ENDPOINT_AUTHORITY: "
            f"enabled={enabled} authority={authority!r}"
        )
    if (not enabled) and authority == GRAV_PE_AUTH_ENDPOINT:
        raise ValueError(
            "ENDPOINT_AUTHORITY_REQUIRES_MECHANISM_ENABLED: "
            f"enabled={enabled} authority={authority!r}"
        )
    return authority if enabled else GRAV_PE_AUTH_SES_DDA


def active_authority_from_fields(enabled: bool, authority: str) -> str:
    if bool(enabled):
        return GRAV_PE_AUTH_ENDPOINT
    return GRAV_PE_AUTH_SES_DDA


def validate_config(cfg: ContinuousGravitationalPeConfig) -> None:
    if not (1 <= int(cfg.history_limit) <= 512):
        raise ValueError("history_limit must be in [1, 512]")
    validate_authority_selection(
        enabled=bool(cfg.enabled),
        authority=str(cfg.gravitational_pe_authority),
    )


def _line_ok(config: Any) -> bool:
    return (
        config is not None
        and str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"
    )


def continuous_gravitational_pe_is_active(config: Any) -> bool:
    """True iff Policy C mechanism is ON (endpoint owns PE)."""
    if not _line_ok(config):
        return False
    cfg = getattr(config, "continuous_gravitational_pe", None)
    if cfg is None or not bool(getattr(cfg, "enabled", False)):
        return False
    auth = str(getattr(cfg, "gravitational_pe_authority", GRAV_PE_AUTH_SES_DDA) or "")
    return auth == GRAV_PE_AUTH_ENDPOINT


def active_gravitational_pe_authority(config: Any | None) -> str:
    """Single active gravitational PE authority for this config (mutex)."""
    if continuous_gravitational_pe_is_active(config):
        return GRAV_PE_AUTH_ENDPOINT
    return GRAV_PE_AUTH_SES_DDA


def endpoint_pe_physically_active(config: Any | None) -> bool:
    return active_gravitational_pe_authority(config) == GRAV_PE_AUTH_ENDPOINT


def ses_gravitational_charge_suppressed(config: Any | None) -> bool:
    """When True, SES must not charge climb/descent gravitational PE."""
    return endpoint_pe_physically_active(config)


def continuous_pe_active(config: Any | None) -> bool:
    return endpoint_pe_physically_active(config)


def set_continuous_gravitational_pe(config: Any, enabled: bool) -> None:
    if config is None:
        return
    on = bool(enabled) and _line_ok(config)
    cur = getattr(config, "continuous_gravitational_pe", None)
    if cur is None:
        if on:
            config.continuous_gravitational_pe = ContinuousGravitationalPeConfig(
                enabled=True,
                gravitational_pe_authority=GRAV_PE_AUTH_ENDPOINT,
            )
        return
    if isinstance(cur, dict):
        cur = ContinuousGravitationalPeConfig.from_dict(cur)
        config.continuous_gravitational_pe = cur
    cur.enabled = bool(on)
    if on:
        cur.gravitational_pe_authority = GRAV_PE_AUTH_ENDPOINT
    else:
        cur.gravitational_pe_authority = GRAV_PE_AUTH_SES_DDA


@dataclass
class ContinuousGravitationalPeState:
    config: ContinuousGravitationalPeConfig = field(
        default_factory=ContinuousGravitationalPeConfig
    )
    counters: dict[str, int] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    last_receipt: dict[str, Any] | None = None
    tick_results: dict[str, dict[str, Any]] = field(default_factory=dict)
    last_tick: int = -1
    last_error: str | None = None

    def reset_tick(self, tick: int) -> None:
        if int(tick) != int(self.last_tick):
            self.tick_results = {}
            self.last_tick = int(tick)


def state_of(world: Any) -> ContinuousGravitationalPeState | None:
    return getattr(world, "continuous_gravitational_pe_state", None)


def ensure_continuous_gravitational_pe_for_runtime(
    world: Any, config: Any
) -> ContinuousGravitationalPeState | None:
    if not continuous_gravitational_pe_is_active(config):
        return state_of(world)
    st = state_of(world)
    cfg = getattr(config, "continuous_gravitational_pe", None)
    if not isinstance(cfg, ContinuousGravitationalPeConfig):
        cfg = ContinuousGravitationalPeConfig.from_dict(
            cfg if isinstance(cfg, dict) else None
        )
        validate_config(cfg)
        config.continuous_gravitational_pe = cfg
    else:
        validate_config(cfg)
    if st is None:
        st = ContinuousGravitationalPeState(config=cfg)
        world.continuous_gravitational_pe_state = st
    else:
        st.config = cfg
    return st


def serialize_state(st: ContinuousGravitationalPeState | None) -> dict[str, Any] | None:
    if st is None:
        return None
    return {
        "schema": STATE_SCHEMA,
        "config": st.config.to_dict(),
        "counters": dict(st.counters or {}),
        "last_tick": int(st.last_tick),
    }


def restore_state(
    world: Any,
    payload: dict[str, Any] | None,
    config: Any | None = None,
) -> ContinuousGravitationalPeState | None:
    """Restore Policy C state. Missing/None → clear (mechanism OFF for old snapshots)."""
    if not isinstance(payload, dict) or not payload:
        if world is not None and hasattr(world, "continuous_gravitational_pe_state"):
            try:
                delattr(world, "continuous_gravitational_pe_state")
            except Exception:
                world.continuous_gravitational_pe_state = None
        return None
    cfg = ContinuousGravitationalPeConfig.from_dict(payload.get("config"))
    validate_config(cfg)
    st = ContinuousGravitationalPeState(config=cfg)
    st.counters = {str(k): int(v) for k, v in dict(payload.get("counters") or {}).items()}
    st.last_tick = int(payload.get("last_tick", -1) or -1)
    # No history / tick_results restore → no pending charge replay.
    if world is not None:
        world.continuous_gravitational_pe_state = st
    if config is not None and getattr(config, "continuous_gravitational_pe", None) is None:
        config.continuous_gravitational_pe = cfg
    return st


def observer_banner(config: Any | None) -> str:
    if endpoint_pe_physically_active(config):
        return BANNER
    return (
        "CONTINUOUS GRAVITATIONAL PE\n"
        "POLICY C OFF\n"
        "PE AUTHORITY: SES_DDA"
    )


def reduce_speed_by_energy(
    vx: float, vy: float, *, mass: float, energy_paid: float
) -> tuple[float, float]:
    """Isotropic KE reduction for FREE endpoint uphill charge."""
    m = float(mass)
    e = float(energy_paid)
    if m <= 0.0 or e <= EPS_ZERO:
        return float(vx), float(vy)
    ke = 0.5 * m * (float(vx) * float(vx) + float(vy) * float(vy))
    if ke <= EPS_ZERO:
        return 0.0, 0.0
    new_ke = max(0.0, ke - e)
    if new_ke <= EPS_ZERO:
        return 0.0, 0.0
    scale = math.sqrt(new_ke / ke)
    return float(vx) * scale, float(vy) * scale


def annotate_plan_endpoint_pe(
    world: Any,
    config: Any,
    plan: dict[str, Any],
    *,
    x0: float,
    y0: float,
    mass: float,
    entity_kind: str,
    work_reservoir: float | None,
) -> dict[str, Any]:
    """Attach endpoint ΔU to an accepted grounded plan; may convert to reject.

    Call after SES topology evaluation (and face-sweep), before pose commit.
    Uses the validated shadow formula. Does not mutate pose.
    """
    if not endpoint_pe_physically_active(config):
        plan["gravitational_pe_authority"] = GRAV_PE_AUTH_SES_DDA
        plan["endpoint_delta_u"] = None
        plan["ses_gravitational_charge_suppressed"] = False
        return plan

    plan["gravitational_pe_authority"] = GRAV_PE_AUTH_ENDPOINT
    plan["ses_gravitational_charge_suppressed"] = True
    plan["endpoint_delta_u"] = None
    plan["endpoint_pe_applied"] = 0.0
    plan["endpoint_pe_dissipated"] = 0.0
    # Coherent slope dynamics: ΔU is measured; force work is live g_t.
    try:
        from mechanistic_mind.physical_system.coherent_slope_dynamics import (
            policy_c_measurement_only_required,
        )

        plan["policy_c_measurement_only"] = bool(
            policy_c_measurement_only_required(config)
        )
    except Exception:
        plan["policy_c_measurement_only"] = False

    if not bool(plan.get("accepted")):
        return plan
    if bool(plan.get("support_lost")) or not bool(plan.get("grounded", True)):
        plan["endpoint_pe_status"] = "SUPPORT_LOSS_OR_AIRBORNE_NO_ENDPOINT_PE"
        return plan
    if bool(plan.get("airborne_passthrough")):
        plan["endpoint_pe_status"] = "AIRBORNE_PASSTHROUGH_NO_ENDPOINT_PE"
        return plan

    from mechanistic_mind.physical_system.surface_elevation_support import (
        surface_support_height,
    )

    x_end = float(plan.get("x", x0))
    y_end = float(plan.get("y", y0))
    z_s = float(surface_support_height(world, float(x0), float(y0), config=config))
    z_e = float(surface_support_height(world, x_end, y_end, config=config))
    g = float(plan.get("g") or 0.0)
    if g <= 0.0:
        from mechanistic_mind.physical_system.surface_elevation_support import _read_g

        g = float(_read_g(world))
    du = float(
        compute_endpoint_delta_u(m_eff=float(mass), g=float(g), z_start=z_s, z_end=z_e)
    )
    plan["z_start_authoritative"] = float(z_s)
    plan["z_end_authoritative"] = float(z_e)
    plan["delta_z_authoritative"] = float(z_e) - float(z_s)
    plan["endpoint_delta_u"] = float(du)
    plan["endpoint_pe_status"] = "COMPUTED"

    # Measurement-only: do not reject on reservoir/KE vs ΔU — locomotor / g_t own payment.
    if bool(plan.get("policy_c_measurement_only")):
        return plan

    if du > EPS_ZERO:
        if str(entity_kind) == "body":
            w0 = float(work_reservoir) if work_reservoir is not None else 0.0
            if w0 + 1e-15 < du:
                plan["accepted"] = False
                plan["block_reason"] = "INSUFFICIENT_WORK_BLOCKED"
                plan["endpoint_pe_status"] = "INSUFFICIENT_WORK_FOR_ENDPOINT_PE"
                plan["W_endpoint"] = float(du)
                plan["work_available"] = float(w0)
                plan["x"] = float(x0)
                plan["y"] = float(y0)
                return plan
        else:
            vx = float(plan.get("vx", 0.0) or 0.0)
            vy = float(plan.get("vy", 0.0) or 0.0)
            ke = 0.5 * float(mass) * (vx * vx + vy * vy)
            if ke + 1e-15 < du:
                plan["accepted"] = False
                plan["block_reason"] = "INSUFFICIENT_KINETIC_BLOCKED"
                plan["endpoint_pe_status"] = "INSUFFICIENT_KINETIC_FOR_ENDPOINT_PE"
                plan["W_endpoint"] = float(du)
                plan["K_available"] = float(ke)
                plan["x"] = float(x0)
                plan["y"] = float(y0)
                plan["vx"] = 0.0
                plan["vy"] = 0.0
                return plan
    return plan


def _policy_c_measurement_only(plan: dict[str, Any]) -> bool:
    """True when coherent slope dynamics owns gravitational force work.

    Endpoint ΔU remains the PE measurement authority; ±ΔU must not also
    mutate reservoir/KE (would double-count against live g_t).
    """
    if bool(plan.get("policy_c_measurement_only")):
        return True
    return False


def apply_endpoint_pe_to_body(
    body: Any,
    plan: dict[str, Any],
    *,
    work_reservoir_before: float,
) -> dict[str, Any]:
    """Debit reservoir for +ΔU; dissipate −ΔU (no credit). Mutates body reservoir.

    When plan.policy_c_measurement_only: record ΔU only — no reservoir mutation.
    """
    du = plan.get("endpoint_delta_u")
    if du is None or not bool(plan.get("accepted")):
        return plan
    du_f = float(du)
    w0 = float(work_reservoir_before)
    plan["mechanical_work_reservoir_before"] = float(w0)
    if _policy_c_measurement_only(plan):
        plan["work_debit"] = 0.0
        plan["endpoint_pe_applied"] = 0.0
        plan["endpoint_pe_dissipated"] = 0.0
        plan["endpoint_pe_measurement_only"] = True
        plan["mechanical_work_reservoir_after"] = float(
            getattr(body, "mechanical_work_reservoir", w0) or 0.0
        )
        return plan
    if du_f > EPS_ZERO:
        body.mechanical_work_reservoir = max(0.0, w0 - du_f)
        plan["work_debit"] = float(du_f)
        plan["endpoint_pe_applied"] = float(du_f)
        plan["endpoint_pe_dissipated"] = 0.0
    elif du_f < -EPS_ZERO:
        plan["work_debit"] = 0.0
        plan["endpoint_pe_applied"] = 0.0
        plan["endpoint_pe_dissipated"] = float(abs(du_f))
    else:
        plan["work_debit"] = 0.0
        plan["endpoint_pe_applied"] = 0.0
        plan["endpoint_pe_dissipated"] = 0.0
    plan["endpoint_pe_measurement_only"] = False
    plan["mechanical_work_reservoir_after"] = float(
        getattr(body, "mechanical_work_reservoir", w0) or 0.0
    )
    return plan


def apply_endpoint_pe_to_free_object(plan: dict[str, Any], *, mass: float) -> dict[str, Any]:
    """Reduce FREE KE for +ΔU; dissipate −ΔU (no KE gain). Mutates plan vx/vy.

    Measurement-only mode: record ΔU, leave vx/vy unchanged.
    """
    du = plan.get("endpoint_delta_u")
    if du is None or not bool(plan.get("accepted")):
        return plan
    du_f = float(du)
    if _policy_c_measurement_only(plan):
        plan["kinetic_paid"] = 0.0
        plan["endpoint_pe_applied"] = 0.0
        plan["endpoint_pe_dissipated"] = 0.0
        plan["endpoint_pe_measurement_only"] = True
        return plan
    if du_f > EPS_ZERO:
        vx, vy = reduce_speed_by_energy(
            float(plan.get("vx", 0.0) or 0.0),
            float(plan.get("vy", 0.0) or 0.0),
            mass=float(mass),
            energy_paid=du_f,
        )
        plan["vx"] = float(vx)
        plan["vy"] = float(vy)
        plan["kinetic_paid"] = float(du_f)
        plan["endpoint_pe_applied"] = float(du_f)
        plan["endpoint_pe_dissipated"] = 0.0
    elif du_f < -EPS_ZERO:
        plan["kinetic_paid"] = 0.0
        plan["endpoint_pe_applied"] = 0.0
        plan["endpoint_pe_dissipated"] = float(abs(du_f))
    else:
        plan["kinetic_paid"] = 0.0
        plan["endpoint_pe_applied"] = 0.0
        plan["endpoint_pe_dissipated"] = 0.0
    plan["endpoint_pe_measurement_only"] = False
    return plan


def record_policy_c_receipt(
    world: Any,
    config: Any,
    plan: dict[str, Any],
    *,
    entity_kind: str,
    entity_id: str,
    tick: int,
) -> dict[str, Any] | None:
    if not endpoint_pe_physically_active(config):
        return None
    st = ensure_continuous_gravitational_pe_for_runtime(world, config)
    if st is None:
        return None
    st.reset_tick(int(tick))
    receipt = {
        "receipt_kind": RECEIPT_KIND,
        "mechanism": MECHANISM_ID,
        "profile_version": PROFILE_VERSION,
        "tick": int(tick),
        "entity_kind": str(entity_kind),
        "entity_id": str(entity_id),
        "gravitational_pe_authority": GRAV_PE_AUTH_ENDPOINT,
        "accepted": bool(plan.get("accepted")),
        "block_reason": plan.get("block_reason"),
        "endpoint_delta_u": plan.get("endpoint_delta_u"),
        "endpoint_pe_applied": float(plan.get("endpoint_pe_applied") or 0.0),
        "endpoint_pe_dissipated": float(plan.get("endpoint_pe_dissipated") or 0.0),
        "delta_z_authoritative": plan.get("delta_z_authoritative"),
        "z_start_authoritative": plan.get("z_start_authoritative"),
        "z_end_authoritative": plan.get("z_end_authoritative"),
        "ses_gravitational_charge_suppressed": True,
        "work_debit": float(plan.get("work_debit") or 0.0),
        "kinetic_paid": float(plan.get("kinetic_paid") or 0.0),
        "support_lost": bool(plan.get("support_lost")),
        "endpoint_pe_status": plan.get("endpoint_pe_status"),
        "banner": BANNER,
        **RESEARCHER_FLAGS,
        "continuous_pe_active": True,
        "influenced_physics": True,
        "agent_accessible": False,
    }
    key = f"{entity_kind}:{entity_id}"
    st.tick_results[key] = receipt
    st.last_receipt = receipt
    st.history.append(receipt)
    lim = int(st.config.history_limit)
    if len(st.history) > lim:
        st.history = st.history[-lim:]
    st.counters["receipts"] = int(st.counters.get("receipts", 0)) + 1
    if bool(plan.get("accepted")) and abs(float(plan.get("endpoint_pe_applied") or 0.0)) > EPS_ZERO:
        st.counters["endpoint_uphill_charges"] = int(st.counters.get("endpoint_uphill_charges", 0)) + 1
    if bool(plan.get("accepted")) and abs(float(plan.get("endpoint_pe_dissipated") or 0.0)) > EPS_ZERO:
        st.counters["endpoint_downhill_dissipations"] = (
            int(st.counters.get("endpoint_downhill_dissipations", 0)) + 1
        )
    if not bool(plan.get("accepted")):
        st.counters["blocked"] = int(st.counters.get("blocked", 0)) + 1
    return receipt
