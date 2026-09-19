#!/usr/bin/env python3
"""First-run bootstrap for Psy Observer Web (publication / Public Beta 1).

Creates `.venv_psy_web` and installs `requirements-observer.txt` when needed.
Uses only the Python standard library so it can run before the venv exists.

Usage:
  python3 scripts/bootstrap_psy_observer_env.py --root /path/to/project
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import venv
from pathlib import Path

MIN_MAJOR, MIN_MINOR = 3, 11
MARKER_NAME = ".mm_observer_env_ok"
REQ_NAME = "requirements-observer.txt"


class BootstrapError(Exception):
    pass


def log(msg: str) -> None:
    print(msg, flush=True)


def require_python_version(executable: str | None = None) -> None:
    if executable is None:
        major, minor = sys.version_info[:2]
        label = sys.executable
    else:
        out = subprocess.run(
            [executable, "-c", "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        if out.returncode != 0:
            raise BootstrapError(f"Could not query Python version for {executable}.")
        parts = (out.stdout or "").strip().split(".")
        major, minor = int(parts[0]), int(parts[1])
        label = executable
    if (major, minor) < (MIN_MAJOR, MIN_MINOR):
        raise BootstrapError(
            f"Python {MIN_MAJOR}.{MIN_MINOR}+ is required (found {major}.{minor} at {label}).\n"
            "Install a current Python from https://www.python.org/downloads/ "
            "or your OS package manager, then run Psy Observer again."
        )


def venv_python(root: Path) -> Path:
    if os.name == "nt":
        return root / ".venv_psy_web" / "Scripts" / "python.exe"
    return root / ".venv_psy_web" / "bin" / "python"


def marker_path(root: Path) -> Path:
    return root / ".venv_psy_web" / MARKER_NAME


def requirements_path(root: Path) -> Path:
    return root / REQ_NAME


def env_ready(root: Path) -> bool:
    py = venv_python(root)
    if not py.is_file():
        return False
    probe = subprocess.run(
        [
            str(py),
            "-c",
            "import fastapi, uvicorn, numpy, pydantic\n"
            "from mechanistic_mind.ui.psy_observer_web import launcher\n",
        ],
        cwd=str(root),
        env={**os.environ, "PYTHONPATH": str(root)},
        capture_output=True,
        text=True,
        timeout=40,
        check=False,
    )
    if probe.returncode != 0:
        return False
    marker = marker_path(root)
    req = requirements_path(root)
    if not marker.is_file() or not req.is_file():
        return False
    try:
        return marker.read_text(encoding="utf-8").strip() == req.read_text(encoding="utf-8").strip()
    except OSError:
        return False


def create_venv(root: Path) -> Path:
    dest = root / ".venv_psy_web"
    log(f"Creating virtual environment at {dest} …")
    builder = venv.EnvBuilder(with_pip=True, clear=False, upgrade_deps=False)
    if not dest.exists():
        builder.create(dest)
    py = venv_python(root)
    if not py.is_file():
        # Recreate if incomplete
        builder = venv.EnvBuilder(with_pip=True, clear=True, upgrade_deps=False)
        builder.create(dest)
    if not py.is_file():
        raise BootstrapError(f"Virtual environment was created but Python is missing: {py}")
    return py


def pip_install(py: Path, root: Path) -> None:
    req = requirements_path(root)
    if not req.is_file():
        raise BootstrapError(f"Missing {REQ_NAME} in project root.")
    log("Upgrading pip …")
    r = subprocess.run(
        [str(py), "-m", "pip", "install", "--upgrade", "pip"],
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    if r.returncode != 0:
        raise BootstrapError(
            "Failed to upgrade pip inside .venv_psy_web.\n"
            + ((r.stderr or r.stdout or "")[-1200:])
        )
    log(f"Installing dependencies from {REQ_NAME} …")
    log("(This may take a few minutes on first launch.)")
    r = subprocess.run(
        [str(py), "-m", "pip", "install", "-r", str(req)],
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    if r.returncode != 0:
        raise BootstrapError(
            "Failed to install Observer dependencies.\n"
            "Check your network connection and try again.\n"
            + ((r.stderr or r.stdout or "")[-1600:])
        )
    marker_path(root).write_text(req.read_text(encoding="utf-8"), encoding="utf-8")
    log("Dependency installation complete.")


def ensure_environment(root: Path) -> Path:
    root = root.resolve()
    require_python_version()
    if env_ready(root):
        log("Psy Observer environment is ready.")
        return venv_python(root)
    log("Preparing Psy Observer for first launch.")
    log("This may take a few minutes.")
    py = create_venv(root)
    pip_install(py, root)
    if not env_ready(root):
        raise BootstrapError(
            "Environment was created but required packages still cannot be imported.\n"
            "See .psy_observer/launcher.log for details."
        )
    log("First-run setup finished.")
    return py


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bootstrap Psy Observer Web Python environment")
    parser.add_argument("--root", type=Path, required=True, help="project root")
    parser.add_argument("--check-only", action="store_true", help="exit 0 if ready, 1 otherwise")
    args = parser.parse_args(argv)
    root = args.root.expanduser().resolve()
    try:
        if args.check_only:
            return 0 if env_ready(root) else 1
        ensure_environment(root)
        return 0
    except BootstrapError as exc:
        print(f"\nPsy Observer could not prepare its Python environment.\n\n{exc}\n", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 — surface unexpected bootstrap failures
        print(f"\nUnexpected bootstrap failure: {exc}\n", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
