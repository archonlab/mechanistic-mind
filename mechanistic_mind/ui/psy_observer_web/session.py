"""In-process Current MM session for Psy Observer Web.

Owns the run loop. Simulation tick rate is independent of UI render rate.

BETA2-OBS-02: Play advances simulation without waiting for Observer frame
construction. A dedicated capture worker builds frames from a coherent
step-lock snapshot (latest-request-wins). RUNNING publishes compact/bounded
frames; PAUSED/INSPECT/step use full detail.
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from datetime import datetime, timezone
from collections import deque
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
import gc

from mechanistic_mind.model.tiktaalik import display_name, tiktaalik_config
from mechanistic_mind.physical_system import (
    CognitionConfig,
    PhysicalSystemConfig,
    PhysicalSystemRuntime,
    TwoAgentRuntime,
)
from mechanistic_mind.physical_body.config import PhysicalBodyConfig, default_physical_body2_config
from mechanistic_mind.internal_medium.config import InternalMediumConfig, default_internal_medium_config
from mechanistic_mind.planet.config import PlanetConfig, default_planet_config

from .run_finalize import default_results_root, new_run_id, write_finalized_run
from .scientific_history import (
    ScientificHistoryWriter,
    live_scientific_dir,
    load_evidence_package,
)

from mechanistic_mind.scientific_v3.writer import ScientificV3Writer
from .subscriptions import ObserverInterest, PRESETS, PRODUCT_GRAPHS, PRODUCT_GEOMETRY, PRODUCT_SIGNALS, PRODUCT_EXPERIMENTER, PRODUCT_COGNITION, PRODUCT_DIAGNOSTICS, PRODUCT_SMC, PRODUCT_HISTORICAL_SENSORIMOTOR, PRODUCT_SIGNAL_SENSORIMOTOR, stub_deferred
from .serialize import (
    compact_history_from_runtime,
    compact_timeline_event,
    live_frame,
    collect_observer_events,
    collect_observer_events_for_tick,
)
from .live_bounds import (
    LIVE_EVENT_EMBED,
    LIVE_EVENT_EMBED_FULL,
    LIVE_EVENT_RING_MAX,
    LIVE_TELEMETRY_EMBED,
    LIVE_TRAJECTORY_EMBED,
    LIVE_TELEMETRY_RING_MIN,
    LIVE_TRAJECTORY_RING_MIN,
    LIVE_TRAJECTORY_RING_MULT,
    LIVE_WORLD_INTERVENTION_EMBED,
    LIVE_WORLD_INTERVENTION_SESSION_MAX,
    SCI_APPEND_EVENT_TAIL,
    live_bounds_snapshot,
    live_refresh_elements_touched,
    tail_list,
)


# Wall-clock period for one scientific tick at 1× (human-observable cadence).
# Higher multipliers shorten this period; MAX uses no intentional sleep.
# This is simulation acceleration only — dt / physics / cognition unchanged.
BASE_TICK_PERIOD_1X = 0.025  # 40 scientific ticks/sec target at 1× when CPU allows
MAX_SPEED = 50.0
# Aliases — LIVE display caps (not scientific / agent memory).
EVENT_RING_MAX = LIVE_EVENT_RING_MAX
TRAJECTORY_EMBED_TAIL = LIVE_TRAJECTORY_EMBED
TELEMETRY_EMBED_TAIL = LIVE_TELEMETRY_EMBED
# Full public WORLD frames are latest-wins. Compact per-tick history lives on `_timeline`.
FULL_PUBLIC_FRAME_RETAIN = 1


def tick_sleep_seconds(speed: float) -> float:
    """Intentional wall-clock wait after each scientific tick (0 for MAX).

    Derived from BASE_TICK_PERIOD_1X / speed (wall-clock only; dt unchanged).
    Floor speed 0.01× → ~2.5 s/tick target (~0.4 t/s) when compute allows.
    """
    sp = float(speed)
    if sp >= MAX_SPEED - 0.5:
        return 0.0
    return max(0.0, BASE_TICK_PERIOD_1X / max(0.01, sp))


def observer_capture_period(speed: float, ui_hz: float) -> float:
    """Wall-clock period between full observer visual frames."""
    hz = max(1e-3, float(ui_hz))
    base = 1.0 / hz
    sp = float(speed)
    if sp <= 1.0:
        return base
    # High speed: keep ~ui_hz visual updates/sec (wall clock), not per-tick.
    # Slightly lower floor so MAX does not starve the browser.
    return max(1.0 / 20.0, base)


@dataclass
class SessionConfig:
    seed: int = 17
    target_tick: int | None = None
    buffer_capacity: int = 512
    ui_hz: float = 10.0  # max live push rate (observer sample Hz)
    steps_per_loop: int = 1
    speed: float = 1.0  # relative sim steps aggressiveness (wall-clock only)
    cognition_enabled: bool = True
    results_root: Path | None = None
    # Execution / presentation policy — NOT a different scientific world.
    # LIVE: interactive observation (default)
    # FAST: accelerated sim + moderate observer sample rate
    # MAX: CPU-limited sim + low observer sample rate
    # HEADLESS: no live presentation capture; scientific ticks unchanged
    execution_mode: str = "LIVE"
    # Evidence capture policy — orthogonal to execution_mode.
    # FULL_SCIENTIFIC: existing ScientificHistoryWriter (V2 tiered)
    # SEARCH_COMPACT: bounded metrics + rolling candidate windows only
    evidence_mode: str = "FULL_SCIENTIFIC"
    search_compact_pre_window: int = 32
    search_compact_post_window: int = 32
    search_compact_max_candidates: int = 8
    search_compact_trigger_threshold: int = 8
    # Persistence infrastructure only. 0 = OFF.
    checkpoint_every_ticks: int = 0
    # Beta 3.1 canonical default: PE sealed-history disk eviction ON.
    pe_cold_history_eviction: bool = True


# Presets map presentation policy → wall-clock speed + observer Hz.
# Scientific dt / cognition / physics are NEVER changed by these presets.
EXECUTION_MODE_PRESETS: dict[str, dict[str, float | bool]] = {
    "LIVE": {"speed": 1.0, "ui_hz": 10.0, "capture": True},
    "FAST": {"speed": 10.0, "ui_hz": 5.0, "capture": True},
    "MAX": {"speed": MAX_SPEED, "ui_hz": 2.0, "capture": True},
    "HEADLESS": {"speed": MAX_SPEED, "ui_hz": 1.0, "capture": False},
}


@dataclass
class ObserverSession:
    config: SessionConfig = field(default_factory=SessionConfig)
    runtime: PhysicalSystemRuntime = field(init=False)
    status: str = "PAUSED"  # PAUSED | RUNNING | STOPPED | FINALIZING | SAVE_FAILED
    mode: str = "LIVE"  # LIVE | REPLAY | INSPECT
    inspect_tick: int | None = None
    _buffer: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=FULL_PUBLIC_FRAME_RETAIN))
    _timeline: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=4096))
    _lock: threading.RLock = field(default_factory=threading.RLock)
    _step_lock: threading.Lock = field(default_factory=threading.Lock)
    _published: dict[str, Any] | None = None
    _prev_body: dict[str, Any] | None = None
    _prev_bodies: dict[str, dict[str, Any]] = field(default_factory=dict)
    # GEO-02: scientific-tick geometry prev poses (independent of Observer capture cadence)
    _geo_prev_bodies: dict[str, dict[str, Any]] = field(default_factory=dict)
    _geo_accum: Any = None
    _geo_agent_filter: str = "ALL"
    _sig_accum: Any = None
    _signal_specimen_library: Any = None
    _uncontrolled_live_replays: list = field(default_factory=list)
    _experimenter: Any = None
    _experimenter_intervention_ever: bool = False
    _action_realization: Any = None
    _work_ecology: Any = None
    _locomotor_economy: Any = None
    # Cached GEO overlay built OUTSIDE `_step_lock` (BETA2-OBS-04)
    _geo_overlay_published: dict[str, Any] | None = None
    _geo_empirical_version_sent: int = -1
    _geo_empirical_last_publish_mono: float = 0.0
    _geo_static_version: int = 1
    # LIVE empirical only vs separately loaded SAVED run overlay (never silent mix).
    _geo_overlay_source: str = "LIVE"  # LIVE | SAVED
    _geo_saved_overlay: dict[str, Any] | None = None
    _geo_saved_provenance: dict[str, Any] | None = None
    # BETA2-OBS-04: allow matrix benchmarks to disable LIVE interpreters
    _geo_live_enabled: bool = True
    _sig_live_enabled: bool = True
    _subscribers: list[Callable[[dict[str, Any]], None]] = field(default_factory=list)
    _eager_subscribers: list[Callable[[dict[str, Any]], None]] = field(default_factory=list)
    _publish_demand_fn: Callable[[], bool] | None = None
    _heartbeat_subscribers: list[Callable[[dict[str, Any]], None]] = field(default_factory=list)
    _stat_live_frame_builds: int = 0
    _stat_json_dumps_publish: int = 0
    _stat_json_publish_bytes: int = 0
    _published_ws_text: str | None = None
    _last_push: float = 0.0
    _thread: threading.Thread | None = None
    _heartbeat_thread: threading.Thread | None = None
    _heartbeat_stop: bool = False
    _stop_flag: bool = False
    # LIVE mechanism / vision apply at tick boundaries (never mid-tick).
    _live_apply_queue: deque[dict[str, Any]] = field(default_factory=deque)
    _live_apply_lock: threading.Lock = field(default_factory=threading.Lock)
    _live_apply_seq: int = 0
    _pending_live_apply: dict[str, Any] | None = None
    _tick_in_progress: bool = False
    _tick_started_mono: float = 0.0
    _last_tick_wall_ms: float = 0.0
    _last_tick_completed_mono: float = 0.0
    _runtime_generation: int = 0
    _frame_seq: int = 0
    _trajectory: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=2048))
    _telemetry: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=2048))
    _historical_compat: dict[str, Any] | None = None
    _run_started_at: str | None = None
    _termination_reason: str | None = None
    _last_finalize: dict[str, Any] | None = None
    _finalize_key: tuple[Any, ...] | None = None
    _active_run_id: str | None = None
    _finalize_lock: threading.Lock = field(default_factory=threading.Lock)
    _save_job: dict[str, Any] | None = None
    _save_job_thread: threading.Thread | None = None
    _event_ring: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=EVENT_RING_MAX))
    _event_keys: set[tuple[Any, ...]] = field(default_factory=set)
    # Beta 2: LIVE world/mechanism interventions for current runtime generation only.
    # Recent session interventions for LIVE embed + API list (bounded).
    # Full provenance for Analyzer comes from scientific_events.jsonl.
    _world_interventions: deque = field(
        default_factory=lambda: deque(maxlen=LIVE_WORLD_INTERVENTION_SESSION_MAX)
    )
    _world_intervention_fp0: str | None = None
    # Configuration integrity (mechanism authority + preflight + run-start manifest).
    _resolved_mechanism_config: Any = None
    _preflight_result: dict[str, Any] | None = None
    _runtime_mechanism_manifest: dict[str, Any] | None = None
    _canonical_config: dict[str, Any] | None = None
    _canonical_requested: dict[str, Any] | None = None
    _applied_receipt: dict[str, Any] | None = None
    _visual_dropped: int = 0
    _observer_interest: ObserverInterest = field(default_factory=ObserverInterest)
    _psc_shadow_replay_count: int = 0
    _perf_window_start: float = 0.0
    _perf_ticks: int = 0
    _perf_captures: int = 0
    _perf_sim_tps: float = 0.0
    _perf_obs_fps: float = 0.0
    _last_frame_tick: int | None = None
    _sci_writer: ScientificHistoryWriter | None = None
    _v3_writer: ScientificV3Writer | None = field(default=None)
    _v3_last_error: str | None = field(default=None)
    _compact_writer: Any = None
    _sci_live_dir: Path | None = None
    _checkpoint_status: dict[str, Any] = field(default_factory=lambda: {
        "state": "OFF",
        "last_tick": None,
        "next_tick": None,
        "last_error": None,
        "last_wall_s": None,
        "last_mb": None,
        "recoverable_through": None,
    })
    _checkpoint_resume_meta: dict[str, Any] | None = None
    # Async Observer capture (BETA2-OBS-02) — never block SIM on live_frame.
    _capture_thread: threading.Thread | None = None
    _capture_stop: bool = False
    _capture_cond: threading.Condition = field(default_factory=threading.Condition)
    _capture_pending: dict[str, Any] | None = None
    _capture_inflight: bool = False
    _capture_queue_drops: int = 0
    _capture_test_delay_s: float = 0.0  # test hook: sleep before taking step_lock
    _published_json: str | None = None
    _observer_lag_ticks: int = 0
    # Capture scheduling / diagnostics (BETA2-OBS-02.1)
    _capture_wants_lock: bool = False
    _capture_coop_yield: bool = True  # SIM yields step_lock to capture worker
    _capture_timing_enabled: bool = True
    _capture_timings: deque[dict[str, Any]] = field(
        default_factory=lambda: deque(maxlen=2048)
    )
    _sim_lock_waits_ms: deque[float] = field(default_factory=lambda: deque(maxlen=4096))
    _last_publish_mono: float = 0.0
    _publish_intervals_ms: deque[float] = field(default_factory=lambda: deque(maxlen=2048))
    _capture_detail_counts: dict[str, int] = field(
        default_factory=lambda: {"compact": 0, "full": 0, "other": 0}
    )
    # Tiktaalik Eye — Observer diagnostic only (never scientific capture).
    _eye_rate: str = "OFF"
    _eye_geometry_debug: bool = False
    _eye_force_snapshot: bool = False
    _eye_last_payload: dict[str, Any] | None = None
    _eye_prev_visual: dict[str, dict[str, float]] = field(default_factory=dict)
    _eye_last_wall: float = 0.0
    _eye_last_tick: int = -1
    _eye_update_count: int = 0
    _eye_last_build_ms: float = 0.0
    _eye_fpv_visible: bool = False
    _eye_prev_fpv: dict[str, dict[str, float]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._perf_window_start = time.monotonic()
        self.reset(seed=self.config.seed)
        self._ensure_capture_worker()

    def mechanism_integrity_status(self) -> dict[str, Any]:
        """CONFIGURED / RUNTIME / AVAILABLE compact status for Observer."""
        from mechanistic_mind.physical_system.experiment_canonical import canonical_fingerprint

        resolved = self._resolved_mechanism_config
        pf = self._preflight_result
        manifest = self._runtime_mechanism_manifest
        cfg_fp = canonical_fingerprint(self._canonical_config) if self._canonical_config else None
        return {
            "preflight": pf,
            "resolved": resolved.to_dict() if resolved is not None and hasattr(resolved, "to_dict") else resolved,
            "manifest_present": manifest is not None,
            "manifest_fingerprint": (manifest or {}).get("resolved_fingerprint"),
            "manifest_checksum": (manifest or {}).get("checksum"),
            "ready": bool(pf and pf.get("status") == "READY"),
            "configured_fingerprint": cfg_fp,
            "requested_fingerprint": (self._applied_receipt or {}).get("requested", {}).get("fingerprint"),
            "runtime_fingerprint": (self._applied_receipt or {}).get("runtime", {}).get("fingerprint"),
            "applied_configuration": self._applied_receipt,
        }

    def mechanisms_warm_state(self) -> dict[str, Any]:
        """WARM enabled flags + integrity. Does not include COLD catalog metadata."""
        rt = getattr(self, "runtime", None)
        if rt is None:
            return {"error": "no runtime", "catalog_included": False, "mechanisms": []}
        snap = rt.mechanisms()
        items = []
        for m in snap.get("mechanisms") or []:
            if not isinstance(m, dict):
                continue
            items.append({
                "id": m.get("id"),
                "enabled": bool(m.get("enabled")),
                "ablatable": bool(m.get("ablatable", True)),
            })
        integrity = self.mechanism_integrity_status()
        pf = integrity.get("preflight") if isinstance(integrity.get("preflight"), dict) else {}
        slim_integrity = {
            "ready": bool(integrity.get("ready")),
            "manifest_present": bool(integrity.get("manifest_present")),
            "manifest_fingerprint": integrity.get("manifest_fingerprint"),
            "manifest_checksum": integrity.get("manifest_checksum"),
            "preflight_status": pf.get("status") if isinstance(pf, dict) else None,
        }
        return {
            "schema": "mm.observer.mechanism_state.v1",
            "catalog_included": False,
            "runtime_generation": int(self._runtime_generation),
            "tick": int(getattr(rt, "tick", 0) or 0),
            "model": "MM 1.0 — Tiktaalik",
            "runtime_version": snap.get("runtime_version"),
            "mechanisms": items,
            "enabled": snap.get("enabled"),
            "disabled": snap.get("disabled"),
            "mechanism_integrity": slim_integrity,
            "preflight_status": slim_integrity.get("preflight_status"),
            "psc_motor_resolution": str(
                getattr(getattr(getattr(rt, "config", None), "cognition", None), "psc_motor_resolution", None)
                or "LOCO_FACTORIZED"
            ),
        }

    def _clear_integrity_locked(self) -> None:
        self._resolved_mechanism_config = None
        self._preflight_result = None
        self._runtime_mechanism_manifest = None

    def _bind_and_preflight_locked(
        self,
        *,
        requested_mechanisms: dict[str, Any] | None,
        vision_radius: int | None = None,
        source_hint: str = "NEW_EXPERIMENT",
        apply_fresh_defaults: bool = True,
    ) -> dict[str, Any]:
        """Apply resolved mechanisms to current runtime and verify before scientific ticks."""
        from mechanistic_mind.physical_system.mechanism_configuration import (
            apply_resolved_to_runtime,
            build_runtime_manifest,
            resolve_mechanism_config,
            run_preflight,
        )

        resolved = resolve_mechanism_config(
            requested_mechanisms,
            vision_radius=vision_radius,
            source_hint=source_hint,
            apply_fresh_defaults=apply_fresh_defaults,
        )
        apply_info = apply_resolved_to_runtime(self.runtime, resolved)
        # Second bind pass if first had errors (e.g. missing config objects).
        if apply_info.get("errors"):
            apply_info = apply_resolved_to_runtime(self.runtime, resolved)
        preflight = run_preflight(self.runtime, resolved)
        # One repair+reverify cycle before t=1 when mismatches exist.
        if preflight.status != "READY":
            apply_resolved_to_runtime(self.runtime, resolved)
            preflight = run_preflight(self.runtime, resolved)
        self._resolved_mechanism_config = resolved
        self._preflight_result = preflight.to_dict()
        if preflight.status == "READY":
            self._runtime_mechanism_manifest = build_runtime_manifest(
                runtime=self.runtime,
                resolved=resolved,
                preflight=preflight,
                run_id=self._active_run_id,
                generation=self._runtime_generation,
            )
        else:
            self._runtime_mechanism_manifest = None
        return {
            "resolved": resolved.to_dict(),
            "preflight": self._preflight_result,
            "apply": apply_info,
            "manifest": self._runtime_mechanism_manifest,
        }

    def _require_preflight_ready(self, operation: str, before: dict[str, Any], request: dict[str, Any]) -> dict[str, Any] | None:
        """Return a rejected control receipt if preflight is not READY; else None."""
        pf = self._preflight_result
        if pf is not None and pf.get("status") == "READY":
            return None
        # Attempt bind with stored/fresh defaults if never run.
        if pf is None:
            with self._step_lock:
                with self._lock:
                    self._bind_and_preflight_locked(
                        requested_mechanisms=None,
                        source_hint="NEW_EXPERIMENT",
                        apply_fresh_defaults=True,
                    )
            pf = self._preflight_result
        if pf is not None and pf.get("status") == "READY":
            return None
        reason = "PREFLIGHT_FAILED"
        mismatches = (pf or {}).get("mismatches") or []
        out = self._with_receipt(
            self._clone_published(),
            operation,
            {**request, "preflight": pf},
            before,
            accepted=False,
            reason=reason,
        )
        out["preflight"] = pf
        out["mismatches"] = mismatches
        return out

    def reset(self, *, seed: int | None = None, cognition_enabled: bool | None = None) -> dict[str, Any]:
        prior_finalize = None
        if getattr(self, "runtime", None) is not None and int(self.runtime.tick) > 0 and self._finalize_key is None:
            # Discarding an unsaved active run: persist under RESET when possible.
            self._halt_runner("FINALIZING")
            prior_finalize = self.finalize_run(reason="RESET")
        self._halt_runner("PAUSED")
        with self._step_lock:
            with self._lock:
                before = self._control_state()
                if seed is not None:
                    self.config.seed = int(seed)
                if cognition_enabled is not None:
                    self.config.cognition_enabled = bool(cognition_enabled)
                cfg = tiktaalik_config()
                cfg.cognition.cognition_enabled = bool(self.config.cognition_enabled)
                self.runtime = PhysicalSystemRuntime(seed=self.config.seed, config=cfg)
                self._runtime_generation += 1
                self._clear_integrity_locked()
                # Fresh reset → full normal organism defaults (climate OFF).
                integrity = self._bind_and_preflight_locked(
                    requested_mechanisms={"cognition": bool(self.config.cognition_enabled)},
                    source_hint="NEW_EXPERIMENT",
                    apply_fresh_defaults=True,
                )
                self.status = "PAUSED"
                self.mode = "LIVE"
                self.inspect_tick = None
                self._buffer = deque(maxlen=FULL_PUBLIC_FRAME_RETAIN)
                self._timeline = deque(maxlen=max(1024, int(self.config.buffer_capacity) * 8))
                self._prev_body = None
                self._prev_bodies = {}
                self._geo_prev_bodies = {}
                self._reset_geo_accum_locked()
                self._reset_sig_accum_locked()
                self._experimenter_intervention_ever = False
                self._reset_experimenter_locked()
                self._reset_action_realization_locked()
                self._reset_work_ecology_locked()
                self._reset_locomotor_economy_locked()
                self._trajectory = deque(maxlen=max(LIVE_TRAJECTORY_RING_MIN, int(self.config.buffer_capacity) * LIVE_TRAJECTORY_RING_MULT))
                self._telemetry = deque(maxlen=max(LIVE_TELEMETRY_RING_MIN, int(self.config.buffer_capacity) * LIVE_TRAJECTORY_RING_MULT))
                self._historical_compat = None
                self._published = None
                self._published_json = None
                self._published_ws_text = None
                self._run_started_at = None
                self._termination_reason = "RESET"
                self._last_finalize = prior_finalize
                self._finalize_key = None
                self._active_run_id = None
                self._close_scientific_locked()
                self._event_ring = deque(maxlen=EVENT_RING_MAX)
                self._event_keys = set()
                self._clear_world_interventions_locked()
                self._visual_dropped = 0
                self._perf_window_start = time.monotonic()
                self._perf_ticks = 0
                self._perf_captures = 0
                self._perf_sim_tps = 0.0
                self._perf_obs_fps = 0.0
                self._last_frame_tick = None
                self._published_json = None
                self._observer_lag_ticks = 0
                self._eye_last_payload = None
                self._eye_prev_visual = {}
                self._eye_last_wall = 0.0
                self._eye_last_tick = -1
                self._eye_force_snapshot = False
                self._eye_fpv_visible = False
                self._eye_prev_fpv = {}
                self._invalidate_pending_captures_locked()
                self._record_motion_locked()
                self._apply_pe_cold_eviction_locked()
                frame = self._capture_locked(detail="full")
                out = self._with_receipt(
                    frame, "RESET", {"seed": seed, "cognition_enabled": cognition_enabled},
                    before, requires_reset=True,
                )
                out["preflight"] = integrity.get("preflight")
                out["mechanism_result"] = self.runtime.mechanisms()
                out["mechanism_integrity"] = self.mechanism_integrity_status()
                from mechanistic_mind.physical_system.experiment_canonical import canonical_from_runtime

                self._canonical_config = canonical_from_runtime(self.runtime)
                self._canonical_config["pe_cold_history_eviction"] = bool(self.config.pe_cold_history_eviction)
                self._canonical_requested = deepcopy(self._canonical_config)
                self._applied_receipt = self.applied_configuration_receipt()
                out["applied_configuration"] = self._applied_receipt
                if prior_finalize is not None:
                    out["finalize"] = prior_finalize
                return out

    def _invalidate_pending_captures_locked(self) -> None:
        """Drop any async capture belonging to a prior run/generation."""
        with self._capture_cond:
            self._capture_pending = None

    def subscribe(self, fn: Callable[[dict[str, Any]], None], *, eager: bool = True) -> None:
        with self._lock:
            self._subscribers.append(fn)
            if eager and fn not in self._eager_subscribers:
                self._eager_subscribers.append(fn)

    def unsubscribe(self, fn: Callable[[dict[str, Any]], None]) -> None:
        with self._lock:
            if fn in self._subscribers:
                self._subscribers.remove(fn)
            if fn in self._eager_subscribers:
                self._eager_subscribers.remove(fn)

    def set_publish_demand(self, fn: Callable[[], bool] | None) -> None:
        """Optional extra demand (e.g. websocket client count). Observer-only."""
        self._publish_demand_fn = fn

    def publication_wanted(self) -> bool:
        """True when a live public WORLD frame should be built/serialized."""
        if str(self.config.execution_mode or "LIVE").upper() == "HEADLESS":
            return False
        if self._eager_subscribers:
            return True
        if self._publish_demand_fn is not None:
            try:
                return bool(self._publish_demand_fn())
            except Exception:
                return False
        return False

    def subscribe_heartbeat(self, fn: Callable[[dict[str, Any]], None]) -> None:
        with self._lock:
            self._heartbeat_subscribers.append(fn)

    def unsubscribe_heartbeat(self, fn: Callable[[dict[str, Any]], None]) -> None:
        with self._lock:
            if fn in self._heartbeat_subscribers:
                self._heartbeat_subscribers.remove(fn)

    def runtime_progress(self) -> dict[str, Any]:
        """Cheap RUNNING progress snapshot — no frame build, no step_lock."""
        pending = None
        with self._live_apply_lock:
            if self._pending_live_apply is not None:
                pending = dict(self._pending_live_apply)
            elif self._live_apply_queue:
                pending = dict(self._live_apply_queue[0])
                pending["queued_n"] = len(self._live_apply_queue)
        in_prog = bool(self._tick_in_progress)
        started = float(self._tick_started_mono or 0.0)
        elapsed_ms = (time.monotonic() - started) * 1000.0 if in_prog and started else 0.0
        detail = "IDLE"
        if self.status == "RUNNING":
            if in_prog:
                detail = "COMPUTING_TICK"
            elif pending:
                detail = "PENDING_LIVE_APPLY"
            else:
                detail = "BETWEEN_TICKS"
        exec_mode = str(self.config.execution_mode or "LIVE").upper()
        sim_tick = int(getattr(self.runtime, "tick", 0) or 0)
        frame_tick = int(self._last_frame_tick) if self._last_frame_tick is not None else sim_tick
        return {
            "status": self.status,
            "status_detail": detail,
            "tick": sim_tick,
            "tick_in_progress": in_prog,
            "tick_elapsed_ms": round(elapsed_ms, 1) if in_prog else None,
            "last_tick_wall_ms": round(float(self._last_tick_wall_ms), 2),
            "last_tick_completed_mono": float(self._last_tick_completed_mono or 0.0),
            "sim_ticks_per_sec": round(float(self._perf_sim_tps), 1),
            "observer_fps": round(float(self._perf_obs_fps), 1),
            "pending_live_apply": pending,
            "heartbeat_mono": time.monotonic(),
            "execution_mode": exec_mode,
            "display_frozen": bool(exec_mode == "HEADLESS" and self.status == "RUNNING"),
            "display_tick": frame_tick,
        }

    def _ensure_heartbeat_worker(self) -> None:
        if self._heartbeat_thread is not None and self._heartbeat_thread.is_alive():
            return
        self._heartbeat_stop = False
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_worker_loop,
            name="psy-observer-heartbeat",
            daemon=True,
        )
        self._heartbeat_thread.start()

    def _heartbeat_worker_loop(self) -> None:
        """Push lightweight progress so UI does not mark COMPUTING ticks as STALE."""
        while not self._heartbeat_stop:
            time.sleep(0.4)
            if self.status != "RUNNING":
                continue
            hb = self.runtime_progress()
            for fn in list(self._heartbeat_subscribers):
                try:
                    fn(hb)
                except Exception:
                    pass

    def _enqueue_live_apply(self, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._live_apply_lock:
            self._live_apply_seq += 1
            req = {
                "request_id": f"live-apply-{self._live_apply_seq}",
                "kind": kind,
                "queued_at_mono": time.monotonic(),
                "queued_at_tick": int(getattr(self.runtime, "tick", 0) or 0),
                "status": "WAITING_FOR_TICK_BOUNDARY",
                **payload,
            }
            self._live_apply_queue.append(req)
            self._pending_live_apply = dict(req)
            return dict(req)

    def _drain_live_apply_queue_unlocked(self) -> list[dict[str, Any]]:
        """Apply queued LIVE interventions at a safe tick boundary (caller holds step_lock)."""
        applied: list[dict[str, Any]] = []
        while True:
            with self._live_apply_lock:
                if not self._live_apply_queue:
                    self._pending_live_apply = None
                    break
                req = self._live_apply_queue.popleft()
            kind = str(req.get("kind") or "")
            try:
                if kind == "mechanism":
                    out = self._apply_mechanism_now_unlocked(
                        str(req["mechanism_id"]), bool(req["enabled"]),
                    )
                elif kind == "vision_radius":
                    out = self._apply_vision_radius_now_unlocked(int(req["radius"]))
                elif kind == "visual_surface_discrimination":
                    out = self._apply_surface_discrimination_now_unlocked(str(req["mode"]))
                elif kind == "optical_mapping":
                    out = self._apply_optical_mapping_now_unlocked(str(req["mode"]))
                elif kind == "spatial_vision":
                    out = self._apply_spatial_vision_now_unlocked(str(req["mode"]))
                elif kind == "psc_off_ticks":
                    out = self._apply_psc_off_ticks_now_unlocked(req.get("value"))
                else:
                    out = {
                        "accepted": False,
                        "error": f"unknown live apply kind {kind}",
                        "control_receipt": {"accepted": False},
                    }
            except Exception as exc:
                out = {
                    "accepted": False,
                    "error": f"LIVE_APPLY_FAILED:{exc}",
                    "control_receipt": {"accepted": False, "reason": str(exc)},
                }
            ok = bool((out.get("control_receipt") or {}).get("accepted", out.get("accepted", True)))
            done = {
                **{k: v for k, v in req.items() if k != "result"},
                "status": "APPLIED" if ok else "REJECTED",
                "applied_at_tick": int(getattr(self.runtime, "tick", 0) or 0),
                "applied_at_mono": time.monotonic(),
            }
            applied.append(done)
            with self._live_apply_lock:
                self._pending_live_apply = None
        return applied

    def _event_key(self, ev: dict[str, Any]) -> tuple[Any, ...]:
        evidence = ev.get("evidence") if isinstance(ev.get("evidence"), dict) else {}
        return (
            int(ev.get("tick") or -1),
            str(ev.get("type") or ev.get("kind") or ""),
            str(ev.get("agent_id") or ev.get("actor_agent_id") or ""),
            str(ev.get("emitter_agent_id") or evidence.get("emitter_agent_id") or ""),
            str(ev.get("receiver_agent_id") or evidence.get("receiver_agent_id") or ""),
            str(evidence.get("selected_action") or evidence.get("action") or ""),
            str(evidence.get("emission_id") or evidence.get("receipt_id") or ""),
        )

    def _live_presentation_bookkeeping_enabled(self) -> bool:
        """LIVE presentation rings/forensic accumulators — not required for science.

        HEADLESS must not pay per-tick for Observer-only trajectory/telemetry rings
        or action_realization / work_ecology / locomotor_economy accumulators.
        Scientific V2 builds those fields from the slot at write time.
        """
        return str(self.config.execution_mode or "LIVE").upper() != "HEADLESS"

    def _accumulate_events_locked(self) -> None:
        """Drain structured events every scientific tick into a bounded observer ring."""
        # Prefer current-tick emissions (O(buffer) filter) over re-sorting a wide window.
        tick_now = int(self.runtime.tick)
        fresh = collect_observer_events_for_tick(self.runtime, tick=tick_now, limit=120)
        newly: list[dict[str, Any]] = []
        for ev in fresh:
            key = self._event_key(ev)
            if key in self._event_keys:
                continue
            self._event_keys.add(key)
            self._event_ring.append(ev)
            newly.append(ev)
        if newly and self._sig_live_enabled and self._live_presentation_bookkeeping_enabled():
            self._observe_signal_events_locked(newly)
        if len(self._event_keys) > EVENT_RING_MAX * 2:
            self._event_keys = {self._event_key(e) for e in self._event_ring}

    def _record_motion_locked(self) -> None:
        if not self._live_presentation_bookkeeping_enabled():
            # HEADLESS: skip LIVE rings + forensic observers. Geometry already gated.
            return
        self._trajectory.append({
            "tick": int(self.runtime.tick),
            "x": float(self.runtime.body.x),
            "y": float(self.runtime.body.y),
        })
        # GEO-02: also record all-agent trajectory markers on selected body path only —
        # multi-agent paths come from geometry events overlay.
        self._observe_geometry_tick_locked()
        self._observe_action_realization_locked()
        self._observe_work_ecology_locked()
        self._observe_locomotor_economy_locked()
        work = getattr(self.runtime, "last_work_allocation", None) or {}
        self._telemetry.append({
            "tick": int(self.runtime.tick),
            "work_reservoir": float(getattr(self.runtime.body, "mechanical_work_reservoir", 0.0) or 0.0),
            "resource_A": float(getattr(self.runtime.body, "R_A_site", []).sum()) if getattr(self.runtime.body, "R_A_site", None) is not None else 0.0,
            "resource_B": float(getattr(self.runtime.body, "R_B_site", []).sum()) if getattr(self.runtime.body, "R_B_site", None) is not None else 0.0,
            "speed": float((self.runtime.body.vx ** 2 + self.runtime.body.vy ** 2) ** 0.5),
            "omega": float(getattr(self.runtime.body, "omega", 0.0)),
            "action_requested": float(work.get("requested_action") or 0.0),
            "action_allocated": float(work.get("allocated_action") or 0.0),
            "motor_requested": float(work.get("requested_motor") or 0.0),
            "motor_allocated": float(work.get("allocated_motor") or 0.0),
            "deformation_requested": float(work.get("requested_deformation") or 0.0),
            "deformation_allocated": float(work.get("allocated_deformation") or 0.0),
        })
        self._append_compact_history_locked()

    def _append_compact_history_locked(self) -> None:
        """Record per-tick action/pose/contact. Not a public WORLD frame."""
        if not self._live_presentation_bookkeeping_enabled():
            return
        self._timeline.append(compact_history_from_runtime(self.runtime, status=self.status))


    def collected_events(self, *, limit: int = 200) -> list[dict[str, Any]]:
        """Observer event batch for Timeline / Analyze Results (bounded).

        Always drain pending structured events from the runtime before serving.
        Events emitted between captures (or injected for forensics) must not be
        invisible solely because the ring already holds earlier ticks.
        """
        with self._lock:
            self._accumulate_events_locked()
            items = list(self._event_ring)
        if not items:
            return collect_observer_events(self.runtime, limit=limit)
        return items[-max(1, int(limit)):]

    def _frame_detail_for_speed(self) -> str:
        """RUNNING always uses compact/bounded frames so capture cannot stall SIM.

        Full detail is available on PAUSED / INSPECT / explicit step captures.
        """
        if self.status == "RUNNING":
            return "compact"
        return "full"

    def _update_perf_locked(self, *, tick: bool = False, capture: bool = False) -> None:
        now = time.monotonic()
        if self._perf_window_start <= 0:
            self._perf_window_start = now
        if tick:
            self._perf_ticks += 1
        if capture:
            self._perf_captures += 1
        elapsed = now - self._perf_window_start
        if elapsed >= 0.5:
            self._perf_sim_tps = self._perf_ticks / elapsed
            self._perf_obs_fps = self._perf_captures / elapsed
            self._perf_window_start = now
            self._perf_ticks = 0
            self._perf_captures = 0

    def _ensure_capture_worker(self) -> None:
        with self._capture_cond:
            if self._capture_thread is not None and self._capture_thread.is_alive():
                return
            self._capture_stop = False
            self._capture_thread = threading.Thread(
                target=self._capture_worker_loop,
                name="psy-observer-capture",
                daemon=True,
            )
            self._capture_thread.start()

    def _request_observer_capture(self, *, detail: str | None = None) -> None:
        """Latest-wins capture request. Never queues more than one pending job."""
        self._ensure_capture_worker()
        with self._capture_cond:
            if self._capture_pending is not None or self._capture_inflight:
                self._capture_queue_drops += 1
                self._visual_dropped += 1
            self._capture_pending = {
                "generation": int(self._runtime_generation),
                "detail": detail,
                "requested_tick": int(self.runtime.tick),
                "requested_at": time.monotonic(),
            }
            # Ask SIM to defer step_lock so this request is not starved.
            self._capture_wants_lock = True
            self._capture_cond.notify()

    def _yield_step_lock_to_capture(self) -> None:
        """Prevent SIM from starving the capture worker of `_step_lock`.

        At high SIM rates (especially MAX with no intentional sleep) the play
        thread can re-acquire `_step_lock` so quickly that the capture worker
        waits seconds for a turn — OBS stalls / STALE while SIM keeps running.
        When the capture worker signals `_capture_wants_lock`, SIM briefly
        defers taking the lock (bounded wait).
        """
        if not self._capture_coop_yield:
            return
        if not self._capture_wants_lock:
            return
        deadline = time.monotonic() + 0.05  # max 50ms cooperative deferral
        while self._capture_wants_lock and time.monotonic() < deadline:
            time.sleep(0.0002)

    def _capture_worker_loop(self) -> None:
        while True:
            with self._capture_cond:
                while self._capture_pending is None and not self._capture_stop:
                    self._capture_cond.wait(timeout=0.05)
                if self._capture_stop and self._capture_pending is None:
                    break
                req = self._capture_pending
                self._capture_pending = None
                if req is None:
                    continue
                self._capture_inflight = True
            delay = float(self._capture_test_delay_s or 0.0)
            if delay > 0:
                time.sleep(delay)
            gen = int(req.get("generation") or -1)
            if gen != int(self._runtime_generation):
                with self._capture_cond:
                    self._capture_inflight = False
                    if self._capture_pending is None:
                        self._capture_wants_lock = False
                    self._capture_cond.notify_all()
                continue
            detail = req.get("detail")
            requested_tick = int(req.get("requested_tick") or -1)
            requested_at = float(req.get("requested_at") or time.monotonic())
            frame = None
            timing: dict[str, Any] = {
                "requested_tick": requested_tick,
                "requested_at": requested_at,
                "wakeup_lag_ms": (time.monotonic() - requested_at) * 1000.0,
                "detail_requested": detail,
            }
            wall0 = time.perf_counter()
            try:
                # Signal SIM to defer re-acquiring step_lock (anti-starvation).
                self._capture_wants_lock = True
                t_lock0 = time.perf_counter()
                acquired = self._step_lock.acquire(timeout=5.0)
                lock_wait_ms = (time.perf_counter() - t_lock0) * 1000.0
                timing["lock_wait_ms"] = lock_wait_ms
                timing["lock_acquired"] = bool(acquired)
                if not acquired:
                    timing["discarded"] = "lock_timeout"
                    continue
                timing["capture_start_tick"] = int(getattr(self.runtime, "tick", -1))
                try:
                    if gen != int(self._runtime_generation):
                        timing["discarded"] = "generation_mismatch"
                        continue
                    with self._lock:
                        if self.status == "STOPPED":
                            timing["discarded"] = "stopped"
                            continue
                        detail_s = detail or self._frame_detail_for_speed()
                        timing["detail_used"] = detail_s
                        t_build0 = time.perf_counter()
                        # Build frame under lock; JSON serialize OUTSIDE step_lock.
                        from mechanistic_mind.research.tick_profiler import span as _obs_span

                        with _obs_span("observer_frame"):
                            frame = self._capture_locked(detail=detail_s, serialize=False)
                        timing["frame_build_ms"] = (time.perf_counter() - t_build0) * 1000.0
                        timing["lock_hold_ms"] = (time.perf_counter() - t_lock0) * 1000.0
                finally:
                    self._step_lock.release()
                    # Allow SIM to proceed while we serialize/publish.
                    with self._capture_cond:
                        if self._capture_pending is None:
                            self._capture_wants_lock = False
                if frame is not None:
                    # Build/refresh GEO overlay OUTSIDE `_step_lock` so W×H grids
                    # never extend SIM lock-hold (BETA2-OBS-04 / OBS-05).
                    detail_used = str(timing.get("detail_used") or "compact")
                    if self._geo_live_enabled:
                        t_geo0 = time.perf_counter()
                        overlay, transport = self._publish_geo_overlay_outside_lock(
                            detail=detail_used,
                        )
                        timing["geo_overlay_ms"] = (time.perf_counter() - t_geo0) * 1000.0
                        gi = frame.get("geometry_interpretation")
                        if isinstance(gi, dict):
                            if overlay is not None:
                                gi["traversability"] = overlay
                            gi["geo_transport"] = transport
                        frame["geo_transport"] = transport
                    # Lightweight Observer diagnostics on the published frame.
                    op = frame.get("observer_perf") if isinstance(frame.get("observer_perf"), dict) else {}
                    op = dict(op)
                    op["capture_build_ms"] = round(float(timing.get("frame_build_ms") or 0.0), 3)
                    op["detail_used"] = timing.get("detail_used")
                    op["requested_tick"] = timing.get("requested_tick")
                    op["queue_drops"] = int(self._capture_queue_drops)
                    op["queue_depth"] = self.capture_queue_depth()
                    frame["observer_perf"] = op
                    t_ser0 = time.perf_counter()
                    from mechanistic_mind.research.tick_profiler import span as _obs_span

                    with _obs_span("observer_serialize"):
                        self._serialize_published(frame)
                    timing["serialization_ms"] = (time.perf_counter() - t_ser0) * 1000.0
                    op["serialization_ms"] = round(float(timing["serialization_ms"]), 3)
                    try:
                        raw = getattr(self, "_last_serialized_bytes", None)
                        if raw is not None:
                            op["frame_bytes"] = int(raw)
                    except Exception:
                        pass
                    frame["observer_perf"] = op
                    t_pub0 = time.perf_counter()
                    from mechanistic_mind.research.tick_profiler import span as _obs_span

                    with _obs_span("observer_publish"):
                        self._maybe_push(frame)
                    timing["publish_ms"] = (time.perf_counter() - t_pub0) * 1000.0
                    timing["completed_frame_tick"] = int(
                        (frame.get("header") or {}).get("frame_tick")
                        or (frame.get("header") or {}).get("tick")
                        or -1
                    )
                    now_m = time.monotonic()
                    if self._last_publish_mono > 0:
                        self._publish_intervals_ms.append(
                            (now_m - self._last_publish_mono) * 1000.0
                        )
                    self._last_publish_mono = now_m
                    key = str(timing.get("detail_used") or "other")
                    if key not in ("compact", "full"):
                        key = "other"
                    self._capture_detail_counts[key] = int(
                        self._capture_detail_counts.get(key, 0)
                    ) + 1
            finally:
                timing["total_capture_ms"] = (time.perf_counter() - wall0) * 1000.0
                timing["queue_drops"] = int(self._capture_queue_drops)
                if self._capture_timing_enabled:
                    self._capture_timings.append(timing)
                with self._capture_cond:
                    self._capture_inflight = False
                    if self._capture_pending is None:
                        self._capture_wants_lock = False
                    else:
                        self._capture_wants_lock = True
                    self._capture_cond.notify_all()

    def capture_timing_snapshot(self) -> list[dict[str, Any]]:
        return list(self._capture_timings)

    def capture_queue_depth(self) -> int:
        with self._capture_cond:
            return (1 if self._capture_pending else 0) + (1 if self._capture_inflight else 0)

    def wait_capture_idle(self, timeout: float = 2.0) -> bool:
        deadline = time.monotonic() + max(0.0, float(timeout))
        with self._capture_cond:
            while self._capture_pending is not None or self._capture_inflight:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._capture_cond.wait(timeout=remaining)
            return True

    def _capture_locked(self, *, detail: str | None = None, serialize: bool = True) -> dict[str, Any]:
        try:
            setattr(self.runtime, "_observer_runtime_generation", self._runtime_generation)
        except Exception:
            pass
        detail_s = detail or self._frame_detail_for_speed()
        self._accumulate_events_locked()
        # Compact RUNNING: smaller event tail to keep lock-hold and JSON bounded.
        ev_tail = LIVE_EVENT_EMBED if str(detail_s).lower() == "compact" else LIVE_EVENT_EMBED_FULL
        events_payload = tail_list(self._event_ring, ev_tail)
        # Avoid multi-hundred-ms GC pauses mid-frame (can trip STALE even with coop yield).
        _gc_was = gc.isenabled()
        if _gc_was:
            gc.disable()
        try:
            _interest = getattr(self, "_observer_interest", None)
            _inc_cog = True if _interest is None else bool(_interest.wants(PRODUCT_COGNITION))
            if _interest is not None:
                _interest.record_producer("world")
                if _inc_cog:
                    _interest.record_producer(PRODUCT_COGNITION)
            frame = live_frame(
                self.runtime,
                status=self.status,
                mode=self.mode if self.mode != "INSPECT" else "INSPECT",
                target_tick=self.config.target_tick,
                previous_body=self._prev_body,
                previous_bodies=dict(self._prev_bodies),
                detail=detail_s,
                structured_events=events_payload,
                # Compact RUNNING: use last published overlay (O(1)). Fresh rebuild
                # happens outside `_step_lock` in the capture worker.
                geometry_traversability=self._geo_overlay_for_capture_locked(detail=detail_s),
                include_cognition=_inc_cog,
            )
        finally:
            if _gc_was:
                gc.enable()
        # LIVE frame embeds only a bounded recent intervention strip.
        # Full scientific intervention provenance remains in scientific_events.
        session_n = len(self._world_interventions)
        live_interventions = tail_list(self._world_interventions, LIVE_WORLD_INTERVENTION_EMBED)
        frame["world_interventions"] = live_interventions
        frame["world_intervention_summary"] = {
            "n": session_n,
            "live_embed_n": len(live_interventions),
            "live_embed_cap": LIVE_WORLD_INTERVENTION_EMBED,
            "session_cap": LIVE_WORLD_INTERVENTION_SESSION_MAX,
            "authority": "LIVE_RECENT_PLUS_SUMMARY",
            "scientific_authority": "scientific_events.jsonl",
            "runtime_generation": int(self._runtime_generation),
            "configuration_history": (
                "MULTI_REGIME" if session_n else "STATIC"
            ),
        }
        # Compact integrity status (bounded — not full manifest every frame).
        pf = self._preflight_result
        frame["mechanism_integrity"] = {
            "ready": bool(pf and pf.get("status") == "READY"),
            "preflight_status": (pf or {}).get("status"),
            "fingerprint": (
                (self._runtime_mechanism_manifest or {}).get("resolved_fingerprint")
                or (
                    self._resolved_mechanism_config.fingerprint()
                    if self._resolved_mechanism_config is not None else None
                )
            ),
            "mismatch_n": len((pf or {}).get("mismatches") or []),
            "rows": (pf or {}).get("rows"),
        }
        if self._sig_accum is None:
            self._reset_sig_accum_locked()
        if self._sig_live_enabled:
            frame["signal_context_interpretation"] = self._sig_accum.compact_summary()
        else:
            frame["signal_context_interpretation"] = {
                "status": "DISABLED",
                "honesty": {
                    "observer_only": True,
                    "live_bounded": True,
                    "matched_controls": "ANALYZE_RESULTS_ONLY",
                    "no_communication_claim": True,
                },
            }
        frame["experimenter_interaction"] = self._experimenter_compact_locked()
        frame["crash_checkpoint"] = self.checkpoint_status()
        # GEO-03: bounded action realization (O(agents), not map scan)
        if self._action_realization is None:
            self._reset_action_realization_locked()
        ar = self._action_realization.compact_live() if self._action_realization else {"status": "DISABLED"}
        frame["action_realization"] = ar
        # Attach banner into experimenter compact for YOU CONTROL strip
        if isinstance(frame.get("experimenter_interaction"), dict) and ar.get("experimenter_banner"):
            frame["experimenter_interaction"]["realization_banner"] = ar["experimenter_banner"]
        # GEO-04: bounded work ecology (O(agents))
        if self._work_ecology is None:
            self._reset_work_ecology_locked()
        we = self._work_ecology.compact_live() if self._work_ecology else {"status": "DISABLED"}
        frame["work_ecology"] = we
        if self._locomotor_economy is None:
            self._reset_locomotor_economy_locked()
        le = self._locomotor_economy.compact_live() if self._locomotor_economy else {"status": "DISABLED"}
        frame["locomotor_economy"] = le
        views = frame.get("agents_views") or {}
        for _aid, view in views.items():
            if isinstance(view, dict) and view.get("generation") is None:
                view["generation"] = self._runtime_generation
        self._frame_seq += 1
        captured_at = datetime.now(timezone.utc).isoformat()
        frame_id = f"g{self._runtime_generation}-f{self._frame_seq}-t{self.runtime.tick}"
        ticks = {
            "runtime": int(self.runtime.tick),
            "world": int(self.runtime.world.tick),
            "body": int(self.runtime.body.tick),
            "internal": int(self.runtime.internal.tick),
        }
        slots = getattr(self.runtime, "slots", None)
        if slots:
            for i, slot in enumerate(slots):
                ticks[f"agent_{i}"] = int(slot.tick)
        live_tick = int(self.runtime.tick)
        self._last_frame_tick = live_tick
        elements_touched = live_refresh_elements_touched(
            event_embed=len(events_payload),
            traj_embed=0,
            telem_embed=0,
            intervention_embed=len(live_interventions),
        )
        frame["observation"] = {
            "observation_frame_id": frame_id,
            "runtime_generation": self._runtime_generation,
            "captured_at": captured_at,
            "captured_monotonic": time.monotonic(),
            "stale_after_seconds": max(1.0, 3.0 / max(0.1, float(self.config.ui_hz))),
            "ticks": ticks,
            "tick_consistent": len(set(ticks.values())) == 1,
            "selected_agent_id": (frame.get("header") or {}).get("selected_agent_id") or (frame.get("header") or {}).get("selected_agent"),
            "frame_detail": detail_s,
            "live_bounds": live_bounds_snapshot(),
            "history_elements_touched_by_live_refresh": elements_touched,
        }
        frame.setdefault("header", {}).update({
            "observation_frame_id": frame_id,
            "runtime_generation": self._runtime_generation,
            "captured_at": captured_at,
            "live_runtime_tick": live_tick,
            "frame_tick": live_tick,
            "simulation_speed": float(self.config.speed),
            "execution_mode": str(self.config.execution_mode or "LIVE"),
            "observer_hz": float(self.config.ui_hz),
            "max_ticks": self.config.target_tick,
            "model_architecture": display_name(),
            # When not RUNNING, do not leave a stale window average in the header.
            "sim_ticks_per_sec": (
                round(float(self._perf_sim_tps), 1) if self.status == "RUNNING" else 0.0
            ),
            "observer_fps": round(float(self._perf_obs_fps), 1),
            "visual_frames_dropped": int(self._visual_dropped),
            "observer_decoupled": True,
            "frame_detail": detail_s,
        })
        obs = frame.setdefault("observer", {})
        obs["runtime_generation"] = self._runtime_generation
        obs["inspected_tick"] = live_tick
        obs["live_runtime_tick"] = live_tick
        obs["frame_tick"] = live_tick
        obs["selected_agent_id"] = (frame.get("header") or {}).get("selected_agent_id")
        obs["identity_tuple"] = {
            "runtime_generation": self._runtime_generation,
            "inspected_tick": live_tick,
            "selected_agent_id": obs.get("selected_agent_id"),
            "selected_body_id": (frame.get("header") or {}).get("selected_body_id"),
            "agent_seed": (frame.get("header") or {}).get("inspected_agent_seed"),
        }
        # Motion series are recorded every scientific tick via _record_motion_locked.
        # Capture only embeds (does not append) to avoid double-counting and to keep
        # SIM-path recording independent of Observer sampling.
        if not self._trajectory or int(self._trajectory[-1].get("tick", -1)) != live_tick:
            self._record_motion_locked()
        self._prev_body = deepcopy(self.runtime.body.snapshot())
        slots_now = getattr(self.runtime, "slots", None)
        if slots_now:
            self._prev_bodies = {
                f"agent_{i}": deepcopy(slot.body.snapshot())
                for i, slot in enumerate(slots_now)
            }
        else:
            self._prev_bodies = {"agent_0": deepcopy(self._prev_body)}
        if detail_s == "compact":
            traj_points = tail_list(self._trajectory, LIVE_TRAJECTORY_EMBED)
            telem_series = tail_list(self._telemetry, LIVE_TELEMETRY_EMBED)
        else:
            # Full detail: entire in-memory rings (already maxlen-bounded; not sci history).
            traj_points = list(self._trajectory)
            telem_series = list(self._telemetry)
        frame["trajectory"] = {
            "points": traj_points,
            "capacity": self._trajectory.maxlen,
            "boundary": "WRAP_PERIODIC",
            "truncated": len(self._trajectory) > len(traj_points),
            "live_authority": "live_recent_trajectory",
            "not_scientific_trajectory": True,
        }
        frame["telemetry"] = {
            "series": telem_series,
            "capacity": self._telemetry.maxlen,
            "truncated": len(self._telemetry) > len(telem_series),
            "live_authority": "live_recent_telemetry",
        }
        obs_meta = frame.get("observation")
        if isinstance(obs_meta, dict):
            obs_meta["history_elements_touched_by_live_refresh"] = live_refresh_elements_touched(
                event_embed=len(events_payload),
                traj_embed=len(traj_points),
                telem_embed=len(telem_series),
                intervention_embed=len(live_interventions),
            )
        if self._historical_compat:
            frame["historical_compatibility"] = deepcopy(self._historical_compat)
        # Attach geo_transport + provenance on every capture (incl. Apply/reset/hydrate).
        # Async capture worker may refresh grids outside the lock afterward; this keeps
        # synchronous paths (Apply, hydrate, Use LIVE) from embedding stale/missing GEO.
        gi = frame.get("geometry_interpretation")
        if isinstance(gi, dict):
            trav = gi.get("traversability") if isinstance(gi.get("traversability"), dict) else None
            source_u = str(getattr(self, "_geo_overlay_source", "LIVE") or "LIVE").upper()
            n_obs = int((trav or {}).get("n_observations") or 0)
            transport = {
                "static_version": int(self._geo_static_version or 0),
                "empirical_version": int((trav or {}).get("empirical_version") or 0),
                "empirical_inline": True,
                "n_observations": n_obs,
            }
            overlay, transport = self._attach_geo_provenance(trav, transport, source=source_u)
            if overlay is not None:
                gi["traversability"] = overlay
            gi["geo_transport"] = transport
            frame["geo_transport"] = transport
        experiment = frame.setdefault("experiment", {})
        experiment["observer"] = {
            "ui_hz": float(self.config.ui_hz),
            "buffer_capacity": int(self.config.buffer_capacity),
            "speed": float(self.config.speed),
            "target_tick": self.config.target_tick,
            "execution_mode": str(self.config.execution_mode or "LIVE"),
            "observer_hz": float(self.config.ui_hz),
            "base_tick_period_1x": BASE_TICK_PERIOD_1X,
            "capture_period_s": observer_capture_period(self.config.speed, self.config.ui_hz),
            "async_capture": True,
            "capture_enabled": str(self.config.execution_mode or "LIVE").upper() != "HEADLESS",
            "capture_queue_drops": int(self._capture_queue_drops),
        }
        pe_cold = self.pe_cold_eviction_applied()
        experiment["pe_cold_history_eviction"] = pe_cold
        runtime_block = experiment.setdefault("runtime", {})
        if isinstance(runtime_block, dict):
            runtime_block["pe_cold_history_eviction"] = bool(pe_cold["applied"])
        frame.setdefault("header", {})["pe_cold_history_eviction"] = bool(pe_cold["applied"])
        sim_tick_now = int(self.runtime.tick)
        lag = max(0, sim_tick_now - live_tick)
        self._observer_lag_ticks = lag
        frame.setdefault("header", {}).update({
            "observer_lag_ticks": lag,
            "sim_tick": sim_tick_now,
            "frame_tick": live_tick,
        })
        self._stat_live_frame_builds += 1
        self._buffer.append(frame)
        self._attach_tiktaalik_eye_locked(frame)
        self._published = frame
        if serialize and self.publication_wanted():
            self._serialize_published(frame)
        elif serialize and str(self.status).upper() != "RUNNING":
            # PAUSED/STEP/control receipts still need a cached JSON for HTTP/WS.
            self._serialize_published(frame)

        # Demand-driven: drop optional Observer products (science already recorded separately).
        interest = getattr(self, "_observer_interest", None)
        if interest is not None:
            if not interest.wants(PRODUCT_GRAPHS):
                frame["trajectory"] = stub_deferred(PRODUCT_GRAPHS)
                if isinstance(frame.get("telemetry"), dict):
                    frame["telemetry"] = {
                        **stub_deferred(PRODUCT_GRAPHS),
                        "series": [],
                        "capacity": (frame.get("telemetry") or {}).get("capacity"),
                    }
            if not interest.wants(PRODUCT_SIGNALS):
                frame["signal_context_interpretation"] = stub_deferred(PRODUCT_SIGNALS)
            if not interest.wants(PRODUCT_EXPERIMENTER):
                frame["experimenter_interaction"] = stub_deferred(PRODUCT_EXPERIMENTER)
            if not interest.wants(PRODUCT_GEOMETRY):
                gi = frame.get("geometry_interpretation")
                if isinstance(gi, dict):
                    frame["geometry_interpretation"] = {**stub_deferred(PRODUCT_GEOMETRY), "status": "DEFERRED"}
            if not interest.wants(PRODUCT_COGNITION):
                views = frame.get("agents_views") or {}
                for _aid, view in list(views.items()) if isinstance(views, dict) else []:
                    if not isinstance(view, dict):
                        continue
                    view["mind"] = stub_deferred(PRODUCT_COGNITION)
                    view["cognition_pipeline"] = stub_deferred(PRODUCT_COGNITION)
                    view["prospection_view"] = stub_deferred(PRODUCT_COGNITION)
                    view["causal_chain"] = stub_deferred(PRODUCT_COGNITION)
            frame.setdefault("header", {})["observer_detail_preset"] = interest.preset
            frame.setdefault("header", {})["observer_products"] = sorted(interest.products)
            frame["observer_interest"] = interest.snapshot()

        self._update_perf_locked(capture=True)
        return frame

    def _serialize_published(self, frame: dict[str, Any]) -> None:
        """JSON-cache the published frame (safe outside `_step_lock`)."""
        t_ser0 = time.perf_counter()
        try:
            self._published_json = json.dumps(frame, default=str, separators=(",", ":"))
            self._last_serialized_bytes = len(self._published_json)
            self._published_ws_text = '{"type":"frame","data":' + self._published_json + "}"
            self._stat_json_dumps_publish += 1
            self._stat_json_publish_bytes += self._last_serialized_bytes
        except TypeError:
            self._published_json = None
            self._published_ws_text = None
            self._last_serialized_bytes = 0
        self._last_publish_serialize_ms = (time.perf_counter() - t_ser0) * 1000.0

    def _control_state(self) -> dict[str, Any]:
        rt = getattr(self, "runtime", None)
        return {
            "tick": int(rt.tick) if rt is not None else None,
            "runtime_generation": self._runtime_generation,
            "status": self.status,
            "mode": self.mode,
            "speed": float(self.config.speed),
        }

    def _lifecycle_error(
        self,
        operation: str,
        reason: str | None,
        *,
        code: str | None = None,
        recoverable: bool | None = None,
    ) -> dict[str, Any]:
        """Observer/control error object — not a scientific DecisionReceipt."""
        op = str(operation or "").upper()
        msg = str(reason or "").strip() or "rejected"
        status = str(self.status)
        if code is None:
            low = msg.lower()
            if status == "SAVE_FAILED" or "save_failed" in low or "persistence_integrity" in low:
                code = "SAVE_FAILED"
            elif "http_failed" in low or "networkerror" in low or "disconnected" in low:
                code = "HTTP_FAILED"
            elif "finalization in progress" in low or "save_stop_started" in low or msg == "PREFLIGHT_FAILED":
                code = "INVALID_TRANSITION"
            elif "unknown" in low or "unsupported" in low or "not ablatable" in low:
                code = "INVALID_TRANSITION"
            elif op == "STOP":
                code = "STOP_REJECTED"
            else:
                code = "INVALID_TRANSITION"
        if recoverable is None:
            recoverable = code in {"SAVE_FAILED", "INVALID_TRANSITION", "STOP_REJECTED", "HTTP_FAILED"}
            if status == "STOPPED" and code != "SAVE_FAILED":
                recoverable = False
        return {
            "code": str(code),
            "message": msg,
            "recoverable": bool(recoverable),
        }

    def _with_receipt(
        self,
        frame: dict[str, Any],
        operation: str,
        request: dict[str, Any],
        previous: dict[str, Any],
        *,
        accepted: bool = True,
        requires_reset: bool = False,
        reason: str | None = None,
        error: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Attach an Observer control receipt without deepcopying the frame body.

        Nested frame content is treated as immutable (same contract as current_frame).
        Only the top-level dict and header are shallow-copied so receipts cannot
        mutate the published snapshot. Scientific Decision/Motor receipts are unchanged.
        """
        hdr = dict((frame or {}).get("header") or {})
        out = {**(frame or {}), "header": hdr}
        lifecycle = str(self.status)
        receipt: dict[str, Any] = {
            "receipt_id": f"ctl-{self._runtime_generation}-{self._frame_seq}-{operation.lower()}",
            "operation": operation,
            "request": request,
            "accepted": bool(accepted),
            "ok": bool(accepted),
            "previous_state": previous,
            "new_state": self._control_state(),
            "tick": int(self.runtime.tick),
            "runtime_generation": self._runtime_generation,
            "requires_reset": bool(requires_reset),
            "reason": reason,
            "lifecycle_state": lifecycle,
        }
        if not accepted:
            receipt["error"] = error or self._lifecycle_error(operation, reason)
        out["control_receipt"] = receipt
        return out

    def _maybe_push(self, frame: dict[str, Any], *, force: bool = False) -> bool:
        now = time.monotonic()
        min_dt = 1.0 / max(1e-3, float(self.config.ui_hz))
        if not force and (now - self._last_push) < min_dt:
            self._visual_dropped += 1
            return False
        self._last_push = now
        for fn in list(self._subscribers):
            try:
                fn(frame)
            except Exception:
                pass
        return True

    def play(self) -> dict[str, Any]:
        before = self._control_state()
        if self.status == "FINALIZING":
            return self._with_receipt(
                self._clone_published(), "PLAY", {}, before,
                accepted=False, reason="finalization in progress",
            )
        blocked = self._require_preflight_ready("PLAY", before, {})
        if blocked is not None:
            return blocked
        if self._run_started_at is None:
            self._run_started_at = datetime.now(timezone.utc).isoformat()
            self._active_run_id = new_run_id()
            self._termination_reason = None
            # Stamp run_id onto manifest once identity is known.
            if self._runtime_mechanism_manifest is not None:
                self._runtime_mechanism_manifest = dict(self._runtime_mechanism_manifest)
                self._runtime_mechanism_manifest["run_id"] = self._active_run_id
        self.mode = "LIVE"
        self.inspect_tick = None
        self.status = "RUNNING"
        self._stop_flag = False
        self._ensure_capture_worker()
        self._ensure_heartbeat_worker()
        with self._lock:
            self._ensure_scientific_locked()
            self._ensure_loop_locked()
        out = self._with_receipt(self._clone_published(status="RUNNING"), "PLAY", {}, before)
        out["preflight"] = self._preflight_result
        out["mechanism_integrity"] = self.mechanism_integrity_status()
        self._maybe_push(out, force=True)
        return out

    def pause(self) -> dict[str, Any]:
        before = self._control_state()
        if self.status == "FINALIZING":
            return self._with_receipt(
                self._clone_published(), "PAUSE", {}, before,
                accepted=False, reason="finalization in progress",
            )
        self.status = "PAUSED"
        self._invalidate_pending_captures_locked()
        self.wait_capture_idle(timeout=1.0)
        with self._step_lock:
            with self._lock:
                self._perf_sim_tps = 0.0
                self._perf_ticks = 0
                self._perf_window_start = time.monotonic()
                frame = self._capture_locked(detail="full")
        out = self._with_receipt(frame, "PAUSE", {}, before)
        self._maybe_push(out, force=True)
        return out

    def stop_info(self) -> dict[str, Any]:
        """Facts for Stop confirmation dialog — no side effects."""
        slots = getattr(self.runtime, "slots", None)
        return {
            "tick": int(self.runtime.tick),
            "seed": int(getattr(self.runtime, "seed", self.config.seed)),
            "runtime": type(self.runtime).__name__,
            "agent_count": len(slots) if slots else 1,
            "status": self.status,
            "default_action": "SAVE_AND_STOP",
            "run_id": self._active_run_id,
            "started_at": self._run_started_at,
            "last_finalize": deepcopy(self._last_finalize) if self._last_finalize else None,
        }

    def _release_run_identity(self) -> None:
        """After a run is finalized (or discarded), next Play/Step opens a new run_id.

        Prevents Save → Play → Save from reusing the prior run_id and falsely
        accepting a stale idempotent artifact while the live tick has advanced.
        """
        self._active_run_id = None
        self._run_started_at = None
        with self._lock:
            self._close_scientific_locked()

    def _results_root(self) -> Path:
        return Path(self.config.results_root) if self.config.results_root else default_results_root()

    def _pe_cold_evict_root_locked(self) -> Path:
        live = self._sci_live_dir
        if live:
            return Path(live) / "pe_cold"
        return self._results_root() / "pe_cold" / "session"

    def _apply_pe_cold_eviction_locked(self) -> None:
        """Stamp session eviction request onto the process PE cold-archive flags."""
        from mechanistic_mind.research import pe_cold_archive as cold

        on = bool(self.config.pe_cold_history_eviction)
        if on:
            cold.set_cold_archive(True)
            cold.set_cold_eviction(True, root=self._pe_cold_evict_root_locked())
        else:
            cold.set_cold_eviction(False)

    def pe_cold_eviction_applied(self) -> dict[str, Any]:
        from mechanistic_mind.research import pe_cold_archive as cold

        applied = bool(cold.cold_eviction_enabled())
        root = cold.eviction_root()
        return {
            "requested": bool(self.config.pe_cold_history_eviction),
            "applied": applied,
            "label": "ON" if applied else "OFF",
            "archive_applied": bool(cold.cold_archive_enabled()),
            "chunk_size": int(cold.cold_chunk_records()),
            "mmap": False,
            "evict_root": str(root) if applied and root is not None else None,
        }

    def _ensure_scientific_locked(self) -> None:
        """Open append-only scientific / compact writer for the active run_id (idempotent)."""
        mode = str(getattr(self.config, "evidence_mode", None) or "FULL_SCIENTIFIC").upper()
        if mode == "SEARCH_COMPACT":
            if self._compact_writer is not None:
                return
            rid = self._active_run_id
            if not rid:
                return
            live = live_scientific_dir(self._results_root(), rid)
            from mechanistic_mind.ui.psy_observer_web.search_compact.controller import (
                SearchCompactController,
                trigger_action_count_threshold,
            )
            from mechanistic_mind.ui.psy_observer_web.search_compact.writer import SearchCompactWriter
            fp = (
                (self._runtime_mechanism_manifest or {}).get("resolved_fingerprint")
                or (self._resolved_mechanism_config.fingerprint()
                    if self._resolved_mechanism_config is not None else None)
            )
            ctrl = SearchCompactController(
                run_id=rid,
                seed=int(getattr(self.runtime, "seed", self.config.seed)),
                config_fingerprint=fp,
                pre_window=int(self.config.search_compact_pre_window),
                post_window=int(self.config.search_compact_post_window),
                max_candidates=int(self.config.search_compact_max_candidates),
                triggers=[
                    trigger_action_count_threshold(
                        threshold=int(self.config.search_compact_trigger_threshold),
                    ),
                ],
            )
            writer = SearchCompactWriter(live / "search_compact", ctrl)
            writer.open({
                "run_id": rid,
                "seed": int(getattr(self.runtime, "seed", self.config.seed)),
                "config_fingerprint": fp,
                "evidence_mode": "SEARCH_COMPACT",
                "execution_mode": str(self.config.execution_mode or "LIVE"),
                "runtime_type": type(self.runtime).__name__,
                "agent_count": len(getattr(self.runtime, "slots", None) or [1]),
                "runtime_generation": int(self._runtime_generation),
                "pre_window": ctrl.pre_window,
                "post_window": ctrl.post_window,
                "max_candidates": ctrl.max_candidates,
            })
            self._compact_writer = writer
            self._sci_live_dir = live
            self._apply_pe_cold_eviction_locked()
            return

        if self._sci_writer is not None:
            return
        rid = self._active_run_id
        if not rid:
            return
        live = live_scientific_dir(self._results_root(), rid)
        slots = getattr(self.runtime, "slots", None)
        writer = ScientificHistoryWriter(live)
        writer.open({
            "run_id": rid,
            "runtime_type": type(self.runtime).__name__,
            "seed": int(getattr(self.runtime, "seed", self.config.seed)),
            "agent_count": len(slots) if slots else 1,
            "runtime_generation": int(self._runtime_generation),
            "started_at": self._run_started_at,
            "ecology_preset": getattr(
                getattr(self.runtime, "config", None), "ecology_preset", "CURRENT"
            ) or "CURRENT",
            "runtime_mechanism_manifest": self._runtime_mechanism_manifest,
            "mechanism_config_fingerprint": (
                (self._runtime_mechanism_manifest or {}).get("resolved_fingerprint")
                or (self._resolved_mechanism_config.fingerprint()
                    if self._resolved_mechanism_config is not None else None)
            ),
            "preflight_status": (self._preflight_result or {}).get("status"),
            "evidence_mode": "FULL_SCIENTIFIC",
            "psc_prediction": __import__(
                "mechanistic_mind.research.psc_opt", fromlist=["backend_provenance"]
            ).backend_provenance(),
        })
        self._sci_writer = writer
        self._sci_live_dir = live
        self._apply_pe_cold_eviction_locked()
        # SCIENTIFIC_V3 CORE — additive; does not replace V2
        if self._v3_writer is None:
            v3 = ScientificV3Writer(live)
            v3.open(
                run_id=str(rid),
                generation=int(self._runtime_generation),
                extra_meta={
                    "runtime_type": type(self.runtime).__name__,
                    "seed": int(getattr(self.runtime, "seed", self.config.seed)),
                    "alongside": "SCIENTIFIC_V2_TIERED",
                    **(self._checkpoint_resume_meta or {}),
                },
            )
            self._v3_writer = v3

    def _close_scientific_locked(self, *, clear_live_dir: bool = True) -> None:
        w = self._sci_writer
        self._sci_writer = None
        if w is not None:
            try:
                w.close()
            except Exception:
                pass
        v3w = self._v3_writer
        self._v3_writer = None
        if v3w is not None:
            try:
                v3w.close()
            except Exception:
                pass
        cw = self._compact_writer
        self._compact_writer = None
        if cw is not None:
            try:
                cw.close()
            except Exception:
                pass
        if clear_live_dir:
            self._sci_live_dir = None

    def _append_scientific_locked(self) -> None:
        """Persist one scientific / compact record set per new simulation tick."""
        if self._active_run_id is None:
            return
        self._ensure_scientific_locked()
        mode = str(getattr(self.config, "evidence_mode", None) or "FULL_SCIENTIFIC").upper()
        if mode == "SEARCH_COMPACT":
            cw = self._compact_writer
            if cw is None:
                return
            fresh = tail_list(self._event_ring, SCI_APPEND_EVENT_TAIL)
            cw.append_tick(self.runtime, events=fresh)
            return
        from mechanistic_mind.research.tick_profiler import span as _prof_span

        w = self._sci_writer
        if w is None:
            return
        with _prof_span("sci_v2"):
            w.append_tick(self.runtime)
            fresh = tail_list(self._event_ring, SCI_APPEND_EVENT_TAIL)
            if fresh:
                w.append_events(fresh)
        v3w = self._v3_writer
        if v3w is not None:
            try:
                with _prof_span("sci_v3"):
                    v3w.append_runtime_tick(self.runtime)
            except Exception as exc:
                # Fail honestly — do not silently drop; surface on writer health / session
                self._v3_last_error = str(exc)

    def scientific_evidence(
        self,
        *,
        cutoff_tick: int | None = None,
    ) -> dict[str, Any]:
        """Read-only evidence package for Analyzer (tolerates appends beyond cutoff)."""
        with self._lock:
            if self._sci_writer is not None:
                self._sci_writer.flush()
            if self._v3_writer is not None:
                try:
                    self._v3_writer.flush()
                except Exception as exc:
                    self._v3_last_error = str(exc)
            live_dir = self._sci_live_dir
            timeline = list(self._timeline)
            events = list(self._event_ring)
            status = self.status
            rid = self._active_run_id
            slots = getattr(self.runtime, "slots", None)
            identity = {
                "runtime_type": type(self.runtime).__name__,
                "seed": int(getattr(self.runtime, "seed", self.config.seed)),
                "agent_count": len(slots) if slots else 1,
                "runtime_generation": int(self._runtime_generation),
                "ecology_preset": getattr(
                    getattr(self.runtime, "config", None), "ecology_preset", "CURRENT"
                ) or "CURRENT",
            }
            # Deterministic cutoff: caller value or current live tick snapshot
            live_tick = int(self.runtime.tick)
            cut = int(cutoff_tick) if cutoff_tick is not None else live_tick
            runtime = self.runtime
        pkg = load_evidence_package(
            evidence_dir=live_dir,
            runtime=runtime,
            ui_timeline=timeline,
            ui_events=events,
            cutoff_tick=cut,
            runtime_status=status,
            run_id=rid,
            identity=identity,
            include_bulk_rows=False,
            include_behavioral=False,
            include_v3_core=False,
        )
        pkg["v3_evidence_health"] = {
            "writer_attached": self._v3_writer is not None,
            "last_error": self._v3_last_error,
            "health": (self._v3_writer.health if self._v3_writer is not None else None),
            "live_dir": str(live_dir) if live_dir else None,
        }
        return pkg

    def signal_forensics_current_run(
        self,
        *,
        cutoff_tick: int | None = None,
        max_episode_details: int = 40,
        max_timeline_rows: int | None = 50_000,
        max_events: int | None = 200_000,
    ) -> dict[str, Any]:
        """User-triggered Signal Forensics on CURRENT RUN scientific evidence.

        Does not run on LIVE refresh. Reuses Analyzer evidence package authority.
        """
        from mechanistic_mind.ui.psy_observer_web.signal_context.analyze_run import (
            analyze_signal_from_rows_events,
        )

        pkg = self.scientific_evidence(cutoff_tick=cutoff_tick)
        rows = list(pkg.get("scientific_rows") or [])
        events = list(pkg.get("events") or [])
        if max_timeline_rows is not None and len(rows) > int(max_timeline_rows):
            # Keep latest contiguous rows for performance (document as SPARSE if truncated).
            rows = rows[-int(max_timeline_rows) :]
            trunc = True
        else:
            trunc = False
        if max_events is not None and len(events) > int(max_events):
            events = events[-int(max_events) :]
            trunc = True
        world = getattr(getattr(self.runtime, "world", None), "config", None) or getattr(
            self.runtime, "config", None
        )
        width = int(getattr(world, "width", None) or getattr(self.runtime.world, "width", 32) or 32)
        height = int(getattr(world, "height", None) or getattr(self.runtime.world, "height", 32) or 32)
        try:
            width = int(self.runtime.world.width)
            height = int(self.runtime.world.height)
        except Exception:
            pass
        result = analyze_signal_from_rows_events(
            rows=rows,
            events=events,
            run_id=pkg.get("run_id"),
            generation=int(self._runtime_generation),
            width=width,
            height=height,
            max_episode_details=int(max_episode_details),
            focus_ticks=None,  # current-run: percentile + recent, not seed-17 focus ticks
            source_label="CURRENT_RUN",
            telemetry_schema=pkg.get("telemetry_schema"),
            coverage=("SPARSE" if trunc else pkg.get("coverage")),
            runtime_status=pkg.get("runtime_status"),
            cutoff_tick=pkg.get("analysis_cutoff_tick"),
            meta={
                **(pkg.get("scientific_meta") or {}),
                **(pkg.get("identity") or {}),
                "runtime_mechanism_manifest": (
                    (pkg.get("scientific_meta") or {}).get("runtime_mechanism_manifest")
                    or (pkg.get("runtime_mechanism_integrity") or {})
                ),
            },
            seed=(pkg.get("identity") or {}).get("seed") or getattr(self.runtime, "seed", None),
        )
        # Ensure identity agreement with Analyzer package
        result["evidence_package_run_id"] = pkg.get("run_id")
        result["evidence_package_cutoff"] = pkg.get("analysis_cutoff_tick")
        result["evidence_agreement"] = {
            "run_id_match": result.get("run_id") == pkg.get("run_id"),
            "cutoff_match": result.get("cutoff_tick") == pkg.get("analysis_cutoff_tick"),
            "analyzer_same_authority": True,
        }
        result["accepted"] = True
        result["evidence_authority"] = "scientific_evidence_package"
        result["live_buffer_independent"] = True
        result["reference_fixture_auto_loaded"] = False
        live_sum = self.signal_context_live_summary()
        result["live_snapshot"] = {
            "n_episodes": live_sum.get("n_episodes"),
            "n_receptions_buffered": live_sum.get("n_receptions_buffered"),
            "note": "LIVE buffer is not historical authority.",
        }
        return result

    def v3_evidence_health(self) -> dict[str, Any]:
        """Explicit V3 writer health — never silent about CORE capture failure."""
        w = self._v3_writer
        health = w.health if w is not None else None
        return {
            "writer_attached": w is not None,
            "last_error": self._v3_last_error,
            "health": health,
            "live_dir": str(self._sci_live_dir) if self._sci_live_dir else None,
        }

    def finalize_run(self, *, reason: str = "USER_STOP_SAVED") -> dict[str, Any]:
        """Persist current run. Idempotent for the same generation+tick+reason."""
        with self._finalize_lock:
            live_tick = int(self.runtime.tick)
            generation = int(self._runtime_generation)
            key = (generation, live_tick, str(reason))
            if self._finalize_key == key and self._last_finalize and self._last_finalize.get("accepted"):
                out = deepcopy(self._last_finalize)
                out["idempotent"] = True
                out["verified"] = True
                out.setdefault("final_tick", live_tick)
                return out
            results_root = Path(self.config.results_root) if self.config.results_root else default_results_root()
            run_id = self._active_run_id or new_run_id()
            self._active_run_id = run_id
            slots = getattr(self.runtime, "slots", None)
            identity = {
                "expected_final_tick": live_tick,
                "runtime_generation": generation,
                "runtime_type": type(self.runtime).__name__,
                "seed": int(getattr(self.runtime, "seed", self.config.seed)),
                "agent_count": len(slots) if slots else 1,
                "model": display_name(),
            }
            with self._lock:
                self._ensure_scientific_locked()
                # Flush+close writer so meta/jsonl are durable before promote;
                # keep live dir path for copy_scientific_into.
                if self._sci_writer is not None:
                    self._close_scientific_locked(clear_live_dir=False)
                sci_live = self._sci_live_dir
                timeline = list(self._timeline)
                telemetry = list(self._telemetry)
                hist = {
                    "frame_capacity": self._buffer.maxlen,
                    "oldest_tick": int((self._buffer[0].get("header") or {}).get("tick", -1)) if self._buffer else None,
                    "newest_tick": int((self._buffer[-1].get("header") or {}).get("tick", -1)) if self._buffer else None,
                    "live_tick": live_tick,
                    "timeline_len": len(timeline),
                    "telemetry_len": len(telemetry),
                    "runtime_generation": generation,
                    "scientific_live_dir": str(sci_live) if sci_live else None,
                }
            session_meta = {
                "started_at": self._run_started_at,
                "seed": int(self.config.seed),
                "experiment_profile": display_name(),
                "buffer": hist,
            }
            try:
                result = write_finalized_run(
                    results_root=results_root,
                    runtime=self.runtime,
                    session_meta=session_meta,
                    timeline=timeline,
                    telemetry=telemetry,
                    termination_reason=str(reason),
                    run_id=run_id,
                    identity=identity,
                    scientific_live_dir=sci_live,
                )
            except Exception as exc:
                result = {
                    "accepted": False,
                    "error": str(exc),
                    "termination_reason": "SAVE_FAILED",
                    "phases": ["save_failed"],
                    "run_id": run_id,
                    "final_tick": None,
                    "live_tick": live_tick,
                }
            # Never advertise success if verified tick disagrees with the live boundary
            if result.get("accepted"):
                verified = result.get("final_tick")
                if verified is None or int(verified) != live_tick:
                    result = {
                        "accepted": False,
                        "saved": False,
                        "error": (
                            "persistence_integrity_error: finalize result tick "
                            f"{verified!r} != live stop tick {live_tick}"
                        ),
                        "persistence_integrity_error": True,
                        "live_tick": live_tick,
                        "captured_tick": verified,
                        "persisted_tick": verified,
                        "run_id": run_id,
                        "run_dir": result.get("run_dir"),
                        "termination_reason": "SAVE_FAILED",
                        "phases": list(result.get("phases") or []) + ["post_finalize_tick_guard"],
                        "final_tick": None,
                    }
            self._last_finalize = result
            if result.get("accepted"):
                self._finalize_key = key
                self._termination_reason = str(reason)
                # Critical: release run_id so a later Play→Save cannot reuse the
                # finalized directory as a false idempotent hit at a later tick.
                self._release_run_identity()
            else:
                self._termination_reason = "SAVE_FAILED"
            return result

    def save_job_status(self) -> dict[str, Any]:
        """Layered Save/Stop progress. Compact — never the Observer world graph."""
        job = dict(self._save_job or {})
        thread = self._save_job_thread
        alive = bool(thread is not None and thread.is_alive())
        if self.status == "FINALIZING" and not alive and job.get("finalize") not in {"succeeded", "failed"}:
            # Worker vanished without a terminal status (should not stick forever).
            self.status = "SAVE_FAILED"
            job["finalize"] = "failed"
            job["save"] = "unknown"
            job["error"] = job.get("error") or "finalize worker ended while status was FINALIZING"
            job["lifecycle"] = "SAVE_FAILED"
            self._save_job = job
            if not (self._last_finalize or {}).get("accepted"):
                self._last_finalize = {
                    "accepted": False,
                    "saved": False,
                    "error": job["error"],
                    "termination_reason": "SAVE_FAILED",
                    "final_tick": None,
                }
        fin = self._last_finalize or {}
        save_layer = job.get("save") or (
            "succeeded" if fin.get("accepted") and fin.get("saved")
            else "failed" if fin.get("accepted") is False
            else "not_started"
        )
        return {
            "schema": "mm.psy_observer_web.save_job.v1",
            "job_id": job.get("job_id"),
            "lifecycle": self.status,
            "save": save_layer,
            "finalize": job.get("finalize") or (
                "succeeded" if fin.get("accepted") else "failed" if fin else "not_started"
            ),
            "http": "n/a_server",
            "runtime": {
                "tick": int(self.runtime.tick) if getattr(self, "runtime", None) is not None else None,
                "status": self.status,
                "worker_alive": alive,
            },
            "error": job.get("error") or fin.get("error"),
            "phases": list(fin.get("phases") or job.get("phases") or []),
            "run_dir": fin.get("run_dir") or job.get("run_dir"),
            "final_tick": fin.get("final_tick"),
            "pending": self.status == "FINALIZING",
            "layers": {
                "save": save_layer,
                "finalize": job.get("finalize") or ("pending" if self.status == "FINALIZING" else "idle"),
                "http": "n/a_server",
                "runtime": self.status,
            },
        }

    def _compact_stop_frame(self, *, status: str | None = None) -> dict[str, Any]:
        hdr = {
            "status": status or self.status,
            "tick": int(self.runtime.tick),
            "runtime_generation": int(self._runtime_generation),
            "compact_control": True,
        }
        return {"header": hdr}

    def _mark_save_job(self, **fields: Any) -> None:
        job = dict(self._save_job or {})
        job.update(fields)
        job["lifecycle"] = self.status
        self._save_job = job

    def _begin_save_stop_job(self, *, reason: str | None, before: dict[str, Any]) -> dict[str, Any]:
        request = {"save": True, "reason": reason, "wait": False}
        if self.status == "FINALIZING":
            out = self._with_receipt(
                self._compact_stop_frame(), "STOP", request, before,
                accepted=True, reason="SAVE_STOP_IN_PROGRESS",
            )
            out["finalize"] = {"accepted": None, "pending": True, **(self._last_finalize or {})}
            out["save_job"] = self.save_job_status()
            return out
        if self.status == "STOPPED" and (self._last_finalize or {}).get("accepted"):
            out = self._with_receipt(
                self._compact_stop_frame(status="STOPPED"), "STOP", request, before,
                accepted=True, reason="already STOPPED",
            )
            out["finalize"] = deepcopy(self._last_finalize)
            out["save_job"] = self.save_job_status()
            return out
        job_id = uuid.uuid4().hex[:12]
        self._stop_flag = True
        self.status = "FINALIZING"
        self._save_job = {
            "job_id": job_id,
            "save": "pending",
            "finalize": "pending",
            "phases": ["requested"],
        }
        self._join_runner()
        thread = threading.Thread(
            target=self._save_stop_worker,
            args=(reason or "USER_STOP_SAVED", before, request),
            name="psy-observer-save-stop",
            daemon=False,
        )
        self._save_job_thread = thread
        thread.start()
        out = self._with_receipt(
            self._compact_stop_frame(status="FINALIZING"), "STOP", request, before,
            accepted=True, reason="SAVE_STOP_STARTED",
        )
        out["finalize"] = {"accepted": None, "pending": True, "job_id": job_id}
        out["save_job"] = self.save_job_status()
        self._maybe_push({**self._clone_published(status="FINALIZING"), "save_job": out["save_job"]}, force=True)
        return out

    def _save_stop_worker(self, reason: str, before: dict[str, Any], request: dict[str, Any]) -> None:
        try:
            self._execute_save_stop(reason=reason, before=before, request=request)
        except Exception as exc:
            self.status = "SAVE_FAILED"
            fin = {
                "accepted": False,
                "saved": False,
                "error": str(exc),
                "termination_reason": "SAVE_FAILED",
                "final_tick": None,
            }
            self._last_finalize = fin
            self._mark_save_job(save="failed", finalize="failed", error=str(exc))
            out = self._with_receipt(
                self._clone_published(status="SAVE_FAILED"), "STOP", request, before,
                accepted=False, reason=str(exc),
                error=self._lifecycle_error("STOP", str(exc), code="SAVE_FAILED", recoverable=True),
            )
            out["finalize"] = fin
            out["save_job"] = self.save_job_status()
            self._maybe_push(out, force=True)
        finally:
            if self.status == "FINALIZING":
                self.status = "SAVE_FAILED"
                self._mark_save_job(
                    save="failed",
                    finalize="failed",
                    error="finalize ended still FINALIZING",
                )

    def _execute_save_stop(
        self,
        *,
        reason: str,
        before: dict[str, Any],
        request: dict[str, Any],
    ) -> dict[str, Any]:
        """Synchronous save-stop body. Never returns while status is FINALIZING."""
        term = reason or "USER_STOP_SAVED"
        self._stop_flag = True
        self.status = "FINALIZING"
        self._mark_save_job(finalize="pending", save="pending")
        self._join_runner()
        try:
            with self._step_lock:
                with self._lock:
                    boundary_tick = int(self.runtime.tick)
                    boundary_generation = int(self._runtime_generation)
                    boundary_runtime_type = type(self.runtime).__name__
                    self._capture_locked()
                    if int(self.runtime.tick) != boundary_tick:
                        self.status = "SAVE_FAILED"
                        fin = {
                            "accepted": False,
                            "error": (
                                "persistence_integrity_error: runtime advanced during "
                                f"finalize capture ({boundary_tick} → {self.runtime.tick})"
                            ),
                            "persistence_integrity_error": True,
                            "live_tick": int(self.runtime.tick),
                            "captured_tick": boundary_tick,
                            "termination_reason": "SAVE_FAILED",
                            "final_tick": None,
                        }
                        self._last_finalize = fin
                        self._mark_save_job(save="failed", finalize="failed", error=fin["error"])
                        out = self._with_receipt(
                            self._clone_published(status="SAVE_FAILED"), "STOP", request, before,
                            accepted=False, reason=fin["error"],
                            error=self._lifecycle_error("STOP", fin["error"], code="SAVE_FAILED", recoverable=True),
                        )
                        out["finalize"] = fin
                        out["save_job"] = self.save_job_status()
                        self._maybe_push(out, force=True)
                        return out
            self._mark_save_job(phases=["saving_snapshot"])
            fin = self.finalize_run(reason=term)
            if not fin.get("accepted"):
                self.status = "SAVE_FAILED"
                self._mark_save_job(save="failed", finalize="failed", error=fin.get("error"))
                out = self._with_receipt(
                    self._clone_published(status="SAVE_FAILED"), "STOP", request, before,
                    accepted=False,
                    reason=fin.get("error") or "save failed; runtime preserved",
                    error=self._lifecycle_error(
                        "STOP",
                        fin.get("error") or "save failed; runtime preserved",
                        code="SAVE_FAILED",
                        recoverable=True,
                    ),
                )
                out["finalize"] = fin
                out["save_job"] = self.save_job_status()
                self._maybe_push(out, force=True)
                return out
            verified_tick = int(fin["final_tick"])
            fin_gen = fin.get("runtime_generation")
            if fin_gen is None:
                fin_gen = boundary_generation
            if verified_tick != boundary_tick or int(fin_gen) != boundary_generation:
                self.status = "SAVE_FAILED"
                fin = {
                    **fin,
                    "accepted": False,
                    "error": (
                        "persistence_integrity_error: verified persist boundary "
                        f"(tick={verified_tick}, gen={fin.get('runtime_generation')}) "
                        f"!= stop boundary (tick={boundary_tick}, gen={boundary_generation}, "
                        f"runtime={boundary_runtime_type})"
                    ),
                    "persistence_integrity_error": True,
                    "live_tick": boundary_tick,
                    "captured_tick": verified_tick,
                    "termination_reason": "SAVE_FAILED",
                    "final_tick": None,
                }
                self._last_finalize = fin
                self._mark_save_job(save="failed", finalize="failed", error=fin["error"])
                out = self._with_receipt(
                    self._clone_published(status="SAVE_FAILED"), "STOP", request, before,
                    accepted=False, reason=fin["error"],
                    error=self._lifecycle_error("STOP", fin["error"], code="SAVE_FAILED", recoverable=True),
                )
                out["finalize"] = fin
                out["save_job"] = self.save_job_status()
                self._maybe_push(out, force=True)
                return out
            self.status = "STOPPED"
            self._mark_save_job(save="succeeded", finalize="succeeded", run_dir=fin.get("run_dir"))
            out = self._with_receipt(
                self._clone_published(status="STOPPED"), "STOP", request, before,
                reason=(
                    f"SAVED · t{verified_tick} · verified snapshot tick: {verified_tick} · "
                    f"saved to {fin.get('run_dir')}"
                ),
            )
            out["control_receipt"]["tick"] = verified_tick
            out["control_receipt"]["verified_final_tick"] = verified_tick
            out["finalize"] = fin
            out["save_job"] = self.save_job_status()
            self._maybe_push(out, force=True)
            return out
        finally:
            if self.status == "FINALIZING":
                self.status = "SAVE_FAILED"
                err = "finalize aborted still FINALIZING"
                self._mark_save_job(save="failed", finalize="failed", error=err)
                if not (self._last_finalize or {}).get("accepted"):
                    self._last_finalize = {
                        "accepted": False,
                        "saved": False,
                        "error": err,
                        "termination_reason": "SAVE_FAILED",
                        "final_tick": None,
                    }

    def stop(self, *, save: bool = False, reason: str | None = None, wait: bool = True) -> dict[str, Any]:
        """Stop simulation. save=True → finalize then STOPPED; save=False → STOPPED without artifact.

        wait=False (HTTP Save & Stop): start finalize on a backend thread and return
        immediately so the browser does not hold one fragile fetch across snapshot I/O.
        """
        before = self._control_state()
        request = {"save": bool(save), "reason": reason, "wait": bool(wait)}
        if save and not wait:
            return self._begin_save_stop_job(reason=reason, before=before)

        if self.status == "FINALIZING":
            thread = self._save_job_thread
            if wait and thread is not None and thread.is_alive():
                thread.join(timeout=3600.0)
            fin = deepcopy(self._last_finalize) if self._last_finalize else {
                "accepted": False, "reason": "finalization in progress",
            }
            pending = self.status == "FINALIZING" and not fin.get("accepted")
            out = self._with_receipt(
                self._clone_published(status=self.status), "STOP",
                request, before,
                accepted=True if pending else bool(fin.get("accepted")),
                reason="SAVE_STOP_IN_PROGRESS" if pending else "idempotent finalize while FINALIZING",
                error=(
                    None if pending or fin.get("accepted")
                    else self._lifecycle_error(
                        "STOP",
                        fin.get("error") or "idempotent finalize while FINALIZING",
                        code="SAVE_FAILED" if self.status == "SAVE_FAILED" else "INVALID_TRANSITION",
                    )
                ),
            )
            if not (pending or fin.get("accepted")):
                out["control_receipt"]["accepted"] = False
                out["control_receipt"]["ok"] = False
            if fin.get("final_tick") is not None:
                out["control_receipt"]["tick"] = int(fin["final_tick"])
                out["control_receipt"]["verified_final_tick"] = int(fin["final_tick"])
            out["finalize"] = fin
            out["save_job"] = self.save_job_status()
            return out

        if save:
            return self._execute_save_stop(
                reason=reason or "USER_STOP_SAVED",
                before=before,
                request=request,
            )

        term = reason or "USER_STOP_NO_SAVE"
        self.status = "STOPPED"
        self._stop_flag = True
        self._join_runner()
        self._termination_reason = term
        self._finalize_key = None
        self._release_run_identity()
        out = self._with_receipt(
            self._clone_published(status="STOPPED"), "STOP", request, before,
            reason="stopped without saving",
        )
        out["finalize"] = {
            "accepted": True,
            "saved": False,
            "termination_reason": term,
            "run_dir": None,
        }
        out["save_job"] = self.save_job_status()
        self._maybe_push(out, force=True)
        return out

    def step(self, n: int = 1) -> dict[str, Any]:
        before = self._control_state()
        if self.status == "FINALIZING":
            return self._with_receipt(
                self._clone_published(), "STEP", {"n": int(n)}, before,
                accepted=False, reason="finalization in progress",
            )
        blocked = self._require_preflight_ready("STEP", before, {"n": int(n)})
        if blocked is not None:
            return blocked
        if self._run_started_at is None:
            self._run_started_at = datetime.now(timezone.utc).isoformat()
            self._active_run_id = new_run_id()
            if self._runtime_mechanism_manifest is not None:
                self._runtime_mechanism_manifest = dict(self._runtime_mechanism_manifest)
                self._runtime_mechanism_manifest["run_id"] = self._active_run_id
        self.mode = "LIVE"
        self.inspect_tick = None
        self.status = "PAUSED"
        with self._step_lock:
            with self._lock:
                self._ensure_scientific_locked()
            for _ in range(max(1, int(n))):
                if self.config.target_tick is not None and self.runtime.tick >= int(self.config.target_tick):
                    break
                self._scientific_step_once_unlocked()
                with self._lock:
                    self._accumulate_events_locked()
                    self._record_motion_locked()
                    self._append_scientific_locked()
                    self._update_perf_locked(tick=True)
                    self._maybe_checkpoint_locked()
            with self._lock:
                if str(self.config.execution_mode or "LIVE").upper() == "HEADLESS":
                    frame = self._stub_header_frame()
                else:
                    _det = "full" if self._observer_interest.preset == "FULL" else "compact"
                    frame = self._capture_locked(detail=_det)
        out = self._with_receipt(frame, "STEP", {"n": int(n)}, before)
        out["preflight"] = self._preflight_result
        out["mechanism_integrity"] = self.mechanism_integrity_status()
        self._maybe_push(out, force=True)
        return out

    def _scientific_step_once_unlocked(self) -> None:
        """One scientific tick with experimenter pre/post hooks (caller holds step_lock)."""
        from mechanistic_mind.research.tick_profiler import span as _prof_span

        self._tick_in_progress = True
        self._tick_started_mono = time.monotonic()
        try:
            with _prof_span("experimenter_pre"):
                self._experimenter_pre_step_unlocked()
            with _prof_span("sim"):
                self.runtime.step(1)
            with _prof_span("experimenter_post"):
                self._experimenter_post_step_unlocked()
        finally:
            self._last_tick_wall_ms = (time.monotonic() - self._tick_started_mono) * 1000.0
            self._last_tick_completed_mono = time.monotonic()
            self._tick_in_progress = False
        # Safe boundary: apply deferred LIVE mechanism/vision requests before next tick.
        from mechanistic_mind.research.tick_profiler import span as _prof_span

        with _prof_span("live_apply_queue"):
            self._drain_live_apply_queue_unlocked()

    def set_live_interpreters(
        self,
        *,
        geometry: bool | None = None,
        signal_context: bool | None = None,
    ) -> dict[str, Any]:
        """Enable/disable LIVE GEO/SIGINT processing (Observer-only; for perf matrix)."""
        with self._lock:
            if geometry is not None:
                self._geo_live_enabled = bool(geometry)
            if signal_context is not None:
                self._sig_live_enabled = bool(signal_context)
            return {
                "accepted": True,
                "geo_live_enabled": self._geo_live_enabled,
                "sig_live_enabled": self._sig_live_enabled,
            }

    def set_speed(self, speed: float) -> dict[str, Any]:
        before = self._control_state()
        # Wall-clock throttle only. Floor 0.01x for human observation (~0.4 t/s target).
        self.config.speed = float(max(0.01, min(MAX_SPEED, speed)))
        # Recapture so header.simulation_speed matches config immediately.
        # While RUNNING, use the same compact detail as async capture so SET_SPEED
        # does not temporarily publish a richer schema that disappears on the next
        # ordinary compact frame (pipeline NOT AVAILABLE flicker).
        detail = self._frame_detail_for_speed()
        with self._step_lock:
            with self._lock:
                frame = self._capture_locked(detail=detail)
        out = self._with_receipt(
            frame, "SET_SPEED", {"speed": float(self.config.speed)}, before,
            reason=(
                f"wall-clock throttle only; 1x period={BASE_TICK_PERIOD_1X}s; "
                f"MAX={MAX_SPEED}; scientific ticks never skipped; frame_detail={detail}"
            ),
        )
        self._maybe_push(out, force=True)
        return out

    def set_execution_mode(self, mode: str, *, target_tick: int | None = None) -> dict[str, Any]:
        """Set LIVE/FAST/MAX/HEADLESS presentation policy without changing science.

        Same simulated ticks; only wall-clock throttle + observer sample cadence +
        whether live presentation capture runs.
        """
        before = self._control_state()
        key = str(mode or "LIVE").strip().upper()
        if key not in EXECUTION_MODE_PRESETS:
            return self._with_receipt(
                self._clone_published(),
                "SET_EXECUTION_MODE",
                {"mode": mode},
                before,
                accepted=False,
                reason=f"unknown execution_mode; allowed={sorted(EXECUTION_MODE_PRESETS)}",
            )
        preset = EXECUTION_MODE_PRESETS[key]
        self.config.execution_mode = key
        self.config.speed = float(preset["speed"])
        self.config.ui_hz = float(preset["ui_hz"])
        if target_tick is not None:
            self.config.target_tick = int(target_tick) if int(target_tick) > 0 else None
        detail = self._frame_detail_for_speed()
        with self._step_lock:
            with self._lock:
                frame = self._capture_locked(detail=detail)
        out = self._with_receipt(
            frame,
            "SET_EXECUTION_MODE",
            {
                "mode": key,
                "speed": float(self.config.speed),
                "ui_hz": float(self.config.ui_hz),
                "observer_hz": float(self.config.ui_hz),
                "target_tick": self.config.target_tick,
                "capture": bool(preset["capture"]),
            },
            before,
            reason=(
                "presentation policy only; scientific ticks never skipped; "
                "dt/physics/cognition unchanged"
            ),
        )
        self._maybe_push(out, force=True)
        return out

    def set_target_tick(self, target_tick: int | None) -> dict[str, Any]:
        before = self._control_state()
        self.config.target_tick = (
            int(target_tick) if target_tick is not None and int(target_tick) > 0 else None
        )
        with self._step_lock:
            with self._lock:
                frame = self._capture_locked(detail=self._frame_detail_for_speed())
        out = self._with_receipt(
            frame, "SET_TARGET_TICK", {"target_tick": self.config.target_tick}, before,
        )
        self._maybe_push(out, force=True)
        return out

    def set_evidence_mode(self, mode: str) -> dict[str, Any]:
        """FULL_SCIENTIFIC vs SEARCH_COMPACT — evidence notebook only, not physics."""
        before = self._control_state()
        key = str(mode or "FULL_SCIENTIFIC").strip().upper()
        allowed = {"FULL_SCIENTIFIC", "SEARCH_COMPACT"}
        if key not in allowed:
            return self._with_receipt(
                self._clone_published(),
                "SET_EVIDENCE_MODE",
                {"mode": mode},
                before,
                accepted=False,
                reason=f"unknown evidence_mode; allowed={sorted(allowed)}",
            )
        # Switching mid-run closes current writer; next scientific tick opens new policy.
        with self._lock:
            self._close_scientific_locked(clear_live_dir=False)
            self.config.evidence_mode = key
        with self._step_lock:
            with self._lock:
                frame = self._capture_locked(detail=self._frame_detail_for_speed())
        out = self._with_receipt(
            frame,
            "SET_EVIDENCE_MODE",
            {
                "mode": key,
                "note": (
                    "COMPACT EVIDENCE — same organism/world; bounded notebook only"
                    if key == "SEARCH_COMPACT"
                    else "full scientific evidence retained"
                ),
            },
            before,
            reason="evidence capture policy only; runtime dynamics unchanged",
        )
        self._maybe_push(out, force=True)
        return out

    def set_observer_hz(self, hz: float) -> dict[str, Any]:
        """Observer sample rate only — does not change simulation tick rate."""
        before = self._control_state()
        self.config.ui_hz = float(max(0.1, min(60.0, hz)))
        with self._step_lock:
            with self._lock:
                frame = self._capture_locked(detail=self._frame_detail_for_speed())
        out = self._with_receipt(
            frame,
            "SET_OBSERVER_HZ",
            {"observer_hz": float(self.config.ui_hz)},
            before,
            reason="observer sample Hz only; simulation tick rate independent",
        )
        self._maybe_push(out, force=True)
        return out

    def select_agent(self, index: int) -> dict[str, Any]:
        """Observer slot selection. Technical IDs only; not cognition input.

        Must not advance tick, mutate agent cognition, RNG, learning, or physics.
        """
        before = self._control_state()
        rt = self.runtime
        tick_before = int(rt.tick)
        if not hasattr(rt, "select_agent"):
            return self._with_receipt(
                self._clone_published(), "SELECT_AGENT", {"index": index},
                before, accepted=False, reason="single-agent runtime",
            )
        # Snapshot scientific state fingerprint before selection
        slots = getattr(rt, "slots", None) or []
        pre = [
            (
                int(s.tick),
                float(s.body.x),
                float(s.body.y),
                s.last_selected_action,
                id(s.cognition),
            )
            for s in slots
        ]
        chosen = rt.select_agent(int(index))
        post = [
            (
                int(s.tick),
                float(s.body.x),
                float(s.body.y),
                s.last_selected_action,
                id(s.cognition),
            )
            for s in slots
        ]
        if pre != post or int(rt.tick) != tick_before:
            return self._with_receipt(
                self._clone_published(), "SELECT_AGENT", {"index": index},
                before, accepted=False,
                reason="select_agent mutated scientific runtime state — refused",
            )
        with self._lock:
            frame = self._capture_locked()
        out = self._with_receipt(
            frame, "SELECT_AGENT",
            {"index": chosen, "selected_agent_id": f"agent_{chosen}"},
            before,
        )
        out["control_receipt"]["selected_agent_id"] = f"agent_{chosen}"
        out["control_receipt"]["tick"] = tick_before
        self._maybe_push(out, force=True)
        return out

    def set_ablations(self, **flags: bool) -> dict[str, Any]:
        before = self._control_state()
        with self._step_lock:
            self.runtime.set_ablations(**flags)
            with self._lock:
                frame = self._capture_locked()
                snap = self.runtime.mechanisms()
        out = self._with_receipt(frame, "SET_ABLATIONS", dict(flags), before)
        out["mechanism_result"] = snap
        self._maybe_push(out, force=True)
        return out

    def set_psc_motor_resolution(self, mode: str) -> dict[str, Any]:
        """Observer control: PSC MOTOR RESOLUTION (LOCO_FACTORIZED | OBSERVED_COMPOSITE).

        Does not reset history/SMC/body. Records config intervention.
        """
        before = self._control_state() if hasattr(self, "_control_state") else {}
        rt = self.runtime
        if hasattr(rt, "set_psc_motor_resolution"):
            result = rt.set_psc_motor_resolution(mode)
        else:
            result = {"accepted": False, "reason": "runtime_unsupported"}
        # config history on session
        ch = getattr(self, "_config_history", None)
        if not isinstance(ch, list):
            ch = []
            self._config_history = ch
        ch.append({
            "tick": int(getattr(rt, "tick", 0) or 0),
            "field": "psc_motor_resolution",
            "result": result,
            "history_reset": False,
            "cognition_reset": False,
            "smc_reset": False,
            "body_reset": False,
        })
        out = {"ok": bool(result.get("accepted")), **result, "before": before}
        return out

    def set_mechanism(self, mechanism_id: str, enabled: bool) -> dict[str, Any]:
        """LIVE mechanism toggle.

        When RUNNING and a tick currently holds `_step_lock`, queue the change and
        return immediately with WAITING_FOR_TICK_BOUNDARY (never multi-minute HTTP stall).
        Applied at the next tick boundary; no mid-tick mutation.
        """
        before = self._control_state()
        request = {"mechanism_id": mechanism_id, "enabled": enabled}
        if self.status == "RUNNING":
            got = self._step_lock.acquire(blocking=False)
            if not got:
                previous = self.runtime.mechanisms()
                item = next(
                    (m for m in previous.get("mechanisms", []) if m.get("id") == mechanism_id),
                    None,
                )
                if item is None:
                    return self._with_receipt(
                        self._clone_published(), "TOGGLE_MECHANISM", request,
                        before, accepted=False, reason="unknown mechanism",
                    )
                if not item.get("ablatable", True):
                    return self._with_receipt(
                        self._clone_published(), "TOGGLE_MECHANISM", request,
                        before, accepted=False, reason="mechanism is read-only / not ablatable",
                    )
                if bool(item.get("enabled")) == bool(enabled):
                    out = self._with_receipt(
                        self._clone_published(), "TOGGLE_MECHANISM",
                        {**request, "live": True, "noop": True}, before,
                    )
                    out["mechanism_result"] = previous
                    out["toggle_runtime_applied"] = True
                    return out
                req = self._enqueue_live_apply(
                    "mechanism",
                    {"mechanism_id": str(mechanism_id), "enabled": bool(enabled)},
                )
                out = self._with_receipt(
                    self._clone_published(),
                    "TOGGLE_MECHANISM",
                    {**request, "live": True, "deferred": True},
                    before,
                    accepted=True,
                    reason="WAITING_FOR_TICK_BOUNDARY",
                )
                out["pending_live_apply"] = req
                out["toggle_runtime_applied"] = False
                out["mechanism_result"] = previous
                out["integrity_status"] = "PENDING_APPLY"
                return out
            try:
                return self._apply_mechanism_now_unlocked(str(mechanism_id), bool(enabled), before=before)
            finally:
                self._step_lock.release()
        with self._step_lock:
            return self._apply_mechanism_now_unlocked(str(mechanism_id), bool(enabled), before=before)

    def _apply_mechanism_now_unlocked(
        self,
        mechanism_id: str,
        enabled: bool,
        *,
        before: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Apply mechanism toggle under `_step_lock` (safe tick boundary / paused)."""
        if before is None:
            before = self._control_state()
        request = {"mechanism_id": mechanism_id, "enabled": enabled}
        previous = self.runtime.mechanisms()
        item = next(
            (m for m in previous.get("mechanisms", []) if m.get("id") == mechanism_id),
            None,
        )
        if item is None:
            return self._with_receipt(
                self._clone_published(), "TOGGLE_MECHANISM", request,
                before, accepted=False, reason="unknown mechanism",
            )
        if not item.get("ablatable", True):
            return self._with_receipt(
                self._clone_published(), "TOGGLE_MECHANISM", request,
                before, accepted=False, reason="mechanism is read-only / not ablatable",
            )
        old_en = bool(item.get("enabled"))
        if old_en == bool(enabled):
            with self._lock:
                frame = self._capture_locked()
            out = self._with_receipt(
                frame, "TOGGLE_MECHANISM",
                {"mechanism_id": mechanism_id, "enabled": bool(enabled), "live": True, "noop": True},
                before,
            )
            out["mechanism_result"] = previous
            out["toggle_runtime_applied"] = True
            self._maybe_push(out, force=True)
            return out
        from mechanistic_mind.ui.psy_observer_web.live_intervention import fingerprint_for_runtime
        fp_before = fingerprint_for_runtime(self.runtime)
        snap = self.runtime.set_mechanism(mechanism_id, bool(enabled))
        if str(mechanism_id) == "prospective_scenario_competition" and bool(enabled):
            if getattr(self, "_psc_enabled_after_ticks", None) is None:
                try:
                    self._psc_enabled_after_ticks = int(getattr(self.runtime, "tick", 0) or 0)
                except Exception:
                    self._psc_enabled_after_ticks = None
        from mechanistic_mind.physical_system.mechanism_configuration import (
            ResolvedMechanismConfig,
            build_runtime_manifest,
            run_preflight,
        )
        prev_res = self._resolved_mechanism_config
        if prev_res is not None:
            resolved = ResolvedMechanismConfig(
                mechanisms=dict(prev_res.mechanisms),
                params=dict(prev_res.params),
                provenance=dict(prev_res.provenance),
                version=prev_res.version,
                source="LIVE_INTERVENTION",
            )
        else:
            en = dict(snap.get("enabled") or {})
            resolved = ResolvedMechanismConfig(
                mechanisms={k: bool(v) for k, v in en.items()},
                params={},
                provenance={k: "RUNTIME" for k in en},
                source="LIVE_INTERVENTION",
            )
        resolved.mechanisms[str(mechanism_id)] = bool(enabled)
        resolved.provenance[str(mechanism_id)] = "EXPLICIT"
        planet = getattr(getattr(self.runtime, "config", None), "planet", None)
        te = getattr(planet, "terrain", None) if planet else None
        amb = getattr(planet, "ambient", None) if planet else None
        resolved.mechanisms["terrain_geography"] = bool(getattr(te, "enabled", False)) if te else False
        resolved.mechanisms["ambient_physical_dynamics"] = bool(getattr(amb, "enabled", False)) if amb else False
        preflight = run_preflight(self.runtime, resolved)
        self._resolved_mechanism_config = resolved
        self._preflight_result = preflight.to_dict()
        if preflight.status == "READY":
            self._runtime_mechanism_manifest = build_runtime_manifest(
                runtime=self.runtime,
                resolved=resolved,
                preflight=preflight,
                run_id=self._active_run_id,
                generation=self._runtime_generation,
            )
        self._record_live_intervention_locked(
            category="mechanism",
            changes={
                f"mechanism.{mechanism_id}": {"old": old_en, "new": bool(enabled)},
            },
            fingerprint_before=fp_before,
            source="api/mechanisms",
        )
        self._sync_canonical_mechanism(str(mechanism_id), bool(enabled))
        with self._lock:
            frame = self._capture_locked()
        out = self._with_receipt(
            frame, "TOGGLE_MECHANISM",
            {"mechanism_id": mechanism_id, "enabled": bool(enabled), "live": True},
            before,
            requires_reset=item.get("toggle_policy") == "RESET_REQUIRED",
            reason=(
                "state history is retained; reset recommended for matched comparisons"
                if item.get("toggle_policy") == "RESET_RECOMMENDED" else None
            ),
        )
        out["mechanism_result"] = snap
        out["preflight"] = self._preflight_result
        out["mechanism_integrity"] = self.mechanism_integrity_status()
        item_after = next(
            (m for m in (snap.get("mechanisms") or []) if m.get("id") == mechanism_id),
            None,
        )
        runtime_matches = bool(item_after and bool(item_after.get("enabled")) == bool(enabled))
        out["toggle_runtime_applied"] = runtime_matches
        if not runtime_matches or (self._preflight_result or {}).get("status") != "READY":
            out["integrity_status"] = "MISMATCH"
        else:
            out["integrity_status"] = "READY"
        out["dependency_warnings"] = [
            {
                "mechanism_id": mechanism_id,
                "dependency": dep,
                "message": "No automatic cascade; existing state is retained.",
            }
            for dep in item.get("dependencies", [])
        ]
        self._maybe_push(out, force=True)
        return out

    def set_vision_radius(self, radius: int) -> dict[str, Any]:
        """LIVE physical vision Moore radius R∈{1,2,3}. No world/cognition/history reset."""
        from mechanistic_mind.physical_system.near_field_exteroception import (
            clamp_vision_radius,
        )
        before = self._control_state()
        new = clamp_vision_radius(radius)
        request = {"radius": new, "path": "physical_near_field_vision.radius"}
        if self.status == "RUNNING":
            got = self._step_lock.acquire(blocking=False)
            if not got:
                req = self._enqueue_live_apply("vision_radius", {"radius": int(new)})
                out = self._with_receipt(
                    self._clone_published(),
                    "SET_VISION_RADIUS",
                    {**request, "live": True, "deferred": True},
                    before,
                    accepted=True,
                    reason="WAITING_FOR_TICK_BOUNDARY",
                )
                out["pending_live_apply"] = req
                out["vision_radius"] = {"accepted": True, "pending": True, "new": int(new)}
                return out
            try:
                return self._apply_vision_radius_now_unlocked(int(new), before=before)
            finally:
                self._step_lock.release()
        with self._step_lock:
            return self._apply_vision_radius_now_unlocked(int(new), before=before)

    def _apply_vision_radius_now_unlocked(
        self,
        radius: int,
        *,
        before: dict | None = None,
    ) -> dict[str, Any]:
        """Apply vision radius under `_step_lock`."""
        from mechanistic_mind.physical_system.near_field_exteroception import (
            DEFAULT_VISION_RADIUS,
            clamp_vision_radius,
            moore_max_candidates,
        )
        from mechanistic_mind.ui.psy_observer_web.live_intervention import fingerprint_for_runtime

        if before is None:
            before = self._control_state()
        new = clamp_vision_radius(radius)
        request = {"radius": new, "path": "physical_near_field_vision.radius"}
        # Read current radius from primary config
        nfe = None
        slots = getattr(self.runtime, "slots", None)
        if slots:
            nfe = getattr(slots[0].config, "near_field_exteroception", None)
        else:
            nfe = getattr(getattr(self.runtime, "config", None), "near_field_exteroception", None)
        old = clamp_vision_radius(getattr(nfe, "radius", DEFAULT_VISION_RADIUS) if nfe else DEFAULT_VISION_RADIUS)
        if old == new:
            with self._lock:
                frame = self._capture_locked()
            out = self._with_receipt(
                frame, "SET_VISION_RADIUS",
                {**request, "old": old, "new": new, "live": True, "noop": True},
                before,
            )
            out["vision_radius"] = {"accepted": True, "old": old, "new": new, "noop": True}
            self._maybe_push(out, force=True)
            return out
        fp_before = fingerprint_for_runtime(self.runtime)
        snap = self.runtime.set_vision_radius(new)
        self._sync_canonical_vision(radius=new)
        # Keep resolved CONFIG authority aligned with LIVE runtime radius
        # so preflight does not report CONFIG R≠RUNTIME R after a valid set.
        from mechanistic_mind.physical_system.mechanism_configuration import (
            ResolvedMechanismConfig,
            build_runtime_manifest,
            run_preflight,
        )
        prev_res = self._resolved_mechanism_config
        if prev_res is not None:
            resolved = ResolvedMechanismConfig(
                mechanisms=dict(prev_res.mechanisms),
                params=dict(prev_res.params),
                provenance=dict(prev_res.provenance),
                version=prev_res.version,
                source="LIVE_INTERVENTION",
            )
        else:
            resolved = ResolvedMechanismConfig(
                mechanisms={"physical_near_field_vision": True},
                params={"vision_radius": new},
                provenance={"vision_radius": "EXPLICIT", "physical_near_field_vision": "RUNTIME"},
                source="LIVE_INTERVENTION",
            )
        resolved.params["vision_radius"] = int(new)
        resolved.provenance["vision_radius"] = "EXPLICIT"
        preflight = run_preflight(self.runtime, resolved)
        self._resolved_mechanism_config = resolved
        self._preflight_result = preflight.to_dict()
        if preflight.status == "READY":
            self._runtime_mechanism_manifest = build_runtime_manifest(
                runtime=self.runtime,
                resolved=resolved,
                preflight=preflight,
                run_id=self._active_run_id,
                generation=self._runtime_generation,
            )
        # Always record radius change even if fingerprint helpers lag (explicit path).
        ev = self._record_live_intervention_locked(
            category="sensor",
            changes={
                "physical_near_field_vision.radius": {"old": old, "new": new},
            },
            fingerprint_before=fp_before,
            source="api/vision/radius",
        )
        if ev is None:
            # Fingerprint unchanged (should not happen once radius is in eff config) —
            # still emit an explicit intervention for Analyzer regime boundaries.
            from mechanistic_mind.ui.psy_observer_web.live_intervention import (
                build_world_intervention_event,
                fingerprint_for_runtime as fp_rt,
            )
            fp_after = fp_rt(self.runtime)
            ev = build_world_intervention_event(
                simulation_tick=int(getattr(self.runtime, "tick", 0) or 0),
                runtime_generation=int(self._runtime_generation),
                session_instance_id=self._session_instance_id(),
                category="sensor",
                changes={"physical_near_field_vision.radius": {"old": old, "new": new}},
                fingerprint_before=fp_before,
                fingerprint_after=fp_after or fp_before + f"|radius={new}",
                history_reset=False,
                cognition_reset=False,
                body_reset=False,
                source="api/vision/radius",
                extra={
                    "reset": {
                        "world": False,
                        "body": False,
                        "cognition": False,
                        "history": False,
                    },
                },
            )
            self._world_interventions.append(ev)
            try:
                self._event_ring.append(ev)
            except Exception:
                pass
        with self._lock:
            frame = self._capture_locked()
        out = self._with_receipt(
            frame, "SET_VISION_RADIUS",
            {
                **request,
                "old": old,
                "new": new,
                "live": True,
                "max_candidates": moore_max_candidates(new),
                "requires_reset": False,
            },
            before,
            requires_reset=False,
            reason="physical candidate neighborhood only; existing FOV/distance/illumination filters unchanged",
        )
        out["vision_radius"] = snap
        out["intervention"] = ev
        out["preflight"] = self._preflight_result
        out["mechanism_integrity"] = self.mechanism_integrity_status()
        self._maybe_push(out, force=True)
        return out

    def set_visual_surface_discrimination(self, mode: str) -> dict[str, Any]:
        """LIVE OFF/LOW/RICH. No world/cognition/history reset."""
        from mechanistic_mind.physical_system.near_field_exteroception import (
            clamp_surface_discrimination,
        )
        before = self._control_state()
        new = clamp_surface_discrimination(mode)
        request = {"mode": new, "path": "near_field_exteroception.visual_surface_discrimination"}
        if self.status == "RUNNING":
            got = self._step_lock.acquire(blocking=False)
            if not got:
                req = self._enqueue_live_apply("visual_surface_discrimination", {"mode": new})
                out = self._with_receipt(
                    self._clone_published(),
                    "SET_SURFACE_DISCRIMINATION",
                    {**request, "live": True, "deferred": True},
                    before,
                    accepted=True,
                    reason="WAITING_FOR_TICK_BOUNDARY",
                )
                out["pending_live_apply"] = req
                out["visual_surface_discrimination"] = {"accepted": True, "pending": True, "new": new}
                return out
            try:
                return self._apply_surface_discrimination_now_unlocked(new, before=before)
            finally:
                self._step_lock.release()
        with self._step_lock:
            return self._apply_surface_discrimination_now_unlocked(new, before=before)

    def _apply_surface_discrimination_now_unlocked(
        self,
        mode: str,
        *,
        before: dict | None = None,
    ) -> dict[str, Any]:
        from mechanistic_mind.physical_system.near_field_exteroception import (
            clamp_surface_discrimination,
        )
        if before is None:
            before = self._control_state()
        new = clamp_surface_discrimination(mode)
        nfe = None
        slots = getattr(self.runtime, "slots", None)
        if slots:
            nfe = getattr(slots[0].config, "near_field_exteroception", None)
        else:
            nfe = getattr(getattr(self.runtime, "config", None), "near_field_exteroception", None)
        old = clamp_surface_discrimination(
            getattr(nfe, "visual_surface_discrimination", "OFF") if nfe else "OFF"
        )
        request = {"mode": new, "path": "near_field_exteroception.visual_surface_discrimination"}
        if old == new:
            with self._lock:
                frame = self._capture_locked()
            out = self._with_receipt(
                frame, "SET_SURFACE_DISCRIMINATION",
                {**request, "old": old, "new": new, "live": True, "noop": True},
                before,
            )
            out["visual_surface_discrimination"] = {"accepted": True, "old": old, "new": new, "noop": True}
            self._maybe_push(out, force=True)
            return out
        snap = self.runtime.set_visual_surface_discrimination(new)
        self._sync_canonical_vision(visual_surface_discrimination=new)
        with self._lock:
            frame = self._capture_locked()
        out = self._with_receipt(
            frame, "SET_SURFACE_DISCRIMINATION",
            {**request, "old": old, "new": new, "live": True, "requires_reset": False},
            before,
            requires_reset=False,
            reason="FOV-gated optical channels only; physics/history/cognition not reset",
        )
        out["visual_surface_discrimination"] = snap
        self._maybe_push(out, force=True)
        return out

    def set_optical_mapping(self, mode: str) -> dict[str, Any]:
        """LIVE optical mapping. Regenerates WORLD optical tensor; no tick/history reset."""
        from mechanistic_mind.physical_system.near_field_exteroception import clamp_optical_mapping

        before = self._control_state()
        new = clamp_optical_mapping(mode)
        request = {"mode": new, "path": "near_field_exteroception.optical_mapping"}
        if self.status == "RUNNING":
            got = self._step_lock.acquire(blocking=False)
            if not got:
                req = self._enqueue_live_apply("optical_mapping", {"mode": new})
                out = self._with_receipt(
                    self._clone_published(),
                    "SET_OPTICAL_MAPPING",
                    {**request, "live": True, "deferred": True},
                    before,
                    accepted=True,
                    reason="WAITING_FOR_TICK_BOUNDARY",
                )
                out["pending_live_apply"] = req
                out["optical_mapping"] = {"accepted": True, "pending": True, "new": new}
                return out
            try:
                return self._apply_optical_mapping_now_unlocked(new, before=before)
            finally:
                self._step_lock.release()
        with self._step_lock:
            return self._apply_optical_mapping_now_unlocked(new, before=before)

    def _apply_optical_mapping_now_unlocked(
        self, mode: str, *, before: dict | None = None,
    ) -> dict[str, Any]:
        from mechanistic_mind.physical_system.near_field_exteroception import clamp_optical_mapping

        if before is None:
            before = self._control_state()
        new = clamp_optical_mapping(mode)
        request = {"mode": new, "path": "near_field_exteroception.optical_mapping"}
        snap = self.runtime.set_optical_mapping(new)
        self._sync_canonical_vision(optical_mapping=new)
        with self._lock:
            frame = self._capture_locked()
        out = self._with_receipt(
            frame, "SET_OPTICAL_MAPPING",
            {**request, "live": True, "world_optical_regenerated": bool(snap.get("world_optical_regenerated"))},
            before,
            requires_reset=False,
            reason="WORLD optical appearance regenerated; cognition/history not reset",
        )
        out["optical_mapping"] = snap
        self._maybe_push(out, force=True)
        return out

    def set_spatial_vision(self, mode: str) -> dict[str, Any]:
        """LIVE LEGACY | ANGULAR | OCCLUSION | TEMPORAL_SPATIAL. No tick/history reset."""
        from mechanistic_mind.physical_system.near_field_exteroception import clamp_spatial_vision

        before = self._control_state()
        new = clamp_spatial_vision(mode)
        request = {"mode": new, "path": "near_field_exteroception.spatial_vision"}
        if self.status == "RUNNING":
            got = self._step_lock.acquire(blocking=False)
            if not got:
                req = self._enqueue_live_apply("spatial_vision", {"mode": new})
                out = self._with_receipt(
                    self._clone_published(),
                    "SET_SPATIAL_VISION",
                    {**request, "live": True, "deferred": True},
                    before,
                    accepted=True,
                    reason="WAITING_FOR_TICK_BOUNDARY",
                )
                out["pending_live_apply"] = req
                out["spatial_vision"] = {"accepted": True, "pending": True, "new": new}
                return out
            try:
                return self._apply_spatial_vision_now_unlocked(new, before=before)
            finally:
                self._step_lock.release()
        with self._step_lock:
            return self._apply_spatial_vision_now_unlocked(new, before=before)

    def _apply_spatial_vision_now_unlocked(
        self, mode: str, *, before: dict | None = None,
    ) -> dict[str, Any]:
        from mechanistic_mind.physical_system.near_field_exteroception import clamp_spatial_vision

        if before is None:
            before = self._control_state()
        new = clamp_spatial_vision(mode)
        request = {"mode": new, "path": "near_field_exteroception.spatial_vision"}
        snap = self.runtime.set_spatial_vision(new)
        self._sync_canonical_vision(spatial_vision=new)
        with self._lock:
            frame = self._capture_locked()
        out = self._with_receipt(
            frame, "SET_SPATIAL_VISION",
            {**request, "live": True, "history_reset": False},
            before,
            requires_reset=False,
            reason="Sensor geometry bins/occlusion only; physics/history/cognition not reset",
        )
        out["spatial_vision"] = snap
        self._maybe_push(out, force=True)
        return out

    def set_psc_off_ticks(self, value: Any) -> dict[str, Any]:
        """MANUAL / 0 / 1000 / 5000 / CUSTOM. Does not reset history."""
        parsed: int | None
        if value is None or str(value).strip().upper() in {"MANUAL", "NONE", ""}:
            parsed = None
        else:
            parsed = max(0, int(value))
        before = self._control_state()
        if self.status == "RUNNING":
            got = self._step_lock.acquire(blocking=False)
            if not got:
                req = self._enqueue_live_apply("psc_off_ticks", {"value": parsed})
                out = self._with_receipt(
                    self._clone_published(),
                    "SET_PSC_OFF_TICKS",
                    {"value": parsed, "live": True, "deferred": True},
                    before,
                    accepted=True,
                    reason="WAITING_FOR_TICK_BOUNDARY",
                )
                out["pending_live_apply"] = req
                return out
            try:
                return self._apply_psc_off_ticks_now_unlocked(parsed, before=before)
            finally:
                self._step_lock.release()
        with self._step_lock:
            return self._apply_psc_off_ticks_now_unlocked(parsed, before=before)

    def _apply_psc_off_ticks_now_unlocked(
        self, value: int | None, *, before: dict | None = None,
    ) -> dict[str, Any]:
        if before is None:
            before = self._control_state()
        snap = self.runtime.set_psc_off_ticks(value)
        with self._lock:
            frame = self._capture_locked()
        from .tiktaalik_eye import psc_off_ticks_status

        status = psc_off_ticks_status(self.runtime)
        out = self._with_receipt(
            frame, "SET_PSC_OFF_TICKS",
            {"value": value, "live": True, "history_reset": False},
            before,
            requires_reset=False,
            reason="PSC auto-ON schedule only; history preserved",
        )
        out["psc_off_ticks"] = snap
        out["psc_schedule"] = status
        self._maybe_push(out, force=True)
        return out

    def tiktaalik_eye_status(self) -> dict[str, Any]:
        from .tiktaalik_eye import psc_off_ticks_status

        return {
            "rate": self._eye_rate,
            "geometry_debug": bool(self._eye_geometry_debug),
            "fpv": bool(self._eye_fpv_visible),
            "update_count": int(self._eye_update_count),
            "last_build_ms": float(self._eye_last_build_ms),
            "payload_bytes": int((self._eye_last_payload or {}).get("payload_bytes") or 0),
            "psc_schedule": psc_off_ticks_status(self.runtime),
            "observer_only": True,
            "feeds_cognition": False,
        }

    def set_tiktaalik_eye(
        self,
        *,
        rate: str | None = None,
        geometry_debug: bool | None = None,
        fpv: bool | None = None,
    ) -> dict[str, Any]:
        from .tiktaalik_eye import clamp_eye_rate

        if rate is not None:
            self._eye_rate = clamp_eye_rate(rate)
            if self._eye_rate == "OFF":
                self._eye_last_payload = None
                self._eye_prev_fpv = {}
                self._eye_prev_visual = {}
        if geometry_debug is not None:
            self._eye_geometry_debug = bool(geometry_debug)
        if fpv is not None:
            self._eye_fpv_visible = bool(fpv)
            self._eye_force_snapshot = True
            self._eye_last_wall = 0.0
            self._eye_last_tick = -1
        if self._eye_rate == "SNAPSHOT":
            self._eye_force_snapshot = True
        snap = self.tiktaalik_eye_status()
        if self._eye_rate != "OFF":
            with self._lock:
                frame = self._capture_locked()
            self._maybe_push(frame, force=True)
            snap["frame_tick"] = (frame.get("header") or {}).get("tick")
            snap["tiktaalik_eye"] = frame.get("tiktaalik_eye")
        return snap

    def _attach_tiktaalik_eye_locked(self, frame: dict[str, Any]) -> None:
        """Latest-wins Eye payload. No work when OFF or HEADLESS."""
        from .tiktaalik_eye import (
            RATE_PERIOD_S,
            build_tiktaalik_eye_payload,
            clamp_eye_rate,
            visual_subset,
        )

        exec_mode = str(self.config.execution_mode or "LIVE").upper()
        rate = clamp_eye_rate(self._eye_rate)
        if exec_mode == "HEADLESS" or rate == "OFF":
            frame["tiktaalik_eye"] = {
                "schema": "mm.observer.tiktaalik_eye.v1",
                "status": "OFF",
                "rate": "OFF" if rate == "OFF" else rate,
                "reason": "HEADLESS" if exec_mode == "HEADLESS" else "preview_off",
                "feeds_cognition": False,
                "worldmap_rgb_used": False,
                "fpv_included": False,
            }
            return
        now = time.monotonic()
        tick = int(getattr(self.runtime, "tick", 0) or 0)
        due = False
        if self._eye_force_snapshot:
            due = True
            self._eye_force_snapshot = False
        elif rate == "SNAPSHOT":
            due = str(self.status).upper() != "RUNNING"
        elif rate == "PER_TICK":
            due = tick != int(self._eye_last_tick)
        else:
            period = float(RATE_PERIOD_S.get(rate, 0.2))
            due = (now - float(self._eye_last_wall)) >= period or self._eye_last_payload is None
        if not due and self._eye_last_payload is not None:
            frame["tiktaalik_eye"] = self._eye_last_payload
            return
        if not due:
            frame["tiktaalik_eye"] = {
                "schema": "mm.observer.tiktaalik_eye.v1",
                "status": "WAITING",
                "rate": rate,
                "feeds_cognition": False,
            }
            return
        t0 = time.perf_counter()
        from mechanistic_mind.research.tick_profiler import span as _obs_span
        from mechanistic_mind.research.tick_profiler import count as _obs_count

        _obs_count("eye_payload_build")
        nb_map: dict[str, list] = {}
        if self._eye_geometry_debug:
            views = frame.get("agents_views") or {}
            if isinstance(views, dict):
                for aid, view in views.items():
                    if not isinstance(view, dict):
                        continue
                    nf = (view.get("physical") or {}).get("near_field_exteroception") or {}
                    nbs = nf.get("neighbors") if isinstance(nf, dict) else None
                    if nbs:
                        nb_map[str(aid)] = nbs
        with _obs_span("observer_eye"):
            payload = build_tiktaalik_eye_payload(
                self.runtime,
                prev_visual_by_agent=self._eye_prev_visual,
                include_geometry_debug=bool(self._eye_geometry_debug),
                neighbors_by_agent=nb_map,
                include_fpv=bool(self._eye_fpv_visible),
                prev_fpv_finals=self._eye_prev_fpv,
                rate=rate,
            )
        nxt_fpv = payload.pop("fpv_next_finals", None) or {}
        if nxt_fpv:
            self._eye_prev_fpv = nxt_fpv
        self._eye_last_build_ms = (time.perf_counter() - t0) * 1000.0
        payload["build_ms"] = round(self._eye_last_build_ms, 4)
        self._eye_last_payload = payload
        self._eye_last_wall = now
        self._eye_last_tick = tick
        self._eye_update_count += 1
        nxt: dict[str, dict[str, float]] = {}
        slots = getattr(self.runtime, "slots", None)
        if slots:
            from .undercover_identity import slot_agent_body_ids

            exp_slot = getattr(self.runtime, "experimenter_slot", None)
            for i, slot in enumerate(slots):
                aid, _ = slot_agent_body_ids(i, experimenter_slot=exp_slot)
                nxt[aid] = visual_subset(getattr(slot, "last_agent_observation", None))
        else:
            nxt["agent_0"] = visual_subset(getattr(self.runtime, "last_agent_observation", None))
        self._eye_prev_visual = nxt
        frame["tiktaalik_eye"] = payload

    SNAPSHOT_SCHEMA = "mm.physical_system.snapshot.v2"
    SNAPSHOT_SCHEMA_TWO = "mm.physical_system.two_agent.snapshot.v1"

    def _clear_world_interventions_locked(self) -> None:
        self._world_interventions = deque(maxlen=LIVE_WORLD_INTERVENTION_SESSION_MAX)
        self._world_intervention_fp0 = None

    def _session_instance_id(self) -> str | None:
        import os
        return os.environ.get("PSY_OBSERVER_INSTANCE_ID")

    def list_world_interventions(self) -> dict[str, Any]:
        with self._lock:
            from mechanistic_mind.ui.psy_observer_web.live_intervention import regimes_from_interventions
            items = list(self._world_interventions)
            regimes = regimes_from_interventions(
                items,
                start_tick=0,
                end_tick=int(getattr(self.runtime, "tick", 0) or 0),
                initial_fingerprint=self._world_intervention_fp0,
            )
            return {
                "runtime_generation": int(self._runtime_generation),
                "n_interventions": len(items),
                "session_cap": LIVE_WORLD_INTERVENTION_SESSION_MAX,
                "live_authority": "session_ring_not_scientific_history",
                "scientific_authority": "scientific_events.jsonl",
                "interventions": items,
                "regimes": regimes,
            }

    def _record_live_intervention_locked(
        self,
        *,
        category: str,
        changes: dict[str, dict[str, Any]],
        fingerprint_before: str | None = None,
        source: str = "observer_ui",
    ) -> dict[str, Any] | None:
        """Record WORLD_INTERVENTION if effective fingerprint changed. Caller holds step_lock."""
        from mechanistic_mind.ui.psy_observer_web.live_intervention import (
            build_world_intervention_event,
            fingerprint_for_runtime,
        )
        fp_before = fingerprint_before or fingerprint_for_runtime(self.runtime)
        fp_after = fingerprint_for_runtime(self.runtime)
        # World fingerprint covers ecology/climate/resources, not cognition mechanisms.
        # Explicit mechanism toggles (e.g. PSC) must still enter configuration history.
        mechanism_change = (
            str(category) == "mechanism"
            and isinstance(changes, dict)
            and any(str(k).startswith("mechanism.") for k in changes)
        )
        if fp_before == fp_after and not mechanism_change:
            # No effective configuration change — do not fabricate a regime boundary.
            return None
        if self._world_intervention_fp0 is None:
            self._world_intervention_fp0 = fp_before
        tick = int(getattr(self.runtime, "tick", 0) or 0)
        ev = build_world_intervention_event(
            simulation_tick=tick,
            runtime_generation=int(self._runtime_generation),
            session_instance_id=self._session_instance_id(),
            category=category,
            changes=changes,
            fingerprint_before=fp_before,
            fingerprint_after=fp_after,
            history_reset=False,
            cognition_reset=False,
            body_reset=False,
            source=source,
        )
        self._world_interventions.append(ev)
        # Also surface on the structured event ring for Analyzer ingestion.
        try:
            key = self._event_key(ev)
            if key not in self._event_keys:
                self._event_keys.add(key)
                self._event_ring.append(ev)
        except Exception:
            try:
                self._event_ring.append(ev)
            except Exception:
                pass
        return ev

    def apply_live_intervention(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Mutate current runtime LIVE without rebuilding agents/history.

        World-structural keys (seed, map size, agent_count, …) are rejected.
        Ecology preset and mechanism toggles apply in place when supported.
        """
        from mechanistic_mind.ui.psy_observer_web.live_intervention import (
            WORLD_STRUCTURAL_KEYS,
            classify_control,
            fingerprint_for_runtime,
        )
        before = self._control_state()
        # Reject world-structural fields if present with intent to change them.
        world_in = payload.get("world") or {}
        structural_hits: list[str] = []
        for k in WORLD_STRUCTURAL_KEYS:
            if k in payload and k not in {"ecology_preset"}:
                structural_hits.append(k)
        for k in ("width", "height", "boundary_mode", "boundary_topology", "terrain_seed"):
            if k in world_in:
                structural_hits.append(f"world.{k}")
        if "agent_count" in payload:
            structural_hits.append("agent_count")
        if "seed" in payload:
            # Allow seed in payload only if it matches current (UI convenience); else reject.
            try:
                if int(payload["seed"]) != int(self.config.seed):
                    structural_hits.append("seed")
            except (TypeError, ValueError):
                structural_hits.append("seed")
        if "agent_body" in payload or "body" in payload:
            structural_hits.append("agent_body")
        if structural_hits:
            frame = self._clone_published()
            return self._with_receipt(
                frame,
                "LIVE_INTERVENTION",
                deepcopy(payload),
                before,
                accepted=False,
                reason=(
                    "WORLD-STRUCTURAL settings require APPLY & RESET WORLD: "
                    + ", ".join(sorted(set(structural_hits)))
                ),
                requires_reset=True,
            )

        changes: dict[str, dict[str, Any]] = {}
        category = str(payload.get("category") or "ecology")

        with self._step_lock:
            fp_before = fingerprint_for_runtime(self.runtime)
            # Ecology preset live stamp onto existing config (no runtime rebuild).
            eco = payload.get("ecology_preset")
            if eco is not None:
                from mechanistic_mind.physical_system.ecology_presets import (
                    apply_ecology_preset,
                    normalize_ecology_preset,
                )
                old_eco = getattr(self.runtime.config, "ecology_preset", None)
                new_eco = normalize_ecology_preset(eco)
                if str(old_eco) != str(new_eco):
                    slots = getattr(self.runtime, "slots", None)
                    if slots:
                        for rt in slots:
                            apply_ecology_preset(rt.config, new_eco, inplace=True)
                        self.runtime.config = slots[0].config
                    else:
                        apply_ecology_preset(self.runtime.config, new_eco, inplace=True)
                    changes["ecology_preset"] = {"old": old_eco, "new": new_eco}
                    category = "ecology"
                    if self._canonical_config is not None:
                        self._canonical_config["ecology_preset"] = new_eco
                    # Best-effort terrain field refresh when terrain becomes enabled —
                    # does not recreate agents or cognition.
                    try:
                        te = getattr(self.runtime.config.planet, "terrain", None)
                        if te is not None and bool(getattr(te, "enabled", False)):
                            from mechanistic_mind.planet import terrain as terrain_mod
                            if hasattr(terrain_mod, "ensure_terrain_fields"):
                                terrain_mod.ensure_terrain_fields(
                                    self.runtime.world, te, seed=int(self.config.seed),
                                )
                            elif hasattr(self.runtime.world, "ensure_terrain"):
                                self.runtime.world.ensure_terrain(te)
                    except Exception:
                        pass
                    # Ecology presets may overwrite climate/resources/terrain.
                    # Re-stamp resolved mechanism authority so CONFIG/RUNTIME stay aligned
                    # (same rule as APPLY & RESET: resolved climate wins over ecology stamp).
                    if self._resolved_mechanism_config is not None:
                        from mechanistic_mind.physical_system.mechanism_configuration import (
                            apply_resolved_to_runtime,
                            build_runtime_manifest,
                            run_preflight,
                        )
                        apply_resolved_to_runtime(self.runtime, self._resolved_mechanism_config)
                        preflight = run_preflight(self.runtime, self._resolved_mechanism_config)
                        self._preflight_result = preflight.to_dict()
                        if preflight.status == "READY":
                            self._runtime_mechanism_manifest = build_runtime_manifest(
                                runtime=self.runtime,
                                resolved=self._resolved_mechanism_config,
                                preflight=preflight,
                                run_id=self._active_run_id,
                                generation=self._runtime_generation,
                            )
                        # Record climate after re-stamp if ecology had flipped it.
                        planet = getattr(self.runtime.config, "planet", None)
                        ce = getattr(planet, "climate_ecology", None) if planet else None
                        if ce is not None:
                            clim_on = bool(getattr(ce, "enabled", False))
                            want = bool(
                                self._resolved_mechanism_config.mechanisms.get(
                                    "spatiotemporal_climate_ecology", False
                                )
                            )
                            if clim_on != want:
                                changes["climate_ecology.enabled_after_resolve"] = {
                                    "old": clim_on,
                                    "new": want,
                                    "note": "resolved mechanism authority reapplied after ecology",
                                }

            # Mechanism map in payload (same shape as Apply mechanisms dict).
            mechs = payload.get("mechanisms") or {}
            for mid, val in mechs.items():
                if mid == "cognition_enabled":
                    mid = "cognition"
                try:
                    prev = self.runtime.mechanisms()
                    item = next(
                        (m for m in prev.get("mechanisms", []) if m.get("id") == mid),
                        None,
                    )
                    if item is None or not item.get("ablatable", True):
                        continue
                    old_en = bool(item.get("enabled"))
                    new_en = bool(val)
                    if old_en == new_en:
                        continue
                    self.runtime.set_mechanism(str(mid), new_en)
                    changes[f"mechanism.{mid}"] = {"old": old_en, "new": new_en}
                    if category == "ecology" and not eco:
                        category = "mechanism"
                except (KeyError, ValueError, TypeError):
                    continue

            if "cognition_enabled" in payload:
                try:
                    prev = self.runtime.mechanisms()
                    item = next(
                        (m for m in prev.get("mechanisms", []) if m.get("id") == "cognition"),
                        None,
                    )
                    new_en = bool(payload["cognition_enabled"])
                    old_en = bool(item.get("enabled")) if item else bool(self.config.cognition_enabled)
                    if old_en != new_en:
                        self.runtime.set_mechanism("cognition", new_en)
                        self.config.cognition_enabled = new_en
                        changes["mechanism.cognition"] = {"old": old_en, "new": new_en}
                        category = "model"
                except (KeyError, ValueError, TypeError):
                    pass

            # Observer-only knobs that do not rebuild runtime.
            if "target_tick" in payload:
                old_t = self.config.target_tick
                self.config.target_tick = payload.get("target_tick")
                if old_t != self.config.target_tick:
                    changes["target_tick"] = {"old": old_t, "new": self.config.target_tick}
            if "ui_hz" in payload:
                old_u = self.config.ui_hz
                self.config.ui_hz = float(payload["ui_hz"])
                if old_u != self.config.ui_hz:
                    changes["ui_hz"] = {"old": old_u, "new": self.config.ui_hz}
            if "buffer_capacity" in payload:
                old_b = self.config.buffer_capacity
                self.config.buffer_capacity = int(payload["buffer_capacity"])
                if old_b != self.config.buffer_capacity:
                    changes["buffer_capacity"] = {"old": old_b, "new": self.config.buffer_capacity}

            ev = None
            if changes:
                ev = self._record_live_intervention_locked(
                    category=category,
                    changes=changes,
                    fingerprint_before=fp_before,
                    source=str(payload.get("source") or "api/experiment/live"),
                )
            with self._lock:
                frame = self._capture_locked(detail="full")
                if hasattr(frame, "get"):
                    frame = dict(frame)
                    frame["world_interventions"] = tail_list(
                        self._world_interventions, LIVE_WORLD_INTERVENTION_EMBED
                    )
                    frame["live_intervention"] = ev

        out = self._with_receipt(
            frame,
            "LIVE_INTERVENTION",
            {
                **deepcopy(payload),
                "live": True,
                "history_reset": False,
                "cognition_reset": False,
                "body_reset": False,
                "noop": ev is None,
                "classified": {k: classify_control(k) for k in changes},
            },
            before,
            accepted=True,
            requires_reset=False,
            reason=None if ev is not None else "no effective configuration change",
        )
        out["world_intervention"] = ev
        out["world_interventions"] = tail_list(
            self._world_interventions, LIVE_WORLD_INTERVENTION_EMBED
        )
        out["preflight"] = getattr(self, "_preflight_result", None)
        out["mechanism_integrity"] = self.mechanism_integrity_status()
        self._maybe_push(out, force=True)
        return out

    def snapshot(self) -> dict[str, Any]:
        with self._step_lock:
            return self.runtime.snapshot()

    def snapshot_meta(self) -> dict[str, Any]:
        cfg = getattr(self.runtime, "config", None)
        keys = sorted(k for k in vars(cfg) if not k.startswith("_")) if cfg is not None else []
        actual = (
            self.SNAPSHOT_SCHEMA_TWO
            if getattr(self.runtime, "slots", None)
            else self.SNAPSHOT_SCHEMA
        )
        return {
            "schema": actual,
            "accepted_schema": [self.SNAPSHOT_SCHEMA, self.SNAPSHOT_SCHEMA_TWO],
            "tick": int(self.runtime.tick),
            "seed": int(getattr(self.runtime, "seed", self.config.seed)),
            "runtime_generation": self._runtime_generation,
            "config_keys": keys,
            "durable_path": "GET /api/snapshot; Save & Stop writes results/psychology_observer/psy_observer_web/",
            "historical_policy": "missing newer mechanism keys restore documented OFF/free behavior",
            "two_agent_schema": self.SNAPSHOT_SCHEMA_TWO,
            "schema_actual": actual,
            "termination_reason": self._termination_reason,
            "last_finalize": deepcopy(self._last_finalize) if self._last_finalize else None,
        }

    def checkpoint_status(self) -> dict[str, Any]:
        cad = int(self.config.checkpoint_every_ticks or 0)
        tick = int(getattr(self.runtime, "tick", 0) or 0)
        last = self._checkpoint_status.get("last_tick")
        nxt = None
        if cad > 0:
            nxt = ((tick // cad) + 1) * cad if tick else cad
        return {
            **self._checkpoint_status,
            "cadence": cad if cad > 0 else "OFF",
            "tick": tick,
            "next_tick": nxt,
            "state": self._checkpoint_status.get("state") or ("READY" if cad > 0 else "OFF"),
            "recoverable_through": last,
            "note": "Persistence infrastructure. Not cognition.",
        }

    def set_checkpoint_cadence(self, every_ticks: int) -> dict[str, Any]:
        n = int(every_ticks or 0)
        if n < 0:
            n = 0
        self.config.checkpoint_every_ticks = n
        st = self.checkpoint_status()
        st["accepted"] = True
        return st

    def _maybe_checkpoint_locked(self) -> None:
        cad = int(self.config.checkpoint_every_ticks or 0)
        if cad <= 0:
            return
        tick = int(self.runtime.tick)
        if tick <= 0 or (tick % cad) != 0:
            return
        last = self._checkpoint_status.get("last_tick")
        if last is not None and int(last) == tick:
            return
        self._write_checkpoint_locked()

    def write_checkpoint_now(self) -> dict[str, Any]:
        with self._step_lock:
            with self._lock:
                return self._write_checkpoint_locked()

    def _write_checkpoint_locked(self) -> dict[str, Any]:
        from mechanistic_mind.ui.psy_observer_web.crash_checkpoint import write_checkpoint

        dest = self._sci_live_dir or (self._results_root() / "_session_checkpoints")
        dest = Path(dest)
        dest.mkdir(parents=True, exist_ok=True)
        self._checkpoint_status["state"] = "WRITING"
        try:
            out = write_checkpoint(
                self.runtime,
                dest_root=dest,
                run_id=self._active_run_id,
                extra={
                    "runtime_generation": int(self._runtime_generation),
                    "previous_run_id": (self._checkpoint_resume_meta or {}).get("previous_run_id"),
                },
            )
            self._checkpoint_status.update({
                "state": "READY",
                "last_tick": out.get("tick"),
                "last_error": None,
                "last_wall_s": out.get("wall_s"),
                "last_mb": out.get("snapshot_mb"),
                "recoverable_through": out.get("tick"),
                "dir": out.get("dir"),
            })
            return {**out, **self.checkpoint_status()}
        except Exception as exc:  # noqa: BLE001 — failed write must not kill SIM
            self._checkpoint_status["state"] = "FAILED"
            self._checkpoint_status["last_error"] = str(exc)
            return {"accepted": False, "error": str(exc), **self.checkpoint_status()}

    def restore_committed_checkpoint(self, *, dest_root: Path | None = None) -> dict[str, Any]:
        """Restore CURRENT (or PREVIOUS) generation. Starts a new V3 segment."""
        from mechanistic_mind.ui.psy_observer_web.crash_checkpoint import load_committed, load_snapshot_dict

        root = Path(dest_root) if dest_root is not None else (
            self._sci_live_dir or self._results_root()
        )
        committed = load_committed(root)
        if not committed:
            return {"accepted": False, "error": "no committed checkpoint"}
        payload = load_snapshot_dict(committed)
        prev_run = self._active_run_id
        ck_tick = int(committed["manifest"].get("tick") or payload.get("tick") or 0)
        self._halt_runner("PAUSED")
        with self._lock:
            self._close_scientific_locked(clear_live_dir=True)
        self._checkpoint_resume_meta = {
            "resumed_from_checkpoint": True,
            "checkpoint_tick": ck_tick,
            "previous_run_id": prev_run,
            "checkpoint_dir": committed.get("dir"),
            "branch_note": "New segment from checkpoint; do not merge dead post-checkpoint ticks.",
        }
        out = self.restore(payload)
        receipt = out.get("control_receipt") or {}
        if receipt.get("accepted") is False:
            return {"accepted": False, "error": "restore rejected", "restore": out}
        self._active_run_id = new_run_id()
        self._run_started_at = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._ensure_scientific_locked()
        return {
            "accepted": True,
            "checkpoint_tick": ck_tick,
            "manifest": committed["manifest"],
            "resume": self._checkpoint_resume_meta,
            "runtime_tick": int(self.runtime.tick),
            "new_run_id": self._active_run_id,
            "restore_receipt_op": receipt.get("operation"),
        }

    def restore(self, payload: dict[str, Any]) -> dict[str, Any]:
        schema = None if not isinstance(payload, dict) else payload.get("schema")
        if schema not in {self.SNAPSHOT_SCHEMA, self.SNAPSHOT_SCHEMA_TWO}:
            before = self._control_state()
            return self._with_receipt(
                self._clone_published(),
                "RESTORE_SNAPSHOT",
                {"schema": schema},
                before,
                accepted=False,
                reason=(
                    f"unsupported or missing snapshot schema; accepted "
                    f"{self.SNAPSHOT_SCHEMA} or {self.SNAPSHOT_SCHEMA_TWO}"
                ),
            )
        self._halt_runner("PAUSED")
        with self._step_lock:
            with self._lock:
                before = self._control_state()
                if schema == self.SNAPSHOT_SCHEMA_TWO:
                    self.runtime = TwoAgentRuntime.restore(payload)
                else:
                    self.runtime = PhysicalSystemRuntime.restore(payload)
                self._runtime_generation += 1
                self.status = "PAUSED"
                self.mode = "LIVE"
                self.inspect_tick = None
                self._prev_body = None
                self._prev_bodies = {}
                self._geo_prev_bodies = {}
                self._reset_geo_accum_locked()
                self._trajectory.clear()
                self._telemetry.clear()
                self._buffer.clear()
                self._timeline.clear()
                self._published = None
                self._published_json = None
                self._published_ws_text = None
                self._run_started_at = None
                self._active_run_id = None
                self._finalize_key = None
                # Rebind Undercover controller to restored physical body — never respawn.
                self._reset_experimenter_locked()
                if (
                    hasattr(self.runtime, "experimenter_slot")
                    and getattr(self.runtime, "experimenter_slot", None) is not None
                ):
                    from mechanistic_mind.ui.psy_observer_web.experimenter_control import (
                        rebind_experimenter_controller,
                    )
                    ctrl = self._ensure_experimenter_locked()
                    rebind_experimenter_controller(self.runtime, ctrl)
                    self._experimenter_intervention_ever = True
                missing = [
                    k for k in ("deformation_work", "complementary_resources", "endogenous_motor_work", "discrete_action_work")
                    if k not in (payload.get("config") or {})
                    and schema == self.SNAPSHOT_SCHEMA
                ]
                self._historical_compat = {
                    "active": bool(missing),
                    "missing_mechanism_keys": missing,
                    "policy": "missing newer mechanism keys restore historical OFF/free behavior",
                }
                frame = self._capture_locked()
        self._maybe_push(frame, force=True)
        from mechanistic_mind.physical_system.experiment_canonical import canonical_from_runtime

        self._canonical_config = canonical_from_runtime(self.runtime)
        self._canonical_config["pe_cold_history_eviction"] = bool(self.config.pe_cold_history_eviction)
        self._canonical_requested = deepcopy(self._canonical_config)
        self._applied_receipt = self.applied_configuration_receipt()
        out = self._with_receipt(
            frame, "RESTORE_SNAPSHOT", {"schema": payload.get("schema")},
            before, requires_reset=True,
        )
        out["applied_configuration"] = self._applied_receipt
        return out

    def timeline(self, *, limit: int = 200) -> list[dict[str, Any]]:
        with self._lock:
            items = list(self._timeline)
            return items[-max(1, int(limit)) :]

    def frame_at_tick(self, tick: int) -> dict[str, Any]:
        """INSPECT from bounded buffer only — never invent missing history."""
        with self._lock:
            found = None
            for frame in reversed(self._buffer):
                if int((frame.get("header") or {}).get("tick", -1)) == int(tick):
                    found = frame
                    break
            live_tick = int(self.runtime.tick)
            status = self.status
        if found is not None:
            out = deepcopy(found)
            out["header"] = {
                **out.get("header", {}),
                "mode": "INSPECT",
                "live_runtime_tick": live_tick,
                "runtime_status": status,
            }
            return out
        return {
            "header": {
                "mode": "INSPECT",
                "status": status,
                "tick": int(tick),
                "live_runtime_tick": live_tick,
                "selected_agent": "body-0",
            },
            "error": "NOT AVAILABLE",
            "reason": "NOT_RECORDED: tick not present in bounded live buffer; take snapshots for durable history",
        }

    def set_motion_trace(self, *, enabled: bool, mode: str = "every_10") -> dict[str, Any]:
        before = self._control_state()
        with self._step_lock:
            result = self.runtime.set_motion_trace(enabled=enabled, mode=mode)
            with self._lock:
                frame = self._capture_locked()
        out = self._with_receipt(
            frame, "SET_MOTION_TRACE", {"enabled": bool(enabled), "mode": mode}, before,
        )
        out["motion_trace"] = result
        self._maybe_push(out, force=True)
        return out

    def set_action_trace(self, *, enabled: bool, mode: str = "every_10") -> dict[str, Any]:
        before = self._control_state()
        with self._step_lock:
            result = self.runtime.set_action_trace(enabled=enabled, mode=mode)
            with self._lock:
                frame = self._capture_locked()
        out = self._with_receipt(
            frame, "SET_ACTION_TRACE", {"enabled": bool(enabled), "mode": mode}, before,
        )
        out["action_trace"] = result
        self._maybe_push(out, force=True)
        return out

    

    def observer_interest_snapshot(self) -> dict[str, Any]:
        return self._observer_interest.snapshot()

    def set_observer_detail_preset(self, preset: str) -> dict[str, Any]:
        """MINIMAL|NORMAL|FULL — Observer display only; does not touch cognition/science."""
        snap = self._observer_interest.set_preset(preset)
        # Force a fresh capture so UI sees deferred stubs immediately (no runtime reset).
        try:
            detail = "compact" if self.status == "RUNNING" else (
                "full" if self._observer_interest.preset == "FULL" else "compact"
            )
            with self._step_lock:
                with self._lock:
                    frame = self._capture_locked(detail=detail)
            self._maybe_push(frame, force=True)
        except Exception:
            pass
        return {"interest": snap, "runtime_tick": int(getattr(self.runtime, "tick", 0) or 0),
                "runtime_generation": int(self._runtime_generation), "status": self.status}

    def set_observer_products(self, products: list[str] | tuple[str, ...] | None) -> dict[str, Any]:
        snap = self._observer_interest.set_products(products or [])
        return {"interest": snap, "runtime_tick": int(getattr(self.runtime, "tick", 0) or 0),
                "runtime_generation": int(self._runtime_generation)}

    def update_observer_product(self, product: str, enabled: bool) -> dict[str, Any]:
        if enabled:
            snap = self._observer_interest.add(product)
        else:
            snap = self._observer_interest.remove(product)
        return {"interest": snap}

    def sensorimotor_consequence_panel(self) -> dict:
        if not self._observer_interest.wants(PRODUCT_SMC):
            return {"schema": "mm.observer.sensorimotor_consequence.v1", "agents": [], **stub_deferred(PRODUCT_SMC)}
        """Compact CURRENT MM — SENSORIMOTOR CONSEQUENCES (Observer UI)."""
        from mechanistic_mind.physical_system import sensorimotor_consequence as smc
        out = {"schema": "mm.observer.sensorimotor_consequence.v1", "agents": []}
        rt = getattr(self, "runtime", None)
        if rt is None:
            return out
        slots = getattr(rt, "slots", None) or []
        for i, slot in enumerate(slots):
            cog = getattr(slot, "cognition", None)
            if not isinstance(cog, dict):
                # PhysicalSystemRuntime single-agent
                continue
            store = cog.get("sensorimotor_consequence") or {}
            last = cog.get("last_selection") or {}
            diag = smc.diagnostic(store) if store else {"enabled": False}
            preds = last.get("sensorimotor_candidate_predictions") or []
            # Neutral presentation: motor signature → support + predicted delta
            top = []
            for p in preds[:8]:
                top.append({
                    "motor": p.get("candidate_locomotion") or p.get("motor_signature"),
                    "status": p.get("status"),
                    "support": p.get("support"),
                    "predicted_sensory_delta": p.get("predicted_delta"),
                })
            out["agents"].append({
                "slot": i,
                "agent_id": getattr(slot, "agent_id", None) or f"agent_{i}",
                "diagnostic": diag,
                "candidate_predictions": top,
                "withheld_from_psc": bool(last.get("sensorimotor_withheld_from_psc")),
                "selected_action": last.get("action"),
            })
        # TwoAgentRuntime uses slots; also try agents list
        if not out["agents"] and hasattr(rt, "agents"):
            for i, ag in enumerate(getattr(rt, "agents") or []):
                cog = getattr(ag, "cognition", None) or (ag.get("cognition") if isinstance(ag, dict) else None)
                if not isinstance(cog, dict):
                    continue
                store = cog.get("sensorimotor_consequence") or {}
                last = cog.get("last_selection") or {}
                diag = smc.diagnostic(store) if store else {"enabled": False}
                preds = last.get("sensorimotor_candidate_predictions") or []
                top = [{
                    "motor": p.get("candidate_locomotion") or p.get("motor_signature"),
                    "status": p.get("status"),
                    "support": p.get("support"),
                    "predicted_sensory_delta": p.get("predicted_delta"),
                } for p in preds[:8]]
                out["agents"].append({
                    "slot": i,
                    "diagnostic": diag,
                    "candidate_predictions": top,
                    "withheld_from_psc": bool(last.get("sensorimotor_withheld_from_psc")),
                    "selected_action": last.get("action"),
                })
        return out



    def signal_sensorimotor_panel(self, *, include_shadow: bool = False) -> dict:
        """Demand-driven SIGNAL → PREDICTION → PSC panel (Observer display only).

        Analysis-only PSC shadow replay is NOT run unless ``include_shadow`` is True.
        Default polls must stay cheap while RUNNING.
        """
        if not self._observer_interest.wants(PRODUCT_SIGNAL_SENSORIMOTOR):
            return {**stub_deferred(PRODUCT_SIGNAL_SENSORIMOTOR), "schema": "mm.observer.signal_sensorimotor.v1"}
        self._observer_interest.record_producer(PRODUCT_SIGNAL_SENSORIMOTOR)
        # Selected agent cognition + observation — no store scans / no history recompute.
        out = {
            "schema": "mm.observer.signal_sensorimotor.v1",
            "observer_only": True,
            "note": "osc L/R bands are agent-accessible but NOT in SMC; FIELD_A/B are.",
        }
        rt = getattr(self, "runtime", None)
        if rt is None:
            out["error"] = "no_runtime"
            return out
        slot = rt
        slots = getattr(rt, "slots", None)
        if slots:
            idx = int(getattr(rt, "selected_index", 0) or 0)
            idx = max(0, min(idx, len(slots) - 1))
            slot = slots[idx]
            out["agent_id"] = getattr(slot, "agent_id", None) or f"agent_{idx}"
        else:
            out["agent_id"] = "agent_0"
        try:
            obs = slot.agent_observation() if hasattr(slot, "agent_observation") else {}
        except TypeError:
            obs = slot.agent_observation(foreign_bodies=None) if hasattr(slot, "agent_observation") else {}
        except Exception:
            obs = {}
        if not isinstance(obs, dict):
            obs = {}
        field = {k: float(obs.get(k) or 0.0) for k in ("local.FIELD_A", "local.FIELD_B")}
        L = [float(obs.get(f"osc_l_{i}") or 0.0) for i in range(6)]
        R = [float(obs.get(f"osc_r_{i}") or 0.0) for i in range(6)]
        tot_l, tot_r = sum(L), sum(R)
        out["signal_input"] = {
            "FIELD_A": field["local.FIELD_A"],
            "FIELD_B": field["local.FIELD_B"],
            "L_bands": L,
            "R_bands": R,
            "derived_display_only": {
                "TOTAL_L": tot_l,
                "TOTAL_R": tot_r,
                "R_minus_L": tot_r - tot_l,
                "ASYMMETRY": (tot_r - tot_l) / (tot_r + tot_l + 1e-9),
                "label": "DERIVED DISPLAY ONLY — NOT AN AGENT VARIABLE",
            },
        }
        # Bounded recent FIELD strip from session telemetry if present
        telem = list(getattr(self, "_telemetry", []) or [])[-64:]
        strip = []
        for row in telem:
            if not isinstance(row, dict):
                continue
            strip.append({
                "tick": row.get("tick"),
                "FIELD_A": row.get("FIELD_A") or row.get("field_a"),
                "FIELD_B": row.get("FIELD_B") or row.get("field_b"),
            })
        out["recent_accessible_signal"] = {
            "points": strip,
            "capacity": 64,
            "label": "RECENT AGENT-ACCESSIBLE SIGNAL (bounded UI history)",
        }
        cog = getattr(slot, "cognition", None) if not isinstance(slot, dict) else None
        if not isinstance(cog, dict):
            cog = getattr(rt, "cognition", {}) if hasattr(rt, "cognition") else {}
        sel = (cog or {}).get("last_selection") or {}
        smc_preds = sel.get("sensorimotor_candidate_predictions") or []
        signal_cands = []
        for p in smc_preds[:12]:
            if not isinstance(p, dict):
                continue
            d = p.get("predicted_delta") if isinstance(p.get("predicted_delta"), dict) else {}
            sd = {k: d[k] for k in ("local.FIELD_A", "local.FIELD_B") if k in d}
            osc_d = {k: d[k] for k in d if str(k).startswith("osc_")}
            L = [float(osc_d.get(f"osc_l_{i}", 0.0)) for i in range(6)] if osc_d else None
            R = [float(osc_d.get(f"osc_r_{i}", 0.0)) for i in range(6)] if osc_d else None
            # Predicted L'/R' ≈ current + delta (display only for UI)
            cur_L = [float(obs.get(f"osc_l_{i}") or 0.0) for i in range(6)]
            cur_R = [float(obs.get(f"osc_r_{i}") or 0.0) for i in range(6)]
            Lp = [cur_L[i] + (L[i] if L else 0.0) for i in range(6)] if osc_d else None
            Rp = [cur_R[i] + (R[i] if R else 0.0) for i in range(6)] if osc_d else None
            tot_l = sum(cur_L); tot_r = sum(cur_R)
            asym0 = (tot_r - tot_l) / (tot_r + tot_l + 1e-9)
            if Lp is not None and Rp is not None:
                tl, tr = sum(Lp), sum(Rp)
                asym1 = (tr - tl) / (tr + tl + 1e-9)
                dasym = asym1 - asym0
            else:
                dasym = None
            signal_cands.append({
                "motor": p.get("motor") or p.get("motor_signature"),
                "status": p.get("status"),
                "support": p.get("support"),
                "signal_predicted_delta": sd or None,
                "osc_predicted_delta": osc_d or None,
                "L_prime": Lp,
                "R_prime": Rp,
                "delta_asymmetry_derived": dasym,
            })
        hss = sel.get("o_prime_history_bridge") or {}
        hss_cands = sel.get("o_prime_history_candidates") or []
        cfg = (cog or {}).get("config") or {}
        psc_on = str(sel.get("prospective_selection_mode") or cfg.get("prospective_selection") or "").upper() == "SCENARIO_COMPETITION"
        # also check config cognition object
        if hasattr(slot, "config") and getattr(slot.config, "cognition", None) is not None:
            cc = slot.config.cognition
            if str(getattr(cc, "prospective_selection", "")).upper() == "SCENARIO_COMPETITION":
                psc_on = True
        # Bilateral SMC status (no directional semantics)
        cog_cfg = (cog or {}).get("config") if isinstance(cog, dict) else {}
        bil_on = True
        if isinstance(cog_cfg, dict):
            bil_on = bool(cog_cfg.get("sensorimotor_consequence_bilateral", True))
        elif hasattr(slot, "config") and getattr(getattr(slot, "config", None), "cognition", None) is not None:
            bil_on = bool(getattr(slot.config.cognition, "sensorimotor_consequence_bilateral", True))
        smc_store = (cog or {}).get("sensorimotor_consequence") if isinstance(cog, dict) else None
        if isinstance(smc_store, dict) and "bilateral" in smc_store:
            bil_on = bool(smc_store.get("bilateral"))
        has_osc_pred = any(isinstance(c, dict) and c.get("osc_predicted_delta") for c in signal_cands)
        if not bil_on:
            bil_status = "WITHHELD"
        elif has_osc_pred:
            bil_status = "ACTIVE"
        elif bool((cog or {}).get("sensorimotor_consequence", {}).get("enabled") if isinstance(cog, dict) else False) or any(True for _ in []):
            bil_status = "LEARNING"
        else:
            bil_status = "NOT AVAILABLE"
        # Prefer LEARNING when SMC enabled but no osc preds yet
        smc_en = False
        if isinstance(smc_store, dict):
            smc_en = bool(smc_store.get("enabled"))
        if bil_on and smc_en and not has_osc_pred:
            bil_status = "LEARNING"
        elif bil_on and has_osc_pred:
            bil_status = "ACTIVE"
        out["bilateral_smc"] = {
            "status": bil_status,
            "enabled": bil_on,
            "predictions_available": has_osc_pred,
        }
        out["psc"] = {
            "enabled": bool(psc_on),
            "selected_action": sel.get("action"),
            "selection_source": sel.get("source"),
            "signal_candidates": signal_cands,
            "hss_meta": {
                "enabled": hss.get("enabled"),
                "withheld_from_psc": hss.get("withheld_from_psc"),
                "history_support_differentiated": hss.get("history_support_differentiated"),
                "selection_differs_from_withheld_cf": hss.get("selection_differs_from_withheld_cf"),
            } if isinstance(hss, dict) else None,
            "hss_candidates": hss_cands[:12] if isinstance(hss_cands, list) else [],
            "status_line": (
                "PSC OFF — accumulating sensorimotor history" if not psc_on
                else (
                    "SIGNAL FUTURES DIFFERENTIATED" if len({
                        tuple(sorted((c.get("signal_predicted_delta") or {}).items()))
                        for c in signal_cands if c.get("signal_predicted_delta")
                    }) >= 2
                    else ("SIGNAL PREDICTIONS AVAILABLE" if signal_cands else "SIGNAL PRESENT")
                )
            ),
        }
        # Vision badge: Observer context only if available from last perception bundle
        out["no_foreign_body_vision_badge"] = None
        try:
            # Prefer optical provenance on published frame if present
            frame = getattr(self, "_published", None) or {}
            # conservative: unknown
            out["vision_context"] = {"foreign_body_visual_exposure": None, "label": "OBSERVER CONTEXT"}
        except Exception:
            pass
        # Embodied predictive coverage (Observer diagnostic)
        from mechanistic_mind.physical_system import sensorimotor_consequence as _smc
        smc_store = (cog or {}).get("sensorimotor_consequence") if isinstance(cog, dict) else None
        ch_list = list((smc_store or {}).get("channel_list") or _smc.SENSORY_CHANNELS)
        fam_cov = {}
        for fam, keys in _smc.FAMILY_CHANNELS.items():
            n = len(keys)
            hit = sum(1 for k in keys if k in ch_list)
            fam_cov[fam] = {"modeled": hit, "total": n}
        last_motor = (cog or {}).get("last_motor_output") if isinstance(cog, dict) else None
        sig = None
        if isinstance(last_motor, dict):
            sig = _smc.motor_signature_from_composite(last_motor)
        out["embodied_prediction"] = {
            "sensory_coverage": fam_cov,
            "allowlist_n": len(ch_list),
            "motor": last_motor,
            "smc_action_signature": sig,
            "psc_query_aliasing": True,
            "aliasing_note": "PSC query_candidates conditions on locomotion only; learning uses full composite signature",
            "warning": "SMC ACTION ALIASING at PSC query path" if True else None,
        }
        out["tick"] = int(getattr(rt, "tick", 0) or 0)
        
        # --- PRODUCTION motor resolution (live mode; not shadow) ---
        try:
            from mechanistic_mind.physical_system import observed_composite_psc as _ocpsc
            cog_d = cog if isinstance(cog, dict) else {}
            ls = cog_d.get("last_selection") or {}
            mode = _ocpsc.normalize_mode(
                ls.get("psc_motor_resolution")
                or (cog_d.get("config") or {}).get("psc_motor_resolution")
                or getattr(getattr(getattr(rt, "config", None), "cognition", None), "psc_motor_resolution", None)
            )
            oc_meta = ls.get("observed_composite_selection") if isinstance(ls.get("observed_composite_selection"), dict) else {}
            mo = cog_d.get("last_motor_output") if isinstance(cog_d.get("last_motor_output"), dict) else {}
            out["psc_motor_resolution"] = mode
            out["motor_resolution_production"] = {
                "mode": mode,
                "experimental": mode == _ocpsc.MODE_OBSERVED,
                "label": "EXPERIMENTAL" if mode == _ocpsc.MODE_OBSERVED else "DEFAULT",
                "candidate_count": oc_meta.get("n_candidates"),
                "exact_composite_matches": oc_meta.get("exact_composite_matches"),
                "selected_composite": oc_meta.get("selected_signature") or (
                    mo.get("display") if mo.get("selection_source") == "OBSERVED_COMPOSITE_PSC" else None
                ),
                "selection_source": mo.get("selection_source"),
                "match_provenance": oc_meta.get("status"),
                "analysis_separates_shadow": True,
            }
        except Exception as _e:
            out["motor_resolution_production"] = {"error": str(_e), "mode": "LOCO_FACTORIZED"}

        # --- MOTOR RESOLUTION shadow (analysis only; does not affect agent) ---
        try:
            from mechanistic_mind.physical_system.full_composite_psc_shadow import replay_tick as _fc_replay
            from mechanistic_mind.physical_system import sensorimotor_consequence as _smc
            cog_d = cog if isinstance(cog, dict) else {}
            store = cog_d.get("sensorimotor_consequence") or {}
            prosp = cog_d.get("prospection") or {}
            motor = cog_d.get("last_motor_output")
            ls = cog_d.get("last_selection") or {}
            locos = list(ls.get("select_actions") or ["WAIT", "MOVE:N", "MOVE:S", "MOVE:E", "MOVE:W"])
            obs_f = {k: float(v) for k, v in (obs or {}).items() if isinstance(v, (int, float))}
            detail = str(getattr(getattr(self, "_observer_interest", None), "preset", None) or "NORMAL").upper()
            if detail == "MINIMAL" or not include_shadow:
                out["motor_resolution_shadow"] = {
                    "schema": "mm.observer.full_composite_psc_shadow.v1",
                    "status": "DEFERRED",
                    "reason": "MINIMAL" if detail == "MINIMAL" else "not_requested",
                    "analysis_only": True,
                    "does_not_affect_agent": True,
                    "label": "ANALYSIS ONLY — DOES NOT AFFECT AGENT",
                }
            else:
                prod_loco = (motor or {}).get("locomotion") if isinstance(motor, dict) else ls.get("action")
                seed = int(getattr(rt, "seed", 0) or 0)
                tick = int(getattr(rt, "tick", 0) or 0)
                self._psc_shadow_replay_count = int(self._psc_shadow_replay_count) + 1
                rep = _fc_replay(
                    observation=obs_f,
                    smc_store=store if isinstance(store, dict) else {},
                    prospection=prosp if isinstance(prosp, dict) else {},
                    compression=cog_d.get("compression"),
                    loco_candidates=locos,
                    seed=seed,
                    tick=tick,
                    production_selected_loco=prod_loco,
                    production_realized_motor=motor if isinstance(motor, dict) else None,
                    run_adaptive=True,
                    divergence_refine_threshold=0.02,
                )
                fc = rep.get("full_composite") or {}
                ad = rep.get("adaptive") or {}
                cls = rep.get("classification")
                banner = None
                if cls == "DIFFERENT_LOCOMOTION":
                    banner = "SHADOW LOCOMOTION DIFFERENCE"
                elif cls == "SAME_LOCOMOTION_DIFFERENT_COMPOSITE":
                    banner = "SHADOW COMPOSITE DIFFERENCE"
                compact = {
                    "schema": "mm.observer.full_composite_psc_shadow.v1",
                    "analysis_only": True,
                    "does_not_affect_agent": True,
                    "label": "ANALYSIS ONLY — DOES NOT AFFECT AGENT",
                    "banner": banner,
                    "classification": cls,
                    "production": {
                        "mode": "LOCO_ONLY",
                        "selected_loco": prod_loco,
                        "realized_composite": (rep.get("production") or {}).get("realized_composite_sig"),
                    },
                    "full_composite_shadow": {
                        "candidate_count": fc.get("n_actions"),
                        "winning_composite": fc.get("selected_sig"),
                        "winning_loco": fc.get("selected_loco"),
                    },
                    "adaptive_shadow": {
                        "refined": bool(ad.get("refined_locos")),
                        "candidate_count": ad.get("n_candidates"),
                        "winning_composite": ad.get("selected_sig"),
                    },
                }
                if detail == "FULL":
                    compact["full_details"] = {
                        "earliest_divergence": rep.get("earliest_divergence"),
                        "motor_dimension_attribution": rep.get("motor_dimension_attribution"),
                        "sensory_family_attribution": rep.get("sensory_family_attribution"),
                        "compete_outcome": fc.get("compete_outcome"),
                        "mutation_ok": (rep.get("mutation_audit") or {}).get("smc_counters_unchanged"),
                    }
                out["motor_resolution_shadow"] = compact
        except Exception as _e:
            out["motor_resolution_shadow"] = {
                "schema": "mm.observer.full_composite_psc_shadow.v1",
                "error": str(_e),
                "analysis_only": True,
                "does_not_affect_agent": True,
                "label": "ANALYSIS ONLY — DOES NOT AFFECT AGENT",
            }

        return out

    def historical_sensorimotor_selection_panel(self) -> dict:
        """Lightweight READY/ACTIVE status for O′→history→PSC bridge (no store scans)."""
        if not self._observer_interest.wants(PRODUCT_HISTORICAL_SENSORIMOTOR):
            return {**stub_deferred(PRODUCT_HISTORICAL_SENSORIMOTOR),
                    "schema": "mm.observer.historical_sensorimotor_selection.v1",
                    "agents": [], "ui_state": "OFF", "bridge_enabled": False, "psc_enabled": False}
        out = {
            "schema": "mm.observer.historical_sensorimotor_selection.v1",
            "agents": [],
            "bridge_enabled": False,
            "psc_enabled": False,
            "ui_state": "OFF",
            "experience_ticks": None,
            "psc_enabled_after_ticks": getattr(self, "_psc_enabled_after_ticks", None),
        }
        try:
            tick = int(getattr(getattr(self, "runtime", None), "tick", None)
                       or getattr(getattr(getattr(self, "runtime", None), "world", None), "tick", 0)
                       or 0)
        except Exception:
            tick = 0
        out["experience_ticks"] = tick
        agents = []
        # TwoAgent or single
        slots = []
        rt = getattr(self, "runtime", None)
        if rt is None:
            return out
        if hasattr(rt, "slots"):
            slots = list(rt.slots or [])
        elif hasattr(rt, "cognition"):
            slots = [rt]
        bridge_any = False
        psc_any = False
        for i, slot in enumerate(slots):
            cog = getattr(slot, "cognition", None)
            if not isinstance(cog, dict):
                continue
            cfg = cog.get("config") or {}
            if hasattr(slot, "config") and getattr(slot.config, "cognition", None) is not None:
                cc = slot.config.cognition
                bridge_on = bool(getattr(cc, "historical_sensorimotor_selection_bridge", False))
                psc_on = str(getattr(cc, "prospective_selection", "")).upper() == "SCENARIO_COMPETITION"
            else:
                bridge_on = bool(cfg.get("historical_sensorimotor_selection_bridge"))
                psc_on = str(cfg.get("prospective_selection") or "").upper() == "SCENARIO_COMPETITION"
            bridge_any = bridge_any or bridge_on
            psc_any = psc_any or psc_on
            last = cog.get("last_selection") or {}
            meta = last.get("o_prime_history_bridge") or {}
            agents.append({
                "slot": i,
                "agent_id": getattr(slot, "agent_id", None) or getattr(slot, "seed", i),
                "bridge_enabled": bridge_on,
                "psc_enabled": psc_on,
                "ui_state": (
                    "OFF" if not bridge_on else ("ACTIVE" if psc_on else "READY")
                ),
                "last_bridge_meta": {
                    "enabled": meta.get("enabled"),
                    "withheld_from_psc": meta.get("withheld_from_psc"),
                    "n_history_match": meta.get("n_history_match"),
                    "history_support_differentiated": meta.get("history_support_differentiated"),
                    "selection_differs_from_withheld_cf": meta.get("selection_differs_from_withheld_cf"),
                } if isinstance(meta, dict) else None,
            })
        out["agents"] = agents
        out["bridge_enabled"] = bridge_any
        out["psc_enabled"] = psc_any
        if not bridge_any:
            out["ui_state"] = "OFF"
        elif not psc_any:
            out["ui_state"] = "READY"
        else:
            out["ui_state"] = "ACTIVE"
        return out


    def diagnostics(self) -> dict[str, Any]:
        published = self._published
        if published is not None:
            diag = published.get("diagnostics")
            if diag is not None:
                return deepcopy(diag)
        with self._step_lock:
            return self.runtime.diagnostic_bundle()

    def current_frame(self) -> dict[str, Any]:
        """Return published Observer frame without deep-copying the payload.

        Nested frame content is treated as immutable. Only the top-level dict and
        header are shallow-copied so live tick / lag metrics can be annotated
        without a multi-megabyte deepcopy (HTTP polling must not stall SIM via GIL).
        """
        frame = self._published
        if frame is None:
            if str(self.config.execution_mode or "LIVE").upper() == "HEADLESS":
                return self._stub_header_frame()
            with self._step_lock:
                with self._lock:
                    if self._published is None:
                        self._capture_locked(detail="full")
                    frame = self._published
        assert frame is not None
        hdr = dict(frame.get("header") or {})
        sim_tick = int(self.runtime.tick)
        frame_tick = int(hdr.get("frame_tick") or hdr.get("tick") or sim_tick)
        hdr["live_runtime_tick"] = sim_tick
        hdr["sim_tick"] = sim_tick
        hdr["tick"] = sim_tick if str(self.config.execution_mode or "LIVE").upper() == "HEADLESS" else hdr.get("tick", frame_tick)
        hdr["observer_lag_ticks"] = max(0, sim_tick - frame_tick)
        hdr["execution_mode"] = str(self.config.execution_mode or "LIVE")
        hdr["evidence_mode"] = str(getattr(self.config, "evidence_mode", None) or "FULL_SCIENTIFIC")
        if hdr["evidence_mode"] == "SEARCH_COMPACT":
            hdr["evidence_label"] = "COMPACT EVIDENCE"
        hdr["observer_hz"] = float(self.config.ui_hz)
        hdr["target_tick"] = self.config.target_tick
        hdr["max_ticks"] = self.config.target_tick
        exec_mode = str(self.config.execution_mode or "LIVE").upper()
        hdr["display_frozen"] = bool(exec_mode == "HEADLESS" and self.status == "RUNNING")
        hdr["display_tick"] = frame_tick
        if self.status == "RUNNING":
            hdr["sim_ticks_per_sec"] = round(float(self._perf_sim_tps), 1)
            hdr["observer_fps"] = round(float(self._perf_obs_fps), 1)
        else:
            hdr["sim_ticks_per_sec"] = 0.0
        # ETA is operational UI only — never written into cognition/scientific state.
        target = self.config.target_tick
        if target is not None and self.status == "RUNNING" and self._perf_sim_tps > 0:
            remain = max(0, int(target) - sim_tick)
            hdr["eta_wall_seconds"] = round(remain / float(self._perf_sim_tps), 1)
        else:
            hdr["eta_wall_seconds"] = None
        return {**frame, "header": hdr, "experiment": {
            **(frame.get("experiment") or {}),
            "applied_configuration": self._applied_receipt,
        }}

    def published_json(self) -> str | None:
        """Cached JSON of the last published frame body (no live-tick overlay)."""
        return self._published_json

    def published_ws_text(self) -> str | None:
        """Cached websocket envelope; one json.dumps of the frame body."""
        return self._published_ws_text

    def _stub_header_frame(self) -> dict[str, Any]:
        tick = int(self.runtime.tick)
        exec_mode = str(self.config.execution_mode or "LIVE")
        return {
            "header": {
                "tick": tick,
                "status": self.status,
                "mode": self.mode,
                "execution_mode": exec_mode,
                "sim_tick": tick,
                "frame_tick": tick,
                "display_tick": tick,
                "display_frozen": exec_mode.upper() == "HEADLESS" and self.status == "RUNNING",
                "observer_lag_ticks": 0,
            }
        }

    def observer_publication_stats(self) -> dict[str, Any]:
        return {
            "live_frame_builds": int(self._stat_live_frame_builds),
            "json_dumps_publish": int(self._stat_json_dumps_publish),
            "json_publish_bytes": int(self._stat_json_publish_bytes),
            "full_frames_retained": len(self._buffer),
            "compact_history_n": len(self._timeline),
            "full_frame_cap": FULL_PUBLIC_FRAME_RETAIN,
        }

    def tick_profile_snapshot(self) -> dict[str, Any]:
        from mechanistic_mind.research import tick_profiler as tp

        snap = tp.snapshot_stats()
        snap["slow_ticks"] = tp.slow_ticks()
        snap["last_tick_wall_ms"] = round(float(self._last_tick_wall_ms), 3)
        snap["runtime_tick"] = int(self.runtime.tick)
        snap["run_id"] = self._active_run_id
        snap["evidence_mode"] = str(getattr(self.config, "evidence_mode", None) or "FULL_SCIENTIFIC")
        snap["execution_mode"] = str(self.config.execution_mode or "LIVE")
        snap["eye"] = self.tiktaalik_eye_status()
        snap["capture"] = {
            "recent": list(self._capture_timings)[-24:],
            "publication": self.observer_publication_stats(),
        }
        live = self._sci_live_dir
        snap["sci_live_dir"] = str(live) if live else None
        return snap

    def _clone_published(self, status: str | None = None) -> dict[str, Any]:
        """Shallow wrap of the published Observer frame for control receipts.

        Nested payload is treated as immutable. Control receipts must not deepcopy
        the world/agent graphs — scientific Decision/Motor receipts are unchanged.
        """
        out = self.current_frame()
        if status:
            hdr = dict(out.get("header") or {})
            hdr["status"] = status
            out = {**out, "header": hdr}
        return out

    def _loop(self) -> None:
        from mechanistic_mind.research.tick_profiler import begin_tick as _pt_begin
        from mechanistic_mind.research.tick_profiler import end_tick as _pt_end
        from mechanistic_mind.research.tick_profiler import span as _pt_span

        last_capture = 0.0
        while True:
            if self._stop_flag or self.status == "STOPPED":
                break
            if self.status != "RUNNING":
                time.sleep(0.02)
                continue
            speed = float(self.config.speed)
            ui_hz = float(self.config.ui_hz)
            target = self.config.target_tick
            request_capture = False
            tick_t0 = time.perf_counter()
            _pt_begin()
            with _pt_span("tick"):
                # Cooperative yield so capture worker is not starved of step_lock.
                with _pt_span("yield_capture"):
                    self._yield_step_lock_to_capture()
                t_lock0 = time.perf_counter()
                with self._step_lock:
                    if self._capture_timing_enabled:
                        self._sim_lock_waits_ms.append((time.perf_counter() - t_lock0) * 1000.0)
                    if self._stop_flag or self.status != "RUNNING":
                        pass
                    elif target is not None and self.runtime.tick >= int(target):
                        self.status = "PAUSED"
                    else:
                        self._scientific_step_once_unlocked()
                        with self._lock:
                            with _pt_span("session_events"):
                                self._accumulate_events_locked()
                                self._record_motion_locked()
                                self._update_perf_locked(tick=True)
                            with _pt_span("sci"):
                                self._append_scientific_locked()
                            with _pt_span("checkpoint"):
                                self._maybe_checkpoint_locked()
                        now = time.monotonic()
                        capture_period = observer_capture_period(speed, ui_hz)
                        headless = str(self.config.execution_mode or "LIVE").upper() == "HEADLESS"
                        if (not headless) and self.publication_wanted() and now - last_capture >= capture_period:
                            request_capture = True
                            last_capture = now
                # Observer capture is asynchronous — SIM must not wait for live_frame.
                # HEADLESS skips presentation capture entirely (scientific ticks unchanged).
                if request_capture:
                    with _pt_span("observer_request"):
                        self._request_observer_capture(detail=self._frame_detail_for_speed())
                sleep_s = tick_sleep_seconds(speed)
                spent = time.perf_counter() - tick_t0
                remain = sleep_s - spent
                if remain > 0:
                    with _pt_span("throttle"):
                        time.sleep(remain)
            _pt_end(int(self.runtime.tick))

    def replay_frame(self, tick: int) -> dict[str, Any]:
        """Read-only bounded replay. Never changes session/runtime."""
        out = self.frame_at_tick(tick)
        out["header"] = {
            **out.get("header", {}),
            "mode": "REPLAY",
            "live_runtime_tick": int(self.runtime.tick),
            "runtime_status": self.status,
        }
        return out

    def history(self) -> dict[str, Any]:
        with self._lock:
            ticks = [int(e.get("tick", -1)) for e in self._timeline]
            return {
                "ticks": ticks,
                "oldest_tick": ticks[0] if ticks else None,
                "newest_tick": ticks[-1] if ticks else None,
                "live_tick": int(self.runtime.tick),
                "frame_capacity": FULL_PUBLIC_FRAME_RETAIN,
                "full_frames_retained": len(self._buffer),
                "compact_history_n": len(self._timeline),
                "trajectory_capacity": self._trajectory.maxlen,
                "telemetry_capacity": self._telemetry.maxlen,
            }

    def runner_count(self) -> int:
        t = self._thread
        return 1 if t is not None and t.is_alive() else 0

    def _latest_frame_locked(self, status: str | None = None) -> dict[str, Any]:
        if self._buffer:
            frame = deepcopy(self._buffer[-1])
            if status:
                frame.setdefault("header", {})["status"] = status
            return frame
        return self._capture_locked()

    def _reset_geo_accum_locked(self) -> None:
        from mechanistic_mind.ui.psy_observer_web.geometry.live_accum import LiveTraversabilityAccumulator

        w, h = 32, 32
        try:
            planet = getattr(getattr(self.runtime, "config", None), "planet", None)
            if planet is not None:
                w, h = int(planet.width), int(planet.height)
            else:
                world = getattr(self.runtime, "world", None)
                t = getattr(world, "T", None) if world is not None else None
                if t is not None and hasattr(t, "shape"):
                    h, w = int(t.shape[0]), int(t.shape[1])
        except Exception:
            pass
        self._geo_accum = LiveTraversabilityAccumulator(width=w, height=h)
        self._geo_prev_bodies = {}
        self._geo_overlay_published = None
        self._geo_empirical_version_sent = -1
        self._geo_empirical_last_publish_mono = 0.0
        self._geo_static_version = int(self._geo_static_version or 1) + 1
        # Apply/reset invalidates any SAVED GEO so LIVE never shows prior-run maps.
        self._geo_overlay_source = "LIVE"
        self._geo_saved_overlay = None
        self._geo_saved_provenance = None

    def _geo_world_provenance_locked(self) -> dict[str, Any]:
        """Observer provenance tying GEO overlays to the current runtime world."""
        rt = self.runtime
        world = getattr(rt, "world", None)
        tmeta = (getattr(world, "terrain_meta", None) or {}) if world is not None else {}
        ameta = (getattr(world, "ambient_meta", None) or {}) if world is not None else {}
        te = getattr(getattr(getattr(rt, "config", None), "planet", None), "terrain", None)
        ae = getattr(getattr(getattr(rt, "config", None), "planet", None), "ambient", None)
        return {
            "runtime_generation": int(getattr(self, "_runtime_generation", 0) or 0),
            "session_instance": id(self),
            "experiment_seed": int(getattr(rt, "seed", getattr(self.config, "seed", 0)) or 0),
            "ecology_preset": getattr(getattr(rt, "config", None), "ecology_preset", None),
            "tick": int(getattr(world, "tick", 0) or 0) if world is not None else None,
            "terrain_enabled": bool(getattr(te, "enabled", False)) if te is not None else False,
            "terrain_seed": tmeta.get("terrain_seed"),
            "terrain_checksum": tmeta.get("checksum"),
            "terrain_generator_version": tmeta.get("generator_version"),
            "ambient_enabled": bool(getattr(ae, "enabled", False)) if ae is not None else False,
            "ambient_seed": ameta.get("ambient_seed"),
            "ambient_checksum": ameta.get("checksum"),
            "ambient_generator_version": ameta.get("generator_version"),
            "geo_static_version": int(self._geo_static_version or 0),
        }

    def _reset_sig_accum_locked(self) -> None:
        from mechanistic_mind.ui.psy_observer_web.signal_context.live_accum import (
            LiveSignalEpisodeAccumulator,
        )

        rid = str(self._active_run_id or "live")
        self._sig_accum = LiveSignalEpisodeAccumulator(run_id=rid)

    def _reset_action_realization_locked(self) -> None:
        from mechanistic_mind.ui.psy_observer_web.geometry.action_realization import (
            ActionRealizationAccumulator,
        )
        self._action_realization = ActionRealizationAccumulator(maxlen=64)

    def _reset_work_ecology_locked(self) -> None:
        from mechanistic_mind.ui.psy_observer_web.geometry.work_ecology import (
            WorkEcologyAccumulator,
        )
        self._work_ecology = WorkEcologyAccumulator(maxlen=64)

    def _observe_action_realization_locked(self) -> None:
        """O(agents) forensic receipt after each scientific tick."""
        if self._action_realization is None:
            self._reset_action_realization_locked()
        assert self._action_realization is not None
        from mechanistic_mind.ui.psy_observer_web.geometry.action_realization import (
            collect_from_runtime,
        )
        exp_slot = getattr(self.runtime, "experimenter_slot", None)
        for receipt in collect_from_runtime(self.runtime, experimenter_slot=exp_slot):
            self._action_realization.observe(receipt)

    def _observe_work_ecology_locked(self) -> None:
        """O(agents) work budget receipt after each scientific tick."""
        if self._work_ecology is None:
            self._reset_work_ecology_locked()
        assert self._work_ecology is not None
        from mechanistic_mind.ui.psy_observer_web.geometry.work_ecology import (
            collect_work_budgets_from_runtime,
        )
        exp_slot = getattr(self.runtime, "experimenter_slot", None)
        ar_latest = dict(self._action_realization.latest) if self._action_realization else {}
        for receipt in collect_work_budgets_from_runtime(
            self.runtime,
            experimenter_slot=exp_slot,
            action_realization_latest=ar_latest,
        ):
            self._work_ecology.observe(receipt)

    def _reset_locomotor_economy_locked(self) -> None:
        from mechanistic_mind.ui.psy_observer_web.geometry.locomotor_economy import (
            LocomotorEconomyAccumulator,
        )
        self._locomotor_economy = LocomotorEconomyAccumulator(maxlen=64)

    def _observe_locomotor_economy_locked(self) -> None:
        if self._locomotor_economy is None:
            self._reset_locomotor_economy_locked()
        assert self._locomotor_economy is not None
        from mechanistic_mind.ui.psy_observer_web.geometry.locomotor_economy import (
            collect_locomotor_from_runtime,
        )
        exp_slot = getattr(self.runtime, "experimenter_slot", None)
        for receipt in collect_locomotor_from_runtime(self.runtime, experimenter_slot=exp_slot):
            self._locomotor_economy.observe(receipt)

    def action_realization_history(
        self, *, agent_id: str | None = None, limit: int = 48
    ) -> dict[str, Any]:
        with self._lock:
            if self._action_realization is None:
                return {"accepted": True, "receipts": [], "status": "EMPTY"}
            rows = self._action_realization.history(agent_id=agent_id, limit=limit)
            return {
                "accepted": True,
                "receipts": rows,
                "latest": dict(self._action_realization.latest),
                "honesty": {"observer_only": True, "not_cognition": True},
            }

    def work_ecology_history(
        self, *, agent_id: str | None = None, limit: int = 48
    ) -> dict[str, Any]:
        with self._lock:
            if self._work_ecology is None:
                return {"accepted": True, "receipts": [], "status": "EMPTY"}
            rows = self._work_ecology.history(agent_id=agent_id, limit=limit)
            return {
                "accepted": True,
                "receipts": rows,
                "latest": dict(self._work_ecology.latest),
                "episodes": dict(getattr(self._work_ecology, "_episode", {})),
                "honesty": {"observer_only": True, "physical_language_only": True},
            }

    def _reset_experimenter_locked(self) -> None:
        from mechanistic_mind.ui.psy_observer_web.experimenter_control import ExperimenterController
        # Preserve intervention provenance across reset of controller body.
        ever = bool(self._experimenter_intervention_ever)
        self._experimenter = ExperimenterController()
        if ever:
            self._experimenter.intervention_active = True
            self._experimenter_intervention_ever = True

    def _ensure_experimenter_locked(self) -> Any:
        if self._experimenter is None:
            self._reset_experimenter_locked()
        return self._experimenter

    def _experimenter_pre_step_unlocked(self) -> None:
        ctrl = self._experimenter
        if ctrl is None or not ctrl.active:
            return
        from mechanistic_mind.ui.psy_observer_web.experimenter_control import (
            apply_experimenter_pre_step,
        )
        from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
        if isinstance(self.runtime, TwoAgentRuntime):
            apply_experimenter_pre_step(self.runtime, ctrl)

    def _experimenter_post_step_unlocked(self) -> None:
        ctrl = self._experimenter
        if ctrl is None or not ctrl.active:
            return
        from mechanistic_mind.ui.psy_observer_web.experimenter_control import (
            record_experimenter_post_step,
        )
        from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
        if isinstance(self.runtime, TwoAgentRuntime):
            record_experimenter_post_step(self.runtime, ctrl)
            # Contact involving experimenter
            for r in getattr(self.runtime, "last_contacts", []) or []:
                if not r or not r.get("contact"):
                    continue
                pair = r.get("pair") or (0, 1)
                if ctrl.slot_index is not None and int(ctrl.slot_index) in pair:
                    other = pair[0] if pair[1] == ctrl.slot_index else pair[1]
                    ctrl.log(
                        "EXPERIMENTER_CONTACT",
                        int(self.runtime.tick),
                        with_body=f"body-{other}",
                    )

    def _experimenter_compact_locked(self) -> dict[str, Any]:
        ctrl = self._ensure_experimenter_locked()
        st = ctrl.status()
        events = list(ctrl.event_log)[-24:]
        target = None
        if ctrl.target_agent_id and hasattr(self.runtime, "slots"):
            try:
                tid = int(str(ctrl.target_agent_id).replace("agent_", ""))
                if 0 <= tid < len(self.runtime.slots) and tid != ctrl.slot_index:
                    tb = self.runtime.slots[tid].body
                    eb = (
                        self.runtime.slots[ctrl.slot_index].body
                        if ctrl.slot_index is not None else None
                    )
                    if eb is not None:
                        dx = float(tb.x) - float(eb.x)
                        dy = float(tb.y) - float(eb.y)
                        target = {
                            "agent_id": f"agent_{tid}",
                            "distance": (dx * dx + dy * dy) ** 0.5,
                            "dx": dx, "dy": dy,
                            "x": float(tb.x), "y": float(tb.y),
                            "action": self.runtime.slots[tid].last_selected_action,
                            "selection_source": (
                                (self.runtime.slots[tid].cognition or {})
                                .get("last_selection") or {}
                            ).get("source"),
                            "field_A": (self.runtime.slots[tid].last_agent_observation or {}).get("local.FIELD_A"),
                            "field_B": (self.runtime.slots[tid].last_agent_observation or {}).get("local.FIELD_B"),
                        }
            except (ValueError, TypeError, IndexError):
                target = None
        return {
            **st,
            "intervention_ever": bool(self._experimenter_intervention_ever),
            "recent_events": events,
            "target": target,
            "captures": [
                {"capture_id": c.capture_id, "start_tick": c.start_tick, "end_tick": c.end_tick}
                for c in ctrl.captures[-8:]
            ],
            "honesty": {
                "exploratory_not_causal": True,
                "observer_only_selection": True,
                "no_chat": True,
            },
        }

    def experimenter_status(self) -> dict[str, Any]:
        with self._lock:
            return self._experimenter_compact_locked()

    def experimenter_spawn(
        self,
        *,
        x: float | None = None,
        y: float | None = None,
        theta: float = 0.0,
        near_agent: int | None = None,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
        from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
        from mechanistic_mind.ui.psy_observer_web.experimenter_control import (
            promote_physical_to_two_agent_host,
            spawn_experimenter_body,
        )

        before = self._control_state()
        if run_id is not None and self._active_run_id and str(run_id) != str(self._active_run_id):
            return {"accepted": False, "error": "SPAWN_REJECTED:STALE_RUN_ID"}
        with self._step_lock:
            with self._lock:
                ctrl = self._ensure_experimenter_locked()
                if self.runtime is None:
                    return {
                        "accepted": False,
                        "error": "SPAWN_REJECTED:RUNTIME_UNAVAILABLE",
                    }
                # Single-agent worlds use PhysicalSystemRuntime; experimenter spawn
                # appends onto TwoAgentRuntime.slots. Promote host without replacing
                # the autonomous agent object (preserves cognition/body state).
                if not isinstance(self.runtime, TwoAgentRuntime):
                    if not isinstance(self.runtime, PhysicalSystemRuntime):
                        return {
                            "accepted": False,
                            "error": "SPAWN_REJECTED:RUNTIME_UNAVAILABLE",
                            "detail": type(self.runtime).__name__,
                        }
                    self.runtime = promote_physical_to_two_agent_host(self.runtime)
                n_slots = len(self.runtime.slots)
                if near_agent is not None:
                    ni = int(near_agent)
                    if not (0 <= ni < n_slots) or (
                        self.runtime.experimenter_slot is not None
                        and ni == int(self.runtime.experimenter_slot)
                    ):
                        return {
                            "accepted": False,
                            "error": "SPAWN_REJECTED:NO_VALID_TARGET",
                            "detail": f"near_agent={ni} slots={n_slots}",
                        }
                    b = self.runtime.slots[ni].body
                    x = float(b.x) + 2.0
                    y = float(b.y)
                if x is None or y is None:
                    if n_slots < 1:
                        return {
                            "accepted": False,
                            "error": "SPAWN_REJECTED:NO_VALID_TARGET",
                        }
                    x = float(self.runtime.slots[0].body.x) + 3.0
                    y = float(self.runtime.slots[0].body.y)
                try:
                    out = spawn_experimenter_body(
                        self.runtime, x=float(x), y=float(y), theta=float(theta), controller=ctrl,
                    )
                except Exception as exc:  # noqa: BLE001 — surface to Interaction Lab
                    return {
                        "accepted": False,
                        "error": "SPAWN_REJECTED:RUNTIME_UNAVAILABLE",
                        "detail": str(exc),
                    }
                if out.get("accepted"):
                    self._experimenter_intervention_ever = True
                    ctrl.begin_recording(self.runtime)
                    # Scientific history marker
                    if self._sci_writer is not None:
                        try:
                            self._sci_writer.append_event({
                                "event_type": "EXPERIMENTER_BODY_SPAWNED",
                                "tick": int(self.runtime.tick),
                                "experimenter_intervention": True,
                                **ctrl.spawn_meta,
                            })
                        except Exception:
                            pass
                frame = self._capture_locked(detail="full")
        if out.get("accepted"):
            self._maybe_push(frame, force=True)
        return {**out, "frame_tick": int(self.runtime.tick), "control_before": before}

    def experimenter_remove(self) -> dict[str, Any]:
        from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
        from mechanistic_mind.ui.psy_observer_web.experimenter_control import remove_experimenter_body

        with self._step_lock:
            with self._lock:
                ctrl = self._ensure_experimenter_locked()
                if not isinstance(self.runtime, TwoAgentRuntime):
                    return {"accepted": False, "error": "TwoAgentRuntime required"}
                out = remove_experimenter_body(self.runtime, ctrl)
                frame = self._capture_locked(detail="full")
        if out.get("accepted"):
            self._maybe_push(frame, force=True)
        return out

    def experimenter_command(
        self,
        *,
        kind: str,
        action: str | None = None,
        amplitude: float | None = None,
        specimen_id: str | None = None,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        if run_id is not None and self._active_run_id and str(run_id) != str(self._active_run_id):
            return {"accepted": False, "error": "stale run_id"}
        if self.status == "STOPPED":
            return {"accepted": False, "error": "run ended"}
        with self._lock:
            ctrl = self._ensure_experimenter_locked()
            if not ctrl.active:
                return {"accepted": False, "error": "controlled body not spawned"}
            # SPECIMEN_REPLAY: queue inject immediately via library
            if kind == "SPECIMEN_REPLAY" and specimen_id:
                return self._experimenter_replay_specimen_locked(specimen_id, amplitude=amplitude)
            return ctrl.enqueue(kind, action=action, amplitude=amplitude, specimen_id=specimen_id)

    def experimenter_set_mobility(self, mode: str) -> dict[str, Any]:
        with self._lock:
            ctrl = self._ensure_experimenter_locked()
            out = ctrl.set_mobility_mode(mode)
            if out.get("accepted") and self._sci_writer is not None:
                try:
                    self._sci_writer.append_event({
                        "event_type": "EXPERIMENTER_MOBILITY_MODE",
                        "tick": int(self.runtime.tick),
                        "experimenter_mobility_mode": out.get("mobility_mode"),
                        "work_source": (
                            "EXPERIMENTER_RESEARCH_SUPPLY"
                            if out.get("mobility_mode") == "RESEARCH_MOBILITY"
                            else "ORDINARY_WORK"
                        ),
                        "experimenter_intervention": True,
                    })
                except Exception:
                    pass
            frame = self._capture_locked(detail="full")
        if out.get("accepted"):
            self._maybe_push(frame, force=True)
        return {**out, "frame_tick": int(self.runtime.tick)}

    def _experimenter_replay_specimen_locked(
        self, specimen_id: str, *, amplitude: float | None = None
    ) -> dict[str, Any]:
        from mechanistic_mind.ui.psy_observer_web.signal_context.natural_replay import (
            queue_natural_replay,
        )
        ctrl = self._ensure_experimenter_locked()
        if not ctrl.active or ctrl.slot_index is None:
            return {"accepted": False, "error": "controlled body not spawned"}
        lib = self._signal_specimen_library
        if lib is None:
            return {"accepted": False, "error": "unavailable specimen library"}
        spec = lib.get(specimen_id) if hasattr(lib, "get") else None
        if spec is None:
            return {"accepted": False, "error": "unavailable specimen"}
        # Replay from controlled body location via inject_source cells
        slot = int(ctrl.slot_index)
        amp = float(amplitude) if amplitude is not None else None
        try:
            # Use existing queue path; override origin to experimenter slot cells
            from mechanistic_mind.physical_system.physical_signal import _site_cells
            body = self.runtime.slots[slot].body
            cfg = self.runtime.slots[slot].config.body
            w = int(self.runtime.world.T.shape[1])
            h = int(self.runtime.world.T.shape[0])
            cells = _site_cells(body, cfg, w, h)
            ch = str(getattr(spec, "channel", "A") or "A")
            a = float(amp if amp is not None else getattr(spec, "amplitude", 0.7) or 0.7)
            self.runtime.inject_source(
                channel=ch,
                amplitude=a,
                cells=cells,
                trigger="experimenter_control",
                observer_source_id=f"experimenter:natural:{specimen_id}",
            )
            ctrl.log(
                "EXPERIMENTER_NATURAL_SIGNAL_REPLAYED",
                int(self.runtime.tick),
                specimen_id=specimen_id,
                channel=ch,
                amplitude=a,
            )
            return {
                "accepted": True,
                "kind": "NATURAL_SPECIMEN_REPLAY",
                "specimen_id": specimen_id,
                "fidelity": getattr(spec, "fidelity", "EXACT") if hasattr(spec, "fidelity") else "EXACT",
            }
        except Exception as e:
            return {"accepted": False, "error": str(e)}

    def experimenter_set_target(self, agent_id: str | None) -> dict[str, Any]:
        with self._lock:
            ctrl = self._ensure_experimenter_locked()
            ctrl.target_agent_id = agent_id
            return {"accepted": True, "target_agent_id": agent_id, "observer_only": True}

    def experimenter_capture(self) -> dict[str, Any]:
        from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime

        with self._step_lock:
            with self._lock:
                ctrl = self._ensure_experimenter_locked()
                if not isinstance(self.runtime, TwoAgentRuntime):
                    return {"accepted": False, "error": "TwoAgentRuntime required"}
                if not ctrl.active and not ctrl.scripted_commands:
                    return {"accepted": False, "error": "nothing to capture"}
                cap = ctrl.capture(
                    self.runtime,
                    run_id=str(self._active_run_id or "live"),
                )
                return {"accepted": True, "capture": cap.to_dict()}

    def experimenter_list_captures(self) -> dict[str, Any]:
        with self._lock:
            ctrl = self._ensure_experimenter_locked()
            return {
                "captures": [c.to_dict() for c in ctrl.captures],
                "honesty": {"exploratory_not_causal": True},
            }

    def experimenter_test_capture(self, capture_id: str, *, horizon: int = 40) -> dict[str, Any]:
        from mechanistic_mind.ui.psy_observer_web.experimenter_control import (
            run_source_context_factorial,
            build_interaction_fingerprint,
        )
        with self._lock:
            ctrl = self._ensure_experimenter_locked()
            cap = next((c for c in ctrl.captures if c.capture_id == capture_id), None)
            if cap is None:
                return {"accepted": False, "error": "capture not found"}
            factorial = run_source_context_factorial(cap, seed=int(self.config.seed), horizon=horizon)
            fp = build_interaction_fingerprint(factorial)
            return {
                "accepted": bool(factorial.get("accepted")),
                "factorial": factorial,
                "fingerprint": fp,
                "honesty": {
                    "manual_not_causal": True,
                    "matched_branches_are_hypothesis_test": True,
                },
            }

    def _observe_signal_events_locked(self, events: list[dict[str, Any]]) -> None:
        """Bounded LIVE signal-episode detection (Observer-only)."""
        if self._sig_accum is None:
            self._reset_sig_accum_locked()
        assert self._sig_accum is not None
        if self._active_run_id and self._sig_accum.run_id != str(self._active_run_id):
            self._sig_accum.reset(run_id=str(self._active_run_id))
        self._sig_accum.observe_events(events)
        # SIGINT-03: O(sources this tick) specimen index — not O(history)
        try:
            from mechanistic_mind.ui.psy_observer_web.signal_context.natural_replay import (
                capture_natural_emissions_from_runtime,
            )
            from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime

            if isinstance(self.runtime, TwoAgentRuntime) and self._sig_live_enabled:
                capture_natural_emissions_from_runtime(
                    self.runtime,
                    run_id=str(self._active_run_id or "live"),
                    library=self._ensure_specimen_library(),
                )
        except Exception:
            pass

    def signal_context_live_summary(self) -> dict[str, Any]:
        with self._step_lock:
            if self._sig_accum is None:
                self._reset_sig_accum_locked()
            return self._sig_accum.compact_summary()

    def signal_episode_inspect(self, episode_id: str) -> dict[str, Any]:
        """Lookup a LIVE-buffered episode by id (no matched controls — ANALYZE only)."""
        with self._step_lock:
            if self._sig_accum is None:
                return {"accepted": False, "error": "no live signal accumulator"}
            for ep in self._sig_accum._episodes:
                if str(ep.get("episode_id")) == str(episode_id):
                    return {
                        "accepted": True,
                        "episode": ep,
                        "matched_controls": "ANALYZE_RESULTS_ONLY",
                        "honesty": {
                            "observer_only": True,
                            "no_communication_claim": True,
                            "reception_to_cognition": "NOT_ESTABLISHED",
                        },
                    }
            return {"accepted": False, "error": "episode not in LIVE buffer", "episode_id": episode_id}

    def _ensure_specimen_library(self) -> Any:
        if self._signal_specimen_library is None:
            from mechanistic_mind.ui.psy_observer_web.signal_context.natural_replay import (
                NaturalSignalLibrary,
            )
            self._signal_specimen_library = NaturalSignalLibrary(maxlen=256)
        return self._signal_specimen_library

    def list_signal_specimens(self, *, channel: str | None = None, limit: int = 64) -> dict[str, Any]:
        lib = self._ensure_specimen_library()
        return {
            "accepted": True,
            "specimens": lib.list(channel=channel, limit=limit),
            "note": "Experimenter-side physical recordings — not messages.",
        }

    def save_signal_specimen_from_event(self, event: dict[str, Any]) -> dict[str, Any]:
        """SAVE AS SIGNAL SPECIMEN from EMITTED event / receipt evidence (Observer-only)."""
        from mechanistic_mind.ui.psy_observer_web.signal_context.natural_replay import (
            specimen_from_emission_evidence,
        )

        ev = event or {}
        evidence = ev.get("evidence") if isinstance(ev.get("evidence"), dict) else ev
        if not isinstance(evidence, dict):
            return {"accepted": False, "error": "missing emission evidence"}
        # Prefer live receipt cells if emission_id matches
        with self._step_lock:
            rec = getattr(self.runtime, "last_signal_receipt", None) or {}
            for src in rec.get("sources") or []:
                if src.get("emission_id") and src.get("emission_id") == evidence.get("emission_id"):
                    evidence = {**evidence, **{k: v for k, v in src.items() if v is not None}}
                    break
            tick = int(ev.get("tick") or getattr(self.runtime, "tick", -1))
            run_id = str(self._active_run_id or "live")
            sp = specimen_from_emission_evidence(evidence, run_id=run_id, tick=tick)
            lib = self._ensure_specimen_library()
            saved = lib.add(sp)
        return {
            "accepted": True,
            "specimen": saved.to_dict(),
            "event_type": "NATURAL_SIGNAL_SPECIMEN_CREATED",
            "honesty": {"observer_only": True, "not_a_message": True},
        }

    def replay_signal_specimen_live(
        self,
        specimen_id: str,
        *,
        target: str = "PEER",
        mode: str = "EXACT",
        amplitude_scale: float = 1.0,
    ) -> dict[str, Any]:
        """LIVE uncontrolled replay — marked UNCONTROLLED_LIVE_REPLAY (not causal verdict)."""
        from mechanistic_mind.ui.psy_observer_web.signal_context.natural_replay import (
            NaturalSignalSpecimen,
            queue_natural_replay,
        )
        from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime

        lib = self._ensure_specimen_library()
        sp = lib.get(specimen_id)
        if sp is None:
            return {"accepted": False, "error": "specimen not found", "specimen_id": specimen_id}
        with self._step_lock:
            rt = self.runtime
            if not isinstance(rt, TwoAgentRuntime):
                return {"accepted": False, "error": "TwoAgentRuntime required for signal replay"}
            recv = 1
            if target == "SELF":
                eid = str(sp.emitter_agent_id or "")
                recv = 0 if eid.endswith("0") else 1
            elif target == "PEER":
                eid = str(sp.emitter_agent_id or "")
                recv = 1 if eid.endswith("0") else 0
            q = queue_natural_replay(
                rt,
                sp,
                mode=mode,
                amplitude_scale=float(amplitude_scale),
                target=target,
                receiver_slot=recv,
                observer_source_id=f"live_replay:{specimen_id}",
            )
            trial = {
                "trial_id": f"live-{int(rt.tick)}-{specimen_id[:8]}",
                "status": "UNCONTROLLED_LIVE_REPLAY",
                "tick": int(rt.tick),
                "specimen_id": specimen_id,
                "target": target,
                "mode": mode,
                "queue": q,
                "note": "Not causal evidence — reproduce via matched branching.",
            }
            self._uncontrolled_live_replays.append(trial)
            if len(self._uncontrolled_live_replays) > 64:
                self._uncontrolled_live_replays = self._uncontrolled_live_replays[-64:]
        if q.get("accepted") and self.status == "RUNNING":
            self._request_observer_capture(detail=self._frame_detail_for_speed())
        return {"accepted": bool(q.get("accepted")), **trial}

    def list_signal_repertoire(self, *, filter_name: str = "ALL", limit: int = 64) -> dict[str, Any]:
        """On-demand SIGINT-04 repertoire browser (not embedded in LIVE frames)."""
        from mechanistic_mind.ui.psy_observer_web.run_finalize import default_results_root

        root = Path(self.config.results_root) if self.config.results_root else default_results_root()
        sci = root / "signal_context_interpreter"
        if not sci.is_dir():
            sci = Path(__file__).resolve().parents[3] / "results" / "signal_context_interpreter"
        dirs = sorted(
            [p for p in sci.glob("beta2_sigint_04_*") if p.is_dir()],
            key=lambda p: p.name,
            reverse=True,
        ) if sci.is_dir() else []
        if not dirs:
            return {
                "accepted": True,
                "filter": filter_name,
                "specimens": [],
                "families": [],
                "note": "No SIGINT-04 artifacts yet — run scripts/run_beta2_sigint_04.py",
                "honesty": {"not_communication": True, "on_demand_only": True},
            }
        d = dirs[0]
        def _load(name: str, default=None):
            p = d / name
            if not p.is_file():
                return default if default is not None else []
            return json.loads(p.read_text(encoding="utf-8"))

        rep = _load("natural_signal_repertoire.json", {})
        families = _load("signal_families.json", [])
        fps = {f.get("specimen_id"): f for f in _load("response_fingerprints.json", [])}
        candidates = {c.get("specimen_id"): c for c in _load("downstream_response_candidates.json", [])}
        inert_ids = {
            x.get("specimen_id") for x in _load("inert_under_tested_contexts.json", [])
        }
        rows = []
        for sp in (rep.get("specimens") or [])[: max(1, min(256, int(limit) * 2))]:
            sid = sp.get("specimen_id")
            fp = fps.get(sid) or {}
            cand = candidates.get(sid)
            tags = list((cand or {}).get("classification") or fp.get("tags") or [])
            evidence = fp.get("evidence_class") or (
                "UNTESTED" if sid not in inert_ids and not cand else None
            )
            if sid in inert_ids and not tags:
                evidence = "INERT_UNDER_TESTED_CONTEXTS"
            if cand:
                evidence = cand.get("stage_b", cand.get("stage_a", {})).get("evidence_class") or evidence
            filt = str(filter_name or "ALL").upper().replace(" ", "_")
            if filt == "UNTESTED" and evidence not in (None, "UNTESTED"):
                continue
            if filt == "INERT_UNDER_TESTED_CONTEXTS" and evidence != "INERT_UNDER_TESTED_CONTEXTS" and sid not in inert_ids:
                continue
            if filt == "COGNITION_CANDIDATES" and "COGNITION_CANDIDATE" not in tags:
                continue
            if filt == "ACTION_CANDIDATES" and "ACTION_CANDIDATE" not in tags:
                continue
            if filt == "TRAJECTORY_CANDIDATES" and "TRAJECTORY_CANDIDATE" not in tags:
                continue
            rows.append({
                **{k: sp.get(k) for k in (
                    "specimen_id", "channel", "trigger", "amplitude",
                    "source_tick", "emitter_agent_id", "reconstruction_completeness",
                )},
                "family_id": fp.get("family_id") or (cand or {}).get("family_id"),
                "evidence_class": evidence,
                "tags": tags,
                "fingerprint": {
                    "FIELD_exposure": fp.get("FIELD_exposure"),
                    "selection_source": fp.get("selection_source"),
                    "action": fp.get("action"),
                    "trajectory": fp.get("trajectory"),
                    "confidence": fp.get("confidence"),
                },
                "candidate": cand,
            })
            if len(rows) >= int(limit):
                break
        return {
            "accepted": True,
            "filter": filter_name,
            "experiment_dir": d.name,
            "specimens": rows,
            "families": families[:32],
            "n_specimens": len(rows),
            "honesty": {"not_communication": True, "on_demand_only": True},
        }

    def list_interaction_episodes(self, *, limit: int = 32) -> dict[str, Any]:
        """On-demand SIGINT-05 interaction episode browser (not in LIVE frames)."""
        from mechanistic_mind.ui.psy_observer_web.run_finalize import default_results_root

        root = Path(self.config.results_root) if self.config.results_root else default_results_root()
        sci = root / "signal_context_interpreter"
        if not sci.is_dir():
            sci = Path(__file__).resolve().parents[3] / "results" / "signal_context_interpreter"
        dirs = sorted(
            [p for p in sci.glob("beta2_sigint_05_*") if p.is_dir()],
            key=lambda p: p.name,
            reverse=True,
        ) if sci.is_dir() else []
        if not dirs:
            return {
                "accepted": True,
                "episodes": [],
                "note": "No SIGINT-05 artifacts yet — run scripts/run_beta2_sigint_05.py",
                "honesty": {"not_conversation": True, "on_demand_only": True},
            }
        d = dirs[0]

        def _load(name: str, default=None):
            p = d / name
            if not p.is_file():
                return default if default is not None else []
            return json.loads(p.read_text(encoding="utf-8"))

        rep = _load("interaction_episode_repertoire.json", {})
        ref = _load("reference_episode_1554_1563.json", {})
        trials = _load("matched_episode_trials.json", [])
        coupling = _load("trajectory_coupling.json", [])
        by_ep = {}
        for t in trials:
            by_ep.setdefault(t.get("episode_id"), []).append(t)
        rows = []
        episodes = list(rep.get("episodes") or [])
        if ref and not any(e.get("start_tick") == 1554 for e in episodes):
            episodes = [ref] + episodes
        for ep in episodes[: max(1, min(64, int(limit)))]:
            eid = ep.get("episode_id")
            ts = by_ep.get(eid) or []
            levels = {}
            if ts:
                # OR across trials
                for key in ("L1_exposure", "L2_cognition", "L3_action", "L4_trajectory", "L5_coupling"):
                    levels[key] = any((t.get("levels") or {}).get(key) for t in ts)
            coup = next((c for c in coupling if c.get("episode_id") == eid), None)
            rows.append({
                "episode_id": eid,
                "start_tick": ep.get("start_tick"),
                "end_tick": ep.get("end_tick"),
                "duration": ep.get("duration"),
                "n_components": ep.get("n_components") or len(ep.get("components") or []),
                "components": ep.get("components") or [],
                "source_run_id": ep.get("source_run_id"),
                "reconstruction": ep.get("reconstruction"),
                "alternation_count": ep.get("alternation_count"),
                "emitter_sequence": ep.get("emitter_sequence"),
                "channel_sequence": ep.get("channel_sequence"),
                "temporal_strip": ep.get("temporal_strip"),
                "levels": levels,
                "n_trials": len(ts),
                "coupling_sample": (coup or {}).get("coupling_delta_full_vs_control"),
            })
        return {
            "accepted": True,
            "experiment_dir": d.name,
            "episodes": rows,
            "reference": {
                "start_tick": ref.get("start_tick"),
                "end_tick": ref.get("end_tick"),
                "reconstruction": ref.get("reconstruction"),
                "temporal_strip": ref.get("temporal_strip"),
            } if ref else None,
            "honesty": {"not_conversation": True, "on_demand_only": True},
        }

    def list_cognitive_forensics(self, *, limit: int = 8) -> dict[str, Any]:
        """On-demand SIGINT-06 forensic summaries (not in LIVE frames)."""
        from mechanistic_mind.ui.psy_observer_web.run_finalize import default_results_root

        root = Path(self.config.results_root) if self.config.results_root else default_results_root()
        sci = root / "signal_context_interpreter"
        if not sci.is_dir():
            sci = Path(__file__).resolve().parents[3] / "results" / "signal_context_interpreter"
        dirs = sorted(
            [p for p in sci.glob("beta2_sigint_06_*") if p.is_dir()],
            key=lambda p: p.name,
            reverse=True,
        ) if sci.is_dir() else []
        if not dirs:
            return {
                "accepted": True,
                "trials": [],
                "note": "No SIGINT-06 artifacts yet — run scripts/run_beta2_sigint_06.py",
                "honesty": {"forensic_only": True, "on_demand_only": True},
            }
        d = dirs[0]

        def _load(name: str, default=None):
            p = d / name
            if not p.is_file():
                return default if default is not None else []
            return json.loads(p.read_text(encoding="utf-8"))

        report = _load("report.json", {})
        bottlenecks = _load("bottleneck_analysis.json", [])
        pipelines = _load("cognitive_pipeline_diff.json", [])
        first = _load("first_divergence.json", [])
        by_ep = {}
        for row in bottlenecks:
            hid = (row.get("hit") or {}).get("episode_id")
            by_ep[hid] = {"bottleneck": row.get("bottleneck"), "hit": row.get("hit")}
        for row in pipelines:
            hid = (row.get("hit") or {}).get("episode_id")
            by_ep.setdefault(hid, {})["pipeline_ladder"] = row.get("pipeline_ladder")
            by_ep[hid]["parallel_lanes"] = row.get("parallel_lanes")
            by_ep[hid]["hit"] = row.get("hit")
        for row in first:
            hid = (row.get("hit") or {}).get("episode_id")
            by_ep.setdefault(hid, {})["ladder_summary"] = row.get("ladder_summary")
        trials = list(by_ep.values())[: max(1, min(16, int(limit)))]
        return {
            "accepted": True,
            "experiment_dir": d.name,
            "verdicts": (report or {}).get("verdicts"),
            "trials": trials,
            "honesty": {"forensic_only": True, "on_demand_only": True, "not_communication": True},
        }

    def replay_interaction_episode_live(
        self,
        episode: dict[str, Any],
        *,
        mode: str = "FULL",
    ) -> dict[str, Any]:
        """LIVE uncontrolled episode replay — not causal evidence."""
        from mechanistic_mind.ui.psy_observer_web.signal_context.interaction_episode import (
            NaturalSignalEpisode,
            EpisodeComponent,
            schedule_for_mode,
            select_components,
            _deposit_cells_for_component,
            _amp,
            TRIGGER_EPISODE_REPLAY,
        )
        from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime

        comps_raw = episode.get("components") or []
        if not comps_raw:
            return {"accepted": False, "error": "episode missing components"}
        components = tuple(EpisodeComponent.from_dict(c) for c in comps_raw)
        ep = NaturalSignalEpisode(
            episode_id=str(episode.get("episode_id") or "live-ep"),
            source_run_id=str(episode.get("source_run_id") or "live"),
            start_tick=int(episode.get("start_tick") or 0),
            end_tick=int(episode.get("end_tick") or 0),
            components=components,
            reconstruction=str(episode.get("reconstruction") or "PARTIAL"),
        )
        mode_map = {
            "FULL": "FULL_EPISODE",
            "A→B": "A_TO_B_ONLY",
            "A_TO_B_ONLY": "A_TO_B_ONLY",
            "B→A": "B_TO_A_ONLY",
            "B_TO_A_ONLY": "B_TO_A_ONLY",
            "SHUFFLED": "TIMING_SHUFFLED",
            "REVERSED": "ORDER_REVERSED",
        }
        m = mode_map.get(mode, mode)
        with self._step_lock:
            rt = self.runtime
            if not isinstance(rt, TwoAgentRuntime):
                return {"accepted": False, "error": "TwoAgentRuntime required"}
            # Queue first scheduled tick only for LIVE (subsequent via pending each step is hard);
            # inject all components for ISOLATED, else inject Δt==0 components now.
            comps = select_components(ep, m)
            sched = schedule_for_mode(comps, m)
            now = [c for t, c in sched if t == 0]
            if not now and sched:
                # inject earliest tick components
                t0 = min(t for t, _ in sched)
                now = [c for t, c in sched if t == t0]
            n = 0
            for c in now:
                amp = _amp(c)
                if amp is None:
                    continue
                cells = _deposit_cells_for_component(rt, c)
                if not cells:
                    continue
                rt.inject_source(
                    channel=c.channel,
                    amplitude=float(amp),
                    cells=cells,
                    trigger=TRIGGER_EPISODE_REPLAY,
                    observer_source_id=f"live_episode:{ep.episode_id}",
                )
                n += 1
            trial = {
                "trial_id": f"live-ep-{int(rt.tick)}-{ep.episode_id[:8]}",
                "status": "UNCONTROLLED_LIVE_REPLAY",
                "tick": int(rt.tick),
                "episode_id": ep.episode_id,
                "mode": m,
                "n_injected_this_step": n,
                "note": "LIVE injects current-tick components only; causal claims need matched branching.",
            }
            self._uncontrolled_live_replays.append(trial)
            if len(self._uncontrolled_live_replays) > 64:
                self._uncontrolled_live_replays = self._uncontrolled_live_replays[-64:]
        if n and self.status == "RUNNING":
            self._request_observer_capture(detail=self._frame_detail_for_speed())
        return {"accepted": n > 0, **trial}

    def _geo_overlay_for_capture_locked(self, *, detail: str = "compact") -> dict[str, Any] | None:
        """Under `_step_lock`: return overlay for capture — LIVE current runtime or SAVED buffer.

        Never silently substitutes an older run's map when LIVE samples are missing.
        """
        if not self._geo_live_enabled:
            return {
                "status": "DISABLED",
                "observer_only": True,
                "note": "GEO LIVE processing disabled (perf matrix / isolation).",
            }
        source = str(getattr(self, "_geo_overlay_source", "LIVE") or "LIVE").upper()
        if source == "SAVED":
            saved = self._geo_saved_overlay
            if isinstance(saved, dict):
                out = dict(saved)
                out["geo_source"] = "SAVED"
                out["provenance"] = self._geo_saved_provenance or out.get("provenance")
                return out
            return {
                "status": "LIVE_GEO_UNAVAILABLE",
                "observer_only": True,
                "geo_source": "SAVED",
                "n_observations": 0,
                "note": "SAVED GEO requested but no hydrated overlay is loaded.",
                "provenance": self._geo_saved_provenance,
            }
        if self._geo_accum is None:
            self._reset_geo_accum_locked()
        full = str(detail).lower() != "compact"
        n_live = int(getattr(self._geo_accum, "_n_observations", 0) or 0)
        if not full:
            # O(1) — never rebuild W×H grids under the simulation lock.
            cached = self._geo_overlay_published
            if cached is not None:
                out = dict(cached) if isinstance(cached, dict) else cached
                if isinstance(out, dict):
                    out["geo_source"] = "LIVE"
                    if int(out.get("n_observations") or 0) <= 0:
                        out["status"] = "LIVE_GEO_UNAVAILABLE"
                        out["note"] = (
                            "LIVE GEO unavailable — no MOVE empirical samples for the current runtime. "
                            "Not falling back to older runs."
                        )
                return out
            if n_live <= 0:
                return {
                    "status": "LIVE_GEO_UNAVAILABLE",
                    "observer_only": True,
                    "geo_source": "LIVE",
                    "n_observations": 0,
                    "pending_refresh": True,
                    "note": (
                        "LIVE GEO unavailable — no MOVE empirical samples for the current runtime. "
                        "Not falling back to older runs."
                    ),
                }
            return {
                "status": "AVAILABLE",
                "pending_refresh": True,
                "observer_only": True,
                "geo_source": "LIVE",
                "n_observations": n_live,
                "note": "Overlay refresh runs outside step_lock.",
            }
        payload = self._build_geo_overlay_payload(detail=detail)
        payload = dict(payload)
        payload["geo_source"] = "LIVE"
        if int(payload.get("n_observations") or 0) <= 0:
            payload["status"] = "LIVE_GEO_UNAVAILABLE"
            payload["note"] = (
                "LIVE GEO unavailable — no MOVE empirical samples for the current runtime. "
                "Not falling back to older runs."
            )
            payload["class_grid"] = None
            payload["opposing_rate_grid"] = None
            payload["worst_alignment_grid"] = None
            payload["attempt_grid"] = None
            payload["glyphs"] = []
        return payload

    def _build_geo_overlay_payload(self, *, detail: str = "compact") -> dict[str, Any]:
        if self._geo_accum is None:
            self._reset_geo_accum_locked()
        assert self._geo_accum is not None
        full = str(detail).lower() != "compact"
        return self._geo_accum.overlay_payload(
            agent_filter=str(self._geo_agent_filter or "ALL"),
            max_glyphs=128 if full else 48,
            max_events=40 if full else 16,
            include_by_cell_min_attempts=1 if full else 3,
            max_by_cell=220 if full else 0,
            flat_grids=not full,
        )

    def _refresh_geo_overlay_outside_lock(self, *, detail: str = "compact") -> dict[str, Any] | None:
        """Rebuild GEO overlay without holding `_step_lock` (may race observe — LIVE OK)."""
        if not self._geo_live_enabled:
            return {
                "status": "DISABLED",
                "observer_only": True,
                "note": "GEO LIVE processing disabled (perf matrix / isolation).",
            }
        with self._lock:
            if self._geo_accum is None:
                return None
            payload = self._build_geo_overlay_payload(detail=detail)
            self._geo_overlay_published = payload
            return payload

    def _attach_geo_provenance(
        self,
        payload: dict[str, Any] | None,
        transport: dict[str, Any],
        *,
        source: str,
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        with self._lock:
            prov = self._geo_world_provenance_locked()
        source_u = str(source or "LIVE").upper()
        transport = {
            **transport,
            "geo_source": source_u,
            "runtime_generation": prov.get("runtime_generation"),
            "experiment_seed": prov.get("experiment_seed"),
            "terrain_checksum": prov.get("terrain_checksum"),
            "ambient_checksum": prov.get("ambient_checksum"),
            "provenance": prov,
        }
        if payload is None:
            return None, transport
        out = dict(payload)
        out["geo_source"] = source_u
        out["provenance"] = prov if source_u == "LIVE" else (self._geo_saved_provenance or prov)
        if source_u == "LIVE" and int(out.get("n_observations") or 0) <= 0:
            out["status"] = "LIVE_GEO_UNAVAILABLE"
            out["note"] = (
                "LIVE GEO unavailable — no MOVE empirical samples for the current runtime. "
                "Not falling back to older runs."
            )
            # Strip empty/zero grids so clients never paint a blank map as if it were data.
            out["class_grid"] = None
            out["opposing_rate_grid"] = None
            out["worst_alignment_grid"] = None
            out["attempt_grid"] = None
            out["glyphs"] = []
        return out, transport

    def _publish_geo_overlay_outside_lock(
        self,
        *,
        detail: str = "compact",
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        """Rate-limited empirical publish for compact LIVE (OBS-05).

        Scientific accumulate remains every MOVE tick. Visual map grids are
        published at ≤ EMPIRICAL_PUBLISH_HZ; hydrate/reset forces a full send.
        SAVED overlays are published from a separate buffer — never mixed into LIVE.
        """
        from mechanistic_mind.ui.psy_observer_web.geometry.live_accum import EMPIRICAL_PUBLISH_HZ

        with self._lock:
            source = str(getattr(self, "_geo_overlay_source", "LIVE") or "LIVE").upper()
            saved = self._geo_saved_overlay
            saved_prov = self._geo_saved_provenance

        if source == "SAVED":
            if not isinstance(saved, dict):
                empty = {
                    "status": "LIVE_GEO_UNAVAILABLE",
                    "observer_only": True,
                    "geo_source": "SAVED",
                    "note": "SAVED GEO requested but no hydrated overlay is loaded.",
                    "n_observations": 0,
                }
                return self._attach_geo_provenance(
                    empty,
                    {
                        "static_version": int(self._geo_static_version),
                        "empirical_version": 0,
                        "empirical_inline": True,
                        "n_observations": 0,
                    },
                    source="SAVED",
                )
            payload = dict(saved)
            payload["geo_source"] = "SAVED"
            payload["provenance"] = saved_prov
            payload["status"] = payload.get("status") or "AVAILABLE"
            transport = {
                "static_version": int(self._geo_static_version),
                "empirical_version": int(payload.get("empirical_version") or 0),
                "n_observations": payload.get("n_observations"),
                "empirical_inline": True,
                "publish_hz_cap": EMPIRICAL_PUBLISH_HZ,
                "geo_source": "SAVED",
            }
            return self._attach_geo_provenance(payload, transport, source="SAVED")

        full = str(detail).lower() != "compact"
        now = time.monotonic()
        min_period = 1.0 / max(0.5, float(EMPIRICAL_PUBLISH_HZ))
        force = int(self._geo_empirical_version_sent) < 0
        due = (now - float(self._geo_empirical_last_publish_mono or 0.0)) >= min_period

        if (
            not full
            and not force
            and not due
            and isinstance(self._geo_overlay_published, dict)
            and self._geo_overlay_published.get("status") in {"AVAILABLE", "LIVE_GEO_UNAVAILABLE", "CACHED"}
        ):
            published = self._geo_overlay_published
            sent_ver = max(0, int(self._geo_empirical_version_sent))
            n_obs = int(published.get("n_observations") or 0)
            if n_obs <= 0:
                stub = {
                    "status": "LIVE_GEO_UNAVAILABLE",
                    "observer_only": True,
                    "empirical_version": sent_ver,
                    "n_observations": 0,
                    "note": (
                        "LIVE GEO unavailable — no MOVE empirical samples for the current runtime."
                    ),
                }
            else:
                stub = {
                    "status": "CACHED",
                    "observer_only": True,
                    "empirical_version": sent_ver,
                    "n_observations": published.get("n_observations"),
                    "n_buckets": published.get("n_buckets"),
                    "agent_filter": published.get("agent_filter"),
                    "width": published.get("width"),
                    "height": published.get("height"),
                    "glyphs": published.get("glyphs") or [],
                    "events": (published.get("events") or [])[-8:],
                    "class_legend": published.get("class_legend"),
                    "honesty": published.get("honesty"),
                    "note": "Grids omitted — use geo_transport.empirical_version cache.",
                }
            transport = {
                "static_version": int(self._geo_static_version),
                "empirical_version": sent_ver,
                "n_observations": n_obs,
                "empirical_inline": False,
                "publish_hz_cap": EMPIRICAL_PUBLISH_HZ,
            }
            return self._attach_geo_provenance(stub, transport, source="LIVE")

        payload = self._refresh_geo_overlay_outside_lock(detail=detail)
        if payload is None:
            return self._attach_geo_provenance(
                {
                    "status": "LIVE_GEO_UNAVAILABLE",
                    "observer_only": True,
                    "n_observations": 0,
                    "note": "LIVE GEO unavailable.",
                },
                {
                    "static_version": int(self._geo_static_version),
                    "empirical_version": max(0, int(self._geo_empirical_version_sent)),
                    "empirical_inline": False,
                    "n_observations": 0,
                },
                source="LIVE",
            )
        n_obs = int(payload.get("n_observations") or 0)
        self._geo_empirical_version_sent = max(0, int(self._geo_empirical_version_sent)) + 1
        self._geo_empirical_last_publish_mono = now
        payload = dict(payload)
        payload["empirical_version"] = int(self._geo_empirical_version_sent)
        if n_obs <= 0:
            payload["status"] = "LIVE_GEO_UNAVAILABLE"
            payload["note"] = (
                "LIVE GEO unavailable — no MOVE empirical samples for the current runtime. "
                "Not falling back to older runs."
            )
            payload["class_grid"] = None
            payload["opposing_rate_grid"] = None
            payload["worst_alignment_grid"] = None
            payload["attempt_grid"] = None
            payload["glyphs"] = []
        transport = {
            "static_version": int(self._geo_static_version),
            "empirical_version": int(self._geo_empirical_version_sent),
            "n_observations": n_obs,
            "empirical_inline": True,
            "publish_hz_cap": EMPIRICAL_PUBLISH_HZ,
        }
        return self._attach_geo_provenance(payload, transport, source="LIVE")

    def _geo_overlay_locked(self, *, detail: str = "compact") -> dict[str, Any] | None:
        """Compatibility wrapper (API / diagnostics). Prefer outside-lock refresh for LIVE."""
        return self._geo_overlay_for_capture_locked(detail=detail)

    def set_geometry_agent_filter(self, agent_filter: str) -> dict[str, Any]:
        """Observer-only filter for empirical overlay (ALL | agent_0 | agent_1)."""
        allowed = {"ALL", "agent_0", "agent_1", "AGENT_0", "AGENT_1", "all"}
        raw = str(agent_filter or "ALL")
        if raw not in allowed:
            return {"accepted": False, "error": "invalid filter", "allowed": sorted(allowed)}
        if raw.upper() == "ALL" or raw.lower() == "all":
            norm = "ALL"
        elif raw.upper() == "AGENT_0" or raw == "agent_0":
            norm = "agent_0"
        else:
            norm = "agent_1"
        with self._lock:
            self._geo_agent_filter = norm
            self._geo_empirical_version_sent = -1
            self._geo_overlay_published = None
        if self.status != "RUNNING":
            with self._step_lock:
                self._capture_locked(detail="full")
        else:
            self._request_observer_capture(detail=self._frame_detail_for_speed())
        return {"accepted": True, "agent_filter": norm}

    def geometry_hydrate_from_run(self, run_id: str, *, max_rows: int | None = 80_000) -> dict[str, Any]:
        """Load SAVED empirical traversability from a scientific timeline (Observer-only).

        Does NOT replace LIVE accumulators. Display switches to geo_source=SAVED with
        explicit provenance. Apply/reset clears this overlay.
        """
        import json

        from mechanistic_mind.ui.psy_observer_web.geometry.analyze_run import load_timeline_jsonl
        from mechanistic_mind.ui.psy_observer_web.geometry.live_accum import LiveTraversabilityAccumulator
        from mechanistic_mind.ui.psy_observer_web.geometry.traversability import steps_from_timeline_rows
        from mechanistic_mind.ui.psy_observer_web.run_finalize import default_results_root
        from mechanistic_mind.ui.psy_observer_web.scientific_history import published_run_dir

        root = Path(self.config.results_root) if getattr(self.config, "results_root", None) else default_results_root()
        run_dir = published_run_dir(root, run_id)
        timeline = run_dir / "scientific_timeline.jsonl"
        if not timeline.is_file():
            return {"accepted": False, "error": "scientific_timeline.jsonl not found", "run_id": run_id}

        # Provenance from saved run metadata when present (not from current LIVE world).
        saved_meta: dict[str, Any] = {}
        for name in ("run_summary.json", "finalize.json", "identity.json", "manifest.json"):
            p = run_dir / name
            if p.is_file():
                try:
                    saved_meta.update(json.loads(p.read_text(encoding="utf-8")))
                except Exception:
                    pass
        identity = saved_meta.get("identity") if isinstance(saved_meta.get("identity"), dict) else {}
        world_meta = saved_meta.get("world") if isinstance(saved_meta.get("world"), dict) else {}
        terrain_meta = (
            saved_meta.get("terrain_meta")
            or world_meta.get("terrain_meta")
            or identity.get("terrain_meta")
            or {}
        )
        ambient_meta = (
            saved_meta.get("ambient_meta")
            or world_meta.get("ambient_meta")
            or identity.get("ambient_meta")
            or {}
        )

        with self._step_lock:
            live_prov = self._geo_world_provenance_locked()
            w = int(self._geo_accum.width) if self._geo_accum is not None else 32
            h = int(self._geo_accum.height) if self._geo_accum is not None else 32
            if self._geo_accum is not None:
                w = int(self._geo_accum.width)
                h = int(self._geo_accum.height)
            rows = load_timeline_jsonl(timeline, max_rows=max_rows)
            steps = steps_from_timeline_rows(rows, width=w, height=h)
            # Temporary accumulator — does not touch LIVE geo accum.
            tmp = LiveTraversabilityAccumulator(width=w, height=h)
            n = tmp.hydrate_from_steps(steps)
            overlay = tmp.overlay_payload(
                agent_filter=str(self._geo_agent_filter or "ALL"),
                max_glyphs=128,
                max_events=40,
                include_by_cell_min_attempts=1,
                max_by_cell=220,
                flat_grids=False,
            )
            overlay = dict(overlay)
            overlay["geo_source"] = "SAVED"
            overlay["status"] = "AVAILABLE" if n > 0 else "LIVE_GEO_UNAVAILABLE"
            overlay["empirical_version"] = int(n)
            overlay["n_observations"] = int(getattr(tmp, "_n_observations", n) or n)
            provenance = {
                "geo_source": "SAVED",
                "run_id": str(run_id),
                "experiment_seed": (
                    identity.get("seed")
                    or saved_meta.get("seed")
                    or saved_meta.get("experiment_seed")
                ),
                "runtime_generation": identity.get("runtime_generation") or saved_meta.get("runtime_generation"),
                "tick": saved_meta.get("tick") or identity.get("tick"),
                "terrain_seed": terrain_meta.get("terrain_seed"),
                "terrain_checksum": terrain_meta.get("checksum"),
                "ambient_seed": ambient_meta.get("ambient_seed"),
                "ambient_checksum": ambient_meta.get("checksum"),
                "live_runtime_generation": live_prov.get("runtime_generation"),
                "live_terrain_checksum": live_prov.get("terrain_checksum"),
                "live_ambient_checksum": live_prov.get("ambient_checksum"),
                "note": (
                    "SAVED GEO from historical scientific timeline. "
                    "Not current LIVE empirical. Not agent perception."
                ),
            }
            overlay["provenance"] = provenance
            self._geo_saved_overlay = overlay
            self._geo_saved_provenance = provenance
            self._geo_overlay_source = "SAVED"
            # Bump static version so client caches cannot reuse prior LIVE grids under SAVED.
            self._geo_static_version = int(self._geo_static_version or 1) + 1
            self._geo_empirical_version_sent = -1
            self._geo_overlay_published = None
            self._capture_locked(detail="full" if self.status != "RUNNING" else self._frame_detail_for_speed())
        return {
            "accepted": True,
            "run_id": run_id,
            "steps_loaded": n,
            "n_observations": overlay.get("n_observations"),
            "geo_source": "SAVED",
            "geo_static_version": int(self._geo_static_version),
            "provenance": provenance,
            "note": "Observer-only SAVED GEO hydrate — LIVE accumulators untouched.",
        }

    def geometry_use_live(self) -> dict[str, Any]:
        """Switch WORLD empirical display back to current LIVE runtime GEO."""
        with self._step_lock:
            self._geo_overlay_source = "LIVE"
            self._geo_empirical_version_sent = -1
            self._geo_overlay_published = None
            self._geo_static_version = int(self._geo_static_version or 1) + 1
            frame = self._capture_locked(detail="full" if self.status != "RUNNING" else self._frame_detail_for_speed())
        return {
            "accepted": True,
            "geo_source": "LIVE",
            "geo_static_version": int(self._geo_static_version),
            "provenance": (frame.get("geo_transport") or {}).get("provenance"),
        }

    def geometry_clear_saved(self) -> dict[str, Any]:
        """Drop any SAVED GEO overlay and return to LIVE display."""
        with self._step_lock:
            self._geo_saved_overlay = None
            self._geo_saved_provenance = None
            self._geo_overlay_source = "LIVE"
            self._geo_empirical_version_sent = -1
            self._geo_overlay_published = None
            self._geo_static_version = int(self._geo_static_version or 1) + 1
            frame = self._capture_locked(detail="full" if self.status != "RUNNING" else self._frame_detail_for_speed())
        return {
            "accepted": True,
            "geo_source": "LIVE",
            "geo_static_version": int(self._geo_static_version),
            "provenance": (frame.get("geo_transport") or {}).get("provenance"),
            "note": "SAVED GEO cleared; displaying LIVE runtime GEO only.",
        }

    def geometry_cell_detail(self, ix: int, iy: int, agent_filter: str | None = None) -> dict[str, Any]:
        with self._step_lock:
            if self._geo_accum is None:
                self._reset_geo_accum_locked()
            filt = agent_filter or self._geo_agent_filter or "ALL"
            if str(filt).upper() == "ALL":
                filt = "ALL"
            cell = self._geo_accum.cell_directional(int(ix), int(iy), agent_filter=str(filt))
            # Attach ground-truth sample at cell center
            from mechanistic_mind.ui.psy_observer_web.geometry.ground_truth import sample_local_flow

            gt = sample_local_flow(self.runtime, x=float(ix) + 0.5, y=float(iy) + 0.5)
            return {
                "accepted": True,
                "ground_truth": gt,
                "empirical": cell,
                "honesty": {
                    "observer_only": True,
                    "empirical_not_terrain": True,
                    "no_hard_walls": True,
                },
            }

    def _observe_geometry_tick_locked(self) -> None:
        """Update LIVE traversability from consecutive scientific poses (all agents)."""
        if not self._geo_live_enabled:
            return
        if self._geo_accum is None:
            self._reset_geo_accum_locked()
        rt = self.runtime
        slots = getattr(rt, "slots", None)
        contact = getattr(rt, "last_contact", None)
        contact_on = bool(contact.get("active") or contact.get("contact")) if isinstance(contact, dict) else False

        def pose_of(body: Any) -> dict[str, Any]:
            return {"x": float(body.x), "y": float(body.y)}

        if slots:
            for i, slot in enumerate(slots):
                aid = f"agent_{i}"
                cur = pose_of(slot.body)
                prev = self._geo_prev_bodies.get(aid)
                action = getattr(slot, "last_selected_action", None)
                if prev is not None:
                    self._geo_accum.observe(
                        agent_id=aid,
                        tick=int(rt.tick),
                        action=action,
                        x0=float(prev["x"]),
                        y0=float(prev["y"]),
                        x1=float(cur["x"]),
                        y1=float(cur["y"]),
                        contact=contact_on,
                    )
                self._geo_prev_bodies[aid] = cur
        else:
            aid = "agent_0"
            cur = pose_of(rt.body)
            prev = self._geo_prev_bodies.get(aid)
            action = getattr(rt, "last_selected_action", None)
            if prev is not None:
                self._geo_accum.observe(
                    agent_id=aid,
                    tick=int(rt.tick),
                    action=action,
                    x0=float(prev["x"]),
                    y0=float(prev["y"]),
                    x1=float(cur["x"]),
                    y1=float(cur["y"]),
                    contact=contact_on,
                )
            self._geo_prev_bodies[aid] = cur

    def _halt_runner(self, status: str) -> None:
        with self._lock:
            self.status = status
            self._stop_flag = True
        self._join_runner()

    def _join_runner(self, timeout: float = 2.0) -> None:
        t = self._thread
        if t is not None and t.is_alive() and t is not threading.current_thread():
            t.join(timeout=timeout)
        if self._thread is not None and not self._thread.is_alive():
            self._thread = None

    def _ensure_loop_locked(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_flag = False
        self._thread = threading.Thread(target=self._loop, name="psy-observer-sim", daemon=True)
        self._thread.start()

    def _resolve_complete_experiment(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Merge Apply payload into the session canonical config (PATCH preserve)."""
        from mechanistic_mind.physical_system.experiment_canonical import (
            PRESET_BETA3,
            canonical_from_runtime,
            merge_canonical,
            normalize_preset_name,
            preset_canonical,
        )

        load = bool(payload.get("load_preset") or payload.get("replace_with_preset"))
        preset = normalize_preset_name(payload.get("public_preset") or payload.get("preset"))
        has_mechs = isinstance(payload.get("mechanisms"), dict) and bool(payload.get("mechanisms"))
        # Named preset without a mechanism map is an explicit preset load (Beta 3 tests / Load Preset).
        # Named preset WITH a mechanism map is a label only — merge, do not wipe.
        if load or (preset is not None and not has_mechs):
            base = preset_canonical(preset, seed=int(payload.get("seed") or self.config.seed))
        elif self._canonical_config is not None:
            base = dict(self._canonical_config)
        else:
            try:
                base = canonical_from_runtime(self.runtime)
            except Exception:
                base = preset_canonical(PRESET_BETA3 if preset == PRESET_BETA3 else None, seed=int(self.config.seed))
            base["pe_cold_history_eviction"] = bool(self.config.pe_cold_history_eviction)
        if "pe_cold_history_eviction" not in payload and base.get("pe_cold_history_eviction") is None:
            base["pe_cold_history_eviction"] = bool(self.config.pe_cold_history_eviction)
        complete = merge_canonical(base, payload)
        complete["seed"] = int(complete.get("seed") or self.config.seed)
        return complete

    def applied_configuration_receipt(self) -> dict[str, Any]:
        from mechanistic_mind.physical_system.experiment_canonical import (
            canonical_fingerprint,
            compare_requested_runtime,
            runtime_readback,
        )

        requested = dict(self._canonical_requested or self._canonical_config or {})
        runtime = runtime_readback(self.runtime, pe_cold=bool(self.config.pe_cold_history_eviction))
        cmp = compare_requested_runtime(requested, runtime)
        return {
            "schema": "mm.observer.applied_configuration.v1",
            "configured": {
                "fingerprint": canonical_fingerprint(self._canonical_config or requested),
                "public_preset": (self._canonical_config or {}).get("public_preset"),
            },
            "requested": {
                "fingerprint": cmp["requested_fingerprint"],
                "public_preset": requested.get("public_preset"),
                "vision": requested.get("vision"),
                "mechanisms": requested.get("mechanisms"),
            },
            "runtime": {
                "fingerprint": cmp["runtime_fingerprint"],
                "vision": runtime.get("vision"),
                "mechanisms": runtime.get("mechanisms"),
                "psc_motor_resolution": runtime.get("psc_motor_resolution"),
                "source": "runtime.mechanisms + config.near_field_exteroception",
            },
            "match": cmp["match"],
            "mismatches": cmp["mismatches"],
        }

    def _sync_canonical_mechanism(self, mechanism_id: str, enabled: bool) -> None:
        if self._canonical_config is None:
            return
        self._canonical_config.setdefault("mechanisms", {})[str(mechanism_id)] = bool(enabled)

    def _sync_canonical_vision(self, **fields: Any) -> None:
        if self._canonical_config is None:
            return
        vis = dict(self._canonical_config.get("vision") or {})
        vis.update({k: v for k, v in fields.items() if v is not None})
        self._canonical_config["vision"] = vis

    def _stamp_runtime_vision_locked(self, vision: dict[str, Any] | None) -> None:
        if not vision or getattr(self, "runtime", None) is None:
            return
        rt = self.runtime
        if vision.get("radius") is not None and hasattr(rt, "set_vision_radius"):
            rt.set_vision_radius(int(vision["radius"]))
        if vision.get("spatial_vision") and hasattr(rt, "set_spatial_vision"):
            rt.set_spatial_vision(str(vision["spatial_vision"]))
        if vision.get("visual_surface_discrimination") and hasattr(rt, "set_visual_surface_discrimination"):
            rt.set_visual_surface_discrimination(str(vision["visual_surface_discrimination"]))
        if vision.get("optical_mapping") and hasattr(rt, "set_optical_mapping"):
            rt.set_optical_mapping(str(vision["optical_mapping"]), reinstall=True)

    def apply_experiment(self, payload: dict[str, Any]) -> dict[str, Any]:
        """APPLY & RESET WORLD — rebuild runtime from one complete canonical snapshot."""
        self._halt_runner("PAUSED")
        self._invalidate_pending_captures_locked()
        with self._step_lock:
            with self._lock:
                before = self._control_state()
                from mechanistic_mind.physical_system.experiment_canonical import (
                    PRESET_BETA3,
                    normalize_preset_name,
                    stamp_vision_on_config,
                )
                complete = self._resolve_complete_experiment(payload)
                self._canonical_requested = deepcopy(complete)
                seed = int(complete.get("seed") or self.config.seed)
                cognition = dict(complete.get("mechanisms") or {})
                cog_kwargs: dict[str, Any] = {}
                allowed = set(CognitionConfig.__dataclass_fields__)
                for k, v in cognition.items():
                    if k in allowed:
                        cog_kwargs[k] = v
                if complete.get("cognition_enabled") is not None:
                    cog_kwargs["cognition_enabled"] = bool(complete["cognition_enabled"])
                if complete.get("psc_motor_resolution"):
                    cog_kwargs["psc_motor_resolution"] = str(complete["psc_motor_resolution"])
                self.config.seed = seed
                self.config.target_tick = complete.get("target_tick", payload.get("target_tick", self.config.target_tick))
                if "buffer_capacity" in complete:
                    self.config.buffer_capacity = int(complete["buffer_capacity"])
                elif "buffer_capacity" in payload:
                    self.config.buffer_capacity = int(payload["buffer_capacity"])
                if "ui_hz" in complete:
                    self.config.ui_hz = float(complete["ui_hz"])
                elif "ui_hz" in payload:
                    self.config.ui_hz = float(payload["ui_hz"])
                if "speed" in complete:
                    self.config.speed = float(complete["speed"])
                elif "speed" in payload:
                    self.config.speed = float(payload["speed"])
                if "checkpoint_every_ticks" in complete or "checkpoint_every_ticks" in payload:
                    try:
                        self.config.checkpoint_every_ticks = max(
                            0,
                            int((complete.get("checkpoint_every_ticks")
                                 if complete.get("checkpoint_every_ticks") is not None
                                 else payload.get("checkpoint_every_ticks")) or 0),
                        )
                    except (TypeError, ValueError):
                        pass
                if complete.get("pe_cold_history_eviction") is not None:
                    self.config.pe_cold_history_eviction = bool(complete["pe_cold_history_eviction"])
                cog = CognitionConfig(
                    **{k: cog_kwargs[k] for k in CognitionConfig.__dataclass_fields__ if k in cog_kwargs}
                )
                planet = default_planet_config()
                world = complete.get("world") or payload.get("world") or {}
                mode = world.get("boundary_mode") or world.get("boundary_topology") or "WRAP_PERIODIC"
                mode = str(mode).upper().replace("/", "_").replace(" ", "_")
                if mode in {"WRAP", "PERIODIC", "WRAP_PERIODIC", "TOROIDAL"}:
                    mode = "WRAP_PERIODIC"
                elif mode in {"CLOSED", "OPEN"}:
                    raise ValueError(
                        f"boundary_mode={mode} is UNSUPPORTED in Current MM Planet physics "
                        "(spatial topology is WRAP_PERIODIC only)"
                    )
                else:
                    raise ValueError(f"unknown boundary_mode={mode}")
                pdict = planet.to_dict()
                for k, v in world.items():
                    if k in {"boundary_mode", "boundary_topology", "boundary"}:
                        continue
                    if k in pdict:
                        if k in {"width", "height"}:
                            setattr(planet, k, max(4, min(256, int(v))))
                        else:
                            try:
                                setattr(planet, k, type(pdict[k])(v) if pdict[k] is not None else v)
                            except Exception:
                                pass
                body = default_physical_body2_config()
                b_in = complete.get("agent_body") or complete.get("body") or payload.get("agent_body") or payload.get("body") or {}
                bdict = body.to_dict()
                for k, v in b_in.items():
                    if k in bdict and k not in {"footprint", "permeability"}:
                        try:
                            setattr(body, k, type(bdict[k])(v))
                        except Exception:
                            pass
                internal = default_internal_medium_config()
                cfg = PhysicalSystemConfig(planet=planet, body=body, internal=internal, cognition=cog)
                from mechanistic_mind.physical_system.ecology_presets import (
                    DEFAULT_ECOLOGY_PRESET,
                    make_ecology_config,
                    normalize_ecology_preset,
                )
                eco = complete.get("ecology_preset") or (complete.get("world") or {}).get("ecology_preset")
                eco_name = normalize_ecology_preset(eco if eco is not None else DEFAULT_ECOLOGY_PRESET)
                cfg = make_ecology_config(eco_name, base=cfg)
                cfg.cognition = cog
                world_in = complete.get("world") or {}
                t_override = complete.get("terrain_seed", world_in.get("terrain_seed"))
                if t_override is not None and getattr(cfg.planet, "terrain", None) is not None:
                    try:
                        cfg.planet.terrain.terrain_seed = int(t_override)
                    except (TypeError, ValueError):
                        pass
                preset_id = normalize_preset_name(complete.get("public_preset"))
                agent_count = int(complete.get("agent_count") or 1)
                if preset_id == PRESET_BETA3 and complete.get("agent_count") is None:
                    agent_count = 2
                from mechanistic_mind.physical_system.mechanism_configuration import (
                    resolve_mechanism_config,
                    stamp_config_mechanisms,
                )
                vis = dict(complete.get("vision") or {})
                mech_payload = dict(cognition)
                mech_payload["cognition_enabled"] = bool(complete.get("cognition_enabled", True))
                if vis.get("radius") is not None:
                    mech_payload["vision_radius"] = vis["radius"]
                resolved = resolve_mechanism_config(
                    mech_payload,
                    vision_radius=vis.get("radius"),
                    source_hint="CANONICAL",
                    apply_fresh_defaults=True,
                )
                stamp_config_mechanisms(cfg, resolved)
                stamp_vision_on_config(cfg, vis)
                non_cog = {
                    k: v for k, v in mech_payload.items()
                    if k not in allowed and k not in {"cognition_enabled", "vision_radius"}
                }
                if agent_count >= 2:
                    signal_on = bool(
                        resolved.mechanisms.get(
                            "experimental_physical_signal",
                            non_cog.get("experimental_physical_signal", False),
                        )
                    )
                    self.runtime = TwoAgentRuntime(
                        seed=seed, config=cfg, signal_enabled=signal_on,
                    )
                else:
                    self.runtime = PhysicalSystemRuntime(seed=seed, config=cfg)
                # Static-patch ecology: seed separated A+B patches after world init.
                if getattr(cfg, "_baseline_seed_patches", False):
                    from mechanistic_mind.physical_system.baseline_ecology_presets import (
                        seed_static_patches,
                    )
                    seed_static_patches(
                        self.runtime.world,
                        seed=seed,
                        spec=getattr(cfg, "_baseline_patch_spec", None),
                    )
                self._runtime_generation += 1
                self._clear_integrity_locked()
                from mechanistic_mind.physical_system.mechanism_configuration import (
                    apply_resolved_to_runtime,
                    build_runtime_manifest,
                    run_preflight,
                )
                apply_resolved_to_runtime(self.runtime, resolved)
                psc_mode = str(complete.get("psc_motor_resolution") or "")
                if psc_mode:
                    setter = getattr(self.runtime, "set_psc_motor_resolution", None)
                    if callable(setter):
                        setter(psc_mode)
                self._stamp_runtime_vision_locked(vis)
                preflight = run_preflight(self.runtime, resolved)
                if preflight.status != "READY":
                    apply_resolved_to_runtime(self.runtime, resolved)
                    self._stamp_runtime_vision_locked(vis)
                    preflight = run_preflight(self.runtime, resolved)
                self._canonical_config = deepcopy(complete)
                self._resolved_mechanism_config = resolved
                self._preflight_result = preflight.to_dict()
                if preflight.status == "READY":
                    self._runtime_mechanism_manifest = build_runtime_manifest(
                        runtime=self.runtime,
                        resolved=resolved,
                        preflight=preflight,
                        run_id=self._active_run_id,
                        generation=self._runtime_generation,
                    )
                else:
                    self._runtime_mechanism_manifest = None
                self._applied_receipt = self.applied_configuration_receipt()
                integrity = {
                    "resolved": resolved.to_dict(),
                    "preflight": self._preflight_result,
                    "manifest": self._runtime_mechanism_manifest,
                    "applied_configuration": self._applied_receipt,
                }
                self.config.cognition_enabled = cog.cognition_enabled
                self.status = "PAUSED"
                self.mode = "LIVE"
                self.inspect_tick = None
                self._buffer = deque(maxlen=FULL_PUBLIC_FRAME_RETAIN)
                self._timeline = deque(maxlen=max(1024, int(self.config.buffer_capacity) * 8))
                self._prev_body = None
                self._prev_bodies = {}
                self._geo_prev_bodies = {}
                self._reset_geo_accum_locked()
                self._reset_sig_accum_locked()
                self._experimenter_intervention_ever = False
                self._reset_experimenter_locked()
                self._reset_action_realization_locked()
                self._reset_work_ecology_locked()
                self._reset_locomotor_economy_locked()
                self._trajectory = deque(maxlen=max(LIVE_TRAJECTORY_RING_MIN, int(self.config.buffer_capacity) * LIVE_TRAJECTORY_RING_MULT))
                self._telemetry = deque(maxlen=max(LIVE_TELEMETRY_RING_MIN, int(self.config.buffer_capacity) * LIVE_TRAJECTORY_RING_MULT))
                self._historical_compat = None
                self._published = None
                self._published_json = None
                self._published_ws_text = None
                self._run_started_at = None
                self._active_run_id = None
                self._close_scientific_locked()
                self._sci_live_dir = None
                self._finalize_key = None
                self._termination_reason = None
                self._last_finalize = None
                self._event_ring = deque(maxlen=EVENT_RING_MAX)
                self._event_keys = set()
                self._clear_world_interventions_locked()
                self._visual_dropped = 0
                self._capture_queue_drops = 0
                self._perf_window_start = time.monotonic()
                self._perf_ticks = 0
                self._perf_captures = 0
                self._record_motion_locked()
                # Seed fingerprint baseline for the new runtime generation.
                try:
                    from mechanistic_mind.ui.psy_observer_web.live_intervention import fingerprint_for_runtime
                    self._world_intervention_fp0 = fingerprint_for_runtime(self.runtime)
                except Exception:
                    self._world_intervention_fp0 = None
                self._apply_pe_cold_eviction_locked()
                frame = self._capture_locked(detail="full")
        self._maybe_push(frame, force=True)
        out = self._with_receipt(
            frame, "APPLY_AND_RESET_WORLD", deepcopy(payload), before,
            requires_reset=True,
        )
        out["preflight"] = integrity.get("preflight")
        out["mechanism_result"] = self.runtime.mechanisms()
        out["mechanism_integrity"] = self.mechanism_integrity_status()
        out["applied_configuration"] = self._applied_receipt
        return out


# process singleton
_SESSION: ObserverSession | None = None


def get_session() -> ObserverSession:
    global _SESSION
    if _SESSION is None:
        _SESSION = ObserverSession()
    return _SESSION
