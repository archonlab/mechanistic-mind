from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FoundationMechanismSpec:
    mechanism_key: str
    role: str
    reads: tuple[str, ...]
    writes: tuple[str, ...]
    timescale: str
    status: str
    alternatives: tuple[str, ...]
    discriminating_test: str


# These are candidate computational roles, not a claim that psychology already
# possesses a complete or settled list of fundamental mechanisms.
FOUNDATION_MAP: tuple[FoundationMechanismSpec, ...] = (
    FoundationMechanismSpec(
        "internal_regulation",
        "Maintain and update slow internal variables and deviations from target ranges.",
        ("previous consequence", "internal state", "goals"),
        ("internal", "global_state"),
        "fast + slow",
        "FOUNDATION_CANDIDATE",
        ("set-point control", "predictive regulation", "resource-budget control"),
        "Perturb internal resources while holding external opportunities fixed.",
    ),
    FoundationMechanismSpec(
        "perception",
        "Transform partial environmental observation into agent-accessible perceptual state.",
        ("environment observation",),
        ("percept",),
        "fast",
        "FOUNDATION_CANDIDATE",
        ("identity transduction", "noisy encoding", "feature extraction"),
        "Vary observation noise/information while preserving world truth.",
    ),
    FoundationMechanismSpec(
        "attention",
        "Select a capacity-limited subset of currently available information.",
        ("percept", "goals", "global_state"),
        ("attention",),
        "fast",
        "FOUNDATION_CANDIDATE",
        ("salience", "goal-directed", "uncertainty-directed"),
        "Compete relevant and irrelevant signals under limited capacity.",
    ),
    FoundationMechanismSpec(
        "learning",
        "Update action/consequence models from experienced transitions.",
        ("attention", "previous action", "consequence"),
        ("learning",),
        "medium",
        "FOUNDATION_CANDIDATE",
        ("running mean", "recency weighted", "Bayesian", "associative trace"),
        "Reversal, stochasticity, and transfer tests.",
    ),
    FoundationMechanismSpec(
        "memory",
        "Persist selected traces beyond the current tick and retrieve them later.",
        ("attention", "learning", "previous state"),
        ("memory",),
        "medium + slow",
        "FOUNDATION_CANDIDATE",
        ("episodic trace", "associative memory", "compressed statistics"),
        "Delay, interference, cue-dependent retrieval, and ablation.",
    ),
    FoundationMechanismSpec(
        "prediction",
        "Generate expected future consequences conditional on candidate actions.",
        ("learning", "memory", "attention"),
        ("predictions",),
        "fast",
        "FOUNDATION_CANDIDATE",
        ("model-free expectation", "transition model", "multi-step planning"),
        "Novel state/action combinations and horizon manipulation.",
    ),
    FoundationMechanismSpec(
        "prediction_error",
        "Measure mismatch between expected and observed consequences.",
        ("predictions", "consequence"),
        ("prediction_errors",),
        "fast",
        "FOUNDATION_CANDIDATE",
        ("signed error", "vector error", "surprise"),
        "Separate noise from persistent regime change.",
    ),
    FoundationMechanismSpec(
        "uncertainty",
        "Represent lack of knowledge separately from expected value.",
        ("learning", "memory", "prediction error"),
        ("uncertainty",),
        "medium",
        "FOUNDATION_CANDIDATE",
        ("sample-count", "variance", "posterior entropy"),
        "Equal expected value with different evidence amounts.",
    ),
    FoundationMechanismSpec(
        "goals",
        "Maintain desired constraints or target regions over different horizons.",
        ("internal", "memory", "environment context"),
        ("goals",),
        "slow",
        "FOUNDATION_CANDIDATE",
        ("setpoints", "hierarchical targets", "constraint satisfaction"),
        "Create conflicts between immediate and delayed target satisfaction.",
    ),
    FoundationMechanismSpec(
        "global_modulation",
        "Let slow/global state alter gain, exploration, learning, or action thresholds.",
        ("internal", "uncertainty", "prediction_errors"),
        ("global_state",),
        "slow",
        "FOUNDATION_CANDIDATE",
        ("arousal-like gain", "adaptive learning rate", "risk modulation"),
        "Hold local evidence fixed while changing global internal state.",
    ),
    FoundationMechanismSpec(
        "self_model",
        "Track regularities about the agent's own action efficacy and constraints.",
        ("action history", "consequences", "internal"),
        ("self_model",),
        "slow",
        "FOUNDATION_CANDIDATE",
        ("capability model", "control estimate", "body/resource model"),
        "Alter action efficacy independently of external outcome value.",
    ),
    FoundationMechanismSpec(
        "habit",
        "Create history-dependent action bias from repeated selection.",
        ("action history",),
        ("habits",),
        "slow",
        "FOUNDATION_CANDIDATE",
        ("frequency trace", "contextual chunking", "cached policy"),
        "Outcome devaluation and context switch after repetition.",
    ),
    FoundationMechanismSpec(
        "valuation",
        "Evaluate predicted consequences against multiple current constraints without a single hidden reward scalar.",
        ("predictions", "internal", "goals", "habits"),
        ("values",),
        "fast",
        "FOUNDATION_CANDIDATE",
        ("multi-objective", "lexicographic", "Pareto", "state-dependent utility"),
        "Tradeoff worlds where objectives conflict.",
    ),
    FoundationMechanismSpec(
        "action_generation",
        "Turn currently available actions and valuations into explicit candidates.",
        ("attention", "values", "uncertainty"),
        ("action candidates",),
        "fast",
        "FOUNDATION_CANDIDATE",
        ("affordance sampling", "goal-conditioned generation"),
        "Change action availability without changing values.",
    ),
    FoundationMechanismSpec(
        "action_selection",
        "Choose among competing candidates under value, uncertainty, and modulation.",
        ("action candidates", "uncertainty", "global_state"),
        ("selected action",),
        "fast",
        "FOUNDATION_CANDIDATE",
        ("argmax", "softmax", "uncertainty-first", "threshold competition"),
        "Explore/exploit and conflict-resolution experiments.",
    ),
)
