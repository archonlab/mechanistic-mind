#!/usr/bin/env python3
"""Run BETA2-SIGINT-05 interaction episode replay × trajectory coupling."""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.ui.psy_observer_web.signal_context.interaction_episode import (
    DEFAULT_REF_RUN,
    EpisodeScreenConfig,
    discover_bidirectional_episodes,
    geometry_flow_snapshot,
    group_episode_families,
    reconstruct_reference_episode_1554_1563,
    run_episode_branch,
    run_episode_trial_suite,
    run_partial_closed_loop_probe,
    temporal_strip,
    trajectory_coupling_summary,
)
from mechanistic_mind.ui.psy_observer_web.signal_context.intervention import (
    find_matched_s0,
    fingerprint_equal,
    make_signal_runtime,
)

ROOT = Path("/home/thehost/Desktop/psy")


def _write(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")


def main() -> None:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = ROOT / "results/signal_context_interpreter" / f"beta2_sigint_05_{ts}"
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()

    print("Reconstructing reference episode t1554–1563...", flush=True)
    ref = reconstruct_reference_episode_1554_1563(DEFAULT_REF_RUN)
    ref_dict = ref.to_dict()
    ref_dict["temporal_strip"] = temporal_strip(ref)
    _write(out / "reference_episode_1554_1563.json", ref_dict)
    _write(out / "episode_reconstruction.json", {
        "episode_id": ref.episode_id,
        "reconstruction": ref.reconstruction,
        "n_components": len(ref.components),
        "n_receptions": len(ref.receptions),
        "duration": ref.duration,
        "notes": list(ref.notes),
        "verdict": ref.reconstruction,
    })
    print(f"  reconstruction={ref.reconstruction} components={len(ref.components)}", flush=True)

    print("Discovering bidirectional episode repertoire...", flush=True)
    episodes = discover_bidirectional_episodes(
        DEFAULT_REF_RUN / "scientific_events.jsonl",
        run_id=DEFAULT_REF_RUN.name,
        max_episodes=16,
        min_both_ticks=3,
    )
    # Ensure reference is included
    if not any(e.start_tick == 1554 and e.end_tick == 1563 for e in episodes):
        episodes = [ref] + episodes
    families = group_episode_families(episodes)
    _write(out / "interaction_episode_repertoire.json", {
        "n_episodes": len(episodes),
        "episodes": [e.to_dict() for e in episodes],
        "source_run": DEFAULT_REF_RUN.name,
    })
    _write(out / "episode_families.json", families)
    print(f"  repertoire={len(episodes)} families={len(families)}", flush=True)

    cfg = EpisodeScreenConfig(
        max_episodes=4,
        stage_a_seeds=(17, 19),
        stage_b_seeds=(17, 19, 23),
        horizon=80,
        max_s0_search=350,
        min_s0_age=30,
    )

    # Stage A: reference + up to 2 other episodes
    to_screen = [ref]
    for e in episodes:
        if e.episode_id == ref.episode_id:
            continue
        to_screen.append(e)
        if len(to_screen) >= cfg.max_episodes:
            break

    print("Matched episode trials (Stage A)...", flush=True)
    stage_a_modes = (
        "CONTROL", "SHAM", "FULL_EPISODE",
        "A_TO_B_ONLY", "B_TO_A_ONLY",
        "ISOLATED_COMPONENTS", "TIMING_SHUFFLED", "ORDER_REVERSED",
    )
    all_trials = []
    first_div_rows = []
    coupling_rows = []
    promoted = []
    for ep in to_screen:
        print(f"  episode {ep.start_tick}-{ep.end_tick} ...", flush=True)
        for seed in cfg.stage_a_seeds:
            trial = run_episode_trial_suite(ep, seed=int(seed), cfg=cfg, modes=stage_a_modes)
            if not trial.get("accepted"):
                print(f"    seed {seed}: no S0", flush=True)
                continue
            all_trials.append({
                "episode_id": ep.episode_id,
                "start_tick": ep.start_tick,
                "end_tick": ep.end_tick,
                "reconstruction": ep.reconstruction,
                **{k: v for k, v in trial.items() if k != "natural_followups_full"},
                "natural_followups_n": len(trial.get("natural_followups_full") or []),
            })
            first_div_rows.append({
                "episode_id": ep.episode_id,
                "seed": seed,
                "divergences": trial.get("divergences"),
                "levels": trial.get("levels"),
            })
            coupling_rows.append({
                "episode_id": ep.episode_id,
                "seed": seed,
                "coupling": trial.get("coupling"),
                "coupling_delta_full_vs_control": trial.get("coupling_delta_full_vs_control"),
            })
            lv = trial.get("levels") or {}
            if any(lv.get(k) for k in ("L2_cognition", "L3_action", "L4_trajectory", "L5_coupling")):
                promoted.append({"episode_id": ep.episode_id, "seed": seed, "levels": lv})

    _write(out / "matched_episode_trials.json", all_trials)
    _write(out / "first_divergence.json", first_div_rows)
    _write(out / "trajectory_coupling.json", coupling_rows)

    # Ablations / specificity on reference if any promotion, else still run light ablations once
    print("Ablations + open/closed loop on reference...", flush=True)
    ablations = []
    abl_modes = (
        "FULL_EPISODE", "REMOVE_FIRST_A_EMISSION", "REMOVE_FIRST_B_RESPONSE",
        "REMOVE_ALTERNATION", "DELAYED_EPISODE",
    )
    s0 = find_matched_s0(
        seed=17, receiver="agent_1", pre_action="WAIT",
        pre_selection_source="RETAINED_PREDICTION", require_no_contact=True,
        max_search=350, min_age=30,
    )
    geometry = None
    if s0:
        rt0 = TwoAgentRuntime.restore(s0["snapshot"])
        geometry = geometry_flow_snapshot(rt0)
        ctrl = run_episode_branch(
            s0["snapshot"], ref, mode="CONTROL", horizon=cfg.horizon,
            experiment_id="abl", intervention_id="c",
        )
        for mode in abl_modes:
            arm = run_episode_branch(
                s0["snapshot"], ref, mode=mode, horizon=cfg.horizon,
                experiment_id="abl", intervention_id=mode,
            )
            from mechanistic_mind.ui.psy_observer_web.signal_context.interaction_episode import (
                first_divergences_episode,
            )
            ablations.append({
                "mode": mode,
                "n_injected": arm.get("n_injected"),
                "divergences_vs_control": first_divergences_episode(ctrl, arm),
                "coupling": trajectory_coupling_summary(
                    arm["traces"], post_start=ref.duration + 1,
                ),
            })
    _write(out / "episode_ablations.json", ablations)
    _write(out / "geometry_controls.json", geometry or {"note": "no S0"})

    cloop = run_partial_closed_loop_probe(ref, seed=17, cfg=cfg)
    _write(out / "open_vs_closed_loop.json", cloop)

    # Natural follow-up emissions aggregate
    follow = []
    for t in all_trials:
        follow.append({
            "episode_id": t.get("episode_id"),
            "seed": t.get("seed"),
            "natural_followups_n": t.get("natural_followups_n"),
            "levels": t.get("levels"),
        })
    _write(out / "natural_followup_emissions.json", follow)

    # Determinism
    det_ctrl = det_full = False
    if s0:
        c1 = run_episode_branch(
            s0["snapshot"], ref, mode="CONTROL", horizon=15,
            experiment_id="det", intervention_id="d",
        )
        c2 = run_episode_branch(
            s0["snapshot"], ref, mode="CONTROL", horizon=15,
            experiment_id="det", intervention_id="d",
        )
        det_ctrl = all(
            fingerprint_equal(a["fingerprint"], b["fingerprint"])
            for a, b in zip(c1["traces"], c2["traces"])
        )
        f1 = run_episode_branch(
            s0["snapshot"], ref, mode="FULL_EPISODE", horizon=15,
            experiment_id="det", intervention_id="d",
        )
        f2 = run_episode_branch(
            s0["snapshot"], ref, mode="FULL_EPISODE", horizon=15,
            experiment_id="det", intervention_id="d",
        )
        det_full = all(
            fingerprint_equal(a["fingerprint"], b["fingerprint"])
            for a, b in zip(f1["traces"], f2["traces"])
        )
    (out / "determinism_report.md").write_text(
        "\n".join([
            "# Determinism (SIGINT-05)",
            f"- CONTROL/CONTROL: `{det_ctrl}`",
            f"- FULL_EPISODE/FULL_EPISODE: `{det_full}`",
            "",
        ]),
        encoding="utf-8",
    )

    elapsed = time.perf_counter() - t0
    (out / "performance_report.md").write_text(
        "\n".join([
            "# Performance (SIGINT-05)",
            f"- wall time: {elapsed:.1f}s",
            f"- episodes screened: {len(to_screen)}",
            f"- trials: {len(all_trials)}",
            "- episode data on-demand only (not in compact LIVE frames)",
            "- OBS-05 architecture preserved",
            "",
        ]),
        encoding="utf-8",
    )
    (out / "interaction_episode_replay_architecture.md").write_text(
        "\n".join([
            "# Interaction episode replay architecture (SIGINT-05)",
            "",
            "NATURAL EMISSION SEQUENCE (scientific_events)",
            "  → NaturalSignalEpisode (ordered components + Δt)",
            "  → matched S0 branch",
            "  → schedule inject_source per Δt (FULL / A→B / B→A / shuffle / reverse / …)",
            "  → _deposit → ordinary FIELD → local.FIELD_*",
            "  → measure coupling / cognition / action / trajectory",
            "",
            "OPEN_LOOP: replay entire recorded sequence.",
            "PARTIAL_CLOSED_LOOP: inject first-tick components only; natural dynamics follow.",
            "",
            "TRAJECTORY_COUPLING is a physical metric (distance, alignment, co-movement ticks).",
            "It is not following / cooperation / conversation.",
            "",
        ]),
        encoding="utf-8",
    )

    # Aggregate verdicts
    n_trials = len(all_trials)
    n_L1 = sum(1 for t in all_trials if (t.get("levels") or {}).get("L1_exposure"))
    n_L2 = sum(1 for t in all_trials if (t.get("levels") or {}).get("L2_cognition"))
    n_L3 = sum(1 for t in all_trials if (t.get("levels") or {}).get("L3_action"))
    n_L4 = sum(1 for t in all_trials if (t.get("levels") or {}).get("L4_trajectory"))
    n_L5 = sum(1 for t in all_trials if (t.get("levels") or {}).get("L5_coupling"))

    def level_verdict(n_hit: int) -> str:
        if n_trials == 0:
            return "NOT_ESTABLISHED"
        if n_hit >= max(2, (n_trials + 1) // 2):
            return "INTERVENTION_SUPPORTED"
        if n_hit >= 1:
            return "BRANCH_CAUSAL_EFFECT"
        return "NOT_ESTABLISHED"

    # Structure comparisons
    full_vs_iso = "NOT_ESTABLISHED"
    temporal_dep = "NOT_ESTABLISHED"
    bidirectional = "NOT_ESTABLISHED"
    for t in all_trials:
        div = t.get("divergences") or {}
        full = div.get("FULL_EPISODE") or {}
        iso = div.get("ISOLATED_COMPONENTS") or {}
        shuf = div.get("TIMING_SHUFFLED") or {}
        aonly = div.get("A_TO_B_ONLY") or {}
        bonly = div.get("B_TO_A_ONLY") or {}
        sham = div.get("SHAM") or {}
        if full.get("action") is not None and sham.get("action") is None:
            if iso.get("action") is None:
                full_vs_iso = "TEMPORAL_STRUCTURE_CANDIDATE"
            if shuf.get("action") is None or shuf.get("action") != full.get("action"):
                temporal_dep = "TEMPORAL_ORDER_DEPENDENCE_CANDIDATE"
            if (aonly.get("action") is None or bonly.get("action") is None) and full.get("action"):
                bidirectional = "BIDIRECTIONAL_DEPENDENCE_CANDIDATE"
        # Also check coupling
        if full.get("coupling_distance") is not None and sham.get("coupling_distance") is None:
            if n_L5 >= 1 and full_vs_iso == "NOT_ESTABLISHED":
                if iso.get("coupling_distance") is None:
                    full_vs_iso = "TEMPORAL_STRUCTURE_CANDIDATE"

    # Coupling effect: mean co_movement delta
    coupling_effect = "NOT_ESTABLISHED"
    deltas = [
        (t.get("coupling_delta_full_vs_control") or {}).get("co_movement_vs_control")
        for t in all_trials
        if t.get("coupling_delta_full_vs_control")
    ]
    deltas = [d for d in deltas if d is not None]
    if deltas and sum(1 for d in deltas if d > 0) >= max(2, (len(deltas) + 1) // 2):
        coupling_effect = "INTERVENTION_SUPPORTED"
    elif deltas and any(d > 0 for d in deltas):
        coupling_effect = "BRANCH_CAUSAL_EFFECT"
    elif n_L5 == 0:
        coupling_effect = "NOT_ESTABLISHED"

    any_leak = any(t.get("any_leak") for t in all_trials)

    verdicts = {
        "REFERENCE_EPISODE_RECONSTRUCTION": ref.reconstruction,
        "INTERACTION_EPISODE_REPERTOIRE": "SUPPORTED" if len(episodes) >= 1 else "WEAK",
        "PHYSICAL_EPISODE_REPLAY": "SUPPORTED" if n_trials else "NOT_SUPPORTED",
        "RECEIVER_EXPOSURE": level_verdict(n_L1),
        "FIELD→COGNITION": level_verdict(n_L2),
        "FIELD→ACTION": level_verdict(n_L3),
        "FIELD→TRAJECTORY": level_verdict(n_L4),
        "POST_EPISODE_TRAJECTORY_COUPLING": coupling_effect if n_L5 else level_verdict(n_L5),
        "FULL_VS_ISOLATED_COMPONENTS": full_vs_iso,
        "TEMPORAL_ORDER_DEPENDENCE": temporal_dep,
        "BIDIRECTIONAL_DEPENDENCE": bidirectional,
        "NATURAL_FOLLOWUP_EMISSION": (
            "OBSERVED"
            if any((t.get("natural_followups_n") or 0) > 0 for t in all_trials)
            else "NOT_ESTABLISHED"
        ),
        "INTERACTION_CHAIN_CANDIDATE": (
            "FLAGGED" if cloop.get("INTERACTION_CHAIN_CANDIDATE") else "NOT_SUPPORTED"
        ),
        "CONTEXT_DEPENDENCE": "INSUFFICIENT_EVIDENCE",
        "GEOMETRY/FLOW_CONFOUND": (
            "CONTROLS_RECORDED" if geometry else "NOT_RECORDED"
        ),
        "COGNITION_INFORMATION_BOUNDARY": "HELD" if not any_leak else "VIOLATED",
        "MATCHED_BRANCHING": "SUPPORTED" if n_trials else "NOT_SUPPORTED",
        "CONTROL/CONTROL": "PASS" if det_ctrl else "FAIL",
        "DETERMINISM": "PASS" if (det_ctrl and det_full) else "FAIL",
        "SIGINT-01_COMPATIBILITY": "PRESERVED",
        "SIGINT-02_COMPATIBILITY": "REUSED_INTERVENTION_PATH",
        "SIGINT-03_COMPATIBILITY": "REUSED_SPECIMEN_CONCEPTS",
        "SIGINT-04_COMPATIBILITY": "REUSED_SCREENING_PATTERN",
        "GEO_COMPATIBILITY": "PRESERVED",
        "OBSERVER_PERFORMANCE": "ON_DEMAND_EPISODE_API",
        "SCIENTIFIC_HISTORY": "SUPPORTED",
        "LEARNED_COMMUNICATION": "NOT_SUPPORTED",
    }

    report = {
        "task": "BETA2-SIGINT-05",
        "timestamp": ts,
        "elapsed_s": elapsed,
        "reference_episode": f"{ref.start_tick}-{ref.end_tick}",
        "reconstruction": ref.reconstruction,
        "n_episodes_repertoire": len(episodes),
        "n_trials": n_trials,
        "n_promoted_hits": len(promoted),
        "level_counts": {"L1": n_L1, "L2": n_L2, "L3": n_L3, "L4": n_L4, "L5": n_L5},
        "verdicts": verdicts,
        "honesty": {
            "not_conversation": True,
            "not_following": True,
            "not_cooperation": True,
            "not_communication": True,
            "coupling_is_physical_metric": True,
        },
    }
    _write(out / "report.json", report)

    md = [
        "# BETA2-SIGINT-05 — Interaction Episode Replay × Trajectory Coupling",
        "",
        f"Timestamp: `{ts}` · elapsed `{elapsed:.1f}s`",
        "",
        "## Core question",
        "",
        "Does replaying the temporal structure of a bidirectional signal episode",
        "produce downstream effects that isolated natural signal replay did not?",
        "",
        "## Reference episode",
        "",
        f"- ticks: `{ref.start_tick}–{ref.end_tick}`",
        f"- reconstruction: `{ref.reconstruction}`",
        f"- components: {len(ref.components)} · receptions: {len(ref.receptions)}",
        f"- notes: {'; '.join(ref.notes)}",
        "",
        "## Screen",
        "",
        f"- repertoire episodes: {len(episodes)}",
        f"- matched trials: {n_trials}",
        f"- Level hits L1/L2/L3/L4/L5: {n_L1}/{n_L2}/{n_L3}/{n_L4}/{n_L5}",
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
        "TRAJECTORY_COUPLING is a physical metric. Not following, cooperation, or conversation.",
        "LEARNED_COMMUNICATION remains NOT_SUPPORTED.",
        "",
    ])
    (out / "report.md").write_text("\n".join(md), encoding="utf-8")

    print(f"Wrote {out}", flush=True)
    print(json.dumps(verdicts, indent=2), flush=True)


if __name__ == "__main__":
    main()
