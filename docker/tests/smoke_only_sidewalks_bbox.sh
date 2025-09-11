#!/usr/bin/env bash
set -euo pipefail

# Smoke test: full bbox with --only_sidewalks; crossings/kerbs not written
cd "$(dirname "$0")/.."

OUT_SW_REL="assets/test_outputs/only_sw_bbox.geojson"
OUT_CR_REL="assets/test_outputs/only_sw_bbox_crossings.geojson"
OUT_KB_REL="assets/test_outputs/only_sw_bbox_kerbs.geojson"

rm -f "../$OUT_SW_REL" "../$OUT_CR_REL" "../$OUT_KB_REL"
set +e
./run_full_bbox.sh -o "$OUT_SW_REL" --only_sidewalks --no-buildings --classes=10
status=$?
set -e

if [[ ! -s "../$OUT_SW_REL" ]]; then
  echo "FAIL: Sidewalks output not created or empty: ../$OUT_SW_REL (exit=$status)" >&2
  exit 1
fi

if [[ -e "../$OUT_CR_REL" ]]; then
  echo "FAIL: Crossings file should not exist with --only_sidewalks: ../$OUT_CR_REL" >&2
  exit 1
fi

if [[ -e "../$OUT_KB_REL" ]]; then
  echo "FAIL: Kerbs file should not exist with --only_sidewalks: ../$OUT_KB_REL" >&2
  exit 1
fi

echo "OK: Only-sidewalks bbox output created: ../$OUT_SW_REL (exit=$status ignored)."

