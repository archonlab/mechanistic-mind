"""MM 1.0 — Tiktaalik canonical model identity, manifest, and defaults."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from .identity import (
    LEGACY_RUNTIME_VERSION,
    MANIFEST_SCHEMA_VERSION,
    MODEL_CODENAME,
    MODEL_FAMILY,
    MODEL_VERSION,
    OBSERVER_API_VERSION,
    PROMOTION,
    RUNTIME_VERSION,
    SNAPSHOT_SCHEMA,
    display_name,
    promotion_class,
    release_display_name,
)

EXPERIMENTAL_COGNITION_KEYS = (
    "unknown_action_physical_probe",
    "predictive_equivalence",
    "predictive_relevance",
    "temporal_predictive_structure",
    "temporal_prospection_bridge",
    "predictive_conflict",
    "future_sensitive_action",
    "prediction_error_revision",
    "temporal_prediction_error",
    "predicted_context_prospection",
    "multistep_action_prospection",
)

BOUNDED_LIMITS = {
    "causal_trace_capacity": 512,
    "prospective_depth": 3,
    "pc_MAX_CLASSES": 64,
    "pc_MAX_MEMBERS": 128,
    "tps_WINDOW": 4,
    "tps_RING": 16,
    "pr_MAX_TRANSITIONS": 128,
    "pr_MAX_WORKSPACE": 32,
    "pr_MAX_DEPTH": 8,
    "pr_MAX_BRANCH": 4,
    "sc_MAX_SCENARIOS_TOTAL": 32,
    "pcp_MAX_BRANCHES": 8,
    "map_MAX_BRANCHES": 8,
}


def tiktaalik_cognition_config():
    from mechanistic_mind.physical_system.cognition import CognitionConfig

    return CognitionConfig()


def tiktaalik_config():
    """Canonical Tiktaalik PhysicalSystemConfig: promoted BASELINE_CLIMATE_DEFAULT."""
    from mechanistic_mind.physical_system.ecology_presets import (
        ECOLOGY_BASELINE,
        make_ecology_config,
    )

    cfg = make_ecology_config(ECOLOGY_BASELINE)
    cfg.runtime_version = RUNTIME_VERSION
    cfg.cognition = tiktaalik_cognition_config()
    return cfg


def experimental_overrides(config) -> dict[str, bool]:
    cog = getattr(config, "cognition", None)
    if cog is None:
        return {}
    base = tiktaalik_cognition_config()
    out: dict[str, bool] = {}
    for key in EXPERIMENTAL_COGNITION_KEYS:
        cur = bool(getattr(cog, key, False))
        if cur != bool(getattr(base, key, False)):
            out[key] = cur
    planet = getattr(config, "planet", None)
    ce = getattr(planet, "climate_ecology", None) if planet else None
    # Climate ON is the promoted Tiktaalik baseline — not an experimental override.
    # Flag only when climate is OFF relative to canonical baseline, or when an
    # alternate ecology preset is selected.
    from mechanistic_mind.physical_system.ecology_presets import (
        ECOLOGY_BASELINE,
        normalize_ecology_preset,
    )

    eco = normalize_ecology_preset(getattr(config, "ecology_preset", None) or ECOLOGY_BASELINE)
    if eco != ECOLOGY_BASELINE:
        out["ecology_preset_non_baseline"] = True
    # Climate OFF under any climate-bearing package is an explicit ablation,
    # not merely a LEGACY/GENTLE default.
    from mechanistic_mind.research.climate_authority import climate_package_implies_on

    if ce is not None and not bool(getattr(ce, "enabled", False)) and climate_package_implies_on(eco):
        out["spatiotemporal_climate_ecology_disabled"] = True
    ps = getattr(config, "physical_signal", None)
    if ps is not None and str(getattr(ps, "mode", "OFF")).upper() == "EXPERIMENTAL":
        out["experimental_physical_signal"] = True
    return out


def is_canonical_tiktaalik(config) -> bool:
    return not experimental_overrides(config)


def model_metadata(config=None, *, seed: int | None = None, tick: int | None = None) -> dict[str, Any]:
    overrides = experimental_overrides(config) if config is not None else {}
    canonical = is_canonical_tiktaalik(config) if config is not None else True
    return {
        "model_family": MODEL_FAMILY,
        "model_version": MODEL_VERSION,
        "model_codename": MODEL_CODENAME,
        "display_name": display_name(),
        "runtime_version": RUNTIME_VERSION,
        "schema_version": SNAPSHOT_SCHEMA,
        "manifest_schema": MANIFEST_SCHEMA_VERSION,
        "observer_api_version": OBSERVER_API_VERSION,
        "canonical": canonical,
        "classification": "CANONICAL" if canonical else "TIKTAALIK + EXPERIMENTAL OVERRIDES",
        "experimental_overrides": overrides,
        "seed": seed,
        "tick": tick,
    }


def build_manifest(*, write_path: Path | None = None) -> dict[str, Any]:
    canonical = [k for k, v in PROMOTION.items() if v == "CANONICAL"]
    experimental = [k for k, v in PROMOTION.items() if v == "EXPERIMENTAL"]
    legacy = [k for k, v in PROMOTION.items() if v == "LEGACY"]
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "model_family": MODEL_FAMILY,
        "model_version": MODEL_VERSION,
        "model_codename": MODEL_CODENAME,
        "display_name": display_name(),
        "runtime_version": RUNTIME_VERSION,
        "snapshot_schema": SNAPSHOT_SCHEMA,
        "observer_api_version": OBSERVER_API_VERSION,
        "canonical_mechanisms": sorted(canonical),
        "experimental_mechanisms": sorted(experimental),
        "legacy_mechanisms": sorted(legacy),
        "default_runtime_config": {
            "model": "tiktaalik",
            "cognition": tiktaalik_cognition_config().to_dict(),
        },
        "bounded_memory_limits": deepcopy(BOUNDED_LIMITS),
        "design_boundaries": {
            "deep_future_action_competition": "NOT_DEMONSTRATED",
            "migration": "NOT_DEMONSTRATED",
            "learned_communication": "NOT_DEMONSTRATED",
            "predicted_context_is_read_only_when_enabled": True,
            "future_action_not_present_action": True,
            "prospection_must_not_train_itself": True,
        },
    }
    if write_path is not None:
        write_path.parent.mkdir(parents=True, exist_ok=True)
        write_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def snapshot_compatibility(snapshot: dict[str, Any]) -> dict[str, Any]:
    cfg = snapshot.get("config") or {}
    rv = str(cfg.get("runtime_version") or LEGACY_RUNTIME_VERSION)
    model = cfg.get("model") or {}
    if not model and rv in {RUNTIME_VERSION, LEGACY_RUNTIME_VERSION}:
        compat = "COMPATIBLE_LEGACY_NAME"
    elif model.get("runtime_version") == RUNTIME_VERSION or rv == RUNTIME_VERSION:
        compat = "COMPATIBLE"
    elif rv == LEGACY_RUNTIME_VERSION:
        compat = "COMPATIBLE_LEGACY_NAME"
    else:
        compat = "UNKNOWN_RUNTIME_VERSION"
    return {
        "compatible": compat in {"COMPATIBLE", "COMPATIBLE_LEGACY_NAME"},
        "classification": compat,
        "snapshot_schema": snapshot.get("schema"),
        "runtime_version": rv,
        "model": model or None,
    }
