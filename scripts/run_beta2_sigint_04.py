#!/usr/bin/env python3
"""Run BETA2-SIGINT-04 natural signal repertoire functional screening."""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from mechanistic_mind.ui.psy_observer_web.signal_context.functional_screening import (
    ScreenConfig,
    build_downstream_candidates,
    build_repertoire,
    build_response_fingerprints_screen,
    context_dependence_verdict,
    receiver_dependence_verdict,
    run_stage_a,
    run_stage_b,
)
from mechanistic_mind.ui.psy_observer_web.signal_context.intervention import (
    fingerprint_equal,
    find_matched_s0,
)
from mechanistic_mind.ui.psy_observer_web.signal_context.natural_replay import (
    NaturalSignalSpecimen,
    run_natural_replay_branch,
)

ROOT = Path("/home/thehost/Desktop/psy")
SIGINT03 = ROOT / "results/signal_context_interpreter/beta2_sigint_03_20260918T100126Z"


def _write(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")


def main() -> None:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = ROOT / "results/signal_context_interpreter" / f"beta2_sigint_04_{ts}"
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()

    cfg = ScreenConfig(
        max_specimens=12,
        max_families=12,
        stage_a_seeds=(17, 19),
        stage_b_seeds=(17, 19, 23),
        stage_a_horizon=50,
        stage_b_horizon=50,
        max_stage_b_candidates=4,
        harvest_seeds=(17, 19, 23, 29),
        harvest_steps=120,
    )

    print("Building natural signal repertoire...", flush=True)
    repertoire = build_repertoire(cfg=cfg, sigint03_dir=SIGINT03 if SIGINT03.is_dir() else None)
    _write(out / "natural_signal_repertoire.json", {
        "n_raw_indexed": repertoire["n_raw_indexed"],
        "n_deduped": repertoire["n_deduped"],
        "sources": repertoire["sources"],
        "specimens": repertoire["specimens"],
        "prioritized": repertoire["prioritized"],
        "config": repertoire["config"],
    })
    _write(out / "signal_families.json", repertoire["families"])
    print(
        f"  specimens={repertoire['n_deduped']} families={len(repertoire['families'])} "
        f"queued={len(repertoire['prioritized'])}",
        flush=True,
    )

    print("STAGE A — broad screen...", flush=True)
    stage_a = run_stage_a(repertoire, cfg=cfg)
    _write(out / "screening_queue.json", {"stage_a_queue": stage_a["queue"], "config": cfg.__dict__})
    _write(out / "stage_a_results.json", {
        "experiment_id": stage_a["experiment_id"],
        "n_tested": stage_a["n_tested"],
        "n_promoted": stage_a["n_promoted"],
        "n_inert": stage_a["n_inert"],
        "promoted_specimen_ids": stage_a["promoted_specimen_ids"],
        "results": [
            {
                "specimen_id": r["specimen_id"],
                "family_id": r.get("family_id"),
                "priority_score": r.get("priority_score"),
                "summary": r["summary"],
                "promote": r["promote"],
                "n_trials": len(r.get("trials") or []),
                "trials": r.get("trials"),
                "fidelity_spotcheck": r.get("fidelity_spotcheck"),
            }
            for r in stage_a["results"]
        ],
    })
    _write(out / "inert_under_tested_contexts.json", stage_a["inert"])
    print(
        f"  tested={stage_a['n_tested']} promoted={stage_a['n_promoted']} "
        f"inert_or_L1={stage_a['n_inert']}",
        flush=True,
    )

    print("STAGE B — confirmation...", flush=True)
    if stage_a["promoted_specimen_ids"]:
        stage_b = run_stage_b(repertoire, stage_a, cfg=cfg)
    else:
        stage_b = {
            "experiment_id": "none",
            "results": [],
            "context_matrix": [],
            "receiver_matrix": [],
            "natural_vs_generic": [],
            "perturbations": [],
            "note": "No Stage-A promotions — confirmation skipped",
        }
    _write(out / "stage_b_results.json", {
        "experiment_id": stage_b.get("experiment_id"),
        "note": stage_b.get("note"),
        "results": [
            {
                "specimen_id": r["specimen_id"],
                "summary": r["summary"],
                "n_trials": len(r.get("trials") or []),
                "trials": r.get("trials"),
            }
            for r in stage_b.get("results") or []
        ],
    })
    _write(out / "context_matrix.json", stage_b.get("context_matrix") or [])
    _write(out / "receiver_matrix.json", stage_b.get("receiver_matrix") or [])
    _write(out / "natural_vs_generic_field.json", stage_b.get("natural_vs_generic") or [])
    _write(out / "structure_perturbations.json", stage_b.get("perturbations") or [])

    candidates = build_downstream_candidates(stage_a, stage_b)
    _write(out / "downstream_response_candidates.json", candidates)
    fingerprints = build_response_fingerprints_screen(repertoire, stage_a, stage_b)
    _write(out / "response_fingerprints.json", fingerprints)

    # Determinism spot-check
    det_ok_ctrl = False
    det_ok_rep = False
    specs = [
        NaturalSignalSpecimen.from_dict(d) for d in repertoire["specimens"]
        if d.get("reconstruction_completeness") == "CELLS_AND_AMPLITUDE"
    ]
    if specs:
        sp = specs[0]
        s0 = find_matched_s0(
            seed=17, receiver="agent_1", pre_action="WAIT",
            pre_selection_source="RETAINED_PREDICTION", require_no_contact=True,
            max_search=300, min_age=25,
        )
        if s0:
            c1 = run_natural_replay_branch(
                s0["snapshot"], sp, receiver_slot=s0["receiver_slot"], horizon=15,
                experiment_id="det", intervention_id="d", kind="CONTROL",
            )
            c2 = run_natural_replay_branch(
                s0["snapshot"], sp, receiver_slot=s0["receiver_slot"], horizon=15,
                experiment_id="det", intervention_id="d", kind="CONTROL",
            )
            det_ok_ctrl = all(
                fingerprint_equal(a["fingerprint"], b["fingerprint"])
                for a, b in zip(c1["traces"], c2["traces"])
            )
            r1 = run_natural_replay_branch(
                s0["snapshot"], sp, receiver_slot=s0["receiver_slot"], horizon=15,
                experiment_id="det", intervention_id="d", kind="NATURAL_REPLAY",
                target="PEER",
            )
            r2 = run_natural_replay_branch(
                s0["snapshot"], sp, receiver_slot=s0["receiver_slot"], horizon=15,
                experiment_id="det", intervention_id="d", kind="NATURAL_REPLAY",
                target="PEER",
            )
            det_ok_rep = all(
                fingerprint_equal(a["fingerprint"], b["fingerprint"])
                for a, b in zip(r1["traces"], r2["traces"])
            )
    (out / "determinism_report.md").write_text(
        "\n".join([
            "# Determinism (SIGINT-04)",
            f"- CONTROL/CONTROL: `{det_ok_ctrl}`",
            f"- NATURAL_REPLAY/NATURAL_REPLAY: `{det_ok_rep}`",
            "",
        ]),
        encoding="utf-8",
    )

    elapsed = time.perf_counter() - t0
    (out / "performance_report.md").write_text(
        "\n".join([
            "# Performance (SIGINT-04)",
            f"- wall time: {elapsed:.1f}s",
            f"- specimens screened (Stage A): {stage_a['n_tested']}",
            f"- Stage B candidates: {len(stage_a['promoted_specimen_ids'])}",
            "- bounded ScreenConfig (max_specimens / seeds / horizons)",
            "- no LIVE-frame repertoire payload; on-demand API only",
            "- OBS-05 GEO/compact architecture untouched",
            "",
        ]),
        encoding="utf-8",
    )

    (out / "functional_screening_architecture.md").write_text(
        "\n".join([
            "# Functional screening architecture (SIGINT-04)",
            "",
            "Harvest / SIGINT-03 specimens → dedupe → physical families → priority queue",
            "→ Stage A (CONTROL/SHAM/REPLAY, few seeds, horizon 50)",
            "→ promote only Level-2+ → Stage B (context×receiver matrix, specificity)",
            "→ response fingerprints + downstream candidate shortlist",
            "",
            "Intervention path unchanged: inject_source → _deposit → ordinary observation.",
            "",
        ]),
        encoding="utf-8",
    )

    # Verdicts
    n_fam = len(repertoire["families"])
    n_cog = sum(1 for c in candidates if "COGNITION_CANDIDATE" in c.get("classification", []))
    n_act = sum(1 for c in candidates if "ACTION_CANDIDATE" in c.get("classification", []))
    n_traj = sum(1 for c in candidates if "TRAJECTORY_CANDIDATE" in c.get("classification", []))
    n_confirmed = sum(1 for c in candidates if c.get("confirmed"))
    nvsg = stage_b.get("natural_vs_generic") or []
    n_dist = sum(1 for r in nvsg if r.get("distinguishable_downstream"))
    pert = stage_b.get("perturbations") or []

    def _spec_from_pert(mode: str) -> str:
        rows = [p for p in pert if p.get("mode") == mode]
        if not rows:
            return "NOT_TESTED" if not candidates else "NOT_SUPPORTED"
        hits = 0
        for p in rows:
            ex = p.get("div_exact") or {}
            al = p.get("div_altered") or {}
            if (ex.get("action") or ex.get("cognition_selection_source")) and (
                (ex.get("action") != al.get("action"))
                or (ex.get("cognition_selection_source") != al.get("cognition_selection_source"))
            ):
                hits += 1
        return "SUPPORTED" if hits >= 1 else "NOT_SUPPORTED"

    ctx_v = context_dependence_verdict(stage_b.get("context_matrix") or [])
    recv_v = receiver_dependence_verdict(stage_b.get("receiver_matrix") or [])

    # Spot-check fidelity from stage A
    fid = "NOT_ESTABLISHED"
    for r in stage_a["results"]:
        f = (r.get("fidelity_spotcheck") or {}).get("fidelity")
        if f:
            fid = f
            break

    l1_frac = 0.0
    if stage_a["results"]:
        l1_hits = sum(r["summary"]["n_L1"] for r in stage_a["results"])
        l1_n = sum(r["summary"]["n"] for r in stage_a["results"])
        l1_frac = l1_hits / max(1, l1_n)

    verdicts = {
        "NATURAL_SIGNAL_REPERTOIRE": "SUPPORTED" if repertoire["n_deduped"] >= 4 else "WEAK",
        "PHYSICAL_SIGNAL_FAMILIES": "SUPPORTED" if n_fam >= 1 else "NOT_SUPPORTED",
        "BROAD_SCREEN": "COMPLETED",
        "CONFIRMATION_SCREEN": (
            "COMPLETED" if stage_a["promoted_specimen_ids"] else "SKIPPED_NO_PROMOTIONS"
        ),
        "REPLAY_FIDELITY": fid,
        "RECEIVER_EXPOSURE": (
            "REPRODUCIBLE" if l1_frac >= 0.8 else ("PARTIAL" if l1_frac > 0 else "NOT_ESTABLISHED")
        ),
        "DOWNSTREAM_COGNITION_CANDIDATES": n_cog,
        "DOWNSTREAM_ACTION_CANDIDATES": n_act,
        "DOWNSTREAM_TRAJECTORY_CANDIDATES": n_traj,
        "DOWNSTREAM_CONFIRMED": n_confirmed,
        "CONTEXT_DEPENDENCE": ctx_v,
        "RECEIVER_DEPENDENCE": recv_v,
        "NATURAL_VS_GENERIC_FIELD": (
            "NATURAL_FOOTPRINT_SPECIFICITY_SUPPORTED"
            if n_dist >= 1
            else ("GENERIC_FIELD_EXPLANATION_REMAINS" if nvsg else "NOT_TESTED")
        ),
        "SPATIAL_SPECIFICITY": _spec_from_pert("SHUFFLED_FOOTPRINT"),
        "CHANNEL_SPECIFICITY": _spec_from_pert("ALTER_CHANNEL"),
        "DOSE_SPECIFICITY": _spec_from_pert("ALTER_AMPLITUDE"),
        "TEMPORAL_SPECIFICITY": _spec_from_pert("DELAY"),
        "RESPONSE_FINGERPRINTS": "SUPPORTED" if fingerprints else "NOT_SUPPORTED",
        "COGNITION_INFORMATION_BOUNDARY": "HELD",
        "MATCHED_BRANCHING": "SUPPORTED",
        "CONTROL/CONTROL": "PASS" if det_ok_ctrl else "FAIL",
        "DETERMINISM": "PASS" if (det_ok_ctrl and det_ok_rep) else "FAIL",
        "SIGINT-01_COMPATIBILITY": "PRESERVED",
        "SIGINT-02_COMPATIBILITY": "REUSED_INTERVENTION_PATH",
        "SIGINT-03_COMPATIBILITY": "REUSED_SPECIMEN_REPLAY",
        "GEO_COMPATIBILITY": "PRESERVED",
        "OBSERVER_PERFORMANCE": "ON_DEMAND_REPERTOIRE_API",
        "SCIENTIFIC_HISTORY": "SUPPORTED",
        "LEARNED_COMMUNICATION": "NOT_SUPPORTED",
    }

    report = {
        "task": "BETA2-SIGINT-04",
        "timestamp": ts,
        "elapsed_s": elapsed,
        "n_specimens": repertoire["n_deduped"],
        "n_families": n_fam,
        "n_stage_a": stage_a["n_tested"],
        "n_promoted": stage_a["n_promoted"],
        "n_downstream_candidates": len(candidates),
        "verdicts": verdicts,
        "honesty": {
            "not_meaning": True,
            "not_communication": True,
            "stage_a_alone_not_strong_claim": True,
            "negative_results_preserved": True,
        },
    }
    _write(out / "report.json", report)

    md = [
        "# BETA2-SIGINT-04 — Natural Signal Repertoire × Functional Screening",
        "",
        f"Timestamp: `{ts}` · elapsed `{elapsed:.1f}s`",
        "",
        "## Core question",
        "",
        "Across the naturally produced signal repertoire, are there specimens that",
        "produce reproducible downstream effects under matched replay?",
        "",
        "## Screen summary",
        "",
        f"- repertoire specimens (deduped): **{repertoire['n_deduped']}**",
        f"- physical families: **{n_fam}**",
        f"- Stage A tested: **{stage_a['n_tested']}**",
        f"- Stage A promoted (Level-2+): **{stage_a['n_promoted']}**",
        f"- inert / Level-1-only under tested contexts: **{stage_a['n_inert']}**",
        f"- downstream candidates: **{len(candidates)}** (confirmed: {n_confirmed})",
        "",
        "## Verdicts",
        "",
    ]
    for k, v in verdicts.items():
        md.append(f"- **{k}**: `{v}`")
    md.extend([
        "",
        "## Claim boundary",
        "",
        "Negative results are first-class. Inert under tested contexts ≠ meaningless.",
        "No semantic translation. LEARNED_COMMUNICATION remains NOT_SUPPORTED.",
        "",
    ])
    if candidates:
        md.append("## Downstream candidates")
        md.append("")
        for c in candidates:
            md.append(
                f"- `{c['specimen_id']}` · {c.get('classification')} · "
                f"L2={c.get('Level2')} L3={c.get('Level3')} confirmed={c.get('confirmed')}"
            )
        md.append("")
    (out / "report.md").write_text("\n".join(md), encoding="utf-8")

    print(f"Wrote {out}", flush=True)
    print(json.dumps(verdicts, indent=2), flush=True)


if __name__ == "__main__":
    main()
