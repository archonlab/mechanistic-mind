"""Within-run behavioral contrasts — labeled DERIVED_ASSOCIATION only."""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from .tick_stories import TickStory


def _loco_move(s: TickStory) -> bool:
    loco = ((s.motor or {}).get("components") or {}).get("locomotion")
    if loco is None:
        return False
    u = str(loco).upper()
    return u.startswith("MOVE") or u not in ("WAIT", "NONE", "")


def _has_ctx(s: TickStory, kind: str) -> bool:
    return any(c.get("kind") == kind for c in s.external_context)


def _freq(counter: Counter) -> dict[str, Any]:
    total = sum(counter.values()) or 1
    return {
        "counts": dict(counter.most_common()),
        "n": total,
        "frequencies": {k: round(v / total, 4) for k, v in counter.most_common()},
    }


def _bucket_stats(stories: list[TickStory]) -> dict[str, Any]:
    modes = Counter()
    paths = Counter()
    motors = Counter()
    wait = 0
    neck = Counter()
    for s in stories:
        dec = s.decision or {}
        modes[str(dec.get("selection_mode") or "UNKNOWN")] += 1
        paths[str(dec.get("selection_path") or "UNKNOWN")] += 1
        motors[str(s.composite_motor_summary or "?")] += 1
        if not _loco_move(s):
            wait += 1
        neck_c = ((s.motor or {}).get("components") or {}).get("neck")
        if neck_c:
            neck[str(neck_c)] += 1
    n = len(stories) or 1
    return {
        "n_ticks": len(stories),
        "wait_probability": round(wait / n, 4),
        "selection_modes": _freq(modes),
        "selection_paths": _freq(paths),
        "composite_motors_top": dict(Counter(motors).most_common(12)),
        "neck_controls": dict(neck.most_common(8)),
    }


def build_contrasts(stories: list[TickStory]) -> list[dict[str, Any]]:
    contrasts: list[dict[str, Any]] = []

    def contrast(name: str, pos: list[TickStory], neg: list[TickStory], definition: str) -> None:
        contrasts.append({
            "name": name,
            "layer": "DERIVED_ASSOCIATION",
            "definition": definition,
            "note": "Association only — not causation.",
            "positive": _bucket_stats(pos),
            "negative": _bucket_stats(neg),
        })

    by_agent: dict[str, list[TickStory]] = defaultdict(list)
    for s in stories:
        by_agent[s.cognitive_agent_id].append(s)

    vis_pos = [s for s in stories if _has_ctx(s, "VISION_EXPOSURE")]
    vis_neg = [s for s in stories if not _has_ctx(s, "VISION_EXPOSURE")]
    if vis_pos and vis_neg:
        contrast("visual_exposure_vs_none", vis_pos, vis_neg,
                 "Ticks with Observer body_exposure + accessible exo_* vs without")

    sig_pos = [s for s in stories if _has_ctx(s, "SIGNAL_RECEPTION")]
    sig_neg = [s for s in stories if not _has_ctx(s, "SIGNAL_RECEPTION")]
    if sig_pos and sig_neg:
        contrast("signal_present_vs_absent", sig_pos, sig_neg,
                 "Ticks with PHYSICAL_SIGNAL_RECEIVED joined to FIELD_* observation vs without")

    contact_pos = [s for s in stories if _has_ctx(s, "CONTACT")]
    contact_neg = [s for s in stories if not _has_ctx(s, "CONTACT")]
    if contact_pos and contact_neg:
        contrast("contact_vs_no_contact", contact_pos, contact_neg,
                 "Ticks with CONTACT event vs without")

    # Resource high vs low (median A)
    As = []
    for s in stories:
        for d in s.derived_changes:
            if d.get("kind") == "RESOURCE_STATE" and d.get("resource_A") is not None:
                As.append((s, float(d["resource_A"])))
                break
    if len(As) >= 10:
        As_sorted = sorted(As, key=lambda x: x[1])
        mid = len(As_sorted) // 2
        low = [x[0] for x in As_sorted[:mid]]
        high = [x[0] for x in As_sorted[mid:]]
        contrast("high_vs_low_resource_A", high, low,
                 "Ticks above vs below median timeline resource_A")

    agents = sorted(by_agent.keys())
    if len(agents) >= 2:
        contrast(
            f"{agents[0]}_vs_{agents[1]}",
            by_agent[agents[0]],
            by_agent[agents[1]],
            "Per-agent composite motor / decision-mode distributions",
        )

    # Before vs after first visual exposure per agent
    for agent, seq in by_agent.items():
        seq = sorted(seq, key=lambda x: x.tick)
        first_vis = next((s.tick for s in seq if _has_ctx(s, "VISION_EXPOSURE")), None)
        if first_vis is None:
            continue
        before = [s for s in seq if s.tick < first_vis]
        after = [s for s in seq if s.tick >= first_vis]
        if before and after:
            contrast(
                f"before_vs_after_first_visual_{agent}",
                after,
                before,
                f"Ticks before vs after first VISION_EXPOSURE for {agent}",
            )
            break  # one representative

    return contrasts
