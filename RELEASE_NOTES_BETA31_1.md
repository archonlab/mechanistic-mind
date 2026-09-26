# MM 1.0 Tiktaalik — Public Beta 3.1.1 release notes

**Release name:** `MM-1.0-Tiktaalik-Public-Beta-3.1.1`  
**Tag:** `v1.0.0-tiktaalik-public-beta-3.1.1`

This is a **launcher/bootstrap patch** of frozen Public Beta 3.1. Tiktaalik
scientific/model semantics are unchanged. Canonical preset **TIKTAALIK_BETA31**
is unchanged. Existing Public Beta 3.1 (`v1.0.0-tiktaalik-public-beta-3.1`)
remains frozen and available.

## What is fixed

- A fresh GitHub/source copy launched via `PsyObserver` / platform launchers now
  **automatically bootstraps** `.venv_psy_web` when that environment does not
  exist. Users do not create the venv by hand.
- Required dependencies are installed through the existing canonical script
  `scripts/bootstrap_psy_observer_env.py` and `requirements-observer.txt`.
- Subsequent launches **reuse** `.venv_psy_web` and do not reinstall unless the
  environment is missing or incomplete.
- First-run failure reports bootstrap/recovery guidance (network, Python ≥ 3.11,
  log path) instead of only “environment missing.”

The Python launcher also invokes the same bootstrap path, so
`python -m mechanistic_mind.ui.psy_observer_web.launcher` on a clean tree
behaves like the platform wrappers.

## Validation

- Linux first-run (environment created, dependencies installed, Observer
  started, `/api/health`, SPA load): **runtime tested**
- Linux second-run (env reused, no unnecessary reinstall): **runtime tested**
- Packaged-copy first-run and second-run: **runtime tested**
- macOS `launch_psy_observer.command` bootstrap path: **statically validated**
  (not executed on macOS in this release)
- Windows `launch_psy_observer.bat` bootstrap path: **statically validated**
  (not executed on Windows in this release)

## What did not change

- No Tiktaalik scientific or model semantics
- No change to `TIKTAALIK_BETA31`
- No change to cognition, PSC, PE/TPS/TPE, SMC/HSS, motor selection, NECK/OSC/PUSH,
  vision, physics, ecology, terrain, persistence, or Analyzer science
- Frozen Public Beta 3 package is untouched
- Existing Beta 3.1 tag and GitHub ZIP/TAR.GZ assets are not replaced by this
  release

First launch still needs **network** for `pip` and **Python 3.11+**. See
`PSY_OBSERVER_LAUNCHER.md` if bootstrap fails.

Scientific workflow and limitations remain those of Beta 3.1
(`RELEASE_NOTES_BETA31.md`, `KNOWN_LIMITATIONS.md`).
