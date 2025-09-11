#!/usr/bin/env bash
set -euo pipefail

# Usage: ./run_protoblocks_polygon.sh [-i FILE] [-o FILE] [--crs=EPSG:code]
# Examples:
#   ./run_protoblocks_polygon.sh                                          # Uses default polygon.geojson, EPSG:4326
#   ./run_protoblocks_polygon.sh -i assets/test_data/polygon.geojson      # Explicit input
#   ./run_protoblocks_polygon.sh -i my_poly.gpkg --crs=EPSG:3857          # OGR polygon input with CRS
#   ./run_protoblocks_polygon.sh -i polygon.shp -o outputs/protob.gpkg    # Custom output path/format

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${ROOT_DIR}/assets/test_outputs"
mkdir -p "${OUT_DIR}"

INPUT_POLYGON="${ROOT_DIR}/assets/test_data/polygon.geojson"
INPUT_CRS="EPSG:4326"
OUTPUT_PATH="${OUT_DIR}/protoblocks_polygon.geojson"

for arg in "$@"; do
  case "$arg" in
    -i|--input)
      shift; INPUT_POLYGON="${1:-}"; shift || true ;;
    --input=*) INPUT_POLYGON="${arg#*=}" ;;
    -o|--output)
      shift; OUTPUT_PATH="${1:-}"; shift || true ;;
    --output=*) OUTPUT_PATH="${arg#*=}" ;;
    --crs=*) INPUT_CRS="${arg#*=}" ;;
    -h|--help)
      cat <<EOF
Usage: $0 [-i FILE] [-o FILE] [--crs=EPSG:code]
EOF
      exit 0 ;;
  esac
done

if [[ ! -f "$INPUT_POLYGON" ]]; then
  # Try to resolve relative to repo root
  if [[ -f "${ROOT_DIR}/$INPUT_POLYGON" ]]; then
    INPUT_POLYGON="${ROOT_DIR}/$INPUT_POLYGON"
  else
    echo "Error: Input polygon file not found: $INPUT_POLYGON" >&2
    exit 1
  fi
fi

if command -v realpath >/dev/null 2>&1; then
  ABS_INP="$(realpath "$INPUT_POLYGON")"
elif readlink -f / >/dev/null 2>&1; then
  ABS_INP="$(readlink -f "$INPUT_POLYGON")"
else
  ABS_INP="$INPUT_POLYGON"
fi

# Map to container-relative path under /plugins/osm_sidewalkreator
if [[ "$ABS_INP" == ${ROOT_DIR}/* ]]; then
  CONTAINER_INP_REL="${ABS_INP#${ROOT_DIR}/}"
else
  # Fallback: use basename, assuming file copied under assets
  CONTAINER_INP_REL="$INPUT_POLYGON"
fi

echo "Running protoblocks (polygon):"
echo "  Input:  $CONTAINER_INP_REL"
echo "  CRS:    $INPUT_CRS"
echo "  Output: $OUTPUT_PATH"

docker run --rm \
  -v "${ROOT_DIR}:/plugins/osm_sidewalkreator" \
  -e INPUT_POLYGON="${CONTAINER_INP_REL}" \
  -e INPUT_CRS="${INPUT_CRS}" \
  -e OUTPUT_PATH="${OUTPUT_PATH}" \
  -w / \
  qgis/qgis:latest bash -lc '
set -euo pipefail
mkdir -p /tmp/runtime-qgis && chmod 700 /tmp/runtime-qgis
export XDG_RUNTIME_DIR=/tmp/runtime-qgis
export QGIS_PREFIX_PATH=/usr
export QGIS_PLUGINPATH=/usr/lib/qgis/plugins
export PYTHONPATH=/usr/share/qgis/python:/usr/share/qgis/python/plugins:/plugins
export QT_QPA_PLATFORM=offscreen
python3 - <<PY
import os
from qgis.core import QgsApplication, QgsVectorLayer
QgsApplication.setPrefixPath("/usr", True)
app=QgsApplication([], False); app.initQgis()
from qgis.analysis import QgsNativeAlgorithms
QgsApplication.processingRegistry().addProvider(QgsNativeAlgorithms())
from osm_sidewalkreator.processing.protoblock_provider import ProtoblockProvider
QgsApplication.processingRegistry().addProvider(ProtoblockProvider())
from osm_sidewalkreator.processing.protoblock_algorithm import ProtoblockAlgorithm
from qgis import processing

inp = os.environ["INPUT_POLYGON"]
inp = inp if inp.startswith("/") else f"/plugins/osm_sidewalkreator/{inp}"
crs = os.environ.get("INPUT_CRS", "EPSG:4326")
outp = os.environ.get("OUTPUT_PATH", "/plugins/osm_sidewalkreator/assets/test_outputs/protoblocks_polygon.geojson")
if not outp.startswith("/"):
    outp = f"/plugins/osm_sidewalkreator/{outp}"
os.makedirs(os.path.dirname(outp), exist_ok=True)

# Build a unary-unioned single-feature memory layer if multiple features exist
layer = QgsVectorLayer(inp, "input_poly", "ogr")
if not layer.isValid() or layer.featureCount() == 0:
    raise SystemExit(f"Invalid or empty polygon layer: {inp}")

# Dissolve/unary union via processing for robustness across geometry types
res = processing.run(
    "native:dissolve",
    {"INPUT": layer, "FIELD": [], "SEPARATE_DISJOINT": False, "OUTPUT": "memory:union_poly"},
)
union_layer = res["OUTPUT"] if res and res.get("OUTPUT") else layer

params = {
  ProtoblockAlgorithm.INPUT_POLYGON: union_layer,
  ProtoblockAlgorithm.INPUT_CRS: crs,
  ProtoblockAlgorithm.TIMEOUT: 60,
  ProtoblockAlgorithm.OUTPUT_PROTOBLOCKS: outp,
}
result = processing.run(ProtoblockAlgorithm(), params)
print("Processing completed successfully!")
print(f"Output sink: {result.get(ProtoblockAlgorithm.OUTPUT_PROTOBLOCKS)}")
PY'

echo "Wrote: ${OUTPUT_PATH}"
