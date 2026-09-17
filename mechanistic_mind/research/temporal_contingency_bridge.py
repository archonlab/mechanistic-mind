"""Update 4.10 / 4.11 — temporal contingencies → prospective organism states.

4.11: state-conditioned retrieval; multi-horizon predicted organism states;
WAIT as real no-intervention trajectory; A−WAIT diagnostic (not value).
Does not write contingency confidence into candidate utility.
Does not add habit × weight into the prospective path.
Does not aggregate H1/H2/H3 into one scalar.
"""
from __future__ import annotations

from copy import deepcopy
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
from mechanistic_mind.psyche.sensorimotor import (
    SensorimotorStore,
    available_actions,
    context_cue,
)
from mechanistic_mind.psyche.temporal_contingency import (
    best_prediction_for_action,
    build_prospective_trajectory,
    coarse_body_state_key,
    ensure_temporal,
    intervention_difference,
    retrieve_temporal,
    temporal_cue_bucket,
)
from mechanistic_mind.research.prospective_valuation import prospective_ordinary_value
from mechanistic_mind.research.transition_composition import compose_two_step, depth2_tree
from mechanistic_mind.research.persistent_prospective_trace import (
    ACTIVE as TRACE_ACTIVE,
    advance_trace,
    retained_tail,
    trace_from_composition,
)


class TemporalContingencyBridgeModule(PsycheModule):
    module_id = "PSY-TEMPORAL-CONTINGENCY-BRIDGE-V410"
    version = "0.4.16"
    stage = PsycheStage.ACTION_GENERATION

    def __init__(
        self,
        *,
        enabled: bool = False,
        prospective_valuation: bool = True,
        prediction_ablated: bool = False,
        action_conditioning: bool = True,
        context_conditioning: bool = True,
        state_conditioning: bool = True,
        reconstruction_ablated: bool = False,
        min_support: float = 3.0,
        trajectory_lags: tuple[int, ...] = (1, 2, 3),
    ) -> None:
        self.enabled = bool(enabled)
        self.prospective_valuation = bool(prospective_valuation)
        self.prediction_ablated = bool(prediction_ablated)
        self.action_conditioning = bool(action_conditioning)
        self.context_conditioning = bool(context_conditioning)
        self.state_conditioning = bool(state_conditioning)
        # Update 4.16 hard ablation.  This only blocks creation of a fresh
        # episode trace; an already-persisted trace is advanced independently.
        self.reconstruction_ablated = bool(reconstruction_ablated)
        self.min_support = float(min_support)
        self.trajectory_lags = tuple(int(x) for x in trajectory_lags)

    def process(self, context: PsycheContext) -> PsycheOutput:
        if not self.enabled:
            return PsycheOutput(
                signals={"temporal_contingency_bridge": {"enabled": False}},
                updates=(
                    PsycheUpdate(
                        "working",
                        "temporal_contingency_bridge",
                        {"enabled": False},
                    ),
                ),
            )

        store = SensorimotorStore.from_dict(
            context.state.memory.get("sensorimotor")
            if isinstance(context.state.memory, dict)
            else None
        )
        raw = store.to_dict()
        tc = ensure_temporal(raw)
        obs = context.observation
        data = dict(obs.data) if isinstance(obs.data, dict) else {}
        available = set(available_actions(obs))
        # WAIT must remain available as a real trajectory even if selection omits it
        available_with_wait = set(available) | {"WAIT"}
        cue = context_cue(data, cue_mode=str(data.get("cue_mode") or "PERCEPTUAL_CUE_ENABLED"))
        bucket = temporal_cue_bucket(cue) if self.context_conditioning else "*"

        current_signals: dict[str, float] = {}
        if isinstance(context.state.internal, dict):
            current_signals = {
                k: float(v)
                for k, v in (context.state.internal.get("interoceptive_model") or {}).items()
                if isinstance(v, (int, float)) and not isinstance(v, bool)
            }
        if not current_signals:
            intero = data.get("interoception") if isinstance(data.get("interoception"), dict) else {}
            current_signals = {
                k: float(v)
                for k, v in intero.items()
                if isinstance(v, (int, float)) and not isinstance(v, bool)
            }

        state_key = coarse_body_state_key(current_signals, from_interoception=False)
        # also from observation for consistency with storage
        state_key_obs = coarse_body_state_key(data)
        if state_key.endswith("?") or "S?" in state_key:
            state_key = state_key_obs

        hits = retrieve_temporal(
            tc,
            bucket=bucket,
            available_actions=available_with_wait,
            action_conditioning=self.action_conditioning,
            context_conditioning=self.context_conditioning,
            min_support=self.min_support,
            state_key=state_key if self.state_conditioning else None,
            state_conditioning=self.state_conditioning,
        )

        values = {}
        if isinstance(context.state.values, dict):
            values = context.state.values.get("by_action") or {}
        if not isinstance(values, dict):
            values = {}
        goals = context.state.goals if isinstance(context.state.goals, dict) else {}

        # --- 4.11 prospective self-state trajectories (shadow structure; per-horizon valuation) ---
        traj_actions = sorted(available_with_wait)
        trajectories: dict[str, Any] = {}
        horizon_valuations: dict[str, Any] = {}
        for action in traj_actions:
            traj = build_prospective_trajectory(
                action=action,
                current_signals=current_signals,
                hits=hits,
                lags=self.trajectory_lags,
            )
            trajectories[action] = traj
            hv = {}
            for L, pack in (traj.get("horizons") or {}).items():
                delta = pack.get("mean_body_delta")
                if not delta or pack.get("status") not in ("KNOWN", "WEAK", "UNKNOWN"):
                    hv[str(L)] = {
                        "ordinary_value": None,
                        "status": pack.get("status"),
                        "note": "NO_DELTA_OR_UNKNOWN",
                    }
                    continue
                if pack.get("predicted_state") is None:
                    hv[str(L)] = {"ordinary_value": None, "status": "UNKNOWN"}
                    continue
                # Evaluate predicted *delta* with existing ordinary valuation (Observer / diagnostic).
                # Repetition/habit is NOT added on this path.
                prosp = prospective_ordinary_value(
                    mean_body_delta=delta,
                    body_delta_samples=float(pack.get("support") or 0.0),
                    contradiction=float(pack.get("contradiction") or 0.0),
                    current_signals=current_signals,
                    goals=goals,
                    energy_capacity=1.0,
                    hydration_capacity=1.0,
                    support=float(pack.get("support") or 0.0),
                    prediction_ablated=self.prediction_ablated,
                ) if self.prospective_valuation else {}
                hv[str(L)] = {
                    "ordinary_value": prosp.get("ordinary_value"),
                    "epistemic_status": prosp.get("epistemic_status"),
                    "components": prosp.get("components"),
                    "habit_in_path": False,
                    "status": pack.get("status"),
                    "support": pack.get("support"),
                    "confidence": pack.get("confidence"),
                    "state_match": pack.get("state_match"),
                }
            horizon_valuations[action] = hv

        wait_traj = trajectories.get("WAIT") or build_prospective_trajectory(
            action="WAIT", current_signals=current_signals, hits=hits, lags=self.trajectory_lags
        )
        interventions: dict[str, Any] = {}
        for action, traj in trajectories.items():
            if action == "WAIT":
                continue
            interventions[action] = intervention_difference(
                traj, wait_traj, lags=self.trajectory_lags
            )

        prospective_self_state = {
            "version": "4.11",
            "current_signals": current_signals,
            "state_key": state_key,
            "context_bucket": bucket,
            "trajectories": trajectories,
            "horizon_ordinary_valuations": horizon_valuations,
            "intervention_difference_A_minus_WAIT": interventions,
            "aggregation": "NONE",
            "habit_value_in_prospective_path": False,
            "semantic_self_token": False,
            "researcher_note": (
                "prospective organism-state prediction under candidate actions; "
                "WAIT is no-intervention baseline trajectory, not identity"
            ),
        }


        # --- 4.12 shadow composition (no ranking / no policy) ---
        composed_payload = {
            "version": "4.12",
            "shadow_only": True,
            "ranking": False,
            "note": "optional live sketch; experiment runner owns controlled A/B tests",
        }
        try:
            # Prefer USE + WAIT sketch for Observer when both exist
            use_acts = [a for a in traj_actions if str(a).startswith("USE")]
            if use_acts:
                composed_payload["sketch_USE_then_WAIT"] = compose_two_step(
                    tc=tc,
                    s0_signals=current_signals,
                    action_a=use_acts[0],
                    action_b="WAIT",
                    bucket=bucket,
                    lag_a=1,
                    lag_b=1,
                    available_actions=available_with_wait,
                    min_support=self.min_support,
                )
            composed_payload["depth2_tree"] = depth2_tree(
                tc=tc,
                s0_signals=current_signals,
                actions=[a for a in traj_actions if a == "WAIT" or str(a).startswith("USE")][:4],
                bucket=bucket,
                lag=1,
                min_support=self.min_support,
            )
        except Exception as exc:
            composed_payload["error"] = str(exc)

        # --- 4.16 persistent episode trace (bounded; no value/policy bridge) ---
        # The old trace is read from mechanism state before any fresh trace is
        # made.  advance_trace never consults acquired contingencies or the
        # freshly reconstructed composition.
        working = context.state.working if isinstance(context.state.working, dict) else {}
        previous_trace = working.get("current_prospective_trace")
        trace_counter = int(working.get("prospective_trace_counter") or 0)
        current_trace = None
        if isinstance(previous_trace, dict) and previous_trace.get("status") == TRACE_ACTIVE:
            current_trace = advance_trace(
                previous_trace,
                tick=context.tick,
                realized_state=current_signals,
                actual_action=store.executed_action,
            )

        fresh_trace = None
        if not self.reconstruction_ablated:
            sketch = composed_payload.get("sketch_USE_then_WAIT")
            if isinstance(sketch, dict) and sketch.get("status") == "OK":
                trace_counter += 1
                fresh_trace = trace_from_composition(
                    counter=trace_counter,
                    created_tick=context.tick,
                    origin_signals=current_signals,
                    composition=sketch,
                )
        if current_trace is None:
            current_trace = deepcopy(fresh_trace)

        continuity_payload = {
            "version": "4.16",
            "current_episode_trace": current_trace,
            "fresh_reconstruction": fresh_trace,
            "retained_tail": retained_tail(current_trace),
            "reconstruction_ablated": self.reconstruction_ablated,
            "acquired_space_separate": True,
            "policy_coupled": False,
            "value_coupled": False,
        }


        # --- Legacy-compatible single-lag candidates (policy scalar; state-conditioned) ---
        candidates: list[PsycheActionCandidate] = []
        rows = []
        pred_updates: dict[str, Any] = {}
        seen = set()
        for action in sorted(available):
            best = best_prediction_for_action(hits, action)
            if best is None:
                continue
            if action in seen:
                continue
            seen.add(action)
            legacy = values.get(action, {}) if isinstance(values.get(action), dict) else {}
            # Strip habit from legacy fallback so prospective path does not reintroduce
            # repetition→value; policy may still see endogenous habit via other modules.
            legacy_ordinary = float(legacy.get("base_total", 0.0) or 0.0) - float(
                legacy.get("habit", 0.0) or 0.0
            )
            mean_body = best.get("mean_body_delta") or {}
            prosp = {
                "prospective_available": False,
                "ordinary_value": None,
                "epistemic_status": "UNKNOWN",
                "reason": "PROSPECTIVE_DISABLED",
                "predicted_signal_deltas": {},
                "confidence_used_as_value": False,
            }
            if self.prospective_valuation:
                prosp = prospective_ordinary_value(
                    mean_body_delta=mean_body,
                    body_delta_samples=float(best.get("support") or 0.0),
                    contradiction=float(best.get("contradiction") or 0.0),
                    current_signals=current_signals,
                    goals=goals,
                    energy_capacity=1.0,
                    hydration_capacity=1.0,
                    support=float(best.get("support") or 0.0),
                    prediction_ablated=self.prediction_ablated,
                )
            if prosp.get("prospective_available") and prosp.get("ordinary_value") is not None:
                ordinary = float(prosp["ordinary_value"])
                value_source = "PROSPECTIVE_PHYSICAL"
            else:
                ordinary = legacy_ordinary
                value_source = "LEGACY_MINUS_HABIT_OR_UNKNOWN"
            sig_deltas = prosp.get("predicted_signal_deltas") or {}
            if isinstance(sig_deltas, dict) and sig_deltas:
                pred_updates[action] = {
                    **{k: float(v) for k, v in sig_deltas.items() if isinstance(v, (int, float))},
                    "__prediction_source": "TEMPORAL_CONTINGENCY",
                    "__prediction_scope": "TEMPORAL_LAG",
                    "__lag": int(best.get("lag", -1)),
                    "__temporal_status": best.get("status"),
                    "__temporal_confidence": float(best.get("confidence") or 0.0),
                    "__temporal_support": float(best.get("support") or 0.0),
                    "__state_key": state_key,
                    "__state_match": best.get("_state_match"),
                }
            pred_state = None
            try:
                from mechanistic_mind.psyche.temporal_contingency import predicted_organism_state

                pred_state = predicted_organism_state(current_signals, mean_body)
            except Exception:
                pred_state = None
            meta = {
                "proposal_source": "TEMPORAL_CONTINGENCY",
                "predictive_confidence": float(best.get("confidence") or 0.0),
                "support_count": float(best.get("support") or 0.0),
                "predicted_transition_summary": {
                    "mean_body_delta": mean_body,
                    "lag": best.get("lag"),
                    "status": best.get("status"),
                    "predicted_signal_deltas": prosp.get("predicted_signal_deltas"),
                    "predicted_organism_state": pred_state,
                    "state_key": state_key,
                    "state_match": best.get("_state_match"),
                },
                "epistemic_status": prosp.get("epistemic_status"),
                "ordinary_action_value": ordinary,
                "value_source": value_source,
                "prospective": prosp,
                "temporal_contingency": True,
                "confidence_used_as_value": False,
                "habit_value_in_prospective_path": False,
                "temporal_key": best.get("key"),
                "lag": best.get("lag"),
                "update_411_trajectory_available": True,
            }
            candidates.append(
                PsycheActionCandidate(
                    source_module=self.module_id,
                    action=Action(action),
                    total_value=ordinary,
                    components=(
                        {k: float(v) for k, v in (prosp.get("components") or {}).items()}
                        if isinstance(prosp.get("components"), dict)
                        else {}
                    ),
                    metadata=meta,
                )
            )
            rows.append(
                {
                    "action": action,
                    "lag": best.get("lag"),
                    "status": best.get("status"),
                    "support": best.get("support"),
                    "confidence": best.get("confidence"),
                    "ordinary_value": ordinary,
                    "epistemic_status": prosp.get("epistemic_status"),
                    "state_match": best.get("_state_match"),
                    "state_key": state_key,
                }
            )

        bridge_payload = {
            "enabled": True,
            "version": "4.11",
            "n_hits": len(hits),
            "n_candidates": len(candidates),
            "rows": rows[:16],
            "state_key": state_key,
            "state_conditioning": self.state_conditioning,
            "trajectory_lags": list(self.trajectory_lags),
            "aggregation": "NONE",
        }

        updates = [
            PsycheUpdate("working", "temporal_contingency_bridge", bridge_payload),
            PsycheUpdate("working", "prospective_self_state", prospective_self_state),
            PsycheUpdate("working", "composed_prospective_trajectories", composed_payload),
            PsycheUpdate("working", "current_prospective_trace", current_trace),
            PsycheUpdate("working", "fresh_prospective_reconstruction", fresh_trace),
            PsycheUpdate("working", "prospective_trace_continuity", continuity_payload),
            PsycheUpdate("working", "prospective_trace_counter", trace_counter),
        ]
        if pred_updates:
            updates.append(PsycheUpdate("working", "predicted_action_effects", pred_updates))

        return PsycheOutput(
            signals={
                "temporal_contingency_bridge": bridge_payload,
                "prospective_self_state": {
                    "state_key": state_key,
                    "n_actions": len(trajectories),
                },
                "persistent_prospective_trace": {
                    "trace_id": (current_trace or {}).get("trace_id"),
                    "created_tick": (current_trace or {}).get("created_tick"),
                    "status": (current_trace or {}).get("status"),
                    "tail_nodes": len(retained_tail(current_trace)),
                    "fresh_trace_id": (fresh_trace or {}).get("trace_id"),
                    "reconstruction_ablated": self.reconstruction_ablated,
                    "policy_coupled": False,
                },
            },
            candidates=tuple(candidates),
            updates=tuple(updates),
        )
