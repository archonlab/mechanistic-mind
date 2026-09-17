"""Multi-channel physical perception (Update 4).

Channels carry numeric physical signals only. No semantic object labels,
no privileged object IDs in agent-facing packets, no cross-channel binding.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

PERCEPTION_CONTACT_ONLY = "CONTACT_ONLY"
PERCEPTION_MULTI_CHANNEL = "MULTI_CHANNEL"
PERCEPTION_MODES = (PERCEPTION_CONTACT_ONLY, PERCEPTION_MULTI_CHANNEL)

CHANNEL_DISTANT_STRUCTURAL = "DISTANT_STRUCTURAL"
CHANNEL_PASSIVE_WAVE = "PASSIVE_WAVE"
CHANNEL_AMBIENT_SCALAR = "AMBIENT_SCALAR"
CHANNEL_ACTIVE_RETURN = "ACTIVE_RETURN"
CHANNEL_NEAR_CONTACT = "NEAR_CONTACT"

# Keys never allowed in agent-facing channel packets.
PERCEPTION_FORBIDDEN_KEYS = frozenset(
    {
        "id",
        "object_id",
        "hidden_role",
        "existence",
        "autonomous",
        "autonomous_runtime",
        "causal_provenance",
        "source_object_id",
        "target_object_id",
        "affordance",
        "cue_signature",
        "shape",
        "color",
        "signal",
    }
)

_DEFAULT_STRUCTURAL_RADIUS = 8
_DEFAULT_PASSIVE_RADIUS = 6
_DEFAULT_EMIT_RADIUS = 5
_DEFAULT_NEAR_RADIUS = 2
_MAX_STRUCTURAL_SIGNALS = 12
_MAX_WAVE_COMPONENTS = 8
_MAX_RETURN_FEATURES = 12


def normalize_emission(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Bounded numeric emitter config on an object record."""
    raw = raw if isinstance(raw, dict) else {}
    period = raw.get("period")
    return {
        "enabled": bool(raw.get("enabled", False)),
        "strength": float(raw.get("strength", 0.0)),
        "frequency": float(raw.get("frequency", 1.0)),
        "radius": max(0, int(raw.get("radius", _DEFAULT_PASSIVE_RADIUS))),
        "attenuation": max(0.0, min(1.0, float(raw.get("attenuation", 0.18)))),
        "period": None if period is None else max(1, int(period)),
        "phase": int(raw.get("phase", 0)),
        "directionality": max(
            0.0, min(1.0, float(raw.get("directionality", 0.0)))
        ),
        "reflectivity": max(
            0.0, min(1.0, float(raw.get("reflectivity", 0.35)))
        ),
        "state_field": raw.get("state_field"),
        "state_gain": float(raw.get("state_gain", 0.0)),
        "decorrelation_period": max(0, int(raw.get("decorrelation_period", 0))),
        "local_scalar_only": bool(raw.get("local_scalar_only", False)),
    }


def _manhattan(a: tuple[int, int], b: tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _bearing_bin(dx: int, dy: int) -> int:
    # 8 bins around the agent; numeric only.
    if dx == 0 and dy == 0:
        return 0
    import math

    angle = math.atan2(dy, dx)
    return int((angle + math.pi) / (2 * math.pi) * 8) % 8


def _strip_forbidden(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in payload.items()
        if key not in PERCEPTION_FORBIDDEN_KEYS
    }


def _occlusion_along_ray(
    objects: dict[str, Any],
    *,
    origin: tuple[int, int],
    target: tuple[int, int],
    skip_id: str,
) -> float:
    """Approximate occlusion ∈ [0,1] from objects on Manhattan corridor."""
    if origin == target:
        return 0.0
    dx = 0 if target[0] == origin[0] else (1 if target[0] > origin[0] else -1)
    dy = 0 if target[1] == origin[1] else (1 if target[1] > origin[1] else -1)
    x, y = origin
    occlusion = 0.0
    steps = _manhattan(origin, target)
    for _ in range(max(0, steps - 1)):
        if x != target[0]:
            x += dx
        elif y != target[1]:
            y += dy
        for object_id, record in objects.items():
            if str(object_id) == skip_id or not isinstance(record, dict):
                continue
            pos = record.get("position")
            if not (isinstance(pos, (list, tuple)) and len(pos) == 2):
                continue
            if int(pos[0]) == x and int(pos[1]) == y:
                attenuation = float(record.get("directional_attenuation", 0.0))
                size = float(record.get("size", 0.35))
                occlusion = min(1.0, occlusion + 0.35 * attenuation + 0.15 * size)
    return occlusion


def distant_structural_signals(
    *,
    agent_position: tuple[int, int],
    objects: dict[str, Any],
    radius: int = _DEFAULT_STRUCTURAL_RADIUS,
    near_radius: int = _DEFAULT_NEAR_RADIUS,
) -> list[dict[str, Any]]:
    """Partial geometry/structure before contact. Feature count drops with distance."""
    signals: list[dict[str, Any]] = []
    for object_id, record in sorted(objects.items()):
        if not isinstance(record, dict) or record.get("active", True) is False:
            continue
        existence = record.get("existence")
        if isinstance(existence, dict) and existence.get("present") is False:
            continue
        pos = record.get("position")
        if not (isinstance(pos, (list, tuple)) and len(pos) == 2):
            continue
        object_pos = (int(pos[0]), int(pos[1]))
        distance = _manhattan(agent_position, object_pos)
        if distance <= 0 or distance > radius:
            continue
        # Near-field handled by NEAR_CONTACT / vision; still allow weak overlap.
        dx = object_pos[0] - agent_position[0]
        dy = object_pos[1] - agent_position[1]
        # Information content proxy: farther → fewer feature slots.
        # Not merely amplitude scaling of a fixed vector.
        if distance >= int(0.75 * radius):
            feature_budget = 2
        elif distance >= int(0.45 * radius):
            feature_budget = 4
        elif distance > near_radius:
            feature_budget = 6
        else:
            feature_budget = 7
        occlusion = _occlusion_along_ray(
            objects,
            origin=agent_position,
            target=object_pos,
            skip_id=str(object_id),
        )
        strength = max(
            0.0,
            (1.0 - distance / max(1, radius)) * (1.0 - 0.85 * occlusion),
        )
        size = float(record.get("size", 0.35))
        features: dict[str, float] = {
            "strength": round(strength, 4),
            "bearing_bin": float(_bearing_bin(dx, dy)),
        }
        candidates = [
            ("extent", round(size * strength, 4)),
            ("occlusion", round(occlusion, 4)),
            ("opacity", round(float(record.get("opacity", 1.0)) * strength, 4)),
            ("brightness", round(float(record.get("brightness", 0.5)) * strength, 4)),
            ("hardness", round(float(record.get("hardness", 0.5)) * strength, 4)),
            (
                "mass_proxy",
                round(min(1.0, float(record.get("mass_kg", 0.0)) / 40.0) * strength, 4),
            ),
        ]
        for name, value in candidates[: max(0, feature_budget - 2)]:
            features[name] = value
        # Drop near-zero signals.
        if features["strength"] <= 1e-4:
            continue
        signals.append(
            {
                "channel": CHANNEL_DISTANT_STRUCTURAL,
                "distance_bin": int(distance),
                "feature_count": len(features),
                "features": features,
            }
        )
    signals.sort(
        key=lambda item: (
            -float(item["features"]["strength"]),
            int(item["distance_bin"]),
            int(item["features"].get("bearing_bin", 0)),
        )
    )
    return [_strip_forbidden(item) for item in signals[:_MAX_STRUCTURAL_SIGNALS]]


def passive_wave_signals(
    *,
    agent_position: tuple[int, int],
    objects: dict[str, Any],
    clock: int,
) -> list[dict[str, Any]]:
    """Generic propagating emissions; numeric measurements only."""
    components: list[dict[str, Any]] = []
    for object_id, record in sorted(objects.items()):
        if not isinstance(record, dict) or record.get("active", True) is False:
            continue
        existence = record.get("existence")
        if isinstance(existence, dict) and existence.get("present") is False:
            continue
        emission = normalize_emission(record.get("emission"))
        if not emission["enabled"] or emission["strength"] <= 0.0:
            continue
        pos = record.get("position")
        if not (isinstance(pos, (list, tuple)) and len(pos) == 2):
            continue
        object_pos = (int(pos[0]), int(pos[1]))
        distance = _manhattan(agent_position, object_pos)
        if distance > emission["radius"]:
            continue
        if emission["period"] is not None:
            phase = (int(clock) + emission["phase"]) % emission["period"]
            if phase != 0:
                continue
        path_loss = (1.0 - emission["attenuation"]) ** distance
        state_factor = 1.0
        field = emission.get("state_field")
        if field:
            mutable = record.get("mutable_state") if isinstance(record.get("mutable_state"), dict) else record
            capacity = float((record.get("state_capacities") or {}).get(field, record.get(f"max_{field}", 1.0)) or 1.0)
            phase_value = max(0.0, min(1.0, float(mutable.get(field, 0.0)) / max(1e-9, capacity)))
            if emission["decorrelation_period"]:
                phase_value = ((int(clock) * 37) % emission["decorrelation_period"]) / emission["decorrelation_period"]
            state_factor = max(0.0, 1.0 + emission["state_gain"] * phase_value)
        amplitude = emission["strength"] * state_factor * path_loss
        if amplitude <= 1e-5:
            continue
        dx = object_pos[0] - agent_position[0]
        dy = object_pos[1] - agent_position[1]
        component = {
                "channel": CHANNEL_PASSIVE_WAVE,
                "amplitude": round(amplitude, 5),
                "frequency": round(emission["frequency"], 4),
                "directionality": round(emission["directionality"], 4),
            }
        if not emission["local_scalar_only"]:
            component.update({"bearing_bin": float(_bearing_bin(dx, dy)), "distance_bin": int(distance)})
        components.append(component)
    components.sort(
        key=lambda item: (-float(item["amplitude"]), float(item["frequency"]))
    )
    return [_strip_forbidden(item) for item in components[:_MAX_WAVE_COMPONENTS]]


def near_contact_signals(
    *,
    visual_fragments: list[dict[str, Any]],
    visible_objects: list[dict[str, Any]],
    action_receipt: dict[str, Any] | None,
    near_radius: int = _DEFAULT_NEAR_RADIUS,
) -> list[dict[str, Any]]:
    """Integrate existing near-field/contact cues without semantic labels."""
    signals: list[dict[str, Any]] = []
    for item in visual_fragments:
        if not isinstance(item, dict):
            continue
        distance = int(item.get("distance", 99))
        if distance > near_radius:
            continue
        features = {
            "distance_bin": float(distance),
            "size": float(item.get("size", 0.0) or 0.0),
            "opacity": float(item.get("opacity", 0.0) or 0.0),
            "brightness": float(item.get("brightness", 0.0) or 0.0),
        }
        # Exclude shape/color/cue_signature deliberately.
        signals.append(
            {
                "channel": CHANNEL_NEAR_CONTACT,
                "kind_bin": 1.0 if item.get("kind") == "OBJECT" else 0.0,
                "feature_count": len(features),
                "features": features,
            }
        )
    receipt = action_receipt if isinstance(action_receipt, dict) else {}
    contact_bits = {
        "obstacle_contact": 1.0 if receipt.get("obstacle_contact") else 0.0,
        "object_moved": 1.0 if receipt.get("object_moved") else 0.0,
        "push_resistance": float(receipt.get("push_resistance") or 0.0),
        "carried": 1.0 if receipt.get("carried") else 0.0,
    }
    if any(value > 0.0 for value in contact_bits.values()):
        signals.append(
            {
                "channel": CHANNEL_NEAR_CONTACT,
                "kind_bin": 2.0,
                "feature_count": len(contact_bits),
                "features": contact_bits,
            }
        )
    # Bound.
    return [_strip_forbidden(item) for item in signals[:16]]


def compute_emit_returns(
    *,
    agent_position: tuple[int, int],
    objects: dict[str, Any],
    emit_strength: float = 1.0,
    emit_radius: int = _DEFAULT_EMIT_RADIUS,
) -> list[dict[str, Any]]:
    """Physical return patterns from an agent EMIT. No object IDs in returns."""
    returns: list[dict[str, Any]] = []
    # Observer-only side channel collected separately by caller if needed.
    for object_id, record in sorted(objects.items()):
        if not isinstance(record, dict) or record.get("active", True) is False:
            continue
        existence = record.get("existence")
        if isinstance(existence, dict) and existence.get("present") is False:
            continue
        pos = record.get("position")
        if not (isinstance(pos, (list, tuple)) and len(pos) == 2):
            continue
        object_pos = (int(pos[0]), int(pos[1]))
        distance = _manhattan(agent_position, object_pos)
        if distance <= 0 or distance > emit_radius:
            continue
        emission = normalize_emission(record.get("emission"))
        reflectivity = emission["reflectivity"]
        if reflectivity <= 0.0:
            reflectivity = max(
                0.05,
                min(
                    1.0,
                    0.2 * float(record.get("hardness", 0.5))
                    + 0.15 * float(record.get("size", 0.35))
                    + 0.1 * float(record.get("directional_attenuation", 0.0)),
                ),
            )
        path = (0.82) ** (2 * distance)
        amplitude = emit_strength * reflectivity * path
        if amplitude <= 1e-5:
            continue
        dx = object_pos[0] - agent_position[0]
        dy = object_pos[1] - agent_position[1]
        features = {
            "amplitude": round(amplitude, 5),
            "delay_bins": float(distance),
            "bearing_bin": float(_bearing_bin(dx, dy)),
            "dispersion": round(min(1.0, distance / max(1, emit_radius)), 4),
            "hardness_proxy": round(
                float(record.get("hardness", 0.5)) * amplitude, 4
            ),
        }
        # Farther returns keep fewer features (information loss).
        if distance > emit_radius // 2:
            features = {
                key: features[key]
                for key in ("amplitude", "delay_bins", "bearing_bin")
            }
        returns.append(
            {
                "channel": CHANNEL_ACTIVE_RETURN,
                "feature_count": len(features),
                "features": features,
                # Observer-only annotation stripped before cognition:
                "_observer_object_id": str(object_id),
            }
        )
    returns.sort(
        key=lambda item: -float(item["features"]["amplitude"])
    )
    return returns[:_MAX_RETURN_FEATURES]


def agent_facing_returns(returns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for item in returns:
        row = {
            key: value
            for key, value in item.items()
            if not str(key).startswith("_")
        }
        cleaned.append(_strip_forbidden(row))
    return cleaned


def channel_summary(channels: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for name, rows in channels.items():
        strengths = []
        feature_counts = []
        for row in rows:
            features = row.get("features") if isinstance(row, dict) else None
            if isinstance(features, dict):
                if "strength" in features:
                    strengths.append(float(features["strength"]))
                elif "amplitude" in features:
                    strengths.append(float(features["amplitude"]))
                feature_counts.append(int(row.get("feature_count") or len(features)))
            elif isinstance(row, dict) and "amplitude" in row:
                strengths.append(float(row["amplitude"]))
                feature_counts.append(3)
        summary[name] = {
            "active_count": len(rows),
            "strength_sum": round(sum(strengths), 5),
            "strength_max": round(max(strengths), 5) if strengths else 0.0,
            "feature_diversity": int(sum(feature_counts)),
            "mean_feature_count": (
                round(sum(feature_counts) / len(feature_counts), 3)
                if feature_counts
                else 0.0
            ),
        }
    return summary


def build_perception_packet(
    *,
    agent_position: tuple[int, int],
    objects: dict[str, Any],
    visual_fragments: list[dict[str, Any]],
    visible_objects: list[dict[str, Any]],
    action_receipt: dict[str, Any] | None,
    clock: int,
    mode: str,
    pending_returns: list[dict[str, Any]] | None,
    structural_radius: int = _DEFAULT_STRUCTURAL_RADIUS,
    near_radius: int = _DEFAULT_NEAR_RADIUS,
    ambient_scalars: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Assemble agent-facing multi-channel perception."""
    mode = str(mode or PERCEPTION_CONTACT_ONLY)

    ambient_rows = []
    if isinstance(ambient_scalars, dict) and ambient_scalars:
        # Local fragments only; keys are generic physical channel ids, not place names.
        for key, value in sorted(ambient_scalars.items()):
            ambient_rows.append({
                "feature": str(key),
                "amplitude": round(float(value), 5),
                "strength": round(abs(float(value)), 5),
            })
    near = near_contact_signals(
        visual_fragments=visual_fragments,
        visible_objects=visible_objects,
        action_receipt=action_receipt,
        near_radius=near_radius,
    )
    if mode != PERCEPTION_MULTI_CHANNEL:
        channels = {
            CHANNEL_DISTANT_STRUCTURAL: [],
            CHANNEL_PASSIVE_WAVE: [],
            CHANNEL_ACTIVE_RETURN: [],
            CHANNEL_NEAR_CONTACT: near,
            CHANNEL_AMBIENT_SCALAR: ambient_rows,
        }
    else:
        channels = {
            CHANNEL_DISTANT_STRUCTURAL: distant_structural_signals(
                agent_position=agent_position,
                objects=objects,
                radius=structural_radius,
                near_radius=near_radius,
            ),
            CHANNEL_PASSIVE_WAVE: passive_wave_signals(
                agent_position=agent_position,
                objects=objects,
                clock=clock,
            ),
            CHANNEL_ACTIVE_RETURN: agent_facing_returns(pending_returns or []),
            CHANNEL_NEAR_CONTACT: near,
            CHANNEL_AMBIENT_SCALAR: ambient_rows,
        }
    return {
        "mode": mode,
        "channels": channels,
        "summary": channel_summary(channels),
    }


def perception_delta(
    previous: dict[str, Any] | None,
    current: dict[str, Any],
) -> dict[str, Any]:
    """Bounded change diagnostics for Observer / experience."""
    prev_summary = (
        (previous or {}).get("summary")
        if isinstance(previous, dict)
        else {}
    )
    curr_summary = current.get("summary") if isinstance(current, dict) else {}
    delta: dict[str, Any] = {}
    for name in (
        CHANNEL_DISTANT_STRUCTURAL,
        CHANNEL_PASSIVE_WAVE,
        CHANNEL_ACTIVE_RETURN,
        CHANNEL_NEAR_CONTACT,
        CHANNEL_AMBIENT_SCALAR,
    ):
        before = prev_summary.get(name) if isinstance(prev_summary, dict) else {}
        after = curr_summary.get(name) if isinstance(curr_summary, dict) else {}
        before = before if isinstance(before, dict) else {}
        after = after if isinstance(after, dict) else {}
        delta[name] = {
            "active_count_delta": int(after.get("active_count", 0))
            - int(before.get("active_count", 0)),
            "strength_sum_delta": round(
                float(after.get("strength_sum", 0.0))
                - float(before.get("strength_sum", 0.0)),
                5,
            ),
            "feature_diversity_delta": int(after.get("feature_diversity", 0))
            - int(before.get("feature_diversity", 0)),
        }
    return delta
