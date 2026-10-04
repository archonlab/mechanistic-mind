"""Composite motor control — one cognitive cycle, multiple effector domains.

Schema: COMPOSITE_MOTOR_V1

PERCEPTION (passive, continuous) is NOT part of the motor vector.
One decision cycle produces CompositeMotorOutput with factorized components:
  locomotion | neck | oscillator | push | manipulator | manipulator_left | manipulator_right | manipulator_pair


No Cartesian compound action tokens.
No multiple cognition cycles per tick.
No automatic skills / gaze / turn-taking / communication.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from mechanistic_mind.physical_system.actions import (
    EFFECTOR_Z_ACTIONS,
    LEFT_EFFECTOR_Z_ACTIONS,
    OSC_ACTIONS,
    PUSH_ACTIONS,
    RIGHT_EFFECTOR_Z_ACTIONS,
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
MANIP_NONE = "NONE"
OSC_DELTA_NONE = 0
EFFECTOR_Z_NONE = 0
# Sign convention: +1 = UP = increases relative_z = tip rises; -1 = DOWN = tip descends.
MANIPULATOR_ACTIONS = ("GRASP", "RELEASE")
BILATERAL_MANIPULATOR_ACTIONS = ("LEFT_GRASP", "LEFT_RELEASE", "RIGHT_GRASP", "RIGHT_RELEASE")
PAIR_MANIPULATOR_ACTIONS = ("BRING_TOGETHER", "SEPARATE", "COMBINE")


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
    manipulator: str = MANIP_NONE  # NONE | GRASP | RELEASE (single-grasp channel)
    manipulator_left: str = MANIP_NONE  # NONE | GRASP | RELEASE
    manipulator_right: str = MANIP_NONE  # NONE | GRASP | RELEASE
    manipulator_pair: str = MANIP_NONE  # NONE | BRING_TOGETHER | SEPARATE
    apply_to_surface: bool = False  # APPLY_TO_SURFACE; source hand is fixed LEFT
    # Body-local relative_z rate command: -1 DOWN | 0 NONE | +1 UP (per hand).
    effector_z_left: int = EFFECTOR_Z_NONE
    effector_z_right: int = EFFECTOR_Z_NONE
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
            "manipulator": str(self.manipulator or MANIP_NONE),
            "manipulator_left": str(self.manipulator_left or MANIP_NONE),
            "manipulator_right": str(self.manipulator_right or MANIP_NONE),
            "manipulator_pair": str(self.manipulator_pair or MANIP_NONE),
            "apply_to_surface": bool(self.apply_to_surface),
            "effector_z_left": int(self.effector_z_left or 0),
            "effector_z_right": int(self.effector_z_right or 0),
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
        if self.manipulator and self.manipulator != MANIP_NONE:
            parts.append(self.manipulator)
        if self.manipulator_left and self.manipulator_left != MANIP_NONE:
            parts.append(f"LEFT_{self.manipulator_left}")
        if self.manipulator_right and self.manipulator_right != MANIP_NONE:
            parts.append(f"RIGHT_{self.manipulator_right}")
        if self.manipulator_pair and self.manipulator_pair != MANIP_NONE:
            parts.append(self.manipulator_pair)
        if self.apply_to_surface:
            parts.append("APPLY_TO_SURFACE")
        zl = int(self.effector_z_left or 0)
        zr = int(self.effector_z_right or 0)
        if zl > 0:
            parts.append("LEFT_EFFECTOR_Z_UP")
        elif zl < 0:
            parts.append("LEFT_EFFECTOR_Z_DOWN")
        if zr > 0:
            parts.append("RIGHT_EFFECTOR_Z_UP")
        elif zr < 0:
            parts.append("RIGHT_EFFECTOR_Z_DOWN")
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
        elif kind in MANIPULATOR_ACTIONS:
            out.locomotion = "WAIT"
            out.manipulator = kind
        elif kind in BILATERAL_MANIPULATOR_ACTIONS:
            out.locomotion = "WAIT"
            if kind.startswith("LEFT_"):
                out.manipulator_left = kind.split("_", 1)[1]
            else:
                out.manipulator_right = kind.split("_", 1)[1]
        elif kind in PAIR_MANIPULATOR_ACTIONS:
            out.locomotion = "WAIT"
            out.manipulator_pair = kind
        elif kind == "APPLY_TO_SURFACE":
            out.locomotion = "WAIT"
            out.apply_to_surface = True
        elif kind in OSC_FREQ_ACTIONS:
            out.locomotion = "WAIT"
            out.oscillator.frequency_delta = 1 if kind == "OSC_FREQ_UP" else -1
        elif kind in OSC_AMP_ACTIONS:
            out.locomotion = "WAIT"
            out.oscillator.amplitude_delta = 1 if kind == "OSC_AMP_UP" else -1
        elif kind in OSC_EMIT_ACTIONS:
            out.locomotion = "WAIT"
            out.oscillator.emit_trigger = True
        elif kind in LEFT_EFFECTOR_Z_ACTIONS:
            out.locomotion = "WAIT"
            out.effector_z_left = 1 if kind == "LEFT_EFFECTOR_Z_UP" else -1
        elif kind in RIGHT_EFFECTOR_Z_ACTIONS:
            out.locomotion = "WAIT"
            out.effector_z_right = 1 if kind == "RIGHT_EFFECTOR_Z_UP" else -1
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
        if self.manipulator and self.manipulator != MANIP_NONE:
            return str(self.manipulator)
        if self.manipulator_left and self.manipulator_left != MANIP_NONE:
            return f"LEFT_{self.manipulator_left}"
        if self.manipulator_right and self.manipulator_right != MANIP_NONE:
            return f"RIGHT_{self.manipulator_right}"
        if self.manipulator_pair and self.manipulator_pair != MANIP_NONE:
            return str(self.manipulator_pair)
        if self.apply_to_surface:
            return "APPLY_TO_SURFACE"
        if int(self.effector_z_left or 0) > 0:
            return "LEFT_EFFECTOR_Z_UP"
        if int(self.effector_z_left or 0) < 0:
            return "LEFT_EFFECTOR_Z_DOWN"
        if int(self.effector_z_right or 0) > 0:
            return "RIGHT_EFFECTOR_Z_UP"
        if int(self.effector_z_right or 0) < 0:
            return "RIGHT_EFFECTOR_Z_DOWN"
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
    manipulator: str = MANIP_NONE,
    manipulator_source: str = "UNAVAILABLE",
    manipulator_left: str = MANIP_NONE,
    manipulator_left_source: str = "UNAVAILABLE",
    manipulator_right: str = MANIP_NONE,
    manipulator_right_source: str = "UNAVAILABLE",
    manipulator_pair: str = MANIP_NONE,
    manipulator_pair_source: str = "UNAVAILABLE",
    apply_to_surface: bool = False,
    apply_to_surface_source: str = "UNAVAILABLE",
    effector_z_left: int = EFFECTOR_Z_NONE,
    effector_z_left_source: str = "UNAVAILABLE",
    effector_z_right: int = EFFECTOR_Z_NONE,
    effector_z_right_source: str = "UNAVAILABLE",
) -> CompositeMotorOutput:
    out = CompositeMotorOutput(
        locomotion=locomotion or "WAIT",
        neck=neck if neck else NECK_NONE,
        oscillator=osc,
        push=bool(push),
        manipulator=str(manipulator or MANIP_NONE),
        manipulator_left=str(manipulator_left or MANIP_NONE),
        manipulator_right=str(manipulator_right or MANIP_NONE),
        manipulator_pair=str(manipulator_pair or MANIP_NONE),
        apply_to_surface=bool(apply_to_surface),
        effector_z_left=int(effector_z_left or 0),
        effector_z_right=int(effector_z_right or 0),
        schema=MOTOR_SCHEMA,
        selection_source="COMPOSITE_FACTORIZED",
        domain_sources={
            "locomotion": loco_source,
            "neck": neck_source,
            "oscillator": osc_source,
            "push": push_source,
            "manipulator": manipulator_source,
            "manipulator_left": manipulator_left_source,
            "manipulator_right": manipulator_right_source,
            "manipulator_pair": manipulator_pair_source,
            "apply_to_surface": apply_to_surface_source if apply_to_surface else "UNAVAILABLE",
            "effector_z_left": effector_z_left_source,
            "effector_z_right": effector_z_right_source,
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
    physical_grasp_release: bool = False,
    bilateral_grasp_release: bool = False,
    bilateral_bring_together: bool = False,
    bilateral_out: dict[str, str] | None = None,
    effector_relative_z: bool = False,
    effector_z_out: dict[str, Any] | None = None,
) -> tuple[str, str, OscillatorMotorComponent, str, bool, str, str, str]:
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

    manip = MANIP_NONE
    manip_src = "UNAVAILABLE"
    if physical_grasp_release:
        manip_opts = [NECK_NONE] + [a for a in available if a in MANIPULATOR_ACTIONS]
        manip_pick, manip_src = _pick_supported(
            manip_opts, predictions, rng=(rng_value + 0.73) % 1.0, prefer_none=True,
        )
        if manip_pick in MANIPULATOR_ACTIONS:
            manip = manip_pick

    if bilateral_grasp_release:
        left_opts = [NECK_NONE] + [a for a in available if a in ("LEFT_GRASP", "LEFT_RELEASE")]
        left_pick, left_src = _pick_supported(
            left_opts, predictions, rng=(rng_value + 0.73) % 1.0, prefer_none=True,
        )
        right_opts = [NECK_NONE] + [a for a in available if a in ("RIGHT_GRASP", "RIGHT_RELEASE")]
        right_pick, right_src = _pick_supported(
            right_opts, predictions, rng=(rng_value + 0.81) % 1.0, prefer_none=True,
        )
        left_cmd = left_pick.split("_", 1)[1] if left_pick in ("LEFT_GRASP", "LEFT_RELEASE") else MANIP_NONE
        right_cmd = right_pick.split("_", 1)[1] if right_pick in ("RIGHT_GRASP", "RIGHT_RELEASE") else MANIP_NONE
        if bilateral_out is not None:
            bilateral_out["manipulator_left"] = left_cmd
            bilateral_out["manipulator_left_source"] = left_src
            bilateral_out["manipulator_right"] = right_cmd
            bilateral_out["manipulator_right_source"] = right_src

    if bilateral_bring_together:
        pair_opts = [NECK_NONE] + [a for a in available if a in PAIR_MANIPULATOR_ACTIONS]
        pair_pick, pair_src = _pick_supported(
            pair_opts, predictions, rng=(rng_value + 0.89) % 1.0, prefer_none=True,
        )
        pair_cmd = pair_pick if pair_pick in PAIR_MANIPULATOR_ACTIONS else MANIP_NONE
        if bilateral_out is not None:
            bilateral_out["manipulator_pair"] = pair_cmd
            bilateral_out["manipulator_pair_source"] = pair_src

    if effector_relative_z:
        left_z_opts = [NECK_NONE] + [a for a in available if a in LEFT_EFFECTOR_Z_ACTIONS]
        left_z_pick, left_z_src = _pick_supported(
            left_z_opts, predictions, rng=(rng_value + 0.93) % 1.0, prefer_none=True,
        )
        right_z_opts = [NECK_NONE] + [a for a in available if a in RIGHT_EFFECTOR_Z_ACTIONS]
        right_z_pick, right_z_src = _pick_supported(
            right_z_opts, predictions, rng=(rng_value + 0.97) % 1.0, prefer_none=True,
        )
        left_z = 0
        if left_z_pick == "LEFT_EFFECTOR_Z_UP":
            left_z = 1
        elif left_z_pick == "LEFT_EFFECTOR_Z_DOWN":
            left_z = -1
        right_z = 0
        if right_z_pick == "RIGHT_EFFECTOR_Z_UP":
            right_z = 1
        elif right_z_pick == "RIGHT_EFFECTOR_Z_DOWN":
            right_z = -1
        if effector_z_out is not None:
            effector_z_out["effector_z_left"] = left_z
            effector_z_out["effector_z_left_source"] = left_z_src
            effector_z_out["effector_z_right"] = right_z
            effector_z_out["effector_z_right_source"] = right_z_src

    return neck, neck_src, osc, osc_src, push, push_src, manip, manip_src


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
        "manipulator": None,
        "manipulator_left": None,
        "manipulator_right": None,
        "manipulator_pair": None,
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

    applied["manipulator"] = {
        "action": str(motor.manipulator or MANIP_NONE),
        "applied": True,
        "note": "world attachment is resolved after body integrate, not here",
    }
    applied["manipulator_left"] = {
        "action": str(motor.manipulator_left or MANIP_NONE),
        "applied": True,
        "note": "world attachment is resolved after body integrate, not here",
    }
    applied["manipulator_right"] = {
        "action": str(motor.manipulator_right or MANIP_NONE),
        "applied": True,
        "note": "world attachment is resolved after body integrate, not here",
    }
    applied["manipulator_pair"] = {
        "action": str(motor.manipulator_pair or MANIP_NONE),
        "applied": True,
        "note": "pair aperture is resolved after GRASP/RELEASE, not here",
    }

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
    if motor.manipulator and motor.manipulator != MANIP_NONE:
        evs.append({
            "type": "MOTOR_COMPONENT_SELECTED",
            "tick": tick,
            "domain": "manipulator",
            "value": motor.manipulator,
        })
    if motor.manipulator_left and motor.manipulator_left != MANIP_NONE:
        evs.append({
            "type": "MOTOR_COMPONENT_SELECTED",
            "tick": tick,
            "domain": "manipulator_left",
            "value": motor.manipulator_left,
        })
    if motor.manipulator_right and motor.manipulator_right != MANIP_NONE:
        evs.append({
            "type": "MOTOR_COMPONENT_SELECTED",
            "tick": tick,
            "domain": "manipulator_right",
            "value": motor.manipulator_right,
        })
    if motor.manipulator_pair and motor.manipulator_pair != MANIP_NONE:
        evs.append({
            "type": "MOTOR_COMPONENT_SELECTED",
            "tick": tick,
            "domain": "manipulator_pair",
            "value": motor.manipulator_pair,
        })
    if motor.apply_to_surface:
        evs.append({
            "type": "MOTOR_COMPONENT_SELECTED",
            "tick": tick,
            "domain": "apply_to_surface",
            "value": "APPLY_TO_SURFACE",
        })
    zl = int(motor.effector_z_left or 0)
    zr = int(motor.effector_z_right or 0)
    if zl:
        evs.append({
            "type": "MOTOR_COMPONENT_SELECTED",
            "tick": tick,
            "domain": "effector_z_left",
            "value": "UP" if zl > 0 else "DOWN",
        })
    if zr:
        evs.append({
            "type": "MOTOR_COMPONENT_SELECTED",
            "tick": tick,
            "domain": "effector_z_right",
            "value": "UP" if zr > 0 else "DOWN",
        })
    return evs
