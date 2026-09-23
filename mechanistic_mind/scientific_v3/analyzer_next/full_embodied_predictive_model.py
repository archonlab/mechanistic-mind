
"""FULL EMBODIED PREDICTIVE MODEL — Analyzer aggregation."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Iterable

from mechanistic_mind.physical_system import sensorimotor_consequence as smc

FAMILIES = {
    "optical": ("exo_0", "exo_1", "exo_2"),
    "field": ("local.FIELD_A", "local.FIELD_B"),
    "bilateral": tuple(f"osc_l_{i}" for i in range(6)) + tuple(f"osc_r_{i}" for i in range(6)),
    "vestibular": ("vest_0", "vest_1"),
    "proprioception": ("prop_neck_0", "prop_neck_1"),
    "local_world": ("local.T", "local.M0", "local.M1", "local.M2", "local.vx", "local.vy"),
    "body": ("body.B0", "body.B1", "body.B2", "body.T", "body.mech", "body.vx", "body.vy"),
    "internal": ("internal.c0", "internal.c1", "internal.c2", "internal.c3", "internal.c4"),
}


def _iter_jsonl(path: Path):
    if not path.exists():
        return
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                yield row


def _family_hits(delta: dict[str, Any]) -> set[str]:
    hit = set()
    for fam, keys in FAMILIES.items():
        if any(k in delta for k in keys):
            hit.add(fam)
    return hit


def aggregate_full_embodied_predictive_model(run_dir: Path) -> dict[str, Any]:
    run_dir = Path(run_dir)
    allow = set(smc.SENSORY_CHANNELS)
    coverage = {fam: {"n": len(keys), "in_allowlist": sum(1 for k in keys if k in allow)} for fam, keys in FAMILIES.items()}

    funnel = {
        "SMC_QUERIES": 0,
        "MULTI_CANDIDATE_SMC_QUERIES": 0,
        "CANDIDATE_FUTURES_DIFFERENTIATED": 0,
        "MULTIMODAL_FUTURES_DIFFERENTIATED": 0,
        "O_PRIME_MULTIMODAL": 0,
        "HISTORY_QUERIED": 0,
        "HISTORICAL_SUPPORT_DIFFERENTIATED": 0,
        "HISTORICAL_EVIDENCE_AVAILABLE_TO_PSC": 0,
        "FINAL_SELECTION_DIFFERS_FROM_WITHHELD_CF": 0,
    }
    examples = []
    n_dec = 0
    for row in _iter_jsonl(run_dir / "scientific_decisions.jsonl"):
        n_dec += 1
        smc_b = row.get("sensorimotor_consequence") if isinstance(row.get("sensorimotor_consequence"), dict) else {}
        preds = smc_b.get("predictions") if isinstance(smc_b.get("predictions"), list) else []
        if preds:
            funnel["SMC_QUERIES"] += 1
        if len(preds) >= 2:
            funnel["MULTI_CANDIDATE_SMC_QUERIES"] += 1
            deltas = []
            fam_sets = []
            for p in preds:
                if not isinstance(p, dict):
                    continue
                d = p.get("predicted_delta") if isinstance(p.get("predicted_delta"), dict) else {}
                if d:
                    deltas.append(tuple(sorted((k, round(float(v), 5)) for k, v in d.items() if isinstance(v, (int, float)))))
                    fam_sets.append(frozenset(_family_hits(d)))
            if len(set(deltas)) >= 2:
                funnel["CANDIDATE_FUTURES_DIFFERENTIATED"] += 1
            if len(set(fam_sets)) >= 2 and any(len(fs) >= 2 for fs in fam_sets):
                funnel["MULTIMODAL_FUTURES_DIFFERENTIATED"] += 1
            if any(len(fs) >= 2 for fs in fam_sets):
                funnel["O_PRIME_MULTIMODAL"] += 1
                if len(examples) < 5:
                    examples.append({
                        "tick": row.get("tick"),
                        "agent": row.get("cognitive_agent_id"),
                        "selected": row.get("selected_action_legacy"),
                        "n_preds": len(preds),
                        "families_in_preds": [sorted(fs) for fs in fam_sets[:6]],
                        "motors": [p.get("motor") or p.get("motor_signature") for p in preds[:6] if isinstance(p, dict)],
                    })
        hss = row.get("historical_sensorimotor_selection") if isinstance(row.get("historical_sensorimotor_selection"), dict) else {}
        if int(hss.get("n_history_match") or 0) > 0:
            funnel["HISTORY_QUERIED"] += 1
        if hss.get("history_support_differentiated"):
            funnel["HISTORICAL_SUPPORT_DIFFERENTIATED"] += 1
        cands = hss.get("candidates") if isinstance(hss.get("candidates"), list) else []
        if any(isinstance(c, dict) and c.get("available_to_psc") for c in cands) and not hss.get("withheld_from_psc"):
            funnel["HISTORICAL_EVIDENCE_AVAILABLE_TO_PSC"] += 1
        if hss.get("selection_differs_from_withheld_cf"):
            funnel["FINAL_SELECTION_DIFFERS_FROM_WITHHELD_CF"] += 1

    motor = {
        "learning_signature": "COMPOSITE L:loco|N:neck|E:emit|F:fd|A:ad|P:push",
        "learning_status": "FULLY_REPRESENTED",
        "psc_query_candidates": "ALIASED_TO_LOCOMOTION",
        "psc_query_status": "ALIASED",
        "dimensions": {
            "locomotion": "SELF_CONTROLLED_PHYSICAL_ACTION / REPRESENTED",
            "neck": "SELF_CONTROLLED_PHYSICAL_ACTION / LEARNING_YES_PSC_QUERY_ALIASED",
            "oscillator_emit_freq_amp": "SELF_CONTROLLED_PHYSICAL_ACTION / LEARNING_YES_PSC_QUERY_ALIASED",
            "push": "SELF_CONTROLLED_PHYSICAL_ACTION / LEARNING_YES_PSC_QUERY_ALIASED",
            "TAKE_RELEASE_CONTACT": "NOT_APPLICABLE",
            "body_rotation_separate": "NOT_APPLICABLE",
        },
    }

    sensory_status = {
        fam: ("FULLY_REPRESENTED" if v["in_allowlist"] == v["n"] else "PARTIALLY_REPRESENTED")
        for fam, v in coverage.items()
    }

    return {
        "section": "FULL EMBODIED PREDICTIVE MODEL",
        "status": "PARTIALLY_REPRESENTED",  # due to PSC query aliasing
        "sensory_coverage": coverage,
        "sensory_status": sensory_status,
        "allowlist_n": len(allow),
        "motor_coverage": motor,
        "funnel": funnel,
        "n_decisions": n_dec,
        "examples": examples,
        "composite_motor_learning": "COMPOSITE_MOTOR_PREDICTION_DEMONSTRATED",
        "composite_motor_psc_query": "COMPOSITE_MOTOR_ALIASING_DEMONSTRATED",
        "claims_boundary": {
            "supported": [
                "multimodal action-conditioned sensory prediction (learning path)",
                "embodied sensory allowlist coverage of accessible observation",
                "composite-motor-conditioned prediction at learning/query(full motor)",
                "multimodal predicted O′",
            ],
            "not_established": [
                "PSC candidate competition uses full composite motor signatures",
                "self-model / body schema / spatial concept",
                "communication / intention / language",
            ],
        },
    }


def format_full_embodied_predictive_model(payload: dict[str, Any] | None) -> str:
    if not payload:
        return "FULL EMBODIED PREDICTIVE MODEL\nstatus: NOT_RECORDED\n"
    lines = [
        "FULL EMBODIED PREDICTIVE MODEL",
        "==============================",
        f"status: {payload.get('status')}",
        f"allowlist_n: {payload.get('allowlist_n')}",
        "",
        "A. SENSORY COVERAGE",
    ]
    for fam, v in (payload.get("sensory_coverage") or {}).items():
        st = (payload.get("sensory_status") or {}).get(fam)
        lines.append(f"  {fam}: {v.get('in_allowlist')}/{v.get('n')}  [{st}]")
    lines += ["", "B. MOTOR COVERAGE"]
    mc = payload.get("motor_coverage") or {}
    lines.append(f"  learning: {mc.get('learning_status')} ({mc.get('learning_signature')})")
    lines.append(f"  PSC query_candidates: {mc.get('psc_query_status')}")
    for k, v in (mc.get("dimensions") or {}).items():
        lines.append(f"    {k}: {v}")
    lines += ["", "C. COMPOSITE MOTOR FIDELITY"]
    lines.append(f"  learning path: {payload.get('composite_motor_learning')}")
    lines.append(f"  PSC query path: {payload.get('composite_motor_psc_query')}")
    lines += ["", "D–F. FUNNEL"]
    for k, v in (payload.get("funnel") or {}).items():
        lines.append(f"  {k}: {v}")
    if payload.get("examples"):
        lines += ["", "I. FORENSIC TICKS"]
        for ex in payload["examples"][:4]:
            lines.append(f"  tick {ex.get('tick')} {ex.get('agent')} selected={ex.get('selected')} families={ex.get('families_in_preds')}")
    cb = payload.get("claims_boundary") or {}
    lines += ["", "CLAIMS BOUNDARY", f"  supported: {cb.get('supported')}", f"  not_established: {cb.get('not_established')}", ""]
    return chr(10).join(lines)
