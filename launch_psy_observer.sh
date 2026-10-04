#!/usr/bin/env bash
# MM Observer — Acanthostega Beta 4.0 launcher (Linux / Unix).
# Double-click `MM Observer` (or PsyObserver). The launcher owns the window and backend.

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

# Prefer bundled runtime; keep PYTHONPATH install-relative (relocatable).
RUNTIME_PY=""
for cand in \
  "$ROOT/runtime/python/bin/python3.12" \
  "$ROOT/runtime/python/bin/python3" \
  "$ROOT/runtime/python/bin/python"
do
  if [ -x "$cand" ]; then
    RUNTIME_PY="$cand"
    break
  fi
done

SITE_PACKAGES=""
for sp in "$ROOT"/.venv_psy_web/lib/python*/site-packages; do
  if [ -d "$sp" ]; then
    SITE_PACKAGES="$sp"
  fi
done

export PYTHONPATH="$ROOT${SITE_PACKAGES:+:$SITE_PACKAGES}"
export PYTHONNOUSERSITE=1
unset PYTHONHOME || true

if [ -n "$RUNTIME_PY" ]; then
  export PSY_OBSERVER_PACKAGED=1
  export PSY_OBSERVER_PYTHON="$RUNTIME_PY"
  export PSY_OBSERVER_SKIP_BOOTSTRAP=1
fi

# XDG defaults (Python launcher also enforces these).
: "${XDG_CONFIG_HOME:=$HOME/.config}"
: "${XDG_DATA_HOME:=$HOME/.local/share}"
: "${XDG_CACHE_HOME:=$HOME/.cache}"
: "${XDG_STATE_HOME:=$HOME/.local/state}"
export PSY_OBSERVER_CONFIG_DIR="${PSY_OBSERVER_CONFIG_DIR:-$XDG_CONFIG_HOME/mm-observer}"
export PSY_OBSERVER_DATA_DIR="${PSY_OBSERVER_DATA_DIR:-$XDG_DATA_HOME/mm-observer}"
export PSY_OBSERVER_CACHE_DIR="${PSY_OBSERVER_CACHE_DIR:-$XDG_CACHE_HOME/mm-observer}"
export PSY_OBSERVER_STATE_DIR="${PSY_OBSERVER_STATE_DIR:-$XDG_STATE_HOME/mm-observer}"
export PSY_OBSERVER_RESULTS_ROOT="${PSY_OBSERVER_RESULTS_ROOT:-$PSY_OBSERVER_DATA_DIR/results}"

LOG_DIR="$PSY_OBSERVER_STATE_DIR/launcher"
LOG_FILE="$LOG_DIR/launcher.log"
BOOTSTRAP="$ROOT/scripts/bootstrap_psy_observer_env.py"
VENV_PY="$ROOT/.venv_psy_web/bin/python"
mkdir -p "$LOG_DIR" \
  "$PSY_OBSERVER_CONFIG_DIR" \
  "$PSY_OBSERVER_DATA_DIR" \
  "$PSY_OBSERVER_CACHE_DIR" \
  "$PSY_OBSERVER_RESULTS_ROOT"

fail() {
  msg="$1"
  echo "MM Observer could not start." >&2
  echo "" >&2
  echo "$msg" >&2
  echo "" >&2
  echo "See README.md for help." >&2
  echo "Log: $LOG_FILE" >&2
  {
    echo "$(date -u +"%Y-%m-%dT%H:%M:%SZ") ERROR $msg"
  } >> "$LOG_FILE" 2>/dev/null || true
  if [ ! -t 0 ] && [ -n "${DISPLAY:-}" ]; then
    (zenity --error --title "MM Observer" --text "MM Observer could not start.

$msg" >/dev/null 2>&1 &) || true
    (kdialog --error "MM Observer could not start.

$msg" >/dev/null 2>&1 &) || true
    (notify-send "MM Observer" "$msg" >/dev/null 2>&1 &) || true
  fi
  exit 1
}

version_ok() {
  local exe="$1"
  "$exe" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3, 11) else 1)' 2>/dev/null
}

find_system_python() {
  # Only for non-packaged developer checkouts.
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
  [ -f "$BOOTSTRAP" ] || return 1
  "$VENV_PY" "$BOOTSTRAP" --root "$ROOT" --check-only >/dev/null 2>&1
}

ensure_environment() {
  if [ -n "${PSY_OBSERVER_SKIP_BOOTSTRAP:-}" ]; then
    return 0
  fi
  if [ -n "${PSY_OBSERVER_PYTHON:-}" ] && [ -x "${PSY_OBSERVER_PYTHON}" ]; then
    return 0
  fi
  if venv_ready; then
    return 0
  fi

  echo "Preparing MM Observer environment"
  echo "Creating Python environment and installing dependencies if needed."
  echo "This may take a few minutes on first launch (network required)."
  echo ""

  local progress_pid=""
  if [ ! -t 1 ] && [ -n "${DISPLAY:-}" ] && command -v zenity >/dev/null 2>&1; then
    zenity --progress --pulsate --no-cancel --auto-close \
      --title="MM Observer" \
      --text="Preparing MM Observer for first launch.\nThis may take a few minutes." \
      >/dev/null 2>&1 &
    progress_pid=$!
  fi

  local sys_py
  if ! sys_py="$(find_system_python)"; then
    [ -n "$progress_pid" ] && kill "$progress_pid" >/dev/null 2>&1 || true
    fail "Python 3.11 or newer is required to prepare MM Observer for a developer checkout.

Packaged releases include a bundled runtime and do not need system Python."
  fi

  if ! "$sys_py" "$BOOTSTRAP" --root "$ROOT" 2>&1 | tee -a "$LOG_FILE"; then
    [ -n "$progress_pid" ] && kill "$progress_pid" >/dev/null 2>&1 || true
    fail "First-run setup failed while creating .venv_psy_web or installing dependencies.

Details are in:
  $LOG_FILE"
  fi

  [ -n "$progress_pid" ] && kill "$progress_pid" >/dev/null 2>&1 || true
  echo "First-run setup finished."
}

pick_runtime_python() {
  if [ -n "${PSY_OBSERVER_PYTHON:-}" ] && [ -x "${PSY_OBSERVER_PYTHON}" ]; then
    printf '%s\n' "${PSY_OBSERVER_PYTHON}"
    return 0
  fi
  if [ -n "$RUNTIME_PY" ] && [ -x "$RUNTIME_PY" ]; then
    printf '%s\n' "$RUNTIME_PY"
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
Re-extract the release archive if this is a packaged build."
fi

# Packaged: never bootstrap. Developer: may bootstrap.
if [ -z "$RUNTIME_PY" ]; then
  if [ ! -f "$BOOTSTRAP" ]; then
    fail "Missing bootstrap script: scripts/bootstrap_psy_observer_env.py"
  fi
  ensure_environment
fi

if ! PY="$(pick_runtime_python)"; then
  fail "Bundled Python runtime missing (runtime/python) and no .venv_psy_web available."
fi

cd "$ROOT"
echo "Starting MM Observer"
exec "$PY" -m mechanistic_mind.ui.psy_observer_web.launcher "$@"
