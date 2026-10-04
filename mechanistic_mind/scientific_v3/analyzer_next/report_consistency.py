"""Report consistency validator — ERROR / WARNING / INFO."""
from __future__ import annotations

from typing import Any


def validate_report_consistency(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    infos: list[str] = []

    files = payload.get("evidence_files") or []
    counts = payload.get("evidence_counts") or {}
    consumed = int(counts.get("tick_stories") or payload.get("tick_stories_count") or 0)
    if consumed > 0 and (not files or files == ["NONE"] or str(files).upper() == "NONE"):
        errors.append("evidence consumed while Evidence files: NONE")

    hist = payload.get("canonical_history") or {}
    for aid, row in (hist.get("agents") or {}).items():
        wait = int(row.get("wait_count") or 0)
        move = int(row.get("move_count") or 0)
        lw = row.get("longest_wait_streak")
        lm = row.get("longest_move_streak")
        if wait > 0 and int(lw or 0) == 0:
            errors.append(f"{aid}: nonzero WAIT occupancy with zero longest WAIT streak")
        if move > 0 and int(lm or 0) == 0:
            errors.append(f"{aid}: nonzero MOVE occupancy with zero longest MOVE streak")
        ticks = int(row.get("ticks_observed") or row.get("canonical_ticks") or 0)
        if wait + move > ticks > 0:
            errors.append(f"{aid}: WAIT+MOVE occupancy exceeds canonical agent-ticks")
        dr = row.get("decision_receipts")
        if dr is not None and int(dr) == int(payload.get("decision_receipts") or 0) and int(payload.get("decision_receipts") or 0) > ticks > 0:
            errors.append(f"{aid}: global DecisionReceipt count duplicated as per-agent count")

    psc = payload.get("psc_regime") or {}
    enabled = (psc.get("effective_runtime_state") or {}).get("enabled_at_tick")
    trans_n = (psc.get("effective_runtime_state") or {}).get("transition_count")
    regimes = psc.get("regimes") or []
    if enabled and trans_n == 0:
        errors.append("PSC enabled_at present without recorded transition")
    if enabled and regimes and all("OFF" in str(r.get("effective_psc")) for r in regimes):
        errors.append("PSC transition recorded but all regimes labelled OFF")
    hss = payload.get("historical_sensorimotor_selection") or {}
    fun = hss.get("funnel") or {}
    if enabled and int(fun.get("withheld_evaluations") or 0) > 0:
        infos.append(
            "HSS withheld_evaluations remain after PSC ON — this is the O-prime history gate, not PSC OFF"
        )

    vision_text = str(payload.get("beta31_vision_report_text") or "")
    model = str((payload.get("identity") or {}).get("public_preset") or "")
    if "BETA 3.1 VISION ANALYSIS" in vision_text and "ACANTHOSTEGA" in model.upper():
        errors.append("Beta 3.1 section title inside an Acanthostega run")

    layered = payload.get("layered_coverage") or {}
    banner = str(layered.get("banner") or payload.get("coverage") or "")
    aux = str(layered.get("auxiliary") or "")
    if "FULL" in banner.upper() and aux == "PARTIAL" and "AUXILIARY" not in banner.upper():
        errors.append("FULL top-level coverage with auxiliary layers partial and unqualified")
    if str(payload.get("coverage") or "").upper() == "FULL" and aux == "PARTIAL":
        warnings.append("legacy coverage=FULL retained only as core-chain completeness; see layered_coverage")

    ident = payload.get("identity") or {}
    if ident.get("runtime_type") and ident.get("runtime_type") == "UNKNOWN":
        errors.append("runtime identity UNKNOWN despite saved run manifest")

    complete = int(payload.get("complete_odmc_count") or 0)
    expected = int((payload.get("scientific_v3_core") or {}).get("ticks_expected") or payload.get("tick_stories_count") or 0)
    if expected and complete > expected:
        errors.append("complete chains exceed expected agent-ticks")

    status = "ANALYSIS COMPLETE"
    if errors:
        status = "ANALYSIS COMPLETE · REPORT VALIDATION FAILED"
    return {
        "schema": "mm.analyzer.report_consistency.v1",
        "status": status,
        "errors": errors,
        "warnings": warnings,
        "infos": infos,
        "error_count": len(errors),
        "warning_count": len(warnings),
    }
