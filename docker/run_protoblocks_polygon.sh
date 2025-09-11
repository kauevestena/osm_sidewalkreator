#!/usr/bin/env bash
set -euo pipefail

# Usage: ./run_protoblocks_polygon.sh [input_polygon.geojson] [input_crs]
# Examples:
#   ./run_protoblocks_polygon.sh                                    # Uses default polygon.geojson with EPSG:4326
#   ./run_protoblocks_polygon.sh my_polygon.geojson                 # Uses my_polygon.geojson with EPSG:4326
#   ./run_protoblocks_polygon.sh my_polygon.geojson EPSG:3857       # Uses my_polygon.geojson with EPSG:3857

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${ROOT_DIR}/assets/test_outputs"

# Set input parameters with defaults
INPUT_POLYGON="${1:-${ROOT_DIR}/assets/test_data/polygon.geojson}"
INPUT_CRS="${2:-EPSG:4326}"

# Check if input file exists
if [[ ! -f "$INPUT_POLYGON" ]]; then
    echo "Error: Input polygon file not found: $INPUT_POLYGON"
    echo "Usage: $0 [input_polygon.geojson] [input_crs]"
    exit 1
fi

mkdir -p "${OUT_DIR}"

echo "Running protoblocks generation with:"
echo "  Input polygon: $INPUT_POLYGON"
echo "  Input CRS: $INPUT_CRS"
echo "  Output directory: $OUT_DIR"

docker run --rm \
  -v "${ROOT_DIR}:/plugins/osm_sidewalkreator" \
  -e INPUT_POLYGON="${INPUT_POLYGON}" \
  -e INPUT_CRS="${INPUT_CRS}" \
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
from osm_sidewalkreator.processing.protoblock_algorithm import ProtoblockAlgorithm
from qgis import processing

input_polygon = "/plugins/osm_sidewalkreator/assets/test_data/polygon.geojson"
input_crs = os.environ.get("INPUT_CRS", "EPSG:4326")

print(f"Processing polygon: {input_polygon}")
print(f"Input CRS: {input_crs}")

params = {
  "INPUT_POLYGON": input_polygon,
  "INPUT_CRS": input_crs,
  "TIMEOUT": 60,
  "OUTPUT_PROTOBLOCKS": "/plugins/osm_sidewalkreator/assets/test_outputs/protoblocks_polygon.geojson"
}
result = processing.run(ProtoblockAlgorithm(), params)
print("Processing completed successfully!")
print(f"Output: {result}")
PY'

echo "Wrote: ${OUT_DIR}/protoblocks_polygon.geojson"
echo "Command completed successfully with CRS: $INPUT_CRS"
