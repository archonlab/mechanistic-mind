"""Reception → cognition / action deltas (Observer-side, temporal only)."""
from __future__ import annotations

from typing import Any

from mechanistic_mind.ui.psy_observer_web.signal_context.windows import window_summary


# Fields known to be partially instrumented in scientific_timeline.
COGNITION_FIELD_COVERAGE = {
    "action": "AVAILABLE",
    "action_source": "AVAILABLE",
    "prediction_count": "PARTIAL",  # cumulative metric; early 0 may be real or pre-learning
    "prospective_compositions": "PARTIAL",
    "selection_via_SCENARIO_SELECTED": "AVAILABLE",  # events lane — do not equate with metrics==0
    "memory_fingerprint": "MISSING",
    "retrieval_fingerprint": "MISSING",
    "prediction_identities": "MISSING",
    "prediction_error": "MISSING",  # not on scientific tick rows
    "observation_fragment_FIELD": "MISSING",  # floats not persisted on timeline
    "causal_parent_ids_into_cognition": "MISSING",
}


def coverage_status(field: str) -> str:
    return COGNITION_FIELD_COVERAGE.get(field, "NOT_AVAILABLE")


def _changed(a: Any, b: Any) -> bool:
    if a is None and b is None:
        return False
    return a != b


def cognitive_delta(
    windows: dict[str, Any],
    *,
    episode_id: str,
    receiver_agent_id: str,
) -> dict[str, Any]:
    """Compare PRE vs POST_SHORT summaries. Evidence class is TEMPORALLY_ASSOCIATED only."""
    pre = window_summary(windows.get("PRE") or [])
    post = window_summary(windows.get("POST_SHORT") or [])

    # Fake-zero prevention: if metrics are 0 but status AVAILABLE, mark PARTIAL honesty
    pred_cov = coverage_status("prediction_count")
    prosp_cov = coverage_status("prospective_compositions")

    action_changed = _changed(pre.get("action_last"), post.get("action_last"))
    source_changed = _changed(
        pre.get("action_source_last"), post.get("action_source_last")
    )
    pred_changed = False
    if (
        pre.get("prediction_count_last") is not None
        and post.get("prediction_count_last") is not None
    ):
        pred_changed = int(post["prediction_count_last"]) != int(
            pre["prediction_count_last"]
        )
    prosp_changed = False
    if (
        pre.get("prospective_last") is not None
        and post.get("prospective_last") is not None
    ):
        prosp_changed = int(post["prospective_last"]) != int(pre["prospective_last"])

    delta = {
        "action_changed": action_changed,
        "selection_source_changed": source_changed,
        "prediction_count_changed": pred_changed,
        "prospective_count_changed": prosp_changed,
        "contact_changed": bool(pre.get("contact_any")) != bool(post.get("contact_any")),
    }

    evidence = "TEMPORALLY_ASSOCIATED"
    if pre.get("status") == "MISSING" or post.get("status") == "MISSING":
        evidence = "NOT_ESTABLISHED"

    return {
        "signal_episode": episode_id,
        "receiver": receiver_agent_id,
        "PRE": {
            "selection_source": pre.get("action_source_last"),
            "action": pre.get("action_last"),
            "prediction_count": pre.get("prediction_count_last"),
            "prospective_compositions": pre.get("prospective_last"),
            "contact_any": pre.get("contact_any"),
            "position": (pre.get("mean_x"), pre.get("mean_y")),
            "n_ticks": pre.get("n"),
            "status": pre.get("status"),
        },
        "POST": {
            "selection_source": post.get("action_source_last"),
            "action": post.get("action_last"),
            "prediction_count": post.get("prediction_count_last"),
            "prospective_compositions": post.get("prospective_last"),
            "contact_any": post.get("contact_any"),
            "position": (post.get("mean_x"), post.get("mean_y")),
            "n_ticks": post.get("n"),
            "status": post.get("status"),
        },
        "DELTA": delta,
        "EVIDENCE": {
            "reception_to_cognitive_delta": evidence,
            "note": "POST≠PRE is temporal association only — not causal linkage.",
        },
        "coverage": {
            "prediction_count": pred_cov,
            "prospective_compositions": prosp_cov,
            "action": coverage_status("action"),
            "action_source": coverage_status("action_source"),
            "fake_zero_warning": (
                "prediction_count/prospective_compositions==0 does NOT imply cognition absent; "
                "SCENARIO_SELECTED may still fire via ENDOGENOUS_VARIATION / other sources."
            ),
        },
    }


def action_geometry_separation(
    *,
    pre_action: str | None,
    post_action: str | None,
    pre_alignment: float | None,
    post_alignment: float | None,
    geometry_note: str | None = None,
) -> dict[str, Any]:
    """Separate requested-action change from geometry-driven deflection."""
    action_changed = pre_action != post_action and pre_action is not None and post_action is not None
    return {
        "action_request_changed": action_changed,
        "pre_action": pre_action,
        "post_action": post_action,
        "pre_alignment": pre_alignment,
        "post_alignment": post_alignment,
        "geometry_note": geometry_note or "NOT_AVAILABLE",
        "interpretation": (
            "ACTION REQUEST CHANGED after signal episode."
            if action_changed
            else "ACTION REQUEST UNCHANGED — realized motion differences may be geometry/contact."
        ),
        "evidence": {
            "signal_to_action_change": (
                "TEMPORALLY_ASSOCIATED" if action_changed else "NOT_ESTABLISHED"
            ),
            "action_to_realized_motion": "PHYSICALLY_EXPLAINED" if pre_alignment is not None else "NOT_AVAILABLE",
            "signal_to_action_causality": "NOT_ESTABLISHED",
        },
    }
