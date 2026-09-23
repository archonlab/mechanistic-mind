"""OBSERVED_COMPOSITE — experimental production PSC motor resolution.

Default production remains LOCO_FACTORIZED. This module is used only when
`psc_motor_resolution == "OBSERVED_COMPOSITE"` is set explicitly.

Reuses validated production functions (same as full-composite shadow replay):
  - sensorimotor_consequence.query (exact composite)
  - o_prime_history_bridge.construct_o_prime / query_history_on_o_prime / build_psc_scenario
  - scenario_competition.compete_scenarios

NO Cartesian invention. NO adaptive refinement. NO new scorer.
"""
from __future__ import annotations

from typing import Any

from mechanistic_mind.physical_system import sensorimotor_consequence as smc
from mechanistic_mind.physical_system import o_prime_history_bridge as oph
from mechanistic_mind.physical_system import scenario_competition as sc
from mechanistic_mind.physical_system.composite_motor import (
    CompositeMotorOutput,
    OscillatorMotorComponent,
    NECK_NONE,
)
from mechanistic_mind.physical_system.psc_motor_resolution_shadow import (
    composite_query,
    observed_composites_for_loco,
    parse_motor_signature,
)

MODE_LOCO = "LOCO_FACTORIZED"
MODE_OBSERVED = "OBSERVED_COMPOSITE"
ALLOWED_MODES = (MODE_LOCO, MODE_OBSERVED)


def normalize_mode(raw: Any) -> str:
    """Missing / unknown / legacy → LOCO_FACTORIZED (safe default)."""
    s = str(raw or "").strip().upper().replace("-", "_").replace(" ", "_")
    if s in {"OBSERVED_COMPOSITE", "OBSERVEDCOMPOSITE", "FULL_COMPOSITE", "OBSERVED"}:
        return MODE_OBSERVED
    return MODE_LOCO


def motor_from_parsed(parsed: dict[str, Any], *, source: str = "OBSERVED_COMPOSITE_PSC") -> CompositeMotorOutput:
    osc_d = parsed.get("oscillator") or {}
    out = CompositeMotorOutput(
        locomotion=str(parsed.get("locomotion") or "WAIT"),
        neck=str(parsed.get("neck") or NECK_NONE),
        oscillator=OscillatorMotorComponent(
            emit_trigger=bool(osc_d.get("emit_trigger")),
            frequency_delta=int(osc_d.get("frequency_delta") or 0),
            amplitude_delta=int(osc_d.get("amplitude_delta") or 0),
        ),
        push=bool(parsed.get("push")),
        selection_source=source,
        domain_sources={
            "locomotion": source,
            "neck": source,
            "oscillator": source,
            "push": source,
            "resolution": MODE_OBSERVED,
        },
    )
    out.legacy_token = out.compute_legacy_token()
    return out


def motor_from_signature(sig: str, *, source: str = "OBSERVED_COMPOSITE_PSC") -> CompositeMotorOutput | None:
    parsed = parse_motor_signature(sig)
    if not parsed:
        return None
    return motor_from_parsed(parsed, source=source)


def _match_kind(pred: dict[str, Any]) -> str:
    st = pred.get("status")
    reason = str(pred.get("reason") or "")
    if st == smc.UNKNOWN or not pred.get("predicted_delta"):
        return "UNKNOWN"
    if "loco_prefix" in reason:
        return "LOCO_FALLBACK"
    if st in {smc.MATCH, smc.LOW_SUPPORT}:
        return "EXACT_COMPOSITE_MATCH"
    return "SOFT_EXISTING_MATCH"


def collect_observed_candidates(
    *,
    observation: dict[str, float],
    smc_store: dict[str, Any],
    loco_candidates: list[str],
    prospection: dict[str, Any],
    compression: dict[str, Any] | None,
    retrieval_enabled: bool,
    tick: int | None,
    min_support: int = 1,
) -> list[dict[str, Any]]:
    """Empirical composites only — no Cartesian product."""
    rows: list[dict[str, Any]] = []
    history_actions = list(loco_candidates)
    for loco in loco_candidates:
        for c in observed_composites_for_loco(smc_store, loco):
            if int(c.get("support") or 0) < min_support:
                continue
            motor = c["motor"]
            # Query live store for production (updates query counters — intentional)
            pred = smc.query(smc_store, observation=observation, motor=motor, tick=tick)
            kind = _match_kind(pred)
            # Do not collapse via loco_prefix_aggregate
            if kind == "LOCO_FALLBACK" or kind == "UNKNOWN":
                continue
            if pred.get("status") not in {smc.MATCH, smc.LOW_SUPPORT}:
                continue
            if not pred.get("predicted_delta"):
                continue
            meta = oph.construct_o_prime(observation, pred.get("predicted_delta"))
            hist = oph.query_history_on_o_prime(
                prospection=prospection,
                compression=compression,
                o_prime=meta["o_prime"],
                actions=list(history_actions),
                retrieval_enabled=retrieval_enabled,
            )
            pred_tagged = {**pred, "candidate_locomotion": loco}
            scn = oph.build_psc_scenario(
                loco=str(c["motor_signature"]),
                o_prime=meta["o_prime"],
                history=hist,
                smc_pred=pred_tagged,
                construct_meta=meta,
            )
            if not scn:
                continue
            rows.append({
                "motor_signature": str(c["motor_signature"]),
                "locomotion": loco,
                "motor": motor,
                "smc_match_kind": kind,
                "smc_support": pred.get("support"),
                "smc_record_id": pred.get("record_id"),
                "smc_reliability": pred.get("reliability"),
                "predicted_fields": meta.get("predicted_fields"),
                "o_prime_ref": {
                    "n_predicted_fields": len(meta.get("predicted_fields") or []),
                    "predicted_fields": list(meta.get("predicted_fields") or [])[:12],
                },
                "history_ref": {
                    "status": hist.get("status"),
                    "historical_support": hist.get("historical_support"),
                    "reliability": hist.get("reliability"),
                    "depth": hist.get("depth"),
                },
                "scenario": scn,
                "provenance": {
                    "path": MODE_OBSERVED,
                    "store_support": c.get("support"),
                    "record_id": c.get("record_id"),
                },
            })
    # Deduplicate by motor_signature (authoritative)
    by_sig: dict[str, dict[str, Any]] = {}
    for r in rows:
        sig = r["motor_signature"]
        prev = by_sig.get(sig)
        if prev is None or int(r.get("smc_support") or 0) > int(prev.get("smc_support") or 0):
            by_sig[sig] = r
    return list(by_sig.values())


def compete_observed(
    candidates: list[dict[str, Any]],
    *,
    rng_value: float,
) -> dict[str, Any]:
    groups: dict[str, list] = {}
    actions: list[str] = []
    for r in candidates:
        scn = r.get("scenario")
        if not scn:
            continue
        key = str(r["motor_signature"])
        groups.setdefault(key, []).append(sc.jsonish_copy(scn))
        if key not in actions:
            actions.append(key)
    if not actions:
        return {
            "status": "NO_SCENARIOS",
            "selected": None,
            "competition": {"outcome_class": "NO_SUPPORT"},
            "n_candidates": 0,
        }
    result = sc.compete_scenarios(
        groups=sc.jsonish_copy(groups),
        actions=list(actions),
        rng_value=float(rng_value),
    )
    selected = result.get("selected")
    winner = next((r for r in candidates if r["motor_signature"] == selected), None)
    return {
        "status": "OK",
        "selected": selected,
        "winner": winner,
        "source": result.get("source"),
        "selection_rule": result.get("selection_rule"),
        "competition": result.get("competition") or {},
        "n_candidates": len(actions),
        "candidate_signatures": list(actions),
    }


def select_observed_composite_motor(
    *,
    observation: dict[str, float],
    smc_store: dict[str, Any],
    loco_candidates: list[str],
    prospection: dict[str, Any],
    compression: dict[str, Any] | None,
    retrieval_enabled: bool,
    tick: int | None,
    rng_value: float,
) -> dict[str, Any]:
    """Full production path. Returns motor + evidence or status FALLBACK_LOCO."""
    cands = collect_observed_candidates(
        observation=observation,
        smc_store=smc_store,
        loco_candidates=loco_candidates,
        prospection=prospection,
        compression=compression,
        retrieval_enabled=retrieval_enabled,
        tick=tick,
    )
    exact_n = sum(1 for c in cands if c.get("smc_match_kind") == "EXACT_COMPOSITE_MATCH")
    competed = compete_observed(cands, rng_value=rng_value)
    if competed.get("status") != "OK" or not competed.get("winner"):
        return {
            "status": "FALLBACK_LOCO",
            "reason": "INSUFFICIENT_COMPOSITE_EVIDENCE",
            "n_candidates": len(cands),
            "exact_composite_matches": exact_n,
            "candidates": cands,
            "competition": competed.get("competition"),
            "motor": None,
        }
    winner = competed["winner"]
    motor = motor_from_parsed(winner["motor"], source="OBSERVED_COMPOSITE_PSC")
    return {
        "status": "SELECTED",
        "reason": "OBSERVED_COMPOSITE_COMPETE",
        "n_candidates": competed.get("n_candidates"),
        "exact_composite_matches": exact_n,
        "candidate_signatures": competed.get("candidate_signatures"),
        "candidates": [
            {
                "motor_signature": c["motor_signature"],
                "smc_match_kind": c["smc_match_kind"],
                "smc_support": c["smc_support"],
                "smc_record_id": c["smc_record_id"],
                "history_ref": c["history_ref"],
                "o_prime_ref": c["o_prime_ref"],
                "provenance": c["provenance"],
            }
            for c in cands
        ],
        "selected_signature": winner["motor_signature"],
        "selected_locomotion": winner["locomotion"],
        "competition": competed.get("competition"),
        "compete_source": competed.get("source"),
        "motor": motor,
        "winner_row": winner,
    }
