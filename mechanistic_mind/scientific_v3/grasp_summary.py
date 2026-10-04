"""Machine-readable GRASP/RELEASE counts. Mechanical events only; no intention claims."""
from __future__ import annotations

from typing import Any

_HAND_KEYS = ("LEFT", "RIGHT", "manipulator_0")


def _empty_hand() -> dict[str, int]:
    return {
        "grasp_attempts": 0,
        "grasp_successes": 0,
        "out_of_reach_failures": 0,
        "occupied_failures": 0,
        "release_successes": 0,
        "release_empty": 0,
    }


def summarize_grasp_events(events: list[dict[str, Any]] | None) -> dict[str, Any]:
    counts = _empty_hand()
    by_hand = {k: _empty_hand() for k in _HAND_KEYS}
    simultaneous = 0
    ticks_holding = {0: 0, 1: 0, 2: 0}
    independent_releases = 0
    contention_occupied = 0
    displacement_by_hand: dict[str, int] = {k: 0 for k in _HAND_KEYS}

    def _bump(hand: str, field: str) -> None:
        counts[field] += 1
        if hand in by_hand:
            by_hand[hand][field] += 1
        else:
            by_hand["manipulator_0"][field] += 1

    by_tick_cmds: dict[int, set[str]] = {}
    for ev in events or []:
        kind = str(ev.get("type") or ev.get("event") or "")
        evid = ev.get("evidence") if isinstance(ev.get("evidence"), dict) else {}
        mid = str(evid.get("manipulator_id") or ev.get("manipulator_id") or "manipulator_0")
        tick = evid.get("tick")
        if tick is None:
            tick = ev.get("tick")
        try:
            tick_i = int(tick) if tick is not None else -1
        except (TypeError, ValueError):
            tick_i = -1
        cmd = str(evid.get("manipulator_action") or ev.get("manipulator_action") or "")
        if cmd in {"GRASP", "RELEASE"} and tick_i >= 0:
            by_tick_cmds.setdefault(tick_i, set()).add(f"{mid}:{cmd}")
        if kind == "GRASP_ATTEMPT":
            _bump(mid, "grasp_attempts")
        elif kind == "GRASP_SUCCEEDED":
            _bump(mid, "grasp_successes")
            _bump(mid, "grasp_attempts")
            displacement_by_hand[mid if mid in displacement_by_hand else "manipulator_0"] += 1
        elif kind == "GRASP_FAILED_OUT_OF_REACH":
            _bump(mid, "out_of_reach_failures")
            _bump(mid, "grasp_attempts")
        elif kind == "GRASP_FAILED_OCCUPIED":
            _bump(mid, "occupied_failures")
            _bump(mid, "grasp_attempts")
            contention_occupied += 1
        elif kind == "RELEASE_SUCCEEDED":
            _bump(mid, "release_successes")
            independent_releases += 1
        elif kind == "RELEASE_NO_OBJECT":
            _bump(mid, "release_empty")
        elif kind == "MANIPULATOR_OCCUPANCY":
            n = evid.get("n_held")
            try:
                ni = int(n)
            except (TypeError, ValueError):
                ni = int(float(evid.get("prop_grip_left") or 0) + float(evid.get("prop_grip_right") or 0))
            if ni <= 0:
                ticks_holding[0] += 1
            elif ni == 1:
                ticks_holding[1] += 1
            else:
                ticks_holding[2] += 1

    for cmds in by_tick_cmds.values():
        left_g = "LEFT:GRASP" in cmds or "LEFT:RELEASE" in cmds
        right_g = "RIGHT:GRASP" in cmds or "RIGHT:RELEASE" in cmds
        if left_g and right_g:
            simultaneous += 1

    counts["note"] = (
        "Counts are mechanical receipts. Not ingestion, recognition, or intention."
    )
    counts["by_hand"] = by_hand
    counts["simultaneous_bilateral_commands"] = simultaneous
    counts["ticks_holding_0"] = ticks_holding[0]
    counts["ticks_holding_1"] = ticks_holding[1]
    counts["ticks_holding_2"] = ticks_holding[2]
    counts["independent_releases"] = independent_releases
    counts["contention_occupied_outcomes"] = contention_occupied
    counts["object_displacement_by_manipulator"] = displacement_by_hand
    counts["legacy_single_grasp_compatible"] = True
    return counts


def summarize_pair_events(events: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Mechanical pair/contact summary. Not mixing, recipe, or intention."""
    bring = 0
    separate = 0
    closing_ticks = 0
    opening_ticks = 0
    begin = 0
    end = 0
    no_dual = 0
    work = 0.0
    min_surf = None
    apertures: list[float] = []
    episodes: list[int] = []
    open_tick = None
    agent_contact = 0
    for ev in events or []:
        kind = str(ev.get("type") or ev.get("event") or "")
        evid = ev.get("evidence") if isinstance(ev.get("evidence"), dict) else {}
        if kind in {"BODY_CONTACT", "AGENT_CONTACT", "PUSH_CONTACT"}:
            agent_contact += 1
        if kind == "HELD_OBJECT_CONTACT_BEGIN":
            begin += 1
            tick = evid.get("tick", ev.get("tick"))
            try:
                open_tick = int(tick)
            except (TypeError, ValueError):
                open_tick = None
        elif kind == "HELD_OBJECT_CONTACT_END":
            end += 1
            tick = evid.get("tick", ev.get("tick"))
            try:
                t1 = int(tick)
            except (TypeError, ValueError):
                t1 = None
            if open_tick is not None and t1 is not None:
                episodes.append(max(0, t1 - open_tick))
            open_tick = None
        cmd = str(evid.get("pair_command") or ev.get("pair_command") or "")
        if cmd == "BRING_TOGETHER":
            bring += 1
        elif cmd == "SEPARATE":
            separate += 1
        outcome = str(evid.get("outcome") or ev.get("outcome") or kind)
        if outcome == "PAIR_CLOSING":
            closing_ticks += 1
        elif outcome == "PAIR_OPENING":
            opening_ticks += 1
        elif outcome == "PAIR_NO_DUAL_OBJECTS":
            no_dual += 1
        try:
            wd = float(evid.get("work_debit") or ev.get("work_debit") or 0.0)
            work += wd
        except (TypeError, ValueError):
            pass
        sd = evid.get("surface_distance", evid.get("surface_distance_after"))
        try:
            if sd is not None:
                fv = float(sd)
                min_surf = fv if min_surf is None else min(min_surf, fv)
        except (TypeError, ValueError):
            pass
        ap = evid.get("aperture", evid.get("aperture_after"))
        try:
            if ap is not None:
                apertures.append(float(ap))
        except (TypeError, ValueError):
            pass
    return {
        "pair_bring_together_commands": bring,
        "pair_separate_commands": separate,
        "closing_ticks": closing_ticks,
        "opening_ticks": opening_ticks,
        "held_object_contact_begin": begin,
        "held_object_contact_end": end,
        "contact_episode_durations": episodes,
        "commands_without_dual_objects": no_dual,
        "minimum_surface_distance": min_surf,
        "aperture_trajectory": apertures,
        "pair_work_debit": work,
        "agent_body_contact_events": agent_contact,
        "mixing_claimed": False,
        "note": (
            "Held-object material contact is not agent-agent body contact "
            "and is not mixing or reaction."
        ),
        "legacy_compatible": True,
    }
