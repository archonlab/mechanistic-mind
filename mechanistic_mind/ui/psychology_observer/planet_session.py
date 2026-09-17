"""In-process planet inspection session for Observer (MM-OBS-1).

Steps production physics unchanged. Boundary configuration is fixture/setup only
(not live UI sliders). Default boundary OFF.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
import uuid

import numpy as np

from mechanistic_mind.planet.boundary import configure_external_material_boundary
from mechanistic_mind.planet.config import PlanetConfig, default_planet_config
from mechanistic_mind.planet.dynamics import step_planet
from mechanistic_mind.planet.runtime import serialize_planet_state
from mechanistic_mind.physical_system import PhysicalSystemConfig, PhysicalSystemRuntime

from .planet_model import BoundedScalarHistory, PlanetDisplayState, display_from_planet_state, display_from_serialized


@dataclass
class PlanetInspectionSession:
    seed: int = 17
    config: PlanetConfig = field(default_factory=default_planet_config)
    history: BoundedScalarHistory = field(default_factory=BoundedScalarHistory)
    _state: Any = None
    _display: PlanetDisplayState | None = None
    runtime: PhysicalSystemRuntime | None = None

    def reset(self, *, seed: int | None = None) -> PlanetDisplayState:
        if seed is not None:
            self.seed = int(seed)
        runtime_config = PhysicalSystemConfig()
        runtime_config.planet = self.config
        self.runtime = PhysicalSystemRuntime(seed=self.seed, config=runtime_config)
        self._state = self.runtime.world
        self.history = BoundedScalarHistory()
        self._display = display_from_planet_state(self._state, self.config, seed=self.seed, source="live")
        self.history.push(self._display)
        return self._display

    @property
    def display(self) -> PlanetDisplayState | None:
        return self._display

    def step(self, n: int = 1) -> PlanetDisplayState:
        if self._state is None:
            self.reset()
        for _ in range(max(1, int(n))):
            if self.runtime is None:
                step_planet(self._state, self.config, seed=self.seed)
            else:
                self.runtime.step()
        self._display = display_from_planet_state(self._state, self.config, seed=self.seed, source="live")
        self.history.push(self._display)
        return self._display

    def apply_boundary_fixture(
        self,
        *,
        enabled: bool,
        contact_mask: np.ndarray | None = None,
        K: float | None = None,
        M_ext: list[float] | None = None,
    ) -> PlanetDisplayState:
        """Test/setup only — not a live Observer control surface."""
        if self._state is None:
            self.reset()
        if not enabled:
            # re-init OFF cleanly
            self._state.external_material_boundary.enabled = False
            self._state.external_material_boundary.contact_mask = None
            self._state.external_material_boundary.K = None
            self._state.external_material_boundary.M_ext = None
        else:
            configure_external_material_boundary(
                self._state,
                enabled=True,
                contact_mask=contact_mask,
                K=K,
                M_ext=M_ext,
            )
        self._display = display_from_planet_state(self._state, self.config, seed=self.seed, source="live")
        return self._display

    def snapshot_payload(self) -> dict[str, Any]:
        """Backward-compatible WORLD export for Analyzer and saved views."""
        if self._state is None:
            self.reset()
        return serialize_planet_state(self._state, self.config)

    def canonical_snapshot_payload(self) -> dict[str, Any]:
        if self.runtime is None:
            self.reset()
        return self.runtime.snapshot()

    def save_run(
        self,
        results_root: Path,
        *,
        stop_reason: str,
        boundary_fixture_id: str,
    ) -> Path | None:
        """Persist the current physical run before its in-memory state is discarded."""
        if self._display is None or self._display.tick <= 0:
            return None

        stopped_at = datetime.now(timezone.utc)
        run_id = (
            f"physical-{stopped_at.strftime('%Y%m%dT%H%M%S.%fZ')}"
            f"-{uuid.uuid4().hex[:8]}"
        )
        run_dir = Path(results_root) / "current_physical_world" / run_id
        run_dir.mkdir(parents=True, exist_ok=False)

        snapshot = self.canonical_snapshot_payload()
        manifest = {
            "schema": "mm.psychology_observer.physical_run.v1",
            "run_id": run_id,
            "stopped_at": stopped_at.isoformat(),
            "stop_reason": str(stop_reason),
            "seed": int(self.seed),
            "final_tick": int(self._display.tick),
            "boundary_fixture_id": str(boundary_fixture_id),
            "snapshot": "physical_system_snapshot.json",
        }
        (run_dir / "physical_system_snapshot.json").write_text(
            json.dumps(snapshot, ensure_ascii=False, sort_keys=True, indent=2),
            encoding="utf-8",
        )
        (run_dir / "run.json").write_text(
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2),
            encoding="utf-8",
        )
        return run_dir

    def load_snapshot(self, payload: dict[str, Any]) -> PlanetDisplayState:
        if payload.get("schema") in {"mm.physical_system.snapshot.v1", "mm.physical_system.snapshot.v2"}:
            self.runtime = PhysicalSystemRuntime.restore(payload)
            self._state = self.runtime.world
            self.config = self.runtime.config.planet
            self._display = display_from_planet_state(
                self._state, self.config, seed=self.seed, source="snapshot"
            )
            self.history.push(self._display)
            return self._display
        self._display = display_from_serialized(payload, source="snapshot")
        # also materialize state for further stepping via restore
        from mechanistic_mind.planet.runtime import restore_planet_state
        self._state, self.config = restore_planet_state(payload)
        self.runtime = None  # historical WORLD-only snapshots remain inspection-only
        self.history.push(self._display)
        return self._display
