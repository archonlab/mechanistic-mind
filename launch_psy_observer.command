#!/usr/bin/env bash
# Psy Observer Web — Beta 3.1 launcher (macOS Finder double-clickable).
# Resolves its own directory; keeps Terminal open on failure.
# First launch may create .venv_psy_web and install requirements-observer.txt.

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
  echo ""
  echo "Press Return to close this window."
  # shellcheck disable=SC2162
  read _ || true
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
  # Common python.org / Homebrew locations
  for cand in \
    /usr/local/bin/python3 \
    /opt/homebrew/bin/python3 \
    /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 \
    /Library/Frameworks/Python.framework/Versions/3.11/bin/python3
  do
    if [ -x "$cand" ] && version_ok "$cand"; then
      printf '%s\n' "$cand"
      return 0
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

    echo "Preparing Psy Observer environment"
    echo "Creating Python environment and installing dependencies if needed."
    echo "This may take a few minutes on first launch (network required)."
  echo ""

  local sys_py
  if ! sys_py="$(find_system_python)"; then
    fail "Python 3.11 or newer is required to prepare Psy Observer.

Install Python from https://www.python.org/downloads/
(or Homebrew: brew install python), then open this launcher again.

Gatekeeper note: first open may require right-click → Open."
  fi

  if ! "$sys_py" "$BOOTSTRAP" --root "$ROOT" 2>&1 | tee -a "$LOG_FILE"; then
    fail "First-run setup failed while creating .venv_psy_web or installing dependencies.
See $LOG_FILE"
  fi
  echo "First-run setup finished."
}

if [ ! -f "$ROOT/mechanistic_mind/ui/psy_observer_web/web_dist/index.html" ]; then
  fail "Missing production web_dist. Re-download the Beta 3.1 archive."
fi
if [ ! -f "$BOOTSTRAP" ]; then
  fail "Missing bootstrap script: scripts/bootstrap_psy_observer_env.py"
fi

ensure_environment

if [ -n "${PSY_OBSERVER_PYTHON:-}" ] && [ -x "${PSY_OBSERVER_PYTHON}" ]; then
  PY="${PSY_OBSERVER_PYTHON}"
elif [ -x "$VENV_PY" ]; then
  PY="$VENV_PY"
else
  fail "Python environment missing after bootstrap (.venv_psy_web)."
fi

cd "$ROOT"
echo "Starting Psy Observer"
# Gatekeeper note: first open may require right-click → Open if macOS quarantines the file.
exec "$PY" -m mechanistic_mind.ui.psy_observer_web.launcher "$@"
