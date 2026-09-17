"""Update 4.4/4.5 — MP → ordinary candidate + prospective consequence valuation.

Availability from acquisition; desirability only from predicted physical deltas
via the same target-gain logic as OrganismValuationModule.

No curiosity / novelty / MP bonus / confidence-as-value.
"""
from __future__ import annotations

from typing import Any

from mechanistic_mind.agent import Action

from mechanistic_mind.psyche.contracts import (
    PsycheActionCandidate,
    PsycheContext,
    PsycheModule,
    PsycheOutput,
    PsycheStage,
    PsycheUpdate,
)
from mechanistic_mind.psyche.sensorimotor import available_actions
from mechanistic_mind.research.sensorimotor_bootstrap import (
    SensorimotorBootstrapStore,
    retrieve_primitive_executables,
)
from mechanistic_mind.research.sensorimotor_physics import _context_bucket
from mechanistic_mind.research.prospective_valuation import prospective_ordinary_value


class MotorPrimitiveBridgeModule(PsycheModule):
    module_id = "PSY-MOTOR-PRIMITIVE-BRIDGE-V044"
    version = "0.4.5"
    stage = PsycheStage.ACTION_GENERATION

    def __init__(
        self,
        *,
        enabled: bool = True,
        prospective_valuation: bool = True,
        prediction_ablated: bool = False,
    ) -> None:
        self.enabled = bool(enabled)
        self.prospective_valuation = bool(prospective_valuation)
        self.prediction_ablated = bool(prediction_ablated)

    def process(self, context: PsycheContext) -> PsycheOutput:
        if not self.enabled:
            return PsycheOutput(
                signals={"mp_bridge": {"enabled": False, "status": "DISABLED"}}
            )

        store = SensorimotorBootstrapStore.from_dict(
            context.state.memory.get("sensorimotor_bootstrap")
            if isinstance(context.state.memory, dict)
            else None
        )
        obs = context.observation
        data = dict(obs.data) if isinstance(obs.data, dict) else {}
        available = set(available_actions(obs))
        pos_raw = data.get("position")
        position = None
        if isinstance(pos_raw, (list, tuple)) and len(pos_raw) == 2:
            position = (int(pos_raw[0]), int(pos_raw[1]))
        bucket = _context_bucket(data)

        retrieved = retrieve_primitive_executables(
            store,
            position=position,
            available_actions=available,
            context_bucket=bucket,
        )

        values = {}
        if isinstance(context.state.values, dict):
            values = context.state.values.get("by_action") or {}
        if not isinstance(values, dict):
            values = {}

        current_signals = {}
        if isinstance(context.state.internal, dict):
            current_signals = dict(context.state.internal.get("interoceptive_model") or {})
        if not current_signals:
            intero = data.get("interoception") if isinstance(data.get("interoception"), dict) else {}
            current_signals = dict(intero)
        goals = context.state.goals if isinstance(context.state.goals, dict) else {}

        # capacities if present on intero/context
        e_cap = float(data.get("energy_capacity") or current_signals.get("energy_capacity") or 1.0)
        h_cap = float(data.get("hydration_capacity") or current_signals.get("hydration_capacity") or 1.0)

        candidates: list[PsycheActionCandidate] = []
        rows = []
        for item in retrieved:
            action = str(item["action"])
            legacy = values.get(action, {}) if isinstance(values.get(action), dict) else {}
            legacy_ordinary = float(legacy.get("base_total", 0.0) or 0.0)

            prosp = {
                "prospective_available": False,
                "ordinary_value": None,
                "epistemic_status": "UNKNOWN",
                "reason": "PROSPECTIVE_DISABLED",
                "predicted_signal_deltas": {},
                "predicted_body_delta": {},
                "confidence_used_as_value": False,
            }
            if self.prospective_valuation:
                prosp = prospective_ordinary_value(
                    mean_body_delta=item.get("mean_body_delta") or {},
                    body_delta_samples=float(item.get("body_delta_samples") or 0.0),
                    contradiction=float(item.get("contradiction_rate") or 0.0),
                    current_signals=current_signals,
                    goals=goals,
                    energy_capacity=e_cap,
                    hydration_capacity=h_cap,
                    support=float(item.get("support") or 0.0),
                    prediction_ablated=self.prediction_ablated,
                )

            if prosp.get("prospective_available") and prosp.get("ordinary_value") is not None:
                ordinary = float(prosp["ordinary_value"])
                value_source = "PROSPECTIVE_PHYSICAL"
            else:
                ordinary = legacy_ordinary
                value_source = "LEGACY_VALUES_OR_ZERO"

            components = {}
            if isinstance(prosp.get("components"), dict):
                components = {k: float(v) for k, v in prosp["components"].items()}
            elif legacy:
                components = {
                    str(k): float(v)
                    for k, v in legacy.items()
                    if isinstance(v, (int, float)) and k != "base_total"
                }

            meta = {
                "proposal_source": "MOTOR_PRIMITIVE_BRIDGE",
                "primitive_id": item["primitive_id"],
                "predictive_confidence": float(item.get("predictive_support") or 0.0),
                "support_count": float(item.get("support") or 0.0),
                "predicted_transition_summary": {
                    "displacement": item.get("predicted_displacement"),
                    "effect_hist": item.get("effect_hist"),
                    "mean_body_delta": item.get("mean_body_delta"),
                    "predicted_signal_deltas": prosp.get("predicted_signal_deltas"),
                },
                "prediction_status": item.get("prediction_status"),
                "epistemic_status": prosp.get("epistemic_status"),
                "ordinary_action_value": ordinary,
                "value_source": value_source,
                "prospective": prosp,
                "mp_bridge": True,
                "mp_makes_good": False,
                "confidence_used_as_value": False,
                "movement": action.startswith("MOVE:"),
            }
            candidates.append(
                PsycheActionCandidate(
                    source_module=self.module_id,
                    action=Action(action),
                    total_value=ordinary,
                    components=components,
                    metadata=meta,
                )
            )
            rows.append(
                {
                    "primitive_id": item["primitive_id"],
                    "action": action,
                    "ordinary_value": ordinary,
                    "legacy_ordinary": legacy_ordinary,
                    "epistemic_status": prosp.get("epistemic_status"),
                    "value_source": value_source,
                    "prospective_available": prosp.get("prospective_available"),
                    "predicted_signal_deltas": prosp.get("predicted_signal_deltas"),
                    "regulation": prosp.get("regulation"),
                    "support": item.get("support"),
                    "retrieved": True,
                    "candidate_generated": True,
                }
            )

        bridge_diag = {
            "enabled": True,
            "prospective_valuation": self.prospective_valuation,
            "prediction_ablated": self.prediction_ablated,
            "retrieval_enabled": store.retrieval_enabled,
            "primitive_count": len(store.primitives),
            "retrieved_executable": len(retrieved),
            "candidates_emitted": len(candidates),
            "rows": rows,
            "observer_note": "OBSERVER ONLY — bridge availability ≠ value; prospective uses physical deltas only",
        }
        return PsycheOutput(
            candidates=tuple(candidates),
            updates=(PsycheUpdate("working", "mp_bridge", bridge_diag),),
            signals={"mp_bridge": bridge_diag},
        )
