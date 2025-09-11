#!/usr/bin/env bash
set -euo pipefail

# Smoke test: protoblocks from bbox via convenience script
cd "$(dirname "$0")/.."

OUT_REL="assets/test_outputs/protoblocks_bbox_smoke.geojson"

rm -f "../$OUT_REL"
./run_protoblocks_bbox.sh -o "$OUT_REL"

if [[ -s "../$OUT_REL" ]]; then
  echo "OK: Created ../$OUT_REL ($(stat -c%s "../$OUT_REL") bytes)"
else
  echo "FAIL: Output not created or empty: ../$OUT_REL" >&2
  exit 1
fi
