# Psy Observer Web launcher

**Psy Observer Web** is the Public Beta 3.1 interface for MM 1.0 Tiktaalik.

## Normal use (platform launchers)

| Platform | File |
|----------|------|
| Linux | `launch_psy_observer.sh` (also `PsyObserver`) |
| macOS | `launch_psy_observer.command` |
| Windows | `launch_psy_observer.bat` (also `.cmd`) |

Double-click or run the file for your OS. You do not need a terminal, a virtual environment activation step, a port number, or a localhost URL.

What happens:

1. The launcher finds this project even if you started it from somewhere else.
2. It prefers `.venv_psy_web` when present (Unix `bin/`, Windows `Scripts/`).
3. If `.venv_psy_web` is missing or incomplete, first launch runs
   `scripts/bootstrap_psy_observer_env.py`: it creates the environment and
   installs `requirements-observer.txt`. **Internet access is required** for
   that install. First launch can take several minutes. Later launches reuse
   `.venv_psy_web` and do not reinstall unless the environment is broken.
4. It checks that the production Observer interface is already built (`web_dist`).
5. If Psy Observer Web is already running for this checkout, it opens that same local window again.
6. Otherwise it starts one local server on `127.0.0.1`, picks a free port if needed (preferred **8768**), waits until healthy, and opens your browser.

All platforms call the same Python entry:

`python -m mechanistic_mind.ui.psy_observer_web.launcher`

(`python -m mechanistic_mind.ui.psy_observer_web` is equivalent — it delegates to the launcher.)

That is the single source of truth for port selection, lock/reuse, and browser open. They do **not** start Legacy Psychology Observer.

## Shutdown

Closing a browser tab does **not** stop the experiment.

To stop Psy Observer Web:

- click **Quit Psy Observer** in the small application window, or
- press Ctrl+C in the launcher terminal, or
- run `./launch_psy_observer.sh --quit` (Linux/macOS) / `launch_psy_observer.bat --quit` (Windows).

## macOS notes

- First launch may need **right-click → Open** if Gatekeeper quarantines the `.command` file.
- Homebrew is not required by Psy Observer Web.

## Windows notes

- Double-click `launch_psy_observer.bat`. WSL is not required.
- On failure the window stays open with a readable message (`pause`).

## Logs

`.psy_observer/launcher.log`

## If first-run setup fails

You do **not** need to create `.venv_psy_web` by hand. Typical causes: no
network, blocked `pip`, or Python older than 3.11. Install a current Python,
restore network access, then run the same launcher again. Details are in
`.psy_observer/launcher.log`. To force a clean retry, delete `.venv_psy_web`
and relaunch.

## Development

```bash
cd web/psy-observer && npm run build
python -m mechanistic_mind.ui.psy_observer_web.launcher --no-browser
```

Useful flags: `--quit` `--no-browser` `--no-window` `--no-wait`
