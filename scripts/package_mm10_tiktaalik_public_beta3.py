#!/usr/bin/env python3
"""Build Release/MM-1.0-Tiktaalik-Public-Beta-3 from the development tree.

Does not mutate scientific sources except files already present. Destination
only. GIT_PUSH is never performed.
"""
from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
from pathlib import Path

SRC = Path(__file__).resolve().parents[1]
SLUG = "MM-1.0-Tiktaalik-Public-Beta-3"
DEST = SRC / "Release" / SLUG
BETA1 = SRC / "Release" / "MM-1.0-Tiktaalik-Beta1"

SKIP_DIR_NAMES = {
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".git",
    ".venv", ".venv_psy_web", "node_modules", ".psy_observer", ".cursor",
    ".idea", ".vscode", "dist", "build", ".eggs", "htmlcov", "Release",
    "results", "analysis_jobs", "telemetry",
}
SKIP_FILE_SUFFIXES = {".pyc", ".pyo", ".so", ".dylib", ".egg"}
SKIP_FILE_NAMES = {".DS_Store", "Thumbs.db", ".coverage", ".env", ".env.local"}
SKIP_NAME_PREFIXES = (".live-", ".tmp-")
MAX_FILE = 8_000_000  # 8 MiB accidental-dump guard (web_dist JS is smaller)


def chmod_x(path: Path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def should_skip_file(sp: Path) -> bool:
    name = sp.name
    if name in SKIP_FILE_NAMES:
        return True
    if Path(name).suffix in SKIP_FILE_SUFFIXES:
        return True
    if name.endswith(".tar.gz") or name.endswith(".zip"):
        return True
    if name.startswith(SKIP_NAME_PREFIXES):
        return True
    if sp.is_symlink():
        return True
    try:
        sz = sp.stat().st_size
        if "web_dist" in sp.parts:
            if sz > 40_000_000:
                return True
        elif sz > MAX_FILE:
            return True
    except OSError:
        return True
    return False


def copy_filtered(src: Path, dst: Path) -> int:
    n = 0
    if not src.exists():
        return 0
    if src.is_file():
        if should_skip_file(src):
            return 0
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return 1
    for root, dirs, files in os.walk(src):
        root_p = Path(root)
        dirs[:] = [
            d for d in dirs
            if d not in SKIP_DIR_NAMES
            and not d.startswith(".venv")
            and not d.startswith(".live-")
            and not d.startswith(".tmp-")
        ]
        rel = root_p.relative_to(src)
        out_dir = dst / rel
        out_dir.mkdir(parents=True, exist_ok=True)
        for f in files:
            sp = root_p / f
            if should_skip_file(sp):
                continue
            dp = out_dir / f
            shutil.copy2(sp, dp)
            n += 1
    return n


def copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def audit_tree(dest: Path) -> dict:
    findings: list[str] = []
    home_hits = 0
    desktop_hits = 0
    localhost_hits = 0
    secret_hits = 0
    escaped_links: list[str] = []
    dest_r = dest.resolve()
    for p in dest.rglob("*"):
        if p.is_symlink():
            try:
                target = p.resolve()
            except OSError:
                escaped_links.append(str(p))
                continue
            if dest_r not in target.parents and target != dest_r:
                escaped_links.append(f"{p} -> {target}")
            continue
        if not p.is_file():
            continue
        if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".woff", ".woff2", ".ico"}:
            continue
        try:
            if p.stat().st_size > 2_000_000:
                continue
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if "/home/thehost" in text:
            home_hits += 1
            if home_hits <= 25:
                findings.append(f"ABS_PATH {p.relative_to(dest)}")
        if "~/Desktop/psy" in text or "/Desktop/psy" in text:
            desktop_hits += 1
        if "localhost" in text.lower() and p.suffix in {".md", ".py", ".sh", ".json"}:
            localhost_hits += 1
        low = text.lower()
        if any(k in low for k in ("api_key", "begin private", "aws_secret", "sk-")):
            secret_hits += 1
            findings.append(f"SECRET_HINT {p.relative_to(dest)}")
    return {
        "home_thehost_files": home_hits,
        "desktop_psy_files": desktop_hits,
        "localhost_mention_files": localhost_hits,
        "secret_hint_files": secret_hits,
        "escaped_symlinks": escaped_links,
        "sample": findings[:40],
    }


def main() -> int:
    if DEST.exists():
        shutil.rmtree(DEST)
    DEST.mkdir(parents=True)

    counts: dict[str, int] = {}
    counts["mechanistic_mind"] = copy_filtered(SRC / "mechanistic_mind", DEST / "mechanistic_mind")
    counts["web"] = copy_filtered(SRC / "web", DEST / "web")
    counts["configs"] = copy_filtered(SRC / "configs", DEST / "configs")
    counts["docs"] = copy_filtered(SRC / "docs", DEST / "docs")
    counts["knowledge"] = copy_filtered(SRC / "knowledge", DEST / "knowledge")
    counts["worlds"] = copy_filtered(SRC / "worlds", DEST / "worlds")
    counts["mm"] = copy_filtered(SRC / "mm", DEST / "mm")
    counts["packaging"] = copy_filtered(SRC / "packaging", DEST / "packaging")
    counts["tools"] = copy_filtered(SRC / "tools", DEST / "tools")
    counts["tests"] = copy_filtered(SRC / "tests", DEST / "tests")

    exp_dst = DEST / "experiments"
    exp_dst.mkdir()
    n_exp = 0
    if (SRC / "experiments").is_dir():
        for p in (SRC / "experiments").iterdir():
            if p.name.startswith(".") or p.is_dir():
                continue
            if p.suffix == ".py" or (p.suffix in {".md", ".txt"} and p.stat().st_size < 200_000):
                shutil.copy2(p, exp_dst / p.name)
                n_exp += 1
    counts["experiments_py"] = n_exp

    scripts = DEST / "scripts"
    scripts.mkdir()
    copy_file(SRC / "scripts" / "bootstrap_psy_observer_env.py", scripts / "bootstrap_psy_observer_env.py")
    copy_file(SRC / "requirements-observer.txt", DEST / "requirements-observer.txt")
    copy_file(SRC / "pyproject.toml", DEST / "pyproject.toml")
    copy_file(SRC / ".gitignore", DEST / ".gitignore")

    for name in (
        "README.md", "CHANGELOG.md", "KNOWN_LIMITATIONS.md", "RELEASE_NOTES_BETA3.md",
        "PSY_OBSERVER_LAUNCHER.md", "ONTOLOGY_AUDIT.md",
        "LICENSE", "COPYRIGHT", "COMMERCIAL_LICENSING.md",
    ):
        src_p = SRC / name
        if src_p.is_file():
            copy_file(src_p, DEST / name)

    launcher_src = BETA1 if (BETA1 / "launch_psy_observer.sh").is_file() else SRC
    for name in (
        "launch_psy_observer.sh", "launch_psy_observer.command",
        "launch_psy_observer.bat", "launch_psy_observer.cmd", "PsyObserver",
    ):
        src_p = launcher_src / name
        if src_p.is_file():
            copy_file(src_p, DEST / name)
    chmod_x(DEST / "launch_psy_observer.sh")
    chmod_x(DEST / "launch_psy_observer.command")
    chmod_x(DEST / "PsyObserver")
    for sh in (DEST / "launch_psy_observer.sh", DEST / "PsyObserver", DEST / "launch_psy_observer.command"):
        if sh.is_file():
            text = sh.read_text(encoding="utf-8", errors="ignore")
            sh.write_text(text.replace("Beta 1", "Beta 3"), encoding="utf-8")

    (DEST / "results").mkdir()
    (DEST / "results" / ".gitkeep").write_text("", encoding="utf-8")
    (DEST / "results" / "README.md").write_text(
        "# Generated data\n\n"
        "Observer archives are written under `results/psychology_observer/` "
        "relative to this package root. This directory starts empty.\n",
        encoding="utf-8",
    )

    # pyproject observer extras
    pyproj = (DEST / "pyproject.toml").read_text(encoding="utf-8")
    if "observer =" not in pyproj:
        pyproj = pyproj.replace(
            'dev = ["pytest>=8.0"]',
            'dev = ["pytest>=8.0"]\n'
            "observer = [\n"
            '  "fastapi>=0.110",\n'
            '  "uvicorn[standard]>=0.27",\n'
            '  "numpy>=1.26",\n'
            '  "pydantic>=2.0",\n'
            '  "httpx>=0.27",\n'
            "]",
        )
        (DEST / "pyproject.toml").write_text(pyproj, encoding="utf-8")

    audit = audit_tree(DEST)
    (DEST / "release_audit").mkdir(exist_ok=True)
    import json
    (DEST / "release_audit" / "copy_counts.json").write_text(
        json.dumps({"counts": counts, "audit": audit}, indent=2) + "\n", encoding="utf-8"
    )
    print("DEST", DEST)
    print("counts", counts)
    print("audit", {k: audit[k] for k in audit if k != "sample"})
    for line in audit.get("sample") or []:
        print(" ", line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
