#!/usr/bin/env bash
set -euo pipefail

# Show help if requested
if [[ "${1:-}" == "--help" ]] || [[ "${1:-}" == "-h" ]]; then
  cat << EOF
Usage: $0 [OPTIONS]

OPTIONS:
  --classes=N[,N,...]     Street classes to process (comma-separated indices, default: 10)
  --min_lon=FLOAT         Minimum longitude (westernmost coordinate)
  --min_lat=FLOAT         Minimum latitude (southernmost coordinate)  
  --max_lon=FLOAT         Maximum longitude (easternmost coordinate)
  --max_lat=FLOAT         Maximum latitude (northernmost coordinate)
  --bbox=LON,LAT,LON,LAT  Bounding box as min_lon,min_lat,max_lon,max_lat
  --buildings             Include building data (default)
  --no-buildings          Skip building data
  --output, -o FILE       Output sidewalks file (OGR-supported path)
  --help, -h              Show this help message

COORDINATE PRIORITY:
  1. Individual coordinates (--min_lon, --min_lat, --max_lon, --max_lat)
  2. Bbox argument (--bbox=min_lon,min_lat,max_lon,max_lat)  
  3. bbox.json file in assets/test_data/

EXAMPLES:
  $0 --classes=10 --no-buildings
  $0 --min_lon=-49.3 --min_lat=-25.5 --max_lon=-49.29 --max_lat=-25.45 --classes=10,11
  $0 --bbox=-49.3,-25.5,-49.29,-25.45 --buildings

EOF
  exit 0
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${ROOT_DIR}/assets/test_outputs"
mkdir -p "${OUT_DIR}"

# CLI overrides
CLASSES_ARG=""
BBOX_ARG=""
GET_BUILDINGS_ARG=""
MIN_LON_ARG=""
MIN_LAT_ARG=""
MAX_LON_ARG=""
MAX_LAT_ARG=""
OUTPUT_PATH="${OUT_DIR}/sidewalks_bbox.geojson"

for arg in "$@"; do
  case "$arg" in
    --classes=*) CLASSES_ARG="${arg#*=}" ;;
    --bbox=*) BBOX_ARG="${arg#*=}" ;;
    --min_lon=*) MIN_LON_ARG="${arg#*=}" ;;
    --min_lat=*) MIN_LAT_ARG="${arg#*=}" ;;
    --max_lon=*) MAX_LON_ARG="${arg#*=}" ;;
    --max_lat=*) MAX_LAT_ARG="${arg#*=}" ;;
    --no-buildings) GET_BUILDINGS_ARG="0" ;;
    --buildings) GET_BUILDINGS_ARG="1" ;;
    -o|--output) shift; OUTPUT_PATH="${1:-}"; shift || true ;;
    --output=*) OUTPUT_PATH="${arg#*=}" ;;
  esac
done

# Determine coordinates in order of priority:
# 1. Individual coordinate arguments (--min_lat, etc.)
# 2. Bbox argument (--bbox=min_lon,min_lat,max_lon,max_lat)
# 3. bbox.json file

if [ -n "$MIN_LON_ARG" ] && [ -n "$MIN_LAT_ARG" ] && [ -n "$MAX_LON_ARG" ] && [ -n "$MAX_LAT_ARG" ]; then
  # Use individual coordinate arguments
  MIN_LON="$MIN_LON_ARG"
  MIN_LAT="$MIN_LAT_ARG"
  MAX_LON="$MAX_LON_ARG"
  MAX_LAT="$MAX_LAT_ARG"
  echo "Using individual coordinate arguments: min_lon=$MIN_LON, min_lat=$MIN_LAT, max_lon=$MAX_LON, max_lat=$MAX_LAT"
elif [ -n "$BBOX_ARG" ]; then
  # Use bbox argument  
  IFS=',' read -r MIN_LON MIN_LAT MAX_LON MAX_LAT <<< "$BBOX_ARG"
  echo "Using bbox argument: $BBOX_ARG"
elif command -v jq >/dev/null 2>&1; then
  # Use jq to parse bbox.json
  MIN_LON=$(jq -r .min_lon "${ROOT_DIR}/assets/test_data/bbox.json")
  MIN_LAT=$(jq -r .min_lat "${ROOT_DIR}/assets/test_data/bbox.json")
  MAX_LON=$(jq -r .max_lon "${ROOT_DIR}/assets/test_data/bbox.json")
  MAX_LAT=$(jq -r .max_lat "${ROOT_DIR}/assets/test_data/bbox.json")
  echo "Using bbox.json with jq: min_lon=$MIN_LON, min_lat=$MIN_LAT, max_lon=$MAX_LON, max_lat=$MAX_LAT"
else
  # Fallback to python parsing of bbox.json
  echo "jq not found; using python to parse bbox.json"
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
  echo "Parsed from bbox.json: min_lon=$MIN_LON, min_lat=$MIN_LAT, max_lon=$MAX_LON, max_lat=$MAX_LAT"
fi

export MIN_LON MIN_LAT MAX_LON MAX_LAT

docker run --rm \
  -e MIN_LON -e MIN_LAT -e MAX_LON -e MAX_LAT \
  -e GET_BUILDINGS=${GET_BUILDINGS_ARG:-1} \
  -e STREET_CLASSES=${CLASSES_ARG:-10} \
  -e OUTPUT_PATH="${OUTPUT_PATH}" \
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
from osm_sidewalkreator.processing.full_sidewalkreator_bbox_algorithm import FullSidewalkreatorBboxAlgorithm
from qgis import processing
# Env toggles and classes
classes_env = os.getenv("STREET_CLASSES", "10")
try:
    street_classes = [int(x) for x in classes_env.split(",") if x.strip()!=""]
except Exception:
    street_classes = [10]
min_lon=float(os.environ["MIN_LON"]); min_lat=float(os.environ["MIN_LAT"]) 
max_lon=float(os.environ["MAX_LON"]); max_lat=float(os.environ["MAX_LAT"]) 

# Ensure proper geographic bounds (westernmost < easternmost, southernmost < northernmost)
west_lon = min(min_lon, max_lon)   # most negative longitude (westernmost)
east_lon = max(min_lon, max_lon)   # least negative longitude (easternmost)
south_lat = min(min_lat, max_lat)  # most negative latitude (southernmost)
north_lat = max(min_lat, max_lat)  # least negative latitude (northernmost)

# WORKAROUND: QGIS swaps yMin and xMax internally, so we pre-swap them
# We want final result: xMin=west_lon, yMin=south_lat, xMax=east_lon, yMax=north_lat  
# QGIS swaps positions 1 and 2, so we provide: xMin, xMax, yMin, yMax
extent=f"{west_lon},{east_lon},{south_lat},{north_lat} [EPSG:4326]"
print(f"DOCKER DEBUG: Input coordinates - min_lon:{min_lon}, min_lat:{min_lat}, max_lon:{max_lon}, max_lat:{max_lat}")
print(f"DOCKER DEBUG: Normalized bounds - west:{west_lon}, south:{south_lat}, east:{east_lon}, north:{north_lat}")
print(f"DOCKER DEBUG: QGIS workaround extent: {extent}")
import sys; sys.stdout.flush()  # Force output to be visible
outp = os.environ.get("OUTPUT_PATH", "/plugins/osm_sidewalkreator/assets/test_outputs/sidewalks_bbox.geojson")
if not outp.startswith("/"):
    outp = f"/plugins/osm_sidewalkreator/{outp}"
import os as _os
_os.makedirs(_os.path.dirname(outp), exist_ok=True)
params={
  "INPUT_EXTENT": extent,
  "TIMEOUT": 90,
  "GET_BUILDING_DATA": os.getenv("GET_BUILDINGS", "1") in ("1","true","TRUE","yes","YES"),
  "STREET_CLASSES": street_classes,
  "OUTPUT_SIDEWALKS": outp
}
print("Street class indices:", street_classes)
print(processing.run(FullSidewalkreatorBboxAlgorithm(), params))
PY'

echo "Wrote: ${OUTPUT_PATH}"
