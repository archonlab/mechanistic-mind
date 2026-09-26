"""Composite motor control — one cognitive cycle, multiple effector domains.

Schema: COMPOSITE_MOTOR_V1

PERCEPTION (passive, continuous) is NOT part of the motor vector.
One decision cycle produces CompositeMotorOutput with factorized components:
  locomotion | neck | oscillator | push

No Cartesian compound action tokens.
No multiple cognition cycles per tick.
No automatic skills / gaze / turn-taking / communication.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from mechanistic_mind.physical_system.actions import (
    OSC_ACTIONS,
    PUSH_ACTIONS,
    action_direction,
    apply_physical_action,
    is_push_action,
    neck_motor_command,
)
from mechanistic_mind.physical_system.oscillatory_signaling import apply_osc_motor_action

MOTOR_SCHEMA = "COMPOSITE_MOTOR_V1"
LEGACY_SCHEMA = "LEGACY_SINGLE_SLOT"

OSC_FREQ_ACTIONS = ("OSC_FREQ_UP", "OSC_FREQ_DOWN")
OSC_AMP_ACTIONS = ("OSC_AMP_UP", "OSC_AMP_DOWN")
OSC_EMIT_ACTIONS = ("OSC_EMIT",)
assert set(OSC_FREQ_ACTIONS) | set(OSC_AMP_ACTIONS) | set(OSC_EMIT_ACTIONS) == set(OSC_ACTIONS)

LOCO_NONE = "NONE"
NECK_NONE = "NONE"
OSC_DELTA_NONE = 0


@dataclass
class OscillatorMotorComponent:
    frequency_delta: int = 0  # -1 | 0 | +1
    amplitude_delta: int = 0  # -1 | 0 | +1
    emit_trigger: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "OscillatorMotorComponent":
        if not data:
            return cls()
        return cls(
            frequency_delta=int(data.get("frequency_delta") or 0),
            amplitude_delta=int(data.get("amplitude_delta") or 0),
            emit_trigger=bool(data.get("emit_trigger")),
        )


@dataclass
class CompositeMotorOutput:
    """ONE structured decision output. Not multiple brains."""

    locomotion: str = "WAIT"  # WAIT | MOVE:N|S|E|W
    neck: str = NECK_NONE  # NONE | NECK_LEFT | NECK_RIGHT | NECK_HOLD
    oscillator: OscillatorMotorComponent = field(default_factory=OscillatorMotorComponent)
    push: bool = False
    schema: str = MOTOR_SCHEMA
    # Legacy projection for metrics / Analyzer / old UI (primary channel label).
    legacy_token: str = "WAIT"
    selection_source: str = "COMPOSITE"
    # Domain-level selection sources (same cognitive cycle, factorized).
    domain_sources: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "locomotion": self.locomotion,
            "neck": self.neck,
            "oscillator": self.oscillator.to_dict(),
            "push": bool(self.push),
            "legacy_token": self.legacy_token,
            "selection_source": self.selection_source,
            "domain_sources": dict(self.domain_sources),
            "display": self.display_label(),
        }

    def display_label(self) -> str:
        """Human-readable formatting only — not scientific identity."""
        parts = [self.locomotion if self.locomotion else "WAIT"]
        if self.neck and self.neck != NECK_NONE:
            parts.append(self.neck)
        osc = self.oscillator
        if osc.frequency_delta > 0:
            parts.append("OSC_FREQ_UP")
        elif osc.frequency_delta < 0:
            parts.append("OSC_FREQ_DOWN")
        if osc.amplitude_delta > 0:
            parts.append("OSC_AMP_UP")
        elif osc.amplitude_delta < 0:
            parts.append("OSC_AMP_DOWN")
        if osc.emit_trigger:
            parts.append("OSC_EMIT")
        if self.push:
            parts.append("PUSH")
        return " | ".join(parts)

    @classmethod
    def from_legacy(cls, action: str, *, source: str = "LEGACY") -> "CompositeMotorOutput":
        """Map a single-slot action string onto one active motor domain."""
        kind = str(action or "WAIT")
        out = cls(selection_source=source, schema=LEGACY_SCHEMA, legacy_token=kind)
        out.domain_sources = {"legacy": source}
        if kind == "WAIT" or kind.startswith("WAIT"):
            out.locomotion = "WAIT"
        elif action_direction(kind) is not None:
            out.locomotion = kind
        elif neck_motor_command(kind) is not None:
            out.locomotion = "WAIT"
            out.neck = kind
        elif is_push_action(kind):
            out.locomotion = "WAIT"
            out.push = True
        elif kind in OSC_FREQ_ACTIONS:
            out.locomotion = "WAIT"
            out.oscillator.frequency_delta = 1 if kind == "OSC_FREQ_UP" else -1
        elif kind in OSC_AMP_ACTIONS:
            out.locomotion = "WAIT"
            out.oscillator.amplitude_delta = 1 if kind == "OSC_AMP_UP" else -1
        elif kind in OSC_EMIT_ACTIONS:
            out.locomotion = "WAIT"
            out.oscillator.emit_trigger = True
        else:
            out.locomotion = "WAIT"
        return out

    def compute_legacy_token(self) -> str:
        """Primary label for legacy counters: prefer locomotion, else first active side channel."""
        if self.locomotion and self.locomotion not in ("WAIT", LOCO_NONE):
            return self.locomotion
        if self.neck and self.neck != NECK_NONE:
            return self.neck
        if self.oscillator.emit_trigger:
            return "OSC_EMIT"
        if self.oscillator.frequency_delta > 0:
            return "OSC_FREQ_UP"
        if self.oscillator.frequency_delta < 0:
            return "OSC_FREQ_DOWN"
        if self.oscillator.amplitude_delta > 0:
            return "OSC_AMP_UP"
        if self.oscillator.amplitude_delta < 0:
            return "OSC_AMP_DOWN"
        if self.push:
            return "PUSH"
        return "WAIT"


def locomotion_options(available: list[str]) -> list[str]:
    out = [a for a in available if a == "WAIT" or str(a).startswith("MOVE:")]
    return out or ["WAIT"]


def neck_options(available: list[str]) -> list[str]:
    necks = [a for a in available if str(a).startswith("NECK_")]
    return [NECK_NONE] + necks


def _pick_supported(
    options: list[str],
    predictions: list[dict[str, Any]],
    *,
    rng: float,
    prefer_none: bool = True,
    explore_rate: float = 0.08,
) -> tuple[str, str]:
    """Pick an option with MATCH support if any; else NONE or rare endogenous.

    Same cognitive cycle — not a second brain. Exploration is domain-local
    residual variation only (no automatic skill / gaze / turn-taking).
    """
    if not options:
        return NECK_NONE if prefer_none else "WAIT", "EMPTY"
    supported = []
    for p in predictions or []:
        act = str(p.get("action") or "")
        status = str(p.get("status") or p.get("result", {}).get("status") or "").upper()
        if act in options and status in {"MATCH", "OK", "HIT", ""}:
            if status or p.get("predicted") is not None or p.get("result") is not None:
                supported.append(act)
        elif act in options and (p.get("predicted") is not None or isinstance(p.get("result"), dict)):
            supported.append(act)
    non_none = [a for a in supported if a != NECK_NONE and a != "WAIT"]
    if non_none:
        chosen = sorted(set(non_none))[0]
        return chosen, "RETAINED_PREDICTION"
    # Rare endogenous exploration so side channels remain learnable.
    if prefer_none and float(rng) < float(explore_rate):
        candidates = [a for a in options if a not in (NECK_NONE, "WAIT")] or list(options)
        idx = int(max(0, min(len(candidates) - 1, int(float(rng) * 997) % len(candidates))))
        return candidates[idx], "ENDOGENOUS_VARIATION"
    if prefer_none and NECK_NONE in options:
        return NECK_NONE, "DEFAULT_NONE"
    if "WAIT" in options:
        return "WAIT", "DEFAULT_WAIT"
    idx = int(max(0, min(len(options) - 1, int(float(rng) * len(options)))))
    return options[idx], "ENDOGENOUS_VARIATION"


def build_composite_from_factorized(
    *,
    locomotion: str,
    loco_source: str,
    neck: str,
    neck_source: str,
    osc: OscillatorMotorComponent,
    osc_source: str,
    push: bool,
    push_source: str,
) -> CompositeMotorOutput:
    out = CompositeMotorOutput(
        locomotion=locomotion or "WAIT",
        neck=neck if neck else NECK_NONE,
        oscillator=osc,
        push=bool(push),
        schema=MOTOR_SCHEMA,
        selection_source="COMPOSITE_FACTORIZED",
        domain_sources={
            "locomotion": loco_source,
            "neck": neck_source,
            "oscillator": osc_source,
            "push": push_source,
        },
    )
    out.legacy_token = out.compute_legacy_token()
    return out


def select_factorized_side_channels(
    *,
    available: list[str],
    predictions: list[dict[str, Any]],
    rng_value: float,
    articulated_head: bool,
    oscillatory: bool,
    physical_push: bool,
) -> tuple[str, str, OscillatorMotorComponent, str, bool, str]:
    """Factorized side-channel picks in the SAME decision cycle (no extra cognition)."""
    neck = NECK_NONE
    neck_src = "UNAVAILABLE"
    if articulated_head:
        neck, neck_src = _pick_supported(
            neck_options(available), predictions, rng=rng_value, prefer_none=True,
        )

    osc = OscillatorMotorComponent()
    osc_src = "UNAVAILABLE"
    if oscillatory:
        # Frequency
        freq_opts = [NECK_NONE] + [a for a in available if a in OSC_FREQ_ACTIONS]
        freq_pick, freq_src = _pick_supported(
            freq_opts, predictions, rng=(rng_value + 0.17) % 1.0, prefer_none=True,
        )
        if freq_pick == "OSC_FREQ_UP":
            osc.frequency_delta = 1
        elif freq_pick == "OSC_FREQ_DOWN":
            osc.frequency_delta = -1
        # Amplitude
        amp_opts = [NECK_NONE] + [a for a in available if a in OSC_AMP_ACTIONS]
        amp_pick, amp_src = _pick_supported(
            amp_opts, predictions, rng=(rng_value + 0.31) % 1.0, prefer_none=True,
        )
        if amp_pick == "OSC_AMP_UP":
            osc.amplitude_delta = 1
        elif amp_pick == "OSC_AMP_DOWN":
            osc.amplitude_delta = -1
        # Emit trigger
        emit_opts = [NECK_NONE] + [a for a in available if a in OSC_EMIT_ACTIONS]
        emit_pick, emit_src = _pick_supported(
            emit_opts, predictions, rng=(rng_value + 0.47) % 1.0, prefer_none=True,
        )
        osc.emit_trigger = emit_pick == "OSC_EMIT"
        osc_src = f"freq:{freq_src}|amp:{amp_src}|emit:{emit_src}"

    push = False
    push_src = "UNAVAILABLE"
    if physical_push:
        push_opts = [NECK_NONE] + [a for a in available if a in PUSH_ACTIONS]
        push_pick, push_src = _pick_supported(
            push_opts, predictions, rng=(rng_value + 0.61) % 1.0, prefer_none=True,
        )
        push = push_pick == "PUSH"

    return neck, neck_src, osc, osc_src, push, push_src


def apply_composite_motor(
    body: Any,
    motor: CompositeMotorOutput,
    *,
    body_config: Any,
    impulse_scale: float = 0.35,
    oscillatory_cfg: Any = None,
) -> dict[str, Any]:
    """Apply all motor domains for one tick. Does not erase unrelated physical state."""
    applied: dict[str, Any] = {
        "schema": motor.schema,
        "locomotion": None,
        "neck": None,
        "oscillator": None,
        "push": None,
    }

    # Locomotion: WAIT or MOVE impulse. NONE treated as WAIT (no active locomotor command).
    loco = motor.locomotion if motor.locomotion and motor.locomotion != LOCO_NONE else "WAIT"
    loco_res = apply_physical_action(body, loco, body_config=body_config, impulse_scale=impulse_scale)
    applied["locomotion"] = {"action": loco, "applied": loco_res.applied, "detail": loco_res.detail}

    # Neck: only when explicit command; NONE → zero motor this tick (physics continues).
    if motor.neck and motor.neck != NECK_NONE:
        neck_res = apply_physical_action(
            body, motor.neck, body_config=body_config, impulse_scale=impulse_scale,
        )
        applied["neck"] = {"action": motor.neck, "applied": neck_res.applied, "detail": neck_res.detail}
    else:
        body.neck_motor = 0.0
        applied["neck"] = {"action": NECK_NONE, "applied": True, "detail": {"neck_motor": 0.0}}

    # Oscillator parameter deltas + emit trigger (persistent state on body).
    osc = motor.oscillator
    osc_detail: dict[str, Any] = {}
    if oscillatory_cfg is not None and getattr(oscillatory_cfg, "enabled", False):
        body._osc_cfg = oscillatory_cfg  # noqa: SLF001
        if osc.frequency_delta > 0:
            osc_detail["freq"] = apply_osc_motor_action(body, "OSC_FREQ_UP", oscillatory_cfg)
        elif osc.frequency_delta < 0:
            osc_detail["freq"] = apply_osc_motor_action(body, "OSC_FREQ_DOWN", oscillatory_cfg)
        if osc.amplitude_delta > 0:
            osc_detail["amp"] = apply_osc_motor_action(body, "OSC_AMP_UP", oscillatory_cfg)
        elif osc.amplitude_delta < 0:
            osc_detail["amp"] = apply_osc_motor_action(body, "OSC_AMP_DOWN", oscillatory_cfg)
        if osc.emit_trigger:
            osc_detail["emit"] = apply_osc_motor_action(body, "OSC_EMIT", oscillatory_cfg)
        applied["oscillator"] = {
            "frequency_delta": osc.frequency_delta,
            "amplitude_delta": osc.amplitude_delta,
            "emit_trigger": bool(osc.emit_trigger),
            "detail": osc_detail,
            "osc_freq_u": float(getattr(body, "osc_freq_u", 0.5)),
            "osc_amp_u": float(getattr(body, "osc_amp_u", 0.5)),
            "osc_emit_remaining": int(getattr(body, "osc_emit_remaining", 0) or 0),
        }
    else:
        applied["oscillator"] = {"enabled": False}

    # PUSH arming
    if motor.push:
        push_res = apply_physical_action(body, "PUSH", body_config=body_config, impulse_scale=impulse_scale)
        applied["push"] = {"action": "PUSH", "applied": push_res.applied}
    else:
        # Do not clear push mid-tick if already set by another path this tick; default clear.
        if not bool(getattr(body, "push_exertion", 0.0)):
            body.push_exertion = 0.0
        applied["push"] = {"action": False, "applied": True}

    return applied


def motor_control_events(motor: CompositeMotorOutput, *, tick: int) -> list[dict[str, Any]]:
    """Compact control-event records (not ongoing effector spam)."""
    evs: list[dict[str, Any]] = []
    if motor.locomotion and motor.locomotion not in ("WAIT", LOCO_NONE):
        evs.append({"type": "MOTOR_COMPONENT_SELECTED", "tick": tick, "domain": "locomotion", "value": motor.locomotion})
    if motor.neck and motor.neck != NECK_NONE:
        evs.append({"type": "MOTOR_COMPONENT_SELECTED", "tick": tick, "domain": "neck", "value": motor.neck})
        evs.append({"type": "NECK_TORQUE_APPLIED", "tick": tick, "value": motor.neck})
    osc = motor.oscillator
    if osc.frequency_delta:
        evs.append({
            "type": "OSC_PARAMETER_CHANGED", "tick": tick, "param": "frequency",
            "delta": osc.frequency_delta,
        })
    if osc.amplitude_delta:
        evs.append({
            "type": "OSC_PARAMETER_CHANGED", "tick": tick, "param": "amplitude",
            "delta": osc.amplitude_delta,
        })
    if osc.emit_trigger:
        evs.append({"type": "OSC_EMISSION_STARTED", "tick": tick, "trigger": True})
    if motor.push:
        evs.append({"type": "PUSH_EXERTED", "tick": tick})
    return evs
