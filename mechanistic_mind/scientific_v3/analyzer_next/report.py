"""BEHAVIORAL RECONSTRUCTION report text — evidence-first, uncertainty at the edge."""
from __future__ import annotations

from typing import Any

from .episodes import Episode, episode_counts
from .tick_stories import TickStory, format_composite_motor


SECTION_TITLE = "BEHAVIORAL RECONSTRUCTION"

# Words that must not appear as established facts in OBSERVED blocks
_HYPOTHESIS_ONLY = (
    "recognized", "understood", "communicated", "wanted", "preferred",
    "feared", "searched", "sought", "intended", "believed", "knew",
)


def _fmt_num(x: Any, digits: int = 4) -> str:
    try:
        return f"{float(x):.{digits}f}"
    except (TypeError, ValueError):
        return str(x)


def format_episode_block(ep: Episode, stories_by_key: dict[tuple[str, int], TickStory]) -> list[str]:
    lines: list[str] = []
    lines.append(f"Episode t{ep.start_tick}–t{ep.end_tick} — {ep.agent} / {ep.body_id or '?'} — {ep.episode_type}")
    lines.append("")
    lines.append("OBSERVED")
    # Pull first/last story details when available
    s0 = stories_by_key.get((ep.agent, ep.start_tick))
    s1 = stories_by_key.get((ep.agent, ep.end_tick)) or s0
    if s0 and s0.decision:
        d = s0.decision
        lines.append(
            f"- DecisionReceipt selected continuation {d.get('selected_action_legacy')!r} "
            f"via selection_path={d.get('selection_path')} "
            f"(source={d.get('selection_source')}, mode={d.get('selection_mode')})"
        )
    if s0:
        lines.append(f"- MotorReceipt (COMPOSITE_MOTOR_V1): {s0.composite_motor_summary}")
    if s1 and s1.consequence:
        c = s1.consequence
        rd = c.get("resource_delta") or {}
        pd = c.get("pose_delta") or {}
        lines.append(
            f"- ConsequenceReceipt attribution={c.get('attribution')}: "
            f"Δpose dx={_fmt_num(pd.get('dx'), 5)} dy={_fmt_num(pd.get('dy'), 5)}; "
            f"ΔA={_fmt_num(rd.get('A'))} ΔB={_fmt_num(rd.get('B'))} Δwork={_fmt_num(rd.get('work'))}"
        )
    for bit in ep.observations_summary:
        lines.append(f"- {bit}")
    for ctx_kind in ("VISION_EXPOSURE", "SIGNAL_RECEPTION", "SIGNAL_EMISSION", "CONTACT"):
        if s0 and any(c.get("kind") == ctx_kind for c in s0.external_context):
            c = next(c for c in s0.external_context if c.get("kind") == ctx_kind)
            if ctx_kind == "VISION_EXPOSURE":
                lines.append(
                    f"- body-derived optical contribution present in Observer provenance; "
                    f"accessible exo keys: {', '.join(c.get('exo_components') or [])}"
                )
            elif ctx_kind == "SIGNAL_RECEPTION":
                lines.append(
                    f"- PHYSICAL_SIGNAL_RECEIVED; source_attribution={c.get('source_attribution')}; "
                    f"FIELD keys in observation: {', '.join(c.get('field_components') or [])}"
                )
            elif ctx_kind == "CONTACT":
                lines.append("- CONTACT event recorded this tick")
    if len(lines) == 3:
        lines.append("- (episode markers from composite motor / derived geometry; see DERIVED)")

    lines.append("")
    lines.append("DERIVED")
    derived_any = False
    if s0:
        for d in s0.derived_changes:
            if d.get("kind") != "RELATIVE_GEOMETRY":
                continue
            ap = d.get("approach") or {}
            ori = d.get("orienting") or {}
            if ap:
                lines.append(
                    f"- toroidal distance to {d.get('other_agent')} "
                    f"{_fmt_num(ap.get('distance_t'), 3)} → {_fmt_num(ap.get('distance_t1'), 3)} "
                    f"(Δ={_fmt_num(ap.get('delta_distance'), 3)})"
                )
                lines.append(
                    f"- distance change attribution: agent_contribution={_fmt_num(ap.get('agent_contribution'), 3)}, "
                    f"source_contribution={_fmt_num(ap.get('source_contribution'), 3)}, "
                    f"dominant_mover={ap.get('dominant_mover')}"
                )
                derived_any = True
            if ori and ep.episode_type in ("ORIENTING_CHANGE", "APPROACH", "VISUAL_EXPOSURE", "SIGNAL_EXPOSURE"):
                lines.append(
                    f"- source-bearing error |ε|={_fmt_num(ori.get('abs_angular_error_deg'), 1)}° "
                    f"(bearing={_fmt_num(ori.get('bearing_to_source_deg'), 1)}°, "
                    f"heading={_fmt_num(ori.get('heading_deg'), 1)}°)"
                )
                derived_any = True
    if ep.physical_outcome and ep.evidence_class == "DERIVED":
        lines.append(f"- outcome payload: {ep.physical_outcome}")
        derived_any = True
    if not derived_any:
        lines.append("- no additional geometry derived for this episode window")

    lines.append("")
    lines.append("NOT ESTABLISHED")
    lines.append("- whether any specific sensory component uniquely caused the selected continuation")
    lines.append("- recognition of another body")
    lines.append("- communicative interpretation of physical signals")
    if ep.episode_type in ("APPROACH", "WITHDRAWAL"):
        lines.append("- intentional approach/withdrawal (geometry change ≠ goal-directed seeking)")
    lines.append("")
    return lines


def format_odmc_example(s: TickStory) -> list[str]:
    lines = [f"Tick t{s.tick} — {s.cognitive_agent_id} / {s.physical_body_id}"]
    lines.append("OBSERVED")
    # observation components of interest
    for c in s.observation_components:
        k = c["key"]
        if k.startswith("local.FIELD_") or k.startswith("exo_") or k.startswith("prop_neck_") or k.startswith("vest_"):
            lines.append(f"- accessible {k}={_fmt_num(c.get('value'))}")
    if s.decision:
        d = s.decision
        lines.append(
            f"- DecisionReceipt: path={d.get('selection_path')} selected={d.get('selected_action_legacy')!r} "
            f"candidates={d.get('candidate_count')}"
        )
    lines.append(f"- MotorReceipt COMPOSITE: {s.composite_motor_summary}")
    if s.consequence:
        c = s.consequence
        lines.append(
            f"- ConsequenceReceipt {c.get('tick_from')}→{c.get('tick_to')} "
            f"attribution={c.get('attribution')} resources={c.get('resource_delta')}"
        )
    lines.append("CHAIN")
    lines.append(
        "  Observation → AVAILABLE_TO_AGENT / PART_OF_DECISION_CONTEXT → Decision → "
        "PRODUCED_MOTOR → Motor → PHYSICALLY_RESULTED_IN → Consequence"
    )
    lines.append("NOT ESTABLISHED")
    lines.append("  specific observation-component → decision causation")
    lines.append("")
    return lines


def format_behavioral_reconstruction(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(SECTION_TITLE)
    lines.append("=" * len(SECTION_TITLE))
    lines.append("")

    if payload.get("status") == "NOT_RECORDED":
        lines.append("Evidence basis: SCIENTIFIC_V3 CORE not present in this run.")
        lines.append("Mode: DEGRADED (V2-compatible). O→D→M→C links: NOT_RECORDED (not zero).")
        lines.append("No fabricated DecisionReceipt / MotorReceipt / ConsequenceReceipt chains.")
        lines.append("")
        note = payload.get("note")
        if note:
            lines.append(str(note))
            lines.append("")
        return "\n".join(lines)

    # Human-facing factual summary first
    what = payload.get("what_happened") or []
    if what:
        for line in what:
            lines.append(line)
        lines.append("")

    lines.append("Evidence basis")
    lines.append(f"  run_id: {payload.get('run_id')}")
    lines.append(f"  evidence_version: SCIENTIFIC_V3")
    lines.append(f"  analysis_cutoff_tick: {payload.get('analysis_cutoff_tick')}")
    lines.append(f"  TickStories reconstructed: {payload.get('tick_stories_count')}")
    lines.append(f"  complete O→D→M→C: {payload.get('complete_odmc')}")
    lines.append(f"  world_size (wrap): {payload.get('world_size')}")
    lines.append(f"  join summary: {payload.get('join_summary')}")
    lines.append("")
    lines.append("  Decision evidence authority: SCIENTIFIC_V3 DecisionReceipts")
    lines.append(
        f"  Legacy SCENARIO_SELECTED event rows: {payload.get('legacy_scenario_selected_count', 0)} "
        "(compatibility metric only — absence must not be read as missing cognition)"
    )
    lines.append(f"  DecisionReceipts in window: {payload.get('decision_receipts')}")
    lines.append("")

    lines.append("Agent summaries")
    for a in payload.get("agent_summaries") or []:
        lines.append(
            f"  {a['agent']} / {a.get('body')}: stories={a.get('n_stories')} "
            f"WAIT_p={a.get('wait_p')} top_motor={a.get('top_motor')} "
            f"selection_paths={a.get('selection_paths')}"
        )
    lines.append("")

    lines.append("Major episodes")
    counts = payload.get("episode_counts") or {}
    lines.append(f"  counts_by_type: {counts}")
    lines.append("")
    stories_by_key = payload.get("_stories_by_key") or {}
    for ep_d in payload.get("selected_episodes") or []:
        # ep_d may be dict
        if isinstance(ep_d, Episode):
            ep = ep_d
        else:
            ep = Episode(**{k: ep_d[k] for k in Episode.__dataclass_fields__ if k in ep_d})
        lines.extend(format_episode_block(ep, stories_by_key))

    lines.append("Cross-agent episodes")
    cross = [e for e in (payload.get("selected_episodes") or []) if (isinstance(e, dict) and e.get("participants")) or (isinstance(e, Episode) and e.participants)]
    if not cross:
        lines.append("  (none selected in top interesting set — see episode counts)")
    else:
        for e in cross[:8]:
            if isinstance(e, dict):
                lines.append(
                    f"  {e.get('episode_type')} t{e.get('start_tick')}–t{e.get('end_tick')} "
                    f"{e.get('agent')} participants={e.get('participants')}"
                )
            else:
                lines.append(
                    f"  {e.episode_type} t{e.start_tick}–t{e.end_tick} {e.agent} participants={e.participants}"
                )
    lines.append("")

    lines.append("Observation → decision → motor → consequence examples")
    for ex in payload.get("odmc_examples") or []:
        if isinstance(ex, TickStory):
            lines.extend(format_odmc_example(ex))
        elif isinstance(ex, dict) and "tick" in ex:
            lines.append(f"Tick t{ex['tick']} — {ex.get('agent')}")
            lines.append(f"  composite_motor: {ex.get('composite_motor')}")
            lines.append(f"  decision_path: {ex.get('decision_path')}")
            lines.append(f"  reasons: {ex.get('reasons')}")
            lines.append("")
    lines.append("")

    lines.append("Behavioral contrasts")
    for c in payload.get("contrasts") or []:
        lines.append(f"  [{c.get('layer')}] {c.get('name')}: {c.get('definition')}")
        pos = c.get("positive") or {}
        neg = c.get("negative") or {}
        lines.append(
            f"    positive n={pos.get('n_ticks')} WAIT_p={pos.get('wait_probability')} "
            f"| negative n={neg.get('n_ticks')} WAIT_p={neg.get('wait_probability')}"
        )
        lines.append(f"    note: {c.get('note')}")
    if not payload.get("contrasts"):
        lines.append("  (insufficient contrast partitions in this window)")
    lines.append("")

    lines.append("Open causal questions")
    for q in payload.get("open_questions") or []:
        lines.append(f"  - {q}")
    lines.append("")
    lines.append("Language boundary: recognition / communication / seeking / wanting appear only as HYPOTHESIS, never as OBSERVED facts.")
    lines.append("")
    return "\n".join(lines)


# late import for type in format — Episode already imported



def format_sensorimotor_section(payload: dict[str, Any], *, steps_sample: list | None = None) -> str:
    """SENSORIMOTOR CONSEQUENCE ANALYSIS section for Download Analysis Log."""
    lines: list[str] = []
    lines.append("SENSORIMOTOR CONSEQUENCE ANALYSIS")
    lines.append("=================================")
    lines.append("")
    lines.append("Operational question: after other-body sensory exposure and a motor that")
    lines.append("changes relative geometry / optical input, does the next decision/motor")
    lines.append("continue, reverse, or ignore that geometric trend?")
    lines.append("Labels are operational — not intent, seeking, recognition, or communication.")
    lines.append("")
    sm = payload.get("sensorimotor_summary") or {}
    g = sm.get("global") or {}
    lines.append("Global (ticks with VISUAL_EXPOSURE)")
    lines.append(f"  visual_steps: {g.get('visual_steps')}")
    lines.append(f"  trend_given_visual: {g.get('trend_given_visual')}")
    lines.append(f"  response_given_visual: {g.get('response_given_visual')}")
    lines.append(f"  after_distance_increase: {g.get('after_distance_increase')}")
    lines.append(f"  after_distance_decrease: {g.get('after_distance_decrease')}")
    lines.append("")
    lines.append("Per agent")
    for aid, st in sorted((sm.get("agents") or {}).items()):
        lines.append(f"  {aid}: {st}")
    lines.append("")
    lines.append(f"MOTOR_REVERSAL count: {payload.get('motor_reversals_count')}")
    lines.append(f"SENSORIMOTOR_TREND_REVERSAL candidates: {payload.get('sensorimotor_trend_reversals_count')}")
    lines.append("  (ASSOCIATED pattern; specific sensory causation NOT_ESTABLISHED)")
    lines.append("")
    lines.append("RECEDING_WHILE_WATCHING search")
    recede = payload.get("receding_while_watching") or []
    lines.append(f"  matched episodes: {len(recede)}")
    for r in recede[:8]:
        lines.append(
            f"  - {r.get('agent')} t{r.get('start_tick')}–t{r.get('end_tick')}: "
            f"dist {_fmt_num(r.get('initial_distance'),3)}→{_fmt_num(r.get('final_distance'),3)} "
            f"(Δ={_fmt_num(r.get('distance_delta'),3)}); "
            f"|ε| {_fmt_num(r.get('bearing_error_start_deg'),1)}→{_fmt_num(r.get('bearing_error_end_deg'),1)}; "
            f"optical {_fmt_num(r.get('optical_start'),4)}→{_fmt_num(r.get('optical_end'),4)}; "
            f"loco={r.get('loco_sequence')}; reversed_at={r.get('locomotion_reversed_at')}"
        )
        lines.append(f"    boundary: {r.get('interpretation_boundary')}")
    if not recede:
        lines.append("  No episode matched the operational definition in this window.")
    lines.append("")
    lines.append("Visual exposure asymmetry")
    asym = payload.get("visual_asymmetry") or {}
    for aid, v in sorted((asym.get("per_agent") or {}).items()):
        lines.append(f"  {aid}: {v}")
    for e in asym.get("candidate_explanations") or []:
        lines.append(f"  candidate: {e}")
    lines.append("")
    lines.append("Longitudinal (LONGITUDINAL_CHANGE — not labeled learning)")
    longit = payload.get("longitudinal") or {}
    for wname, w in (longit.get("windows") or {}).items():
        lines.append(f"  {wname} range={w.get('range')}")
        for aid, a in sorted((w.get("agents") or {}).items()):
            lines.append(
                f"    {aid}: vis={a.get('visual_exposure_ticks')} near_wait_p={a.get('wait_p')} "
                f"neck={a.get('neck_control_ticks')} reverse_resp={a.get('reverse_responses')} "
                f"mean_dist={a.get('mean_distance')} modes={a.get('decision_modes')}"
            )
    lines.append("")
    lines.append("TARGET INTERVAL — t3250–3315 (and approach history)")
    focus = payload.get("focus_3250_3315") or (payload.get("target_intervals") or {}).get("3250-3315") or {}
    pre = (focus.get("approach_history_200_pre") or {}).get("distance_trace_agent0_or_first") or []
    if pre:
        lines.append("  Distance trace (focal first agent) before interval (last points):")
        for tick, dist in pre[-15:]:
            lines.append(f"    t{tick}: dist={_fmt_num(dist, 3)}")
    agents = focus.get("agents") or {}
    for aid, rows in sorted(agents.items()):
        lines.append(f"  {aid} ticks in interval: {len(rows)}")
        for row in rows[:20]:
            lines.append(
                f"    t{row.get('tick')}: motor={row.get('motor')} dec={row.get('decision')} "
                f"dist={_fmt_num(row.get('distance'),3)} Δd={_fmt_num(row.get('distance_delta'),3)} "
                f"dom={row.get('dominant_mover')} |ε|={_fmt_num(row.get('bearing_error_deg'),1)} "
                f"vis={row.get('visual')} contact={row.get('contact')}"
            )
    lines.append("")
    lines.append("INTERPRETATION BOUNDARY")
    lines.append("  Observation→Decision spine: RECORDED (V3)")
    lines.append("  Sensory component available in observation: RECORDED when exo_*/FIELD_* present")
    lines.append("  Specific sensory component caused selection: NOT_ESTABLISHED")
    lines.append("  Recognition / communication / seeking / intentional correction: NOT_ESTABLISHED")
    lines.append("")
    return "\n".join(lines)


def format_action_conditioned_model_section(payload: dict[str, Any] | None) -> str:
    """ACTION-CONDITIONED SENSORIMOTOR MODEL — prediction availability, not preference."""
    try:
        from .sensorimotor_model_report import format_sensorimotor_model_section
        return format_sensorimotor_model_section(payload)
    except Exception as exc:  # noqa: BLE001 — analyzer must not crash report
        return (
            "ACTION-CONDITIONED SENSORIMOTOR MODEL\n"
            "====================================\n\n"
            f"status: ERROR ({exc})\n"
        )


def format_historical_sensorimotor_selection_section(payload: dict[str, Any] | None) -> str:
    try:
        from .historical_sensorimotor_selection_report import format_historical_sensorimotor_selection
        return format_historical_sensorimotor_selection(payload)
    except Exception as exc:  # noqa: BLE001
        return f"HISTORICAL SENSORIMOTOR SELECTION\nstatus: ERROR ({exc})\n"
