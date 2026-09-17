"""Update 4.19 — Bounded compositional action-pattern audit / optional reuse.

Does not invent free-form actions. Tracks repeated primitive sequences among
existing physically legal actions and may retain them as unlabeled reusable
patterns. No semantic names.
"""
from __future__ import annotations

from typing import Any

MAX_PATTERNS = 32
MIN_SUPPORT = 3


def empty_action_store() -> dict[str, Any]:
    return {
        "recent": [],
        "patterns": {},
        "reuse_enabled": True,
        "retained": 0,
    }


def observe_action(store: dict[str, Any], action: str, *, tick: int) -> None:
    recent = store.setdefault("recent", [])
    recent.append(str(action))
    store["recent"] = recent[-6:]
    # count length-2 and length-3 sequences
    for n in (2, 3):
        if len(recent) < n:
            continue
        seq = tuple(recent[-n:])
        key = ">>".join(seq)
        row = store.setdefault("patterns", {}).get(key)
        if row is None:
            if len(store["patterns"]) >= MAX_PATTERNS:
                victim = min(store["patterns"].items(), key=lambda kv: kv[1].get("support", 0))[0]
                store["patterns"].pop(victim, None)
            row = {"sequence": list(seq), "support": 0, "first_tick": tick, "last_tick": tick}
            store["patterns"][key] = row
        row["support"] = int(row.get("support") or 0) + 1
        row["last_tick"] = tick
        if row["support"] == MIN_SUPPORT:
            store["retained"] = int(store.get("retained") or 0) + 1


def reusable_candidates(store: dict[str, Any], available: set[str]) -> list[dict[str, Any]]:
    """Return unlabeled reusable next-step hints from repeated sequences."""
    if not store.get("reuse_enabled", True):
        return []
    recent = store.get("recent") or []
    out = []
    for key, row in (store.get("patterns") or {}).items():
        if int(row.get("support") or 0) < MIN_SUPPORT:
            continue
        seq = row.get("sequence") or []
        if len(seq) < 2:
            continue
        prefix, nxt = seq[:-1], seq[-1]
        if list(recent[-(len(prefix)):]) == list(prefix) and nxt in available:
            out.append({
                "pattern_id": key[:16],
                "next_action": nxt,
                "support": row.get("support"),
                # no semantic label
            })
    out.sort(key=lambda r: (-int(r.get("support") or 0), str(r.get("pattern_id"))))
    return out[:4]


def snapshot(store: dict[str, Any]) -> dict[str, Any]:
    pats = store.get("patterns") or {}
    return {
        "pattern_count": len(pats),
        "retained": store.get("retained"),
        "reuse_enabled": store.get("reuse_enabled"),
        "top": sorted(
            (
                {"sequence": v.get("sequence"), "support": v.get("support")}
                for v in pats.values()
            ),
            key=lambda r: (-int(r.get("support") or 0), str(r.get("sequence"))),
        )[:8],
    }
