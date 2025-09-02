#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${ROOT_DIR}/assets/test_outputs"
mkdir -p "${OUT_DIR}"

if command -v jq >/dev/null 2>&1; then
  MIN_LON=$(jq -r .min_lon "${ROOT_DIR}/assets/test_data/bbox.json")
  MIN_LAT=$(jq -r .min_lat "${ROOT_DIR}/assets/test_data/bbox.json")
  MAX_LON=$(jq -r .max_lon "${ROOT_DIR}/assets/test_data/bbox.json")
  MAX_LAT=$(jq -r .max_lat "${ROOT_DIR}/assets/test_data/bbox.json")
else
  echo "jq not found; using defaults from bbox.json"
  MIN_LON=$(python3 - <<PY
import json,sys
d=json.load(open(sys.argv[1]));print(d['min_lon'])
PY
"${ROOT_DIR}/assets/test_data/bbox.json")
  MIN_LAT=$(python3 - <<PY
import json,sys
d=json.load(open(sys.argv[1]));print(d['min_lat'])
PY
"${ROOT_DIR}/assets/test_data/bbox.json")
  MAX_LON=$(python3 - <<PY
import json,sys
d=json.load(open(sys.argv[1]));print(d['max_lon'])
PY
"${ROOT_DIR}/assets/test_data/bbox.json")
  MAX_LAT=$(python3 - <<PY
import json,sys
d=json.load(open(sys.argv[1]));print(d['max_lat'])
PY
"${ROOT_DIR}/assets/test_data/bbox.json")
fi

export MIN_LON MIN_LAT MAX_LON MAX_LAT

docker run --rm \
  -e MIN_LON -e MIN_LAT -e MAX_LON -e MAX_LAT \
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
from osm_sidewalkreator.processing.protoblock_bbox_algorithm import ProtoblockBboxAlgorithm
from qgis import processing
min_lon=float(os.environ["MIN_LON"]); min_lat=float(os.environ["MIN_LAT"]) 
max_lon=float(os.environ["MAX_LON"]); max_lat=float(os.environ["MAX_LAT"]) 
# Use same format as run_full_bbox.sh to work around QGIS coordinate swapping
west_lon, east_lon = min_lon, max_lon
south_lat, north_lat = min_lat, max_lat
extent=f"{west_lon},{east_lon},{south_lat},{north_lat} [EPSG:4326]"
params={
  "EXTENT": extent,
  "TIMEOUT": 60,
  "OUTPUT_PROTOBLOCKS": "/plugins/osm_sidewalkreator/assets/test_outputs/protoblocks_bbox.geojson"
}
print(processing.run(ProtoblockBboxAlgorithm(), params))
PY'

echo "Wrote: ${OUT_DIR}/protoblocks_bbox.geojson"
