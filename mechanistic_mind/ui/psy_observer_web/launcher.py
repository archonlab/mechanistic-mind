"""Psy Observer local application lifecycle.

Launcher → localhost FastAPI → built React SPA → PhysicalSystemRuntime.

This module is the packaging boundary for Linux one-click, and later
desktop-entry / AppImage / .app / Windows wrappers.
"""
from __future__ import annotations

import argparse
import json
import os
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

APP_NAME = "Psy Observer"
APP_MODEL = "MM 1.0 — Tiktaalik"
PREFERRED_PORT = 8768
HOST = "127.0.0.1"
LOCK_SCHEMA = "psy.observer.instance.v1"
HEALTH_TIMEOUT_S = 30.0
STATE_DIRNAME = ".psy_observer"

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


def state_dir(root: Path) -> Path:
    return root / STATE_DIRNAME


def lock_path(root: Path) -> Path:
    return state_dir(root) / "instance.json"


def log_path(root: Path) -> Path:
    return state_dir(root) / "launcher.log"


def spa_index(root: Path) -> Path:
    return root / "mechanistic_mind" / "ui" / "psy_observer_web" / "web_dist" / "index.html"


def log(root: Path, message: str) -> None:
    state_dir(root).mkdir(parents=True, exist_ok=True)
    line = f"{datetime.now(timezone.utc).isoformat()} {message}\n"
    with log_path(root).open("a", encoding="utf-8") as fh:
        fh.write(line)


def python_candidates(root: Path) -> list[Path]:
    """Prefer project venvs; support Unix bin/ and Windows Scripts/ layouts."""
    names: list[Path] = []
    env = os.environ.get("PSY_OBSERVER_PYTHON")
    if env:
        names.append(Path(env))
    names.extend([
        root / ".venv_psy_web" / "bin" / "python",
        root / ".venv_psy_web" / "bin" / "python3",
        root / ".venv_psy_web" / "Scripts" / "python.exe",
        root / ".venv_psy_web" / "Scripts" / "python",
        root / ".venv" / "bin" / "python",
        root / ".venv" / "bin" / "python3",
        root / ".venv" / "Scripts" / "python.exe",
        root / ".venv" / "Scripts" / "python",
        Path(sys.executable),
    ])
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


def locate_python(root: Path) -> Path:
    tried: list[str] = []
    for cand in python_candidates(root):
        ok, reason = _can_import_observer(cand, root)
        if ok:
            return cand
        tried.append(f"{cand}: {reason}")
    if not any(p.exists() for p in python_candidates(root)[:4]):
        raise LaunchError(
            "Python environment missing. Psy Observer needs the project "
            "Python environment (.venv_psy_web)."
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
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root)
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


def read_lock(root: Path) -> dict[str, Any] | None:
    path = lock_path(root)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    return data


def write_lock(root: Path, payload: dict[str, Any]) -> None:
    state_dir(root).mkdir(parents=True, exist_ok=True)
    tmp = lock_path(root).with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(lock_path(root))


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


def is_our_health(payload: dict[str, Any] | None, instance_id: str | None = None) -> bool:
    if not payload or not payload.get("ok"):
        return False
    if payload.get("app") != APP_NAME:
        return False
    # Both single- and two-agent Current MM runtimes are Psy Observer Web.
    if payload.get("runtime") not in {"PhysicalSystemRuntime", "TwoAgentRuntime"}:
        return False
    if instance_id and payload.get("instance_id") != instance_id:
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


def existing_healthy(root: Path) -> dict[str, Any] | None:
    lock = read_lock(root)
    if not lock:
        return None
    url = lock.get("url")
    token = lock.get("instance_id")
    if not url:
        return None
    health = probe_health(str(url))
    if is_our_health(health, str(token) if token else None):
        lock["health"] = health
        return lock
    owner = lock.get("owner_pid")
    server = lock.get("server_pid")
    if pid_alive(owner) or pid_alive(server):
        # Process exists but is not a healthy Psy Observer — do not reuse.
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
    url = lock.get("url")
    port = lock.get("port")
    token = lock.get("instance_id")
    if url:
        request_stop(str(url))
    terminate_pid(lock.get("server_pid"))
    owner = lock.get("owner_pid")
    if owner and int(owner) != os.getpid() and pid_alive(owner):
        terminate_pid(owner)
    # If the child outlived the recorded PID (or PID was stale), free our port
    # only when /api/health still identifies Psy Observer on that URL/port.
    if url and is_our_health(probe_health(str(url)), str(token) if token else None):
        for pid in pids_listening_on_port(int(port or 0)):
            terminate_pid(pid)
        # Brief wait; do not kill unrelated occupants.
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and is_our_health(probe_health(str(url))):
            time.sleep(0.05)
    clear_lock(root)
    log(root, "shutdown complete")


def show_error(message: str, root: Path | None = None) -> None:
    text = f"{APP_NAME} could not start.\n\n{message}"
    print(text, file=sys.stderr)
    if root is not None:
        log(root, f"ERROR {message}")
        print(f"\nLog: {log_path(root)}", file=sys.stderr)
    if sys.stdin.isatty():
        return
    for cmd in (
        ["zenity", "--error", "--title", APP_NAME, "--text", text],
        ["kdialog", "--error", text],
        ["notify-send", APP_NAME, message],
    ):
        try:
            subprocess.run(cmd, check=False, timeout=8)
            return
        except Exception:
            continue


def _start_server(root: Path, python: Path, port: int, instance_id: str) -> subprocess.Popen[Any]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root)
    env[ENV_INSTANCE_ID] = instance_id
    env[ENV_PROJECT_ROOT] = str(root)
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
        start_new_session=True,
    )


def _ownership_window(url: str, on_quit: Callable[[], None]) -> bool:
    try:
        import tkinter as tk
    except Exception:
        return False
    try:
        root = tk.Tk()
    except Exception:
        return False
    root.title(APP_NAME)
    root.geometry("420x180")
    root.resizable(False, False)
    tk.Label(root, text=APP_NAME, font=("sans-serif", 16, "bold")).pack(pady=(16, 4))
    tk.Label(
        root,
        text=f"{APP_MODEL} is running locally.\nClosing the browser will not stop the experiment.",
        justify="center",
    ).pack(pady=4)
    bar = tk.Frame(root)
    bar.pack(pady=16)

    def quit_app() -> None:
        on_quit()
        root.destroy()

    tk.Button(bar, text="Open in browser", command=lambda: open_browser(url)).pack(side="left", padx=6)
    tk.Button(bar, text="Quit Psy Observer", command=quit_app).pack(side="left", padx=6)
    root.protocol("WM_DELETE_WINDOW", quit_app)
    root.mainloop()
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
    state_dir(root).mkdir(parents=True, exist_ok=True)
    log(root, f"launch requested cwd={Path.cwd()} root={root}")

    existing = existing_healthy(root)
    if existing:
        url = str(existing["url"])
        log(root, f"reusing healthy instance {url}")
        if open_ui:
            open_browser(url)
        existing["reused"] = True
        existing["startup_s"] = time.monotonic() - t0
        return existing

    verify_spa(root)
    python = locate_python(root)
    port = choose_port(preferred_port)
    instance_id = uuid.uuid4().hex
    url = instance_url(port)
    child = _start_server(root, python, port, instance_id)
    lock = {
        "schema": LOCK_SCHEMA,
        "app": APP_NAME,
        "model": APP_MODEL,
        "instance_id": instance_id,
        "owner_pid": os.getpid(),
        "server_pid": child.pid,
        "host": HOST,
        "port": port,
        "url": url,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "python": str(python),
    }
    write_lock(root, lock)
    log(root, f"started server pid={child.pid} port={port} id={instance_id}")

    try:
        health = wait_for_health(url, instance_id)
    except Exception:
        terminate_pid(child.pid)
        clear_lock(root)
        raise

    lock["health"] = health
    lock["startup_s"] = time.monotonic() - t0
    write_lock(root, {k: v for k, v in lock.items() if k != "health"})
    log(root, f"healthy in {lock['startup_s']:.3f}s url={url}")

    if open_ui:
        open_browser(url)

    if not wait:
        lock["reused"] = False
        return lock

    stopping = {"done": False}

    def cleanup(*_args: Any) -> None:
        if stopping["done"]:
            return
        stopping["done"] = True
        shutdown_owned(root, lock)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)
    try:
        used_window = False
        if ownership_ui and not sys.stdin.isatty():
            used_window = _ownership_window(url, cleanup)
        if not used_window:
            print(f"{APP_NAME} is running.")
            print("Closing the browser will not stop the experiment.")
            print("Press Ctrl+C or run PsyObserver --quit to shut down.")
            while not stopping["done"] and pid_alive(child.pid):
                time.sleep(0.4)
            if not pid_alive(child.pid) and not stopping["done"]:
                clear_lock(root)
    finally:
        cleanup()
    lock["reused"] = False
    return lock


def quit_existing(root: Path | None = None) -> int:
    root = (root or project_root()).resolve()
    lock = read_lock(root)
    if not lock:
        existing = None
        for port in range(PREFERRED_PORT, PREFERRED_PORT + 8):
            url = instance_url(port)
            health = probe_health(url)
            if is_our_health(health):
                existing = {"url": url, "instance_id": (health or {}).get("instance_id")}
                break
        if not existing:
            print(f"{APP_NAME} is not running.")
            return 0
        request_stop(str(existing["url"]))
        print(f"{APP_NAME} stop requested.")
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
