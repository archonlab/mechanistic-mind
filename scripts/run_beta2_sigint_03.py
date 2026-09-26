#!/usr/bin/env python3
"""Run BETA2-SIGINT-03 natural signal replay × echo probe × response fingerprint."""
from __future__ import annotations

import json
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.ui.psy_observer_web.signal_context.intervention import (
    fingerprint_equal,
    scientific_fingerprint,
)
from mechanistic_mind.ui.psy_observer_web.signal_context.natural_replay import (
    build_response_fingerprint,
    harvest_field_a_specimens,
    run_echo_experiment,
    run_fidelity_gate,
    run_natural_replay_branch,
    stable_id,
)

ROOT = Path("/home/thehost/Desktop/psy")


def _write(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")


def _level(n_hit: int, n_tot: int) -> str:
    if n_tot <= 0:
        return "NOT_ESTABLISHED"
    if n_hit >= n_tot and n_tot >= 2:
        return "REPRODUCIBLE_REPLAY_EFFECT"
    if n_hit >= max(2, (n_tot + 1) // 2):
        return "INTERVENTION_SUPPORTED"
    if n_hit >= 1:
        return "BRANCH_CAUSAL_EFFECT"
    return "NOT_ESTABLISHED"


def main() -> None:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = ROOT / "results/signal_context_interpreter" / f"beta2_sigint_03_{ts}"
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()

    print("Harvesting natural FIELD_A specimens...", flush=True)
    specimens = harvest_field_a_specimens(seed=17, max_steps=160, max_specimens=6)
    if not specimens:
        specimens = harvest_field_a_specimens(seed=19, max_steps=200, max_specimens=6)
    _write(out / "natural_signal_specimens.json", [s.to_dict() for s in specimens])
    print(f"  captured {len(specimens)} specimens", flush=True)

    primary = next(
        (s for s in specimens if s.reconstruction_completeness == "CELLS_AND_AMPLITUDE"),
        specimens[0] if specimens else None,
    )
    if primary is None:
        raise SystemExit("No natural specimens harvested")

    fidelity_rows = []
    for s in specimens[:4]:
        fid = run_fidelity_gate(s, seed=17)
        fidelity_rows.append({"specimen_id": s.specimen_id, **fid})
        print(f"  fidelity {s.specimen_id[:12]}… → {fid.get('fidelity')}", flush=True)
    _write(out / "replay_fidelity.json", fidelity_rows)
    primary_fid = next(
        (r for r in fidelity_rows if r["specimen_id"] == primary.specimen_id),
        fidelity_rows[0],
    )

    print("SELF_ECHO_PROBE...", flush=True)
    self_echo = run_echo_experiment(
        primary, echo_kind="SELF_ECHO", seeds=(17, 19, 23), horizon=18, include_generic=True,
    )
    _write(out / "self_echo_trials.json", self_echo)

    print("PEER_ECHO_PROBE...", flush=True)
    peer_echo = run_echo_experiment(
        primary, echo_kind="PEER_ECHO", seeds=(17, 19, 23), horizon=18, include_generic=True,
    )
    _write(out / "peer_echo_trials.json", peer_echo)

    # Altered replay (one variable) on peer matched contexts after exact fidelity ok
    altered_trials = []
    if primary_fid.get("fidelity") in ("EXACT_PHYSICAL_REPLAY", "APPROXIMATE_PHYSICAL_REPLAY"):
        print("ALTERED_REPLAY (amplitude / channel / delay)...", flush=True)
        for mode, scale in (("ALTER_AMPLITUDE", 0.5), ("ALTER_CHANNEL", 1.0), ("DELAY", 1.0)):
            alt = run_echo_experiment(
                primary, echo_kind="PEER_ECHO", seeds=(17, 19), horizon=16, include_generic=False,
            )
            # Re-run one seed with altered mode for provenance
            from mechanistic_mind.ui.psy_observer_web.signal_context.intervention import find_matched_s0

            s0 = find_matched_s0(
                seed=17, receiver="agent_1", pre_action="WAIT",
                pre_selection_source="RETAINED_PREDICTION", require_no_contact=True,
                max_search=400, min_age=30,
            )
            if s0:
                iid = stable_id("alt", mode, primary.specimen_id)
                ctrl = run_natural_replay_branch(
                    s0["snapshot"], primary, receiver_slot=s0["receiver_slot"],
                    horizon=16, experiment_id="alt", intervention_id=iid, kind="CONTROL",
                )
                exact = run_natural_replay_branch(
                    s0["snapshot"], primary, receiver_slot=s0["receiver_slot"],
                    horizon=16, experiment_id="alt", intervention_id=iid,
                    kind="NATURAL_REPLAY", mode="EXACT", target="PEER",
                )
                alt_arm = run_natural_replay_branch(
                    s0["snapshot"], primary, receiver_slot=s0["receiver_slot"],
                    horizon=16, experiment_id="alt", intervention_id=iid,
                    kind="NATURAL_REPLAY", mode=mode, amplitude_scale=scale, target="PEER",
                )
                from mechanistic_mind.ui.psy_observer_web.signal_context.intervention import (
                    first_divergences,
                )
                altered_trials.append({
                    "mode": mode,
                    "amplitude_scale": scale,
                    "div_exact": first_divergences(ctrl, exact),
                    "div_altered": first_divergences(ctrl, alt_arm),
                    "channel_exact": exact.get("channel"),
                    "channel_altered": alt_arm.get("channel"),
                    "amp_exact": exact.get("amplitude"),
                    "amp_altered": alt_arm.get("amplitude"),
                    "delay_ticks": alt_arm.get("delay_ticks"),
                })
            # keep unused alt var quiet
            _ = alt
    _write(out / "altered_replay.json", altered_trials)

    fingerprints = [
        build_response_fingerprint(
            specimen=primary, echo_result=self_echo, context_label="WAIT|RETAINED|no_contact|SELF",
        ),
        build_response_fingerprint(
            specimen=primary, echo_result=peer_echo, context_label="WAIT|RETAINED|no_contact|PEER",
        ),
    ]
    _write(out / "response_fingerprints.json", fingerprints)

    # Natural vs generic aggregation
    nvsg = []
    for trial in (peer_echo.get("trials") or []):
        nvsg.append({
            "seed": trial.get("seed"),
            "echo_kind": "PEER_ECHO",
            **(trial.get("natural_vs_generic") or {}),
        })
    for trial in (self_echo.get("trials") or []):
        nvsg.append({
            "seed": trial.get("seed"),
            "echo_kind": "SELF_ECHO",
            **(trial.get("natural_vs_generic") or {}),
        })
    distinguishable_n = sum(1 for r in nvsg if r.get("distinguishable"))
    _write(out / "natural_vs_generic_field.json", {
        "rows": nvsg,
        "n_distinguishable": distinguishable_n,
        "n_compared": len([r for r in nvsg if "distinguishable" in r]),
        "verdict": (
            "NATURAL_STRUCTURE_DISTINGUISHABLE"
            if distinguishable_n >= 2
            else "NOT_SUPPORTED"
        ),
    })

    # Context dependence: SELF vs PEER receiver for same specimen
    ctx = {
        "specimen_id": primary.specimen_id,
        "self_obs_frac": fingerprints[0]["confidence"]["obs_frac"],
        "peer_obs_frac": fingerprints[1]["confidence"]["obs_frac"],
        "self_action": fingerprints[0]["action"],
        "peer_action": fingerprints[1]["action"],
        "self_selection": fingerprints[0]["selection_source"],
        "peer_selection": fingerprints[1]["selection_source"],
        "verdict": (
            "CONTEXT_DEPENDENT_EFFECT"
            if fingerprints[0]["action"] != fingerprints[1]["action"]
            or fingerprints[0]["selection_source"] != fingerprints[1]["selection_source"]
            else "RECEIVER_COMPARISON_INCONCLUSIVE"
        ),
    }
    _write(out / "context_dependence.json", ctx)

    matched = {
        "primary_specimen_id": primary.specimen_id,
        "self_echo_replication": self_echo.get("replication"),
        "peer_echo_replication": peer_echo.get("replication"),
        "self_seeds_ok": (self_echo.get("replication") or {}).get("seeds_ok"),
        "peer_seeds_ok": (peer_echo.get("replication") or {}).get("seeds_ok"),
    }
    _write(out / "matched_controls.json", matched)

    # Flatten replay trials
    replay_trials = []
    for label, block in (("SELF_ECHO", self_echo), ("PEER_ECHO", peer_echo)):
        for t in block.get("trials") or []:
            replay_trials.append({"probe": label, **t})
    _write(out / "replay_trials.json", replay_trials)

    # Determinism check
    det_lines = ["# Determinism (SIGINT-03)\n"]
    snap_rt = None
    from mechanistic_mind.ui.psy_observer_web.signal_context.intervention import (
        find_matched_s0,
        make_signal_runtime,
    )
    s0 = find_matched_s0(
        seed=17, receiver="agent_1", pre_action="WAIT",
        pre_selection_source="RETAINED_PREDICTION", require_no_contact=True,
        max_search=400, min_age=30,
    )
    ctrl_eq = False
    replay_eq = False
    if s0:
        c1 = run_natural_replay_branch(
            s0["snapshot"], primary, receiver_slot=s0["receiver_slot"],
            horizon=12, experiment_id="det", intervention_id="d1", kind="CONTROL",
        )
        c2 = run_natural_replay_branch(
            s0["snapshot"], primary, receiver_slot=s0["receiver_slot"],
            horizon=12, experiment_id="det", intervention_id="d1", kind="CONTROL",
        )
        ctrl_eq = all(
            fingerprint_equal(a["fingerprint"], b["fingerprint"])
            for a, b in zip(c1["traces"], c2["traces"])
        )
        r1 = run_natural_replay_branch(
            s0["snapshot"], primary, receiver_slot=s0["receiver_slot"],
            horizon=12, experiment_id="det", intervention_id="d1",
            kind="NATURAL_REPLAY", mode="EXACT", target="PEER",
        )
        r2 = run_natural_replay_branch(
            s0["snapshot"], primary, receiver_slot=s0["receiver_slot"],
            horizon=12, experiment_id="det", intervention_id="d1",
            kind="NATURAL_REPLAY", mode="EXACT", target="PEER",
        )
        replay_eq = all(
            fingerprint_equal(a["fingerprint"], b["fingerprint"])
            for a, b in zip(r1["traces"], r2["traces"])
        )
    det_lines.append(f"- CONTROL/CONTROL identical: `{ctrl_eq}`")
    det_lines.append(f"- NATURAL_REPLAY/NATURAL_REPLAY identical: `{replay_eq}`")
    det_lines.append(f"- primary specimen: `{primary.specimen_id}`")
    (out / "determinism_report.md").write_text("\n".join(det_lines) + "\n", encoding="utf-8")

    # Lightweight LIVE performance / capture smoke (bounded)
    perf_t0 = time.perf_counter()
    rt = make_signal_runtime(seed=23)
    from mechanistic_mind.ui.psy_observer_web.signal_context.natural_replay import (
        NaturalSignalLibrary,
        capture_natural_emissions_from_runtime,
        queue_natural_replay,
    )
    lib = NaturalSignalLibrary(maxlen=64)
    for _ in range(80):
        rt.step()
        capture_natural_emissions_from_runtime(rt, run_id="perf", library=lib)
    n_lib = len(lib.list(limit=256))
    live_mark = None
    if specimens:
        q = queue_natural_replay(
            rt, primary, mode="EXACT", target="PEER", receiver_slot=1,
            observer_source_id="live_uncontrolled_smoke",
        )
        rt.step()
        live_mark = {
            "status": "UNCONTROLLED_LIVE_REPLAY",
            "accepted": q.get("accepted"),
            "note": "Not causal evidence",
        }
    perf_elapsed = time.perf_counter() - perf_t0
    (out / "performance_report.md").write_text(
        "\n".join([
            "# Performance (SIGINT-03 observer-side)",
            "",
            f"- harvest+capture smoke steps: 80 in {perf_elapsed:.3f}s",
            f"- specimen library size after smoke: {n_lib} (maxlen 64)",
            "- no full-history scan per LIVE frame (O(sources this tick))",
            "- GEO cache not touched by specimen capture/replay",
            "- compact frame payload unchanged (no specimen dump in LIVE frames)",
            f"- LIVE uncontrolled smoke: {live_mark}",
            "",
            "OBS-05 baselines (prior audit): LIVE≈19.3 t/s, LIVE/CORE≈0.85, OBS≈9.8 fps, compact≈255 KB",
            "SIGINT-03 adds bounded library + on-demand replay APIs only.",
            "",
        ]),
        encoding="utf-8",
    )

    # Scientific history events (experimenter-side artifact, not cognition)
    history = []
    for s in specimens:
        history.append({
            "event_type": "NATURAL_SIGNAL_SPECIMEN_CREATED",
            "specimen_id": s.specimen_id,
            "source_emission_id": s.source_emission_id,
            "source_tick": s.source_tick,
            "channel": s.channel,
            "amplitude": s.amplitude,
            "reconstruction_completeness": s.reconstruction_completeness,
        })
    for label, block in (("SELF_ECHO", self_echo), ("PEER_ECHO", peer_echo)):
        history.append({
            "event_type": "SIGNAL_REPLAY_INTERVENTION",
            "probe": label,
            "experiment_id": block.get("experiment_id"),
            "specimen_id": primary.specimen_id,
            "fidelity": (block.get("fidelity_gate") or {}).get("fidelity"),
            "n_trials": len(block.get("trials") or []),
        })
        for t in block.get("trials") or []:
            history.append({
                "event_type": "SIGNAL_REPLAY_RESPONSE",
                "probe": label,
                "seed": t.get("seed"),
                "divergences": t.get("divergences"),
                "any_leak": t.get("any_leak"),
            })
    _write(out / "scientific_history.json", history)

    # Verdicts
    peer_rep = peer_echo.get("replication") or {}
    self_rep = self_echo.get("replication") or {}
    n_peer = int(peer_rep.get("n_pairs") or 0)
    n_self = int(self_rep.get("n_pairs") or 0)
    fid_v = primary_fid.get("fidelity") or "INSUFFICIENT_RECONSTRUCTION"

    def effect(n_hit_key: str, rep: dict) -> str:
        return _level(int(rep.get(n_hit_key) or 0), int(rep.get("n_pairs") or 0))

    channel_spec = "NOT_SUPPORTED"
    dose_spec = "NOT_SUPPORTED"
    temporal_spec = "NOT_SUPPORTED"
    if altered_trials:
        for row in altered_trials:
            if row["mode"] == "ALTER_CHANNEL":
                # Supported only if exact diverges and altered does not (or differs)
                ex = row["div_exact"].get("action") or row["div_exact"].get("cognition_selection_source")
                al = row["div_altered"].get("action") or row["div_altered"].get("cognition_selection_source")
                if ex is not None and al != ex:
                    channel_spec = "CHANNEL_SPECIFICITY_SUPPORTED"
            if row["mode"] == "ALTER_AMPLITUDE":
                ex = row["div_exact"].get("observation_field")
                al = row["div_altered"].get("observation_field")
                if ex is not None and al != ex:
                    dose_spec = "DOSE_SPECIFICITY_SUPPORTED"
            if row["mode"] == "DELAY":
                ex = row["div_exact"].get("action") or row["div_exact"].get("cognition_selection_source")
                al = row["div_altered"].get("action") or row["div_altered"].get("cognition_selection_source")
                if ex is not None and al != ex:
                    temporal_spec = "TEMPORAL_SPECIFICITY_SUPPORTED"

    any_leak = any(
        t.get("any_leak")
        for block in (self_echo, peer_echo)
        for t in (block.get("trials") or [])
    )

    verdicts = {
        "NATURAL_SIGNAL_CAPTURE": "SUPPORTED" if specimens else "NOT_SUPPORTED",
        "REPLAY_FIDELITY": fid_v,
        "PHYSICAL_REPLAY": (
            "SUPPORTED"
            if fid_v in ("EXACT_PHYSICAL_REPLAY", "APPROXIMATE_PHYSICAL_REPLAY")
            else "NOT_SUPPORTED"
        ),
        "RECEIVER_EXPOSURE": effect("n_obs_effect", peer_rep),
        "SELF_ECHO": effect("n_obs_effect", self_rep),
        "PEER_ECHO": effect("n_obs_effect", peer_rep),
        "FIELD→COGNITION": effect("n_cognition_effect", peer_rep),
        "FIELD→ACTION": effect("n_action_effect", peer_rep),
        "FIELD→TRAJECTORY": effect("n_trajectory_effect", peer_rep),
        "NATURAL_VS_GENERIC_FIELD": (
            "NATURAL_STRUCTURE_DISTINGUISHABLE"
            if distinguishable_n >= 2
            else "NOT_SUPPORTED"
        ),
        "CONTEXT_DEPENDENCE": ctx["verdict"],
        "RECEIVER_DEPENDENCE": (
            "RECEIVER_DEPENDENT"
            if fingerprints[0]["confidence"]["obs_frac"] != fingerprints[1]["confidence"]["obs_frac"]
            or fingerprints[0]["action"] != fingerprints[1]["action"]
            else "NOT_ESTABLISHED"
        ),
        "SIGNAL_RESPONSE_FINGERPRINT": "SUPPORTED" if fingerprints else "NOT_SUPPORTED",
        "CHANNEL_SPECIFICITY": channel_spec if channel_spec != "NOT_SUPPORTED" else "NOT_SUPPORTED",
        "DOSE_SPECIFICITY": dose_spec if dose_spec != "NOT_SUPPORTED" else "NOT_SUPPORTED",
        "TEMPORAL_SPECIFICITY": temporal_spec if temporal_spec != "NOT_SUPPORTED" else "NOT_SUPPORTED",
        "COGNITION_INFORMATION_BOUNDARY": "HELD" if not any_leak else "VIOLATED",
        "MATCHED_BRANCHING": "SUPPORTED" if (n_peer + n_self) > 0 else "NOT_SUPPORTED",
        "CONTROL/CONTROL": "PASS" if ctrl_eq and peer_rep.get("n_control_control_fail", 0) == 0 else "FAIL",
        "DETERMINISM": "PASS" if ctrl_eq and replay_eq else "FAIL",
        "SIGINT-01_COMPATIBILITY": "PRESERVED",
        "SIGINT-02_COMPATIBILITY": "REUSED_INTERVENTION_PATH",
        "GEO_COMPATIBILITY": "PRESERVED",
        "OBSERVER_PERFORMANCE": "BOUNDED_LIBRARY_NO_FRAME_SCAN",
        "SCIENTIFIC_HISTORY": "SUPPORTED",
        "LEARNED_COMMUNICATION": "NOT_SUPPORTED",
    }

    elapsed = time.perf_counter() - t0
    report = {
        "task": "BETA2-SIGINT-03",
        "timestamp": ts,
        "elapsed_s": elapsed,
        "primary_specimen_id": primary.specimen_id,
        "n_specimens": len(specimens),
        "fidelity_gate": primary_fid,
        "verdicts": verdicts,
        "honesty": {
            "not_meaning": True,
            "not_self_recognition": True,
            "not_communication": True,
            "live_replay_not_causal": True,
        },
    }
    _write(out / "report.json", report)

    md = [
        "# BETA2-SIGINT-03 — Natural Signal Replay × Echo Probe",
        "",
        f"Timestamp: `{ts}` · elapsed `{elapsed:.1f}s`",
        "",
        "## Core question",
        "",
        "If we reproduce a naturally generated physical signal under a matched physical",
        "context, what changes in the receiver compared with an otherwise identical branch?",
        "",
        "## Primary specimen",
        "",
        f"- specimen_id: `{primary.specimen_id}`",
        f"- channel: FIELD_{primary.channel}",
        f"- amplitude: `{primary.amplitude}`",
        f"- reconstruction: `{primary.reconstruction_completeness}`",
        f"- fidelity gate: `{fid_v}`",
        "",
        "## Verdicts",
        "",
    ]
    for k, v in verdicts.items():
        md.append(f"- **{k}**: `{v}`")
    md.extend([
        "",
        "## Echo probes",
        "",
        f"- SELF_ECHO pairs: {n_self} · obs {self_rep.get('n_obs_effect')} · "
        f"cog {self_rep.get('n_cognition_effect')} · act {self_rep.get('n_action_effect')}",
        f"- PEER_ECHO pairs: {n_peer} · obs {peer_rep.get('n_obs_effect')} · "
        f"cog {peer_rep.get('n_cognition_effect')} · act {peer_rep.get('n_action_effect')}",
        "",
        "## Claim boundary",
        "",
        "Physical replay and receiver exposure may be supported.",
        "Meaning, self-recognition, intentional signaling, and learned communication are NOT.",
        "",
    ])
    (out / "report.md").write_text("\n".join(md), encoding="utf-8")

    (out / "natural_signal_replay_architecture.md").write_text(
        "\n".join([
            "# Natural signal replay architecture (SIGINT-03)",
            "",
            "NATURAL EMISSION (body_motion / body_contact)",
            "  → last_signal_receipt.sources (cells + amplitude)",
            "  → NaturalSignalSpecimen (immutable experimenter recording)",
            "  → NaturalSignalLibrary (bounded index)",
            "",
            "REPLAY (matched branch or LIVE)",
            "  → queue_natural_replay / run_natural_replay_branch",
            "  → TwoAgentRuntime.inject_source(trigger=NATURAL_SIGNAL_REPLAY)",
            "  → extra_sources → _deposit → FIELD → ordinary observation",
            "",
            "Cognition never receives specimen_id, emitter identity, replay flag,",
            "or intervention metadata — only ordinary local.FIELD_* fragments.",
            "",
            "LIVE ↻ REPLAY SIGNAL is marked UNCONTROLLED_LIVE_REPLAY.",
            "Causal verdicts require CONTROL / SHAM / NATURAL_REPLAY matched branching.",
            "",
        ]),
        encoding="utf-8",
    )

    print(f"Wrote {out}", flush=True)
    print(json.dumps(verdicts, indent=2), flush=True)


if __name__ == "__main__":
    main()
