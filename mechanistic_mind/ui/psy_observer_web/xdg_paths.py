"""XDG user directories for packaged MM Observer.

Developer checkouts keep writing under the project tree unless
PSY_OBSERVER_PACKAGED=1 or an explicit PSY_OBSERVER_*_DIR override is set.
"""
from __future__ import annotations

import os
from pathlib import Path

APP_ID = "mm-observer"


def _home() -> Path:
    return Path(os.environ.get("HOME") or Path.home()).expanduser()


def xdg_config_home() -> Path:
    raw = os.environ.get("XDG_CONFIG_HOME")
    return Path(raw).expanduser() if raw else (_home() / ".config")


def xdg_data_home() -> Path:
    raw = os.environ.get("XDG_DATA_HOME")
    return Path(raw).expanduser() if raw else (_home() / ".local" / "share")


def xdg_cache_home() -> Path:
    raw = os.environ.get("XDG_CACHE_HOME")
    return Path(raw).expanduser() if raw else (_home() / ".cache")


def xdg_state_home() -> Path:
    raw = os.environ.get("XDG_STATE_HOME")
    return Path(raw).expanduser() if raw else (_home() / ".local" / "state")


def xdg_runtime_home() -> Path:
    raw = os.environ.get("XDG_RUNTIME_DIR")
    if raw:
        return Path(raw)
    return xdg_state_home() / APP_ID / "runtime-fallback"


def runtime_dir() -> Path:
    env = os.environ.get("PSY_OBSERVER_RUNTIME_DIR")
    if env:
        return Path(env).expanduser().resolve()
    return (xdg_runtime_home() / APP_ID).resolve()


def is_packaged_mode() -> bool:
    if os.environ.get("PSY_OBSERVER_PACKAGED", "").strip() in {"1", "true", "yes"}:
        return True
    if os.environ.get("PSY_OBSERVER_DATA_DIR") or os.environ.get("PSY_OBSERVER_STATE_DIR"):
        return True
    return False


def config_dir() -> Path:
    env = os.environ.get("PSY_OBSERVER_CONFIG_DIR")
    if env:
        return Path(env).expanduser().resolve()
    return (xdg_config_home() / APP_ID).resolve()


def data_dir() -> Path:
    env = os.environ.get("PSY_OBSERVER_DATA_DIR")
    if env:
        return Path(env).expanduser().resolve()
    return (xdg_data_home() / APP_ID).resolve()


def cache_dir() -> Path:
    env = os.environ.get("PSY_OBSERVER_CACHE_DIR")
    if env:
        return Path(env).expanduser().resolve()
    return (xdg_cache_home() / APP_ID).resolve()


def state_dir() -> Path:
    env = os.environ.get("PSY_OBSERVER_STATE_DIR")
    if env:
        return Path(env).expanduser().resolve()
    return (xdg_state_home() / APP_ID).resolve()


def results_root(*, project_root: Path | None = None) -> Path:
    """Saved runs / Analyzer persistence root."""
    env = os.environ.get("PSY_OBSERVER_RESULTS_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    if is_packaged_mode():
        return data_dir() / "results"
    if project_root is not None:
        return Path(project_root).resolve() / "results"
    # Lazy import avoided — callers pass project_root when available.
    return data_dir() / "results" if is_packaged_mode() else Path("results")


def ensure_user_dirs() -> dict[str, str]:
    paths = {
        "config": config_dir(),
        "data": data_dir(),
        "cache": cache_dir(),
        "state": state_dir(),
        "results": results_root(),
    }
    for p in paths.values():
        p.mkdir(parents=True, exist_ok=True)
    (paths["results"]).mkdir(parents=True, exist_ok=True)
    (paths["cache"] / "payload").mkdir(parents=True, exist_ok=True)
    (paths["state"] / "logs").mkdir(parents=True, exist_ok=True)
    return {k: str(v) for k, v in paths.items()}
