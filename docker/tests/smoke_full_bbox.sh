#!/usr/bin/env bash
set -euo pipefail

# Smoke test: full pipeline from bbox via convenience script
cd "$(dirname "$0")/.."

OUT_SW_REL="assets/test_outputs/sidewalks_bbox_smoke.geojson"
OUT_CR_REL="assets/test_outputs/sidewalks_bbox_smoke_crossings.geojson"
OUT_KB_REL="assets/test_outputs/sidewalks_bbox_smoke_kerbs.geojson"

rm -f "../$OUT_SW_REL" "../$OUT_CR_REL" "../$OUT_KB_REL"
set +e
./run_full_bbox.sh -o "$OUT_SW_REL" --no-buildings --classes=10
status=$?
set -e

if [[ ! -s "../$OUT_SW_REL" ]]; then
  echo "FAIL: Output not created or empty: ../$OUT_SW_REL" >&2
  exit 1
fi

if [[ ! -s "../$OUT_CR_REL" ]]; then
  echo "FAIL: Crossings output not created or empty: ../$OUT_CR_REL (exit=$status)" >&2
  exit 1
fi

if [[ ! -s "../$OUT_KB_REL" ]]; then
  echo "FAIL: Kerbs output not created or empty: ../$OUT_KB_REL (exit=$status)" >&2
  exit 1
fi

echo "OK: Created bbox outputs: ../$OUT_SW_REL, ../$OUT_CR_REL, ../$OUT_KB_REL (exit=$status ignored)"
