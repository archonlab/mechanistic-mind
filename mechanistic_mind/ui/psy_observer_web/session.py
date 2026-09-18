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
from .serialize import compact_timeline_event, live_frame, collect_observer_events


# Wall-clock period for one scientific tick at 1× (human-observable cadence).
# Higher multipliers shorten this period; MAX uses no intentional sleep.
# This is simulation acceleration only — dt / physics / cognition unchanged.
BASE_TICK_PERIOD_1X = 0.025  # 40 scientific ticks/sec target at 1× when CPU allows
MAX_SPEED = 50.0
EVENT_RING_MAX = 2500
TRAJECTORY_EMBED_TAIL = 96
TELEMETRY_EMBED_TAIL = 64


def tick_sleep_seconds(speed: float) -> float:
    """Intentional wall-clock wait after each scientific tick (0 for MAX)."""
    sp = float(speed)
    if sp >= MAX_SPEED - 0.5:
        return 0.0
    return max(0.0, BASE_TICK_PERIOD_1X / max(0.05, sp))


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
    ui_hz: float = 10.0  # max live push rate
    steps_per_loop: int = 1
    speed: float = 1.0  # relative sim steps aggressiveness
    cognition_enabled: bool = True
    results_root: Path | None = None


@dataclass
class ObserverSession:
    config: SessionConfig = field(default_factory=SessionConfig)
    runtime: PhysicalSystemRuntime = field(init=False)
    status: str = "PAUSED"  # PAUSED | RUNNING | STOPPED | FINALIZING | SAVE_FAILED
    mode: str = "LIVE"  # LIVE | REPLAY | INSPECT
    inspect_tick: int | None = None
    _buffer: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=512))
    _timeline: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=4096))
    _lock: threading.RLock = field(default_factory=threading.RLock)
    _step_lock: threading.Lock = field(default_factory=threading.Lock)
    _published: dict[str, Any] | None = None
    _prev_body: dict[str, Any] | None = None
    _prev_bodies: dict[str, dict[str, Any]] = field(default_factory=dict)
    _subscribers: list[Callable[[dict[str, Any]], None]] = field(default_factory=list)
    _last_push: float = 0.0
    _thread: threading.Thread | None = None
    _stop_flag: bool = False
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
    _event_ring: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=EVENT_RING_MAX))
    _event_keys: set[tuple[Any, ...]] = field(default_factory=set)
    _visual_dropped: int = 0
    _perf_window_start: float = 0.0
    _perf_ticks: int = 0
    _perf_captures: int = 0
    _perf_sim_tps: float = 0.0
    _perf_obs_fps: float = 0.0
    _last_frame_tick: int | None = None
    _sci_writer: ScientificHistoryWriter | None = None
    _sci_live_dir: Path | None = None
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

    def __post_init__(self) -> None:
        self._perf_window_start = time.monotonic()
        self.reset(seed=self.config.seed)
        self._ensure_capture_worker()

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
                self.status = "PAUSED"
                self.mode = "LIVE"
                self.inspect_tick = None
                self._buffer = deque(maxlen=int(self.config.buffer_capacity))
                self._timeline = deque(maxlen=max(1024, int(self.config.buffer_capacity) * 8))
                self._prev_body = None
                self._prev_bodies = {}
                self._trajectory = deque(maxlen=max(256, int(self.config.buffer_capacity) * 4))
                self._telemetry = deque(maxlen=max(256, int(self.config.buffer_capacity) * 4))
                self._historical_compat = None
                self._published = None
                self._run_started_at = None
                self._termination_reason = "RESET"
                self._last_finalize = prior_finalize
                self._finalize_key = None
                self._active_run_id = None
                self._close_scientific_locked()
                self._event_ring = deque(maxlen=EVENT_RING_MAX)
                self._event_keys = set()
                self._visual_dropped = 0
                self._perf_window_start = time.monotonic()
                self._perf_ticks = 0
                self._perf_captures = 0
                self._perf_sim_tps = 0.0
                self._perf_obs_fps = 0.0
                self._last_frame_tick = None
                self._published_json = None
                self._observer_lag_ticks = 0
                self._invalidate_pending_captures_locked()
                self._record_motion_locked()
                frame = self._capture_locked(detail="full")
                out = self._with_receipt(
                    frame, "RESET", {"seed": seed, "cognition_enabled": cognition_enabled},
                    before, requires_reset=True,
                )
                if prior_finalize is not None:
                    out["finalize"] = prior_finalize
                return out

    def _invalidate_pending_captures_locked(self) -> None:
        """Drop any async capture belonging to a prior run/generation."""
        with self._capture_cond:
            self._capture_pending = None

    def subscribe(self, fn: Callable[[dict[str, Any]], None]) -> None:
        with self._lock:
            self._subscribers.append(fn)

    def unsubscribe(self, fn: Callable[[dict[str, Any]], None]) -> None:
        with self._lock:
            if fn in self._subscribers:
                self._subscribers.remove(fn)

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

    def _accumulate_events_locked(self) -> None:
        """Drain structured events every scientific tick into a bounded observer ring."""
        fresh = collect_observer_events(self.runtime, limit=120)
        for ev in fresh:
            key = self._event_key(ev)
            if key in self._event_keys:
                continue
            self._event_keys.add(key)
            self._event_ring.append(ev)
        if len(self._event_keys) > EVENT_RING_MAX * 2:
            self._event_keys = {self._event_key(e) for e in self._event_ring}

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
                    t_ser0 = time.perf_counter()
                    self._serialize_published(frame)
                    timing["serialization_ms"] = (time.perf_counter() - t_ser0) * 1000.0
                    t_pub0 = time.perf_counter()
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
        events_payload = list(self._event_ring)[-80:]
        # Avoid multi-hundred-ms GC pauses mid-frame (can trip STALE even with coop yield).
        _gc_was = gc.isenabled()
        if _gc_was:
            gc.disable()
        try:
            frame = live_frame(
                self.runtime,
                status=self.status,
                mode=self.mode if self.mode != "INSPECT" else "INSPECT",
                target_tick=self.config.target_tick,
                previous_body=self._prev_body,
                previous_bodies=dict(self._prev_bodies),
                detail=detail_s,
                structured_events=events_payload,
            )
        finally:
            if _gc_was:
                gc.enable()
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
            ticks["agent_0"] = int(slots[0].tick)
            ticks["agent_1"] = int(slots[1].tick)
        live_tick = int(self.runtime.tick)
        self._last_frame_tick = live_tick
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
        }
        frame.setdefault("header", {}).update({
            "observation_frame_id": frame_id,
            "runtime_generation": self._runtime_generation,
            "captured_at": captured_at,
            "live_runtime_tick": live_tick,
            "frame_tick": live_tick,
            "simulation_speed": float(self.config.speed),
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
        traj_points = list(self._trajectory)
        telem_series = list(self._telemetry)
        if detail_s == "compact":
            traj_points = traj_points[-TRAJECTORY_EMBED_TAIL:]
            telem_series = telem_series[-TELEMETRY_EMBED_TAIL:]
        frame["trajectory"] = {
            "points": traj_points,
            "capacity": self._trajectory.maxlen,
            "boundary": "WRAP_PERIODIC",
            "truncated": len(self._trajectory) > len(traj_points),
        }
        frame["telemetry"] = {
            "series": telem_series,
            "capacity": self._telemetry.maxlen,
            "truncated": len(self._telemetry) > len(telem_series),
        }
        if self._historical_compat:
            frame["historical_compatibility"] = deepcopy(self._historical_compat)
        experiment = frame.setdefault("experiment", {})
        experiment["observer"] = {
            "ui_hz": float(self.config.ui_hz),
            "buffer_capacity": int(self.config.buffer_capacity),
            "speed": float(self.config.speed),
            "target_tick": self.config.target_tick,
            "base_tick_period_1x": BASE_TICK_PERIOD_1X,
            "capture_period_s": observer_capture_period(self.config.speed, self.config.ui_hz),
            "async_capture": True,
            "capture_queue_drops": int(self._capture_queue_drops),
        }
        sim_tick_now = int(self.runtime.tick)
        lag = max(0, sim_tick_now - live_tick)
        self._observer_lag_ticks = lag
        frame.setdefault("header", {}).update({
            "observer_lag_ticks": lag,
            "sim_tick": sim_tick_now,
            "frame_tick": live_tick,
        })
        self._buffer.append(frame)
        self._timeline.append(compact_timeline_event(frame))
        self._published = frame
        if serialize:
            self._serialize_published(frame)
        self._update_perf_locked(capture=True)
        return frame

    def _serialize_published(self, frame: dict[str, Any]) -> None:
        """JSON-cache the published frame (safe outside `_step_lock`)."""
        t_ser0 = time.perf_counter()
        try:
            self._published_json = json.dumps(frame, default=str, separators=(",", ":"))
        except TypeError:
            self._published_json = None
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
    ) -> dict[str, Any]:
        out = deepcopy(frame)
        out["control_receipt"] = {
            "receipt_id": f"ctl-{self._runtime_generation}-{self._frame_seq}-{operation.lower()}",
            "operation": operation,
            "request": request,
            "accepted": bool(accepted),
            "previous_state": previous,
            "new_state": self._control_state(),
            "tick": int(self.runtime.tick),
            "runtime_generation": self._runtime_generation,
            "requires_reset": bool(requires_reset),
            "reason": reason,
        }
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
        if self._run_started_at is None:
            self._run_started_at = datetime.now(timezone.utc).isoformat()
            self._active_run_id = new_run_id()
            self._termination_reason = None
        self.mode = "LIVE"
        self.inspect_tick = None
        self.status = "RUNNING"
        self._stop_flag = False
        self._ensure_capture_worker()
        with self._lock:
            self._ensure_scientific_locked()
            self._ensure_loop_locked()
        out = self._with_receipt(self._clone_published(status="RUNNING"), "PLAY", {}, before)
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

    def _ensure_scientific_locked(self) -> None:
        """Open append-only scientific writer for the active run_id (idempotent)."""
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
        })
        self._sci_writer = writer
        self._sci_live_dir = live

    def _close_scientific_locked(self, *, clear_live_dir: bool = True) -> None:
        w = self._sci_writer
        self._sci_writer = None
        if w is not None:
            try:
                w.close()
            except Exception:
                pass
        if clear_live_dir:
            self._sci_live_dir = None

    def _append_scientific_locked(self) -> None:
        """Persist one scientific record set per new simulation tick (not per UI capture)."""
        if self._active_run_id is None:
            return
        self._ensure_scientific_locked()
        w = self._sci_writer
        if w is None:
            return
        w.append_tick(self.runtime)
        # Drain freshly accumulated structured events into the scientific archive
        fresh = list(self._event_ring)[-40:]
        if fresh:
            w.append_events(fresh)

    def scientific_evidence(
        self,
        *,
        cutoff_tick: int | None = None,
    ) -> dict[str, Any]:
        """Read-only evidence package for Analyzer (tolerates appends beyond cutoff)."""
        with self._lock:
            if self._sci_writer is not None:
                self._sci_writer.flush()
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
            }
            # Deterministic cutoff: caller value or current live tick snapshot
            live_tick = int(self.runtime.tick)
            cut = int(cutoff_tick) if cutoff_tick is not None else live_tick
            runtime = self.runtime
        return load_evidence_package(
            evidence_dir=live_dir,
            runtime=runtime,
            ui_timeline=timeline,
            ui_events=events,
            cutoff_tick=cut,
            runtime_status=status,
            run_id=rid,
            identity=identity,
        )

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

    def stop(self, *, save: bool = False, reason: str | None = None) -> dict[str, Any]:
        """Stop simulation. save=True → finalize then STOPPED; save=False → STOPPED without artifact."""
        before = self._control_state()
        if self.status == "FINALIZING":
            # Wait for in-flight finalize (idempotent)
            with self._finalize_lock:
                fin = deepcopy(self._last_finalize) if self._last_finalize else {
                    "accepted": False, "reason": "finalization in progress",
                }
            out = self._with_receipt(
                self._clone_published(status=self.status), "STOP",
                {"save": save, "reason": reason}, before,
                accepted=bool(fin.get("accepted")),
                reason="idempotent finalize while FINALIZING",
            )
            if fin.get("final_tick") is not None:
                out["control_receipt"]["tick"] = int(fin["final_tick"])
                out["control_receipt"]["verified_final_tick"] = int(fin["final_tick"])
            out["finalize"] = fin
            return out

        request = {"save": bool(save), "reason": reason}
        if save:
            term = reason or "USER_STOP_SAVED"
            self._stop_flag = True
            self.status = "FINALIZING"
            self._join_runner()
            # Freeze current generation, then capture one atomic frame for visibility
            with self._step_lock:
                with self._lock:
                    boundary_tick = int(self.runtime.tick)
                    boundary_generation = int(self._runtime_generation)
                    boundary_runtime_type = type(self.runtime).__name__
                    self._capture_locked()
                    # Capture must not advance scientific state; tick must hold.
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
                        out = self._with_receipt(
                            self._clone_published(status="SAVE_FAILED"), "STOP", request, before,
                            accepted=False, reason=fin["error"],
                        )
                        out["finalize"] = fin
                        self._last_finalize = fin
                        self._maybe_push(out, force=True)
                        return out
            fin = self.finalize_run(reason=term)
            if not fin.get("accepted"):
                self.status = "SAVE_FAILED"
                out = self._with_receipt(
                    self._clone_published(status="SAVE_FAILED"), "STOP", request, before,
                    accepted=False,
                    reason=fin.get("error") or "save failed; runtime preserved",
                )
                out["finalize"] = fin
                self._maybe_push(out, force=True)
                return out
            verified_tick = int(fin["final_tick"])
            fin_gen = fin.get("runtime_generation")
            if fin_gen is None:
                fin_gen = boundary_generation
            if verified_tick != boundary_tick or int(fin_gen) != boundary_generation:
                # Should be unreachable after finalize guards; refuse success if it happens.
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
                out = self._with_receipt(
                    self._clone_published(status="SAVE_FAILED"), "STOP", request, before,
                    accepted=False, reason=fin["error"],
                )
                out["finalize"] = fin
                self._maybe_push(out, force=True)
                return out
            self.status = "STOPPED"
            out = self._with_receipt(
                self._clone_published(status="STOPPED"), "STOP", request, before,
                reason=(
                    f"SAVED · t{verified_tick} · verified snapshot tick: {verified_tick} · "
                    f"saved to {fin.get('run_dir')}"
                ),
            )
            # Success tick is the verified persisted boundary — never a pre-save UI guess.
            out["control_receipt"]["tick"] = verified_tick
            out["control_receipt"]["verified_final_tick"] = verified_tick
            out["finalize"] = fin
            self._maybe_push(out, force=True)
            return out

        # Stop without saving
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
        self._maybe_push(out, force=True)
        return out

    def step(self, n: int = 1) -> dict[str, Any]:
        before = self._control_state()
        if self.status == "FINALIZING":
            return self._with_receipt(
                self._clone_published(), "STEP", {"n": int(n)}, before,
                accepted=False, reason="finalization in progress",
            )
        if self._run_started_at is None:
            self._run_started_at = datetime.now(timezone.utc).isoformat()
            self._active_run_id = new_run_id()
        self.mode = "LIVE"
        self.inspect_tick = None
        self.status = "PAUSED"
        with self._step_lock:
            with self._lock:
                self._ensure_scientific_locked()
            for _ in range(max(1, int(n))):
                if self.config.target_tick is not None and self.runtime.tick >= int(self.config.target_tick):
                    break
                self.runtime.step(1)
                with self._lock:
                    self._accumulate_events_locked()
                    self._record_motion_locked()
                    self._append_scientific_locked()
                    self._update_perf_locked(tick=True)
            with self._lock:
                frame = self._capture_locked(detail="full")
        self._maybe_push(frame, force=True)
        return self._with_receipt(frame, "STEP", {"n": int(n)}, before)

    def set_speed(self, speed: float) -> dict[str, Any]:
        before = self._control_state()
        # Speed change must not reset the run or skip ticks.
        self.config.speed = float(max(0.05, min(MAX_SPEED, speed)))
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

    def set_mechanism(self, mechanism_id: str, enabled: bool) -> dict[str, Any]:
        before = self._control_state()
        request = {"mechanism_id": mechanism_id, "enabled": enabled}
        with self._step_lock:
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
            snap = self.runtime.set_mechanism(mechanism_id, bool(enabled))
            with self._lock:
                frame = self._capture_locked()
        out = self._with_receipt(
            frame, "TOGGLE_MECHANISM",
            {"mechanism_id": mechanism_id, "enabled": bool(enabled)},
            before,
            requires_reset=item.get("toggle_policy") == "RESET_REQUIRED",
            reason=(
                "state history is retained; reset recommended for matched comparisons"
                if item.get("toggle_policy") == "RESET_RECOMMENDED" else None
            ),
        )
        out["mechanism_result"] = snap
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

    SNAPSHOT_SCHEMA = "mm.physical_system.snapshot.v2"
    SNAPSHOT_SCHEMA_TWO = "mm.physical_system.two_agent.snapshot.v1"

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
                self._trajectory.clear()
                self._telemetry.clear()
                self._buffer.clear()
                self._timeline.clear()
                self._published = None
                self._run_started_at = None
                self._active_run_id = None
                self._finalize_key = None
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
        return self._with_receipt(
            frame, "RESTORE_SNAPSHOT", {"schema": payload.get("schema")},
            before, requires_reset=True,
        )

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
        hdr["observer_lag_ticks"] = max(0, sim_tick - frame_tick)
        if self.status == "RUNNING":
            hdr["sim_ticks_per_sec"] = round(float(self._perf_sim_tps), 1)
            hdr["observer_fps"] = round(float(self._perf_obs_fps), 1)
        else:
            hdr["sim_ticks_per_sec"] = 0.0
        return {**frame, "header": hdr}

    def published_json(self) -> str | None:
        """Cached JSON of the last published frame body (no live-tick overlay)."""
        return self._published_json

    def _clone_published(self, status: str | None = None) -> dict[str, Any]:
        """Deep copy for control receipts that mutate the returned dict."""
        frame = self._published
        if frame is None:
            with self._step_lock:
                with self._lock:
                    if self._published is None:
                        self._capture_locked(detail="full")
                    frame = self._published
        out = deepcopy(frame)
        if status:
            out.setdefault("header", {})["status"] = status
        return out

    def _loop(self) -> None:
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
            # Cooperative yield so capture worker is not starved of step_lock.
            self._yield_step_lock_to_capture()
            t_lock0 = time.perf_counter()
            with self._step_lock:
                if self._capture_timing_enabled:
                    self._sim_lock_waits_ms.append((time.perf_counter() - t_lock0) * 1000.0)
                if self._stop_flag or self.status != "RUNNING":
                    continue
                if target is not None and self.runtime.tick >= int(target):
                    self.status = "PAUSED"
                    continue
                self.runtime.step(1)
                with self._lock:
                    self._accumulate_events_locked()
                    self._record_motion_locked()
                    self._append_scientific_locked()
                    self._update_perf_locked(tick=True)
                now = time.monotonic()
                capture_period = observer_capture_period(speed, ui_hz)
                if now - last_capture >= capture_period:
                    request_capture = True
                    last_capture = now
            # Observer capture is asynchronous — SIM must not wait for live_frame.
            if request_capture:
                self._request_observer_capture(detail=self._frame_detail_for_speed())
            sleep_s = tick_sleep_seconds(speed)
            spent = time.perf_counter() - tick_t0
            remain = sleep_s - spent
            if remain > 0:
                time.sleep(remain)

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
            ticks = [int((f.get("header") or {}).get("tick", -1)) for f in self._buffer]
            return {
                "ticks": ticks,
                "oldest_tick": ticks[0] if ticks else None,
                "newest_tick": ticks[-1] if ticks else None,
                "live_tick": int(self.runtime.tick),
                "frame_capacity": self._buffer.maxlen,
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

    def _record_motion_locked(self) -> None:
        self._trajectory.append({
            "tick": int(self.runtime.tick),
            "x": float(self.runtime.body.x),
            "y": float(self.runtime.body.y),
        })
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

    def apply_experiment(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Apply only supported config keys, then reset."""
        self._halt_runner("PAUSED")
        self._invalidate_pending_captures_locked()
        with self._step_lock:
            with self._lock:
                before = self._control_state()
                seed = int(payload.get("seed", self.config.seed))
                cognition = payload.get("mechanisms") or payload.get("cognition") or {}
                cog_kwargs = {}
                allowed = set(CognitionConfig.__dataclass_fields__)
                for k, v in cognition.items():
                    if k in allowed:
                        cog_kwargs[k] = v
                if "cognition_enabled" in payload:
                    cog_kwargs["cognition_enabled"] = bool(payload["cognition_enabled"])
                self.config.seed = seed
                self.config.target_tick = payload.get("target_tick", self.config.target_tick)
                if "buffer_capacity" in payload:
                    self.config.buffer_capacity = int(payload["buffer_capacity"])
                if "ui_hz" in payload:
                    self.config.ui_hz = float(payload["ui_hz"])
                if "speed" in payload:
                    self.config.speed = float(payload["speed"])
                cog = CognitionConfig(
                    **{k: cog_kwargs[k] for k in CognitionConfig.__dataclass_fields__ if k in cog_kwargs}
                )
                planet = default_planet_config()
                world = payload.get("world") or {}
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
                b_in = payload.get("agent_body") or payload.get("body") or {}
                bdict = body.to_dict()
                for k, v in b_in.items():
                    if k in bdict and k not in {"footprint", "permeability"}:
                        try:
                            setattr(body, k, type(bdict[k])(v))
                        except Exception:
                            pass
                internal = default_internal_medium_config()
                cfg = PhysicalSystemConfig(planet=planet, body=body, internal=internal, cognition=cog)
                agent_count = int(payload.get("agent_count") or 1)
                # Non-cognition experiment mechanisms (world/signal/climate, …) are not
                # CognitionConfig fields — apply them after construction so Apply & reset
                # honors the same toggles the EXPERIMENT UI posts.
                non_cog = {
                    k: v for k, v in cognition.items()
                    if k not in allowed and k != "cognition_enabled"
                }
                if agent_count >= 2:
                    signal_on = bool(non_cog.get("experimental_physical_signal", False))
                    self.runtime = TwoAgentRuntime(
                        seed=seed, config=cfg, signal_enabled=signal_on,
                    )
                else:
                    self.runtime = PhysicalSystemRuntime(seed=seed, config=cfg)
                for mid, val in non_cog.items():
                    try:
                        self.runtime.set_mechanism(str(mid), bool(val))
                    except (KeyError, ValueError, TypeError):
                        pass
                self._runtime_generation += 1
                self.config.cognition_enabled = cog.cognition_enabled
                self.status = "PAUSED"
                self.mode = "LIVE"
                self.inspect_tick = None
                self._buffer = deque(maxlen=int(self.config.buffer_capacity))
                self._timeline = deque(maxlen=max(1024, int(self.config.buffer_capacity) * 8))
                self._prev_body = None
                self._prev_bodies = {}
                self._trajectory = deque(maxlen=max(256, int(self.config.buffer_capacity) * 4))
                self._telemetry = deque(maxlen=max(256, int(self.config.buffer_capacity) * 4))
                self._historical_compat = None
                self._published = None
                self._published_json = None
                self._run_started_at = None
                self._active_run_id = None
                self._close_scientific_locked()
                self._sci_live_dir = None
                self._finalize_key = None
                self._termination_reason = None
                self._last_finalize = None
                self._event_ring = deque(maxlen=EVENT_RING_MAX)
                self._event_keys = set()
                self._visual_dropped = 0
                self._capture_queue_drops = 0
                self._perf_window_start = time.monotonic()
                self._perf_ticks = 0
                self._perf_captures = 0
                self._record_motion_locked()
                frame = self._capture_locked(detail="full")
        self._maybe_push(frame, force=True)
        return self._with_receipt(
            frame, "APPLY_EXPERIMENT", deepcopy(payload), before,
            requires_reset=True,
        )


# process singleton
_SESSION: ObserverSession | None = None


def get_session() -> ObserverSession:
    global _SESSION
    if _SESSION is None:
        _SESSION = ObserverSession()
    return _SESSION
