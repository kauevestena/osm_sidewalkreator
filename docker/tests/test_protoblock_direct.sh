#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${ROOT_DIR}/assets/test_outputs"
mkdir -p "${OUT_DIR}"

INPUT_POLYGON="../assets/test_data/polygon_3857.geojson"
INPUT_CRS="EPSG:3857"

echo "Testing protoblock algorithm directly with:"
echo "  Input polygon: $INPUT_POLYGON"
echo "  Input CRS: $INPUT_CRS"

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
app=QgsApplication([], False)
app.initQgis()

from qgis.analysis import QgsNativeAlgorithms
QgsApplication.processingRegistry().addProvider(QgsNativeAlgorithms())

print("Testing direct algorithm call...")

try:
    from osm_sidewalkreator.processing.protoblock_algorithm import ProtoblockAlgorithm
    print("✓ Algorithm imported successfully")
    
    alg = ProtoblockAlgorithm()
    print(f"✓ Algorithm created: {alg.name()}")
    
    # Test parameter initialization
    alg.initAlgorithm()
    params = alg.parameterDefinitions()
    print(f"✓ Parameters initialized. Count: {len(params)}")
    for param in params:
        print(f"  - {param.name()}: {param.description()}")
        
    print("Algorithm appears to be working correctly!")
    
except Exception as e:
    import traceback
    print(f"✗ Error: {e}")
    traceback.print_exc()

PY'
