"""Psy Observer local application lifecycle.

Launcher → localhost FastAPI → built React SPA → PhysicalSystemRuntime.

This module is the packaging boundary for Linux one-click, and later
desktop-entry / AppImage / .app / Windows wrappers.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import traceback
import urllib.error
import urllib.request
import uuid
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .instance_lifecycle import (
    ENV_PACKAGE_IDENTITY,
    ENV_SHUTDOWN_TOKEN,
    ENV_SUPERVISOR_PID,
    ENV_SUPERVISOR_STARTTIME,
    LOCK_SCHEMA as LOCK_SCHEMA_V2,
    application_window_argv,
    atomic_write_restricted,
    chrome_executable,
    linux_pdeathsig_preexec,
    new_ownership_token,
    package_identity,
    pid_cmdline,
    pid_matches_record,
    pid_starttime,
    profile_dir_for,
    raise_existing_window,
    spawn_application_window,
)

APP_NAME = "Psy Observer"  # health / protocol identity (stable)
APP_DISPLAY_NAME = "MM Observer"
WINDOW_TITLE = "Mechanistic Mind Observer — Acanthostega Beta 4.0"
APP_MODEL = "Mechanistic Mind · Acanthostega Beta 4.0"
PREFERRED_PORT = 8768
HOST = "127.0.0.1"
LOCK_SCHEMA = LOCK_SCHEMA_V2
LOCK_SCHEMA_LEGACY = "psy.observer.instance.v1"
HEALTH_TIMEOUT_S = 30.0
STATE_DIRNAME = ".psy_observer"  # legacy install-local; packaged uses XDG
LOG_MAX_BYTES = 2_000_000

# Set by the owning launcher for the child server process.
ENV_INSTANCE_ID = "PSY_OBSERVER_INSTANCE_ID"
ENV_PROJECT_ROOT = "PSY_OBSERVER_PROJECT_ROOT"


class LaunchError(Exception):
    """Human-readable startup failure."""


def project_root(start: Path | None = None) -> Path:
    """Resolve the repository root from this file or an explicit start path."""
    if start is not None:
        cur = start.resolve()
        if cur.is_file():
            cur = cur.parent
        for _ in range(8):
            if (cur / "mechanistic_mind").is_dir() and (cur / "PsyObserver").exists():
                return cur
            if cur.parent == cur:
                break
            cur = cur.parent
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "mechanistic_mind").is_dir() and (
            (parent / "PsyObserver").exists() or (parent / "mechanistic_mind" / "physical_system").is_dir()
        ):
            return parent
    raise LaunchError("Could not find the Psy Observer project directory.")


def _packaged_install(root: Path) -> bool:
    return (root / "runtime" / "python" / "bin").is_dir() or os.environ.get(
        "PSY_OBSERVER_PACKAGED", ""
    ).strip() in {"1", "true", "yes"}


def state_dir(root: Path) -> Path:
    """Launcher locks/logs: XDG state when packaged; else install-local legacy dir."""
    if _packaged_install(root) or os.environ.get("PSY_OBSERVER_STATE_DIR"):
        from .xdg_paths import state_dir as xdg_state

        return xdg_state() / "launcher"
    return root / STATE_DIRNAME


def lock_path(root: Path) -> Path:
    return state_dir(root) / "instance.json"


def log_path(root: Path) -> Path:
    return state_dir(root) / "launcher.log"


def spa_index(root: Path) -> Path:
    return root / "mechanistic_mind" / "ui" / "psy_observer_web" / "web_dist" / "index.html"


def icon_path(root: Path) -> Path | None:
    for rel in (
        "packaging/psy_observer/icons/mm-observer-256.png",
        "packaging/psy_observer/icons/mm-observer-128.png",
        "packaging/psy_observer/icons/mm-observer.svg",
    ):
        p = root / rel
        if p.is_file():
            return p
    return None


def log(root: Path, message: str) -> None:
    d = state_dir(root)
    d.mkdir(parents=True, exist_ok=True)
    path = log_path(root)
    if path.is_file() and path.stat().st_size > LOG_MAX_BYTES:
        rotated = path.with_suffix(".log.1")
        try:
            if rotated.exists():
                rotated.unlink()
            path.replace(rotated)
        except OSError:
            pass
    line = f"{datetime.now(timezone.utc).isoformat()} {message}\n"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line)


def site_packages_dir(root: Path) -> Path | None:
    lib = root / ".venv_psy_web" / "lib"
    if not lib.is_dir():
        return None
    matches = sorted(lib.glob("python*/site-packages"))
    return matches[-1] if matches else None


def bundled_runtime_python(root: Path) -> Path | None:
    bin_dir = root / "runtime" / "python" / "bin"
    for name in ("python3.12", "python3", "python"):
        p = bin_dir / name
        if _python_looks_runnable(p):
            return p
    return None


def runtime_pythonpath(root: Path) -> str:
    parts = [str(root.resolve())]
    sp = site_packages_dir(root)
    if sp is not None:
        parts.append(str(sp.resolve()))
    return os.pathsep.join(parts)


def apply_packaged_env(root: Path, env: dict[str, str] | None = None) -> dict[str, str]:
    out = dict(env or os.environ)
    out["PSY_OBSERVER_PROJECT_ROOT"] = str(root.resolve())
    out["PYTHONPATH"] = runtime_pythonpath(root)
    out["PYTHONNOUSERSITE"] = "1"
    out.pop("PYTHONHOME", None)
    if _packaged_install(root):
        out["PSY_OBSERVER_PACKAGED"] = "1"
        from .xdg_paths import cache_dir, config_dir, data_dir, ensure_user_dirs, state_dir as xdg_state

        ensure_user_dirs()
        out.setdefault("PSY_OBSERVER_CONFIG_DIR", str(config_dir()))
        out.setdefault("PSY_OBSERVER_DATA_DIR", str(data_dir()))
        out.setdefault("PSY_OBSERVER_CACHE_DIR", str(cache_dir()))
        out.setdefault("PSY_OBSERVER_STATE_DIR", str(xdg_state()))
        out.setdefault("PSY_OBSERVER_RESULTS_ROOT", str(data_dir() / "results"))
        out["PSY_OBSERVER_SKIP_BOOTSTRAP"] = "1"
    return out


def python_candidates(root: Path) -> list[Path]:
    """Prefer bundled runtime + site-packages; never require system Python when packaged."""
    names: list[Path] = []
    env = os.environ.get("PSY_OBSERVER_PYTHON")
    if env:
        names.append(Path(env))
    bundled = bundled_runtime_python(root)
    if bundled is not None:
        names.append(bundled)
    names.extend([
        root / ".venv_psy_web" / "bin" / "python",
        root / ".venv_psy_web" / "bin" / "python3",
        root / ".venv_psy_web" / "Scripts" / "python.exe",
        root / ".venv_psy_web" / "Scripts" / "python",
        root / ".venv" / "bin" / "python",
        root / ".venv" / "bin" / "python3",
        root / ".venv" / "Scripts" / "python.exe",
        root / ".venv" / "Scripts" / "python",
    ])
    # System interpreter only for non-packaged developer checkouts.
    if not _packaged_install(root):
        names.append(Path(sys.executable))
    out: list[Path] = []
    seen: set[str] = set()
    for path in names:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        out.append(path)
    return out


def _python_looks_runnable(executable: Path) -> bool:
    if not executable.exists():
        return False
    # Windows: os.X_OK is unreliable for .exe; existence is enough.
    if os.name == "nt" or executable.suffix.lower() in {".exe", ".bat", ".cmd"}:
        return True
    return os.access(executable, os.X_OK)


def verify_python(executable: Path) -> tuple[bool, str]:
    if not _python_looks_runnable(executable):
        return False, "not executable"
    try:
        proc = subprocess.run(
            [
                str(executable), "-c",
                "import fastapi, uvicorn; import mechanistic_mind.physical_system; "
                "import mechanistic_mind.ui.psy_observer_web.server",
            ],
            cwd=str(executable.parents[2] if ".venv" in str(executable) else Path.cwd()),
            capture_output=True, text=True, timeout=20,
            env={**os.environ, "PYTHONPATH": str(project_root())},
        )
    except LaunchError:
        proc = subprocess.run(
            [str(executable), "-c", "import fastapi, uvicorn"],
            capture_output=True, text=True, timeout=20,
        )
        if proc.returncode != 0:
            return False, (proc.stderr or proc.stdout or "import failed").strip()
        return True, "ok"
    except Exception as exc:
        return False, str(exc)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "import failed").strip()
        return False, err
    return True, "ok"


def venv_python_path(root: Path) -> Path:
    if os.name == "nt":
        return root / ".venv_psy_web" / "Scripts" / "python.exe"
    return root / ".venv_psy_web" / "bin" / "python"


def ensure_environment(root: Path) -> None:
    """Create `.venv_psy_web` via the canonical bootstrap script when needed.

    Packaged installs ship a ready runtime and never bootstrap or fall back to
    system Python / pip.
    """
    if os.environ.get("PSY_OBSERVER_SKIP_BOOTSTRAP") or _packaged_install(root):
        return
    override = os.environ.get("PSY_OBSERVER_PYTHON")
    if override:
        p = Path(override)
        if p.exists() and _python_looks_runnable(p):
            return
    venv_py = venv_python_path(root)
    ok, _reason = _can_import_observer(venv_py, root)
    if ok:
        return
    script = root / "scripts" / "bootstrap_psy_observer_env.py"
    if not script.is_file():
        raise LaunchError(
            "Python environment missing. Psy Observer needs .venv_psy_web, "
            "and scripts/bootstrap_psy_observer_env.py is not present."
        )
    print("Preparing Psy Observer environment", flush=True)
    print("Creating Python environment and installing dependencies if needed.", flush=True)
    print("This may take a few minutes on first launch (network required).", flush=True)
    log(root, "bootstrap starting")
    proc = subprocess.run(
        [sys.executable, str(script), "--root", str(root)],
        cwd=str(root),
        check=False,
    )
    if proc.returncode != 0:
        raise LaunchError(
            "First-run setup failed while creating .venv_psy_web or installing "
            "dependencies.\n"
            f"See {log_path(root)}\n"
            "Typical causes: no network, blocked pip, or Python older than 3.11.\n"
            "Fix the cause and run Psy Observer again. You do not need to create "
            "the virtual environment by hand."
        )
    log(root, "bootstrap finished")


def locate_python(root: Path) -> Path:
    tried: list[str] = []
    for cand in python_candidates(root):
        ok, reason = _can_import_observer(cand, root)
        if ok:
            return cand
        tried.append(f"{cand}: {reason}")
    if _packaged_install(root):
        raise LaunchError(
            f"{APP_DISPLAY_NAME} could not start: the bundled Python runtime is "
            "missing or incomplete. Re-extract the release archive.\n"
            + (tried[0] if tried else "")
        )
    if not any(p.exists() for p in python_candidates(root)[:4]):
        raise LaunchError(
            "Python environment missing after bootstrap. Psy Observer needs "
            f".venv_psy_web. See README.md and {log_path(root)}."
        )
    detail = tried[0] if tried else "unknown"
    if "ModuleNotFoundError" in detail or "import" in detail.lower():
        raise LaunchError(
            "Required packages are missing (FastAPI, uvicorn, or the Mechanistic Mind "
            f"runtime). The Python environment is incomplete.\n{detail}"
        )
    raise LaunchError(
        "Psy Observer failed to start. The scientific runtime could not be imported.\n"
        f"{detail}"
    )


def _can_import_observer(executable: Path, root: Path) -> tuple[bool, str]:
    if not executable.exists():
        return False, "missing"
    if not _python_looks_runnable(executable):
        return False, "not executable"
    env = apply_packaged_env(root)
    try:
        proc = subprocess.run(
            [
                str(executable), "-c",
                "import fastapi, uvicorn\n"
                "from mechanistic_mind.physical_system import PhysicalSystemRuntime\n"
                "from mechanistic_mind.ui.psy_observer_web.server import app",
            ],
            cwd=str(root),
            capture_output=True, text=True, timeout=25, env=env,
        )
    except Exception as exc:
        return False, str(exc)
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout or "import failed").strip()[:400]
    return True, "ok"


def verify_spa(root: Path) -> Path:
    index = spa_index(root)
    if not index.is_file():
        raise LaunchError(
            "The Observer interface is not built yet (missing production web files). "
            "A developer needs to build the React SPA before Psy Observer can open."
        )
    return index


def quarantine_lock(root: Path) -> None:
    path = lock_path(root)
    if not path.is_file():
        return
    dest = path.with_name("instance.json.stale")
    try:
        if dest.exists():
            dest.unlink()
        path.replace(dest)
    except OSError:
        try:
            path.unlink()
        except OSError:
            pass


def read_lock(root: Path) -> dict[str, Any] | None:
    path = lock_path(root)
    if not path.is_file():
        return None
    if path.is_symlink():
        quarantine_lock(root)
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        quarantine_lock(root)
        return None
    if not isinstance(data, dict):
        quarantine_lock(root)
        return None
    return data


def write_lock(root: Path, payload: dict[str, Any]) -> None:
    state_dir(root).mkdir(parents=True, exist_ok=True)
    atomic_write_restricted(lock_path(root), payload)


def clear_lock(root: Path) -> None:
    path = lock_path(root)
    try:
        path.unlink(missing_ok=True)
    except TypeError:
        if path.exists():
            path.unlink()
    bak = path.with_suffix(".json.tmp")
    if bak.exists():
        bak.unlink()


def pid_alive(pid: int | None) -> bool:
    if not pid or int(pid) <= 0:
        return False
    try:
        os.kill(int(pid), 0)
    except OSError:
        return False
    return True


def probe_health(url: str, timeout: float = 1.5) -> dict[str, Any] | None:
    target = url.rstrip("/") + "/api/health"
    try:
        with urllib.request.urlopen(target, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode() or "{}")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    return payload if isinstance(payload, dict) else None


def is_our_health(
    payload: dict[str, Any] | None,
    instance_id: str | None = None,
    package_id: str | None = None,
) -> bool:
    if not payload or not payload.get("ok"):
        return False
    if payload.get("app") != APP_NAME:
        return False
    # Both single- and two-agent Current MM runtimes are Psy Observer Web.
    if payload.get("runtime") not in {"PhysicalSystemRuntime", "TwoAgentRuntime"}:
        return False
    if instance_id and payload.get("instance_id") != instance_id:
        return False
    if package_id and payload.get("package_identity") and payload.get("package_identity") != package_id:
        return False
    return True


def port_in_use(port: int, host: str = HOST) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        return sock.connect_ex((host, int(port))) == 0


def choose_port(preferred: int = PREFERRED_PORT, host: str = HOST) -> int:
    for port in range(int(preferred), int(preferred) + 32):
        if not port_in_use(port, host):
            return port
    raise LaunchError("Could not find a free local port for Psy Observer.")


def instance_url(port: int, host: str = HOST) -> str:
    return f"http://{host}:{int(port)}/"


def _owned_server_alive(lock: dict[str, Any]) -> bool:
    return pid_matches_record(
        lock.get("server_pid"),
        starttime=lock.get("server_starttime"),
        cmdline_needle="psy_observer_web",
    )


def _owned_owner_alive(lock: dict[str, Any]) -> bool:
    return pid_matches_record(
        lock.get("owner_pid"),
        starttime=lock.get("owner_starttime"),
    )


def recover_stale_lock(root: Path) -> str:
    """Clear or quarantine lock metadata that does not identify a live owned instance.

    Never kills a process from metadata alone.
    """
    lock = read_lock(root)
    if not lock:
        return "none"
    url = lock.get("url")
    token = lock.get("instance_id")
    health = probe_health(str(url)) if url else None
    ident = package_identity(root)
    if is_our_health(health, str(token) if token else None) and (
        not health.get("package_identity") or health.get("package_identity") == ident
    ):
        if _owned_owner_alive(lock) or _owned_server_alive(lock):
            return "live"
    if _owned_owner_alive(lock) or _owned_server_alive(lock):
        return "owned_unhealthy"
    # Dead PIDs / PID reuse: metadata only.
    quarantine_lock(root)
    log(root, "quarantined stale instance metadata (no verified live owner)")
    return "stale_cleared"


def foreign_healthy_instance(root: Path) -> dict[str, Any] | None:
    """A live MM Observer whose package identity is not this installation."""
    lock = read_lock(root)
    if not lock:
        return None
    url = lock.get("url")
    if not url:
        return None
    health = probe_health(str(url))
    if not is_our_health(health, str(lock.get("instance_id") or "") or None):
        return None
    ident = package_identity(root)
    hid = (health or {}).get("package_identity") or lock.get("package_identity")
    if hid and hid != ident:
        lock["health"] = health
        lock["cross_version"] = True
        return lock
    return None


def loopback_foreign_mm(root: Path, preferred: int = PREFERRED_PORT) -> list[dict[str, Any]]:
    """Detect other MM Observer package identities on loopback. Never kills them."""
    ident = package_identity(root)
    found: list[dict[str, Any]] = []
    for port in range(int(preferred), int(preferred) + 32):
        if not port_in_use(port):
            continue
        url = instance_url(port)
        health = probe_health(url, timeout=0.25)
        if not health or not health.get("ok"):
            continue
        if health.get("app") != APP_NAME:
            continue
        hid = health.get("package_identity")
        if hid and hid != ident:
            found.append({
                "port": port,
                "url": url,
                "package_identity": hid,
                "instance_id": health.get("instance_id"),
            })
    return found


def warn_older_instance_running(foreign: list[dict[str, Any]]) -> None:
    if not foreign:
        return
    ports = ", ".join(str(row.get("port")) for row in foreign)
    text = (
        "An older MM Observer instance is still running.\n\n"
        f"Detected package identity on port(s) {ports}.\n"
        "This launch will not attach to it. A new instance will use another port."
    )
    log(project_root(), text.replace("\n", " "))
    if os.environ.get("PSY_OBSERVER_NO_GUI", "").strip() in {"1", "true", "yes"}:
        return
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        return
    try:
        subprocess.Popen(
            ["zenity", "--warning", "--title", APP_DISPLAY_NAME, "--text", text, "--no-wrap"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def existing_healthy(root: Path) -> dict[str, Any] | None:
    lock = read_lock(root)
    if not lock:
        return None
    url = lock.get("url")
    token = lock.get("instance_id")
    if not url:
        return None
    health = probe_health(str(url))
    ident = package_identity(root)
    if is_our_health(health, str(token) if token else None):
        hid = (health or {}).get("package_identity") or lock.get("package_identity")
        if hid and hid != ident:
            return None
        if _packaged_install(root) and not hid:
            # Legacy orphan without package identity: do not attach a new package to it.
            return None
        lock["health"] = health
        return lock
    owner = lock.get("owner_pid")
    server = lock.get("server_pid")
    if _owned_owner_alive(lock) or _owned_server_alive(lock):
        return None
    if pid_alive(owner) or pid_alive(server):
        # Alive PID that does not match recorded identity — PID reuse; do not kill.
        return None
    clear_lock(root)
    return None


def wait_for_health(url: str, instance_id: str, timeout: float = HEALTH_TIMEOUT_S) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last = "no response"
    while time.monotonic() < deadline:
        payload = probe_health(url, timeout=1.0)
        if is_our_health(payload, instance_id):
            return payload or {}
        if payload:
            last = f"unexpected health {payload}"
        time.sleep(0.1)
    raise LaunchError(
        "Psy Observer started but did not become ready. "
        f"The health check failed ({last}). See the launcher log for details."
    )


def open_browser(url: str) -> None:
    try:
        webbrowser.open(url, new=2)
        return
    except Exception:
        pass
    # Platform fallbacks if webbrowser fails.
    fallbacks: list[tuple[str, ...]] = [
        ("xdg-open", url),
        ("gio", "open", url),
        ("open", url),  # macOS
    ]
    if os.name == "nt":
        fallbacks.insert(0, ("cmd", "/c", "start", "", url))
    for cmd in fallbacks:
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        except Exception:
            continue
    raise LaunchError("Psy Observer is running, but the browser could not be opened.")


def request_stop(url: str, timeout: float = 2.0) -> None:
    req = urllib.request.Request(url.rstrip("/") + "/api/control/stop", method="POST", data=b"")
    try:
        urllib.request.urlopen(req, timeout=timeout).read()
    except Exception:
        pass


def request_instance_shutdown(url: str, token: str | None, timeout: float = 5.0) -> bool:
    if not token:
        return False
    req = urllib.request.Request(
        url.rstrip("/") + "/api/instance/shutdown",
        data=b"{}",
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-MM-Shutdown-Token": str(token),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return int(getattr(resp, "status", 200)) < 400
    except Exception:
        return False


def pids_listening_on_port(port: int) -> list[int]:
    """Best-effort PIDs bound to a TCP port (for owned-instance teardown)."""
    port_i = int(port)
    pids: list[int] = []
    if os.name == "nt":
        try:
            out = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True, text=True, timeout=5, check=False,
            ).stdout or ""
        except Exception:
            return []
        needle = f":{port_i}"
        for line in out.splitlines():
            if "LISTENING" not in line.upper() and "LISTEN" not in line.upper():
                continue
            if needle not in line:
                continue
            parts = line.split()
            if not parts:
                continue
            try:
                pids.append(int(parts[-1]))
            except ValueError:
                continue
        return sorted(set(pids))
    try:
        out = subprocess.run(
            ["ss", "-lptn", f"sport = :{port_i}"],
            capture_output=True, text=True, timeout=3, check=False,
        ).stdout or ""
    except Exception:
        out = ""
    import re
    for match in re.findall(r"pid=(\d+)", out):
        try:
            pids.append(int(match))
        except ValueError:
            continue
    return sorted(set(pids))


def terminate_pid(pid: int | None, timeout: float = 4.0) -> None:
    if not pid_alive(pid):
        return
    assert pid is not None
    pid_i = int(pid)
    if os.name == "nt":
        # Windows: SIGKILL is not a reliable process teardown path.
        subprocess.run(
            ["taskkill", "/PID", str(pid_i), "/T", "/F"],
            capture_output=True,
            check=False,
        )
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline and pid_alive(pid_i):
            time.sleep(0.05)
        return
    try:
        os.kill(pid_i, signal.SIGTERM)
    except OSError:
        return
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and pid_alive(pid_i):
        time.sleep(0.05)
    if pid_alive(pid_i):
        try:
            os.kill(pid_i, signal.SIGKILL)
        except OSError:
            pass


def shutdown_owned(root: Path, lock: dict[str, Any] | None = None) -> None:
    lock = lock or read_lock(root) or {}
    if lock:
        lock = dict(lock)
        lock["shutting_down"] = True
        try:
            write_lock(root, {k: v for k, v in lock.items() if k != "health"})
        except Exception:
            pass
    url = lock.get("url")
    token = lock.get("shutdown_token")
    instance_id = lock.get("instance_id")
    if url and token:
        request_instance_shutdown(str(url), str(token))
    elif url:
        request_stop(str(url))
    deadline = time.monotonic() + 6.0
    while time.monotonic() < deadline and _owned_server_alive(lock):
        time.sleep(0.08)
    if _owned_server_alive(lock):
        terminate_pid(lock.get("server_pid"))
    if pid_matches_record(lock.get("window_pid"), starttime=lock.get("window_starttime")):
        terminate_pid(lock.get("window_pid"))
    owner = lock.get("owner_pid")
    if owner and int(owner) != os.getpid() and _owned_owner_alive(lock):
        terminate_pid(owner)
    profile = lock.get("window_profile")
    if profile:
        try:
            shutil.rmtree(profile, ignore_errors=True)
        except Exception:
            pass
    # Port occupancy is not ownership. Never kill listeners solely by port.
    if url and is_our_health(probe_health(str(url)), str(instance_id) if instance_id else None):
        deadline = time.monotonic() + 1.5
        while time.monotonic() < deadline and is_our_health(probe_health(str(url))):
            time.sleep(0.05)
    port = lock.get("port")
    if port:
        deadline = time.monotonic() + 4.0
        while time.monotonic() < deadline and port_in_use(int(port)):
            if not is_our_health(probe_health(str(url) if url else instance_url(int(port))), str(instance_id) if instance_id else None):
                break
            time.sleep(0.05)
    clear_lock(root)
    log(root, "shutdown complete")


def show_error(message: str, root: Path | None = None) -> None:
    log_hint = ""
    if root is not None:
        log(root, f"ERROR {message}")
        log_hint = f"\n\nDiagnostic log:\n{log_path(root)}"
    text = (
        f"{APP_DISPLAY_NAME} could not start.\n\n{message}{log_hint}\n\n"
        f"Version {APP_MODEL}"
    )
    print(text, file=sys.stderr)
    if os.environ.get("PSY_OBSERVER_NO_GUI", "").strip() in {"1", "true", "yes"}:
        return
    if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
        for cmd in (
            ["zenity", "--error", "--title", APP_DISPLAY_NAME, "--text", text, "--no-wrap"],
            ["kdialog", "--error", text],
        ):
            try:
                subprocess.run(cmd, check=False, timeout=20)
                return
            except Exception:
                continue
        try:
            import tkinter as tk
            from tkinter import messagebox

            win = tk.Tk()
            win.withdraw()
            messagebox.showerror(APP_DISPLAY_NAME, text)
            win.destroy()
            return
        except Exception:
            pass
        try:
            subprocess.run(["notify-send", APP_DISPLAY_NAME, message], check=False, timeout=8)
        except Exception:
            pass


def show_closing_state() -> Callable[[], None]:
    """Non-blocking 'Closing MM Observer…' dialog. Returns a closer."""
    if os.environ.get("PSY_OBSERVER_NO_GUI", "").strip() in {"1", "true", "yes"}:
        return lambda: None
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        return lambda: None
    try:
        proc = subprocess.Popen(
            [
                "zenity",
                "--info",
                "--title",
                APP_DISPLAY_NAME,
                "--text",
                "Closing MM Observer…",
                "--no-wrap",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        def _close() -> None:
            if proc.poll() is None:
                proc.terminate()

        return _close
    except Exception:
        return lambda: None


def _start_server(
    root: Path,
    python: Path,
    port: int,
    instance_id: str,
    shutdown_token: str,
) -> subprocess.Popen[Any]:
    env = apply_packaged_env(root)
    env[ENV_INSTANCE_ID] = instance_id
    env[ENV_SHUTDOWN_TOKEN] = shutdown_token
    env[ENV_PACKAGE_IDENTITY] = package_identity(root)
    env[ENV_PROJECT_ROOT] = str(root)
    env[ENV_SUPERVISOR_PID] = str(os.getpid())
    st = pid_starttime(os.getpid())
    if st:
        env[ENV_SUPERVISOR_STARTTIME] = st
    log_file = log_path(root).open("a", encoding="utf-8")
    log_file.write(f"\n--- server start {datetime.now(timezone.utc).isoformat()} port={port} ---\n")
    log_file.flush()
    return subprocess.Popen(
        [
            str(python), "-m", "uvicorn",
            "mechanistic_mind.ui.psy_observer_web.server:app",
            "--host", HOST,
            "--port", str(port),
            "--log-level", "info",
        ],
        cwd=str(root),
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        start_new_session=False,
        preexec_fn=linux_pdeathsig_preexec if os.name == "posix" else None,
    )


def _ownership_window(url: str, on_quit: Callable[[], None], *, root: Path | None = None) -> bool:
    try:
        import tkinter as tk
    except Exception:
        return False
    try:
        win = tk.Tk()
    except Exception:
        return False
    win.title(WINDOW_TITLE)
    win.geometry("480x200")
    win.resizable(False, False)
    ico = icon_path(root) if root is not None else None
    if ico is not None:
        try:
            from tkinter import PhotoImage

            img = PhotoImage(file=str(ico))
            win.iconphoto(True, img)
            win._mm_icon = img  # noqa: SLF001 — keep reference
        except Exception:
            pass
    tk.Label(win, text=APP_DISPLAY_NAME, font=("sans-serif", 16, "bold")).pack(pady=(16, 4))
    tk.Label(
        win,
        text=f"{WINDOW_TITLE}\nClosing the browser will not stop the experiment.",
        justify="center",
    ).pack(pady=4)
    bar = tk.Frame(win)
    bar.pack(pady=16)

    def quit_app() -> None:
        on_quit()
        win.destroy()

    tk.Button(bar, text="Open in browser", command=lambda: open_browser(url)).pack(side="left", padx=6)
    tk.Button(bar, text=f"Quit {APP_DISPLAY_NAME}", command=quit_app).pack(side="left", padx=6)
    win.protocol("WM_DELETE_WINDOW", quit_app)
    win.mainloop()
    return True


def launch(
    *,
    root: Path | None = None,
    preferred_port: int = PREFERRED_PORT,
    open_ui: bool = True,
    ownership_ui: bool = True,
    wait: bool = True,
) -> dict[str, Any]:
    t0 = time.monotonic()
    root = (root or project_root()).resolve()
    # Do not leak packaged flags (SKIP_BOOTSTRAP, PACKAGED) into this interpreter;
    # they belong on the child server process only.
    os.environ["PSY_OBSERVER_PROJECT_ROOT"] = str(root)
    os.environ["PYTHONPATH"] = apply_packaged_env(root).get("PYTHONPATH", os.environ.get("PYTHONPATH", ""))
    os.environ["PYTHONNOUSERSITE"] = "1"
    state_dir(root).mkdir(parents=True, exist_ok=True)
    log(root, f"launch requested cwd={Path.cwd()} root={root} packaged={_packaged_install(root)}")

    recover_stale_lock(root)
    others = loopback_foreign_mm(root, preferred_port)
    foreign_lock = foreign_healthy_instance(root)
    if others or foreign_lock:
        rows = list(others)
        if foreign_lock and not any(int(r.get("port") or 0) == int(foreign_lock.get("port") or 0) for r in rows):
            rows.append({
                "port": foreign_lock.get("port"),
                "url": foreign_lock.get("url"),
                "package_identity": foreign_lock.get("package_identity"),
                "instance_id": foreign_lock.get("instance_id"),
            })
        warn_older_instance_running(rows)
        # Never attach to a foreign package; choose_port skips busy listeners.
    existing = existing_healthy(root)
    if existing:
        url = str(existing["url"])
        log(root, f"reusing healthy instance {url}")
        if open_ui:
            if not raise_existing_window():
                show_error(
                    "MM Observer is already running.\n\n"
                    "Its window should be visible in your session. "
                    "This launch did not start a second server.",
                    root,
                )
        existing["reused"] = True
        existing["startup_s"] = time.monotonic() - t0
        return existing

    verify_spa(root)
    ensure_environment(root)
    python = locate_python(root)
    port = choose_port(preferred_port)
    instance_id = uuid.uuid4().hex
    shutdown_token = new_ownership_token()
    url = instance_url(port)
    child = _start_server(root, python, port, instance_id, shutdown_token)
    from .xdg_paths import runtime_dir

    ident = package_identity(root)
    lock = {
        "schema": LOCK_SCHEMA,
        "app": APP_NAME,
        "display_name": APP_DISPLAY_NAME,
        "model": APP_MODEL,
        "instance_id": instance_id,
        "shutdown_token": shutdown_token,
        "package_identity": ident,
        "install_root": str(root),
        "owner_pid": os.getpid(),
        "owner_starttime": pid_starttime(os.getpid()),
        "server_pid": child.pid,
        "server_starttime": pid_starttime(child.pid),
        "host": HOST,
        "port": port,
        "url": url,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "python": str(python),
        "state_dir": str(state_dir(root)),
        "window_kind": "chromium_app_mode",
        "shutting_down": False,
    }
    write_lock(root, lock)
    log(root, f"started server pid={child.pid} port={port} id={instance_id}")

    try:
        health = wait_for_health(url, instance_id)
    except Exception:
        terminate_pid(child.pid)
        clear_lock(root)
        raise LaunchError(
            "The local MM Observer server started but did not become ready. "
            "No application window was opened."
        )

    lock["health"] = health
    lock["startup_s"] = time.monotonic() - t0
    write_lock(root, {k: v for k, v in lock.items() if k != "health"})
    log(root, f"healthy in {lock['startup_s']:.3f}s url={url}")

    window_proc: subprocess.Popen[Any] | None = None
    if open_ui:
        chrome = chrome_executable()
        if chrome is None:
            terminate_pid(child.pid)
            clear_lock(root)
            raise LaunchError(
                "The application window engine is unavailable. "
                "Install Google Chrome or Chromium, then launch MM Observer again."
            )
        profile = profile_dir_for(instance_id, runtime_dir())
        try:
            window_proc = spawn_application_window(url=url, profile_dir=profile, chrome=chrome)
        except Exception as exc:
            terminate_pid(child.pid)
            clear_lock(root)
            raise LaunchError(f"Could not open the MM Observer application window.\n{exc}") from exc
        lock["window_pid"] = window_proc.pid
        lock["window_starttime"] = pid_starttime(window_proc.pid)
        lock["window_profile"] = str(profile)
        lock["window_argv_app"] = True
        write_lock(root, {k: v for k, v in lock.items() if k != "health"})
        log(root, f"application window pid={window_proc.pid}")

    if not wait:
        lock["reused"] = False
        return lock

    stopping = {"done": False}

    def cleanup(*_args: Any) -> None:
        if stopping["done"]:
            return
        stopping["done"] = True
        closer = show_closing_state()
        try:
            shutdown_owned(root, lock)
            if window_proc is not None and window_proc.poll() is None:
                try:
                    window_proc.terminate()
                    window_proc.wait(timeout=4)
                except Exception:
                    if window_proc.poll() is None:
                        window_proc.kill()
        finally:
            closer()

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)
    try:
        print(f"{APP_DISPLAY_NAME} is running.")
        print(WINDOW_TITLE)
        while not stopping["done"]:
            if window_proc is not None and window_proc.poll() is not None:
                break
            if not pid_alive(child.pid):
                break
            time.sleep(0.25)
    finally:
        cleanup()
    lock["reused"] = False
    return lock


def quit_existing(root: Path | None = None) -> int:
    root = (root or project_root()).resolve()
    lock = read_lock(root)
    if not lock:
        print(f"{APP_NAME} is not running.")
        return 0
    shutdown_owned(root, lock)
    print(f"{APP_NAME} stopped.")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=f"{APP_NAME} local launcher")
    parser.add_argument("--quit", action="store_true", help="shut down the owned Observer")
    parser.add_argument("--no-browser", action="store_true", help="do not open the browser")
    parser.add_argument("--no-window", action="store_true", help="do not open the ownership window")
    parser.add_argument("--no-wait", action="store_true", help="start and return (tests)")
    parser.add_argument("--port", type=int, default=PREFERRED_PORT)
    parser.add_argument("--root", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        root = args.root.resolve() if args.root else project_root()
        if args.quit:
            return quit_existing(root)
        launch(
            root=root,
            preferred_port=args.port,
            open_ui=not args.no_browser,
            ownership_ui=not args.no_window,
            wait=not args.no_wait,
        )
        return 0
    except LaunchError as exc:
        root = None
        try:
            root = args.root.resolve() if args.root else project_root()
        except Exception:
            pass
        show_error(str(exc), root)
        return 1
    except Exception as exc:
        root = None
        try:
            root = project_root()
        except Exception:
            pass
        show_error(f"Unexpected launcher failure: {exc}\n{traceback.format_exc()}", root)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
