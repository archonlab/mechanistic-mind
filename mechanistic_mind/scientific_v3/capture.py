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
            motor_r = build_motor_receipt(
                run_id=run_id,
                tick=decision_tick,
                cognitive_agent_id=cog_id,
                physical_body_id=body_id,
                decision_id_value=did,
                motor_output=motor_out,
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
            if motor_out and motor_out.get("selection_source"):
                sel_source = sel_source or motor_out.get("selection_source")

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
        any(str(k).startswith(("exo_", "vision", "opt_")) for k in (o.get("accessible") or {}))
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
