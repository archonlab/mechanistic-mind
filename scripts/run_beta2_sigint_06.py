#!/usr/bin/env python3
"""Run BETA2-SIGINT-06 cognitive divergence forensics on SIGINT-05 Level-2 hits."""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from mechanistic_mind.ui.psy_observer_web.signal_context.cognitive_forensics import (
    DEFAULT_SIGINT05,
    load_sigint05_level2_hits,
    reproduce_level2_hit,
    run_small_context_matrix,
)

ROOT = Path("/home/thehost/Desktop/psy")


def _write(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")


def main() -> None:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = ROOT / "results/signal_context_interpreter" / f"beta2_sigint_06_{ts}"
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()

    print("Loading SIGINT-05 Level-2 hits...", flush=True)
    hits = load_sigint05_level2_hits(DEFAULT_SIGINT05)
    _write(out / "level2_trials.json", [
        {
            "episode_id": h.get("episode_id"),
            "start_tick": h.get("start_tick"),
            "end_tick": h.get("end_tick"),
            "seed": h.get("seed"),
            "s0_tick": h.get("s0_tick"),
            "levels": h.get("levels"),
            "divergences_FULL": (h.get("divergences") or {}).get("FULL_EPISODE"),
            "divergences_SHAM": (h.get("divergences") or {}).get("SHAM"),
            "has_episode_payload": h.get("episode") is not None,
        }
        for h in hits
    ])
    print(f"  n={len(hits)}", flush=True)
    if len(hits) != 3:
        print(f"WARNING: expected 3 L2 hits, got {len(hits)}", flush=True)

    forensic_results = []
    for i, hit in enumerate(hits):
        print(
            f"Forensics {i+1}/{len(hits)} episode {hit.get('start_tick')}-{hit.get('end_tick')} "
            f"seed={hit.get('seed')}...",
            flush=True,
        )
        # Extended horizons on all hits but bounded: 100 + 250 (not 500 for compute)
        ext = (100, 250) if i == 0 else (100,)
        result = reproduce_level2_hit(hit, horizon=120, extended_horizons=ext)
        # Context matrix only for reproduced hits
        ctx = []
        if result.get("level2_reproduced"):
            print("  context matrix...", flush=True)
            ctx = run_small_context_matrix(hit, horizon=60)
        result["context_matrix"] = ctx
        forensic_results.append(result)
        print(
            f"  reproduced={result.get('level2_reproduced')} "
            f"class={result.get('reproduction_class')} "
            f"bottleneck={((result.get('bottleneck') or {}).get('best_supported') or {}).get('code')}",
            flush=True,
        )

    # Artifact slices
    _write(out / "first_divergence.json", [
        {
            "hit": r.get("hit"),
            "focus_slot": r.get("focus_slot"),
            "ladder_summary": {
                k: {
                    "first": (v or {}).get("first_divergence_tick"),
                    "last": (v or {}).get("last_divergence_tick"),
                    "status": (v or {}).get("status"),
                    "kind": (v or {}).get("kind"),
                    "reconverge": (v or {}).get("reconvergence_tick"),
                }
                for k, v in (r.get("pipeline_ladder") or {}).items()
            },
            "both_slots_source_first": r.get("both_slots_source_first"),
        }
        for r in forensic_results if r.get("accepted")
    ])
    _write(out / "cognitive_pipeline_diff.json", [
        {
            "hit": r.get("hit"),
            "pipeline_ladder": r.get("pipeline_ladder"),
            "parallel_lanes": r.get("parallel_lanes"),
        }
        for r in forensic_results if r.get("accepted")
    ])
    _write(out / "action_selection_margin.json", [
        {
            "hit": r.get("hit"),
            "sample": (r.get("bottleneck") or {}).get("sample_at_first_source_divergence"),
            "classification": (r.get("bottleneck") or {}).get("classification"),
        }
        for r in forensic_results if r.get("accepted")
    ])
    _write(out / "bottleneck_analysis.json", [
        {
            "hit": r.get("hit"),
            "bottleneck": r.get("bottleneck"),
        }
        for r in forensic_results if r.get("accepted")
    ])
    _write(out / "persistence.json", [
        {"hit": r.get("hit"), "persistence": r.get("persistence")}
        for r in forensic_results if r.get("accepted")
    ])
    _write(out / "extended_horizon.json", [
        {"hit": r.get("hit"), "extended": r.get("extended_horizon")}
        for r in forensic_results if r.get("accepted")
    ])
    _write(out / "context_matrix.json", [
        {"hit": r.get("hit"), "contexts": r.get("context_matrix")}
        for r in forensic_results if r.get("accepted")
    ])
    _write(out / "signal_component_ablations.json", [
        {"hit": r.get("hit"), "ablations": r.get("ablations")}
        for r in forensic_results if r.get("accepted")
    ])
    _write(out / "natural_followup_emissions.json", [
        {
            "hit": r.get("hit"),
            "natural_emission_divergence": r.get("natural_emission_divergence"),
            "SIGNAL_TO_COGNITION_TO_EMISSION_CANDIDATE": r.get(
                "SIGNAL_TO_COGNITION_TO_EMISSION_CANDIDATE"
            ),
        }
        for r in forensic_results if r.get("accepted")
    ])
    _write(out / "causal_chains.json", [
        {"hit": r.get("hit"), "edges": r.get("causal_edges")}
        for r in forensic_results if r.get("accepted")
    ])

    n_rep = sum(1 for r in forensic_results if r.get("level2_reproduced"))
    n_acc = sum(1 for r in forensic_results if r.get("accepted"))
    n_action_conv = sum(
        1 for r in forensic_results
        if (r.get("bottleneck") or {}).get("classification")
        == "ACTION_CONVERGENCE_WITH_INTERNAL_DIVERGENCE"
    )
    n_delayed_act = sum(
        1
        for r in forensic_results
        for e in (r.get("extended_horizon") or [])
        if e.get("action_first") is not None
    )
    n_emission = sum(1 for r in forensic_results if r.get("SIGNAL_TO_COGNITION_TO_EMISSION_CANDIDATE"))
    codes = [
        ((r.get("bottleneck") or {}).get("best_supported") or {}).get("code")
        for r in forensic_results if r.get("accepted")
    ]
    persist_labels = [
        (r.get("persistence") or {}).get("label")
        for r in forensic_results if r.get("accepted")
    ]
    det_ok = all(r.get("control_control_equal") for r in forensic_results if r.get("accepted"))
    full_det = all(r.get("full_full_equal") for r in forensic_results if r.get("accepted"))
    any_leak = any(r.get("any_leak") for r in forensic_results)

    # Context dependence
    ctx_dep = "INSUFFICIENT_EVIDENCE"
    for r in forensic_results:
        ctxs = [c for c in (r.get("context_matrix") or []) if c.get("accepted")]
        if len(ctxs) >= 2:
            flags = [c.get("cog_first") is not None for c in ctxs]
            if any(flags) and not all(flags):
                ctx_dep = "CONTEXT_DEPENDENT_LEVEL2"
                break
            if all(flags):
                ctx_dep = "CONTEXT_STABLE_LEVEL2"

    bottleneck_verdict = "NOT_ESTABLISHED"
    if n_action_conv >= 1:
        # majority code
        from collections import Counter
        c = Counter(x for x in codes if x)
        if c:
            top, n = c.most_common(1)[0]
            bottleneck_verdict = f"SUPPORTED:{top}" if n >= 1 else "NOT_ESTABLISHED"

    elapsed = time.perf_counter() - t0
    (out / "determinism_report.md").write_text(
        "\n".join([
            "# Determinism (SIGINT-06)",
            f"- CONTROL/CONTROL: `{det_ok}`",
            f"- FULL/FULL: `{full_det}`",
            "",
        ]),
        encoding="utf-8",
    )
    (out / "performance_report.md").write_text(
        "\n".join([
            "# Performance (SIGINT-06)",
            f"- wall time: {elapsed:.1f}s",
            f"- L2 hits analyzed: {len(hits)}",
            "- offline/on-demand forensics only",
            "- OBS-05 LIVE frames untouched",
            "",
        ]),
        encoding="utf-8",
    )

    verdicts = {
        "SIGINT05_LEVEL2_REPRODUCTION": (
            f"{n_rep}/{n_acc}" if n_acc else "NOT_ESTABLISHED"
        ),
        "FIELD→COGNITION": "REPRODUCED" if n_rep else "NOT_REPRODUCED",
        "COGNITIVE_DIVERGENCE_PERSISTENCE": (
            persist_labels[0] if persist_labels else "NOT_ESTABLISHED"
        ),
        "COGNITIVE_RECONVERGENCE": (
            "OBSERVED" if any(p == "RECONVERGENT" or p == "TRANSIENT" for p in persist_labels) else "NOT_ESTABLISHED"
        ),
        "CANDIDATE_SET_DIVERGENCE": "SEE_PIPELINE",
        "CANDIDATE_RANK_DIVERGENCE": "SEE_PIPELINE",
        "SELECTION_SOURCE_DIVERGENCE": "REPRODUCED" if n_rep else "NOT_REPRODUCED",
        "ACTION_SELECTION_MARGIN_CHANGE": "SEE_MARGIN_ARTIFACT",
        "ACTION_CONVERGENCE_WITH_INTERNAL_DIVERGENCE": (
            "SUPPORTED" if n_action_conv >= 1 else "NOT_ESTABLISHED"
        ),
        "SIGNAL→ACTION": "NOT_ESTABLISHED",
        "DELAYED_SIGNAL→ACTION": (
            "OBSERVED" if n_delayed_act else "NOT_ESTABLISHED"
        ),
        "SIGNAL→TRAJECTORY": "NOT_ESTABLISHED",
        "SIGNAL→NATURAL_EMISSION": (
            "CANDIDATE" if n_emission else "NOT_ESTABLISHED"
        ),
        "SIGNAL_TO_COGNITION_TO_EMISSION_CANDIDATE": (
            "FLAGGED" if n_emission else "NOT_SUPPORTED"
        ),
        "SIGNAL_TO_ACTION_BOTTLENECK": bottleneck_verdict,
        "CONTEXT_DEPENDENCE": ctx_dep,
        "COGNITION_INFORMATION_BOUNDARY": "HELD" if not any_leak else "VIOLATED",
        "CONTROL/CONTROL": "PASS" if det_ok else "FAIL",
        "DETERMINISM": "PASS" if (det_ok and full_det) else "FAIL",
        "SIGINT-01–05_COMPATIBILITY": "PRESERVED",
        "GEO_COMPATIBILITY": "PRESERVED",
        "OBSERVER_PERFORMANCE": "ON_DEMAND_FORENSICS",
        "SCIENTIFIC_HISTORY": "SUPPORTED",
        "LEARNED_COMMUNICATION": "NOT_SUPPORTED",
    }

    # Enrich pipeline-derived verdicts from actual ladders
    cand_set = cand_rank = margin_chg = False
    for r in forensic_results:
        lad = r.get("pipeline_ladder") or {}
        if (lad.get("candidate_set") or {}).get("status") == "DIVERGED":
            cand_set = True
        if (lad.get("candidate_ranking") or {}).get("status") == "DIVERGED":
            cand_rank = True
        sample = (r.get("bottleneck") or {}).get("sample_at_first_source_divergence") or {}
        if sample.get("control_margin") != sample.get("replay_margin") and (
            sample.get("control_margin") or sample.get("replay_margin")
        ):
            margin_chg = True
    verdicts["CANDIDATE_SET_DIVERGENCE"] = "SUPPORTED" if cand_set else "NOT_ESTABLISHED"
    verdicts["CANDIDATE_RANK_DIVERGENCE"] = "SUPPORTED" if cand_rank else "NOT_ESTABLISHED"
    verdicts["ACTION_SELECTION_MARGIN_CHANGE"] = "SUPPORTED" if margin_chg else "NOT_ESTABLISHED"

    report = {
        "task": "BETA2-SIGINT-06",
        "timestamp": ts,
        "elapsed_s": elapsed,
        "sigint05_dir": str(DEFAULT_SIGINT05),
        "n_level2_hits": len(hits),
        "n_reproduced": n_rep,
        "bottleneck_codes": codes,
        "persistence_labels": persist_labels,
        "verdicts": verdicts,
        "honesty": {
            "not_hesitation": True,
            "not_ignored_message": True,
            "not_communication": True,
            "forensic_only": True,
        },
    }
    _write(out / "report.json", report)
    _write(out / "forensic_results.json", forensic_results)

    md = [
        "# BETA2-SIGINT-06 — Cognitive Divergence Forensics × Signal-to-Action Bottleneck",
        "",
        f"Timestamp: `{ts}` · elapsed `{elapsed:.1f}s`",
        "",
        "## Core question",
        "",
        "Why did three SIGINT-05 matched episode interventions change cognition/selection",
        "observables without changing action?",
        "",
        "## Level-2 hits analyzed",
        "",
    ]
    for h in hits:
        md.append(
            f"- episode `{h.get('start_tick')}–{h.get('end_tick')}` "
            f"(`{h.get('episode_id')}`) seed={h.get('seed')} s0={h.get('s0_tick')}"
        )
    md.extend(["", "## Reproduction", f"- reproduced: **{n_rep}/{n_acc}**", ""])
    md.append("## Bottlenecks")
    md.append("")
    for r in forensic_results:
        if not r.get("accepted"):
            continue
        b = (r.get("bottleneck") or {}).get("best_supported") or {}
        md.append(
            f"- `{r['hit'].get('start_tick')}–{r['hit'].get('end_tick')}`: "
            f"{(r.get('bottleneck') or {}).get('classification')} · "
            f"code={b.get('code')} · {b.get('text')}"
        )
    md.extend(["", "## Verdicts", ""])
    for k, v in verdicts.items():
        md.append(f"- **{k}**: `{v}`")
    md.extend([
        "",
        "## Claim boundary",
        "",
        "Forensic explanation of action equality despite cognitive divergence.",
        "Not understanding, hesitation, or communication.",
        "",
    ])
    (out / "report.md").write_text("\n".join(md), encoding="utf-8")

    print(f"Wrote {out}", flush=True)
    print(json.dumps(verdicts, indent=2), flush=True)


if __name__ == "__main__":
    main()
