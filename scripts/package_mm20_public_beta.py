#!/usr/bin/env python3
"""Whitelist packager for Mechanistic Mind 2.0 Public Beta 1.

Copies frozen lab science into a clean public tree. Does NOT mutate /psy science.
Identity/banner/docs/path sanitization occur only in the destination.
"""
from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SRC = Path("/home/thehost/Desktop/psy")
TEMPLATE = Path("/home/thehost/Desktop/MM-1.0-Tiktaalik-Public-Beta-1")
DEST = Path("/home/thehost/Desktop/MM-2.0-Tiktaalik-Undercover-Public-Beta-1")
SLUG = "MM-2.0-Tiktaalik-Undercover-Public-Beta-1"

SKIP_DIR_NAMES = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".git",
    ".venv",
    ".venv_psy_web",
    "node_modules",
    ".psy_observer",
    ".cursor",
    ".idea",
    ".vscode",
    "dist",
    "build",
    ".eggs",
    "htmlcov",
}

SKIP_FILE_SUFFIXES = {".pyc", ".pyo", ".so", ".dylib", ".egg"}
SKIP_FILE_NAMES = {".DS_Store", "Thumbs.db", ".coverage", ".env"}


def copy_filtered(src: Path, dst: Path) -> int:
    """Recursive copy skipping caches/venvs. Returns file count."""
    n = 0
    if src.is_file():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return 1
    for root, dirs, files in os.walk(src):
        root_p = Path(root)
        rel = root_p.relative_to(src)
        # prune
        dirs[:] = [d for d in dirs if d not in SKIP_DIR_NAMES and not d.startswith(".venv")]
        out_dir = dst / rel
        out_dir.mkdir(parents=True, exist_ok=True)
        for f in files:
            if f in SKIP_FILE_NAMES:
                continue
            if Path(f).suffix in SKIP_FILE_SUFFIXES:
                continue
            if f.endswith(".tar.gz") or f.endswith(".zip"):
                continue
            sp = root_p / f
            if sp.is_symlink():
                continue
            # skip huge accidental dumps
            try:
                if sp.stat().st_size > 50_000_000:
                    continue
            except OSError:
                continue
            dp = out_dir / f
            shutil.copy2(sp, dp)
            n += 1
    return n


def chmod_x(path: Path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def main() -> None:
    assert SRC.is_dir(), SRC
    assert TEMPLATE.is_dir(), TEMPLATE
    if DEST.exists():
        print("Removing previous DEST", DEST)
        shutil.rmtree(DEST)
    DEST.mkdir(parents=True)

    audit = DEST / "release_audit"
    audit.mkdir()

    # --- whitelist copies ---
    counts = {}

    # Core science + UI (lab frozen)
    counts["mechanistic_mind"] = copy_filtered(SRC / "mechanistic_mind", DEST / "mechanistic_mind")
    counts["web"] = copy_filtered(SRC / "web", DEST / "web")
    counts["configs"] = copy_filtered(SRC / "configs", DEST / "configs")
    counts["docs"] = copy_filtered(SRC / "docs", DEST / "docs")
    counts["knowledge"] = copy_filtered(SRC / "knowledge", DEST / "knowledge")
    counts["worlds"] = copy_filtered(SRC / "worlds", DEST / "worlds")
    counts["mm"] = copy_filtered(SRC / "mm", DEST / "mm")
    counts["packaging"] = copy_filtered(SRC / "packaging", DEST / "packaging")
    counts["tools"] = copy_filtered(SRC / "tools", DEST / "tools")

    # Tests: full lab suite minus caches (public verification)
    counts["tests"] = copy_filtered(SRC / "tests", DEST / "tests")

    # Experiments: curated — exclude result JSON dumps larger strategy: copy .py only + small configs
    exp_dst = DEST / "experiments"
    exp_dst.mkdir()
    n_exp = 0
    for p in (SRC / "experiments").iterdir():
        if p.name.startswith("."):
            continue
        if p.is_dir():
            continue
        if p.suffix == ".py":
            shutil.copy2(p, exp_dst / p.name)
            n_exp += 1
        elif p.suffix in {".md", ".txt"} and p.stat().st_size < 200_000:
            shutil.copy2(p, exp_dst / p.name)
            n_exp += 1
    counts["experiments_py"] = n_exp

    # Bootstrap + requirements from prior public template (lab missing)
    scripts = DEST / "scripts"
    scripts.mkdir()
    shutil.copy2(TEMPLATE / "scripts" / "bootstrap_psy_observer_env.py", scripts / "bootstrap_psy_observer_env.py")
    # keep a few harmless experiment runners from template if useful
    for name in (
        "run_prospective_scenario_competition_experiments.py",
        "run_endogenous_motor_coupling_experiments.py",
        "run_internal_external_transfer_experiments.py",
        "run_causal_gearbox_mapping.py",
    ):
        src_p = TEMPLATE / "scripts" / name
        if src_p.is_file():
            shutil.copy2(src_p, scripts / name)

    shutil.copy2(TEMPLATE / "requirements-observer.txt", DEST / "requirements-observer.txt")
    # Legal from prior public (AGPL already chosen historically — not invented here)
    for legal in ("LICENSE", "COPYRIGHT", "COMMERCIAL_LICENSING.md"):
        shutil.copy2(TEMPLATE / legal, DEST / legal)

    # Launchers from public template (bootstrap-capable), will rebrand below
    for name in (
        "launch_psy_observer.sh",
        "launch_psy_observer.command",
        "launch_psy_observer.bat",
        "launch_psy_observer.cmd",
        "PsyObserver",
    ):
        shutil.copy2(TEMPLATE / name, DEST / name)
    chmod_x(DEST / "launch_psy_observer.sh")
    chmod_x(DEST / "launch_psy_observer.command")
    chmod_x(DEST / "PsyObserver")

    # .gitignore from lab (good) + ensure results ignored
    shutil.copy2(SRC / ".gitignore", DEST / ".gitignore")

    # Empty results placeholder (writable documentation only)
    (DEST / "results").mkdir()
    (DEST / "results" / ".gitkeep").write_text("", encoding="utf-8")
    (DEST / "results" / "README.md").write_text(
        "# Generated data\n\n"
        "Observer run archives and scientific history are written under\n"
        "`results/psychology_observer/` when you Save a run.\n"
        "This directory starts empty in the public package.\n",
        encoding="utf-8",
    )

    # pyproject shaped for observer extras
    (DEST / "pyproject.toml").write_text(
        """[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "mechanistic-mind"
version = "2.0.0"
description = "Mechanistic Mind 2.0 — Tiktaalik: Undercover — Public Beta 1"
readme = "README.md"
requires-python = ">=3.11"
dependencies = []

[project.optional-dependencies]
observer = [
  "fastapi>=0.110",
  "uvicorn[standard]>=0.27",
  "numpy>=1.26",
  "pydantic>=2.0",
  "httpx>=0.27",
]
dev = ["pytest>=8.0"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q -p no:cacheprovider"

[tool.setuptools.packages.find]
include = ["mechanistic_mind*"]
""",
        encoding="utf-8",
    )

    # --- packaging-only identity / banner updates in DEST ---
    identity = DEST / "mechanistic_mind" / "model" / "identity.py"
    text = identity.read_text(encoding="utf-8")
    # Replace header constants carefully
    text = re.sub(
        r'MODEL_VERSION = "1\.0"',
        'MODEL_VERSION = "2.0"',
        text,
        count=1,
    )
    if "RELEASE_EDITION" not in text:
        text = text.replace(
            'MODEL_CODENAME = "Tiktaalik"\n',
            'MODEL_CODENAME = "Tiktaalik"\n'
            '# Public edition / packaging label — does not rename internal mechanisms.\n'
            'RELEASE_EDITION = "Undercover"\n'
            'PUBLIC_RELEASE = "Public Beta 1"\n',
            1,
        )
    else:
        text = re.sub(r'RELEASE_EDITION = "[^"]*"', 'RELEASE_EDITION = "Undercover"', text)
        text = re.sub(r'PUBLIC_RELEASE = "[^"]*"', 'PUBLIC_RELEASE = "Public Beta 1"', text)
    text = re.sub(
        r'RUNTIME_VERSION = "[^"]*"',
        'RUNTIME_VERSION = "MM_2_0_TIKTAALIK_UNDERCOVER"',
        text,
        count=1,
    )
    if "def release_display_name" not in text:
        text = text.replace(
            "def display_name() -> str:\n    return f\"MM {MODEL_VERSION} — {MODEL_CODENAME}\"\n",
            "def display_name() -> str:\n"
            "    \"\"\"Scientific model display (stable identity).\"\"\"\n"
            "    return f\"MM {MODEL_VERSION} — {MODEL_CODENAME}\"\n\n\n"
            "def release_display_name() -> str:\n"
            "    \"\"\"Public packaging banner for Observer / launchers.\"\"\"\n"
            "    return (\n"
            "        f\"MM {MODEL_VERSION} TIKTAALIK | TIKTAALIK: UNDERCOVER | \"\n"
            "        f\"{PUBLIC_RELEASE.upper()}\"\n"
            "    )\n",
            1,
        )
    else:
        text = re.sub(
            r'def release_display_name\(\)[\s\S]*?return \([\s\S]*?\)\n',
            "def release_display_name() -> str:\n"
            "    \"\"\"Public packaging banner for Observer / launchers.\"\"\"\n"
            "    return (\n"
            "        f\"MM {MODEL_VERSION} TIKTAALIK | TIKTAALIK: UNDERCOVER | \"\n"
            "        f\"{PUBLIC_RELEASE.upper()}\"\n"
            "    )\n",
            text,
            count=1,
        )
    # Docstring
    text = text.replace(
        '"""MM 1.0 Tiktaalik identity constants (no runtime imports)."""',
        '"""MM 2.0 Tiktaalik: Undercover identity constants (no runtime imports)."""',
    )
    identity.write_text(text, encoding="utf-8")

    # Export release_display_name from tiktaalik if needed
    tik = DEST / "mechanistic_mind" / "model" / "tiktaalik.py"
    ttxt = tik.read_text(encoding="utf-8")
    if "release_display_name" not in ttxt:
        ttxt = ttxt.replace(
            "    display_name,\n    promotion_class,\n)",
            "    display_name,\n    promotion_class,\n    release_display_name,\n)",
            1,
        )
        # ensure identity import includes it
        if "release_display_name" not in ttxt.split("from .identity import")[1].split(")")[0]:
            ttxt = ttxt.replace(
                "    display_name,\n",
                "    display_name,\n    release_display_name,\n",
                1,
            )
        tik.write_text(ttxt, encoding="utf-8")

    # Re-check identity export in tiktaalik imports
    ttxt = tik.read_text(encoding="utf-8")
    if "release_display_name" not in ttxt:
        raise SystemExit("failed to wire release_display_name into tiktaalik.py")
    # Also add to __all__ style re-exports if model_metadata uses display only — OK

    # Ensure identity exports RELEASE fields used by server in public template
    # Patch launcher APP_MODEL in DEST
    launch_py = DEST / "mechanistic_mind" / "ui" / "psy_observer_web" / "launcher.py"
    lp = launch_py.read_text(encoding="utf-8")
    lp = re.sub(
        r'APP_MODEL = "[^"]*"',
        'APP_MODEL = "MM 2.0 TIKTAALIK | TIKTAALIK: UNDERCOVER | PUBLIC BETA 1"',
        lp,
        count=1,
    )
    launch_py.write_text(lp, encoding="utf-8")

    # Wire server.py to release_display_name like public template if missing
    server = DEST / "mechanistic_mind" / "ui" / "psy_observer_web" / "server.py"
    st = server.read_text(encoding="utf-8")
    if "release_display_name" not in st:
        st = st.replace(
            "from mechanistic_mind.model.tiktaalik import display_name, model_metadata",
            "from mechanistic_mind.model.tiktaalik import display_name, model_metadata, release_display_name",
        )
        # inject release field near model in health/about if pattern exists
        st = st.replace(
            '"model": display_name(),',
            '"model": display_name(),\n        "release": release_display_name(),',
        )
        server.write_text(st, encoding="utf-8")

    # Ensure tiktaalik re-exports release_display_name at module level for server import
    ttxt = tik.read_text(encoding="utf-8")
    if "release_display_name" not in ttxt.split("from .identity import", 1)[1][:400]:
        ttxt = ttxt.replace(
            "from .identity import (",
            "from .identity import (\n    release_display_name,",
            1,
        )
        # may duplicate — clean later if needed
        tik.write_text(ttxt, encoding="utf-8")

    # Sanitize absolute developer paths in analysis helpers (public copy only)
    for rel in (
        "mechanistic_mind/ui/psy_observer_web/signal_context/cognitive_forensics.py",
        "mechanistic_mind/ui/psy_observer_web/signal_context/interaction_episode.py",
    ):
        p = DEST / rel
        t = p.read_text(encoding="utf-8")
        t2 = re.sub(
            r'DEFAULT_SIGINT05 = Path\(\s*"[^"]+"\s*"[^"]+"\s*\)',
            "DEFAULT_SIGINT05 = None  # public package: pass explicit path",
            t,
        )
        t2 = re.sub(
            r'DEFAULT_REF_RUN = Path\(\s*"[^"]+"\s*"[^"]+"\s*\)',
            "DEFAULT_REF_RUN = None  # public package: pass explicit path",
            t2,
        )
        if t2 == t:
            # broader replace of /home/thehost lines
            t2 = t.replace("/home/thehost/Desktop/psy/", "")
        p.write_text(t2, encoding="utf-8")

    # Fix loaders that assume DEFAULT is Path
    cf = DEST / "mechanistic_mind/ui/psy_observer_web/signal_context/cognitive_forensics.py"
    cft = cf.read_text(encoding="utf-8")
    if "DEFAULT_SIGINT05 = None" in cft:
        cft = cft.replace(
            "root = Path(sigint05_dir) if sigint05_dir else DEFAULT_SIGINT05",
            "if not sigint05_dir:\n"
            "        raise FileNotFoundError(\n"
            "            'SIGINT-05 fixture directory required (no bundled default in public package)'\n"
            "        )\n"
            "    root = Path(sigint05_dir)",
        )
        cf.write_text(cft, encoding="utf-8")
    ie = DEST / "mechanistic_mind/ui/psy_observer_web/signal_context/interaction_episode.py"
    iet = ie.read_text(encoding="utf-8")
    if "DEFAULT_REF_RUN = None" in iet and "/home/thehost" in iet:
        # force clear any leftover absolute strings
        iet = re.sub(r'/home/thehost/[^\s"\']+', "", iet)
        ie.write_text(iet, encoding="utf-8")

    # Rebrand launchers Beta 2 → Public Beta 1 / MM 2.0
    for name in ("launch_psy_observer.sh", "launch_psy_observer.command", "launch_psy_observer.bat", "launch_psy_observer.cmd", "PsyObserver"):
        p = DEST / name
        t = p.read_text(encoding="utf-8", errors="ignore")
        t = t.replace("Beta 2", "Public Beta 1")
        t = t.replace("Beta 1 archive", "Public Beta 1 archive")
        t = t.replace("This Beta 2 archive", "This Public Beta 1 archive")
        p.write_text(t, encoding="utf-8")

    req = DEST / "requirements-observer.txt"
    req.write_text(
        "# Mechanistic Mind 2.0 — Tiktaalik: Undercover — Public Beta 1\n"
        "# Psy Observer Web runtime dependencies\n"
        "fastapi>=0.110\n"
        "uvicorn[standard]>=0.27\n"
        "numpy>=1.26\n"
        "pydantic>=2.0\n"
        "httpx>=0.27\n"
        "pytest>=8.0\n",
        encoding="utf-8",
    )

    # Bootstrap docstring tweak
    boot = (DEST / "scripts" / "bootstrap_psy_observer_env.py").read_text(encoding="utf-8")
    boot = boot.replace("Beta 2", "Public Beta 1").replace("publication / Beta 2", "Public Beta 1")
    (DEST / "scripts" / "bootstrap_psy_observer_env.py").write_text(boot, encoding="utf-8")

    (audit / "COPY_COUNTS.json").write_text(
        __import__("json").dumps({"counts": counts, "dest": str(DEST.name), "src_commit": _git_commit()}, indent=2),
        encoding="utf-8",
    )
    print("PACKAGED", DEST)
    print("counts", counts)


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(SRC), "rev-parse", "HEAD"], text=True
        ).strip()
    except Exception:
        return "unknown"


if __name__ == "__main__":
    main()
