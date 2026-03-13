#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DATA_DIR="$ROOT_DIR/data"
BASELINE_DIR="$DATA_DIR/.baseline"

MASKS_SRC="$BASELINE_DIR/masks"
GENERATED_SRC="$BASELINE_DIR/generated"
MASKS_DST="$DATA_DIR/masks"
GENERATED_DST="$DATA_DIR/generated"
TRASH_DST="$DATA_DIR/.trash"

if [[ ! -d "$MASKS_SRC" || ! -d "$GENERATED_SRC" ]]; then
  echo "Baseline not found. Run ./infra/scripts/save-test-baseline.sh first."
  exit 1
fi

rm -rf "$MASKS_DST" "$GENERATED_DST" "$TRASH_DST"
cp -a "$MASKS_SRC" "$MASKS_DST"
cp -a "$GENERATED_SRC" "$GENERATED_DST"
mkdir -p "$TRASH_DST"

echo "Restored dataset files from baseline."

echo "Resetting DB review/deletion state..."

RESET_PYTHON_CODE="$(cat <<'PY'
from app.core.config import get_dataset_config
from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.models.deletion_operation import DeletionOperation
from app.models.generated_image import GeneratedImage
from app.models.ingestion_run import IngestionRun
from app.models.mask_group import MaskGroup
from app.models.review_decision import ReviewDecision
from app.services.ingestion import run_ingestion

init_db()
db = SessionLocal()
try:
    # Full review-state reset so ingest starts from clean baseline data on disk.
    db.query(ReviewDecision).delete(synchronize_session=False)
    db.query(DeletionOperation).delete(synchronize_session=False)
    db.query(IngestionRun).delete(synchronize_session=False)
    db.query(GeneratedImage).delete(synchronize_session=False)
    db.query(MaskGroup).delete(synchronize_session=False)
    db.commit()

    run = run_ingestion(db, get_dataset_config())
    print(f"Reset complete: files_scanned={run.files_scanned} errors_count={run.errors_count}")
finally:
    db.close()
PY
)"

if command -v docker >/dev/null 2>&1 && docker compose ps --services --filter status=running 2>/dev/null | grep -q '^backend$'; then
  docker compose exec -T backend python - <<PY
$RESET_PYTHON_CODE
PY
else
  echo "Docker backend not running; using local reset path (Gradio/non-Docker)."

  if [[ -f "$ROOT_DIR/.env" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$ROOT_DIR/.env"
    set +a
  fi

  export APP_CONFIG_PATH="${APP_CONFIG_PATH:-$ROOT_DIR/app_config.yaml}"
  export DATASET_ROOT_DIR="${DATASET_ROOT_DIR:-$DATA_DIR}"
  export DATABASE_URL="${DATABASE_URL:-sqlite:///$DATA_DIR/review.db}"
  export SESSION_COOKIE_SECURE="${SESSION_COOKIE_SECURE:-false}"

  LOCAL_PYTHON="$ROOT_DIR/.venv-gradio/bin/python"
  if [[ ! -x "$LOCAL_PYTHON" ]]; then
    LOCAL_PYTHON="$(command -v python3 || true)"
  fi
  if [[ -z "$LOCAL_PYTHON" ]]; then
    echo "Python not found. Create .venv-gradio or install python3 first."
    exit 1
  fi

  PYTHONPATH="$ROOT_DIR/backend" "$LOCAL_PYTHON" - <<PY
$RESET_PYTHON_CODE
PY
fi

echo "Testing state restored. Reload the web app."
