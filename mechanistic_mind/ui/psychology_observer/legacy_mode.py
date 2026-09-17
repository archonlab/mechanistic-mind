"""MM-CONFIG-1.1 — explicit Legacy Experiment mode (Observer ownership).

Not an experiment registry entry. Current MM ≠ historical 4.xx workflow.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


LEGACY_MODE_OFF_STATUS = "NO LEGACY EXPERIMENT ACTIVE"
LEGACY_MODE_ON_STATUS = "LEGACY EXPERIMENTS ENABLED"


@dataclass(frozen=True, slots=True)
class LegacyModeSnapshot:
    enabled: bool
    selected_preset: str
    logical_active_experiment: str | None
    start_run_available: bool
    can_disable: bool


def logical_active_legacy_experiment(*, enabled: bool, selected_preset: str) -> str | None:
    """Preset StringVar is UI memory only; logically active iff mode ON and non-empty."""
    if not enabled:
        return None
    name = str(selected_preset or "").strip()
    return name or None


def legacy_start_run_available(*, enabled: bool, selected_preset: str) -> bool:
    return logical_active_legacy_experiment(enabled=enabled, selected_preset=selected_preset) is not None


def can_disable_legacy_mode(*, controller_is_active: bool) -> bool:
    """Do not orphan a running historical process."""
    return not bool(controller_is_active)


def snapshot(
    *,
    enabled: bool,
    selected_preset: str,
    controller_is_active: bool,
) -> LegacyModeSnapshot:
    active = logical_active_legacy_experiment(enabled=enabled, selected_preset=selected_preset)
    return LegacyModeSnapshot(
        enabled=bool(enabled),
        selected_preset=str(selected_preset or ""),
        logical_active_experiment=active,
        start_run_available=legacy_start_run_available(
            enabled=enabled, selected_preset=selected_preset
        )
        and not controller_is_active,
        can_disable=can_disable_legacy_mode(controller_is_active=controller_is_active),
    )


def headless_legacy_contract() -> dict[str, Any]:
    return {
        "legacy_mode_default": False,
        "neutral_status": LEGACY_MODE_OFF_STATUS,
        "fake_registry_none_experiment": False,
        "start_run_requires_legacy_mode": True,
        "physical_world_independent": True,
        "analyzer_independent": True,
    }
