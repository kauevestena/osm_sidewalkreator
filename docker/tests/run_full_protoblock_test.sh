#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${ROOT_DIR}/assets/test_outputs"
mkdir -p "${OUT_DIR}"

INPUT_POLYGON="../assets/test_data/polygon_3857_proper.geojson"

echo "Running full protoblock test with CRS support:"
echo "  Input polygon: $INPUT_POLYGON"
echo ""

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
import os, sys
from qgis.core import QgsApplication, QgsProcessingContext, QgsProcessingFeedback

# Initialize QGIS
QgsApplication.setPrefixPath("/usr", True)
app = QgsApplication([], False)
app.initQgis()

from qgis.analysis import QgsNativeAlgorithms
QgsApplication.processingRegistry().addProvider(QgsNativeAlgorithms())

print("=== QGIS Initialized ===")

# Register our provider
try:
    from osm_sidewalkreator.processing.protoblock_provider import ProtoblockProvider
    provider = ProtoblockProvider()
    QgsApplication.processingRegistry().addProvider(provider)
    print("✓ ProtoblockProvider registered")
except Exception as e:
    print(f"✗ Failed to register provider: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test algorithm availability
alg_id = "sidewalkreator_algorithms_provider:generateprotoblocksfromosm"
try:
    alg = QgsApplication.processingRegistry().algorithmById(alg_id)
    if alg:
        print(f"✓ Algorithm found: {alg.displayName()}")
    else:
        print(f"✗ Algorithm not found: {alg_id}")
        sys.exit(1)
except Exception as e:
    print(f"✗ Error getting algorithm: {e}")
    sys.exit(1)

# Test createInstance specifically
try:
    instance = QgsApplication.processingRegistry().createAlgorithmById(alg_id)
    if instance:
        print(f"✓ Algorithm instance created successfully")
        print(f"  Name: {instance.name()}")
        print(f"  Display name: {instance.displayName()}")
        
        # Initialize parameters
        instance.initAlgorithm()
        params = instance.parameterDefinitions()
        print(f"  Parameters: {len(params)}")
        for p in params:
            print(f"    - {p.name()}: {p.description()}")
    else:
        print(f"✗ Failed to create algorithm instance")
        sys.exit(1)
except Exception as e:
    print(f"✗ Error creating algorithm instance: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n=== Algorithm Tests Passed ===")

# Now try to run the algorithm using processing.run
print("=== Running Algorithm ===")

input_polygon = os.environ.get("INPUT_POLYGON", "/plugins/osm_sidewalkreator/assets/test_data/polygon_3857.geojson")

print(f"Input polygon: {input_polygon}")

# Check if input file exists
abs_input = f"/plugins/osm_sidewalkreator/assets/test_data/polygon_3857_proper.geojson"
if not os.path.exists(abs_input):
    print(f"✗ Input file does not exist: {abs_input}")
    sys.exit(1)
print(f"✓ Input file exists: {abs_input}")

params = {
    "INPUT_POLYGON": abs_input,
    "TIMEOUT": 60,
    "OUTPUT_PROTOBLOCKS": "/plugins/osm_sidewalkreator/assets/test_outputs/protoblocks_3857_test.geojson"
}

print(f"Parameters: {params}")

try:
    from qgis import processing
    
    # Create a feedback object
    feedback = QgsProcessingFeedback()
    context = QgsProcessingContext()
    
    print("Calling processing.run...")
    result = processing.run(alg_id, params, context=context, feedback=feedback)
    print(f"✓ Processing completed!")
    print(f"Result: {result}")
    
except Exception as e:
    print(f"✗ Processing failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n=== SUCCESS: Algorithm executed successfully! ===")

PY'
