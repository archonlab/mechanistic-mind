\
"""Build V3 CORE receipts from post-step runtime state (read-only)."""
from __future__ import annotations

from typing import Any

from .coverage import (
    COMPLETE,
    NOT_APPLICABLE,
    NOT_AVAILABLE,
    NOT_RECORDED,
    PARTIAL,
    empty_coverage,
    mark,
)
from .identity import (
    CONTROLLER_AUTONOMOUS,
    CONTROLLER_EXPERIMENTER,
    IdentityMap,
    classify_controller,
    cognitive_agent_id_for_slot,
    physical_body_id_for_slot,
)
from .ids import decision_id, motor_id, observation_id
from .receipts import (
    build_consequence_receipt,
    build_decision_receipt,
    build_motor_receipt,
    build_observation_receipt,
    compact_accessible_observation,
)


def _presence(value: Any, *, zero_is_true_zero: bool = False) -> str:
    """Distinguish MISSING / TRUE_ZERO / PRESENT without inventing numerics."""
    if value is None:
        return "MISSING"
    if zero_is_true_zero:
        try:
            if float(value) == 0.0:
                return "TRUE_ZERO"
        except (TypeError, ValueError):
            pass
    if value is False:
        return "TRUE_ZERO"
    if value == [] or value == {}:
        return "TRUE_ZERO"
    return "PRESENT"


def _append_actuation_etc_exact_lineage(
    *,
    event_refs: list[dict[str, Any]],
    slot: Any,
    decision_tick: int,
    body_id: str,
    run_id: str,
    motor_id_value: str | None,
    motor_out: dict[str, Any] | None,
) -> None:
    """Researcher exact join: Z request → EBAE → displacement → ETC → work → failure → detach.

    Reuses already-computed receipts only. Does not re-run EBAE/ETC/contact solvers.
    Never enters cognition. Does not change whether contact/work/failure occurred.
    """
    generation = int(getattr(slot, "_runtime_generation", getattr(slot, "runtime_generation", 0)) or 0)
    ebae_act = getattr(slot, "last_agent_effector_z_actuation", None)
    etc_step = getattr(getattr(slot, "world", None), "last_effector_terrain_contact_step", None)
    mat = getattr(slot, "last_material_transformation_receipt", None)
    wmt = getattr(getattr(slot, "world", None), "last_material_transaction_id", None)

    zl = zr = 0
    if isinstance(motor_out, dict):
        try:
            zl = int(motor_out.get("effector_z_left") or 0)
        except (TypeError, ValueError):
            zl = 0
        try:
            zr = int(motor_out.get("effector_z_right") or 0)
        except (TypeError, ValueError):
            zr = 0

    etc_by_hand: dict[str, dict[str, Any]] = {}
    if isinstance(etc_step, dict) and int(etc_step.get("tick", -1)) == int(decision_tick):
        for r in etc_step.get("receipts") or []:
            if not isinstance(r, dict):
                continue
            hid = str(r.get("effector_id") or "").upper()
            if hid:
                etc_by_hand[hid] = r

    for hand, req in (("LEFT", zl), ("RIGHT", zr)):
        ebae_rec = None
        if isinstance(ebae_act, dict) and int(ebae_act.get("tick", -1)) == int(decision_tick):
            raw = ebae_act.get(hand.lower())
            if isinstance(raw, dict):
                ebae_rec = raw
        etc_rec = etc_by_hand.get(hand)
        lineage_id = f"aetc:{run_id}:{int(decision_tick)}:{generation}:{body_id}:{hand}"
        ebae_id = None
        if isinstance(ebae_rec, dict):
            ebae_id = str(
                ebae_rec.get("receipt_id")
                or ebae_rec.get("event_id")
                or f"ebae:{run_id}:{decision_tick}:{body_id}:{hand}"
            )
        etc_id = None
        if isinstance(etc_rec, dict):
            etc_id = str(
                etc_rec.get("episode_id")
                or etc_rec.get("receipt_id")
                or f"etc:{run_id}:{decision_tick}:{body_id}:{hand}"
            )
        work_val = None
        if isinstance(ebae_rec, dict) and ebae_rec.get("work_used") is not None:
            work_val = ebae_rec.get("work_used")
        contact_fact = None
        if isinstance(etc_rec, dict):
            contact_fact = etc_rec.get("contact_fact")
        fail_status = "MISSING"
        detach_status = "MISSING"
        mat_id = None
        if isinstance(mat, dict) and int(mat.get("tick", mat.get("world_tick", -1))) == int(decision_tick):
            mat_id = str(mat.get("transaction_id") or mat.get("receipt_id") or wmt or "")
            st = str(mat.get("status") or mat.get("outcome") or mat.get("phase") or "")
            if "FAIL" in st.upper() or mat.get("failure"):
                fail_status = "PRESENT"
            else:
                fail_status = "TRUE_ZERO"
            if "DETACH" in st.upper() or mat.get("detached") or mat.get("created_object_id"):
                detach_status = "PRESENT"
            else:
                detach_status = "TRUE_ZERO"

        request_status = "PRESENT" if req != 0 else ("TRUE_ZERO" if motor_out is not None else "MISSING")
        ebae_status = "MISSING"
        if isinstance(ebae_rec, dict):
            ebae_status = "PRESENT"
        elif isinstance(ebae_act, dict) and ebae_act.get("status") in ("NONE", "CAPABILITY_OFF"):
            ebae_status = "TRUE_ZERO"
        elif req == 0 and motor_out is not None:
            ebae_status = "TRUE_ZERO"

        event_refs.append(
            {
                "kind": "actuation_etc_causal_lineage",
                "schema": "ACTUATION_ETC_EXACT_CAUSAL_LINEAGE_V1",
                "lineage_id": lineage_id,
                "tick": int(decision_tick),
                "run_id": run_id,
                "runtime_generation": generation,
                "cognitive_agent_id": None,
                "physical_body_id": body_id,
                "effector_id": hand,
                "motor_id": motor_id_value,
                "stages": {
                    "z_request": {
                        "status": request_status,
                        "requested_relative_delta": int(req),
                    },
                    "ebae_actuation": {
                        "status": ebae_status,
                        "receipt_id": ebae_id,
                        "accepted_status": (ebae_rec or {}).get("status") if ebae_rec else None,
                        "request_submitted": bool(ebae_rec),
                    },
                    "displacement": {
                        "status": _presence(
                            None
                            if not ebae_rec
                            else (ebae_rec.get("achieved_relative_delta")
                                  if ebae_rec.get("achieved_relative_delta") is not None
                                  else ebae_rec.get("relative_z_after")),
                            zero_is_true_zero=True,
                        ),
                        "relative_z_before": (ebae_rec or {}).get("relative_z_before") if ebae_rec else None,
                        "relative_z_after": (ebae_rec or {}).get("relative_z_after") if ebae_rec else None,
                        "achieved_relative_delta": (ebae_rec or {}).get("achieved_relative_delta") if ebae_rec else None,
                    },
                    "etc_contact": {
                        "status": (
                            "PRESENT"
                            if contact_fact is True
                            else ("TRUE_ZERO" if contact_fact is False or (etc_rec is None and ebae_status != "MISSING") else "MISSING")
                        ),
                        "receipt_id": etc_id,
                        "contact_fact": contact_fact,
                        "episode_id": (etc_rec or {}).get("episode_id") if etc_rec else None,
                        "terrain_cell": (etc_rec or {}).get("terrain_cell") if etc_rec else None,
                        "vw1_interval_ref": (etc_rec or {}).get("terrain_source") if etc_rec else None,
                    },
                    "work_transmitted": {
                        "status": _presence(work_val, zero_is_true_zero=True),
                        "work_used": work_val,
                    },
                    "material_failure": {
                        "status": fail_status,
                        "material_receipt_id": mat_id,
                    },
                    "detachment": {
                        "status": detach_status,
                        "material_receipt_id": mat_id,
                    },
                },
                "researcher_only": True,
                "cognition_exposed": False,
                "agent_accessible": False,
                "physics_replayed": False,
                "contact_solver_reexecuted": False,
            }
        )


def _append_o3_o4_exact_lineage(
    *,
    event_refs: list[dict[str, Any]],
    slot: Any,
    decision_tick: int,
    body_id: str,
    run_id: str,
    observation_id_value: str | None,
) -> None:
    """Researcher exact O3→O4→exo→O5 timing join from existing O4 reception traces.

    Does not raycast or recompute light. Does not use FPV pixels. No O1–O5 numeric change.
    """
    generation = int(getattr(slot, "_runtime_generation", getattr(slot, "runtime_generation", 0)) or 0)
    world = getattr(slot, "world", None)
    body = getattr(slot, "body", None)
    trace = None
    by_body = getattr(world, "_o4_last_reception_by_body", None) if world is not None else None
    if isinstance(by_body, dict) and body is not None:
        trace = by_body.get(id(body))
    if trace is None and world is not None:
        trace = getattr(world, "_o4_last_reception_trace", None)
    if not isinstance(trace, dict):
        event_refs.append(
            {
                "kind": "o3_o4_exact_receptor_lineage",
                "schema": "O3_O4_EXACT_RECEPTOR_LINEAGE_V1",
                "lineage_id": f"o34:{run_id}:{int(decision_tick)}:{generation}:{body_id}",
                "tick": int(decision_tick),
                "run_id": run_id,
                "runtime_generation": generation,
                "physical_body_id": body_id,
                "observation_id": observation_id_value,
                "status": "MISSING",
                "reason": "NO_O4_TRACE_FOR_TICK",
                "researcher_only": True,
                "cognition_exposed": False,
                "agent_accessible": False,
                "fpv_used": False,
                "light_recomputed": False,
            }
        )
        return

    # Compact exact fields only — reuse stored O4 authority values.
    contributors = list(trace.get("contributors") or [])
    compact_contrib = []
    for c in contributors[:32]:
        if not isinstance(c, dict):
            continue
        compact_contrib.append(
            {
                "surface_id": c.get("surface_id") or c.get("entity_id") or c.get("contributor_id"),
                "accepted": c.get("accepted"),
                "reject_reason": c.get("reject_reason") or c.get("reason"),
                "visibility": c.get("visibility") or c.get("eye_visibility"),
                "bands": c.get("contrib_bands") or c.get("bands"),
            }
        )
    src = trace.get("source") or trace.get("o3_source") or {}
    light_off = None
    cfg = getattr(slot, "config", None)
    try:
        from mechanistic_mind.physical_system.abstract_spectral_light_source_and_direct_transport import (
            abstract_spectral_light_source_and_direct_transport_is_active,
        )
        light_off = not bool(abstract_spectral_light_source_and_direct_transport_is_active(cfg))
    except Exception:
        asls = getattr(getattr(cfg, "abstract_spectral_light_source_and_direct_transport", None), "source", None)
        if asls is not None:
            light_off = not bool(getattr(asls, "enabled", True))

    reached = bool(trace.get("physical_signal_reached_receptor"))
    accepted = int(trace.get("accepted") or 0)
    post = list(trace.get("post_clip_intensity") or [])
    event_refs.append(
        {
            "kind": "o3_o4_exact_receptor_lineage",
            "schema": "O3_O4_EXACT_RECEPTOR_LINEAGE_V1",
            "lineage_id": f"o34:{run_id}:{int(decision_tick)}:{generation}:{body_id}",
            "tick": int(decision_tick),
            "run_id": run_id,
            "runtime_generation": generation,
            "physical_body_id": body_id,
            "observation_id": observation_id_value,
            "o4_schema": trace.get("schema") or trace.get("o4_schema"),
            "o4_profile": trace.get("profile") or trace.get("o4_profile"),
            "stages": {
                "o3_source_profile": {
                    "status": "TRUE_ZERO" if light_off else "PRESENT",
                    "light_source_off": light_off,
                    "source_digest": src.get("digest") if isinstance(src, dict) else None,
                },
                "o2_o3a_surface_contribution": {
                    "status": "PRESENT" if contributors else ("TRUE_ZERO" if reached is False else "MISSING"),
                    "contributor_count": len(contributors),
                    "contributors_compact": compact_contrib,
                },
                "eye_visibility": {
                    "status": "PRESENT",
                    "accepted": accepted,
                    "rejected": trace.get("rejected"),
                    "reason_counts": trace.get("reason_counts"),
                },
                "o4_receptor_contribution": {
                    "status": "PRESENT" if accepted > 0 else "TRUE_ZERO",
                    "physical_signal_reached_receptor": reached,
                },
                "summed_receptor_bands": {
                    "status": "PRESENT" if post else "MISSING",
                    "post_clip_intensity": post,
                    "pre_clip_bins": trace.get("pre_clip_bins"),
                },
                "cognition_facing_exo": {
                    "status": "PRESENT",
                    "note": "exo_* scalars are in observation.accessible; joined via observation_id",
                },
                "o5_observation_timing_envelope": {
                    "status": "PRESENT",
                    "receptor_sample_tick": trace.get("receptor_sample_tick") or trace.get("tick"),
                    "visual_causal_delay_ticks": trace.get("visual_causal_delay_ticks"),
                    "k_visual": trace.get("k_visual"),
                },
            },
            "distinguishers": {
                "light_off": light_off,
                "occlusion_reject": bool((trace.get("reason_counts") or {}).get("OCCLUDED_VW1") or (trace.get("reason_counts") or {}).get("OCCLUDED_ENTITY")),
                "unknown_material": bool((trace.get("reason_counts") or {}).get("UNKNOWN_MATERIAL")),
                "true_darkness_or_no_signal": bool(reached is False and light_off is False),
                "missing_trace": False,
            },
            "researcher_only": True,
            "cognition_exposed": False,
            "agent_accessible": False,
            "fpv_used": False,
            "light_recomputed": False,
            "raycast_reexecuted": False,
        }
    )


def _world_size(runtime: Any) -> tuple[float | None, float | None]:
    world = getattr(runtime, "world", None)
    if world is None:
        slots = getattr(runtime, "slots", None)
        if slots:
            world = getattr(slots[0], "world", None)
    if world is None:
        return None, None
    T = getattr(world, "T", None)
    if T is None:
        return None, None
    try:
        h = float(T.shape[0])
        w = float(T.shape[1])
        return w, h
    except Exception:
        return None, None


def _event_refs_for_slot(runtime: Any, slot_index: int, decision_tick: int) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    # Contact / push from two_agent last_contacts
    for receipt in getattr(runtime, "last_contacts", None) or []:
        if not receipt:
            continue
        pair = receipt.get("pair")
        if not pair or slot_index not in pair:
            continue
        if receipt.get("contact"):
            refs.append({"kind": "contact", "tick": decision_tick, "pair": list(pair)})
        push = receipt.get("push") or {}
        if push.get("push_applied"):
            refs.append({"kind": "push", "tick": decision_tick, "pair": list(pair)})
    # Structured events on slot (IDs only — no large payloads)
    slots = getattr(runtime, "slots", None)
    if slots and 0 <= slot_index < len(slots):
        slot = slots[slot_index]
        bus = getattr(slot, "structured_events", None)
        recent = []
        if bus is not None:
            # Prefer a small tail API if present
            if hasattr(bus, "tail"):
                try:
                    recent = list(bus.tail(32))
                except Exception:
                    recent = []
            elif hasattr(bus, "events"):
                try:
                    recent = list(bus.events)[-32:]
                except Exception:
                    recent = []
        for ev in recent:
            if not isinstance(ev, dict):
                continue
            try:
                et = int(ev.get("tick"))
            except (TypeError, ValueError):
                continue
            if et != int(decision_tick):
                continue
            typ = str(ev.get("type") or ev.get("event_type") or "")
            if not typ:
                continue
            kind = None
            if "PUSH" in typ:
                kind = "push"
            elif "CONTACT" in typ:
                kind = "contact"
            elif "SIGNAL" in typ and "EMIT" in typ:
                kind = "signal_emission"
            elif "SIGNAL" in typ and ("RECV" in typ or "RECEIV" in typ):
                kind = "signal_reception"
            elif "TRANSFER" in typ or "RESOURCE" in typ:
                kind = "resource_transfer"
            if kind:
                refs.append({
                    "kind": kind,
                    "tick": decision_tick,
                    "event_type": typ,
                    "event_id": ev.get("id") or ev.get("event_id"),
                })
    # Dedup by kind+pair/type
    seen = set()
    out = []
    for r in refs:
        key = (r.get("kind"), r.get("event_type"), tuple(r.get("pair") or ()))
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def _derive_attribution(motor: dict[str, Any] | None, event_refs: list[dict[str, Any]], pose_dx: float, pose_dy: float) -> str:
    """Only attribute when evidence is clear; else UNKNOWN."""
    kinds = {r.get("kind") for r in event_refs}
    loco = str(((motor or {}).get("components") or {}).get("locomotion") or "WAIT")
    moved = (abs(pose_dx) + abs(pose_dy)) > 1e-12
    if "contact" in kinds or "push" in kinds:
        if loco not in ("WAIT", "NONE", "") and moved:
            return "MIXED"
        return "CONTACT"
    if loco not in ("WAIT", "NONE", "") and moved:
        return "SELF_MOTOR"
    if moved and loco in ("WAIT", "NONE", ""):
        return "SHARED_WORLD"
    if not moved:
        return "UNKNOWN"
    return "UNKNOWN"


def capture_v3_tick(
    runtime: Any,
    *,
    run_id: str,
    identity_map: IdentityMap,
    generation: int = 0,
) -> dict[str, Any]:
    """Capture CORE receipts for the decision tick that just completed.

    Call AFTER finish_tick / _step_once. Uses last_v3_* snapshots stashed during
    begin/finish so Observation/Decision/Motor are pre-commit (decision_tick T)
    and Consequence is T→T+1.
    """
    slots = getattr(runtime, "slots", None)
    if not slots:
        slots = [runtime]
        experimenter_slot = None
        single = True
    else:
        experimenter_slot = getattr(runtime, "experimenter_slot", None)
        single = False

    width, height = _world_size(runtime)
    spines: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    motors: list[dict[str, Any]] = []
    consequences: list[dict[str, Any]] = []

    for i, slot in enumerate(slots):
        cog_cfg = getattr(getattr(slot, "config", None), "cognition", None)
        cog_on = bool(getattr(cog_cfg, "cognition_enabled", False))
        controller_type, role_label = classify_controller(
            slot_index=i,
            experimenter_slot=experimenter_slot,
            cognition_enabled=cog_on,
        )
        body_id = physical_body_id_for_slot(i)
        cog_id = cognitive_agent_id_for_slot(i, controller_type=controller_type)

        # decision tick: prefer explicit stash; else post-increment tick - 1
        decision_tick = getattr(slot, "last_v3_decision_tick", None)
        if decision_tick is None:
            try:
                decision_tick = int(getattr(slot, "tick", 0)) - 1
            except Exception:
                decision_tick = -1
        decision_tick = int(decision_tick)
        if decision_tick < 0:
            continue

        identity_map.upsert_slot(
            slot_index=i,
            experimenter_slot=experimenter_slot,
            cognition_enabled=cog_on,
            tick=decision_tick,
        )

        before = getattr(slot, "last_v3_body_before", None)
        after = getattr(slot, "last_v3_body_after", None)
        if after is None:
            body = getattr(slot, "body", None)
            after = body.snapshot() if body is not None and hasattr(body, "snapshot") else {}

        event_refs = _event_refs_for_slot(runtime if not single else slot, i, decision_tick)
        man_rec = getattr(slot, "last_manipulator_receipt", None)
        if isinstance(man_rec, dict):
            hands = man_rec.get("hands") if isinstance(man_rec.get("hands"), dict) else None
            if hands:
                for mid, hrec in hands.items():
                    if not isinstance(hrec, dict):
                        continue
                    event_refs.append({
                        "kind": "manipulator",
                        "manipulator_id": str(hrec.get("manipulator_id") or mid),
                        "command": hrec.get("manipulator_action"),
                        "outcome": hrec.get("event"),
                        "object_id": hrec.get("researcher_only_object_id"),
                        "distance_reach": hrec.get("event"),
                        "occupancy_before": hrec.get("occupancy_before"),
                        "occupancy_after": hrec.get("occupancy_after"),
                        "work_debit": hrec.get("work_debit"),
                        "arbitration": hrec.get("arbitration") or man_rec.get("arbitration"),
                    })
            elif man_rec.get("event"):
                event_refs.append({
                    "kind": "manipulator",
                    "manipulator_id": man_rec.get("manipulator_id"),
                    "command": man_rec.get("manipulator_action"),
                    "outcome": man_rec.get("event"),
                    "object_id": man_rec.get("researcher_only_object_id"),
                    "occupancy_before": man_rec.get("occupancy_before"),
                    "occupancy_after": man_rec.get("occupancy_after"),
                    "work_debit": man_rec.get("work_debit"),
                })
        pair_rec = getattr(slot, "last_pair_receipt", None)
        if isinstance(pair_rec, dict) and pair_rec.get("pair_command") not in (None, "", "NONE"):
            event_refs.append({
                "kind": "held_object_pair",
                "command": pair_rec.get("pair_command"),
                "outcome": pair_rec.get("outcome"),
                "pair_state_before": pair_rec.get("pair_state_before"),
                "pair_state_after": pair_rec.get("pair_state_after"),
                "aperture_before": pair_rec.get("aperture_before"),
                "aperture_after": pair_rec.get("aperture_after"),
                "delta_aperture": pair_rec.get("delta_aperture"),
                "left_held": pair_rec.get("left_held"),
                "right_held": pair_rec.get("right_held"),
                "left_object_id": pair_rec.get("left_object_id"),
                "right_object_id": pair_rec.get("right_object_id"),
                "surface_distance_before": pair_rec.get("surface_distance_before"),
                "surface_distance_after": pair_rec.get("surface_distance_after"),
                "contact_before": pair_rec.get("contact_before"),
                "contact_after": pair_rec.get("contact_after"),
                "work_debit": pair_rec.get("work_debit"),
                "mixing": bool((pair_rec.get("material_transformation") or {}).get("outcome") == "MERGE_COMMITTED"),
            })
        transform_rec = getattr(slot, "last_material_transformation_receipt", None)
        if isinstance(transform_rec, dict) and int(transform_rec.get("tick", -1)) == decision_tick:
            event_refs.append({
                "kind": "material_transformation",
                **transform_rec,
            })
        deposit_rec = getattr(slot, "last_surface_deposition_receipt", None)
        if isinstance(deposit_rec, dict) and int(deposit_rec.get("tick", -1)) == decision_tick:
            event_refs.append({
                "kind": "surface_deposition",
                "event": deposit_rec.get("event"),
                "outcome": deposit_rec.get("outcome"),
                "event_id": deposit_rec.get("event_id"),
                "motor_command": deposit_rec.get("motor_command"),
                "source_manipulator": deposit_rec.get("source_manipulator"),
                "source_object_id": deposit_rec.get("source_object_id"),
                "deposit_id": deposit_rec.get("deposit_id"),
                "resolved_cell": deposit_rec.get("resolved_cell"),
                "source_state_before": deposit_rec.get("source_state_before"),
                "source_state_after": deposit_rec.get("source_state_after"),
                "deposit_state_before": deposit_rec.get("deposit_state_before"),
                "deposited_delta": deposit_rec.get("deposited_delta"),
                "deposit_state_after": deposit_rec.get("deposit_state_after"),
                "mass_residual": deposit_rec.get("mass_residual"),
                "quantity_residual": deposit_rec.get("quantity_residual"),
                "component_residuals": deposit_rec.get("component_residuals"),
                "causal_reason": deposit_rec.get("causal_reason"),
                "terrain_effects_applied": deposit_rec.get("terrain_effects_applied"),
                "source_removed": deposit_rec.get("source_removed"),
                "deposit_created": deposit_rec.get("deposit_created"),
                "deposit_updated": deposit_rec.get("deposit_updated"),
            })
        traction_rec = getattr(slot, "last_surface_traction_receipt", None)
        if isinstance(traction_rec, dict) and int(traction_rec.get("tick", -1)) == decision_tick:
            event_refs.append({
                "kind": "surface_traction",
                "event": traction_rec.get("event"),
                "tick": traction_rec.get("tick"),
                "body_id": traction_rec.get("body_id"),
                "selected_locomotor_command": traction_rec.get("selected_locomotor_command"),
                "deposit_id": traction_rec.get("deposit_id"),
                "resolved_cell": traction_rec.get("resolved_cell"),
                "deposit_eligible_this_tick": traction_rec.get("deposit_eligible_this_tick"),
                "deposition_event_ids": traction_rec.get("deposition_event_ids"),
                "derivation_version": traction_rec.get("derivation_version"),
                "surface_affinity": traction_rec.get("surface_affinity"),
                "formula_version": traction_rec.get("formula_version"),
                "traction_multiplier": traction_rec.get("traction_multiplier"),
                "requested_locomotor_dv": traction_rec.get("requested_locomotor_dv"),
                "traction_scaled_dv": traction_rec.get("traction_scaled_dv"),
                "realized_dv": traction_rec.get("realized_dv"),
                "v_max_clamped": traction_rec.get("v_max_clamped"),
                "displacement_this_tick": traction_rec.get("displacement_this_tick"),
                "causal_source": traction_rec.get("causal_source"),
                "causal_latency": traction_rec.get("causal_latency"),
                "energy_interpretation": traction_rec.get("energy_interpretation"),
                "deposit_consumed": traction_rec.get("deposit_consumed"),
                "recipe_match": traction_rec.get("recipe_match"),
            })
        experience_rec = getattr(slot, "last_traction_experience_receipt", None)
        if isinstance(experience_rec, dict) and int(
            experience_rec.get("consequence_observation_tick", -1)
        ) == decision_tick:
            researcher = experience_rec.get("researcher_only_fields") or {}
            event_refs.append({
                "kind": "traction_experience",
                "event": experience_rec.get("event"),
                "body_id": experience_rec.get("body_id"),
                "selected_motor_command": experience_rec.get("selected_motor_command"),
                "action_tick": experience_rec.get("action_tick"),
                "consequence_observation_tick": experience_rec.get("consequence_observation_tick"),
                "action_consequence_latency_ticks": experience_rec.get("action_consequence_latency_ticks"),
                "causal_order": experience_rec.get("causal_order"),
                "realized_dv": experience_rec.get("realized_dv"),
                "displacement": experience_rec.get("displacement"),
                "prediction_error_status": experience_rec.get("prediction_error_status"),
                "prediction_error_abs_l1": experience_rec.get("prediction_error_abs_l1"),
                "memory_status": experience_rec.get("memory_status"),
                "memory_reference": experience_rec.get("memory_reference"),
                "action_provenance": experience_rec.get("action_provenance"),
                "cognition_delivered": experience_rec.get("cognition_delivered"),
                "agent_visible_field_names": experience_rec.get("agent_visible_field_names"),
                "deposit_id": researcher.get("deposit_id"),
                "traction_multiplier": researcher.get("traction_multiplier"),
                "researcher_only": True,
                "agent_accessible": False,
            })
        prediction_rec = getattr(slot, "last_traction_prediction_receipt", None)
        if isinstance(prediction_rec, dict) and int(
            prediction_rec.get("consequence_observation_tick", -1)
        ) == decision_tick:
            event_refs.append({
                "kind": "traction_prediction_adaptation",
                "event": prediction_rec.get("event"),
                "body_id": prediction_rec.get("body_id"),
                "selected_motor_command": prediction_rec.get("selected_motor_command"),
                "action_tick": prediction_rec.get("action_tick"),
                "consequence_observation_tick": prediction_rec.get("consequence_observation_tick"),
                "prediction_issued_tick": prediction_rec.get("prediction_issued_tick"),
                "action_consequence_latency_ticks": prediction_rec.get("action_consequence_latency_ticks"),
                "causal_order": prediction_rec.get("causal_order"),
                "exposure_phase": prediction_rec.get("exposure_phase"),
                "episode_index": prediction_rec.get("episode_index"),
                "prediction_availability": prediction_rec.get("prediction_availability"),
                "aggregate_error": prediction_rec.get("aggregate_error"),
                "revision_applied": prediction_rec.get("revision_applied"),
                "model_state_reference": prediction_rec.get("model_state_reference"),
                "memory_status": prediction_rec.get("memory_status"),
                "memory_reference": prediction_rec.get("memory_reference"),
                "context_signature": prediction_rec.get("context_signature"),
                "action_provenance": prediction_rec.get("action_provenance"),
                "entered_adaptation_statistics": prediction_rec.get("entered_adaptation_statistics"),
                "exclusion_reason": prediction_rec.get("exclusion_reason"),
                "predicted_agent_visible_delta": prediction_rec.get("predicted_agent_visible_delta"),
                "observed_agent_visible_delta": prediction_rec.get("observed_agent_visible_delta"),
                "observed_agent_visible_absolute": prediction_rec.get("observed_agent_visible_absolute"),
                "per_field_error": prediction_rec.get("per_field_error"),
                "researcher_only_fields": {
                    "deposit_id": (prediction_rec.get("researcher_only_fields") or {}).get("deposit_id"),
                    "traction_multiplier": (prediction_rec.get("researcher_only_fields") or {}).get(
                        "traction_multiplier"
                    ),
                },
                "researcher_only": True,
                "agent_accessible": False,
            })
        coating_rec = getattr(slot, "last_surface_optical_coating_receipt", None)
        if isinstance(coating_rec, dict) and int(coating_rec.get("tick", -1)) == decision_tick:
            event_refs.append({
                "kind": "surface_optical_coating",
                "event": coating_rec.get("event"),
                "tick": coating_rec.get("tick"),
                "body_id": coating_rec.get("body_id"),
                "cell": coating_rec.get("cell"),
                "visibility": coating_rec.get("visibility"),
                "coverage": coating_rec.get("coverage"),
                "final_coated_response": coating_rec.get("final_coated_response"),
                "agent_symbolic_label": False,
                "traction_encoded_directly": False,
                "material_identity_exposed": False,
                "researcher_only": True,
                "agent_accessible": False,
            })
        material_tx = getattr(slot, "last_world_material_transaction", None)
        if isinstance(material_tx, dict) and int(material_tx.get("tick", -1)) == decision_tick:
            event_refs.append({
                "kind": "world_material_transaction",
                "event": material_tx.get("event"),
                "tick": material_tx.get("tick"),
                "transaction_id": material_tx.get("transaction_id"),
                "operation_kind": material_tx.get("operation_kind"),
                "status": material_tx.get("status"),
                "actor_body_id": material_tx.get("actor_body_id"),
                "researcher_only": True,
                "agent_accessible": False,
                "recipe_match": False,
                "reward_created": False,
            })
        spatial_event = getattr(getattr(slot, "world", None), "last_spatial_index_event", None)
        if isinstance(spatial_event, dict) and int(spatial_event.get("tick", -1)) == decision_tick:
            event_refs.append({
                "kind": "spatial_contents_index",
                "event": spatial_event.get("event"),
                "tick": spatial_event.get("tick"),
                "generation": spatial_event.get("generation"),
                "reason": spatial_event.get("reason"),
                "checksum": spatial_event.get("checksum"),
                "mismatch_count": spatial_event.get("mismatch_count"),
                "researcher_only": True,
                "agent_accessible": False,
                "physical_effects_applied": False,
            })
        lps_step = getattr(getattr(slot, "world", None), "last_local_signal_step", None)
        if (
            isinstance(lps_step, dict)
            and getattr(getattr(slot, "world", None), "local_signal_transport", None) is not None
            and int(lps_step.get("tick", -1)) == decision_tick
        ):
            # Researcher-only LOCAL PHYSICAL SIGNAL TRANSPORT receipts (emission at T, arrival at T+1).
            from mechanistic_mind.physical_system.spatial_contents import body_refs_for_runtime

            refs = body_refs_for_runtime(runtime)
            my_body = refs[i][0] if 0 <= i < len(refs) else None
            for em in lps_step.get("emissions") or []:
                src = em.get("source_body_id")
                if src == my_body or (src is None and i == 0):
                    event_refs.append({"kind": "local_physical_signal", **em,
                                       "researcher_only": True, "agent_accessible": False})
            for rc in lps_step.get("receptions") or []:
                if rc.get("receiver_body_id") == my_body:
                    event_refs.append({"kind": "local_physical_signal", **rc,
                                       "researcher_only": True, "agent_accessible": False})
        pca_step = getattr(getattr(slot, "world", None), "last_contact_acoustic_step", None)
        if (
            i == 0
            and isinstance(pca_step, dict)
            and getattr(getattr(slot, "world", None), "contact_acoustic_state", None) is not None
            and int(pca_step.get("tick", -1)) == decision_tick
        ):
            # Researcher-only PHYSICAL CONTACT ACOUSTIC provenance (one copy per shared-world tick).
            for m in pca_step.get("measurements") or []:
                event_refs.append({"kind": "physical_contact_acoustic", **m})
            for e in pca_step.get("emissions") or []:
                event_refs.append({"kind": "physical_contact_acoustic", **e})
        fok_step = getattr(getattr(slot, "world", None), "last_free_object_step", None)
        if (
            i == 0
            and isinstance(fok_step, dict)
            and getattr(getattr(slot, "world", None), "free_object_kinematics_state", None) is not None
            and int(fok_step.get("tick", -1)) == decision_tick
        ):
            # Researcher-only FREE RESOURCE OBJECT KINEMATICS provenance (one copy per shared-world tick).
            for r in fok_step.get("releases") or []:
                event_refs.append({"kind": "free_resource_object_kinematics", **r})
            for m in fok_step.get("motion") or []:
                event_refs.append({"kind": "free_resource_object_kinematics", **m})
        boc_step = getattr(getattr(slot, "world", None), "last_body_object_contact_step", None)
        if (
            i == 0
            and isinstance(boc_step, dict)
            and getattr(getattr(slot, "world", None), "body_object_contact_state", None) is not None
            and int(boc_step.get("tick", -1)) == decision_tick
        ):
            for r in (boc_step.get("begin") or []) + (boc_step.get("end") or []):
                event_refs.append({"kind": "body_resource_object_contact", **r})
            # Compact PERSIST: one aggregated row per tick (not every pair receipt).
            if boc_step.get("persist"):
                event_refs.append({
                    "kind": "body_resource_object_contact",
                    "contact_phase": "PERSIST_AGGREGATE",
                    "tick": boc_step.get("tick"),
                    "count": len(boc_step.get("persist") or []),
                    "active_episodes": boc_step.get("active_episodes"),
                    "contact_fact": True,
                    "collision_response_applied": False,
                    "impulse_transferred": False,
                    "position_corrected": False,
                    "velocity_changed": False,
                    "sound_emitted": False,
                    "agent_accessible": False,
                    "researcher_only": True,
                })
        # EBAE observability: link actuation receipts when a Z request was submitted.
        # Does not re-execute EBAE; researcher-only; never enters cognition.
        ebae_act = getattr(slot, "last_agent_effector_z_actuation", None)
        if isinstance(ebae_act, dict) and int(ebae_act.get("tick", -1)) == decision_tick:
            for hand in ("left", "right"):
                rec = ebae_act.get(hand)
                if not isinstance(rec, dict):
                    continue
                event_refs.append(
                    {
                        "kind": "effector_bounded_actuator_effort",
                        "receipt_kind": rec.get("receipt_kind") or "EFFECTOR_ACTUATOR_EFFORT",
                        "receipt_id": str(
                            rec.get("receipt_id")
                            or f"ebae:{decision_tick}:{rec.get('body_id')}:{str(hand).upper()}"
                        ),
                        "event": rec.get("event") or "EFFECTOR_ACTUATOR_EFFORT_STEP",
                        "status": rec.get("status"),
                        "tick": rec.get("tick", decision_tick),
                        "body_id": rec.get("body_id"),
                        "effector_id": rec.get("effector_id") or str(hand).upper(),
                        "requested_relative_delta": rec.get("requested_relative_delta"),
                        "achieved_relative_delta": rec.get("achieved_relative_delta"),
                        "kinematically_admissible_delta": rec.get("kinematically_admissible_delta"),
                        "relative_z_before": rec.get("relative_z_before"),
                        "relative_z_after": rec.get("relative_z_after"),
                        "work_used": rec.get("work_used"),
                        "work_attempted": rec.get("work_attempted"),
                        "capacity_saturated": rec.get("capacity_saturated"),
                        "rate_clipped": rec.get("rate_clipped"),
                        "reach_clipped": rec.get("reach_clipped"),
                        "opposing": rec.get("opposing"),
                        "external_constraint": rec.get("external_constraint"),
                        "motor_id": None,
                        "request_submitted": True,
                        "researcher_only": True,
                        "cognition_exposed": False,
                        "agent_accessible": False,
                    }
                )
            if ebae_act.get("status") in ("NONE", "CAPABILITY_OFF") and not any(
                isinstance(ebae_act.get(h), dict) for h in ("left", "right")
            ):
                event_refs.append(
                    {
                        "kind": "effector_bounded_actuator_effort",
                        "receipt_kind": "EFFECTOR_ACTUATOR_EFFORT",
                        "status": ebae_act.get("status"),
                        "tick": decision_tick,
                        "request_submitted": False,
                        "researcher_only": True,
                        "cognition_exposed": False,
                        "agent_accessible": False,
                    }
                )
        etc_step = getattr(getattr(slot, "world", None), "last_effector_terrain_contact_step", None)
        if (
            i == 0
            and isinstance(etc_step, dict)
            and getattr(getattr(slot, "world", None), "effector_terrain_contact_geometry_state", None) is not None
            and int(etc_step.get("tick", -1)) == decision_tick
        ):
            for r in etc_step.get("receipts") or []:
                event_refs.append({"kind": "effector_terrain_contact", **r})
        eort_step = getattr(
            getattr(slot, "world", None), "last_effector_occupancy_reachability_trace_step", None
        )
        if (
            i == 0
            and isinstance(eort_step, dict)
            and getattr(
                getattr(slot, "world", None),
                "effector_occupancy_reachability_trace_state",
                None,
            )
            is not None
            and int(eort_step.get("tick", -1)) == decision_tick
        ):
            for r in eort_step.get("traces") or []:
                event_refs.append({"kind": "effector_occupancy_reachability_trace", **r})
        hotc_step = getattr(
            getattr(slot, "world", None), "last_held_resource_object_terrain_contact_step", None
        )
        if (
            i == 0
            and isinstance(hotc_step, dict)
            and getattr(
                getattr(slot, "world", None),
                "held_resource_object_terrain_contact_geometry_state",
                None,
            )
            is not None
            and int(hotc_step.get("tick", -1)) == decision_tick
        ):
            for r in hotc_step.get("receipts") or []:
                event_refs.append({"kind": "held_resource_object_terrain_contact", **r})
        hotmt_rec = getattr(
            getattr(slot, "world", None),
            "last_held_resource_object_terrain_mechanical_transmission",
            None,
        )
        if (
            i == 0
            and isinstance(hotmt_rec, dict)
            and getattr(
                getattr(slot, "world", None),
                "held_resource_object_terrain_mechanical_transmission_state",
                None,
            )
            is not None
            and int(hotmt_rec.get("tick", -1)) == decision_tick
        ):
            event_refs.append(
                {"kind": "held_resource_object_terrain_mechanical_transmission", **hotmt_rec}
            )
        hmsi_rec = getattr(
            getattr(slot, "world", None),
            "last_held_mediated_surface_exertion_integration",
            None,
        )
        if (
            i == 0
            and isinstance(hmsi_rec, dict)
            and getattr(
                getattr(slot, "world", None),
                "held_mediated_surface_exertion_integration_state",
                None,
            )
            is not None
            and int(hmsi_rec.get("tick", -1)) == decision_tick
        ):
            event_refs.append(
                {"kind": "held_mediated_surface_exertion_integration", **hmsi_rec}
            )
        dtip_rec = getattr(
            getattr(slot, "world", None),
            "last_detached_terrain_material_initial_placement",
            None,
        )
        if (
            i == 0
            and isinstance(dtip_rec, dict)
            and getattr(
                getattr(slot, "world", None),
                "detached_terrain_material_initial_placement_state",
                None,
            )
            is not None
            and int(dtip_rec.get("tick", -1)) == decision_tick
        ):
            event_refs.append(
                {"kind": "detached_terrain_material_initial_placement", **dtip_rec}
            )
        bnlt_rep = getattr(
            getattr(slot, "world", None),
            "last_bnlt_move_breakaway_repair",
            None,
        )
        if (
            i == 0
            and isinstance(bnlt_rep, dict)
            and getattr(
                getattr(slot, "world", None),
                "bnlt_move_breakaway_locomotion_repair_state",
                None,
            )
            is not None
            and int(bnlt_rep.get("tick", -1)) == decision_tick
        ):
            event_refs.append(
                {"kind": "bnlt_move_breakaway_locomotion_repair", **bnlt_rep}
            )
        altvs = getattr(
            getattr(slot, "world", None),
            "last_active_locomotion_traction_vs_sliding_friction",
            None,
        )
        if (
            i == 0
            and isinstance(altvs, dict)
            and getattr(
                getattr(slot, "world", None),
                "active_locomotion_traction_vs_sliding_friction_state",
                None,
            )
            is not None
            and int(altvs.get("tick", -1)) == decision_tick
        ):
            event_refs.append(
                {"kind": "active_locomotion_traction_vs_sliding_friction", **altvs}
            )
        crowded_rec = getattr(
            getattr(slot, "world", None),
            "last_crowded_placement_retry",
            None,
        )
        if (
            i == 0
            and isinstance(crowded_rec, dict)
            and getattr(
                getattr(slot, "world", None),
                "event_driven_crowded_placement_retry_contract_state",
                None,
            )
            is not None
            and int(crowded_rec.get("tick", -1)) == decision_tick
        ):
            event_refs.append(
                {"kind": "crowded_placement_retry", **crowded_rec}
            )
        size_geo_rec = getattr(
            getattr(slot, "world", None),
            "last_detached_material_size_geometry",
            None,
        )
        if (
            i == 0
            and isinstance(size_geo_rec, dict)
            and getattr(
                getattr(slot, "world", None),
                "detached_material_amount_scaled_collision_radius_state",
                None,
            )
            is not None
            and int(size_geo_rec.get("creation_tick", size_geo_rec.get("tick", -1)) or -1)
            == decision_tick
        ):
            event_refs.append(
                {"kind": "DETACHED_MATERIAL_SIZE_GEOMETRY", **size_geo_rec}
            )
        held_combine_rec = getattr(
            getattr(slot, "world", None),
            "last_held_combine_geometry_resize",
            None,
        )
        if (
            i == 0
            and isinstance(held_combine_rec, dict)
            and getattr(
                getattr(slot, "world", None),
                "held_combine_radius_resize_transaction_state",
                None,
            )
            is not None
            and int(held_combine_rec.get("tick", -1)) == decision_tick
        ):
            event_refs.append(
                {"kind": "HELD_COMBINE_GEOMETRY_RESIZE", **held_combine_rec}
            )
        held_deposition_rec = getattr(
            getattr(slot, "world", None),
            "last_held_deposition_geometry_shrink",
            None,
        )
        if (
            i == 0
            and isinstance(held_deposition_rec, dict)
            and getattr(
                getattr(slot, "world", None),
                "held_deposition_radius_shrink_transaction_state",
                None,
            )
            is not None
            and int(held_deposition_rec.get("tick", -1)) == decision_tick
        ):
            event_refs.append(
                {"kind": "HELD_DEPOSITION_GEOMETRY_SHRINK", **held_deposition_rec}
            )
        landing_rec = getattr(
            getattr(slot, "world", None),
            "last_vertical_terrain_landing",
            None,
        )
        if (
            i == 0
            and isinstance(landing_rec, dict)
            and getattr(
                getattr(slot, "world", None),
                "vertical_terrain_landing_contact_response_state",
                None,
            )
            is not None
            and int(landing_rec.get("tick", -1)) == decision_tick
        ):
            event_refs.append(
                {"kind": "VERTICAL_TERRAIN_LANDING_V1", **landing_rec}
            )
        via_step = getattr(
            getattr(slot, "world", None),
            "last_vertical_impact_acoustic_step",
            None,
        )
        if (
            i == 0
            and isinstance(via_step, dict)
            and getattr(
                getattr(slot, "world", None),
                "vertical_impact_acoustic_emission_state",
                None,
            )
            is not None
            and int(via_step.get("tick", -1)) == decision_tick
        ):
            for m in via_step.get("measurements") or []:
                event_refs.append({"kind": "VERTICAL_IMPACT_ACOUSTIC_EMISSION", **m})
            for e in via_step.get("emissions") or []:
                event_refs.append({"kind": "VERTICAL_IMPACT_ACOUSTIC_EMISSION", **e})
        apas = getattr(
            getattr(slot, "world", None),
            "authoritative_physical_acoustic_stream_state",
            None,
        )
        if i == 0 and apas is not None:
            # Emit only records whose scientific_tick matches this decision tick.
            for row in list(getattr(apas, "records", None) or []):
                if not isinstance(row, dict):
                    continue
                if int(row.get("scientific_tick", -1)) != int(decision_tick):
                    continue
                event_refs.append(
                    {
                        "kind": "PHYSICAL_ACOUSTIC_STREAM_RECORD",
                        **{k: row.get(k) for k in row},
                    }
                )
            # One meta row per tick for capacity/eviction (Analyzer progress).
            if int(getattr(apas, "last_sync_tick", -1) or -1) == int(decision_tick) or any(
                int(r.get("scientific_tick", -1)) == int(decision_tick)
                for r in list(getattr(apas, "records", None) or [])
                if isinstance(r, dict)
            ):
                event_refs.append(
                    {
                        "kind": "PHYSICAL_ACOUSTIC_STREAM_RECORD",
                        "meta_only": True,
                        "history_capacity": int(getattr(apas, "capacity", 0) or 0),
                        "evicted_count": int(getattr(apas, "evicted_count", 0) or 0),
                        "retained_count": len(getattr(apas, "records", None) or []),
                        "schema": "AUTHORITATIVE_PHYSICAL_ACOUSTIC_STREAM_V1",
                    }
                )
        oap = getattr(
            getattr(slot, "world", None),
            "observer_acoustic_probe_state",
            None,
        )
        if i == 0 and oap is not None and bool(getattr(oap, "enabled", False)):
            for sample in list(getattr(oap, "samples", None) or []):
                if not isinstance(sample, dict):
                    continue
                if int(sample.get("scientific_tick", -1)) != int(decision_tick):
                    continue
                event_refs.append(
                    {"kind": "OBSERVER_ACOUSTIC_PROBE_SAMPLE", **dict(sample)}
                )
            if int(getattr(oap, "last_sample_tick", -1) or -1) == int(decision_tick):
                event_refs.append(
                    {
                        "kind": "OBSERVER_ACOUSTIC_PROBE_SAMPLE",
                        "meta_only": True,
                        "history_capacity": int(getattr(oap, "capacity", 0) or 0),
                        "evicted_count": int(getattr(oap, "evicted_count", 0) or 0),
                        "probe_id": getattr(oap, "probe_id", None),
                        "schema": "OBSERVER_ACOUSTIC_PROBE_V1",
                    }
                )
        soab = getattr(
            getattr(slot, "world", None),
            "selected_organism_auditory_boundary_state",
            None,
        )
        if soab is not None:
            slot_aid = str(cog_id or getattr(slot, "technical_id", None) or "")
            for rec in list(getattr(soab, "receipts", None) or []):
                if not isinstance(rec, dict):
                    continue
                if int(rec.get("scientific_tick", -1)) != int(decision_tick):
                    continue
                if slot_aid and str(rec.get("agent_id") or "") not in ("", slot_aid):
                    continue
                event_refs.append(
                    {
                        "kind": "ORGANISM_AUDITORY_BOUNDARY_RECEIPT",
                        "schema": "SELECTED_ORGANISM_AUDITORY_BOUNDARY_RECEIPT_V1",
                        "receipt_id": rec.get("receipt_id"),
                        "scientific_tick": rec.get("scientific_tick"),
                        "agent_id": rec.get("agent_id"),
                        "body_id": rec.get("body_id"),
                        "profile": rec.get("profile"),
                        "boundary": rec.get("boundary"),
                        "section_a_organism_accessible": rec.get("section_a_organism_accessible"),
                        "section_b_researcher_provenance": {
                            "organism_accessible": False,
                            "phenotype_clip_stamp": (
                                (rec.get("section_b_researcher_provenance") or {}).get(
                                    "phenotype_clip_stamp"
                                )
                            ),
                            "observation_key": (
                                (rec.get("section_b_researcher_provenance") or {}).get(
                                    "observation_key"
                                )
                            ),
                        },
                        "researcher_only": True,
                        "agent_accessible": False,
                        "meta_only": False,
                    }
                )
        oatt = getattr(
            getattr(slot, "world", None),
            "organism_auditory_transformation_trace_state",
            None,
        )
        if oatt is not None:
            slot_aid = str(cog_id or getattr(slot, "technical_id", None) or "")
            for tr in list(getattr(oatt, "traces", None) or []):
                if not isinstance(tr, dict):
                    continue
                if int(tr.get("observation_tick", tr.get("scientific_tick", -1))) != int(
                    decision_tick
                ):
                    continue
                if slot_aid and str(tr.get("agent_id") or "") not in ("", slot_aid):
                    continue
                a3 = tr.get("a3") or {}
                a4 = tr.get("a4") or {}
                a5 = tr.get("a5") or {}
                event_refs.append(
                    {
                        "kind": "ORGANISM_AUDITORY_TRANSFORMATION_TRACE",
                        "schema": "ORGANISM_AUDITORY_TRANSFORMATION_TRACE_V1",
                        "trace_id": tr.get("trace_id"),
                        "profile": tr.get("profile"),
                        "completion_status": tr.get("completion_status"),
                        "reception_tick": tr.get("reception_tick"),
                        "observation_tick": tr.get("observation_tick"),
                        "causal_delay_ticks": tr.get("causal_delay_ticks"),
                        "agent_id": tr.get("agent_id"),
                        "body_id": tr.get("body_id"),
                        "sav1_receipt_id": tr.get("sav1_receipt_id"),
                        "observation_key": tr.get("observation_key"),
                        "a3_left": a3.get("left_receptor_band_energy"),
                        "a3_right": a3.get("right_receptor_band_energy"),
                        "a4_sensor_scale": a4.get("sensor_scale"),
                        "a4_clipping_count": a4.get("clipping_count"),
                        "transform_residual": a4.get("transform_residual"),
                        "a5_left": a5.get("left_receptor_channels"),
                        "a5_right": a5.get("right_receptor_channels"),
                        "authority": tr.get("authority"),
                        "limitations": tr.get("limitations"),
                        "researcher_only": True,
                        "agent_accessible": False,
                        "meta_only": False,
                    }
                )
        # C0 calibration reference once per slot-0 tick when LPS acoustic path is active.
        if (
            i == 0
            and getattr(getattr(slot, "world", None), "local_signal_transport", None) is not None
        ):
            from mechanistic_mind.physical_system.physical_frequency_amplitude_calibration_contract import (
                c0_calibration_reference,
            )

            event_refs.append(
                {
                    "kind": "PHYSICAL_FREQUENCY_AMPLITUDE_CALIBRATION_CONTRACT",
                    "meta_only": True,
                    **c0_calibration_reference(),
                }
            )
        resli_st = getattr(
            getattr(slot, "world", None),
            "release_and_excavation_support_loss_integration_state",
            None,
        )
        if i == 0 and resli_st is not None:
            last = getattr(resli_st, "last_receipt", None)
            if isinstance(last, dict) and int(last.get("tick", -1)) == decision_tick:
                event_refs.append(
                    {"kind": "RELEASE_EXCAVATION_SUPPORT_LOSS_V1", **last}
                )
        free_space_rec = getattr(
            getattr(slot, "world", None),
            "last_free_space_support_state",
            None,
        )
        if (
            i == 0
            and isinstance(free_space_rec, dict)
            and getattr(
                getattr(slot, "world", None),
                "free_space_state_and_pe_authority_contract_state",
                None,
            )
            is not None
            and int(free_space_rec.get("tick", -1)) == decision_tick
        ):
            event_refs.append(
                {"kind": "FREE_SPACE_SUPPORT_STATE_V1", **free_space_rec}
            )
        rcss_rec = getattr(
            getattr(slot, "world", None),
            "last_repeated_conservative_surface_column_separation",
            None,
        )
        if (
            i == 0
            and isinstance(rcss_rec, dict)
            and getattr(
                getattr(slot, "world", None),
                "repeated_conservative_surface_column_separation_state",
                None,
            )
            is not None
            and int(rcss_rec.get("tick", -1)) == decision_tick
        ):
            event_refs.append(
                {"kind": "repeated_conservative_surface_column_separation", **rcss_rec}
            )
        boi_step = getattr(getattr(slot, "world", None), "last_body_object_contact_impulse_step", None)
        if (
            i == 0
            and isinstance(boi_step, dict)
            and getattr(getattr(slot, "world", None), "body_object_contact_impulse_state", None) is not None
            and int(boi_step.get("tick", -1)) == decision_tick
        ):
            for r in boi_step.get("responses") or []:
                event_refs.append({"kind": "body_resource_object_contact_response", **r})
        oia_step = getattr(getattr(slot, "world", None), "last_body_object_impact_acoustic_step", None)
        if (
            i == 0
            and isinstance(oia_step, dict)
            and getattr(getattr(slot, "world", None), "body_object_impact_acoustic_state", None) is not None
            and int(oia_step.get("tick", -1)) == decision_tick
        ):
            # Researcher-only BODY/OBJECT IMPACT ACOUSTIC provenance (one copy per shared-world tick).
            for m in oia_step.get("measurements") or []:
                event_refs.append({"kind": "body_object_impact_acoustics", **m})
            for e in oia_step.get("emissions") or []:
                event_refs.append({"kind": "body_object_impact_acoustics", **e})
        ooc_step = getattr(getattr(slot, "world", None), "last_resource_object_pair_contact_step", None)
        if (
            i == 0
            and isinstance(ooc_step, dict)
            and getattr(getattr(slot, "world", None), "resource_object_pair_contact_state", None) is not None
            and int(ooc_step.get("tick", -1)) == decision_tick
        ):
            for r in (ooc_step.get("begin") or []) + (ooc_step.get("end") or []):
                event_refs.append({"kind": "resource_object_pair_contact", **r})
            if ooc_step.get("persist"):
                event_refs.append({
                    "kind": "resource_object_pair_contact",
                    "contact_phase": "PERSIST_AGGREGATE",
                    "tick": ooc_step.get("tick"),
                    "count": len(ooc_step.get("persist") or []),
                    "active_episodes": ooc_step.get("active_episodes"),
                    "broad_phase_strategy": ooc_step.get("broad_phase_strategy"),
                    "contact_fact": True,
                    "collision_response_applied": False,
                    "impulse_transferred": False,
                    "position_corrected": False,
                    "velocity_changed": False,
                    "sound_emitted": False,
                    "composition_changed": False,
                    "agent_accessible": False,
                    "researcher_only": True,
                })
        ooi_step = getattr(getattr(slot, "world", None), "last_resource_object_pair_contact_impulse_step", None)
        if (
            i == 0
            and isinstance(ooi_step, dict)
            and getattr(getattr(slot, "world", None), "resource_object_pair_contact_impulse_state", None) is not None
            and int(ooi_step.get("tick", -1)) == decision_tick
        ):
            for r in ooi_step.get("responses") or []:
                event_refs.append({"kind": "resource_object_pair_contact_response", **r})
        ooia_step = getattr(getattr(slot, "world", None), "last_resource_object_pair_impact_acoustic_step", None)
        if (
            i == 0
            and isinstance(ooia_step, dict)
            and getattr(getattr(slot, "world", None), "resource_object_pair_impact_acoustic_state", None) is not None
            and int(ooia_step.get("tick", -1)) == decision_tick
        ):
            for m in ooia_step.get("measurements") or []:
                event_refs.append({"kind": "resource_object_pair_impact_acoustics", **m})
            for e in ooia_step.get("emissions") or []:
                event_refs.append({"kind": "resource_object_pair_impact_acoustics", **e})

        sdc_state = getattr(getattr(slot, "world", None), "ses_decomposition_contract_state", None)
        if sdc_state is not None:
            # Researcher-only G2C1 SES decomposition contract receipts for this decision tick.
            # Body receipts go to their own slot; object/world receipts only on slot 0 (shared world),
            # so each application_key appears in exactly one consequence. Capture never emits receipts.
            sdc_body_id = str(getattr(slot, "technical_id", None) or f"agent_{i}")
            for r in list(getattr(sdc_state, "history", None) or []):
                if not isinstance(r, dict) or int(r.get("tick", -1)) != decision_tick:
                    continue
                if r.get("entity_kind") == "body":
                    if str(r.get("entity_id")) != sdc_body_id:
                        continue
                elif i != 0:
                    continue
                event_refs.append({"kind": "ses_decomposition_contract", **r})
        srtc_state = getattr(getattr(slot, "world", None), "ses_runtime_transition_classifier_state", None)
        if srtc_state is not None:
            # Researcher-only G2C2 runtime classifier receipts (same slot partitioning as G2C1).
            srtc_body_id = str(getattr(slot, "technical_id", None) or f"agent_{i}")
            for r in list(getattr(srtc_state, "history", None) or []):
                if not isinstance(r, dict) or int(r.get("tick", -1)) != decision_tick:
                    continue
                if r.get("entity_kind") == "body":
                    if str(r.get("entity_id")) != srtc_body_id:
                        continue
                elif i != 0:
                    continue
                event_refs.append({"kind": "ses_runtime_transition_classifier", **r})
        rafs_state = getattr(getattr(slot, "world", None), "radius_aware_face_sweep_state", None)
        if rafs_state is not None:
            # Researcher-only radius face-sweep receipts (same slot partitioning as G2C2).
            rafs_body_id = str(getattr(slot, "technical_id", None) or f"agent_{i}")
            for r in list(getattr(rafs_state, "history", None) or []):
                if not isinstance(r, dict) or int(r.get("tick", -1)) != decision_tick:
                    continue
                if r.get("entity_kind") == "body":
                    if str(r.get("entity_id")) != rafs_body_id:
                        continue
                elif i != 0:
                    continue
                event_refs.append({"kind": "radius_aware_face_sweep", **r})
        dnls_state = getattr(getattr(slot, "world", None), "diagnostic_normal_load_shadow_state", None)
        if dnls_state is not None:
            dnls_body_id = str(getattr(slot, "technical_id", None) or f"agent_{i}")
            for r in list(getattr(dnls_state, "history", None) or []):
                if not isinstance(r, dict) or int(r.get("tick", -1)) != decision_tick:
                    continue
                if r.get("entity_kind") in ("body", "experimenter"):
                    if str(r.get("entity_id")) != dnls_body_id:
                        continue
                elif i != 0:
                    continue
                event_refs.append({"kind": "diagnostic_normal_load_shadow", **r})

        cgpe_state = getattr(getattr(slot, "world", None), "continuous_gravitational_pe_diagnostic_shadow_state", None)
        if cgpe_state is not None:
            cgpe_body_id = str(getattr(slot, "technical_id", None) or f"agent_{i}")
            for r in list(getattr(cgpe_state, "history", None) or []):
                if not isinstance(r, dict) or int(r.get("tick", -1)) != decision_tick:
                    continue
                if r.get("entity_kind") in ("body", "experimenter"):
                    if str(r.get("entity_id")) != cgpe_body_id:
                        continue
                elif i != 0:
                    continue
                event_refs.append({"kind": "continuous_gravitational_pe_diagnostic_shadow", **r})
        hfc_step = getattr(getattr(slot, "world", None), "last_held_foreign_body_contact_step", None)
        if (
            i == 0
            and isinstance(hfc_step, dict)
            and getattr(getattr(slot, "world", None), "held_foreign_body_contact_state", None) is not None
            and int(hfc_step.get("tick", -1)) == decision_tick
        ):
            for r in (hfc_step.get("begin") or []) + (hfc_step.get("end") or []):
                event_refs.append({"kind": "held_resource_object_foreign_body_contact", **r})
            if hfc_step.get("persist"):
                event_refs.append({
                    "kind": "held_resource_object_foreign_body_contact",
                    "contact_phase": "PERSIST_AGGREGATE",
                    "tick": hfc_step.get("tick"),
                    "count": len(hfc_step.get("persist") or []),
                    "active_episodes": hfc_step.get("active_episodes"),
                    "contact_fact": True,
                    "collision_response_applied": False,
                    "impulse_transferred": False,
                    "position_corrected": False,
                    "velocity_changed": False,
                    "sound_emitted": False,
                    "damage_applied": False,
                    "auto_release": False,
                    "holder_mediation": False,
                    "agent_accessible": False,
                    "researcher_only": True,
                })
        hti_step = getattr(getattr(slot, "world", None), "last_held_translational_impulse_step", None)
        if (
            i == 0
            and isinstance(hti_step, dict)
            and getattr(getattr(slot, "world", None), "held_translational_impulse_state", None) is not None
            and int(hti_step.get("tick", -1)) == decision_tick
        ):
            for r in (hti_step.get("receipts") or []):
                event_refs.append({"kind": "held_resource_object_translational_impulse_mediation", **r})
            event_refs.append({
                "kind": "held_resource_object_translational_impulse_mediation",
                "contact_phase": "RESPONSE_STEP",
                "tick": hti_step.get("tick"),
                "responses": hti_step.get("responses"),
                "impulses_applied": hti_step.get("impulses_applied"),
                "translationally_eligible": hti_step.get("translationally_eligible"),
                "effector_work_unresolved": hti_step.get("effector_work_unresolved"),
                "multi_constraint_unresolved": hti_step.get("multi_constraint_unresolved"),
                "object_remains_held": True,
                "automatic_release": False,
                "damage_applied": False,
                "sound_emitted": False,
                "agent_accessible": False,
                "researcher_only": True,
            })
        ehl_step = getattr(getattr(slot, "world", None), "last_effector_work_held_load_step", None)
        if (
            i == 0
            and isinstance(ehl_step, dict)
            and getattr(getattr(slot, "world", None), "effector_work_held_load_state", None) is not None
            and int(ehl_step.get("tick", -1)) == decision_tick
        ):
            event_refs.append({
                "kind": "effector_work_and_held_load_inertia_accounting",
                "receipt_kind": ehl_step.get("receipt_kind"),
                "receipt_id": ehl_step.get("receipt_id"),
                "source": ehl_step.get("source"),
                "tick": ehl_step.get("tick"),
                "work_debit": ehl_step.get("work_debit"),
                "admission_scale": ehl_step.get("admission_scale"),
                "work_limited": ehl_step.get("work_limited"),
                "work_unavailable": ehl_step.get("work_unavailable"),
                "work_positive_requested_total": ehl_step.get("work_positive_requested_total"),
                "aperture_desired_delta": ehl_step.get("aperture_desired_delta"),
                "aperture_admitted_delta": ehl_step.get("aperture_admitted_delta"),
                "UNACCOUNTED_EFFECTOR_WORK_PRODUCES_IMPULSE": False,
                "ACCOUNTED_EFFECTOR_WORK_PRODUCES_SWING_IMPULSE": False,
                "damage_applied": False,
                "sound_emitted": False,
                "swing_impulse": False,
                "agent_accessible": False,
                "researcher_only": True,
            })
        column_event = getattr(getattr(slot, "world", None), "last_surface_column_event", None)
        if (
            isinstance(column_event, dict)
            and int(column_event.get("world_tick", -1)) == decision_tick
            and str(column_event.get("event") or "").startswith("SURFACE_COLUMN_TRANSFER")
        ):
            # Researcher-only conservative column transfer (TRANSFER_SURFACE_COLUMN_SLICE).
            event_refs.append({
                "kind": "surface_column_transfer",
                "event": column_event.get("event"),
                "tick": column_event.get("world_tick"),
                "status": column_event.get("status"),
                "rejection_reason": column_event.get("rejection_reason"),
                "transaction_id": column_event.get("transaction_id"),
                "transfer_id": column_event.get("transfer_id"),
                "source_cell": column_event.get("source_cell"),
                "destination_cell": column_event.get("destination_cell"),
                "requested_thickness": column_event.get("requested_thickness"),
                "committed_thickness": column_event.get("committed_thickness"),
                "source_revision_before": column_event.get("source_revision_before"),
                "source_revision_after": column_event.get("source_revision_after"),
                "destination_revision_before": column_event.get("destination_revision_before"),
                "destination_revision_after": column_event.get("destination_revision_after"),
                "source_elevation_before": column_event.get("source_elevation_before"),
                "source_elevation_after": column_event.get("source_elevation_after"),
                "destination_elevation_before": column_event.get("destination_elevation_before"),
                "destination_elevation_after": column_event.get("destination_elevation_after"),
                "source_resolved_depth_before": column_event.get("source_resolved_depth_before"),
                "source_resolved_depth_after": column_event.get("source_resolved_depth_after"),
                "destination_resolved_depth_before": column_event.get("destination_resolved_depth_before"),
                "destination_resolved_depth_after": column_event.get("destination_resolved_depth_after"),
                "transferred_mass_per_area": column_event.get("transferred_mass_per_area"),
                "transferred_quantity_per_area": column_event.get("transferred_quantity_per_area"),
                "conservation_verified": column_event.get("conservation_verified"),
                "conservation_residual_max": column_event.get("conservation_residual_max"),
                "layer_merge_status": column_event.get("layer_merge_status"),
                "atomic_pair": column_event.get("atomic_pair"),
                "transfer_delta_count": column_event.get("transfer_delta_count"),
                "closed_world_residual_max": column_event.get("closed_world_residual_max"),
                "selection_provenance": column_event.get("selection_provenance"),
                "researcher_only": True,
                "agent_action": False,
                "agent_accessible": False,
                "physical_effects_active": False,
                "resource_spawned": False,
                "geometry_role": "METADATA_ONLY",
            })
        elif isinstance(column_event, dict) and int(column_event.get("world_tick", -1)) == decision_tick:
            event_refs.append({
                "kind": "surface_column",
                "event": column_event.get("event"),
                "tick": column_event.get("world_tick"),
                "cell": column_event.get("cell"),
                "status": column_event.get("status"),
                "delta_id": column_event.get("delta_id"),
                "delta_revision": column_event.get("delta_revision"),
                "baseline_checksum": column_event.get("baseline_checksum"),
                "resolved_checksum": column_event.get("resolved_checksum"),
                "generator_version": column_event.get("generator_version"),
                "interval_validation": (
                    column_event["interval_validation"].get("verified")
                    if isinstance(column_event.get("interval_validation"), dict)
                    else column_event.get("interval_validation")
                ),
                "conservation_verified": (
                    column_event["conservation"].get("verified")
                    if isinstance(column_event.get("conservation"), dict)
                    else None
                ),
                "researcher_only": True,
                "agent_accessible": False,
                "physical_effects_active": False,
                "geometry_role": "METADATA_ONLY",
            })

        # Autonomous cognitive agents get full O→D→M→C
        if controller_type == CONTROLLER_AUTONOMOUS and cog_id:
            obs_map = compact_accessible_observation(
                getattr(slot, "last_agent_observation", None)
            )
            obs_r = build_observation_receipt(
                run_id=run_id,
                tick=decision_tick,
                cognitive_agent_id=cog_id,
                physical_body_id=body_id,
                accessible=obs_map,
            )
            mid = motor_id(run_id, decision_tick, cog_id)
            did = decision_id(run_id, decision_tick, cog_id)
            oid = observation_id(run_id, decision_tick, cog_id)

            motor_out = getattr(slot, "last_motor_output", None)
            if not isinstance(motor_out, dict):
                motor_out = None
            include_manip = False
            include_bilat = False
            try:
                from mechanistic_mind.physical_system.physical_manipulator import (
                    bilateral_grasp_release_is_active,
                    bring_together_is_active,
                    grasp_release_is_active,
                )
                include_manip = bool(grasp_release_is_active(getattr(slot, "config", None)))
                include_bilat = bool(bilateral_grasp_release_is_active(getattr(slot, "config", None)))
                include_pair = bool(bring_together_is_active(getattr(slot, "config", None)))
            except Exception:
                include_manip = False
                include_bilat = False
                include_pair = False
            motor_r = build_motor_receipt(
                run_id=run_id,
                tick=decision_tick,
                cognitive_agent_id=cog_id,
                physical_body_id=body_id,
                decision_id_value=did,
                motor_output=motor_out,
                include_manipulator_channel=include_manip,
                include_bilateral_channels=include_bilat,
                include_pair_channel=include_pair,
            )

            last_sel = {}
            cog = getattr(slot, "cognition", None)
            if isinstance(cog, dict):
                last_sel = cog.get("last_selection") or {}
            sel_source = None
            sel_rule = None
            if isinstance(last_sel, dict):
                sel_source = last_sel.get("source")
                sel_rule = last_sel.get("selection_rule")
            if motor_out and isinstance(motor_out, dict) and motor_out.get("selection_source"):
                sel_source = sel_source or motor_out.get("selection_source")
            elif motor_out is not None and hasattr(motor_out, "selection_source"):
                sel_source = sel_source or getattr(motor_out, "selection_source", None)

            dec_r = build_decision_receipt(
                run_id=run_id,
                tick=decision_tick,
                cognitive_agent_id=cog_id,
                physical_body_id=body_id,
                observation_id_value=oid,
                motor_id_value=mid,
                last_selection=last_sel if isinstance(last_sel, dict) else {},
                selected_action=getattr(slot, "last_selected_action", None),
                selection_source=str(sel_source) if sel_source else None,
                selection_rule=str(sel_rule) if sel_rule else None,
            )

            # Motor factor Z request authority: prefer motor receipt components.
            z_motor = motor_out if isinstance(motor_out, dict) else {}
            comps = (motor_r or {}).get("components") if isinstance(motor_r, dict) else None
            if isinstance(comps, dict):
                z_motor = {
                    "effector_z_left": comps.get("effector_z_left", 0),
                    "effector_z_right": comps.get("effector_z_right", 0),
                }

            # Exact researcher lineage joins (no physics/optics recompute).
            _append_actuation_etc_exact_lineage(
                event_refs=event_refs,
                slot=slot,
                decision_tick=decision_tick,
                body_id=body_id,
                run_id=run_id,
                motor_id_value=mid,
                motor_out=z_motor,
            )
            _append_o3_o4_exact_lineage(
                event_refs=event_refs,
                slot=slot,
                decision_tick=decision_tick,
                body_id=body_id,
                run_id=run_id,
                observation_id_value=oid,
            )

            cons_r = build_consequence_receipt(
                run_id=run_id,
                tick_from=decision_tick,
                body_id=body_id,
                motor_id_value=mid,
                cognitive_agent_id=cog_id,
                before=before if isinstance(before, dict) else {},
                after=after if isinstance(after, dict) else {},
                world_width=width,
                world_height=height,
                event_refs=event_refs,
            )
            pose = cons_r["pose_delta"]
            cons_r["attribution"] = _derive_attribution(
                motor_r, event_refs, float(pose["dx"]), float(pose["dy"])
            )

            observations.append(obs_r)
            decisions.append(dec_r)
            motors.append(motor_r)
            consequences.append(cons_r)
            spines.append({
                "schema": "mm.scientific_v3.spine.core.v1",
                "run_id": run_id,
                "tick": decision_tick,
                "cognitive_agent_id": cog_id,
                "physical_body_id": body_id,
                "controller_type": controller_type,
                "role_label": role_label,
                "observation_id": oid,
                "decision_id": did,
                "motor_id": mid,
                "consequence_id": cons_r["consequence_id"],
            })
        else:
            # Still record consequence for body when we have before/after (identity coverage).
            cons_r = build_consequence_receipt(
                run_id=run_id,
                tick_from=decision_tick,
                body_id=body_id,
                motor_id_value=None,
                cognitive_agent_id=cog_id,
                before=before if isinstance(before, dict) else {},
                after=after if isinstance(after, dict) else {},
                world_width=width,
                world_height=height,
                event_refs=event_refs,
                attribution="EXPERIMENTER_CONTROL" if controller_type == CONTROLLER_EXPERIMENTER else "UNKNOWN",
            )
            consequences.append(cons_r)
            spines.append({
                "schema": "mm.scientific_v3.spine.core.v1",
                "run_id": run_id,
                "tick": decision_tick,
                "cognitive_agent_id": cog_id,
                "physical_body_id": body_id,
                "controller_type": controller_type,
                "role_label": role_label,
                "observation_id": None,
                "decision_id": None,
                "motor_id": None,
                "consequence_id": cons_r["consequence_id"],
                "note": "Non-autonomous slot — no O→D→M chain",
            })

    cov = empty_coverage(tier="CORE")
    mark(cov, "identity", COMPLETE if identity_map.entries else NOT_RECORDED)
    mark(cov, "tick_history", COMPLETE if spines else NOT_RECORDED)
    mark(cov, "observation", COMPLETE if observations else NOT_RECORDED)
    mark(cov, "decision", COMPLETE if decisions else NOT_RECORDED)
    mark(cov, "composite_motor", COMPLETE if motors else NOT_RECORDED)
    mark(cov, "consequence", COMPLETE if consequences else NOT_RECORDED)
    mark(cov, "trajectory", PARTIAL if consequences else NOT_RECORDED)
    mark(cov, "resources", PARTIAL if consequences else NOT_RECORDED)
    mark(cov, "vision", NOT_RECORDED)  # CORE: only via accessible obs channels if present
    mark(cov, "signals", NOT_RECORDED)
    mark(cov, "cognition", COMPLETE if decisions else NOT_RECORDED)
    mark(cov, "interaction", PARTIAL if any(c.get("event_refs") for c in consequences) else NOT_RECORDED)
    has_exp = any(
        e.get("controller_type") == CONTROLLER_EXPERIMENTER for e in identity_map.entries.values()
    )
    mark(cov, "experimenter", COMPLETE if has_exp else NOT_APPLICABLE)

    # If accessible obs contains exo_/vision-like keys, upgrade vision to PARTIAL
    if any(
        any(str(k).startswith(("exo_", "vision", "opt_", "surface_c", "spatial_")) for k in (o.get("accessible") or {}))
        for o in observations
    ):
        mark(cov, "vision", PARTIAL)
    if any(
        any(str(k).startswith(("local.FIELD", "signal")) for k in (o.get("accessible") or {}))
        for o in observations
    ):
        mark(cov, "signals", PARTIAL)

    return {
        "spines": spines,
        "observations": observations,
        "decisions": decisions,
        "motors": motors,
        "consequences": consequences,
        "coverage": cov,
    }
