"""Authenticated MM Observer instance identity, PID ownership, and app-window spawn.

Launcher is the lifecycle supervisor. This module never treats a busy port as
proof of ownership and never kills a PID from stale metadata alone.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import signal
import shutil
import stat
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LOCK_SCHEMA = "mm.observer.instance.v2"
APP_NAME = "Psy Observer"
APP_DISPLAY_NAME = "MM Observer"
WINDOW_TITLE = "Mechanistic Mind Observer — Acanthostega Beta 4.0"
WINDOW_CLASS = "mm-observer"
HOST = "127.0.0.1"

ENV_INSTANCE_ID = "PSY_OBSERVER_INSTANCE_ID"
ENV_SHUTDOWN_TOKEN = "PSY_OBSERVER_SHUTDOWN_TOKEN"
ENV_PACKAGE_IDENTITY = "PSY_OBSERVER_PACKAGE_IDENTITY"
ENV_SUPERVISOR_PID = "PSY_OBSERVER_SUPERVISOR_PID"
ENV_SUPERVISOR_STARTTIME = "PSY_OBSERVER_SUPERVISOR_STARTTIME"

CHROME_CANDIDATES = (
    "google-chrome-stable",
    "google-chrome",
    "chromium-browser",
    "chromium",
    "microsoft-edge-stable",
    "microsoft-edge",
)


def package_identity(root: Path, version: str = "0.2.0") -> str:
    digest = hashlib.sha256(str(Path(root).resolve()).encode("utf-8")).hexdigest()[:16]
    return f"{version}:{digest}"


def new_ownership_token() -> str:
    return secrets.token_urlsafe(32)


def pid_starttime(pid: int | None) -> str | None:
    if not pid or int(pid) <= 0:
        return None
    proc = Path(f"/proc/{int(pid)}/stat")
    try:
        text = proc.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    rparen = text.rfind(")")
    if rparen < 0:
        return None
    fields = text[rparen + 2 :].split()
    if len(fields) < 20:
        return None
    return fields[19]


def pid_cmdline(pid: int | None) -> str:
    if not pid or int(pid) <= 0:
        return ""
    try:
        raw = Path(f"/proc/{int(pid)}/cmdline").read_bytes()
    except OSError:
        return ""
    return raw.replace(b"\x00", b" ").decode("utf-8", errors="replace").strip()


def pid_alive(pid: int | None) -> bool:
    if not pid or int(pid) <= 0:
        return False
    try:
        os.kill(int(pid), 0)
    except OSError:
        return False
    return True


def pid_matches_record(
    pid: int | None,
    *,
    starttime: str | None,
    cmdline_needle: str | None = None,
) -> bool:
    """True only if PID is alive, starttime matches, and cmdline matches.

    Missing starttime is never treated as ownership (PID reuse protection).
    """
    if not pid_alive(pid):
        return False
    if not starttime:
        return False
    live = pid_starttime(pid)
    if live is None or str(live) != str(starttime):
        return False
    if cmdline_needle:
        cmd = pid_cmdline(pid)
        if cmdline_needle not in cmd:
            return False
    return True


def atomic_write_restricted(path: Path, payload: dict[str, Any]) -> None:
    path = Path(path)
    if path.is_symlink() or path.parent.is_symlink():
        raise OSError("refusing to write instance metadata through a symlink")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass
    tmp = path.with_suffix(path.suffix + ".tmp")
    if tmp.is_symlink():
        tmp.unlink()
    data = json.dumps(payload, indent=2) + "\n"
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        raise
    tmp.replace(path)
    try:
        os.chmod(path, 0o600)
        path.chmod(path.stat().st_mode & ~stat.S_IRWXO & ~stat.S_IRWXG)
    except OSError:
        pass


def chrome_executable() -> Path | None:
    env = os.environ.get("PSY_OBSERVER_CHROME")
    if env and Path(env).is_file() and os.access(env, os.X_OK):
        return Path(env)
    for name in CHROME_CANDIDATES:
        found = shutil.which(name)
        if found:
            return Path(found)
    for p in (
        Path("/usr/bin/google-chrome-stable"),
        Path("/usr/bin/google-chrome"),
        Path("/usr/bin/chromium-browser"),
        Path("/usr/bin/chromium"),
    ):
        if p.is_file() and os.access(p, os.X_OK):
            return p
    return None


def application_window_argv(chrome: Path, url: str, profile_dir: Path) -> list[str]:
    """Dedicated Chromium application-mode window; private profile; no tab chrome."""
    return [
        str(chrome),
        f"--app={url}",
        f"--user-data-dir={profile_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-extensions",
        "--disable-sync",
        "--disable-background-networking",
        "--disable-session-crashed-bubble",
        "--disable-features=TranslateUI,MediaRouter",
        f"--class={WINDOW_CLASS}",
        f"--app-id={WINDOW_CLASS}",
        "--window-size=1440,900",
        "--new-window",
    ]


def profile_dir_for(instance_id: str, runtime_root: Path) -> Path:
    return Path(runtime_root) / "window-profile" / str(instance_id)


def linux_pdeathsig_preexec() -> None:
    """Ask the kernel to SIGTERM this child if the supervisor dies (Linux)."""
    if os.name != "posix":
        return
    try:
        import ctypes

        libc = ctypes.CDLL("libc.so.6", use_errno=True)
        PR_SET_PDEATHSIG = 1
        libc.prctl(PR_SET_PDEATHSIG, int(signal.SIGTERM))
        if os.getppid() == 1:
            os.kill(os.getpid(), signal.SIGTERM)
    except Exception:
        return


def spawn_application_window(
    *,
    url: str,
    profile_dir: Path,
    chrome: Path | None = None,
) -> subprocess.Popen[Any]:
    exe = chrome or chrome_executable()
    if exe is None:
        raise RuntimeError(
            "MM Observer needs a Chromium-based browser (Google Chrome or Chromium) "
            "to open its application window. Install Chrome/Chromium, then launch again."
        )
    profile_dir.mkdir(parents=True, exist_ok=True)
    argv = application_window_argv(exe, url, profile_dir)
    env = dict(os.environ)
    env.setdefault("CHROME_DESKTOP", "mm-observer.desktop")
    return subprocess.Popen(
        argv,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
        start_new_session=False,
        preexec_fn=linux_pdeathsig_preexec if os.name == "posix" else None,
    )


def raise_existing_window() -> bool:
    for cmd in (
        ["wmctrl", "-a", WINDOW_TITLE],
        ["wmctrl", "-xa", WINDOW_CLASS],
        ["xdotool", "search", "--name", WINDOW_TITLE, "windowactivate"],
    ):
        try:
            proc = subprocess.run(cmd, capture_output=True, timeout=3, check=False)
            if proc.returncode == 0:
                return True
        except Exception:
            continue
    return False


def tokens_match(provided: str | None, expected: str | None) -> bool:
    if not provided or not expected:
        return False
    try:
        return hmac.compare_digest(str(provided), str(expected))
    except Exception:
        return False


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_instance_record(
    *,
    root: Path,
    instance_id: str,
    shutdown_token: str,
    owner_pid: int,
    server_pid: int | None,
    port: int,
    url: str,
    python: str,
    state_dir: str,
    window_pid: int | None = None,
    version: str = "0.2.0",
) -> dict[str, Any]:
    ident = package_identity(root, version)
    rec = {
        "schema": LOCK_SCHEMA,
        "app": APP_NAME,
        "display_name": APP_DISPLAY_NAME,
        "window_title": WINDOW_TITLE,
        "model": "Mechanistic Mind · Acanthostega Beta 4.0",
        "instance_id": instance_id,
        "shutdown_token": shutdown_token,
        "package_identity": ident,
        "install_root": str(Path(root).resolve()),
        "owner_pid": int(owner_pid),
        "owner_starttime": pid_starttime(owner_pid),
        "server_pid": int(server_pid) if server_pid else None,
        "server_starttime": pid_starttime(server_pid) if server_pid else None,
        "window_pid": int(window_pid) if window_pid else None,
        "window_starttime": pid_starttime(window_pid) if window_pid else None,
        "host": HOST,
        "port": int(port),
        "url": url,
        "started_at": now_iso(),
        "python": python,
        "state_dir": state_dir,
        "shutting_down": False,
        "window_kind": "chromium_app_mode",
    }
    return rec


def public_health_fields(rec: dict[str, Any] | None) -> dict[str, Any]:
    rec = rec or {}
    return {
        "app": APP_NAME,
        "display_name": APP_DISPLAY_NAME,
        "window_title": WINDOW_TITLE,
        "instance_id": rec.get("instance_id"),
        "package_identity": rec.get("package_identity"),
        "port": rec.get("port"),
        "schema": rec.get("schema"),
        "local": True,
    }
