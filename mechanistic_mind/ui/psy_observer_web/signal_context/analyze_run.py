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
    dist = (dx * dx + dy * dy) ** 0.5
    return {
        "status": "AVAILABLE",
        "distance": dist,
        "relative_bearing_xy": [dx, dy],
        "contact": bool(a0.get("contact") or a1.get("contact")),
        "honesty": {
            "other_agent_cognition_not_exposed": True,
            "observer_ground_truth_only": True,
        },
    }


def signal_episode_context(
    episode: dict[str, Any],
    *,
    timeline_rows: list[dict[str, Any]],
    steps: list[dict[str, Any]],
    reception_ticks: set[tuple[str, int]],
    baseline_mean: float = 0.0,
    baseline_std: float = 0.0,
    all_peaks: list[float] | None = None,
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

    # Requested vs realized around peak
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
    # Approximate alignments from steps near PRE last / POST first
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

    relation = _two_agent_relation(timeline_rows, tick=peak_t)

    evidence_verdict = comparison.get("evidence") or "NOT_ESTABLISHED"
    if evidence_verdict == "MATCHED_ASSOCIATION":
        # Still not causal
        pass

    return {
        "signal_episode": episode,
        "informativeness": info,
        "windows": {
            "spec": windows.get("window_spec"),
            "availability": windows.get("availability"),
            # omit full tick lists in default return — keep summaries in delta
        },
        "physical_relation": relation,
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
) -> dict[str, Any]:
    """Retrospective signal-context analysis package."""
    run_dir = Path(run_dir)
    rid = run_id or run_dir.name
    timeline_path = run_dir / "scientific_timeline.jsonl"
    events_path = run_dir / "scientific_events.jsonl"
    if not timeline_path.exists():
        raise FileNotFoundError(timeline_path)

    rows = load_timeline_jsonl(timeline_path, max_rows=max_timeline_rows)
    events = []
    if events_path.exists():
        events = load_events_jsonl(
            events_path,
            max_events=max_events,
            types={"PHYSICAL_SIGNAL_RECEIVED", "PHYSICAL_SIGNAL_EMITTED", "SCENARIO_SELECTED"},
        )

    episodes = group_signal_episodes(events, run_id=rid, generation=generation)
    recv_ticks = _reception_tick_set(events)
    steps = steps_from_timeline_rows(rows, width=width, height=height)
    base_mean, base_std = _baseline_stats(episodes)
    peaks = [float(e["intensity"]["peak"]) for e in episodes]

    # Prefer informative + focus-tick episodes for detailed analysis
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

    interesting = interesting[:max_episode_details]
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

    # Channel tallies
    ch_counts: dict[str, int] = {}
    attr_counts: dict[str, int] = {}
    for ep in episodes:
        ch_counts[str(ep["channel"])] = ch_counts.get(str(ep["channel"]), 0) + 1
        attr_counts[str(ep["attribution"])] = attr_counts.get(str(ep["attribution"]), 0) + 1

    matched_assoc = sum(
        1 for d in details if d.get("EVIDENCE_VERDICT") == "MATCHED_ASSOCIATION"
    )

    return {
        "run_id": rid,
        "generation": generation,
        "n_timeline_rows": len(rows),
        "n_events_loaded": len(events),
        "n_episodes": len(episodes),
        "n_episode_details": len(details),
        "channel_counts": ch_counts,
        "attribution_counts": attr_counts,
        "baseline_intensity": {"mean": base_mean, "std": base_std},
        "matched_association_count": matched_assoc,
        "patterns": patterns,
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
            }
            for e in episodes
        ],
        "history_coverage": {
            "timeline_fields": {
                "action": "AVAILABLE",
                "action_source": "AVAILABLE",
                "prediction_count": "PARTIAL",
                "prospective_compositions": "PARTIAL",
                "local.FIELD_*": "MISSING",
                "memory_fingerprint": "MISSING",
            },
            "events": {
                "PHYSICAL_SIGNAL_RECEIVED": "AVAILABLE",
                "PHYSICAL_SIGNAL_EMITTED": "AVAILABLE",
                "SCENARIO_SELECTED": "AVAILABLE",
                "causal_parent_ids_into_cognition": "MISSING",
            },
            "fake_zero_note": (
                "prediction_count==0 with SCENARIO_SELECTED present is PARTIAL coverage, "
                "not absent cognition."
            ),
        },
        "intervention_harness": {
            "status": "DESIGN_ONLY_SIGINT_02",
            "note": (
                "Safe controlled FIELD_A/B injection at matched contexts deferred; "
                "see intervention_design.md in artifacts."
            ),
        },
        "honesty": {
            "observer_only": True,
            "no_communication_claim": True,
            "no_other_agent_cognition_leak": True,
            "reception_to_cognition": "NOT_CAUSALLY_LINKED_IN_RUNTIME",
        },
    }


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    n = 0
    with path.open("w") as fh:
        for row in rows:
            fh.write(json.dumps(row, default=str) + "\n")
            n += 1
    return n
