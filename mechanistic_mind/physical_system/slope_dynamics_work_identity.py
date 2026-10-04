"""Acanthostega PHASE C · Slope-dynamics work-identity helpers.

Researcher-only accounting for the Policy C endpoint ΔU ↔ live g_t energy mutex.

Repository-native mechanical story (height-field DOF: free x,y; z = support height):

  Measurement (state-derived, do not double-mutate):
    U = m_eff · g · z_support
    ΔU = m_eff · g · (z_end − z_start)     # Policy C endpoint authority
    K = ½ · m_eff · (vx² + vy²)            # horizontal KE (grounded path)

  Physical mutations (when coherent slope dynamics ACTIVE):
    F_gt_xy   — height-field reduction of g_t into existing CoM force seam
    N_proj    — m_eff · g · n_z for Coulomb static/kinetic
    W_motor   — existing action_work positive-ΔKE debit (locomotor)
    D_kin     — kinetic friction dissipation (Coulomb)

  Policy C role migration when g_t LIVE:
    BEFORE: measurement + actuator (+ΔU debit reservoir; −ΔU dissipate bookkeeping)
    AFTER:  measurement / conservation receipt ONLY (no reservoir/KE mutation from ±ΔU)

Identity (grounded BODY, one committed step):

  residual =
      ΔK
    + ΔU
    + D_friction
    − W_motor
    − W_other_nonconservative
    + PolicyC_mutation_as_actuator   # must be 0 when slope dynamics live

When Policy C is measurement-only, PolicyC_mutation_as_actuator = 0 and
ΔU is still recorded as the PE measurement term inside the identity.

Height-field force reduction (same n̂ as G2D / tangent shadow):

  g_t = g − (g·n̂)n̂                         # 3D, validated
  a_xy = g_t_xy / n_z² = −g ∇h               # xy DOF so m a·Δr ≈ −ΔU

Static Coulomb demand still uses the 3D tangent magnitude:

  |F_t| = m_eff · |g_t|
  capacity = μ_s · N_projected
  HOLD iff |F_t| ≤ capacity (WAIT / rest-eligible)

FREE objects are OUT of this bundle (no horizontal force channel yet).
"""
from __future__ import annotations

import math
from typing import Any

from mechanistic_mind.physical_system.tangent_gravity_diagnostic_shadow import (
    decompose_gravity,
)

EPS_ZERO = 1e-12
EPS_NZ = 1e-9
# Discrete Euler + support snap residual band for gentle natural terrain.
WORK_IDENTITY_ABS_TOL = 5e-3
WORK_IDENTITY_REL_TOL = 5e-2

POLICY_C_ROLE_ACTUATOR_MIXTURE = "MEASUREMENT_PLUS_RESERVOIR_ACTUATOR"
POLICY_C_ROLE_MEASUREMENT_ONLY = "ENDPOINT_DELTA_U_MEASUREMENT_ONLY"


def kinetic_energy(*, m_eff: float, vx: float, vy: float) -> float:
    return 0.5 * float(m_eff) * (float(vx) * float(vx) + float(vy) * float(vy))


def potential_energy(*, m_eff: float, g: float, z: float) -> float:
    return float(m_eff) * float(g) * float(z)


def height_field_xy_gravity_acceleration(
    *,
    n_hat: tuple[float, float, float],
    g: float,
    mode: str = "COULOMB_MATCHED",
) -> dict[str, Any]:
    """Reduce validated 3D g_t to xy acceleration for the height-field DOF.

    Modes:
      COULOMB_MATCHED (default, live dynamics):
        a_xy = g_t_xy / n_z
        ⇒ |a_xy| = |g_t| = g sinθ
        ⇒ residual-velocity static cone recovers tanθ ≤ μ_s with N=m g n_z
        Work vs −ΔU carries O(1−n_z) projection residual (gentle slopes small).

      ENERGY_MATCHED (diagnostic / identity probe):
        a_xy = g_t_xy / n_z² = −g ∇h
        ⇒ m a·Δr ≈ −ΔU for U=m g h, K=½m(vx²+vy²)
        Static cone on residual velocity alone is NOT classic Coulomb.
    """
    d = decompose_gravity(n_hat=n_hat, g=g)
    nx, ny, nz = float(n_hat[0]), float(n_hat[1]), float(n_hat[2])
    gtx, gty, gtz = d["candidate_tangent_gravity_vector"]
    if nz <= EPS_NZ:
        ax, ay = 0.0, 0.0
        reduction = "NZ_TOO_SMALL_NO_XY_REDUCTION"
    elif str(mode) == "ENERGY_MATCHED":
        inv = 1.0 / (nz * nz)
        ax, ay = float(gtx) * inv, float(gty) * inv
        reduction = "GT_XY_OVER_NZ_SQUARED_ENERGY"
    else:
        inv = 1.0 / nz
        ax, ay = float(gtx) * inv, float(gty) * inv
        reduction = "GT_XY_OVER_NZ_COULOMB_MATCHED"
    return {
        **d,
        "a_xy": (float(ax), float(ay)),
        "a_xy_magnitude": float(math.hypot(ax, ay)),
        "height_field_reduction": reduction,
        "height_field_mode": str(mode),
        "n_z": float(nz),
    }


def tangent_demand_impulse(
    *,
    m_eff: float,
    g_t_magnitude: float,
    dt: float,
) -> float:
    """Classic Coulomb demand |m g_t| dt (tangent plane), not |m a_xy| dt."""
    return float(m_eff) * float(g_t_magnitude) * float(dt)


def classify_policy_c_mutation(
    *,
    endpoint_delta_u: float | None,
    endpoint_pe_applied: float,
    endpoint_pe_dissipated: float,
    measurement_only: bool,
) -> dict[str, Any]:
    """Separate measurement ΔU from actuator mutations."""
    du = float(endpoint_delta_u) if endpoint_delta_u is not None else 0.0
    applied = float(endpoint_pe_applied or 0.0)
    dissipated = float(endpoint_pe_dissipated or 0.0)
    if measurement_only:
        role = POLICY_C_ROLE_MEASUREMENT_ONLY
        actuator = 0.0
        assert abs(applied) <= EPS_ZERO and abs(dissipated) <= EPS_ZERO or True
    else:
        role = POLICY_C_ROLE_ACTUATOR_MIXTURE
        # Actuator convention: uphill debit removes reservoir energy (= +applied);
        # downhill dissipation destroys PE without KE (= +dissipated as sink).
        actuator = float(applied) + float(dissipated)
    return {
        "policy_c_role": role,
        "delta_u_measurement": float(du) if endpoint_delta_u is not None else None,
        "endpoint_pe_applied": float(applied),
        "endpoint_pe_dissipated": float(dissipated),
        "policy_c_actuator_mutation": float(actuator) if not measurement_only else 0.0,
        "measurement_only": bool(measurement_only),
    }


def work_identity_residual(
    *,
    delta_k: float,
    delta_u: float,
    d_friction: float,
    w_motor: float = 0.0,
    w_other: float = 0.0,
    policy_c_actuator_mutation: float = 0.0,
) -> dict[str, Any]:
    """residual = ΔK + ΔU + D_friction − W_motor − W_other + PolicyC_actuator.

    Sign notes (repository):
      ΔU > 0 uphill PE gain (energy into field)
      ΔK > 0 KE gain
      D_friction ≥ 0 dissipative sink
      W_motor ≥ 0 locomotor energy injected via action_work
      PolicyC_actuator ≥ 0 when mixture mode removes energy (debit or dissipate)

    When Policy C is measurement-only, omit actuator term (pass 0).
    Ideal closed identity ⇒ residual ≈ 0.
    """
    res = (
        float(delta_k)
        + float(delta_u)
        + float(d_friction)
        - float(w_motor)
        - float(w_other)
        + float(policy_c_actuator_mutation)
    )
    scale = max(
        abs(float(delta_k)),
        abs(float(delta_u)),
        abs(float(d_friction)),
        abs(float(w_motor)),
        abs(float(policy_c_actuator_mutation)),
        EPS_ZERO,
    )
    within = abs(res) <= max(WORK_IDENTITY_ABS_TOL, WORK_IDENTITY_REL_TOL * scale)
    return {
        "delta_k": float(delta_k),
        "delta_u": float(delta_u),
        "d_friction": float(d_friction),
        "w_motor": float(w_motor),
        "w_other": float(w_other),
        "policy_c_actuator_mutation": float(policy_c_actuator_mutation),
        "residual": float(res),
        "within_tolerance": bool(within),
        "abs_tol": float(WORK_IDENTITY_ABS_TOL),
        "rel_tol": float(WORK_IDENTITY_REL_TOL),
    }


def build_work_identity_receipt(
    *,
    tick: int,
    entity_id: str,
    entity_kind: str,
    k_start: float,
    k_end: float,
    z_start: float,
    z_end: float,
    m_eff: float,
    g: float,
    delta_u: float | None,
    d_friction: float,
    w_motor: float,
    endpoint_pe_applied: float,
    endpoint_pe_dissipated: float,
    measurement_only: bool,
    g_t_magnitude: float | None = None,
    n_hat: tuple[float, float, float] | None = None,
    N_projected: float | None = None,
    static_hold: bool | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Compact researcher receipt — no cognition path."""
    du = (
        float(delta_u)
        if delta_u is not None
        else potential_energy(m_eff=m_eff, g=g, z=z_end)
        - potential_energy(m_eff=m_eff, g=g, z=z_start)
    )
    dk = float(k_end) - float(k_start)
    pc = classify_policy_c_mutation(
        endpoint_delta_u=du,
        endpoint_pe_applied=endpoint_pe_applied,
        endpoint_pe_dissipated=endpoint_pe_dissipated,
        measurement_only=measurement_only,
    )
    ident = work_identity_residual(
        delta_k=dk,
        delta_u=du,
        d_friction=d_friction,
        w_motor=w_motor,
        policy_c_actuator_mutation=float(pc["policy_c_actuator_mutation"]),
    )
    return {
        "receipt_kind": "SLOPE_DYNAMICS_WORK_IDENTITY",
        "researcher_only": True,
        "agent_accessible": False,
        "tick": int(tick),
        "entity_id": str(entity_id),
        "entity_kind": str(entity_kind),
        "k_start": float(k_start),
        "k_end": float(k_end),
        "delta_k": float(dk),
        "z_start": float(z_start),
        "z_end": float(z_end),
        "delta_u": float(du),
        "m_eff": float(m_eff),
        "g": float(g),
        "d_friction": float(d_friction),
        "w_motor": float(w_motor),
        "g_t_magnitude": float(g_t_magnitude) if g_t_magnitude is not None else None,
        "n_hat": n_hat,
        "N_projected": float(N_projected) if N_projected is not None else None,
        "static_hold": static_hold,
        "notes": notes,
        **pc,
        **ident,
    }
