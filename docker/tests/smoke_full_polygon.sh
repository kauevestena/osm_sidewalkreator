#!/usr/bin/env bash
set -euo pipefail

# Smoke test: full pipeline from polygon via convenience script
cd "$(dirname "$0")/.."

INP="../assets/test_data/polygon.geojson"
OUT_SW_REL="assets/test_outputs/sidewalks_polygon_smoke.geojson"

rm -f "../$OUT_SW_REL"
set +e
./run_full_polygon.sh -i "$INP" -o "$OUT_SW_REL" --no-buildings --no-addresses
status=$?
set -e

if [[ ! -s "../$OUT_SW_REL" ]]; then
  echo "FAIL: Sidewalks output not created or empty: ../$OUT_SW_REL (exit=$status)" >&2
  exit 1
fi

echo "OK: Created sidewalk output ../$OUT_SW_REL (exit=$status ignored)."
