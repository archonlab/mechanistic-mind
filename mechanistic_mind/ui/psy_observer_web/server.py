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


class SpeedBody(BaseModel):
    speed: float = 1.0


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
    return get_session().stop(save=save, reason=reason)


@app.get("/api/control/stop-info")
def control_stop_info() -> dict[str, Any]:
    return get_session().stop_info()


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
def get_mechanisms() -> dict[str, Any]:
    """CURRENT INTEGRATED MM mechanism registry + live toggles."""
    from mechanistic_mind.physical_system.mechanism_registry import RUNTIME_VERSION
    from mechanistic_mind.physical_system.structured_events import EVENT_SCHEMA
    rt = getattr(get_session(), "runtime", None)
    if rt is None:
        return {"error": "no runtime", "model": RUNTIME_VERSION}
    snap = rt.mechanisms()
    return {
        "model": "MM 1.0 — Tiktaalik",
        "runtime_version": snap.get("runtime_version"),
        "mechanisms": snap.get("mechanisms"),
        "enabled": snap.get("enabled"),
        "disabled": snap.get("disabled"),
        "force_contributions": getattr(rt, "last_force_contributions", None),
        "events_schema": EVENT_SCHEMA,
    }


class MechanismToggleBody(BaseModel):
    enabled: bool


@app.post("/api/mechanisms/{mechanism_id}")
def post_mechanism(mechanism_id: str, body: MechanismToggleBody) -> dict[str, Any]:
    return get_session().set_mechanism(mechanism_id, bool(body.enabled))


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
    import json
    root = Path(__file__).resolve().parents[3]
    out = []
    for p in sorted((root / "results").glob("mm_*")):
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
            "files": len(list(p.iterdir())),
        })
    return {
        "status": "CATALOG_ONLY",
        "analyzer": "NOT_AVAILABLE",
        "packs": out,
    }


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

    ui_timeline = []
    st = run_dir / "session_timeline.jsonl"
    if st.is_file():
        for line in st.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                ui_timeline.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    ui_events = []
    se = run_dir / "structured_events.json"
    if se.is_file():
        try:
            payload = json.loads(se.read_text(encoding="utf-8"))
            ui_events = list(payload.get("events") or [])
        except Exception:
            pass

    cut = cutoff_tick
    if cut is None and manifest.get("final_tick") is not None:
        cut = int(manifest["final_tick"])

    pkg = load_evidence_package(
        evidence_dir=run_dir,
        runtime=None,
        ui_timeline=ui_timeline,
        ui_events=ui_events,
        cutoff_tick=cut,
        runtime_status="STOPPED",
        run_id=rid,
        identity=identity,
    )
    pkg["source"] = "saved"
    pkg["run_dir"] = str(run_dir)
    pkg["manifest"] = {
        "final_tick": manifest.get("final_tick"),
        "seed": manifest.get("seed"),
        "runtime_type": manifest.get("runtime_type"),
        "termination_reason": manifest.get("termination_reason"),
        "scientific_history": manifest.get("scientific_history"),
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

    def offer_text(self, text: str, loop: asyncio.AbstractEventLoop) -> None:
        """Keep only the latest serialized frame; never block the sim thread."""
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

    sess.subscribe(_on_frame)


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
