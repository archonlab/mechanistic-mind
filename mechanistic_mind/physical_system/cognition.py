"""Cognitive stores owned by PhysicalSystemRuntime (not a second runtime).

Reuses validated 4.21–4.25 module APIs and IntegratedPsycheV1 selection ranking
patterns without Engine / ContextualObjectEcologyWorld.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from mechanistic_mind.integrated.causal_trace import edge, empty_trace, event
from mechanistic_mind.research import instrumental_observation as io
from mechanistic_mind.research import multiscale_prediction as ms
from mechanistic_mind.research import predictive_compression as pc
from mechanistic_mind.research import predictive_equivalence as pe
from mechanistic_mind.research import predictive_relevance as prl
from mechanistic_mind.research import prospective_composition as pr
from mechanistic_mind.research import temporal_predictive_structure as tps
from mechanistic_mind.research import temporal_prospection_bridge as tpb
from mechanistic_mind.research import predictive_conflict as pcf
from mechanistic_mind.research import future_sensitive_action as fsa
from mechanistic_mind.research import prediction_error_revision as per
from mechanistic_mind.research import temporal_prediction_error as tpe
from mechanistic_mind.research import predicted_context_prospection as pcp
from mechanistic_mind.research import multistep_action_prospection as mapr

from .actions import available_actions
from .observation import audit_cognition_payload
from .unknown_action_probe import classify_unmodeled_actions, probe_receipt

# BETA2-03: retain tick-local last_selection payloads without deepcopy.
# Set False to restore BETA2-02 deepcopy retention for equivalence harnesses.
_USE_TICK_LOCAL_RETAIN = True


def set_tick_local_retain(enabled: bool) -> None:
    global _USE_TICK_LOCAL_RETAIN
    _USE_TICK_LOCAL_RETAIN = bool(enabled)


def tick_local_retain_enabled() -> bool:
    return bool(_USE_TICK_LOCAL_RETAIN)


def _retain_tick_local(value: Any) -> Any:
    """Retain a tick-local cognition object without deepcopy.

    Only for structures constructed in the current cognition tick that are not
    mutated after retention. ``last_selection`` is replaced each tick.
    Historical isolation for receipts / public views is provided by their own
    deepcopy on export (see diagnostics.build_action_decision_receipt,
    cognition_public_view).
    """
    if not _USE_TICK_LOCAL_RETAIN:
        return deepcopy(value)
    return value


def _retain_tick_local_list(rows: list[Any] | None, *, limit: int) -> list[Any]:
    """New list container; element identity retained (tick-local, read-only after)."""
    if not rows:
        return []
    if not _USE_TICK_LOCAL_RETAIN:
        return deepcopy(rows[:limit])
    return list(rows[:limit])
from . import scenario_competition as sc


@dataclass
class CognitionConfig:
    predictive_compression: bool = True
    multiscale_prediction: bool = True
    prospective_composition: bool = True
    instrumental_observation: bool = True  # store only; physical EMIT path may be BRIDGE_MISSING
    bounded_memory: bool = True
    retrieval: bool = True
    causal_trace_capacity: int = 512
    prospective_depth: int = 3
    cognition_enabled: bool = True
    # LEGACY_FIRST: diagnosis baseline (continuations[0].actions[0])
    # SCENARIO_COMPETITION: explicit peer competition among first-action scenarios
    prospective_selection: str = "SCENARIO_COMPETITION"
    # Detection-only experimental classifier. Default OFF. Does not select.
    unknown_action_physical_probe: bool = False
    # Experimental: group continuous antecedents by experienced continuations.
    # Default OFF. Complements exact SHA; does not replace raw observation.
    predictive_equivalence: bool = False
    # Experimental: relation-specific relevant keys for partial retrieval.
    # Default OFF. Not a global sensor mask. Not attention.
    predictive_relevance: bool = False
    # Experimental: trajectory-conditioned prediction from ordinary recent fragments.
    # Default OFF. No CLOCK. Not RISING/FALLING labels.
    temporal_predictive_structure: bool = False
    # Experimental: transport TPS MATCH into 4.23 first-step roots. Default OFF.
    # Does not predict, select, or rewrite composition rules.
    temporal_prospection_bridge: bool = False
    # Experimental: content-based identity for incompatible same-action futures.
    # Default OFF. Does not select, invent confidence, or privilege sources.
    predictive_conflict: bool = False
    # Experimental: pass content-identified scenarios into existing competition.
    # Default OFF. Does not invent a policy, reward, or actions.
    future_sensitive_action: bool = False
    # Experimental: mismatch vs issued prediction can invalidate current MATCH.
    # Default OFF. Does not rewrite historical counts, punish, or select.
    prediction_error_revision: bool = False
    # Experimental: bounded prediction residuals enter existing TPS. Default OFF.
    # Does not detect DRIFT, invalidate, or assign value.
    temporal_prediction_error: bool = False
    # Experimental: predicted future context → read-only action-consequence lookup.
    # Default OFF. Does not write experience, invent actions, or select.
    predicted_context_prospection: bool = False
    # Experimental: present action → future context → future action composition.
    # Default OFF. Does not invent macros, value, or execute future actions.
    multistep_action_prospection: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "predictive_compression": self.predictive_compression,
            "multiscale_prediction": self.multiscale_prediction,
            "prospective_composition": self.prospective_composition,
            "instrumental_observation": self.instrumental_observation,
            "bounded_memory": self.bounded_memory,
            "retrieval": self.retrieval,
            "causal_trace_capacity": self.causal_trace_capacity,
            "prospective_depth": self.prospective_depth,
            "cognition_enabled": self.cognition_enabled,
            "prospective_selection": self.prospective_selection,
            "unknown_action_physical_probe": self.unknown_action_physical_probe,
            "predictive_equivalence": self.predictive_equivalence,
            "predictive_relevance": self.predictive_relevance,
            "temporal_predictive_structure": self.temporal_predictive_structure,
            "temporal_prospection_bridge": self.temporal_prospection_bridge,
            "predictive_conflict": self.predictive_conflict,
            "future_sensitive_action": self.future_sensitive_action,
            "prediction_error_revision": self.prediction_error_revision,
            "temporal_prediction_error": self.temporal_prediction_error,
            "predicted_context_prospection": self.predicted_context_prospection,
            "multistep_action_prospection": self.multistep_action_prospection,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "CognitionConfig":
        data = data or {}
        return cls(**{k: data[k] for k in cls.__dataclass_fields__ if k in data})


def empty_cognitive_state(config: CognitionConfig) -> dict[str, Any]:
    compression = pc.empty_memory()
    multiscale = ms.empty_org()
    prospection = pr.empty_store()
    prospection["relation_boost_ids"] = []
    prospection["broader_member_ids"] = []
    instrumental = io.empty_store()
    compression["ablate_compression"] = not config.predictive_compression
    multiscale["ablate_local"] = not config.multiscale_prediction
    multiscale["ablate_broader"] = not config.multiscale_prediction
    prospection["ablate_composition"] = not config.prospective_composition
    instrumental["ablate_learned"] = not config.instrumental_observation
    equivalence = pe.empty_store()
    equivalence["enabled"] = bool(config.predictive_equivalence)
    relevance = prl.empty_meta()
    relevance["enabled"] = bool(config.predictive_relevance)
    temporal = tps.empty_store()
    temporal["enabled"] = bool(config.temporal_predictive_structure)
    tpb_meta = tpb.empty_meta()
    tpb_meta["enabled"] = bool(config.temporal_prospection_bridge)
    conflict = pcf.empty_store()
    conflict["enabled"] = bool(config.predictive_conflict)
    fsa_meta = fsa.empty_meta()
    fsa_meta["enabled"] = bool(config.future_sensitive_action)
    per_store = per.empty_store()
    per_store["enabled"] = bool(config.prediction_error_revision)
    tpe_store = tpe.empty_store()
    tpe_store["enabled"] = bool(config.temporal_prediction_error)
    pcp_meta = pcp.empty_meta()
    pcp_meta["enabled"] = bool(config.predicted_context_prospection)
    map_meta = mapr.empty_meta()
    map_meta["enabled"] = bool(config.multistep_action_prospection)
    return {
        "config": config.to_dict(),
        "compression": compression,
        "multiscale": multiscale,
        "prospection": prospection,
        "instrumental": instrumental,
        "equivalence": equivalence,
        "relevance": relevance,
        "temporal": temporal,
        "temporal_bridge": tpb_meta,
        "conflict": conflict,
        "future_action": fsa_meta,
        "prediction_revision": per_store,
        "temporal_prediction_error": tpe_store,
        "predicted_context_prospection": pcp_meta,
        "multistep_action_prospection": map_meta,
        "trace": empty_trace(config.causal_trace_capacity),
        "last_fragment": None,
        "last_action": None,
        "last_experience_event": None,
        "last_active_event": None,
        "pending_instrumental_fragment": None,
        "last_selection": None,
        "last_apply": None,
        "bridges": {
            "body_velocity_impulse_v1": "IMPLEMENTED",
            "agent_observation_body_local_v1": "IMPLEMENTED",
            "4.21_to_4.22_compressed_rep": "SHALLOW_FRAGMENT_RAW_ID_ONLY",
            "4.25_physical_emit_transducer_on_psr": "BRIDGE_MISSING",
        },
        "metrics": {
            "prediction_error_sum": 0.0,
            "prediction_count": 0,
            "prospective_compositions": 0,
            "novel_compositions": 0,
            "instrumental_acquired": 0,
            "instrumental_later_used": 0,
            "action_counts": {},
        },
    }


@dataclass
class CognitionTickResult:
    observation: dict[str, float]
    selected_action: str
    selection_source: str
    learn_events: dict[str, Any] = field(default_factory=dict)
    composition: dict[str, Any] = field(default_factory=dict)
    predictions: list[dict[str, Any]] = field(default_factory=list)
    selection_rule: str = ""
    actions: list[str] = field(default_factory=list)


def run_cognition_before_action(
    state: dict[str, Any],
    *,
    observation: dict[str, float],
    tick: int,
    rng_value: float,
) -> CognitionTickResult:
    """Learn from previous transition if any, then select next physical action."""
    hits = audit_cognition_payload(observation)
    if hits:
        raise RuntimeError(f"cognition received forbidden observation tokens: {hits}")

    cfg = state["config"]
    actions = list(available_actions())
    previous, previous_action = state.get("last_fragment"), state.get("last_action")
    trace = state["trace"]
    metrics = state["metrics"]
    learn_events: dict[str, Any] = {}
    eq_store = _equivalence_store(state)

    if isinstance(previous, dict) and previous_action:
        if cfg.get("prediction_error_revision"):
            per.realize(
                _per_store(state),
                observation=observation,
                tick=tick,
                last_action=str(previous_action),
            )
        if cfg.get("temporal_prediction_error"):
            tpe.ingest(
                _tpe_store(state),
                observation=observation,
                tick=tick,
                last_action=str(previous_action),
            )
        predicted = (
            pc.predict(state["compression"], previous, previous_action, domain="accessible")
            if cfg.get("retrieval")
            else {"status": "ABLATION"}
        )
        if (
            cfg.get("predictive_equivalence")
            and cfg.get("retrieval")
            and predicted.get("status") in {"NO_MATCH", "UNKNOWN", "ABLATION"}
        ):
            rel_meta = _relevance_meta(state)
            if cfg.get("predictive_relevance"):
                pe_found = prl.retrieve(eq_store, previous, previous_action, meta=rel_meta)
            else:
                pe_found = pe.retrieve(eq_store, previous, previous_action)
            if pe_found.get("status") == "MATCH":
                predicted = pe_found
        predicted_values = predicted.get("predicted") or predicted.get("mean_predicted") or {}
        if cfg.get("bounded_memory"):
            raw = pc.observe(
                state["compression"],
                tick=tick,
                fragment=previous,
                action=previous_action,
                predicted=predicted_values,
                realized=observation,
                domain="accessible",
            )
        else:
            raw = {"raw_id": None}
        exp_id = event(
            trace,
            tick=tick,
            kind="EXPERIENCE",
            mechanism="ordinary_observation",
            payload={"raw_id": raw.get("raw_id"), "action": previous_action},
        )
        if state.get("last_experience_event"):
            edge(
                trace,
                source=state["last_experience_event"],
                target=exp_id,
                tick=tick,
                mechanism="physical_recurrence",
                provenance="next_accessible_observation",
                relation="TEMPORALLY_ASSOCIATED",
            )
        state["last_experience_event"] = exp_id
        learn_events["experience"] = exp_id

        if cfg.get("multiscale_prediction") and cfg.get("bounded_memory"):
            lid = ms.ingest_local(
                state["multiscale"],
                tick=tick,
                domain="accessible",
                fragment=previous,
                action=previous_action,
                realized=observation,
                raw_id=raw.get("raw_id"),
            )
            if lid:
                sid = event(
                    trace,
                    tick=tick,
                    kind="PREDICTIVE_STRUCTURE_CHANGED",
                    mechanism="multiscale_prediction",
                    payload={"local_id": lid},
                )
                edge(
                    trace,
                    source=exp_id,
                    target=sid,
                    tick=tick,
                    mechanism="multiscale_prediction",
                    provenance={"raw_id": raw.get("raw_id")},
                    relation="CAUSALLY_SUPPORTED",
                )
                learn_events["multiscale_local"] = lid

        pr.learn_transition(
            state["prospection"],
            tick=tick,
            antecedent=previous,
            action=previous_action,
            consequent=observation,
        )
        tr_id = event(
            trace,
            tick=tick,
            kind="TRANSITION_CHANGED",
            mechanism="prospective_composition",
            payload={"action": previous_action},
        )
        edge(
            trace,
            source=exp_id,
            target=tr_id,
            tick=tick,
            mechanism="prospective_composition",
            provenance={"tick": tick},
            relation="CAUSALLY_SUPPORTED",
        )
        learn_events["transition"] = tr_id

        pending = state.get("pending_instrumental_fragment")
        if isinstance(pending, dict) and cfg.get("instrumental_observation"):
            # Store learning only — physical EMIT acquisition remains BRIDGE_MISSING on PSR.
            io.learn_prediction(state["instrumental"], pending, observation)
            state["pending_instrumental_fragment"] = None
            learn_events["instrumental_learn"] = True

        if cfg.get("predictive_equivalence"):
            pe_learn = pe.learn(
                eq_store,
                fragment=previous,
                action=previous_action,
                consequent=observation,
                tick=tick,
                raw_id=raw.get("raw_id"),
            )
            learn_events["predictive_equivalence"] = pe_learn
            if cfg.get("predictive_relevance"):
                learn_events["predictive_relevance"] = prl.refresh(
                    eq_store, tick=tick, meta=_relevance_meta(state)
                )

        tstore = _temporal_store(state)
        if cfg.get("temporal_predictive_structure"):
            learn_events["temporal_predictive_structure"] = tps.learn(
                tstore,
                consequent=observation,
                action=previous_action,
                tick=tick,
                raw_id=raw.get("raw_id"),
            )
            if cfg.get("predictive_relevance"):
                learn_events["temporal_relevance"] = tps.refresh_relevance(tstore, tick=tick)

        if predicted_values:
            err = sum(
                abs(float(observation.get(k, 0.0)) - float(predicted_values.get(k, 0.0)))
                for k in set(observation) | set(predicted_values)
            )
            metrics["prediction_error_sum"] += err
            metrics["prediction_count"] += 1

    tstore = _temporal_store(state)
    if cfg.get("temporal_predictive_structure") and isinstance(observation, dict):
        tps.append(tstore, observation)

    predictions: list[dict[str, Any]] = []
    last_pe_diag: dict[str, Any] = {}
    last_tps_diag: dict[str, Any] = {}
    if cfg.get("retrieval"):
        for action in actions:
            found = pc.predict(state["compression"], observation, action, domain="accessible")
            source = "compression"
            if (
                cfg.get("temporal_predictive_structure")
                and found.get("status") in {"NO_MATCH", "UNKNOWN", "ABLATION"}
            ):
                tmeta = tstore.get("relevance") if cfg.get("predictive_relevance") else None
                t_found = tps.retrieve(tstore, observation, action, meta=tmeta)
                if t_found.get("status") == "MATCH":
                    found = t_found
                    source = "temporal_predictive_structure"
                elif t_found.get("status") == "TEMPORAL_CONFLICT":
                    for cand in t_found.get("candidates") or []:
                        predictions.append(
                            {
                                "action": action,
                                "source": "temporal_predictive_structure",
                                "result": cand,
                                "temporal_conflict": True,
                                "next_gear_missing": True,
                            }
                        )
            if (
                cfg.get("predictive_equivalence")
                and found.get("status") in {"NO_MATCH", "UNKNOWN", "ABLATION"}
            ):
                rel_meta = _relevance_meta(state)
                if cfg.get("predictive_relevance"):
                    pe_found = prl.retrieve(eq_store, observation, action, meta=rel_meta)
                    if pe_found.get("status") == "MATCH":
                        found = pe_found
                        source = "predictive_relevance"
                    elif pe_found.get("status") == "CONFLICT":
                        found = pe_found
                        source = "predictive_relevance"
                else:
                    pe_found = pe.retrieve(eq_store, observation, action)
                    if pe_found.get("status") == "MATCH":
                        found = pe_found
                        source = "predictive_equivalence"
            if found.get("status") not in {"NO_MATCH", "UNKNOWN", "ABLATION", "DISABLED", "CONFLICT", "TEMPORAL_CONFLICT"}:
                predictions.append({"action": action, "source": source, "result": found})
        wait_act = actions[0] if actions else "WAIT"
        if cfg.get("predictive_equivalence") and isinstance(observation, dict):
            if cfg.get("predictive_relevance"):
                last_pe_diag = prl.diagnostic(eq_store, observation, wait_act, meta=_relevance_meta(state))
            else:
                last_pe_diag = pe.diagnostic(eq_store, observation, wait_act)
        if cfg.get("temporal_predictive_structure") and isinstance(observation, dict):
            last_tps_diag = tps.diagnostic(tstore, observation, wait_act)

    entry_steps: list[dict[str, Any]] = []
    last_tpb_diag: dict[str, Any] = {}
    tpb_meta = _temporal_bridge_meta(state)
    if (
        cfg.get("temporal_prospection_bridge")
        and cfg.get("temporal_predictive_structure")
        and cfg.get("prospective_composition")
        and isinstance(observation, dict)
    ):
        tmeta = tstore.get("relevance") if cfg.get("predictive_relevance") else None
        entry_steps = tpb.collect_entry_steps(
            tstore,
            observation,
            actions,
            meta=tpb_meta,
            tps_meta=tmeta,
            predictions=predictions,
        )
        if cfg.get("prediction_error_revision"):
            entry_steps = per.filter_entry_steps(_per_store(state), entry_steps)

    composition = pr.compose_trajectories(
        state["prospection"],
        start=observation,
        max_depth=int(cfg.get("prospective_depth") or 3),
        branch_actions=actions,
        entry_steps=entry_steps or None,
    )
    if entry_steps:
        last_tpb_diag = tpb.diagnostic(entry_steps, composition)
    continuations = composition.get("continuations") or []
    if cfg.get("prediction_error_revision"):
        continuations = per.filter_continuations(_per_store(state), continuations)
        composition = {**composition, "continuations": continuations}
    conflict_org: dict[str, Any] = {"status": "DISABLED", "candidates": []}
    last_conflict_diag: dict[str, Any] = {}
    last_fsa_diag: dict[str, Any] = {}
    last_per_diag: dict[str, Any] = {}
    last_tpe_diag: dict[str, Any] = {}
    last_pcp_diag: dict[str, Any] = {}
    pcp_branches: list[dict[str, Any]] = []
    last_map_diag: dict[str, Any] = {}
    map_branches: list[dict[str, Any]] = []
    if (
        cfg.get("predicted_context_prospection")
        and cfg.get("temporal_predictive_structure")
        and isinstance(observation, dict)
    ):
        pmeta = _pcp_meta(state)
        pmeta["enabled"] = True
        tmeta = tstore.get("relevance") if cfg.get("predictive_relevance") else None
        pcp_branches = pcp.collect(
            tps_store=tstore,
            prospection=state["prospection"],
            present=observation,
            actions=actions,
            predictions=predictions,
            tps_meta=tmeta,
            meta=pmeta,
            max_depth=int(cfg.get("prospective_depth") or 3),
        )
        if pcp_branches:
            continuations = list(continuations) + list(pcp_branches)
            composition = {**composition, "continuations": continuations}
        last_pcp_diag = pcp.diagnostic(pmeta, pcp_branches, observation)
        last_pcp_diag["observer"] = pcp.observer_panel(
            present=observation,
            recent=(last_tps_diag or {}).get("recent"),
            branches=pcp_branches,
            tps_diag=last_tps_diag,
        )
    if cfg.get("multistep_action_prospection") and isinstance(observation, dict):
        mmeta = _map_meta(state)
        mmeta["enabled"] = True
        map_branches = mapr.collect(
            store=state["prospection"],
            present=observation,
            actions=actions,
            continuations=continuations,
            meta=mmeta,
            max_depth=int(cfg.get("prospective_depth") or 3),
        )
        if map_branches:
            # Keep snapshot/pcp roots; annotated/filled chains replace the working list
            # so first_action vs future_actions is visible downstream. No store write.
            by_path: dict[tuple[Any, ...], dict[str, Any]] = {}
            for c in list(continuations) + list(map_branches):
                acts = tuple(str(a) for a in (c.get("actions") or []))
                by_path[acts] = c
            continuations = list(by_path.values())
            composition = {**composition, "continuations": continuations}
        last_map_diag = mapr.diagnostic(mmeta, map_branches, observation)
        last_map_diag["observer"] = mapr.observer_panel(
            present=observation,
            branches=map_branches,
        )
    if cfg.get("predictive_conflict"):
        cstore = _conflict_store(state)
        cstore["enabled"] = True
        last_act = state.get("last_action")
        conflict_org = pcf.organize(
            cstore,
            continuations,
            realized=observation if last_act else None,
            last_action=str(last_act) if last_act else None,
        )
        last_conflict_diag = pcf.diagnostic(cstore)
    instrumental_prediction = (
        io.predict(state["instrumental"], observation)
        if cfg.get("instrumental_observation")
        else {"status": "ABLATED"}
    )
    if continuations:
        metrics["prospective_compositions"] += 1
        metrics["novel_compositions"] += int(any(int(x.get("depth", 0)) > 1 for x in continuations))

    selected = None
    selected_source = "ENDOGENOUS_VARIATION"
    selection_rule = "ENDOGENOUS_INDEX: actions[floor(rng*len(actions))] when no prospective/prediction winner"
    selection_mode = str(cfg.get("prospective_selection") or "SCENARIO_COMPETITION")
    competition_result: dict[str, Any] = {"outcome_class": "NOT_RUN", "mode": selection_mode}
    scenario_groups_public: dict[str, Any] = {}
    peer_evaluation = "NONE"

    if cfg.get("prospective_composition"):
        if selection_mode == "LEGACY_FIRST":
            # Control / reproducibility only — preserves diagnosis baseline privilege.
            if continuations:
                leg = sc.legacy_first_select(continuations)
                selected = leg["selected"]
                selected_source = leg["source"]
                selection_rule = leg["selection_rule"]
                competition_result = leg.get("competition") or {}
                peer_evaluation = "NONE — LEGACY_FIRST list-position privilege"
            elif predictions:
                selected = str(max(predictions, key=lambda x: int(x["result"].get("support", 0)))["action"])
                selected_source = "RETAINED_PREDICTION"
                selection_rule = "RETAINED_PREDICTION: argmax support among compression matches"
                peer_evaluation = "COMPRESSION_SUPPORT_ONLY"
        else:
            # SCENARIO_COMPETITION: composition discovers; competition selects.
            fsa_meta = _future_action_meta(state)
            if cfg.get("future_sensitive_action"):
                fsa_meta["enabled"] = True
                groups = fsa.build_groups(
                    store=state["prospection"],
                    observation=observation,
                    continuations=continuations,
                    actions=actions,
                    conflict_candidates=(conflict_org.get("candidates") or []),
                    action_counts=(state.get("metrics") or {}).get("action_counts") or {},
                    meta=fsa_meta,
                )
            else:
                groups = sc.collect_scenario_groups(
                    store=state["prospection"],
                    observation=observation,
                    continuations=continuations,
                    actions=actions,
                )
            if cfg.get("prediction_error_revision"):
                groups = per.filter_groups(_per_store(state), groups)
            scenario_groups_public = {
                a: {
                    "supported": bool(groups.get(a)),
                    "count": len(groups.get(a) or []),
                    "scenarios": groups.get(a) or [],
                }
                for a in actions
            }
            comp = sc.compete_scenarios(groups=groups, actions=actions, rng_value=rng_value)
            competition_result = comp.get("competition") or {}
            competition_result["mode"] = selection_mode
            if cfg.get("future_sensitive_action"):
                competition_result["future_sensitive"] = True
                competition_result["not_new_policy"] = True
                last_fsa_diag = fsa.diagnostic(
                    _future_action_meta(state),
                    fsa.observer_panel(
                        groups,
                        competition_result,
                        selected=comp.get("selected"),
                        realized=None,
                    ),
                )
            if comp.get("selected") is not None:
                selected = str(comp["selected"])
                selected_source = str(comp["source"])
                selection_rule = str(comp["selection_rule"])
                peer_evaluation = (
                    "SCENARIO_COMPETITION — lexicographic dominance on "
                    "(historical_support, reliability, depth); list order unused"
                )
            elif predictions:
                selected = str(max(predictions, key=lambda x: int(x["result"].get("support", 0)))["action"])
                selected_source = "RETAINED_PREDICTION"
                selection_rule = "RETAINED_PREDICTION: argmax support among compression matches (no prospective support)"
                peer_evaluation = "COMPRESSION_SUPPORT_ONLY"
            else:
                peer_evaluation = "SCENARIO_COMPETITION — no supported scenarios; defer fallback"
    elif predictions:
        selected = str(max(predictions, key=lambda x: int(x["result"].get("support", 0)))["action"])
        selected_source = "RETAINED_PREDICTION"
        selection_rule = "RETAINED_PREDICTION: argmax support among compression matches"
        peer_evaluation = "COMPRESSION_SUPPORT_ONLY"

    if selected not in actions:
        selected = actions[min(len(actions) - 1, int(float(rng_value) * len(actions)))]
        selected_source = "ENDOGENOUS_VARIATION"
        selection_rule = "ENDOGENOUS_INDEX: actions[floor(rng*len(actions))] fallback"
        if competition_result.get("outcome_class") == "NO_SUPPORT":
            competition_result["fallback"] = "ENDOGENOUS_VARIATION"

    probe_enabled = bool(cfg.get("unknown_action_physical_probe"))
    if probe_enabled:
        probe_cls = classify_unmodeled_actions(
            store=state["prospection"],
            observation=observation,
            supported_actions=list(competition_result.get("supported_actions") or []),
            actions=actions,
        )
        probe_info = probe_receipt(enabled=True, classification=probe_cls)
    else:
        probe_info = probe_receipt(enabled=False)
    # DESIGN_BOUNDARY: do not change selected / selected_source.

    pred_event = event(
        trace,
        tick=tick,
        kind="PREDICTION_RETRIEVAL",
        mechanism=selected_source,
        payload={"selected_action": selected, "match_count": len(predictions)},
    )
    if state.get("last_experience_event") and (predictions or continuations):
        edge(
            trace,
            source=state["last_experience_event"],
            target=pred_event,
            tick=tick,
            mechanism=selected_source,
            provenance="runtime_retrieval",
            relation="CAUSALLY_SUPPORTED",
        )
    action_event = event(
        trace,
        tick=tick,
        kind="ACTION_SELECTED",
        mechanism="current_mm_cognition",
        payload={"action": selected, "source": selected_source},
    )
    edge(
        trace,
        source=pred_event,
        target=action_event,
        tick=tick,
        mechanism="action_selection",
        provenance=selected_source,
        relation="CAUSALLY_SUPPORTED",
    )
    if state.get("last_active_event") and instrumental_prediction.get("status") == "MATCH":
        edge(
            trace,
            source=state["last_active_event"],
            target=pred_event,
            tick=tick,
            mechanism="instrumental_observation",
            provenance="acquired_fragment_retrieved",
            relation="CAUSALLY_SUPPORTED",
        )
        metrics["instrumental_later_used"] += 1

    metrics["action_counts"][selected] = int(metrics["action_counts"].get(selected, 0)) + 1
    if cfg.get("prediction_error_revision"):
        per.pending_from_selection(
            _per_store(state),
            selected=str(selected),
            continuations=continuations,
            tick=tick,
            predictions=predictions,
            entry_steps=entry_steps,
        )
        last_per_diag = per.diagnostic(
            _per_store(state),
            competition_after=competition_result,
            selected=selected,
        )
    if cfg.get("temporal_prediction_error"):
        tpe.pending_from_selection(
            _tpe_store(state),
            selected=str(selected),
            continuations=continuations,
            tick=tick,
            predictions=predictions,
            entry_steps=entry_steps,
        )
        last_tpe_diag = tpe.diagnostic(
            _tpe_store(state),
            selected=selected,
            competition=competition_result,
            eligible=None,
        )
    if last_pcp_diag:
        last_pcp_diag["selected_now"] = selected
        obs = last_pcp_diag.get("observer")
        if isinstance(obs, dict):
            obs["SELECTED NOW"] = selected
            obs["CURRENT FIRST ACTION"] = last_pcp_diag.get("first_present_actions") or obs.get("CURRENT FIRST ACTION")
    if last_map_diag:
        last_map_diag = mapr.diagnostic(
            _map_meta(state) if cfg.get("multistep_action_prospection") else last_map_diag,
            map_branches,
            observation,
            selected=str(selected) if selected else None,
        )
        last_map_diag["observer"] = mapr.observer_panel(
            present=observation,
            branches=map_branches,
            selected=str(selected) if selected else None,
        )
    if cfg.get("bounded_memory"):
        pc.purge_redundant_raw(state["compression"], keep_recent=True)

    if isinstance(observation, dict):
        state["last_fragment"] = (
            dict(observation) if _USE_TICK_LOCAL_RETAIN else deepcopy(observation)
        )
    else:
        state["last_fragment"] = observation
    state["last_action"] = selected
    state["last_selection"] = {
        "action": selected,
        "source": selected_source,
        "candidates": actions,
        "prediction_matches": _retain_tick_local_list(predictions, limit=8),
        "continuations": _retain_tick_local_list(continuations, limit=8),
        "instrumental_prediction": _retain_tick_local(instrumental_prediction),
        "action_event": action_event,
        "selection_rule": selection_rule,
        "composition_meta": {
            "expansion_count": composition.get("expansion_count"),
            "max_depth_reached": composition.get("max_depth_reached"),
            "composition_enabled": composition.get("composition_enabled"),
        },
        "peer_evaluation": peer_evaluation,
        "prospective_selection_mode": selection_mode,
        "scenario_groups": _retain_tick_local(scenario_groups_public),
        "competition": _retain_tick_local(competition_result),
        "unknown_action_probe": _retain_tick_local(probe_info),
        "equivalence_diagnostic": _retain_tick_local(last_pe_diag),
        "temporal_diagnostic": _retain_tick_local(last_tps_diag),
        "temporal_bridge_diagnostic": _retain_tick_local(last_tpb_diag),
        "temporal_entry_steps": _retain_tick_local_list(entry_steps, limit=8),
        "predictive_conflict": _retain_tick_local(conflict_org),
        "conflict_diagnostic": _retain_tick_local(last_conflict_diag),
        "future_sensitive_action": _retain_tick_local(last_fsa_diag),
        "prediction_error_revision": _retain_tick_local(last_per_diag),
        "temporal_prediction_error": _retain_tick_local(last_tpe_diag),
        "predicted_context_prospection": _retain_tick_local(last_pcp_diag),
        "predicted_context_branches": _retain_tick_local_list(pcp_branches, limit=8),
        "multistep_action_prospection": _retain_tick_local(last_map_diag),
        "multistep_action_branches": _retain_tick_local_list(map_branches, limit=8),
    }
    return CognitionTickResult(
        observation=observation,
        selected_action=selected,
        selection_source=selected_source,
        learn_events=learn_events,
        composition=composition,
        predictions=predictions,
        selection_rule=selection_rule,
        actions=list(actions),
    )


def _equivalence_store(state: dict[str, Any]) -> dict[str, Any]:
    store = state.get("equivalence")
    if not isinstance(store, dict):
        store = pe.empty_store()
        state["equivalence"] = store
    store["enabled"] = bool((state.get("config") or {}).get("predictive_equivalence"))
    return store


def _relevance_meta(state: dict[str, Any]) -> dict[str, Any]:
    meta = state.get("relevance")
    if not isinstance(meta, dict):
        meta = prl.empty_meta()
        state["relevance"] = meta
    meta["enabled"] = bool((state.get("config") or {}).get("predictive_relevance"))
    return meta


def _temporal_store(state: dict[str, Any]) -> dict[str, Any]:
    store = state.get("temporal")
    if not isinstance(store, dict):
        store = tps.empty_store()
        state["temporal"] = store
    store["enabled"] = bool((state.get("config") or {}).get("temporal_predictive_structure"))
    return store


def _temporal_bridge_meta(state: dict[str, Any]) -> dict[str, Any]:
    meta = state.get("temporal_bridge")
    if not isinstance(meta, dict):
        meta = tpb.empty_meta()
        state["temporal_bridge"] = meta
    meta["enabled"] = bool((state.get("config") or {}).get("temporal_prospection_bridge"))
    return meta


def _conflict_store(state: dict[str, Any]) -> dict[str, Any]:
    store = state.get("conflict")
    if not isinstance(store, dict):
        store = pcf.empty_store()
        state["conflict"] = store
    store["enabled"] = bool((state.get("config") or {}).get("predictive_conflict"))
    return store


def _future_action_meta(state: dict[str, Any]) -> dict[str, Any]:
    meta = state.get("future_action")
    if not isinstance(meta, dict):
        meta = fsa.empty_meta()
        state["future_action"] = meta
    meta["enabled"] = bool((state.get("config") or {}).get("future_sensitive_action"))
    return meta


def _per_store(state: dict[str, Any]) -> dict[str, Any]:
    store = state.get("prediction_revision")
    if not isinstance(store, dict):
        store = per.empty_store()
        state["prediction_revision"] = store
    store["enabled"] = bool((state.get("config") or {}).get("prediction_error_revision"))
    return store


def _tpe_store(state: dict[str, Any]) -> dict[str, Any]:
    store = state.get("temporal_prediction_error")
    if not isinstance(store, dict):
        store = tpe.empty_store()
        state["temporal_prediction_error"] = store
    store["enabled"] = bool((state.get("config") or {}).get("temporal_prediction_error"))
    return store


def _pcp_meta(state: dict[str, Any]) -> dict[str, Any]:
    meta = state.get("predicted_context_prospection")
    if not isinstance(meta, dict):
        meta = pcp.empty_meta()
        state["predicted_context_prospection"] = meta
    meta["enabled"] = bool((state.get("config") or {}).get("predicted_context_prospection"))
    return meta


def _map_meta(state: dict[str, Any]) -> dict[str, Any]:
    meta = state.get("multistep_action_prospection")
    if not isinstance(meta, dict):
        meta = mapr.empty_meta()
        state["multistep_action_prospection"] = meta
    meta["enabled"] = bool((state.get("config") or {}).get("multistep_action_prospection"))
    return meta


def cognition_public_view(state: dict[str, Any]) -> dict[str, Any]:
    """Researcher-facing cognitive panels (no world truth)."""
    sel = state.get("last_selection") or {}
    return {
        "mechanisms": deepcopy(state.get("config") or {}),
        "bridges": deepcopy(state.get("bridges") or {}),
        "memory": pc.snapshot(state["compression"]),
        "predictive_organization": ms.snapshot(state["multiscale"]),
        "prospection": {
            **pr.snapshot(state["prospection"]),
            "current": deepcopy((sel.get("continuations") or [])[:8]),
        },
        "instrumental_observation": {
            **io.snapshot(state["instrumental"]),
            "physical_emit_path": "BRIDGE_MISSING",
            "current_prediction": deepcopy(sel.get("instrumental_prediction") or {}),
        },
        "action": {
            "candidates": list(sel.get("candidates") or available_actions()),
            "selected": sel.get("action"),
            "source": sel.get("source"),
            "prediction_matches": deepcopy(sel.get("prediction_matches") or []),
            "last_apply": deepcopy(state.get("last_apply")),
            "selection_rule": sel.get("selection_rule"),
            "peer_evaluation": sel.get("peer_evaluation", "NONE"),
            "composition_meta": sel.get("composition_meta"),
            "prospective_selection_mode": sel.get("prospective_selection_mode"),
            "scenario_groups": deepcopy(sel.get("scenario_groups") or {}),
            "competition": deepcopy(sel.get("competition") or {}),
            "unknown_action_probe": deepcopy(sel.get("unknown_action_probe") or {"enabled": False}),
        },
        "last_decision_receipt": deepcopy(state.get("last_decision_receipt")),
        "causal_trace": {
            "events": deepcopy(state["trace"]["events"][-64:]),
            "edges": deepcopy(state["trace"]["edges"][-192:]),
            "capacity": state["trace"]["capacity"],
        },
        "metrics": deepcopy(state.get("metrics") or {}),
        "predictive_equivalence": {
            **pe.snapshot(_equivalence_store(state)),
            "enabled": bool((state.get("config") or {}).get("predictive_equivalence")),
            "last": deepcopy(sel.get("equivalence_diagnostic") or {}),
            "note": "LEARNED_PREDICTIVE_REPRESENTATION — not physical ground truth",
        },
        "predictive_relevance": {
            **prl.snapshot(_equivalence_store(state), _relevance_meta(state)),
            "last": deepcopy(sel.get("equivalence_diagnostic") or {})
            if (sel.get("equivalence_diagnostic") or {}).get("kind") == "LEARNED_RELEVANCE_STRUCTURE"
            else {},
        },
        "temporal_predictive_structure": {
            **tps.snapshot(_temporal_store(state)),
            "enabled": bool((state.get("config") or {}).get("temporal_predictive_structure")),
            "last": deepcopy(sel.get("temporal_diagnostic") or {}),
            "note": "TEMPORAL_PREDICTIVE_STRUCTURE — not time perception, not a clock",
        },
        "temporal_prospection_bridge": {
            **tpb.snapshot(_temporal_bridge_meta(state)),
            "enabled": bool((state.get("config") or {}).get("temporal_prospection_bridge")),
            "last": deepcopy(sel.get("temporal_bridge_diagnostic") or {}),
            "entry_steps": deepcopy(sel.get("temporal_entry_steps") or []),
            "note": "TEMPORAL_PROSPECTION_BRIDGE — transport only, not planning",
        },
        "predictive_conflict": {
            **pcf.snapshot(_conflict_store(state)),
            "enabled": bool((state.get("config") or {}).get("predictive_conflict")),
            "last": deepcopy(sel.get("conflict_diagnostic") or {}),
            "organize": deepcopy(sel.get("predictive_conflict") or {}),
            "note": "PREDICTIVE_CONFLICT — not doubt, not belief, not choice",
        },
        "future_sensitive_action": {
            **fsa.snapshot(_future_action_meta(state)),
            "enabled": bool((state.get("config") or {}).get("future_sensitive_action")),
            "last": deepcopy(sel.get("future_sensitive_action") or {}),
            "note": "FUTURE_SENSITIVE_ACTION — not utility, not preference, not a new policy",
        },
        "prediction_error_revision": {
            **per.snapshot(_per_store(state)),
            "enabled": bool((state.get("config") or {}).get("prediction_error_revision")),
            "last": deepcopy(sel.get("prediction_error_revision") or {}),
            "note": "PREDICTION_ERROR_REVISION — not punishment, not trust, not policy",
        },
        "temporal_prediction_error": {
            **tpe.snapshot(_tpe_store(state)),
            "enabled": bool((state.get("config") or {}).get("temporal_prediction_error")),
            "last": deepcopy(sel.get("temporal_prediction_error") or {}),
            "note": "TEMPORAL_PREDICTION_ERROR — residual fragments, not drift detection",
        },
        "predicted_context_prospection": {
            **pcp.snapshot(_pcp_meta(state)),
            "enabled": bool((state.get("config") or {}).get("predicted_context_prospection")),
            "last": deepcopy(sel.get("predicted_context_prospection") or {}),
            "branches": deepcopy(sel.get("predicted_context_branches") or []),
            "observer": deepcopy((sel.get("predicted_context_prospection") or {}).get("observer") or {}),
            "note": "PREDICTED CONTEXT PROSPECTION — not imagined experience, not a policy",
        },
        "multistep_action_prospection": {
            **mapr.snapshot(_map_meta(state)),
            "enabled": bool((state.get("config") or {}).get("multistep_action_prospection")),
            "last": deepcopy(sel.get("multistep_action_prospection") or {}),
            "branches": deepcopy(sel.get("multistep_action_branches") or []),
            "observer": deepcopy((sel.get("multistep_action_prospection") or {}).get("observer") or {}),
            "note": "MULTI-STEP ACTION PROSPECTION — not planning, not a policy",
        },
    }
