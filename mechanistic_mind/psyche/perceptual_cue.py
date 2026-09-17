"""Update 4.1 — bounded non-semantic perceptual features for ordinary context_cue.

PHYSICALLY AVAILABLE channel packets → coarse bands suitable for cue/retrieval.
No object IDs, no semantic labels, no privileged cross-channel binding.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

CUE_LEGACY_ONLY = "LEGACY_CUE_ONLY"
CUE_PERCEPTUAL_ENABLED = "PERCEPTUAL_CUE_ENABLED"
CUE_MODES = (CUE_LEGACY_ONLY, CUE_PERCEPTUAL_ENABLED)

_CHANNEL_ORDER = (
    "DISTANT_STRUCTURAL",
    "PASSIVE_WAVE",
    "ACTIVE_RETURN",
    "NEAR_CONTACT",
)


def _band01(value: float, edges: tuple[float, float] = (0.25, 0.6)) -> str:
    if value <= 1e-9:
        return "Z"
    if value < edges[0]:
        return "L"
    if value < edges[1]:
        return "M"
    return "H"


def _int_band(value: int, edges: tuple[int, int] = (2, 5)) -> str:
    if value <= 0:
        return "Z"
    if value < edges[0]:
        return "L"
    if value < edges[1]:
        return "M"
    return "H"


def extract_bounded_perceptual_features(
    physical_perception: dict[str, Any] | None,
    *,
    max_features: int = 24,
) -> list[tuple[str, ...]]:
    """Deterministic coarse features from Update 4 channel packets / summary / delta."""
    if not isinstance(physical_perception, dict):
        return []
    channels = physical_perception.get("channels")
    summary = physical_perception.get("summary")
    delta = physical_perception.get("delta")
    channels = channels if isinstance(channels, dict) else {}
    summary = summary if isinstance(summary, dict) else {}
    delta = delta if isinstance(delta, dict) else {}

    features: list[tuple[str, ...]] = []
    for name in _CHANNEL_ORDER:
        rows = channels.get(name) or ()
        if not isinstance(rows, (list, tuple)):
            rows = ()
        row_summary = summary.get(name) if isinstance(summary.get(name), dict) else {}
        row_delta = delta.get(name) if isinstance(delta.get(name), dict) else {}
        active = int(row_summary.get("active_count", len(rows)) or 0)
        strength = float(row_summary.get("strength_sum", 0.0) or 0.0)
        diversity = int(row_summary.get("feature_diversity", 0) or 0)
        mean_feat = float(row_summary.get("mean_feature_count", 0.0) or 0.0)
        # Presence + coarse intensity / diversity (partial distant stays partial via mean_feat).
        features.append(
            (
                "ch",
                name[:2],  # DS/PW/AR/NE abbreviated non-semantic tags
                "p",
                "1" if active > 0 else "0",
                "s",
                _band01(strength),
                "n",
                _int_band(active),
                "f",
                _band01(mean_feat / 8.0),
                "d",
                _int_band(diversity, (4, 12)),
            )
        )
        # Temporal delta bands when present.
        s_delta = float(row_delta.get("strength_sum_delta", 0.0) or 0.0)
        n_delta = int(row_delta.get("active_count_delta", 0) or 0)
        if abs(s_delta) > 1e-9 or n_delta != 0:
            features.append(
                (
                    "ch",
                    name[:2],
                    "Δs",
                    "P" if s_delta > 0 else ("N" if s_delta < 0 else "Z"),
                    "Δn",
                    "P" if n_delta > 0 else ("N" if n_delta < 0 else "Z"),
                )
            )
        # Coarse directional / frequency samples from individual packets (no IDs).
        bearings: list[float] = []
        freqs: list[float] = []
        feat_counts: list[int] = []
        for packet in list(rows)[:6]:
            if not isinstance(packet, dict):
                continue
            feats = packet.get("features")
            feats = feats if isinstance(feats, dict) else {}
            if "bearing_bin" in feats:
                bearings.append(float(feats["bearing_bin"]))
            elif "bearing_bin" in packet:
                bearings.append(float(packet["bearing_bin"]))
            if "frequency" in packet:
                freqs.append(float(packet["frequency"]))
            fc = packet.get("feature_count")
            if fc is not None:
                feat_counts.append(int(fc))
            elif feats:
                feat_counts.append(len(feats))
        if bearings:
            # Quantize mean bearing into 4 bins only — not object identity.
            mean_b = sum(bearings) / len(bearings)
            features.append(("ch", name[:2], "br", str(int(mean_b) // 2)))
        if freqs:
            mean_f = sum(freqs) / len(freqs)
            features.append(("ch", name[:2], "fq", _band01(mean_f / 2.0)))
        if feat_counts and name == "DISTANT_STRUCTURAL":
            # Preserve information loss: low mean feature_count stays low band.
            features.append(
                (
                    "ch",
                    "DS",
                    "partial",
                    _band01(sum(feat_counts) / (len(feat_counts) * 8.0)),
                )
            )

    # Stable order, hard bound.
    features = sorted(features, key=lambda item: repr(item))[:max_features]
    return features


def perceptual_feature_tokens(
    physical_perception: dict[str, Any] | None,
    *,
    max_features: int = 24,
) -> tuple[str, ...]:
    rows = extract_bounded_perceptual_features(
        physical_perception, max_features=max_features
    )
    return tuple("|".join(item) for item in rows)


def cue_uptake_summary(
    *,
    physical_perception: dict[str, Any] | None,
    cue: dict[str, Any],
    mode: str,
) -> dict[str, Any]:
    """Observer diagnostic: available vs represented in cue."""
    channels = {}
    if isinstance(physical_perception, dict):
        raw = physical_perception.get("channels") or {}
        if isinstance(raw, dict):
            channels = raw
    tokens = list(cue.get("perceptual_features") or ())
    by_channel: dict[str, dict[str, str]] = {}
    for name in _CHANNEL_ORDER:
        available = bool(channels.get(name))
        tag = name[:2]
        represented = any(str(tok).startswith(f"ch|{tag}|") for tok in tokens)
        by_channel[name] = {
            "AVAILABLE_TO_SENSOR": "yes" if available else "no",
            "REPRESENTED_IN_CUE": (
                "yes"
                if represented
                else ("no" if mode == CUE_PERCEPTUAL_ENABLED else "n/a_legacy")
            ),
            "MATCHED_IN_RETRIEVAL": "UNKNOWN",
            "CONTRIBUTED_TO_DECISION": "UNKNOWN",
        }
    return {
        "cue_mode": mode,
        "perceptual_token_count": len(tokens),
        "channels": by_channel,
        "tokens_preview": tokens[:12],
    }
