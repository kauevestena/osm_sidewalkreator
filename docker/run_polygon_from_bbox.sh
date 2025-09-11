#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${ROOT_DIR}/assets/test_outputs"
mkdir -p "${OUT_DIR}"

# Optional: allow overriding bbox via CLI: --bbox=min_lon,min_lat,max_lon,max_lat
BBOX_ARG=""
CLASSES_ARG=""
GET_BUILDINGS_ARG=""
FETCH_ADDR_ARG=""
for arg in "$@"; do
  case "$arg" in
    --bbox=*) BBOX_ARG="${arg#*=}" ;;
    --classes=*) CLASSES_ARG="${arg#*=}" ;;
    --no-buildings) GET_BUILDINGS_ARG="0" ;;
    --buildings) GET_BUILDINGS_ARG="1" ;;
    --no-addresses) FETCH_ADDR_ARG="0" ;;
    --addresses) FETCH_ADDR_ARG="1" ;;
  esac
done

if [ -n "$BBOX_ARG" ]; then
  IFS=',' read -r MIN_LON MIN_LAT MAX_LON MAX_LAT <<< "$BBOX_ARG"
else
  if command -v jq >/dev/null 2>&1; then
    MIN_LON=$(jq -r .min_lon "${ROOT_DIR}/assets/test_data/bbox.json")
    MIN_LAT=$(jq -r .min_lat "${ROOT_DIR}/assets/test_data/bbox.json")
    MAX_LON=$(jq -r .max_lon "${ROOT_DIR}/assets/test_data/bbox.json")
    MAX_LAT=$(jq -r .max_lat "${ROOT_DIR}/assets/test_data/bbox.json")
  else
    echo "jq not found; using python to parse bbox.json"
    MIN_LON=$(python3 - <<PY
import json,sys;d=json.load(open(sys.argv[1]));print(d['min_lon'])
PY
"${ROOT_DIR}/assets/test_data/bbox.json")
    MIN_LAT=$(python3 - <<PY
import json,sys;d=json.load(open(sys.argv[1]));print(d['min_lat'])
PY
"${ROOT_DIR}/assets/test_data/bbox.json")
    MAX_LON=$(python3 - <<PY
import json,sys;d=json.load(open(sys.argv[1]));print(d['max_lon'])
PY
"${ROOT_DIR}/assets/test_data/bbox.json")
    MAX_LAT=$(python3 - <<PY
import json,sys;d=json.load(open(sys.argv[1]));print(d['max_lat'])
PY
"${ROOT_DIR}/assets/test_data/bbox.json")
  fi
fi

export MIN_LON MIN_LAT MAX_LON MAX_LAT \
  STREET_CLASSES=${CLASSES_ARG:-10} \
  GET_BUILDINGS=${GET_BUILDINGS_ARG:-1} \
  FETCH_ADDRESSES=${FETCH_ADDR_ARG:-1}

docker run --rm \
  -e MIN_LON -e MIN_LAT -e MAX_LON -e MAX_LAT \
  -e STREET_CLASSES -e GET_BUILDINGS -e FETCH_ADDRESSES \
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
import os, json
from qgis.core import QgsApplication, QgsFeature, QgsFields, QgsField, QgsGeometry, QgsPointXY, QgsVectorLayer
from qgis.PyQt.QtCore import QVariant

QgsApplication.setPrefixPath("/usr", True)
app = QgsApplication([], False); app.initQgis()
from qgis.analysis import QgsNativeAlgorithms
QgsApplication.processingRegistry().addProvider(QgsNativeAlgorithms())
from osm_sidewalkreator.processing.protoblock_provider import ProtoblockProvider
QgsApplication.processingRegistry().addProvider(ProtoblockProvider())
from osm_sidewalkreator.processing.full_sidewalkreator_polygon_algorithm import FullSidewalkreatorPolygonAlgorithm
from qgis import processing

min_lon=float(os.environ["MIN_LON"]); min_lat=float(os.environ["MIN_LAT"]) 
max_lon=float(os.environ["MAX_LON"]); max_lat=float(os.environ["MAX_LAT"]) 
print(f"Using bbox: west={min_lon}, south={min_lat}, east={max_lon}, north={max_lat}")

# Build a polygon from bbox in EPSG:4326
vl = QgsVectorLayer("Polygon?crs=EPSG:4326", "bbox_polygon", "memory")
pr = vl.dataProvider()
f = QgsFeature()
ring = [QgsPointXY(min_lon, min_lat), QgsPointXY(max_lon, min_lat), QgsPointXY(max_lon, max_lat), QgsPointXY(min_lon, max_lat), QgsPointXY(min_lon, min_lat)]
f.setGeometry(QgsGeometry.fromPolygonXY([ring]))
pr.addFeature(f)
vl.updateExtents()

# Persist polygon for inspection
from qgis.core import QgsVectorFileWriter
_ = QgsVectorFileWriter.writeAsVectorFormat(vl, "/plugins/osm_sidewalkreator/assets/test_data/polygon_from_bbox.geojson", "utf-8", vl.crs(), "GeoJSON")

# Params
classes_env = os.getenv("STREET_CLASSES", "10")
try:
    street_classes = [int(x) for x in classes_env.split(",") if x.strip()!=""]
except Exception:
    street_classes = [10]
get_bld = os.getenv("GET_BUILDINGS", "1") in ("1","true","TRUE","yes","YES")
fetch_addr = os.getenv("FETCH_ADDRESSES", "1") in ("1","true","TRUE","yes","YES")
params = {
  "INPUT_POLYGON": vl,
  "TIMEOUT": 60,
  "FETCH_BUILDINGS_DATA": get_bld,
  "FETCH_ADDRESS_DATA": fetch_addr,
  "STREET_CLASSES": street_classes,
  "OUTPUT_SIDEWALKS": "/plugins/osm_sidewalkreator/assets/test_outputs/sidewalks_polygon_from_bbox.geojson",
  "OUTPUT_CROSSINGS": "/plugins/osm_sidewalkreator/assets/test_outputs/crossings_polygon_from_bbox.geojson",
  "OUTPUT_KERBS": "/plugins/osm_sidewalkreator/assets/test_outputs/kerbs_polygon_from_bbox.geojson"
}
print("Street class indices:", street_classes)
print(processing.run(FullSidewalkreatorPolygonAlgorithm(), params))
PY'

echo "Wrote: ${OUT_DIR}/sidewalks_polygon_from_bbox.geojson"
echo "Wrote: ${OUT_DIR}/crossings_polygon_from_bbox.geojson"
echo "Wrote: ${OUT_DIR}/kerbs_polygon_from_bbox.geojson"

