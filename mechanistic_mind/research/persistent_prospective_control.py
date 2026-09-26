"""4.28 — Persistent prospective control (label-free).

A PSC-selected prospective continuation may remain causally relevant across
subsequent ticks while predictive support holds. Not an INTENTION variable.
Not an arbitrary N-tick commitment.

Reuses support/mismatch ideas from Update 4.16 persistent prospective traces,
but couples them to PSC selection and context-grounded compositions.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from mechanistic_mind.research.persistent_prospective_trace import (
    MAX_TRACE_LIFETIME_TICKS,
    state_compatibility,
)


MAX_ACTIVE = 1
MAX_MOTOR_CHUNKS = 32
MIN_CHUNK_SUPPORT = 3
SUPPORT_L1_EPS = 0.35  # predictive mismatch threshold (not SUCCESS/FAILURE)


def empty_store() -> dict[str, Any]:
    return {
        "enabled": False,
        "ablate_persistence": False,
        "ablate_motor_chunks": False,
        "active": None,
        "motor_chunks": {},
        "selections": 0,
        "continuations": 0,
        "interruptions": 0,
        "completions": 0,
        "chunk_formations": 0,
        "last_event": None,
        "note": "PERSISTENT_PROSPECTIVE_CONTROL — support-gated, not a timer commitment",
    }


def snapshot(store: dict[str, Any] | None) -> dict[str, Any]:
    s = store or {}
    active = s.get("active")
    return {
        "enabled": bool(s.get("enabled")),
        "has_active": active is not None,
        "active": deepcopy(active) if active else None,
        "n_motor_chunks": len(s.get("motor_chunks") or {}),
        "selections": s.get("selections"),
        "continuations": s.get("continuations"),
        "interruptions": s.get("interruptions"),
        "completions": s.get("completions"),
        "chunk_formations": s.get("chunk_formations"),
        "last_event": deepcopy(s.get("last_event")),
        "ablate_persistence": bool(s.get("ablate_persistence")),
        "ablate_motor_chunks": bool(s.get("ablate_motor_chunks")),
        "safety_lifetime_cap": MAX_TRACE_LIFETIME_TICKS,
        "note": s.get("note"),
    }


def observer_compact(store: dict[str, Any] | None) -> dict[str, Any]:
    s = store or {}
    a = s.get("active") or {}
    return {
        "detail": "compact",
        "enabled": bool(s.get("enabled")),
        "active_id": a.get("id"),
        "age": a.get("age"),
        "cursor": a.get("cursor"),
        "depth": a.get("depth"),
        "support_status": a.get("support_status"),
        "novel_composition": bool(a.get("novel_composition")),
        "interruptions": s.get("interruptions"),
        "continuations": s.get("continuations"),
        "n_motor_chunks": len(s.get("motor_chunks") or {}),
    }


def _action_sig(actions: list[str]) -> str:
    return "|".join(str(a) for a in actions)


def observe_motor_sequence(
    store: dict[str, Any],
    *,
    actions: list[str],
) -> None:
    """Accumulate support for repeated action sequences (motor chunks)."""
    if not store.get("enabled") or store.get("ablate_motor_chunks"):
        return
    acts = [str(a) for a in actions if a]
    if len(acts) < 2:
        return
    key = _action_sig(acts[:6])
    chunks = store.setdefault("motor_chunks", {})
    row = chunks.get(key)
    if row is None:
        if len(chunks) >= MAX_MOTOR_CHUNKS:
            victim = min(chunks.items(), key=lambda kv: (int(kv[1].get("support") or 0), str(kv[0])))[0]
            del chunks[victim]
        row = {"id": f"MC{len(chunks)+1:04d}", "actions": acts[:6], "support": 0, "reuse": 0}
        chunks[key] = row
        store["chunk_formations"] = int(store.get("chunk_formations") or 0) + 1
    row["support"] = int(row.get("support") or 0) + 1


def select_continuation(
    store: dict[str, Any],
    *,
    tick: int,
    continuation: dict[str, Any],
    origin_observation: dict[str, float] | None = None,
) -> dict[str, Any] | None:
    """Adopt a PSC-selected multi-step continuation as active prospective organization."""
    if not store.get("enabled") or store.get("ablate_persistence"):
        return None
    acts = [str(a) for a in (continuation.get("actions") or continuation.get("future_actions") and
            [continuation.get("first_action"), *(continuation.get("future_actions") or [])] or [])]
    if continuation.get("actions"):
        acts = [str(a) for a in continuation.get("actions") or []]
    elif continuation.get("first_action"):
        acts = [str(continuation.get("first_action"))] + [str(a) for a in (continuation.get("future_actions") or [])]
    if len(acts) < 2:
        return None  # single-step is ordinary selection, not persistence
    store["selections"] = int(store.get("selections") or 0) + 1
    active = {
        "id": f"PPC-{int(store.get('selections') or 1):06d}",
        "created_tick": int(tick),
        "age": 0,
        "cursor": 0,
        "actions": acts,
        "depth": len(acts),
        "path_ids": list(continuation.get("path_ids") or []),
        "source": continuation.get("source"),
        "novel_composition": bool(
            continuation.get("source") == "context_grounded_prospection"
            or int(continuation.get("depth") or 0) > 1
        ),
        "origin_observation": dict(origin_observation or {}),
        "predicted_states": list(continuation.get("predicted_states") or []),
        "support_status": "ACTIVE",
        "historical_support": continuation.get("historical_support"),
        "reliability": continuation.get("reliability"),
        "complete_route_seen": bool(continuation.get("complete_route_seen", False)),
    }
    store["active"] = active
    store["last_event"] = {"type": "SELECT", "tick": int(tick), "id": active["id"], "depth": active["depth"]}
    return deepcopy(active)


def preferred_action(store: dict[str, Any]) -> str | None:
    """Next action under active prospective influence (if any)."""
    if not store.get("enabled") or store.get("ablate_persistence"):
        return None
    active = store.get("active")
    if not active or active.get("support_status") != "ACTIVE":
        return None
    cursor = int(active.get("cursor") or 0)
    acts = active.get("actions") or []
    if cursor >= len(acts):
        return None
    return str(acts[cursor])


def advance(
    store: dict[str, Any],
    *,
    tick: int,
    realized_observation: dict[str, float] | None,
    realized_action: str | None,
    predicted_next: dict[str, float] | None = None,
    relevant_break: bool = False,
) -> dict[str, Any]:
    """Advance or interrupt active prospective organization by predictive support.

    ``relevant_break`` is an analyzer/experiment hook injecting a physical break;
    cognition only sees mismatch via predicted vs realized (or forced collapse
    when the experiment physically breaks an intermediate relation — passed as
    collapsed prediction). Prefer mismatch path; relevant_break is for controlled
    probes where prediction objects are unavailable.
    """
    active = store.get("active")
    if not active:
        return {"status": "NONE"}
    if not store.get("enabled") or store.get("ablate_persistence"):
        store["active"] = None
        return {"status": "ABLATED"}

    active["age"] = int(active.get("age") or 0) + 1
    # Safety bound only — not the scientific persistence rule.
    if int(active["age"]) > MAX_TRACE_LIFETIME_TICKS:
        store["interruptions"] = int(store.get("interruptions") or 0) + 1
        store["last_event"] = {"type": "SAFETY_CAP", "tick": int(tick), "id": active.get("id")}
        store["active"] = None
        return {"status": "SAFETY_CAP"}

    expected = None
    cursor = int(active.get("cursor") or 0)
    acts = list(active.get("actions") or [])
    if cursor < len(acts):
        expected = str(acts[cursor])

    # Action divergence
    if realized_action is not None and expected is not None and str(realized_action) != expected:
        # Allow if motor chunk substitution preserves prefix — still count as soft
        pass  # physical realization may differ; predictive state is the gate

    # Predictive support check
    support_status = "ACTIVE"
    compat = {"status": "SKIP", "compatible": True, "l1": None}
    if predicted_next and realized_observation:
        compat = state_compatibility(predicted_next, realized_observation, eps=SUPPORT_L1_EPS)
        if not compat.get("compatible"):
            support_status = "COLLAPSED"
    if relevant_break:
        support_status = "COLLAPSED"

    if support_status == "COLLAPSED":
        active["support_status"] = "COLLAPSED"
        store["interruptions"] = int(store.get("interruptions") or 0) + 1
        store["last_event"] = {
            "type": "INTERRUPT",
            "tick": int(tick),
            "id": active.get("id"),
            "compat": compat,
            "relevant_break": bool(relevant_break),
        }
        store["active"] = None
        return {"status": "INTERRUPT", "compat": compat, "active": deepcopy(active)}

    # Continue
    active["support_status"] = "ACTIVE"
    active["cursor"] = cursor + 1
    store["continuations"] = int(store.get("continuations") or 0) + 1
    if active["cursor"] >= len(acts):
        store["completions"] = int(store.get("completions") or 0) + 1
        store["last_event"] = {"type": "COMPLETE", "tick": int(tick), "id": active.get("id"), "age": active["age"]}
        done = deepcopy(active)
        store["active"] = None
        return {"status": "COMPLETE", "active": done, "compat": compat}

    store["last_event"] = {
        "type": "CONTINUE",
        "tick": int(tick),
        "id": active.get("id"),
        "cursor": active["cursor"],
        "age": active["age"],
        "compat": compat,
    }
    store["active"] = active
    return {"status": "CONTINUE", "active": deepcopy(active), "compat": compat, "next_action": preferred_action(store)}
