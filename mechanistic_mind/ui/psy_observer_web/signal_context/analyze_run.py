"""Offline signal-context analysis from scientific history."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from mechanistic_mind.ui.psy_observer_web.geometry.analyze_run import load_timeline_jsonl
from mechanistic_mind.ui.psy_observer_web.geometry.context import geometry_context
from mechanistic_mind.ui.psy_observer_web.geometry.metrics import (
    action_alignment,
    realized_displacement,
)
from mechanistic_mind.ui.psy_observer_web.geometry.traversability import steps_from_timeline_rows
from mechanistic_mind.ui.psy_observer_web.signal_context.cognition_delta import (
    action_geometry_separation,
    cognitive_delta,
)
from mechanistic_mind.ui.psy_observer_web.signal_context.episodes import (
    episode_informativeness,
    group_signal_episodes,
)
from mechanistic_mind.ui.psy_observer_web.signal_context.matched_controls import (
    compare_episode_vs_controls,
    find_matched_controls,
)
from mechanistic_mind.ui.psy_observer_web.signal_context.patterns import cluster_patterns
from mechanistic_mind.ui.psy_observer_web.signal_context.windows import extract_windows
from mechanistic_mind.ui.psy_observer_web.signal_context.composite_signal_forensics import (
    run_composite_signal_forensics,
)


def load_events_jsonl(
    path: Path,
    *,
    max_events: int | None = None,
    types: set[str] | None = None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    n = 0
    with path.open() as fh:
        for ln in fh:
            ln = ln.strip()
            if not ln:
                continue
            n += 1
            if max_events is not None and n > max_events:
                break
            ev = json.loads(ln)
            if types is not None:
                t = str(ev.get("type") or ev.get("kind") or "")
                if t not in types:
                    continue
            out.append(ev)
    return out


def _reception_tick_set(events: list[dict[str, Any]]) -> set[tuple[str, int]]:
    s: set[tuple[str, int]] = set()
    for ev in events:
        if str(ev.get("type") or "") != "PHYSICAL_SIGNAL_RECEIVED":
            continue
        evidence = ev.get("evidence") if isinstance(ev.get("evidence"), dict) else {}
        aid = str(
            ev.get("receiver_agent_id")
            or evidence.get("receiver_agent_id")
            or ev.get("agent_id")
            or ""
        )
        s.add((aid, int(ev.get("tick") or -1)))
    return s


def _baseline_stats(episodes: list[dict[str, Any]]) -> tuple[float, float]:
    peaks = [float(e["intensity"]["peak"]) for e in episodes]
    if not peaks:
        return 0.0, 0.0
    mean = sum(peaks) / len(peaks)
    var = sum((p - mean) ** 2 for p in peaks) / len(peaks)
    return mean, var ** 0.5


def _percentile(value: float, values: list[float]) -> float:
    if not values:
        return 0.0
    n = sum(1 for v in values if v <= value)
    return 100.0 * n / len(values)


def _two_agent_relation(
    timeline_rows: list[dict[str, Any]],
    *,
    tick: int,
    width: int = 32,
    height: int = 32,
) -> dict[str, Any]:
    a0 = next(
        (r for r in timeline_rows if r.get("agent_id") == "agent_0" and int(r.get("tick") or -1) == tick),
        None,
    )
    a1 = next(
        (r for r in timeline_rows if r.get("agent_id") == "agent_1" and int(r.get("tick") or -1) == tick),
        None,
    )
    if not a0 or not a1:
        return {"status": "NOT_AVAILABLE"}
    dx = float(a1["x"]) - float(a0["x"])
    dy = float(a1["y"]) - float(a0["y"])
    w, h = max(1, int(width)), max(1, int(height))
    # WRAP_PERIODIC minimum-image distance
    dx -= w * round(dx / w)
    dy -= h * round(dy / h)
    dist = (dx * dx + dy * dy) ** 0.5
    return {
        "status": "AVAILABLE",
        "distance": dist,
        "relative_bearing_xy": [dx, dy],
        "boundary": "WRAP_PERIODIC",
        "distance_definition": "minimum_image",
        "contact": bool(a0.get("contact") or a1.get("contact")),
        "honesty": {
            "other_agent_cognition_not_exposed": True,
            "observer_ground_truth_only": True,
            "not_attraction_or_intent": True,
        },
    }


def compute_temporal_physical_relations(
    *,
    scientific_rows: list[dict[str, Any]],
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    """First cross-agent contribution / optical exposure / contact + tick deltas.

    Temporal measurements only — not causal effects.
    Optical exposure uses the same vision_optical.body_exposure authority as Visual Forensics.
    """
    first_contact: int | None = None
    first_optical: int | None = None
    for r in scientific_rows:
        try:
            t = int(r.get("tick"))
        except (TypeError, ValueError):
            continue
        if r.get("contact") and (first_contact is None or t < first_contact):
            first_contact = t
        vo = r.get("vision_optical") if isinstance(r.get("vision_optical"), dict) else {}
        if vo.get("body_exposure") and (first_optical is None or t < first_optical):
            first_optical = t

    first_cross: int | None = None
    for ev in events:
        et = str(ev.get("type") or ev.get("kind") or "")
        if "SIGNAL_RECEIVED" not in et.upper():
            continue
        evidence = ev.get("evidence") if isinstance(ev.get("evidence"), dict) else {}
        recv = str(
            ev.get("receiver_agent_id")
            or evidence.get("receiver_agent_id")
            or ev.get("agent_id")
            or ""
        )
        parents = evidence.get("contributing_emissions_this_tick") or []
        if not isinstance(parents, list):
            continue
        for p in parents:
            if not isinstance(p, dict):
                continue
            em = str(p.get("emitter_agent_id") or "")
            if em.startswith("agent_") and recv.startswith("agent_") and em != recv:
                try:
                    t = int(ev.get("tick"))
                except (TypeError, ValueError):
                    continue
                if first_cross is None or t < first_cross:
                    first_cross = t
                break

    def _delta(a: int | None, b: int | None) -> int | None:
        if a is None or b is None:
            return None
        return int(b) - int(a)

    return {
        "first_cross_agent_contribution_tick": first_cross,
        "first_body_optical_exposure_tick": first_optical,
        "first_physical_contact_tick": first_contact,
        "signal_to_optical_delta": _delta(first_cross, first_optical),
        "signal_to_contact_delta": _delta(first_cross, first_contact),
        "optical_to_contact_delta": _delta(first_optical, first_contact),
        "optical_authority": "vision_optical.body_exposure (same as Visual Forensics)",
        "contact_authority": "scientific_timeline.contact",
        "semantics": {
            "temporal_only": True,
            "not_causal_effects": True,
            "reception_to_cognition": "NOT_ESTABLISHED",
            "physical_signal_neq_message": True,
        },
    }


def analyze_signal_from_rows_events(
    *,
    rows: list[dict[str, Any]],
    events: list[dict[str, Any]],
    run_id: str | None = None,
    generation: int | None = None,
    width: int = 32,
    height: int = 32,
    max_episode_details: int = 80,
    min_peak_percentile: float = 70.0,
    focus_ticks: list[int] | None = None,
    source_label: str = "CURRENT_RUN",
    telemetry_schema: str | None = None,
    coverage: str | None = None,
    runtime_status: str | None = None,
    cutoff_tick: int | None = None,
    meta: dict[str, Any] | None = None,
    seed: int | None = None,
) -> dict[str, Any]:
    """Core Signal Forensics from scientific_rows + events (V1 or V2 package)."""
    rid = run_id or "unknown"
    # Keep signal + scenario + motor/effector events; V2 may use PHYSICAL_SIGNAL_* only.
    sig_types = {
        "PHYSICAL_SIGNAL_RECEIVED",
        "PHYSICAL_SIGNAL_EMITTED",
        "SCENARIO_SELECTED",
        "DISCRETE_ACTION_SELECTED",
        "NECK_MOTOR_APPLIED",
        "NECK_TORQUE_APPLIED",
        "PUSH_EXERTED",
        "OSC_EMISSION_STARTED",
        "OSC_EMISSION_ENDED",
        "OSC_PARAMETER_CHANGED",
        "MOTOR_COMPONENT_SELECTED",
    }
    filtered = []
    for ev in events:
        t = str(ev.get("type") or ev.get("kind") or "")
        if t in sig_types or "SIGNAL_" in t.upper() or t.startswith("OSC_") or t.startswith("MOTOR_"):
            filtered.append(ev)

    episodes = group_signal_episodes(filtered, run_id=rid, generation=generation)
    recv_ticks = _reception_tick_set(filtered)
    steps = steps_from_timeline_rows(rows, width=width, height=height)
    base_mean, base_std = _baseline_stats(episodes)
    peaks = [float(e["intensity"]["peak"]) for e in episodes]

    interesting: list[dict[str, Any]] = []
    focus = set(int(t) for t in (focus_ticks or []))
    for ep in episodes:
        pct = _percentile(float(ep["intensity"]["peak"]), peaks)
        near_focus = any(
            abs(int(ep["start_tick"]) - t) <= 40 or abs(int(ep["peak_tick"]) - t) <= 40
            for t in focus
        ) if focus else False
        if pct >= min_peak_percentile or near_focus or "body_contact" in (
            ep.get("trigger_composition") or []
        ):
            interesting.append(ep)

    # Prefer recent peaks when no explicit focus (current-run UX).
    if not focus and interesting:
        interesting.sort(key=lambda e: int(e.get("peak_tick") or 0), reverse=True)
    interesting = interesting[:max_episode_details]
    # Restore chronological order for display
    interesting.sort(key=lambda e: int(e.get("peak_tick") or 0))

    details: list[dict[str, Any]] = []
    pattern_inputs: list[dict[str, Any]] = []
    for ep in interesting:
        ctx = signal_episode_context(
            ep,
            timeline_rows=rows,
            steps=steps,
            reception_ticks=recv_ticks,
            baseline_mean=base_mean,
            baseline_std=base_std,
            all_peaks=peaks,
            width=width,
            height=height,
        )
        details.append(ctx)
        d = ctx["cognition_delta"]
        pattern_inputs.append(
            {
                "signal_episode": ep["episode_id"],
                "receiver": ep["receiver_agent_id"],
                "PRE": d.get("PRE"),
                "SIGNAL": {
                    "channel": ep.get("channel"),
                    "cross_agent_contribution_fraction": ep.get(
                        "cross_agent_contribution_fraction"
                    ),
                },
                "DELTA": d.get("DELTA"),
                "matched_comparison": ctx.get("matched_comparison"),
            }
        )

    patterns = cluster_patterns(pattern_inputs, min_episodes=3)

    ch_counts: dict[str, int] = {}
    attr_counts: dict[str, int] = {}
    cross_agent_eps = 0
    contact_trig = 0
    for ep in episodes:
        ch_counts[str(ep["channel"])] = ch_counts.get(str(ep["channel"]), 0) + 1
        attr_counts[str(ep["attribution"])] = attr_counts.get(str(ep["attribution"]), 0) + 1
        if float(ep.get("cross_agent_contribution_fraction") or 0) > 0:
            cross_agent_eps += 1
        if "body_contact" in (ep.get("trigger_composition") or []):
            contact_trig += 1

    matched_assoc = sum(
        1 for d in details if d.get("EVIDENCE_VERDICT") == "MATCHED_ASSOCIATION"
    )
    temporal = compute_temporal_physical_relations(scientific_rows=rows, events=filtered)

    ticks = [int(r["tick"]) for r in rows if "tick" in r]
    tick_min = min(ticks) if ticks else None
    tick_max = max(ticks) if ticks else None
    cut = cutoff_tick if cutoff_tick is not None else tick_max

    composite_pkg = run_composite_signal_forensics(
        rows=rows,
        events=filtered,
        meta=meta,
        run_id=rid,
        generation=generation,
        seed=seed,
        cutoff_tick=cut,
        telemetry_schema=telemetry_schema,
        coverage=coverage,
        source_label=source_label,
    )

    return {
        "analysis_source": source_label,
        "run_id": rid,
        "generation": generation,
        "seed": seed if seed is not None else (meta or {}).get("seed"),
        "runtime_status": runtime_status,
        "cutoff_tick": cut,
        "telemetry_schema": telemetry_schema,
        "motor_schema": composite_pkg["source"]["motor_schema"],
        "coverage": coverage,
        "scientific_tick_range": [tick_min, tick_max],
        "n_timeline_rows": len(rows),
        "n_events_loaded": len(filtered),
        "n_episodes": len(episodes),
        "n_episode_details": len(details),
        "n_cross_agent_episodes": cross_agent_eps,
        "n_contact_triggered_episodes": contact_trig,
        "channel_counts": ch_counts,
        "attribution_counts": attr_counts,
        "baseline_intensity": {"mean": base_mean, "std": base_std},
        "matched_association_count": matched_assoc,
        "matched_association_definition": {
            "label": "CANDIDATE ASSOCIATION" if matched_assoc else "NONE",
            "meaning": (
                "Episode PRE→POST cognitive/action delta differs from matched no/low-signal "
                "controls at the same receiver physical context fingerprint "
                "(region/action/contact/speed/work bins). Not causal proof. Not communication."
            ),
            "control_construction": (
                "find_matched_controls: exclude ±30 ticks around episode; score region(+2), "
                "action, action_source, contact, speed_bin; require score≥4 for GOOD."
            ),
            "classification": "MATCHED_ASSOCIATION is a statistical candidate, not established causation.",
        },
        "pattern_definition": {
            "meaning": (
                "cluster_patterns groups reproducible PRE/SIGNAL/DELTA statistical structures "
                "across episodes (channel, action-change rates). Not words, symbols, or messages."
            ),
            "linguistic": False,
        },
        "patterns": patterns,
        "temporal_physical_relations": temporal,
        "episode_details": details,
        "episodes_compact": [
            {
                "episode_id": e["episode_id"],
                "receiver_agent_id": e["receiver_agent_id"],
                "start_tick": e["start_tick"],
                "peak_tick": e["peak_tick"],
                "end_tick": e["end_tick"],
                "channel": e["channel"],
                "peak": e["intensity"]["peak"],
                "attribution": e["attribution"],
                "cross_agent_contribution_fraction": e.get(
                    "cross_agent_contribution_fraction"
                ),
                "trigger_composition": e.get("trigger_composition"),
            }
            for e in episodes
        ],
        # --- COMPOSITE MOTOR × OSC V2 ---
        "source": composite_pkg["source"],
        "signal_systems": composite_pkg["signal_systems"],
        "oscillatory_episodes": composite_pkg["oscillatory_episodes"],
        "n_oscillatory_episodes": composite_pkg["n_oscillatory_episodes"],
        "spectrotemporal_patterns": composite_pkg["spectrotemporal_patterns"],
        "full_duplex": composite_pkg["full_duplex"],
        "composite_motor": composite_pkg["composite_motor"],
        "interaction_chronology": composite_pkg["interaction_chronology"],
        "candidate_associations": composite_pkg["candidate_associations"],
        "scientific_boundary": composite_pkg["scientific_boundary"],
        "fixture_mixed": False,
        "user_triggered": True,
        "polling_on_refresh": False,
        "live_vs_historical": {
            "historical_episodes": len(episodes),
            "note": (
                "LIVE buffer episode count is independent. LIVE=0 does not imply historical=0."
            ),
        },
        "history_coverage": {
            "timeline_fields": {
                "action": "AVAILABLE",
                "action_source": "AVAILABLE",
                "motor_output": (
                    "AVAILABLE" if any(r.get("motor_output") for r in rows[:200]) else "DERIVED"
                ),
                "prediction_count": "PARTIAL",
                "prospective_compositions": "PARTIAL",
                "vision_optical": "AVAILABLE" if any(r.get("vision_optical") for r in rows) else "NOT_AVAILABLE",
                "local.FIELD_*": "VIA_EVENTS",
                "osc_*": "AVAILABLE" if any(
                    r.get("osc_emit_active") is not None for r in rows[:50]
                ) else "NOT_AVAILABLE",
            },
            "events": {
                "PHYSICAL_SIGNAL_RECEIVED": "AVAILABLE",
                "PHYSICAL_SIGNAL_EMITTED": "AVAILABLE",
                "SCENARIO_SELECTED": "AVAILABLE",
                "NECK_MOTOR_APPLIED": "AVAILABLE",
                "PUSH_EXERTED": "AVAILABLE",
                "causal_parent_ids_into_cognition": "MISSING",
            },
            "fake_zero_note": (
                "prediction_count==0 with SCENARIO_SELECTED present is PARTIAL coverage, "
                "not absent cognition."
            ),
        },
        "honesty": {
            "observer_only": True,
            "no_communication_claim": True,
            "no_other_agent_cognition_leak": True,
            "physical_signal_neq_message": True,
            "emission_neq_intention": True,
            "reception_neq_interpretation": True,
            "reception_to_cognition": "NOT_ESTABLISHED",
            "temporal_association_neq_causal_link": True,
            "reference_fixture_not_auto_loaded": source_label != "REFERENCE_FIXTURE",
        },
    }


def analyze_signal_run(
    run_dir: Path,
    *,
    run_id: str | None = None,
    generation: int | None = None,
    width: int = 32,
    height: int = 32,
    max_timeline_rows: int | None = None,
    max_events: int | None = None,
    max_episode_details: int = 80,
    min_peak_percentile: float = 70.0,
    focus_ticks: list[int] | None = None,
    source_label: str = "SAVED_RUN",
) -> dict[str, Any]:
    """Retrospective signal-context analysis from a published/saved run directory."""
    run_dir = Path(run_dir)
    rid = run_id or run_dir.name
    timeline_path = run_dir / "scientific_timeline.jsonl"
    events_path = run_dir / "scientific_events.jsonl"
    if not timeline_path.exists():
        raise FileNotFoundError(timeline_path)

    rows = load_timeline_jsonl(timeline_path, max_rows=max_timeline_rows)
    events: list[dict[str, Any]] = []
    if events_path.exists():
        # Load all events — filter happens inside analyze_signal_from_rows_events
        events = load_events_jsonl(events_path, max_events=max_events, types=None)
    meta: dict[str, Any] = {}
    meta_path = run_dir / "scientific_meta.json"
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            meta = {}
    from mechanistic_mind.ui.psy_observer_web.scientific_telemetry_v2 import detect_telemetry_schema

    schema = detect_telemetry_schema(meta, rows[0] if rows else None)
    return analyze_signal_from_rows_events(
        rows=rows,
        events=events,
        run_id=rid,
        generation=generation if generation is not None else meta.get("runtime_generation"),
        width=width,
        height=height,
        max_episode_details=max_episode_details,
        min_peak_percentile=min_peak_percentile,
        focus_ticks=focus_ticks,
        source_label=source_label,
        telemetry_schema=schema,
        coverage="FULL" if rows else "UNAVAILABLE",
        runtime_status="STOPPED",
        cutoff_tick=max((int(r["tick"]) for r in rows if "tick" in r), default=None),
        meta=meta,
        seed=meta.get("seed"),
    )


def signal_episode_context(
    episode: dict[str, Any],
    *,
    timeline_rows: list[dict[str, Any]],
    steps: list[dict[str, Any]],
    reception_ticks: set[tuple[str, int]],
    baseline_mean: float = 0.0,
    baseline_std: float = 0.0,
    all_peaks: list[float] | None = None,
    width: int = 32,
    height: int = 32,
) -> dict[str, Any]:
    """Full investigation record for one episode (ANALYZE path)."""
    windows = extract_windows(episode, timeline_rows)
    delta = cognitive_delta(
        windows,
        episode_id=str(episode["episode_id"]),
        receiver_agent_id=str(episode["receiver_agent_id"]),
    )
    controls = find_matched_controls(
        episode, timeline_rows, reception_ticks
    )
    comparison = compare_episode_vs_controls(delta, controls)

    peak = float(episode["intensity"]["peak"])
    pct = _percentile(peak, all_peaks or []) if all_peaks else None
    info = episode_informativeness(
        episode,
        baseline_mean=baseline_mean,
        baseline_std=baseline_std,
        percentile=pct,
    )

    geo = geometry_context(
        steps,
        agent_id=str(episode["receiver_agent_id"]),
        tick=int(episode["peak_tick"]),
        window=10,
    )

    aid = str(episode["receiver_agent_id"])
    peak_t = int(episode["peak_tick"])
    step_at = next(
        (s for s in steps if str(s.get("agent_id")) == aid and int(s.get("tick") or -1) == peak_t),
        None,
    )
    pre_action = (delta.get("PRE") or {}).get("action")
    post_action = (delta.get("POST") or {}).get("action")
    pre_align = None
    post_align = None
    for s in steps:
        if str(s.get("agent_id")) != aid:
            continue
        t = int(s.get("tick") or -1)
        if t == peak_t - 1:
            pre_align = s.get("action_alignment")
        if t == peak_t + 1:
            post_align = s.get("action_alignment")

    sep = action_geometry_separation(
        pre_action=pre_action,
        post_action=post_action,
        pre_alignment=pre_align if isinstance(pre_align, (int, float)) else None,
        post_alignment=post_align if isinstance(post_align, (int, float)) else None,
        geometry_note=str((geo.get("summary") or {})),
    )

    relation = _two_agent_relation(
        timeline_rows, tick=peak_t, width=width, height=height
    )
    # Geometry-only approach/retreat across episode window (not intent).
    rel_start = _two_agent_relation(
        timeline_rows, tick=int(episode["start_tick"]), width=width, height=height
    )
    rel_end = _two_agent_relation(
        timeline_rows, tick=int(episode["end_tick"]), width=width, height=height
    )
    approach_retreat: dict[str, Any] = {
        "status": "NOT_AVAILABLE",
        "semantics": "geometry_only_not_attraction_or_intent",
    }
    if rel_start.get("status") == "AVAILABLE" and rel_end.get("status") == "AVAILABLE":
        d0 = float(rel_start["distance"])
        d1 = float(rel_end["distance"])
        dd = d1 - d0
        if abs(dd) < 1e-6:
            label = "NO_CLEAR_CHANGE"
        elif dd < 0:
            label = "APPROACH"
        else:
            label = "RETREAT"
        approach_retreat = {
            "status": "AVAILABLE",
            "distance_at_start": d0,
            "distance_at_end": d1,
            "delta_distance": dd,
            "label": label,
            "boundary": "WRAP_PERIODIC",
            "distance_definition": "minimum_image",
            "semantics": "geometry_only_not_attraction_or_intent",
        }

    evidence_verdict = comparison.get("evidence") or "NOT_ESTABLISHED"

    return {
        "signal_episode": episode,
        "informativeness": info,
        "windows": {
            "spec": windows.get("window_spec"),
            "availability": windows.get("availability"),
        },
        "physical_relation": relation,
        "approach_retreat": approach_retreat,
        "geometry_context_summary": geo.get("summary"),
        "cognition_delta": delta,
        "action_geometry": sep,
        "matched_controls": {
            "match_quality": controls.get("match_quality"),
            "n_controls": controls.get("n_controls"),
            "controls": controls.get("controls"),
        },
        "matched_comparison": comparison,
        "step_at_peak": step_at,
        "EVIDENCE_VERDICT": evidence_verdict,
        "provenance": {
            "emission_to_field_to_reception": "CAUSALLY_LINKED",
            "reception_to_observation": "PARTIAL",
            "reception_to_cognitive_change": "NOT_ESTABLISHED"
            if evidence_verdict == "NOT_ESTABLISHED"
            else evidence_verdict,
            "direct_runtime_receipt_into_cognition": False,
            "note": "Anonymous local.FIELD_* floats enter cognition; RECEIVED event parents do not.",
        },
    }



def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    n = 0
    with path.open("w") as fh:
        for row in rows:
            fh.write(json.dumps(row, default=str) + "\n")
            n += 1
    return n
