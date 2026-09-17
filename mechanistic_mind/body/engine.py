from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from mechanistic_mind.agent import Action

from .physical_intake import (
    apply_transfer_to_materials,
    env_exchange_params_from_body_config,
    intake_params_from_body_config,
    process_materials,
)
from .passive_physical_exchange import (
    processing_enabled as _ppe_processing_enabled,
    resolve_env_exchange_params,
    resolve_processing_params,
)
from .models import BodyConfig, BodyState, InteroceptiveSignals
from .physical_transduction import maybe_step_on_state
from .persistent_processes import (
    advance_persistent_processes,
    default_process_config,
    ensure_process_state,
    sensory_fragments as process_sensory_fragments,
)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _smoothstep01(value: float) -> float:
    x = _clamp01(value)
    return x * x * (3.0 - 2.0 * x)


@dataclass(frozen=True, slots=True)
class BodyTransition:
    state: BodyState
    signals_before: InteroceptiveSignals
    signals_after: InteroceptiveSignals
    signal_delta: dict[str, float]
    objective_effects: dict[str, float]
    movement_cost: dict[str, float]
    mass_dynamics: dict[str, float]


class BodyEngine:
    """Objective daily toy physiology for one organism.

    One simulation tick is one simulated day by default.

    Crucial v0.3.1 separation:
    - `energy_delta` changes short-term functional energy state.
    - `metabolic_energy_intake` enters objective metabolic balance.
    - progress/success has no direct mass effect.
    """

    def __init__(self, config: BodyConfig | None = None) -> None:
        self.config = config or BodyConfig()
        self.config.validate()

    def mass_risk(self, mass_kg: float) -> dict[str, float]:
        cfg = self.config

        if mass_kg >= cfg.low_mass_safe_boundary_kg:
            low = 0.0
        else:
            width = (
                cfg.low_mass_safe_boundary_kg
                - cfg.low_mass_critical_kg
            )
            low = _smoothstep01(
                (
                    cfg.low_mass_safe_boundary_kg
                    - mass_kg
                )
                / width
            )

        if mass_kg <= cfg.high_mass_safe_boundary_kg:
            high = 0.0
        else:
            width = (
                cfg.high_mass_critical_kg
                - cfg.high_mass_safe_boundary_kg
            )
            high = _smoothstep01(
                (
                    mass_kg
                    - cfg.high_mass_safe_boundary_kg
                )
                / width
            )

        combined = 1.0 - (1.0 - low) * (1.0 - high)
        return {
            "low_mass_risk": _clamp01(low),
            "high_mass_risk": _clamp01(high),
            "physiological_mass_risk": _clamp01(combined),
        }

    def _apply_risk_truth(self, state: BodyState) -> None:
        risk = self.mass_risk(state.mass_kg)
        state.low_mass_risk = risk["low_mass_risk"]
        state.high_mass_risk = risk["high_mass_risk"]
        state.physiological_mass_risk = risk[
            "physiological_mass_risk"
        ]

    def process_fragments(self, state: BodyState) -> dict[str, float]:
        proc_cfg = getattr(self.config, "persistent_process_config", None)
        if not isinstance(proc_cfg, dict) or not proc_cfg.get("enabled", True):
            return {}
        return process_sensory_fragments(state.internal_loads, config=proc_cfg)

    def signals(self, state: BodyState) -> InteroceptiveSignals:
        # Risk itself is not directly signalled. The agent experiences only
        # downstream fatigue, damage/discomfort, hydration and effort.
        # Signals are fullness fractions — capacity > 1 still feels "full" at reserve>=capacity.
        return InteroceptiveSignals(
            energy_signal=_clamp01(
                state.energy_reserve / max(1e-9, float(self.config.energy_capacity))
            ),
            hydration_signal=_clamp01(
                state.hydration / max(1e-9, float(self.config.hydration_capacity))
            ),
            fatigue_signal=_clamp01(state.fatigue),
            discomfort_signal=_clamp01(
                0.70 * state.damage
                + 0.20 * max(0.0, state.fatigue - 0.65)
                + 0.10 * max(0.0, 0.30 - state.hydration)
            ),
            effort_signal=_clamp01(state.last_effort_cost),
            activity_load_signal=_clamp01(float(state.activity_load)),
            activity_capacity_signal=_clamp01(float(state.activity_capacity)),
        )

    def movement_cost(
        self,
        state: BodyState,
        *,
        distance: float,
        terrain_factor: float = 1.0,
    ) -> dict[str, float]:
        cfg = self.config
        risk = self.mass_risk(state.mass_kg)

        mass_factor = (
            max(state.mass_kg, 0.1)
            / max(cfg.reference_mass_kg, 0.1)
        ) ** cfg.mass_effort_exponent

        impairment = (
            1.0
            + cfg.damage_effort_multiplier * _clamp01(state.damage)
            + cfg.fatigue_effort_multiplier * _clamp01(state.fatigue)
            + cfg.activity_load_effort_multiplier * _clamp01(float(state.activity_load))
            + cfg.mass_risk_effort_multiplier
            * risk["physiological_mass_risk"]
        )

        effort = max(0.0, float(distance)) * max(
            0.1,
            float(terrain_factor),
        )
        effort *= mass_factor * impairment

        return {
            "energy_delta": (
                -cfg.movement_energy_cost_per_cell * effort
            ),
            "hydration_delta": (
                -cfg.movement_hydration_cost_per_cell * effort
            ),
            "fatigue_delta": (
                cfg.movement_fatigue_cost_per_cell * effort
            ),
            "metabolic_energy_expenditure": (
                cfg.movement_metabolic_expenditure_per_effort
                * effort
            ),
            "effort": effort,
        }

    def transition(
        self,
        state: BodyState,
        *,
        action: Action,
        distance: float = 0.0,
        terrain_factor: float = 1.0,
        external_effects: dict[str, Any] | None = None,
        exogenous_effects: dict[str, Any] | None = None,
        carried_mass_kg: float = 0.0,
    ) -> BodyTransition:
        cfg = self.config
        before = state.clone()
        self._apply_risk_truth(before)
        signals_before = self.signals(before)

        next_state = before.clone()
        risk_before = self.mass_risk(before.mass_kg)
        days = cfg.tick_duration_days

        movement = self.movement_cost(
            next_state,
            distance=distance,
            terrain_factor=terrain_factor,
        )

        objective: dict[str, float] = {
            "energy_delta": -cfg.basal_energy_drain_per_day * days,
            "hydration_delta": (
                -cfg.basal_hydration_drain_per_day * days
            ),
            "fatigue_delta": (
                cfg.passive_fatigue_gain_per_day * days
            ),
            "damage_delta": 0.0,
            "metabolic_energy_intake": 0.0,
            "metabolic_energy_expenditure": (
                cfg.basal_metabolic_expenditure_per_day * days
            ),
        }

        carried_mass = max(0.0, float(carried_mass_kg))
        objective["energy_delta"] -= (
            cfg.carried_energy_cost_per_kg_day * carried_mass * days
        )
        objective["hydration_delta"] -= (
            cfg.carried_hydration_cost_per_kg_day * carried_mass * days
        )
        objective["fatigue_delta"] += (
            cfg.carried_fatigue_cost_per_kg_day * carried_mass * days
        )
        objective["carried_mass_kg"] = carried_mass

        # Being outside the configured mass operating region creates objective
        # physiological strain, not a psychological label.
        objective["fatigue_delta"] += (
            cfg.mass_risk_fatigue_per_day
            * risk_before["physiological_mass_risk"]
            * days
        )
        objective["damage_delta"] += (
            cfg.mass_risk_damage_per_day
            * risk_before["physiological_mass_risk"]
            * days
        )
        objective["energy_delta"] -= (
            cfg.low_mass_extra_energy_drain_per_day
            * risk_before["low_mass_risk"]
            * days
        )

        if distance > 0:
            objective["energy_delta"] += movement["energy_delta"]
            objective["hydration_delta"] += movement[
                "hydration_delta"
            ]
            objective["fatigue_delta"] += movement["fatigue_delta"]
            objective["metabolic_energy_expenditure"] += movement[
                "metabolic_energy_expenditure"
            ]
            next_state.last_effort_cost = _clamp01(
                movement["effort"] * 0.08
            )
        else:
            next_state.last_effort_cost *= 0.45

        # Update 4.5.1: non-displace motor demand (microvariation / isometric work).
        # Same physical accounting family as movement; state-dependent via load/fatigue.
        motor_demand = 0.0
        for src in (external_effects or {}, exogenous_effects or {}):
            raw = src.get("motor_demand_effort") if isinstance(src, dict) else None
            if isinstance(raw, (int, float)) and not isinstance(raw, bool):
                motor_demand += max(0.0, float(raw))
        if motor_demand > 0.0:
            load_f = 1.0 + cfg.activity_load_effort_multiplier * _clamp01(
                float(next_state.activity_load)
            )
            fat_f = 1.0 + cfg.fatigue_effort_multiplier * _clamp01(
                float(next_state.fatigue)
            )
            scale = load_f * fat_f
            objective["energy_delta"] -= cfg.motor_demand_energy_cost * motor_demand * scale
            objective["hydration_delta"] -= (
                cfg.motor_demand_hydration_cost * motor_demand * scale
            )
            objective["fatigue_delta"] += (
                cfg.motor_demand_fatigue_cost * motor_demand * scale
            )
            next_state.last_effort_cost = _clamp01(
                max(float(next_state.last_effort_cost), motor_demand * 0.08 * scale)
            )

        # Update 4: activity load + optional recovery on reduced activity.
        action_kind = str(getattr(action, "kind", "") or "")
        is_wait = action_kind == "WAIT"
        if is_wait:
            next_state.consecutive_wait_ticks = int(
                next_state.consecutive_wait_ticks
            ) + 1
        else:
            next_state.consecutive_wait_ticks = 0

        if cfg.recovery_dynamics_enabled:
            effort_proxy = float(next_state.last_effort_cost)
            # Demand-based: any nontrivial motor/effort demand loads capacity.
            # Not keyed on symbolic WAIT identity.
            high_demand = (
                distance > 0
                or motor_demand > 1e-9
                or effort_proxy >= 0.02
                or action_kind.startswith(("PUSH:", "TAKE:", "EMIT"))
            )
            if high_demand:
                next_state.activity_load = min(
                    1.0,
                    float(next_state.activity_load)
                    + cfg.activity_load_gain_per_effort
                    * max(effort_proxy, 0.05 if distance > 0 else 0.02)
                    * days,
                )
            else:
                # Reduced activity: bounded recovery scaled by current load.
                load = max(0.0, float(next_state.activity_load))
                recovery = min(
                    cfg.max_inactivity_fatigue_recovery_per_day * days,
                    cfg.inactivity_fatigue_recovery_per_day
                    * days
                    * load,
                )
                objective["fatigue_delta"] -= recovery
                next_state.activity_load = max(
                    0.0,
                    load
                    * (1.0 - cfg.activity_load_decay_per_day) ** days
                    - cfg.inactivity_load_recovery_per_day * days * load,
                )
        elif is_wait:
            # Compatibility: still track waits; no extra recovery.
            pass

        # Update 4.8/4.9: USE intake + continuous env exchange → same internal_materials.
        intake_params = intake_params_from_body_config(cfg)
        env_params = resolve_env_exchange_params(cfg)
        ppe_proc = _ppe_processing_enabled(cfg)
        next_state.last_intake_transfer = 0.0
        next_state.last_intake_processed = 0.0
        next_state.last_env_exchange = 0.0
        next_state.last_env_availability = 0.0
        intake_receipt = {}
        # Env availability metadata (Observer); transfer may be absent when ablated.
        for src in (external_effects or {}, exogenous_effects or {}):
            if isinstance(src, dict) and "env_availability" in src:
                try:
                    next_state.last_env_availability = float(src.get("env_availability", 0.0))
                except Exception:
                    pass
                break
        materials_path_on = bool(intake_params.enabled or env_params.enabled or ppe_proc)
        if materials_path_on:
            mats = dict(next_state.internal_materials or {})
            use_accepted = 0.0
            env_accepted = 0.0
            transfer_payload = None
            for src in (external_effects or {}, exogenous_effects or {}):
                if isinstance(src, dict) and isinstance(src.get("intake_transfer"), dict):
                    transfer_payload = src.get("intake_transfer")
                    break
            if intake_params.enabled and transfer_payload:
                for mat, amt in transfer_payload.items():
                    if isinstance(amt, (int, float)) and float(amt) > 0:
                        mats[str(mat)] = float(mats.get(str(mat), 0.0)) + float(amt)
                        use_accepted += float(amt)
                next_state.last_intake_transfer = use_accepted
            env_payload = None
            for src in (external_effects or {}, exogenous_effects or {}):
                if isinstance(src, dict) and isinstance(src.get("env_exchange_transfer"), dict):
                    env_payload = src.get("env_exchange_transfer")
                    break
            if env_params.enabled and env_payload:
                for mat, amt in env_payload.items():
                    if isinstance(amt, (int, float)) and float(amt) > 0:
                        mats[str(mat)] = float(mats.get(str(mat), 0.0)) + float(amt)
                        env_accepted += float(amt)
                next_state.last_env_exchange = env_accepted
            next_state.internal_materials = mats
            # Defer processing only for discrete USE acquisition (4.8).
            # Continuous env exchange must not permanently block processing.
            if use_accepted > 1e-12 and intake_params.enabled:
                proc_body, processed = {}, 0.0
            elif intake_params.enabled or ppe_proc:
                proc_params = intake_params if intake_params.enabled else resolve_processing_params(cfg)
                mats2, proc_body, processed = process_materials(
                    dict(next_state.internal_materials or {}),
                    params=proc_params,
                )
                next_state.internal_materials = mats2
            else:
                # Env-only storage without USE processing path: still store, no process.
                proc_body, processed = {}, 0.0
            next_state.last_intake_processed = processed
            for key, value in proc_body.items():
                objective[key] = float(objective.get(key, 0.0)) + float(value)
            intake_receipt = {
                "accepted_transfer": use_accepted,
                "env_exchange_accepted": env_accepted,
                "env_availability": float(next_state.last_env_availability),
                "processed": processed,
                "internal_total": float(sum((next_state.internal_materials or {}).values())),
                "body_deltas_from_processing": proc_body,
            }

        for source in (external_effects or {}, exogenous_effects or {}):
            for key in (
                "energy_delta",
                "hydration_delta",
                "fatigue_delta",
                "damage_delta",
                "metabolic_energy_intake",
                "metabolic_energy_expenditure",
            ):
                raw = source.get(key)
                if isinstance(raw, (int, float)) and not isinstance(raw, bool):
                    value = float(raw)

                    # Recovery can be less efficient under physiological strain.
                    if (
                        key == "fatigue_delta"
                        and value < 0.0
                        and risk_before["physiological_mass_risk"] > 0.0
                    ):
                        efficiency = (
                            1.0
                            - cfg.mass_risk_recovery_penalty
                            * risk_before["physiological_mass_risk"]
                        )
                        value *= max(0.0, efficiency)

                    objective[key] += value

        # Persistent numeric channels are generic body state. Any external
        # effect named ``internal_load:<channel>`` accumulates after passive
        # decay; no domain meaning or interaction is encoded here.
        decayed_loads = {
            str(key): max(
                0.0,
                float(value) * (1.0 - cfg.internal_load_decay_per_day) ** days,
            )
            for key, value in next_state.internal_loads.items()
        }
        for source in (external_effects or {}, exogenous_effects or {}):
            for key, raw in source.items():
                if not str(key).startswith("internal_load:"):
                    continue
                if not isinstance(raw, (int, float)) or isinstance(raw, bool):
                    continue
                channel = str(key).split(":", 1)[1]
                decayed_loads[channel] = max(
                    0.0,
                    decayed_loads.get(channel, 0.0) + float(raw),
                )
        next_state.internal_loads = decayed_loads

        # Update 4.20 — persistent generic processes (continue under WAIT).
        proc_cfg = getattr(cfg, "persistent_process_config", None)
        if isinstance(proc_cfg, dict) and proc_cfg.get("enabled", True):
            env_sample = None
            for source in (external_effects or {}, exogenous_effects or {}):
                if isinstance(source, dict) and isinstance(source.get("env_sample"), dict):
                    env_sample = source.get("env_sample")
                    break
            new_loads, proc_obj, proc_receipt = advance_persistent_processes(
                next_state.internal_loads,
                config=proc_cfg,
                action_kind=str(getattr(action, "kind", "") or ""),
                env_sample=env_sample,
                days=days,
            )
            next_state.internal_loads = new_loads
            next_state.last_process_receipt = dict(proc_receipt)
            for k, v in proc_obj.items():
                objective[k] = float(objective.get(k, 0.0)) + float(v)
        elif getattr(cfg, "persistent_process_config", None) is None:
            # auto-enable default when config field is None? No — only when explicitly set.
            pass

        next_state.energy_reserve = _clamp01(
            next_state.energy_reserve + objective["energy_delta"]
        )
        next_state.hydration = _clamp01(
            next_state.hydration + objective["hydration_delta"]
        )
        next_state.fatigue = _clamp01(
            next_state.fatigue + objective["fatigue_delta"]
        )
        next_state.damage = _clamp01(
            next_state.damage + objective["damage_delta"]
        )

        # Mass is driven only by objective metabolic balance.
        metabolic_balance = (
            objective["metabolic_energy_intake"]
            - objective["metabolic_energy_expenditure"]
        )
        raw_mass_delta = (
            metabolic_balance
            * cfg.kg_per_metabolic_balance_unit
        )
        mass_delta = min(
            cfg.max_mass_gain_kg_per_day * days,
            max(
                -cfg.max_mass_loss_kg_per_day * days,
                raw_mass_delta,
            ),
        )

        next_state.mass_kg = min(
            cfg.maximum_mass_kg,
            max(
                cfg.minimum_mass_kg,
                next_state.mass_kg + mass_delta,
            ),
        )
        next_state.last_daily_metabolic_balance = metabolic_balance
        next_state.last_mass_delta_kg = (
            next_state.mass_kg - before.mass_kg
        )

        # Biological time: one tick = one simulated day by default.
        next_state.age_days += days
        next_state.simulated_days += days

        self._apply_risk_truth(next_state)
        maybe_step_on_state(next_state, self.config)

        signals_after = self.signals(next_state)
        before_dict = signals_before.to_dict()
        after_dict = signals_after.to_dict()
        delta = {
            key: after_dict[key] - before_dict[key]
            for key in after_dict
        }

        mass_dynamics = {
            "metabolic_energy_intake": objective[
                "metabolic_energy_intake"
            ],
            "metabolic_energy_expenditure": objective[
                "metabolic_energy_expenditure"
            ],
            "metabolic_balance": metabolic_balance,
            "raw_mass_delta_kg": raw_mass_delta,
            "applied_mass_delta_kg": next_state.last_mass_delta_kg,
            "low_mass_risk": next_state.low_mass_risk,
            "high_mass_risk": next_state.high_mass_risk,
            "physiological_mass_risk": (
                next_state.physiological_mass_risk
            ),
            "life_day": float(next_state.life_day),
            "age_years": float(next_state.age_years),
        }

        return BodyTransition(
            state=next_state,
            signals_before=signals_before,
            signals_after=signals_after,
            signal_delta=delta,
            objective_effects=deepcopy(objective),
            movement_cost=deepcopy(movement),
            mass_dynamics=mass_dynamics,
        )
