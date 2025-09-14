#!/usr/bin/env bash
set -euo pipefail

# Usage: ./run_missing_crossings_bbox.sh [--bbox=min_lon,min_lat,max_lon,max_lat] [--min_lon=F --min_lat=F --max_lon=F --max_lat=F] \
#        [--crs=EPSG:code] [--crossings-output FILE] [--kerbs-output FILE] [--timeout SECONDS] [--len M] [--kerb-percent P] [--min-shared-len M]
# Examples:
#   ./run_missing_crossings_bbox.sh
#   ./run_missing_crossings_bbox.sh --bbox=-49.289753,-25.466447,-49.284410,-25.462165 \
#     --crossings-output assets/test_outputs/missing_crossings_bbox.geojson \
#     --kerbs-output assets/test_outputs/missing_kerbs_bbox.geojson

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${ROOT_DIR}/assets/test_outputs"
mkdir -p "${OUT_DIR}"

INPUT_CRS="EPSG:4326"
MIN_LON=""; MIN_LAT=""; MAX_LON=""; MAX_LAT=""; BBOX_ARG=""

CROSSINGS_OUT_REL="assets/test_outputs/missing_crossings_bbox.geojson"
KERBS_OUT_REL="assets/test_outputs/missing_kerbs_bbox.geojson"
TIMEOUT=90
LEN=8
KERB_PERCENT=30
MIN_SHARED_LEN=5

for arg in "$@"; do
  case "$arg" in
    --min_lon=*) MIN_LON="${arg#*=}" ;;
    --min_lat=*) MIN_LAT="${arg#*=}" ;;
    --max_lon=*) MAX_LON="${arg#*=}" ;;
    --max_lat=*) MAX_LAT="${arg#*=}" ;;
    --bbox=*) BBOX_ARG="${arg#*=}" ;;
    --crs=*) INPUT_CRS="${arg#*=}" ;;
    --crossings-output=*) CROSSINGS_OUT_REL="${arg#*=}" ;;
    --kerbs-output=*) KERBS_OUT_REL="${arg#*=}" ;;
    --timeout=*) TIMEOUT="${arg#*=}" ;;
    --len=*) LEN="${arg#*=}" ;;
    --kerb-percent=*) KERB_PERCENT="${arg#*=}" ;;
    --min-shared-len=*) MIN_SHARED_LEN="${arg#*=}" ;;
    -h|--help)
      cat <<EOF
Usage: $0 [--bbox=xmin,ymin,xmax,ymax] [--min_lon=F --min_lat=F --max_lon=F --max_lat=F] \
          [--crs=EPSG:code] [--crossings-output FILE] [--kerbs-output FILE] [--timeout SECONDS] [--len M] [--kerb-percent P] [--min-shared-len M]
EOF
      exit 0 ;;
  esac
done

if [[ -n "$BBOX_ARG" ]] && [[ -z "$MIN_LON$MIN_LAT$MAX_LON$MAX_LAT" ]]; then
  IFS=',' read -r MIN_LON MIN_LAT MAX_LON MAX_LAT <<< "$BBOX_ARG"
fi

if [[ -z "$MIN_LON$MIN_LAT$MAX_LON$MAX_LAT" ]]; then
  if command -v jq >/dev/null 2>&1; then
    MIN_LON=$(jq -r .min_lon "${ROOT_DIR}/assets/test_data/bbox.json")
    MIN_LAT=$(jq -r .min_lat "${ROOT_DIR}/assets/test_data/bbox.json")
    MAX_LON=$(jq -r .max_lon "${ROOT_DIR}/assets/test_data/bbox.json")
    MAX_LAT=$(jq -r .max_lat "${ROOT_DIR}/assets/test_data/bbox.json")
  else
    MIN_LON=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d['min_lon'])" "${ROOT_DIR}/assets/test_data/bbox.json")
    MIN_LAT=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d['min_lat'])" "${ROOT_DIR}/assets/test_data/bbox.json")
    MAX_LON=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d['max_lon'])" "${ROOT_DIR}/assets/test_data/bbox.json")
    MAX_LAT=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d['max_lat'])" "${ROOT_DIR}/assets/test_data/bbox.json")
  fi
fi

export MIN_LON MIN_LAT MAX_LON MAX_LAT INPUT_CRS CROSSINGS_OUT_REL KERBS_OUT_REL TIMEOUT LEN KERB_PERCENT MIN_SHARED_LEN

echo "Running Draw Missing Crossings (bbox):"
echo "  BBOX:   ${MIN_LON},${MIN_LAT},${MAX_LON},${MAX_LAT}"
echo "  CRS:    ${INPUT_CRS}"
echo "  Out(CR): ${CROSSINGS_OUT_REL}"
echo "  Out(KB): ${KERBS_OUT_REL}"

docker run --rm \
  -e MIN_LON -e MIN_LAT -e MAX_LON -e MAX_LAT -e INPUT_CRS \
  -e CROSSINGS_OUT_REL -e KERBS_OUT_REL -e TIMEOUT -e LEN -e KERB_PERCENT -e MIN_SHARED_LEN \
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
try:
    from processing.core.Processing import Processing
    Processing.initialize()
except Exception:
    pass
from qgis import processing

min_lon=float(os.environ["MIN_LON"]); min_lat=float(os.environ["MIN_LAT"]) 
max_lon=float(os.environ["MAX_LON"]); max_lat=float(os.environ["MAX_LAT"]) 
input_crs = os.environ.get("INPUT_CRS", "EPSG:4326")

cr_out_rel = os.environ.get("CROSSINGS_OUT_REL")
kb_out_rel = os.environ.get("KERBS_OUT_REL")

def _norm(p: str) -> str:
    if p.startswith("/") or p.startswith("memory:"):
        return p
    return f"/plugins/osm_sidewalkreator/{p}"

cr_out = _norm(cr_out_rel)
kb_out = _norm(kb_out_rel)

import os as _os
for p in (cr_out, kb_out):
    if p.startswith("memory:"):
        continue
    _os.makedirs(_os.path.dirname(p), exist_ok=True)

# Build extent string in order xMin, xMax, yMin, yMax (QGIS parsing quirk workaround)
west_lon, east_lon = min_lon, max_lon
south_lat, north_lat = min_lat, max_lat
extent=f"{west_lon},{east_lon},{south_lat},{north_lat} [{input_crs}]"

params={
  "INPUT_EXTENT": extent,
  "TIMEOUT": int(os.environ.get("TIMEOUT","90")),
  "CROSSING_LENGTH": float(os.environ.get("LEN","8")),
  "KERB_OFFSET_PERCENT": int(os.environ.get("KERB_PERCENT","30")),
  "MIN_SHARED_EDGE_LEN": float(os.environ.get("MIN_SHARED_LEN","5")),
  "OUTPUT_CROSSINGS": cr_out,
  "OUTPUT_KERBS": kb_out,
}
print("Params:", params)
res = processing.run("sidewalkreator_algorithms_provider:drawmissingcrossingsfrombbox", params)
print("Result:", res)
PY'

echo "Crossings: ${CROSSINGS_OUT_REL}"
echo "Kerbs:     ${KERBS_OUT_REL}"
