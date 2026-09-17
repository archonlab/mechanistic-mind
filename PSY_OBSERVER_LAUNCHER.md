# Psy Observer Web launcher

**Psy Observer Web** is the Beta 1 interface for MM 1.0 Tiktaalik.

## Normal use (platform launchers)

| Platform | File |
|----------|------|
| Linux | `launch_psy_observer.sh` (also `PsyObserver`) |
| macOS | `launch_psy_observer.command` |
| Windows | `launch_psy_observer.bat` (also `.cmd`) |

Double-click or run the file for your OS. You do not need a terminal, a manual virtual-environment step, a port number, or a localhost URL.

### What happens

1. The launcher finds this project even if you started it from somewhere else (cwd-independent; paths with spaces supported).
2. It checks that the production Observer interface is already built (`web_dist`). Node/npm is **not** required for normal use.
3. **First-run bootstrap** (if `.venv_psy_web` is missing or incomplete):
   - shows: *Preparing Psy Observer for first launch. This may take a few minutes.*
   - finds system Python ≥ 3.11 (`python3` / `python` on Unix; `py` / `python` on Windows)
   - creates `.venv_psy_web`
   - installs dependencies from `requirements-observer.txt`
   - records a readiness marker so later launches skip reinstall
4. If Python ≥ 3.11 is unavailable, it prints a clear message (and where to get Python) and exits without silently closing.
5. If Psy Observer Web is already running for this checkout, it opens that same local window again.
6. Otherwise it starts one local server on `127.0.0.1`, picks a free port if needed (preferred **8768**), waits until healthy, and opens your browser.

Shared bootstrap implementation: `scripts/bootstrap_psy_observer_env.py`.

Subsequent launches reuse `.venv_psy_web` and do **not** reinstall packages unless the environment or requirements marker is incomplete.

All platforms call the same Python entry:

`python -m mechanistic_mind.ui.psy_observer_web.launcher`

(`python -m mechanistic_mind.ui.psy_observer_web` is equivalent — it delegates to the launcher.)

That is the single source of truth for port selection, lock/reuse, and browser open. They do **not** start Legacy Psychology Observer.

## Platform verification (Beta 1)

| Platform | Status |
|----------|--------|
| Linux | **NATIVE TESTED — PASS** |
| macOS | **NATIVE TESTED — PASS** |
| Windows | **STATICALLY VERIFIED — NOT YET NATIVELY TESTED** |

## Shutdown

Closing a browser tab does **not** stop the experiment.

To stop Psy Observer Web:

- click **Quit Psy Observer** in the small application window, or
- press Ctrl+C in the launcher terminal, or
- run `./launch_psy_observer.sh --quit` (Linux/macOS) / `launch_psy_observer.bat --quit` (Windows).

## macOS notes

- First launch may need **right-click → Open** if Gatekeeper quarantines the `.command` file.
- Homebrew is not required by Psy Observer Web.
- First-run bootstrap needs network once to install pip packages.

## Windows notes

- Double-click `launch_psy_observer.bat`. WSL is not required.
- On failure the window stays open with a readable message (`pause`).
- Prefer the `py` launcher or a PATH Python ≥ 3.11 from https://www.python.org/downloads/ (enable “Add python.exe to PATH”).

## Logs

`.psy_observer/launcher.log` (includes first-run bootstrap output)

## Development

```bash
cd web/psy-observer && npm run build
python -m mechanistic_mind.ui.psy_observer_web.launcher --no-browser
```

Useful flags: `--quit` `--no-browser` `--no-window` `--no-wait`

Override interpreter (skips bootstrap): `PSY_OBSERVER_PYTHON=/path/to/python`
