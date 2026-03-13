#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$ROOT_DIR/.venv-gradio"

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

if [[ -f "$ROOT_DIR/frontend/dist/index.html" ]]; then
  python "$ROOT_DIR/gradio/app.py" "${APP_ARGS[@]}"
else
  echo "frontend/dist missing; attempting build (requires npm)..."
  python "$ROOT_DIR/gradio/app.py" --build-frontend "${APP_ARGS[@]}"
fi
