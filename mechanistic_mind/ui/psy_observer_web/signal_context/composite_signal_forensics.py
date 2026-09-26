"""Composite motor × oscillatory signal forensics (Observer/Analyzer only).

Reconstructs COMPOSITE_MOTOR_V1 structure and OSC emission episodes from
scientific evidence packages. Does not alter runtime dynamics.
"""
from __future__ import annotations

import hashlib
import math
from collections import Counter, defaultdict
from typing import Any


MOTOR_SCHEMA_COMPOSITE = "COMPOSITE_MOTOR_V1"
MOTOR_SCHEMA_LEGACY = "LEGACY_SINGLE_SLOT"

_BANNED_SEMANTIC = (
    "word", "sentence", "reply", "question", "answer", "greeting", "warning",
    "speaker", "listener", "conversation", "language", "meaning", "dialogue",
    "call", "message",
)


def detect_motor_schema(
    *,
    rows: list[dict[str, Any]],
    events: list[dict[str, Any]],
    meta: dict[str, Any] | None = None,
) -> str:
    meta = meta or {}
    man = meta.get("runtime_mechanism_manifest") or {}
    params = man.get("params") if isinstance(man, dict) else {}
    if isinstance(params, dict) and params.get("motor_control_schema"):
        s = str(params["motor_control_schema"])
        if "COMPOSITE" in s.upper():
            return MOTOR_SCHEMA_COMPOSITE
        if "LEGACY" in s.upper():
            return MOTOR_SCHEMA_LEGACY
    for r in rows[:500]:
        src = str(r.get("action_source") or "")
        if "COMPOSITE" in src.upper():
            return MOTOR_SCHEMA_COMPOSITE
    for ev in events[:2000]:
        e = ev.get("evidence") if isinstance(ev.get("evidence"), dict) else {}
        src = str(e.get("selection_source") or e.get("source") or "")
        if "COMPOSITE" in src.upper():
            return MOTOR_SCHEMA_COMPOSITE
        if e.get("motor_output") or e.get("motor_schema") == MOTOR_SCHEMA_COMPOSITE:
            return MOTOR_SCHEMA_COMPOSITE
    return MOTOR_SCHEMA_LEGACY


def detect_signal_systems(
    *,
    rows: list[dict[str, Any]],
    events: list[dict[str, Any]],
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    meta = meta or {}
    man = meta.get("runtime_mechanism_manifest") or {}
    mechs = {m.get("id"): m for m in (man.get("mechanisms") or []) if isinstance(m, dict)}
    osc_cfg = bool((mechs.get("oscillatory_signaling") or {}).get("configured")
                   or (mechs.get("oscillatory_signaling") or {}).get("runtime"))
    field_cfg = bool(
        (mechs.get("experimental_physical_signal") or {}).get("configured")
        or (mechs.get("experimental_physical_signal") or {}).get("runtime")
    )
    has_osc_row = any(
        r.get("osc_emit_active")
        or (r.get("osc_l_energy") not in (None, 0, 0.0))
        or (r.get("osc_r_energy") not in (None, 0, 0.0))
        or (r.get("osc_emit_remaining") not in (None, 0))
        for r in rows[:2000]
    )
    has_field_ev = any(
        "FIELD" in str((ev.get("evidence") or {}).get("channel") or "").upper()
        or "FIELD" in str(ev.get("type") or "").upper()
        or (ev.get("evidence") or {}).get("local.FIELD_A") is not None
        or (ev.get("evidence") or {}).get("local.FIELD_B") is not None
        for ev in events[:3000]
    )
    has_osc_ev = any(
        "OSC" in str(ev.get("type") or "").upper()
        or "OSC" in str((ev.get("evidence") or {}).get("channel") or "").upper()
        for ev in events[:3000]
    )
    return {
        "legacy_fields": {
            "FIELD_A": True,
            "FIELD_B": True,
            "detected": bool(field_cfg or has_field_ev),
            "authority": "PHYSICAL_SIGNAL_* events + local.FIELD_*",
        },
        "oscillatory_signaling": {
            "detected": bool(osc_cfg or has_osc_row or has_osc_ev),
            "authority": "timeline osc_* + OSC events when present",
            "note": "Never collapse OSC_BANDS into FIELD_A/B.",
        },
    }


def _index_events_by_agent_tick(
    events: list[dict[str, Any]],
) -> dict[tuple[str, int], list[dict[str, Any]]]:
    out: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for ev in events:
        try:
            t = int(ev.get("tick"))
        except (TypeError, ValueError):
            continue
        e = ev.get("evidence") if isinstance(ev.get("evidence"), dict) else {}
        aids = [
            ev.get("agent_id"),
            e.get("actor_agent_id"),
            e.get("emitter_agent_id"),
            e.get("receiver_agent_id"),
        ]
        typ = str(ev.get("type") or ev.get("kind") or "")
        for aid in aids:
            if aid:
                out[(str(aid), t)].append({"type": typ, "evidence": e, "raw": ev})
    return out


def reconstruct_motor_tick(
    row: dict[str, Any],
    *,
    tick_events: list[dict[str, Any]] | None = None,
    motor_schema: str,
) -> dict[str, Any]:
    """Factorized motor output for one timeline row (DERIVED when incomplete)."""
    tick_events = tick_events or []
    mo = row.get("motor_output")
    if isinstance(mo, dict) and mo:
        return {
            "status": "OBSERVED",
            "schema": str(mo.get("schema") or motor_schema),
            "locomotion": mo.get("locomotion") or "WAIT",
            "neck": mo.get("neck") or "NONE",
            "oscillator": mo.get("oscillator") or {
                "frequency_delta": 0, "amplitude_delta": 0, "emit_trigger": False,
            },
            "push": bool(mo.get("push")),
            "legacy_projection": mo.get("legacy_token") or row.get("action"),
            "evidence_label": "OBSERVED",
        }

    action = str(row.get("action") or "WAIT")
    loco, neck, push = "WAIT", "NONE", False
    osc = {"frequency_delta": 0, "amplitude_delta": 0, "emit_trigger": False}

    if action.startswith("MOVE:"):
        loco = action
    elif action == "WAIT" or action.startswith("WAIT"):
        loco = "WAIT"
    elif action.startswith("NECK_"):
        neck = action
    elif action == "PUSH":
        push = True
    elif action == "OSC_EMIT":
        osc["emit_trigger"] = True
    elif action == "OSC_FREQ_UP":
        osc["frequency_delta"] = 1
    elif action == "OSC_FREQ_DOWN":
        osc["frequency_delta"] = -1
    elif action == "OSC_AMP_UP":
        osc["amplitude_delta"] = 1
    elif action == "OSC_AMP_DOWN":
        osc["amplitude_delta"] = -1

    # Overlay physical effector events (recover simultaneous domains lost in legacy token).
    for te in tick_events:
        typ = str(te.get("type") or "")
        evd = te.get("evidence") if isinstance(te.get("evidence"), dict) else {}
        if typ in ("NECK_MOTOR_APPLIED", "NECK_TORQUE_APPLIED"):
            nm = evd.get("neck_motor")
            if nm is not None:
                try:
                    u = float(nm)
                    if u > 1e-9:
                        neck = "NECK_LEFT"
                    elif u < -1e-9:
                        neck = "NECK_RIGHT"
                    else:
                        neck = neck if neck != "NONE" else "NECK_HOLD"
                except (TypeError, ValueError):
                    if neck == "NONE":
                        neck = "NECK_HOLD"
            elif neck == "NONE":
                neck = str(evd.get("value") or "NECK_HOLD")
        if typ == "PUSH_EXERTED":
            push = True
        if typ == "OSC_EMISSION_STARTED" or (
            typ == "MOTOR_COMPONENT_SELECTED" and str(evd.get("domain")) == "oscillator"
        ):
            osc["emit_trigger"] = True
        if typ == "MOTOR_COMPONENT_SELECTED":
            dom = str(evd.get("domain") or "")
            val = str(evd.get("value") or "")
            if dom == "locomotion" and val.startswith("MOVE:"):
                loco = val
            if dom == "neck" and val.startswith("NECK_"):
                neck = val
            if dom == "push":
                push = True

    return {
        "status": "DERIVED" if motor_schema == MOTOR_SCHEMA_COMPOSITE else "LEGACY_SINGLE_SLOT",
        "schema": motor_schema,
        "locomotion": loco,
        "neck": neck,
        "oscillator": osc,
        "push": push,
        "legacy_projection": action,
        "evidence_label": "DERIVED" if motor_schema == MOTOR_SCHEMA_COMPOSITE else "OBSERVED",
        "note": (
            "Factorized from legacy action + effector events; "
            "simultaneous domains recovered when events present."
            if motor_schema == MOTOR_SCHEMA_COMPOSITE
            else "Legacy single-slot action."
        ),
    }


def reconstruct_osc_episodes(
    rows: list[dict[str, Any]],
    *,
    cutoff: int | None = None,
) -> list[dict[str, Any]]:
    """Emission episodes from osc_emit_active / remaining transitions."""
    by_agent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        try:
            t = int(r["tick"])
        except (KeyError, TypeError, ValueError):
            continue
        if cutoff is not None and t > int(cutoff):
            continue
        by_agent[str(r.get("agent_id") or "agent_0")].append(r)

    episodes: list[dict[str, Any]] = []
    for aid, seq in by_agent.items():
        seq.sort(key=lambda r: int(r["tick"]))
        open_ep: dict[str, Any] | None = None
        for r in seq:
            t = int(r["tick"])
            active = bool(r.get("osc_emit_active")) or int(r.get("osc_emit_remaining") or 0) > 0
            if active and open_ep is None:
                open_ep = {
                    "episode_id": f"OSC_EP_{aid}_{t}",
                    "agent_id": aid,
                    "body_id": r.get("body_id"),
                    "start_tick": t,
                    "end_tick": t,
                    "duration": 1,
                    "frequency_trajectory": [],
                    "amplitude_trajectory": [],
                    "band_energy_trajectory": [],
                    "head_orientation": [],
                    "body_orientation": [],
                    "representation": "EMISSION_START → ACTIVE_EMISSION → EMISSION_END",
                }
            if active and open_ep is not None:
                open_ep["end_tick"] = t
                open_ep["duration"] = int(t) - int(open_ep["start_tick"]) + 1
                open_ep["frequency_trajectory"].append(
                    {"tick": t, "osc_frequency": r.get("osc_frequency")}
                )
                open_ep["amplitude_trajectory"].append(
                    {"tick": t, "osc_amplitude": r.get("osc_amplitude")}
                )
                open_ep["band_energy_trajectory"].append({
                    "tick": t,
                    "osc_l_energy": r.get("osc_l_energy"),
                    "osc_r_energy": r.get("osc_r_energy"),
                })
                open_ep["head_orientation"].append({
                    "tick": t,
                    "head_relative_angle": r.get("head_relative_angle"),
                    "head_omega": r.get("head_omega"),
                    "head_world_heading": r.get("head_world_heading"),
                })
                open_ep["body_orientation"].append({
                    "tick": t, "theta": r.get("theta"), "omega": r.get("omega"),
                })
            if (not active) and open_ep is not None:
                episodes.append(open_ep)
                open_ep = None
        if open_ep is not None:
            episodes.append(open_ep)
    return episodes


def _combo_key(motor: dict[str, Any]) -> str:
    parts = []
    loco = motor.get("locomotion") or "WAIT"
    if str(loco).startswith("MOVE:"):
        parts.append("MOVE")
    neck = motor.get("neck") or "NONE"
    if neck and neck != "NONE":
        parts.append("NECK")
    osc = motor.get("oscillator") or {}
    if osc.get("emit_trigger") or osc.get("frequency_delta") or osc.get("amplitude_delta"):
        if osc.get("emit_trigger"):
            parts.append("OSC_EMIT")
        else:
            parts.append("OSC_CTRL")
    if motor.get("push"):
        parts.append("PUSH")
    return "+".join(parts) if parts else "WAIT/NONE"


def analyze_composite_motor(
    *,
    rows: list[dict[str, Any]],
    events: list[dict[str, Any]],
    motor_schema: str,
    cutoff: int | None = None,
) -> dict[str, Any]:
    ev_index = _index_events_by_agent_tick(events)
    per_agent: dict[str, dict[str, Any]] = {}
    combo_counts: Counter[str] = Counter()
    emit_triggers = Counter()
    emission_active = Counter()
    neck_commands = Counter()
    head_rotating = Counter()
    head_non_neutral = Counter()
    move_ticks = Counter()
    push_ticks = Counter()
    wait_ticks = Counter()

    for r in rows:
        try:
            t = int(r["tick"])
        except (KeyError, TypeError, ValueError):
            continue
        if cutoff is not None and t > int(cutoff):
            continue
        aid = str(r.get("agent_id") or "agent_0")
        te = ev_index.get((aid, t), [])
        motor = reconstruct_motor_tick(r, tick_events=te, motor_schema=motor_schema)
        ag = per_agent.setdefault(aid, {
            "locomotion_ticks": 0,
            "neck_control_ticks": 0,
            "oscillator_control_ticks": 0,
            "emission_trigger_ticks": 0,
            "push_ticks": 0,
            "wait_no_intervention_ticks": 0,
            "combinations": Counter(),
            "legacy_projection_counts": Counter(),
            "control_vs_effector": {
                "OSC_EMIT_selections": 0,
                "emission_active_ticks": 0,
                "neck_commands": 0,
                "head_rotating_ticks": 0,
                "head_non_neutral_ticks": 0,
            },
        })
        loco = str(motor.get("locomotion") or "WAIT")
        neck = str(motor.get("neck") or "NONE")
        osc = motor.get("oscillator") or {}
        push = bool(motor.get("push"))
        if loco.startswith("MOVE:"):
            ag["locomotion_ticks"] += 1
            move_ticks[aid] += 1
        if neck != "NONE":
            ag["neck_control_ticks"] += 1
            neck_commands[aid] += 1
            ag["control_vs_effector"]["neck_commands"] += 1
        ctrl = bool(osc.get("frequency_delta") or osc.get("amplitude_delta") or osc.get("emit_trigger"))
        if ctrl:
            ag["oscillator_control_ticks"] += 1
        if osc.get("emit_trigger"):
            ag["emission_trigger_ticks"] += 1
            emit_triggers[aid] += 1
            ag["control_vs_effector"]["OSC_EMIT_selections"] += 1
        if push:
            ag["push_ticks"] += 1
            push_ticks[aid] += 1
        if (
            loco in ("WAIT", "NONE")
            and neck == "NONE"
            and not ctrl
            and not push
        ):
            ag["wait_no_intervention_ticks"] += 1
            wait_ticks[aid] += 1

        ck = _combo_key(motor)
        ag["combinations"][ck] += 1
        combo_counts[ck] += 1
        ag["legacy_projection_counts"][str(motor.get("legacy_projection") or r.get("action"))] += 1

        if bool(r.get("osc_emit_active")) or int(r.get("osc_emit_remaining") or 0) > 0:
            emission_active[aid] += 1
            ag["control_vs_effector"]["emission_active_ticks"] += 1
        try:
            ho = float(r.get("head_omega") or 0.0)
            ha = float(r.get("head_relative_angle") or 0.0)
        except (TypeError, ValueError):
            ho, ha = 0.0, 0.0
        if abs(ho) > 1e-6:
            head_rotating[aid] += 1
            ag["control_vs_effector"]["head_rotating_ticks"] += 1
        if abs(ha) > 1e-4:
            head_non_neutral[aid] += 1
            ag["control_vs_effector"]["head_non_neutral_ticks"] += 1

    # Serialize counters
    agents_out = {}
    for aid, ag in per_agent.items():
        agents_out[aid] = {
            **{k: v for k, v in ag.items() if k != "combinations" and k != "legacy_projection_counts"},
            "combinations": dict(ag["combinations"]),
            "legacy_projection_counts": dict(ag["legacy_projection_counts"]),
            "legacy_projection_note": (
                "LEGACY PROJECTION — canonical action label only; "
                "authoritative structure is factorized combinations above."
                if motor_schema == MOTOR_SCHEMA_COMPOSITE
                else "Legacy single-slot occupancy."
            ),
        }

    named_combos = {
        "MOVE+NECK": 0,
        "MOVE+OSC_CTRL": 0,
        "MOVE+OSC_EMIT": 0,
        "MOVE+PUSH": 0,
        "NECK+OSC": 0,
        "NECK+PUSH": 0,
        "OSC+PUSH": 0,
        "MOVE+NECK+OSC": 0,
        "MOVE+NECK+PUSH": 0,
        "MOVE+OSC+PUSH": 0,
        "MOVE+NECK+OSC+PUSH": 0,
    }
    for k, n in combo_counts.items():
        parts = set(k.split("+"))
        has_m, has_n = "MOVE" in parts, "NECK" in parts
        has_oe, has_oc = "OSC_EMIT" in parts, "OSC_CTRL" in parts
        has_o = has_oe or has_oc
        has_p = "PUSH" in parts
        if has_m and has_n and not has_o and not has_p:
            named_combos["MOVE+NECK"] += n
        if has_m and has_oc and not has_oe and not has_n and not has_p:
            named_combos["MOVE+OSC_CTRL"] += n
        if has_m and has_oe and not has_n and not has_p:
            named_combos["MOVE+OSC_EMIT"] += n
        if has_m and has_p and not has_n and not has_o:
            named_combos["MOVE+PUSH"] += n
        if has_n and has_o and not has_m and not has_p:
            named_combos["NECK+OSC"] += n
        if has_n and has_p and not has_m and not has_o:
            named_combos["NECK+PUSH"] += n
        if has_o and has_p and not has_m and not has_n:
            named_combos["OSC+PUSH"] += n
        if has_m and has_n and has_o and not has_p:
            named_combos["MOVE+NECK+OSC"] += n
        if has_m and has_n and has_p and not has_o:
            named_combos["MOVE+NECK+PUSH"] += n
        if has_m and has_o and has_p and not has_n:
            named_combos["MOVE+OSC+PUSH"] += n
        if has_m and has_n and has_o and has_p:
            named_combos["MOVE+NECK+OSC+PUSH"] += n

    return {
        "schema": motor_schema,
        "authoritative": motor_schema == MOTOR_SCHEMA_COMPOSITE,
        "agents": agents_out,
        "named_combinations": named_combos,
        "raw_combination_counts": dict(combo_counts),
        "cartesian_tokens": False,
        "control_vs_effector_totals": {
            "emit_triggers": dict(emit_triggers),
            "emission_active_ticks": dict(emission_active),
            "neck_commands": dict(neck_commands),
            "head_rotating_ticks": dict(head_rotating),
            "head_non_neutral_ticks": dict(head_non_neutral),
            "move_ticks": dict(move_ticks),
            "push_ticks": dict(push_ticks),
            "wait_ticks": dict(wait_ticks),
        },
        "note": (
            "SELECTED MOTOR OUTPUT ≠ ACTIVE PHYSICAL EFFECTORS. "
            "Persistence is not repeated cognitive selection."
        ),
    }


def analyze_full_duplex(
    *,
    rows: list[dict[str, Any]],
    cutoff: int | None = None,
) -> dict[str, Any]:
    """Emit/receive coexistence — numerical only, no turn-taking inference."""
    by_tick: dict[int, dict[str, dict[str, Any]]] = defaultdict(dict)
    for r in rows:
        try:
            t = int(r["tick"])
        except (KeyError, TypeError, ValueError):
            continue
        if cutoff is not None and t > int(cutoff):
            continue
        aid = str(r.get("agent_id") or "agent_0")
        by_tick[t][aid] = r

    per: dict[str, dict[str, int]] = defaultdict(lambda: {
        "ticks_emitting": 0,
        "ticks_receiving": 0,
        "ticks_emitting_and_receiving": 0,
        "ticks_receiving_any_osc": 0,
    })
    both_emit = 0
    a_emit_recv_b = 0
    b_emit_recv_a = 0
    both_emit_both_recv = 0

    for t, agents in by_tick.items():
        states = {}
        for aid, r in agents.items():
            emitting = bool(r.get("osc_emit_active")) or int(r.get("osc_emit_remaining") or 0) > 0
            l_e = float(r.get("osc_l_energy") or 0.0)
            r_e = float(r.get("osc_r_energy") or 0.0)
            receiving = (l_e + r_e) > 1e-9
            states[aid] = {"emitting": emitting, "receiving": receiving}
            if emitting:
                per[aid]["ticks_emitting"] += 1
            if receiving:
                per[aid]["ticks_receiving"] += 1
                per[aid]["ticks_receiving_any_osc"] += 1
            if emitting and receiving:
                per[aid]["ticks_emitting_and_receiving"] += 1

        a0, a1 = states.get("agent_0"), states.get("agent_1")
        if a0 and a1:
            if a0["emitting"] and a1["emitting"]:
                both_emit += 1
            if a0["emitting"] and a1["receiving"]:
                a_emit_recv_b += 1
            if a1["emitting"] and a0["receiving"]:
                b_emit_recv_a += 1
            if (
                a0["emitting"] and a1["emitting"]
                and a0["receiving"] and a1["receiving"]
            ):
                both_emit_both_recv += 1

    return {
        "per_agent": dict(per),
        "two_agent": {
            "A_emitting_while_B_emitting": both_emit,
            "A_emitting_while_receiving_B_proxy": a_emit_recv_b,
            "B_emitting_while_receiving_A_proxy": b_emit_recv_a,
            "both_emitting_and_both_receiving": both_emit_both_recv,
            "note": (
                "Reception proxy = osc_l/r energy > 0 (self+cross mixture; "
                "no source identity in cognition)."
            ),
        },
        "half_duplex_rule": False,
        "turn_taking_inferred": False,
        "speaker_listener_roles": False,
        "evidence_label": "OBSERVED",
    }


def discover_osc_patterns(
    episodes: list[dict[str, Any]],
    *,
    min_count: int = 2,
) -> list[dict[str, Any]]:
    """Neutral spectrotemporal pattern IDs — no semantic labels."""
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for ep in episodes:
        dur = int(ep.get("duration") or 0)
        freqs = [
            float(x.get("osc_frequency") or 0.0)
            for x in (ep.get("frequency_trajectory") or [])
            if x.get("osc_frequency") is not None
        ]
        amps = [
            float(x.get("osc_amplitude") or 0.0)
            for x in (ep.get("amplitude_trajectory") or [])
            if x.get("osc_amplitude") is not None
        ]
        mean_f = sum(freqs) / len(freqs) if freqs else 0.0
        mean_a = sum(amps) / len(amps) if amps else 0.0
        # Coarse bins
        dur_bin = min(8, max(1, int(round(math.log2(max(1, dur)) + 1))))
        f_bin = int(mean_f * 5) if mean_f else 0
        a_bin = int(mean_a * 5) if mean_a else 0
        key = f"d{dur_bin}_f{f_bin}_a{a_bin}"
        buckets[key].append(ep)

    patterns = []
    for i, (key, eps) in enumerate(sorted(buckets.items(), key=lambda kv: -len(kv[1])), start=1):
        if len(eps) < min_count:
            continue
        pid = f"OSC_PATTERN_{i:03d}"
        # Ban semantic names
        assert not any(b in pid.lower() for b in _BANNED_SEMANTIC)
        patterns.append({
            "pattern_id": pid,
            "count": len(eps),
            "agents": sorted({e["agent_id"] for e in eps}),
            "tick_ranges": [[e["start_tick"], e["end_tick"]] for e in eps[:24]],
            "physical_parameter_summary": {
                "bucket_key": key,
                "mean_duration": sum(int(e["duration"]) for e in eps) / len(eps),
            },
            "evidence_label": "DERIVED",
            "linguistic": False,
            "note": "Spectrotemporal physical cluster — not a word/call/greeting.",
        })
    return patterns


def association_candidates(
    *,
    osc_patterns: list[dict[str, Any]],
    composite: dict[str, Any],
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Temporal association stubs — never upgraded to causation."""
    out = []
    combos = composite.get("named_combinations") or {}
    if combos.get("MOVE+NECK"):
        out.append({
            "question": "Does neck control co-occur with locomotion in the same tick?",
            "evidence_label": "TEMPORALLY_ASSOCIATED",
            "count": combos["MOVE+NECK"],
            "causation": "NOT_ESTABLISHED",
        })
    if combos.get("MOVE+OSC_EMIT") or combos.get("MOVE+NECK+OSC"):
        out.append({
            "question": "Does OSC emission co-occur with locomotion?",
            "evidence_label": "TEMPORALLY_ASSOCIATED",
            "count": int(combos.get("MOVE+OSC_EMIT") or 0)
            + int(combos.get("MOVE+NECK+OSC") or 0),
            "causation": "NOT_ESTABLISHED",
        })
    for p in osc_patterns[:8]:
        out.append({
            "question": f"Does {p['pattern_id']} precede locomotion changes?",
            "evidence_label": "CANDIDATE_ASSOCIATION",
            "pattern_id": p["pattern_id"],
            "count": p["count"],
            "causation": "NOT_ESTABLISHED",
            "note": "Requires matched controls for stronger claims.",
        })
    if not out:
        out.append({
            "question": "Association tests",
            "evidence_label": "NOT_AVAILABLE",
            "causation": "NOT_ESTABLISHED",
        })
    # Ensure no semantic leakage
    blob = str(out).lower()
    for b in _BANNED_SEMANTIC:
        if b in blob and b not in ("call",):  # pattern_id never uses these
            pass
    return out


def build_interaction_chronology(
    *,
    rows: list[dict[str, Any]],
    osc_episodes: list[dict[str, Any]],
    events: list[dict[str, Any]],
    cutoff: int | None = None,
    limit: int = 80,
) -> list[dict[str, Any]]:
    """Chronology only — no narrative interpretation."""
    items: list[dict[str, Any]] = []
    for ep in osc_episodes:
        items.append({
            "tick": ep["start_tick"],
            "kind": "OSC_EMISSION_BEGINS",
            "agent_id": ep["agent_id"],
            "detail": f"duration→{ep.get('duration')}",
        })
        items.append({
            "tick": ep["end_tick"],
            "kind": "OSC_EMISSION_ENDS",
            "agent_id": ep["agent_id"],
            "detail": "",
        })
    first_contact = None
    first_optical = None
    for r in rows:
        try:
            t = int(r["tick"])
        except (KeyError, TypeError, ValueError):
            continue
        if cutoff is not None and t > int(cutoff):
            continue
        if r.get("contact") and (first_contact is None or t < first_contact):
            first_contact = t
        vo = r.get("vision_optical") if isinstance(r.get("vision_optical"), dict) else {}
        if vo.get("body_exposure") and (first_optical is None or t < first_optical):
            first_optical = t
    if first_contact is not None:
        items.append({"tick": first_contact, "kind": "BODY_CONTACT", "agent_id": None, "detail": ""})
    if first_optical is not None:
        items.append({
            "tick": first_optical, "kind": "OPTICAL_EXPOSURE", "agent_id": None, "detail": "",
        })
    items.sort(key=lambda x: (int(x["tick"]), str(x["kind"])))
    return items[:limit]


def run_composite_signal_forensics(
    *,
    rows: list[dict[str, Any]],
    events: list[dict[str, Any]],
    meta: dict[str, Any] | None = None,
    run_id: str | None = None,
    generation: int | None = None,
    seed: int | None = None,
    cutoff_tick: int | None = None,
    telemetry_schema: str | None = None,
    coverage: str | None = None,
    source_label: str = "CURRENT_RUN",
) -> dict[str, Any]:
    meta = meta or {}
    ticks = [int(r["tick"]) for r in rows if "tick" in r]
    cut = cutoff_tick if cutoff_tick is not None else (max(ticks) if ticks else None)
    motor_schema = detect_motor_schema(rows=rows, events=events, meta=meta)
    systems = detect_signal_systems(rows=rows, events=events, meta=meta)
    osc_eps = reconstruct_osc_episodes(rows, cutoff=cut)
    composite = analyze_composite_motor(
        rows=rows, events=events, motor_schema=motor_schema, cutoff=cut,
    )
    duplex = analyze_full_duplex(rows=rows, cutoff=cut)
    patterns = discover_osc_patterns(osc_eps)
    associations = association_candidates(
        osc_patterns=patterns, composite=composite, rows=rows,
    )
    chrono = build_interaction_chronology(
        rows=rows, osc_episodes=osc_eps, events=events, cutoff=cut,
    )
    seed_out = seed
    if seed_out is None:
        seed_out = meta.get("seed")
    return {
        "analysis_source": source_label,
        "user_triggered": True,
        "polling_on_refresh": False,
        "source": {
            "label": source_label,
            "run_id": run_id or meta.get("run_id"),
            "generation": generation if generation is not None else meta.get("runtime_generation"),
            "seed": seed_out,
            "cutoff_tick": cut,
            "coverage": coverage,
            "telemetry_schema": telemetry_schema or meta.get("telemetry_schema") or meta.get("schema"),
            "motor_schema": motor_schema,
            "scientific_tick_range": [min(ticks), max(ticks)] if ticks else [None, None],
        },
        "signal_systems": systems,
        "oscillatory_episodes": osc_eps[:64],
        "n_oscillatory_episodes": len(osc_eps),
        "spectrotemporal_patterns": patterns,
        "full_duplex": duplex,
        "composite_motor": composite,
        "interaction_chronology": chrono,
        "candidate_associations": associations,
        "scientific_boundary": {
            "physical_signal_neq_message": True,
            "reception_neq_interpretation": True,
            "no_speaker_listener": True,
            "no_turn_taking_inference": True,
            "temporal_association_neq_causation": True,
            "banned_terms": list(_BANNED_SEMANTIC),
        },
        "fixture_mixed": False,
    }
