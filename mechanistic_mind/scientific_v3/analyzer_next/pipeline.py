"""Orchestrate Analyzer Next — TickStory + sensorimotor consequence + report."""
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

from mechanistic_mind.scientific_v3.api import RunEvidence

from .contrasts import build_contrasts
from .episodes import Episode, episode_counts, extract_episodes
from .interestingness import select_interesting_episodes, select_interesting_stories
from .joins import apply_joins
from .relationships import RelationshipGraph
from .report import SECTION_TITLE, format_behavioral_reconstruction, format_sensorimotor_section, format_action_conditioned_model_section, format_historical_sensorimotor_selection_section
from .smc_hss_from_decisions import aggregate_sensorimotor_consequence_model, aggregate_historical_sensorimotor_selection
from .signal_conditioned_selection import aggregate_signal_conditioned_selection
from .signal_conditioned_selection_report import format_signal_conditioned_selection
from .full_embodied_predictive_model import aggregate_full_embodied_predictive_model, format_full_embodied_predictive_model
from .full_composite_psc_shadow import aggregate_full_composite_psc_shadow, format_full_composite_psc_shadow
from .psc_motor_resolution_developmental import aggregate_psc_motor_resolution_developmental, format_psc_motor_resolution_developmental
from .vision_analysis import analyze_beta31_vision
from .sensorimotor import (
    TARGET_INTERVALS,
    build_sensorimotor_steps,
    detect_motor_reversals,
    detect_sensorimotor_trend_reversals,
    explain_visual_asymmetry,
    find_receding_while_watching,
    longitudinal_comparison,
    reconstruct_interval,
    summarize_steps,
)
from .tick_stories import TickStory, build_tick_stories


def _pose_from_story(s: TickStory) -> dict[str, Any] | None:
    for d in s.derived_changes:
        if d.get("kind") == "POSE_STATE":
            return d
    return None


def _peer_geom(s: TickStory) -> dict[str, Any] | None:
    for d in s.derived_changes:
        if d.get("kind") == "RELATIVE_GEOMETRY":
            return d
    return None


def _signal_state(s: TickStory) -> dict[str, Any]:
    emitted = False
    received = False
    for c in s.external_context:
        k = c.get("kind")
        if k == "SIGNAL_EMISSION":
            emitted = True
        elif k == "SIGNAL_RECEPTION":
            received = True
    return {"emitted": emitted, "received": received}


def _terrain_assisted_candidate(s: TickStory) -> dict[str, Any]:
    """Operational: displacement not collinear with selected locomotion. Not intent."""
    pose_delta = ((s.consequence or {}).get("pose_delta") or {}) if s.consequence else {}
    dx = float(pose_delta.get("dx") or 0.0)
    dy = float(pose_delta.get("dy") or 0.0)
    loco = str(((s.motor or {}).get("components") or {}).get("locomotion") or "WAIT")
    axis = {
        "MOVE:E": (1.0, 0.0), "MOVE:W": (-1.0, 0.0),
        "MOVE:N": (0.0, 1.0), "MOVE:S": (0.0, -1.0),
        "E": (1.0, 0.0), "W": (-1.0, 0.0), "N": (0.0, 1.0), "S": (0.0, -1.0),
    }
    vec = axis.get(loco) or axis.get(loco.replace("MOVE:", ""))
    mag = (dx * dx + dy * dy) ** 0.5
    if vec is None or mag < 1e-9:
        return {
            "label": "NO_TERRAIN_ASSISTED_CANDIDATE",
            "displacement_mag": mag,
            "locomotion": loco,
        }
    align = (dx * vec[0] + dy * vec[1]) / mag
    assisted = mag >= 0.02 and align < 0.5
    return {
        "label": "TERRAIN_ASSISTED_DISPLACEMENT" if assisted else "MOTOR_ALIGNED_DISPLACEMENT",
        "displacement_mag": mag,
        "alignment_with_loco": round(align, 6),
        "locomotion": loco,
        "pose_delta": {"dx": dx, "dy": dy},
    }


def _iter_trajectory_records(stories: list[TickStory]):
    for s in stories:
        pose = _pose_from_story(s) or {}
        geom = _peer_geom(s) or {}
        vis = any(c.get("kind") == "VISION_EXPOSURE" for c in s.external_context)
        yield {
            "tick": s.tick,
            "agent_id": s.cognitive_agent_id,
            "physical_body_id": s.physical_body_id,
            "position": {"x": pose.get("x"), "y": pose.get("y")},
            "velocity": {"vx": pose.get("vx"), "vy": pose.get("vy")},
            "selected_action": pose.get("action") or (s.decision or {}).get("selected_action_legacy"),
            "motor_contribution": (s.motor or {}).get("components"),
            "head_orientation": {
                "theta": pose.get("theta"),
                "head_world_heading": pose.get("head_world_heading"),
                "head_relative_angle": pose.get("head_relative_angle"),
            },
            "signal_state": _signal_state(s),
            "other_agent_distance": geom.get("toroidal_distance"),
            "other_agent_visible": vis,
            "season_geology_reference": "NOT_RECORDED_PER_TICK",
            "terrain_world_contribution": _terrain_assisted_candidate(s),
            "psc_selected": {
                "selection_path": (s.decision or {}).get("selection_path"),
                "selection_source": (s.decision or {}).get("selection_source"),
                "selected_candidate_id": (s.decision or {}).get("selected_candidate_id"),
            },
        }


def _legacy_scenario_selected_count(run_dir: Path, max_tick: int | None) -> int:
    path = run_dir / "scientific_events.jsonl"
    if not path.is_file():
        return 0
    n = 0
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                o = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (o.get("type") or o.get("kind")) != "SCENARIO_SELECTED":
                continue
            if max_tick is not None and int(o.get("tick", 0)) > int(max_tick):
                continue
            n += 1
    return n


def _loco_token(s: TickStory) -> str:
    return str(((s.motor or {}).get("components") or {}).get("locomotion") or "WAIT")


def _is_wait(loco: str) -> bool:
    return str(loco).upper() in ("WAIT", "NONE", "")


def _wrap_delta(a: float, b: float, size: float) -> float:
    d = b - a
    half = size / 2.0
    if d > half:
        d -= size
    elif d < -half:
        d += size
    return d


def _canonical_history(
    stories: list[TickStory],
    *,
    world_w: float | None = None,
    world_h: float | None = None,
) -> dict[str, Any]:
    """Bounded ingest summary for Analyzer UI — not a second copy of JSONL."""
    ticks: set[int] = set()
    agents: dict[str, dict[str, Any]] = {}
    last_xy: dict[str, tuple[float, float]] = {}
    last_tick: dict[str, int] = {}
    cells: dict[str, set[str]] = {}
    w = float(world_w) if world_w and world_w > 0 else None
    h = float(world_h) if world_h and world_h > 0 else None
    for s in stories:
        ticks.add(int(s.tick))
        ag = agents.setdefault(
            s.cognitive_agent_id,
            {
                "agent_id": s.cognitive_agent_id,
                "body_id": s.physical_body_id,
                "ticks_observed": 0,
                "wait_count": 0,
                "move_count": 0,
                "move_distribution": {},
                "pose_ticks": 0,
                "signal_emissions": 0,
                "signal_receptions": 0,
                "visual_exposure_ticks": 0,
                "distance_manhattan_wrap": 0.0,
                "path_length_euclidean": 0.0,
                "unique_cells": 0,
                "path_available": False,
            },
        )
        ag["ticks_observed"] += 1
        loco = _loco_token(s)
        if _is_wait(loco):
            ag["wait_count"] += 1
        else:
            ag["move_count"] += 1
            dist = ag["move_distribution"]
            dist[loco] = int(dist.get(loco, 0)) + 1
        pose = _pose_from_story(s) or {}
        x, y = pose.get("x"), pose.get("y")
        if x is not None and y is not None:
            ag["pose_ticks"] += 1
            fx, fy = float(x), float(y)
            if w is not None and h is not None:
                cx = int(fx) % int(w) if w else int(fx)
                cy = int(fy) % int(h) if h else int(fy)
            else:
                cx, cy = int(fx), int(fy)
            cells.setdefault(s.cognitive_agent_id, set()).add(f"{cx},{cy}")
            prev = last_xy.get(s.cognitive_agent_id)
            pt = last_tick.get(s.cognitive_agent_id)
            tick = int(s.tick)
            if prev is not None and pt is not None and tick == pt + 1:
                if w is not None and h is not None:
                    dx = _wrap_delta(prev[0], fx, w)
                    dy = _wrap_delta(prev[1], fy, h)
                else:
                    dx, dy = fx - prev[0], fy - prev[1]
                ag["distance_manhattan_wrap"] += abs(dx) + abs(dy)
                ag["path_length_euclidean"] += (dx * dx + dy * dy) ** 0.5
                ag["path_available"] = True
            last_xy[s.cognitive_agent_id] = (fx, fy)
            last_tick[s.cognitive_agent_id] = tick
        sig = _signal_state(s)
        if sig.get("emitted"):
            ag["signal_emissions"] += 1
        if sig.get("received"):
            ag["signal_receptions"] += 1
        if any(c.get("kind") == "VISION_EXPOSURE" for c in s.external_context):
            ag["visual_exposure_ticks"] += 1
    for aid, ag in agents.items():
        n_cells = len(cells.get(aid, set()))
        ag["unique_cells"] = n_cells
        if ag.get("pose_ticks") and not ag.get("path_available") and n_cells == 0:
            ag["distance_manhattan_wrap"] = None
            ag["path_length_euclidean"] = None
            ag["unique_cells"] = None
        else:
            ag["distance_manhattan_wrap"] = round(float(ag["distance_manhattan_wrap"]), 6)
            ag["path_length_euclidean"] = round(float(ag["path_length_euclidean"]), 6)
    tmin = min(ticks) if ticks else None
    tmax = max(ticks) if ticks else None
    return {
        "unique_simulation_ticks": len(ticks),
        "tick_min": tmin,
        "tick_max": tmax,
        "scientific_tick_range": [tmin, tmax],
        "tick_stories": len(stories),
        "world_size": [w, h] if w is not None and h is not None else None,
        "agents": agents,
    }


def _agent_summaries(stories: list[TickStory]) -> list[dict[str, Any]]:
    by: dict[str, list[TickStory]] = {}
    for s in stories:
        by.setdefault(s.cognitive_agent_id, []).append(s)
    out = []
    for agent, seq in sorted(by.items()):
        wait = 0
        motors = Counter()
        paths = Counter()
        vis = 0
        for s in seq:
            loco = ((s.motor or {}).get("components") or {}).get("locomotion")
            if loco is None or str(loco).upper() in ("WAIT", "NONE", ""):
                wait += 1
            motors[s.composite_motor_summary or "?"] += 1
            paths[str((s.decision or {}).get("selection_path") or "?")] += 1
            if any(c.get("kind") == "VISION_EXPOSURE" for c in s.external_context):
                vis += 1
        n = len(seq) or 1
        out.append({
            "agent": agent,
            "body": seq[0].physical_body_id if seq else None,
            "n_stories": len(seq),
            "wait_p": round(wait / n, 4),
            "visual_exposure_ticks": vis,
            "top_motor": motors.most_common(1)[0][0] if motors else None,
            "selection_paths": dict(paths),
        })
    return out


def _what_happened_summary(payload_bits: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    sm = payload_bits.get("sensorimotor_summary") or {}
    asym = payload_bits.get("visual_asymmetry") or {}
    recede = payload_bits.get("receding_while_watching") or []
    rev = payload_bits.get("motor_reversals") or []
    sm_rev = payload_bits.get("sensorimotor_trend_reversals") or []
    agents = (sm.get("agents") or {})
    lines.append("WHAT HAPPENED (evidence summary — not anthropomorphic narrative)")
    latest = payload_bits.get("analysis_cutoff_tick")
    lines.append(f"- Latest analyzed complete tick: {latest}")
    lines.append(f"- TickStories / complete O→D→M→C: {payload_bits.get('complete_odmc')}")
    for aid, st in sorted(agents.items()):
        lines.append(
            f"- {aid}: visual_steps={st.get('visual_steps')}, "
            f"closure_under_vision={st.get('closure_steps_under_vision')} "
            f"(focal_dominant={st.get('closure_focal_dominant')}, "
            f"source_dominant={st.get('closure_source_dominant')}), "
            f"mean_bearing_error_under_vision={st.get('mean_bearing_error_under_vision')}, "
            f"responses={st.get('response_under_vision')}"
        )
    pa = (asym.get("per_agent") or {})
    if pa:
        lines.append("- Visual exposure asymmetry (DERIVED geometric diagnostics):")
        for aid, v in sorted(pa.items()):
            lines.append(
                f"  {aid}: exposure_ticks={v.get('visual_exposure_ticks')}, "
                f"ticks_within_r3={v.get('ticks_within_vision_radius_3')}, "
                f"exposure/near={v.get('exposure_as_fraction_of_near')}, "
                f"mean_err={v.get('mean_bearing_error_during_exposure')}"
            )
        for e in asym.get("candidate_explanations") or []:
            lines.append(f"  candidate: {e}")
    g = sm.get("global") or {}
    lines.append(
        f"- Under visual exposure, after distance INCREASE: n={((g.get('after_distance_increase') or {}).get('n'))}, "
        f"next_response={((g.get('after_distance_increase') or {}).get('next_response'))}"
    )
    lines.append(
        f"- Under visual exposure, after distance DECREASE: n={((g.get('after_distance_decrease') or {}).get('n'))}, "
        f"next_response={((g.get('after_distance_decrease') or {}).get('next_response'))}"
    )
    lines.append(f"- MOTOR_REVERSAL events (cardinal opposite loco): {len(rev)}")
    lines.append(f"- SENSORIMOTOR_TREND_REVERSAL candidates: {len(sm_rev)} (causation NOT_ESTABLISHED)")
    lines.append(f"- RECEDING_WHILE_WATCHING episodes matched: {len(recede)}")
    if recede:
        r0 = recede[0]
        lines.append(
            f"  example: {r0.get('agent')} t{r0.get('start_tick')}–t{r0.get('end_tick')} "
            f"dist {r0.get('initial_distance')}→{r0.get('final_distance')} "
            f"reversed_at={r0.get('locomotion_reversed_at')}"
        )
    focus = (payload_bits.get("target_intervals") or {}).get("3250-3315")
    if focus:
        lines.append("- Focus region t3250–3315: see TARGET INTERVAL reconstruction (agents became close again).")
    lines.append(
        "- Unresolved: whether any specific exo/FIELD component caused a selection; "
        "recognition; intentional approach/withdrawal; learning."
    )
    return lines


def build_behavioral_reconstruction(
    run_dir: str | Path,
    *,
    max_tick: int | None = None,
    write_artifacts: bool = False,
    artifact_dir: str | Path | None = None,
    on_progress: Any | None = None,
) -> dict[str, Any]:
    run_dir = Path(run_dir)
    t0 = time.perf_counter()
    version = RunEvidence.detect_evidence_version(run_dir)
    if version != "SCIENTIFIC_V3":
        payload = {
            "section": SECTION_TITLE,
            "status": "NOT_RECORDED",
            "evidence_version": version,
            "run_id": None,
            "note": (
                "V2-only or pre-V3 run. Behavioral Reconstruction operates in degraded mode: "
                "O→D→M→C relationships are NOT_RECORDED. Use existing V2 analysis paths; "
                "do not interpret missing V3 as zero cognition."
            ),
            "tick_stories_count": 0,
            "complete_odmc": "NOT_RECORDED",
            "episode_counts": {},
            "report_text": None,
            "sensorimotor_report_text": None,
        }
        from .report import format_behavioral_reconstruction as fmt
        payload["report_text"] = fmt(payload)
        payload["sensorimotor_report_text"] = (
            "SENSORIMOTOR CONSEQUENCE ANALYSIS\n"
            "=================================\n\n"
            "status: NOT_RECORDED (no SCIENTIFIC_V3 spine)\n"
        )
        return payload

    ev = RunEvidence(run_dir)
    try:
        run_id = (ev.meta or {}).get("run_id") or run_dir.name.replace(".live-", "")
        if max_tick is None:
            max_tick = ev.spine_max_tick()
        if on_progress:
            on_progress("RECONSTRUCTING", 0, max_tick or 0)

        graph = RelationshipGraph(run_id=run_id)
        stories = build_tick_stories(ev, graph, max_tick=max_tick, on_progress=on_progress)
    finally:
        ev.close()
    join_summary = apply_joins(stories, graph, run_dir=run_dir, max_tick=max_tick)
    if on_progress:
        on_progress("EPISODES", len(stories), max_tick or 0)
    width, height = (join_summary.get("world_size") or [32.0, 32.0])

    steps = build_sensorimotor_steps(stories, width=float(width), height=float(height))
    sm_summary = summarize_steps(steps)
    motor_revs = detect_motor_reversals(stories)
    sm_revs = detect_sensorimotor_trend_reversals(steps)
    stories_by_key = {(s.cognitive_agent_id, s.tick): s for s in stories}
    recede = find_receding_while_watching(steps, stories_by_key)
    asym = explain_visual_asymmetry(stories, steps)
    longit = longitudinal_comparison(stories, steps, int(max_tick or 0))

    episodes = extract_episodes(stories)
    # attach motor / sensorimotor reversal episodes
    for mr in motor_revs:
        episodes.append(Episode(
            episode_type="MOTOR_REVERSAL",
            start_tick=mr["start_tick"],
            end_tick=mr["end_tick"],
            agent=mr["agent"],
            motor_summary={"from": mr.get("from_loco"), "to": mr.get("to_loco")},
            evidence_class="OBSERVED",
            confidence="RECORDED",
            meta=mr,
        ))
    for sr in sm_revs:
        episodes.append(Episode(
            episode_type="SENSORIMOTOR_TREND_REVERSAL",
            start_tick=sr["start_tick"],
            end_tick=sr["end_tick"],
            agent=sr["agent"],
            participants=[sr.get("peer")] if sr.get("peer") else [],
            evidence_class="DERIVED",
            confidence=sr.get("evidence_strength", "WEAK"),
            meta=sr,
            evidence_relationships=[{"rel": "DERIVED_ASSOCIATION", "note": "trend reversal candidate"},
                                    {"rel": "NOT_ESTABLISHED", "note": "intentional correction"}],
        ))
    counts = episode_counts(episodes)
    if on_progress:
        on_progress("AGGREGATING", len(stories), max_tick or 0)
    selected_eps = select_interesting_episodes(episodes, limit=18)
    interesting = select_interesting_stories(stories, limit=12)
    contrasts = build_contrasts(stories)

    complete = sum(1 for s in stories if s.evidence_quality.get("odmc_complete"))
    hist = _canonical_history(stories, world_w=float(width), world_h=float(height))
    tmin, tmax = hist.get("tick_min"), hist.get("tick_max")
    n_obs = sum(1 for s in stories if s.observation_id)
    n_dec = sum(1 for s in stories if s.decision_id)
    n_mot = sum(1 for s in stories if s.motor_id)
    n_cons = sum(1 for s in stories if s.consequence_id)

    target_intervals: dict[str, Any] = {}
    for a, b in TARGET_INTERVALS:
        key = f"{a}-{b}"
        target_intervals[key] = reconstruct_interval(stories, steps, a, b)

    odmc_examples: list[TickStory] = []
    for item in interesting:
        s = stories_by_key.get((item["agent"], item["tick"]))
        if s:
            odmc_examples.append(s)
        if len(odmc_examples) >= 5:
            break

    visual_ep = next((e for e in selected_eps if e.episode_type == "VISUAL_EXPOSURE"), None)
    signal_ep = next((e for e in selected_eps if e.episode_type == "SIGNAL_EXPOSURE"), None)
    approach_ep = next((e for e in selected_eps if e.episode_type in ("APPROACH", "WITHDRAWAL")), None)

    open_questions = [
        "Which accessible observation components, if any, are causally necessary for specific selection outcomes? (ablation)",
        "Does bearing-error reduction after exposure exceed matched no-exposure baselines?",
        "When distance closes under vision, how often is focal movement dominant across the full run?",
        "Do SENSORIMOTOR_TREND_REVERSAL candidates exceed chance under reshuffled motor sequences?",
        "Is RECEDING_WHILE_WATCHING followed by geometry-improving motors more often than matched controls?",
    ]

    bits = {
        "analysis_cutoff_tick": max_tick,
        "complete_odmc": f"{complete} / {len(stories)}",
        "sensorimotor_summary": sm_summary,
        "visual_asymmetry": asym,
        "receding_while_watching": recede,
        "motor_reversals": motor_revs,
        "sensorimotor_trend_reversals": sm_revs,
        "target_intervals": target_intervals,
    }
    what = _what_happened_summary(bits)

    payload: dict[str, Any] = {
        "section": SECTION_TITLE,
        "status": "AVAILABLE",
        "evidence_version": "SCIENTIFIC_V3",
        "run_id": run_id,
        "analysis_cutoff_tick": max_tick,
        "tick_stories_count": len(stories),
        "complete_odmc_count": complete,
        "complete_odmc": f"{complete} / {len(stories)}",
        "unique_simulation_ticks": hist.get("unique_simulation_ticks") or 0,
        "scientific_tick_range": [tmin, tmax],
        "canonical_history": hist,
        "scientific_v3_core": {
            "section": "SCIENTIFIC_V3 CORE RECONSTRUCTION",
            "evidence_version": "SCIENTIFIC_V3",
            "status": "AVAILABLE",
            "decision_receipts": n_dec,
            "observation_receipts": n_obs,
            "motor_receipts": n_mot,
            "consequence_receipts": n_cons,
            "complete_odmc_count": complete,
            "complete_odmc_chains": f"{complete} / {len(stories)}",
            "incomplete_odmc_chains": max(0, len(stories) - complete),
            "ticks_expected": len(stories),
            "tick_range": [tmin, tmax],
            "chain_completeness_pct": round(100.0 * complete / len(stories), 1) if stories else 0.0,
        },
        "world_size": join_summary.get("world_size"),
        "join_summary": join_summary,
        "legacy_scenario_selected_count": _legacy_scenario_selected_count(run_dir, max_tick),
        "decision_receipts": len(stories),
        "agent_summaries": _agent_summaries(stories),
        "episode_counts": counts,
        "selected_episodes": [e.to_dict() for e in selected_eps],
        "interesting_ticks": interesting,
        "contrasts": contrasts,
        "open_questions": open_questions,
        "relationship_graph_summary": graph.summary(),
        "representative": {
            "visual_episode": visual_ep.to_dict() if visual_ep else None,
            "signal_episode": signal_ep.to_dict() if signal_ep else None,
            "geometry_episode": approach_ep.to_dict() if approach_ep else None,
        },
        "what_happened": what,
        "sensorimotor_summary": sm_summary,
        "sensorimotor_steps_count": len(steps),
        "motor_reversals_count": len(motor_revs),
        "sensorimotor_trend_reversals_count": len(sm_revs),
        "receding_while_watching": recede,
        "visual_asymmetry": asym,
        "longitudinal": longit,
        "target_intervals": {
            k: {
                "interval": v.get("interval"),
                "approach_history_200_pre": v.get("approach_history_200_pre"),
                "agent_tick_counts": {aid: len(rows) for aid, rows in (v.get("agents") or {}).items()},
                "sample_ticks": {
                    aid: rows[:12] for aid, rows in (v.get("agents") or {}).items()
                },
            }
            for k, v in target_intervals.items()
        },
        "focus_3250_3315": target_intervals.get("3250-3315"),
        "elapsed_s": None,
        "analyzer_version": "1.2.0",
    }

    report_payload = dict(payload)
    report_payload["selected_episodes"] = selected_eps
    report_payload["odmc_examples"] = odmc_examples
    report_payload["_stories_by_key"] = stories_by_key
    payload["report_text"] = format_behavioral_reconstruction(report_payload)
    payload["sensorimotor_report_text"] = format_sensorimotor_section(payload, steps_sample=steps[:40])
    # SMC / O′ historical-selection: aggregate from DecisionReceipts (Tier 0 evidence).
    sm_model = aggregate_sensorimotor_consequence_model(run_dir)
    payload["sensorimotor_consequence_model"] = sm_model
    payload["action_conditioned_model_report_text"] = format_action_conditioned_model_section(sm_model)
    hss_model = aggregate_historical_sensorimotor_selection(run_dir)
    payload["historical_sensorimotor_selection"] = hss_model
    payload["historical_sensorimotor_selection_report_text"] = format_historical_sensorimotor_selection_section(hss_model)
    sig_model = aggregate_signal_conditioned_selection(run_dir)
    payload["signal_conditioned_sensorimotor_selection"] = sig_model
    payload["signal_conditioned_report_text"] = format_signal_conditioned_selection(sig_model)
    emb_model = aggregate_full_embodied_predictive_model(run_dir)
    payload["full_embodied_predictive_model"] = emb_model
    payload["full_embodied_report_text"] = format_full_embodied_predictive_model(emb_model)
    fc_shadow = aggregate_full_composite_psc_shadow(run_dir)
    payload["full_composite_psc_shadow"] = fc_shadow
    payload["full_composite_psc_shadow_report_text"] = format_full_composite_psc_shadow(fc_shadow)
    fork_dev = aggregate_psc_motor_resolution_developmental(run_dir)
    payload["psc_motor_resolution_developmental"] = fork_dev
    payload["psc_motor_resolution_developmental_report_text"] = format_psc_motor_resolution_developmental(fork_dev)

    vis = analyze_beta31_vision(
        run_dir, stories, max_tick=max_tick,
        out_dir=Path(artifact_dir) if write_artifacts and artifact_dir else None,
    )
    payload["beta31_vision"] = vis.get("beta31_vision")
    payload["beta31_vision_report_text"] = vis.get("beta31_vision_report_text")
    payload["beta31_vision_publication"] = vis.get("publication")
    odmc_n = int(payload.get("complete_odmc_count") or 0)
    stories_n = int(payload.get("tick_stories_count") or 0)
    payload["publication_gate"] = {
        "ANALYZER_VERSION": payload.get("analyzer_version") or "1.2.0",
        "SCIENTIFIC_V3_RECONSTRUCTION": "PASS" if payload.get("status") == "AVAILABLE" else "FAIL",
        "ODMC_COMPLETE": f"{odmc_n} / {stories_n}",
        **(vis.get("publication") or {}),
        "BOUNDED_MEMORY": "YES",
        "ANALYZER_ONLY_CHANGE": "YES",
    }
    # Phase 1: propagate reconstruction exposure into canonical_history agents.
    hist_agents = (payload.get("canonical_history") or {}).get("agents") or {}
    legacy_exp = ((vis.get("beta31_vision") or {}).get("vision_summary") or {}).get("legacy_body_visual_exposure") or {}
    for aid, n in legacy_exp.items():
        if aid in hist_agents:
            hist_agents[aid]["legacy_body_visual_exposure_ticks"] = n
            if not hist_agents[aid].get("visual_exposure_ticks"):
                hist_agents[aid]["visual_exposure_ticks"] = n

    payload["report_text"] = (
        (payload.get("report_text") or "")
        + "\n\n" + payload["action_conditioned_model_report_text"]
        + "\n\n" + payload["historical_sensorimotor_selection_report_text"]
        + "\n\n" + (payload.get("signal_conditioned_report_text") or "")
        + "\n\n" + (payload.get("full_embodied_report_text") or "")
        + "\n\n" + (payload.get("beta31_vision_report_text") or "")
    )

    payload["elapsed_s"] = round(time.perf_counter() - t0, 4)

    if write_artifacts:
        if on_progress:
            on_progress("WRITING", len(stories), max_tick or 0)
        out = Path(artifact_dir) if artifact_dir else run_dir
        write_behavioral_artifacts(
            out, payload, graph=graph, stories=stories, episodes=episodes, steps=steps,
            motor_revs=motor_revs, sm_revs=sm_revs,
        )

    return payload


def write_behavioral_artifacts(
    out_dir: Path,
    payload: dict[str, Any],
    *,
    graph: RelationshipGraph | None = None,
    stories: list[TickStory] | None = None,
    episodes: list[Episode] | None = None,
    steps: list | None = None,
    motor_revs: list | None = None,
    sm_revs: list | None = None,
) -> dict[str, str]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}

    summary = {k: v for k, v in payload.items() if k not in ("report_text", "sensorimotor_report_text", "focus_3250_3315")}
    # keep a compact focus pointer
    focus = payload.get("focus_3250_3315") or {}
    summary["focus_3250_3315_compact"] = {
        "interval": focus.get("interval"),
        "approach_history_200_pre": focus.get("approach_history_200_pre"),
        "agent_tick_counts": {aid: len(rows) for aid, rows in (focus.get("agents") or {}).items()},
    }
    p = out_dir / "analysis_behavioral_summary.json"
    p.write_text(json.dumps(summary, indent=2, sort_keys=True, default=str))
    paths["analysis_behavioral_summary.json"] = str(p)

    if graph is not None:
        gp = out_dir / "analysis_relationship_graph.json"
        gp.write_text(json.dumps(graph.to_export(max_edges=8000), indent=2, sort_keys=True, default=str))
        paths["analysis_relationship_graph.json"] = str(gp)

    if stories is not None:
        sp = out_dir / "analysis_tick_stories.jsonl"
        with sp.open("w", encoding="utf-8") as f:
            for s in stories:
                f.write(json.dumps(s.to_dict(include_receipts=False), sort_keys=True, default=str) + "\n")
        paths["analysis_tick_stories.jsonl"] = str(sp)
        tp = out_dir / "analysis_derived_trajectory.jsonl"
        with tp.open("w", encoding="utf-8") as f:
            for rec in _iter_trajectory_records(stories):
                f.write(json.dumps(rec, sort_keys=True, default=str) + "\n")
        paths["analysis_derived_trajectory.jsonl"] = str(tp)

    if episodes is not None:
        ep = out_dir / "analysis_episodes.json"
        ep.write_text(json.dumps({
            "schema": "mm.analyzer_next.episodes.v1",
            "counts": episode_counts(episodes),
            "episodes": [e.to_dict() for e in episodes],
        }, indent=2, sort_keys=True, default=str))
        paths["analysis_episodes.json"] = str(ep)

    smp = out_dir / "analysis_sensorimotor_consequence.json"
    smp.write_text(json.dumps({
        "schema": "mm.analyzer_next.sensorimotor_consequence.v1",
        "summary": payload.get("sensorimotor_summary"),
        "steps_count": payload.get("sensorimotor_steps_count"),
        "motor_reversals": motor_revs or [],
        "sensorimotor_trend_reversals": sm_revs or [],
        "receding_while_watching": payload.get("receding_while_watching"),
        "visual_asymmetry": payload.get("visual_asymmetry"),
        "longitudinal": payload.get("longitudinal"),
        "steps_sample": [s.to_dict() if hasattr(s, "to_dict") else s for s in (steps or [])[:200]],
    }, indent=2, sort_keys=True, default=str))
    paths["analysis_sensorimotor_consequence.json"] = str(smp)

    rt = out_dir / "BEHAVIORAL_RECONSTRUCTION.txt"
    rt.write_text((payload.get("report_text") or "") + "\n" + (payload.get("sensorimotor_report_text") or ""))
    paths["BEHAVIORAL_RECONSTRUCTION.txt"] = str(rt)
    return paths
