"""Matched no-signal / low-signal controls for SignalEpisodes."""
from __future__ import annotations

import math
from typing import Any

from mechanistic_mind.ui.psy_observer_web.signal_context.windows import window_summary


def _region(x: float | None, y: float | None, *, cell: int = 4) -> tuple[int, int] | None:
    if x is None or y is None:
        return None
    return (int(math.floor(float(x) / cell)), int(math.floor(float(y) / cell)))


def _fingerprint(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "region": _region(row.get("x"), row.get("y")),
        "action": row.get("action"),
        "action_source": row.get("action_source"),
        "contact": bool(row.get("contact")),
        "speed_bin": int(min(5, max(0, float(row.get("speed") or 0.0) * 10))),
        "work_bin": int(min(8, max(0, float(row.get("work") or 0.0)))),
    }


def _score(a: dict[str, Any], b: dict[str, Any]) -> int:
    """Higher = better match. Max ~6."""
    s = 0
    if a.get("region") is not None and a.get("region") == b.get("region"):
        s += 2
    if a.get("action") == b.get("action"):
        s += 1
    if a.get("action_source") == b.get("action_source"):
        s += 1
    if a.get("contact") == b.get("contact"):
        s += 1
    if a.get("speed_bin") == b.get("speed_bin"):
        s += 1
    return s


def find_matched_controls(
    episode: dict[str, Any],
    timeline_rows: list[dict[str, Any]],
    reception_ticks: set[tuple[str, int]],
    *,
    max_controls: int = 8,
    good_threshold: int = 4,
    partial_threshold: int = 3,
    exclude_radius: int = 30,
    low_signal_ok: bool = True,
) -> dict[str, Any]:
    """Find comparable receiver states without (or with low) signal exposure.

    Never silently accepts poor matches — quality class reported.
    """
    aid = str(episode["receiver_agent_id"])
    start = int(episode["start_tick"])
    end = int(episode["end_tick"])

    # Anchor = last PRE tick if available, else episode start
    agent_rows = [
        r for r in timeline_rows if str(r.get("agent_id")) == aid
    ]
    agent_rows.sort(key=lambda r: int(r.get("tick") or 0))
    by_tick = {int(r["tick"]): r for r in agent_rows if "tick" in r}

    anchor = by_tick.get(start - 1) or by_tick.get(start)
    if anchor is None:
        return {
            "match_quality": "NO_VALID_CONTROL",
            "controls": [],
            "n_candidates_scanned": 0,
            "reason": "No timeline anchor for receiver near episode.",
        }

    target_fp = _fingerprint(anchor)
    controls: list[dict[str, Any]] = []
    scanned = 0

    for r in agent_rows:
        t = int(r["tick"])
        scanned += 1
        # Exclude near the signal episode
        if abs(t - start) <= exclude_radius or abs(t - end) <= exclude_radius:
            continue
        if start - exclude_radius <= t <= end + exclude_radius:
            continue
        # Prefer ticks without reception
        has_recv = (aid, t) in reception_ticks
        if has_recv and not low_signal_ok:
            continue
        if has_recv:
            # still allow but mark as LOW_SIGNAL candidate only if we need density
            continue

        sc = _score(target_fp, _fingerprint(r))
        if sc < partial_threshold:
            continue
        # Build mini PRE/POST around control tick as if it were a 1-tick episode
        pre_rows = [by_tick[tt] for tt in range(t - 5, t) if tt in by_tick]
        post_rows = [by_tick[tt] for tt in range(t + 1, t + 21) if tt in by_tick]
        pre_s = window_summary(pre_rows)
        post_s = window_summary(post_rows)
        controls.append(
            {
                "control_tick": t,
                "match_score": sc,
                "quality": "GOOD_MATCH" if sc >= good_threshold else "PARTIAL_MATCH",
                "fingerprint": _fingerprint(r),
                "signal_exposure": "NO_SIGNAL_RECEPTION_AT_TICK",
                "outcomes": {
                    "action_changed": pre_s.get("action_last") != post_s.get("action_last")
                    and pre_s.get("action_last") is not None,
                    "selection_source_changed": pre_s.get("action_source_last")
                    != post_s.get("action_source_last")
                    and pre_s.get("action_source_last") is not None,
                    "pre_action": pre_s.get("action_last"),
                    "post_action": post_s.get("action_last"),
                    "pre_source": pre_s.get("action_source_last"),
                    "post_source": post_s.get("action_source_last"),
                },
            }
        )

    controls.sort(key=lambda c: (-int(c["match_score"]), int(c["control_tick"])))
    controls = controls[:max_controls]

    if not controls:
        quality = "NO_VALID_CONTROL"
    elif all(c["quality"] == "GOOD_MATCH" for c in controls):
        quality = "GOOD_MATCH"
    else:
        quality = "PARTIAL_MATCH"

    return {
        "match_quality": quality,
        "target_fingerprint": target_fp,
        "controls": controls,
        "n_candidates_scanned": scanned,
        "n_controls": len(controls),
        "honesty": {
            "poor_matches_not_silently_accepted": True,
            "signal_exposure_proxy": "absence of PHYSICAL_SIGNAL_RECEIVED at control tick",
            "note": "Field residual may still be present without RECEIVED event edge cases.",
        },
    }


def compare_episode_vs_controls(
    episode_delta: dict[str, Any],
    controls: dict[str, Any],
) -> dict[str, Any]:
    """Aggregate signal vs matched-control outcome rates."""
    d = episode_delta.get("DELTA") or {}
    ctrls = controls.get("controls") or []
    if not ctrls:
        return {
            "evidence": "NOT_ESTABLISHED",
            "reason": "NO_VALID_CONTROL",
            "signal_action_changed": d.get("action_changed"),
            "control_action_change_rate": None,
        }
    n = len(ctrls)
    act_rate = sum(1 for c in ctrls if c["outcomes"].get("action_changed")) / n
    src_rate = sum(1 for c in ctrls if c["outcomes"].get("selection_source_changed")) / n
    sig_act = bool(d.get("action_changed"))
    sig_src = bool(d.get("selection_source_changed"))

    # Conservative: matched association only if signal shows change AND controls rarely do
    evidence = "TEMPORALLY_ASSOCIATED"
    if controls.get("match_quality") in ("GOOD_MATCH", "PARTIAL_MATCH"):
        if sig_act and act_rate <= 0.35:
            evidence = "MATCHED_ASSOCIATION"
        elif sig_src and src_rate <= 0.35:
            evidence = "MATCHED_ASSOCIATION"
        elif not sig_act and not sig_src:
            evidence = "NOT_ESTABLISHED"

    return {
        "evidence": evidence,
        "match_quality": controls.get("match_quality"),
        "n_controls": n,
        "signal": {
            "action_changed": sig_act,
            "selection_source_changed": sig_src,
        },
        "controls": {
            "action_change_rate": act_rate,
            "selection_source_change_rate": src_rate,
        },
        "note": "MATCHED_ASSOCIATION ≠ causal link. Intervention required for INTERVENTION_SUPPORTED.",
    }
