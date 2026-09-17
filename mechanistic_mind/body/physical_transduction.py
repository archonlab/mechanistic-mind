"""Update 4.56 — generic bounded body-side physical transduction.

Experimental. Default BodyConfig leaves this OFF.
Cognition does not receive component names. Same local rule for every channel.
"""
from __future__ import annotations

from typing import Any

# Source declaration order on BodyState (energy_reserve, hydration, fatigue).
# Not a semantic ranking.
COMPONENT_COUNT = 3
DECAY = 0.70
SCALE = 0.25
X_BOUND = 1.0
# Fixed 3→2 mix into existing 4.39 numeric ports. Not trained. Not named.
MIX = (
    (0.70, 0.20, 0.10),
    (0.10, 0.30, 0.60),
)
PERM_CYCLE = (1, 2, 0)


def default_transducer_config(mode: str = "ABSOLUTE") -> dict[str, Any]:
    if mode not in {"ABSOLUTE", "CHANGE"}:
        raise ValueError(mode)
    return {
        "enabled": True,
        "mode": mode,
        "decay": DECAY,
        "scale": SCALE,
        "bound": X_BOUND,
        "mix": MIX,
        "permute": None,
    }


def clip_x(x: float, bound: float = X_BOUND) -> float:
    return max(-bound, min(bound, float(x)))


def clip01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def body_vector_from_values(energy_reserve: float, hydration: float, fatigue: float,
                            permute: tuple[int, ...] | None = None) -> tuple[float, float, float]:
    raw = (float(energy_reserve), float(hydration), float(fatigue))
    if permute is None:
        return raw
    return (raw[permute[0]], raw[permute[1]], raw[permute[2]])


def step_transducer(
    x: tuple[float, float, float],
    body: tuple[float, float, float],
    prev: tuple[float, float, float] | None,
    *,
    mode: str,
    decay: float = DECAY,
    scale: float = SCALE,
    bound: float = X_BOUND,
) -> tuple[float, float, float]:
    """X' = clip(decay * X + scale * u). u is B-0.5 or ΔB. No names, no valence."""
    prev = prev if prev is not None else body
    out = []
    for i in range(COMPONENT_COUNT):
        if mode == "CHANGE":
            u = float(body[i]) - float(prev[i])
        else:
            u = float(body[i]) - 0.5
        out.append(clip_x(decay * float(x[i]) + scale * u, bound))
    return (out[0], out[1], out[2])


def ports_from_x(x: tuple[float, float, float],
                 mix: tuple[tuple[float, ...], ...] = MIX) -> tuple[float, float]:
    """Documented 4.39 interface: mixed X occupies existing numeric body ports."""
    raw0 = sum(mix[0][i] * float(x[i]) for i in range(COMPONENT_COUNT))
    raw1 = sum(mix[1][i] * float(x[i]) for i in range(COMPONENT_COUNT))
    return (clip01(0.5 + 0.5 * raw0), clip01(0.5 + 0.5 * raw1))


def maybe_step_on_state(state: Any, config: Any) -> None:
    """In-place BodyState update. No-op unless experimental config is a dict."""
    cfg = getattr(config, "physical_transduction_config", None)
    if not isinstance(cfg, dict) or not cfg.get("enabled", True):
        return
    body = body_vector_from_values(
        float(state.energy_reserve), float(state.hydration), float(state.fatigue),
        permute=cfg.get("permute"),
    )
    prev = getattr(state, "transducer_prev", None)
    x = tuple(float(v) for v in (getattr(state, "transducer_state", None) or (0.0, 0.0, 0.0)))
    if len(x) != 3:
        x = (0.0, 0.0, 0.0)
    state.transducer_state = step_transducer(
        x, body, prev,
        mode=str(cfg.get("mode") or "ABSOLUTE"),
        decay=float(cfg.get("decay", DECAY)),
        scale=float(cfg.get("scale", SCALE)),
        bound=float(cfg.get("bound", X_BOUND)),
    )
    state.transducer_prev = body
