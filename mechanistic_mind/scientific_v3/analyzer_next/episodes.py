"""Deterministic episode extraction over TickStory sequences."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

from .tick_stories import TickStory


EPISODE_TYPES = (
    "SUSTAINED_LOCOMOTION",
    "WAIT_PERIOD",
    "VISUAL_EXPOSURE",
    "SIGNAL_EXPOSURE",
    "CONTACT",
    "RESOURCE_CHANGE",
    "ORIENTING_CHANGE",
    "APPROACH",
    "WITHDRAWAL",
    "MOTOR_TRANSITION",
    "MOTOR_REVERSAL",
    "SENSORIMOTOR_TREND_REVERSAL",
)


@dataclass
class Episode:
    episode_type: str
    start_tick: int
    end_tick: int
    agent: str
    body_id: str | None = None
    participants: list[str] = field(default_factory=list)
    trigger_context: str | None = None
    initial_state: dict[str, Any] = field(default_factory=dict)
    observations_summary: list[str] = field(default_factory=list)
    decision_summary: dict[str, Any] = field(default_factory=dict)
    motor_summary: dict[str, Any] = field(default_factory=dict)
    physical_outcome: dict[str, Any] = field(default_factory=dict)
    evidence_relationships: list[dict[str, Any]] = field(default_factory=list)
    evidence_class: str = "OBSERVED"  # OBSERVED | DERIVED | MIXED
    confidence: str = "RECORDED"
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _loco(components: dict[str, Any] | None) -> str:
    if not components:
        return "WAIT"
    loco = components.get("locomotion")
    return str(loco or "WAIT")


def _is_move(loco: str) -> bool:
    s = loco.upper()
    return s.startswith("MOVE") or (s not in ("WAIT", "NONE", ""))


def extract_episodes(stories: list[TickStory], *, min_run: int = 3) -> list[Episode]:
    by_agent: dict[str, list[TickStory]] = {}
    for s in stories:
        by_agent.setdefault(s.cognitive_agent_id, []).append(s)
    for a in by_agent:
        by_agent[a].sort(key=lambda x: x.tick)

    episodes: list[Episode] = []

    for agent, seq in by_agent.items():
        # SUSTAINED_LOCOMOTION / WAIT_PERIOD
        i = 0
        while i < len(seq):
            loco = _loco((seq[i].motor or {}).get("components"))
            moving = _is_move(loco)
            j = i + 1
            while j < len(seq):
                loco_j = _loco((seq[j].motor or {}).get("components"))
                if _is_move(loco_j) != moving:
                    break
                if seq[j].tick != seq[j - 1].tick + 1:
                    break
                j += 1
            length = j - i
            if length >= min_run:
                et = "SUSTAINED_LOCOMOTION" if moving else "WAIT_PERIOD"
                episodes.append(Episode(
                    episode_type=et,
                    start_tick=seq[i].tick,
                    end_tick=seq[j - 1].tick,
                    agent=agent,
                    body_id=seq[i].physical_body_id,
                    motor_summary={"locomotion_mode": "MOVE" if moving else "WAIT", "ticks": length},
                    evidence_class="OBSERVED",
                    confidence="RECORDED",
                    trigger_context="Composite motor locomotion component run",
                ))
            i = j

        # MOTOR_TRANSITION
        for k in range(1, len(seq)):
            if seq[k].tick != seq[k - 1].tick + 1:
                continue
            a = seq[k - 1].composite_motor_summary
            b = seq[k].composite_motor_summary
            if a != b:
                episodes.append(Episode(
                    episode_type="MOTOR_TRANSITION",
                    start_tick=seq[k - 1].tick,
                    end_tick=seq[k].tick,
                    agent=agent,
                    body_id=seq[k].physical_body_id,
                    motor_summary={"from": a, "to": b},
                    evidence_class="OBSERVED",
                    confidence="RECORDED",
                ))

        # VISUAL_EXPOSURE / SIGNAL_EXPOSURE runs
        for kind, etype in (("VISION_EXPOSURE", "VISUAL_EXPOSURE"), ("SIGNAL_RECEPTION", "SIGNAL_EXPOSURE")):
            i = 0
            while i < len(seq):
                has = any(c.get("kind") == kind for c in seq[i].external_context)
                if not has:
                    i += 1
                    continue
                j = i + 1
                while j < len(seq) and seq[j].tick == seq[j - 1].tick + 1:
                    if not any(c.get("kind") == kind for c in seq[j].external_context):
                        break
                    j += 1
                first = seq[i]
                last = seq[j - 1]
                obs_bits = []
                if kind == "VISION_EXPOSURE":
                    exo = [c["key"] for c in first.observation_components if str(c.get("key","")).startswith("exo_")]
                    obs_bits.append(f"exo components present: {', '.join(exo) if exo else 'none'}")
                else:
                    fa = [c for c in first.observation_components if c.get("key") == "local.FIELD_A"]
                    if fa:
                        obs_bits.append(f"local.FIELD_A={fa[0].get('value')}")
                episodes.append(Episode(
                    episode_type=etype,
                    start_tick=first.tick,
                    end_tick=last.tick,
                    agent=agent,
                    body_id=first.physical_body_id,
                    observations_summary=obs_bits,
                    decision_summary={
                        "selection_path": (first.decision or {}).get("selection_path"),
                        "selected_legacy": (first.decision or {}).get("selected_action_legacy"),
                    },
                    motor_summary={"composite": first.composite_motor_summary},
                    physical_outcome={
                        "consequence_attribution": (last.consequence or {}).get("attribution"),
                        "resource_delta": (last.consequence or {}).get("resource_delta"),
                    },
                    evidence_relationships=[
                        {"rel": "PART_OF_DECISION_CONTEXT", "note": "O→D→M→C spine recorded"},
                        {"rel": "NOT_ESTABLISHED", "note": "specific sensory causation"},
                    ],
                    evidence_class="MIXED",
                    confidence="RECORDED_SPINE",
                    trigger_context=kind,
                ))
                i = j

        # CONTACT
        for s in seq:
            if any(c.get("kind") == "CONTACT" for c in s.external_context):
                episodes.append(Episode(
                    episode_type="CONTACT",
                    start_tick=s.tick,
                    end_tick=s.tick,
                    agent=agent,
                    body_id=s.physical_body_id,
                    evidence_class="OBSERVED",
                    confidence="RECORDED",
                    motor_summary={"composite": s.composite_motor_summary},
                ))

        # RESOURCE_CHANGE from consequence
        for s in seq:
            rd = (s.consequence or {}).get("resource_delta") or {}
            try:
                dA = abs(float(rd.get("A") or 0))
                dB = abs(float(rd.get("B") or 0))
                dW = abs(float(rd.get("work") or 0))
            except (TypeError, ValueError):
                continue
            if max(dA, dB, dW) >= 0.05:
                episodes.append(Episode(
                    episode_type="RESOURCE_CHANGE",
                    start_tick=s.tick,
                    end_tick=s.tick,
                    agent=agent,
                    body_id=s.physical_body_id,
                    physical_outcome={"resource_delta": rd},
                    evidence_class="OBSERVED",
                    confidence="RECORDED",
                    motor_summary={"composite": s.composite_motor_summary},
                ))

        # APPROACH / WITHDRAWAL / ORIENTING_CHANGE from derived geometry
        for s in seq:
            for d in s.derived_changes:
                if d.get("kind") != "RELATIVE_GEOMETRY":
                    continue
                ap = d.get("approach") or {}
                dd = ap.get("delta_distance")
                if dd is not None:
                    if dd < -0.05:
                        episodes.append(Episode(
                            episode_type="APPROACH",
                            start_tick=s.tick,
                            end_tick=s.tick + 1,
                            agent=agent,
                            body_id=s.physical_body_id,
                            participants=[d.get("other_agent")],
                            physical_outcome=ap,
                            evidence_class="DERIVED",
                            confidence="DERIVED_GEOMETRY",
                            trigger_context="Toroidal distance decreased; see movement decomposition",
                            meta={"note": "Never equate with intentional approach"},
                        ))
                    elif dd > 0.05:
                        episodes.append(Episode(
                            episode_type="WITHDRAWAL",
                            start_tick=s.tick,
                            end_tick=s.tick + 1,
                            agent=agent,
                            body_id=s.physical_body_id,
                            participants=[d.get("other_agent")],
                            physical_outcome=ap,
                            evidence_class="DERIVED",
                            confidence="DERIVED_GEOMETRY",
                        ))
                ori = d.get("orienting") or {}
                # Orienting change needs previous — mark single-tick snapshots as ORIENTING_CHANGE when error large and neck active
                neck = ((s.motor or {}).get("components") or {}).get("neck")
                if neck and str(neck).upper() not in ("NECK_HOLD", "HOLD", "NONE", "") and ori.get("abs_angular_error_deg") is not None:
                    episodes.append(Episode(
                        episode_type="ORIENTING_CHANGE",
                        start_tick=s.tick,
                        end_tick=s.tick,
                        agent=agent,
                        body_id=s.physical_body_id,
                        participants=[d.get("other_agent")],
                        motor_summary={"neck": neck, "composite": s.composite_motor_summary},
                        physical_outcome={"orienting": ori},
                        evidence_class="DERIVED",
                        confidence="DERIVED_TEMPORAL",
                        evidence_relationships=[
                            {"rel": "TEMPORALLY_FOLLOWED", "note": "Neck motor with measurable source-bearing error"},
                            {"rel": "NOT_ESTABLISHED", "note": "Not labeled as recognition or looking-at"},
                        ],
                    ))

    # Deterministic order
    episodes.sort(key=lambda e: (e.start_tick, e.agent, e.episode_type, e.end_tick))
    return episodes


def episode_counts(episodes: list[Episode]) -> dict[str, int]:
    out: dict[str, int] = {t: 0 for t in EPISODE_TYPES}
    for e in episodes:
        out[e.episode_type] = out.get(e.episode_type, 0) + 1
    return out
