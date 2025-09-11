#!/usr/bin/env bash
set -euo pipefail

# Smoke test: full pipeline from bbox via convenience script
cd "$(dirname "$0")/.."

OUT_SW_REL="assets/test_outputs/sidewalks_bbox_smoke.geojson"

rm -f "../$OUT_SW_REL"
set +e
./run_full_bbox.sh -o "$OUT_SW_REL" --no-buildings --classes=10
status=$?
set -e

if [[ -s "../$OUT_SW_REL" ]]; then
  echo "OK: Created ../$OUT_SW_REL ($(stat -c%s "../$OUT_SW_REL") bytes; exit=$status ignored)"
else
  echo "FAIL: Output not created or empty: ../$OUT_SW_REL" >&2
  exit 1
fi
