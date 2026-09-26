"""Crash-safe runtime checkpoints (persistence infrastructure only).

Reuses Save & Stop persist-view: snapshot(persist=True) + dump_persist.
Does not deepcopy cognition. Does not change scientific/cognitive semantics.

Generations:
    <root>/current/   committed known-good
    <root>/previous/  prior known-good
    <root>/tmp/       in-progress write (never the restore source)
"""
from __future__ import annotations

import json
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mechanistic_mind.ui.psy_observer_web.run_finalize import dump_persist

MANIFEST = "checkpoint_manifest.json"
SNAPSHOT = "physical_system_snapshot.json"
CURRENT = "current"
PREVIOUS = "previous"
TMP = "tmp"


def checkpoint_root(base: Path) -> Path:
    return Path(base) / "runtime_checkpoints"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fsync_dir(path: Path) -> None:
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".part")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def read_manifest(gen_dir: Path) -> dict[str, Any] | None:
    p = Path(gen_dir) / MANIFEST
    if not p.is_file():
        return None
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(obj, dict) or obj.get("status") != "COMMITTED":
        return None
    if not (Path(gen_dir) / SNAPSHOT).is_file():
        return None
    return obj


def load_committed(root: Path) -> dict[str, Any] | None:
    """Return current generation if valid, else previous. Never tmp."""
    ck = Path(root)
    if not (ck / CURRENT).is_dir():
        alt = ck / "runtime_checkpoints"
        ck = alt if alt.is_dir() else checkpoint_root(ck)
    for name in (CURRENT, PREVIOUS):
        d = ck / name
        man = read_manifest(d)
        if man:
            return {"dir": str(d), "manifest": man, "snapshot_path": str(d / SNAPSHOT)}
    return None


def write_checkpoint(
    runtime: Any,
    *,
    dest_root: Path,
    run_id: str | None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Pause-safe persist-view dump. Caller must not step runtime during this call."""
    t0 = time.perf_counter()
    dest_root = Path(dest_root)
    ck = checkpoint_root(dest_root)
    ck.mkdir(parents=True, exist_ok=True)
    tmp = ck / TMP
    if tmp.exists():
        shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True, exist_ok=True)

    staging = ck / "staging_new"
    try:
        try:
            snap = runtime.snapshot(persist=True)
        except TypeError:
            snap = runtime.snapshot()
        tick = int(snap.get("tick") or getattr(runtime, "tick", 0) or 0)
        from mechanistic_mind.research import pe_cold_archive as cold

        sidecar = cold.write_open_sidecars(snap, tmp / "pe_open")
        snap_path = tmp / SNAPSHOT
        with snap_path.open("w", encoding="utf-8") as f:
            dump_persist(snap, f, compact=True)
            f.flush()
            os.fsync(f.fileno())
        size = snap_path.stat().st_size
        man = {
            "schema": "mm.observer.crash_checkpoint.v1",
            "status": "COMMITTED",
            "tick": tick,
            "run_id": run_id,
            "runtime_type": type(runtime).__name__,
            "seed": int(getattr(runtime, "seed", 0) or 0),
            "written_at": _utc(),
            "snapshot_bytes": size,
            "open_sidecar_files": sidecar.get("files"),
            "open_sidecar_bytes": sidecar.get("bytes"),
            "note": (
                "Runtime continuation from this tick. Post-checkpoint ticks of a dead "
                "process are a separate branch and must not be merged."
            ),
            **(extra or {}),
        }
        _write_json_atomic(tmp / MANIFEST, man)
        _fsync_dir(tmp)

        current = ck / CURRENT
        previous = ck / PREVIOUS
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        os.rename(tmp, staging)
        if previous.exists():
            shutil.rmtree(previous, ignore_errors=True)
        if current.exists():
            os.rename(current, previous)
        os.rename(staging, current)
        _fsync_dir(ck)
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(staging, ignore_errors=True)
        raise
    wall = time.perf_counter() - t0
    return {
        "accepted": True,
        "tick": tick,
        "dir": str(current),
        "snapshot_bytes": size,
        "snapshot_mb": round(size / (1024 * 1024), 4),
        "wall_s": round(wall, 4),
        "previous_preserved": (ck / PREVIOUS).is_dir() and read_manifest(ck / PREVIOUS) is not None,
        "manifest": man,
    }


def load_snapshot_dict(committed: dict[str, Any]) -> dict[str, Any]:
    path = Path(committed["snapshot_path"])
    with path.open("r", encoding="utf-8") as f:
        obj = json.load(f)
    if not isinstance(obj, dict) or "tick" not in obj:
        raise ValueError("invalid checkpoint snapshot")
    from mechanistic_mind.research import pe_cold_archive as cold

    gen = Path(committed["dir"])
    cold.hydrate_open_sidecars(obj, gen / "pe_open")
    man = committed.get("manifest") or {}
    cold.mark_restore_branch(
        obj,
        checkpoint_tick=int(man.get("tick") or obj.get("tick") or 0),
        previous_run_id=str(man.get("run_id") or "") or None,
    )
    return obj
