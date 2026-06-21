#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-run}"
APP_NAME="HALO"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$ROOT_DIR/.venv-macos"
APP_BUNDLE="$ROOT_DIR/dist/$APP_NAME.app"
PYTHON_BIN="${PYTHON:-python3}"

cd "$ROOT_DIR"

ensure_deps() {
  if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    "$PYTHON_BIN" -m venv "$VENV_DIR"
  fi
  "$VENV_DIR/bin/python" -m pip install --upgrade pip
  "$VENV_DIR/bin/python" -m pip install -r requirements-macos.txt
}

build_app() {
  ensure_deps

  local data_args=("--add-data" "index.html:.")
  if [[ -f "admin.html" ]]; then
    data_args+=("--add-data" "admin.html:.")
  fi
  if [[ -f "studio.html" ]]; then
    data_args+=("--add-data" "studio.html:.")
  fi

  "$VENV_DIR/bin/python" -m PyInstaller \
    --noconfirm \
    --clean \
    --windowed \
    --name "$APP_NAME" \
    --collect-all webview \
    --collect-submodules flask \
    --collect-submodules openai \
    --collect-submodules fal_client \
    --collect-submodules supabase \
    "${data_args[@]}" \
    mac_app.py
}

launch_app() {
  /usr/bin/open -n "$APP_BUNDLE"
}

pkill -x "$APP_NAME" >/dev/null 2>&1 || true

case "$MODE" in
  run)
    build_app
    launch_app
    ;;
  --debug|debug)
    build_app
    lldb -- "$APP_BUNDLE/Contents/MacOS/$APP_NAME"
    ;;
  --logs|logs)
    build_app
    launch_app
    /usr/bin/log stream --info --style compact --predicate "process == \"$APP_NAME\""
    ;;
  --telemetry|telemetry)
    build_app
    launch_app
    /usr/bin/log stream --info --style compact --predicate "process == \"$APP_NAME\""
    ;;
  --verify|verify)
    build_app
    launch_app
    sleep 2
    pgrep -x "$APP_NAME" >/dev/null
    ;;
  *)
    echo "usage: $0 [run|--debug|--logs|--telemetry|--verify]" >&2
    exit 2
    ;;
esac
