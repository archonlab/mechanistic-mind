"""BETA2-INT-01: experimenter-controlled Tiktaalik — ordinary body, human actions.

Observer/experimenter instrument only. Autonomous cognition never receives
experimenter identity. Actions are requested; physics realizes them.
"""
from __future__ import annotations

import time
from collections import deque
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime, agent_seed
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.ui.psy_observer_web.signal_context.intervention import (
    scientific_fingerprint,
    stable_id,
)

VALID_MOVE = {"MOVE:N", "MOVE:S", "MOVE:E", "MOVE:W", "WAIT"}
COMMAND_QUEUE_MAX = 64
EVENT_LOG_MAX = 512

MOBILITY_ORDINARY = "ORDINARY_WORK"
MOBILITY_RESEARCH = "RESEARCH_MOBILITY"
VALID_MOBILITY = {MOBILITY_ORDINARY, MOBILITY_RESEARCH}
RESEARCH_SUPPLY_SOURCE = "EXPERIMENTER_RESEARCH_SUPPLY"


@dataclass
class ExperimenterCommand:
    """Simulation-tick scheduled command (not wall-clock)."""

    sim_tick: int  # apply when runtime.tick == sim_tick (before step), or relative
    kind: str  # ACTION | FIELD_A | FIELD_B | OSC_EMIT | SPECIMEN_REPLAY | WAIT_RELATIVE
    action: str | None = None
    amplitude: float | None = None
    frequency: float | None = None
    duration: int | None = None
    specimen_id: str | None = None
    relative: bool = True  # if True, sim_tick is offset from enqueue time


@dataclass
class ExperimenterInteractionSpecimen:
    """Captured human interaction for deterministic scripted replay."""

    capture_id: str
    run_id: str
    start_tick: int
    end_tick: int
    s0_snapshot: dict[str, Any] | None
    commands: list[dict[str, Any]]
    events: list[dict[str, Any]]
    spawn: dict[str, Any]
    target_agent_id: str | None = None
    note: str = "EXPLORATORY_HUMAN_INTERACTION"

    def to_dict(self) -> dict[str, Any]:
        return {
            "capture_id": self.capture_id,
            "run_id": self.run_id,
            "start_tick": self.start_tick,
            "end_tick": self.end_tick,
            "has_s0": self.s0_snapshot is not None,
            "commands": list(self.commands),
            "events": list(self.events)[-200:],
            "spawn": self.spawn,
            "target_agent_id": self.target_agent_id,
            "note": self.note,
            "honesty": {"exploratory_only": True, "not_causal": True},
        }


class ExperimenterController:
    """Human action source for an ordinary Tiktaalik body (no fake cognition)."""

    def __init__(self) -> None:
        self.active = False
        self.slot_index: int | None = None
        self.body_id = "body-2"  # updated on spawn to body-{slot}; never a second physical body
        self.observer_label = "UNDERCOVER"  # Observer-only visual
        self.agent_id = "undercover"
        self.command_queue: deque[ExperimenterCommand] = deque(maxlen=COMMAND_QUEUE_MAX)
        self.event_log: deque[dict[str, Any]] = deque(maxlen=EVENT_LOG_MAX)
        self.scripted_commands: list[dict[str, Any]] = []
        self.recording = False
        self.record_start_tick: int | None = None
        self.s0_snapshot: dict[str, Any] | None = None
        self.spawn_meta: dict[str, Any] = {}
        self.target_agent_id: str | None = None
        self.last_requested: str | None = None
        self.last_realized: dict[str, Any] | None = None
        self.intervention_active = False
        self.captures: list[ExperimenterInteractionSpecimen] = []
        self.mobility_mode: str = MOBILITY_ORDINARY
        self.last_research_supply: dict[str, Any] | None = None

    def status(self) -> dict[str, Any]:
        if not self.active:
            return {"status": "NOT_SPAWNED", "intervention_active": self.intervention_active}
        return {
            "status": "CONTROL_ACTIVE",
            "slot_index": self.slot_index,
            "body_id": self.body_id,
            "observer_label": self.observer_label,
            "last_requested": self.last_requested,
            "last_realized": self.last_realized,
            "target_agent_id": self.target_agent_id,
            "queue_len": len(self.command_queue),
            "recording": self.recording,
            "intervention_active": True,
            "n_captures": len(self.captures),
            "mobility_mode": self.mobility_mode,
            "research_supply": self.last_research_supply,
            "honesty": {
                "observer_only_label": True,
                "no_cognition_leak": True,
                "requested_vs_realized": True,
                "research_mobility_not_eating": True,
            },
        }

    def set_mobility_mode(self, mode: str) -> dict[str, Any]:
        m = str(mode or MOBILITY_ORDINARY).upper()
        if m not in VALID_MOBILITY:
            return {"accepted": False, "error": f"invalid mobility mode: {mode}"}
        prev = self.mobility_mode
        self.mobility_mode = m
        self.log(
            "EXPERIMENTER_MOBILITY_MODE",
            -1,
            mode=m,
            previous=prev,
            note="External research support when RESEARCH_MOBILITY — not organism eating.",
        )
        return {"accepted": True, "mobility_mode": m, "previous": prev}

    def enqueue(
        self,
        kind: str,
        *,
        action: str | None = None,
        amplitude: float | None = None,
        specimen_id: str | None = None,
        at_tick: int | None = None,
        relative: bool = True,
    ) -> dict[str, Any]:
        if not self.active and kind != "SPAWN":
            return {"accepted": False, "error": "controlled body not spawned"}
        if len(self.command_queue) >= COMMAND_QUEUE_MAX:
            return {"accepted": False, "error": "command queue overflow"}
        if kind == "ACTION":
            act = str(action or "WAIT")
            if act not in VALID_MOVE:
                return {"accepted": False, "error": f"invalid action {act}"}
        cmd = ExperimenterCommand(
            sim_tick=int(at_tick if at_tick is not None else 0),
            kind=kind,
            action=action,
            amplitude=amplitude,
            specimen_id=specimen_id,
            relative=relative,
        )
        self.command_queue.append(cmd)
        return {"accepted": True, "queued": kind, "queue_len": len(self.command_queue)}

    def log(self, event_type: str, tick: int, **payload: Any) -> None:
        row = {"event_type": event_type, "tick": int(tick), **payload}
        self.event_log.append(row)
        if self.recording:
            self.scripted_commands.append(row)

    def begin_recording(self, rt: TwoAgentRuntime) -> None:
        self.recording = True
        self.record_start_tick = int(rt.tick)
        self.s0_snapshot = deepcopy(rt.snapshot())
        self.scripted_commands = []
        self.log("EXPERIMENTER_INTERACTION_CAPTURE_STARTED", int(rt.tick))

    def capture(
        self,
        rt: TwoAgentRuntime,
        *,
        run_id: str = "live",
        post_ticks: int = 0,
    ) -> ExperimenterInteractionSpecimen:
        end = int(rt.tick)
        start = int(self.record_start_tick or end)
        # Collect ACTION/FIELD commands as tick-relative script
        cmds = []
        for row in self.scripted_commands:
            et = row.get("event_type")
            if et in (
                "EXPERIMENTER_ACTION_REQUESTED",
                "EXPERIMENTER_FIELD_EMITTED",
                "EXPERIMENTER_NATURAL_SIGNAL_REPLAYED",
            ):
                cmds.append({
                    "tick_offset": int(row["tick"]) - start,
                    "event_type": et,
                    "action": row.get("action"),
                    "channel": row.get("channel"),
                    "amplitude": row.get("amplitude"),
                    "specimen_id": row.get("specimen_id"),
                })
        cap = ExperimenterInteractionSpecimen(
            capture_id=stable_id("icap", run_id, start, end, time.time_ns()),
            run_id=run_id,
            start_tick=start,
            end_tick=end,
            s0_snapshot=self.s0_snapshot,
            commands=cmds,
            events=list(self.event_log),
            spawn=dict(self.spawn_meta),
            target_agent_id=self.target_agent_id,
        )
        self.captures.append(cap)
        if len(self.captures) > 32:
            self.captures = self.captures[-32:]
        self.recording = False
        self.log("EXPERIMENTER_INTERACTION_CAPTURED", end, capture_id=cap.capture_id)
        return cap


def promote_physical_to_two_agent_host(rt: PhysicalSystemRuntime) -> TwoAgentRuntime:
    """Wrap a single-agent PhysicalSystemRuntime so experimenter spawn can append a slot.

    Preserves the existing autonomous agent object (body/internal/cognition/world)
    as slot 0. Does not alter that agent's scientific state. Observer-only host
    upgrade — required because spawn_experimenter_body appends onto TwoAgentRuntime.slots.
    """
    if isinstance(rt, TwoAgentRuntime):
        return rt
    from mechanistic_mind.physical_system.two_agent import _empty_agent_stats

    x = int(rt.body.x) % max(1, int(rt.world.T.shape[1]))
    y = int(rt.body.y) % max(1, int(rt.world.T.shape[0]))
    signal_on = bool(getattr(getattr(rt.config, "physical_signal", None), "enabled", False))
    host = TwoAgentRuntime(
        seed=int(rt.seed),
        config=rt.config.copy(),
        starts=((x, y), (x, y)),
        signal_enabled=signal_on,
        independent_agent_seeds=False,  # keep existing slot seed as-is
    )
    # Replace freshly constructed slots with the live autonomous agent.
    host.slots = [rt]
    host.world = rt.world
    host.config = rt.config
    host.seed = int(rt.seed)
    host._agent_stats = [_empty_agent_stats()]
    host._prev_xy = [(float(rt.body.x), float(rt.body.y))]
    host.process_order = (0,)
    # Keep a 2-tuple starts shape for snapshot() compatibility; only slot 0 is live.
    host.starts = ((x, y), (x + 4, y))
    host.experimenter_slot = None
    host.selected_index = 0
    if signal_on:
        from mechanistic_mind.physical_system.physical_signal import ensure_fields

        ensure_fields(host.world)
    return host


def spawn_experimenter_body(
    rt: TwoAgentRuntime,
    *,
    x: float,
    y: float,
    theta: float = 0.0,
    controller: ExperimenterController,
) -> dict[str, Any]:
    """Attach ordinary PSR slot with cognition OFF as experimenter body."""
    if not isinstance(rt, TwoAgentRuntime):
        return {
            "accepted": False,
            "error": "SPAWN_REJECTED:RUNTIME_UNAVAILABLE",
            "detail": "TwoAgentRuntime host required",
        }
    if getattr(rt, "experimenter_slot", None) is not None:
        return {"accepted": False, "error": "SPAWN_REJECTED:ALREADY_SPAWNED", "detail": "experimenter already spawned"}
    if not rt.slots:
        return {"accepted": False, "error": "SPAWN_REJECTED:NO_VALID_TARGET", "detail": "no autonomous slots"}
    # Build config like existing slots, cognition disabled
    base = rt.slots[0].config.copy()
    base.cognition.cognition_enabled = False
    base.body.start_x = int(x) % int(rt.world.T.shape[1])
    base.body.start_y = int(y) % int(rt.world.T.shape[0])
    # Match signal mode of the shared world
    if rt.signal_enabled or rt.slots[0].config.physical_signal.enabled:
        from mechanistic_mind.physical_system.physical_signal import PhysicalSignalConfig, ensure_fields
        base.physical_signal = PhysicalSignalConfig(mode="EXPERIMENTAL")
        ensure_fields(rt.world)
        rt.signal_enabled = True
    slot_i = len(rt.slots)
    seed = agent_seed(rt.seed, slot_i) if rt.independent_agent_seeds else int(rt.seed)
    exp = PhysicalSystemRuntime(seed=seed, config=base)
    exp.world = rt.world
    exp.tick = int(rt.slots[0].tick)
    exp.body.tick = int(rt.slots[0].body.tick)
    exp.internal.tick = int(rt.slots[0].internal.tick)
    exp.body.x = float(x)
    exp.body.y = float(y)
    exp.body.theta = float(theta)
    # Mark observer-only (never put in observation)
    exp._experimenter_controlled = True  # type: ignore[attr-defined]
    rt.slots.append(exp)
    rt.experimenter_slot = slot_i
    if len(rt._agent_stats) < len(rt.slots):
        from mechanistic_mind.physical_system.two_agent import _empty_agent_stats
        while len(rt._agent_stats) < len(rt.slots):
            rt._agent_stats.append(_empty_agent_stats())
            rt._prev_xy.append(None)
    # Extend process_order
    rt.process_order = tuple(range(len(rt.slots)))
    controller.active = True
    controller.slot_index = slot_i
    controller.intervention_active = True
    from mechanistic_mind.ui.psy_observer_web.undercover_identity import (
        UNDERCOVER_AGENT_ID,
        undercover_body_id,
    )
    controller.body_id = undercover_body_id(slot_i)
    controller.agent_id = UNDERCOVER_AGENT_ID
    controller.spawn_meta = {
        "x": float(x), "y": float(y), "theta": float(theta),
        "slot": slot_i, "tick": int(rt.tick),
        "agent_id": UNDERCOVER_AGENT_ID,
        "body_id": controller.body_id,
        "note": "One controller → one physical body; no EXPERIMENTER shadow body.",
    }
    controller.log(
        "EXPERIMENTER_BODY_SPAWNED",
        int(rt.tick),
        x=float(x), y=float(y), theta=float(theta), slot=slot_i,
        note="Intervention active — run is no longer untouched baseline.",
    )
    return {
        "accepted": True,
        "slot": slot_i,
        "body_id": controller.body_id,
        "intervention_active": True,
        "status": controller.status(),
    }


def rebind_experimenter_controller(
    rt: TwoAgentRuntime,
    controller: ExperimenterController,
) -> dict[str, Any]:
    """Attach a non-physical controller to an already-present Undercover slot.

    Used after snapshot restore so we never spawn a second physical body.
    """
    from mechanistic_mind.ui.psy_observer_web.undercover_identity import (
        UNDERCOVER_AGENT_ID,
        undercover_body_id,
    )

    slot = getattr(rt, "experimenter_slot", None)
    if slot is None:
        controller.active = False
        controller.slot_index = None
        return {"accepted": False, "error": "no experimenter_slot on runtime"}
    slot_i = int(slot)
    if not (0 <= slot_i < len(rt.slots)):
        return {"accepted": False, "error": "experimenter_slot out of range"}
    exp = rt.slots[slot_i]
    exp._experimenter_controlled = True  # type: ignore[attr-defined]
    # Cognition stays whatever the snapshot stored (normally OFF for Undercover).
    controller.active = True
    controller.slot_index = slot_i
    controller.intervention_active = True
    controller.body_id = undercover_body_id(slot_i)
    controller.agent_id = UNDERCOVER_AGENT_ID
    controller.spawn_meta = {
        "x": float(exp.body.x),
        "y": float(exp.body.y),
        "theta": float(getattr(exp.body, "theta", 0.0) or 0.0),
        "slot": slot_i,
        "tick": int(rt.tick),
        "agent_id": UNDERCOVER_AGENT_ID,
        "body_id": controller.body_id,
        "rebinding": True,
        "note": "Controller rebound to existing physical body — no new spawn.",
    }
    controller.log(
        "EXPERIMENTER_CONTROLLER_REBOUND",
        int(rt.tick),
        slot=slot_i,
        body_id=controller.body_id,
    )
    return {
        "accepted": True,
        "slot": slot_i,
        "body_id": controller.body_id,
        "status": controller.status(),
    }


def remove_experimenter_body(
    rt: TwoAgentRuntime,
    controller: ExperimenterController,
) -> dict[str, Any]:
    slot = getattr(rt, "experimenter_slot", None)
    if slot is None:
        return {"accepted": False, "error": "not spawned"}
    if int(slot) != len(rt.slots) - 1:
        return {"accepted": False, "error": "experimenter must be last slot"}
    rt.slots.pop()
    rt.experimenter_slot = None  # type: ignore[attr-defined]
    if len(rt._agent_stats) > len(rt.slots):
        rt._agent_stats = rt._agent_stats[: len(rt.slots)]
        rt._prev_xy = rt._prev_xy[: len(rt.slots)]
    rt.process_order = tuple(range(len(rt.slots)))
    controller.log("EXPERIMENTER_BODY_REMOVED", int(rt.tick), slot=slot)
    controller.active = False
    controller.slot_index = None
    # Keep intervention_active True for provenance
    return {"accepted": True, "intervention_active": True, "status": controller.status()}


def apply_experimenter_research_supply(
    rt: TwoAgentRuntime,
    controller: ExperimenterController,
) -> dict[str, Any] | None:
    """Top-up experimenter reservoir BEFORE ordinary work allocation.

    Preserves requested-action → allocation → impulse → mechanics path.
    Does NOT teleport, noclip, or bypass forces. Autonomous slots untouched.
    """
    if not controller.active or controller.slot_index is None:
        return None
    slot_i = int(controller.slot_index)
    if slot_i >= len(rt.slots):
        return None
    slot = rt.slots[slot_i]
    # Clear prior stamp every tick so ORDINARY leaves no stale supply
    slot.last_experimenter_research_supply = None  # type: ignore[attr-defined]
    if controller.mobility_mode != MOBILITY_RESEARCH:
        controller.last_research_supply = {"status": "NONE", "mode": MOBILITY_ORDINARY}
        return None
    w_max = float(getattr(slot.config.deformation_work, "reservoir_max", 4.0) or 4.0)
    w0 = float(getattr(slot.body, "mechanical_work_reservoir", 0.0) or 0.0)
    credited = max(0.0, w_max - w0)
    if credited > 0.0:
        slot.body.mechanical_work_reservoir = float(w_max)
    receipt = {
        "source": RESEARCH_SUPPLY_SOURCE,
        "mode": MOBILITY_RESEARCH,
        "before": w0,
        "after": float(slot.body.mechanical_work_reservoir),
        "credited": float(credited),
        "reservoir_max": w_max,
        "not_environmental_resource": True,
        "not_cognition_input": True,
        "not_organism_eating": True,
        "ordinary_allocation_path": True,
        "tick": int(rt.tick),
    }
    slot.last_experimenter_research_supply = receipt  # type: ignore[attr-defined]
    controller.last_research_supply = receipt
    return receipt


def apply_experimenter_pre_step(
    rt: TwoAgentRuntime,
    controller: ExperimenterController,
) -> list[dict[str, Any]]:
    """Drain relative commands into forced action / FIELD inject for this tick."""
    applied = []
    if not controller.active or controller.slot_index is None:
        return applied
    slot = int(controller.slot_index)
    if slot >= len(rt.slots):
        return applied
    # INT-02: external research supply before ordinary begin_tick allocation
    supply = apply_experimenter_research_supply(rt, controller)
    if supply and float(supply.get("credited") or 0.0) > 0.0:
        controller.log(
            "EXPERIMENTER_RESEARCH_SUPPLY",
            int(rt.tick),
            credited=supply["credited"],
            source=RESEARCH_SUPPLY_SOURCE,
            mode=MOBILITY_RESEARCH,
        )
        applied.append({"kind": "RESEARCH_SUPPLY", **supply})
    # Process queue: relative commands apply immediately (one ACTION per tick max)
    action_done = False
    remaining = deque()
    while controller.command_queue:
        cmd = controller.command_queue.popleft()
        if cmd.kind == "ACTION" and not action_done:
            act = str(cmd.action or "WAIT")
            rt.slots[slot]._forced_action_once = act
            controller.last_requested = act
            controller.log(
                "EXPERIMENTER_ACTION_REQUESTED",
                int(rt.tick),
                action=act,
            )
            # Record for scripted replay relative to capture start
            if controller.recording and controller.record_start_tick is not None:
                pass  # logged above
            applied.append({"kind": "ACTION", "action": act})
            action_done = True
        elif cmd.kind in ("FIELD_A", "FIELD_B"):
            ch = "A" if cmd.kind == "FIELD_A" else "B"
            amp = float(cmd.amplitude if cmd.amplitude is not None else 0.7)
            rt.inject_source(
                channel=ch,
                amplitude=amp,
                slot=slot,
                trigger="experimenter_control",
                observer_source_id=f"experimenter:{controller.body_id}",
            )
            controller.log(
                "EXPERIMENTER_FIELD_EMITTED",
                int(rt.tick),
                channel=ch,
                amplitude=amp,
                trigger="experimenter_control",
            )
            applied.append({"kind": cmd.kind, "amplitude": amp})
        elif cmd.kind == "OSC_EMIT":
            # Undercover uses identical oscillatory physics as Tiktaalik bodies.
            from mechanistic_mind.physical_system.oscillatory_signaling import (
                set_undercover_osc_params,
            )
            body = rt.slots[slot].body
            osc_cfg = getattr(rt.slots[slot].config, "oscillatory_signaling", None)
            if osc_cfg is None or not osc_cfg.enabled:
                applied.append({"kind": "OSC_EMIT", "applied": False, "reason": "osc_off"})
            else:
                freq = cmd.frequency if getattr(cmd, "frequency", None) is not None else None
                amp = cmd.amplitude if cmd.amplitude is not None else None
                dur = cmd.duration if getattr(cmd, "duration", None) is not None else None
                info = set_undercover_osc_params(
                    body,
                    frequency=freq,
                    amplitude=amp,
                    duration=dur,
                    cfg=osc_cfg,
                    emit_now=True,
                )
                controller.log(
                    "EXPERIMENTER_OSC_EMITTED",
                    int(rt.tick),
                    frequency=info.get("frequency") or body.osc_frequency,
                    amplitude=info.get("amplitude") or body.osc_amplitude,
                    remaining=int(body.osc_emit_remaining),
                    trigger="experimenter_control",
                )
                applied.append({"kind": "OSC_EMIT", **info})
        elif cmd.kind == "SPECIMEN_REPLAY":
            remaining.append(cmd)  # handled by session with library
        else:
            remaining.append(cmd)
    controller.command_queue = remaining
    return applied


def record_experimenter_post_step(
    rt: TwoAgentRuntime,
    controller: ExperimenterController,
) -> None:
    if not controller.active or controller.slot_index is None:
        return
    slot = rt.slots[int(controller.slot_index)]
    body = slot.body
    controller.last_realized = {
        "x": float(body.x),
        "y": float(body.y),
        "vx": float(getattr(body, "vx", 0.0) or 0.0),
        "vy": float(getattr(body, "vy", 0.0) or 0.0),
        "theta": float(getattr(body, "theta", 0.0) or 0.0),
        "action": slot.last_selected_action,
        "speed": float(
            (getattr(body, "vx", 0.0) or 0.0) ** 2 + (getattr(body, "vy", 0.0) or 0.0) ** 2
        ) ** 0.5,
    }
    realized = {k: v for k, v in controller.last_realized.items() if k != "action"}
    controller.log(
        "EXPERIMENTER_ACTION_REALIZED",
        int(rt.tick),
        action=slot.last_selected_action,
        **realized,
    )


def audit_observation_no_experimenter_leak(obs: dict[str, Any] | None) -> list[str]:
    if not isinstance(obs, dict):
        return []
    leaks = []
    blob = str(obs).lower()
    for needle in (
        "experimenter", "human_controlled", "is_experimenter", "player",
        "creator", "special_agent", "interaction_target", "you",
    ):
        if needle in blob:
            leaks.append(needle)
    return leaks


def run_source_context_factorial(
    capture: ExperimenterInteractionSpecimen,
    *,
    seed: int = 17,
    horizon: int = 40,
) -> dict[str, Any]:
    """Matched CONTROL / BODY_ONLY / FIELD_ONLY / BODY_PLUS_FIELD / SHAM.

    BODY trajectory replay is approximate: FIELD commands from capture are
    replayed via inject_source; body motion uses recorded ACTION sequence on
    experimenter slot when present.
    """
    if capture.s0_snapshot is None:
        return {"accepted": False, "error": "S0 unavailable — cannot run matched test"}

    experiment_id = stable_id("srcctx", capture.capture_id, seed)
    field_cmds = [
        c for c in capture.commands
        if c.get("event_type") == "EXPERIMENTER_FIELD_EMITTED"
        or c.get("channel") in ("A", "B")
    ]
    action_cmds = [
        c for c in capture.commands
        if c.get("event_type") == "EXPERIMENTER_ACTION_REQUESTED" or c.get("action")
    ]

    def _branch(mode: str) -> dict[str, Any]:
        snap = deepcopy(capture.s0_snapshot)
        # Ensure CONTROL-compatible base: strip experimenter from S0 if present
        if mode == "CONTROL" or mode == "FIELD_ONLY":
            if snap.get("experimenter_slot") is not None:
                agents = list(snap.get("agents") or [])
                es = int(snap["experimenter_slot"])
                if 0 <= es < len(agents):
                    agents = [a for i, a in enumerate(agents) if i != es]
                snap["agents"] = agents
                snap["experimenter_slot"] = None
                snap["experimenter_intervention"] = False
                snap["process_order"] = list(range(len(agents)))
        rt = TwoAgentRuntime.restore(snap)
        ctrl = ExperimenterController()
        # Spawn if mode needs body
        need_body = mode in ("BODY_ONLY", "BODY_PLUS_FIELD", "SHAM")
        need_field = mode in ("FIELD_ONLY", "BODY_PLUS_FIELD")
        sham = mode == "SHAM"
        if need_body:
            if getattr(rt, "experimenter_slot", None) is not None:
                # S0 already contains experimenter body from capture-time snapshot
                rebind_experimenter_controller(rt, ctrl)
                ctrl.spawn_meta = dict(capture.spawn or {}) or ctrl.spawn_meta
            else:
                sp = capture.spawn or {}
                spawn_experimenter_body(
                    rt,
                    x=float(sp.get("x", 10)),
                    y=float(sp.get("y", 10)),
                    theta=float(sp.get("theta", 0)),
                    controller=ctrl,
                )
        traces = []
        pre = scientific_fingerprint(rt) if len(rt.slots) >= 2 else None
        # Build schedule by tick_offset
        by_off: dict[int, list] = {}
        if need_field or sham:
            for c in field_cmds:
                off = int(c.get("tick_offset") or 0)
                by_off.setdefault(off, []).append(c)
        act_by: dict[int, str] = {}
        if need_body:
            for c in action_cmds:
                off = int(c.get("tick_offset") or 0)
                act_by[off] = str(c.get("action") or "WAIT")

        for i in range(int(horizon)):
            if need_body and i in act_by and ctrl.slot_index is not None:
                rt.slots[ctrl.slot_index]._forced_action_once = act_by[i]
            if i in by_off:
                for c in by_off[i]:
                    ch = str(c.get("channel") or "A")
                    amp = float(c.get("amplitude") or 0.7)
                    if sham:
                        amp = 0.0
                    if need_body and ctrl.slot_index is not None:
                        rt.inject_source(
                            channel=ch, amplitude=amp, slot=int(ctrl.slot_index),
                            trigger="experimenter_control",
                            observer_source_id=f"exp:{experiment_id}:{mode}",
                        )
                    else:
                        # FIELD_ONLY: deposit at spawn location
                        sp = capture.spawn or {}
                        iy = int(float(sp.get("y", 10)))
                        ix = int(float(sp.get("x", 10)))
                        rt.inject_source(
                            channel=ch, amplitude=amp, iy=iy, ix=ix,
                            trigger="experimenter_control",
                            observer_source_id=f"exp:{experiment_id}:{mode}",
                        )
            rt.step()
            # Track agent_1 selection/action
            a1 = rt.slots[1] if len(rt.slots) > 1 else rt.slots[0]
            sel = (a1.cognition or {}).get("last_selection") or {}
            traces.append({
                "branch_tick": i + 1,
                "action": a1.last_selected_action,
                "selection_source": sel.get("source"),
                "x": float(a1.body.x),
                "y": float(a1.body.y),
                "obs_A": (a1.last_agent_observation or {}).get("local.FIELD_A"),
            })
        return {
            "mode": mode,
            "traces": traces,
            "pre_fingerprint": pre,
            "final_action": traces[-1]["action"] if traces else None,
            "final_source": traces[-1]["selection_source"] if traces else None,
        }

    arms = {}
    for mode in ("CONTROL", "BODY_ONLY", "FIELD_ONLY", "BODY_PLUS_FIELD", "SHAM"):
        # CONTROL: restore S0, no spawn, no field
        if mode == "CONTROL":
            snap = deepcopy(capture.s0_snapshot)
            if snap.get("experimenter_slot") is not None:
                agents = list(snap.get("agents") or [])
                es = int(snap["experimenter_slot"])
                if 0 <= es < len(agents):
                    agents = [a for i, a in enumerate(agents) if i != es]
                snap["agents"] = agents
                snap["experimenter_slot"] = None
                snap["experimenter_intervention"] = False
                snap["process_order"] = list(range(len(agents)))
            rt = TwoAgentRuntime.restore(snap)
            # Ensure no experimenter
            if getattr(rt, "experimenter_slot", None) is not None:
                pass
            traces = []
            for i in range(int(horizon)):
                rt.step()
                a1 = rt.slots[1]
                sel = (a1.cognition or {}).get("last_selection") or {}
                traces.append({
                    "branch_tick": i + 1,
                    "action": a1.last_selected_action,
                    "selection_source": sel.get("source"),
                    "x": float(a1.body.x),
                    "y": float(a1.body.y),
                    "obs_A": (a1.last_agent_observation or {}).get("local.FIELD_A"),
                })
            arms[mode] = {
                "mode": mode,
                "traces": traces,
                "final_action": traces[-1]["action"] if traces else None,
                "final_source": traces[-1]["selection_source"] if traces else None,
            }
        else:
            arms[mode] = _branch(mode)

    def first_src_div(a, b):
        n = min(len(a["traces"]), len(b["traces"]))
        for i in range(n):
            if a["traces"][i]["selection_source"] != b["traces"][i]["selection_source"]:
                return i + 1
        return None

    def first_act_div(a, b):
        n = min(len(a["traces"]), len(b["traces"]))
        for i in range(n):
            if a["traces"][i]["action"] != b["traces"][i]["action"]:
                return i + 1
        return None

    ctrl = arms["CONTROL"]
    comparisons = {
        m: {
            "source_div": first_src_div(ctrl, arms[m]),
            "action_div": first_act_div(ctrl, arms[m]),
        }
        for m in arms if m != "CONTROL"
    }
    # SOURCE_CONTEXT_DEPENDENCE: BODY_PLUS_FIELD differs from FIELD_ONLY on cognition/action
    bpf = arms["BODY_PLUS_FIELD"]
    fo = arms["FIELD_ONLY"]
    source_ctx = (
        first_src_div(fo, bpf) is not None or first_act_div(fo, bpf) is not None
    )
    return {
        "accepted": True,
        "experiment_id": experiment_id,
        "capture_id": capture.capture_id,
        "arms": {m: {
            "final_action": arms[m].get("final_action"),
            "final_source": arms[m].get("final_source"),
            "n_traces": len(arms[m].get("traces") or []),
        } for m in arms},
        "comparisons_vs_control": comparisons,
        "SOURCE_CONTEXT_DEPENDENCE": (
            "SUPPORTED" if source_ctx else "NOT_ESTABLISHED"
        ),
        "honesty": {
            "not_recognition": True,
            "not_social_awareness": True,
            "matched_branching": True,
        },
    }


def build_interaction_fingerprint(
    factorial: dict[str, Any],
) -> dict[str, Any]:
    comps = factorial.get("comparisons_vs_control") or {}
    bpf = comps.get("BODY_PLUS_FIELD") or {}
    return {
        "FIELD_exposure": "SEE_ARMS",
        "selection_source_div_tick": bpf.get("source_div"),
        "action_div_tick": bpf.get("action_div"),
        "SOURCE_CONTEXT_DEPENDENCE": factorial.get("SOURCE_CONTEXT_DEPENDENCE"),
        "honesty": {"not_communication": True, "exploratory_fingerprint": True},
    }
