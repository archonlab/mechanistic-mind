from __future__ import annotations

from copy import deepcopy
from typing import Any

from mechanistic_mind.agent import Action
from mechanistic_mind.mechanisms import ActionProposal, Mechanism, MechanismContext, MechanismOutput, StateUpdate
from mechanistic_mind.research import instrumental_observation as io
from mechanistic_mind.research import multiscale_prediction as ms
from mechanistic_mind.research import predictive_compression as pc
from mechanistic_mind.research import prospective_composition as pr

from .causal_trace import edge, empty_trace, event
from .config import IntegratedConfig


def _numbers(data: Any, prefix: str = "", out: dict[str, float] | None = None) -> dict[str, float]:
    """Bounded numeric projection of agent-accessible observation only."""
    out = {} if out is None else out
    if len(out) >= 32:
        return out
    if isinstance(data, bool):
        out[prefix or "v"] = float(data)
    elif isinstance(data, (int, float)):
        out[prefix or "v"] = max(0.0, min(1.0, float(data)))
    elif isinstance(data, dict):
        for key in sorted(data, key=str):
            if str(key) in {"id", "object_id", "hidden_role", "causal_provenance"}:
                continue
            _numbers(data[key], f"{prefix}.{key}" if prefix else str(key), out)
            if len(out) >= 32:
                break
    elif isinstance(data, (list, tuple)):
        for i, value in enumerate(data[:8]):
            _numbers(value, f"{prefix}.{i}" if prefix else str(i), out)
            if len(out) >= 32:
                break
    return out


def _initial(config: IntegratedConfig) -> dict[str, Any]:
    compression = pc.empty_memory()
    multiscale = ms.empty_org()
    prospection = pr.empty_store()
    # The tested module uses these as optional membership containers only;
    # lists preserve that behavior and satisfy canonical telemetry/snapshots.
    prospection["relation_boost_ids"] = []
    prospection["broader_member_ids"] = []
    instrumental = io.empty_store()
    compression["ablate_compression"] = not config.predictive_compression
    multiscale["ablate_local"] = not config.multiscale_prediction
    multiscale["ablate_broader"] = not config.multiscale_prediction
    prospection["ablate_composition"] = not config.prospective_composition
    instrumental["ablate_learned"] = not config.instrumental_observation
    return {"config": config.to_dict(), "compression": compression, "multiscale": multiscale,
            "prospection": prospection, "instrumental": instrumental,
            "trace": empty_trace(config.causal_trace_capacity), "last_fragment": None,
            "last_action": None, "last_experience_event": None, "last_active_event": None,
            "pending_instrumental_fragment": None,
            "metrics": {"prediction_error_sum": 0.0, "prediction_count": 0,
                        "prospective_compositions": 0, "novel_compositions": 0,
                        "instrumental_acquired": 0, "instrumental_later_used": 0,
                        "action_counts": {}, "interaction_counts": {}}}


class IntegratedPsycheV1(Mechanism):
    """Adapter coupling validated bounded stores inside the ordinary Engine loop."""

    mechanism_id = "PSYCHE-INTEGRATED-V1"
    version = "1.0.0"

    def __init__(self, config: IntegratedConfig | None = None) -> None:
        self.config = config or IntegratedConfig()

    def process(self, context: MechanismContext) -> MechanismOutput:
        state = deepcopy(context.mechanism_state.get("integrated"))
        if not isinstance(state, dict):
            state = _initial(self.config)
        cfg = state["config"]
        fragment = _numbers(context.observation.data)
        actions = [str(a) for a in context.observation.data.get("available_actions", ())]
        if "WAIT" not in actions:
            actions.append("WAIT")
        previous, previous_action = state.get("last_fragment"), state.get("last_action")
        trace = state["trace"]
        metrics = state["metrics"]

        # The previous accessible fragment/action and current accessible fragment are
        # an actually observed transition; no world truth is consulted here.
        if isinstance(previous, dict) and previous_action:
            predicted = pc.predict(state["compression"], previous, previous_action) if cfg["retrieval"] else {"status": "ABLATION"}
            predicted_values = predicted.get("predicted") or predicted.get("mean_predicted") or {}
            if cfg["bounded_memory"]:
                raw = pc.observe(state["compression"], tick=context.tick, fragment=previous,
                                 action=previous_action, predicted=predicted_values, realized=fragment,
                                 domain="accessible")
            else:
                raw = {"raw_id": None}
            exp_id = event(trace, tick=context.tick, kind="EXPERIENCE", mechanism="ordinary_observation",
                           payload={"raw_id": raw["raw_id"], "action": previous_action})
            if state.get("last_experience_event"):
                edge(trace, source=state["last_experience_event"], target=exp_id, tick=context.tick,
                     mechanism="physical_recurrence", provenance="next_accessible_observation", relation="TEMPORAL")
            state["last_experience_event"] = exp_id

            if cfg["multiscale_prediction"] and cfg["bounded_memory"]:
                lid = ms.ingest_local(state["multiscale"], tick=context.tick, domain="accessible",
                                      fragment=previous, action=previous_action, realized=fragment,
                                      raw_id=raw["raw_id"])
                if lid:
                    sid = event(trace, tick=context.tick, kind="PREDICTIVE_STRUCTURE_CHANGED",
                                mechanism="multiscale_prediction", payload={"local_id": lid})
                    edge(trace, source=exp_id, target=sid, tick=context.tick,
                         mechanism="multiscale_prediction", provenance={"raw_id": raw["raw_id"]})
            pr.learn_transition(state["prospection"], tick=context.tick, antecedent=previous,
                                action=previous_action, consequent=fragment)
            tr_id = event(trace, tick=context.tick, kind="TRANSITION_CHANGED",
                          mechanism="prospective_composition", payload={"action": previous_action})
            edge(trace, source=exp_id, target=tr_id, tick=context.tick,
                 mechanism="prospective_composition", provenance={"tick": context.tick})
            pending_instrumental = state.get("pending_instrumental_fragment")
            if isinstance(pending_instrumental, dict) and cfg["instrumental_observation"]:
                io.learn_prediction(state["instrumental"], pending_instrumental, fragment)
                state["pending_instrumental_fragment"] = None
            if previous_action == "EMIT" and cfg["instrumental_observation"]:
                state["pending_instrumental_fragment"] = deepcopy(fragment)
                metrics["instrumental_acquired"] += 1
                state["last_active_event"] = event(trace, tick=context.tick, kind="ACTIVE_RETURN_ACQUIRED",
                                                   mechanism="instrumental_observation",
                                                   payload={"source_action": "EMIT"})
                edge(trace, source=exp_id, target=state["last_active_event"], tick=context.tick,
                     mechanism="instrumental_observation", provenance="ordinary_active_return")
            if predicted_values:
                err = sum(abs(float(fragment.get(k, 0.0)) - float(predicted_values.get(k, 0.0)))
                          for k in set(fragment) | set(predicted_values))
                metrics["prediction_error_sum"] += err
                metrics["prediction_count"] += 1

        predictions = []
        if cfg["retrieval"]:
            for action in actions:
                found = pc.predict(state["compression"], fragment, action, domain="accessible")
                if found.get("status") not in {"NO_MATCH", "UNKNOWN", "ABLATION"}:
                    predictions.append({"action": action, "source": "compression", "result": found})
        composition = pr.compose_trajectories(state["prospection"], start=fragment,
                                              max_depth=int(cfg["prospective_depth"]), branch_actions=actions)
        continuations = composition.get("continuations") or []
        instrumental_prediction = io.predict(state["instrumental"], fragment) if cfg["instrumental_observation"] else {"status": "ABLATED"}
        if continuations:
            metrics["prospective_compositions"] += 1
            metrics["novel_compositions"] += int(any(int(x.get("depth", 0)) > 1 for x in continuations))

        # Learned prospective continuation can alter the selected physical action.
        # Ranking uses only edge reliability/depth, never semantic value or world truth.
        selected = None
        selected_source = "ENDOGENOUS_VARIATION"
        if cfg["prospective_composition"] and continuations:
            selected = str(continuations[0]["actions"][0])
            selected_source = "PROSPECTIVE_CONTINUATION"
        elif predictions:
            selected = str(max(predictions, key=lambda x: int(x["result"].get("support", 0)))["action"])
            selected_source = "RETAINED_PREDICTION"
        if selected not in actions:
            selected = actions[min(len(actions) - 1, int(context.random_value * len(actions)))]

        pred_event = event(trace, tick=context.tick, kind="PREDICTION_RETRIEVAL", mechanism=selected_source,
                           payload={"selected_action": selected, "match_count": len(predictions)})
        if state.get("last_experience_event") and (predictions or continuations):
            edge(trace, source=state["last_experience_event"], target=pred_event, tick=context.tick,
                 mechanism=selected_source, provenance="runtime_retrieval")
        action_event = event(trace, tick=context.tick, kind="ACTION_SELECTED", mechanism=self.mechanism_id,
                             payload={"action": selected, "source": selected_source})
        edge(trace, source=pred_event, target=action_event, tick=context.tick,
             mechanism="action_selection", provenance=selected_source)
        if state.get("last_active_event") and instrumental_prediction.get("status") == "MATCH":
            edge(trace, source=state["last_active_event"], target=pred_event, tick=context.tick,
                 mechanism="instrumental_observation", provenance="acquired_fragment_retrieved")
            metrics["instrumental_later_used"] += 1
        metrics["action_counts"][selected] = int(metrics["action_counts"].get(selected, 0)) + 1

        pc.purge_redundant_raw(state["compression"], keep_recent=True)
        state["last_fragment"], state["last_action"] = fragment, selected
        signals = {"integrated_psyche": {
            "mechanisms": deepcopy(cfg), "agent_observation": deepcopy(context.observation.data),
            "memory": pc.snapshot(state["compression"]), "predictive_organization": ms.snapshot(state["multiscale"]),
            "prospection": {**pr.snapshot(state["prospection"]), "current": deepcopy(continuations[:8])},
            "instrumental_observation": {**io.snapshot(state["instrumental"]),
                                         "last_acquired_event": state.get("last_active_event"),
                                         "current_prediction": deepcopy(instrumental_prediction)},
            "action": {"candidates": actions, "selected": selected, "source": selected_source,
                       "prediction_matches": deepcopy(predictions[:8])},
            "causal_trace": {"events": deepcopy(trace["events"][-64:]), "edges": deepcopy(trace["edges"][-192:]),
                             "capacity": trace["capacity"]}, "metrics": deepcopy(metrics)}}
        return MechanismOutput(proposals=(ActionProposal(source_mechanism=self.mechanism_id,
                                                         action=Action(selected), priority=100,
                                                         metadata={"selection_source": selected_source,
                                                                   "action_event": action_event}),),
                               state_updates=(StateUpdate.mechanism_state("integrated", state),),
                               signals=signals,
                               telemetry={"mechanism_configuration": deepcopy(cfg), "bounded": True})
