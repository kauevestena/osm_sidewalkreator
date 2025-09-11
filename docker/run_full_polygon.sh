#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${ROOT_DIR}/assets/test_outputs"
mkdir -p "${OUT_DIR}"

INPUT_POLYGON="${ROOT_DIR}/assets/test_data/polygon.geojson"
SIDEWALKS_OUT="${OUT_DIR}/sidewalks_polygon.geojson"
# By default, keep auxiliary outputs in memory to avoid file I/O issues
CROSSINGS_OUT="memory:"
KERBS_OUT="memory:"

# CLI overrides
CLASSES_ARG=""
GET_BUILDINGS_ARG=""
FETCH_ADDR_ARG=""
for arg in "$@"; do
  case "$arg" in
    -i|--input) shift; INPUT_POLYGON="${1:-}"; shift || true ;;
    --input=*) INPUT_POLYGON="${arg#*=}" ;;
    -o|--output) shift; SIDEWALKS_OUT="${1:-}"; shift || true ;;
    --output=*) SIDEWALKS_OUT="${arg#*=}" ;;
    --crossings-output=*) CROSSINGS_OUT="${arg#*=}" ;;
    --kerbs-output=*) KERBS_OUT="${arg#*=}" ;;
    --classes=*) CLASSES_ARG="${arg#*=}" ;;
    --no-buildings) GET_BUILDINGS_ARG="0" ;;
    --buildings) GET_BUILDINGS_ARG="1" ;;
    --no-addresses) FETCH_ADDR_ARG="0" ;;
    --addresses) FETCH_ADDR_ARG="1" ;;
    -h|--help)
      cat <<EOF
Usage: $0 [-i FILE] [-o FILE] [--classes=...] [--no-buildings|--buildings] [--no-addresses|--addresses] [--crossings-output=FILE] [--kerbs-output=FILE]
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

echo "Running full pipeline (polygon):"
if command -v realpath >/dev/null 2>&1; then
  ABS_INP="$(realpath "$INPUT_POLYGON")"
elif readlink -f / >/dev/null 2>&1; then
  ABS_INP="$(readlink -f "$INPUT_POLYGON")"
else
  ABS_INP="$INPUT_POLYGON"
fi
if [[ "$ABS_INP" == ${ROOT_DIR}/* ]]; then
  CONTAINER_INP_REL="${ABS_INP#${ROOT_DIR}/}"
else
  CONTAINER_INP_REL="$INPUT_POLYGON"
fi
echo "  Input:     $CONTAINER_INP_REL"
echo "  Sidewalks: $SIDEWALKS_OUT"
echo "  Crossings: $CROSSINGS_OUT"
echo "  Kerbs:     $KERBS_OUT"

docker run --rm \
  -v "${ROOT_DIR}:/plugins/osm_sidewalkreator" \
  -e INPUT_POLYGON="${CONTAINER_INP_REL}" \
  -e OUTPUT_SIDEWALKS="${SIDEWALKS_OUT}" \
  -e OUTPUT_CROSSINGS="${CROSSINGS_OUT}" \
  -e OUTPUT_KERBS="${KERBS_OUT}" \
  -e GET_BUILDINGS=${GET_BUILDINGS_ARG:-1} \
  -e FETCH_ADDRESSES=${FETCH_ADDR_ARG:-1} \
  -e STREET_CLASSES=${CLASSES_ARG:-10} \
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
from osm_sidewalkreator.processing.full_sidewalkreator_polygon_algorithm import FullSidewalkreatorPolygonAlgorithm
from qgis import processing

inp = os.environ["INPUT_POLYGON"]
inp = inp if inp.startswith("/") else f"/plugins/osm_sidewalkreator/{inp}"
sw_out = os.environ.get("OUTPUT_SIDEWALKS", "/plugins/osm_sidewalkreator/assets/test_outputs/sidewalks_polygon.geojson")
cr_out = os.environ.get("OUTPUT_CROSSINGS", "memory:")
kb_out = os.environ.get("OUTPUT_KERBS", "memory:")

def _normalize_out(p: str) -> str:
    if p.startswith("/") or p.startswith("memory:"):
        return p
    return f"/plugins/osm_sidewalkreator/{p}"

sw_out = _normalize_out(sw_out)
cr_out = _normalize_out(cr_out)
kb_out = _normalize_out(kb_out)
import os as _os
for p in (sw_out, cr_out, kb_out):
    if p.startswith("memory:"):
        continue
    d = _os.path.dirname(p)
    _os.makedirs(d, exist_ok=True)

# Dissolve features to unary union to ensure single AOI geometry when multiple are provided
layer = QgsVectorLayer(inp, "input_poly", "ogr")
if not layer.isValid() or layer.featureCount() == 0:
    raise SystemExit(f"Invalid or empty polygon layer: {inp}")
res = processing.run(
    "native:dissolve",
    {"INPUT": layer, "FIELD": [], "SEPARATE_DISJOINT": False, "OUTPUT": "memory:union_poly"},
)
union_layer = res["OUTPUT"] if res and res.get("OUTPUT") else layer

get_bld = os.getenv("GET_BUILDINGS", "1") in ("1","true","TRUE","yes","YES")
fetch_addr = os.getenv("FETCH_ADDRESSES", "1") in ("1","true","TRUE","yes","YES")
classes_env = os.getenv("STREET_CLASSES", "10")
try:
    street_classes = [int(x) for x in classes_env.split(",") if x.strip()!=""]
except Exception:
    street_classes = [10]

params = {
  FullSidewalkreatorPolygonAlgorithm.INPUT_POLYGON: union_layer,
  FullSidewalkreatorPolygonAlgorithm.TIMEOUT: 60,
  FullSidewalkreatorPolygonAlgorithm.FETCH_BUILDINGS_DATA: get_bld,
  FullSidewalkreatorPolygonAlgorithm.FETCH_ADDRESS_DATA: fetch_addr,
  FullSidewalkreatorPolygonAlgorithm.STREET_CLASSES: street_classes,
  FullSidewalkreatorPolygonAlgorithm.OUTPUT_SIDEWALKS: sw_out,
  FullSidewalkreatorPolygonAlgorithm.OUTPUT_CROSSINGS: cr_out,
  FullSidewalkreatorPolygonAlgorithm.OUTPUT_KERBS: kb_out,
}
print("Street class indices:", street_classes)
print(processing.run(FullSidewalkreatorPolygonAlgorithm(), params))
PY'

echo "Wrote: ${SIDEWALKS_OUT}"
