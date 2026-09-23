"""Deterministic interestingness selection — no LLM."""
from __future__ import annotations

from typing import Any

from .episodes import Episode
from .tick_stories import TickStory


def story_interestingness(s: TickStory, *, first_flags: dict[str, bool]) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []
    # large observation change proxy: FIELD_A or exo variance not available tick-to-tick here; use absolute levels
    for c in s.observation_components:
        k = str(c.get("key") or "")
        try:
            v = abs(float(c.get("value") or 0))
        except (TypeError, ValueError):
            continue
        if k == "local.FIELD_A" and v > 0.05:
            score += 3.0 + min(v, 2.0)
            reasons.append("FIELD_A_elevated")
        if k.startswith("exo_") and v > 0.9:
            score += 1.0
            reasons.append("exo_high")

    if any(c.get("kind") == "CONTACT" for c in s.external_context):
        score += 8.0
        reasons.append("contact")
    if any(c.get("kind") == "SIGNAL_RECEPTION" for c in s.external_context):
        score += 2.5
        reasons.append("signal_rx")
    if any(c.get("kind") == "VISION_EXPOSURE" for c in s.external_context):
        score += 1.5
        reasons.append("vision")
        key = f"first_vision:{s.cognitive_agent_id}"
        if not first_flags.get(key):
            first_flags[key] = True
            score += 5.0
            reasons.append("first_vision")

    # motor rarity / composition
    comp = (s.motor or {}).get("components") or {}
    if comp.get("push"):
        score += 4.0
        reasons.append("push")
    neck = str(comp.get("neck") or "")
    if neck and neck.upper() not in ("NECK_HOLD", "HOLD", "NONE"):
        score += 2.0
        reasons.append("neck_control")
    osc = comp.get("oscillator") or {}
    if isinstance(osc, dict) and any(osc.values()):
        score += 3.0
        reasons.append("osc_emit")

    rd = (s.consequence or {}).get("resource_delta") or {}
    try:
        if abs(float(rd.get("A") or 0)) > 0.05 or abs(float(rd.get("B") or 0)) > 0.1:
            score += 3.0
            reasons.append("resource_delta")
    except (TypeError, ValueError):
        pass

    for d in s.derived_changes:
        if d.get("kind") != "RELATIVE_GEOMETRY":
            continue
        ap = d.get("approach") or {}
        dd = ap.get("delta_distance")
        if dd is not None and abs(float(dd)) > 0.15:
            score += 4.0 + min(abs(float(dd)), 2.0)
            reasons.append("strong_approach_or_withdrawal")
        ori = d.get("orienting") or {}
        if ori.get("abs_angular_error_deg") is not None and float(ori["abs_angular_error_deg"]) < 35:
            score += 2.0
            reasons.append("low_bearing_error")

    if not s.evidence_quality.get("odmc_complete"):
        score += 1.0
        reasons.append("broken_chain")

    return score, reasons


def select_interesting_stories(stories: list[TickStory], *, limit: int = 24) -> list[dict[str, Any]]:
    first_flags: dict[str, bool] = {}
    ranked: list[tuple[float, int, str, TickStory, list[str]]] = []
    for s in stories:
        score, reasons = story_interestingness(s, first_flags=first_flags)
        ranked.append((-score, s.tick, s.cognitive_agent_id, s, reasons))
    ranked.sort()
    out = []
    seen = set()
    for neg_score, tick, agent, s, reasons in ranked:
        key = (tick, agent)
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "tick": tick,
            "agent": agent,
            "score": -neg_score,
            "reasons": reasons,
            "story_ref": {
                "observation_id": s.observation_id,
                "decision_id": s.decision_id,
                "motor_id": s.motor_id,
                "consequence_id": s.consequence_id,
            },
            "composite_motor": s.composite_motor_summary,
            "decision_path": (s.decision or {}).get("selection_path"),
        })
        if len(out) >= limit:
            break
    return out


def select_interesting_episodes(episodes: list[Episode], *, limit: int = 20) -> list[Episode]:
    priority = {
        "CONTACT": 100,
        "APPROACH": 80,
        "WITHDRAWAL": 75,
        "SIGNAL_EXPOSURE": 70,
        "VISUAL_EXPOSURE": 65,
        "ORIENTING_CHANGE": 60,
        "RESOURCE_CHANGE": 55,
        "MOTOR_TRANSITION": 40,
        "SUSTAINED_LOCOMOTION": 30,
        "WAIT_PERIOD": 20,
    }
    ranked = sorted(
        episodes,
        key=lambda e: (
            -priority.get(e.episode_type, 0),
            -(e.end_tick - e.start_tick),
            e.start_tick,
            e.agent,
            e.episode_type,
        ),
    )
    # Prefer diversity: first of each type, then fill
    out: list[Episode] = []
    seen_types: set[str] = set()
    for e in ranked:
        if e.episode_type not in seen_types:
            out.append(e)
            seen_types.add(e.episode_type)
        if len(out) >= limit:
            return out
    # Fill remaining slots with diversity: at most 2 extras per type
    extras: dict[str, int] = {}
    for e in ranked:
        if e in out:
            continue
        if extras.get(e.episode_type, 0) >= 2:
            continue
        out.append(e)
        extras[e.episode_type] = extras.get(e.episode_type, 0) + 1
        if len(out) >= limit:
            break
    return out
