"""Observer-only Signal Context Interpreter (BETA2-SIGINT-01).

Evidence machine for physical signal episodes → cognition/action deltas
with matched no-signal controls. Never mutates cognition or physics.
Never claims communication / meaning / intention.
"""
from __future__ import annotations

from mechanistic_mind.ui.psy_observer_web.signal_context.episodes import (
    group_signal_episodes,
    stable_episode_id,
)
from mechanistic_mind.ui.psy_observer_web.signal_context.windows import (
    WINDOW_SPEC,
    extract_windows,
)
from mechanistic_mind.ui.psy_observer_web.signal_context.cognition_delta import (
    cognitive_delta,
    coverage_status,
)
from mechanistic_mind.ui.psy_observer_web.signal_context.matched_controls import (
    find_matched_controls,
)
from mechanistic_mind.ui.psy_observer_web.signal_context.analyze_run import (
    analyze_signal_run,
    signal_episode_context,
)
from mechanistic_mind.ui.psy_observer_web.signal_context.intervention import (
    intervention_design_doc,
    rank_sigint01_candidates,
    run_candidate_experiment,
)

__all__ = [
    "group_signal_episodes",
    "stable_episode_id",
    "WINDOW_SPEC",
    "extract_windows",
    "cognitive_delta",
    "coverage_status",
    "find_matched_controls",
    "analyze_signal_run",
    "signal_episode_context",
    "intervention_design_doc",
    "rank_sigint01_candidates",
    "run_candidate_experiment",
]
