"""Analyzer summary for Policy C continuous gravitational PE (researcher-only)."""
from __future__ import annotations

from typing import Any

EVENT_REF_KIND = "continuous_gravitational_pe_policy_c"
COGNITION_FORBIDDEN_TOKENS = (
    "CONTINUOUS_SUPPORT_HEIGHT_ENDPOINT_DELTA_U",
    "gravitational_pe_authority",
    "endpoint_pe_applied",
    "POLICY_C_UNIFIED",
    "ses_gravitational_charge_suppressed",
)


def summarize_continuous_gravitational_pe_events(receipts: list[dict[str, Any]]) -> dict[str, Any]:
    uphill = downhill = zero = blocked = blocked_with_pe = 0
    for r in receipts:
        if not bool(r.get("accepted")):
            blocked += 1
            if abs(float(r.get("endpoint_pe_applied") or 0.0)) > 1e-15 or abs(
                float(r.get("endpoint_pe_dissipated") or 0.0)
            ) > 1e-15:
                blocked_with_pe += 1
            continue
        applied = float(r.get("endpoint_pe_applied") or 0.0)
        diss = float(r.get("endpoint_pe_dissipated") or 0.0)
        du = r.get("endpoint_delta_u")
        if du is not None and abs(float(du)) <= 1e-15:
            zero += 1
        if applied > 1e-15:
            uphill += 1
        if diss > 1e-15:
            downhill += 1
    return {
        "mechanism": "continuous_gravitational_pe",
        "profile": "POLICY_C_UNIFIED_CONTINUOUS_ENDPOINT_PE_V1",
        "pe_authority": "CONTINUOUS_SUPPORT_HEIGHT_ENDPOINT_DELTA_U",
        "n_receipts": len(receipts),
        "endpoint_uphill_charges": uphill,
        "endpoint_downhill_dissipations": downhill,
        "zero_delta_traversals": zero,
        "blocked": blocked,
        "blocked_with_pe_charge": blocked_with_pe,
        "projected_normal_load_active": False,
        "tangent_gravity_active": False,
        "passive_slope_sliding_active": False,
        "researcher_only": True,
    }


def summarize_continuous_gravitational_pe(world: Any) -> dict[str, Any] | None:
    from mechanistic_mind.physical_system.continuous_gravitational_pe import state_of

    st = state_of(world)
    if st is None:
        return None
    return summarize_continuous_gravitational_pe_events(list(st.history or []))
