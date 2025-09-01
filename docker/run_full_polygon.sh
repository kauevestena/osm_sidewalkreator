#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${ROOT_DIR}/assets/test_outputs"
IN_POLY="${ROOT_DIR}/assets/test_data/polygon.geojson"
mkdir -p "${OUT_DIR}"

# CLI overrides
CLASSES_ARG=""
GET_BUILDINGS_ARG=""
FETCH_ADDR_ARG=""
for arg in "$@"; do
  case "$arg" in
    --classes=*) CLASSES_ARG="${arg#*=}" ;;
    --no-buildings) GET_BUILDINGS_ARG="0" ;;
    --buildings) GET_BUILDINGS_ARG="1" ;;
    --no-addresses) FETCH_ADDR_ARG="0" ;;
    --addresses) FETCH_ADDR_ARG="1" ;;
  esac
done

docker run --rm \
  -v "${ROOT_DIR}:/plugins/osm_sidewalkreator" \
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
from qgis.core import QgsApplication
QgsApplication.setPrefixPath("/usr", True)
app=QgsApplication([], False); app.initQgis()
from qgis.analysis import QgsNativeAlgorithms
QgsApplication.processingRegistry().addProvider(QgsNativeAlgorithms())
from osm_sidewalkreator.processing.protoblock_provider import ProtoblockProvider
QgsApplication.processingRegistry().addProvider(ProtoblockProvider())
from osm_sidewalkreator.processing.full_sidewalkreator_polygon_algorithm import FullSidewalkreatorPolygonAlgorithm
from qgis import processing
# Env toggles
get_bld = os.getenv("GET_BUILDINGS", "1") in ("1","true","TRUE","yes","YES")
fetch_addr = os.getenv("FETCH_ADDRESSES", "1") in ("1","true","TRUE","yes","YES")
classes_env = os.getenv("STREET_CLASSES", "10")
try:
    street_classes = [int(x) for x in classes_env.split(",") if x.strip()!=""]
except Exception:
    street_classes = [10]
params = {
  "INPUT_POLYGON": "/plugins/osm_sidewalkreator/assets/test_data/polygon.geojson",
  "TIMEOUT": 60,
  "FETCH_BUILDINGS_DATA": get_bld,
  "FETCH_ADDRESS_DATA": fetch_addr,
  "STREET_CLASSES": street_classes,
  "OUTPUT_SIDEWALKS": "/plugins/osm_sidewalkreator/assets/test_outputs/sidewalks_polygon.geojson",
  "OUTPUT_CROSSINGS": "/plugins/osm_sidewalkreator/assets/test_outputs/crossings_polygon.geojson",
  "OUTPUT_KERBS": "/plugins/osm_sidewalkreator/assets/test_outputs/kerbs_polygon.geojson"
}
print("Street class indices:", street_classes)
print(processing.run(FullSidewalkreatorPolygonAlgorithm(), params))
PY'

echo "Wrote: ${OUT_DIR}/sidewalks_polygon.geojson"
