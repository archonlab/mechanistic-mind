"""Apply motor channel effects onto world position with resistance.

Uses existing world openness/obstacles. No semantic MOVE labels in cognition —
returns physical outcomes + optional high-level MOVE action for world transition
when displacement succeeds (compatibility bridge only).
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from mechanistic_mind.research.motor_control import (
    MotorControlConfig,
    MotorControlState,
    apply_motor_delta_to_state,
    endogenous_motor_delta,
    motor_attempted_step,
    proprioceptive_bundle,
    variation_body_cost,
)
from mechanistic_mind.research.sensorimotor_bootstrap import (
    SensorimotorBootstrapStore,
    SensorimotorFragment,
    ingest_fragment,
)


def _context_bucket(observation: dict[str, Any]) -> str:
    visible = []
    for item in observation.get("visible_objects") or ():
        if isinstance(item, dict) and item.get("id"):
            visible.append(str(item.get("cue_signature") or item["id"]))
    visible = tuple(sorted(visible)[:4])
    intero = observation.get("interoception") if isinstance(observation.get("interoception"), dict) else {}
    bands = []
    for k in ("energy_signal", "hydration_signal", "fatigue_signal"):
        if k in intero:
            v = float(intero[k])
            bands.append((k, "L" if v < 1 / 3 else "M" if v < 2 / 3 else "H"))
    # Update 4.5.1: activity capacity / load bands for state-conditioned contingencies.
    load = float(intero.get("activity_load_signal", intero.get("activity_load", 0.0)) or 0.0)
    cap = float(intero.get("activity_capacity_signal", max(0.0, 1.0 - load)) or 0.0)
    if cap >= 0.75:
        aband = "H"
    elif cap >= 0.40:
        aband = "M"
    else:
        aband = "L"
    bands.append(("activity_capacity", aband))
    bands.append(("activity_load", "H" if load >= 0.55 else ("M" if load >= 0.25 else "L")))
    return repr((visible, tuple(bands)))


def _perceptual_delta_tokens(before: dict[str, Any], after: dict[str, Any]) -> tuple[str, ...]:
    tokens: list[str] = []
    pb = tuple(before.get("position") or ())
    pa = tuple(after.get("position") or ())
    if pb and pa and pb != pa:
        tokens.append("pos_changed")
    vb = {
        str(i.get("id"))
        for i in (before.get("visible_objects") or ())
        if isinstance(i, dict) and i.get("id")
    }
    va = {
        str(i.get("id"))
        for i in (after.get("visible_objects") or ())
        if isinstance(i, dict) and i.get("id")
    }
    if vb != va:
        tokens.append("visible_set_changed")
    return tuple(tokens)


def step_motor_variation(
    *,
    world: Any,
    state: dict[str, Any],
    agent_id: str,
    motor_state: MotorControlState,
    store: SensorimotorBootstrapStore,
    config: MotorControlConfig,
    seed: int,
    tick: int,
    observation_before: dict[str, Any],
    apply_world_move: bool = True,
) -> dict[str, Any]:
    """One bounded endogenous motor variation step.

    Returns diagnostics + updated motor_state / store / optional action for Engine.
    """
    delta = endogenous_motor_delta(
        config=config, seed=seed, tick=tick, state=motor_state
    )
    proprio_before = proprioceptive_bundle(motor_state)
    new_motor = apply_motor_delta_to_state(motor_state, delta, config=config, tick=tick)
    intero = observation_before.get("interoception") if isinstance(observation_before.get("interoception"), dict) else {}
    act_load = float(intero.get("activity_load_signal", intero.get("activity_load", 0.0)) or 0.0)
    fat = float(intero.get("fatigue_signal", 0.0) or 0.0)
    act_cap = float(intero.get("activity_capacity_signal", max(0.0, 1.0 - act_load)) or 0.0)
    cost = variation_body_cost(
        delta,
        config,
        activity_load=act_load,
        fatigue=fat,
        activity_capacity=act_cap,
    )
    attempted = motor_attempted_step(
        new_motor.channels, threshold=config.displace_threshold
    )
    new_motor.last_attempted_step = attempted

    effect = "NO_DISPLACE"
    resistance = 0.0
    contact = 0.0
    displacement = None
    move_action = None
    position = None
    # Unwrap SimulationState / WorldState if needed.
    world_state = state
    if hasattr(state, "world"):
        world_state = state.world
    if hasattr(world_state, "variables") and isinstance(getattr(world_state, "variables", None), dict):
        # many ecology helpers accept SimulationState or variables dict
        pass
    try:
        position = tuple(world.position(state, agent_id))
    except Exception:
        try:
            position = tuple(world.position(world_state, agent_id))
        except Exception:
            pos = observation_before.get("position")
            position = tuple(pos) if isinstance(pos, (list, tuple)) and len(pos) == 2 else None

    if attempted is None:
        effect = "NO_DISPLACE"
    elif position is None:
        effect = "NONE"
    else:
        dest = (position[0] + attempted[0], position[1] + attempted[1])
        open_ok = True
        open_ok = True
        for cand in (state, world_state):
            try:
                open_ok = bool(world.is_open(cand, dest, ignore_agent_id=agent_id))
                break
            except TypeError:
                try:
                    open_ok = bool(world.is_open(cand, dest))
                    break
                except Exception:
                    continue
            except Exception:
                continue
        if not open_ok:
            effect = "BLOCKED"
            resistance = 1.0
            contact = 1.0
        else:
            # Terrain/obstacle soft resistance if present
            terrain = 1.0
            try:
                terrain = float(world.terrain_factor(state, dest))
            except Exception:
                terrain = 1.0
            if terrain > 1.2:
                resistance = min(1.0, (terrain - 1.0) / 2.0)
                effect = "RESISTED"
            if apply_world_move:
                move_action = f"MOVE:{dest[0]},{dest[1]}"
                displacement = attempted
                effect = "DISPLACED" if effect != "RESISTED" else "RESISTED"
            else:
                displacement = attempted
                effect = "DISPLACED"

    new_motor.last_resistance = float(resistance)
    new_motor.last_contact = float(contact)
    new_motor.last_displacement = displacement
    new_motor.last_effect_kind = effect
    # Load increases with resistance
    new_motor.last_load = [
        min(1.0, abs(c) + 0.25 * resistance) for c in new_motor.channels
    ]

    proprio_after = proprioceptive_bundle(new_motor)
    # Do not treat zero-delta (variation ablation) as sensorimotor evidence.
    if sum(abs(float(x)) for x in delta) <= 1e-12:
        return {
            "motor_state": new_motor,
            "store": store,
            "delta": delta,
            "cost": cost,
            "effect_kind": "NONE",
            "move_action": None,
            "proprioception": proprio_after,
            "ingest": {"skipped": "ZERO_DELTA"},
            "fragment": {"tick": tick, "skipped": True},
            "observer_note": "OBSERVER ONLY — NOT AVAILABLE TO COGNITION",
        }
    # perceptual after unknown until world steps; caller may re-ingest. Store provisional.
    frag = SensorimotorFragment(
        tick=tick,
        actuator_before=list(motor_state.channels),
        actuator_delta=list(delta),
        actuator_after=list(new_motor.channels),
        proprio_before=proprio_before,
        proprio_after=proprio_after,
        perceptual_delta_tokens=(),
        body_delta={k: float(v) for k, v in cost.items() if k != "motor_effort"},
        resistance=float(resistance),
        contact=float(contact),
        displacement=displacement,
        effect_kind=effect,
        context_bucket=_context_bucket(observation_before),
    )
    ingest_info = ingest_fragment(store, frag)

    # Queue physical motor demand for BodyEngine (non-symbolic).
    pending_demand = float(cost.get("motor_effort", 0.0) or 0.0) * float(cost.get("cost_scale", 1.0) or 1.0)
    try:
        vars_ = None
        if hasattr(state, "world") and hasattr(state.world, "variables"):
            vars_ = state.world.variables
        elif isinstance(getattr(state, "variables", None), dict):
            vars_ = state.variables
        if isinstance(vars_, dict):
            prev = float(vars_.get("pending_motor_demand_effort", 0.0) or 0.0)
            vars_["pending_motor_demand_effort"] = prev + pending_demand
            # Also stash provisional body deltas for diagnostics (Observer).
            vars_["pending_motor_cost"] = {
                k: float(v) for k, v in cost.items()
                if isinstance(v, (int, float)) and not isinstance(v, bool)
            }
    except Exception:
        pass

    return {
        "motor_state": new_motor,
        "store": store,
        "delta": delta,
        "cost": cost,
        "effect_kind": effect,
        "move_action": move_action,
        "proprioception": proprio_after,
        "ingest": ingest_info,
        "fragment": frag.to_dict(),
        "observer_note": "OBSERVER ONLY — NOT AVAILABLE TO COGNITION",
    }


def finalize_fragment_perception(
    store: SensorimotorBootstrapStore,
    fragment_dict: dict[str, Any],
    observation_before: dict[str, Any],
    observation_after: dict[str, Any],
) -> None:
    """Attach perceptual delta tokens to the latest matching recent fragment."""
    tokens = _perceptual_delta_tokens(observation_before, observation_after)
    if store.recent_fragments:
        last = dict(store.recent_fragments[-1])
        if last.get("tick") == fragment_dict.get("tick"):
            last["perceptual_delta_tokens"] = list(tokens)
            store.recent_fragments[-1] = last
