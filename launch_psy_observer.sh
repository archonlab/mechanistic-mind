#!/usr/bin/env bash
# Psy Observer Web — Beta 1 launcher (Linux / Unix).
# Double-click or run from any working directory.
# Starts mechanistic_mind.ui.psy_observer_web via the canonical Python launcher
# (preferred port, free-port fallback, browser open). Not Legacy Observer.

set -euo pipefail

SOURCE="${BASH_SOURCE[0]}"
while [ -L "$SOURCE" ]; do
  DIR="$(cd "$(dirname "$SOURCE")" && pwd)"
  LINK="$(readlink "$SOURCE")"
  case "$LINK" in
    /*) SOURCE="$LINK" ;;
    *) SOURCE="$DIR/$LINK" ;;
  esac
done
ROOT="$(cd "$(dirname "$SOURCE")" && pwd)"
export PSY_OBSERVER_PROJECT_ROOT="$ROOT"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"

LOG_DIR="$ROOT/.psy_observer"
LOG_FILE="$LOG_DIR/launcher.log"
mkdir -p "$LOG_DIR"

fail() {
  msg="$1"
  echo "Psy Observer Web could not start." >&2
  echo "" >&2
  echo "$msg" >&2
  echo "" >&2
  echo "See README installation instructions." >&2
  echo "Log: $LOG_FILE" >&2
  {
    echo "$(date -u +"%Y-%m-%dT%H:%M:%SZ") ERROR $msg"
  } >> "$LOG_FILE" 2>/dev/null || true
  if [ ! -t 0 ] && [ -n "${DISPLAY:-}" ]; then
    # Never block startup/failure on a modal dialog (double-click / pipes).
    (zenity --error --title "Psy Observer Web" --text "Psy Observer Web could not start.

$msg" >/dev/null 2>&1 &) || true
    (kdialog --error "Psy Observer Web could not start.

$msg" >/dev/null 2>&1 &) || true
    (notify-send "Psy Observer Web" "$msg" >/dev/null 2>&1 &) || true
  fi
  exit 1
}

pick_python() {
  if [ -n "${PSY_OBSERVER_PYTHON:-}" ] && [ -x "${PSY_OBSERVER_PYTHON}" ]; then
    printf '%s\n' "${PSY_OBSERVER_PYTHON}"
    return 0
  fi
  for candidate in \
    "$ROOT/.venv_psy_web/bin/python" \
    "$ROOT/.venv_psy_web/bin/python3" \
    "$ROOT/.venv/bin/python" \
    "$ROOT/.venv/bin/python3"
  do
    if [ -x "$candidate" ]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return 0
  fi
  if command -v python >/dev/null 2>&1; then
    command -v python
    return 0
  fi
  return 1
}

if ! PY="$(pick_python)"; then
  fail "Python/dependency missing: no project venv (.venv_psy_web) or python3 on PATH."
fi

if [ ! -f "$ROOT/mechanistic_mind/ui/psy_observer_web/web_dist/index.html" ]; then
  fail "The Observer interface is not built yet (missing production web_dist files).
Rebuild with: cd web/psy-observer && npm run build"
fi

cd "$ROOT"
# Single source of truth: preferred port / reuse / browser / lock.
exec "$PY" -m mechanistic_mind.ui.psy_observer_web.launcher "$@"
