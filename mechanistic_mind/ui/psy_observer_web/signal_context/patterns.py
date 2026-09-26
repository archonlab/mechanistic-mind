"""Conservative repeated signal-context → outcome pattern clustering."""
from __future__ import annotations

import hashlib
from typing import Any


def _pattern_key(rec: dict[str, Any]) -> str:
    pre = rec.get("PRE") or {}
    sig = rec.get("SIGNAL") or {}
    parts = (
        str(rec.get("receiver")),
        str(pre.get("action") or ""),
        str(pre.get("selection_source") or ""),
        str(sig.get("channel") or ""),
        "X" if float(sig.get("cross_agent_contribution_fraction") or 0) > 0 else "S",
        "C" if pre.get("contact_any") else "N",
    )
    return "|".join(parts)


def stable_pattern_id(key: str) -> str:
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]
    return f"sigpat-{digest}"


def cluster_patterns(
    episode_records: list[dict[str, Any]],
    *,
    min_episodes: int = 3,
) -> list[dict[str, Any]]:
    """Group similar PRE+signal → POST deltas. No semantic labels."""
    buckets: dict[str, list[dict[str, Any]]] = {}
    for rec in episode_records:
        k = _pattern_key(rec)
        buckets.setdefault(k, []).append(rec)

    patterns: list[dict[str, Any]] = []
    for key, items in sorted(buckets.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        if len(items) < min_episodes:
            continue
        n = len(items)
        act_n = sum(1 for r in items if (r.get("DELTA") or {}).get("action_changed"))
        src_n = sum(
            1 for r in items if (r.get("DELTA") or {}).get("selection_source_changed")
        )
        ctrl_act = []
        ctrl_src = []
        for r in items:
            cmp_ = r.get("matched_comparison") or {}
            c = cmp_.get("controls") or {}
            if c.get("action_change_rate") is not None:
                ctrl_act.append(float(c["action_change_rate"]))
            if c.get("selection_source_change_rate") is not None:
                ctrl_src.append(float(c["selection_source_change_rate"]))

        evidence = "TEMPORALLY_ASSOCIATED"
        mean_ctrl_act = sum(ctrl_act) / len(ctrl_act) if ctrl_act else None
        if mean_ctrl_act is not None and act_n / n >= 0.6 and mean_ctrl_act <= 0.35:
            evidence = "MATCHED_ASSOCIATION"

        pre0 = items[0].get("PRE") or {}
        sig0 = items[0].get("SIGNAL") or {}
        patterns.append(
            {
                "pattern_id": stable_pattern_id(key),
                "key": key,
                "receiver": items[0].get("receiver"),
                "episodes": n,
                "episode_ids": [r.get("signal_episode") for r in items][:32],
                "PRE": {
                    "action": pre0.get("action"),
                    "selection_source": pre0.get("selection_source"),
                    "contact_any": pre0.get("contact_any"),
                },
                "SIGNAL": {
                    "channel": sig0.get("channel"),
                    "cross_agent": sig0.get("cross_agent_contribution_fraction"),
                },
                "POST": {
                    "selection_source_changed_frac": src_n / n,
                    "requested_direction_changed_frac": act_n / n,
                },
                "matched_controls": {
                    "mean_action_change_rate": mean_ctrl_act,
                    "mean_selection_source_change_rate": (
                        sum(ctrl_src) / len(ctrl_src) if ctrl_src else None
                    ),
                },
                "evidence": evidence,
                "honesty": {
                    "no_semantic_meaning": True,
                    "not_communication": True,
                },
            }
        )
    return patterns
