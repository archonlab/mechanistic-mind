"""MM-INT-1 — embodied psyche integration (designed substrate).

DESIGNED MECHANISM != PREPROGRAMMED PHENOMENON.

Ordinary same-stream wiring when BodyConfig.embodied_integration_config is set.
Default BodyConfig leaves this OFF (legacy / research isolation).

Does not implement reward, utility, goal, desire, preference, seeking,
Action.kind selection from memory, or BODY-improvement teaching signals.
Does not promote internal_a / load_c as natural receptors (E3D).
Does not enable X / universal physical F (E3E).
"""
from __future__ import annotations

import math
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from mechanistic_mind.body.acquired_transition_reinstatement import reinstate
from mechanistic_mind.body.internal_transition_acquisition import (
    M_DIM,
    S_DIM,
    TransitionRelationState,
    acquire,
    record,
)
from mechanistic_mind.body.sensorimotor_dynamics import (
    CHANNELS,
    SensorimotorState,
    evolve,
)

# Frozen N→effector projection (sites order matches physical_effector.DEFAULT_SITES).
# Sites: (0,-1), (-1,0), (1,0), (0,1). Drive must be >= 0 for effector clip_e.
DRIVE_PROJECTION: tuple[tuple[float, float, float], ...] = (
    (0.35, 0.10, -0.05),
    (-0.35, 0.10, 0.05),
    (0.05, 0.35, -0.10),
    (-0.05, -0.35, 0.10),
)
REINSTATEMENT_GAIN = 0.12
DRIVE_BOUND = 1.0

# MM-INT-2 drive coupling modes (production integration correction).
DRIVE_COUPLING_LEGACY = "legacy_p_relu"
DRIVE_COUPLING_ANTAGONISTIC = "antagonistic_axes_v1"


def default_embodied_integration_config() -> dict[str, Any]:
    return {
        "enabled": True,
        "nervous_enabled": True,
        "body_receptors_enabled": True,
        "world_receptors_enabled": True,
        "neural_drive_enabled": True,
        "acquisition_enabled": True,
        "reinstatement_enabled": True,
        "reinstatement_to_dynamics_enabled": True,
        "reinstatement_gain": REINSTATEMENT_GAIN,
        "noise_enabled": True,
        "ablate_memory": False,
        "ablate_receptors": False,
        "ablate_effector_drive": False,
        "drive_coupling": DRIVE_COUPLING_LEGACY,
        "provenance": "DESIGNED_SUBSTRATE",
    }


def _clip1(x: float) -> float:
    return max(-1.0, min(1.0, float(x)))


def _center01(x: float) -> float:
    return _clip1(float(x) - 0.5)


def body_receptors(
    energy_reserve: float,
    hydration: float,
    fatigue: float,
) -> tuple[float, float, float]:
    """Structural BODY receptors from physiology scalars. Not hunger/pain labels."""
    return (
        _center01(energy_reserve),
        _center01(hydration),
        _center01(fatigue),
    )


def world_receptors(observation_data: dict[str, Any] | None) -> tuple[float, float, float]:
    """Structural WORLD receptors from local observation only."""
    data = observation_data if isinstance(observation_data, dict) else {}
    visible = data.get("visible_objects") or ()
    if not isinstance(visible, (list, tuple)):
        visible = ()
    saliences = []
    for row in visible:
        if isinstance(row, dict) and isinstance(row.get("cue_salience"), (int, float)):
            saliences.append(float(row["cue_salience"]))
    mean_sal = sum(saliences) / len(saliences) if saliences else 0.5
    # tactile: last_experience contact cue if provided under observation_data
    contact = 0.0
    if data.get("_tactile_contact"):
        contact = 1.0
    elif isinstance(data.get("perceptual_context"), dict):
        frags = data["perceptual_context"].get("fragments") or ()
        for frag in frags:
            if isinstance(frag, dict) and frag.get("modality") == "tactile" and frag.get("contact"):
                contact = 1.0
                break
    count_n = min(1.0, float(len(visible)) / 8.0)
    return (_center01(mean_sal), _center01(contact), _center01(count_n))


def project_neural_drive_legacy(channels: tuple[float, ...]) -> tuple[float, float, float, float]:
    """MM-INT-1 legacy: D = clip(max(0, P @ N), 0, 1)."""
    ch = tuple(float(channels[i]) if i < len(channels) else 0.0 for i in range(CHANNELS))
    out = []
    for row in DRIVE_PROJECTION:
        raw = sum(row[i] * ch[i] for i in range(CHANNELS))
        out.append(max(0.0, min(DRIVE_BOUND, raw)))
    return (out[0], out[1], out[2], out[3])


def project_neural_drive_antagonistic_axes(channels: tuple[float, ...]) -> tuple[float, float, float, float]:
    """MM-INT-2 preregistered coupling: signed N0/N1 → antagonistic site pairs.

    Sites order matches physical_effector.DEFAULT_SITES:
      0=(0,-1)S, 1=(-1,0)W, 2=(1,0)E, 3=(0,1)N
    N2 unused for directional drive (documented residual).
    Declared-domain map [-1,1]→[0,1]; N=0 → D=0. No behavioral calibration.
    """
    n0 = float(channels[0]) if len(channels) > 0 else 0.0
    n1 = float(channels[1]) if len(channels) > 1 else 0.0
    d0 = max(0.0, min(DRIVE_BOUND, max(0.0, -n1)))  # South
    d1 = max(0.0, min(DRIVE_BOUND, max(0.0, -n0)))  # West
    d2 = max(0.0, min(DRIVE_BOUND, max(0.0, n0)))   # East
    d3 = max(0.0, min(DRIVE_BOUND, max(0.0, n1)))   # North
    return (d0, d1, d2, d3)


def project_neural_drive(
    channels: tuple[float, ...],
    *,
    mode: str | None = None,
) -> tuple[float, float, float, float]:
    """N→site drive. mode defaults to legacy_p_relu for historical compatibility."""
    m = mode or DRIVE_COUPLING_LEGACY
    if m == DRIVE_COUPLING_ANTAGONISTIC:
        return project_neural_drive_antagonistic_axes(channels)
    return project_neural_drive_legacy(channels)


def default_mm_int2_integration_config() -> dict[str, Any]:
    """MM-INT-2 organism mode: frozen MM-INT-1 + antagonistic drive coupling."""
    cfg = dict(default_embodied_integration_config())
    cfg["drive_coupling"] = DRIVE_COUPLING_ANTAGONISTIC
    cfg["provenance"] = "DESIGNED_SUBSTRATE_MM_INT2"
    return cfg


def r_l_to_endogenous(r_l, gain: float = REINSTATEMENT_GAIN) -> tuple[float, float, float]:
    """Bounded R_L → endogenous N perturbation. Preserves M×S_after structure; no argmax."""
    g = float(gain)
    out = []
    for k in range(S_DIM):
        acc = 0.0
        for j in range(M_DIM):
            acc += float(r_l[j][k])
        out.append(_clip1(g * math.tanh(acc / float(M_DIM))))
    return (out[0], out[1], out[2])


def _zero_r():
    z = (0.0, 0.0, 0.0)
    return (z, z)


def _weights_from_payload(raw) -> tuple:
    if raw is None:
        return TransitionRelationState().weights
    # nested lists ok
    return tuple(
        tuple(tuple(float(x) for x in pair) for pair in row)
        for row in raw
    )


@dataclass
class EmbodiedIntegrationState:
    nervous: SensorimotorState = field(default_factory=SensorimotorState)
    relation: TransitionRelationState = field(default_factory=TransitionRelationState)
    pending_s: tuple[float, float, float] | None = None
    pending_m: tuple[float, float] | None = None
    pending_valid: bool = False
    last_body_receptors: tuple[float, float, float] = (0.0, 0.0, 0.0)
    last_world_receptors: tuple[float, float, float] = (0.0, 0.0, 0.0)
    last_r_l: tuple = field(default_factory=_zero_r)
    last_drive: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    last_endogenous: tuple[float, float, float] = (0.0, 0.0, 0.0)
    tick: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "nervous": self.nervous.to_dict(),
            "relation": self.relation.to_dict(),
            "pending_s": self.pending_s,
            "pending_m": self.pending_m,
            "pending_valid": bool(self.pending_valid),
            "last_body_receptors": list(self.last_body_receptors),
            "last_world_receptors": list(self.last_world_receptors),
            "last_r_l": [list(row) for row in self.last_r_l],
            "last_drive": list(self.last_drive),
            "last_endogenous": list(self.last_endogenous),
            "tick": int(self.tick),
            "provenance": "DESIGNED_SUBSTRATE",
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "EmbodiedIntegrationState":
        if not isinstance(payload, dict):
            return cls()
        nerv = payload.get("nervous") or {}
        nervous = SensorimotorState(
            channels=tuple(float(x) for x in (nerv.get("channels") or (0.0, 0.0, 0.0))),
            previous_output=tuple(float(x) for x in (nerv.get("previous_output") or (0.0, 0.0, 0.0))),
            tick=int(nerv.get("tick", 0)),
        )
        rel = payload.get("relation") or {}
        relation = TransitionRelationState(
            weights=_weights_from_payload(rel.get("weights")),
            trace_s=tuple(float(x) for x in (rel.get("trace_s") or (0.0, 0.0, 0.0))),
            trace_m=tuple(float(x) for x in (rel.get("trace_m") or (0.0, 0.0))),
            tick=int(rel.get("tick", 0)),
            update_count=int(rel.get("update_count", 0)),
        )
        ps = payload.get("pending_s")
        pm = payload.get("pending_m")
        rl = payload.get("last_r_l") or _zero_r()
        return cls(
            nervous=nervous,
            relation=relation,
            pending_s=tuple(float(x) for x in ps) if isinstance(ps, (list, tuple)) else None,
            pending_m=tuple(float(x) for x in pm) if isinstance(pm, (list, tuple)) else None,
            pending_valid=bool(payload.get("pending_valid", False)),
            last_body_receptors=tuple(float(x) for x in (payload.get("last_body_receptors") or (0.0, 0.0, 0.0))),
            last_world_receptors=tuple(float(x) for x in (payload.get("last_world_receptors") or (0.0, 0.0, 0.0))),
            last_r_l=tuple(tuple(float(x) for x in row) for row in rl),
            last_drive=tuple(float(x) for x in (payload.get("last_drive") or (0.0, 0.0, 0.0, 0.0))),
            last_endogenous=tuple(float(x) for x in (payload.get("last_endogenous") or (0.0, 0.0, 0.0))),
            tick=int(payload.get("tick", 0)),
        )


def step_pre_action(
    state: EmbodiedIntegrationState,
    *,
    energy_reserve: float,
    hydration: float,
    fatigue: float,
    observation_data: dict[str, Any] | None,
    config: dict[str, Any],
    random_value: float = 0.5,
) -> tuple[EmbodiedIntegrationState, tuple[float, float, float, float]]:
    """One ordinary-tick integration update before physical effector application."""
    cfg = config if isinstance(config, dict) else {}
    if not cfg.get("enabled", True):
        return state, (0.0, 0.0, 0.0, 0.0)

    st = EmbodiedIntegrationState.from_dict(state.to_dict())
    ablate_mem = bool(cfg.get("ablate_memory", False))
    ablate_rec = bool(cfg.get("ablate_receptors", False))
    ablate_drive = bool(cfg.get("ablate_effector_drive", False))

    # Deferred acquisition: pending (S,M) + current N as S_after
    if (
        cfg.get("acquisition_enabled", True)
        and not ablate_mem
        and st.pending_valid
        and st.pending_s is not None
        and st.pending_m is not None
    ):
        st.relation = record(st.relation, s=st.pending_s, m=st.pending_m, eligibility=True)
        st.relation = acquire(st.relation, s_after=st.nervous.channels, plasticity=True)
        st.pending_valid = False

    if ablate_mem:
        st.relation = TransitionRelationState()
        st.pending_valid = False
        st.pending_s = None
        st.pending_m = None

    # Receptors
    if ablate_rec or not cfg.get("body_receptors_enabled", True):
        b_rec = (0.0, 0.0, 0.0)
    else:
        b_rec = body_receptors(energy_reserve, hydration, fatigue)
    if ablate_rec or not cfg.get("world_receptors_enabled", True):
        w_rec = (0.0, 0.0, 0.0)
    else:
        w_rec = world_receptors(observation_data)
    st.last_body_receptors = b_rec
    st.last_world_receptors = w_rec

    # Reinstatement → endogenous
    endogenous = (0.0, 0.0, 0.0)
    r_now = _zero_r()
    if (
        cfg.get("reinstatement_enabled", True)
        and cfg.get("reinstatement_to_dynamics_enabled", True)
        and not ablate_mem
    ):
        r_now = reinstate(st.nervous.channels, st.relation.weights)
        gain = float(cfg.get("reinstatement_gain", REINSTATEMENT_GAIN))
        endogenous = r_l_to_endogenous(r_now, gain=gain)
    st.last_r_l = r_now
    st.last_endogenous = endogenous

    s_before = st.nervous.channels
    if cfg.get("nervous_enabled", True):
        noise = float(random_value) if cfg.get("noise_enabled", True) else 0.5
        st.nervous = evolve(
            st.nervous,
            body={},  # production path does not use ia/lc
            production_inputs=(b_rec[0], b_rec[1]),
            sensory=w_rec,
            random_value=noise,
            body_coupling=True,
            dynamics_enabled=True,
            endogenous=endogenous,
            endogenous_coupling=True,
        )
    else:
        st.nervous = SensorimotorState(
            channels=st.nervous.channels,
            previous_output=st.nervous.previous_output,
            tick=st.nervous.tick + 1,
        )

    drive = (0.0, 0.0, 0.0, 0.0)
    if cfg.get("neural_drive_enabled", True) and not ablate_drive:
        drive = project_neural_drive(
            st.nervous.channels,
            mode=str(cfg.get("drive_coupling") or DRIVE_COUPLING_LEGACY),
        )
    st.last_drive = drive

    # Pending experience uses pre-evolve S and M=drive[:2] (not Action.kind)
    if cfg.get("acquisition_enabled", True) and not ablate_mem:
        st.pending_s = s_before
        st.pending_m = (float(drive[0]), float(drive[1]))
        st.pending_valid = True

    st.tick += 1
    return st, drive


def integration_enabled(body_config: Any) -> bool:
    cfg = getattr(body_config, "embodied_integration_config", None)
    return isinstance(cfg, dict) and bool(cfg.get("enabled", True))
