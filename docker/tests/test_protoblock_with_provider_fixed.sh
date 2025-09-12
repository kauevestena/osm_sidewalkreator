#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${ROOT_DIR}/assets/test_outputs"
mkdir -p "${OUT_DIR}"

INPUT_POLYGON="../assets/test_data/polygon_3857.geojson"

echo "Testing protoblock algorithm with provider registration:"
echo "  Input polygon: $INPUT_POLYGON" 

docker run --rm \
  -v "${ROOT_DIR}:/plugins/osm_sidewalkreator" \
  -e INPUT_POLYGON="${INPUT_POLYGON}" \
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
from qgis.core import QgsApplication, QgsProcessingContext
QgsApplication.setPrefixPath("/usr", True)
app = QgsApplication([], False)
app.initQgis()

from qgis.analysis import QgsNativeAlgorithms
QgsApplication.processingRegistry().addProvider(QgsNativeAlgorithms())

print("Registering protoblock provider...")

try:
    from osm_sidewalkreator.processing.protoblock_provider import ProtoblockProvider
    provider = ProtoblockProvider()
    QgsApplication.processingRegistry().addProvider(provider)
    print("✓ Provider registered successfully")
    
    # Try to get our specific algorithm
    alg_id = "sidewalkreator_algorithms_provider:generateprotoblocksfromosm"
    alg = QgsApplication.processingRegistry().algorithmById(alg_id)
    if alg:
        print(f"✓ Found algorithm: {alg_id}")
        print(f"  Display name: {alg.displayName()}")
        
        # Test algorithm creation
        instance = QgsApplication.processingRegistry().createAlgorithmById(alg_id)
        if instance:
            print("✓ Algorithm instance created successfully")
        else:
            print("✗ Failed to create algorithm instance")
    else:
        print(f"✗ Algorithm not found: {alg_id}")
        
    print("Provider registration test completed!")
    
except Exception as e:
    import traceback
    print(f"✗ Error: {e}")
    traceback.print_exc()

PY'
