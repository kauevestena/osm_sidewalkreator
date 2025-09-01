#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${ROOT_DIR}/assets/test_outputs"
IN_POLY="${ROOT_DIR}/assets/test_data/polygon.geojson"
mkdir -p "${OUT_DIR}"

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
from qgis.core import QgsApplication
QgsApplication.setPrefixPath("/usr", True)
app=QgsApplication([], False); app.initQgis()
from qgis.analysis import QgsNativeAlgorithms
QgsApplication.processingRegistry().addProvider(QgsNativeAlgorithms())
from osm_sidewalkreator.processing.protoblock_provider import ProtoblockProvider
QgsApplication.processingRegistry().addProvider(ProtoblockProvider())
from osm_sidewalkreator.processing.protoblock_algorithm import ProtoblockAlgorithm
from qgis import processing
params = {
  "INPUT_POLYGON": "/plugins/osm_sidewalkreator/assets/test_data/polygon.geojson",
  "TIMEOUT": 60,
  "OUTPUT_PROTOBLOCKS": "/plugins/osm_sidewalkreator/assets/test_outputs/protoblocks_polygon.geojson"
}
print(processing.run(ProtoblockAlgorithm(), params))
PY'

echo "Wrote: ${OUT_DIR}/protoblocks_polygon.geojson"
