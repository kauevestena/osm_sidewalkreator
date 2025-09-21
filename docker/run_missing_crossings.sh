#!/usr/bin/env bash
set -euo pipefail

# Usage: ./run_missing_crossings.sh [--bbox "min_lon,min_lat,max_lon,max_lat"]
# Examples:
#   ./run_missing_crossings.sh                                                    # Uses default bbox
#   ./run_missing_crossings.sh --bbox "-49.289753,-25.466447,-49.284410,-25.462165"  # Custom bbox

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/..)" && pwd)"
OUT_DIR="${ROOT_DIR}/assets/test_outputs"
mkdir -p "${OUT_DIR}"

# Default bbox from roadmap (Curitiba, Brazil area with known missing crossings)
DEFAULT_BBOX="-49.289753,-25.466447,-49.284410,-25.462165"
BBOX="${DEFAULT_BBOX}"
TIMEOUT=60
SEARCH_RADIUS_FACTOR=0.5

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --bbox)
      BBOX="$2"
      shift 2
      ;;
    --timeout)
      TIMEOUT="$2"
      shift 2
      ;;
    --search-radius-factor)
      SEARCH_RADIUS_FACTOR="$2"
      shift 2
      ;;
    -h|--help)
      echo "Usage: $0 [--bbox \"min_lon,min_lat,max_lon,max_lat\"] [--timeout SECONDS] [--search-radius-factor FACTOR]"
      echo ""
      echo "Options:"
      echo "  --bbox COORDS               Bounding box coordinates (default: Curitiba test area)"
      echo "  --timeout SECONDS           Timeout for OSM requests (default: 60)"
      echo "  --search-radius-factor FACTOR  Search radius factor (default: 0.5)"
      echo "  -h, --help                  Show this help message"
      echo ""
      echo "Default bbox covers a Curitiba area with known missing crossings:"
      echo "  ${DEFAULT_BBOX}"
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      echo "Use --help for usage information" >&2
      exit 1
      ;;
  esac
done

# Parse bbox components
IFS=',' read -r MIN_LON MIN_LAT MAX_LON MAX_LAT <<< "${BBOX}"

echo "Running Draw Missing Crossings (BBOX) algorithm:"
echo "  Bounding box: ${BBOX}"
echo "  Timeout: ${TIMEOUT}s"
echo "  Search radius factor: ${SEARCH_RADIUS_FACTOR}"
echo "  Output directory: ${OUT_DIR}"

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is required but not installed." >&2
    exit 1
fi

# Run the algorithm in Docker
docker run --rm \
  -v "${ROOT_DIR}:/plugins/osm_sidewalkreator" \
  -w / \
  qgis/qgis:latest \
  bash -lc "
set -euo pipefail
mkdir -p /tmp/runtime-qgis && chmod 700 /tmp/runtime-qgis
export XDG_RUNTIME_DIR=/tmp/runtime-qgis
export QGIS_PREFIX_PATH=/usr
export QGIS_PLUGINPATH=/usr/lib/qgis/plugins
export PYTHONPATH=/usr/share/qgis/python:/usr/share/qgis/python/plugins:/plugins:/plugins/osm_sidewalkreator
export QT_QPA_PLATFORM=offscreen
export PIP_BREAK_SYSTEM_PACKAGES=1

# Install additional dependencies if needed
apt-get update -qq
apt-get install -y python3-gdal unzip >/dev/null
pip install -r /plugins/osm_sidewalkreator/docker/requirements.txt

python3 - <<PY
import os
from qgis.core import QgsApplication, QgsRectangle, QgsCoordinateReferenceSystem
QgsApplication.setPrefixPath(\"/usr\", True)
app = QgsApplication([], False)
app.initQgis()

from qgis.analysis import QgsNativeAlgorithms
QgsApplication.processingRegistry().addProvider(QgsNativeAlgorithms())

from osm_sidewalkreator.processing.protoblock_provider import ProtoblockProvider
QgsApplication.processingRegistry().addProvider(ProtoblockProvider())

from qgis import processing

# Set up parameters
params = {
    'INPUT_EXTENT': '${MIN_LON},${MIN_LAT},${MAX_LON},${MAX_LAT} [EPSG:4326]',
    'TIMEOUT': ${TIMEOUT},
    'SEARCH_RADIUS_FACTOR': ${SEARCH_RADIUS_FACTOR},
    'OUTPUT_CROSSINGS': '/plugins/osm_sidewalkreator/assets/test_outputs/missing_crossings.geojson',
    'OUTPUT_KERBS': '/plugins/osm_sidewalkreator/assets/test_outputs/missing_kerbs.geojson',
    'OUTPUT_PROTOBLOCKS_DEBUG': '/plugins/osm_sidewalkreator/assets/test_outputs/protoblocks_debug.geojson'
}

print('Starting Draw Missing Crossings algorithm...')
print(f'Parameters: {params}')

try:
    result = processing.run('sidewalkreator_algorithms_provider:draw_missing_crossings_bbox', params)
    print('Algorithm completed successfully!')
    print(f'Results: {result}')
except Exception as e:
    print(f'Error running algorithm: {e}')
    import traceback
    traceback.print_exc()
    exit(1)

app.exitQgis()
PY
"

echo ""
echo "Algorithm completed. Check outputs in:"
echo "  Crossings: ${OUT_DIR}/missing_crossings.geojson"
echo "  Kerbs: ${OUT_DIR}/missing_kerbs.geojson"
echo "  Debug protoblocks: ${OUT_DIR}/protoblocks_debug.geojson"