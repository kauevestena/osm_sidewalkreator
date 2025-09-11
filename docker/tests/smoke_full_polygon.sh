#!/usr/bin/env bash
set -euo pipefail

# Smoke test: full pipeline from polygon via convenience script
cd "$(dirname "$0")/.."

INP="../assets/test_data/polygon.geojson"
OUT_SW_REL="assets/test_outputs/sidewalks_polygon_smoke.geojson"
OUT_CR_REL="assets/test_outputs/sidewalks_polygon_smoke_crossings.geojson"
OUT_KB_REL="assets/test_outputs/sidewalks_polygon_smoke_kerbs.geojson"

rm -f "../$OUT_SW_REL" "../$OUT_CR_REL" "../$OUT_KB_REL"
set +e
./run_full_polygon.sh -i "$INP" -o "$OUT_SW_REL" --no-buildings --no-addresses
status=$?
set -e

if [[ ! -s "../$OUT_SW_REL" ]]; then
  echo "FAIL: Sidewalks output not created or empty: ../$OUT_SW_REL (exit=$status)" >&2
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

echo "OK: Created polygon outputs: ../$OUT_SW_REL, ../$OUT_CR_REL, ../$OUT_KB_REL (exit=$status ignored)."
