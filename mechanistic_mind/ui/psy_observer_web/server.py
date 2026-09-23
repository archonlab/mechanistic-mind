"""FastAPI + WebSocket Observer adapter for Current MM."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__
from .session import get_session

app = FastAPI(title="Psy Observer Web", version=__version__)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

WEB_DIST = Path(__file__).resolve().parent / "web_dist"


class ControlBody(BaseModel):
    n: int = 1


class StopBody(BaseModel):
    save: bool = False
    reason: str | None = None
    wait: bool = True


class SpeedBody(BaseModel):
    speed: float = 1.0


class ExecutionModeBody(BaseModel):
    mode: str = "LIVE"
    target_tick: int | None = None


class EvidenceModeBody(BaseModel):
    mode: str = "FULL_SCIENTIFIC"


class ObserverHzBody(BaseModel):
    hz: float = 10.0


class TargetTickBody(BaseModel):
    target_tick: int | None = None


class SelectAgentBody(BaseModel):
    index: int = 0


class AblateBody(BaseModel):
    predictive_compression: bool | None = None
    multiscale_prediction: bool | None = None
    prospective_composition: bool | None = None
    instrumental_observation: bool | None = None
    bounded_memory: bool | None = None
    retrieval: bool | None = None
    cognition_enabled: bool | None = None


class ExperimentBody(BaseModel):
    seed: int | None = None
    target_tick: int | None = None
    speed: float | None = None
    ui_hz: float | None = None
    buffer_capacity: int | None = None
    cognition_enabled: bool | None = None
    mechanisms: dict[str, Any] | None = None
    world: dict[str, Any] | None = None
    agent_body: dict[str, Any] | None = None
    agent_count: int | None = None
    ecology_preset: str | None = None
    # Matched-control override when terrain is enabled by ecology preset (Advanced / Raw).
    terrain_seed: int | None = None
    public_preset: str | None = None
    psc_motor_resolution: str | None = None


@app.get("/api/health")
def health() -> dict[str, Any]:
    from mechanistic_mind.model.tiktaalik import display_name, model_metadata

    session = get_session()
    meta = session.runtime.model_identity() if hasattr(session.runtime, "model_identity") else model_metadata()
    return {
        "ok": True,
        "app": "Psy Observer",
        "model": display_name(),
        "model_metadata": meta,
        "version": __version__,
        "runtime": "TwoAgentRuntime" if getattr(session.runtime, "slots", None) else "PhysicalSystemRuntime",
        "instance_id": os.environ.get("PSY_OBSERVER_INSTANCE_ID"),
        "local": True,
    }


@app.get("/api/model")
def model_info() -> dict[str, Any]:
    from mechanistic_mind.model.tiktaalik import build_manifest

    session = get_session()
    manifest = build_manifest()
    return {
        "identity": session.runtime.model_identity(),
        "manifest": manifest,
        "mechanisms": session.runtime.mechanism_snapshot(),
    }


@app.get("/api/instance")
def instance() -> dict[str, Any]:
    info = health()
    info["identity"] = "Psy Observer · local"
    return info


@app.get("/api/state")
def state() -> dict[str, Any]:
    return get_session().current_frame()


@app.get("/api/header")
def header() -> dict[str, Any]:
    return (get_session().current_frame().get("header") or {})


@app.get("/api/world")
def world() -> dict[str, Any]:
    return (get_session().current_frame().get("world") or {})


@app.get("/api/causal-chain")
def causal_chain() -> dict[str, Any]:
    return (get_session().current_frame().get("causal_chain") or {})


@app.get("/api/mind")
def mind() -> dict[str, Any]:
    return (get_session().current_frame().get("mind") or {})


@app.get("/api/experiment")
def experiment() -> dict[str, Any]:
    return (get_session().current_frame().get("experiment") or {})


@app.get("/api/world/boundary")
def world_boundary() -> dict[str, Any]:
    frame = get_session().current_frame()
    return (frame.get("world") or {}).get("boundary") or {}


@app.get("/api/world/fields")
def world_fields() -> dict[str, Any]:
    frame = get_session().current_frame()
    world = frame.get("world") or {}
    return {
        "fields_available": world.get("fields_available"),
        "render_modes": world.get("render_modes"),
        "resolution": world.get("resolution"),
        "runtime_resolution": world.get("runtime_resolution") or world.get("resolution"),
        "transported_resolution": world.get("transported_resolution") or world.get("grid_shape_transported"),
        "grid_shape_transported": world.get("grid_shape_transported"),
        "boundary": world.get("boundary"),
    }


@app.get("/api/timeline")
def timeline(limit: int = 200) -> dict[str, Any]:
    return {"events": get_session().timeline(limit=limit)}


@app.get("/api/inspect/{tick}")
def inspect_tick(tick: int) -> dict[str, Any]:
    return get_session().frame_at_tick(tick)


@app.get("/api/replay/{tick}")
def replay_tick(tick: int) -> dict[str, Any]:
    return get_session().replay_frame(tick)


@app.get("/api/history")
def history() -> dict[str, Any]:
    return get_session().history()


@app.post("/api/control/play")
def control_play() -> dict[str, Any]:
    return get_session().play()


@app.post("/api/control/pause")
def control_pause() -> dict[str, Any]:
    return get_session().pause()


@app.post("/api/control/stop")
def control_stop(body: StopBody | None = None) -> dict[str, Any]:
    save = bool(body.save) if body is not None else False
    reason = body.reason if body is not None else None
    wait = True if body is None else bool(body.wait)
    return get_session().stop(save=save, reason=reason, wait=wait)


@app.get("/api/control/stop-info")
def control_stop_info() -> dict[str, Any]:
    return get_session().stop_info()


@app.get("/api/control/save-job")
def control_save_job() -> dict[str, Any]:
    """Poll Save & Stop layers without waiting on snapshot I/O."""
    sess = get_session()
    job = sess.save_job_status()
    job["header"] = {
        "status": sess.status,
        "tick": int(sess.runtime.tick),
        "runtime_generation": int(sess._runtime_generation),
    }
    return job


@app.post("/api/control/finalize")
def control_finalize(body: StopBody | None = None) -> dict[str, Any]:
    """Persist without requiring Stop (used by Save & Stop path and tests)."""
    reason = (body.reason if body is not None else None) or "USER_STOP_SAVED"
    sess = get_session()
    before_status = sess.status
    if before_status == "RUNNING":
        sess.pause()
    fin = sess.finalize_run(reason=reason)
    frame = sess.current_frame()
    frame["finalize"] = fin
    frame["control_receipt"] = {
        "operation": "FINALIZE",
        "accepted": bool(fin.get("accepted")),
        "tick": int(sess.runtime.tick),
        "reason": fin.get("error") if not fin.get("accepted") else fin.get("run_dir"),
    }
    return frame


@app.post("/api/control/step")
def control_step(body: ControlBody | None = None) -> dict[str, Any]:
    n = body.n if body else 1
    return get_session().step(n=n)


@app.post("/api/control/reset")
def control_reset(seed: int | None = None) -> dict[str, Any]:
    return get_session().reset(seed=seed)


@app.post("/api/control/speed")
def control_speed(body: SpeedBody) -> dict[str, Any]:
    return get_session().set_speed(body.speed)


@app.post("/api/control/execution-mode")
def control_execution_mode(body: ExecutionModeBody) -> dict[str, Any]:
    return get_session().set_execution_mode(body.mode, target_tick=body.target_tick)


@app.post("/api/control/evidence-mode")
def control_evidence_mode(body: EvidenceModeBody) -> dict[str, Any]:
    return get_session().set_evidence_mode(body.mode)


@app.post("/api/control/observer-hz")
def control_observer_hz(body: ObserverHzBody) -> dict[str, Any]:
    return get_session().set_observer_hz(body.hz)


@app.post("/api/control/target-tick")
def control_target_tick(body: TargetTickBody) -> dict[str, Any]:
    return get_session().set_target_tick(body.target_tick)


@app.post("/api/control/select-agent")
def control_select_agent(body: SelectAgentBody) -> dict[str, Any]:
    return get_session().select_agent(body.index)


@app.post("/api/ablations")
def ablations(body: AblateBody) -> dict[str, Any]:
    flags = {k: v for k, v in body.model_dump().items() if v is not None and k != "cognition_enabled"}
    sess = get_session()
    if body.cognition_enabled is not None:
        return sess.reset(cognition_enabled=body.cognition_enabled)
    return sess.set_ablations(**flags)


@app.post("/api/experiment")
def apply_experiment(body: ExperimentBody) -> dict[str, Any]:
    from fastapi import HTTPException
    try:
        return get_session().apply_experiment(body.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class LiveInterventionBody(BaseModel):
    ecology_preset: str | None = None
    cognition_enabled: bool | None = None
    mechanisms: dict[str, Any] | None = None
    category: str | None = None
    source: str | None = None
    target_tick: int | None = None
    ui_hz: float | None = None
    buffer_capacity: int | None = None
    # Present for UI convenience; changing these is rejected as WORLD-STRUCTURAL.
    seed: int | None = None
    world: dict[str, Any] | None = None
    agent_count: int | None = None
    agent_body: dict[str, Any] | None = None


@app.post("/api/experiment/live")
def apply_live_intervention(body: LiveInterventionBody) -> dict[str, Any]:
    """LIVE ecology/mechanism mutation — does not rebuild runtime or reset agents."""
    return get_session().apply_live_intervention(body.model_dump(exclude_none=True))


@app.get("/api/interventions")
def list_interventions() -> dict[str, Any]:
    return get_session().list_world_interventions()


@app.get("/api/snapshot")
def snapshot() -> dict[str, Any]:
    return get_session().snapshot()


@app.get("/api/snapshot/meta")
def snapshot_meta() -> dict[str, Any]:
    return get_session().snapshot_meta()


@app.post("/api/snapshot/restore")
def snapshot_restore(payload: dict[str, Any]) -> dict[str, Any]:
    return get_session().restore(payload)


@app.get("/api/data")
def data_panel() -> dict[str, Any]:
    sess = get_session()
    frame = sess.current_frame()
    return {
        "buffer_len": len(sess._buffer),
        "timeline_len": len(sess._timeline),
        "buffer_capacity": sess.config.buffer_capacity,
        "ui_hz": sess.config.ui_hz,
        "speed": sess.config.speed,
        "runtime_generation": sess._runtime_generation,
        "history": sess.history(),
        "telemetry_policy": {
            "frames": sess._buffer.maxlen,
            "timeline": sess._timeline.maxlen,
            "trajectory": sess._trajectory.maxlen,
            "telemetry": sess._telemetry.maxlen,
            "world_transport_max_side": 64,
        },
        "metrics": (frame.get("mind") or {}).get("metrics"),
        "snapshot_schema": "mm.physical_system.snapshot.v2",
        "note": "Raw scientific snapshot via GET /api/snapshot. History is bounded; not a full JSONL load.",
    }



class ActionTraceBody(BaseModel):
    enabled: bool = False
    mode: str = "every_10"


@app.get("/api/diagnostics")
def diagnostics() -> dict[str, Any]:
    return get_session().diagnostics()



@app.get("/api/diagnostics/gearbox")
def diagnostics_gearbox() -> dict[str, Any]:
    """Causal gearbox maps (baseline vs experimental). Read-only artifacts."""
    from pathlib import Path
    root = Path(__file__).resolve().parents[3] / "results" / "mm_causal_gearbox"
    def load(name: str):
        p = root / name
        if not p.exists():
            return {"status": "NOT_AVAILABLE", "path": str(p)}
        import json
        return json.loads(p.read_text())
    sess = get_session()
    rt = getattr(sess, "runtime", None)
    live = {}
    if rt is not None:
        import numpy as np
        live = {
            "tick": int(rt.tick),
            "changing": {
                "body.vx_vy": [float(rt.body.vx), float(rt.body.vy)],
                "body.xy": [float(rt.body.x), float(rt.body.y)],
                "body.B_sum": float(rt.body.B.sum()),
                "internal.c_l1": float(np.abs(rt.internal.c).sum()),
                "motor_u": [float(rt.body.motor_ux), float(rt.body.motor_uy)],
                "selected_action": rt.last_selected_action,
                "endo_mode": rt.config.endogenous_motor.mode,
                "morph_mode": rt.config.morphology_mechanics.mode,
                "orient_mode": rt.config.body_orientation.mode,
                "deformation_mode": rt.config.body_deformation.mode,
                "deformation_work_mode": rt.config.deformation_work.mode,
                "mechanical_work_reservoir": float(getattr(rt.body, "mechanical_work_reservoir", 0.0) or 0.0),
                "motor_drive_requested": (getattr(rt, "last_motor_work_ledger", None) or {}).get("motor_drive_requested"),
                "motor_force_requested": (getattr(rt, "last_motor_work_ledger", None) or {}).get("motor_force_requested"),
                "motor_work_requested": (getattr(rt, "last_motor_work_ledger", None) or {}).get("motor_work_requested"),
                "motor_force_realized": (getattr(rt, "last_motor_work_ledger", None) or {}).get("motor_force_realized"),
                "motor_work_realized": (getattr(rt, "last_motor_work_ledger", None) or {}).get("motor_work_realized"),
                "motor_work_unrealized": (getattr(rt, "last_motor_work_ledger", None) or {}).get("motor_work_unrealized"),
                "work_limit_fraction": (getattr(rt, "last_motor_work_ledger", None) or {}).get("work_limit_fraction"),
                "motor_work_receipt_id": (getattr(rt, "last_motor_work_ledger", None) or {}).get("receipt_id"),
                "action_impulse_requested": (getattr(rt, "last_action_work_ledger", None) or {}).get("action_impulse_requested"),
                "action_impulse_realized": (getattr(rt, "last_action_work_ledger", None) or {}).get("action_impulse_realized"),
                "action_dv_requested": (getattr(rt, "last_action_work_ledger", None) or {}).get("action_dv_requested"),
                "action_dv_realized": (getattr(rt, "last_action_work_ledger", None) or {}).get("action_dv_realized"),
                "action_work_requested": (getattr(rt, "last_action_work_ledger", None) or {}).get("action_work_requested"),
                "action_work_allocated": (getattr(rt, "last_action_work_ledger", None) or {}).get("action_work_allocated"),
                "action_work_realized": (getattr(rt, "last_action_work_ledger", None) or {}).get("action_work_realized"),
                "action_work_unrealized": (getattr(rt, "last_action_work_ledger", None) or {}).get("action_work_unrealized"),
                "action_work_limit_fraction": (getattr(rt, "last_action_work_ledger", None) or {}).get("action_work_limit_fraction"),
                "deformation_work_requested": (getattr(rt, "last_work_allocation", None) or {}).get("requested_deformation"),
                "deformation_work_realized": (getattr(rt, "last_deformation_meta", None) or {}).get("reservoir_work_supplied"),
                "work_allocation_receipt": getattr(rt, "last_work_allocation", None),
                "body_R_sum": float(np.sum(rt.body.R_site)) if getattr(rt.body, "R_site", None) is not None else 0.0,
                "env_R_sum": float(np.sum(rt.world.R)) if getattr(rt.world, "R", None) is not None else 0.0,
                "body_R_A": float(np.sum(rt.body.R_A_site)) if getattr(rt.body, "R_A_site", None) is not None else 0.0,
                "body_R_B": float(np.sum(rt.body.R_B_site)) if getattr(rt.body, "R_B_site", None) is not None else 0.0,
                "env_R_A": float(np.sum(rt.world.R_A)) if getattr(rt.world, "R_A", None) is not None else 0.0,
                "env_R_B": float(np.sum(rt.world.R_B)) if getattr(rt.world, "R_B", None) is not None else 0.0,
                "resource_acquired": (getattr(rt, "last_resource_ledger", None) or {}).get("acquired_by_body"),
                "work_credited_from_R": (getattr(rt, "last_resource_ledger", None) or {}).get("work_credited"),
                "complementary_work": (getattr(rt, "last_complementary_ledger", None) or {}).get("work_credited"),
                "limiting_resource": (getattr(rt, "last_complementary_ledger", None) or {}).get("limiting_resource"),
                "work_supplied": (getattr(rt, "last_work_ledger", None) or {}).get("reservoir_work_supplied"),
                "deformation_potential": (getattr(rt, "last_work_ledger", None) or {}).get("potential_after"),
                "deformation": (getattr(rt, "last_deformation_meta", None) or {}).get("deformation"),
                "theta": float(getattr(rt.body, "theta", 0.0)),
                "omega": float(getattr(rt.body, "omega", 0.0)),
                "tau": (getattr(rt, "last_orientation_meta", None) or {}).get("tau"),
            },
        }
    experimental = load("EXPERIMENTAL_GEARBOX.json")
    if isinstance(experimental, dict):
        experimental = dict(experimental)
        experimental["added_edges"] = list(experimental.get("added_edges") or []) + [
            {"from": "B_site", "to": "deformation", "kind": "DIRECT", "graph": "CURRENT_INTEGRATED", "level": 4, "lag": "BOUNDED MATERIAL RESPONSE", "type": "PROMOTED"},
            {"from": "deformation", "to": "body_local_geometry", "kind": "DIRECT", "graph": "CURRENT_INTEGRATED", "level": 4, "lag": "SAME-TICK", "type": "PROMOTED"},
            {"from": "body_local_geometry", "to": "site_exposure_force_torque", "kind": "MEDIATED", "graph": "CURRENT_INTEGRATED", "level": 4, "lag": "SAME-TICK", "type": "PROMOTED"},
            {"from": "mechanical_work_reservoir", "to": "deformation_work", "kind": "DIRECT", "graph": "CURRENT_INTEGRATED", "level": "AUDIT", "lag": "SAME-TICK", "type": "EXPERIMENTAL"},
            {"from": "ENV_A", "to": "BODY_A", "kind": "DIRECT", "graph": "CURRENT_INTEGRATED", "level": 4, "lag": "SITE-LOCAL", "type": "PROMOTED"},
            {"from": "ENV_B", "to": "BODY_B", "kind": "DIRECT", "graph": "CURRENT_INTEGRATED", "level": 4, "lag": "SITE-LOCAL", "type": "PROMOTED"},
            {"from": "BODY_A+BODY_B", "to": "COMPLEMENTARY_CONVERSION", "kind": "COUPLED", "graph": "CURRENT_INTEGRATED", "level": 4, "lag": "SAME-TICK", "type": "PROMOTED"},
            {"from": "COMPLEMENTARY_CONVERSION", "to": "mechanical_work_reservoir", "kind": "DIRECT", "graph": "CURRENT_INTEGRATED", "level": 4, "lag": "SAME-TICK", "type": "PROMOTED"},
        ]
    return {
        "baseline": load("BASELINE_GEARBOX.json"),
        "experimental": experimental,
        "evidence_table_path": "results/mm_causal_gearbox/GEARBOX_EVIDENCE_TABLE.md",
        "morphology_gearbox_path": "results/mm_body_morphology_mechanics/EXPERIMENTAL_GEARBOX_MORPHOLOGY.json",
        "integrated_gearbox_path": "results/mm_integrated_physical_runtime/CURRENT_INTEGRATED_GEARBOX.json",
        "deformation_gearbox_path": "results/mm_body_deformation/GEARBOX_UPDATE.json",
        "deformation_work_gearbox_path": "results/mm_deformation_work/ENERGY_GEARBOX.json",
        "model": "MM_1_0_TIKTAALIK",
        "live": live,
    }


@app.get("/api/mechanisms")
def get_mechanisms(include_catalog: bool = True) -> dict[str, Any]:
    """CURRENT INTEGRATED MM mechanism registry + live toggles + integrity.

    include_catalog=false → WARM enabled flags only (no COLD catalog/descriptions).
    """
    sess = get_session()
    if not include_catalog and hasattr(sess, "mechanisms_warm_state"):
        return sess.mechanisms_warm_state()
    from mechanistic_mind.physical_system.mechanism_registry import RUNTIME_VERSION
    from mechanistic_mind.physical_system.structured_events import EVENT_SCHEMA
    from mechanistic_mind.physical_system.mechanism_configuration import (
        fresh_experiment_default_map,
        mechanism_catalog,
        NEW_EXPERIMENT_VISION_RADIUS,
    )
    rt = getattr(sess, "runtime", None)
    if rt is None:
        return {"error": "no runtime", "model": RUNTIME_VERSION}
    snap = rt.mechanisms()
    integrity = sess.mechanism_integrity_status()
    return {
        "model": "MM 1.0 — Tiktaalik",
        "runtime_version": snap.get("runtime_version"),
        "catalog_included": True,
        "runtime_generation": int(getattr(sess, "_runtime_generation", 0) or 0),
        "mechanisms": snap.get("mechanisms"),
        "enabled": snap.get("enabled"),
        "disabled": snap.get("disabled"),
        "force_contributions": getattr(rt, "last_force_contributions", None),
        "events_schema": EVENT_SCHEMA,
        "mechanism_integrity": integrity,
        "preflight": integrity.get("preflight"),
        "fresh_defaults": fresh_experiment_default_map(),
        "fresh_vision_radius": NEW_EXPERIMENT_VISION_RADIUS,
        "catalog": mechanism_catalog(),
        "psc_motor_resolution": (
            str(getattr(getattr(getattr(rt, "config", None), "cognition", None), "psc_motor_resolution", None) or "LOCO_FACTORIZED")
        ),
    }


@app.get("/api/mechanisms/state")
def get_mechanisms_state() -> dict[str, Any]:
    """WARM mechanism enabled flags — safe to poll while RUNNING."""
    return get_session().mechanisms_warm_state()


@app.get("/api/mechanisms/defaults")
def get_mechanism_defaults() -> dict[str, Any]:
    from mechanistic_mind.physical_system.mechanism_configuration import (
        fresh_experiment_default_map,
        mechanism_catalog,
        NEW_EXPERIMENT_VISION_RADIUS,
        RESOLVED_CONFIG_VERSION,
    )
    return {
        "resolved_config_version": RESOLVED_CONFIG_VERSION,
        "mechanisms": fresh_experiment_default_map(),
        "vision_radius": NEW_EXPERIMENT_VISION_RADIUS,
        "catalog": mechanism_catalog(),
    }


@app.get("/api/mechanisms/preflight")
def get_mechanism_preflight() -> dict[str, Any]:
    return get_session().mechanism_integrity_status()


class PscMotorResolutionBody(BaseModel):
    mode: str | None = None
    psc_motor_resolution: str | None = None


class MechanismToggleBody(BaseModel):
    enabled: bool


@app.post("/api/mechanisms/{mechanism_id}")
def post_mechanism(mechanism_id: str, body: MechanismToggleBody) -> dict[str, Any]:
    return get_session().set_mechanism(mechanism_id, bool(body.enabled))


class VisionRadiusBody(BaseModel):
    radius: int


@app.post("/api/vision/radius")
def post_vision_radius(body: VisionRadiusBody) -> dict[str, Any]:
    """LIVE Moore candidate radius R∈{1,2,3}. Sensor geometry only — no reset."""
    return get_session().set_vision_radius(int(body.radius))


@app.get("/api/vision/radius")
def get_vision_radius() -> dict[str, Any]:
    from mechanistic_mind.physical_system.near_field_exteroception import (
        DEFAULT_VISION_RADIUS,
        clamp_vision_radius,
        moore_max_candidates,
    )

    sess = get_session()
    rt = sess.runtime
    nfe = None
    slots = getattr(rt, "slots", None)
    if slots:
        nfe = getattr(slots[0].config, "near_field_exteroception", None)
    else:
        nfe = getattr(getattr(rt, "config", None), "near_field_exteroception", None)
    r = clamp_vision_radius(getattr(nfe, "radius", DEFAULT_VISION_RADIUS) if nfe else DEFAULT_VISION_RADIUS)
    return {
        "radius": r,
        "max_candidates": moore_max_candidates(r),
        "options": [
            {"radius": 1, "max_candidates": 8, "label": "R=1 · max 8 cells"},
            {"radius": 2, "max_candidates": 24, "label": "R=2 · max 24 cells"},
            {"radius": 3, "max_candidates": 48, "label": "R=3 · max 48 cells"},
        ],
        "note": "Moore candidate neighborhood only; FOV/distance/illumination filters unchanged.",
    }


@app.get("/api/evidence/gearbox")
def integrated_gearbox() -> dict[str, Any]:
    import json
    root = Path(__file__).resolve().parents[3]
    pack = root / "results" / "mm_integrated_physical_runtime"
    graph = pack / "CURRENT_INTEGRATED_GEARBOX.json"
    provenance = pack / "PROVENANCE_MAP.json"
    return {
        "status": "AVAILABLE" if graph.exists() else "NOT_AVAILABLE",
        "integrated": json.loads(graph.read_text()) if graph.exists() else None,
        "provenance": json.loads(provenance.read_text()) if provenance.exists() else None,
        "live": get_mechanisms(),
        "artifact": "results/mm_integrated_physical_runtime/CURRENT_INTEGRATED_GEARBOX.json",
    }


@app.get("/api/results/packs")
def result_packs() -> dict[str, Any]:
    """Catalog of mm_* result packs — lightweight (no full directory listing).

    LIVE RUNNING refreshAux used to call this every ~1.5s and pay
    ``len(list(p.iterdir()))`` per pack — O(files on disk) Observer-side cost that
    grows with research output and can starve the UI while the sim still runs.
    """
    import json
    import time as _time

    root = Path(__file__).resolve().parents[3]
    cache = getattr(result_packs, "_cache", None)
    now = _time.monotonic()
    if isinstance(cache, dict) and (now - float(cache.get("t", 0))) < 5.0:
        return cache["payload"]
    out = []
    results_root = root / "results"
    if results_root.is_dir():
        for p in sorted(results_root.glob("mm_*")):
            if not p.is_dir():
                continue
            promotion = p / "PROMOTION.json"
            promoted = None
            if promotion.exists():
                try:
                    promoted = bool(json.loads(promotion.read_text()).get("promote"))
                except Exception:
                    promoted = None
            out.append({
                "id": p.name,
                "has_final_report": (p / "FINAL_REPORT.md").exists(),
                "has_promotion": promotion.exists(),
                "promoted": promoted,
                # Do not scan pack directories — was a LIVE-path disk tax.
                "files": None,
            })
    payload = {
        "status": "CATALOG_ONLY",
        "analyzer": "NOT_AVAILABLE",
        "packs": out,
    }
    result_packs._cache = {"t": now, "payload": payload}  # type: ignore[attr-defined]
    return payload


@app.get("/api/results/packs/{pack_id}")
def result_pack(pack_id: str) -> dict[str, Any]:
    import json
    if not pack_id.startswith("mm_") or "/" in pack_id or ".." in pack_id:
        return {"status": "REJECTED", "reason": "invalid pack id"}
    root = Path(__file__).resolve().parents[3] / "results" / pack_id
    if not root.is_dir():
        return {"status": "NOT_AVAILABLE", "pack_id": pack_id}
    parsed = {}
    for name in ("PROMOTION.json", "GATE_TABLE.json", "GEARBOX_UPDATE.json"):
        p = root / name
        if p.exists():
            try:
                parsed[name] = json.loads(p.read_text())
            except Exception:
                parsed[name] = {"status": "INVALID_JSON"}
    return {
        "status": "AVAILABLE",
        "pack_id": pack_id,
        "files": sorted(p.name for p in root.iterdir() if p.is_file()),
        "artifacts": parsed,
        "analyzer": "NOT_AVAILABLE",
    }


@app.get("/api/events")
def get_events(limit: int = 50) -> dict[str, Any]:
    sess = get_session()
    rt = getattr(sess, "runtime", None)
    if rt is None:
        return {"events": [], "error": "no runtime"}
    if hasattr(sess, "collected_events"):
        events = sess.collected_events(limit=int(limit))
    else:
        from mechanistic_mind.ui.psy_observer_web.serialize import collect_observer_events
        events = collect_observer_events(rt, limit=int(limit))
    selected = None
    if getattr(rt, "slots", None):
        selected = f"agent_{int(getattr(rt, 'selected_index', 0) or 0)}"
    else:
        selected = "agent_0"
    return {
        "events": events,
        "selected_agent_id": selected,
        "note": "Events from all agents with observer attribution. Filter is observer-only.",
        "event_ring_size": len(getattr(sess, "_event_ring", []) or []),
    }


@app.get("/api/runs")
def list_runs() -> dict[str, Any]:
    """Catalog of finalized Psy Observer Web runs (scientific evidence aware)."""
    from mechanistic_mind.ui.psy_observer_web.scientific_history import list_psyweb_runs
    from mechanistic_mind.ui.psy_observer_web.run_finalize import default_results_root

    sess = get_session()
    root = Path(sess.config.results_root) if getattr(sess.config, "results_root", None) else default_results_root()
    runs = list_psyweb_runs(root)
    return {"runs": runs, "results_root": str(root), "count": len(runs)}


@app.get("/api/analysis/evidence")
def analysis_evidence(
    source: str = "current",
    run_id: str | None = None,
    cutoff_tick: int | None = None,
) -> dict[str, Any]:
    """Read-only scientific evidence package for Analyzer.

    source=current — live run evidence up to cutoff (default: current tick).
    source=saved — finalized run directory evidence.
    Never advances simulation or mutates evidence.
    """
    from mechanistic_mind.ui.psy_observer_web.scientific_history import (
        load_evidence_package,
        published_run_dir,
    )
    from mechanistic_mind.ui.psy_observer_web.run_finalize import default_results_root
    import json

    sess = get_session()
    src = str(source or "current").lower()
    if src == "current":
        pkg = sess.scientific_evidence(cutoff_tick=cutoff_tick)
        pkg["source"] = "current"
        return pkg

    if src != "saved":
        return {"error": "invalid source", "accepted": False}

    rid = str(run_id or "").strip()
    if not rid or "/" in rid or ".." in rid or not rid.startswith("psyweb-"):
        return {"error": "invalid run_id", "accepted": False}

    root = Path(sess.config.results_root) if getattr(sess.config, "results_root", None) else default_results_root()
    run_dir = published_run_dir(root, rid)
    if not run_dir.is_dir():
        return {"error": "run not found", "run_id": rid, "accepted": False}

    identity: dict[str, Any] = {"run_id": rid}
    manifest = {}
    mj = run_dir / "run.json"
    if mj.is_file():
        try:
            manifest = json.loads(mj.read_text(encoding="utf-8"))
            identity.update({
                "runtime_type": manifest.get("runtime_type"),
                "seed": manifest.get("seed"),
                "agent_count": manifest.get("agent_count"),
                "runtime_generation": manifest.get("runtime_generation"),
                "final_tick": manifest.get("final_tick"),
            })
        except Exception:
            pass

    cut = cutoff_tick
    if cut is None and manifest.get("final_tick") is not None:
        cut = int(manifest["final_tick"])

    pkg = load_evidence_package(
        evidence_dir=run_dir,
        runtime=None,
        ui_timeline=[],
        ui_events=[],
        cutoff_tick=cut,
        runtime_status="STOPPED",
        run_id=rid,
        identity=identity,
        include_bulk_rows=False,
        include_behavioral=False,
        include_v3_core=False,
    )
    pkg["source"] = "saved"
    pkg["run_dir"] = str(run_dir)
    return pkg


_ANALYSIS_JOBS: dict[str, dict[str, Any]] = {}


def _analysis_jobs_root() -> Path:
    from mechanistic_mind.ui.psy_observer_web.run_finalize import default_results_root
    sess = get_session()
    root = Path(sess.config.results_root) if getattr(sess.config, "results_root", None) else default_results_root()
    return Path(root) / "analysis_jobs"


@app.post("/api/analysis/jobs")
def analysis_job_start(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Start heavy analysis in a subprocess. Does not mutate the source run."""
    import subprocess
    import sys
    import uuid
    from datetime import datetime, timezone

    from mechanistic_mind.ui.psy_observer_web.scientific_history import published_run_dir
    from mechanistic_mind.ui.psy_observer_web.run_finalize import default_results_root

    body = payload or {}
    source = str(body.get("source") or "current").lower()
    sess = get_session()
    run_dir: Path | None = None
    rid = str(body.get("run_id") or "").strip()
    if source == "current":
        with sess._lock:
            live = sess._sci_live_dir
            if sess._sci_writer is not None:
                sess._sci_writer.flush()
            if sess._v3_writer is not None:
                try:
                    sess._v3_writer.flush()
                except Exception:
                    pass
            rid = rid or str(sess._active_run_id or "")
        run_dir = Path(live) if live else None
    elif source == "saved":
        if not rid or "/" in rid or ".." in rid or not rid.startswith("psyweb-"):
            return {"accepted": False, "error": "invalid run_id"}
        root = Path(sess.config.results_root) if getattr(sess.config, "results_root", None) else default_results_root()
        run_dir = published_run_dir(root, rid)
    else:
        return {"accepted": False, "error": "invalid source"}
    if run_dir is None or not run_dir.is_dir():
        return {"accepted": False, "error": "run directory not found"}

    job_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
    out_dir = _analysis_jobs_root() / job_id
    out_dir.mkdir(parents=True, exist_ok=True)
    # Never write analyzer artifacts into the live/forensic run directory.
    max_tick = body.get("cutoff_tick")
    cmd = [
        sys.executable, "-m", "mechanistic_mind.scientific_v3.analyzer_next.job",
        "--run-dir", str(run_dir),
        "--out-dir", str(out_dir),
    ]
    if max_tick is not None:
        cmd.extend(["--max-tick", str(int(max_tick))])
    env = dict(os.environ)
    env.setdefault("PYTHONUNBUFFERED", "1")
    proc = subprocess.Popen(cmd, cwd=str(Path(__file__).resolve().parents[3]), env=env)
    _ANALYSIS_JOBS[job_id] = {
        "pid": proc.pid,
        "out_dir": str(out_dir),
        "run_dir": str(run_dir),
        "run_id": rid,
        "source": source,
        "proc": proc,
    }
    return {
        "accepted": True,
        "job_id": job_id,
        "pid": proc.pid,
        "out_dir": str(out_dir),
        "run_dir": str(run_dir),
        "run_id": rid,
        "phase": "QUEUED",
        "isolates_observer": True,
    }


@app.get("/api/analysis/jobs/{job_id}")
def analysis_job_status(job_id: str) -> dict[str, Any]:
    if "/" in job_id or ".." in job_id:
        return {"error": "invalid job_id"}
    rec = _ANALYSIS_JOBS.get(job_id)
    out_dir = Path(rec["out_dir"]) if rec else (_analysis_jobs_root() / job_id)
    progress_path = out_dir / "progress.json"
    progress = {}
    if progress_path.is_file():
        try:
            progress = json.loads(progress_path.read_text(encoding="utf-8"))
        except Exception:
            progress = {}
    alive = None
    if rec and rec.get("proc") is not None:
        alive = rec["proc"].poll() is None
        if not alive and progress.get("status") not in ("COMPLETE", "FAILED", "CANCELLED"):
            progress.setdefault("status", "FAILED")
            progress.setdefault("phase", "FAILED")
            progress.setdefault("error", f"analyzer process exited {rec['proc'].returncode}")
    return {
        "job_id": job_id,
        "pid": (rec or {}).get("pid"),
        "observer_pid": os.getpid(),
        "alive": alive,
        "out_dir": str(out_dir),
        **progress,
    }


@app.post("/api/analysis/jobs/{job_id}/cancel")
def analysis_job_cancel(job_id: str) -> dict[str, Any]:
    if "/" in job_id or ".." in job_id:
        return {"accepted": False, "error": "invalid job_id"}
    rec = _ANALYSIS_JOBS.get(job_id)
    out_dir = Path(rec["out_dir"]) if rec else (_analysis_jobs_root() / job_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "CANCEL").write_text("1", encoding="utf-8")
    proc = (rec or {}).get("proc")
    if proc is not None and proc.poll() is None:
        try:
            proc.terminate()
        except Exception:
            pass
    return {"accepted": True, "job_id": job_id, "phase": "CANCELLED"}


@app.get("/api/analysis/jobs/{job_id}/result")
def analysis_job_result(job_id: str) -> dict[str, Any]:
    if "/" in job_id or ".." in job_id:
        return {"error": "invalid job_id"}
    rec = _ANALYSIS_JOBS.get(job_id)
    out_dir = Path(rec["out_dir"]) if rec else (_analysis_jobs_root() / job_id)
    summary = out_dir / "analysis_http_summary.json"
    if not summary.is_file():
        return {"error": "result not ready", "job_id": job_id, "out_dir": str(out_dir)}
    data = json.loads(summary.read_text(encoding="utf-8"))
    data["job_id"] = job_id
    data["artifacts_dir"] = str(out_dir)
    data["source"] = (rec or {}).get("source")
    return data
    pkg["manifest"] = {
        "final_tick": manifest.get("final_tick"),
        "seed": manifest.get("seed"),
        "runtime_type": manifest.get("runtime_type"),
        "termination_reason": manifest.get("termination_reason"),
        "scientific_history": manifest.get("scientific_history"),
    }
    v3 = pkg.get("scientific_v3_core") or {}
    pkg["v3_evidence_health"] = {
        "writer_attached": None,
        "archived": v3.get("evidence_version") == "SCIENTIFIC_V3",
        "status": v3.get("status") or "NOT_RECORDED",
        "run_dir": str(run_dir),
    }
    return pkg


@app.post("/api/analysis/save")
def analysis_save(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Persist a versioned analysis report under run_dir/analysis/<timestamp>/."""
    from mechanistic_mind.ui.psy_observer_web.scientific_history import (
        save_analysis_output,
        published_run_dir,
        ANALYZER_VERSION,
    )
    from mechanistic_mind.ui.psy_observer_web.run_finalize import default_results_root
    from datetime import datetime, timezone

    body = payload or {}
    rid = str(body.get("run_id") or "").strip()
    if not rid or "/" in rid or ".." in rid or not rid.startswith("psyweb-"):
        return {"accepted": False, "error": "invalid run_id"}
    sess = get_session()
    root = Path(sess.config.results_root) if getattr(sess.config, "results_root", None) else default_results_root()
    run_dir = published_run_dir(root, rid)
    if not run_dir.is_dir():
        return {"accepted": False, "error": "run not found", "run_id": rid}

    report_text = str(body.get("report_text") or "")
    report_json = body.get("report_json")
    if not isinstance(report_json, dict):
        report_json = {"report_text": report_text}
    report_json.setdefault("analyzer_version", ANALYZER_VERSION)
    report_json.setdefault("analysis_timestamp", datetime.now(timezone.utc).isoformat())
    report_json.setdefault("run_id", rid)
    out = save_analysis_output(run_dir, report_text=report_text, report_json=report_json)
    return {"accepted": True, "analysis_dir": str(out), "run_id": rid}


@app.get("/api/diagnostics/motion")
def diagnostics_motion() -> dict[str, Any]:
    bundle = get_session().diagnostics()
    return {
        "last_motion_receipt": bundle.get("last_motion_receipt"),
        "motion_trace": bundle.get("motion_trace"),
    }

@app.post("/api/diagnostics/motion-trace")
def diagnostics_motion_trace(body: ActionTraceBody) -> dict[str, Any]:
    sess = get_session()
    if hasattr(sess, "set_motion_trace"):
        return sess.set_motion_trace(enabled=bool(body.enabled), mode=str(body.mode or "every_10"))
    rt = getattr(sess, "runtime", None)
    if rt is None:
        return {"error": "no runtime"}
    return rt.set_motion_trace(enabled=bool(body.enabled), mode=str(body.mode or "every_10"))




class ObserverDetailBody(BaseModel):
    preset: str | None = None
    products: list[str] | None = None
    product: str | None = None
    enabled: bool | None = None


@app.get("/api/observer/detail")
def get_observer_detail() -> dict[str, Any]:
    sess = get_session()
    if hasattr(sess, "observer_interest_snapshot"):
        return sess.observer_interest_snapshot()
    return {"preset": "NORMAL", "products": [], "note": "interest_unavailable"}


@app.post("/api/observer/detail")
def set_observer_detail(body: ObserverDetailBody) -> dict[str, Any]:
    """Set Observer display detail (MINIMAL|NORMAL|FULL) or product interest.

    Does NOT change cognition, mechanisms, scientific evidence, or RNG.
    """
    sess = get_session()
    if body.product is not None and body.enabled is not None and hasattr(sess, "update_observer_product"):
        return sess.update_observer_product(str(body.product), bool(body.enabled))
    if body.products is not None and hasattr(sess, "set_observer_products"):
        return sess.set_observer_products(list(body.products))
    if body.preset and hasattr(sess, "set_observer_detail_preset"):
        return sess.set_observer_detail_preset(str(body.preset))
    return {"error": "no_handler"}

@app.get("/api/diagnostics/sensorimotor-consequence")
def diagnostics_sensorimotor_consequence() -> dict[str, Any]:
    sess = get_session()
    if hasattr(sess, "sensorimotor_consequence_panel"):
        return sess.sensorimotor_consequence_panel()
    return {"schema": "mm.observer.sensorimotor_consequence.v1", "agents": [], "error": "panel_unavailable"}





@app.post("/api/config/psc-motor-resolution")
def config_psc_motor_resolution(body: PscMotorResolutionBody | None = None) -> dict[str, Any]:
    """Set PSC motor resolution. Default LOCO_FACTORIZED; OBSERVED_COMPOSITE is EXPERIMENTAL."""
    body = body or PscMotorResolutionBody()
    mode = body.mode or body.psc_motor_resolution or "LOCO_FACTORIZED"
    sess = get_session()
    if hasattr(sess, "set_psc_motor_resolution"):
        return sess.set_psc_motor_resolution(str(mode))
    return {"accepted": False, "reason": "session_unsupported"}

@app.get("/api/config/psc-motor-resolution")
def get_psc_motor_resolution() -> dict[str, Any]:
    sess = get_session()
    rt = getattr(sess, "runtime", None)
    mode = "LOCO_FACTORIZED"
    try:
        cog = getattr(getattr(rt, "config", None), "cognition", None)
        mode = str(getattr(cog, "psc_motor_resolution", mode) or mode)
    except Exception:
        pass
    return {
        "psc_motor_resolution": mode,
        "experimental": mode.upper() == "OBSERVED_COMPOSITE",
        "label": "EXPERIMENTAL" if str(mode).upper() == "OBSERVED_COMPOSITE" else "DEFAULT",
        "history_reset": False,
        "cognition_reset": False,
        "smc_reset": False,
        "body_reset": False,
    }

@app.get("/api/diagnostics/signal-sensorimotor")
def diagnostics_signal_sensorimotor(include_shadow: bool = False) -> dict[str, Any]:
    sess = get_session()
    if hasattr(sess, "signal_sensorimotor_panel"):
        return sess.signal_sensorimotor_panel(include_shadow=bool(include_shadow))
    return {"schema": "mm.observer.signal_sensorimotor.v1", "error": "panel_unavailable"}

@app.get("/api/diagnostics/historical-sensorimotor-selection")
def diagnostics_historical_sensorimotor_selection() -> dict[str, Any]:
    sess = _session()
    if hasattr(sess, "historical_sensorimotor_selection_panel"):
        return sess.historical_sensorimotor_selection_panel()
    return {"schema": "mm.observer.historical_sensorimotor_selection.v1", "agents": [], "ui_state": "OFF", "error": "panel_unavailable"}

@app.get("/api/diagnostics/why")
def diagnostics_why() -> dict[str, Any]:
    bundle = get_session().diagnostics()
    return {
        "last_decision_receipt": bundle.get("last_decision_receipt"),
        "counterfactual_latest": bundle.get("counterfactual_latest"),
        "summary": bundle.get("summary"),
    }


@app.get("/api/diagnostics/occupancy")
def diagnostics_occupancy() -> dict[str, Any]:
    return get_session().diagnostics().get("occupancy") or {}


@app.get("/api/geometry/live")
def geometry_live() -> dict[str, Any]:
    """Bounded LIVE geometry interpretation from current published frame / runtime."""
    sess = get_session()
    frame = sess.current_frame()
    geo = (frame or {}).get("geometry_interpretation")
    if isinstance(geo, dict):
        return geo
    from mechanistic_mind.ui.psy_observer_web.geometry.live_summary import (
        geometry_live_compact_summary,
    )
    with sess._step_lock:
        overlay = sess._geo_overlay_locked(detail="compact")
        return geometry_live_compact_summary(
            sess.runtime,
            previous_body=getattr(sess, "_prev_body", None),
            previous_bodies=getattr(sess, "_prev_bodies", None) or {},
            traversability_overlay=overlay,
        )


@app.get("/api/geometry/empirical")
def geometry_empirical_payload() -> dict[str, Any]:
    """Full empirical overlay snapshot for reconnect / version miss (Observer-only)."""
    sess = get_session()
    source = str(getattr(sess, "_geo_overlay_source", "LIVE") or "LIVE").upper()
    if source == "SAVED" and isinstance(getattr(sess, "_geo_saved_overlay", None), dict):
        saved = sess._geo_saved_overlay
        return {
            "accepted": True,
            "static_version": int(getattr(sess, "_geo_static_version", 1) or 1),
            "empirical_version": int((saved or {}).get("empirical_version") or 0),
            "runtime_generation": int(getattr(sess, "_runtime_generation", 0) or 0),
            "geo_source": "SAVED",
            "provenance": getattr(sess, "_geo_saved_provenance", None),
            "traversability": saved,
        }
    published = getattr(sess, "_geo_overlay_published", None)
    if isinstance(published, dict) and published.get("status") in {"AVAILABLE", "LIVE_GEO_UNAVAILABLE"}:
        with sess._lock:
            prov = sess._geo_world_provenance_locked()
        return {
            "accepted": True,
            "static_version": int(getattr(sess, "_geo_static_version", 1) or 1),
            "empirical_version": int(published.get("empirical_version") or 0),
            "runtime_generation": int(getattr(sess, "_runtime_generation", 0) or 0),
            "geo_source": "LIVE",
            "provenance": published.get("provenance") or prov,
            "traversability": published,
        }
    # Force rebuild outside step lock
    payload = sess._refresh_geo_overlay_outside_lock(detail="full")
    with sess._lock:
        prov = sess._geo_world_provenance_locked()
    if isinstance(payload, dict):
        payload = dict(payload)
        payload["provenance"] = prov
        payload["geo_source"] = "LIVE"
        if int(payload.get("n_observations") or 0) <= 0:
            payload["status"] = "LIVE_GEO_UNAVAILABLE"
    return {
        "accepted": bool(payload),
        "static_version": int(getattr(sess, "_geo_static_version", 1) or 1),
        "empirical_version": int((payload or {}).get("empirical_version") or 0),
        "runtime_generation": int(getattr(sess, "_runtime_generation", 0) or 0),
        "geo_source": "LIVE",
        "provenance": prov,
        "traversability": payload,
    }


@app.get("/api/geometry/flow-overlay")
def geometry_flow_overlay(stride: int = 2) -> dict[str, Any]:
    """Observer-only downsampled planet flow vectors (ground truth)."""
    from mechanistic_mind.ui.psy_observer_web.geometry.ground_truth import flow_vector_grid

    sess = get_session()
    with sess._step_lock:
        return flow_vector_grid(sess.runtime, stride=max(1, min(8, int(stride))))


class GeometryFilterBody(BaseModel):
    agent_filter: str = "ALL"


class LiveInterpretersBody(BaseModel):
    geometry: bool | None = None
    signal_context: bool | None = None


@app.post("/api/geometry/agent-filter")
def geometry_agent_filter(body: GeometryFilterBody) -> dict[str, Any]:
    """Set Observer-only empirical overlay agent filter (does not affect cognition)."""
    return get_session().set_geometry_agent_filter(body.agent_filter)


@app.post("/api/observer/live-interpreters")
def observer_live_interpreters(body: LiveInterpretersBody) -> dict[str, Any]:
    """Enable/disable LIVE GEO/SIGINT processing for performance isolation."""
    return get_session().set_live_interpreters(
        geometry=body.geometry,
        signal_context=body.signal_context,
    )


@app.post("/api/geometry/hydrate/{run_id}")
def geometry_hydrate(run_id: str, max_rows: int | None = 80000) -> dict[str, Any]:
    """Load SAVED GEO overlay from a run timeline (does not replace LIVE accumulators)."""
    return get_session().geometry_hydrate_from_run(run_id, max_rows=max_rows)


@app.post("/api/geometry/use-live")
def geometry_use_live() -> dict[str, Any]:
    """Switch WORLD empirical display to current LIVE runtime GEO."""
    return get_session().geometry_use_live()


@app.post("/api/geometry/clear-saved")
def geometry_clear_saved() -> dict[str, Any]:
    """Clear SAVED GEO overlay and return to LIVE."""
    return get_session().geometry_clear_saved()


@app.get("/api/geometry/cell")
def geometry_cell(ix: int, iy: int, agent_filter: str | None = None) -> dict[str, Any]:
    """Ground-truth + empirical directional detail for one cell."""
    return get_session().geometry_cell_detail(ix, iy, agent_filter=agent_filter)


@app.get("/api/geometry/run/{run_id}")
def geometry_run_analysis(run_id: str, max_rows: int | None = None) -> dict[str, Any]:
    """Retrospective geometry analysis from a saved run's scientific history."""
    from mechanistic_mind.ui.psy_observer_web.geometry.analyze_run import analyze_scientific_run
    from mechanistic_mind.ui.psy_observer_web.run_finalize import default_results_root
    from mechanistic_mind.ui.psy_observer_web.scientific_history import published_run_dir

    sess = get_session()
    root = Path(sess.config.results_root) if getattr(sess.config, "results_root", None) else default_results_root()
    run_dir = published_run_dir(root, run_id)
    if not run_dir.is_dir():
        return {"accepted": False, "error": "run not found", "run_id": run_id}
    try:
        # Cap default analysis to keep API responsive.
        cap = int(max_rows) if max_rows is not None else 50_000
        return {
            "accepted": True,
            **analyze_scientific_run(run_dir, run_id=run_id, max_timeline_rows=cap),
        }
    except FileNotFoundError as exc:
        return {"accepted": False, "error": str(exc), "run_id": run_id}


@app.get("/api/signal-context/live")
def signal_context_live() -> dict[str, Any]:
    """Bounded LIVE signal-episode summary (Observer-only)."""
    frame = get_session().current_frame()
    sci = (frame or {}).get("signal_context_interpretation")
    if isinstance(sci, dict):
        return sci
    return get_session().signal_context_live_summary()


@app.get("/api/signal-context/episode/{episode_id}")
def signal_context_episode(episode_id: str) -> dict[str, Any]:
    return get_session().signal_episode_inspect(episode_id)


@app.get("/api/signal-context/current")
def signal_context_current_analysis(
    max_timeline_rows: int | None = 50000,
    max_events: int | None = 200000,
    max_episode_details: int = 40,
    cutoff_tick: int | None = None,
) -> dict[str, Any]:
    """Signal Forensics for the CURRENT RUN scientific evidence package.

    User-triggered only — not wired to LIVE Observer refresh.
    """
    try:
        return get_session().signal_forensics_current_run(
            cutoff_tick=cutoff_tick,
            max_timeline_rows=max_timeline_rows,
            max_events=max_events,
            max_episode_details=int(max_episode_details),
        )
    except FileNotFoundError as exc:
        return {"accepted": False, "error": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return {"accepted": False, "error": str(exc)}


@app.get("/api/signal-context/run/{run_id}")
def signal_context_run_analysis(
    run_id: str,
    max_timeline_rows: int | None = 20000,
    max_events: int | None = 120000,
    max_episode_details: int = 40,
    reference: bool = False,
) -> dict[str, Any]:
    """Retrospective signal-context analysis of a SAVED or REFERENCE run.

    Not the primary current-run path. Set reference=true for fixture labeling.
    """
    from mechanistic_mind.ui.psy_observer_web.run_finalize import default_results_root
    from mechanistic_mind.ui.psy_observer_web.scientific_history import published_run_dir
    from mechanistic_mind.ui.psy_observer_web.signal_context.analyze_run import analyze_signal_run

    sess = get_session()
    root = Path(sess.config.results_root) if getattr(sess.config, "results_root", None) else default_results_root()
    run_dir = published_run_dir(root, run_id)
    if not run_dir.is_dir():
        return {"accepted": False, "error": "run not found", "run_id": run_id}
    try:
        # No hardcoded focus_ticks — those biased UI toward t687 of seed-17 fixture.
        result = analyze_signal_run(
            run_dir,
            run_id=run_id,
            max_timeline_rows=max_timeline_rows,
            max_events=max_events,
            max_episode_details=int(max_episode_details),
            focus_ticks=None,
            source_label="REFERENCE_FIXTURE" if reference else "SAVED_RUN",
        )
        return {"accepted": True, **result}
    except FileNotFoundError as exc:
        return {"accepted": False, "error": str(exc), "run_id": run_id}


@app.get("/api/signal-context/interventions")
def signal_context_interventions_list() -> dict[str, Any]:
    """List completed SIGINT-02 offline intervention experiment dirs (Observer-only)."""
    from mechanistic_mind.ui.psy_observer_web.run_finalize import default_results_root

    sess = get_session()
    root = Path(sess.config.results_root) if getattr(sess.config, "results_root", None) else default_results_root()
    base = root / "signal_context_interpreter"
    if not base.is_dir():
        # also check repo results/
        base = Path(__file__).resolve().parents[3] / "results" / "signal_context_interpreter"
    items = []
    if base.is_dir():
        for d in sorted(base.glob("beta2_sigint_02_*"), reverse=True):
            if not d.is_dir():
                continue
            report = d / "report.json"
            meta = {"id": d.name, "path": str(d)}
            if report.is_file():
                try:
                    meta["report"] = json.loads(report.read_text(encoding="utf-8"))
                except Exception:
                    meta["report"] = None
            items.append(meta)
    return {"accepted": True, "experiments": items, "note": "Offline artifacts only — not live injection."}


@app.get("/api/signal-context/interventions/{experiment_id}")
def signal_context_intervention_detail(experiment_id: str) -> dict[str, Any]:
    """Load one SIGINT-02 experiment summary for Observer inspection."""
    from mechanistic_mind.ui.psy_observer_web.run_finalize import default_results_root

    sess = get_session()
    root = Path(sess.config.results_root) if getattr(sess.config, "results_root", None) else default_results_root()
    candidates = [
        root / "signal_context_interpreter" / experiment_id,
        Path(__file__).resolve().parents[3] / "results" / "signal_context_interpreter" / experiment_id,
    ]
    d = next((p for p in candidates if p.is_dir()), None)
    if d is None:
        return {"accepted": False, "error": "experiment not found", "experiment_id": experiment_id}

    def _load(name: str):
        p = d / name
        if not p.is_file():
            return None
        if name.endswith(".jsonl"):
            rows = []
            with p.open(encoding="utf-8") as f:
                for i, line in enumerate(f):
                    if i >= 200:
                        break
                    if line.strip():
                        rows.append(json.loads(line))
            return rows
        return json.loads(p.read_text(encoding="utf-8"))

    return {
        "accepted": True,
        "experiment_id": experiment_id,
        "report": _load("report.json"),
        "replication": _load("replication.json"),
        "dose_response": _load("dose_response.json"),
        "channel_specificity": _load("channel_specificity.json"),
        "temporal_specificity": _load("temporal_specificity.json"),
        "context_dependence": _load("context_dependence.json"),
        "first_divergence": _load("first_divergence.jsonl"),
        "branch_results_sample": _load("branch_results.jsonl"),
        "candidate_patterns_md": (d / "candidate_patterns.md").read_text(encoding="utf-8")
        if (d / "candidate_patterns.md").is_file()
        else None,
        "honesty": {
            "not_live_injection": True,
            "not_communication": True,
            "observer_only": True,
        },
    }


class SpecimenSaveBody(BaseModel):
    event: dict[str, Any] = Field(default_factory=dict)


class SpecimenReplayBody(BaseModel):
    specimen_id: str
    target: str = "PEER"  # SELF | PEER | LOCATION
    mode: str = "EXACT"  # EXACT | ALTER_AMPLITUDE | ALTER_CHANNEL | DELAY
    amplitude_scale: float = 1.0


@app.get("/api/signal-context/specimens")
def signal_specimens_list(channel: str | None = None, limit: int = 64) -> dict[str, Any]:
    """Bounded natural signal specimen library (Observer-only)."""
    return get_session().list_signal_specimens(channel=channel, limit=max(1, min(256, int(limit))))


@app.post("/api/signal-context/specimens/save")
def signal_specimen_save(body: SpecimenSaveBody) -> dict[str, Any]:
    """SAVE AS SIGNAL SPECIMEN from an emission event."""
    return get_session().save_signal_specimen_from_event(body.event)


@app.post("/api/signal-context/specimens/replay")
def signal_specimen_replay(body: SpecimenReplayBody) -> dict[str, Any]:
    """↻ REPLAY SIGNAL — LIVE uncontrolled; causal claims require matched branching."""
    return get_session().replay_signal_specimen_live(
        body.specimen_id,
        target=body.target,
        mode=body.mode,
        amplitude_scale=body.amplitude_scale,
    )


@app.get("/api/signal-context/repertoire")
def signal_repertoire_list(filter: str = "ALL", limit: int = 64) -> dict[str, Any]:
    """SIGINT-04 natural signal repertoire browser (on-demand, bounded)."""
    return get_session().list_signal_repertoire(
        filter_name=filter, limit=max(1, min(256, int(limit))),
    )


class EpisodeReplayBody(BaseModel):
    episode: dict[str, Any] = Field(default_factory=dict)
    mode: str = "FULL"  # FULL | A_TO_B_ONLY | B_TO_A_ONLY | SHUFFLED | REVERSED


@app.get("/api/signal-context/episodes")
def signal_interaction_episodes(limit: int = 32) -> dict[str, Any]:
    """SIGINT-05 interaction episode browser (on-demand)."""
    return get_session().list_interaction_episodes(limit=max(1, min(64, int(limit))))


@app.post("/api/signal-context/episodes/replay")
def signal_interaction_episode_replay(body: EpisodeReplayBody) -> dict[str, Any]:
    """LIVE uncontrolled episode replay — matched branching required for causal claims."""
    return get_session().replay_interaction_episode_live(body.episode, mode=body.mode)


@app.get("/api/signal-context/forensics")
def signal_cognitive_forensics(limit: int = 8) -> dict[str, Any]:
    """SIGINT-06 cognitive divergence forensics (on-demand)."""
    return get_session().list_cognitive_forensics(limit=max(1, min(16, int(limit))))


@app.post("/api/diagnostics/action-trace")
def diagnostics_action_trace(body: ActionTraceBody) -> dict[str, Any]:
    return get_session().set_action_trace(enabled=body.enabled, mode=body.mode)

class _Hub:
    def __init__(self) -> None:
        self.clients: set[WebSocket] = set()
        self.busy: set[WebSocket] = set()
        self.last_text: str | None = None
        self._pending: str | None = None
        self._flushing = False

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.clients.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self.clients.discard(ws)
        self.busy.discard(ws)

    def offer_text(self, text: str, loop: asyncio.AbstractEventLoop, *, retain_as_last: bool = True) -> None:
        """Keep only the latest serialized payload; never block the sim thread.

        Heartbeats must pass retain_as_last=False so reconnect still gets a real frame.
        """
        if retain_as_last:
            self.last_text = text
        self._pending = text
        if not self._flushing:
            self._flushing = True
            asyncio.run_coroutine_threadsafe(self.flush(), loop)

    async def _send_one(self, ws: WebSocket, text: str) -> None:
        try:
            await asyncio.wait_for(ws.send_text(text), timeout=0.4)
        except Exception:
            self.disconnect(ws)
        finally:
            self.busy.discard(ws)

    async def flush(self) -> None:
        try:
            while self._pending is not None:
                text = self._pending
                self._pending = None
                for ws in list(self.clients):
                    if ws in self.busy:
                        continue
                    self.busy.add(ws)
                    asyncio.create_task(self._send_one(ws, text))
                await asyncio.sleep(0)
        finally:
            self._flushing = False
            if self._pending is not None:
                self._flushing = True
                asyncio.create_task(self.flush())


hub = _Hub()
_loop: asyncio.AbstractEventLoop | None = None


@app.on_event("startup")
async def _startup() -> None:
    global _loop
    _loop = asyncio.get_running_loop()
    sess = get_session()

    def _on_frame(frame: dict[str, Any]) -> None:
        if _loop is None:
            return
        # Prefer pre-serialized JSON produced on the capture worker (not SIM).
        cached = sess.published_json()
        if cached is not None:
            hub.offer_text('{"type":"frame","data":' + cached + "}", _loop)
            return

        def _serialize_and_offer() -> None:
            try:
                text = json.dumps({"type": "frame", "data": frame}, default=str)
            except TypeError:
                return
            if _loop is not None:
                hub.offer_text(text, _loop)

        _loop.run_in_executor(None, _serialize_and_offer)

    def _on_heartbeat(hb: dict[str, Any]) -> None:
        if _loop is None:
            return
        try:
            text = json.dumps({"type": "heartbeat", "data": hb}, default=str)
        except TypeError:
            return
        hub.offer_text(text, _loop, retain_as_last=False)

    sess.subscribe(_on_frame)
    sess.subscribe_heartbeat(_on_heartbeat)


@app.on_event("shutdown")
def _shutdown() -> None:
    try:
        sess = get_session()
        if sess.status in {"RUNNING", "PAUSED", "SAVE_FAILED"} and int(sess.runtime.tick) > 0:
            if sess._finalize_key is None:
                sess.stop(save=True, reason="INTERRUPTED")
            else:
                sess.stop(save=False, reason="INTERRUPTED")
        else:
            sess.stop(save=False, reason="INTERRUPTED")
    except Exception:
        pass


def _serialized_live_frame() -> str:
    return json.dumps({"type": "frame", "data": get_session().current_frame()}, default=str)


@app.get("/api/runtime/progress")
def runtime_progress() -> dict[str, Any]:
    """Cheap RUNNING progress (COMPUTING_TICK vs dead). No frame build."""
    return get_session().runtime_progress()


@app.websocket("/ws/live")
async def ws_live(ws: WebSocket) -> None:
    await hub.connect(ws)
    try:
        text = hub.last_text
        if text is None:
            loop = asyncio.get_running_loop()
            text = await loop.run_in_executor(None, _serialized_live_frame)
            hub.last_text = text
        await asyncio.wait_for(ws.send_text(text), timeout=0.4)
        while True:
            try:
                await asyncio.wait_for(ws.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                await asyncio.wait_for(ws.send_text('{"type":"ping"}'), timeout=0.4)
    except WebSocketDisconnect:
        hub.disconnect(ws)
    except Exception:
        hub.disconnect(ws)


@app.get("/api/action-realization/live")
def action_realization_live() -> dict[str, Any]:
    frame = get_session().current_frame()
    return frame.get("action_realization") or {"status": "EMPTY"}


@app.get("/api/action-realization/history")
def action_realization_history(agent_id: str | None = None, limit: int = 48) -> dict[str, Any]:
    return get_session().action_realization_history(agent_id=agent_id, limit=limit)


@app.get("/api/work-ecology/live")
def work_ecology_live() -> dict[str, Any]:
    frame = get_session().current_frame()
    return frame.get("work_ecology") or {"status": "EMPTY"}


@app.get("/api/work-ecology/history")
def work_ecology_history(agent_id: str | None = None, limit: int = 48) -> dict[str, Any]:
    return get_session().work_ecology_history(agent_id=agent_id, limit=limit)


class ExperimenterMobilityBody(BaseModel):
    mode: str = "ORDINARY_WORK"


@app.post("/api/experimenter/mobility")
def experimenter_mobility(body: ExperimenterMobilityBody) -> dict[str, Any]:
    return get_session().experimenter_set_mobility(body.mode)


class ExperimenterSpawnBody(BaseModel):
    x: float | None = None
    y: float | None = None
    theta: float = 0.0
    near_agent: int | None = None
    run_id: str | None = None


class ExperimenterCommandBody(BaseModel):
    kind: str = "ACTION"
    action: str | None = None
    amplitude: float | None = None
    specimen_id: str | None = None
    run_id: str | None = None


class ExperimenterTargetBody(BaseModel):
    agent_id: str | None = None


class ExperimenterTestBody(BaseModel):
    capture_id: str
    horizon: int = 40


@app.get("/api/experimenter/status")
def experimenter_status() -> dict[str, Any]:
    return get_session().experimenter_status()


@app.post("/api/experimenter/spawn")
def experimenter_spawn(body: ExperimenterSpawnBody | None = None) -> dict[str, Any]:
    b = body or ExperimenterSpawnBody()
    return get_session().experimenter_spawn(
        x=b.x,
        y=b.y,
        theta=float(b.theta or 0.0),
        near_agent=b.near_agent,
        run_id=b.run_id,
    )


@app.post("/api/experimenter/remove")
def experimenter_remove() -> dict[str, Any]:
    return get_session().experimenter_remove()


@app.post("/api/experimenter/command")
def experimenter_command(body: ExperimenterCommandBody) -> dict[str, Any]:
    return get_session().experimenter_command(
        kind=str(body.kind or "ACTION"),
        action=body.action,
        amplitude=body.amplitude,
        specimen_id=body.specimen_id,
        run_id=body.run_id,
    )


@app.post("/api/experimenter/target")
def experimenter_target(body: ExperimenterTargetBody | None = None) -> dict[str, Any]:
    b = body or ExperimenterTargetBody()
    return get_session().experimenter_set_target(b.agent_id)


@app.post("/api/experimenter/capture")
def experimenter_capture() -> dict[str, Any]:
    return get_session().experimenter_capture()


@app.get("/api/experimenter/captures")
def experimenter_captures() -> dict[str, Any]:
    return get_session().experimenter_list_captures()


@app.post("/api/experimenter/test")
def experimenter_test(body: ExperimenterTestBody) -> dict[str, Any]:
    return get_session().experimenter_test_capture(
        str(body.capture_id or ""),
        horizon=int(body.horizon or 40),
    )


if WEB_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(WEB_DIST / "index.html")

    @app.get("/{path:path}")
    def spa_fallback(path: str) -> FileResponse:
        candidate = WEB_DIST / path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(WEB_DIST / "index.html")
