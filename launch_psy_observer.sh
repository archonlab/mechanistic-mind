#!/usr/bin/env bash
# Psy Observer Web — Public Beta 1 launcher (Linux / Unix).
# Double-click or run from any working directory.
# First launch may create .venv_psy_web and install requirements-observer.txt.
# Starts mechanistic_mind.ui.psy_observer_web via the canonical Python launcher.

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
BOOTSTRAP="$ROOT/scripts/bootstrap_psy_observer_env.py"
VENV_PY="$ROOT/.venv_psy_web/bin/python"
mkdir -p "$LOG_DIR"

fail() {
  msg="$1"
  echo "Psy Observer Web could not start." >&2
  echo "" >&2
  echo "$msg" >&2
  echo "" >&2
  echo "See README.md for help." >&2
  echo "Log: $LOG_FILE" >&2
  {
    echo "$(date -u +"%Y-%m-%dT%H:%M:%SZ") ERROR $msg"
  } >> "$LOG_FILE" 2>/dev/null || true
  if [ ! -t 0 ] && [ -n "${DISPLAY:-}" ]; then
    (zenity --error --title "Psy Observer Web" --text "Psy Observer Web could not start.

$msg" >/dev/null 2>&1 &) || true
    (kdialog --error "Psy Observer Web could not start.

$msg" >/dev/null 2>&1 &) || true
    (notify-send "Psy Observer Web" "$msg" >/dev/null 2>&1 &) || true
  fi
  exit 1
}

version_ok() {
  local exe="$1"
  "$exe" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3, 11) else 1)' 2>/dev/null
}

find_system_python() {
  local cand
  for cand in python3 python; do
    if command -v "$cand" >/dev/null 2>&1; then
      cand="$(command -v "$cand")"
      if version_ok "$cand"; then
        printf '%s\n' "$cand"
        return 0
      fi
    fi
  done
  return 1
}

venv_ready() {
  [ -x "$VENV_PY" ] || return 1
  "$VENV_PY" "$BOOTSTRAP" --root "$ROOT" --check-only >/dev/null 2>&1
}

ensure_environment() {
  if [ -n "${PSY_OBSERVER_PYTHON:-}" ] && [ -x "${PSY_OBSERVER_PYTHON}" ]; then
    return 0
  fi
  if venv_ready; then
    return 0
  fi

  echo "Preparing Psy Observer for first launch."
  echo "This may take a few minutes."
  echo ""

  local progress_pid=""
  if [ ! -t 1 ] && [ -n "${DISPLAY:-}" ] && command -v zenity >/dev/null 2>&1; then
    zenity --progress --pulsate --no-cancel --auto-close \
      --title="Psy Observer" \
      --text="Preparing Psy Observer for first launch.\nThis may take a few minutes." \
      >/dev/null 2>&1 &
    progress_pid=$!
  fi

  local sys_py
  if ! sys_py="$(find_system_python)"; then
    [ -n "$progress_pid" ] && kill "$progress_pid" >/dev/null 2>&1 || true
    fail "Python 3.11 or newer is required to prepare Psy Observer.

Install Python from:
  • https://www.python.org/downloads/
  • or your Linux distribution package manager (python3)

Then double-click Psy Observer again."
  fi

  if ! "$sys_py" "$BOOTSTRAP" --root "$ROOT" >>"$LOG_FILE" 2>&1; then
    [ -n "$progress_pid" ] && kill "$progress_pid" >/dev/null 2>&1 || true
    # Also print last log lines to the console when available
    tail -n 40 "$LOG_FILE" 2>/dev/null || true
    fail "First-run setup failed while creating .venv_psy_web or installing dependencies.

Details are in:
  $LOG_FILE

Typical causes: no network, blocked pip, or an incomplete Python install."
  fi

  [ -n "$progress_pid" ] && kill "$progress_pid" >/dev/null 2>&1 || true
  echo "First-run setup finished."
}

pick_runtime_python() {
  if [ -n "${PSY_OBSERVER_PYTHON:-}" ] && [ -x "${PSY_OBSERVER_PYTHON}" ]; then
    printf '%s\n' "${PSY_OBSERVER_PYTHON}"
    return 0
  fi
  if [ -x "$VENV_PY" ]; then
    printf '%s\n' "$VENV_PY"
    return 0
  fi
  if [ -x "$ROOT/.venv_psy_web/bin/python3" ]; then
    printf '%s\n' "$ROOT/.venv_psy_web/bin/python3"
    return 0
  fi
  return 1
}

if [ ! -f "$ROOT/mechanistic_mind/ui/psy_observer_web/web_dist/index.html" ]; then
  fail "The Observer interface is not built yet (missing production web_dist files).
This Public Public Beta 1 archive should already include web_dist. Re-download the release if it is missing."
fi

if [ ! -f "$BOOTSTRAP" ]; then
  fail "Missing bootstrap script: scripts/bootstrap_psy_observer_env.py"
fi

ensure_environment

if ! PY="$(pick_runtime_python)"; then
  fail "Python environment missing after bootstrap (.venv_psy_web)."
fi

cd "$ROOT"
exec "$PY" -m mechanistic_mind.ui.psy_observer_web.launcher "$@"
