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
from mechanistic_mind.research import contextual_predictive_organization as cpo
from mechanistic_mind.research import context_grounded_prospection as cgp
from mechanistic_mind.research import persistent_prospective_control as ppc
from mechanistic_mind.research import contextual_stack_bridge as csb
from mechanistic_mind.research import multistep_action_prospection as mapr

from .actions import OSC_ACTIONS, available_actions
from . import sensorimotor_consequence as smc
from . import o_prime_history_bridge as oph
from . import observed_composite_psc as ocpsc
from .composite_motor import (
    LEGACY_SCHEMA,
    MOTOR_SCHEMA,
    CompositeMotorOutput,
    build_composite_from_factorized,
    locomotion_options,
    select_factorized_side_channels,
)
from .observation import audit_cognition_payload
from .unknown_action_probe import classify_unmodeled_actions, probe_receipt

# BETA2-03: retain tick-local last_selection payloads without deepcopy.
# Set False to restore BETA2-02 deepcopy retention for equivalence harnesses.
_USE_TICK_LOCAL_RETAIN = True


def set_tick_local_retain(enabled: bool) -> None:
    global _USE_TICK_LOCAL_RETAIN
    _USE_TICK_LOCAL_RETAIN = bool(enabled)




def _enrich_groups_with_smc(
    groups: dict[str, list],
    *,
    observation: dict[str, float],
    smc_preds: list[dict[str, Any]],
    withhold: bool,
) -> dict[str, list]:
    """Add/augment scenarios with SMC predicted fragments — support/reliability only."""
    if withhold or not smc_preds:
        return groups
    out = {k: list(v or []) for k, v in (groups or {}).items()}
    for pred in smc_preds:
        if pred.get("status") not in {smc.MATCH, smc.LOW_SUPPORT}:
            continue
        loco = str(pred.get("candidate_locomotion") or "")
        if not loco:
            continue
        o_hat = smc.apply_predicted_to_observation(observation, pred.get("predicted_delta"))
        scn = {
            "scenario_id": f"smc:{pred.get('record_id')}:{loco}",
            "source_structure_ids": [pred.get("record_id")],
            "provenance": {"path": "sensorimotor_consequence", "record_id": pred.get("record_id")},
            "action_sequence": [loco],
            "first_action": loco,
            "depth": 1,
            "historical_support": int(pred.get("support") or 0),
            "historical_support_raw": pred.get("support"),
            "reliability": float(pred.get("reliability") or 0.5),
            "reliability_raw": pred.get("reliability"),
            "current_match_evidence": pred,
            "predicted_state_fragments": o_hat,
            "predicted_body_fragments": "NOT_AVAILABLE",
            "predicted_environment_fragments": "NOT_AVAILABLE",
            "composition_path": [pred],
            "score_reliability_path": pred.get("reliability"),
            "sensorimotor_consequence": True,
        }
        out.setdefault(loco, []).append(scn)
    return out

def _smc_store(state: dict[str, Any]) -> dict[str, Any]:
    store = state.get("sensorimotor_consequence")
    if not isinstance(store, dict):
        store = smc.empty_store(enabled=False)
        state["sensorimotor_consequence"] = store
    return store

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
    # COMPOSITE_MOTOR_V1: one cognitive cycle → structured multi-domain motor output.
    # Default ON. Does not add skills, turn-taking, or Cartesian action tokens.
    composite_motor: bool = True
    # Experimental: action-conditioned (O,M)→ΔS store. Default OFF.
    # Learns accessible sensory consequences of self motors; no reward/seeking.
    sensorimotor_consequence_model: bool = False
    # When True with model enabled: learn store but do not attach predictions to PSC.
    sensorimotor_consequence_withhold_from_psc: bool = False
    # Experiment control: shuffle motor labels during learning (breaks conditioning).
    sensorimotor_consequence_shuffle_motors: bool = False
    # When False: osc_l_*/osc_r_* remain in observation but are WITHHELD from SMC / O′.
    sensorimotor_consequence_bilateral: bool = True
    # Optional family WITHHELD map: visual/field/vestibular/proprioceptive/
    # bilateral/local_world/body/internal → bool. None = all ON (full embodied).
    sensorimotor_consequence_families: dict | None = None
    # O′ → existing history retrieval → PSC (default OFF)
    historical_sensorimotor_selection_bridge: bool = False
    historical_sensorimotor_selection_withhold: bool = False
    historical_sensorimotor_selection_shuffle: bool = False  # O′↔history mismatch control
    # Experimental 4.26: higher-order contextual predictive organization. Default OFF.
    contextual_predictive_organization: bool = False
    contextual_predictive_organization_ablate: bool = False
    contextual_predictive_organization_shuffle: bool = False
    # Experimental 4.27: prospection over contextual structures. Default OFF.
    context_grounded_prospection: bool = False
    context_grounded_prospection_ablate: bool = False
    context_grounded_prospection_shuffle: bool = False
    # Experimental 4.28: support-gated persistent prospective control. Default OFF.
    persistent_prospective_control: bool = False
    persistent_prospective_control_ablate: bool = False
    persistent_prospective_control_ablate_chunks: bool = False
    # PSC motor resolution: LOCO_FACTORIZED (default/legacy) | OBSERVED_COMPOSITE (experimental).
    # Missing/legacy configs resolve to LOCO_FACTORIZED. Do not silently migrate.
    psc_motor_resolution: str = "LOCO_FACTORIZED"

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
            "composite_motor": self.composite_motor,
            "sensorimotor_consequence_model": self.sensorimotor_consequence_model,
            "sensorimotor_consequence_withhold_from_psc": self.sensorimotor_consequence_withhold_from_psc,
            "sensorimotor_consequence_shuffle_motors": self.sensorimotor_consequence_shuffle_motors,
            "sensorimotor_consequence_bilateral": self.sensorimotor_consequence_bilateral,
            "sensorimotor_consequence_families": self.sensorimotor_consequence_families,
            "historical_sensorimotor_selection_bridge": self.historical_sensorimotor_selection_bridge,
            "historical_sensorimotor_selection_withhold": self.historical_sensorimotor_selection_withhold,
            "historical_sensorimotor_selection_shuffle": self.historical_sensorimotor_selection_shuffle,
            "contextual_predictive_organization": bool(getattr(self, "contextual_predictive_organization", False)),
            "contextual_predictive_organization_ablate": bool(getattr(self, "contextual_predictive_organization_ablate", False)),
            "contextual_predictive_organization_shuffle": bool(getattr(self, "contextual_predictive_organization_shuffle", False)),
            "context_grounded_prospection": bool(getattr(self, "context_grounded_prospection", False)),
            "context_grounded_prospection_ablate": bool(getattr(self, "context_grounded_prospection_ablate", False)),
            "context_grounded_prospection_shuffle": bool(getattr(self, "context_grounded_prospection_shuffle", False)),
            "persistent_prospective_control": bool(getattr(self, "persistent_prospective_control", False)),
            "persistent_prospective_control_ablate": bool(getattr(self, "persistent_prospective_control_ablate", False)),
            "persistent_prospective_control_ablate_chunks": bool(getattr(self, "persistent_prospective_control_ablate_chunks", False)),
            "psc_motor_resolution": str(getattr(self, "psc_motor_resolution", "LOCO_FACTORIZED") or "LOCO_FACTORIZED"),
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
    smc_store = smc.empty_store(
        enabled=bool(config.sensorimotor_consequence_model),
        bilateral=bool(getattr(config, "sensorimotor_consequence_bilateral", True)),
        families=getattr(config, "sensorimotor_consequence_families", None),
    )
    smc_store["shuffle_motor_labels"] = bool(config.sensorimotor_consequence_shuffle_motors)

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
    cpo_store = cpo.empty_store()
    cpo_store["enabled"] = bool(getattr(config, "contextual_predictive_organization", False))
    cpo_store["ablate_higher_order"] = bool(getattr(config, "contextual_predictive_organization_ablate", False))
    cpo_store["ablate_predictive_use"] = bool(getattr(config, "contextual_predictive_organization_ablate", False))
    cpo_store["shuffle_members"] = bool(getattr(config, "contextual_predictive_organization_shuffle", False))
    cgp_store = cgp.empty_store()
    cgp_store["enabled"] = bool(getattr(config, "context_grounded_prospection", False))
    cgp_store["ablate_composition"] = bool(getattr(config, "context_grounded_prospection_ablate", False))
    cgp_store["shuffle_relations"] = bool(getattr(config, "context_grounded_prospection_shuffle", False))
    ppc_store = ppc.empty_store()
    ppc_store["enabled"] = bool(getattr(config, "persistent_prospective_control", False))
    ppc_store["ablate_persistence"] = bool(getattr(config, "persistent_prospective_control_ablate", False))
    ppc_store["ablate_motor_chunks"] = bool(getattr(config, "persistent_prospective_control_ablate_chunks", False))
    return {
        "config": config.to_dict(),
        "compression": compression,
        "multiscale": multiscale,
        "prospection": prospection,
        "sensorimotor_consequence": smc_store,
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
        "contextual_organization": cpo_store,
        "context_grounded_prospection": cgp_store,
        "persistent_prospective_control": ppc_store,
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
    motor_output: dict[str, Any] | None = None


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
    actions = list(state.get("available_actions") or available_actions())
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
        # 4.26–4.28: contextual organization / context transitions / PPC advance
        state["_contextual_stack_experience"] = csb.on_experience(
            state,
            tick=tick,
            previous=previous if isinstance(previous, dict) else None,
            observation=observation if isinstance(observation, dict) else None,
            previous_action=str(previous_action) if previous_action else None,
            cfg=cfg,
        )
        # Action-conditioned sensorimotor consequence (composite motor → ΔS)
        smc_store = _smc_store(state)
        smc_store["enabled"] = bool(cfg.get("sensorimotor_consequence_model"))
        smc.set_bilateral(smc_store, bool(cfg.get("sensorimotor_consequence_bilateral", True)))
        _fam = cfg.get("sensorimotor_consequence_families")
        if isinstance(_fam, dict):
            smc.set_families(smc_store, **{str(k): bool(v) for k, v in _fam.items()})
        smc_store["shuffle_motor_labels"] = bool(cfg.get("sensorimotor_consequence_shuffle_motors"))
        last_motor = state.get("last_motor_output")
        if isinstance(last_motor, dict) and smc_store.get("enabled"):
            smc_receipt = smc.update(
                smc_store,
                tick=tick,
                observation_t=previous,
                motor=last_motor,
                observation_t1=observation,
            )
            learn_events["sensorimotor_consequence"] = smc_receipt
            state["last_sensorimotor_update"] = {
                "kind": "SENSORIMOTOR_CONSEQUENCE_UPDATED",
                "tick": int(tick),
                "receipt": smc_receipt,
            }
            # Dual-write into prospective store under COMPOSITE motor signature so
            # existing PSC MATCH support can condition on full motor organization.
            # Predicted consequent = previous + mean pathway is handled at query time;
            # here we also learn full observation under motor signature key.
            m_sig = smc.motor_signature_from_composite(
                last_motor,
                shuffle_salt=int(tick) if smc_store.get("shuffle_motor_labels") else None,
            )
            pr.learn_transition(
                state["prospection"],
                tick=tick,
                antecedent=previous,
                action=m_sig,
                consequent=observation,
            )
            # Component-conditioned keys so neck/loco side channels can MATCH.
            loco = str(last_motor.get("locomotion") or "WAIT")
            neck = str(last_motor.get("neck") or "NONE")
            if neck and neck not in ("NONE", "NECK_HOLD", ""):
                pr.learn_transition(
                    state["prospection"],
                    tick=tick,
                    antecedent=previous,
                    action=neck,
                    consequent=observation,
                )
            # Loco-only signature for candidate queries
            pr.learn_transition(
                state["prospection"],
                tick=tick,
                antecedent=previous,
                action=smc.motor_signature_loco_only(loco),
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

    # 4.27/4.28: inject contextual compositions; note PPC preferred action
    continuations, state["_contextual_stack_before_sel"] = csb.before_selection(
        state,
        tick=tick,
        observation=observation if isinstance(observation, dict) else None,
        continuations=continuations,
        cfg=cfg,
    )
    composition = {**composition, "continuations": continuations}

    selected = None
    selected_source = "ENDOGENOUS_VARIATION"
    selection_rule = "ENDOGENOUS_INDEX: actions[floor(rng*len(actions))] when no prospective/prediction winner"
    selection_mode = str(cfg.get("prospective_selection") or "SCENARIO_COMPETITION")
    competition_result: dict[str, Any] = {"outcome_class": "NOT_RUN", "mode": selection_mode}
    scenario_groups_public: dict[str, Any] = {}
    peer_evaluation = "NONE"
    # COMPOSITE_MOTOR_V1: PSC competes on locomotion only (bounded; no Cartesian product).
    # Side channels (neck/osc/push) are factorized in the SAME cycle after loco selection.
    composite_on = bool(cfg.get("composite_motor", True))
    select_actions = locomotion_options(actions) if composite_on else list(actions)

    # --- Sensorimotor consequence queries (available to PSC as MATCH evidence) ---
    smc_store = _smc_store(state)
    smc_store["enabled"] = bool(cfg.get("sensorimotor_consequence_model"))
    smc.set_bilateral(smc_store, bool(cfg.get("sensorimotor_consequence_bilateral", True)))
    _fam = cfg.get("sensorimotor_consequence_families")
    if isinstance(_fam, dict):
        smc.set_families(smc_store, **{str(k): bool(v) for k, v in _fam.items()})
    smc_candidate_preds: list[dict[str, Any]] = []
    smc_withhold = bool(cfg.get("sensorimotor_consequence_withhold_from_psc"))
    o_prime_bridge_rows: list[dict[str, Any]] = []
    o_prime_bridge_meta: dict[str, Any] = {"enabled": False}
    if smc_store.get("enabled") and isinstance(observation, dict):
        smc_candidate_preds = smc.query_candidates(
            smc_store,
            observation=observation,
            loco_candidates=list(select_actions),
            tick=tick,
        )
        if not smc_withhold:
            # Attach as compression-style prediction entries so factorized side
            # channels and retained-prediction paths can see MATCH support.
            for pred in smc_candidate_preds:
                if pred.get("status") in {smc.MATCH, smc.LOW_SUPPORT} and pred.get("predicted_delta"):
                    loco = str(pred.get("candidate_locomotion") or "")
                    if not loco:
                        continue
                    o_hat = smc.apply_predicted_to_observation(observation, pred.get("predicted_delta"))
                    predictions.append({
                        "action": loco,
                        "source": "sensorimotor_consequence",
                        "result": {
                            "status": "MATCH",
                            "support": int(pred.get("support") or 0),
                            "reliability": float(pred.get("reliability") or 0.5),
                            "predicted": o_hat,
                            "sensorimotor_record_id": pred.get("record_id"),
                            "predicted_delta": pred.get("predicted_delta"),
                        },
                        "sensorimotor_consequence": pred,
                    })

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
                    actions=select_actions,
                    conflict_candidates=(conflict_org.get("candidates") or []),
                    action_counts=(state.get("metrics") or {}).get("action_counts") or {},
                    meta=fsa_meta,
                )
            else:
                groups = sc.collect_scenario_groups(
                    store=state["prospection"],
                    observation=observation,
                    continuations=continuations,
                    actions=select_actions,
                )
            if cfg.get("prediction_error_revision"):
                groups = per.filter_groups(_per_store(state), groups)
            scenario_groups_public = {
                a: {
                    "supported": bool(groups.get(a)),
                    "count": len(groups.get(a) or []),
                    "scenarios": groups.get(a) or [],
                }
                for a in select_actions
            }
            groups = _enrich_groups_with_smc(
                groups,
                observation=observation if isinstance(observation, dict) else {},
                smc_preds=smc_candidate_preds,
                withhold=smc_withhold,
            )
            o_prime_bridge_rows: list[dict[str, Any]] = []
            o_prime_bridge_meta: dict[str, Any] = {"enabled": False, "withheld_from_psc": False}
            if (
                cfg.get("historical_sensorimotor_selection_bridge")
                and smc_store.get("enabled")
                and isinstance(observation, dict)
                and smc_candidate_preds
            ):
                o_prime_bridge_rows = oph.evaluate_candidates(
                    observation=observation,
                    smc_preds=smc_candidate_preds,
                    prospection=state.get("prospection") or {},
                    compression=state.get("compression") if cfg.get("retrieval") else None,
                    actions=list(select_actions),
                    retrieval_enabled=bool(cfg.get("retrieval")),
                    shuffle_o_prime_history=bool(cfg.get("historical_sensorimotor_selection_shuffle")),
                    tick=int(tick),
                )
                o_withhold = bool(cfg.get("historical_sensorimotor_selection_withhold"))
                n_match = sum(1 for r in o_prime_bridge_rows if (r.get("history") or {}).get("status") == oph.MATCH)
                supports = [
                    int((r.get("history") or {}).get("historical_support") or 0)
                    for r in o_prime_bridge_rows
                    if (r.get("history") or {}).get("status") == oph.MATCH
                ]
                o_prime_bridge_meta = {
                    "enabled": True,
                    "withheld_from_psc": o_withhold,
                    "shuffle": bool(cfg.get("historical_sensorimotor_selection_shuffle")),
                    "n_candidates_evaluated": len(o_prime_bridge_rows),
                    "n_history_match": n_match,
                    "history_support_spread": (max(supports) - min(supports)) if supports else 0,
                    "history_support_differentiated": bool(supports) and (max(supports) - min(supports)) >= 1,
                }
                # Local CF on pre-bridge groups (same rng_value; no state mutation)
                cf = sc.compete_scenarios(groups=groups, actions=select_actions, rng_value=rng_value)
                o_prime_bridge_meta["local_counterfactual"] = {
                    "selected": cf.get("selected"),
                    "source": cf.get("source"),
                    "outcome_class": (cf.get("competition") or {}).get("outcome_class"),
                }
                if not o_withhold:
                    for r in o_prime_bridge_rows:
                        scn = r.get("scenario")
                        if not scn:
                            continue
                        loco = str(r.get("candidate_locomotion") or "")
                        hss = dict(scn.get("historical_sensorimotor_selection") or {})
                        hss["available_to_psc"] = True
                        scn["historical_sensorimotor_selection"] = hss
                        if loco:
                            groups.setdefault(loco, []).append(scn)
                else:
                    for r in o_prime_bridge_rows:
                        scn = r.get("scenario")
                        if scn:
                            hss = dict(scn.get("historical_sensorimotor_selection") or {})
                            hss["available_to_psc"] = False
                            scn["historical_sensorimotor_selection"] = hss
            else:
                o_prime_bridge_rows = []
            comp = sc.compete_scenarios(groups=groups, actions=select_actions, rng_value=rng_value)
            if o_prime_bridge_meta.get("enabled") and not o_prime_bridge_meta.get("withheld_from_psc"):
                cf_sel = (o_prime_bridge_meta.get("local_counterfactual") or {}).get("selected")
                o_prime_bridge_meta["selection_differs_from_withheld_cf"] = (
                    str(comp.get("selected")) != str(cf_sel)
                    if cf_sel is not None and comp.get("selected") is not None
                    else False
                )
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

    if selected not in select_actions:
        selected = select_actions[min(len(select_actions) - 1, int(float(rng_value) * len(select_actions)))]
        selected_source = "ENDOGENOUS_VARIATION"
        selection_rule = (
            "ENDOGENOUS_INDEX: select_actions[floor(rng*len)] "
            + ("(composite loco set)" if composite_on else "(full repertoire)")
        )
        if competition_result.get("outcome_class") == "NO_SUPPORT":
            competition_result["fallback"] = "ENDOGENOUS_VARIATION"

    # --- PSC motor resolution (default LOCO_FACTORIZED; OBSERVED_COMPOSITE experimental) ---
    psc_motor_res = ocpsc.normalize_mode(cfg.get("psc_motor_resolution"))
    observed_selection_meta: dict[str, Any] = {
        "mode": psc_motor_res,
        "status": "NOT_USED",
        "experimental": psc_motor_res == ocpsc.MODE_OBSERVED,
    }
    motor_output: CompositeMotorOutput | None = None
    skip_factorized = False
    if (
        composite_on
        and psc_motor_res == ocpsc.MODE_OBSERVED
        and bool(smc_store.get("enabled"))
        and bool(cfg.get("historical_sensorimotor_selection_bridge"))
        and isinstance(observation, dict)
        and str(selection_mode).upper() != "LEGACY_FIRST"
    ):
        oc = ocpsc.select_observed_composite_motor(
            observation=observation,
            smc_store=smc_store,
            loco_candidates=list(select_actions),
            prospection=state.get("prospection") or {},
            compression=state.get("compression") if cfg.get("retrieval") else None,
            retrieval_enabled=bool(cfg.get("retrieval")),
            tick=int(tick) if tick is not None else None,
            rng_value=float(rng_value),
        )
        observed_selection_meta.update({
            "status": oc.get("status"),
            "reason": oc.get("reason"),
            "n_candidates": oc.get("n_candidates"),
            "exact_composite_matches": oc.get("exact_composite_matches"),
            "candidate_signatures": oc.get("candidate_signatures"),
            "selected_signature": oc.get("selected_signature"),
            "selected_locomotion": oc.get("selected_locomotion"),
            "candidates": oc.get("candidates"),
            "compete_source": oc.get("compete_source"),
        })
        if oc.get("status") == "SELECTED" and oc.get("motor") is not None:
            motor_output = oc["motor"]
            motor_output.schema = MOTOR_SCHEMA
            selected = motor_output.legacy_token
            selected_source = "OBSERVED_COMPOSITE_PSC"
            selection_rule = (
                "OBSERVED_COMPOSITE [EXPERIMENTAL]: empirical composite signatures → "
                "SMC → O′ → history → compete_scenarios → full COMPOSITE_MOTOR_V1 "
                "(no Cartesian invention; no legacy side-channel overwrite)"
            )
            competition_result = dict(oc.get("competition") or competition_result)
            competition_result["mode"] = selection_mode
            competition_result["psc_motor_resolution"] = ocpsc.MODE_OBSERVED
            competition_result["selected_composite_signature"] = oc.get("selected_signature")
            skip_factorized = True
        else:
            observed_selection_meta["fallback"] = "LOCO_FACTORIZED_THIS_TICK"

    # --- COMPOSITE MOTOR: factorize side channels (LOCO_FACTORIZED / fallback only) ---
    if composite_on and not skip_factorized:
        head_on = any(str(a).startswith("NECK_") for a in actions)
        osc_on = any(str(a) in OSC_ACTIONS for a in actions)
        push_on = "PUSH" in actions
        neck, neck_src, osc, osc_src, push, push_src = select_factorized_side_channels(
            available=list(actions),
            predictions=predictions,
            rng_value=float(rng_value),
            articulated_head=head_on,
            oscillatory=osc_on,
            physical_push=push_on,
        )
        loco = selected if (selected == "WAIT" or str(selected).startswith("MOVE:")) else "WAIT"
        motor_output = build_composite_from_factorized(
            locomotion=loco,
            loco_source=selected_source,
            neck=neck,
            neck_source=neck_src,
            osc=osc,
            osc_source=osc_src,
            push=push,
            push_source=push_src,
        )
        motor_output.schema = MOTOR_SCHEMA
        # Legacy primary token for counters / last_action learning key.
        selected = motor_output.legacy_token
        selected_source = "COMPOSITE_FACTORIZED"
        selection_rule = (
            "COMPOSITE_MOTOR_V1: one cycle → locomotion(PSC) + factorized "
            "neck/oscillator/push (no Cartesian catalog, no second cognition)"
        )
        competition_result = dict(competition_result or {})
        competition_result["psc_motor_resolution"] = ocpsc.MODE_LOCO
    elif not composite_on:
        motor_output = CompositeMotorOutput.from_legacy(str(selected), source=selected_source)
        competition_result = dict(competition_result or {})
        competition_result["psc_motor_resolution"] = psc_motor_res
    else:
        # OBSERVED_COMPOSITE winner already set — do not re-factorize side channels.
        competition_result = dict(competition_result or {})
        competition_result["psc_motor_resolution"] = ocpsc.MODE_OBSERVED

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
        payload={
            "action": selected,
            "source": selected_source,
            "motor_output": motor_output.to_dict() if motor_output else None,
            "motor_schema": (motor_output.schema if motor_output else LEGACY_SCHEMA),
        },
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

    metrics["action_counts"][str(selected)] = int(metrics["action_counts"].get(str(selected), 0)) + 1
    # Component-level control counts (distinct from effector-active ticks).
    mc = metrics.setdefault("motor_component_counts", {})
    if motor_output is not None:
        if motor_output.locomotion and motor_output.locomotion not in ("WAIT", "NONE"):
            mc["locomotion"] = int(mc.get("locomotion", 0)) + 1
            mc[motor_output.locomotion] = int(mc.get(motor_output.locomotion, 0)) + 1
        if motor_output.neck and motor_output.neck != "NONE":
            mc["neck"] = int(mc.get("neck", 0)) + 1
            mc[motor_output.neck] = int(mc.get(motor_output.neck, 0)) + 1
        osc = motor_output.oscillator
        if osc.frequency_delta:
            mc["osc_freq"] = int(mc.get("osc_freq", 0)) + 1
        if osc.amplitude_delta:
            mc["osc_amp"] = int(mc.get("osc_amp", 0)) + 1
        if osc.emit_trigger:
            mc["OSC_EMIT"] = int(mc.get("OSC_EMIT", 0)) + 1
        if motor_output.push:
            mc["PUSH"] = int(mc.get("PUSH", 0)) + 1
        metrics["motor_schema"] = motor_output.schema
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
    state["last_motor_output"] = motor_output.to_dict() if motor_output else None
    # Support-gated continuation may keep organizing action without full PSC reselection.
    _ppc_pref = (state.get("_contextual_stack_before_sel") or {}).get("ppc_preferred")
    if (
        _ppc_pref
        and cfg.get("persistent_prospective_control")
        and not cfg.get("persistent_prospective_control_ablate")
        and (selected_source in {"ENDOGENOUS_VARIATION", "RETAINED_PREDICTION"} or str(selected) == str(_ppc_pref))
    ):
        if str(selected) != str(_ppc_pref) and selected_source in {"ENDOGENOUS_VARIATION", "RETAINED_PREDICTION"}:
            selected = str(_ppc_pref)
            selected_source = "PERSISTENT_PROSPECTIVE_CONTROL"
            selection_rule = "PERSISTENT_PROSPECTIVE_CONTROL: continue selected prospective while support holds"
        elif str(selected) == str(_ppc_pref) and (state.get("persistent_prospective_control") or {}).get("active"):
            selected_source = "PERSISTENT_PROSPECTIVE_CONTROL"
            selection_rule = "PERSISTENT_PROSPECTIVE_CONTROL: continue selected prospective while support holds"
    state["last_action"] = selected
    state["_contextual_stack_after_sel"] = csb.after_selection(
        state,
        tick=tick,
        selected=str(selected) if selected else None,
        continuations=continuations,
        observation=observation if isinstance(observation, dict) else None,
        cfg=cfg,
        selection_source=str(selected_source) if selected_source else None,
    )
    state["last_selection"] = {
        "action": selected,
        "source": selected_source,
        "motor_output": motor_output.to_dict() if motor_output else None,
        "motor_schema": motor_output.schema if motor_output else LEGACY_SCHEMA,
        "candidates": actions,
        "select_actions": list(select_actions),
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
        "contextual_stack": _retain_tick_local({
            "experience": state.get("_contextual_stack_experience"),
            "before_sel": state.get("_contextual_stack_before_sel"),
            "after_sel": state.get("_contextual_stack_after_sel"),
        }),
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

        "sensorimotor_consequence": _retain_tick_local(smc.diagnostic(_smc_store(state))),
        "sensorimotor_candidate_predictions": _retain_tick_local_list(smc_candidate_preds, limit=12),
        "sensorimotor_withheld_from_psc": bool(smc_withhold),
        "o_prime_history_bridge": _retain_tick_local(o_prime_bridge_meta),
        "psc_motor_resolution": psc_motor_res,
        "observed_composite_selection": _retain_tick_local(observed_selection_meta),
        "o_prime_history_candidates": _retain_tick_local_list(
            [
                {
                    "candidate_locomotion": r.get("candidate_locomotion"),
                    "history_status": (r.get("history") or {}).get("status"),
                    "history_support": (r.get("history") or {}).get("historical_support"),
                    "history_match_count": (r.get("history") or {}).get("match_count"),
                    "support_spread": (r.get("history") or {}).get("support_spread"),
                    "predicted_fields": (r.get("construct") or {}).get("predicted_fields"),
                    "available_to_psc": (
                        ((r.get("scenario") or {}).get("historical_sensorimotor_selection") or {}).get("available_to_psc")
                    ),
                    "history_shuffled": bool(r.get("history_shuffled")),
                }
                for r in (o_prime_bridge_rows or [])
            ],
            limit=12,
        ),
        "sensorimotor_last_update": _retain_tick_local(state.get("last_sensorimotor_update")),
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
        motor_output=motor_output.to_dict() if motor_output else None,
    )


def clear_derived_indexes(state: dict[str, Any]) -> None:
    """Drop reconstructible indexes after snapshot restore. Canonical stores unchanged."""
    eq = state.get("equivalence")
    if isinstance(eq, dict):
        pe.clear_derived_caches(eq)
    temporal = state.get("temporal")
    if isinstance(temporal, dict):
        inner = temporal.get("inner")
        if isinstance(inner, dict):
            pe.clear_derived_caches(inner)
        temporal.pop("_retrieve_cache", None)
    smc_store = state.get("sensorimotor_consequence")
    if isinstance(smc_store, dict):
        smc.invalidate_indexes(smc_store)


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
        **csb.public_view_sections(state),
    }
