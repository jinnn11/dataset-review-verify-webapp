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
if ! docker compose ps --services --filter status=running | grep -q '^backend$'; then
  echo "Backend is not running. Start services first: docker compose up -d --build"
  exit 1
fi

docker compose exec -T backend python - <<'PY'
from sqlalchemy import text

from app.core.config import get_dataset_config
from app.db.session import SessionLocal
from app.models.generated_image import GeneratedImage, ImageStatus
from app.services.ingestion import run_ingestion

db = SessionLocal()
try:
    db.execute(text("TRUNCATE TABLE review_decisions RESTART IDENTITY CASCADE"))
    db.execute(text("TRUNCATE TABLE deletion_operations RESTART IDENTITY CASCADE"))
    db.execute(text("TRUNCATE TABLE ingestion_runs RESTART IDENTITY CASCADE"))
    db.query(GeneratedImage).update({GeneratedImage.status: ImageStatus.active}, synchronize_session=False)
    db.commit()

    run = run_ingestion(db, get_dataset_config())
    print(f"Reset complete: files_scanned={run.files_scanned} errors_count={run.errors_count}")
finally:
    db.close()
PY

echo "Testing state restored. Reload the web app."
