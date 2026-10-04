# MM Observer launcher

**MM Observer** (Mechanistic Mind Observer — Acanthostega Beta 4.0) is the zero-setup local application for the public Tiktaalik Beta 3.1 and Acanthostega Beta 4.0 models.

Scientific status: **Beta 4 partially validated — bounded supported claims** (post-V1B S6).

## Normal use (packaged release)

| Platform | File |
|----------|------|
| Linux | `MM Observer` (also `PsyObserver`) |

Double-click or run `./PsyObserver`. You do not need a terminal, system Python, a virtual environment, Node/npm, a port number, or a localhost URL.

Optional application menu entry:

```bash
./install-desktop-entry.sh
```

What happens:

1. The launcher resolves its own install directory (cwd does not matter; the tree is relocatable).
2. It uses the bundled `runtime/python` interpreter and packaged libraries (no user-created venv).
3. Mutable state uses XDG directories (see below); the install directory may be read-only.
4. It checks that the production Observer interface is present (`web_dist`).
5. If MM Observer is already running for this user session, it reuses that instance.
6. Otherwise it starts one local server on `127.0.0.1`, picks a free port if needed (preferred **8768**), waits until healthy, and opens a dedicated Chromium application window (private profile, no address bar).

Window title: **Mechanistic Mind Observer — Acanthostega Beta 4.0**

## User data (XDG)

| Kind | Location |
|------|----------|
| Config | `${XDG_CONFIG_HOME:-$HOME/.config}/mm-observer/` |
| Data (saved runs, exports) | `${XDG_DATA_HOME:-$HOME/.local/share}/mm-observer/` |
| Cache | `${XDG_CACHE_HOME:-$HOME/.cache}/mm-observer/` |
| State (logs, locks) | `${XDG_STATE_HOME:-$HOME/.local/state}/mm-observer/` |

Saved runs persist across application upgrades. Removing the install directory does not delete user data. Cache may be deleted safely.

## Backup

Copy `~/.local/share/mm-observer/` (and optionally `~/.config/mm-observer/`).

## Uninstall

Delete the extracted application directory. Optionally delete the XDG folders above. If you ran `install-desktop-entry.sh`, also remove `~/.local/share/applications/mm-observer.desktop`.

## Portable relocation

Move or rename the install directory, then launch `./PsyObserver` again (or re-run `install-desktop-entry.sh`).

## Shutdown

Close the MM Observer application window, or choose **More → Exit MM Observer**.
That stops the backend, Analyzer workers, and researcher audio, and releases the loopback port.

Closing an ordinary browser tab is not the product shutdown path. Refreshing the
application window does not stop the server.

## Logs

`${XDG_STATE_HOME:-$HOME/.local/state}/mm-observer/launcher/launcher.log`

## Development checkout notes

The Experiment → PSC panel shows **CURRENT RUNTIME** first (live ON/OFF, enabled-at tick, transition count). **NEXT RUN** is draft only. An initial-OFF next-run schedule does not mean the current run is OFF.

Developer checkouts may still create `.venv_psy_web` via `scripts/bootstrap_psy_observer_env.py` when a bundled runtime is absent. Packaged releases never require that path.

Useful flags: `--quit` `--no-browser` `--no-window` `--no-wait`
