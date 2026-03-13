#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$ROOT_DIR/.venv-gradio"
GRADIO_HOST="${GRADIO_HOST:-0.0.0.0}"
GRADIO_PORT="${GRADIO_PORT:-7860}"

if command -v lsof >/dev/null 2>&1; then
  if lsof -iTCP:"$GRADIO_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Port $GRADIO_PORT is already in use."
    echo "Choose another port, for example:"
    echo "  GRADIO_PORT=7871 ./gradio/run_gradio.sh"
    exit 1
  fi
fi

if [[ ! -d "$VENV_DIR" ]]; then
  python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"

export PIP_DISABLE_PIP_VERSION_CHECK=1
python -m pip install --disable-pip-version-check -r "$ROOT_DIR/backend/requirements.txt" -r "$ROOT_DIR/gradio/requirements.txt"

APP_ARGS=()
if [[ "${GRADIO_SHARE:-true}" == "true" ]]; then
  APP_ARGS+=(--share)
fi
APP_ARGS+=(--host "$GRADIO_HOST" --port "$GRADIO_PORT")

echo "Starting Gradio on ${GRADIO_HOST}:${GRADIO_PORT} (share=${GRADIO_SHARE:-true})"

if [[ -f "$ROOT_DIR/frontend/dist/index.html" ]]; then
  python "$ROOT_DIR/gradio/app.py" "${APP_ARGS[@]}"
else
  echo "frontend/dist missing; attempting build (requires npm)..."
  python "$ROOT_DIR/gradio/app.py" --build-frontend "${APP_ARGS[@]}"
fi
