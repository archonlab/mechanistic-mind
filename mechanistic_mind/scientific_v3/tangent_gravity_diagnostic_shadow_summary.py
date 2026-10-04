"""Analyzer summary for tangent gravity diagnostic shadow (researcher-only)."""
from __future__ import annotations

from typing import Any

EVENT_REF_KIND = "tangent_gravity_diagnostic_shadow"
COGNITION_FORBIDDEN_TOKENS = (
    "candidate_tangent_gravity",
    "BREAKAWAY_EXPECTED",
    "HOLD_CAPABLE",
    "static_hold_margin",
    "TANGENT_GRAVITY_SHADOW",
    "g_t",
)


def summarize_tangent_gravity_diagnostic_shadow_events(
    receipts: list[dict[str, Any]],
) -> dict[str, Any]:
    eligible = flat = nonzero = hold = brk = pe_ok = pe_bad = air_leak = 0
    mags: list[float] = []
    for r in receipts:
        if r.get("eligible"):
            eligible += 1
        if r.get("flat"):
            flat += 1
        gt = r.get("candidate_tangent_gravity_magnitude")
        if gt is not None and abs(float(gt)) > 1e-12:
            nonzero += 1
            mags.append(float(gt))
        if r.get("static_hold_classification") == "HOLD_CAPABLE":
            hold += 1
        elif r.get("static_hold_classification") == "BREAKAWAY_EXPECTED":
            brk += 1
        if r.get("pe_sign_consistency") == "CONSISTENT":
            pe_ok += 1
        elif r.get("pe_sign_consistency") == "INCONSISTENT":
            pe_bad += 1
        if r.get("status") == "NOT_ELIGIBLE_AIRBORNE" and gt:
            air_leak += 1
    return {
        "mechanism": "tangent_gravity_diagnostic_shadow",
        "profile": "TANGENT_GRAVITY_DIAGNOSTIC_SHADOW_V1",
        "normal_source": "CENTRE_ANALYTIC_CSG_N_HAT",
        "n_receipts": len(receipts),
        "eligible_samples": eligible,
        "flat_samples": flat,
        "nonzero_tangent_gravity_samples": nonzero,
        "gt_magnitude_min": min(mags) if mags else None,
        "gt_magnitude_max": max(mags) if mags else None,
        "gt_magnitude_mean": (sum(mags) / len(mags)) if mags else None,
        "hold_capable_count": hold,
        "breakaway_expected_count": brk,
        "pe_sign_consistent": pe_ok,
        "pe_sign_inconsistent": pe_bad,
        "airborne_ground_tangent_leakage": air_leak,
        "tangent_gravity_active": False,
        "projected_normal_load_active": False,
        "researcher_only": True,
    }


def summarize_tangent_gravity_diagnostic_shadow(world: Any) -> dict[str, Any] | None:
    from mechanistic_mind.physical_system.tangent_gravity_diagnostic_shadow import state_of

    st = state_of(world)
    if st is None:
        return None
    return summarize_tangent_gravity_diagnostic_shadow_events(list(st.history or []))
