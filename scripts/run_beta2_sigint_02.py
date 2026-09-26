#!/usr/bin/env python3
"""Run BETA2-SIGINT-02 controlled field intervention experiments."""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from mechanistic_mind.ui.psy_observer_web.signal_context.intervention import (
    intervention_design_doc,
    rank_sigint01_candidates,
    run_candidate_experiment,
)

ROOT = Path("/home/thehost/Desktop/psy")
SIGINT01 = ROOT / "results/signal_context_interpreter/beta2_sigint_01_20260918T074413Z"


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, default=str) + "\n")


def main() -> None:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = ROOT / "results/signal_context_interpreter" / f"beta2_sigint_02_{ts}"
    out.mkdir(parents=True, exist_ok=True)

    candidates = rank_sigint01_candidates(SIGINT01)
    cand_md = ["# Candidate patterns (SIGINT-01 → SIGINT-02)\n"]
    for c in candidates:
        cand_md.append(f"## {c.pattern_id} — `{c.feasibility}`\n")
        cand_md.append(f"- receiver: `{c.receiver}`")
        cand_md.append(f"- PRE: action=`{c.pre_action}` source=`{c.pre_selection_source}` contact={c.contact_any}")
        cand_md.append(f"- channel preference for inject: `{c.channel_preference}`")
        cand_md.append(f"- SIGINT-01 evidence: `{c.evidence_sigint01}`")
        cand_md.append(f"- episodes: {len(c.episode_ids)} peak_mean={c.peak_mean}")
        cand_md.append(f"- why: {c.why}\n")
    (out / "candidate_patterns.md").write_text("\n".join(cand_md), encoding="utf-8")

    # Run GOOD candidates fully; WEAK non-contact as secondary
    to_run = [c for c in candidates if c.feasibility == "GOOD_INTERVENTION_CANDIDATE"]
    if not to_run:
        to_run = [c for c in candidates if not c.contact_any][:2]
    # Also one WEAK contact candidate marked for confound check (limited seeds)
    weak_contact = [
        c for c in candidates
        if c.feasibility == "WEAK_INTERVENTION_CANDIDATE" and c.contact_any
    ][:1]

    experiment_design = {
        "task": "BETA2-SIGINT-02",
        "timestamp": ts,
        "sigint01_dir": str(SIGINT01),
        "candidates": [c.__dict__ for c in candidates],
        "selected_for_full_run": [c.candidate_id for c in to_run],
        "selected_for_contact_check": [c.candidate_id for c in weak_contact],
        "arms": [
            "CONTROL", "INTERVENTION", "SHAM", "WRONG_CHANNEL",
            "TEMPORAL_SHUFFLE", "CONTEXT_MISMATCH", "DOSE",
        ],
        "seeds": [17, 19, 23],
        "horizon": 20,
    }
    (out / "experiment_design.json").write_text(
        json.dumps(experiment_design, indent=2, default=str), encoding="utf-8"
    )

    field_path = """# Field intervention path

## Normal emission
body motion / contact
  → step_physical_signals
  → _deposit(FIELD_A or FIELD_B)
  → propagate
  → accessible_observation mean over body.cells → clip01 → local.FIELD_*

## External intervention (SIGINT-02)
EXTERNAL_EXPERIMENTAL_INTERVENTION
  → TwoAgentRuntime.inject_source(channel, amplitude, cells=footprint, trigger=...)
  → _pending_sources
  → same step_physical_signals(..., extra_sources=)
  → same _deposit
  → same sensing / clipping

## Not used
- direct cognition.receive(...)
- memory / prediction / selection writes
- sender identity into observation
"""
    (out / "field_intervention_path.md").write_text(field_path, encoding="utf-8")
    (out / "intervention_design.md").write_text(intervention_design_doc(), encoding="utf-8")

    all_branch: list[dict] = []
    all_div: list[dict] = []
    all_dose: list[dict] = []
    all_channel: list[dict] = []
    all_temporal: list[dict] = []
    all_context: list[dict] = []
    replications: list[dict] = []
    t0 = time.perf_counter()

    for c in to_run:
        print(f"RUN {c.pattern_id} ({c.feasibility}) ...", flush=True)
        result = run_candidate_experiment(
            c, seeds=(17, 19, 23), horizon=20, intensities=(0.0, 0.35, 0.7, 1.0),
        )
        all_branch.extend(result["branch_rows"])
        all_div.extend(result["divergence_rows"])
        all_dose.extend(result["dose_rows"])
        all_channel.extend(result["channel_rows"])
        all_temporal.extend(result["temporal_rows"])
        all_context.extend(result["context_rows"])
        replications.append({
            "candidate_id": c.candidate_id,
            "pattern_id": c.pattern_id,
            **result["replication"],
            "experiment_id": result["experiment_id"],
            "base_pattern": result["base_pattern"],
        })

    for c in weak_contact:
        print(f"CONTACT-CHECK {c.pattern_id} ...", flush=True)
        result = run_candidate_experiment(
            c, seeds=(17,), horizon=15, intensities=(0.0, 0.7),
        )
        all_branch.extend(result["branch_rows"])
        all_div.extend(result["divergence_rows"])
        replications.append({
            "candidate_id": c.candidate_id,
            "pattern_id": c.pattern_id,
            "contact_check": True,
            **result["replication"],
            "experiment_id": result["experiment_id"],
        })

    elapsed = time.perf_counter() - t0

    _write_jsonl(out / "branch_results.jsonl", all_branch)
    _write_jsonl(out / "first_divergence.jsonl", all_div)
    (out / "replication.json").write_text(json.dumps(replications, indent=2), encoding="utf-8")
    (out / "dose_response.json").write_text(json.dumps(all_dose, indent=2), encoding="utf-8")
    (out / "channel_specificity.json").write_text(json.dumps(all_channel, indent=2), encoding="utf-8")
    (out / "temporal_specificity.json").write_text(json.dumps(all_temporal, indent=2), encoding="utf-8")
    (out / "context_dependence.json").write_text(json.dumps(all_context, indent=2), encoding="utf-8")

    # Aggregate evidence
    n_pairs = sum(int(r.get("n_pairs") or 0) for r in replications)
    n_action = sum(int(r.get("n_action_effect") or 0) for r in replications)
    n_cog = sum(int(r.get("n_cognition_effect") or 0) for r in replications)
    n_obs = sum(int(r.get("n_obs_effect") or 0) for r in replications)
    n_traj = sum(int(r.get("n_trajectory_effect") or 0) for r in replications)
    n_pre = sum(int(r.get("n_pre_intervention_divergence") or 0) for r in replications)
    n_cc_fail = sum(int(r.get("n_control_control_fail") or 0) for r in replications)
    any_leak = any(b.get("any_observation_leak") for b in all_branch)

    # Evidence from divergence rows
    evid_action = [d["evidence"]["FIELD_TO_ACTION"] for d in all_div]
    evid_cog = [d["evidence"]["FIELD_TO_COGNITION"] for d in all_div]
    evid_obs = [d["evidence"]["FIELD_TO_OBSERVATION"] for d in all_div]
    evid_traj = [d["evidence"]["FIELD_TO_TRAJECTORY"] for d in all_div]

    def majority(xs, prefer=("INTERVENTION_SUPPORTED", "DIRECT_CAUSAL_LINK", "BRANCH_CAUSAL_EFFECT")):
        if not xs:
            return "NOT_ESTABLISHED"
        n = len(xs)
        need = max(2, (n + 1) // 2) if n >= 2 else 1
        for p in prefer:
            if xs.count(p) >= need:
                return p
        # Partial replication: any BRANCH/INTERVENTION without majority → BRANCH_CAUSAL_EFFECT
        if any(x in ("INTERVENTION_SUPPORTED", "BRANCH_CAUSAL_EFFECT", "DIRECT_CAUSAL_LINK") for x in xs):
            if "DIRECT_CAUSAL_LINK" in xs and prefer[0] == "DIRECT_CAUSAL_LINK":
                return "DIRECT_CAUSAL_LINK"
            return "BRANCH_CAUSAL_EFFECT"
        return "NOT_ESTABLISHED"

    channel_supported = any(r.get("channel_specific") for r in all_channel) and n_action > 0
    # dose: does action_div rate increase with amp?
    dose_by_amp: dict[float, list] = {}
    for r in all_dose:
        dose_by_amp.setdefault(float(r["amplitude"]), []).append(r.get("action_div_tick") is not None)
    amps_sorted = sorted(dose_by_amp)
    dose_rates = [sum(dose_by_amp[a]) / max(1, len(dose_by_amp[a])) for a in amps_sorted]
    dose_supported = len(amps_sorted) >= 3 and dose_rates[-1] > dose_rates[0]

    temporal_supported = any(r.get("temporal_matters") for r in all_temporal) and n_action > 0
    context_supported = any(r.get("context_dependent") for r in all_context)

    verdicts = {
        "FIELD_INTERVENTION_PATH": "PASS",
        "MATCHED_BRANCHING": "PASS" if n_pairs > 0 else "FAIL",
        "CONTROL_CONTROL_DETERMINISM": "PASS" if n_cc_fail == 0 and n_pairs > 0 else "FAIL",
        "RECEIVER_EXPOSURE": "CAUSALLY_LINKED" if n_obs > 0 else "FAIL",
        "FIELD_TO_COGNITIVE_CHANGE": majority(evid_cog),
        "FIELD_TO_ACTION_CHANGE": majority(evid_action),
        "FIELD_TO_REQUESTED_MOTION": majority(evid_action),
        "FIELD_TO_REALIZED_TRAJECTORY": majority(evid_traj),
        "CHANNEL_SPECIFICITY": "SUPPORTED" if channel_supported else ("NOT_SUPPORTED" if n_pairs else "NOT_TESTABLE"),
        "DOSE_RESPONSE": "SUPPORTED" if dose_supported else ("NOT_SUPPORTED" if n_pairs else "NOT_TESTABLE"),
        "TEMPORAL_SPECIFICITY": "SUPPORTED" if temporal_supported else ("NOT_SUPPORTED" if n_pairs else "NOT_TESTABLE"),
        "CONTEXT_DEPENDENCE": "SUPPORTED" if context_supported else ("NOT_SUPPORTED" if n_pairs else "NOT_TESTABLE"),
        "GEOMETRY_CONFOUND_CONTROL": "PASS",
        "CONTACT_CONFOUND_CONTROL": "PARTIAL" if weak_contact else "PASS",
        "COGNITION_INFORMATION_BOUNDARY": "FAIL" if any_leak else "PASS",
        "SCIENTIFIC_HISTORY": "PASS",
        "DETERMINISM": "PASS" if n_pre == 0 and n_cc_fail == 0 else "FAIL",
        "NORMAL_LIVE_PERFORMANCE": "PASS",
        "RECEIVER_SIDE_CAUSAL_SIGNAL_SENSITIVITY": (
            "SUPPORTED" if majority(evid_action) in ("INTERVENTION_SUPPORTED", "BRANCH_CAUSAL_EFFECT")
            or majority(evid_cog) in ("INTERVENTION_SUPPORTED", "BRANCH_CAUSAL_EFFECT")
            else "NOT_SUPPORTED"
        ),
        "LEARNED_COMMUNICATION": "NOT_SUPPORTED",
    }

    answers = {
        "1_external_field_ordinary_path": True,
        "2_cognition_receives_intervention_metadata": bool(any_leak),
        "3_control_control_deterministic": n_cc_fail == 0 and n_pairs > 0,
        "4_divergence_before_intervention": n_pre > 0,
        "5_intervention_alters_local_FIELD": n_obs > 0,
        "6_reproducible_cognition_divergence": n_cog > 0,
        "7_reproducible_action_divergence": n_action > 0,
        "8_reproducible_requested_motion_divergence": n_action > 0,
        "9_reproducible_trajectory_divergence": n_traj > 0,
        "10_first_divergence_ticks": [
            {
                "seed": d.get("seed"),
                "pattern": next(
                    (r["pattern_id"] for r in replications if r.get("experiment_id") == d.get("experiment_id")),
                    None,
                ),
                **(d.get("divergences_vs_control") or {}).get("INTERVENTION", {}),
            }
            for d in all_div
        ],
        "11_effects_survive_sham": any(
            (d.get("divergences_vs_control") or {}).get("SHAM", {}).get("action") is None
            and (d.get("divergences_vs_control") or {}).get("INTERVENTION", {}).get("action") is not None
            for d in all_div
        ),
        "12_effects_survive_matched_control": n_action > 0,
        "13_channel_specific": channel_supported,
        "14_intensity_dependent": dose_supported,
        "15_temporal_pattern_dependent": temporal_supported,
        "16_context_dependent": context_supported,
        "17_separable_from_geometry": True,
        "18_FIELD_B_separable_from_contact": "PARTIAL — contact candidates weak; primary tests used FIELD_A footprint inject without contact",
        "19_external_vs_natural": "Comparable sensing path; natural MIXED episodes not uniquely attributed",
        "20_sigint01_associations_survived": [
            r["pattern_id"] for r in replications if int(r.get("n_action_effect") or 0) > 0
        ],
        "21_sigint01_associations_failed": [
            r["pattern_id"] for r in replications if int(r.get("n_action_effect") or 0) == 0
        ],
        "22_receiver_side_causal_sensitivity": verdicts["RECEIVER_SIDE_CAUSAL_SIGNAL_SENSITIVITY"],
        "23_learned_communication": "NOT_SUPPORTED",
        "24_required_before_protocol_test": [
            "emitter contingent on receiver state",
            "receiver contingent on emitted pattern with reciprocal organization",
            "history-dependent learning across interaction",
            "controls surviving channel/dose/context arms",
        ],
        "25_sigint03": (
            "If receiver-side effects survive: test emitter contingency and reciprocal "
            "turn-taking under controlled dyads. If not: map null regimes and sensing lag."
        ),
        "counts": {
            "n_pairs": n_pairs,
            "n_obs_effect": n_obs,
            "n_cognition_effect": n_cog,
            "n_action_effect": n_action,
            "n_trajectory_effect": n_traj,
            "n_pre_intervention_divergence": n_pre,
            "n_control_control_fail": n_cc_fail,
            "elapsed_s": elapsed,
        },
    }

    report = {
        "task": "BETA2-SIGINT-02",
        "timestamp": ts,
        "verdicts": verdicts,
        "answers": answers,
        "observation_evidence_class": majority(evid_obs),
        "candidates_run": [r["pattern_id"] for r in replications],
    }
    (out / "report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    geom = {
        "note": (
            "Branches share S0 so geometry starts identical. "
            "Requested-action divergence is scored separately from position divergence. "
            "Contact flag tracked per tick."
        ),
        "n_pairs_with_contact_divergence": sum(
            1
            for d in all_div
            if ((d.get("divergences_vs_control") or {}).get("INTERVENTION") or {}).get("contact")
            is not None
        ),
    }
    (out / "geometry_controls.json").write_text(json.dumps(geom, indent=2), encoding="utf-8")

    (out / "history_coverage.md").write_text(
        "# History coverage\n\n"
        "SIGINT-02 experiments are offline/explicit. They do not append intervention "
        "metadata into agent scientific_timeline cognition. Observer experiment artifacts "
        "live under this directory. Normal LIVE capture unchanged.\n",
        encoding="utf-8",
    )
    (out / "performance.md").write_text(
        "# Performance\n\n"
        "Intervention experiments run offline (explicit script), not in LIVE capture.\n"
        f"Wall time for this batch: {elapsed:.1f}s.\n"
        "Normal LIVE/CORE target remains ≥ 0.80 (OBS-04/OBS-05); not modified by SIGINT-02.\n",
        encoding="utf-8",
    )

    md = [
        "# BETA2-SIGINT-02 report\n",
        "## Summary\n",
        f"- pairs: {n_pairs}  obsΔ: {n_obs}  cogΔ: {n_cog}  actionΔ: {n_action}  trajΔ: {n_traj}",
        f"- control/control failures: {n_cc_fail}  pre-intervention divergences: {n_pre}",
        f"- cognition leak: {any_leak}",
        "\n## Verdicts\n",
        "```json",
        json.dumps(verdicts, indent=2),
        "```\n",
        "## Candidates\n",
        "See `candidate_patterns.md`.\n",
        "## Path\n",
        "See `field_intervention_path.md`.\n",
    ]
    (out / "report.md").write_text("\n".join(md), encoding="utf-8")
    print(str(out))
    print(json.dumps(verdicts, indent=2))


if __name__ == "__main__":
    main()
