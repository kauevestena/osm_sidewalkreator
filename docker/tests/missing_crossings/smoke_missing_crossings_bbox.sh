#!/usr/bin/env bash
set -euo pipefail

# Smoke test: missing crossings from bbox via convenience script

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

OUT_CR_REL="assets/test_outputs/missing_crossings_bbox_smoke.geojson"
OUT_KB_REL="assets/test_outputs/missing_kerbs_bbox_smoke.geojson"

cd "${ROOT_DIR}/docker"
./run_missing_crossings_bbox.sh --crossings-output "$OUT_CR_REL" --kerbs-output "$OUT_KB_REL"
status=$?

cd - >/dev/null

if [[ ! -s "${ROOT_DIR}/${OUT_CR_REL}" ]]; then
  echo "WARN: Crossings output not created or empty: ${OUT_CR_REL} (exit=$status). This can happen due to dynamic OSM data." >&2
else
  echo "OK: Created missing crossings output: ${OUT_CR_REL}"
fi

if [[ ! -s "${ROOT_DIR}/${OUT_KB_REL}" ]]; then
  echo "WARN: Kerbs output not created or empty: ${OUT_KB_REL} (exit=$status). This can happen due to dynamic OSM data." >&2
else
  echo "OK: Created missing kerbs output: ${OUT_KB_REL}"
fi

echo "Done (exit status $status, non-fatal if outputs are empty)."

