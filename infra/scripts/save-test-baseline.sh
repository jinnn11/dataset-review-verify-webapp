#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DATA_DIR="$ROOT_DIR/data"
BASELINE_DIR="$DATA_DIR/.baseline"

MASKS_SRC="$DATA_DIR/masks"
GENERATED_SRC="$DATA_DIR/generated"
MASKS_DST="$BASELINE_DIR/masks"
GENERATED_DST="$BASELINE_DIR/generated"

if [[ ! -d "$MASKS_SRC" || ! -d "$GENERATED_SRC" ]]; then
  echo "Expected dataset folders missing: $MASKS_SRC and/or $GENERATED_SRC"
  exit 1
fi

mkdir -p "$BASELINE_DIR"
rm -rf "$MASKS_DST" "$GENERATED_DST"
cp -a "$MASKS_SRC" "$MASKS_DST"
cp -a "$GENERATED_SRC" "$GENERATED_DST"

cat > "$BASELINE_DIR/README.txt" <<META
Baseline snapshot for local testing reset.
Created at: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
Masks count: $(find "$MASKS_DST" -type f | wc -l | tr -d ' ')
Generated count: $(find "$GENERATED_DST" -type f | wc -l | tr -d ' ')
META

echo "Saved testing baseline to: $BASELINE_DIR"
