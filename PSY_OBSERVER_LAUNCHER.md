# PSY Observer launcher

Entry points (package root):

| File | Platform |
|------|----------|
| `launch_psy_observer.sh` | Linux |
| `launch_psy_observer.command` | macOS |
| `launch_psy_observer.bat` / `.cmd` | Windows |
| `PsyObserver` | Linux convenience wrapper |

First launch may create `.venv_psy_web` and install `requirements-observer.txt` via `scripts/bootstrap_psy_observer_env.py`.

Preferred local URL: `http://127.0.0.1:8768` (fallback if busy).

Requires packaged `mechanistic_mind/ui/psy_observer_web/web_dist/`.

Environment overrides:

- `PSY_OBSERVER_PYTHON` — force interpreter
- `PSY_OBSERVER_PROJECT_ROOT` — set by launchers
